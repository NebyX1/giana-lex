from datetime import datetime
from hashlib import sha256
from uuid import UUID, uuid4

from app.extensions import db
from legal.agents.intent_compiler import IntentCompiler
from legal.cases.repository import LegalCaseRepository
from legal.domain.enums import (
    CaseCommandType, CaseEventType, CommandStatus, LegalCaseState,
    WorkflowRunStatus, WorkflowStepStatus,
)
from legal.domain.errors import ConcurrentCaseUpdateError, WorkflowConflictError
from legal.domain.events import NewCaseEvent
from legal.domain.models import IntakeIntent, LegalIssue, VerifiedAuthorityInput
from legal.drafting.service import compliance_review, compose_draft
from legal.evidence.service import citation_gate, create_corpus_snapshot, verify_and_record
from legal.infrastructure.models import (
    CaseCommandRecord, DraftVersionRecord, FactAssertionRecord, FormInstanceRecord,
    AgentRunRecord, HumanTaskRecord, LegalCaseRecord, ReviewFindingRecord,
    IntakeIntentRecord, IntakeQuestionRequestRecord, PrecedentSearchRunRecord,
    WorkflowPackVersionRecord, WorkflowRunRecord, WorkflowStepRunRecord,
)
from legal.intake.service import create_form, persist_intake_intent, submit_form
from legal.precedents.service import select_precedent
from legal.research.service import AuthorityProvider, NoAuthorityProvider, plan_issues
from legal.workflows.loader import WorkflowPackRegistry


INITIAL_WORKFLOW_ID = "legal.durable-initial"
INITIAL_WORKFLOW_VERSION = 1
INITIAL_STEPS = ((1, "durability_checkpoint"),)
DRAFTING_START_STEPS = (
    (1, "intent_compile"), (2, "workflow_select"),
    (3, "precedent_search"), (4, "form_compile"),
)
CONFIRM_STEPS = (
    (1, "confirm_facts"), (2, "issue_plan"), (3, "research"), (4, "verify_evidence"),
    (5, "draft"), (6, "compliance"), (7, "citation_gate"),
)


class DurableWorkflowEngine:
    """Database-backed legal workflow. Specialists return data; this engine owns transitions."""

    def __init__(
        self, repository: LegalCaseRepository | None = None, lock_retries: int = 3,
        authority_provider: AuthorityProvider | None = None, intent_compiler: IntentCompiler | None = None,
    ):
        self.repository = repository or LegalCaseRepository()
        self.lock_retries = lock_retries
        self.authority_provider = authority_provider or NoAuthorityProvider()
        self.intent_compiler = intent_compiler or IntentCompiler()
        self.registry = WorkflowPackRegistry()

    def process_command(self, command_id: UUID) -> None:
        command = db.session.get(CaseCommandRecord, str(command_id))
        if command is None:
            raise ValueError("Workflow command not found")
        if command.status == CommandStatus.COMPLETED.value:
            return
        command.status = CommandStatus.PROCESSING.value
        command.started_at = command.started_at or datetime.utcnow()
        command.attempts += 1
        db.session.commit()
        try:
            command_type = CaseCommandType(command.command_type)
            if command_type == CaseCommandType.START_LEGAL_WORKFLOW:
                self._start_or_resume(command)
            elif command_type == CaseCommandType.SUBMIT_FORM_ANSWERS:
                self._run_signal(command, ((1, "submit_form"),))
            elif command_type == CaseCommandType.CONFIRM_FACTS:
                self._run_signal(command, CONFIRM_STEPS)
            elif command_type == CaseCommandType.SUBMIT_HUMAN_REVIEW:
                self._run_signal(command, ((1, "human_review"),))
            elif command_type == CaseCommandType.RETRY_WORKFLOW_STEP:
                self._retry(command)
            elif command_type == CaseCommandType.CANCEL_WORKFLOW:
                self._cancel(command)
            else:
                raise ValueError(f"Unsupported legal workflow command: {command.command_type}")
            command = db.session.get(CaseCommandRecord, str(command_id))
            command.status = CommandStatus.COMPLETED.value
            command.completed_at = datetime.utcnow()
            command.error = None
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            run = WorkflowRunRecord.query.filter_by(command_id=str(command_id)).first()
            if run is not None and run.status == WorkflowRunStatus.RUNNING.value:
                self._record_failure(run, command, exc)
            command = db.session.get(CaseCommandRecord, str(command_id))
            if command is not None:
                command.status = CommandStatus.FAILED.value
                command.error = str(exc)[:2000]
                command.completed_at = datetime.utcnow()
                db.session.commit()
            raise

    def resume_incomplete_runs(self, limit: int = 100) -> int:
        runs = WorkflowRunRecord.query.filter(
            WorkflowRunRecord.status.in_([WorkflowRunStatus.PENDING.value, WorkflowRunStatus.RUNNING.value])
        ).order_by(WorkflowRunRecord.started_at.asc()).limit(limit).all()
        for run in runs:
            command = db.session.get(CaseCommandRecord, run.command_id)
            if command is not None:
                self._execute_run(run, command.actor_user_id, UUID(command.id))
                command.status = CommandStatus.COMPLETED.value
                command.completed_at = datetime.utcnow()
                command.error = None
                db.session.commit()
        return len(runs)

    def _start_or_resume(self, command: CaseCommandRecord) -> None:
        active = WorkflowRunRecord.query.filter_by(
            case_id=command.case_id, status=WorkflowRunStatus.RUNNING.value
        ).first()
        if active is not None and active.command_id != command.id:
            raise WorkflowConflictError("A workflow is already running for this case")
        run = WorkflowRunRecord.query.filter_by(command_id=command.id).first()
        if run is None:
            case = db.session.get(LegalCaseRecord, command.case_id)
            steps = DRAFTING_START_STEPS if case.task_family == "resolution_drafting" else INITIAL_STEPS
            workflow_id = "legal.resolution-drafting" if steps == DRAFTING_START_STEPS else INITIAL_WORKFLOW_ID
            run = self._create_run(command, workflow_id, steps)
        elif run.status == WorkflowRunStatus.FAILED.value:
            self._reset_failed_run(run)
            snapshot = self.repository.get_snapshot(command.case_id, command.actor_user_id)
            self._append(command.case_id, UUID(command.id), command.actor_user_id, CaseEventType.WORKFLOW_RUN_RETRIED, {
                "run_id": run.id,
                "new_state": snapshot.state_before_failure.value if snapshot.state_before_failure else None,
            }, UUID(run.id))
        self._execute_run(run, command.actor_user_id, UUID(command.id))

    def _run_signal(self, command: CaseCommandRecord, steps) -> None:
        run = WorkflowRunRecord.query.filter_by(command_id=command.id).first()
        if run is None:
            run = self._create_run(command, f"legal.{command.command_type}", steps)
        self._execute_run(run, command.actor_user_id, UUID(command.id))

    def _create_run(self, command, workflow_id: str, steps) -> WorkflowRunRecord:
        run = WorkflowRunRecord(
            id=str(uuid4()), case_id=command.case_id, command_id=command.id,
            workflow_id=workflow_id, workflow_version=1, status=WorkflowRunStatus.RUNNING.value,
            attempt=1, current_step=steps[0][1],
        )
        db.session.add(run)
        for order, step_name in steps:
            db.session.add(WorkflowStepRunRecord(
                id=str(uuid4()), run_id=run.id, case_id=command.case_id, step_name=step_name,
                step_order=order, status=WorkflowStepStatus.PENDING.value, attempt=1, input_json={},
            ))
        db.session.commit()
        self._append(command.case_id, UUID(command.id), command.actor_user_id,
                     CaseEventType.WORKFLOW_RUN_STARTED, {"run_id": run.id}, UUID(run.id))
        return run

    def _execute_run(self, run: WorkflowRunRecord, actor_user_id: int, command_id: UUID) -> None:
        steps = WorkflowStepRunRecord.query.filter_by(run_id=run.id).order_by(
            WorkflowStepRunRecord.step_order.asc()
        ).all()
        continue_run = True
        for step in steps:
            db.session.refresh(run)
            if run.cancel_requested_at is not None:
                self._mark_cancelled(run, command_id, actor_user_id, "Cancellation requested")
                return
            if step.status == WorkflowStepStatus.COMPLETED.value:
                continue
            if not continue_run:
                step.status = WorkflowStepStatus.CANCELLED.value
                continue
            step.status = WorkflowStepStatus.RUNNING.value
            step.started_at = datetime.utcnow()
            run.current_step = step.step_name
            db.session.commit()
            output, continue_run = self._execute_step(step, run, actor_user_id, command_id)
            step.output_json = output
            step.status = WorkflowStepStatus.COMPLETED.value
            step.completed_at = datetime.utcnow()
            db.session.commit()
            self._append(run.case_id, command_id, actor_user_id, CaseEventType.WORKFLOW_STEP_COMPLETED, {
                "run_id": run.id, "step_run_id": step.id, "step_name": step.step_name, "attempt": step.attempt,
            }, UUID(run.id))
        run.status = WorkflowRunStatus.COMPLETED.value
        run.current_step = None
        run.completed_at = datetime.utcnow()
        db.session.commit()
        self._append(run.case_id, command_id, actor_user_id, CaseEventType.WORKFLOW_RUN_COMPLETED,
                     {"run_id": run.id}, UUID(run.id))

    def _execute_step(self, step, run, actor_user_id, command_id) -> tuple[dict, bool]:
        case = db.session.get(LegalCaseRecord, run.case_id)
        command = db.session.get(CaseCommandRecord, run.command_id)
        name = step.step_name
        if name == "durability_checkpoint":
            return {"checkpoint": "persisted", "workflow_version": run.workflow_version}, True
        if name == "intent_compile":
            self._append(case.id, command_id, actor_user_id, CaseEventType.INTAKE_PLANNING_STARTED, {
                "run_id": run.id, "step_run_id": step.id,
            }, UUID(run.id))
            intent_record = IntakeIntentRecord.query.filter_by(case_id=case.id).first()
            if intent_record is None:
                intent = self.intent_compiler.compile(case.title, declared_family=case.task_family)
                intent_record = persist_intake_intent(
                    case.id, case.title, intent, run_id=run.id, step_run_id=step.id,
                )
            else:
                intent = IntakeIntent.model_validate(intent_record.intent_json)
                intent_record.run_id = intent_record.run_id or run.id
                intent_record.step_run_id = intent_record.step_run_id or step.id
            self._record_agent_run(
                case, "INTENT_COMPILER", intent.model_dump(mode="json"), None,
                provider=intent.provider or intent.classifier, model=intent.model,
                output_schema="IntakeIntent",
            )
            self._append(case.id, command_id, actor_user_id, CaseEventType.INTAKE_INTENT_PERSISTED, {
                "intent_id": intent_record.id,
                "request_text_hash": intent_record.request_text_hash,
                "classifier": intent_record.classifier,
                "classifier_version": intent_record.classifier_version,
            }, UUID(run.id))
            self._append_state(run, command_id, actor_user_id, CaseEventType.INTENT_COMPILED,
                               LegalCaseState.INTENT_COMPILED, {
                                   "intent_id": intent_record.id,
                                   "classifier": intent.classifier,
                                   "classification_basis": intent.classification_basis,
                               })
            return intent.model_dump(mode="json"), True
        if name == "workflow_select":
            intent = IntakeIntent.model_validate(self._step_output(run.id, "intent_compile"))
            loaded = self.registry.get(
                intent.selected_workflow_id or "resolution.generic",
                intent.selected_workflow_version,
            )
            self._persist_pack(loaded)
            case.workflow_pack_id = loaded.pack.id
            case.workflow_pack_version = loaded.pack.version
            case.resolution_type = intent.subtype
            db.session.commit()
            self._append_state(run, command_id, actor_user_id, CaseEventType.WORKFLOW_SELECTED,
                               LegalCaseState.WORKFLOW_SELECTED, {"workflow_pack_id": loaded.pack.id,
                               "workflow_pack_version": loaded.pack.version, "checksum": loaded.checksum})
            return {"pack_id": loaded.pack.id, "version": loaded.pack.version, "checksum": loaded.checksum}, True
        if name == "precedent_search":
            self._append_state(run, command_id, actor_user_id, CaseEventType.PRECEDENT_SEARCH_STARTED,
                               LegalCaseState.SEARCHING_PRECEDENTS, {})
            pack = self._pack(case)
            intent_record = IntakeIntentRecord.query.filter_by(case_id=case.id).one()
            intent = IntakeIntent.model_validate(intent_record.intent_json)
            selection = select_precedent(
                case.id, pack, intent, workflow_run_id=run.id, step_run_id=step.id,
            )
            search = PrecedentSearchRunRecord.query.filter_by(case_id=case.id, run_id=run.id).order_by(
                PrecedentSearchRunRecord.started_at.desc()
            ).first()
            self._record_agent_run(case, "PRECEDENT_EXPLORER", {
                "search_run_id": search.id, "status": search.status,
                "searched_count": search.searched_count, "match_label": search.match_label,
                "selected_example_version_id": search.selected_example_version_id,
            }, None, provider="deterministic", output_schema="PrecedentSearchResult")
            self._append(case.id, command_id, actor_user_id, CaseEventType.PRECEDENT_SEARCH_COMPLETED, {
                "search_run_id": search.id,
                "status": search.status,
                "searched_count": search.searched_count,
                "match_label": search.match_label,
                "errors": search.errors_json,
            }, UUID(run.id))
            if selection.primary_example_version_id is None:
                self._append(case.id, command_id, actor_user_id, CaseEventType.PRECEDENT_NOT_FOUND, {
                    "search_run_id": search.id, "searched_count": search.searched_count,
                    "fallback_reason": search.fallback_reason,
                }, UUID(run.id))
            event = CaseEventType.PRECEDENT_SELECTED if selection.primary_example_version_id else CaseEventType.PRECEDENT_FALLBACK_SELECTED
            self._append_state(run, command_id, actor_user_id, event, LegalCaseState.PRECEDENT_SELECTED, {
                "selection_id": selection.id, "primary_example_version_id": selection.primary_example_version_id,
                "search_run_id": search.id, "match_type": selection.match_type,
                "similarities": search.similarities_json, "differences": selection.differences_json,
                "fallback_reason": selection.fallback_reason,
                "authority_notice": "Referencias del antecedente pendientes de verificacion.",
            })
            return {"selection_id": selection.id}, True
        if name == "form_compile":
            form = create_form(
                case.id, self._pack(case), workflow_run_id=run.id, step_run_id=step.id,
            )
            question = IntakeQuestionRequestRecord.query.filter_by(case_id=case.id, workflow_run_id=run.id).order_by(
                IntakeQuestionRequestRecord.created_at.desc()
            ).first()
            self._record_agent_run(case, "QUESTION_PLANNER", {
                "question_request_id": question.id,
                "status": question.status,
                "question_keys": [item["key"] for item in question.questions_json],
            }, None, provider="deterministic", output_schema="IntakeQuestionRequest")
            self._append(case.id, command_id, actor_user_id, CaseEventType.INTAKE_QUESTIONS_COMPILED, {
                "question_request_id": question.id,
                "question_count": len(question.questions_json),
                "status": question.status,
            }, UUID(run.id))
            if form is None:
                self._append_state(run, command_id, actor_user_id, CaseEventType.INTAKE_QUESTION_ANSWERED,
                                   LegalCaseState.VALIDATING_FACTS, {
                                       "question_request_id": question.id, "reason": "no_missing_required_facts",
                                   })
                return {"form_id": None, "question_request_id": question.id, "missing_fields": []}, True
            self._record_agent_run(case, "FORM_COMPILER", {
                "form_id": form.id, "question_request_id": question.id,
                "workflow_pack_id": form.workflow_pack_id,
                "workflow_pack_version": form.workflow_pack_version,
            }, None, provider="deterministic", output_schema="FormInstance")
            self._append_state(run, command_id, actor_user_id, CaseEventType.FORM_CREATED,
                                LegalCaseState.FORM_READY, {"form_id": form.id, "form_version": form.version})
            waiting_payload = {
                "form_id": form.id, "question_request_id": question.id,
                "missing_fields": [item["key"] for item in question.questions_json if item.get("required")],
            }
            self._append(case.id, command_id, actor_user_id, CaseEventType.INTAKE_QUESTION_REQUESTED,
                         waiting_payload, UUID(run.id))
            self._append_state(run, command_id, actor_user_id, CaseEventType.INTAKE_WAITING_USER,
                               LegalCaseState.AWAITING_FACTS, waiting_payload)
            return {"form_id": form.id, "question_request_id": question.id, "schema": form.schema_json}, True
        if name == "submit_form":
            form = db.session.get(FormInstanceRecord, command.payload_json["form_id"])
            if form is None or form.case_id != case.id:
                raise WorkflowConflictError("Form does not belong to this case")
            errors = submit_form(form, self._pack(case), command.payload_json.get("answers", {}),
                                 bool(command.payload_json.get("partial", False)))
            complete = form.status == "submitted" and not errors
            question = IntakeQuestionRequestRecord.query.filter_by(form_id=form.id).first()
            self._append_state(run, command_id, actor_user_id, CaseEventType.FORM_ANSWERS_SUBMITTED,
                               LegalCaseState.VALIDATING_FACTS if complete else LegalCaseState.AWAITING_FACTS,
                                 {"form_id": form.id, "partial": not complete, "errors": errors})
            self._append(run.case_id, command_id, actor_user_id, CaseEventType.INTAKE_ANSWERS_SUBMITTED,
                         {"question_request_id": question.id if question else None, "form_id": form.id,
                          "partial": not complete, "answer_keys": sorted(command.payload_json.get("answers", {}))},
                         UUID(run.id))
            if complete:
                self._append(run.case_id, command_id, actor_user_id, CaseEventType.INTAKE_ANSWERS_VALIDATED,
                             {"question_request_id": question.id if question else None, "form_id": form.id,
                              "fact_count": len(command.payload_json.get("answers", {}))}, UUID(run.id))
            self._append(run.case_id, command_id, actor_user_id,
                         CaseEventType.INTAKE_QUESTION_ANSWERED if complete else CaseEventType.INTAKE_QUESTION_PARTIAL,
                         {"question_request_id": question.id if question else None, "form_id": form.id,
                          "status": question.status if question else form.status}, UUID(run.id))
            return {"form_id": form.id, "status": form.status, "errors": errors}, True
        if name == "confirm_facts":
            requested = set(command.payload_json.get("fact_ids", []))
            facts = FactAssertionRecord.query.filter(FactAssertionRecord.id.in_(requested)).all()
            if len(facts) != len(requested) or any(item.case_id != case.id for item in facts):
                raise WorkflowConflictError("Facts must all belong to this case")
            latest_ids = {
                FactAssertionRecord.query.filter_by(case_id=case.id, key=key).order_by(
                    FactAssertionRecord.recorded_at.desc()
                ).first().id
                for (key,) in db.session.query(FactAssertionRecord.key).filter_by(case_id=case.id).distinct()
            }
            if requested != latest_ids:
                raise WorkflowConflictError("All current facts must be confirmed together")
            for fact in facts:
                fact.verification_status = "confirmed_by_user"
            db.session.commit()
            self._append(case.id, command_id, actor_user_id, CaseEventType.INTAKE_RESUMED, {
                "confirmed_fact_ids": sorted(requested), "resume_step": "issue_plan",
            }, UUID(run.id))
            self._append_state(run, command_id, actor_user_id, CaseEventType.FACTS_VALIDATED,
                               LegalCaseState.FACTS_COMPLETE, {"fact_ids": sorted(requested)})
            return {"confirmed": sorted(requested)}, True
        if name == "issue_plan":
            issues = plan_issues(case.id, self._pack(case))
            payload = [item.model_dump(mode="json") for item in issues]
            self._append_state(run, command_id, actor_user_id, CaseEventType.LEGAL_ISSUES_PLANNED,
                               LegalCaseState.LEGAL_ISSUES_PLANNED, {"issues": payload})
            return {"issues": payload}, True
        if name == "research":
            issues = [LegalIssue.model_validate(item) for item in self._step_output(run.id, "issue_plan")["issues"]]
            facts = FactAssertionRecord.query.filter_by(case_id=case.id, verification_status="confirmed_by_user").all()
            snapshot = create_corpus_snapshot(case.id, case.workflow_pack_id, case.workflow_pack_version)
            case.corpus_snapshot_id = snapshot.id
            db.session.commit()
            candidates = self.authority_provider.retrieve(case.id, issues, facts)
            candidates = [VerifiedAuthorityInput.model_validate(item) for item in candidates]
            self._record_agent_run(case, "LEGAL_RESEARCHER", {
                "candidate_count": len(candidates), "issue_count": len(issues)
            }, snapshot.id)
            self._append_state(run, command_id, actor_user_id, CaseEventType.RESEARCH_STARTED,
                               LegalCaseState.RESEARCHING, {"corpus_snapshot_id": snapshot.id,
                               "candidate_count": len(candidates)})
            return {"corpus_snapshot_id": snapshot.id,
                    "candidates": [item.model_dump(mode="json") for item in candidates]}, True
        if name == "verify_evidence":
            self._append_state(run, command_id, actor_user_id, CaseEventType.AUTHORITY_RETRIEVED,
                               LegalCaseState.VERIFYING_EVIDENCE, {})
            issues = [LegalIssue.model_validate(item) for item in self._step_output(run.id, "issue_plan")["issues"]]
            candidates = [VerifiedAuthorityInput.model_validate(item) for item in self._step_output(run.id, "research")["candidates"]]
            accepted, missing = verify_and_record(case.id, issues, candidates)
            self._record_agent_run(case, "LEGAL_VERIFIER", {
                "accepted": len(accepted), "missing_issues": missing
            }, case.corpus_snapshot_id)
            if missing:
                self._append_state(run, command_id, actor_user_id, CaseEventType.CASE_BLOCKED,
                                   LegalCaseState.BLOCKED, {"reason": "missing_verified_authority", "missing_issues": missing})
                return {"accepted": len(accepted), "missing_issues": missing, "output_status": "blocked_by_missing_authority"}, False
            self._append_state(run, command_id, actor_user_id, CaseEventType.EVIDENCE_READY,
                               LegalCaseState.EVIDENCE_READY, {"proposition_ids": [item.id for item in accepted]})
            return {"accepted": len(accepted), "missing_issues": []}, True
        if name == "draft":
            self._append_state(run, command_id, actor_user_id, CaseEventType.DRAFT_CREATED,
                               LegalCaseState.DRAFTING, {"phase": "started"})
            draft = compose_draft(case.id, self._pack(case), case.corpus_snapshot_id)
            self._record_agent_run(case, "DRAFT_COMPOSER", {
                "draft_id": draft.id, "status": draft.status
            }, case.corpus_snapshot_id)
            if draft.validation_json.get("errors"):
                self._append_state(run, command_id, actor_user_id, CaseEventType.DRAFT_VALIDATION_FAILED,
                                   LegalCaseState.BLOCKED, {"draft_id": draft.id, "errors": draft.validation_json["errors"]})
                return {"draft_id": draft.id, "errors": draft.validation_json["errors"]}, False
            self._append_state(run, command_id, actor_user_id, CaseEventType.DRAFT_CREATED,
                               LegalCaseState.DRAFT_READY, {"draft_id": draft.id, "status": draft.status})
            return {"draft_id": draft.id}, True
        if name == "compliance":
            self._append_state(run, command_id, actor_user_id, CaseEventType.COMPLIANCE_COMPLETED,
                               LegalCaseState.COMPLIANCE_REVIEW, {"phase": "started"})
            draft = db.session.get(DraftVersionRecord, self._step_output(run.id, "draft")["draft_id"])
            findings = compliance_review(case.id, draft)
            self._record_agent_run(case, "COMPLIANCE_AUDITOR", {
                "finding_count": len(findings)
            }, case.corpus_snapshot_id)
            if any(item.blocks_output for item in findings):
                self._append_state(run, command_id, actor_user_id, CaseEventType.CASE_BLOCKED,
                                   LegalCaseState.BLOCKED, {"reason": "compliance_findings"})
                return {"finding_ids": [item.id for item in findings]}, False
            return {"finding_ids": []}, True
        if name == "citation_gate":
            self._append_state(run, command_id, actor_user_id, CaseEventType.CITATION_GATE_COMPLETED,
                               LegalCaseState.CITATION_REVIEW, {"phase": "started"})
            errors = citation_gate(case.id)
            if errors:
                self._append_state(run, command_id, actor_user_id, CaseEventType.CASE_BLOCKED,
                                   LegalCaseState.BLOCKED, {"reason": "citation_gate", "errors": errors})
                return {"errors": errors}, False
            self._append_state(run, command_id, actor_user_id, CaseEventType.HUMAN_REVIEW_REQUIRED,
                               LegalCaseState.READY_FOR_HUMAN_REVIEW, {"output_status": "ready_for_human_review"})
            return {"errors": [], "output_status": "ready_for_human_review"}, True
        if name == "human_review":
            draft = DraftVersionRecord.query.filter_by(case_id=case.id).order_by(
                DraftVersionRecord.version.desc()
            ).first()
            task = HumanTaskRecord.query.filter_by(
                case_id=case.id, task_type="review_draft", status="open"
            ).order_by(HumanTaskRecord.created_at.desc()).first()
            if (
                draft is None
                or draft.id != command.payload_json.get("draft_id")
                or draft.version != command.payload_json.get("draft_version")
                or task is None
                or (task.payload_json or {}).get("draft_version_id") != draft.id
            ):
                raise WorkflowConflictError("The review draft or task is no longer current")
            findings = command.payload_json.get("findings", [])
            if not command.payload_json.get("approved") and not findings:
                findings = [{
                    "severity": "high",
                    "category": "human_review",
                    "description": "Borrador rechazado en revisión humana.",
                    "suggested_action": "Corregir el borrador antes de una nueva revisión.",
                    "blocks_output": True,
                }]
            for finding in findings:
                db.session.add(ReviewFindingRecord(
                    id=str(uuid4()),
                    case_id=case.id,
                    draft_version_id=draft.id,
                    reviewer_type="human",
                    severity=finding.get("severity", "high"),
                    category=finding.get("category", "human_review"),
                    finding_json={
                        "description": finding.get("description", ""),
                        "location": finding.get("location"),
                        "suggested_action": finding.get("suggested_action", "Corregir el borrador."),
                    },
                    blocks_output=bool(finding.get("blocks_output", True)),
                ))
            task.status = "completed"
            task.completed_at = datetime.utcnow()
            db.session.commit()
            if not command.payload_json.get("approved"):
                self._append_state(run, command_id, actor_user_id, CaseEventType.CASE_BLOCKED,
                                    LegalCaseState.BLOCKED, {"reason": "human_review_rejected",
                                    "draft_id": draft.id, "draft_version": draft.version,
                                    "finding_count": len(findings)})
                return {"approved": False, "draft_id": draft.id, "draft_version": draft.version}, False
            self._append_state(run, command_id, actor_user_id, CaseEventType.HUMAN_REVIEW_COMPLETED,
                                LegalCaseState.COMPLETED, {
                                    "approved": True, "draft_id": draft.id,
                                    "draft_version": draft.version, "finding_count": len(findings),
                                })
            return {"approved": True, "draft_id": draft.id, "draft_version": draft.version}, True
        raise ValueError(f"Unknown workflow step {name}")

    def _pack(self, case):
        return self.registry.get(case.workflow_pack_id, case.workflow_pack_version).pack

    def _persist_pack(self, loaded):
        existing = WorkflowPackVersionRecord.query.filter_by(
            pack_id=loaded.pack.id, version=loaded.pack.version
        ).first()
        if existing is None:
            db.session.add(WorkflowPackVersionRecord(
                id=str(uuid4()), pack_id=loaded.pack.id, version=loaded.pack.version,
                status=loaded.pack.status, jurisdiction=loaded.pack.jurisdiction,
                definition_json=loaded.pack.model_dump(mode="json"), checksum=loaded.checksum,
            ))
            db.session.commit()
        elif existing.checksum != loaded.checksum:
            raise RuntimeError(f"Immutable workflow pack changed: {loaded.pack.id} v{loaded.pack.version}")

    @staticmethod
    def _step_output(run_id: str, step_name: str) -> dict:
        step = WorkflowStepRunRecord.query.filter_by(run_id=run_id, step_name=step_name).one()
        return step.output_json or {}

    @staticmethod
    def _record_agent_run(
        case, node_id: str, result: dict, corpus_snapshot_id: str | None,
        *, provider: str = "deterministic", model: str | None = None,
        output_schema: str | None = None,
    ):
        from legal.prompts.compiler import PromptCompiler

        prompt = PromptCompiler().compile(node_id)
        db.session.add(AgentRunRecord(
            id=str(uuid4()), case_id=case.id, node_id=node_id,
            provider=provider, model=model, prompt_version_id=prompt.id,
            corpus_snapshot_id=corpus_snapshot_id, parameters_json={"temperature": 0},
            result_json={
                **result,
                "output_schema": output_schema,
                "output_hash": sha256(str(result).encode("utf-8")).hexdigest(),
            }, duration_ms=0,
        ))
        db.session.commit()

    def _append_state(self, run, command_id, actor_user_id, event_type, state, details):
        self._append(run.case_id, command_id, actor_user_id, event_type,
                     {**details, "new_state": state.value}, UUID(run.id))

    def _retry(self, command):
        query = WorkflowStepRunRecord.query.filter_by(case_id=command.case_id, status=WorkflowStepStatus.FAILED.value)
        if command.payload_json.get("step_run_id"):
            query = query.filter_by(id=command.payload_json["step_run_id"])
        step = query.order_by(WorkflowStepRunRecord.completed_at.desc()).first()
        if step is None:
            raise WorkflowConflictError("No failed workflow step is available to retry")
        run = db.session.get(WorkflowRunRecord, step.run_id)
        self._reset_failed_run(run)
        self._execute_run(run, command.actor_user_id, UUID(command.id))

    @staticmethod
    def _reset_failed_run(run):
        for step in WorkflowStepRunRecord.query.filter_by(run_id=run.id, status=WorkflowStepStatus.FAILED.value):
            step.status = WorkflowStepStatus.PENDING.value
            step.attempt += 1
            step.error = None
            step.started_at = None
            step.completed_at = None
        run.status = WorkflowRunStatus.RUNNING.value
        run.attempt += 1
        run.error = None
        run.failed_at = None
        db.session.commit()

    def _cancel(self, command):
        run = WorkflowRunRecord.query.filter_by(case_id=command.case_id, status=WorkflowRunStatus.RUNNING.value).first()
        if run:
            run.cancel_requested_at = datetime.utcnow()
            db.session.commit()
            self._mark_cancelled(run, UUID(command.id), command.actor_user_id, command.payload_json.get("reason"))
        else:
            case = self.repository.get(command.case_id, command.actor_user_id)
            if case.state not in {LegalCaseState.CANCELLED, LegalCaseState.COMPLETED}:
                self._append(command.case_id, UUID(command.id), command.actor_user_id, CaseEventType.CASE_CANCELLED,
                             {"reason": command.payload_json.get("reason"), "new_state": LegalCaseState.CANCELLED.value})

    def _mark_cancelled(self, run, command_id, actor_user_id, reason):
        run.status = WorkflowRunStatus.CANCELLED.value
        run.completed_at = datetime.utcnow()
        WorkflowStepRunRecord.query.filter_by(run_id=run.id, status=WorkflowStepStatus.PENDING.value).update(
            {"status": WorkflowStepStatus.CANCELLED.value}
        )
        db.session.commit()
        self._append(run.case_id, command_id, actor_user_id, CaseEventType.CASE_CANCELLED,
                     {"reason": reason, "run_id": run.id, "new_state": LegalCaseState.CANCELLED.value}, UUID(run.id))

    def _record_failure(self, run, command, exc):
        now = datetime.utcnow()
        run.status = WorkflowRunStatus.FAILED.value
        run.failed_at = now
        run.error = str(exc)[:2000]
        WorkflowStepRunRecord.query.filter_by(run_id=run.id, status=WorkflowStepStatus.RUNNING.value).update(
            {"status": WorkflowStepStatus.FAILED.value, "error": str(exc)[:2000], "completed_at": now}
        )
        db.session.commit()
        case = self.repository.get(run.case_id, command.actor_user_id)
        if case.state not in {LegalCaseState.FAILED, LegalCaseState.CANCELLED}:
            if run.current_step in {"intent_compile", "workflow_select", "precedent_search", "form_compile", "submit_form"}:
                self._append(run.case_id, UUID(command.id), command.actor_user_id, CaseEventType.INTAKE_FAILED, {
                    "run_id": run.id, "step_name": run.current_step, "error": str(exc)[:2000],
                }, UUID(run.id))
            self._append(run.case_id, UUID(command.id), command.actor_user_id, CaseEventType.CASE_FAILED,
                         {"error": str(exc)[:2000], "new_state": LegalCaseState.FAILED.value}, UUID(run.id))

    def _append(self, case_id, command_id, actor_user_id, event_type, payload, run_id=None):
        for attempt in range(self.lock_retries):
            case = self.repository.get(case_id)
            try:
                self.repository.append_event(case_id, case.state_version, NewCaseEvent(
                    event_type=event_type, command_id=command_id, run_id=run_id,
                    actor_user_id=actor_user_id, payload=payload, occurred_at=datetime.utcnow(),
                ))
                db.session.commit()
                return
            except ConcurrentCaseUpdateError:
                db.session.rollback()
                if attempt + 1 == self.lock_retries:
                    raise

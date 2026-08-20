from uuid import UUID

from app.extensions import db
from app.models import AgentSession, UploadedDocument
from legal.application.query_service import LegalQueryService
from legal.domain.enums import LegalCaseState, WorkflowRunStatus
from legal.domain.workspace import (
    BlockingReason, CaseActivity, CaseCapabilities, CaseEventMetadata, CaseWorkspace,
    DraftArtifact, EvidenceArtifact, FactArtifact, FindingArtifact, FormArtifact,
    DocumentArtifact, FieldProvenanceArtifact, HumanTaskArtifact, IssueArtifact,
    PrecedentArtifact, PrecedentSearchArtifact, QuestionRequestArtifact,
    ResolvedPrecedentSummary, WorkspaceMessage, WorkspaceSession,
)
from legal.domain.models import IntakeIntent, IntakeSummary
from legal.intake.presentation import intake_act_label, required_missing_groups
from legal.evidence.service import citation_gate
from legal.infrastructure.models import (
    CaseEventRecord, DraftVersionRecord, EvidenceSpanRecord, FactAssertionRecord,
    ExampleVersionRecord, FieldProvenanceRecord, FormInstanceRecord, HumanTaskRecord,
    IntakeIntentRecord, IntakeQuestionRequestRecord, PrecedentSearchRunRecord,
    PrecedentSelectionRecord, ReviewFindingRecord,
    WorkflowRunRecord, WorkflowStepRunRecord,
)


_DRAFT_STATES = {
    LegalCaseState.DRAFT_READY.value,
    LegalCaseState.COMPLIANCE_REVIEW.value,
    LegalCaseState.CITATION_REVIEW.value,
    LegalCaseState.READY_FOR_HUMAN_REVIEW.value,
    LegalCaseState.COMPLETED.value,
}


class CaseWorkspaceService:
    def build(self, case_id: UUID, owner_user_id: int, roles: set[str]) -> CaseWorkspace:
        query = LegalQueryService()
        legal_case = query.get_case(case_id, owner_user_id)
        snapshot = query.get_snapshot(case_id, owner_user_id)
        cid = str(case_id)

        form_record = FormInstanceRecord.query.filter_by(case_id=cid).order_by(
            FormInstanceRecord.version.desc()
        ).first()
        precedent_record = PrecedentSelectionRecord.query.filter_by(case_id=cid).order_by(
            PrecedentSelectionRecord.created_at.desc()
        ).first()
        intent_record = IntakeIntentRecord.query.filter_by(case_id=cid).first()
        search_record = PrecedentSearchRunRecord.query.filter_by(case_id=cid).order_by(
            PrecedentSearchRunRecord.started_at.desc()
        ).first()
        question_record = IntakeQuestionRequestRecord.query.filter_by(case_id=cid).order_by(
            IntakeQuestionRequestRecord.created_at.desc()
        ).first()
        provenance_records = FieldProvenanceRecord.query.filter_by(case_id=cid).order_by(
            FieldProvenanceRecord.created_at.asc()
        ).all()
        document_records = UploadedDocument.query.filter_by(case_id=cid).order_by(UploadedDocument.created_at.asc()).all()
        draft_record = DraftVersionRecord.query.filter_by(case_id=cid).order_by(
            DraftVersionRecord.version.desc()
        ).first()
        task_records = HumanTaskRecord.query.filter_by(case_id=cid).order_by(
            HumanTaskRecord.created_at.asc()
        ).all()
        finding_records = ReviewFindingRecord.query.filter_by(case_id=cid).order_by(
            ReviewFindingRecord.created_at.asc()
        ).all()
        session_record = AgentSession.query.filter_by(case_id=cid, user_id=owner_user_id).order_by(
            AgentSession.id.desc()
        ).first()
        latest_event_record = CaseEventRecord.query.filter_by(case_id=cid).order_by(
            CaseEventRecord.sequence_number.desc()
        ).first()
        latest_problem_event = CaseEventRecord.query.filter(
            CaseEventRecord.case_id == cid,
            CaseEventRecord.event_type.in_(["case.blocked", "case.failed"]),
        ).order_by(CaseEventRecord.sequence_number.desc()).first()
        issue_step = WorkflowStepRunRecord.query.filter_by(
            case_id=cid, step_name="issue_plan", status="completed"
        ).order_by(WorkflowStepRunRecord.completed_at.desc()).first()
        issue_values = ((issue_step.output_json or {}).get("issues") or []) if issue_step else []
        evidence_records = EvidenceSpanRecord.query.filter_by(case_id=cid).order_by(
            EvidenceSpanRecord.verified_at.asc()
        ).all()

        latest_facts = {}
        for item in FactAssertionRecord.query.filter_by(case_id=cid).order_by(
            FactAssertionRecord.recorded_at.desc()
        ).all():
            latest_facts.setdefault(item.key, item)

        form = FormArtifact.model_validate(form_record) if form_record else None
        if form is not None:
            schema = dict(form.schema_data or {})
            sections = []
            for index, section in enumerate(schema.get("sections") or []):
                normalized = dict(section)
                normalized.setdefault("id", f"section-{index + 1}")
                normalized.setdefault("title", "Información requerida")
                if normalized["title"] == "Informacion requerida":
                    normalized["title"] = "Información requerida"
                sections.append(normalized)
            schema["sections"] = sections
            schema.setdefault("id", str(form.id))
            schema.setdefault("version", form.version)
            form = form.model_copy(update={"schema_data": schema})

        draft = DraftArtifact.model_validate(draft_record) if draft_record else None
        tasks = [HumanTaskArtifact.model_validate(item) for item in task_records]
        findings = [FindingArtifact.model_validate(item) for item in finding_records]
        open_tasks = [item for item in task_records if item.status == "open"]
        open_review = next((item for item in open_tasks if item.task_type == "review_draft"), None)
        current_review = bool(
            draft_record and open_review
            and (open_review.payload_json or {}).get("draft_version_id") == draft_record.id
        )

        reasons = self._consistency_reasons(legal_case.state.value, legal_case.active_run_id, draft_record, open_review)
        last_event = self._event_metadata(latest_event_record)
        active_run = db.session.get(WorkflowRunRecord, str(legal_case.active_run_id)) if legal_case.active_run_id else None
        activity = self._activity(
            legal_case.state.value, legal_case.active_run_id, active_run, open_tasks,
            draft_record, reasons, last_event, self._event_metadata(latest_problem_event),
        )

        validation_errors = (draft_record.validation_json or {}).get("errors", []) if draft_record else []
        blocking_finding = any(item.blocks_output for item in finding_records)
        citation_errors = citation_gate(cid) if draft_record else []
        export_allowed = (
            "legal_drafter" in roles
            and legal_case.state.value in {
                LegalCaseState.READY_FOR_HUMAN_REVIEW.value,
                LegalCaseState.COMPLETED.value,
            }
            and draft_record is not None
            and draft_record.status == "grounded_draft"
            and not validation_errors
            and not blocking_finding
            and not citation_errors
        )
        review_allowed = (
            "legal_reviewer" in roles
            and legal_case.state == LegalCaseState.READY_FOR_HUMAN_REVIEW
            and draft_record is not None
            and current_review
        )
        reasons.extend(self._workflow_reasons(legal_case.state.value, latest_problem_event))
        reasons.extend(self._capability_reasons(
            roles, legal_case.state.value, draft_record, validation_errors,
            blocking_finding, citation_errors, export_allowed,
        ))

        intake_intent = IntakeIntent.model_validate(intent_record.intent_json) if intent_record else None
        resolved_precedent = None
        selected = None
        profile = {}
        if search_record and search_record.selected_example_version_id:
            selected = db.session.get(ExampleVersionRecord, search_record.selected_example_version_id)
            profile = (selected.profile_json or {}) if selected else {}
            resolved_precedent = ResolvedPrecedentSummary(
                title=selected.title if selected else None,
                number=profile.get("document_number"), date=profile.get("document_date"),
                document_type=profile.get("document_type"), source_url=profile.get("source_url"),
                match_label=search_record.match_label,
                similarities=search_record.similarities_json or [], differences=search_record.differences_json or [],
            )
        missing_fields = [
            item.get("key") for item in (question_record.questions_json if question_record else [])
            if item.get("required") and item.get("key")
        ]
        intake_summary = IntakeSummary(
            act_type=intake_intent.act_type if intake_intent else legal_case.task_family.value,
            subtype=intake_intent.subtype if intake_intent else (legal_case.resolution_type or "unknown"),
            act_label=intake_act_label(
                intake_intent.subtype if intake_intent else (legal_case.resolution_type or "unknown")
            ),
            workflow_id=legal_case.workflow_pack_id, workflow_version=legal_case.workflow_pack_version,
            search_status=search_record.status if search_record else "pending",
            match_label=search_record.match_label if search_record else None,
            missing_fields=missing_fields, known_fact_keys=sorted(latest_facts),
            missing_groups=required_missing_groups(form_record),
            selected_precedent_number=profile.get("document_number"),
            selected_precedent_title=selected.title if selected else None,
            selected_precedent_source_url=profile.get("source_url"),
            generic_fallback_count=int(
                ((search_record.index_status_json or {}).get("generic_fallback_count", 0)) if search_record else 0
            ),
            next_action=_next_intake_action(legal_case.state.value, question_record),
        )

        return CaseWorkspace(
            case=legal_case,
            snapshot=snapshot,
            activity=activity,
            form=form,
            precedent=PrecedentArtifact.model_validate(precedent_record) if precedent_record else None,
            intake_intent=intake_intent,
            precedent_search=PrecedentSearchArtifact.model_validate(search_record) if search_record else None,
            resolved_precedent=resolved_precedent,
            question_request=QuestionRequestArtifact.model_validate(question_record) if question_record else None,
            field_provenance=[FieldProvenanceArtifact.model_validate(item) for item in provenance_records],
            documents=[DocumentArtifact.model_validate(item) for item in document_records],
            intake_summary=intake_summary,
            facts=[FactArtifact.model_validate(item) for item in latest_facts.values()],
            issues=[IssueArtifact.model_validate(item) for item in issue_values],
            evidence=[EvidenceArtifact.model_validate(item) for item in evidence_records],
            draft=draft,
            findings=findings,
            human_tasks=tasks,
            session=WorkspaceSession.model_validate(session_record) if session_record else None,
            messages=[WorkspaceMessage.model_validate(item) for item in session_record.messages] if session_record else [],
            guidance=_case_guidance(legal_case.state.value, search_record, question_record),
            capabilities=CaseCapabilities(
                can_view_draft=draft_record is not None,
                can_edit_draft=False,
                can_export_docx=export_allowed,
                can_review=review_allowed,
                can_reject=review_allowed,
                can_request_second_opinion=(
                    "legal_reviewer" in roles and draft_record is not None
                ),
                can_cancel=legal_case.state not in {
                    LegalCaseState.COMPLETED, LegalCaseState.CANCELLED,
                },
            ),
            blocking_reasons=reasons,
            last_event=last_event,
        )

    @staticmethod
    def _consistency_reasons(state: str, active_run_id, draft, open_review) -> list[BlockingReason]:
        reasons = []
        if state in _DRAFT_STATES and draft is None:
            reasons.append(BlockingReason(
                code="draft_missing",
                message="El estado del expediente requiere un borrador actual, pero no existe.",
                category="consistency",
            ))
        if state == LegalCaseState.READY_FOR_HUMAN_REVIEW.value and open_review is None:
            reasons.append(BlockingReason(
                code="review_task_missing",
                message="El expediente está listo, pero falta la tarea abierta de revisión humana.",
                category="consistency",
            ))
        if state == LegalCaseState.COMPLETED.value and open_review is not None:
            reasons.append(BlockingReason(
                code="completed_with_open_review_task",
                message="El expediente está completado, pero conserva una tarea de revisión abierta.",
                category="consistency",
            ))
        if active_run_id is not None and db.session.get(WorkflowRunRecord, str(active_run_id)) is None:
            reasons.append(BlockingReason(
                code="active_run_missing",
                message="El expediente referencia una ejecución activa que no existe.",
                category="consistency",
            ))
        return reasons

    @staticmethod
    def _workflow_reasons(state: str, problem_event) -> list[BlockingReason]:
        if problem_event is None or state not in {
            LegalCaseState.BLOCKED.value, LegalCaseState.FAILED.value,
        }:
            return []
        payload = problem_event.payload_json or {}
        code = str(payload.get("reason") or ("workflow_failed" if state == "failed" else "workflow_blocked"))
        message = str(payload.get("error") or {
            "missing_verified_authority": "Falta autoridad jurídica verificada para continuar.",
            "compliance_findings": "El control automático encontró observaciones bloqueantes.",
            "citation_gate": "El control de citas encontró referencias que deben corregirse.",
            "human_review_rejected": "La revisión humana solicitó cambios sobre el borrador.",
        }.get(code, "El expediente requiere intervención antes de continuar."))
        return [BlockingReason(code=code, message=message, category="workflow")]

    @staticmethod
    def _capability_reasons(
        roles, state, draft, validation_errors, blocking_finding, citation_errors, export_allowed,
    ) -> list[BlockingReason]:
        if export_allowed:
            return []
        if "legal_drafter" not in roles:
            code, message = "docx_role_required", "Su rol no permite exportar el DOCX del expediente."
        elif draft is None:
            code, message = "docx_draft_missing", "La exportación se habilitará cuando exista un borrador persistido."
        elif state not in {
            LegalCaseState.READY_FOR_HUMAN_REVIEW.value, LegalCaseState.COMPLETED.value,
        }:
            code, message = "docx_state_gate", "La exportación todavía no está habilitada para el estado actual."
        elif draft.status != "grounded_draft" or validation_errors:
            code, message = "docx_draft_invalid", "El borrador no superó la validación requerida para exportar."
        elif blocking_finding:
            code, message = "docx_blocking_finding", "Existen hallazgos bloqueantes que impiden exportar."
        elif citation_errors:
            code, message = "docx_citation_gate", "El control de citas impide exportar el borrador."
        else:
            code, message = "docx_unavailable", "La exportación no está disponible."
        return [BlockingReason(code=code, message=message, category="capability")]

    @staticmethod
    def _activity(
        state, active_run_id, active_run, open_tasks, draft, reasons,
        last_event, latest_problem_event,
    ) -> CaseActivity:
        if active_run is not None and active_run.status == WorkflowRunStatus.RUNNING.value:
            kind = "working"
        elif reasons:
            kind = "blocked"
        elif state == LegalCaseState.FAILED.value:
            kind = "failed"
        elif state == LegalCaseState.BLOCKED.value:
            kind = "blocked"
        elif state == LegalCaseState.COMPLETED.value:
            kind = "completed"
        elif any(item.task_type == "review_draft" for item in open_tasks) or state == LegalCaseState.READY_FOR_HUMAN_REVIEW.value:
            kind = "waiting_human_review"
        elif open_tasks or state in {LegalCaseState.AWAITING_FACTS.value, LegalCaseState.VALIDATING_FACTS.value}:
            kind = "waiting_user"
        elif latest_problem_event and last_event and latest_problem_event.sequence_number == last_event.sequence_number:
            kind = "failed" if latest_problem_event.event_type == "case.failed" else "blocked"
        else:
            kind = "idle"
        current_task = next(
            (item for item in open_tasks if item.task_type == "review_draft"),
            open_tasks[0] if open_tasks else None,
        )
        return CaseActivity(
            kind=kind,
            active_run_id=active_run.id if active_run else active_run_id,
            current_step=active_run.current_step if active_run else None,
            started_at=active_run.started_at if active_run else None,
            task_type=current_task.task_type if current_task else None,
            task_id=current_task.id if current_task else None,
            draft_version=draft.version if draft else None,
            last_event_sequence=last_event.sequence_number if last_event else None,
            last_event_type=last_event.event_type if last_event else None,
            updated_at=last_event.occurred_at if last_event else None,
            message=_activity_message(kind),
        )

    @staticmethod
    def _event_metadata(record) -> CaseEventMetadata | None:
        if record is None:
            return None
        return CaseEventMetadata(
            id=record.id,
            sequence_number=record.sequence_number,
            event_type=record.event_type,
            run_id=record.run_id,
            occurred_at=record.occurred_at,
        )


def _case_guidance(state: str, search=None, question=None) -> str:
    precedent_summary = ""
    if search is not None:
        if search.status in {"unavailable", "failed"}:
            precedent_summary = (search.fallback_reason or "La búsqueda local de antecedentes no está disponible.") + " "
        elif search.selected_example_version_id:
            precedent_summary = f"La búsqueda registró una coincidencia {search.match_label}, utilizable solo como guía estructural."
            differences = "; ".join(str(item) for item in (search.differences_json or [])[:3])
            if differences:
                precedent_summary += f" Diferencias relevantes: {differences}."
            precedent_summary += " "
        else:
            precedent_summary = (search.fallback_reason or "No se seleccionó un antecedente comparable.") + " "
    if state in {"form_ready", "awaiting_facts"}:
        labels = [item.get("label") for item in (question.questions_json if question else []) if item.get("required")]
        pending = "; ".join(item for item in labels if item)
        return precedent_summary + (f"Faltan estos datos confirmables: {pending}." if pending else "La solicitud de datos permanece pendiente.")
    if state == "validating_facts":
        return "Los datos fueron registrados. Revise el resumen de hechos y confírmelos para iniciar la investigación jurídica."
    if state == "blocked":
        return "El expediente está bloqueado por falta o conflicto de evidencia. Revise las observaciones antes de continuar."
    if state == "ready_for_human_review":
        return "El borrador superó los controles automáticos y está listo para revisión humana."
    return "El expediente sigue su workflow controlado. Puede dejar una aclaración y revisar el estado y las fuentes en este espacio."


def _next_intake_action(state: str, question) -> str:
    if question and question.status in {"pending", "partial"}:
        return "answer_questions"
    if state == LegalCaseState.VALIDATING_FACTS.value:
        return "confirm_facts"
    if state in {LegalCaseState.BLOCKED.value, LegalCaseState.FAILED.value}:
        return "resolve_blocker"
    return "follow_workflow"


def _activity_message(kind: str) -> str:
    return {
        "working": "El workflow está procesando el expediente.",
        "waiting_user": "El expediente espera una acción del usuario.",
        "waiting_human_review": "El borrador espera revisión humana.",
        "blocked": "El expediente está bloqueado y requiere intervención.",
        "failed": "La ejecución falló y puede requerir un reintento.",
        "completed": "El expediente está completado.",
        "idle": "El expediente no tiene una ejecución activa.",
    }[kind]

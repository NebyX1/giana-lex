from datetime import datetime
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from legal.cases.repository import LegalCaseRepository
from legal.domain.commands import (
    CancelWorkflow,
    ConfirmFacts,
    CreateLegalCase,
    RetryWorkflowStep,
    StartLegalWorkflow,
    SubmitFormAnswers,
    SubmitHumanReview,
)
from legal.domain.enums import (
    CaseEventType,
    CommandStatus,
    LegalCaseState,
    OutboxStatus,
    WorkflowRunStatus,
    WorkflowStepStatus,
)
from legal.domain.errors import DraftVersionMismatchError, WorkflowConflictError
from legal.domain.events import NewCaseEvent
from legal.infrastructure.models import (
    CaseCommandRecord,
    LegalCaseRecord,
    OutboxEventRecord,
    DraftVersionRecord,
    HumanTaskRecord,
    WorkflowRunRecord,
    WorkflowStepRunRecord,
)


class LegalCommandService:
    def __init__(self, repository: LegalCaseRepository | None = None):
        self.repository = repository or LegalCaseRepository()

    def create_case(self, command: CreateLegalCase):
        existing = self._existing(command.actor_user_id, command.command_type, command.idempotency_key)
        if existing is not None:
            return self.repository.get(existing.case_id, command.actor_user_id), False

        now = datetime.utcnow()
        record = LegalCaseRecord(
            id=str(command.case_id),
            owner_user_id=command.actor_user_id,
            title=command.title,
            task_family=command.task_family.value,
            resolution_type=command.resolution_type,
            jurisdiction=command.jurisdiction,
            risk_tier=command.risk_tier.value,
            workflow_pack_id=command.workflow_pack_id,
            workflow_pack_version=command.workflow_pack_version,
            state=LegalCaseState.NEW.value,
            state_version=0,
            created_at=now,
            updated_at=now,
        )
        db.session.add(record)
        # No ORM relationship connects these records, so SQLAlchemy cannot
        # infer their dependency. Flush the parent before FK children; MariaDB
        # enforces this even when SQLite test defaults do not.
        db.session.flush()
        db.session.add(
            CaseCommandRecord(
                id=str(command.command_id),
                case_id=str(command.case_id),
                actor_user_id=command.actor_user_id,
                command_type=command.command_type,
                idempotency_key=command.idempotency_key,
                payload_json=command.model_dump(mode="json"),
                status=CommandStatus.COMPLETED.value,
                attempts=1,
                started_at=now,
                completed_at=now,
            )
        )
        try:
            db.session.flush()
            self.repository.append_event(
                command.case_id,
                0,
                NewCaseEvent(
                    event_type=CaseEventType.CASE_CREATED,
                    command_id=command.command_id,
                    actor_user_id=command.actor_user_id,
                    occurred_at=now,
                    payload={
                        "title": command.title,
                        "task_family": command.task_family.value,
                        "resolution_type": command.resolution_type,
                        "jurisdiction": command.jurisdiction,
                        "risk_tier": command.risk_tier.value,
                        "workflow_pack_id": command.workflow_pack_id,
                        "workflow_pack_version": command.workflow_pack_version,
                        "new_state": LegalCaseState.NEW.value,
                    },
                ),
            )
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            existing = self._existing(command.actor_user_id, command.command_type, command.idempotency_key)
            if existing is None:
                raise
            return self.repository.get(existing.case_id, command.actor_user_id), False
        return self.repository.get(command.case_id, command.actor_user_id), True

    def enqueue_start(self, command: StartLegalWorkflow) -> tuple[CaseCommandRecord, bool]:
        case = self.repository.get_record(command.case_id, command.actor_user_id)
        if case.state in {LegalCaseState.CANCELLED.value, LegalCaseState.COMPLETED.value}:
            raise WorkflowConflictError("Terminal legal cases cannot start a workflow")
        return self._enqueue(command)

    def enqueue_retry(self, command: RetryWorkflowStep) -> tuple[CaseCommandRecord, bool]:
        self.repository.get_record(command.case_id, command.actor_user_id)
        query = WorkflowStepRunRecord.query.filter_by(
            case_id=str(command.case_id), status=WorkflowStepStatus.FAILED.value
        )
        if command.step_run_id is not None:
            query = query.filter_by(id=str(command.step_run_id))
        if query.first() is None:
            raise WorkflowConflictError("No failed workflow step is available to retry")
        return self._enqueue(command)

    def enqueue_cancel(self, command: CancelWorkflow) -> tuple[CaseCommandRecord, bool]:
        self.repository.get_record(command.case_id, command.actor_user_id)
        record, created = self._enqueue(command)
        if created:
            run = WorkflowRunRecord.query.filter_by(
                case_id=str(command.case_id), status=WorkflowRunStatus.RUNNING.value
            ).order_by(WorkflowRunRecord.started_at.desc()).first()
            if run is not None and run.cancel_requested_at is None:
                run.cancel_requested_at = datetime.utcnow()
                db.session.commit()
        return record, created

    def enqueue_submit_form(self, command: SubmitFormAnswers) -> tuple[CaseCommandRecord, bool]:
        case = self.repository.get_record(command.case_id, command.actor_user_id)
        if case.state not in {LegalCaseState.AWAITING_FACTS.value, LegalCaseState.VALIDATING_FACTS.value}:
            raise WorkflowConflictError("The case is not accepting form answers")
        return self._enqueue(command)

    def enqueue_confirm_facts(self, command: ConfirmFacts) -> tuple[CaseCommandRecord, bool]:
        case = self.repository.get_record(command.case_id, command.actor_user_id)
        if case.state != LegalCaseState.VALIDATING_FACTS.value:
            raise WorkflowConflictError("The case has no facts awaiting confirmation")
        return self._enqueue(command)

    def enqueue_review(self, command: SubmitHumanReview) -> tuple[CaseCommandRecord, bool]:
        case = self.repository.get_record(command.case_id, command.actor_user_id)
        existing = self._existing(command.actor_user_id, command.command_type, command.idempotency_key)
        if existing is not None:
            return existing, False
        if case.state != LegalCaseState.READY_FOR_HUMAN_REVIEW.value:
            raise WorkflowConflictError("The case is not ready for human review")
        draft = DraftVersionRecord.query.filter_by(case_id=case.id).order_by(
            DraftVersionRecord.version.desc()
        ).first()
        task = HumanTaskRecord.query.filter_by(
            case_id=case.id, task_type="review_draft", status="open"
        ).order_by(HumanTaskRecord.created_at.desc()).first()
        if (
            draft is None
            or draft.id != str(command.draft_id)
            or draft.version != command.draft_version
            or task is None
            or (task.payload_json or {}).get("draft_version_id") != draft.id
        ):
            raise DraftVersionMismatchError(
                "El borrador fue actualizado. Recargue la versión más reciente antes de revisarlo."
            )
        return self._enqueue(command)

    def _enqueue(self, command) -> tuple[CaseCommandRecord, bool]:
        existing = self._existing(command.actor_user_id, command.command_type, command.idempotency_key)
        if existing is not None:
            return existing, False
        record = CaseCommandRecord(
            id=str(command.command_id),
            case_id=str(command.case_id),
            actor_user_id=command.actor_user_id,
            command_type=command.command_type,
            idempotency_key=command.idempotency_key,
            payload_json=command.model_dump(mode="json"),
            status=CommandStatus.PENDING.value,
        )
        db.session.add(record)
        db.session.add(
            OutboxEventRecord(
                id=str(uuid4()),
                aggregate_type="case_command",
                aggregate_id=str(command.command_id),
                topic="legal.workflow.command",
                deduplication_key=f"workflow-command:{command.command_id}",
                payload_json={"command_id": str(command.command_id)},
                status=OutboxStatus.PENDING.value,
            )
        )
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            existing = self._existing(command.actor_user_id, command.command_type, command.idempotency_key)
            if existing is None:
                raise
            return existing, False
        return record, True

    @staticmethod
    def _existing(actor_user_id: int, command_type: str, idempotency_key: str):
        return CaseCommandRecord.query.filter_by(
            actor_user_id=actor_user_id,
            command_type=command_type,
            idempotency_key=idempotency_key,
        ).first()

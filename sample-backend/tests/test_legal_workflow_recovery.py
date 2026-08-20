from uuid import UUID, uuid4

from app.extensions import db
from legal.application.command_service import LegalCommandService
from legal.domain.commands import CreateLegalCase, StartLegalWorkflow
from legal.domain.enums import RiskTier, TaskFamily
from legal.infrastructure.models import CaseCommandRecord, WorkflowRunRecord, WorkflowStepRunRecord
from legal.workflows.engine import DurableWorkflowEngine, INITIAL_WORKFLOW_ID, INITIAL_WORKFLOW_VERSION


def test_pending_workflow_survives_engine_restart(app):
    with app.app_context():
        create = CreateLegalCase(
            command_id=uuid4(),
            case_id=uuid4(),
            actor_user_id=1,
            idempotency_key="recovery-case",
            title="Recovery",
            task_family=TaskFamily.LEGAL_QUESTION,
            jurisdiction="lavalleja",
            risk_tier=RiskTier.LOW,
        )
        LegalCommandService().create_case(create)
        start = StartLegalWorkflow(
            command_id=uuid4(),
            case_id=create.case_id,
            actor_user_id=1,
            idempotency_key="recovery-start",
        )
        command, _ = LegalCommandService().enqueue_start(start)
        run = WorkflowRunRecord(
            id=str(uuid4()),
            case_id=str(create.case_id),
            command_id=command.id,
            workflow_id=INITIAL_WORKFLOW_ID,
            workflow_version=INITIAL_WORKFLOW_VERSION,
            status="running",
            attempt=1,
            current_step="durability_checkpoint",
        )
        db.session.add(run)
        db.session.add(
            WorkflowStepRunRecord(
                id=str(uuid4()),
                run_id=run.id,
                case_id=str(create.case_id),
                step_name="durability_checkpoint",
                step_order=1,
                status="pending",
                attempt=1,
                input_json={},
            )
        )
        db.session.commit()

        recovered = DurableWorkflowEngine().resume_incomplete_runs()
        db.session.expire_all()

        assert recovered == 1
        assert db.session.get(WorkflowRunRecord, run.id).status == "completed"
        assert WorkflowStepRunRecord.query.filter_by(run_id=run.id).one().status == "completed"
        assert db.session.get(CaseCommandRecord, str(start.command_id)).status == "completed"

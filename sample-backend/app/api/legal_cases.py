from uuid import UUID, uuid4

from flask import Blueprint, Response, jsonify, request, stream_with_context
from flask_login import current_user, login_required
from pydantic import ValidationError

from app.audit import record_event
from app.authorization import has_any_role, require_roles
from app.extensions import db
from legal.application.command_service import LegalCommandService
from legal.application.event_stream import stream_case_events
from legal.application.query_service import LegalQueryService
from legal.application.workspace_service import CaseWorkspaceService
from legal.bootstrap import build_outbox_publisher
from legal.domain.commands import (
    CancelWorkflow, ConfirmFacts, CreateLegalCase, RetryWorkflowStep,
    StartLegalWorkflow, SubmitFormAnswers, SubmitHumanReview,
)
from legal.domain.errors import CaseNotFoundError, DraftVersionMismatchError, WorkflowConflictError
from legal.domain.schemas import (
    CancelWorkflowRequest, ConfirmFactsRequest, CreateCaseRequest, HumanReviewRequest,
    RejectMemoryRequest, SubmitFormRequest,
)
from legal.infrastructure.models import (
    ClaimEvidenceLinkRecord, EvidenceSpanRecord, ExampleVersionRecord, MemoryProposalRecord,
)
from legal.memory.service import decide_proposal
from legal.workflows.loader import WorkflowPackRegistry


legal_cases_bp = Blueprint("legal_cases", __name__, url_prefix="/api/legal")
_WORKFLOW_PACK_REGISTRY = WorkflowPackRegistry()


def _idempotency_key() -> str | None:
    value = request.headers.get("Idempotency-Key", "").strip()
    return value if 0 < len(value) <= 255 else None


def _case_id(value: str) -> UUID | None:
    try:
        return UUID(value)
    except ValueError:
        return None


def _json(model):
    return model.model_dump(mode="json")


def _not_found():
    return jsonify(error="not_found", message="Expediente no encontrado."), 404


def _command_response(command, published: bool, created: bool):
    db.session.refresh(command)
    return jsonify(
        command_id=command.id,
        case_id=command.case_id,
        status=command.status,
        dispatched=published,
        idempotent_replay=not created,
        error=command.error,
    ), 202


@legal_cases_bp.post("/cases")
@login_required
@require_roles("legal_user")
def create_case():
    key = _idempotency_key()
    if key is None:
        return jsonify(error="idempotency_key_required", message="Idempotency-Key es requerido."), 400
    try:
        payload = CreateCaseRequest.model_validate(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return jsonify(error="invalid_case", message="Datos de expediente invalidos.", details=exc.errors()), 400
    command = CreateLegalCase(
        command_id=uuid4(),
        case_id=uuid4(),
        actor_user_id=current_user.id,
        idempotency_key=key,
        **payload.model_dump(),
    )
    case, created = LegalCommandService().create_case(command)
    record_event(
        "legal_case.create",
        "completed",
        current_user.id,
        subject_type="legal_case",
        subject_id=case.id,
    )
    db.session.commit()
    return jsonify(case=_json(case), idempotent_replay=not created), 201 if created else 200


@legal_cases_bp.get("/cases")
@login_required
@require_roles("legal_user")
def list_cases():
    try:
        limit = min(max(int(request.args.get("limit", "100")), 1), 200)
    except ValueError:
        return jsonify(error="invalid_limit", message="Limite invalido."), 400
    cases = LegalQueryService().list_cases(current_user.id, limit)
    return jsonify(cases=[_json(case) for case in cases])


@legal_cases_bp.get("/cases/<case_id>")
@login_required
@require_roles("legal_user")
def get_case(case_id: str):
    parsed = _case_id(case_id)
    if parsed is None:
        return _not_found()
    try:
        case = LegalQueryService().get_case(parsed, current_user.id)
    except CaseNotFoundError:
        return _not_found()
    return jsonify(case=_json(case))


@legal_cases_bp.get("/cases/<case_id>/snapshot")
@login_required
@require_roles("legal_user")
def get_snapshot(case_id: str):
    parsed = _case_id(case_id)
    if parsed is None:
        return _not_found()
    try:
        snapshot = LegalQueryService().get_snapshot(parsed, current_user.id)
    except CaseNotFoundError:
        return _not_found()
    return jsonify(snapshot=_json(snapshot))


@legal_cases_bp.get("/cases/<case_id>/events")
@login_required
@require_roles("legal_user")
def list_events(case_id: str):
    parsed = _case_id(case_id)
    if parsed is None:
        return _not_found()
    try:
        after = max(int(request.args.get("after", "0")), 0)
        limit = min(max(int(request.args.get("limit", "500")), 1), 1000)
    except ValueError:
        return jsonify(error="invalid_cursor", message="Cursor de eventos invalido."), 400
    try:
        events = LegalQueryService().list_events(parsed, current_user.id, after, limit)
    except CaseNotFoundError:
        return _not_found()
    return jsonify(events=[_json(event) for event in events])


@legal_cases_bp.get("/cases/<case_id>/events/stream")
@login_required
@require_roles("legal_user")
def stream_events(case_id: str):
    parsed = _case_id(case_id)
    if parsed is None:
        return _not_found()
    raw_cursor = request.headers.get("Last-Event-ID") or request.args.get("after", "0")
    try:
        cursor = max(int(raw_cursor), 0)
        LegalQueryService().get_case(parsed, current_user.id)
    except ValueError:
        return jsonify(error="invalid_cursor", message="Last-Event-ID invalido."), 400
    except CaseNotFoundError:
        return _not_found()
    return Response(
        stream_with_context(stream_case_events(parsed, current_user.id, cursor)),
        mimetype="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@legal_cases_bp.post("/cases/<case_id>/start")
@login_required
@require_roles("legal_drafter")
def start_workflow(case_id: str):
    return _enqueue(case_id, "start")


@legal_cases_bp.post("/cases/<case_id>/commands/start")
@login_required
@require_roles("legal_drafter")
def start_workflow_command(case_id: str):
    return _enqueue(case_id, "start")


@legal_cases_bp.post("/cases/<case_id>/retry")
@login_required
@require_roles("legal_drafter")
def retry_workflow(case_id: str):
    return _enqueue(case_id, "retry")


@legal_cases_bp.post("/cases/<case_id>/cancel")
@login_required
@require_roles("legal_user")
def cancel_workflow(case_id: str):
    return _enqueue(case_id, "cancel")


@legal_cases_bp.post("/cases/<case_id>/commands/retry")
@login_required
@require_roles("legal_drafter")
def retry_workflow_command(case_id: str):
    return _enqueue(case_id, "retry")


@legal_cases_bp.post("/cases/<case_id>/commands/cancel")
@login_required
@require_roles("legal_user")
def cancel_workflow_command(case_id: str):
    return _enqueue(case_id, "cancel")


@legal_cases_bp.post("/cases/<case_id>/commands/submit-form")
@login_required
@require_roles("legal_drafter")
def submit_form(case_id: str):
    parsed = _case_id(case_id)
    key = _idempotency_key()
    if parsed is None:
        return _not_found()
    if key is None:
        return jsonify(error="idempotency_key_required", message="Idempotency-Key es requerido."), 400
    try:
        payload = SubmitFormRequest.model_validate(request.get_json(silent=True) or {})
        command, created = LegalCommandService().enqueue_submit_form(SubmitFormAnswers(
            command_id=uuid4(), case_id=parsed, actor_user_id=current_user.id,
            idempotency_key=key, form_id=payload.form_id, answers=payload.answers, partial=payload.partial,
        ))
    except ValidationError as exc:
        return jsonify(error="invalid_form", details=exc.errors()), 400
    except CaseNotFoundError:
        return _not_found()
    except WorkflowConflictError as exc:
        return jsonify(error="workflow_conflict", message=str(exc)), 409
    published = not created or build_outbox_publisher().publish_command(UUID(command.id))
    record_event("legal_case.submit_form", "accepted", current_user.id, subject_type="legal_case",
                 subject_id=parsed, details={"command_id": command.id})
    db.session.commit()
    return _command_response(command, published, created)


@legal_cases_bp.post("/cases/<case_id>/commands/confirm-facts")
@login_required
@require_roles("legal_drafter")
def confirm_facts(case_id: str):
    parsed = _case_id(case_id)
    key = _idempotency_key()
    if parsed is None:
        return _not_found()
    if key is None:
        return jsonify(error="idempotency_key_required", message="Idempotency-Key es requerido."), 400
    try:
        payload = ConfirmFactsRequest.model_validate(request.get_json(silent=True) or {})
        command, created = LegalCommandService().enqueue_confirm_facts(ConfirmFacts(
            command_id=uuid4(), case_id=parsed, actor_user_id=current_user.id,
            idempotency_key=key, fact_ids=payload.fact_ids,
        ))
    except ValidationError as exc:
        return jsonify(error="invalid_facts", details=exc.errors()), 400
    except CaseNotFoundError:
        return _not_found()
    except WorkflowConflictError as exc:
        return jsonify(error="workflow_conflict", message=str(exc)), 409
    published = not created or build_outbox_publisher().publish_command(UUID(command.id))
    record_event("legal_case.confirm_facts", "accepted", current_user.id, subject_type="legal_case",
                 subject_id=parsed, details={"command_id": command.id})
    db.session.commit()
    return _command_response(command, published, created)


@legal_cases_bp.post("/cases/<case_id>/review")
@login_required
@require_roles("legal_reviewer")
def review_case(case_id: str):
    parsed = _case_id(case_id)
    key = _idempotency_key()
    if parsed is None:
        return _not_found()
    if key is None:
        return jsonify(error="idempotency_key_required", message="Idempotency-Key es requerido."), 400
    try:
        payload = HumanReviewRequest.model_validate(request.get_json(silent=True) or {})
        command, created = LegalCommandService().enqueue_review(SubmitHumanReview(
            command_id=uuid4(), case_id=parsed, actor_user_id=current_user.id,
            idempotency_key=key, draft_id=payload.draft_id, draft_version=payload.draft_version,
            approved=payload.approved,
            findings=[item.model_dump(mode="json") for item in payload.findings],
        ))
    except ValidationError as exc:
        return jsonify(error="invalid_review", details=exc.errors()), 400
    except CaseNotFoundError:
        return _not_found()
    except DraftVersionMismatchError as exc:
        return jsonify(error="draft_version_mismatch", message=str(exc)), 409
    except WorkflowConflictError as exc:
        return jsonify(error="workflow_conflict", message=str(exc)), 409
    published = not created or build_outbox_publisher().publish_command(UUID(command.id))
    if created:
        record_event(
            "legal_case.review.approve" if payload.approved else "legal_case.review.reject",
            "accepted",
            current_user.id,
            subject_type="legal_case",
            subject_id=parsed,
            details={
                "case_id": str(parsed),
                "draft_id": str(payload.draft_id),
                "draft_version": payload.draft_version,
            },
        )
        db.session.commit()
    return _command_response(command, published, created)


@legal_cases_bp.get("/cases/<case_id>/workspace")
@login_required
@require_roles("legal_user")
def case_workspace(case_id: str):
    parsed = _case_id(case_id)
    if parsed is None:
        return _not_found()
    try:
        workspace = CaseWorkspaceService().build(
            parsed,
            current_user.id,
            {role for role in ("legal_drafter", "legal_reviewer") if has_any_role(role)},
        )
    except CaseNotFoundError:
        return _not_found()
    payload = workspace.model_dump(mode="json", by_alias=True)
    precedent_search = payload.get("precedent_search")
    if precedent_search is not None:
        precedent_search.pop("calibrated_confidence", None)
    if payload.get("precedent") is not None:
        payload["precedent"].pop("confidence", None)
    return jsonify(payload)


@legal_cases_bp.get("/workflow-packs")
@login_required
@require_roles("legal_user")
def workflow_packs():
    return jsonify(workflow_packs=[{
        **item.pack.model_dump(mode="json"), "checksum": item.checksum,
    } for item in _WORKFLOW_PACK_REGISTRY.list_active()])


@legal_cases_bp.get("/examples/<example_id>")
@login_required
@require_roles("legal_user")
def get_example(example_id: str):
    item = db.session.get(ExampleVersionRecord, example_id)
    return jsonify(example=_record_json(item)) if item else _not_found()


@legal_cases_bp.get("/evidence/<evidence_id>")
@login_required
@require_roles("legal_user")
def get_evidence(evidence_id: str):
    item = db.session.get(EvidenceSpanRecord, evidence_id)
    if item is None:
        return _not_found()
    try:
        LegalQueryService().get_case(UUID(item.case_id), current_user.id)
    except CaseNotFoundError:
        return _not_found()
    links = ClaimEvidenceLinkRecord.query.filter_by(evidence_id=item.id, case_id=item.case_id).all()
    return jsonify(evidence=_record_json(item), proposition_ids=[link.proposition_id for link in links])


@legal_cases_bp.post("/memory-proposals/<proposal_id>/approve")
@login_required
@require_roles("legal_reviewer")
def approve_memory(proposal_id: str):
    return _decide_memory(proposal_id, True)


@legal_cases_bp.post("/memory-proposals/<proposal_id>/reject")
@login_required
@require_roles("legal_reviewer")
def reject_memory(proposal_id: str):
    return _decide_memory(proposal_id, False)


def _decide_memory(proposal_id: str, approve: bool):
    key = _idempotency_key()
    if key is None:
        return jsonify(error="idempotency_key_required", message="Idempotency-Key es requerido."), 400
    proposal = db.session.get(MemoryProposalRecord, proposal_id)
    if proposal is None:
        return _not_found()
    reason = None
    if not approve:
        try:
            reason = RejectMemoryRequest.model_validate(request.get_json(silent=True) or {}).reason
        except ValidationError as exc:
            return jsonify(error="invalid_rejection", details=exc.errors()), 400
    try:
        memory = decide_proposal(proposal, current_user.id, approve, reason)
    except ValueError as exc:
        return jsonify(error="memory_conflict", message=str(exc)), 409
    record_event("legal_memory.approve" if approve else "legal_memory.reject", "completed",
                 current_user.id, subject_type="memory_proposal", subject_id=proposal.id)
    db.session.commit()
    return jsonify(proposal=_record_json(proposal), memory=_record_json(memory))


def _record_json(record):
    if record is None:
        return None
    return {column.name: getattr(record, column.name) for column in record.__table__.columns}


def _enqueue(case_id: str, action: str):
    parsed = _case_id(case_id)
    if parsed is None:
        return _not_found()
    key = _idempotency_key()
    if key is None:
        return jsonify(error="idempotency_key_required", message="Idempotency-Key es requerido."), 400
    kwargs = dict(
        command_id=uuid4(),
        case_id=parsed,
        actor_user_id=current_user.id,
        idempotency_key=key,
    )
    try:
        service = LegalCommandService()
        if action == "start":
            command, created = service.enqueue_start(StartLegalWorkflow(**kwargs))
        elif action == "retry":
            body = request.get_json(silent=True) or {}
            command, created = service.enqueue_retry(
                RetryWorkflowStep(**kwargs, step_run_id=body.get("step_run_id"))
            )
        else:
            payload = CancelWorkflowRequest.model_validate(request.get_json(silent=True) or {})
            command, created = service.enqueue_cancel(CancelWorkflow(**kwargs, reason=payload.reason))
    except ValidationError as exc:
        return jsonify(error="invalid_command", message="Comando invalido.", details=exc.errors()), 400
    except CaseNotFoundError:
        return _not_found()
    except WorkflowConflictError as exc:
        return jsonify(error="workflow_conflict", message=str(exc)), 409

    published = True
    if created:
        published = build_outbox_publisher().publish_command(UUID(command.id))
    record_event(
        f"legal_case.{action}",
        "accepted" if published else "pending",
        current_user.id,
        subject_type="legal_case",
        subject_id=parsed,
        details={"command_id": command.id},
    )
    db.session.commit()
    return _command_response(command, published, created)

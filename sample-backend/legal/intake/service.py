from datetime import date, datetime
from hashlib import sha256
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from app.extensions import db
from legal.domain.models import BudgetTransferLine, DocumentReference, FieldProvenance, normalize_decimal
from legal.infrastructure.models import (
    ExampleVersionRecord,
    FactAssertionRecord,
    FieldProvenanceRecord,
    FormInstanceRecord,
    HumanTaskRecord,
    IntakeQuestionRequestRecord,
    IntakeIntentRecord,
    PrecedentSearchRunRecord,
)
from legal.workflows.loader import WorkflowPack


def persist_intake_intent(
    case_id: str,
    request_text: str,
    intent,
    *,
    run_id: str | None = None,
    step_run_id: str | None = None,
) -> IntakeIntentRecord:
    existing = IntakeIntentRecord.query.filter_by(case_id=case_id).first()
    if existing is not None:
        return existing
    record = IntakeIntentRecord(
        id=str(uuid4()), case_id=case_id, run_id=run_id, step_run_id=step_run_id,
        schema_version=1,
        status="needs_clarification" if intent.clarification_required else "compiled",
        request_text_hash=sha256(request_text.encode("utf-8")).hexdigest(),
        intent_json=intent.model_dump(mode="json"), classifier=intent.classifier,
        classifier_version=intent.classifier_version, provider=intent.provider,
        model=intent.model, error=intent.error,
    )
    db.session.add(record)
    db.session.flush()
    record_intent_facts(case_id, intent.known_facts, f"intake_intent:{record.id}")
    return record


def record_intent_facts(case_id: str, facts: dict[str, Any], source_ref: str) -> None:
    value_types = {
        "amount": "currency", "fiscal_year": "number", "budget_transfers": "budget_transfer_table",
        "source_budget": "budget_allocation", "target_budget": "budget_allocation",
        "informe_hacienda": "document_reference",
    }
    for key, value in facts.items():
        if _blank(value):
            continue
        previous = _latest_fact(case_id, key)
        if previous is not None and previous.value_json.get("value") == value:
            continue
        db.session.add(FactAssertionRecord(
            id=str(uuid4()), case_id=case_id, key=key, value_json={"value": value},
            value_type=value_types.get(key, "text"), source_type="user_message", source_ref=source_ref,
            confidence="1.0", verification_status="unverified",
            supersedes_id=previous.id if previous else None,
        ))
    db.session.flush()


def create_form(
    case_id: str,
    pack: WorkflowPack,
    prefill: dict | None = None,
    *,
    workflow_run_id: str | None = None,
    step_run_id: str | None = None,
) -> FormInstanceRecord | None:
    """Compile only unresolved intake questions and persist all provenance."""
    latest_facts = _latest_facts(case_id)
    known = {key: item.value_json.get("value") for key, item in latest_facts.items()}
    known.update(prefill or {})
    search = PrecedentSearchRunRecord.query.filter_by(case_id=case_id).order_by(
        PrecedentSearchRunRecord.started_at.desc()
    ).first()
    precedent_fields: set[str] = set()
    precedent_ref = None
    if search and search.selected_example_version_id:
        example = db.session.get(ExampleVersionRecord, search.selected_example_version_id)
        if example and example.validation_status == "institutionally_validated":
            precedent_fields = set((example.profile_json or {}).get("required_fields") or [])
            precedent_ref = example.id

    unresolved_required = [field for field in pack.fields if field.required and _blank(known.get(field.key))]
    request_record = IntakeQuestionRequestRecord(
        id=str(uuid4()), case_id=case_id, search_run_id=search.id if search else None,
        workflow_run_id=workflow_run_id, step_run_id=step_run_id,
        status="pending" if unresolved_required else "answered",
        questions_json=[], answers_json=known, errors_json={},
        answered_at=None if unresolved_required else datetime.utcnow(),
    )
    db.session.add(request_record)
    db.session.flush()

    if not unresolved_required:
        _persist_provenance(
            case_id, request_record.id, None, pack, known, latest_facts, precedent_fields, precedent_ref,
        )
        return None

    # Optional fields remain available while required intake is open, but known values are never asked again.
    visible_fields = [field for field in pack.fields if _blank(known.get(field.key))]
    questions = []
    for field in visible_fields:
        source_type = "validated_precedent_structure" if field.key in precedent_fields else "workflow"
        provenance = FieldProvenance(
            field_key=field.key, source_type=source_type,
            source_ref=search.selected_example_version_id if source_type == "validated_precedent_structure" else f"{pack.id}:v{pack.version}",
            reason=field.reason, requires_confirmation=True,
        )
        payload = field.model_dump(mode="json")
        payload["provenance"] = provenance.model_dump(mode="json")
        questions.append(payload)
    request_record.questions_json = questions

    latest = FormInstanceRecord.query.filter_by(case_id=case_id).order_by(FormInstanceRecord.version.desc()).first()
    version = 1 if latest is None else latest.version + 1
    form = FormInstanceRecord(
        id=str(uuid4()), case_id=case_id, version=version, workflow_pack_id=pack.id,
        workflow_pack_version=pack.version, status="open",
        schema_json={
            "title": pack.form_title,
            "description": pack.form_description,
            "sections": _form_sections(pack, questions),
        },
        answers_json={}, errors_json={},
    )
    task = HumanTaskRecord(
        id=str(uuid4()), case_id=case_id, task_type="complete_form", status="open",
        payload_json={"form_id": form.id, "question_request_id": request_record.id},
    )
    db.session.add_all([form, task])
    db.session.flush()
    request_record.form_id = form.id
    request_record.human_task_id = task.id
    _persist_provenance(
        case_id, request_record.id, form.id, pack, known, latest_facts, precedent_fields, precedent_ref,
    )
    return form


def _form_sections(pack: WorkflowPack, questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key = {item["key"]: item for item in questions}
    if not pack.sections:
        return [{
            "id": "intake", "title": pack.form_title, "description": pack.form_description,
            "fields": questions,
        }]
    sections = []
    for section in pack.sections:
        fields = [by_key[key] for key in section.field_keys if key in by_key]
        if fields:
            sections.append({**section.model_dump(mode="json", exclude={"field_keys"}), "fields": fields})
    return sections


def _persist_provenance(
    case_id, request_id, form_id, pack, known, latest_facts, precedent_fields, precedent_ref,
):
    for field in pack.fields:
        fact = latest_facts.get(field.key)
        if field.key in known and not _blank(known[field.key]):
            source_type = "user_message" if fact and fact.source_type == "user_message" else "persisted_fact"
            source_ref = fact.source_ref if fact else "prefill"
            reason = f"El usuario aportó explícitamente {field.label}; se conserva sin inferencias y requiere confirmación."
            value = known[field.key]
        else:
            source_type = "validated_precedent_structure" if field.key in precedent_fields else "workflow"
            source_ref = None if source_type == "workflow" else precedent_ref
            reason = field.reason
            value = None
        db.session.add(FieldProvenanceRecord(
            id=str(uuid4()), case_id=case_id, question_request_id=request_id, form_id=form_id,
            field_key=field.key, source_type=source_type, source_ref=source_ref,
            reason=reason, value_json={"value": value} if value is not None else None,
            requires_confirmation=True,
        ))
    db.session.flush()


def submit_form(form: FormInstanceRecord, pack: WorkflowPack, answers: dict, partial: bool) -> dict[str, Any]:
    request_record = IntakeQuestionRequestRecord.query.filter_by(form_id=form.id).first()
    merged = dict(form.answers_json or {})
    merged.update(answers)
    validation_answers = {**((request_record.answers_json or {}) if request_record else {}), **merged}
    errors = validate_answers(pack, validation_answers, require_complete=not partial)
    complete = not partial and not errors
    form.answers_json = merged
    form.errors_json = errors
    form.updated_at = datetime.utcnow()
    form.status = "submitted" if complete else "partial"
    form.submitted_at = datetime.utcnow() if complete else None
    if request_record:
        request_record.answers_json = validation_answers
        request_record.errors_json = errors
        request_record.updated_at = datetime.utcnow()
        request_record.status = "answered" if complete else ("partial" if partial else "pending")
        request_record.answered_at = datetime.utcnow() if complete else None
    if complete:
        HumanTaskRecord.query.filter_by(case_id=form.case_id, task_type="complete_form", status="open").update(
            {"status": "completed", "completed_at": datetime.utcnow()}
        )
        _record_facts(form.case_id, merged, pack)
    db.session.flush()
    return errors


def validate_answers(pack: WorkflowPack, answers: dict, require_complete: bool = True) -> dict[str, Any]:
    errors: dict[str, Any] = {}
    for field in pack.fields:
        value = answers.get(field.key)
        if require_complete and field.required and _blank(value):
            errors[field.key] = {"code": "required", "message": "Este dato es obligatorio."}
            continue
        if _blank(value):
            continue
        try:
            if field.field_type == "currency":
                amount = Decimal(normalize_decimal(value))
                minimum = field.validation_rules.get("min")
                if minimum is not None and amount <= Decimal(str(minimum)):
                    errors[field.key] = {"code": "must_be_positive", "message": "El importe debe ser mayor que cero."}
            elif field.field_type == "date":
                date.fromisoformat(str(value))
            elif field.field_type == "number" and field.validation_rules.get("integer"):
                number = int(value)
                if str(number) != str(value).strip() or not (
                    int(field.validation_rules.get("min", number)) <= number <= int(field.validation_rules.get("max", number))
                ):
                    raise ValueError("invalid integer range")
            elif field.field_type == "document_reference":
                _validate_document(field.key, value, field.validation_rules)
            elif field.field_type in {"budget_transfer_table", "budget_table"}:
                _validate_budget_lines(value)
            minimum_length = field.validation_rules.get("min_length")
            if minimum_length and isinstance(value, str) and len(value.strip()) < int(minimum_length):
                errors[field.key] = {"code": "too_short", "message": "El dato es demasiado breve."}
        except ValidationError as exc:
            errors[field.key] = {"code": "invalid_shape", "message": _validation_message(exc), "details": exc.errors(include_url=False)}
        except (ValueError, TypeError, InvalidOperation) as exc:
            errors[field.key] = {"code": "invalid_value", "message": str(exc) or "El valor no es válido."}
    for field in pack.fields:
        other = field.validation_rules.get("after")
        if other and not _blank(answers.get(field.key)) and not _blank(answers.get(other)):
            try:
                if date.fromisoformat(str(answers[field.key])) <= date.fromisoformat(str(answers[other])):
                    errors[field.key] = {
                        "code": "must_be_after", "message": f"La fecha debe ser posterior a {other}.", "related_field": other,
                    }
            except ValueError:
                errors.setdefault(field.key, {"code": "invalid_date", "message": "La fecha no es válida."})
    return errors


def _validate_document(field_key: str, value: Any, rules: dict[str, Any]) -> None:
    values = value if rules.get("multiple") and isinstance(value, list) else [value]
    if rules.get("multiple") and not isinstance(value, list):
        raise ValueError("Se esperaba una lista de referencias documentales.")
    for raw in values:
        document = DocumentReference.model_validate(raw)
        expected = rules.get("document_type")
        title = (document.title or "").casefold()
        if expected == "informe_hacienda" and (
            document.document_type == "resolucion" or "resolución" in title or "resolucion" in title
        ):
            raise ValueError("El campo informe_hacienda requiere un Informe de Hacienda; una Resolución no coincide con ese tipo documental.")
        if expected and document.document_type != expected:
            raise ValueError(f"El campo {field_key} requiere un documento de tipo {expected}, no {document.document_type}.")
        issuer_contains = [str(item).casefold() for item in rules.get("issuer_contains", [])]
        if document.issuer and issuer_contains and not any(item in document.issuer.casefold() for item in issuer_contains):
            raise ValueError(f"El emisor de {field_key} no coincide con la oficina esperada.")


def _validate_budget_lines(value: Any) -> None:
    if not isinstance(value, list) or not value:
        raise ValueError("Debe ingresar al menos una fila presupuestal completa.")
    seen = set()
    for index, raw in enumerate(value, start=1):
        if not isinstance(raw, dict) or not raw or all(_blank(item) for item in raw.values()):
            raise ValueError(f"La fila presupuestal {index} está vacía.")
        line = BudgetTransferLine.model_validate(raw)
        key = (line.origin.canonical_id(), line.destination.canonical_id(), line.amount)
        if key in seen:
            raise ValueError(f"La fila presupuestal {index} está duplicada.")
        seen.add(key)
    # Each line is intrinsically balanced: one debit and one credit for the same Decimal amount.
    debits = sum((BudgetTransferLine.model_validate(item).amount for item in value), Decimal("0"))
    credits = sum((BudgetTransferLine.model_validate(item).amount for item in value), Decimal("0"))
    if debits != credits:
        raise ValueError("Los débitos y créditos presupuestales no están balanceados.")


def _validation_message(exc: ValidationError) -> str:
    messages = [str(item.get("msg", "Valor inválido")) for item in exc.errors()]
    return " ".join(messages)


def _record_facts(case_id: str, answers: dict, pack: WorkflowPack) -> None:
    types = {field.key: field.field_type for field in pack.fields}
    for key, value in answers.items():
        previous = _latest_fact(case_id, key)
        field_type = types.get(key, "text")
        normalized = normalize_decimal(value) if field_type == "currency" else value
        if previous is not None and previous.value_json.get("value") == normalized:
            continue
        db.session.add(FactAssertionRecord(
            id=str(uuid4()), case_id=case_id, key=key, value_json={"value": normalized},
            value_type=field_type, source_type="user_answer", source_ref="intake_question_request",
            confidence="1.0", verification_status="unverified",
            supersedes_id=previous.id if previous else None,
        ))


def _latest_fact(case_id: str, key: str):
    return FactAssertionRecord.query.filter_by(case_id=case_id, key=key).order_by(
        FactAssertionRecord.recorded_at.desc()
    ).first()


def _latest_facts(case_id: str) -> dict[str, FactAssertionRecord]:
    result = {}
    for fact in FactAssertionRecord.query.filter_by(case_id=case_id).order_by(FactAssertionRecord.recorded_at.desc()):
        result.setdefault(fact.key, fact)
    return result


def _blank(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}

from pathlib import Path
from uuid import uuid4

from app.extensions import db
from legal.agents.intent_compiler import IntentCompiler
from legal.agents.specs import SPECIALIST_SPECS
from app.api.agent import _legal_workflow_started_message
from legal.application.command_service import LegalCommandService
from legal.domain.commands import CreateLegalCase
from legal.domain.enums import RiskTier, TaskFamily
from legal.domain.models import DocumentReference, VerifiedAuthorityInput
from legal.infrastructure.models import (
    FactAssertionRecord, IntakeIntentRecord, IntakeQuestionRequestRecord,
    PrecedentSearchRunRecord,
)
from legal.intake.service import persist_intake_intent, validate_answers
from legal.precedents.service import search_precedents
from legal.workflows.loader import WorkflowPackRegistry


def _case(app, title="Caso de prueba"):
    command = CreateLegalCase(
        command_id=uuid4(), case_id=uuid4(), actor_user_id=1,
        idempotency_key=f"intake-{uuid4()}", title=title,
        task_family=TaskFamily.RESOLUTION_DRAFTING, jurisdiction="lavalleja",
        risk_tier=RiskTier.HIGH,
    )
    LegalCommandService().create_case(command)
    return str(command.case_id)


def _csrf(client):
    return client.get("/api/auth/csrf").get_json()["csrf_token"]


def _post(client, path, key, payload=None):
    return client.post(path, json=payload, headers={"Idempotency-Key": key, "X-CSRFToken": _csrf(client)})


class VerifiedIntakeProvider:
    def retrieve(self, case_id, issues, facts):
        return [VerifiedAuthorityInput(
            issue_id=issue.issue_id,
            source_id=f"INTAKE-OFFICIAL-{issue.issue_id}",
            source_class="official_primary",
            jurisdiction="uruguay",
            exact_text=f"Texto oficial controlado para {issue.category}.",
            proposition=f"Proposición verificada para {issue.category}.",
            norm_id=f"INTAKE-{issue.issue_id}",
            authenticity_verified=True,
            applicability_verified=True,
        ) for issue in issues]


def test_aliases_are_versioned_exact_and_truthfully_deterministic():
    compiler = IntentCompiler()
    for text in (
        "resolución de trasposición de rubros",
        "resolucion para transposicion presupuestal",
        "resolución por transferencia de rubros",
        "resolución de ajuste presupuestal",
        "resolución por trasnspocision",
    ):
        intent = compiler.compile(text, TaskFamily.RESOLUTION_DRAFTING)
        assert intent.subtype == "fund_transposition"
        assert intent.selected_workflow_version == 2
        assert intent.classifier == "deterministic"
        assert intent.provider is None
        assert intent.classification_basis[0] == "alias_config:intake-aliases-v1"

    assert compiler.compile("resolución para una quita de horas").subtype == "hours_removal"
    assert compiler.compile("resolución de donación").subtype == "donation"
    assert compiler.compile("resolución para renovar el contrato").subtype == "contract_renewal"
    assert compiler.compile("resolución para una nueva contratación").subtype == "new_contract"


def test_workflow_v2_and_golden_precedent_are_retrieved_normally(app):
    with app.app_context():
        pack = WorkflowPackRegistry().get("resolution.fund_transposition").pack
        assert pack.version == 2
        assert "budget_transfers" in {field.key for field in pack.fields}
        assert "enabling_law" not in {field.key for field in pack.fields}
        financing = next(field for field in pack.fields if field.key == "financing")
        assert financing.required is False
        assert "cuando corresponda" in financing.label
        case_id = _case(app)
        intent = IntentCompiler().compile("Resolución para trasposición de rubros")
        run = search_precedents(case_id, pack, intent)
        db.session.commit()
        assert run.status == "completed"
        assert run.match_label == "exact"
        assert run.calibrated_confidence is None
        assert run.searched_count == 12
        assert run.index_status_json["inspected_count"] == 12
        assert run.index_status_json["eligible_count"] == 1
        assert run.index_status_json["candidate_count"] == 1
        assert run.index_status_json["generic_fallback_count"] == 0
        selected = next(item for item in run.candidates_json if item["example_version_id"] == run.selected_example_version_id)
        assert selected["stable_key"] == "IDL-RES-2629-026"
        assert selected["validation_status"] == "institutionally_validated"
        assert all(item["stable_key"] != "EX-RES-TRASPOSICION-RUBROS" for item in run.candidates_json)


def test_unavailable_search_never_claims_a_match(app, tmp_path):
    with app.app_context():
        case_id = _case(app)
        pack = WorkflowPackRegistry().get("resolution.fund_transposition").pack
        intent = IntentCompiler().compile("Resolución para trasposición de rubros")
        run = search_precedents(case_id, pack, intent, root=tmp_path / "missing")
        assert run.status == "unavailable"
        assert run.match_label == "none"
        assert run.selected_example_version_id is None
        assert run.searched_count == 0


def test_initial_message_is_honest_for_async_unavailable_and_no_match(app, tmp_path):
    with app.app_context():
        case_id = _case(app)
        intent = IntentCompiler().compile("Necesito transponer rubros")
        persist_intake_intent(case_id, "Necesito transponer rubros", intent)
        pending = _legal_workflow_started_message(case_id, asynchronous=True)
        failed_dispatch = _legal_workflow_started_message(case_id, asynchronous=True, dispatched=False)
        assert "búsqueda de antecedentes está pendiente" in pending
        assert "No se pudo despachar" in failed_dispatch
        assert "seleccionado" not in pending + failed_dispatch

        pack = WorkflowPackRegistry().get("resolution.fund_transposition").pack
        search_precedents(case_id, pack, intent, root=tmp_path / "missing")
        unavailable = _legal_workflow_started_message(case_id)
        assert "corpus local de antecedentes no está disponible" in unavailable
        assert "seleccionado" not in unavailable

        renewal_case = _case(app, "Renovación")
        renewal_intent = IntentCompiler().compile("Resolución para renovar el contrato")
        persist_intake_intent(renewal_case, "Resolución para renovar el contrato", renewal_intent)
        renewal_pack = WorkflowPackRegistry().get("resolution.contract_renewal").pack
        search_precedents(renewal_case, renewal_pack, renewal_intent)
        no_match = _legal_workflow_started_message(renewal_case)
        assert "comparabilidad material suficiente" in no_match
        assert "Antecedente estructural seleccionado" not in no_match


def test_document_and_budget_validation_are_structured_and_decimal_safe():
    pack = WorkflowPackRegistry().get("resolution.fund_transposition").pack
    valid = {
        "informe_hacienda": {
            "document_type": "informe_hacienda", "number": "1169/026", "date": "2026-06-25",
        },
        "oficio_contaduria": {
            "document_type": "oficio_contaduria", "number": "182/026", "date": "2026-06-25",
        },
        "budget_transfers": [
            {
                "origin": {"program": "101", "object": "299"},
                "destination": {"program": "101", "object": "399"},
                "amount": "1.234,50",
            },
            {
                "origin": {"program": "102"},
                "destination": {"program": "103"},
                "amount": "200,25",
            },
        ],
        "fiscal_year": 2026,
    }
    assert validate_answers(pack, valid, require_complete=False) == {}

    mismatch = dict(valid)
    mismatch["informe_hacienda"] = {
        "document_type": "informe_hacienda", "number": "2629/026", "title": "Resolución N° 2.629/026",
    }
    errors = validate_answers(pack, mismatch, require_complete=False)
    assert errors["informe_hacienda"]["code"] == "invalid_value"
    assert "una Resolución no coincide" in errors["informe_hacienda"]["message"]

    duplicate = dict(valid)
    duplicate["budget_transfers"] = [valid["budget_transfers"][0], valid["budget_transfers"][0]]
    assert "duplicada" in validate_answers(pack, duplicate, require_complete=False)["budget_transfers"]["message"]
    blank = dict(valid)
    blank["budget_transfers"] = [{}]
    assert "vacía" in validate_answers(pack, blank, require_complete=False)["budget_transfers"]["message"]

    wrong_type = dict(valid)
    wrong_type["informe_hacienda"] = {
        "document_type": "resolucion", "number": "2629/026",
    }
    assert validate_answers(pack, wrong_type, require_complete=False)["informe_hacienda"]["message"] == (
        "El campo informe_hacienda requiere un Informe de Hacienda; una Resolución no coincide con ese tipo documental."
    )


def test_document_reference_expanded_shape_keeps_compatibility_ids():
    reference = DocumentReference.model_validate({
        "document_type": "anexo_presupuestal", "year": 2026,
        "issuer": "Dirección General de Hacienda", "upload_id": 17,
        "source_url": "https://example.test/anexo", "notes": "Anexo aportado",
    }).model_dump(mode="json")
    assert reference["upload_id"] == reference["source_document_id"] == 17
    assert reference["number"] is None
    assert DocumentReference(document_type="expediente", number="2026-77").document_type == "expediente"


def test_natural_language_transposition_extracts_safe_facts_and_suppresses_questions(authed_client, app):
    app.extensions["legal_authority_provider"] = VerifiedIntakeProvider()
    text = "Necesito transponer $150.000 del rubro A al rubro B, ejercicio 2026, según informe de Hacienda N.º 45/026."
    intent = IntentCompiler().compile(text)
    assert intent.subtype == "fund_transposition"
    assert intent.known_facts["amount"] == "150000.00"
    assert intent.known_facts["source_budget"] == {"identifier": "A"}
    assert intent.known_facts["target_budget"] == {"identifier": "B"}
    assert intent.known_facts["fiscal_year"] == 2026
    assert intent.known_facts["informe_hacienda"] == {
        "document_type": "informe_hacienda", "number": "45/026", "issuer": "Hacienda",
    }
    assert intent.known_facts["budget_transfers"] == [{
        "origin": {"identifier": "A"}, "destination": {"identifier": "B"}, "amount": "150000.00",
    }]

    response = _post(authed_client, "/api/legal/cases", "natural-fund-create", {
        "title": text, "task_family": "resolution_drafting",
        "jurisdiction": "lavalleja", "risk_tier": "high",
    })
    case_id = response.get_json()["case"]["id"]
    _post(authed_client, f"/api/legal/cases/{case_id}/commands/start", "natural-fund-start")
    workspace = authed_client.get(f"/api/legal/cases/{case_id}/workspace").get_json()
    asked = {
        field["key"] for section in workspace["form"]["schema_json"]["sections"]
        for field in section["fields"]
    }
    assert {"budget_transfers", "fiscal_year", "informe_hacienda"}.isdisjoint(asked)
    assert {"amount", "source_budget", "target_budget", "fiscal_year", "informe_hacienda"} <= set(
        workspace["intake_intent"]["known_facts"]
    )
    assert workspace["intake_summary"]["act_label"] == "transposición de rubros"
    assert workspace["intake_summary"]["generic_fallback_count"] == 0
    assert workspace["intake_summary"]["selected_precedent_number"] == "2.629/026"
    assert "confidence" not in workspace["precedent"]

    with app.app_context():
        message = _legal_workflow_started_message(case_id)
    assert "Identifiqué la actuación como transposición de rubros." in message
    assert "Resolución N° 2.629/026" in message
    assert "número 2.629/026" in message
    assert "https://www.gub.uy/intendencia-lavalleja/institucional/normativa/resolucion-n-2629026" in message
    assert "Expediente y unidad" in message
    assert "workflow" not in message
    assert "Armé el plan" not in message
    assert "60%" not in message

    form_id = workspace["form"]["id"]
    complete = _post(authed_client, f"/api/legal/cases/{case_id}/commands/submit-form", "natural-fund-complete", {
        "form_id": form_id,
        "answers": {
            "expediente": "2026-77", "unit": "Hacienda",
            "oficio_contaduria": {
                "document_type": "oficio_contaduria", "number": "46/026", "issuer": "Contaduría",
            },
            "motivation": "Adecuación del presupuesto vigente",
        },
        "partial": False,
    })
    assert complete.status_code == 202
    with app.app_context():
        fact_ids = [item.id for item in FactAssertionRecord.query.filter_by(case_id=case_id).all()]
    _post(authed_client, f"/api/legal/cases/{case_id}/commands/confirm-facts", "natural-fund-confirm", {
        "fact_ids": fact_ids,
    })
    completed_workspace = authed_client.get(f"/api/legal/cases/{case_id}/workspace").get_json()
    assert completed_workspace["case"]["state"] == "ready_for_human_review"
    assert completed_workspace["draft"]["status"] == "grounded_draft"
    assert any(task["task_type"] == "review_draft" and task["status"] == "open" for task in completed_workspace["human_tasks"])
    events = authed_client.get(f"/api/legal/cases/{case_id}/events").get_json()["events"]
    event_types = [item["event_type"] for item in events]
    for event_type in (
        "intake.planning.started", "intake.questions.compiled", "intake.waiting_user",
        "intake.answers.submitted", "intake.answers.validated", "intake.resumed",
    ):
        assert event_type in event_types


def test_final_fund_transposition_scenario_is_specific(authed_client, app):
    text = "Me vas a ayudar a redactar una resolución de transposición de rubros para la Intendencia de Lavalleja."
    response = _post(authed_client, "/api/legal/cases", "final-fund-create", {
        "title": text,
        "task_family": "resolution_drafting",
        "jurisdiction": "lavalleja",
        "risk_tier": "high",
    })
    case_id = response.get_json()["case"]["id"]
    _post(authed_client, f"/api/legal/cases/{case_id}/commands/start", "final-fund-start")
    workspace = authed_client.get(f"/api/legal/cases/{case_id}/workspace").get_json()

    assert workspace["intake_intent"]["subtype"] == "fund_transposition"
    assert workspace["case"]["workflow_pack_id"] == "resolution.fund_transposition"
    assert workspace["case"]["workflow_pack_version"] == 2
    assert workspace["resolved_precedent"]["number"] == "2.629/026"
    assert workspace["precedent_search"]["status"] == "completed"
    assert workspace["precedent_search"]["searched_count"] == 12
    assert workspace["intake_summary"]["generic_fallback_count"] == 0
    section_titles = [section["title"] for section in workspace["form"]["schema_json"]["sections"]]
    assert section_titles == [
        "Expediente y unidad",
        "Documentos de origen",
        "Movimientos presupuestales",
        "Motivación",
        "Ejercicio fiscal y financiación",
        "Anexos y ruta administrativa",
    ]
    serialized = str(workspace)
    for forbidden in ("60%", "5 datos necesarios", "No existe antecedente de la misma tipologia"):
        assert forbidden not in serialized


def test_labelled_transposition_facts_are_normalized():
    intent = IntentCompiler().compile(
        "Transposición; Importe: $150.000; Rubro origen: A; Rubro destino: B; "
        "Ejercicio: 2026; Informe de Hacienda: N.º 45/026",
        TaskFamily.RESOLUTION_DRAFTING,
    )
    assert intent.known_facts["amount"] == "150000.00"
    assert intent.known_facts["budget_transfers"][0]["origin"] == {"identifier": "A"}
    assert intent.known_facts["fiscal_year"] == 2026
    assert intent.known_facts["informe_hacienda"]["number"] == "45/026"


def test_known_message_fact_is_not_asked_and_question_survives_partial_reload(authed_client, app):
    response = _post(authed_client, "/api/legal/cases", "fund-known-create", {
        "title": "Resolución para trasposición de rubros; Expediente: 2026-77",
        "task_family": "resolution_drafting", "jurisdiction": "lavalleja", "risk_tier": "high",
    })
    case_id = response.get_json()["case"]["id"]
    _post(authed_client, f"/api/legal/cases/{case_id}/commands/start", "fund-known-start")
    workspace = authed_client.get(f"/api/legal/cases/{case_id}/workspace").get_json()
    keys = [
        field["key"] for section in workspace["form"]["schema_json"]["sections"] for field in section["fields"]
    ]
    assert "expediente" not in keys
    assert "1169/026" not in str(workspace["form"])
    assert workspace["intake_intent"]["known_facts"] == {"expediente": "2026-77"}
    assert workspace["question_request"]["status"] == "pending"
    assert "calibrated_confidence" not in workspace["precedent_search"]

    form_id = workspace["form"]["id"]
    first = _post(authed_client, f"/api/legal/cases/{case_id}/commands/submit-form", "fund-partial", {
        "form_id": form_id, "answers": {"unit": "Hacienda"}, "partial": True,
    })
    replay = _post(authed_client, f"/api/legal/cases/{case_id}/commands/submit-form", "fund-partial", {
        "form_id": form_id, "answers": {"unit": "Hacienda"}, "partial": True,
    })
    assert first.status_code == replay.status_code == 202
    assert replay.get_json()["idempotent_replay"] is True
    reloaded = authed_client.get(f"/api/legal/cases/{case_id}/workspace").get_json()
    assert reloaded["question_request"]["status"] == "partial"
    assert reloaded["question_request"]["answers"]["unit"] == "Hacienda"
    with app.app_context():
        assert IntakeIntentRecord.query.filter_by(case_id=case_id).count() == 1
        assert PrecedentSearchRunRecord.query.filter_by(case_id=case_id).count() == 1
        assert IntakeQuestionRequestRecord.query.filter_by(case_id=case_id).count() == 1
        assert FactAssertionRecord.query.filter_by(case_id=case_id, key="expediente", source_type="user_message").one()
        assert FactAssertionRecord.query.filter_by(case_id=case_id, key="unit").count() == 0


def test_examples_cli_is_honest_and_does_not_approve(app):
    runner = app.test_cli_runner()
    compiled = runner.invoke(args=["examples", "compile"])
    assert compiled.exit_code == 0
    assert "index=sql_filesystem" in compiled.output
    reindexed = runner.invoke(args=["examples", "reindex"])
    assert reindexed.exit_code == 0
    assert "qdrant=not_used" in reindexed.output
    validated = runner.invoke(args=["examples", "validate"])
    assert validated.exit_code == 0
    assert "approvals_changed=0" in validated.output
    diagnosed = runner.invoke(args=["examples", "diagnose"])
    assert diagnosed.exit_code == 0
    assert "collection=sql_filesystem" in diagnosed.output


def test_production_messages_have_no_removed_hardcoding():
    backend = Path(__file__).resolve().parents[1]
    agent_source = (backend / "app" / "api" / "agent.py").read_text(encoding="utf-8")
    precedent_source = (backend / "legal" / "precedents" / "service.py").read_text(encoding="utf-8")
    assert "Armé el plan de trabajo" not in agent_source
    assert '"0.6"' not in precedent_source
    assert "deterministic_seam" not in (backend / "legal" / "workflows" / "engine.py").read_text(encoding="utf-8")
    assert SPECIALIST_SPECS["precedent_explorer"].tools == ("search_examples",)
    assert "read_document" not in SPECIALIST_SPECS["analyzer"].tools

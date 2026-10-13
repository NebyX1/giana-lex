from dataclasses import replace

import pytest

from app import create_app
from config import settings
from legal_knowledge.indexing import LegalQdrantIndex
from schemas import (
    DraftOutput,
    DynamicForm,
    ExampleMatch,
    FormField,
    IntakeOutput,
    LLMRun,
    RevisionOutput,
    RiskFinding,
    SkillOutput,
)


@pytest.fixture(autouse=True)
def offline_index(monkeypatch):
    monkeypatch.setattr(LegalQdrantIndex, "search_taxonomy", lambda *args: [])
    monkeypatch.setattr(LegalQdrantIndex, "health", lambda *args: {"connected": False})


class FakeAgents:
    def _run(self, output):
        return LLMRun(
            output=output,
            usage={"requests": 1, "input_tokens": 100, "output_tokens": 40, "total_tokens": 140},
            duration_ms=5,
        )


    def intake(self, context):
        filename = context["candidatos"][0]["filename"] if context["candidatos"] else ""
        return self._run(
            IntakeOutput(
                match_status="partial",
                assistant_message="Encontre un antecedente parcialmente comparable.",
                matched_examples=[ExampleMatch(filename=filename, relevance="partial", reason="Estructura comparable")],
                form=DynamicForm(
                    title="Informacion necesaria",
                    fields=[FormField(id="decision", label="Decision", field_type="textarea")],
                ),
            )
        )

    def draft(self, context):
        return self._run(
            DraftOutput(
                status="draft_ready",
                assistant_message="Borrador preparado.",
                draft_markdown="# RESOLUCION\n\n## RESUELVE\n\n1°.- Aprobar la decision proporcionada.",
            )
        )

    def revision(self, context):
        return self._run(
            RevisionOutput(
                assistant_message="Modificacion aplicada.",
                draft_markdown=context["borrador_vigente"] + "\n\n2°.- Comuniquese.",
            )
        )

    def skill(self, key, instructions, context):
        return self._run(
            SkillOutput(
                status="complete",
                summary=f"Analisis {key} completo con informacion limitada.",
                overall_risk="unknown",
                findings=[
                    RiskFinding(
                        title="Revision necesaria",
                        risk_level="unknown",
                        explanation="No hay fuentes suficientes para afirmar un riesgo.",
                        affected_actors=[],
                    )
                ],
            )
        )


class RepeatingQuestionAgents(FakeAgents):
    def skill(self, key, instructions, context):
        return self._run(
            SkillOutput(
                status="needs_input",
                summary="Falta contexto.",
                overall_risk="unknown",
                questions=DynamicForm(
                    title="Aclaracion",
                    fields=[FormField(id="contexto", label="Contexto", field_type="text")],
                ),
            )
        )


@pytest.fixture
def client(tmp_path):
    test_settings = replace(settings, database_path=tmp_path / "test.sqlite3")
    app = create_app(test_settings, agents=FakeAgents(), database_path=test_settings.database_path)
    app.testing = True
    return app.test_client()


def test_complete_api_flow_without_paid_calls(client):
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json["examples_count"] == len(list(settings.examples_dir.glob("*.md")))

    created = client.post(
        "/api/conversations",
        json={"message": "Necesito una resolucion de contratacion de arrendamiento de obra."},
    )
    assert created.status_code == 200
    assert created.json["stage"] == "collecting_info"
    assert created.json["classification_warning"]
    assert created.json["form"]["fields"][0]["id"] == "decision"
    assert created.json["example_search_status"] in {"direct", "analogies", "out_of_scope", "catalog_empty"}
    assert created.json["debug"]["tools_executed"] == ["search_resolution_types", "load_mold"]
    conversation_id = created.json["conversation_id"]

    listed = client.get("/api/conversations")
    assert listed.status_code == 200
    assert listed.json["conversations"][0]["conversation_id"] == conversation_id
    assert listed.json["conversations"][0]["title"] == "Necesito una resolucion de contratacion de arrendamiento de obra."

    drafted = client.post(
        f"/api/conversations/{conversation_id}/form",
        json={"answers": {"decision": "Contratar la obra descrita por el solicitante"}},
    )
    assert drafted.json["stage"] == "draft_review"
    assert "RESOLUCION" in drafted.json["draft"]
    assert drafted.json["form_history"][0]["answers"]["decision"] == "Contratar la obra descrita por el solicitante"
    assert drafted.json["form_history"][0]["form"]["fields"][0]["id"] == "decision"

    revised = client.post(
        f"/api/conversations/{conversation_id}/revise",
        json={"instructions": "Agregar comunicacion"},
    )
    assert revised.json["revision_count"] == 1
    assert "Comuniquese" in revised.json["draft"]

    checked = client.post(f"/api/conversations/{conversation_id}/check")
    assert checked.status_code == 200
    assert checked.json["verification"]["draft_hash"]
    approved = client.post(f"/api/conversations/{conversation_id}/approve")
    assert approved.json["stage"] == "approved"
    assert {skill["key"] for skill in approved.json["skills"]} == {"political_risk", "legal_risk"}

    for key in ("political_risk", "legal_risk"):
        result = client.post(f"/api/conversations/{conversation_id}/skills/{key}")
        assert result.status_code == 200
        assert result.json["skill_results"][key]["status"] == "complete"

    exported = client.get(f"/api/conversations/{conversation_id}/export")
    assert exported.status_code == 200
    assert exported.data[:2] == b"PK"


def test_cannot_skip_workflow_stages(client):
    created = client.post("/api/conversations", json={"message": "Preparar una resolucion"}).json
    conversation_id = created["conversation_id"]
    assert client.post(f"/api/conversations/{conversation_id}/approve").status_code == 409
    assert client.post(f"/api/conversations/{conversation_id}/skills/legal_risk").status_code == 409
    assert client.get(f"/api/conversations/{conversation_id}/export").status_code == 409


def test_greeting_can_continue_into_document_in_same_conversation(client):
    greeting = client.post("/api/conversations", json={"message": "Hola, me puedes ayudar?"})
    assert greeting.status_code == 200
    assert greeting.json["stage"] == "new"
    assert greeting.json["form"] is None
    assert greeting.json["classification_warning"] is None
    conversation_id = greeting.json["conversation_id"]
    followup = client.post(f"/api/conversations/{conversation_id}/message", json={"message": "¿Qué puedes hacer?"})
    assert followup.status_code == 200
    assert followup.json["stage"] == "new"
    assert len(followup.json["intro_messages"]) == 4

    request = "Necesito una resolucion de contratacion de arrendamiento de obra."
    started = client.post(f"/api/conversations/{conversation_id}/message", json={"message": request})
    assert started.status_code == 200
    assert started.json["conversation_id"] == conversation_id
    assert started.json["stage"] == "collecting_info"
    assert started.json["form"]["fields"][0]["id"] == "decision"
    assert len(started.json["intro_messages"]) == 4
    listed = client.get("/api/conversations").json["conversations"]
    assert len(listed) == 1
    assert listed[0]["conversation_id"] == conversation_id
    assert listed[0]["title"] == request
    assert client.post(f"/api/conversations/{conversation_id}/message", json={"message": "Hola"}).status_code == 409


def test_old_untouched_greeting_is_corrected_on_reopen(client):
    from intake_fallback import generic_intake
    from state import ConversationState, Stage

    state = ConversationState(original_request="Hola, me puedes ayudar?", stage=Stage.COLLECTING_INFO,
                              current_form=generic_intake("Hola, me puedes ayudar?").form,
                              classification_warning="No se encontró una tipología específica.")
    client.application.config["ORCHESTRATOR"].storage.save(state)
    restored = client.get(f"/api/conversations/{state.id}")
    assert restored.status_code == 200
    assert restored.json["stage"] == "new"
    assert restored.json["form"] is None
    assert restored.json["classification_warning"] is None
    assert "Sí, puedo ayudarte" in restored.json["message"]
    assert len(client.get(f"/api/conversations/{state.id}").json["intro_messages"]) == 2


def test_greeting_works_even_without_configured_provider(client):
    client.application.config["ORCHESTRATOR"].agents = None
    assert client.post("/api/conversations", json={"message": "Hola"}).status_code == 200
    response = client.post("/api/conversations", json={"message": "Preparar una resolución"})
    assert response.status_code == 400
    assert response.json["error"] == "llm_not_configured"


def test_delete_conversation(client):
    created = client.post(
        "/api/conversations", json={"message": "Conversacion para eliminar"}
    ).json
    conversation_id = created["conversation_id"]

    deleted = client.delete(f"/api/conversations/{conversation_id}")

    assert deleted.status_code == 204
    missing = client.get(f"/api/conversations/{conversation_id}")
    assert missing.status_code == 404
    assert client.get("/api/conversations").json["conversations"] == []
    repeated = client.delete(f"/api/conversations/{conversation_id}")
    assert repeated.status_code == 404


def test_skill_finishes_after_one_question_round(tmp_path):
    test_settings = replace(settings, database_path=tmp_path / "questions.sqlite3")
    app = create_app(test_settings, agents=RepeatingQuestionAgents(), database_path=test_settings.database_path)
    app.testing = True
    client = app.test_client()
    created = client.post("/api/conversations", json={"message": "Preparar resolucion"}).json
    conversation_id = created["conversation_id"]
    client.post(f"/api/conversations/{conversation_id}/form", json={"answers": {"decision": "Resolver"}})
    client.post(f"/api/conversations/{conversation_id}/check")
    client.post(f"/api/conversations/{conversation_id}/approve")

    first = client.post(f"/api/conversations/{conversation_id}/skills/legal_risk")
    assert first.json["skill_results"]["legal_risk"]["status"] == "needs_input"
    second = client.post(
        f"/api/conversations/{conversation_id}/skills/legal_risk",
        json={"answers": {"contexto": "No hay mas informacion"}},
    )
    assert second.status_code == 200
    assert second.json["skill_results"]["legal_risk"]["status"] == "complete"
    assert second.json["skill_results"]["legal_risk"]["questions"] is None

from dataclasses import replace

import pytest

from app import create_app
from config import settings
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
    assert health.json["examples_count"] == 2

    created = client.post(
        "/api/conversations",
        json={"message": "Necesito una resolucion de contratacion de arrendamiento de obra."},
    )
    assert created.status_code == 200
    assert created.json["stage"] == "collecting_info"
    assert created.json["form"]["fields"][0]["id"] == "decision"
    assert created.json["debug"]["tools_executed"] == ["search_examples", "load_mold"]
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

    revised = client.post(
        f"/api/conversations/{conversation_id}/revise",
        json={"instructions": "Agregar comunicacion"},
    )
    assert revised.json["revision_count"] == 1
    assert "Comuniquese" in revised.json["draft"]

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


def test_skill_finishes_after_one_question_round(tmp_path):
    test_settings = replace(settings, database_path=tmp_path / "questions.sqlite3")
    app = create_app(test_settings, agents=RepeatingQuestionAgents(), database_path=test_settings.database_path)
    app.testing = True
    client = app.test_client()
    created = client.post("/api/conversations", json={"message": "Preparar resolucion"}).json
    conversation_id = created["conversation_id"]
    client.post(f"/api/conversations/{conversation_id}/form", json={"answers": {"decision": "Resolver"}})
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

import io
import json

from app.extensions import db
from app.models import AgentSession, ProviderConnection
from legal.infrastructure.models import LegalCaseRecord
from llm.provider import LLMProvider, ProviderResult, ToolCallRequest


RESOLUTION_TEXT = """TEST DATA - NO ES NORMATIVA REAL
RESOLUCION N 1/TEST
VISTO: El expediente tecnico.
RESULTANDO: Que se adjunto informacion de prueba.
CONSIDERANDO: Que corresponde revision humana.
ATENTO: A las fuentes que eventualmente se verifiquen.
RESUELVE:
ARTICULO 1: Someter este texto de prueba a revision.
"""


def _create_session(authed_client, csrf_headers, app):
    with app.app_context():
        provider = ProviderConnection(
            user_id=1,
            provider="ollama",
            display_name="LLM falso",
            auth_mode="none",
            base_url="http://localhost:11434/v1",
            default_model="fake-agent",
        )
        db.session.add(provider)
        db.session.commit()
        provider_id = provider.id
    return authed_client.post(
        "/api/sessions",
        json={"provider_connection_id": provider_id},
        headers=csrf_headers,
    ).get_json()["id"]


class ReviewFlowProvider(LLMProvider):
    def __init__(self, _connection):
        self.step = 0

    def run(self, messages, tools, model=None):
        self.step += 1
        if self.step == 1:
            return ProviderResult(tool_calls=[ToolCallRequest("read-1", "read_document", {"document_id": 1})])
        if self.step == 2:
            assert any(
                message.get("role") == "tool" and "TEST DATA - NO ES NORMATIVA REAL" in message.get("content", "")
                for message in messages
            )
            return ProviderResult(tool_calls=[ToolCallRequest("structure-1", "analyze_resolution", {"text": RESOLUTION_TEXT})])
        if self.step == 3:
            return ProviderResult(tool_calls=[ToolCallRequest("references-1", "extract_legal_references", {"text": RESOLUTION_TEXT})])
        if self.step == 4:
            return ProviderResult(tool_calls=[ToolCallRequest("procedure-1", "review_procedure", {"text": RESOLUTION_TEXT})])
        return ProviderResult(
            text="Revision tecnica: estructura detectada. Las referencias y reglas juridicas deben verificarse con corpus real validado."
        )


def test_review_resolution_end_to_end(authed_client, csrf_headers, app):
    session_id = _create_session(authed_client, csrf_headers, app)
    uploaded = authed_client.post(
        f"/api/documents/sessions/{session_id}",
        data={"file": (io.BytesIO(RESOLUTION_TEXT.encode()), "expediente.txt")},
        headers={"X-CSRFToken": csrf_headers["X-CSRFToken"]},
        content_type="multipart/form-data",
    )
    assert uploaded.status_code == 201
    app.extensions["llm_provider_factory"] = ReviewFlowProvider

    response = authed_client.post(
        f"/api/agent/sessions/{session_id}/run",
        json={
            "content": f"Revise el documento document_id={uploaded.get_json()['id']}.",
            "active_skills": ["auditor-compliance"],
        },
        headers=csrf_headers,
    )
    body = response.get_data(as_text=True)
    assert "agent.completed" in body
    opened = authed_client.get(f"/api/sessions/{session_id}").get_json()
    assert [call["tool_name"] for call in opened["tool_calls"]] == [
        "read_document", "analyze_resolution", "extract_legal_references", "review_procedure"
    ]
    assert all(call["status"] == "completed" for call in opened["tool_calls"])
    assert "corpus real validado" in opened["messages"][-1]["content"]


class FakeRetriever:
    def search(self, query, corpus, top_k=5, **_filters):
        return [{
            "identifier": f"test-{corpus}",
            "text": "TEST DATA - NO ES NORMATIVA REAL",
            "source": f"test-{corpus}.txt",
            "category": "test-data",
            "metadata": {"corpus": corpus, "category": "test-data", "title": "Fixture tecnica"},
            "score": 1.0,
        }]


class DraftFlowProvider(LLMProvider):
    def __init__(self, _connection):
        self.step = 0

    def run(self, messages, tools, model=None):
        self.step += 1
        if self.step == 1:
            return ProviderResult(tool_calls=[ToolCallRequest("examples-1", "search_examples", {"query": "resolucion"})])
        if self.step == 2:
            return ProviderResult(tool_calls=[ToolCallRequest("ask-draft", "ask_user", {
                "questions": [{
                    "id": "object", "type": "text", "question": "Cual es el objeto del borrador?", "required": True
                }]
            })])
        if self.step == 3:
            return ProviderResult(tool_calls=[ToolCallRequest("dept-1", "search_departmental_norms", {"query": "prueba tecnica"})])
        if self.step == 4:
            return ProviderResult(tool_calls=[ToolCallRequest("nat-1", "search_national_norms", {"query": "prueba tecnica"})])
        draft = {
            "document_type": "resolution",
            "title": "RESOLUCION - BORRADOR TECNICO",
            "visto": "Datos tecnicos de prueba.",
            "resultandos": ["Que se recibio una respuesta de prueba."],
            "considerandos": ["Que toda fuente juridica permanece pendiente de validacion."],
            "atento": "A las fuentes reales que se incorporen y verifiquen.",
            "resuelve": [{"number": "1", "text": "Someter el borrador a revision humana."}],
            "notes": ["BORRADOR - TEST DATA"],
        }
        return ProviderResult(text=json.dumps(draft, ensure_ascii=False))


def test_create_resolution_end_to_end(authed_client, csrf_headers, app, monkeypatch):
    session_id = _create_session(authed_client, csrf_headers, app)
    provider = DraftFlowProvider(None)
    app.extensions["llm_provider_factory"] = lambda _connection: provider
    monkeypatch.setattr("rag.retriever.get_default_retriever", lambda: FakeRetriever())

    first = authed_client.post(
        f"/api/agent/sessions/{session_id}/run",
        json={"content": "Necesito preparar una resolucion.", "active_skills": ["redactor-legal"]},
        headers=csrf_headers,
    ).get_data(as_text=True)
    assert "legal.workflow.started" in first
    opened = authed_client.get(f"/api/sessions/{session_id}").get_json()
    assert opened["tool_calls"] == []
    with app.app_context():
        session = db.session.get(AgentSession, session_id)
        case = db.session.get(LegalCaseRecord, session.case_id)
        assert case.state == "awaiting_facts"
    rendered = authed_client.post(
        f"/api/documents/sessions/{session_id}/generate-docx",
        json={"resolution": {"document_type": "resolution"}},
        headers=csrf_headers,
    )
    assert rendered.status_code == 409
    assert rendered.get_json()["error"] == "workflow_gate_failed"

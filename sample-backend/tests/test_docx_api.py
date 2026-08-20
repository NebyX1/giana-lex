from app.extensions import db
from app.models import ProviderConnection
from llm.provider import LLMProvider, ProviderResult


def _session(authed_client, csrf_headers, app):
    with app.app_context():
        provider = ProviderConnection(
            user_id=1, provider="ollama", display_name="Fake", auth_mode="none",
            base_url="http://localhost:11434/v1", default_model="fake",
        )
        db.session.add(provider)
        db.session.commit()
        provider_id = provider.id
    return authed_client.post(
        "/api/sessions", json={"provider_connection_id": provider_id}, headers=csrf_headers
    ).get_json()["id"]


def test_generate_and_download_structured_docx(authed_client, csrf_headers, app):
    session_id = _session(authed_client, csrf_headers, app)
    response = authed_client.post(
        f"/api/documents/sessions/{session_id}/generate-docx",
        json={"resolution": {
            "document_type": "resolution",
            "title": "RESOLUCION - BORRADOR",
            "visto": "Antecedente tecnico de prueba.",
            "resultandos": ["Que se aportaron datos tecnicos."],
            "considerandos": ["Que corresponde revision humana."],
            "atento": "A las fuentes que se verifiquen.",
            "resuelve": [{"number": "1", "text": "Someter el borrador a revision."}],
        }},
        headers=csrf_headers,
    )
    assert response.status_code == 201
    payload = response.get_json()
    assert payload["status"] == "BORRADOR"
    downloaded = authed_client.get(payload["download_url"])
    assert downloaded.status_code == 200
    assert downloaded.data.startswith(b"PK")


def test_generate_and_download_text_draft_docx(authed_client, csrf_headers, app):
    session_id = _session(authed_client, csrf_headers, app)
    response = authed_client.post(
        f"/api/documents/sessions/{session_id}/generate-docx",
        json={"content": "# CONTRATO DE ARRENDAMIENTO DE OBRA\n\n## 1. Objeto\n\n- Ejecutar la obra acordada."},
        headers=csrf_headers,
    )
    assert response.status_code == 201
    payload = response.get_json()
    downloaded = authed_client.get(payload["download_url"])
    assert downloaded.status_code == 200
    assert downloaded.data.startswith(b"PK")


class Reviewer(LLMProvider):
    def __init__(self, _connection):
        pass

    def run(self, messages, tools, model=None):
        assert len(messages) == 2
        assert "Segunda opinion independiente" in messages[0]["content"]
        return ProviderResult(text="Puntos a verificar: competencia y fuente normativa.")


def test_second_opinion_uses_clean_context(authed_client, csrf_headers, app):
    session_id = _session(authed_client, csrf_headers, app)
    app.extensions["llm_provider_factory"] = Reviewer
    response = authed_client.post(
        f"/api/agent/sessions/{session_id}/second-opinion",
        json={"draft": "BORRADOR TECNICO SIN VALOR JURIDICO."},
        headers=csrf_headers,
    )
    assert response.status_code == 200
    assert response.get_json()["independent_context"] is True
    assert "competencia" in response.get_json()["review"]

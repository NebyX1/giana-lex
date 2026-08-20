import io

from app.extensions import db
from app.models import AgentSession, ProviderConnection, UploadedDocument


def _session(authed_client, csrf_headers, app):
    with app.app_context():
        provider = ProviderConnection(
            user_id=1, provider="ollama", display_name="Ollama", auth_mode="none",
            base_url="http://localhost:11434/v1",
        )
        db.session.add(provider)
        db.session.commit()
        provider_id = provider.id
    return authed_client.post(
        "/api/sessions", json={"provider_connection_id": provider_id}, headers=csrf_headers
    ).get_json()["id"]


def test_upload_list_and_download_text_document(authed_client, csrf_headers, app):
    session_id = _session(authed_client, csrf_headers, app)
    response = authed_client.post(
        f"/api/documents/sessions/{session_id}",
        data={"file": (io.BytesIO(b"Documento de prueba tecnica"), "expediente.txt")},
        headers={"X-CSRFToken": csrf_headers["X-CSRFToken"]},
        content_type="multipart/form-data",
    )
    assert response.status_code == 201
    document_id = response.get_json()["id"]
    listed = authed_client.get(f"/api/documents/sessions/{session_id}").get_json()["documents"]
    assert listed[0]["filename"] == "expediente.txt"
    downloaded = authed_client.get(f"/api/documents/{document_id}/download")
    assert downloaded.data == b"Documento de prueba tecnica"


def test_upload_rejects_unowned_session(authed_client, csrf_headers):
    response = authed_client.post(
        "/api/documents/sessions/9999",
        data={"file": (io.BytesIO(b"x"), "x.txt")},
        headers={"X-CSRFToken": csrf_headers["X-CSRFToken"]},
        content_type="multipart/form-data",
    )
    assert response.status_code == 404


def test_upload_rejects_executable_extension(authed_client, csrf_headers, app):
    session_id = _session(authed_client, csrf_headers, app)
    response = authed_client.post(
        f"/api/documents/sessions/{session_id}",
        data={"file": (io.BytesIO(b"MZ"), "payload.exe")},
        headers={"X-CSRFToken": csrf_headers["X-CSRFToken"]},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400


def test_upload_to_linked_session_keeps_case_provenance(authed_client, csrf_headers, app):
    session_id = _session(authed_client, csrf_headers, app)
    created = authed_client.post(
        "/api/legal/cases",
        json={"title": "Caso documental", "task_family": "resolution_drafting", "jurisdiction": "lavalleja"},
        headers={"Idempotency-Key": "upload-linked-case", "X-CSRFToken": csrf_headers["X-CSRFToken"]},
    )
    case_id = created.get_json()["case"]["id"]
    with app.app_context():
        db.session.get(AgentSession, session_id).case_id = case_id
        db.session.commit()

    response = authed_client.post(
        f"/api/documents/sessions/{session_id}",
        data={"file": (io.BytesIO(b"Informe vinculado"), "informe.txt")},
        headers={"X-CSRFToken": csrf_headers["X-CSRFToken"]},
        content_type="multipart/form-data",
    )
    assert response.status_code == 201
    with app.app_context():
        assert db.session.get(UploadedDocument, response.get_json()["id"]).case_id == case_id

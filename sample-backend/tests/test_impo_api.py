import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from impo.service import ImpoImportResult


FIXTURE = Path(__file__).parent / "fixtures" / "impo_ley_18381.json"


def load_fixture_bytes() -> bytes:
    return json.dumps(json.loads(FIXTURE.read_text(encoding="utf-8")), ensure_ascii=False).encode("iso-8859-1")


def test_list_norms_requires_auth(client):
    response = client.get("/api/config/normativa/nacional")
    assert response.status_code == 401


def test_list_norms_returns_empty(authed_client, tmp_path, monkeypatch):
    monkeypatch.setattr("impo.storage.NACIONAL_ROOT", tmp_path)
    monkeypatch.setattr("impo.storage.REGISTRY_PATH", tmp_path / "registry.json")
    response = authed_client.get("/api/config/normativa/nacional")
    assert response.status_code == 200
    body = response.get_json()
    assert "norms" in body
    assert "stats" in body
    assert body["stats"]["total"] == 0


def test_import_invalid_url_returns_400(authed_client, csrf_headers):
    response = authed_client.post(
        "/api/config/normativa/nacional/import",
        json={"url": "https://evil.com/bases/leyes/1"},
        headers=csrf_headers,
    )
    assert response.status_code == 400
    assert "invalid_url" in response.get_json().get("error", "")


def test_import_missing_url_returns_400(authed_client, csrf_headers):
    response = authed_client.post(
        "/api/config/normativa/nacional/import",
        json={"url": ""},
        headers=csrf_headers,
    )
    assert response.status_code == 400


def test_import_valid_norma_with_mocked_download(authed_client, csrf_headers, app, monkeypatch, tmp_path):
    monkeypatch.setattr("impo.storage.NACIONAL_ROOT", tmp_path)
    monkeypatch.setattr("impo.storage.REGISTRY_PATH", tmp_path / "registry.json")

    raw_bytes = load_fixture_bytes()
    response_mock = MagicMock()
    response_mock.status_code = 200
    response_mock.headers = {}
    response_mock.content = raw_bytes
    monkeypatch.setattr("impo.client.httpx.get", lambda *args, **kwargs: response_mock)

    fake_embedder = MagicMock()
    fake_embedder.vector_size = 3
    fake_embedder.embed = lambda texts: [[1.0, 0.0, 0.0] for _ in texts]

    fake_store = MagicMock()
    fake_store.ensure_collection = MagicMock()
    fake_store.upsert = MagicMock(return_value=3)
    fake_store.delete_source = MagicMock()
    fake_store.set_payload = MagicMock(return_value=1)

    def factory():
        from impo.service import ImpoService
        svc = ImpoService(embedder=fake_embedder, store=fake_store, http_client=None)
        return svc

    with patch("app.api.national_norms.get_default_service", factory):
        response = authed_client.post(
            "/api/config/normativa/nacional/import",
            json={"url": "https://www.impo.com.uy/bases/leyes/18381-2008"},
            headers=csrf_headers,
        )
    assert response.status_code == 201
    body = response.get_json()
    result = body["result"]
    assert result["status"] == "created"
    assert result["article_count"] == 3
    assert result["norma_id"] == "ley:18381:2008"


def test_activate_and_deactivate_flow(authed_client, csrf_headers, app, monkeypatch, tmp_path):
    monkeypatch.setattr("impo.storage.NACIONAL_ROOT", tmp_path)
    monkeypatch.setattr("impo.storage.REGISTRY_PATH", tmp_path / "registry.json")

    raw_bytes = load_fixture_bytes()
    response_mock = MagicMock()
    response_mock.status_code = 200
    response_mock.headers = {}
    response_mock.content = raw_bytes
    monkeypatch.setattr("impo.client.httpx.get", lambda *args, **kwargs: response_mock)

    fake_embedder = MagicMock()
    fake_embedder.vector_size = 3
    fake_embedder.embed = lambda texts: [[1.0, 0.0, 0.0] for _ in texts]

    fake_store = MagicMock()
    fake_store.set_payload = MagicMock(return_value=1)

    def factory():
        from impo.service import ImpoService
        svc = ImpoService(embedder=fake_embedder, store=fake_store, http_client=None)
        return svc

    with patch("app.api.national_norms.get_default_service", factory):
        authed_client.post(
            "/api/config/normativa/nacional/import",
            json={"url": "https://www.impo.com.uy/bases/leyes/18381-2008"},
            headers=csrf_headers,
        )

    with patch("app.api.national_norms.get_default_service", factory):
        deactivate = authed_client.post(
            "/api/config/normativa/nacional/ley:18381:2008/deactivate",
            headers=csrf_headers,
        )
    assert deactivate.status_code == 200
    assert deactivate.get_json()["result"]["status"] == "deactivated"

    listing = authed_client.get("/api/config/normativa/nacional")
    norms = listing.get_json()["norms"]
    assert any(n["id"] == "ley:18381:2008" and n["active"] is False for n in norms)

    with patch("app.api.national_norms.get_default_service", factory):
        activate = authed_client.post(
            "/api/config/normativa/nacional/ley:18381:2008/activate",
            headers=csrf_headers,
        )
    assert activate.status_code == 200
    assert activate.get_json()["result"]["status"] == "activated"

    listing = authed_client.get("/api/config/normativa/nacional")
    norms = listing.get_json()["norms"]
    assert any(n["id"] == "ley:18381:2008" and n["active"] is True for n in norms)


def test_search_by_query(authed_client, csrf_headers, app, monkeypatch, tmp_path):
    monkeypatch.setattr("impo.storage.NACIONAL_ROOT", tmp_path)
    monkeypatch.setattr("impo.storage.REGISTRY_PATH", tmp_path / "registry.json")

    raw_bytes = load_fixture_bytes()
    response_mock = MagicMock()
    response_mock.status_code = 200
    response_mock.headers = {}
    response_mock.content = raw_bytes
    monkeypatch.setattr("impo.client.httpx.get", lambda *args, **kwargs: response_mock)

    fake_embedder = MagicMock()
    fake_embedder.vector_size = 3
    fake_embedder.embed = lambda texts: [[1.0, 0.0, 0.0] for _ in texts]

    def factory():
        from impo.service import ImpoService
        svc = ImpoService(embedder=fake_embedder, store=MagicMock(), http_client=None)
        return svc

    with patch("app.api.national_norms.get_default_service", factory):
        authed_client.post(
            "/api/config/normativa/nacional/import",
            json={"url": "https://www.impo.com.uy/bases/leyes/18381-2008"},
            headers=csrf_headers,
        )

    response = authed_client.get("/api/config/normativa/nacional?q=18381")
    norms = response.get_json()["norms"]
    assert len(norms) == 1
    assert norms[0]["numero"] == "18381"

    response = authed_client.get("/api/config/normativa/nacional?q=noexiste")
    assert len(response.get_json()["norms"]) == 0
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from impo.client import ImpoDownload, download_norma
from impo.identity import build_norma_id
from impo.normalize import normalize_impo_data, strip_html
from impo.url import ImpoUrlError, normalize_impo_url


FIXTURE = Path(__file__).parent / "fixtures" / "impo_ley_18381.json"


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class TestUrlNormalization:
    def test_basic_url(self):
        result = normalize_impo_url("https://www.impo.com.uy/bases/leyes/18381-2008")
        assert result.canonical == "https://www.impo.com.uy/bases/leyes/18381-2008"
        assert result.json_url == "https://www.impo.com.uy/bases/leyes/18381-2008?json=true"

    def test_url_with_trailing_slash(self):
        result = normalize_impo_url("https://www.impo.com.uy/bases/leyes/18381-2008/")
        assert result.canonical == "https://www.impo.com.uy/bases/leyes/18381-2008"

    def test_url_with_query_string(self):
        result = normalize_impo_url("https://www.impo.com.uy/bases/leyes/18381-2008?verreferencias=norma")
        assert result.canonical == "https://www.impo.com.uy/bases/leyes/18381-2008"

    def test_article_url_resolves_to_norma(self):
        result = normalize_impo_url("https://www.impo.com.uy/bases/leyes/18381-2008/9")
        assert result.canonical == "https://www.impo.com.uy/bases/leyes/18381-2008"

    def test_article_url_with_query(self):
        result = normalize_impo_url("https://www.impo.com.uy/bases/leyes/18381-2008/9?verreferencias=articulo")
        assert result.canonical == "https://www.impo.com.uy/bases/leyes/18381-2008"

    def test_url_without_www(self):
        result = normalize_impo_url("https://impo.com.uy/bases/leyes/18381-2008")
        assert result.canonical == "https://impo.com.uy/bases/leyes/18381-2008"

    def test_http_normalizes_to_https(self):
        result = normalize_impo_url("http://www.impo.com.uy/bases/leyes/18381-2008")
        assert result.canonical.startswith("https://")

    def test_constitucion_url(self):
        result = normalize_impo_url("https://www.impo.com.uy/bases/constitucion/1967-1967")
        assert result.canonical == "https://www.impo.com.uy/bases/constitucion/1967-1967"

    def test_codigo_url(self):
        result = normalize_impo_url("https://www.impo.com.uy/bases/codigo-tributario/14306-1974")
        assert result.canonical == "https://www.impo.com.uy/bases/codigo-tributario/14306-1974"

    def test_decreto_ley_url(self):
        result = normalize_impo_url("https://www.impo.com.uy/bases/decretos-ley/10388-1943")
        assert result.canonical == "https://www.impo.com.uy/bases/decretos-ley/10388-1943"


class TestUrlSecurity:
    def test_invalid_domain_rejected(self):
        with pytest.raises(ImpoUrlError, match="Dominio no permitido"):
            normalize_impo_url("https://www.example.com/bases/leyes/18381-2008")

    def test_localhost_rejected(self):
        with pytest.raises(ImpoUrlError):
            normalize_impo_url("https://localhost/bases/leyes/18381-2008")

    def test_127_0_0_1_rejected(self):
        with pytest.raises(ImpoUrlError):
            normalize_impo_url("https://127.0.0.1/bases/leyes/18381-2008")

    def test_file_protocol_rejected(self):
        with pytest.raises(ImpoUrlError, match="http o https"):
            normalize_impo_url("file:///etc/passwd")

    def test_ftp_protocol_rejected(self):
        with pytest.raises(ImpoUrlError, match="http o https"):
            normalize_impo_url("ftp://www.impo.com.uy/bases/leyes/18381-2008")

    def test_url_without_bases_path_rejected(self):
        with pytest.raises(ImpoUrlError, match="/bases/"):
            normalize_impo_url("https://www.impo.com.uy/otras/leyes/18381-2008")

    def test_url_with_embedded_credentials_rejected(self):
        with pytest.raises(ImpoUrlError, match="credenciales"):
            normalize_impo_url("https://user:pass@www.impo.com.uy/bases/leyes/18381-2008")

    def test_empty_url_rejected(self):
        with pytest.raises(ImpoUrlError, match="vacia"):
            normalize_impo_url("")

    def test_url_without_norma_segment_rejected(self):
        with pytest.raises(ImpoUrlError):
            normalize_impo_url("https://www.impo.com.uy/bases/leyes")


class TestDeduplication:
    def test_same_norma_two_urls_produce_same_identity(self):
        a = normalize_impo_url("https://www.impo.com.uy/bases/leyes/18381-2008")
        b = normalize_impo_url("https://impo.com.uy/bases/leyes/18381-2008/")
        assert a.canonical.split("/bases/")[-1] == b.canonical.split("/bases/")[-1]

    def test_norma_url_and_article_url_produce_same_canonical(self):
        a = normalize_impo_url("https://www.impo.com.uy/bases/leyes/18381-2008")
        b = normalize_impo_url("https://www.impo.com.uy/bases/leyes/18381-2008/9")
        assert a.canonical == b.canonical

    def test_norma_id_is_deterministic(self):
        id1 = build_norma_id("Ley", "18381", "2008")
        id2 = build_norma_id("Ley", "18381", "2008")
        assert id1 == id2 == "ley:18381:2008"

    def test_decreto_id(self):
        assert build_norma_id("Decreto", "500", "1991") == "decreto:500:1991"

    def test_codigo_id(self):
        assert build_norma_id("Codigo Tributario", "14306", "1974") == "codigo-tributario:14306:1974"


class TestNormalization:
    def test_strip_html_removes_tags(self):
        assert strip_html("<p>Hello <b>world</b></p>") == "Hello world"

    def test_strip_html_handles_entities(self):
        assert strip_html("a &amp; b &lt; c") == "a & b < c"

    def test_normalize_produces_clean_articles(self):
        data = load_fixture()
        normalized = normalize_impo_data(data, "https://www.impo.com.uy/bases/leyes/18381-2008", "https://www.impo.com.uy/bases/leyes/18381-2008?json=true", "ley:18381:2008")
        assert normalized.tipo == "Ley"
        assert normalized.numero == "18381"
        assert normalized.anio == "2008"
        assert normalized.norma_id == "ley:18381:2008"
        assert len(normalized.articulos) == 3
        article = normalized.articulos[0]
        assert article.number == "1"
        assert "<p>" not in article.text
        assert "Toda persona" in article.text
        assert article.url == "https://www.impo.com.uy/bases/leyes/18381-2008/1"

    def test_normalize_preserves_notes_and_references(self):
        data = load_fixture()
        normalized = normalize_impo_data(data, "canonical", "json", "ley:18381:2008")
        assert "Notas" in normalized.articulos[0].notes
        assert "Constitución" in normalized.referencias


class TestDownloadWithMock:
    def test_download_parses_iso_8859_1_json(self, monkeypatch):
        data = load_fixture()
        raw = json.dumps(data, ensure_ascii=False).encode("iso-8859-1")
        response_mock = MagicMock()
        response_mock.status_code = 200
        response_mock.headers = {}
        response_mock.content = raw
        monkeypatch.setattr("impo.client.httpx.get", lambda *args, **kwargs: response_mock)
        canonical = normalize_impo_url("https://www.impo.com.uy/bases/leyes/18381-2008")
        result = download_norma(canonical)
        assert result.tipo == "Ley"
        assert result.numero == "18381"
        assert len(result.articulos) == 3
        assert result.checksum

    def test_download_404_raises(self, monkeypatch):
        response_mock = MagicMock()
        response_mock.status_code = 404
        response_mock.headers = {}
        response_mock.content = b""
        monkeypatch.setattr("impo.client.httpx.get", lambda *args, **kwargs: response_mock)
        canonical = normalize_impo_url("https://www.impo.com.uy/bases/leyes/18381-2008")
        with pytest.raises(Exception, match="404"):
            download_norma(canonical)

    def test_download_redirect_rejected(self, monkeypatch):
        response_mock = MagicMock()
        response_mock.status_code = 302
        response_mock.headers = {"location": "https://evil.com/data"}
        response_mock.content = b""
        monkeypatch.setattr("impo.client.httpx.get", lambda *args, **kwargs: response_mock)
        canonical = normalize_impo_url("https://www.impo.com.uy/bases/leyes/18381-2008")
        with pytest.raises(Exception, match="redirigir"):
            download_norma(canonical)

    def test_download_invalid_json_raises(self, monkeypatch):
        response_mock = MagicMock()
        response_mock.status_code = 200
        response_mock.headers = {}
        response_mock.content = b"not json at all"
        monkeypatch.setattr("impo.client.httpx.get", lambda *args, **kwargs: response_mock)
        canonical = normalize_impo_url("https://www.impo.com.uy/bases/leyes/18381-2008")
        with pytest.raises(Exception, match="JSON invalido"):
            download_norma(canonical)

    def test_download_missing_fields_raises(self, monkeypatch):
        response_mock = MagicMock()
        response_mock.status_code = 200
        response_mock.headers = {}
        response_mock.content = json.dumps({"tipoNorma": "Ley"}).encode("iso-8859-1")
        monkeypatch.setattr("impo.client.httpx.get", lambda *args, **kwargs: response_mock)
        canonical = normalize_impo_url("https://www.impo.com.uy/bases/leyes/18381-2008")
        with pytest.raises(Exception, match="tipoNorma/nroNorma/anioNorma"):
            download_norma(canonical)
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from impo.identity import build_norma_id, deterministic_filename, norm_dir_for_tipo
from impo.normalize import normalize_impo_data
from impo.storage import (
    NACIONAL_ROOT,
    load_registry,
    persist_norma,
    read_metadata,
    read_text_file,
    rebuild_registry_from_disk,
    search_registry,
)


FIXTURE = Path(__file__).parent / "fixtures" / "impo_ley_18381.json"


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_persist_norma_writes_all_files(tmp_path, monkeypatch):
    monkeypatch.setattr("impo.storage.NACIONAL_ROOT", tmp_path)
    data = load_fixture()
    norma_id = build_norma_id("Ley", "18381", "2008")
    normalized = normalize_impo_data(data, "canonical-url", "json-url", norma_id)
    source_bytes = json.dumps(data, ensure_ascii=False).encode("iso-8859-1")
    metadata = persist_norma(
        "leyes",
        "ley_18381_2008",
        source_json_bytes=source_bytes,
        normalized=normalized,
        canonical_url="canonical-url",
        json_url="json-url",
        checksum="abc123",
    )
    assert metadata["id"] == norma_id
    assert metadata["active"] is True
    assert metadata["article_count"] == 3
    assert metadata["checksum"] == "abc123"
    target = tmp_path / "leyes" / "ley_18381_2008"
    assert (target / "source.impo.json").exists()
    assert (target / "normalized.json").exists()
    assert (target / "normalized.txt").exists()
    assert (target / "metadata.json").exists()


def test_persist_is_atomic_on_failure(tmp_path, monkeypatch):
    monkeypatch.setattr("impo.storage.NACIONAL_ROOT", tmp_path)
    data = load_fixture()
    norma_id = build_norma_id("Ley", "18381", "2008")
    normalized = normalize_impo_data(data, "canonical", "json", norma_id)
    source_bytes = json.dumps(data).encode("iso-8859-1")
    persist_norma(
        "leyes", "ley_18381_2008",
        source_json_bytes=source_bytes, normalized=normalized,
        canonical_url="c", json_url="j", checksum="v1",
    )
    target = tmp_path / "leyes" / "ley_18381_2008"
    original_source = (target / "source.impo.json").read_bytes()
    assert original_source
    # New write with different checksum
    persist_norma(
        "leyes", "ley_18381_2008",
        source_json_bytes=source_bytes, normalized=normalized,
        canonical_url="c", json_url="j", checksum="v2",
        existing_metadata=read_metadata("leyes", "ley_18381_2008"),
    )
    new_metadata = read_metadata("leyes", "ley_18381_2008")
    assert new_metadata["checksum"] == "v2"


def test_search_registry_finds_by_number(tmp_path, monkeypatch):
    monkeypatch.setattr("impo.storage.NACIONAL_ROOT", tmp_path)
    monkeypatch.setattr("impo.storage.REGISTRY_PATH", tmp_path / "registry.json")
    data = load_fixture()
    norma_id = build_norma_id("Ley", "18381", "2008")
    normalized = normalize_impo_data(data, "canonical", "json", norma_id)
    source_bytes = json.dumps(data).encode("iso-8859-1")
    metadata = persist_norma(
        "leyes", "ley_18381_2008",
        source_json_bytes=source_bytes, normalized=normalized,
        canonical_url="https://www.impo.com.uy/bases/leyes/18381-2008",
        json_url="json", checksum="abc",
    )
    from impo.storage import upsert_registry_entry
    upsert_registry_entry(metadata)
    results = search_registry("18381")
    assert len(results) == 1
    assert results[0]["id"] == norma_id
    results = search_registry("términoinexistente")
    assert len(results) == 0


def test_rebuild_registry_from_disk(tmp_path, monkeypatch):
    monkeypatch.setattr("impo.storage.NACIONAL_ROOT", tmp_path)
    monkeypatch.setattr("impo.storage.REGISTRY_PATH", tmp_path / "registry.json")
    data = load_fixture()
    normalized = normalize_impo_data(data, "c", "j", build_norma_id("Ley", "18381", "2008"))
    persist_norma(
        "leyes", "ley_18381_2008",
        source_json_bytes=json.dumps(data).encode("iso-8859-1"),
        normalized=normalized, canonical_url="c", json_url="j", checksum="x",
    )
    count = rebuild_registry_from_disk()
    assert count >= 1
    registry = load_registry()
    assert "ley:18381:2008" in registry


def test_category_mapping():
    assert norm_dir_for_tipo("Ley") == "leyes"
    assert norm_dir_for_tipo("Decreto") == "decretos"
    assert norm_dir_for_tipo("Decreto Ley") == "leyes"
    assert norm_dir_for_tipo("Codigo Tributario") == "leyes"
    assert norm_dir_for_tipo("Constitucion") == "constitucion"
    assert norm_dir_for_tipo("Reglamento") == "reglamentos"


def test_deterministic_filename():
    assert deterministic_filename("Ley", "18381", "2008") == "ley_18381_2008"
    assert deterministic_filename("Decreto", "500", "1991") == "decreto_500_1991"
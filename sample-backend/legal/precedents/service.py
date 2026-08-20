import re
import unicodedata
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

import yaml

from app.extensions import db
from legal.domain.models import IntakeIntent
from legal.infrastructure.models import (
    CandidateAuthorityRecord,
    ExampleProfileRecord,
    ExampleVersionRecord,
    PrecedentSearchRunRecord,
    PrecedentSelectionRecord,
)
from legal.workflows.loader import WorkflowPack


EXAMPLES_ROOT = Path(__file__).resolve().parents[2] / "ejemplos" / "resoluciones"
COLLECTION = "idl_resolution_examples_sql_filesystem"
ELIGIBLE_STATUS = "institutionally_validated"
SUBTYPE_ALIASES = {
    "trasposicion_rubros": "fund_transposition",
    "transposicion_rubros": "fund_transposition",
    "fund_transposition": "fund_transposition",
}


class SemanticPrecedentProvider(Protocol):
    provider: str
    model: str

    def score(self, query: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, float]: ...


def fold_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return re.sub(r"[^a-z0-9]+", " ", "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )).strip()


def canonical_subtype(value: str) -> str:
    folded = fold_text(value).replace(" ", "_")
    return SUBTYPE_ALIASES.get(folded, folded)


def canonical_jurisdiction(value: str) -> str:
    folded = fold_text(value)
    return "lavalleja" if "lavalleja" in folded else folded.replace(" ", "_")


def _parse_example(path: Path) -> tuple[dict[str, Any], str, bytes] | None:
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    parts = text.split("---", 2)
    if len(parts) != 3:
        return None
    return yaml.safe_load(parts[1]) or {}, parts[2].strip(), raw


def compile_examples(root: Path = EXAMPLES_ROOT) -> list[ExampleVersionRecord]:
    """Synchronize complete filesystem profiles into the local SQL index."""
    compiled = []
    if not root.is_dir():
        return compiled
    for path in sorted(root.glob("[0-9][0-9]_*.md")):
        parsed = _parse_example(path)
        if parsed is None:
            continue
        metadata, body, raw = parsed
        stable_key = str(metadata.get("document_id") or path.stem)
        profile = ExampleProfileRecord.query.filter_by(stable_key=stable_key).first()
        if profile is None:
            profile = ExampleProfileRecord(id=str(uuid4()), stable_key=stable_key, current_version=1, active=True)
            db.session.add(profile)
            db.session.flush()
        checksum = sha256(raw).hexdigest()
        version = ExampleVersionRecord.query.filter_by(
            example_id=profile.id, version=profile.current_version
        ).first()
        profile_json = _compile_profile(metadata, body, path)
        values = {
            "title": str(metadata.get("title") or path.stem),
            "act_subtype": canonical_subtype(str(metadata.get("typology") or "generic")),
            "jurisdiction": str(metadata.get("jurisdiction") or "lavalleja"),
            "validation_status": str(metadata.get("validation_status") or "unreviewed"),
            "profile_json": profile_json,
            "cited_authority_refs_json": _candidate_references(body),
            "source_checksum": checksum,
            "source_path": str(path),
        }
        if version is None:
            version = ExampleVersionRecord(id=str(uuid4()), example_id=profile.id, version=profile.current_version, **values)
            db.session.add(version)
        elif version.source_checksum != checksum:
            profile.current_version += 1
            version = ExampleVersionRecord(id=str(uuid4()), example_id=profile.id, version=profile.current_version, **values)
            db.session.add(version)
        compiled.append(version)
    db.session.flush()
    return compiled


def _compile_profile(metadata: dict[str, Any], body: str, path: Path) -> dict[str, Any]:
    body_checksum = sha256(body.encode("utf-8")).hexdigest()
    return {
        "document_id": metadata.get("document_id") or path.stem,
        "document_number": metadata.get("document_number"),
        "document_date": str(metadata.get("document_date")) if metadata.get("document_date") else None,
        "document_type": metadata.get("document_type"),
        "typology": canonical_subtype(str(metadata.get("typology") or "generic")),
        "jurisdiction": metadata.get("jurisdiction") or "lavalleja",
        "tags": list(metadata.get("tags") or []),
        "aliases": list(metadata.get("aliases") or []),
        "source_use": metadata.get("source_use"),
        "source_url": metadata.get("source_url"),
        "source_checksum_algorithm": metadata.get("source_checksum_algorithm") or "sha256",
        "structural_validation_status": metadata.get("structural_validation_status"),
        "required_fields": list(metadata.get("required_fields") or []),
        "required_sections": list(metadata.get("required_sections") or []),
        "material_attributes": dict(metadata.get("material_attributes") or {}),
        "body": body,
        "body_checksum": body_checksum,
        "source_checksum": body_checksum,
    }


def validate_profiles(root: Path = EXAMPLES_ROOT) -> list[dict[str, Any]]:
    reports = []
    required = {"document_id", "title", "typology", "jurisdiction", "document_type", "validation_status"}
    if not root.is_dir():
        return [{"path": str(root), "valid": False, "errors": ["corpus_unavailable"]}]
    for path in sorted(root.glob("[0-9][0-9]_*.md")):
        parsed = _parse_example(path)
        if parsed is None:
            reports.append({"path": str(path), "valid": False, "errors": ["invalid_frontmatter"]})
            continue
        metadata, body, _raw = parsed
        errors = [f"missing:{key}" for key in sorted(required) if not metadata.get(key)]
        if not body.strip():
            errors.append("missing:body")
        if metadata.get("validation_status") == ELIGIBLE_STATUS:
            for key in ("source_url", "structural_validation_status", "required_fields", "required_sections"):
                if not metadata.get(key):
                    errors.append(f"missing:{key}")
        reports.append({"path": str(path), "valid": not errors, "errors": errors})
    return reports


def compile_search_profile(intent: IntakeIntent, pack: WorkflowPack) -> dict[str, Any]:
    return {
        "act_type": intent.act_type,
        "subtype": canonical_subtype(intent.subtype),
        "jurisdiction": intent.jurisdiction,
        "known_facts": intent.known_facts,
        "terms": sorted(set(
            [canonical_subtype(intent.subtype).replace("_", " ")]
            + [str(item) for item in pack.precedent_types]
        )),
    }


def search_precedents(
    case_id: str,
    pack: WorkflowPack,
    intent: IntakeIntent,
    *,
    workflow_run_id: str | None = None,
    step_run_id: str | None = None,
    root: Path = EXAMPLES_ROOT,
    semantic_provider: SemanticPrecedentProvider | None = None,
) -> PrecedentSearchRunRecord:
    query = compile_search_profile(intent, pack)
    generic_fallback_count = 1 if intent.subtype == "generic" else 0
    search = PrecedentSearchRunRecord(
        id=str(uuid4()), case_id=case_id, run_id=workflow_run_id, step_run_id=step_run_id,
        status="pending", query_json=query, collections_json=[COLLECTION],
        index_status_json={
            "filesystem": "available" if root.is_dir() else "unavailable", "sql": "pending",
            "inspected_count": 0, "eligible_count": 0, "candidate_count": 0,
            "generic_fallback_count": generic_fallback_count,
        },
        searched_count=0, candidates_json=[], match_label="none", calibrated_confidence=None,
        similarities_json=[], differences_json=[], errors_json=[],
    )
    db.session.add(search)
    db.session.flush()
    if not root.is_dir():
        search.status = "unavailable"
        search.index_status_json = {
            "filesystem": "unavailable", "sql": "not_built", "inspected_count": 0,
            "eligible_count": 0, "candidate_count": 0,
            "generic_fallback_count": generic_fallback_count,
        }
        search.errors_json = ["precedent_corpus_unavailable"]
        search.fallback_reason = "El corpus local de antecedentes no está disponible."
        search.completed_at = datetime.utcnow()
        db.session.flush()
        return search

    compiled = compile_examples(root)
    eligible = []
    for item in compiled:
        parent = db.session.get(ExampleProfileRecord, item.example_id)
        if item.validation_status == ELIGIBLE_STATUS and parent is not None and parent.active:
            eligible.append((item, parent))
    search.searched_count = len(compiled)
    search.index_status_json = {
        "filesystem": "available", "sql": "rebuilt",
        "semantic": "not_configured" if semantic_provider is None else "pending",
        "inspected_count": len(compiled), "eligible_count": len(eligible),
        "candidate_count": len(eligible), "generic_fallback_count": generic_fallback_count,
    }
    query_tokens = set(fold_text(" ".join(query["terms"])).split())
    candidates = []
    for item, parent in eligible:
        profile = item.profile_json or {}
        subtype = canonical_subtype(item.act_subtype)
        exact = subtype == query["subtype"] and canonical_jurisdiction(item.jurisdiction) == canonical_jurisdiction(query["jurisdiction"])
        text = " ".join([
            item.title, subtype, " ".join(profile.get("tags") or []),
            " ".join(profile.get("aliases") or []),
        ])
        candidate_tokens = set(fold_text(text).split())
        lexical = len(query_tokens & candidate_tokens) / len(query_tokens | candidate_tokens) if query_tokens | candidate_tokens else 0.0
        structured = 1.0 if exact else (0.5 if subtype == query["subtype"] else 0.0)
        similarities, differences = _compare_material(query, item)
        candidates.append({
            "example_version_id": item.id,
            "stable_key": parent.stable_key,
            "title": item.title,
            "subtype": subtype,
            "validation_status": item.validation_status,
            "eligibility": "institutionally_validated",
            "source_url": profile.get("source_url"),
            "components": {"structured": structured, "lexical": round(lexical, 6)},
            "similarities": similarities,
            "differences": differences,
            "fusion_score": structured * 0.75 + lexical * 0.25,
        })

    if semantic_provider is not None and candidates:
        try:
            semantic = semantic_provider.score(query, candidates)
            for candidate in candidates:
                value = semantic.get(candidate["example_version_id"])
                if value is not None and 0 <= value <= 1:
                    candidate["components"]["semantic"] = value
                    candidate["fusion_score"] = candidate["fusion_score"] * 0.8 + value * 0.2
            search.index_status_json = {**search.index_status_json, "semantic": "available"}
        except Exception as exc:
            search.errors_json = [f"semantic_provider_failed:{type(exc).__name__}"]
            search.index_status_json = {**search.index_status_json, "semantic": "failed"}

    candidates.sort(key=lambda item: (-item["fusion_score"], item["stable_key"]))
    selected = candidates[0] if candidates else None
    if selected and selected["components"]["structured"] == 1.0:
        label = "exact"
    elif selected and selected["fusion_score"] >= 0.7:
        label = "strong"
    elif selected and selected["fusion_score"] >= 0.2:
        label = "partial"
    else:
        label = "none"
        selected = None
    search.candidates_json = [{key: value for key, value in item.items() if key != "fusion_score"} for item in candidates]
    search.selected_example_version_id = selected["example_version_id"] if selected else None
    search.match_label = label
    search.similarities_json = selected["similarities"] if selected else []
    search.differences_json = selected["differences"] if selected else []
    search.fallback_reason = None if selected else (
        "No hay antecedentes institucionalmente validados en el índice local."
        if not eligible else "Ningún antecedente validado alcanzó comparabilidad material suficiente."
    )
    search.status = "completed"
    search.completed_at = datetime.utcnow()
    db.session.flush()
    return search


def _compare_material(query: dict[str, Any], item: ExampleVersionRecord) -> tuple[list[str], list[str]]:
    profile = item.profile_json or {}
    similarities = []
    differences = []
    if canonical_subtype(item.act_subtype) == query["subtype"]:
        similarities.append(f"Misma tipología canónica: {query['subtype']}.")
    if canonical_jurisdiction(item.jurisdiction) == canonical_jurisdiction(query["jurisdiction"]):
        similarities.append(f"Misma jurisdicción: {query['jurisdiction']}.")
    material = profile.get("material_attributes") or {}
    for key, query_value in (query.get("known_facts") or {}).items():
        if key not in material:
            continue
        if fold_text(str(query_value)) == fold_text(str(material[key])):
            similarities.append(f"Coincide el atributo {key}.")
        else:
            differences.append(f"El atributo {key} difiere entre la solicitud y el antecedente.")
    return similarities, differences


def select_precedent(
    case_id: str,
    pack: WorkflowPack,
    intent: IntakeIntent | None = None,
    **search_kwargs,
) -> PrecedentSelectionRecord:
    if intent is None:
        intent = IntakeIntent(
            task_family="resolution_drafting", act_type="resolution", subtype=pack.intent.subtype,
            selected_workflow_id=pack.id, selected_workflow_version=pack.version,
            classification_basis=["workflow_pack"], classifier="deterministic",
            classifier_version="workflow-pack", risk_tier="high",
        )
    search = search_precedents(case_id, pack, intent, **search_kwargs)
    selected = db.session.get(ExampleVersionRecord, search.selected_example_version_id) if search.selected_example_version_id else None
    candidate = next((item for item in search.candidates_json if item["example_version_id"] == search.selected_example_version_id), None)
    components = (candidate or {}).get("components") or {}
    legacy_score = components.get("structured", 0) * 0.75 + components.get("lexical", 0) * 0.25
    selection = PrecedentSelectionRecord(
        id=str(uuid4()), case_id=case_id,
        primary_example_version_id=selected.id if selected else None,
        match_type=search.match_label,
        confidence=str(round(legacy_score, 4)),
        alternatives_json=[item["example_version_id"] for item in search.candidates_json if item["example_version_id"] != search.selected_example_version_id][:3],
        differences_json=search.differences_json,
        fallback_reason=search.fallback_reason,
    )
    db.session.add(selection)
    if selected:
        for raw_ref in selected.cited_authority_refs_json:
            db.session.add(CandidateAuthorityRecord(
                id=str(uuid4()), case_id=case_id, raw_reference=raw_ref,
                discovered_in_example_id=selected.id, discovery_reason="cited",
                verification_status="unverified",
            ))
    db.session.flush()
    return selection


def _candidate_references(body: str) -> list[str]:
    refs = []
    for line in body.splitlines():
        if any(word in fold_text(line) for word in ("ley ", "decreto", "t o c a f", "tocaf", "norma")):
            cleaned = re.sub(r"[*_`]", "", line).strip()
            if cleaned and "[NORM" not in cleaned.upper() and cleaned not in refs:
                refs.append(cleaned[:500])
    return refs

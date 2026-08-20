from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from ..audit import record_event
from ..authorization import require_roles
from ..extensions import db
from depto.service import DeptoService, get_default_depto_service
from depto.url import DeptoUrlError


departmental_bp = Blueprint("departmental_norms", __name__, url_prefix="/api/config/normativa/departamental")


def _service() -> DeptoService:
    return get_default_depto_service()


def _payload() -> dict:
    return request.get_json(silent=True) or {}


@departmental_bp.get("")
@login_required
def list_norms():
    query = request.args.get("q", "").strip()
    family = request.args.get("family", "").strip() or None
    service = _service()
    norms = service.list_norms(query or None, family=family)
    stats = service.get_stats()
    return jsonify(norms=norms, stats=stats)


@departmental_bp.post("/import")
@login_required
@require_roles("corpus_curator")
def import_norm():
    data = _payload()
    url = str(data.get("url", "")).strip()
    if not url:
        return jsonify(error="invalid_request", message="URL es requerida."), 400
    service = _service()
    try:
        result = service.importer.import_source(
            url=url,
            norm_type=data.get("norm_type") or None,
            number=data.get("number") or None,
            year=str(data.get("year")) if data.get("year") else None,
            family=data.get("family") or None,
            title=data.get("title") or None,
            source_quality=data.get("source_quality") or "unknown",
            active=bool(data.get("active", True)),
            index=True,
        )
    except DeptoUrlError as exc:
        record_event("depto.import", "validation_failed", current_user.id)
        db.session.commit()
        return jsonify(error="invalid_url", message=str(exc)), 400
    except Exception as exc:
        record_event("depto.import", "failed", current_user.id)
        db.session.commit()
        return jsonify(error="import_failed", message=str(exc)), 502
    record_event("depto.import", result.status, current_user.id)
    db.session.commit()
    status_code = 201 if result.status in ("created", "indirect") else 200
    return jsonify(result=result.to_dict()), status_code


@departmental_bp.post("/repair-cache")
@login_required
@require_roles("corpus_curator")
def repair_cache():
    """Reprocess sources already stored on disk with the current extractor."""
    service = _service()
    result = service.repair_cached_sources(index=True)
    status = "completed" if not result["failed"] else "completed_with_errors"
    record_event("depto.repair_cache", status, current_user.id)
    db.session.commit()
    return jsonify(result=result)


@departmental_bp.post("/<norm_id>/activate")
@login_required
@require_roles("corpus_curator")
def activate(norm_id: str):
    service = _service()
    result = _toggle(norm_id, active=True)
    record_event("depto.activate", result.status, current_user.id)
    db.session.commit()
    return jsonify(result=result)


@departmental_bp.post("/<norm_id>/deactivate")
@login_required
@require_roles("corpus_curator")
def deactivate(norm_id: str):
    service = _service()
    result = _toggle(norm_id, active=False)
    record_event("depto.deactivate", result.status, current_user.id)
    db.session.commit()
    return jsonify(result=result)


def _toggle(norm_id: str, active: bool) -> dict:
    from depto import storage as st
    from qdrant_client import models
    from rag.constants import DEPARTMENTAL_COLLECTION
    entry = st.load_registry().get(norm_id)
    if not entry:
        return {"status": "not_found", "message": "Norma no encontrada.", "norm_id": norm_id}
    # If the norm has text, toggle its active payload in Qdrant.
    if entry.get("indexed"):
        try:
            store = _service().importer.store
            store.set_payload(
                DEPARTMENTAL_COLLECTION,
                filter_key="norm_id",
                filter_value=norm_id,
                payload={"active": active},
            )
        except Exception as exc:
            return {"status": "error", "message": f"No se pudo actualizar Qdrant: {exc}", "norm_id": norm_id}
    st.update_registry_entry(norm_id, {"active_for_rag": active})
    return {
        "status": "activated" if active else "deactivated",
        "message": f"Norma {'activada' if active else 'desactivada'}. {'Disponible para Giana.' if active else 'Excluida del RAG.'}",
        "norm_id": norm_id,
    }


@departmental_bp.get("/<norm_id>/relationships")
@login_required
def relationships(norm_id: str):
    from depto import storage as st
    rels = st.relationships_for(norm_id)
    return jsonify(relationships=rels)

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required

from ..audit import record_event
from ..authorization import require_roles
from ..extensions import db
from impo.service import ImpoService, get_default_service
from impo.storage import load_registry
from impo.url import ImpoUrlError


national_bp = Blueprint("national_norms", __name__, url_prefix="/api/config/normativa/nacional")


def _service() -> ImpoService:
    return get_default_service()


def _payload() -> dict:
    return request.get_json(silent=True) or {}


@national_bp.get("")
@login_required
def list_norms():
    query = request.args.get("q", "").strip()
    service = _service()
    norms = service.list_norms(query or None)
    stats = service.get_stats()
    return jsonify(norms=norms, stats=stats)


@national_bp.post("/import")
@login_required
@require_roles("corpus_curator")
def import_norm():
    data = _payload()
    url = str(data.get("url", "")).strip()
    if not url:
        return jsonify(error="invalid_request", message="URL es requerida."), 400
    service = _service()
    try:
        result = service.import_url(url, index=True)
    except ImpoUrlError as exc:
        record_event("impo.import", "validation_failed", current_user.id)
        db.session.commit()
        return jsonify(error="invalid_url", message=str(exc)), 400
    except Exception as exc:
        current_app.logger.exception("IMPO import failed")
        record_event("impo.import", "failed", current_user.id)
        db.session.commit()
        return jsonify(error="import_failed", message=str(exc)), 502
    record_event("impo.import", result.status, current_user.id)
    db.session.commit()
    status_code = 201 if result.status == "created" else 200
    return jsonify(result=result.to_dict()), status_code


@national_bp.post("/repair-index")
@login_required
@require_roles("corpus_curator")
def repair_index():
    service = _service()
    try:
        result = service.repair_index(missing_only=True)
    except Exception as exc:
        current_app.logger.exception("IMPO index repair failed")
        record_event("impo.repair_index", "failed", current_user.id)
        db.session.commit()
        return jsonify(error="repair_failed", message=str(exc)), 502
    outcome = "completed" if not result["failed"] else "partial"
    record_event("impo.repair_index", outcome, current_user.id, details=result)
    db.session.commit()
    return jsonify(result=result)


@national_bp.post("/<norma_id>/activate")
@login_required
@require_roles("corpus_curator")
def activate(norma_id: str):
    service = _service()
    result = service.activate_norma(norma_id)
    record_event("impo.activate", result.status, current_user.id)
    db.session.commit()
    return jsonify(result=result.to_dict())


@national_bp.post("/<norma_id>/deactivate")
@login_required
@require_roles("corpus_curator")
def deactivate(norma_id: str):
    service = _service()
    result = service.deactivate_norma(norma_id)
    record_event("impo.deactivate", result.status, current_user.id)
    db.session.commit()
    return jsonify(result=result.to_dict())


@national_bp.post("/<norma_id>/refresh")
@login_required
@require_roles("corpus_curator")
def refresh(norma_id: str):
    service = _service()
    try:
        result = service.refresh_norma(norma_id)
    except Exception as exc:
        current_app.logger.exception("IMPO refresh failed")
        record_event("impo.refresh", "failed", current_user.id)
        db.session.commit()
        return jsonify(error="refresh_failed", message=str(exc)), 502
    record_event("impo.refresh", result.status, current_user.id)
    db.session.commit()
    return jsonify(result=result.to_dict())

from __future__ import annotations

from functools import wraps
import json

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user
from pydantic import ValidationError

from .schemas import ImportResolutionInput, ManualResolutionInput, ResolutionPatch, TaxonomyNodeInput, TaxonomyNodePatch
from .service import KnowledgeConflictError, KnowledgeNotFoundError
from identity.authorization import has_any_role


blueprint = Blueprint("legal_knowledge", __name__, url_prefix="/api/settings/legal")


def service():
    return current_app.config["LEGAL_KNOWLEDGE"]


def actor():
    if current_user.is_authenticated:
        return f"user:{current_user.id}:{current_user.email}"[:120]
    return "test-bypass"


@blueprint.before_request
def require_authenticated_user():
    if current_app.config.get("TESTING_AUTH_BYPASS"):
        return None
    if not current_user.is_authenticated:
        return jsonify(error="authentication_required", message="Autenticacion requerida."), 401


def admin_required(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        allowed = current_app.config.get("TESTING_AUTH_BYPASS") or has_any_role("corpus_curator", "technical_admin")
        if not allowed:
            return jsonify({"ok": False, "error": "forbidden", "message": "Se requieren permisos administrativos"}), 403
        return function(*args, **kwargs)
    return wrapped


@blueprint.errorhandler(ValidationError)
def validation_error(error):
    return jsonify({"ok": False, "error": "validation_error", "message": "Datos inválidos", "details": error.errors()}), 400


@blueprint.errorhandler(KnowledgeNotFoundError)
def not_found(error):
    return jsonify({"ok": False, "error": "not_found", "message": str(error)}), 404


@blueprint.errorhandler(KnowledgeConflictError)
def conflict(error):
    return jsonify({"ok": False, "error": "conflict", "message": str(error)}), 409


@blueprint.get("/overview")
def overview():
    return jsonify({"ok": True, "overview": service().overview()})


@blueprint.get("/taxonomy")
def taxonomy_list():
    return jsonify({"ok": True, "nodes": service().taxonomy_tree(
        query=request.args.get("q", ""), status=request.args.get("status", ""), level=request.args.get("level", "")
    )})


@blueprint.post("/taxonomy")
@admin_required
def taxonomy_create():
    data = TaxonomyNodeInput.model_validate(request.get_json(silent=True) or {})
    return jsonify({"ok": True, "node": service().create_taxonomy(data, actor())}), 201


@blueprint.get("/taxonomy/<node_id>")
def taxonomy_detail(node_id):
    return jsonify({"ok": True, "node": service().get_taxonomy(node_id)})


@blueprint.patch("/taxonomy/<node_id>")
@admin_required
def taxonomy_update(node_id):
    patch = TaxonomyNodePatch.model_validate(request.get_json(silent=True) or {})
    return jsonify({"ok": True, "node": service().update_taxonomy(node_id, patch, actor())})


@blueprint.post("/taxonomy/<node_id>/duplicate")
@admin_required
def taxonomy_duplicate(node_id):
    data = request.get_json(silent=True) or {}
    return jsonify({"ok": True, "node": service().duplicate_taxonomy(node_id, data.get("code", ""), data.get("slug", ""), actor())}), 201


@blueprint.post("/taxonomy/<node_id>/reindex")
@admin_required
def taxonomy_reindex(node_id):
    return jsonify({"ok": True, **service().enqueue_reindex("taxonomy", node_id, actor())}), 202


@blueprint.get("/resolutions")
def resolutions_list():
    result = service().list_resolutions(
        page=request.args.get("page", 1, type=int), page_size=request.args.get("page_size", 25, type=int),
        query=request.args.get("q", ""), year=request.args.get("year", type=int),
        status=request.args.get("status", ""), role=request.args.get("role", ""),
        taxonomy_node_id=request.args.get("taxonomy_node_id", ""), index_status=request.args.get("index_status", ""),
        order=request.args.get("order", "recent"),
    )
    return jsonify({"ok": True, **result})


@blueprint.post("/resolutions")
@admin_required
def resolution_create():
    data = ManualResolutionInput.model_validate(request.get_json(silent=True) or {})
    return jsonify({"ok": True, "resolution": service().create_manual_resolution(data, actor())}), 201


@blueprint.get("/resolutions/<resolution_id>")
def resolution_detail(resolution_id):
    return jsonify({"ok": True, "resolution": service().get_resolution(resolution_id)})


@blueprint.patch("/resolutions/<resolution_id>")
@admin_required
def resolution_update(resolution_id):
    patch = ResolutionPatch.model_validate(request.get_json(silent=True) or {})
    return jsonify({"ok": True, "resolution": service().update_resolution(resolution_id, patch, actor())})


@blueprint.post("/resolutions/import-url")
@admin_required
def resolution_import_url():
    data = ImportResolutionInput.model_validate(request.get_json(silent=True) or {})
    if not data.confirm:
        return jsonify({"ok": True, "preview": service().preview_url(str(data.url), data.expected_title)})
    result = service().import_url(str(data.url), data.assignments, data.expected_title, actor())
    return jsonify({"ok": True, **result}), 201 if result.get("created") else 200


@blueprint.post("/resolutions/import-file")
@admin_required
def resolution_import_file():
    uploaded = request.files.get("file")
    if not uploaded or not uploaded.filename:
        return jsonify({"ok": False, "error": "validation_error", "message": "El archivo es obligatorio"}), 400
    try:
        metadata = json.loads(request.form.get("metadata", "{}"))
    except json.JSONDecodeError:
        return jsonify({"ok": False, "error": "validation_error", "message": "Metadatos inválidos"}), 400
    content = uploaded.stream.read(10 * 1024 * 1024 + 1)
    result = service().import_file(uploaded.filename, uploaded.content_type, content, metadata, actor())
    return jsonify({"ok": True, "resolution": result}), 201


@blueprint.post("/resolutions/<resolution_id>/reindex")
@admin_required
def resolution_reindex(resolution_id):
    return jsonify({"ok": True, **service().enqueue_reindex("resolution", resolution_id, actor())}), 202


@blueprint.get("/index/status")
def index_status():
    return jsonify({"ok": True, **service().index_status()})


@blueprint.post("/index/retry-failed")
@admin_required
def retry_failed():
    return jsonify({"ok": True, **service().process_outbox(limit=100, only_failed=True)})


@blueprint.post("/index/check")
@admin_required
def check_index():
    return jsonify({"ok": True, **service().check_consistency()})


@blueprint.get("/retrieval/taxonomy")
def retrieval_taxonomy():
    matches = service().search_resolution_types(request.args.get("q", ""), request.args.get("limit", 5, type=int))
    return jsonify({"ok": True, "matches": [item.model_dump() for item in matches]})

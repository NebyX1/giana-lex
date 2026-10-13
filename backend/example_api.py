"""Administrative API for editorial resolution examples."""
from __future__ import annotations

import json

import click
from flask import Blueprint, current_app, jsonify, request
from flask.cli import with_appcontext
from flask_login import current_user

from example_catalog import MAX_IMPORT_BYTES
from identity.authorization import has_any_role


blueprint = Blueprint("example_catalog", __name__, url_prefix="/api/settings/examples")


def service():
    return current_app.config["EXAMPLE_CATALOG"]


def actor():
    return f"user:{current_user.id}:{current_user.email}" if current_user.is_authenticated else "test-bypass"


def can_edit():
    return current_app.config.get("TESTING_AUTH_BYPASS") or has_any_role("corpus_curator", "technical_admin")


@blueprint.before_request
def protect():
    if not current_app.config.get("TESTING_AUTH_BYPASS") and not current_user.is_authenticated:
        return jsonify(error="authentication_required", message="Autenticación requerida"), 401
    if request.method != "GET" and not can_edit():
        return jsonify(error="forbidden", message="Se requiere permiso de edición del corpus"), 403


@blueprint.errorhandler(ValueError)
def invalid(exc):
    return jsonify(error="validation_error", message=str(exc)), 400


@blueprint.errorhandler(RuntimeError)
def conflict(exc):
    return jsonify(error="conflict", message=str(exc)), 409


@blueprint.errorhandler(KeyError)
def missing(_exc):
    return jsonify(error="not_found", message="Ejemplo no encontrado"), 404


@blueprint.get("")
def list_examples():
    return jsonify(service().list(request.args))


@blueprint.get("/<identifier>")
def detail(identifier):
    result = service().get(identifier)
    return jsonify(result) if result else (jsonify(error="not_found", message="Ejemplo no encontrado"), 404)


@blueprint.post("")
def create():
    return jsonify(service().create(request.get_json(silent=True) or {}, actor())), 201


@blueprint.patch("/<identifier>")
def update(identifier):
    return jsonify(service().update(identifier, request.get_json(silent=True) or {}, actor()))


@blueprint.post("/<identifier>/restore/<revision_id>")
def restore(identifier, revision_id):
    data = request.get_json(silent=True) or {}
    return jsonify(service().restore(identifier, revision_id, data.get("expected_version"), actor(), data.get("reason") or ""))


@blueprint.post("/import")
def import_examples():
    upload = request.files.get("file")
    if not upload:
        raise ValueError("Falta el archivo")
    data = upload.stream.read(MAX_IMPORT_BYTES + 1)
    return jsonify(service().import_bytes(data, upload.filename or "", actor(),
                                           preview=request.form.get("preview") == "true"))


@blueprint.get("/search-preview")
def search_preview():
    return jsonify(service().search(request.args.get("q", ""), min(20, request.args.get("limit", 20, type=int))))


@click.command("import-examples")
@click.argument("path", type=click.Path(exists=True, dir_okay=False, path_type=str))
@click.option("--preview", is_flag=True)
@with_appcontext
def import_examples_cli(path, preview):
    from pathlib import Path
    result = service().import_bytes(Path(path).read_bytes(), Path(path).name, "cli", preview=preview)
    click.echo(json.dumps(result, ensure_ascii=False, indent=2))


@click.command("index-examples")
@with_appcontext
def index_examples_cli():
    click.echo(f"Indexed {service().rebuild_vector()} editorial examples")

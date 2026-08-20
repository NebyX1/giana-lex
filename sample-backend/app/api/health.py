from flask import Blueprint, current_app, jsonify
from sqlalchemy import text
from redis import Redis

from ..extensions import db


health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def liveness():
    return jsonify(status="ok", service="giana-lex-backend")


@health_bp.get("/ready")
def readiness():
    checks = {"database": "ok"}
    try:
        db.session.execute(text("SELECT 1"))
    except Exception:
        return jsonify(status="unavailable", checks={"database": "failed"}), 503
    try:
        from legal.workflows.loader import WorkflowPackRegistry
        from legal.prompts.compiler import validate_prompt_registry

        if not WorkflowPackRegistry().list_active():
            raise RuntimeError("No active workflow packs")
        validate_prompt_registry()
        checks["workflow_packs"] = "ok"
        checks["prompt_registry"] = "ok"
        from legal.agents.intent_compiler import ALIASES_PATH
        from legal.precedents.service import EXAMPLES_ROOT

        checks["intake_planner"] = "deterministic" if ALIASES_PATH.is_file() else "unavailable"
        checks["precedent_search"] = "sql_filesystem" if EXAMPLES_ROOT.is_dir() else "unavailable"
        checks["precedent_semantic"] = (
            "available" if current_app.extensions.get("precedent_semantic_provider") else "not_configured"
        )
        if checks["intake_planner"] == "unavailable":
            raise RuntimeError("Intake alias configuration unavailable")
    except Exception:
        checks["legal_registry"] = "failed"
        return jsonify(status="unavailable", checks=checks), 503

    if current_app.config.get("TESTING"):
        checks["qdrant"] = "skipped_testing"
    elif not current_app.config.get("QDRANT_URL"):
        checks["qdrant"] = "not_configured"
        return jsonify(status="unavailable", checks=checks), 503
    else:
        try:
            from rag.store import QdrantStore
            QdrantStore(
                url=current_app.config["QDRANT_URL"],
                api_key=current_app.config.get("QDRANT_API_KEY"),
            ).client.get_collections()
            checks["qdrant"] = "ok"
        except Exception:
            checks["qdrant"] = "failed"
            return jsonify(status="unavailable", checks=checks), 503

    if current_app.config["LEGAL_DISPATCHER"] == "redis":
        try:
            client = Redis.from_url(current_app.config["REDIS_URL"])
            client.ping()
            checks["redis"] = "ok"
            if not client.exists(current_app.config["LEGAL_WORKER_HEARTBEAT_KEY"]):
                checks["legal_worker"] = "missing_heartbeat"
                return jsonify(status="unavailable", checks=checks), 503
            checks["legal_worker"] = "ok"
            checks["legal_workflow"] = "ok"
        except Exception:
            checks["legal_workflow"] = "failed"
            return jsonify(status="unavailable", checks=checks), 503
    else:
        checks["legal_workflow"] = "inline"
    return jsonify(status="ok", checks=checks)

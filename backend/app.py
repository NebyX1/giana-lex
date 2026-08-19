import logging
from pathlib import Path

from flask import Flask, jsonify, request, send_file
from pydantic import ValidationError

from agents import PydanticAgents
from config import Settings, settings as default_settings
from llm import LLMNotConfigured
from orchestrator import NotFoundError, OperationError, Orchestrator
from state import InvalidTransition, Stage
from storage import Storage
from tools.export_docx import export_markdown_docx


def create_app(settings: Settings = default_settings, agents=None, database_path: Path | None = None) -> Flask:
    app = Flask(__name__)
    storage = Storage(database_path or settings.database_path)
    if agents is None:
        agents = PydanticAgents(settings) if settings.llm_configured else None
    orchestrator = Orchestrator(settings, storage, agents)
    app.config["ORCHESTRATOR"] = orchestrator

    def response_for(state, message: str | None = None):
        return {
            "ok": True,
            "conversation_id": state.id,
            "stage": state.stage.value,
            "message": message or state.last_debug.get("message", ""),
            "examples": [match.model_dump() for match in state.selected_examples],
            "form": state.current_form.model_dump() if state.current_form else None,
            "draft": state.draft,
            "approved": state.approved,
            "skills": orchestrator.skill_metadata() if state.approved else [],
            "skill_results": state.skill_results,
            "revision_count": state.revision_count,
            "debug": state.last_debug,
        }

    @app.errorhandler(OperationError)
    def operation_error(error):
        return jsonify({"ok": False, "error": error.code, "message": str(error), "retryable": error.retryable}), 400

    @app.errorhandler(InvalidTransition)
    def transition_error(error):
        return jsonify({"ok": False, "error": "invalid_stage", "message": str(error), "retryable": False}), 409

    @app.errorhandler(NotFoundError)
    def not_found(error):
        return jsonify({"ok": False, "error": "not_found", "message": str(error), "retryable": False}), 404

    @app.errorhandler(Exception)
    def unexpected(error):
        logging.exception("Error no controlado")
        return jsonify({"ok": False, "error": "internal_error", "message": "Ocurrio un error interno", "retryable": False}), 500

    @app.get("/api/health")
    def health():
        return jsonify(
            {
                "status": "ok",
                "llm_configured": settings.llm_configured,
                "model": settings.llm_model or None,
                "examples_count": len(list(settings.examples_dir.glob("*.md"))),
                "mold_available": (settings.molds_dir / "resolucion_basica.md").is_file(),
                "skills": list(orchestrator.skills),
            }
        )

    @app.post("/api/conversations")
    def create_conversation():
        if orchestrator.agents is None:
            raise OperationError("llm_not_configured", "El proveedor LLM no esta configurado", False)
        data = request.get_json(silent=True) or {}
        return jsonify(response_for(orchestrator.create_conversation(data.get("message"))))

    @app.get("/api/conversations/<conversation_id>")
    def get_conversation(conversation_id):
        return jsonify(response_for(orchestrator.get(conversation_id)))

    @app.post("/api/conversations/<conversation_id>/form")
    def submit_form(conversation_id):
        data = request.get_json(silent=True) or {}
        return jsonify(response_for(orchestrator.submit_form(conversation_id, data.get("answers") or {})))

    @app.post("/api/conversations/<conversation_id>/revise")
    def revise(conversation_id):
        data = request.get_json(silent=True) or {}
        return jsonify(response_for(orchestrator.revise(conversation_id, data.get("instructions"))))

    @app.post("/api/conversations/<conversation_id>/approve")
    def approve(conversation_id):
        return jsonify(response_for(orchestrator.approve(conversation_id)))

    @app.get("/api/skills")
    def skills():
        return jsonify({"ok": True, "skills": orchestrator.skill_metadata()})

    @app.post("/api/conversations/<conversation_id>/skills/<key>")
    def run_skill(conversation_id, key):
        data = request.get_json(silent=True) or {}
        return jsonify(response_for(orchestrator.run_skill(conversation_id, key, data.get("answers"))))

    @app.get("/api/conversations/<conversation_id>/export")
    def export(conversation_id):
        state = orchestrator.get(conversation_id)
        if state.stage != Stage.APPROVED or not state.draft:
            raise InvalidTransition("Solo se puede exportar un borrador aprobado")
        return send_file(
            export_markdown_docx(state.draft),
            as_attachment=True,
            download_name=f"giana-lex-{state.id}.docx",
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)

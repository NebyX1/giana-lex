import hashlib
import mimetypes
import secrets
import uuid
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_file
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from ..extensions import db, limiter
from ..authorization import require_roles
from ..models import AgentSession, UploadedDocument
from documents.resolution import LegalResolutionDraft
from legal.domain.enums import LegalCaseState
from legal.evidence.service import citation_gate
from legal.infrastructure.models import DraftVersionRecord, LegalCaseRecord, ReviewFindingRecord
from tools.create_docx import render_resolution_docx, render_text_docx


documents_bp = Blueprint("documents", __name__, url_prefix="/api/documents")
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
ALLOWED_MIME_TYPES = {
    ".pdf": {"application/pdf"},
    ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/zip"},
    ".txt": {"text/plain"},
    ".md": {"text/markdown", "text/plain"},
}


def upload_root() -> Path:
    root = Path(current_app.instance_path) / "uploads"
    root.mkdir(parents=True, exist_ok=True)
    return root


def session_document_root(user_id: int, session_id: int) -> Path:
    root = upload_root() / str(user_id) / str(session_id)
    root.mkdir(parents=True, exist_ok=True)
    return root


@documents_bp.post("/sessions/<int:session_id>")
@login_required
@limiter.limit("20 per hour")
def upload_document(session_id: int):
    session = AgentSession.query.filter_by(id=session_id, user_id=current_user.id).first()
    if session is None:
        return jsonify(error="not_found", message="Sesion no encontrada."), 404
    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        return jsonify(error="invalid_upload", message="Debe adjuntar un archivo."), 400

    original = secure_filename(uploaded.filename)
    extension = Path(original).suffix.lower()
    if not original or extension not in ALLOWED_EXTENSIONS:
        return jsonify(error="invalid_upload", message="Formato no admitido."), 400
    mime_type = (uploaded.mimetype or mimetypes.guess_type(original)[0] or "application/octet-stream").lower()
    if mime_type not in ALLOWED_MIME_TYPES[extension]:
        return jsonify(error="invalid_upload", message="El tipo MIME no coincide con el formato."), 400

    max_bytes = current_app.config["DOCUMENT_MAX_BYTES"]
    content = uploaded.stream.read(max_bytes + 1)
    if len(content) > max_bytes:
        return jsonify(error="invalid_upload", message="El archivo excede el limite permitido."), 413
    if not content:
        return jsonify(error="invalid_upload", message="El archivo esta vacio."), 400

    stored_name = f"{secrets.token_hex(16)}{extension}"
    target = session_document_root(current_user.id, session.id) / stored_name
    target.write_bytes(content)
    document = UploadedDocument(
        user_id=current_user.id,
        session_id=session.id,
        case_id=session.case_id,
        original_name=original,
        stored_name=stored_name,
        mime_type=mime_type,
        size_bytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
    )
    db.session.add(document)
    db.session.commit()
    return jsonify(document.to_json()), 201


@documents_bp.get("/sessions/<int:session_id>")
@login_required
def list_documents(session_id: int):
    session = AgentSession.query.filter_by(id=session_id, user_id=current_user.id).first()
    if session is None:
        return jsonify(error="not_found", message="Sesion no encontrada."), 404
    documents = UploadedDocument.query.filter_by(session_id=session.id, user_id=current_user.id).all()
    return jsonify(documents=[document.to_json() for document in documents])


@documents_bp.get("/<int:document_id>/download")
@login_required
def download_document(document_id: int):
    document = UploadedDocument.query.filter_by(id=document_id, user_id=current_user.id).first()
    if document is None:
        return jsonify(error="not_found", message="Documento no encontrado."), 404
    path = session_document_root(current_user.id, document.session_id) / document.stored_name
    if not path.is_file():
        return jsonify(error="not_found", message="El archivo no esta disponible."), 404
    return send_file(path, as_attachment=True, download_name=document.original_name, mimetype=document.mime_type)


@documents_bp.get("/sessions/<int:session_id>/generated/<path:filename>")
@login_required
def download_generated_document(session_id: int, filename: str):
    session = AgentSession.query.filter_by(id=session_id, user_id=current_user.id).first()
    if session is None:
        return jsonify(error="not_found", message="Sesion no encontrada."), 404
    safe_name = secure_filename(filename)
    if safe_name != filename or Path(safe_name).suffix.lower() != ".docx":
        return jsonify(error="invalid_document", message="Nombre de documento invalido."), 400
    path = session_document_root(current_user.id, session.id) / safe_name
    if not path.is_file():
        return jsonify(error="not_found", message="Documento generado no encontrado."), 404
    return send_file(
        path,
        as_attachment=True,
        download_name=safe_name,
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@documents_bp.post("/sessions/<int:session_id>/generate-docx")
@login_required
@require_roles("legal_drafter")
@limiter.limit("10 per hour")
def generate_docx(session_id: int):
    session = AgentSession.query.filter_by(id=session_id, user_id=current_user.id).first()
    if session is None:
        return jsonify(error="not_found", message="Sesion no encontrada."), 404
    data = request.get_json(silent=True) or {}
    filename = f"borrador-{uuid.uuid4().hex[:12]}.docx"
    root = session_document_root(current_user.id, session.id)
    if session.case_id:
        case = db.session.get(LegalCaseRecord, session.case_id)
        if case is None or case.owner_user_id != current_user.id:
            return jsonify(error="not_found", message="Expediente no encontrado."), 404
        if case.state not in {
            LegalCaseState.READY_FOR_HUMAN_REVIEW.value,
            LegalCaseState.COMPLETED.value,
        }:
            return jsonify(error="workflow_gate_failed", message="El expediente no esta habilitado para DOCX."), 409
        draft = DraftVersionRecord.query.filter_by(case_id=case.id).order_by(DraftVersionRecord.version.desc()).first()
        blocking = ReviewFindingRecord.query.filter_by(case_id=case.id, blocks_output=True).first()
        if (draft is None or draft.status != "grounded_draft"
                or draft.validation_json.get("errors") or blocking or citation_gate(case.id)):
            return jsonify(error="workflow_gate_failed", message="El borrador no supero los gates requeridos."), 409
        resolution = _persisted_resolution(draft.draft_json)
        result = render_resolution_docx(resolution, filename, root)
    elif "resolution" in data:
        try:
            resolution = LegalResolutionDraft.model_validate(data.get("resolution") or {})
        except Exception:
            return jsonify(error="invalid_document", message="La estructura de la resolucion es invalida."), 400
        result = render_resolution_docx(resolution, filename, root)
    else:
        content = data.get("content")
        if not isinstance(content, str) or not content.strip() or len(content) > 200_000:
            return jsonify(error="invalid_document", message="El contenido del documento es invalido."), 400
        result = render_text_docx(content, filename, root)
    return jsonify(
        **result,
        filename=filename,
        download_url=f"/api/documents/sessions/{session.id}/generated/{filename}",
        status="BORRADOR",
    ), 201


def _persisted_resolution(value: dict) -> LegalResolutionDraft:
    def text(items):
        return [str(item.get("text", "")).strip() for item in items or [] if item.get("text")]

    operative = text(value.get("operative_articles"))
    return LegalResolutionDraft.model_validate({
        "document_type": "resolution",
        "title": value.get("title") or "BORRADOR - Proyecto de resolucion",
        "visto": "\n\n".join(text(value.get("vistos"))),
        "resultandos": text(value.get("resultandos")),
        "considerandos": text(value.get("considerandos")),
        "atento": "\n\n".join(text(value.get("legal_basis"))),
        "resuelve": [
            {"number": str(index), "text": item}
            for index, item in enumerate(operative, 1)
        ],
        "notes": ["BORRADOR SUJETO A REVISION HUMANA"],
    })

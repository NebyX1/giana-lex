import json
from dataclasses import replace
from pathlib import Path
from uuid import UUID, uuid4

from flask import Blueprint, Response, current_app, jsonify, request, stream_with_context
from flask_login import current_user, login_required

from agent.permissions import PermissionPolicy
from agent.runtime import AgentRuntime
from agent.skill_loader import SkillLoader
from llm.openai_compatible import OpenAICompatibleProvider
from moldes.loader import load_mold
from tools.registry import ToolRegistry

from ..extensions import db, limiter
from ..models import AgentSession, Message, ToolCall, UploadedDocument
from ..authorization import has_any_role, require_roles
from ..audit import record_event
from .documents import session_document_root


agent_bp = Blueprint("agent", __name__, url_prefix="/api/agent")
BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _owned_session(session_id: int) -> AgentSession | None:
    return AgentSession.query.filter_by(id=session_id, user_id=current_user.id, archived_at=None).first()


def _components(session: AgentSession):
    registry = current_app.extensions.get("tool_registry")
    if registry is None:
        registry = ToolRegistry().discover()
        current_app.extensions["tool_registry"] = registry
    permissions = PermissionPolicy.load(BACKEND_ROOT / "config" / "permissions.yaml")
    factory = current_app.extensions.get("llm_provider_factory", OpenAICompatibleProvider)
    provider = factory(session.provider_connection)
    return registry, permissions, provider


def _prompt_and_tools(session: AgentSession, registry: ToolRegistry, harness=None) -> tuple[str, set[str]]:
    prompt = (BACKEND_ROOT / "agent" / "prompts" / "GIANA_LEX.md").read_text(encoding="utf-8")
    selected = json.loads(session.active_skills or "[]")
    allowed = {"ask_user", "get_current_agent_status"}
    loader = SkillLoader(BACKEND_ROOT / "skills")
    skills = loader.discover()
    if harness:
        decision = harness.decision or harness.classify(selected, set(skills))
        selected = [decision.primary_skill, *decision.secondary_skills]
    elif not selected:
        selected = ["analista-legal"]
    sections = [prompt]
    skill_sections = []
    for name in selected:
        skill = skills.get(name)
        if skill:
            skill_section = f"\n## Skill activa: {skill.name}\n{skill.instructions}"
            sections.append(skill_section)
            skill_sections.append(skill_section)
            allowed.update(skill.tools)
    if harness and harness.decision and harness.decision.needs_retrieval:
        research_skill = skills.get("investigador-normativo")
        if research_skill:
            allowed.update(research_skill.tools)
    if harness:
        template_content = None
        if harness.state.selected_template:
            mold = load_mold(harness.state.selected_template, BACKEND_ROOT / "moldes")
            template_content = str(mold["content"])
            # The router has already selected and loaded the exact template.
            # Keeping load_mold exposed would make the model guess file paths.
            allowed.discard("load_mold")
        system_prompt = harness.prepare_prompt(prompt, skill_sections, template=template_content)
    else:
        system_prompt = "\n".join(sections)
    if session.case_id:
        system_prompt += _legal_case_context(session.case_id)
    return system_prompt, allowed & registry.names


def _legal_case_context(case_id: str) -> str:
    from legal.infrastructure.models import (
        DraftVersionRecord, EvidenceSpanRecord, FactAssertionRecord, FormInstanceRecord,
        IntakeIntentRecord, IntakeQuestionRequestRecord, LegalCaseRecord,
        PrecedentSearchRunRecord, PrecedentSelectionRecord,
    )

    legal_case = db.session.get(LegalCaseRecord, case_id)
    if legal_case is None:
        return ""
    form = FormInstanceRecord.query.filter_by(case_id=case_id).order_by(FormInstanceRecord.version.desc()).first()
    precedent = PrecedentSelectionRecord.query.filter_by(case_id=case_id).order_by(PrecedentSelectionRecord.created_at.desc()).first()
    search = PrecedentSearchRunRecord.query.filter_by(case_id=case_id).order_by(PrecedentSearchRunRecord.started_at.desc()).first()
    intake_intent = IntakeIntentRecord.query.filter_by(case_id=case_id).first()
    question = IntakeQuestionRequestRecord.query.filter_by(case_id=case_id).order_by(IntakeQuestionRequestRecord.created_at.desc()).first()
    draft = DraftVersionRecord.query.filter_by(case_id=case_id).order_by(DraftVersionRecord.version.desc()).first()
    facts = FactAssertionRecord.query.filter_by(case_id=case_id).order_by(FactAssertionRecord.recorded_at.desc()).all()
    evidence = EvidenceSpanRecord.query.filter_by(case_id=case_id).limit(20).all()
    context = {
        "case_id": case_id,
        "state": legal_case.state,
        "active_run_id": legal_case.active_run_id,
        "task_family": legal_case.task_family,
        "resolution_type": legal_case.resolution_type,
        "workflow_pack": legal_case.workflow_pack_id,
        "intake_intent": intake_intent.intent_json if intake_intent else None,
        "precedent_search": ({
            "status": search.status,
            "match_label": search.match_label,
            "searched_count": search.searched_count,
            "similarities": search.similarities_json,
            "differences": search.differences_json,
            "fallback_reason": search.fallback_reason,
        } if search else None),
        "precedent": ({
            "match_type": precedent.match_type,
            "differences": precedent.differences_json,
            "fallback_reason": precedent.fallback_reason,
        } if precedent else None),
        "question_request": ({
            "id": question.id, "status": question.status,
            "questions": question.questions_json, "errors": question.errors_json,
        } if question else None),
        "form": ({
            "status": form.status,
            "requested_fields": [
                {"key": field.get("key"), "label": field.get("label"), "reason": field.get("reason")}
                for section in (form.schema_json or {}).get("sections", [])
                for field in section.get("fields", [])
            ],
            "answers": form.answers_json,
            "errors": form.errors_json,
        } if form else None),
        "facts": [{"key": item.key, "value": item.value_json, "status": item.verification_status} for item in facts],
        "verified_evidence": [{"source_id": item.source_id, "exact_text": item.exact_text} for item in evidence],
        "draft": draft.draft_json if draft else None,
    }
    return (
        "\n\n## Expediente durable vinculado\n"
        + json.dumps(context, ensure_ascii=False, default=str)
        + "\nConverse normalmente con el usuario usando este contexto. Explique el plan, lo encontrado y el siguiente paso. "
        "No invente hechos ni fuentes. El formulario y las confirmaciones se muestran en la interfaz: cuando el estado "
        "espere datos, ayude a entender los campos sin afirmar que fueron completados; cuando ya fueron enviados, no "
        "pida reenviarlos. No redacte un resultado final si los gates del expediente todavía no lo permiten. Si el estado "
        "es blocked, explique qué evidencia o intervención falta; no ofrezca ejecutar búsquedas, herramientas o transiciones "
        "desde esta conversación, porque solamente los comandos del workflow durable pueden hacerlo. Nunca prometa ni "
        "afirme que ejecutará una acción, transición o herramienta. Solo describa trabajo en curso cuando active_run_id "
        "identifique una ejecución activa; si no existe, limite la respuesta al estado persistido y a orientación."
    )


def _harness(content: str, session: AgentSession, *, resume: bool = False):
    from harness import HarnessOrchestrator, HarnessSettings

    settings = HarnessSettings.from_config(current_app.config)
    if session.provider_connection.provider != "ollama" and settings.fallback_models:
        # Model identifiers are provider-specific; never send an Ollama Cloud
        # fallback name to Featherless, OpenAI, or a custom endpoint.
        settings = replace(settings, fallback_models=())
    if not settings.enabled:
        return None
    sessions = current_app.extensions.setdefault("harness_sessions", {})
    runtime = sessions.get(session.id) if resume else None
    if runtime is None:
        runtime = HarnessOrchestrator(content, settings)
        sessions[session.id] = runtime
        while len(sessions) > 100:
            sessions.pop(next(iter(sessions)))
        if resume:
            for call in session.tool_calls:
                if call.status != "completed" or not call.result:
                    continue
                try:
                    runtime.restore_tool_result(call.tool_name, json.loads(call.result))
                except (TypeError, ValueError, json.JSONDecodeError):
                    continue
    elif resume:
        runtime.resume_execution()
    tasks = current_app.extensions.setdefault("harness_tasks", {})
    tasks[runtime.state.task_id] = runtime
    while len(tasks) > 100:
        tasks.pop(next(iter(tasks)))
    return runtime


def _tool_context(session: AgentSession) -> dict:
    root = session_document_root(session.user_id, session.id)
    documents = {
        document.id: root / document.stored_name
        for document in UploadedDocument.query.filter_by(
            user_id=session.user_id,
            session_id=session.id,
        ).all()
    }
    context = {
        "document_root": root,
        "documents": documents,
        "examples_root": BACKEND_ROOT / "ejemplos",
        "molds_root": BACKEND_ROOT / "moldes",
    }
    try:
        from rag.retriever import get_default_retriever

        context["legal_retriever"] = get_default_retriever()
    except RuntimeError:
        pass
    return context


def _sse(event: dict) -> str:
    return f"event: {event['event']}\ndata: {json.dumps(event['data'], ensure_ascii=False)}\n\n"


@agent_bp.get("/skills")
@login_required
def list_skills():
    loader = SkillLoader(BACKEND_ROOT / "skills")
    skills = loader.discover().values()
    return jsonify(
        skills=[
            {"name": skill.name, "description": skill.description, "version": skill.version, "tools": skill.tools}
            for skill in skills
        ]
    )


@agent_bp.post("/sessions/<int:session_id>/run")
@login_required
@limiter.limit(lambda: current_app.config["AGENT_RUNS_PER_MINUTE"])
def run_agent(session_id: int):
    session = _owned_session(session_id)
    if session is None:
        return jsonify(error="not_found", message="Sesion no encontrada."), 404
    if session.status == "waiting_for_user":
        return jsonify(error="waiting_for_user", message="La sesion espera una respuesta."), 409

    data = request.get_json(silent=True) or {}
    content = str(data.get("content", "")).strip()
    active_skills = data.get("active_skills", [])
    if not content:
        return jsonify(error="invalid_message", message="El mensaje no puede estar vacio."), 400
    if not isinstance(active_skills, list) or not all(isinstance(item, str) for item in active_skills):
        return jsonify(error="invalid_skills", message="Las skills son invalidas."), 400

    if session.case_id:
        operational = _operational_legal_case_chat(session, content)
        if operational is not None:
            return operational
        return _continue_legal_case_chat(session, content)

    from legal.agents.intent_compiler import IntentCompiler
    from legal.domain.enums import TaskFamily

    intent = IntentCompiler().compile(content)
    if intent.task_family == TaskFamily.RESOLUTION_DRAFTING and not session.case_id:
        if not has_any_role("legal_drafter"):
            record_event("authorization.denied", "denied", current_user.id,
                         subject_type="required_role", subject_id="legal_drafter",
                         details={"endpoint": "run_agent", "task_family": intent.task_family.value})
            db.session.commit()
            return jsonify(error="forbidden", message="Se requiere rol de redaccion juridica."), 403
        return _start_legal_drafting(session, content, intent)

    session.active_skills = json.dumps(active_skills)
    db.session.add(Message(session_id=session.id, role="user", content=content))
    db.session.commit()
    def generate():
        streamed_session = db.session.get(AgentSession, session_id)
        registry, permissions, provider = _components(streamed_session)
        harness = _harness(content, streamed_session)
        system_prompt, available_tools = _prompt_and_tools(streamed_session, registry, harness)
        runtime = AgentRuntime(provider, registry, permissions, current_app.config["AGENT_MAX_STEPS"], observer=harness)
        yield from (
            _sse(event)
            for event in runtime.run(
                streamed_session,
                system_prompt,
                available_tools,
                _tool_context(streamed_session),
            )
        )

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache, no-store", "X-Accel-Buffering": "no"},
    )


@agent_bp.post("/sessions/<int:session_id>/answer")
@login_required
@limiter.limit(lambda: current_app.config["AGENT_RUNS_PER_MINUTE"])
def answer_question(session_id: int):
    session = _owned_session(session_id)
    if session is None:
        return jsonify(error="not_found", message="Sesion no encontrada."), 404
    if session.status != "waiting_for_user":
        return jsonify(error="not_waiting", message="La sesion no espera una respuesta."), 409

    data = request.get_json(silent=True) or {}
    answers = data.get("answers")
    if not isinstance(answers, dict) or not answers:
        return jsonify(error="invalid_answers", message="Las respuestas son invalidas."), 400
    pending = (
        ToolCall.query.filter_by(session_id=session.id, status="waiting_for_user")
        .order_by(ToolCall.id.desc())
        .first()
    )
    if pending is None:
        return jsonify(error="invalid_state", message="No existe una pregunta pendiente."), 409

    result = json.dumps({"answers": answers}, ensure_ascii=False)
    pending.status = "completed"
    pending.result = result
    db.session.add(
        Message(session_id=session.id, role="tool", content=result, tool_call_id=pending.call_id)
    )
    session.pending_question = None
    session.status = "ready"
    db.session.commit()

    pending_call_id = pending.call_id

    def generate():
        streamed_session = db.session.get(AgentSession, session_id)
        registry, permissions, provider = _components(streamed_session)
        latest_request = next((message.content for message in reversed(streamed_session.messages) if message.role == "user"), "")
        harness = _harness(latest_request, streamed_session, resume=True)
        system_prompt, available_tools = _prompt_and_tools(streamed_session, registry, harness)
        runtime = AgentRuntime(provider, registry, permissions, current_app.config["AGENT_MAX_STEPS"], observer=harness)
        yield _sse({"event": "question.answered", "data": {"call_id": pending_call_id}})
        yield from (
            _sse(event)
            for event in runtime.run(
                streamed_session,
                system_prompt,
                available_tools,
                _tool_context(streamed_session),
            )
        )

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


@agent_bp.post("/sessions/<int:session_id>/cancel")
@login_required
def cancel_agent(session_id: int):
    session = _owned_session(session_id)
    if session is None:
        return jsonify(error="not_found", message="Sesion no encontrada."), 404
    session.status = "cancelled"
    db.session.commit()
    return jsonify(status="cancelled")


@agent_bp.post("/sessions/<int:session_id>/retry")
@login_required
@limiter.limit(lambda: current_app.config["AGENT_RUNS_PER_MINUTE"])
def retry_agent(session_id: int):
    """Resume a failed provider phase without repeating research or user input."""
    session = _owned_session(session_id)
    if session is None:
        return jsonify(error="not_found", message="Sesion no encontrada."), 404
    if session.status != "failed":
        return jsonify(error="invalid_state", message="Solo puede reintentarse una ejecución fallida."), 409
    latest_request = next(
        (message.content for message in reversed(session.messages) if message.role == "user"),
        "",
    )
    if not latest_request:
        return jsonify(error="invalid_state", message="No existe una solicitud para reintentar."), 409
    if session.case_id:
        return _continue_legal_case_chat(session, latest_request, persist_user=False)
    session.status = "ready"
    db.session.commit()

    def generate():
        streamed_session = db.session.get(AgentSession, session_id)
        registry, permissions, provider = _components(streamed_session)
        harness = _harness(latest_request, streamed_session, resume=True)
        system_prompt, available_tools = _prompt_and_tools(streamed_session, registry, harness)
        runtime = AgentRuntime(
            provider,
            registry,
            permissions,
            current_app.config["AGENT_MAX_STEPS"],
            observer=harness,
        )
        yield _sse({"event": "agent.retrying", "data": {"session_id": session_id}})
        yield from (
            _sse(event)
            for event in runtime.run(
                streamed_session,
                system_prompt,
                available_tools,
                _tool_context(streamed_session),
            )
        )

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache, no-store", "X-Accel-Buffering": "no"},
    )


def _continue_legal_case_chat(session: AgentSession, content: str, *, persist_user: bool = True):
    """Answer conversationally from durable case state; workflow commands own all mutations."""
    session.status = "running"
    if persist_user:
        db.session.add(Message(session_id=session.id, role="user", content=content))
    db.session.commit()
    session_id = session.id

    def generate():
        streamed_session = db.session.get(AgentSession, session_id)
        try:
            _registry, _permissions, provider = _components(streamed_session)
            base_prompt = (BACKEND_ROOT / "agent" / "prompts" / "GIANA_LEX.md").read_text(encoding="utf-8")
            messages = [{"role": "system", "content": base_prompt + _legal_case_context(streamed_session.case_id)}]
            messages.extend(
                {"role": item.role, "content": item.content}
                for item in streamed_session.messages[-30:]
                if item.role in {"user", "assistant"} and item.content
            )
            yield _sse({"event": "session.started", "data": {"session_id": session_id}})
            result = provider.run(messages, [], streamed_session.model)
            answer = (result.text or "").strip()
            if not answer:
                raise RuntimeError("El proveedor no devolvió una respuesta conversacional.")
            assistant = Message(session_id=session_id, role="assistant", content=answer)
            streamed_session.status = "completed"
            db.session.add(assistant)
            db.session.commit()
            yield _sse({"event": "assistant.completed", "data": {"message": assistant.to_json()}})
            yield _sse({"event": "agent.completed", "data": {"status": "completed"}})
        except Exception:
            current_app.logger.exception("Failed linked legal case conversation")
            streamed_session.status = "failed"
            db.session.commit()
            yield _sse({"event": "error", "data": {
                "message": "No se pudo completar la respuesta del expediente.",
                "retryable": True,
            }})

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache, no-store", "X-Accel-Buffering": "no"},
    )


def _operational_legal_case_chat(session: AgentSession, content: str):
    from legal.agents.case_conversation_router import CaseConversationRouter
    from legal.infrastructure.models import (
        DraftVersionRecord, HumanTaskRecord, LegalCaseRecord, WorkflowRunRecord,
    )

    legal_case = db.session.get(LegalCaseRecord, session.case_id)
    if legal_case is None or legal_case.owner_user_id != current_user.id:
        return None
    draft = DraftVersionRecord.query.filter_by(case_id=legal_case.id).order_by(
        DraftVersionRecord.version.desc()
    ).first()
    open_tasks = HumanTaskRecord.query.filter_by(case_id=legal_case.id, status="open").all()
    active_run = db.session.get(WorkflowRunRecord, legal_case.active_run_id) if legal_case.active_run_id else None
    decision = CaseConversationRouter().decide(
        content,
        state=legal_case.state,
        has_draft=draft is not None,
        has_open_review=any(item.task_type == "review_draft" for item in open_tasks),
        has_open_form=any(item.task_type == "complete_form" for item in open_tasks),
        draft_version=draft.version if draft else None,
        active_run_id=active_run.id if active_run else None,
        current_step=active_run.current_step if active_run else None,
    )
    if decision is None:
        return None

    user_message = Message(session_id=session.id, role="user", content=content)
    assistant = Message(session_id=session.id, role="assistant", content=decision.text)
    session.status = "completed"
    db.session.add_all([user_message, assistant])
    db.session.commit()
    events = [
        {"event": "case.ui.action", "data": {
            "case_id": legal_case.id,
            "action": decision.action,
            "intent": decision.intent.value,
        }},
        {"event": "assistant.completed", "data": {"message": assistant.to_json()}},
        {"event": "agent.completed", "data": {"status": "completed"}},
    ]
    return Response(
        "".join(_sse(event) for event in events),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache, no-store", "X-Accel-Buffering": "no"},
    )


def _start_legal_drafting(session: AgentSession, content: str, intent):
    """Compatibility adapter: legal drafting enters the durable workflow, never AgentRuntime."""
    from legal.application.command_service import LegalCommandService
    from legal.bootstrap import build_outbox_publisher
    from legal.domain.commands import CreateLegalCase, StartLegalWorkflow
    from legal.intake.service import persist_intake_intent

    service = LegalCommandService()
    if session.case_id:
        case_id = UUID(session.case_id)
        created = False
    else:
        case_id = uuid4()
        case, created = service.create_case(CreateLegalCase(
            command_id=uuid4(), case_id=case_id, actor_user_id=current_user.id,
            idempotency_key=f"legacy-agent-case:{session.id}", title=content[:300],
            task_family=intent.task_family, resolution_type=intent.resolution_type,
            jurisdiction=intent.jurisdiction, risk_tier=intent.risk_tier,
            workflow_pack_id=intent.workflow_pack_id, workflow_pack_version=intent.workflow_pack_version,
        ))
        session.case_id = str(case.id)
        UploadedDocument.query.filter_by(
            session_id=session.id, user_id=current_user.id, case_id=None
        ).update({"case_id": str(case.id)})
    persist_intake_intent(str(case_id), content, intent)
    session.active_skills = json.dumps([])
    db.session.add(Message(session_id=session.id, role="user", content=content))
    db.session.commit()

    command, command_created = service.enqueue_start(StartLegalWorkflow(
        command_id=uuid4(), case_id=case_id, actor_user_id=current_user.id,
        idempotency_key=f"legacy-agent-start:{session.id}:{case_id}",
    ))
    published = not command_created or build_outbox_publisher().publish_command(UUID(command.id))
    db.session.expire_all()
    assistant_message = Message(
        session_id=session.id,
        role="assistant",
        content=_legal_workflow_started_message(
            str(case_id), dispatched=published,
            asynchronous=current_app.config["LEGAL_DISPATCHER"] == "redis",
        ),
    )
    db.session.add(assistant_message)
    record_event("legacy_agent.drafting_adapted", "accepted", current_user.id,
                 subject_type="legal_case", subject_id=case_id,
                 details={"session_id": session.id, "command_id": command.id})
    db.session.commit()

    events = [
        {"event": "legal.case.linked", "data": {"case_id": str(case_id), "created": created}},
        {"event": "assistant.completed", "data": {"message": assistant_message.to_json()}},
        {"event": "legal.workflow.started", "data": {
            "case_id": str(case_id), "command_id": command.id,
            "status": command.status, "dispatched": published,
        }},
    ]
    return Response(
        "".join(_sse(event) for event in events), mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache, no-store", "X-Accel-Buffering": "no"},
    )


def _legal_workflow_started_message(case_id: str, *, dispatched: bool = True, asynchronous: bool = False) -> str:
    from legal.intake.presentation import intake_act_label, required_missing_groups
    from legal.infrastructure.models import (
        ExampleVersionRecord, FormInstanceRecord, IntakeIntentRecord, IntakeQuestionRequestRecord,
        PrecedentSearchRunRecord,
    )

    intent = IntakeIntentRecord.query.filter_by(case_id=case_id).first()
    search = PrecedentSearchRunRecord.query.filter_by(case_id=case_id).order_by(
        PrecedentSearchRunRecord.started_at.desc()
    ).first()
    question = IntakeQuestionRequestRecord.query.filter_by(case_id=case_id).order_by(
        IntakeQuestionRequestRecord.created_at.desc()
    ).first()
    form = FormInstanceRecord.query.filter_by(case_id=case_id).order_by(FormInstanceRecord.version.desc()).first()
    intent_json = intent.intent_json if intent else {}
    subtype = intent_json.get("subtype")
    parts = []
    if subtype:
        parts.append(f"Identifiqué la actuación como {intake_act_label(subtype)}.")
    if asynchronous and not dispatched:
        parts.append("No se pudo despachar el workflow; la búsqueda de antecedentes no comenzó.")
    elif search is None:
        parts.append("La búsqueda de antecedentes está pendiente." if asynchronous else "La búsqueda de antecedentes aún no tiene un resultado persistido.")
    elif search.status in {"unavailable", "failed"}:
        parts.append(search.fallback_reason or "La búsqueda de antecedentes no está disponible.")
    elif search.selected_example_version_id:
        selected = db.session.get(ExampleVersionRecord, search.selected_example_version_id)
        profile = (selected.profile_json or {}) if selected else {}
        title = selected.title if selected else "Antecedente sin título"
        number = profile.get("document_number")
        source_url = profile.get("source_url")
        details = title
        if number:
            details += f"; número {number}"
        if source_url:
            details += f"; fuente {source_url}"
        parts.append(f"Antecedente estructural seleccionado: {details}.")
        if search.differences_json:
            parts.append("Diferencias materiales registradas: " + "; ".join(search.differences_json) + ".")
    else:
        parts.append(search.fallback_reason or "La búsqueda no seleccionó un antecedente comparable.")
    if question and question.status in {"pending", "partial"} and form:
        groups = required_missing_groups(form)
        parts.append("Aún faltan datos en: " + "; ".join(groups) + ".")
    elif question and question.status == "answered":
        parts.append("No quedan datos obligatorios por solicitar; los hechos aportados requieren confirmación.")
    elif asynchronous and dispatched:
        parts.append("Las preguntas se compilarán cuando finalice la búsqueda.")
    return " ".join(parts)


@agent_bp.post("/sessions/<int:session_id>/second-opinion")
@login_required
@require_roles("legal_reviewer")
@limiter.limit(lambda: current_app.config["AGENT_RUNS_PER_MINUTE"])
def second_opinion(session_id: int):
    session = _owned_session(session_id)
    if session is None:
        return jsonify(error="not_found", message="Sesion no encontrada."), 404
    data = request.get_json(silent=True) or {}
    draft = str(data.get("draft", "")).strip()
    if not draft or len(draft) > current_app.config["CHAT_MAX_MESSAGE_CHARS"]:
        return jsonify(error="invalid_document", message="El borrador es invalido."), 400

    registry, _permissions, provider = _components(session)
    loader = SkillLoader(BACKEND_ROOT / "skills")
    skill = loader.discover()["auditor-compliance"]
    base_prompt = (BACKEND_ROOT / "agent" / "prompts" / "GIANA_LEX.md").read_text(encoding="utf-8")
    clean_messages = [
        {"role": "system", "content": f"{base_prompt}\n\n## Segunda opinion independiente\n{skill.instructions}"},
        {
            "role": "user",
            "content": "Revise independientemente este BORRADOR. No asuma que es correcto. Separe hallazgos verificados, puntos a verificar e incertidumbres.\n\n" + draft,
        },
    ]
    tools = registry.definitions(set(skill.tools) & registry.names)
    try:
        result = provider.run(clean_messages, tools, session.model)
    except Exception:
        return jsonify(error="provider_error", message="No se pudo completar la segunda opinion."), 502
    return jsonify(
        status="BORRADOR_REVISADO",
        review=result.text,
        tool_calls=[{"call_id": call.call_id, "name": call.name, "arguments": call.arguments} for call in result.tool_calls],
        independent_context=True,
    )

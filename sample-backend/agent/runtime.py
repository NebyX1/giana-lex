import json
import logging
from datetime import datetime
from typing import Any, Iterator

import httpx
from pydantic import ValidationError

from app.extensions import db
from llm.provider import LLMProvider
from app.models import AgentSession, Message, ToolCall
from tools.base import AgentWaitingForUser
from tools.registry import ToolRegistry

from .permissions import Permission, PermissionPolicy


logger = logging.getLogger(__name__)


class AgentRuntime:
    def __init__(
        self,
        provider: LLMProvider,
        registry: ToolRegistry,
        permissions: PermissionPolicy,
        max_steps: int = 12,
        observer: Any | None = None,
    ):
        self.provider = provider
        self.registry = registry
        self.permissions = permissions
        self.max_steps = max_steps
        self.observer = observer

    def run(
        self,
        session: AgentSession,
        system_prompt: str,
        tools: set[str] | None = None,
        tool_context: dict[str, Any] | None = None,
    ) -> Iterator[dict[str, Any]]:
        session.status = "running"
        session.pending_question = None
        db.session.commit()
        if self.observer:
            self.observer.run_started(session)
        yield {"event": "session.started", "data": {"session_id": session.id}}

        context = [{"role": "system", "content": system_prompt}]
        calls_by_message: dict[int, list[ToolCall]] = {}
        for persisted_call in session.tool_calls:
            if persisted_call.message_id:
                calls_by_message.setdefault(persisted_call.message_id, []).append(persisted_call)
        for message in session.messages:
            content = _compact_tool_payload(message.content) if message.role == "tool" else message.content
            item: dict[str, Any] = {"role": message.role, "content": content}
            if message.role == "assistant" and calls_by_message.get(message.id):
                item["tool_calls"] = [
                    {
                        "id": call.call_id,
                        "type": "function",
                        "function": {"name": call.tool_name, "arguments": call.arguments},
                    }
                    for call in calls_by_message[message.id]
                ]
            if message.role == "tool" and message.tool_call_id:
                item["tool_call_id"] = message.tool_call_id
            context.append(item)
        definitions = self.registry.definitions(tools)

        for _step in range(self.max_steps):
            db.session.refresh(session)
            if session.status == "cancelled":
                yield {"event": "agent.completed", "data": {"status": "cancelled"}}
                return
            yield {"event": "assistant.started", "data": {}}
            if self.observer and not self.observer.before_model():
                session.status = "failed"
                db.session.commit()
                yield {"event": "error", "data": {"message": "El harness alcanzo el presupuesto de ejecucion."}}
                return
            call_definitions = (
                self.observer.definitions_for_next_call(definitions)
                if self.observer and hasattr(self.observer, "definitions_for_next_call")
                else definitions
            )
            if self.observer and hasattr(self.observer, "instruction_for_next_call"):
                handoff = self.observer.instruction_for_next_call()
                if handoff:
                    context.append({"role": "system", "content": handoff})
            try:
                selected_model = self.observer.model_for_next_call(session.model) if self.observer else session.model
                result = self.provider.run(context, call_definitions, selected_model)
            except Exception as exc:
                if self.observer and self.observer.provider_failed(exc):
                    continue
                logger.exception(
                    "Provider failed after retry policy for session_id=%s model=%s",
                    session.id,
                    session.model or "provider-default",
                )
                session.status = "failed"
                db.session.commit()
                yield {
                    "event": "error",
                    "data": {
                        "message": _provider_error_message(exc),
                        "retryable": True,
                    },
                }
                return

            if self.observer:
                self.observer.model_completed(result)

            if not result.tool_calls:
                final_text = result.text
                final_action = "accept"
                if self.observer:
                    final_action, final_text, feedback = self.observer.validate_final(result.text)
                    if final_action == "retry":
                        context.append({"role": "system", "content": feedback})
                        continue
                if final_text:
                    yield {"event": "assistant.delta", "data": {"content": final_text}}
                message = Message(session_id=session.id, role="assistant", content=final_text)
                session.status = "needs_review" if final_action == "safe" else "completed"
                session.updated_at = datetime.utcnow()
                db.session.add(message)
                db.session.commit()
                yield {"event": "assistant.completed", "data": {"message": message.to_json()}}
                yield {"event": "agent.completed", "data": {"usage": result.usage, "status": session.status}}
                if self.observer:
                    self.observer.run_completed(session)
                return

            if result.text:
                yield {"event": "assistant.delta", "data": {"content": result.text}}

            assistant_message = Message(session_id=session.id, role="assistant", content=result.text)
            db.session.add(assistant_message)
            db.session.flush()
            context.append({
                "role": "assistant",
                "content": result.text,
                "tool_calls": [
                    {"id": call.call_id, "type": "function", "function": {"name": call.name, "arguments": json.dumps(call.arguments)}}
                    for call in result.tool_calls
                ],
            })

            for call in result.tool_calls:
                persisted = ToolCall(
                    session_id=session.id,
                    user_id=session.user_id,
                    message_id=assistant_message.id,
                    call_id=call.call_id,
                    tool_name=call.name,
                    arguments=json.dumps(call.arguments, ensure_ascii=False),
                    status="running",
                    started_at=datetime.utcnow(),
                )
                db.session.add(persisted)
                db.session.commit()
                yield {"event": "tool.started", "data": {"call_id": call.call_id, "tool_name": call.name}}

                guard_error = None
                if self.observer and tools is not None and call.name not in tools:
                    guard_error = "Tool fuera del alcance de las skills activas."
                if self.observer and not guard_error:
                    guard_error = self.observer.before_tool(call.name, call.arguments)
                if guard_error:
                    if guard_error.startswith(("RESEARCH_COMPLETE:", "TOOL_SKIPPED:")):
                        payload = {
                            "status": "skipped",
                            "reason": "research_phase_closed",
                            "message": guard_error.split(":", 1)[1].strip(),
                        }
                        serialized = json.dumps(payload, ensure_ascii=False)
                        persisted.status = "skipped"
                        persisted.result = serialized
                        persisted.finished_at = datetime.utcnow()
                        db.session.add(Message(
                            session_id=session.id,
                            role="tool",
                            content=serialized,
                            tool_call_id=call.call_id,
                        ))
                        db.session.commit()
                        context.append({"role": "tool", "tool_call_id": call.call_id, "content": serialized})
                        yield {"event": "tool.skipped", "data": {"call_id": call.call_id, "tool_name": call.name, "result": payload}}
                        continue
                    persisted.status = "failed"
                    persisted.error = guard_error
                    persisted.finished_at = datetime.utcnow()
                    error_payload = {
                        "error": "tool_rejected",
                        "tool_name": call.name,
                        "message": guard_error,
                        "retryable": not guard_error.startswith("LOOP_DETECTED"),
                    }
                    serialized = json.dumps(error_payload, ensure_ascii=False)
                    db.session.add(Message(
                        session_id=session.id,
                        role="tool",
                        content=serialized,
                        tool_call_id=call.call_id,
                    ))
                    db.session.commit()
                    yield {"event": "tool.failed", "data": {"call_id": call.call_id, "message": guard_error}}
                    model_payload = _compact_tool_payload(serialized)
                    contextualized = self.observer.contextualize_tool_result(model_payload) if self.observer else model_payload
                    context.append({"role": "tool", "tool_call_id": call.call_id, "content": contextualized})
                    if guard_error.startswith("LOOP_DETECTED"):
                        session.status = "failed"
                        db.session.commit()
                        yield {"event": "error", "data": {"message": "Se detuvo una secuencia repetida de herramientas sin progreso."}}
                        return
                    continue

                permission = self.permissions.check(call.name)
                if permission is Permission.DENY:
                    persisted.status = "denied"
                    persisted.error = "Tool no permitida."
                    persisted.finished_at = datetime.utcnow()
                    db.session.commit()
                    yield {"event": "tool.failed", "data": {"call_id": call.call_id, "message": "Tool no permitida."}}
                    return
                if permission is Permission.ASK:
                    session.status = "waiting_for_permission"
                    db.session.commit()
                    yield {"event": "agent.waiting", "data": {"reason": "permission", "call_id": call.call_id}}
                    return

                try:
                    context_values = {
                        "session_id": session.id,
                        "user_id": session.user_id,
                        "status": session.status,
                        **(tool_context or {}),
                    }
                    tool_result = self.registry.execute(
                        call.name,
                        call.arguments,
                        context_values,
                    )
                except AgentWaitingForUser as waiting:
                    persisted.status = "waiting_for_user"
                    persisted.result = json.dumps(waiting.payload, ensure_ascii=False)
                    session.status = "waiting_for_user"
                    session.pending_question = persisted.result
                    db.session.commit()
                    if self.observer:
                        self.observer.waiting_for_user(waiting.payload)
                    yield {"event": "question.created", "data": {"call_id": call.call_id, **waiting.payload}}
                    yield {"event": "agent.waiting", "data": {"reason": "user"}}
                    return
                except Exception as exc:
                    error_payload = _tool_error_payload(self.registry, call.name, exc)
                    serialized = json.dumps(error_payload, ensure_ascii=False)
                    persisted.status = "failed"
                    persisted.error = str(error_payload["message"])
                    persisted.result = serialized
                    persisted.finished_at = datetime.utcnow()
                    db.session.add(Message(
                        session_id=session.id,
                        role="tool",
                        content=serialized,
                        tool_call_id=call.call_id,
                    ))
                    db.session.commit()
                    hard_error = None
                    if self.observer:
                        hard_error = self.observer.tool_failed(call.name, call.arguments, exc)
                    yield {"event": "tool.failed", "data": {"call_id": call.call_id, "message": error_payload["message"]}}
                    model_payload = _compact_tool_payload(serialized)
                    contextualized = self.observer.contextualize_tool_result(model_payload) if self.observer else model_payload
                    context.append({"role": "tool", "tool_call_id": call.call_id, "content": contextualized})
                    if hard_error:
                        session.status = "failed"
                        db.session.commit()
                        yield {"event": "error", "data": {"message": hard_error}}
                        return
                    continue

                serialized = json.dumps(tool_result, ensure_ascii=False)
                discovered_sources = (
                    self.observer.tool_completed(call.name, call.arguments, tool_result)
                    if self.observer
                    else _sources_from_result(tool_result)
                )
                persisted.status = "completed"
                persisted.result = serialized
                persisted.sources = json.dumps(discovered_sources, ensure_ascii=False)
                persisted.finished_at = datetime.utcnow()
                db.session.add(
                    Message(
                        session_id=session.id,
                        role="tool",
                        content=serialized,
                        tool_call_id=call.call_id,
                    )
                )
                db.session.commit()
                model_payload = _compact_tool_payload(serialized)
                contextualized = self.observer.contextualize_tool_result(model_payload) if self.observer else model_payload
                context.append({"role": "tool", "tool_call_id": call.call_id, "content": contextualized})
                yield {"event": "tool.completed", "data": {"call_id": call.call_id, "tool_name": call.name, "result": tool_result}}
                for source in discovered_sources:
                    yield {"event": "source.found", "data": {"source": source}}

        session.status = "failed"
        db.session.commit()
        if self.observer:
            self.observer.iteration_limit_reached()
        yield {"event": "error", "data": {"message": "El agente alcanzo el limite de pasos."}}


def _sources_from_result(result: Any) -> list[dict[str, Any]]:
    values = result if isinstance(result, list) else result.get("results", []) if isinstance(result, dict) else []
    sources = []
    for value in values:
        if not isinstance(value, dict) or not (value.get("source") or value.get("source_file")):
            continue
        metadata = value.get("metadata") or {}
        sources.append({
            "id": value.get("identifier") or value.get("id") or value.get("source"),
            "title": metadata.get("title") or value.get("title") or value.get("source") or value.get("source_file"),
            "excerpt": value.get("text") or value.get("snippet"),
            "category": value.get("category") or metadata.get("category"),
            "corpus": metadata.get("corpus"),
            "url": metadata.get("source_url") or value.get("url"),
        })
    return sources


def _tool_error_payload(registry: ToolRegistry, name: str, exc: Exception) -> dict[str, Any]:
    tool = registry.get(name)
    schema = tool.input_schema.model_json_schema() if tool else {}
    if isinstance(exc, ValidationError):
        message = "Los argumentos no cumplen el contrato de la herramienta."
        issues = [
            {
                "field": ".".join(str(part) for part in issue.get("loc", ())),
                "message": issue.get("msg", "Valor invalido."),
                "type": issue.get("type", "validation_error"),
            }
            for issue in exc.errors(include_url=False, include_input=False)
        ]
    elif isinstance(exc, FileNotFoundError):
        message = "El recurso solicitado no existe. Use uno de los valores permitidos por el contrato."
        issues = []
    elif isinstance(exc, (TypeError, ValueError)):
        message = str(exc) or "La herramienta rechazo la solicitud."
        issues = []
    else:
        message = "La herramienta no pudo completar la operacion."
        issues = []
    return {
        "error": "tool_failed",
        "tool_name": name,
        "message": message,
        "issues": issues,
        "expected_arguments": schema,
        "retryable": isinstance(exc, (ValidationError, TypeError, ValueError, FileNotFoundError)),
    }


def _provider_error_message(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status in {401, 403}:
            return "El proveedor cloud rechazó la autenticación. Revise la conexión y reintente; el trabajo quedó guardado."
        if status == 404:
            return "El modelo cloud seleccionado no está disponible. El trabajo quedó guardado para reintentar con otro modelo."
        if status == 429:
            return "El proveedor cloud está temporalmente saturado. Los reintentos automáticos se agotaron; el trabajo quedó guardado."
        if status == 413:
            return "El proveedor rechazó el tamaño del contexto. El trabajo quedó guardado para reintentar con contexto reducido."
        if status >= 500:
            return "El proveedor cloud no respondió después de los reintentos automáticos. El trabajo quedó guardado y puede reintentarse."
    if isinstance(exc, (TimeoutError, httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError)):
        return "La conexión con el proveedor cloud agotó los reintentos. El trabajo quedó guardado y puede reintentarse."
    return "El proveedor cloud no pudo finalizar la respuesta. El trabajo quedó guardado y puede reintentarse."


def _compact_tool_payload(serialized: str, max_chars: int = 7000) -> str:
    """Keep model context bounded while retaining full results in the database/UI."""
    if len(serialized) <= max_chars:
        return serialized
    try:
        value = json.loads(serialized)
    except (TypeError, json.JSONDecodeError):
        return serialized[:max_chars] + "\n[contenido adicional omitido del contexto del modelo]"

    def compact(item: Any, *, string_limit: int, list_limit: int) -> Any:
        if isinstance(item, str):
            return item if len(item) <= string_limit else item[:string_limit] + "…"
        if isinstance(item, list):
            return [compact(entry, string_limit=string_limit, list_limit=list_limit) for entry in item[:list_limit]]
        if isinstance(item, dict):
            return {
                key: compact(entry, string_limit=string_limit, list_limit=list_limit)
                for key, entry in item.items()
            }
        return item

    reduced = json.dumps(compact(value, string_limit=900, list_limit=6), ensure_ascii=False)
    if len(reduced) <= max_chars:
        return reduced
    return json.dumps(compact(value, string_limit=350, list_limit=4), ensure_ascii=False)[:max_chars]

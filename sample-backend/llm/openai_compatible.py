import json
import uuid
from typing import Any

import httpx
from flask import current_app

from app.models import ProviderConnection
from app.services.provider_service import ensure_valid_token, get_auth_header

from .provider import LLMProvider, ProviderResult, ToolCallRequest


class OpenAICompatibleProvider(LLMProvider):
    def __init__(self, connection: ProviderConnection):
        self.connection = connection

    def run(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        model: str | None = None,
    ) -> ProviderResult:
        if not ensure_valid_token(self.connection):
            raise RuntimeError("No se pudo renovar la autenticacion del proveedor.")

        headers = get_auth_header(self.connection)
        headers["Content-Type"] = "application/json"
        if self.connection.provider == "openai":
            response_tools = [
                {
                    **item["function"],
                    "parameters": _strict_json_schema(item["function"].get("parameters", {})),
                    "strict": True,
                }
                for item in tools
            ]
            body = {
                "model": model or self.connection.default_model,
                "input": _responses_input(messages),
                "tools": response_tools,
                "tool_choice": "auto",
                "stream": False,
            }
            url = f"{self.connection.base_url.rstrip('/')}/responses"
        else:
            body = {
                "model": model or self.connection.default_model,
                "messages": messages,
                "tools": tools,
                "tool_choice": "auto",
                "stream": False,
            }
            url = f"{self.connection.base_url.rstrip('/')}/chat/completions"
        response = httpx.post(
            url,
            json=body,
            headers=headers,
            timeout=httpx.Timeout(
                connect=current_app.config["PROVIDER_CONNECT_TIMEOUT"],
                read=current_app.config["PROVIDER_READ_TIMEOUT"],
                write=current_app.config["PROVIDER_CONNECT_TIMEOUT"],
                pool=current_app.config["PROVIDER_CONNECT_TIMEOUT"],
            ),
        )
        response.raise_for_status()
        payload = response.json()
        return parse_responses(payload) if self.connection.provider == "openai" else parse_chat_completion(payload)


def _strict_json_schema(value: Any) -> Any:
    """Normalize Pydantic schemas to the strict function-calling subset."""
    if isinstance(value, list):
        return [_strict_json_schema(item) for item in value]
    if not isinstance(value, dict):
        return value
    normalized = {
        key: _strict_json_schema(item)
        for key, item in value.items()
        if key not in {"default", "title"}
    }
    if normalized.get("type") == "object" or "properties" in normalized:
        properties = normalized.get("properties") or {}
        normalized["additionalProperties"] = False
        normalized["required"] = list(properties)
    return normalized


def _responses_input(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    converted = []
    for message in messages:
        if message.get("role") == "tool":
            converted.append({
                "type": "function_call_output",
                "call_id": message.get("tool_call_id"),
                "output": message.get("content", ""),
            })
            continue
        converted.append({"role": message.get("role"), "content": message.get("content", "")})
        for call in message.get("tool_calls") or []:
            function = call.get("function") or {}
            converted.append({
                "type": "function_call",
                "call_id": call.get("id"),
                "name": function.get("name"),
                "arguments": function.get("arguments", "{}"),
            })
    return converted


def parse_chat_completion(payload: dict[str, Any]) -> ProviderResult:
    choices = payload.get("choices") or []
    if not choices:
        raise ValueError("El proveedor no devolvio una respuesta valida.")
    choice = choices[0]
    message = choice.get("message") or {}
    calls = []
    for raw_call in message.get("tool_calls") or []:
        function = raw_call.get("function") or {}
        try:
            arguments = json.loads(function.get("arguments") or "{}")
        except json.JSONDecodeError as exc:
            raise ValueError("El proveedor devolvio argumentos de tool invalidos.") from exc
        calls.append(
            ToolCallRequest(
                call_id=raw_call.get("id") or f"call_{uuid.uuid4().hex}",
                name=function.get("name") or "",
                arguments=arguments,
            )
        )
    usage = payload.get("usage") or {}
    return ProviderResult(
        text=message.get("content") or "",
        tool_calls=calls,
        finish_reason=choice.get("finish_reason"),
        usage={key: int(value) for key, value in usage.items() if isinstance(value, int)},
    )


def parse_responses(payload: dict[str, Any]) -> ProviderResult:
    text_parts = []
    calls = []
    for item in payload.get("output") or []:
        if item.get("type") == "function_call":
            try:
                arguments = json.loads(item.get("arguments") or "{}")
            except json.JSONDecodeError as exc:
                raise ValueError("El proveedor devolvio argumentos de tool invalidos.") from exc
            calls.append(ToolCallRequest(
                call_id=item.get("call_id") or item.get("id") or f"call_{uuid.uuid4().hex}",
                name=item.get("name") or "",
                arguments=arguments,
            ))
        if item.get("type") == "message":
            for content in item.get("content") or []:
                if content.get("type") in {"output_text", "text"}:
                    text_parts.append(content.get("text") or "")
    usage = payload.get("usage") or {}
    return ProviderResult(
        text="".join(text_parts),
        tool_calls=calls,
        finish_reason=payload.get("status"),
        usage={key: int(value) for key, value in usage.items() if isinstance(value, int)},
    )

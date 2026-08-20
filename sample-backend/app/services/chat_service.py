import json

import httpx
from flask import current_app

from ..models import ProviderConnection
from .provider_service import ensure_valid_token, get_auth_header


def build_chat_request(conn: ProviderConnection, messages: list[dict], model: str | None = None) -> dict:
    selected_model = model or conn.default_model or "gpt-4o"
    return {
        "model": selected_model,
        "messages": messages,
        "stream": True,
    }


def stream_chat(conn: ProviderConnection, messages: list[dict], model: str | None = None):
    if not ensure_valid_token(conn):
        yield _sse_event("error", {"message": "No se pudo refrescar el token de acceso."})
        return

    body = build_chat_request(conn, messages, model)
    headers = get_auth_header(conn)
    headers["Content-Type"] = "application/json"
    headers["Accept"] = "text/event-stream"

    base_url = conn.base_url.rstrip("/")
    if conn.provider == "openai":
        url = f"{base_url}/responses"
    else:
        url = f"{base_url}/chat/completions"

    connect_timeout = current_app.config["PROVIDER_CONNECT_TIMEOUT"]
    read_timeout = current_app.config["PROVIDER_READ_TIMEOUT"]

    try:
        with httpx.stream(
            "POST",
            url,
            json=body,
            headers=headers,
            timeout=httpx.Timeout(connect=connect_timeout, read=read_timeout, write=connect_timeout, pool=connect_timeout),
        ) as resp:
            if resp.status_code >= 400:
                error_body = resp.read().decode("utf-8", errors="replace")
                yield _sse_event("error", {"message": f"Proveedor error {resp.status_code}: {error_body[:500]}"})
                return
            yield from _parse_sse_stream(resp)
    except httpx.TimeoutException:
        yield _sse_event("error", {"message": "Tiempo de espera agotado."})
    except Exception as exc:
        yield _sse_event("error", {"message": f"Error de conexion: {exc}"})


def _parse_sse_stream(resp):
    for line in resp.iter_lines():
        if not line or line.startswith(":"):
            continue
        if line.startswith("data: "):
            data = line[6:]
        elif line.startswith("data:"):
            data = line[5:]
        else:
            continue
        if data.strip() == "[DONE]":
            yield _sse_event("done", {})
            return
        try:
            chunk = json.loads(data)
        except json.JSONDecodeError:
            continue
        content = _extract_content(chunk)
        if content:
            yield _sse_event("delta", {"content": content})
        finish = _extract_finish(chunk)
        if finish:
            yield _sse_event("done", {"finish_reason": finish})
            return


def _extract_content(chunk: dict) -> str:
    if "choices" in chunk and chunk["choices"]:
        delta = chunk["choices"][0].get("delta", {})
        return delta.get("content", "") or ""
    if "delta" in chunk:
        return chunk["delta"].get("content", "") or ""
    return ""


def _extract_finish(chunk: dict) -> str | None:
    if "choices" in chunk and chunk["choices"]:
        return chunk["choices"][0].get("finish_reason")
    return None


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
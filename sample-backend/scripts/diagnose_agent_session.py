"""Inspect an agent session without exposing credentials or prompt contents.

Use ``--live`` only for an explicit provider smoke test. It repeats the next
model call with the persisted conversation and prints a sanitized outcome.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

import httpx

from app import create_app
from agent.permissions import PermissionPolicy
from agent.runtime import AgentRuntime
from app.api.agent import BACKEND_ROOT, _harness, _prompt_and_tools, _tool_context
from app.extensions import db
from app.models import AgentSession
from harness import HarnessOrchestrator, HarnessSettings
from llm.openai_compatible import OpenAICompatibleProvider
from tools.registry import ToolRegistry


def build_context(session: AgentSession, system_prompt: str) -> list[dict]:
    calls_by_message: dict[int, list] = {}
    for call in session.tool_calls:
        if call.message_id:
            calls_by_message.setdefault(call.message_id, []).append(call)

    context: list[dict] = [{"role": "system", "content": system_prompt}]
    for message in session.messages:
        item = {"role": message.role, "content": message.content}
        if message.role == "assistant" and message.id in calls_by_message:
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
    return context


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("session_id", type=int)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        session = db.session.get(AgentSession, args.session_id)
        if session is None:
            raise SystemExit("Session not found")
        registry = ToolRegistry().discover()
        latest_request = next(
            (message.content for message in session.messages if message.role == "user"),
            "",
        )
        harness = HarnessOrchestrator(latest_request, HarnessSettings.from_config(app.config))
        system_prompt, allowed_tools = _prompt_and_tools(session, registry, harness)
        definitions = registry.definitions(allowed_tools)
        context = build_context(session, system_prompt)
        report = {
            "session_id": session.id,
            "status": session.status,
            "provider_kind": session.provider_connection.provider,
            "provider_name": session.provider_connection.display_name,
            "model": session.model or session.provider_connection.default_model,
            "message_chars": sum(len(message.content) for message in session.messages),
            "system_chars": len(system_prompt),
            "tool_schema_chars": len(json.dumps(definitions)),
            "tool_calls": [
                {"name": call.tool_name, "status": call.status, "error": call.error}
                for call in session.tool_calls
            ],
        }
        if args.resume:
            session.status = "ready"
            db.session.commit()
            runtime_harness = _harness(latest_request, session, resume=True)
            resume_prompt, resume_tools = _prompt_and_tools(session, registry, runtime_harness)
            runtime = AgentRuntime(
                OpenAICompatibleProvider(session.provider_connection),
                registry,
                PermissionPolicy.load(BACKEND_ROOT / "config" / "permissions.yaml"),
                app.config["AGENT_MAX_STEPS"],
                observer=runtime_harness,
            )
            events = list(runtime.run(session, resume_prompt, resume_tools, _tool_context(session)))
            report["resume"] = {
                "status": session.status,
                "events": [event["event"] for event in events],
                "error": next(
                    (event["data"].get("message") for event in events if event["event"] == "error"),
                    None,
                ),
            }
        if args.live:
            try:
                result = OpenAICompatibleProvider(session.provider_connection).run(
                    context,
                    definitions,
                    session.model,
                )
                report["live"] = {
                    "ok": True,
                    "text_chars": len(result.text),
                    "tool_calls": [call.name for call in result.tool_calls],
                    "finish_reason": result.finish_reason,
                }
            except httpx.HTTPStatusError as exc:
                report["live"] = {
                    "ok": False,
                    "type": "HTTPStatusError",
                    "status": exc.response.status_code,
                    "body": exc.response.text[:2000],
                }
            except Exception as exc:  # diagnostic boundary
                report["live"] = {
                    "ok": False,
                    "type": type(exc).__name__,
                    "message": str(exc)[:2000],
                }
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

import json
from pathlib import Path

import pytest

from agent.permissions import Permission, PermissionPolicy
from agent.skill_loader import SkillLoader
from llm.openai_compatible import parse_chat_completion, parse_responses
from llm.provider import LLMProvider, ProviderResult, ToolCallRequest
from tools.registry import ToolRegistry

from app.extensions import db
from app.models import AgentSession, ProviderConnection


def test_provider_parser_normalizes_tool_calls():
    result = parse_chat_completion({
        "choices": [{
            "message": {"content": None, "tool_calls": [{
                "id": "call-1",
                "function": {"name": "get_current_agent_status", "arguments": '{"include_session":true}'},
            }]},
            "finish_reason": "tool_calls",
        }],
        "usage": {"total_tokens": 10},
    })
    assert result.tool_calls[0].name == "get_current_agent_status"
    assert result.tool_calls[0].arguments == {"include_session": True}
    assert result.usage["total_tokens"] == 10


def test_responses_parser_normalizes_text_and_tools():
    result = parse_responses({
        "status": "completed",
        "output": [
            {"type": "message", "content": [{"type": "output_text", "text": "Reviso la fuente."}]},
            {"type": "function_call", "call_id": "call-r", "name": "search_national_norms", "arguments": '{"query":"competencia"}'},
        ],
        "usage": {"total_tokens": 12},
    })
    assert result.text == "Reviso la fuente."
    assert result.tool_calls[0].name == "search_national_norms"


def test_registry_discovers_and_validates_tools():
    registry = ToolRegistry().discover()
    assert {"ask_user", "get_current_agent_status"} <= registry.names
    definitions = registry.definitions()
    assert any(item["function"]["name"] == "ask_user" for item in definitions)
    with pytest.raises(ValueError):
        registry.register(registry.get("ask_user"))


def test_permission_policy_defaults_to_deny():
    policy = PermissionPolicy.load(Path(__file__).resolve().parents[1] / "config" / "permissions.yaml")
    assert policy.check("ask_user") is Permission.ALLOW
    assert policy.check("execute_shell") is Permission.DENY
    assert policy.check("unknown_tool") is Permission.DENY


def test_skill_loader_discovers_skills():
    loader = SkillLoader(Path(__file__).resolve().parents[1] / "skills")
    skills = loader.discover()
    assert len(skills) == 8
    assert skills["analista-legal"].version >= 2
    assert "ask_user" in skills["redactor-legal"].tools


class FakeProvider(LLMProvider):
    def __init__(self, connection):
        self.responses = [
            ProviderResult(tool_calls=[ToolCallRequest("ask-1", "ask_user", {
                "questions": [{"id": "object", "type": "text", "question": "Cual es el objeto?", "required": True}]
            })]),
            ProviderResult(tool_calls=[ToolCallRequest("status-1", "get_current_agent_status", {"include_session": True})]),
            ProviderResult(text="Con la informacion aportada puedo continuar.", finish_reason="stop"),
        ]

    def run(self, messages, tools, model=None):
        return self.responses.pop(0)


def _session(app):
    with app.app_context():
        conn = ProviderConnection(
            user_id=1, provider="ollama", display_name="Fake", auth_mode="none",
            base_url="http://localhost:11434/v1", default_model="fake",
        )
        db.session.add(conn)
        db.session.commit()
        return conn.id


def test_agent_ask_user_pause_and_resume(authed_client, csrf_headers, app):
    provider_id = _session(app)
    session_id = authed_client.post(
        "/api/sessions", json={"provider_connection_id": provider_id}, headers=csrf_headers
    ).get_json()["id"]
    fake = FakeProvider(None)
    app.extensions["llm_provider_factory"] = lambda _connection: fake

    response = authed_client.post(
        f"/api/agent/sessions/{session_id}/run",
        json={"content": "Necesito analizar un documento.", "active_skills": ["redactor-legal"]},
        headers=csrf_headers,
    )
    body = response.get_data(as_text=True)
    assert "question.created" in body
    assert "agent.waiting" in body

    response = authed_client.post(
        f"/api/agent/sessions/{session_id}/answer",
        json={"answers": {"object": "Autorizar un convenio"}},
        headers=csrf_headers,
    )
    body = response.get_data(as_text=True)
    assert "question.answered" in body
    assert "tool.completed" in body
    assert "agent.completed" in body

    opened = authed_client.get(f"/api/sessions/{session_id}").get_json()
    assert opened["case_id"] is None
    assert opened["status"] == "completed"
    assert any(call["tool_name"] == "ask_user" and call["status"] == "completed" for call in opened["tool_calls"])
    assert opened["messages"][-1]["content"] == "Con la informacion aportada puedo continuar."

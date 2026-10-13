import asyncio
from dataclasses import replace
from threading import Event
import time

import pytest
from pydantic_ai.models.test import TestModel
from pydantic_ai.models.function import FunctionModel

from agents import PydanticAgents
from config import settings
from intake_fallback import generic_intake
from orchestrator import Orchestrator
from schemas import LLMRun
from state import Stage
from storage import Storage
from test_api import FakeAgents
from tools.search_examples import search_examples


REQUEST = "Giana, quiero que me ayudes a crear una resolución para la contratación de un zafral para el área de parques y jardines."


def test_initial_agent_cancels_slow_provider_and_has_no_search_tools(monkeypatch):
    async def slow_model(messages, info):
        assert info.function_tools == []
        await asyncio.sleep(2)
        pytest.fail("La llamada debería haberse cancelado")

    monkeypatch.setattr("agents.legal_knowledge_tools", lambda: pytest.fail("El intake no debe habilitar búsquedas"))
    agents = PydanticAgents(replace(settings, intake_timeout_seconds=0.1),
                            model=FunctionModel(slow_model), legal_knowledge=object())
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        agents.classify_resolution({"solicitud": REQUEST, "candidatos": []})
    assert time.monotonic() - started < 1


def test_unrelated_examples_produce_local_contract_form_without_llm(monkeypatch, tmp_path):
    # Keep an explicitly unrelated corpus as the production library grows.
    for filename in ("01_compensacion_funcionario.md", "02_trasposicion_rubros.md"):
        (tmp_path / filename).write_text((settings.examples_dir / filename).read_text(encoding="utf-8"), encoding="utf-8")
    agents = PydanticAgents(settings, model=TestModel())
    monkeypatch.setattr(agents, "_run", lambda *args: pytest.fail("No debe llamar al modelo"))
    run = agents.intake({"solicitud": REQUEST, "candidatos": [
        item.model_dump() for item in search_examples(REQUEST, tmp_path)
    ]})
    assert run.usage["requests"] == 0
    assert run.output.match_status == "none"
    assert {"contratado", "funciones", "plazo", "remuneracion"} <= {f.id for f in run.output.form.fields}


@pytest.mark.parametrize("slow_step", ["search", "intake"])
def test_deadline_delivers_form_and_late_work_cannot_overwrite_answers(tmp_path, slow_step):
    release, finished = Event(), Event()

    class SlowAgents(FakeAgents):
        def intake(self, context):
            if slow_step == "intake":
                release.wait(2)
                finished.set()
            return super().intake(context)

    class Knowledge:
        def search_resolution_types(self, *args):
            if slow_step == "search":
                release.wait(2)
                finished.set()
            return []

    config = replace(settings, intake_timeout_seconds=0.05)
    storage = Storage(tmp_path / "state.sqlite3")
    orchestrator = Orchestrator(config, storage, SlowAgents(), Knowledge())
    try:
        started = time.monotonic()
        state = orchestrator.create_conversation(REQUEST)
        assert time.monotonic() - started < 1
        assert state.stage == Stage.COLLECTING_INFO
        assert "tiempo disponible" in state.last_debug["message"]
        answers = {field.id: "Dato proporcionado" for field in state.current_form.fields if field.required}
        drafted = orchestrator.submit_form(state.id, answers)
        assert drafted.stage == Stage.DRAFT_REVIEW
    finally:
        release.set()
    assert finished.wait(1)
    assert storage.get(state.id).form_answers == answers
    assert storage.get(state.id).stage == Stage.DRAFT_REVIEW


def test_provider_failure_returns_persisted_generic_form(tmp_path):
    class BrokenAgents:
        def intake(self, context):
            raise RuntimeError("provider unavailable")

    orchestrator = Orchestrator(settings, Storage(tmp_path / "state.sqlite3"), BrokenAgents())
    state = orchestrator.create_conversation("Preparar un documento")
    assert state.stage == Stage.COLLECTING_INFO
    assert orchestrator.get(state.id).current_form == state.current_form
    assert state.selected_examples == []


def test_fallback_draft_uses_generic_mold_without_unrelated_examples(tmp_path):
    class Agents(FakeAgents):
        def intake(self, context):
            return LLMRun(output=generic_intake(REQUEST), usage={}, duration_ms=0)

        def draft(self, context):
            assert context["molde"]
            assert context["ejemplos_relevantes"] == []
            assert context["solicitud"] == REQUEST
            return super().draft(context)

    orchestrator = Orchestrator(settings, Storage(tmp_path / "state.sqlite3"), Agents())
    state = orchestrator.create_conversation(REQUEST)
    answers = {f.id: "Dato proporcionado" for f in state.current_form.fields if f.required}
    assert orchestrator.submit_form(state.id, answers).stage == Stage.DRAFT_REVIEW

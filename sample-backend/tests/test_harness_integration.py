import json

import httpx

from app.extensions import db
from app.models import AgentSession, ProviderConnection
from legal.infrastructure.models import LegalCaseRecord
from llm.provider import LLMProvider, ProviderResult, ToolCallRequest


def create_session(client, csrf_headers, app):
    with app.app_context():
        provider = ProviderConnection(
            user_id=1, provider="ollama", display_name="Harness fake", auth_mode="none",
            base_url="http://localhost:11434/v1", default_model="fake",
        )
        db.session.add(provider)
        db.session.commit()
        provider_id = provider.id
    return client.post("/api/sessions", json={"provider_connection_id": provider_id}, headers=csrf_headers).get_json()["id"]


class RecordingProvider(LLMProvider):
    def __init__(self, final="Texto corregido."):
        self.final = final
        self.calls = []

    def run(self, messages, tools, model=None):
        self.calls.append((messages, tools))
        return ProviderResult(text=self.final)


class FlakyCloudProvider(LLMProvider):
    def __init__(self, failures: int):
        self.failures = failures
        self.calls = 0

    def run(self, messages, tools, model=None):
        self.calls += 1
        if self.calls <= self.failures:
            raise httpx.ReadTimeout("temporary cloud timeout")
        return ProviderResult(text="Texto corregido y finalizado.")


def test_legacy_mode_preserves_original_prompt_flow(authed_client, csrf_headers, app):
    app.config["HARNESS_ENABLED"] = False
    provider = RecordingProvider()
    app.extensions["llm_provider_factory"] = lambda _connection: provider
    session_id = create_session(authed_client, csrf_headers, app)
    body = authed_client.post(
        f"/api/agent/sessions/{session_id}/run",
        json={"content": "Corregi este texto.", "active_skills": ["corrector-estilo-ortografia-legal"]},
        headers=csrf_headers,
    ).get_data(as_text=True)
    assert "agent.completed" in body
    assert "## Harness policy" not in provider.calls[0][0][0]["content"]
    assert not app.extensions.get("harness_tasks")


def test_harness_mode_wraps_existing_runtime(authed_client, csrf_headers, app):
    app.config.update(HARNESS_ENABLED=True, HARNESS_MODE="adaptive", LLM_CAPABILITY_PROFILE="balanced")
    provider = RecordingProvider()
    app.extensions["llm_provider_factory"] = lambda _connection: provider
    session_id = create_session(authed_client, csrf_headers, app)
    body = authed_client.post(
        f"/api/agent/sessions/{session_id}/run",
        json={"content": "Corregi la ortografia.", "active_skills": []},
        headers=csrf_headers,
    ).get_data(as_text=True)
    assert "agent.completed" in body
    prompt = provider.calls[0][0][0]["content"]
    assert "## Harness policy" in prompt
    assert "corrector-estilo-ortografia-legal" in prompt
    task = list(app.extensions["harness_tasks"].values())[-1]
    assert task.state.stage is TaskStage.COMPLETED
    assert task.trace.metrics["llm_calls"] == 1


def test_cloud_timeout_is_retried_automatically(authed_client, csrf_headers, app):
    app.config.update(
        HARNESS_ENABLED=True,
        HARNESS_MODE="adaptive",
        HARNESS_MAX_RETRIES=2,
        HARNESS_RETRY_BACKOFF_SECONDS=0,
    )
    provider = FlakyCloudProvider(failures=1)
    app.extensions["llm_provider_factory"] = lambda _connection: provider
    session_id = create_session(authed_client, csrf_headers, app)
    body = authed_client.post(
        f"/api/agent/sessions/{session_id}/run",
        json={"content": "Corregí este texto.", "active_skills": []},
        headers=csrf_headers,
    ).get_data(as_text=True)
    assert provider.calls == 2
    assert "agent.completed" in body
    opened = authed_client.get(f"/api/sessions/{session_id}").get_json()
    assert opened["status"] == "completed"


def test_failed_cloud_phase_can_resume_without_repeating_work(authed_client, csrf_headers, app):
    app.config.update(
        HARNESS_ENABLED=True,
        HARNESS_MODE="adaptive",
        HARNESS_MAX_RETRIES=2,
        HARNESS_RETRY_BACKOFF_SECONDS=0,
    )
    provider = FlakyCloudProvider(failures=3)
    app.extensions["llm_provider_factory"] = lambda _connection: provider
    session_id = create_session(authed_client, csrf_headers, app)
    first = authed_client.post(
        f"/api/agent/sessions/{session_id}/run",
        json={"content": "Corregí este texto.", "active_skills": []},
        headers=csrf_headers,
    ).get_data(as_text=True)
    assert "retryable" in first
    assert authed_client.get(f"/api/sessions/{session_id}").get_json()["status"] == "failed"

    resumed = authed_client.post(
        f"/api/agent/sessions/{session_id}/retry",
        json={},
        headers=csrf_headers,
    ).get_data(as_text=True)
    assert provider.calls == 4
    assert "agent.completed" in resumed
    opened = authed_client.get(f"/api/sessions/{session_id}").get_json()
    assert opened["status"] == "completed"
    assert [message["role"] for message in opened["messages"]].count("user") == 1


class RepeatingSearchProvider(LLMProvider):
    def __init__(self):
        self.step = 0

    def run(self, messages, tools, model=None):
        self.step += 1
        if not tools:
            return ProviderResult(text="No se localizaron fuentes suficientes; se requiere revisión jurídica.")
        return ProviderResult(tool_calls=[ToolCallRequest(f"search-{self.step}", "search_national_norms", {"query": "competencia"})])


class EmptyRetriever:
    def search(self, **kwargs):
        return []


def test_harness_stops_repeated_search_loop(authed_client, csrf_headers, app, monkeypatch):
    app.config.update(HARNESS_ENABLED=True, HARNESS_MODE="strict", LLM_CAPABILITY_PROFILE="weak")
    app.extensions["llm_provider_factory"] = lambda _connection: RepeatingSearchProvider()
    monkeypatch.setattr("rag.retriever.get_default_retriever", lambda: EmptyRetriever())
    session_id = create_session(authed_client, csrf_headers, app)
    body = authed_client.post(
        f"/api/agent/sessions/{session_id}/run",
        json={"content": "Busque normativa sobre competencia.", "active_skills": ["investigador-normativo"]},
        headers=csrf_headers,
    ).get_data(as_text=True)
    assert "research_phase_closed" in body
    assert "tool.failed" not in body
    task = list(app.extensions["harness_tasks"].values())[-1]
    assert task.trace.metrics["loops_prevented"] == 1


class HallucinatingProvider(LLMProvider):
    def __init__(self):
        self.calls = 0

    def run(self, messages, tools, model=None):
        self.calls += 1
        return ProviderResult(text="La Intendencia tiene competencia conforme a la Ley 99.")


def test_harness_blocks_hallucination_after_retry_budget(authed_client, csrf_headers, app):
    app.config.update(HARNESS_ENABLED=True, HARNESS_MODE="strict", HARNESS_MAX_RETRIES=1)
    provider = HallucinatingProvider()
    app.extensions["llm_provider_factory"] = lambda _connection: provider
    session_id = create_session(authed_client, csrf_headers, app)
    body = authed_client.post(
        f"/api/agent/sessions/{session_id}/run",
        json={"content": "¿Tiene competencia juridica la Intendencia?", "active_skills": []},
        headers=csrf_headers,
    ).get_data(as_text=True)
    assert provider.calls == 2
    opened = authed_client.get(f"/api/sessions/{session_id}").get_json()
    assert "No es posible completar" in opened["messages"][-1]["content"]
    task = list(app.extensions["harness_tasks"].values())[-1]
    assert task.trace.metrics["unsupported_claims_blocked"] == 2
    assert "agent.completed" in body


class TranspositionProvider(LLMProvider):
    def __init__(self):
        self.step = 0
        self.prompts = []
        self.tool_names = []

    def run(self, messages, tools, model=None):
        self.step += 1
        self.prompts.append(messages[0]["content"])
        self.tool_names.append({item["function"]["name"] for item in tools})
        if self.step == 1:
            return ProviderResult(tool_calls=[ToolCallRequest(
                "example-budget", "search_examples", {"query": "transposición de fondos"},
            )])
        if self.step == 2:
            return ProviderResult(tool_calls=[ToolCallRequest("ask-budget", "ask_user", {
                "questions": [
                    {"id": "amount", "type": "text", "question": "Monto y moneda", "required": True},
                    {"id": "items", "type": "text", "question": "Partidas de origen y destino", "required": True},
                ]
            })])
        if self.step == 3:
            return ProviderResult(tool_calls=[ToolCallRequest(
                "search-budget",
                "search_national_norms",
                {"query": "norma habilitante transposición de fondos"},
            )])
        draft = {
            "document_type": "resolution",
            "title": "RESOLUCIÓN - BORRADOR",
            "number": None,
            "place": "Lavalleja",
            "date": None,
            "visto": "La solicitud de transposición de fondos y sus antecedentes.",
            "resultandos": ["Que se informaron el monto y las partidas involucradas."],
            "considerandos": ["Que corresponde documentar la decisión con revisión jurídica humana."],
            "atento": "A la evidencia normativa incorporada al expediente.",
            "resuelve": [{"number": "1", "text": "Disponer la transposición indicada en el expediente."}],
            "notes": ["BORRADOR SUJETO A REVISIÓN HUMANA"],
        }
        return ProviderResult(text=json.dumps(draft, ensure_ascii=False))


class BudgetRetriever:
    def search(self, query, corpus, top_k=5, **_filters):
        return [{
            "identifier": f"budget-{corpus}",
            "text": "Fuente normativa oficial de prueba para transposición presupuestal.",
            "source": f"official-{corpus}.txt",
            "metadata": {"corpus": corpus, "title": "Norma presupuestal de prueba"},
            "score": 1.0,
        }]


def test_transposition_flow_keeps_state_and_loads_template_deterministically(
    authed_client, csrf_headers, app, monkeypatch
):
    app.config.update(
        HARNESS_ENABLED=True,
        HARNESS_MODE="adaptive",
        HARNESS_MAX_LLM_CALLS=10,
        LLM_CAPABILITY_PROFILE="balanced",
    )
    provider = TranspositionProvider()
    app.extensions["llm_provider_factory"] = lambda _connection: provider
    monkeypatch.setattr("rag.retriever.get_default_retriever", lambda: BudgetRetriever())
    session_id = create_session(authed_client, csrf_headers, app)

    first = authed_client.post(
        f"/api/agent/sessions/{session_id}/run",
        json={
            "content": "Me ayudas a redactar una resolución sobre transposición de fondos?",
            "active_skills": ["redactor-legal"],
        },
        headers=csrf_headers,
    ).get_data(as_text=True)
    assert "legal.workflow.started" in first
    assert provider.tool_names == []
    with app.app_context():
        session = db.session.get(AgentSession, session_id)
        case = db.session.get(LegalCaseRecord, session.case_id)
        assert case.workflow_pack_id == "resolution.fund_transposition"
        assert case.state == "awaiting_facts"


class ContractProvider(LLMProvider):
    def __init__(self):
        self.step = 0
        self.tool_names = []
        self.prompts = []

    def run(self, messages, tools, model=None):
        self.step += 1
        names = {item["function"]["name"] for item in tools}
        self.tool_names.append(names)
        self.prompts.append(messages[0]["content"])
        if self.step == 1:
            return ProviderResult(tool_calls=[ToolCallRequest(
                "example-contract", "search_examples", {"query": "arrendamiento de obra"},
            )])
        if self.step == 2:
            return ProviderResult(tool_calls=[ToolCallRequest("ask-contract", "ask_user", {
                "questions": [{"id": "deliverable", "type": "text", "question": "Resultado verificable", "required": True}]
            })])
        if "search_national_norms" in names:
            return ProviderResult(tool_calls=[ToolCallRequest(
                f"contract-law-{self.step}",
                "search_national_norms",
                {"query": f"arrendamiento de obra contratación pública consulta {self.step}"},
            )])
        return ProviderResult(text="""# BORRADOR — CONTRATO DE ARRENDAMIENTO DE OBRA

## Partes y representación
La Intendencia y la profesional identificadas en el expediente proyectan celebrar este contrato.

## Cláusula 1. Objeto y resultado
La contratada entregará el proyecto ejecutivo confirmado por las partes.

## Cláusula 2. Plazo, precio y pago
Se aplicarán el plazo, precio y los hitos confirmados en el expediente.

## Cláusula 3. Obligaciones y recepción
La contraparte técnica verificará los entregables y comunicará observaciones.

## Cláusula 4. Independencia técnica, confidencialidad y terminación
La ejecución será autónoma. Las partes protegerán la información y documentarán cualquier terminación.

## Firmas
Se completarán al suscribir.

## Puntos para revisión antes de firmar
BORRADOR sujeto a control jurídico, contable y administrativo previo.""")


def test_contract_flow_asks_once_caps_research_and_delivers_contract(
    authed_client, csrf_headers, app, monkeypatch
):
    app.config.update(HARNESS_ENABLED=True, HARNESS_MODE="adaptive", HARNESS_MAX_LLM_CALLS=10)
    provider = ContractProvider()
    app.extensions["llm_provider_factory"] = lambda _connection: provider
    monkeypatch.setattr("rag.retriever.get_default_retriever", lambda: BudgetRetriever())
    session_id = create_session(authed_client, csrf_headers, app)

    first = authed_client.post(
        f"/api/agent/sessions/{session_id}/run",
        json={"content": "Redactá un contrato de arrendamiento de obra para un ingeniero.", "active_skills": ["redactor-legal"]},
        headers=csrf_headers,
    ).get_data(as_text=True)
    assert "question.created" in first

    resumed = authed_client.post(
        f"/api/agent/sessions/{session_id}/answer",
        json={"answers": {"deliverable": "Proyecto ejecutivo completo"}},
        headers=csrf_headers,
    ).get_data(as_text=True)
    assert "agent.completed" in resumed
    assert "CONTRATO DE ARRENDAMIENTO DE OBRA" in resumed
    assert all("contrato-arrendamiento-obra" in prompt for prompt in provider.prompts)
    assert "search_national_norms" not in provider.tool_names[-1]
    opened = authed_client.get(f"/api/sessions/{session_id}").get_json()
    calls = opened["tool_calls"]
    assert [call["tool_name"] for call in calls].count("ask_user") == 1
    assert calls[0]["tool_name"] == "search_examples"
    assert [call["tool_name"] for call in calls].count("search_national_norms") == 1
    assert all(call["status"] in {"completed", "skipped"} for call in calls)
    assert not any(call["status"] == "failed" for call in calls)


# Imported late to make the public integration assertion explicit.
from harness.state import TaskStage

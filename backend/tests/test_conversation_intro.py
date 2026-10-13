from dataclasses import replace

import pytest

from config import settings
from conversation_intro import introductory_response
from orchestrator import Orchestrator
from state import Stage
from storage import Storage


@pytest.mark.parametrize("message", [
    "Hola, me puedes ayudar?", "¡Hola!", "Buenas tardes, Giana Lex",
    "Giana, ¿me podés ayudar?", "¿En qué me puedes ayudar?",
    "¿Qué puedes hacer por mí?", "¿Cuáles son tus capacidades?",
    "Necesito ayuda", "Hola, ¿puedes ayudarme, por favor?", "¿Quién eres?",
])
def test_greetings_explain_capabilities_without_model_or_search(tmp_path, message):
    class UnusedKnowledge:
        def search_resolution_types(self, *_args):
            pytest.fail("A greeting must not search for resolution types")

    class UnusedCatalog:
        def search(self, *_args):
            pytest.fail("A greeting must not search for examples")

    config = replace(settings, llm_base_url="", llm_api_key="", llm_model="")
    orchestrator = Orchestrator(config, Storage(tmp_path / "intro.sqlite3"), None,
                                UnusedKnowledge(), UnusedCatalog())
    state = orchestrator.create_conversation(message, owner_user_id=7)
    assert state.stage == Stage.NEW
    assert state.current_form is None
    assert state.classification_warning is None
    assert state.example_search_status == "not_started"
    assert "Sí, puedo ayudarte" in state.last_debug["message"]
    assert "resoluciones" in state.last_debug["message"]
    assert "Comprobar un borrador" in state.last_debug["message"]
    assert "Cuéntame qué necesitas" in state.last_debug["message"]
    restored = orchestrator.get(state.id)
    assert restored.owner_user_id == 7
    assert restored.intro_messages[-1]["text"] == state.last_debug["message"]


@pytest.mark.parametrize("message", [
    "Hola, me puedes ayudar a redactar una resolución de contratación?",
    "Giana, necesito una resolución para contratar un zafral.",
    "Buenas tardes, revisar los riesgos jurídicos de un acto administrativo.",
    "Ayúdame a preparar un documento", "Preparar una resolución",
    "Hola, necesito ayuda con una adjudicación de licitación.",
    "Hola, me puedes ayudar? Necesito trasladar a un funcionario.",
    "Buscar ejemplos de resoluciones de exoneración de patente.",
])
def test_substantive_requests_are_not_treated_as_greetings(message):
    assert introductory_response(message) is None

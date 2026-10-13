import json

from pydantic_ai.models.test import TestModel

from agents import PydanticAgents
from config import settings
from schemas import IntakeOutput


def test_prompted_output_pipeline_with_pydantic_ai_test_model():
    payload = {
        "match_status": "none",
        "assistant_message": "No encontre un antecedente suficientemente parecido.",
        "matched_examples": [],
        "form": {
            "title": "Datos necesarios",
            "fields": [{"id": "objeto", "label": "Objeto", "field_type": "textarea", "required": True}],
        },
    }
    agents = PydanticAgents(settings, model=TestModel(custom_output_text=json.dumps(payload)))

    run = agents.intake({"solicitud": "compensacion mensual", "candidatos": [{
        "filename": "modelo.md", "title": "Compensacion mensual", "excerpt": "Compensacion mensual", "score": 1,
    }], "molde": "RESUELVE"})

    assert isinstance(run.output, IntakeOutput)
    assert run.output.match_status == "none"
    assert run.usage["requests"] == 1

import json
from pathlib import Path

from legal.agents.intent_compiler import IntentCompiler
from legal.domain.enums import TaskFamily


def evaluate(dataset: Path | None = None) -> dict:
    path = dataset or Path(__file__).with_name("typologies.json")
    fixtures = json.loads(path.read_text(encoding="utf-8"))
    results = []
    for fixture in fixtures:
        intent = IntentCompiler().compile(fixture["request"], TaskFamily.RESOLUTION_DRAFTING)
        correct = (
            intent.subtype == fixture["subtype"]
            and intent.selected_workflow_id == fixture["workflow"]
            and intent.selected_workflow_version == fixture["version"]
        )
        expected_facts = fixture.get("expected_known_facts")
        facts_correct = None if expected_facts is None else all(
            intent.known_facts.get(key) == value for key, value in expected_facts.items()
        )
        results.append({"id": fixture["id"], "correct": correct, "facts_correct": facts_correct})
    fact_results = [item for item in results if item["facts_correct"] is not None]
    return {
        "count": len(results),
        "typology_accuracy": sum(item["correct"] for item in results) / len(results),
        "fact_extraction_accuracy": (
            sum(item["facts_correct"] for item in fact_results) / len(fact_results) if fact_results else None
        ),
        "results": results,
    }


if __name__ == "__main__":
    print(json.dumps(evaluate(), indent=2, ensure_ascii=False))

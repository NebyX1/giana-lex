import json
from pathlib import Path

from legal.agents.intent_compiler import IntentCompiler
from legal.domain.enums import TaskFamily


def evaluate(root: Path | None = None) -> dict:
    fixture_root = root or Path(__file__).with_name("resolutions")
    rows = []
    for path in sorted(fixture_root.glob("*.json")):
        fixture = json.loads(path.read_text(encoding="utf-8"))
        intent = IntentCompiler().compile(fixture["request"], TaskFamily.RESOLUTION_DRAFTING)
        rows.append({"id": fixture["id"], "workflow_correct": intent.workflow_pack_id == fixture["workflow"]})
    return {"cases": rows, "workflow_accuracy": sum(row["workflow_correct"] for row in rows) / len(rows)}


if __name__ == "__main__":
    print(json.dumps(evaluate(), indent=2))

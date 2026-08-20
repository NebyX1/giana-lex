from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from ejemplos.loader import EXAMPLES_ROOT, search_examples
from .base import Tool


class SearchExamplesInput(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    limit: int = Field(default=10, ge=1, le=50)


class SearchExamples(Tool[SearchExamplesInput]):
    name = "search_examples"
    description = "Busca ejemplos no vinculantes y los marca expresamente como EXAMPLE, no autoridad."
    input_schema = SearchExamplesInput

    def execute(self, arguments: SearchExamplesInput, context: dict[str, Any]) -> dict[str, object]:
        root = context.get("examples_root", EXAMPLES_ROOT)
        return {"results": search_examples(arguments.query, Path(root), arguments.limit), "classification": "EXAMPLE"}


tool = SearchExamples()

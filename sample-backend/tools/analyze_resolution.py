from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator

from documents.parsers import parse_document
from documents.resolution import parse_resolution
from .base import Tool


class AnalyzeResolutionInput(BaseModel):
    text: str | None = Field(default=None, max_length=2_000_000)
    path: str | None = Field(default=None, max_length=4096)

    @model_validator(mode="after")
    def one_source(self):
        if (self.text is None) == (self.path is None):
            raise ValueError("Indique exactamente uno de: text o path.")
        return self


class AnalyzeResolution(Tool[AnalyzeResolutionInput]):
    name = "analyze_resolution"
    description = "Convierte la estructura observable de una resolucion a JSON validado."
    input_schema = AnalyzeResolutionInput

    def execute(self, arguments: AnalyzeResolutionInput, context: dict[str, Any]) -> dict[str, Any]:
        text = arguments.text
        if arguments.path is not None:
            root = context.get("document_root", Path.cwd())
            text = parse_document(arguments.path, allowed_root=root).text
        return parse_resolution(text or "")


tool = AnalyzeResolution()

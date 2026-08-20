from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator

from documents.legal_references import extract_legal_references
from documents.parsers import parse_document
from .base import Tool


class ExtractLegalReferencesInput(BaseModel):
    text: str | None = Field(default=None, max_length=2_000_000)
    path: str | None = Field(default=None, max_length=4096)

    @model_validator(mode="after")
    def one_source(self):
        if (self.text is None) == (self.path is None):
            raise ValueError("Indique exactamente uno de: text o path.")
        return self


class ExtractLegalReferences(Tool[ExtractLegalReferencesInput]):
    name = "extract_legal_references"
    description = "Extrae menciones normativas mediante patrones acotados, sin afirmar su vigencia."
    input_schema = ExtractLegalReferencesInput

    def execute(self, arguments: ExtractLegalReferencesInput, context: dict[str, Any]) -> dict[str, object]:
        text = arguments.text
        if arguments.path is not None:
            text = parse_document(
                arguments.path, allowed_root=context.get("document_root", Path.cwd())
            ).text
        references = extract_legal_references(text or "")
        return {"references": references, "count": len(references), "verified": False}


tool = ExtractLegalReferences()

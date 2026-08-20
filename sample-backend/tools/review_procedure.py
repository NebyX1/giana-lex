from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator

from documents.parsers import parse_document
from documents.resolution import parse_resolution
from .base import Tool


class ReviewProcedureInput(BaseModel):
    text: str | None = Field(default=None, max_length=2_000_000)
    path: str | None = Field(default=None, max_length=4096)

    @model_validator(mode="after")
    def one_source(self):
        if (self.text is None) == (self.path is None):
            raise ValueError("Indique exactamente uno de: text o path.")
        return self


class ReviewProcedure(Tool[ReviewProcedureInput]):
    name = "review_procedure"
    description = "Revisa presencia estructural basica sin afirmar cumplimiento procedimental o legal."
    input_schema = ReviewProcedureInput

    def execute(self, arguments: ReviewProcedureInput, context: dict[str, Any]) -> dict[str, object]:
        text = arguments.text
        if arguments.path is not None:
            text = parse_document(
                arguments.path, allowed_root=context.get("document_root", Path.cwd())
            ).text
        resolution = parse_resolution(text or "")
        checks = [
            {"item": "visto", "status": "PRESENTE" if resolution["seen"] else "NO DETECTADO"},
            {"item": "considerandos", "status": "PRESENTE" if resolution["considerations"] else "NO DETECTADO"},
            {"item": "articulos", "status": "PRESENTE" if resolution["articles"] else "NO DETECTADO"},
            {"item": "firmas", "status": "PRESENTE" if resolution["signatures"] else "NO DETECTADO"},
        ]
        return {
            "checks": checks,
            "assessment": "REVISION ESTRUCTURAL SOLAMENTE",
            "warning": "No se evaluaron plazos, competencia, notificaciones, vigencia ni reglas juridicas.",
        }


tool = ReviewProcedure()

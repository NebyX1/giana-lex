from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator

from documents.parsers import parse_document
from .base import Tool


class ReadDocumentInput(BaseModel):
    path: str | None = Field(default=None, min_length=1, max_length=4096)
    document_id: int | None = Field(default=None, gt=0)
    max_bytes: int = Field(default=20 * 1024 * 1024, gt=0, le=100 * 1024 * 1024)

    @model_validator(mode="after")
    def require_document(self):
        if (self.path is None) == (self.document_id is None):
            raise ValueError("Indique path o document_id, pero no ambos.")
        return self


class ReadDocument(Tool[ReadDocumentInput]):
    name = "read_document"
    description = "Lee y normaliza de forma segura un archivo TXT, MD, PDF o DOCX."
    input_schema = ReadDocumentInput

    def execute(self, arguments: ReadDocumentInput, context: dict[str, Any]) -> dict[str, object]:
        root = context.get("document_root", Path.cwd())
        path = arguments.path
        if arguments.document_id is not None:
            path = (context.get("documents") or {}).get(arguments.document_id)
            if path is None:
                raise ValueError("El documento no pertenece a la sesion o no existe.")
        return parse_document(path, allowed_root=root, max_bytes=arguments.max_bytes).to_dict()


tool = ReadDocument()

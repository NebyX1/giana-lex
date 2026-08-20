from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from documents.parsers import parse_document
from moldes.loader import MOLDS_ROOT, load_mold
from .base import Tool
from .compare_documents import compare_texts
from .load_mold import MoldPath


class CompareWithMoldInput(BaseModel):
    document_path: str = Field(min_length=1, max_length=4096)
    mold_path: MoldPath = Field(description="Nombre exacto del molde contra el cual comparar.")
    max_changes: int = Field(default=200, ge=1, le=1000)


class CompareWithMold(Tool[CompareWithMoldInput]):
    name = "compare_with_mold"
    description = "Compara un documento con un molde editable sin declarar cumplimiento juridico."
    input_schema = CompareWithMoldInput

    def execute(self, arguments: CompareWithMoldInput, context: dict[str, Any]) -> dict[str, object]:
        document = parse_document(
            arguments.document_path, allowed_root=context.get("document_root", Path.cwd())
        )
        mold = load_mold(arguments.mold_path, context.get("molds_root", MOLDS_ROOT))
        result = compare_texts(document.text, str(mold["content"]), arguments.max_changes)
        result.update({
            "mold_status": mold["legal_status"],
            "warning": "Las diferencias son textuales y no determinan validez ni cumplimiento juridico.",
        })
        return result


tool = CompareWithMold()

from __future__ import annotations

import difflib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from documents.parsers import normalize_text, parse_document
from .base import Tool


class CompareDocumentsInput(BaseModel):
    left_path: str = Field(min_length=1, max_length=4096)
    right_path: str = Field(min_length=1, max_length=4096)
    max_changes: int = Field(default=200, ge=1, le=1000)


def compare_texts(left: str, right: str, max_changes: int = 200) -> dict[str, object]:
    left_lines = normalize_text(left).splitlines()
    right_lines = normalize_text(right).splitlines()
    matcher = difflib.SequenceMatcher(None, left_lines, right_lines, autojunk=False)
    changes = []
    total = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        total += 1
        if len(changes) < max_changes:
            changes.append({
                "type": tag,
                "left_lines": [i1 + 1, i2],
                "right_lines": [j1 + 1, j2],
                "left": left_lines[i1:i2],
                "right": right_lines[j1:j2],
            })
    return {
        "identical": not total,
        "similarity": round(matcher.ratio(), 4),
        "change_blocks": changes,
        "total_change_blocks": total,
        "truncated": total > len(changes),
        "legal_assessment": "NO REALIZADA",
    }


class CompareDocuments(Tool[CompareDocumentsInput]):
    name = "compare_documents"
    description = "Compara texto de dos documentos sin inferir equivalencia o efecto juridico."
    input_schema = CompareDocumentsInput

    def execute(self, arguments: CompareDocumentsInput, context: dict[str, Any]) -> dict[str, object]:
        root = context.get("document_root", Path.cwd())
        left = parse_document(arguments.left_path, allowed_root=root).text
        right = parse_document(arguments.right_path, allowed_root=root).text
        return compare_texts(left, right, arguments.max_changes)


tool = CompareDocuments()

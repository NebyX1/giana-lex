from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from tools.base import Tool

from .retriever import LegalRetriever, get_default_retriever


class LegalSearchInput(BaseModel):
    query: str
    top_k: int = 5
    category: str | None = None
    document_type: str | None = None
    year: int | None = None
    case_id: str | None = None
    source_class: str | None = None

    def model_post_init(self, __context: Any) -> None:
        if not 2 <= len(self.query.strip()) <= 2000:
            raise ValueError("query must contain between 2 and 2000 characters")
        if not 1 <= self.top_k <= 20:
            raise ValueError("top_k must be between 1 and 20")
        if self.category is not None and len(self.category) > 100:
            raise ValueError("category cannot exceed 100 characters")
        if self.document_type is not None and len(self.document_type) > 100:
            raise ValueError("document_type cannot exceed 100 characters")
        if self.year is not None and not 1800 <= self.year <= 2200:
            raise ValueError("year must be between 1800 and 2200")
        if self.case_id is not None and len(self.case_id) > 100:
            raise ValueError("case_id cannot exceed 100 characters")
        if self.source_class is not None and len(self.source_class) > 100:
            raise ValueError("source_class cannot exceed 100 characters")


class LegalSearchTool(Tool[LegalSearchInput]):
    input_schema = LegalSearchInput

    def __init__(
        self,
        name: str,
        description: str,
        corpus: str,
        fixed_category: str | None = None,
        retriever: LegalRetriever | None = None,
    ):
        self.name = name
        self.description = description
        self.corpus = corpus
        self.fixed_category = fixed_category
        self.retriever = retriever

    def execute(self, arguments: LegalSearchInput, context: dict[str, Any]) -> list[dict[str, Any]]:
        retriever = self.retriever or context.get("legal_retriever") or get_default_retriever()
        return retriever.search(
            query=arguments.query,
            corpus=self.corpus,
            top_k=arguments.top_k,
            category=self.fixed_category or arguments.category,
            document_type=arguments.document_type,
            year=arguments.year,
            case_id=arguments.case_id,
            source_class=arguments.source_class,
        )

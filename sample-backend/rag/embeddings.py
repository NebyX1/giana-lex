from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Protocol

from .constants import DEFAULT_VECTOR_SIZE, embedding_model


class Embedder(Protocol):
    @property
    def vector_size(self) -> int: ...

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class FastEmbedder:
    """Lazy FastEmbed adapter; constructing the module never downloads a model."""

    def __init__(self, model_name: str | None = None, vector_size: int = DEFAULT_VECTOR_SIZE):
        self.model_name = model_name or embedding_model()
        self._vector_size = vector_size
        self._model = None

    @property
    def vector_size(self) -> int:
        return self._vector_size

    def _get_model(self):
        if self._model is None:
            try:
                from fastembed import TextEmbedding
            except ImportError as exc:
                raise RuntimeError(
                    "FastEmbed is required for real RAG use. Install the 'fastembed' package."
                ) from exc
            self._model = TextEmbedding(model_name=self.model_name)
        return self._model

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        safe_texts = [text.strip() or " " for text in texts]
        if not safe_texts:
            return []
        vectors: Iterable = self._get_model().embed(safe_texts)
        result = [vector.tolist() if hasattr(vector, "tolist") else list(vector) for vector in vectors]
        if result:
            self._vector_size = len(result[0])
        return result

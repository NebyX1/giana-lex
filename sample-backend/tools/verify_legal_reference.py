from __future__ import annotations

import inspect
import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from .base import Tool


VerificationStatus = Literal["VERIFICADA", "NO ENCONTRADA", "AMBIGUA"]


class VerifyLegalReferenceInput(BaseModel):
    reference: str = Field(min_length=3, max_length=500)
    jurisdiction: str | None = Field(default=None, max_length=200)
    limit: int = Field(default=5, ge=1, le=20)


def _normalized(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.casefold()))


def _call_rag(service: Any, query: str, limit: int) -> Any:
    if hasattr(service, "search") and "corpus" in inspect.signature(service.search).parameters:
        return [
            *service.search(query=query, corpus="departamental", top_k=limit),
            *service.search(query=query, corpus="nacional", top_k=limit),
        ]
    method = next((getattr(service, name, None) for name in ("search", "retrieve", "query") if callable(getattr(service, name, None))), None)
    if method is None and callable(service):
        method = service
    if method is None:
        raise TypeError("El servicio RAG no expone search, retrieve, query ni __call__.")
    parameters = inspect.signature(method).parameters
    return method(query, limit=limit) if "limit" in parameters else method(query)


def _items(result: Any) -> list[Any]:
    if result is None:
        return []
    if isinstance(result, dict):
        for key in ("results", "documents", "matches", "items"):
            if isinstance(result.get(key), list):
                return result[key]
        return [result]
    return result if isinstance(result, list) else list(result) if isinstance(result, tuple) else [result]


def verify_reference(reference: str, service: Any, limit: int = 5) -> dict[str, Any]:
    if service is None:
        return {
            "status": "NO ENCONTRADA",
            "reference": reference,
            "reason": "No hay servicio RAG juridico disponible; la referencia no fue verificada.",
            "evidence": [],
        }
    try:
        raw_items = _items(_call_rag(service, reference, limit))
    except Exception as exc:
        return {
            "status": "NO ENCONTRADA",
            "reference": reference,
            "reason": f"Fallo la consulta al servicio RAG: {exc}",
            "evidence": [],
        }

    query_tokens = _normalized(reference)
    evidence = []
    for item in raw_items:
        if isinstance(item, dict):
            label = str(item.get("title") or item.get("citation") or item.get("text") or "")
            score = item.get("score")
            source = item.get("source") or item.get("url") or item.get("id")
        else:
            label, score, source = str(item), None, None
        overlap = len(query_tokens & _normalized(label)) / max(len(query_tokens), 1)
        if overlap >= 0.6:
            evidence.append({"label": label[:1000], "source": source, "score": score, "overlap": round(overlap, 3)})

    exact = [item for item in evidence if item["overlap"] >= 0.9]
    if len(exact) == 1:
        status: VerificationStatus = "VERIFICADA"
        reason = "Se encontro una coincidencia suficientemente especifica en el servicio RAG."
    elif len(evidence) > 1 or len(exact) > 1:
        status = "AMBIGUA"
        reason = "Se encontraron varias coincidencias plausibles; requiere desambiguacion."
    elif evidence:
        status = "AMBIGUA"
        reason = "La coincidencia es parcial; requiere revision de la fuente."
    else:
        status = "NO ENCONTRADA"
        reason = "El servicio RAG no devolvio una coincidencia suficientemente especifica."
    return {"status": status, "reference": reference, "reason": reason, "evidence": evidence}


class VerifyLegalReference(Tool[VerifyLegalReferenceInput]):
    name = "verify_legal_reference"
    description = "Contrasta una referencia con un servicio RAG disponible y devuelve un estado conservador."
    input_schema = VerifyLegalReferenceInput

    def execute(self, arguments: VerifyLegalReferenceInput, context: dict[str, Any]) -> dict[str, Any]:
        service = context.get("rag_service") or context.get("legal_rag") or context.get("legal_retriever")
        query = arguments.reference
        if arguments.jurisdiction:
            query = f"{query} ({arguments.jurisdiction})"
        result = verify_reference(query, service, arguments.limit)
        result["requested_reference"] = arguments.reference
        return result


tool = VerifyLegalReference()

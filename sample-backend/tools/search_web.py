from typing import Any

import httpx
from flask import current_app
from pydantic import BaseModel, Field

from .base import Tool


class SearchWebInput(BaseModel):
    query: str = Field(min_length=2, max_length=1000)
    limit: int = Field(default=5, ge=1, le=10)


class SearchWeb(Tool[SearchWebInput]):
    name = "search_web"
    description = "Busca informacion externa mediante un proveedor web configurado; los resultados no son autoridad juridica."
    input_schema = SearchWebInput

    def execute(self, arguments: SearchWebInput, context: dict[str, Any]) -> dict[str, Any]:
        endpoint = current_app.config.get("WEB_SEARCH_URL", "")
        if not endpoint:
            return {"results": [], "status": "not_configured", "warning": "La busqueda web no esta configurada."}
        headers = {"Accept": "application/json"}
        api_key = current_app.config.get("WEB_SEARCH_API_KEY")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        response = httpx.get(
            endpoint,
            params={"q": arguments.query, "limit": arguments.limit},
            headers=headers,
            follow_redirects=False,
            timeout=current_app.config["PROVIDER_CONNECT_TIMEOUT"],
        )
        response.raise_for_status()
        payload = response.json()
        raw_results = payload.get("results", []) if isinstance(payload, dict) else []
        results = []
        for item in raw_results[: arguments.limit]:
            if not isinstance(item, dict):
                continue
            results.append({
                "title": str(item.get("title", ""))[:500],
                "url": str(item.get("url", ""))[:2000],
                "snippet": str(item.get("snippet", item.get("description", "")))[:3000],
                "category": "web",
                "source_type": "WEB_UNTRUSTED_DATA",
            })
        return {"results": results, "warning": "Contenido web no confiable; verificar con fuentes oficiales."}


tool = SearchWeb()

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any

import httpx

from .url import CanonicalUrl, IMPO_HOME


IMPO_USER_AGENT = "Giana-Lex/1.0 (juridico@lavalleja.gub.uy; +https://impo.com.uy/datos-abiertos)"
IMPO_TIMEOUT = httpx.Timeout(connect=15.0, read=60.0, write=15.0, pool=15.0)
IMPO_MAX_BYTES = 60 * 1024 * 1024
IMPO_MAX_RETRIES = 3
IMPO_BACKOFF_SECONDS = 1.5


class ImpoDownloadError(ValueError):
    pass


@dataclass(frozen=True)
class ImpoDownload:
    data: dict[str, Any]
    raw_bytes: bytes
    checksum: str
    url: str
    json_url: str

    @property
    def tipo(self) -> str:
        return str(self.data.get("tipoNorma") or "").strip()

    @property
    def numero(self) -> str:
        return str(self.data.get("nroNorma") or "").strip()

    @property
    def anio(self) -> str:
        return str(self.data.get("anioNorma") or "").strip()

    @property
    def nombre(self) -> str:
        return str(self.data.get("nombreNorma") or "").strip()

    @property
    def articulos(self) -> list[dict[str, Any]]:
        value = self.data.get("articulos")
        return value if isinstance(value, list) else []


def _decode_impo_bytes(raw: bytes) -> dict[str, Any]:
    text = raw.decode("iso-8859-1")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            return json.loads(text, strict=False)
        except json.JSONDecodeError as exc:
            raise ImpoDownloadError(f"JSON invalido recibido desde IMPO: {exc}") from exc


def _validate_impo_data(data: dict[str, Any]) -> None:
    if not isinstance(data, dict):
        raise ImpoDownloadError("La respuesta no es un objeto JSON")
    tipo = data.get("tipoNorma")
    if not tipo:
        raise ImpoDownloadError(
            "La norma no contiene tipoNorma; no es una norma valida."
        )
    articulos = data.get("articulos")
    if articulos is not None and not isinstance(articulos, list):
        raise ImpoDownloadError("El campo 'articulos' debe ser una lista cuando esta presente.")
    if articulos is not None and len(articulos) == 0:
        raise ImpoDownloadError("La norma no contiene articulos.")
    nro = data.get("nroNorma")
    anio = data.get("anioNorma")
    if not nro or not anio:
        from .identity import _strip_accents
        constitucion = "constitucion" in _strip_accents(str(tipo).lower())
        if not constitucion:
            raise ImpoDownloadError(
                "La norma no contiene tipoNorma/nroNorma/anioNorma; no es una norma valida."
            )


def download_norma(
    canonical: CanonicalUrl,
    *,
    client: httpx.Client | None = None,
    max_retries: int = IMPO_MAX_RETRIES,
    backoff: float = IMPO_BACKOFF_SECONDS,
) -> ImpoDownload:
    headers = {"User-Agent": IMPO_USER_AGENT, "Accept": "application/json"}
    raw_bytes = None
    last_error: Exception | None = None
    from urllib.parse import urlparse
    from .url import check_impo_ip_safety
    check_impo_ip_safety(urlparse(canonical.json_url).hostname or "")
    for attempt in range(1, max_retries + 1):
        try:
            if client is None:
                response = httpx.get(
                    canonical.json_url,
                    headers=headers,
                    timeout=IMPO_TIMEOUT,
                    follow_redirects=False,
                )
            else:
                response = client.get(canonical.json_url, headers=headers)
            if response.status_code == 404:
                raise ImpoDownloadError(
                    f"IMPO devolvio 404 para {canonical.canonical}. La norma no existe o cambio de ubicacion."
                )
            if response.status_code >= 400:
                raise ImpoDownloadError(
                    f"IMPO devolvio HTTP {response.status_code} para {canonical.canonical}."
                )
            if response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get("location", "")
                raise ImpoDownloadError(
                    f"IMPO intento redirigir a {location}. Redirecciones no permitidas por seguridad."
                )
            raw_bytes = response.content
            if len(raw_bytes) > IMPO_MAX_BYTES:
                raise ImpoDownloadError(
                    f"Respuesta excede el limite de {IMPO_MAX_BYTES // (1024 * 1024)} MB."
                )
            data = _decode_impo_bytes(raw_bytes)
            _validate_impo_data(data)
            checksum = hashlib.sha256(raw_bytes).hexdigest()
            return ImpoDownload(
                data=data,
                raw_bytes=raw_bytes,
                checksum=checksum,
                url=canonical.canonical,
                json_url=canonical.json_url,
            )
        except ImpoDownloadError:
            raise
        except httpx.TimeoutException as exc:
            last_error = exc
            if attempt < max_retries:
                time.sleep(backoff * attempt)
            continue
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt < max_retries:
                time.sleep(backoff * attempt)
            continue
    raise ImpoDownloadError(
        f"No se pudo descargar la norma desde IMPO tras {max_retries} intentos: {last_error}"
    )


def build_impo_client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": IMPO_USER_AGENT},
        timeout=IMPO_TIMEOUT,
        follow_redirects=False,
    )


def is_impo_reachable() -> bool:
    try:
        httpx.head(IMPO_HOME, timeout=httpx.Timeout(connect=5.0), follow_redirects=False)
        return True
    except httpx.HTTPError:
        return False
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Any

import httpx

from .url import is_redirect_allowed, validate_depto_url

from impo.client import IMPO_MAX_BYTES  # reuse the same size cap


DEPT_UA = "Giana-Lex/1.0 (juridico@lavalleja.gub.uy; digesto departamental Lavalleja)"
TIMEOUT = httpx.Timeout(connect=15.0, read=90.0, write=20.0, pool=20.0)
MAX_RETRIES = 3
BACKOFF = 1.5
MAX_BYTES = 60 * 1024 * 1024


class DeptoDownloadError(ValueError):
    pass


@dataclass
class DownloadedSource:
    url: str
    final_url: str
    content_type: str
    raw: bytes
    encoding: str | None

    @property
    def checksum(self) -> str:
        return hashlib.sha256(self.raw).hexdigest()

    @property
    def is_pdf(self) -> bool:
        ct = self.content_type.lower()
        return "pdf" in ct or self.raw[:5] == b"%PDF-"

    @property
    def is_html(self) -> bool:
        ct = self.content_type.lower()
        return "html" in ct or self.raw.lstrip().startswith((b"<!doctype", b"<html", b"<!DOCTYPE"))


def download_source(
    raw_url: str,
    *,
    client: httpx.Client | None = None,
    max_retries: int = MAX_RETRIES,
    backoff: float = BACKOFF,
) -> DownloadedSource:
    url = validate_depto_url(raw_url)
    headers = {"User-Agent": DEPT_UA, "Accept": "application/pdf,text/html,application/json,text/plain,*/*"}
    last_error: Exception | None = None
    current = url
    from urllib.parse import urlparse
    from .url import check_depto_ip_safety
    check_depto_ip_safety(urlparse(url).hostname or "")
    for attempt in range(1, max_retries + 1):
        try:
            if client is None:
                response = httpx.get(current, headers=headers, timeout=TIMEOUT, follow_redirects=False)
            else:
                response = client.get(current, headers=headers)
            if response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get("location", "")
                if not is_redirect_allowed(location):
                    raise DeptoDownloadError(
                        f"Redireccion a host no autorizado bloqueada: {location}"
                    )
                from urllib.parse import urljoin
                current = urljoin(current, location)
                continue
            if response.status_code == 404:
                raise DeptoDownloadError(f"Fuente no encontrada (HTTP 404): {current}")
            if response.status_code >= 400:
                raise DeptoDownloadError(f"HTTP {response.status_code} para {current}")
            raw = response.content
            if len(raw) > MAX_BYTES:
                raise DeptoDownloadError(f"Respuesta excede el limite de {MAX_BYTES // (1024 * 1024)} MB")
            content_type = response.headers.get("content-type", "")
            return DownloadedSource(
                url=current,
                final_url=current,
                content_type=content_type,
                raw=raw,
                encoding=response.encoding,
            )
        except DeptoDownloadError:
            raise
        except (httpx.TimeoutException, httpx.HTTPError) as exc:
            last_error = exc
            if attempt < max_retries:
                time.sleep(backoff * attempt)
            continue
    raise DeptoDownloadError(
        f"No se pudo descargar la fuente tras {max_retries} intentos: {last_error}"
    )


def build_depto_client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": DEPT_UA},
        timeout=TIMEOUT,
        follow_redirects=False,
    )
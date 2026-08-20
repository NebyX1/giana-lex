from __future__ import annotations

import logging
import re
import time
from urllib.parse import urljoin

import requests
from lxml import html

from .parser import LavallejaResolutionParser, normalize_resolution_number, parse_date, validate_official_resolution_url


LOGGER = logging.getLogger(__name__)
CATALOG_URL = "https://www.gub.uy/intendencia-lavalleja/institucional/normativa"


class LavallejaResolutionImporter:
    def __init__(self, timeout: float = 20, retries: int = 2, rate_limit_seconds: float = 0.45, session=None):
        self.timeout = timeout
        self.retries = retries
        self.rate_limit_seconds = rate_limit_seconds
        self.session = session or requests.Session()
        self.session.headers.update({
            "User-Agent": "Giana-Lex-Legal-Knowledge/1.0 (+administrative research; respectful crawler)",
            "Accept": "text/html,application/xhtml+xml",
        })
        self.parser = LavallejaResolutionParser()
        self._last_request = 0.0

    @staticmethod
    def derived_url(resolution_number: str) -> str:
        normalized = normalize_resolution_number(resolution_number)
        if not normalized:
            raise ValueError("Número de resolución inválido")
        return f"{CATALOG_URL}/resolucion-n-{normalized}"

    def _wait_rate_limit(self):
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.rate_limit_seconds:
            time.sleep(self.rate_limit_seconds - elapsed)

    def fetch(self, url: str) -> str:
        current = validate_official_resolution_url(url)
        last_error = None
        for attempt in range(self.retries + 1):
            try:
                for _redirect in range(4):
                    self._wait_rate_limit()
                    response = self.session.get(current, timeout=self.timeout, allow_redirects=False, stream=True)
                    self._last_request = time.monotonic()
                    if response.is_redirect or response.is_permanent_redirect:
                        current = validate_official_resolution_url(urljoin(current, response.headers["Location"]))
                        continue
                    response.raise_for_status()
                    content_type = response.headers.get("Content-Type", "")
                    if "text/html" not in content_type:
                        raise ValueError("La fuente oficial no devolvió HTML")
                    chunks = []
                    total = 0
                    for chunk in response.iter_content(64 * 1024):
                        total += len(chunk)
                        if total > 5 * 1024 * 1024:
                            raise ValueError("La página oficial excede el límite de 5 MB")
                        chunks.append(chunk)
                    response.encoding = response.encoding or "utf-8"
                    return b"".join(chunks).decode(response.encoding, errors="replace")
                raise ValueError("La fuente oficial redirigió demasiadas veces")
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(min(2 ** attempt, 4))
        raise RuntimeError(f"No se pudo descargar la resolución: {last_error}") from last_error

    def parse_url(self, url: str):
        validated = validate_official_resolution_url(url)
        LOGGER.info("resolution_import_started url=%s", validated)
        source = self.fetch(validated)
        parsed = self.parser.parse(validated, source)
        LOGGER.info("resolution_import_completed number=%s", parsed.resolution_number)
        return parsed

    def resolve_number(self, resolution_number: str, catalog_lookup=None):
        requested = normalize_resolution_number(resolution_number)
        derived = self.derived_url(resolution_number)
        try:
            parsed = self.parse_url(derived)
            if parsed.resolution_number_normalized != requested:
                raise ValueError(
                    f"La ficha obtenida corresponde a {parsed.resolution_number}, no a {resolution_number}"
                )
            return parsed
        except Exception as derived_error:
            if catalog_lookup:
                fallback = catalog_lookup(requested)
                if fallback and fallback != derived:
                    parsed = self.parse_url(fallback)
                    if parsed.resolution_number_normalized == requested:
                        return parsed
            raise derived_error

    def crawl_catalog(self, start_page=0, max_pages=1):
        for page in range(start_page, start_page + max_pages):
            source = self.fetch(f"{CATALOG_URL}?page={page}")
            document = html.fromstring(source)
            rows = document.xpath("//li[contains(concat(' ', normalize-space(@class), ' '), ' Media ')]")
            if not rows:
                break
            for row in rows:
                links = row.xpath(".//a[@rel='bookmark']")
                if not links:
                    continue
                link = links[0]
                title = " ".join(link.xpath(".//text()")).strip()
                number_match = re.search(r"[\d.]+/\d{2,4}", title)
                if not number_match:
                    continue
                summary = " ".join(row.xpath(".//p//text()")).strip()
                published = " ".join(row.xpath(".//*[contains(@class,'Box-info')]//text()")).strip()
                yield {
                    "resolution_number": number_match.group(0),
                    "resolution_number_normalized": normalize_resolution_number(number_match.group(0)),
                    "title": title,
                    "summary": summary,
                    "publication_date": parse_date(published),
                    "detail_url": urljoin(CATALOG_URL, link.get("href")),
                }

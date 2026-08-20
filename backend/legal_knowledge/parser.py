from __future__ import annotations

import hashlib
import ipaddress
import re
import socket
import unicodedata
from datetime import datetime
from urllib.parse import urlparse

from lxml import html

from .schemas import ParsedResolution


NUMBER_PATTERN = re.compile(r"(?:resoluci[oó]n\s*(?:n[°ºo]\.?\s*)?)?([\d.]+\s*/\s*\d{2,4})", re.I)
SECTION_PATTERN = re.compile(r"^(VISTO|RESULTANDOS?|CONSIDERANDOS?|ATENTO|RESUELVE)\s*:?[\s-]*(.*)$", re.I)
ORDINAL_PATTERN = re.compile(r"^(?:[IVXLCDM]+\)|\d+[º°o]?\s*[.)-])\s*(.*)$", re.I)
SPANISH_MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}


def compact_space(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def normalize_resolution_number(value: str) -> str:
    match = NUMBER_PATTERN.search(value or "")
    if not match:
        return re.sub(r"\D", "", value or "")
    return re.sub(r"\D", "", match.group(1))


def display_resolution_number(value: str) -> str:
    match = NUMBER_PATTERN.search(value or "")
    return compact_space(match.group(1)).replace(" ", "") if match else compact_space(value)


def number_parts(value: str) -> tuple[int | None, str | None, int | None]:
    displayed = display_resolution_number(value)
    if "/" not in displayed:
        return None, None, None
    main, year_code = displayed.split("/", 1)
    try:
        main_number = int(main.replace(".", ""))
    except ValueError:
        main_number = None
    digits = re.sub(r"\D", "", year_code)
    year = None
    if digits:
        number = int(digits)
        year = 2000 + number if len(digits) <= 3 else number
    return main_number, digits or None, year


def parse_date(value: str):
    value = compact_space(value).lower()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    match = re.search(r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})", value)
    if match:
        month = SPANISH_MONTHS.get(match.group(2))
        if month:
            return datetime(int(match.group(3)), month, int(match.group(1))).date()
    return None


def _plain(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char)).lower()


class LavallejaResolutionParser:
    def parse(self, source_url: str, source_html: str) -> ParsedResolution:
        document = html.fromstring(source_html)
        article = document.xpath("//article//*[contains(concat(' ', normalize-space(@class), ' '), ' Page-document ')]")
        if not article:
            article = document.xpath("//article")
        if not article:
            raise ValueError("La página oficial no contiene una ficha de normativa reconocible")
        root = article[0]
        heading = compact_space(" ".join(root.xpath(".//h1[1]//text() | .//h2[1]//text()")))
        number_match = NUMBER_PATTERN.search(heading)
        if not number_match:
            raise ValueError("No se encontró el número de resolución en el encabezado oficial")
        resolution_number = display_resolution_number(number_match.group(1))
        main_number, year_code, year = number_parts(resolution_number)
        summary = compact_space(" ".join(root.xpath(".//*[contains(@class,'Page-description')]//text()")))
        publication_text = compact_space(" ".join(root.xpath(".//*[contains(@class,'Page-date')][1]//text()")))
        publication_date = parse_date(publication_text)

        paragraphs = []
        for element in root.xpath(".//p | .//li"):
            text = compact_space(" ".join(element.xpath(".//text()")))
            if text:
                paragraphs.append(text)
        if not paragraphs:
            raise ValueError("La ficha oficial no contiene texto de resolución")

        resolution_date = next((parse_date(text) for text in paragraphs[:4] if parse_date(text)), None)
        sections = {"visto": [], "resultandos": [], "considerandos": [], "atento": [], "resuelve": []}
        current = None
        firmantes = []
        for paragraph in paragraphs:
            match = SECTION_PATTERN.match(paragraph)
            if match:
                label = _plain(match.group(1))
                current = "visto" if label == "visto" else "resultandos" if label.startswith("resultando") else "considerandos" if label.startswith("considerando") else "atento" if label == "atento" else "resuelve"
                remainder = compact_space(match.group(2))
                if remainder:
                    sections[current].append(remainder)
                continue
            ordinal = ORDINAL_PATTERN.match(paragraph)
            if current in {"resultandos", "considerandos", "resuelve"} and ordinal:
                sections[current].append(paragraph)
                continue
            if current and current != "resuelve":
                sections[current].append(paragraph)
            elif current == "resuelve" and ordinal:
                sections[current].append(paragraph)
            elif current == "resuelve" and len(paragraph) < 120:
                firmantes.append(paragraph)

        normalized_lines = [f"Resolución N° {resolution_number}", summary]
        for key, title in (("visto", "VISTO"), ("resultandos", "RESULTANDO"), ("considerandos", "CONSIDERANDO"), ("atento", "ATENTO"), ("resuelve", "RESUELVE")):
            if sections[key]:
                normalized_lines.extend([title, *sections[key]])
        if firmantes:
            normalized_lines.extend(["FIRMANTES", *firmantes])
        normalized_text = "\n\n".join(line for line in normalized_lines if line)
        raw_text = "\n\n".join(paragraphs)
        source_hash = hashlib.sha256(source_html.encode("utf-8")).hexdigest()
        title = heading.rstrip(" .")
        return ParsedResolution(
            source_url=source_url,
            source_html=source_html,
            source_hash=source_hash,
            resolution_number=resolution_number,
            resolution_number_normalized=normalize_resolution_number(resolution_number),
            resolution_main_number=main_number,
            resolution_year_code=year_code,
            year=year,
            title=title,
            official_summary=summary,
            publication_date=publication_date,
            resolution_date=resolution_date,
            raw_text=raw_text,
            normalized_text=normalized_text,
            visto="\n".join(sections["visto"]),
            resultandos=sections["resultandos"],
            considerandos=sections["considerandos"],
            atento="\n".join(sections["atento"]),
            resuelve=sections["resuelve"],
            firmantes=firmantes,
            structured_sections={**sections, "firmantes": firmantes},
        )


def validate_official_resolution_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError("La fuente oficial debe utilizar HTTPS")
    if (parsed.hostname or "").lower() not in {"gub.uy", "www.gub.uy"}:
        raise ValueError("La fuente debe pertenecer a gub.uy")
    path = parsed.path.rstrip("/")
    prefix = "/intendencia-lavalleja/institucional/normativa"
    if not path.startswith(prefix):
        raise ValueError("La URL no pertenece a la normativa de la Intendencia de Lavalleja")
    if parsed.username or parsed.password or parsed.port not in {None, 443}:
        raise ValueError("La URL oficial contiene componentes no admitidos")
    for info in socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM):
        address = ipaddress.ip_address(info[4][0])
        if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved:
            raise ValueError("La fuente oficial resolvió a una red no permitida")
    return parsed._replace(fragment="").geturl()

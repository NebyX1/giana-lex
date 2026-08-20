from __future__ import annotations

import io
import re
from html.parser import HTMLParser
from typing import Any

from .download import DownloadedSource


SKIP_TAGS = {
    "script", "style", "nav", "footer", "header", "aside", "form",
    "button", "iframe", "noscript", "svg", "canvas", "template",
}
BLOCK_TAGS = {
    "p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6",
    "ul", "ol", "table", "section", "article", "blockquote", "pre",
}


class _BodyParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        # Count only nested elements whose own contents must be ignored.  The
        # previous implementation counted every element inside <header>/<nav>
        # and therefore got stuck when it met void tags such as <img> or
        # <input> (they have no closing tag).  From that point onward the real
        # document body was silently discarded.
        if tag in SKIP_TAGS:
            self._skip_depth += 1
        if tag in BLOCK_TAGS and not self._skip_depth:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
        if tag in BLOCK_TAGS and not self._skip_depth:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip_depth:
            self.parts.append(data)


def _clean_text(raw: str) -> str:
    raw = raw.replace("\u00a0", " ")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in raw.splitlines()]
    lines = [line for line in lines if line]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_html_text(source: DownloadedSource) -> str:
    raw = source.raw
    for enc in (source.encoding, "utf-8", "iso-8859-1", "latin-1"):
        try:
            html = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        html = raw.decode("utf-8", errors="replace")
    parser = _BodyParser()
    try:
        parser.feed(html)
    except Exception:
        return _clean_text(html)
    return _clean_text("".join(parser.parts))


def _pdf_text_extraction(raw: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise DeptoExtractionError("PDF requiere la libreria pypdf") from exc
    reader = PdfReader(io.BytesIO(raw))
    pages = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            pages.append("")
    return _clean_text("\n\n".join(pages))


class DeptoExtractionError(ValueError):
    pass


def pdf_text_quality(text: str) -> dict[str, Any]:
    """Assess whether extracted PDF text is usable or is a scanned image."""
    if not text or not text.strip():
        return {"usable": False, "reason": "empty", "chars": 0, "letters_ratio": 0.0}
    letters = sum(1 for ch in text if ch.isalpha())
    ratio = letters / max(1, len(text))
    return {
        "usable": letters >= 200 and ratio >= 0.5,
        "reason": "text" if (letters >= 200 and ratio >= 0.5) else "low_quality",
        "chars": len(text),
        "letters_ratio": round(ratio, 3),
    }


def extract_pdf_text(source: DownloadedSource) -> tuple[str, str]:
    """Return (text, extraction_method)."""
    text = _pdf_text_extraction(source.raw)
    quality = pdf_text_quality(text)
    if quality["usable"]:
        return text, "pdf_text"
    # Scanned/low-quality PDF. OCR is only used when no text alternative exists.
    try:
        return _ocr_pdf(source.raw), "ocr"
    except DeptoExtractionError:
        return text, "pdf_text"


def _ocr_pdf(raw: bytes) -> str:
    try:
        import fitz  # PyMuPDF
        import pytesseract
    except ImportError:
        raise DeptoExtractionError("OCR requiere pymupdf y pytesseract (no instalados)")
    doc = fitz.open(stream=raw, filetype="pdf")
    texts = []
    for page in doc:
        pix = page.get_pixmap(dpi=200)
        import io as _io
        img = _io.BytesIO(pix.tobytes("png"))
        texts.append(pytesseract.image_to_string(img, lang="spa"))
    return _clean_text("\n\n".join(texts))


def extract_text_from_source(source: DownloadedSource) -> tuple[str, str]:
    """Return (text, extraction_method)."""
    if source.is_pdf:
        return extract_pdf_text(source)
    if source.is_html:
        return extract_html_text(source), "html_text"
    # Fallback: try as plain text / JSON
    try:
        return source.raw.decode("utf-8", errors="replace"), "raw_text"
    except Exception:
        return source.raw.decode("latin-1", errors="replace"), "raw_text"


def extract_decree_from_official_minutes(text: str, number: str) -> str:
    """Extract one enacted decree from the text of an official session record.

    Historical individual PDFs published by the Junta are sometimes image-only,
    while the same decree is reproduced as searchable text in the official acta.
    This deliberately requires both the decree heading and the institutional
    enactment formula so a mere mention elsewhere in the minutes cannot be
    mistaken for the norm itself.
    """
    escaped_number = re.escape(str(number).strip())
    heading = re.compile(
        rf"(?im)^\s*DECRETO\s+N[\s.°ºo�]*{escaped_number}\s*[.]?\s*$"
    )
    end_marker = re.compile(r"(?m)^\s*\*{3,}(?:\s+\*{3,})*\s*$")

    for match in heading.finditer(text or ""):
        preamble = text[match.start():match.start() + 500]
        if not re.search(r"(?i)JUNTA\s+DEPARTAMENTAL\s+DE\s+LAVALLEJA", preamble):
            continue
        if not re.search(r"(?i)DECRETA\s*:", preamble):
            continue
        end = end_marker.search(text, match.end())
        if not end:
            continue
        section = text[match.start():end.start()]
        # Some older PDFs expose accented glyphs as U+FFFD. Dropping only that
        # unknown glyph preserves every known character and turns "Art�culo"
        # into the still unambiguous/searchable "Articulo".
        section = re.sub(r"(?i)art\ufffdculo", "Articulo", section)
        section = section.replace("\ufffd", "")
        return _clean_text(section)

    raise DeptoExtractionError(
        f"No se encontró una transcripción íntegra del Decreto {number} en el acta oficial"
    )


def extract_official_compilation_section(text: str, heading: str, following_heading: str) -> str:
    """Return one complete named section from an official multi-document PDF."""
    start = (text or "").find(heading)
    if start < 0:
        raise DeptoExtractionError(f"No se encontró la sección oficial: {heading}")
    end = text.find(following_heading, start + len(heading))
    if end < 0:
        raise DeptoExtractionError(
            f"No se encontró el límite posterior de la sección oficial: {following_heading}"
        )
    section = _clean_text(text[start:end])
    if len(section) < 500:
        raise DeptoExtractionError(f"La sección oficial {heading} está incompleta")
    return section


def extract_official_document_body(text: str, body_start_pattern: str) -> str:
    """Remove covers and a table of contents before the enacted document body."""
    match = re.search(body_start_pattern, text or "")
    if not match:
        raise DeptoExtractionError("No se encontró el inicio del cuerpo normativo oficial")
    body = _clean_text(text[match.start():])
    if len(body) < 500:
        raise DeptoExtractionError("El cuerpo normativo oficial está incompleto")
    return body

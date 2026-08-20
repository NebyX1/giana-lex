from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from impo.identity import norm_category_for_tipo, norm_dir_for_tipo


_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t]+")
_MULTI_NEWLINE = re.compile(r"\n{3,}")


def strip_html(value: str | None) -> str:
    if not value:
        return ""
    text = _TAG.sub("", value)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    text = text.replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&quot;", '"').replace("&#39;", "'")
    text = _WS.sub(" ", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    text = _MULTI_NEWLINE.sub("\n\n", text)
    return text.strip()


def _clean(value: Any) -> str:
    return strip_html(str(value or "")).strip()


@dataclass
class NormalizedArticle:
    number: str
    title: str
    text: str
    notes: str
    references: str
    indexation: str
    url: str
    section: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "nroArticulo": self.number,
            "secArticulo": self.section,
            "tituloArticulo": self.title,
            "textoArticulo": self.text,
            "notasArticulo": self.notes,
            "referenciasAlArticulo": self.references,
            "indexacionArticulo": self.indexation,
            "urlArticulo": self.url,
        }


@dataclass
class NormalizedNorma:
    tipo: str
    numero: str
    anio: str
    nombre: str
    leyenda: str
    fecha_promulgacion: str
    fecha_publicacion: str
    vistos: str
    referencias: str
    indexacion: str
    articulos: list[NormalizedArticle] = field(default_factory=list)
    canonical_url: str = ""
    json_url: str = ""
    norma_id: str = ""
    category: str = ""
    directory: str = ""
    title: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "tipo": self.tipo,
            "numero": self.numero,
            "anio": self.anio,
            "nombre": self.nombre,
            "leyenda": self.leyenda,
            "fechaPromulgacion": self.fecha_promulgacion,
            "fechaPublicacion": self.fecha_publicacion,
            "vistos": self.vistos,
            "referenciasNorma": self.referencias,
            "indexacionNorma": self.indexacion,
            "articulos": [article.to_dict() for article in self.articulos],
            "canonical_url": self.canonical_url,
            "json_url": self.json_url,
            "norma_id": self.norma_id,
            "category": self.category,
            "directory": self.directory,
            "title": self.title,
            "article_count": len(self.articulos),
        }


def normalize_impo_data(
    data: dict[str, Any],
    canonical_url: str,
    json_url: str,
    norma_id: str,
) -> NormalizedNorma:
    tipo = str(data.get("tipoNorma") or "").strip()
    numero = str(data.get("nroNorma") or "").strip()
    anio = str(data.get("anioNorma") or "").strip()
    nombre = str(data.get("nombreNorma") or "").strip()
    leyenda = _clean(data.get("leyenda"))
    fecha_promulgacion = str(data.get("fechaPromulgacion") or "").strip()
    fecha_publicacion = str(data.get("fechaPublicacion") or "").strip()
    vistos = _clean(data.get("vistos"))
    referencias = _clean(data.get("referenciasNorma"))
    indexacion = _clean(data.get("indexacionNorma"))

    raw_articles = data.get("articulos") or []
    articles: list[NormalizedArticle] = []
    for raw in raw_articles:
        if not isinstance(raw, dict):
            continue
        number = str(raw.get("nroArticulo") or "").strip()
        section = str(raw.get("secArticulo") or "").strip()
        title = _clean(raw.get("tituloArticulo") or raw.get("titulosArticulo"))
        text = _clean(raw.get("textoArticulo"))
        notes = _clean(raw.get("notasArticulo") or raw.get("notasDelArticulo"))
        references = _clean(raw.get("referenciasAlArticulo"))
        indexation = _clean(raw.get("indexacionArticulo"))
        url = str(raw.get("urlArticulo") or "").strip()
        if url and url.startswith("/"):
            url = f"https://www.impo.com.uy{url}"
        if not text and not title:
            continue
        articles.append(
            NormalizedArticle(
                number=number,
                title=title,
                text=text,
                notes=notes,
                references=references,
                indexation=indexation,
                url=url,
                section=section,
            )
        )

    category = norm_category_for_tipo(tipo)
    directory = norm_dir_for_tipo(tipo)
    if nombre:
        title = nombre
    elif numero and anio:
        title = f"{tipo} {numero}/{anio}"
    else:
        title = tipo
    return NormalizedNorma(
        tipo=tipo,
        numero=numero,
        anio=anio,
        nombre=nombre,
        leyenda=leyenda,
        fecha_promulgacion=fecha_promulgacion,
        fecha_publicacion=fecha_publicacion,
        vistos=vistos,
        referencias=referencias,
        indexacion=indexacion,
        articulos=articles,
        canonical_url=canonical_url,
        json_url=json_url,
        norma_id=norma_id,
        category=category,
        directory=directory,
        title=title,
    )


def normalized_from_dict(data: dict[str, Any]) -> NormalizedNorma:
    """Restore a persisted normalized norm without contacting IMPO again."""
    return normalize_impo_data(
        {
            "tipoNorma": data.get("tipo"),
            "nroNorma": data.get("numero"),
            "anioNorma": data.get("anio"),
            "nombreNorma": data.get("nombre"),
            "leyenda": data.get("leyenda"),
            "fechaPromulgacion": data.get("fechaPromulgacion"),
            "fechaPublicacion": data.get("fechaPublicacion"),
            "vistos": data.get("vistos"),
            "referenciasNorma": data.get("referenciasNorma"),
            "indexacionNorma": data.get("indexacionNorma"),
            "articulos": data.get("articulos") or [],
        },
        str(data.get("canonical_url") or ""),
        str(data.get("json_url") or ""),
        str(data.get("norma_id") or ""),
    )


def build_plain_text(norma: NormalizedNorma) -> str:
    lines: list[str] = []
    lines.append(f"{norma.tipo} Nº {norma.numero} - Año {norma.anio}")
    lines.append(norma.nombre)
    lines.append("")
    if norma.fecha_promulgacion:
        lines.append(f"Fecha de promulgación: {norma.fecha_promulgacion}")
    if norma.fecha_publicacion:
        lines.append(f"Fecha de publicación: {norma.fecha_publicacion}")
    if norma.leyenda:
        lines.append(norma.leyenda)
    lines.append("")
    if norma.vistos:
        lines.append("VISTOS:")
        lines.append(norma.vistos)
        lines.append("")
    for article in norma.articulos:
        header = f"Artículo {article.number}".strip()
        if article.title:
            header = f"{header} - {article.title}"
        lines.append(header)
        lines.append(article.text)
        if article.notes:
            lines.append(f"Notas: {article.notes}")
        if article.references:
            lines.append(f"Referencias: {article.references}")
        lines.append("")
    if norma.referencias:
        lines.append("Referencias de la norma:")
        lines.append(norma.referencias)
        lines.append("")
    if norma.indexacion:
        lines.append("Indexación:")
        lines.append(norma.indexacion)
        lines.append("")
    return "\n".join(lines).strip()

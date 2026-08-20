"""Recover image-only decrees from their exact official acta transcription."""
from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from depto import storage as st
from depto.download import DownloadedSource, download_source
from depto.extract import extract_decree_from_official_minutes, extract_pdf_text
from depto.service import DeptoService


OFFICIAL_ACTAS = {
    "decreto:3589:2019": {
        "acta": "https://juntadepartamentallavalleja.gub.uy/wp-content/uploads/2025/10/ACTA_N_914_02_10_2019_ORDINARIA.pdf",
        "scan": "https://juntadepartamentallavalleja.gub.uy/wp-content/uploads/2025/10/3589_derogacion_decreto_3582_modificacion_decreto_3571_de.pdf",
    },
    "decreto:3647:2020": {
        "acta": "https://juntadepartamentallavalleja.gub.uy/wp-content/uploads/2025/10/ACTA_N_939_21_10_2020_ORDINARIA_CASA_CULTURA.pdf",
        "scan": "https://juntadepartamentallavalleja.gub.uy/wp-content/uploads/2025/10/3647_Deroga_articulos_70_y_71_Decreto_3571.pdf",
    },
}


def main() -> None:
    service = DeptoService()
    results: list[dict] = []
    for norm_id, sources in OFFICIAL_ACTAS.items():
        norm_type, number, year = norm_id.split(":", 2)
        previous = st.load_registry().get(norm_id, {})
        acta = download_source(sources["acta"])
        acta_text, _ = extract_pdf_text(acta)
        decree_text = extract_decree_from_official_minutes(acta_text, number)
        transcription = DownloadedSource(
            url=sources["acta"],
            final_url=acta.final_url,
            content_type="text/plain; charset=utf-8",
            raw=decree_text.encode("utf-8"),
            encoding="utf-8",
        )
        result = service.importer._import_downloaded(
            transcription,
            norm_type=norm_type,
            number=number,
            year=year,
            family=previous.get("normative_family") or "general",
            title=previous.get("title"),
            source_quality="official_acta_transcription",
            active=True,
            index=True,
            evidence_url=sources["scan"],
            force=True,
        )
        results.append(result.to_dict())

    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

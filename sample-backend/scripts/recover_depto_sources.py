"""Recover departmental norms previously registered only as references.

The URLs below are official PDF attachments exposed by the Junta
Departamental de Lavalleja public archive.  The script is idempotent and uses
the normal importer/indexer so registry, normalized files and Qdrant stay in
sync.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from depto import storage as st
from depto.service import DeptoService


OFFICIAL_SOURCES = {
    "decreto:2953:2011": "https://juntadepartamentallavalleja.gub.uy/wp-content/uploads/2025/10/2953_PRESUPUESTO_IDL_2011_2015_original.pdf",
    "decreto:3061:2012": "https://juntadepartamentallavalleja.gub.uy/wp-content/uploads/2025/10/3061_Decl_Int_Cultural_Dptal.pdf",
    "decreto:3092:2012": "https://juntadepartamentallavalleja.gub.uy/wp-content/uploads/2025/10/3092_Modificacion_Presupuestal_Normas_2013_IDL.pdf",
    "decreto:3096:2012": "https://juntadepartamentallavalleja.gub.uy/wp-content/uploads/2025/10/3096_Modificacion_art_14_dec_2100_01_presut_func.pdf",
    "decreto:3238:2014": "https://juntadepartamentallavalleja.gub.uy/wp-content/uploads/2025/10/3238_Modificacion_articulos_18_19_21_22_Decreto_2965_Ruidos_Molestos.pdf",
    "decreto:3326:2015": "https://juntadepartamentallavalleja.gub.uy/wp-content/uploads/2025/10/3326_COMISION_DE_PATRIMONIO_DEPARTAMENTAL.pdf",
    "decreto:3473:2018": "https://juntadepartamentallavalleja.gub.uy/wp-content/uploads/2025/10/3473_Instalacion_polo_tecnologico_innoval_en_Minas.pdf",
    "decreto:3496:2018": "https://juntadepartamentallavalleja.gub.uy/wp-content/uploads/2025/10/3496_Normativa_de_edificacion_higiene_vivienda.pdf",
    "decreto:3534:2018": "https://juntadepartamentallavalleja.gub.uy/wp-content/uploads/2025/10/3534-Normas-referidas-a-SUCIVE.pdf",
    "decreto:3800:2023": "https://juntadepartamentallavalleja.gub.uy/wp-content/uploads/2025/10/3800_modificacion_Decreto_3326_2015_Art_3.pdf",
}


def main() -> None:
    service = DeptoService()
    registry = st.load_registry()
    results: list[dict] = []
    for norm_id, url in OFFICIAL_SOURCES.items():
        norm_type, number, year = norm_id.split(":", 2)
        old_id = "decreto:3473:unknown" if number == "3473" else norm_id
        previous = registry.get(old_id) or registry.get(norm_id) or {}
        result = service.importer.import_source(
            url=url,
            norm_type=norm_type,
            number=number,
            year=year,
            family=previous.get("normative_family") or "general",
            title=None,
            source_quality="primary_full_text",
            active=True,
            index=True,
            evidence_url=url,
        )
        results.append(result.to_dict())
        registry = st.load_registry()
        if old_id != norm_id and old_id in registry and result.text_available:
            registry.pop(old_id, None)
            st.save_registry(registry)

    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

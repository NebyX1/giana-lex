"""Recover the official Decreto 2665 published as a legacy Word 97 file.

The Junta archive exposes this norm only as ``.doc``.  On Windows we use the
installed Word converter with macros disabled, then pass the resulting plain
text through the normal importer/indexer.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from depto import storage as st
from depto.download import DownloadedSource, download_source
from depto.service import DeptoService


SOURCE_URL = (
    "https://juntadepartamentallavalleja.gub.uy/wp-content/uploads/2025/10/"
    "2665-Autorizacion-creacion-de-linea-Minas-Villa-Rosario.doc"
)
OLD_NORM_ID = "decreto:2665:2011"
NORM_ID = "decreto:2665:2007"


def _convert_with_word(raw: bytes) -> str:
    if os.name != "nt":
        raise RuntimeError("La conversión del Word 97 requiere Windows y Microsoft Word")
    with tempfile.TemporaryDirectory(prefix="giana-depto-word-") as temp_dir:
        input_path = Path(temp_dir) / "decreto-2665.doc"
        output_path = Path(temp_dir) / "decreto-2665.txt"
        input_path.write_bytes(raw)
        environment = os.environ.copy()
        environment["GIANA_LEGACY_DOC_INPUT"] = str(input_path)
        environment["GIANA_LEGACY_DOC_OUTPUT"] = str(output_path)
        command = r"""
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
$word.AutomationSecurity = 3
$document = $null
try {
  $document = $word.Documents.Open($env:GIANA_LEGACY_DOC_INPUT, $false, $true)
  $document.SaveAs2($env:GIANA_LEGACY_DOC_OUTPUT, 7)
} finally {
  if ($null -ne $document) { $document.Close($false) }
  $word.Quit()
}
"""
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )
        if completed.returncode != 0 or not output_path.exists():
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise RuntimeError(f"Microsoft Word no pudo convertir el documento: {detail}")
        converted = output_path.read_bytes()
        if converted.startswith((b"\xff\xfe", b"\xfe\xff")):
            return converted.decode("utf-16")
        return converted.decode("cp1252")


def main() -> None:
    official_doc = download_source(SOURCE_URL)
    text = _convert_with_word(official_doc.raw).strip()
    source = DownloadedSource(
        url=SOURCE_URL,
        final_url=official_doc.final_url,
        content_type="text/plain; charset=utf-8",
        raw=text.encode("utf-8"),
        encoding="utf-8",
    )
    service = DeptoService()
    result = service.importer._import_downloaded(
        source,
        norm_type="decreto",
        number="2665",
        year="2007",
        family="general",
        title="Autorización de la línea Minas - Villa Rosario",
        source_quality="primary_full_text",
        active=True,
        index=True,
        evidence_url=SOURCE_URL,
        force=True,
    )
    if result.text_available:
        registry = st.load_registry()
        registry.pop(OLD_NORM_ID, None)
        st.save_registry(registry)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

from pathlib import Path


MOLD_FILENAME = "resolucion_basica.md"


def load_mold(molds_dir: Path) -> str:
    root = Path(molds_dir).resolve()
    path = (root / MOLD_FILENAME).resolve()
    if path.parent != root or not path.is_file():
        raise FileNotFoundError(f"No se encontro el molde {MOLD_FILENAME}")
    return path.read_text(encoding="utf-8")

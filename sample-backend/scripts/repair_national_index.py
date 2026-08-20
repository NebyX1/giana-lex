"""Repair missing national RAG sources from durable local IMPO copies."""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from impo.service import ImpoService


if __name__ == "__main__":
    print(json.dumps(ImpoService().repair_index(missing_only=True), ensure_ascii=False, indent=2))

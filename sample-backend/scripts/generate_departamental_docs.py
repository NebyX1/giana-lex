"""Generate MISSING_SOURCES.md and NORMATIVE_RELATIONSHIPS.md from the registry."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from depto import storage as st

ROOT = st.DEPARTAMENTAL_ROOT

# --- MISSING_SOURCES.md ---
missing_lines = ["# Fuentes originales no localizadas\n"]
reg = st.load_registry()
missing = [e for e in reg.values() if not e.get("text_available")]
for entry in sorted(missing, key=lambda e: e.get("id", "")):
    missing_lines.append(f"## {entry.get('type', '')} {entry.get('number', '')} ({entry.get('year') or 'año desconocido'})")
    missing_lines.append(f"- Existencia confirmada: {bool(entry.get('existence_confirmed'))}")
    missing_lines.append(f"- Original no localizado: True")
    for ev in entry.get("evidence_sources", []) or []:
        missing_lines.append(f"- Evidencia: {ev}")
    if not entry.get("evidence_sources"):
        missing_lines.append(f"- Evidencia: (ninguna URL almacenada)")
    missing_lines.append("")
(ROOT / "MISSING_SOURCES.md").write_text("\n".join(missing_lines), encoding="utf-8")

# --- NORMATIVE_RELATIONSHIPS.md ---
rels = st.load_relationships()
family_entries = {}
for e in reg.values():
    family_entries.setdefault(e.get("normative_family", "general"), []).append(e)

rel_lines = ["# Relaciones normativas del digesto de Lavalleja\n"]
rel_lines.append("Generado desde relationships.json. No mantener a mano.\n")
by_from = {}
for r in rels:
    by_from.setdefault(r.get("from"), []).append(r)

for family, entries in sorted(family_entries.items()):
    rel_lines.append(f"## {family}\n")
    for entry in sorted(entries, key=lambda e: e.get("id", "")):
        nid = entry.get("id")
        rel_lines.append(f"- {entry.get('type','')} {entry.get('number','')} ({entry.get('year') or '—'})")
        for r in by_from.get(nid, []):
            status = r.get("status", "")
            marker = "✓" if status == "verified" else ("?" if status == "candidate" else "*")
            rel_lines.append(f"    {marker} {r.get('relation')} -> {r.get('to')}")
        for r in rels:
            if r.get("to") == nid and r.get("relation") in ("MODIFIES", "DEROGATES", "RESTORES", "REPLACES", "REGULATES", "INCORPORATES"):
                status = r.get("status", "")
                marker = "✓" if status == "verified" else ("?" if status == "candidate" else "*")
                rel_lines.append(f"    {marker} {r.get('relation')} by {r.get('from')}")
    rel_lines.append("")

(ROOT / "NORMATIVE_RELATIONSHIPS.md").write_text("\n".join(rel_lines), encoding="utf-8")

print(f"MISSING_SOURCES.md: {len(missing)} normas sin texto")
print(f"NORMATIVE_RELATIONSHIPS.md: {len(rels)} relaciones")
print(f"Familias: {len(family_entries)}")
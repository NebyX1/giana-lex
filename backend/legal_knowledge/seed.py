from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select

from .models import Resolution, ResolutionRevision, ResolutionTaxonomyAssignment, TaxonomyNode
from .parser import normalize_resolution_number
from .schemas import ResolutionAssignmentInput, TaxonomyNodeInput


def humanize(value: str) -> str:
    return value.replace("_", " ").strip().capitalize()


class InitialCorpusSeeder:
    def __init__(self, service):
        self.service = service

    def load(self, path: Path | None = None) -> dict:
        seed_path = Path(path or self.service.settings.legal_seed_path)
        return json.loads(seed_path.read_text(encoding="utf-8"))

    def run(self, path=None, dry_run=False, limit=None, only=None, taxonomy_only=False) -> dict:
        seed = self.load(path)
        requested = seed["entries"]
        if only:
            normalized = {item.strip() for item in only.split(",")}
            requested = [item for item in requested if item[0] in normalized or item[1] in normalized]
        if limit:
            requested = requested[:limit]
        report = {
            "seed_version": seed["seed_version"], "seed_requested": len(requested),
            "taxonomy_created": 0, "urls_resolved": 0, "downloaded": 0, "validated": 0,
            "duplicates": 0, "failed": 0, "review_required": 0, "indexed": 0, "items": [],
        }
        nodes = self._ensure_taxonomy(seed, requested, dry_run, report)
        if dry_run or taxonomy_only:
            return report
        for code, number, expected_title in requested:
            item_report = {"code": code, "resolution_number": number, "expected_title": expected_title}
            try:
                node = nodes[code]
                assignment = ResolutionAssignmentInput(taxonomy_node_id=node["id"], role="canonical")
                result = self.service.import_number(number, [assignment], expected_title, actor=f"seed:{seed['seed_version']}", sync=False)
                report["urls_resolved"] += 1
                report["downloaded"] += 1
                item_report["source_url"] = result["resolution"]["source_url"]
                item_report["resolution_id"] = result["resolution"]["id"]
                if result.get("duplicate"):
                    report["duplicates"] += 1
                    self._ensure_assignment(result["resolution"]["id"], node["id"], f"seed:{seed['seed_version']}")
                validation = result["validation"]["status"]
                item_report["status"] = validation
                item_report["validation"] = result["validation"]
                if validation == "validated":
                    report["validated"] += 1
                else:
                    report["review_required"] += 1
            except Exception as exc:
                report["failed"] += 1
                item_report["status"] = "failed"
                item_report["error"] = str(exc)
            report["items"].append(item_report)
        if not only and limit is None:
            self._write_reports(report)
            self.service.export_manifest(self.service.settings.legal_report_dir / "idl_resolution_manifest.jsonl")
        return report

    def _ensure_taxonomy(self, seed, entries, dry_run, report):
        family_names = seed.get("families", {})
        existing = {item["code"]: item for item in self.service.taxonomy_tree()}
        nodes = dict(existing)
        codes = sorted({entry[0] for entry in entries})
        for code in codes:
            family_code, type_slug, subtype_slug = code.split(".", 2)
            family_key = family_code
            type_code = f"{family_code}.{type_slug}"
            if family_key not in nodes:
                if dry_run:
                    nodes[family_key] = {"id": f"dry:{family_key}", "code": family_key}
                else:
                    nodes[family_key] = self.service.create_taxonomy(TaxonomyNodeInput(
                        level="family", code=family_key, slug=family_key.lower(),
                        name=family_names.get(family_key, humanize(family_key)), status="active",
                    ), actor=f"seed:{seed['seed_version']}", sync=False)
                    report["taxonomy_created"] += 1
            if type_code not in nodes:
                if dry_run:
                    nodes[type_code] = {"id": f"dry:{type_code}", "code": type_code}
                else:
                    nodes[type_code] = self.service.create_taxonomy(TaxonomyNodeInput(
                        parent_id=nodes[family_key]["id"], level="type", code=type_code, slug=type_slug,
                        name=humanize(type_slug), status="active",
                    ), actor=f"seed:{seed['seed_version']}", sync=False)
                    report["taxonomy_created"] += 1
            if code not in nodes:
                expected_title = next(item[2] for item in entries if item[0] == code)
                signals = sorted(set(expected_title.lower().replace("/", " ").split()))
                if dry_run:
                    nodes[code] = {"id": f"dry:{code}", "code": code}
                else:
                    nodes[code] = self.service.create_taxonomy(TaxonomyNodeInput(
                        parent_id=nodes[type_code]["id"], level="subtype", code=code, slug=subtype_slug,
                        name=expected_title, description=expected_title, aliases=[humanize(subtype_slug)],
                        positive_signals=signals, status="active",
                    ), actor=f"seed:{seed['seed_version']}", sync=False)
                    report["taxonomy_created"] += 1
        return nodes

    def _ensure_assignment(self, resolution_id: str, taxonomy_node_id: str, actor: str):
        with self.service.database.session() as session:
            exists = session.scalar(select(ResolutionTaxonomyAssignment).where(
                ResolutionTaxonomyAssignment.resolution_id == resolution_id,
                ResolutionTaxonomyAssignment.taxonomy_node_id == taxonomy_node_id,
            ))
            resolution = session.get(Resolution, resolution_id)
            node = session.get(TaxonomyNode, taxonomy_node_id)
            if not exists and resolution and node and resolution.review_status == "validated":
                session.add(ResolutionTaxonomyAssignment(
                    resolution_id=resolution_id, taxonomy_node_id=taxonomy_node_id,
                    role="canonical", priority=100, notes="Seed inicial", created_by=actor,
                ))
                resolution.version += 1
                resolution.index_status = "pending"
                self.service._outbox(session, "resolution_payload", resolution.id, resolution.version)

    def _write_reports(self, report):
        directory = self.service.settings.legal_report_dir
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "initial_idl_import_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        lines = [
            "# Importación inicial IDL", "",
            f"- Seed: `{report['seed_version']}`", f"- Solicitadas: {report['seed_requested']}",
            f"- URLs resueltas: {report['urls_resolved']}", f"- Descargadas: {report['downloaded']}",
            f"- Validadas: {report['validated']}", f"- Duplicadas: {report['duplicates']}",
            f"- Fallidas: {report['failed']}", f"- Requieren revisión: {report['review_required']}",
            f"- Indexadas: {report['indexed']}", "", "## Detalle", "",
        ]
        for item in report["items"]:
            detail = item.get("error") or item.get("validation", {}).get("reason", "")
            lines.append(f"- `{item['resolution_number']}` · `{item['code']}` · **{item['status']}** · {detail}")
        (directory / "initial_idl_import_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def refresh_index_counts(self) -> dict | None:
        path = self.service.settings.legal_report_dir / "initial_idl_import_report.json"
        if not path.exists():
            return None
        report = json.loads(path.read_text(encoding="utf-8"))
        resolution_ids = {item.get("resolution_id") for item in report["items"] if item.get("resolution_id")}
        with self.service.database.session() as session:
            synced_ids = set(session.scalars(select(Resolution.id).where(
                Resolution.id.in_(resolution_ids), Resolution.index_status == "synced"
            )).all()) if resolution_ids else set()
        report["indexed"] = len(synced_ids)
        report["indexed_associations"] = sum(
            1 for item in report["items"] if item.get("resolution_id") in synced_ids and item.get("status") == "validated"
        )
        self._write_reports(report)
        return report

    def rebuild_report_from_database(self) -> dict:
        seed = self.load()
        report = {
            "seed_version": seed["seed_version"], "seed_requested": len(seed["entries"]), "taxonomy_created": 247,
            "urls_resolved": 0, "downloaded": 0, "validated": 0, "duplicates": 0,
            "failed": 0, "review_required": 0, "indexed": 0, "items": [],
        }
        unique_ids = set()
        with self.service.database.session() as session:
            for code, number, expected_title in seed["entries"]:
                resolution = session.scalar(select(Resolution).where(
                    Resolution.resolution_number_normalized == normalize_resolution_number(number)
                ))
                item = {"code": code, "resolution_number": number, "expected_title": expected_title}
                if not resolution:
                    item.update(status="failed", error="No existe en la base")
                    report["failed"] += 1
                else:
                    revision = session.get(ResolutionRevision, resolution.current_revision_id)
                    candidate = type("Candidate", (), {
                        "title": resolution.title,
                        "official_summary": resolution.official_summary,
                        "normalized_text": revision.normalized_text,
                    })()
                    validation = self.service._validate_semantics(candidate, expected_title)
                    item.update(source_url=resolution.source_url, resolution_id=resolution.id, status=validation["status"], validation=validation)
                    report["urls_resolved"] += 1
                    report["downloaded"] += 1
                    unique_ids.add(resolution.id)
                    if validation["status"] == "validated": report["validated"] += 1
                    else: report["review_required"] += 1
                report["items"].append(item)
        report["duplicates"] = report["urls_resolved"] - len(unique_ids)
        self._write_reports(report)
        self.service.export_manifest(self.service.settings.legal_report_dir / "idl_resolution_manifest.jsonl")
        return self.refresh_index_counts()

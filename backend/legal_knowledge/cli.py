from __future__ import annotations

import json

import click
from flask import current_app

from .seed import InitialCorpusSeeder


@click.group("legal")
def legal_cli():
    """Administra la biblioteca de resoluciones y su índice derivado."""


def service():
    return current_app.config["LEGAL_KNOWLEDGE"]


@legal_cli.command("seed")
@click.option("--dry-run", is_flag=True)
@click.option("--limit", type=int)
@click.option("--only", help="Códigos o números separados por coma")
@click.option("--taxonomy-only", is_flag=True)
def seed(dry_run, limit, only, taxonomy_only):
    result = InitialCorpusSeeder(service()).run(dry_run=dry_run, limit=limit, only=only, taxonomy_only=taxonomy_only)
    click.echo(json.dumps(result, ensure_ascii=False, indent=2, default=str))


@legal_cli.command("import-url")
@click.argument("url")
@click.option("--dry-run", is_flag=True)
def import_url(url, dry_run):
    result = service().preview_url(url) if dry_run else service().import_url(url, actor="cli")
    click.echo(json.dumps(result, ensure_ascii=False, indent=2, default=str))


@legal_cli.command("index-pending")
@click.option("--limit", default=100, type=int)
def index_pending(limit):
    result = service().process_outbox(limit=limit)
    InitialCorpusSeeder(service()).refresh_index_counts()
    click.echo(json.dumps(result, indent=2))


@legal_cli.command("retry")
@click.option("--limit", default=100, type=int)
def retry(limit):
    click.echo(json.dumps(service().process_outbox(limit=limit, only_failed=True), indent=2))


@legal_cli.command("check-index")
def check_index():
    click.echo(json.dumps(service().check_consistency(), ensure_ascii=False, indent=2, default=str))


@legal_cli.command("rebuild-index")
@click.option("--dry-run", is_flag=True)
def rebuild_index(dry_run):
    if dry_run:
        overview = service().overview()
        result = {"taxonomy": overview["typologies_active"], "resolutions": overview["resolutions"], "status": "dry_run"}
    else:
        result = service().enqueue_rebuild(actor="cli")
    click.echo(json.dumps(result, ensure_ascii=False, indent=2))


@legal_cli.command("status")
def status():
    click.echo(json.dumps(service().index_status(), ensure_ascii=False, indent=2, default=str))


@legal_cli.command("manifest")
@click.option("--output", default="backend/data/legal/reports/idl_resolution_manifest.jsonl")
def manifest(output):
    count = service().export_manifest(current_app.config["SETTINGS"].base_dir.parent / output)
    click.echo(f"{count} resoluciones exportadas")


@legal_cli.command("report")
def report():
    result = InitialCorpusSeeder(service()).rebuild_report_from_database()
    click.echo(json.dumps({key: value for key, value in result.items() if key != "items"}, ensure_ascii=False, indent=2))


@legal_cli.command("crawl-catalog")
@click.option("--start-page", default=0, type=int)
@click.option("--limit", "max_pages", default=1, type=int, help="Cantidad máxima de páginas")
@click.option("--dry-run", is_flag=True)
def crawl_catalog(start_page, max_pages, dry_run):
    if dry_run:
        click.echo(json.dumps({"start_page": start_page, "max_pages": max_pages, "status": "dry_run"}, indent=2))
        return
    click.echo(json.dumps(service().crawl_catalog(start_page, max_pages), ensure_ascii=False, indent=2))

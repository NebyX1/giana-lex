"""Locate missing Lavalleja decrees in the official Junta document archive.

This utility is read-only.  It crawls the public decree catalogue and prints
the official detail/PDF candidates for the requested decree numbers.
"""
from __future__ import annotations

import argparse
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser
from urllib.parse import urljoin

import httpx


BASE_URL = "https://juntadepartamentallavalleja.gub.uy"
CATALOGUE_URL = f"{BASE_URL}/index.php/documentos/decretos"


class AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.anchors: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.anchors.append((" ".join(self._text).strip(), self._href))
            self._href = None
            self._text = []


def anchors(html: str) -> list[tuple[str, str]]:
    parser = AnchorParser()
    parser.feed(html)
    return parser.anchors


def discover(numbers: set[str], *, max_pages: int = 90) -> dict[str, list[dict[str, str]]]:
    del max_pages  # retained for CLI compatibility
    found: dict[str, list[dict[str, str]]] = {number: [] for number in sorted(numbers)}
    headers = {"User-Agent": "Giana-Lex/1.0 (archivo juridico departamental)"}

    def search_number(number: str) -> tuple[str, list[dict[str, str]]]:
        with httpx.Client(headers=headers, timeout=30, follow_redirects=True) as client:
            response = client.get(
                f"{BASE_URL}/wp-json/wp/v2/search",
                params={"search": number, "per_page": 100},
            )
            response.raise_for_status()
            candidates: list[dict[str, str]] = []
            attachment_results = [
                result for result in response.json()
                if result.get("subtype") == "attachment"
            ]
            exact_results = []
            for result in attachment_results:
                title = str(result.get("title") or "")
                title_key = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
                if (
                    re.search(rf"(?:^|_){re.escape(number)}(?:_|$)", title_key)
                    and not title_key.startswith("acta_")
                ):
                    exact_results.append(result)
            selected_results = exact_results or attachment_results[:8]
            for result in selected_results:
                self_links = result.get("_links", {}).get("self", [])
                if not self_links:
                    continue
                media = client.get(self_links[0]["href"])
                if media.status_code != 200:
                    continue
                payload = media.json()
                source_url = payload.get("source_url", "")
                if not source_url.lower().endswith(".pdf"):
                    continue
                title = str(result.get("title") or "")
                title_key = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
                exact = bool(re.search(rf"(?:^|_){re.escape(number)}(?:_|$)", title_key))
                candidates.append({
                    "title": title,
                    "detail_url": str(result.get("url") or ""),
                    "pdf_url": source_url,
                    "match": "direct" if exact and not title_key.startswith("acta_") else "acta_or_reference",
                })
            candidates.sort(key=lambda item: (item["match"] != "direct", item["title"]))
            return number, candidates

    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(search_number, number) for number in numbers]
        for future in as_completed(futures):
            number, candidates = future.result()
            found[number] = candidates
    return found


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("numbers", nargs="+")
    parser.add_argument("--max-pages", type=int, default=90)
    args = parser.parse_args()
    print(json.dumps(discover(set(args.numbers), max_pages=args.max_pages), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

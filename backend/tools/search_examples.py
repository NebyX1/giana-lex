import re
import unicodedata
from pathlib import Path

from rank_bm25 import BM25Okapi

from schemas import ExampleCandidate


GENERIC_TERMS = {
    "administrativo", "administrativa", "acto", "autorizar", "departamental", "documento",
    "intendencia", "necesito", "resolucion", "solicitud", "solicita", "solicitada",
}


def normalize_text(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKD", text.lower())
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.findall(r"[a-z0-9]+", ascii_text)


def _title(content: str, fallback: str) -> str:
    metadata = re.search(r"^title:\s*(.+)$", content, re.MULTILINE)
    if metadata:
        return metadata.group(1).strip()
    heading = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    return heading.group(1).strip() if heading else fallback


def search_examples(query: str, examples_dir: Path, limit: int = 3) -> list[ExampleCandidate]:
    files = sorted(Path(examples_dir).glob("*.md"))
    if not files:
        return []
    documents = [path.read_text(encoding="utf-8") for path in files]
    tokenized = [normalize_text(document) for document in documents]
    query_tokens = normalize_text(query)
    scores = BM25Okapi(tokenized).get_scores(query_tokens)
    # With a two-document corpus BM25 can assign IDF 0 to every unique term.
    # A small lexical overlap component makes those otherwise equal scores useful.
    combined_scores = [
        float(score) + (len(set(query_tokens) & set(tokens)) / max(1, len(set(query_tokens))))
        for score, tokens in zip(scores, tokenized)
    ]
    ranked = sorted(zip(files, documents, combined_scores), key=lambda item: float(item[2]), reverse=True)
    results = []
    for path, content, score in ranked[: max(1, limit)]:
        clean = re.sub(r"\s+", " ", content).strip()
        results.append(
            ExampleCandidate(
                filename=path.name,
                title=_title(content, path.stem),
                score=round(float(score), 4),
                excerpt=clean[:1200],
            )
        )
    return results


def has_lexical_support(query: str, candidate: ExampleCandidate, minimum_terms: int = 2) -> bool:
    query_terms = set(normalize_text(query)) - GENERIC_TERMS
    candidate_terms = set(normalize_text(f"{candidate.title} {candidate.excerpt}")) - GENERIC_TERMS
    return len(query_terms & candidate_terms) >= minimum_terms


def load_selected_examples(filenames: list[str], examples_dir: Path, max_files: int = 2) -> list[dict[str, str]]:
    root = Path(examples_dir).resolve()
    loaded = []
    for filename in filenames[:max_files]:
        path = (root / Path(filename).name).resolve()
        if path.parent != root or not path.is_file() or path.suffix.lower() != ".md":
            continue
        loaded.append({"filename": path.name, "content": path.read_text(encoding="utf-8")[:10000]})
    return loaded

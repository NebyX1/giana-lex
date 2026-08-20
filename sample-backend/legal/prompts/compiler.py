from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from app.extensions import db
from legal.infrastructure.models import PromptVersionRecord


POLICY_ORDER = (
    "SYSTEM_CORE.md", "LEGAL_BOUNDARIES.md", "SOURCE_HIERARCHY.md",
    "UNTRUSTED_CONTENT.md", "MEMORY_POLICY.md", "DRAFTING_POLICY.md",
)
REQUIRED_NODES = (
    "INTENT_COMPILER", "PRECEDENT_CURATOR", "LEGAL_ISSUE_PLANNER",
    "LEGAL_RESEARCHER", "LEGAL_VERIFIER", "DRAFT_COMPOSER", "COMPLIANCE_AUDITOR",
    "MANAGER", "PRECEDENT_EXPLORER", "ANALYZER", "QUESTION_PLANNER", "FORM_COMPILER",
)


def validate_prompt_registry(root: Path | None = None) -> None:
    base = root or Path(__file__).parent
    missing = [
        str(path) for path in (
            *(base / "policies" / name for name in POLICY_ORDER),
            *(base / "nodes" / f"{name}.md" for name in REQUIRED_NODES),
        ) if not path.is_file() or not path.read_text(encoding="utf-8").strip()
    ]
    if missing:
        raise RuntimeError(f"Missing or empty prompt registry entries: {', '.join(missing)}")


class PromptCompiler:
    def __init__(self, root: Path | None = None):
        self.root = root or Path(__file__).parent

    def compile(self, node_id: str, trusted_context: str = "", untrusted_data: str = "") -> PromptVersionRecord:
        node_path = self.root / "nodes" / f"{node_id.upper()}.md"
        if not node_path.is_file():
            raise ValueError(f"Unknown prompt node {node_id}")
        components = []
        used = []
        for name in POLICY_ORDER:
            text = (self.root / "policies" / name).read_text(encoding="utf-8").strip()
            if text not in components:
                components.append(text)
                used.append(name)
        components.append(node_path.read_text(encoding="utf-8").strip())
        if trusted_context:
            components.append(f"<TRUSTED_CONTEXT>\n{trusted_context}\n</TRUSTED_CONTEXT>")
        if untrusted_data:
            components.append(f'<UNTRUSTED_SOURCE_DATA source_id="runtime">\n{untrusted_data}\n</UNTRUSTED_SOURCE_DATA>')
        content = "\n\n".join(components)
        prompt_hash = sha256(content.encode("utf-8")).hexdigest()
        existing = PromptVersionRecord.query.filter_by(prompt_hash=prompt_hash).first()
        if existing:
            return existing
        record = PromptVersionRecord(
            id=str(uuid4()), prompt_hash=prompt_hash, node_id=node_id,
            policies_json=used, content=content, token_estimate=max(1, len(content) // 4),
        )
        db.session.add(record)
        db.session.flush()
        return record

from typing import Protocol

from legal.domain.models import LegalIssue, VerifiedAuthorityInput
from legal.infrastructure.models import FactAssertionRecord
from legal.workflows.loader import WorkflowPack
from rag.retriever import LegalRetriever


class AuthorityProvider(Protocol):
    def retrieve(self, case_id: str, issues: list[LegalIssue], facts: list[FactAssertionRecord]) -> list[VerifiedAuthorityInput]: ...


class NoAuthorityProvider:
    def retrieve(self, case_id: str, issues: list[LegalIssue], facts: list[FactAssertionRecord]) -> list[VerifiedAuthorityInput]:
        return []


class RetrieverAuthorityProvider:
    """Returns official retrieval candidates; persistence remains unverified until the verifier runs."""
    def __init__(self, retriever: LegalRetriever, top_k_per_issue: int = 4):
        self.retriever = retriever
        self.top_k_per_issue = top_k_per_issue

    def retrieve(self, case_id: str, issues: list[LegalIssue], facts: list[FactAssertionRecord]) -> list[VerifiedAuthorityInput]:
        candidates = []
        for issue in issues:
            if not issue.question.strip():
                continue
            for corpus in ("nacional", "departamental"):
                for hit in self.retriever.search(issue.question, corpus, top_k=self.top_k_per_issue, active=True):
                    metadata = hit.get("metadata") or {}
                    text = str(hit.get("text") or "").strip()
                    source_id = str(hit.get("identifier") or "").strip()
                    norm_id = metadata.get("norm_id") or metadata.get("norma_id")
                    source_url = metadata.get("source_url")
                    complete = bool(source_id and norm_id and source_url and text and metadata.get("active") is True)
                    candidates.append(VerifiedAuthorityInput(
                        issue_id=issue.issue_id,
                        source_id=source_id or "missing-source-id",
                        source_version=str(metadata.get("source_hash") or metadata.get("indexed_at") or "unknown"),
                        source_class="official_primary",
                        jurisdiction=str(metadata.get("jurisdiction") or ("uruguay" if corpus == "nacional" else "lavalleja")),
                        exact_text=text or "Fuente sin texto oficial completo.",
                        proposition=issue.question,
                        norm_id=str(norm_id) if norm_id else None,
                        article=str(metadata.get("article")) if metadata.get("article") else None,
                        source_url=str(source_url) if source_url else None,
                        authenticity_verified=complete,
                        applicability_verified=complete and LegalRetriever._lexical_overlap(issue.question, text) >= 0.2,
                        active=metadata.get("active") is True,
                    ))
        return candidates


def plan_issues(case_id: str, pack: WorkflowPack) -> list[LegalIssue]:
    facts = FactAssertionRecord.query.filter_by(case_id=case_id).all()
    fact_ids = [item.id for item in facts if item.verification_status == "confirmed_by_user"]
    return [
        LegalIssue(
            issue_id=f"{index}:{category}", category=category,
            question=f"Verificar {category} para los hechos confirmados del expediente.",
            relevant_fact_ids=fact_ids, required_source_classes=["official_primary", "official_secondary"],
            risk_level="high" if category == "competence" else "medium",
        )
        for index, category in enumerate(pack.legal_issues, 1)
    ]

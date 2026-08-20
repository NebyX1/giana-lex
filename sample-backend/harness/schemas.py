from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class AuthorityLevel(StrEnum):
    PRIMARY_AUTHORITY = "PRIMARY_AUTHORITY"
    OFFICIAL_ADMINISTRATIVE = "OFFICIAL_ADMINISTRATIVE"
    SECONDARY = "SECONDARY"
    EXAMPLE = "EXAMPLE"
    TEMPLATE = "TEMPLATE"
    USER_PROVIDED = "USER_PROVIDED"
    WEB_UNTRUSTED_DATA = "WEB_UNTRUSTED_DATA"
    UNKNOWN = "UNKNOWN"


class ClaimStatus(StrEnum):
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    UNVERIFIED = "UNVERIFIED"
    INFERENCE = "INFERENCE"


class FailureType(StrEnum):
    TOOL_ARGUMENT_ERROR = "TOOL_ARGUMENT_ERROR"
    NO_RESULTS = "NO_RESULTS"
    LOW_RELEVANCE_RESULTS = "LOW_RELEVANCE_RESULTS"
    CONTRADICTORY_EVIDENCE = "CONTRADICTORY_EVIDENCE"
    MISSING_USER_FACT = "MISSING_USER_FACT"
    MISSING_AUTHORITY = "MISSING_AUTHORITY"
    STRUCTURED_OUTPUT_ERROR = "STRUCTURED_OUTPUT_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    MODEL_REFUSAL = "MODEL_REFUSAL"
    MODEL_TIMEOUT = "MODEL_TIMEOUT"
    TOOL_TIMEOUT = "TOOL_TIMEOUT"
    LOOP_DETECTED = "LOOP_DETECTED"
    CONTEXT_OVERFLOW = "CONTEXT_OVERFLOW"
    UNSUPPORTED_CLAIM = "UNSUPPORTED_CLAIM"
    UNKNOWN = "UNKNOWN"


class FailureArea(StrEnum):
    ROUTING_FAILURE = "ROUTING_FAILURE"
    RETRIEVAL_FAILURE = "RETRIEVAL_FAILURE"
    TOOL_FAILURE = "TOOL_FAILURE"
    EVIDENCE_FAILURE = "EVIDENCE_FAILURE"
    REASONING_FAILURE = "REASONING_FAILURE"
    DRAFTING_FAILURE = "DRAFTING_FAILURE"
    VALIDATION_FAILURE = "VALIDATION_FAILURE"
    CONTEXT_FAILURE = "CONTEXT_FAILURE"
    MODEL_FAILURE = "MODEL_FAILURE"


@dataclass(frozen=True)
class MissingField:
    field: str
    required: bool = True
    source: str = "user"


@dataclass
class Claim:
    claim_id: str
    text: str
    category: str = "legal"
    evidence_ids: list[str] = field(default_factory=list)
    status: ClaimStatus = ClaimStatus.UNVERIFIED


@dataclass(frozen=True)
class ValidationIssue:
    issue_type: str
    severity: str
    message: str
    text: str | None = None


@dataclass
class VerificationResult:
    status: str
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.status == "pass"


@dataclass(frozen=True)
class RoutingDecision:
    primary_skill: str
    secondary_skills: tuple[str, ...] = ()
    needs_retrieval: bool = False
    needs_template: bool = False
    needs_user_clarification: bool = False
    task_type: str = "general"
    document_type: str | None = None
    subtype: str | None = None
    variant: str | None = None
    complexity: str = "simple"
    legal_risk: str = "low"


@dataclass(frozen=True)
class ExecutionBudget:
    max_llm_calls: int = 3
    max_tool_calls: int = 15
    max_retries: int = 2
    max_iterations: int = 12


@dataclass
class GateResult:
    name: str
    passed: bool
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

import httpx
from pydantic import ValidationError

from .schemas import FailureArea, FailureType


@dataclass(frozen=True)
class LoopSignal:
    detected: bool
    reason: str = ""


class LoopDetector:
    def __init__(self, repeat_limit: int = 2, no_progress_limit: int = 2):
        self.repeat_limit = repeat_limit
        self.no_progress_limit = no_progress_limit
        self.tool_signatures: list[str] = []
        self.queries: list[str] = []
        self.errors: list[str] = []
        self.no_new_evidence_rounds: Counter[str] = Counter()

    def record_tool(self, name: str, arguments: dict[str, Any]) -> LoopSignal:
        signature = f"{name}:{json.dumps(arguments, sort_keys=True, ensure_ascii=True)}"
        self.tool_signatures.append(signature)
        if self.tool_signatures.count(signature) >= self.repeat_limit:
            return LoopSignal(True, "same_tool_and_arguments")
        query = str(arguments.get("query", "")).strip().casefold()
        if query:
            if any(SequenceMatcher(None, query, previous).ratio() >= 0.94 for previous in self.queries):
                self.queries.append(query)
                return LoopSignal(True, "repeated_or_near_duplicate_query")
            self.queries.append(query)
        return LoopSignal(False)

    def record_evidence(self, new_count: int, scope: str = "global") -> LoopSignal:
        if new_count:
            self.no_new_evidence_rounds[scope] = 0
        else:
            self.no_new_evidence_rounds[scope] += 1
        return LoopSignal(self.no_new_evidence_rounds[scope] >= self.no_progress_limit, "no_new_evidence")

    def record_error(self, error: str) -> LoopSignal:
        self.errors.append(error)
        return LoopSignal(Counter(self.errors)[error] >= self.repeat_limit, "repeated_error")


class RetryPolicy:
    RETRYABLE = {
        FailureType.TOOL_ARGUMENT_ERROR,
        FailureType.NO_RESULTS,
        FailureType.LOW_RELEVANCE_RESULTS,
        FailureType.MISSING_AUTHORITY,
        FailureType.STRUCTURED_OUTPUT_ERROR,
        FailureType.VALIDATION_ERROR,
        FailureType.MODEL_TIMEOUT,
        FailureType.TOOL_TIMEOUT,
        FailureType.UNSUPPORTED_CLAIM,
    }

    def __init__(self, max_retries: int = 2):
        self.max_retries = max_retries

    def action(self, failure: FailureType, retry_count: int) -> str:
        if failure is FailureType.MISSING_USER_FACT:
            return "ask_user"
        if failure in {FailureType.CONTRADICTORY_EVIDENCE, FailureType.LOOP_DETECTED}:
            return "escalate"
        if failure in self.RETRYABLE and retry_count < self.max_retries:
            return "retry"
        return "escalate" if retry_count >= self.max_retries else "fail_safe"


class FailureClassifier:
    def classify_exception(self, exc: Exception, stage: str = "") -> tuple[FailureType, FailureArea]:
        if isinstance(exc, ValidationError) or isinstance(exc, (TypeError, ValueError, FileNotFoundError)) and stage == "tool":
            return FailureType.TOOL_ARGUMENT_ERROR, FailureArea.TOOL_FAILURE
        if isinstance(exc, (TimeoutError, httpx.TimeoutException)):
            return FailureType.MODEL_TIMEOUT if stage == "model" else FailureType.TOOL_TIMEOUT, FailureArea.MODEL_FAILURE if stage == "model" else FailureArea.TOOL_FAILURE
        if isinstance(exc, (httpx.NetworkError, httpx.RemoteProtocolError)):
            return FailureType.MODEL_TIMEOUT if stage == "model" else FailureType.TOOL_TIMEOUT, FailureArea.MODEL_FAILURE if stage == "model" else FailureArea.TOOL_FAILURE
        if isinstance(exc, httpx.HTTPStatusError):
            status = exc.response.status_code
            body = exc.response.text.casefold()
            if status == 413 or "context length" in body or "too many tokens" in body:
                return FailureType.CONTEXT_OVERFLOW, FailureArea.CONTEXT_FAILURE
            if status in {404, 408, 409, 425, 429, 500, 502, 503, 504}:
                return FailureType.MODEL_TIMEOUT, FailureArea.MODEL_FAILURE
        return FailureType.UNKNOWN, FailureArea.MODEL_FAILURE if stage == "model" else FailureArea.TOOL_FAILURE

    def area_for(self, failure: FailureType) -> FailureArea:
        if failure in {FailureType.NO_RESULTS, FailureType.LOW_RELEVANCE_RESULTS}:
            return FailureArea.RETRIEVAL_FAILURE
        if failure in {FailureType.MISSING_AUTHORITY, FailureType.CONTRADICTORY_EVIDENCE, FailureType.UNSUPPORTED_CLAIM}:
            return FailureArea.EVIDENCE_FAILURE
        if failure in {FailureType.CONTEXT_OVERFLOW}:
            return FailureArea.CONTEXT_FAILURE
        if failure in {FailureType.MODEL_REFUSAL, FailureType.MODEL_TIMEOUT, FailureType.STRUCTURED_OUTPUT_ERROR}:
            return FailureArea.MODEL_FAILURE
        if failure in {FailureType.VALIDATION_ERROR}:
            return FailureArea.VALIDATION_FAILURE
        return FailureArea.TOOL_FAILURE


@dataclass(frozen=True)
class EscalationDecision:
    escalate: bool
    reason: str = ""
    strategy: str = ""


class EscalationPolicy:
    def decide(self, failure: FailureType, retry_count: int, has_strong_model: bool = False) -> EscalationDecision:
        critical = failure in {FailureType.CONTRADICTORY_EVIDENCE, FailureType.LOOP_DETECTED}
        exhausted = retry_count > 0 and failure in {FailureType.STRUCTURED_OUTPUT_ERROR, FailureType.VALIDATION_ERROR, FailureType.UNSUPPORTED_CLAIM}
        if not (critical or exhausted):
            return EscalationDecision(False)
        strategy = "strong_model" if has_strong_model else "decompose_and_require_human_review"
        return EscalationDecision(True, failure.value, strategy)

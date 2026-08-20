from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping

from .schemas import ExecutionBudget


class HarnessMode(StrEnum):
    OFF = "off"
    STANDARD = "standard"
    STRICT = "strict"
    ADAPTIVE = "adaptive"


class ModelProfile(StrEnum):
    STRONG = "strong"
    BALANCED = "balanced"
    WEAK = "weak"
    AUTO = "auto"


@dataclass(frozen=True)
class ModelCapabilityProfile:
    name: ModelProfile
    tool_use: str
    structured_output: str
    reasoning: str
    long_context: str
    instruction_following: str

    @property
    def requires_scaffolding(self) -> bool:
        return self.name is ModelProfile.WEAK

    @classmethod
    def from_name(cls, value: str) -> "ModelCapabilityProfile":
        try:
            name = ModelProfile(value.strip().lower())
        except ValueError:
            name = ModelProfile.BALANCED
        if name is ModelProfile.AUTO:
            name = ModelProfile.BALANCED
        profiles = {
            ModelProfile.STRONG: ("high", "high", "high", "high", "high"),
            ModelProfile.BALANCED: ("medium", "medium", "medium", "medium", "medium"),
            ModelProfile.WEAK: ("low", "low", "low", "low", "medium"),
        }
        return cls(name, *profiles[name])


@dataclass(frozen=True)
class HarnessSettings:
    enabled: bool = False
    mode: HarnessMode = HarnessMode.ADAPTIVE
    profile: ModelCapabilityProfile = ModelCapabilityProfile.from_name("balanced")
    max_iterations: int = 12
    max_retries: int = 2
    max_tool_calls: int = 15
    max_llm_calls: int = 10
    context_max_chars: int = 24000
    debug: bool = False
    fast_model: str = ""
    strong_model: str = ""
    fallback_models: tuple[str, ...] = ()
    retry_backoff_seconds: float = 0.0

    @classmethod
    def from_config(cls, config: Mapping[str, object]) -> "HarnessSettings":
        raw_mode = str(config.get("HARNESS_MODE", "adaptive")).lower()
        try:
            mode = HarnessMode(raw_mode)
        except ValueError:
            mode = HarnessMode.ADAPTIVE
        return cls(
            enabled=bool(config.get("HARNESS_ENABLED", False)) and mode is not HarnessMode.OFF,
            mode=mode,
            profile=ModelCapabilityProfile.from_name(str(config.get("LLM_CAPABILITY_PROFILE", "balanced"))),
            max_iterations=max(1, int(config.get("HARNESS_MAX_ITERATIONS", 12))),
            max_retries=max(0, int(config.get("HARNESS_MAX_RETRIES", 2))),
            max_tool_calls=max(1, int(config.get("HARNESS_MAX_TOOL_CALLS", 15))),
            max_llm_calls=max(1, int(config.get("HARNESS_MAX_LLM_CALLS", 10))),
            context_max_chars=max(4000, int(config.get("HARNESS_CONTEXT_MAX_CHARS", 24000))),
            debug=bool(config.get("HARNESS_DEBUG", False)),
            fast_model=str(config.get("LLM_FAST_MODEL", "") or "").strip(),
            strong_model=str(config.get("LLM_STRONG_MODEL", "") or "").strip(),
            fallback_models=tuple(
                model.strip()
                for model in str(config.get("LLM_FALLBACK_MODELS", "") or "").split(",")
                if model.strip()
            ),
            retry_backoff_seconds=max(0.0, float(config.get("HARNESS_RETRY_BACKOFF_SECONDS", 0.75))),
        )

    def budget(self, strict: bool) -> ExecutionBudget:
        # The configured value is the real ceiling. A hidden three-call cap made
        # legitimate drafting flows fail after research + one tool repair.
        return ExecutionBudget(self.max_llm_calls, self.max_tool_calls, self.max_retries, self.max_iterations)


def effective_mode(settings: HarnessSettings, complexity: str, legal_risk: str) -> HarnessMode:
    if settings.mode is not HarnessMode.ADAPTIVE:
        return settings.mode
    if complexity == "complex" or legal_risk == "high" or settings.profile.requires_scaffolding:
        return HarnessMode.STRICT
    return HarnessMode.STANDARD

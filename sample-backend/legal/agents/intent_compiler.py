import re
import unicodedata
from pathlib import Path
from typing import Any, Protocol

import yaml

from legal.domain.enums import RiskTier, TaskFamily
from legal.domain.models import IntakeIntent, WorkflowCandidate, normalize_decimal


class IntentModel(Protocol):
    provider: str
    model: str

    def compile(self, text: str) -> IntakeIntent | dict[str, Any]: ...


ALIASES_PATH = Path(__file__).resolve().parents[1] / "intake" / "aliases.v1.yaml"


def fold_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return re.sub(r"\s+", " ", "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )).strip()


class IntentCompiler:
    """Versioned exact rules first; a validated model may resolve only ambiguity."""

    def __init__(self, model: IntentModel | None = None, aliases_path: Path = ALIASES_PATH):
        self.model = model
        self.config = yaml.safe_load(aliases_path.read_text(encoding="utf-8"))

    def compile(self, text: str, declared_family: TaskFamily | str | None = None) -> IntakeIntent:
        family = TaskFamily(declared_family) if declared_family else None
        normalized = fold_text(text)
        matched = []
        for rule in self.config["resolution_subtypes"]:
            aliases = [fold_text(item) for item in rule["aliases"]]
            hits = [alias for alias in aliases if alias in normalized]
            if hits:
                matched.append((rule, hits))
        drafting = family == TaskFamily.RESOLUTION_DRAFTING or any(
            phrase in normalized for phrase in self.config["act_aliases"]["resolution"]
        ) or bool(matched)
        if not drafting:
            return IntakeIntent(
                task_family=family or TaskFamily.LEGAL_QUESTION,
                act_type="legal_question",
                subtype="generic",
                jurisdiction="lavalleja",
                known_facts=self._known_facts(text),
                classification_basis=[f"alias_config:{self.config['version']}", "declared_or_default_family"],
                clarification_required=False,
                classifier="deterministic",
                classifier_version=self.config["version"],
                risk_tier=RiskTier.MEDIUM,
            )

        if len(matched) == 1:
            rule, hits = matched[0]
            return self._deterministic_intent(text, rule, hits)

        model_error = None
        model_failure_kind = "unavailable"
        if self.model is not None:
            for _attempt in range(2):
                try:
                    candidate = IntakeIntent.model_validate(self.model.compile(text))
                    if candidate.classifier != "model" or not candidate.provider or not candidate.model:
                        raise ValueError("model output must identify classifier, provider and model")
                    return candidate
                except Exception as exc:
                    model_error = f"{type(exc).__name__}: {exc}"[:500]
                    if isinstance(exc, (ValueError, TypeError)):
                        model_failure_kind = "invalid_model_output"

        generic_rule = next(item for item in self.config["resolution_subtypes"] if item["subtype"] == "generic")
        status = model_failure_kind if self.model is not None else "deterministic"
        basis = [f"alias_config:{self.config['version']}"]
        if not matched:
            basis.append("no_exact_subtype_alias")
        else:
            basis.append("ambiguous_exact_aliases:" + ",".join(item[0]["subtype"] for item in matched))
        return IntakeIntent(
            task_family=TaskFamily.RESOLUTION_DRAFTING,
            act_type="resolution",
            subtype="generic",
            jurisdiction="lavalleja",
            requested_artifact="resolution_draft",
            known_facts=self._known_facts(text),
            unresolved_terms=[] if not matched else [item[0]["subtype"] for item in matched],
            workflow_candidates=[WorkflowCandidate(
                workflow_id=generic_rule["workflow_id"], version=generic_rule["workflow_version"],
                basis="fallback explícito por clasificación ambigua",
            )],
            selected_workflow_id=generic_rule["workflow_id"],
            selected_workflow_version=generic_rule["workflow_version"],
            classification_basis=basis,
            clarification_required=bool(matched),
            classifier=status,
            classifier_version=self.config["version"],
            provider=getattr(self.model, "provider", None) if self.model is not None else None,
            model=getattr(self.model, "model", None) if self.model is not None else None,
            error=model_error,
            risk_tier=RiskTier.HIGH,
        )

    def _deterministic_intent(self, text: str, rule: dict, hits: list[str]) -> IntakeIntent:
        return IntakeIntent(
            task_family=TaskFamily.RESOLUTION_DRAFTING,
            act_type="resolution",
            subtype=rule["subtype"],
            jurisdiction="lavalleja",
            requested_artifact="resolution_draft",
            known_facts=self._known_facts(text),
            workflow_candidates=[WorkflowCandidate(
                workflow_id=rule["workflow_id"], version=rule["workflow_version"],
                basis=f"regla exacta {self.config['version']}: {hits[0]}",
            )],
            selected_workflow_id=rule["workflow_id"],
            selected_workflow_version=rule["workflow_version"],
            classification_basis=[
                f"alias_config:{self.config['version']}",
                f"exact_alias:{hits[0]}",
            ],
            clarification_required=False,
            classifier="deterministic",
            classifier_version=self.config["version"],
            risk_tier=RiskTier.HIGH,
        )

    def _known_facts(self, text: str) -> dict[str, Any]:
        """Extract explicit labels and tightly bounded administrative expressions only."""
        facts: dict[str, Any] = {}
        folded_labels = {
            fold_text(alias): key
            for key, aliases in self.config.get("fact_labels", {}).items()
            for alias in aliases
        }
        if not folded_labels:
            return facts
        # Preserve original values while matching labels accent-insensitively line by line.
        for segment in re.split(r"[\n;]+", text):
            if ":" not in segment:
                continue
            label, value = segment.split(":", 1)
            key = folded_labels.get(fold_text(label))
            clean = value.strip()
            if key and clean:
                facts[key] = self._normalize_labelled_fact(key, clean)
        # Common unlabelled expediente form is exact enough to retain without inference.
        if "expediente" not in facts:
            match = re.search(r"\bexpediente\s+(?:n[º°o]\.?\s*)?([\w./-]+)", text, re.IGNORECASE)
            if match:
                facts["expediente"] = match.group(1)
        if "amount" not in facts:
            match = re.search(r"\$\s*([0-9][0-9.,]*)", text)
            if match:
                facts["amount"] = normalize_decimal(match.group(1))
        if "fiscal_year" not in facts:
            match = re.search(r"\bejercicio(?:\s+fiscal)?\s+(20\d{2}|21\d{2})\b", text, re.IGNORECASE)
            if match:
                facts["fiscal_year"] = int(match.group(1))
        transfer = re.search(
            r"\bdel\s+rubro\s+([A-Za-z0-9._/-]+)\s+al\s+rubro\s+([A-Za-z0-9._/-]+)",
            text, re.IGNORECASE,
        )
        if transfer:
            facts.setdefault("source_budget", {"identifier": transfer.group(1)})
            facts.setdefault("target_budget", {"identifier": transfer.group(2)})
        if "informe_hacienda" not in facts:
            report = self._hacienda_reference(text)
            if report:
                facts["informe_hacienda"] = report
        origin = facts.get("source_budget")
        destination = facts.get("target_budget")
        amount = facts.get("amount")
        if origin and destination and amount and "budget_transfers" not in facts:
            facts["budget_transfers"] = [{
                "origin": origin, "destination": destination, "amount": amount,
            }]
        return facts

    @staticmethod
    def _normalize_labelled_fact(key: str, value: str) -> Any:
        if key == "amount":
            return normalize_decimal(value.replace("$", ""))
        if key == "fiscal_year":
            return int(value) if re.fullmatch(r"\d{4}", value) else value
        if key in {"source_budget", "target_budget"}:
            return {"identifier": re.sub(r"^rubro\s+", "", value, flags=re.IGNORECASE).strip()}
        if key == "informe_hacienda":
            return IntentCompiler._hacienda_reference(value) or {
                "document_type": "informe_hacienda", "number": value,
                "issuer": "Hacienda",
            }
        return value

    @staticmethod
    def _hacienda_reference(value: str) -> dict[str, Any] | None:
        match = re.search(
            r"informe(?:\s+de)?\s+hacienda\s*(?:n\s*[.º°o]*\s*)?([0-9][0-9./-]*)",
            value, re.IGNORECASE,
        )
        if not match:
            number_only = re.fullmatch(r"(?:n\s*[.º°o]*\s*)?([0-9][0-9./-]*)", value.strip(), re.IGNORECASE)
            if not number_only:
                return None
            match = number_only
        return {
            "document_type": "informe_hacienda",
            "number": match.group(1).rstrip(".,;"),
            "issuer": "Hacienda",
        }

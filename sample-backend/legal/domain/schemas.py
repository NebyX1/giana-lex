from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from .enums import RiskTier, TaskFamily


class CreateCaseRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    task_family: TaskFamily = TaskFamily.LEGAL_QUESTION
    resolution_type: str | None = Field(default=None, max_length=120)
    jurisdiction: str = Field(default="lavalleja", min_length=1, max_length=120)
    risk_tier: RiskTier = RiskTier.LOW


class CancelWorkflowRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class SubmitFormRequest(BaseModel):
    form_id: str
    answers: dict = Field(default_factory=dict)
    partial: bool = False


class ConfirmFactsRequest(BaseModel):
    fact_ids: list[str] = Field(min_length=1)


class HumanReviewFinding(BaseModel):
    severity: Literal["info", "warning", "high", "critical"] = "high"
    category: str = Field(default="human_review", min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=4000)
    location: str | None = Field(default=None, max_length=500)
    suggested_action: str = Field(default="Corregir el borrador.", min_length=1, max_length=1000)
    blocks_output: bool = True


class HumanReviewRequest(BaseModel):
    draft_id: UUID
    draft_version: int = Field(ge=1)
    approved: bool
    findings: list[HumanReviewFinding]


class RejectMemoryRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)

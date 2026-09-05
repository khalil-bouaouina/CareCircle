"""Pydantic request/response models."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from brief_builder.contract import CATEGORIES, TASK_TYPES

Category = Literal["care", "communication", "routine", "observance", "safety"]
TaskType = Literal[
    "bathing",
    "dressing",
    "meal",
    "medication_support",
    "housekeeping",
    "nursing_visit",
    "transport",
    "companionship",
]
StatementStatus = Literal["active", "proposed", "rejected", "retired"]
Completion = Literal["yes", "partial", "no"]
Decision = Literal["approve", "reject"]

assert set(Category.__args__) == set(CATEGORIES)
assert set(TaskType.__args__) == set(TASK_TYPES)

_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _check_hhmm(value: str | None) -> str | None:
    if value is None:
        return None
    if not _HHMM.match(value):
        raise ValueError("time must be HH:MM")
    return value


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class _TimeWindowMixin(BaseModel):
    @field_validator("time_start", "time_end", check_fields=False)
    @classmethod
    def _validate_hhmm(cls, value: str | None) -> str | None:
        return _check_hhmm(value)


# --- elder / persons ---------------------------------------------------------


class ElderOut(ORMModel):
    id: int
    display_name: str
    primary_language: str
    capacity_mode: Literal["self", "assisted", "mandated"]


class PersonOut(ORMModel):
    id: int
    name: str
    role: Literal["primary_caregiver", "family", "worker"]
    language: str


# --- statements --------------------------------------------------------------


class StatementCreate(_TimeWindowMixin):
    statement: str = Field(min_length=3, max_length=500)
    category: Category
    applies_to_tasks: list[TaskType] = []
    excluded_tasks: list[TaskType] = []
    time_start: str | None = None
    time_end: str | None = None
    hidden_from: list[int] = []


class StatementUpdate(_TimeWindowMixin):
    statement: str | None = Field(default=None, min_length=3, max_length=500)
    category: Category | None = None
    applies_to_tasks: list[TaskType] | None = None
    excluded_tasks: list[TaskType] | None = None
    time_start: str | None = None
    time_end: str | None = None
    status: StatementStatus | None = None


class VisibilityUpdate(BaseModel):
    hidden_from: list[int]


class StatementOut(ORMModel):
    id: int
    statement: str
    category: str
    applies_to_tasks: list[str]
    excluded_tasks: list[str]
    time_start: str | None
    time_end: str | None
    hidden_from: list[int]
    status: str
    source_checkout_id: int | None
    created_at: datetime
    updated_at: datetime


# --- visits ------------------------------------------------------------------


class VisitCreate(BaseModel):
    worker_name: str = Field(min_length=1, max_length=120)
    worker_role: str = Field(min_length=1, max_length=64)
    worker_language: str = "fr"
    task_type: TaskType
    scheduled_start: datetime
    scheduled_end: datetime


class CheckoutOut(ORMModel):
    id: int
    completion: str
    observation_codes: list[str]
    note_text: str | None
    submitted_at: datetime


class VisitOut(ORMModel):
    id: int
    worker_name: str
    worker_role: str
    worker_language: str
    task_type: str
    scheduled_start: datetime
    scheduled_end: datetime
    token_expires_at: datetime | None
    state: str
    has_brief: bool = False
    checkout: CheckoutOut | None = None


class VisitCreated(BaseModel):
    visit: VisitOut
    token: str
    link: str


# --- worker surface ----------------------------------------------------------


class BriefLineOut(BaseModel):
    statement_id: int
    text: str
    critical: bool


class ObservationCodeOut(ORMModel):
    code: str
    label_en: str
    label_fr: str
    category: str


class BriefOut(BaseModel):
    elder_first_name: str
    task_type: str
    worker_name: str
    scheduled_start: datetime
    scheduled_end: datetime
    lines: list[BriefLineOut]
    fallback_used: bool
    model: str | None
    generated_at: datetime
    observation_codes: list[ObservationCodeOut]


class CheckoutIn(BaseModel):
    completion: Completion
    observation_codes: list[str] = []
    note_text: str | None = Field(default=None, max_length=2000)


class CheckoutAccepted(BaseModel):
    checkout_id: int
    visit_state: str
    proposal_created: bool


# --- proposals ---------------------------------------------------------------


class ProposalOut(ORMModel):
    id: int
    source_checkout_id: int | None
    suggested_statement: str
    status: str
    decided_by: str | None
    decided_at: datetime | None
    created_at: datetime


class ProposalDecision(BaseModel):
    decision: Decision
    category: Category | None = None  # optional override when approving


# --- access log --------------------------------------------------------------


class AccessLogOut(ORMModel):
    id: int
    actor_label: str
    action: str
    target_summary: str
    at: datetime
    sentence: str = ""


class ResetResult(BaseModel):
    ok: bool
    statements: int
    visits: int

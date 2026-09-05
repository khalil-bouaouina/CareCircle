"""Frozen dataclasses mirroring the tables (B4). No behaviour, just typed shapes.

``Actor`` and ``Purpose`` are not tables; they exist so ``resolve()`` has a
signature you can read.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


class _Row:
    @classmethod
    def from_row(cls, row: dict):
        names = cls.__dataclass_fields__  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in row.items() if k in names})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)  # type: ignore[call-overload]


@dataclass(frozen=True)
class Elder(_Row):
    id: int
    display_name: str
    primary_language: str
    capacity_mode: str  # self | assisted | mandated

    @property
    def first_name(self) -> str:
        return self.display_name.split()[0]


@dataclass(frozen=True)
class Person(_Row):
    id: int
    elder_id: int
    name: str
    role: str  # primary_caregiver | family | worker
    language: str


@dataclass(frozen=True)
class Statement(_Row):
    id: int
    elder_id: int
    statement: str
    category: str
    applies_to_tasks: list[str] = field(default_factory=list)
    excluded_tasks: list[str] = field(default_factory=list)
    time_start: str | None = None
    time_end: str | None = None
    hidden_from: list[int] = field(default_factory=list)
    status: str = "active"
    source_checkout_id: int | None = None
    created_at: str = ""
    updated_at: str = ""


@dataclass(frozen=True)
class Visit(_Row):
    id: int
    elder_id: int
    worker_name: str
    worker_role: str
    worker_language: str
    task_type: str
    scheduled_start: str  # ISO 8601
    scheduled_end: str
    token_hash: str | None
    token_valid_from: str | None
    token_expires_at: str | None
    state: str  # scheduled | briefed | completed | expired
    created_at: str = ""

    @property
    def start_hhmm(self) -> str:
        return self.scheduled_start[11:16]

    @property
    def end_hhmm(self) -> str:
        return self.scheduled_end[11:16]


@dataclass(frozen=True)
class BriefLine:
    statement_id: int
    text: str
    critical: bool


@dataclass(frozen=True)
class Brief(_Row):
    id: int
    visit_id: int
    selected_statement_ids: list[int]
    rendered_lines_json: list[dict]
    model: str | None
    generated_at: str
    fallback_used: bool

    @property
    def lines(self) -> list[BriefLine]:
        return [BriefLine(**line) for line in self.rendered_lines_json]


@dataclass(frozen=True)
class Checkout(_Row):
    id: int
    visit_id: int
    completion: str  # yes | partial | no
    observation_codes: list[str]
    note_text: str | None
    submitted_at: str


@dataclass(frozen=True)
class ObservationCode(_Row):
    code: str
    label_en: str
    label_fr: str
    category: str
    suggested_statement: str | None = None


@dataclass(frozen=True)
class Proposal(_Row):
    id: int
    elder_id: int
    source_checkout_id: int | None
    suggested_statement: str
    status: str  # pending | approved | rejected
    decided_by: str | None
    decided_at: str | None
    created_at: str


@dataclass(frozen=True)
class AccessEntry(_Row):
    id: int
    elder_id: int
    actor_label: str
    action: str
    target_summary: str
    at: str


@dataclass(frozen=True)
class UserAccount(_Row):
    id: int
    email: str
    password_hash: str
    name: str
    created_at: str


@dataclass(frozen=True)
class UserElderLink(_Row):
    user_id: int
    elder_id: int
    person_id: int | None
    role: str  # primary_caregiver | family | elder


# --- not tables ---------------------------------------------------------------


@dataclass(frozen=True)
class Actor:
    kind: str  # elder | person | worker
    person_id: int | None
    label: str  # what the elder reads in her access log


@dataclass(frozen=True)
class Purpose:
    task_type: str | None = None
    window_start: str | None = None  # "HH:MM"
    window_end: str | None = None

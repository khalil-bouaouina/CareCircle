"""Frozen dataclasses mirroring the tables (B5). No behaviour, just typed shapes
so functions have honest signatures.

``Actor``, ``Purpose``, ``Familiarity``, ``BriefLine`` and ``BriefResult`` are
not tables; they exist so services have readable signatures.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


class _Row:
    """Give every table-backed dataclass a ``from_row`` so repositories stay short."""

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
    role: str  # primary_caregiver | family


@dataclass(frozen=True)
class Worker(_Row):
    id: int
    name: str
    role: str
    language: str
    created_at: str = ""

    @property
    def first_name(self) -> str:
        return self.name.split()[0]


@dataclass(frozen=True)
class Statement(_Row):
    id: int
    elder_id: int
    statement: str
    kind: str  # preference | approach
    category: str
    source: str  # family | worker | correction
    applies_to_tasks: list[str] = field(default_factory=list)
    excluded_tasks: list[str] = field(default_factory=list)
    time_start: str | None = None
    time_end: str | None = None
    hidden_from: list[int] = field(default_factory=list)
    status: str = "active"
    origin_visit_id: int | None = None
    confirmations: int = 0
    source_checkout_id: int | None = None
    created_at: str = ""
    updated_at: str = ""


@dataclass(frozen=True)
class Visit(_Row):
    id: int
    elder_id: int
    worker_id: int
    task_type: str
    scheduled_start: str  # ISO 8601
    scheduled_end: str
    token_hash: str | None = None
    token_valid_from: str | None = None
    token_expires_at: str | None = None
    state: str = "scheduled"
    created_at: str = ""

    @property
    def start_hhmm(self) -> str:
        return self.scheduled_start[11:16]

    @property
    def end_hhmm(self) -> str:
        return self.scheduled_end[11:16]

    @property
    def date(self) -> str:
        return self.scheduled_start[:10]


@dataclass(frozen=True)
class BriefLine:
    statement_id: int
    text: str
    critical: bool = False
    is_correction: bool = False
    confirmations: int = 0


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
    handover_note: str | None
    submitted_at: str


@dataclass(frozen=True)
class Proposal(_Row):
    id: int
    elder_id: int
    source_checkout_id: int | None
    origin_kind: str  # handover | pattern | correction
    suggested_kind: str  # preference | approach
    suggested_statement: str
    status: str  # pending | accepted | rejected
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


@dataclass(frozen=True)
class Familiarity:
    visit_count: int
    last_visit_at: str | None
    is_first_visit: bool


@dataclass(frozen=True)
class BriefResult:
    """Six things, five of which the frontend reads. Hence a dataclass, not a tuple."""

    lines: list[BriefLine]
    fallback_used: bool
    note_count: int
    contributor_count: int
    changed_count: int
    is_first_visit: bool

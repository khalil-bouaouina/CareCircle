"""The contract between the backend (Person A) and the brief builder (Person C).

This file is the only thing both sides import from each other. Changes here
must be announced out loud (see codebase-and-tasks.md, Part 5).

Guarantees
----------
Person A guarantees: the statements passed to ``build_brief`` are ALREADY
consent-filtered by the visibility resolver. Hidden rows never reach this
function.

Person C guarantees: every ``BriefLine.statement_id`` returned appears in the
input ``statements`` list. The model selects; it never writes and never invents.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Closed lists (architecture.md section 4). Closed lists are what make scoping
# tractable; an open text field would push filtering onto the model.
# ---------------------------------------------------------------------------

TASK_TYPES: tuple[str, ...] = (
    "bathing",
    "dressing",
    "meal",
    "medication_support",
    "housekeeping",
    "nursing_visit",
    "transport",
    "companionship",
)

CATEGORIES: tuple[str, ...] = (
    "care",
    "communication",
    "routine",
    "observance",
    "safety",
)

MAX_BRIEF_LINES = 6


# ---------------------------------------------------------------------------
# Data passed across the boundary
# ---------------------------------------------------------------------------


@dataclass
class Statement:
    id: int
    statement: str
    category: str  # care|communication|routine|observance|safety
    applies_to_tasks: list[str] = field(default_factory=list)  # empty = all tasks
    excluded_tasks: list[str] = field(default_factory=list)
    time_start: str | None = None  # "13:00"
    time_end: str | None = None


@dataclass
class VisitContext:
    task_type: str
    scheduled_start: str  # "10:00"
    scheduled_end: str
    worker_role: str
    worker_language: str


@dataclass
class BriefLine:
    statement_id: int
    text: str
    critical: bool


@dataclass
class BriefResult:
    lines: list[BriefLine]
    fallback_used: bool
    model: str | None


# ---------------------------------------------------------------------------
# The two entry points
# ---------------------------------------------------------------------------


def build_brief(
    statements: list[Statement],
    visit: VisitContext,
) -> BriefResult:
    """Three-stage pipeline: scope filter -> model selection -> validation.

    Falls back to a deterministic render if the model is unavailable or its
    output is unusable. Never raises because of the model.
    """
    raise NotImplementedError("implemented in Part 3")


def suggest_statement(
    observation_codes: list[str],
    note_text: str | None,
    recent_checkouts: list[dict],
) -> str | None:
    """Returns a suggested statement, or None if nothing durable."""
    raise NotImplementedError("implemented in Part 3")

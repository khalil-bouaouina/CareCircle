"""Stage 1 -- deterministic task and time scoping.

Plain code, no model. This mirrors the WHERE clause in architecture.md
section 5. The backend resolver applies the same filter at the database
level; this is the in-package copy so the package can be tested from
fixtures alone and so the guarantee holds even if a caller forgets.
"""

from __future__ import annotations

from .contract import Statement, VisitContext

MINUTES_PER_DAY = 24 * 60


def _to_minutes(hhmm: str) -> int:
    hours, minutes = hhmm.strip().split(":")
    return int(hours) * 60 + int(minutes)


def _intervals(start: int, end: int) -> list[tuple[int, int]]:
    """Return half-open intervals for a window, splitting if it wraps midnight."""
    if start == end:
        return [(0, MINUTES_PER_DAY)]  # degenerate: treat as the whole day
    if start < end:
        return [(start, end)]
    return [(start, MINUTES_PER_DAY), (0, end)]


def windows_overlap(
    a_start: str, a_end: str, b_start: str, b_end: str
) -> bool:
    """True if the two "HH:MM" windows share at least one minute."""
    a = _intervals(_to_minutes(a_start), _to_minutes(a_end))
    b = _intervals(_to_minutes(b_start), _to_minutes(b_end))
    return any(s1 < e2 and s2 < e1 for (s1, e1) in a for (s2, e2) in b)


def task_applies(statement: Statement, task_type: str) -> bool:
    if task_type in statement.excluded_tasks:
        return False
    if statement.applies_to_tasks and task_type not in statement.applies_to_tasks:
        return False
    return True


def time_applies(statement: Statement, visit: VisitContext) -> bool:
    if statement.time_start is None or statement.time_end is None:
        return True
    return windows_overlap(
        statement.time_start,
        statement.time_end,
        visit.scheduled_start,
        visit.scheduled_end,
    )


def filter_scope(statements: list[Statement], visit: VisitContext) -> list[Statement]:
    """Return the statements relevant to this visit's task and time window.

    Order is preserved. Consent (``hidden_from``) is NOT applied here -- that
    belongs to the resolver, which runs before this package is ever called.
    """
    return [
        s
        for s in statements
        if task_applies(s, visit.task_type) and time_applies(s, visit)
    ]

"""How much this worker already knows (B15).

Two functions, both nearly pure, which matters because the whole delta-brief
behaviour rests on them.
"""

from __future__ import annotations

from ..models import Familiarity, Statement
from ..repositories import visits


def assess(elder_id: int, worker_id: int) -> Familiarity:
    visit_count = visits.count_visits_by_worker(elder_id, worker_id)
    return Familiarity(
        visit_count=visit_count,
        last_visit_at=visits.last_completed_visit_at(elder_id, worker_id),
        is_first_visit=visit_count == 0,
    )


def changed_since(statements: list[Statement], since: str | None) -> set[int]:
    """Ids of statements whose ``updated_at`` is later than ``since``.
    Everything is new when ``since`` is None."""
    if since is None:
        return {s.id for s in statements}
    return {s.id for s in statements if s.updated_at > since}

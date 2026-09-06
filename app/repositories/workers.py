"""worker (B7). Turnover is the problem; workers are rows, not strings."""

from __future__ import annotations

from ..db import execute, now_iso, query, query_one
from ..models import Worker


def create_worker(name: str, role: str, language: str, worker_id: int | None = None) -> int:
    return execute(
        "INSERT INTO worker (id, name, role, language, created_at) VALUES (?, ?, ?, ?, ?)",
        (worker_id, name.strip(), role.strip(), language, now_iso()),
    )


def get_worker(worker_id: int) -> Worker | None:
    row = query_one("SELECT * FROM worker WHERE id = ?", (worker_id,))
    return Worker.from_row(row) if row else None


def list_workers_for_elder(elder_id: int) -> list[tuple[Worker, int]]:
    """Each worker plus their visit count with this elder. Powers the select on
    the visits screen."""
    rows = query(
        """SELECT w.*, COUNT(v.id) AS visit_count
             FROM worker w
             LEFT JOIN visit v ON v.worker_id = w.id AND v.elder_id = ?
            GROUP BY w.id
            ORDER BY visit_count DESC, w.name""",
        (elder_id,),
    )
    return [(Worker.from_row(r), int(r["visit_count"])) for r in rows]


def count_contributing_workers(elder_id: int) -> int:
    """Distinct workers who authored at least one active statement, via
    ``origin_visit_id``. This is the "6 previous workers" number."""
    row = query_one(
        """SELECT COUNT(DISTINCT v.worker_id) AS n
             FROM preference_statement s
             JOIN visit v ON v.id = s.origin_visit_id
            WHERE s.elder_id = ? AND s.status = 'active'""",
        (elder_id,),
    )
    return int(row["n"]) if row else 0

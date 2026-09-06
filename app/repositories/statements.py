"""preference_statement (B8).

READS of statement data for any surface go through ``services.visibility.resolve``;
``list_statements`` is its data source and must not be called from a route.

Every write path sets ``updated_at``. The delta brief is only as good as this field.
"""

from __future__ import annotations

from ..db import _dump, _load_json, execute, now_iso, query, query_one
from ..models import Statement

_JSON = ("applies_to_tasks", "excluded_tasks", "hidden_from")


def _row(row: dict | None) -> Statement | None:
    return Statement.from_row(_load_json(row, *_JSON)) if row else None


def create_statement(
    elder_id: int,
    statement: str,
    kind: str,
    category: str,
    source: str,
    applies_to_tasks: list[str] | None = None,
    excluded_tasks: list[str] | None = None,
    time_start: str | None = None,
    time_end: str | None = None,
    hidden_from: list[int] | None = None,
    status: str = "active",
    origin_visit_id: int | None = None,
    source_checkout_id: int | None = None,
    confirmations: int = 0,
    statement_id: int | None = None,
    created_at: str | None = None,
    updated_at: str | None = None,
) -> int:
    created = created_at or now_iso()
    updated = updated_at or created
    return execute(
        """INSERT INTO preference_statement
           (id, elder_id, statement, kind, category, source,
            applies_to_tasks, excluded_tasks, time_start, time_end, hidden_from,
            status, origin_visit_id, confirmations, source_checkout_id, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            statement_id, elder_id, statement, kind, category, source,
            _dump(applies_to_tasks), _dump(excluded_tasks), time_start, time_end,
            _dump(sorted(set(hidden_from or []))),
            status, origin_visit_id, confirmations, source_checkout_id, created, updated,
        ),
    )


def get_statement(statement_id: int) -> Statement | None:
    return _row(query_one("SELECT * FROM preference_statement WHERE id = ?", (statement_id,)))


def list_statements(elder_id: int, status: str = "active", kind: str | None = None) -> list[Statement]:
    """Ordered by category, then id, so pages are stable between loads."""
    sql = "SELECT * FROM preference_statement WHERE elder_id = ? AND status = ?"
    params: tuple = (elder_id, status)
    if kind is not None:
        sql += " AND kind = ?"
        params += (kind,)
    return [_row(r) for r in query(sql + " ORDER BY category, id", params)]


def set_hidden_from(statement_id: int, person_ids: list[int]) -> None:
    execute(
        "UPDATE preference_statement SET hidden_from = ?, updated_at = ? WHERE id = ?",
        (_dump(sorted(set(person_ids))), now_iso(), statement_id),
    )


def set_status(statement_id: int, status: str) -> None:
    execute(
        "UPDATE preference_statement SET status = ?, updated_at = ? WHERE id = ?",
        (status, now_iso(), statement_id),
    )


def increment_confirmations(statement_id: int) -> None:
    execute(
        "UPDATE preference_statement SET confirmations = confirmations + 1, updated_at = ? WHERE id = ?",
        (now_iso(), statement_id),
    )


def count_active(elder_id: int) -> int:
    """Exists solely for the continuity counter, and earns its place there."""
    row = query_one(
        "SELECT COUNT(*) AS n FROM preference_statement WHERE elder_id = ? AND status = 'active'",
        (elder_id,),
    )
    return int(row["n"]) if row else 0

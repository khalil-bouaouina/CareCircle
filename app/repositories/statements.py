"""preference_statement. READS of statement data for any surface go through
``services.visibility.resolve``; the list function here is its data source and
must not be called from a route."""

from __future__ import annotations

from ..db import _dump, _load_json, execute, now_iso, query, query_one
from ..models import Statement

_JSON = ("applies_to_tasks", "excluded_tasks", "hidden_from")


def _row(row: dict | None) -> Statement | None:
    return Statement.from_row(_load_json(row, *_JSON)) if row else None


def create_statement(
    elder_id: int,
    statement: str,
    category: str,
    applies_to_tasks: list[str],
    excluded_tasks: list[str],
    time_start: str | None,
    time_end: str | None,
    hidden_from: list[int] | None = None,
    status: str = "active",
    source_checkout_id: int | None = None,
    statement_id: int | None = None,
) -> int:
    now = now_iso()
    return execute(
        """INSERT INTO preference_statement
           (id, elder_id, statement, category, applies_to_tasks, excluded_tasks,
            time_start, time_end, hidden_from, status, source_checkout_id, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            statement_id,
            elder_id,
            statement,
            category,
            _dump(applies_to_tasks),
            _dump(excluded_tasks),
            time_start,
            time_end,
            _dump(sorted(set(hidden_from or []))),
            status,
            source_checkout_id,
            now,
            now,
        ),
    )


def get_statement(statement_id: int) -> Statement | None:
    return _row(query_one("SELECT * FROM preference_statement WHERE id = ?", (statement_id,)))


def list_statements(elder_id: int, status: str = "active") -> list[Statement]:
    """Ordered by category, then id, so pages are stable."""
    rows = query(
        "SELECT * FROM preference_statement WHERE elder_id = ? AND status = ? ORDER BY category, id",
        (elder_id, status),
    )
    return [_row(r) for r in rows]


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


def count_active(elder_id: int) -> int:
    """Exists solely for the "6 of 31 notes" footer."""
    row = query_one(
        "SELECT COUNT(*) AS n FROM preference_statement WHERE elder_id = ? AND status = 'active'",
        (elder_id,),
    )
    return int(row["n"]) if row else 0

from __future__ import annotations

from ..db import _dump, _load_json, execute, now_iso, query, query_one
from ..models import Brief, BriefLine, Visit


def _visit(row: dict | None) -> Visit | None:
    return Visit.from_row(row) if row else None


def create_visit(
    elder_id: int,
    worker_name: str,
    worker_role: str,
    worker_language: str,
    task_type: str,
    scheduled_start: str,
    scheduled_end: str,
    token_hash: str | None,
    token_valid_from: str | None,
    token_expires_at: str | None,
    state: str = "scheduled",
    visit_id: int | None = None,
) -> int:
    return execute(
        """INSERT INTO visit
           (id, elder_id, worker_name, worker_role, worker_language, task_type,
            scheduled_start, scheduled_end, token_hash, token_valid_from, token_expires_at, state, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            visit_id,
            elder_id,
            worker_name,
            worker_role,
            worker_language,
            task_type,
            scheduled_start,
            scheduled_end,
            token_hash,
            token_valid_from,
            token_expires_at,
            state,
            now_iso(),
        ),
    )


def get_visit(visit_id: int) -> Visit | None:
    return _visit(query_one("SELECT * FROM visit WHERE id = ?", (visit_id,)))


def get_visit_by_token_hash(token_hash: str) -> Visit | None:
    return _visit(query_one("SELECT * FROM visit WHERE token_hash = ?", (token_hash,)))


def list_visits(elder_id: int) -> list[Visit]:
    rows = query("SELECT * FROM visit WHERE elder_id = ? ORDER BY scheduled_start DESC, id DESC", (elder_id,))
    return [_visit(r) for r in rows]


def set_state(visit_id: int, state: str) -> None:
    execute("UPDATE visit SET state = ? WHERE id = ?", (state, visit_id))


def latest_scheduled(elder_id: int) -> Visit | None:
    """For the demo role picker."""
    return _visit(
        query_one(
            "SELECT * FROM visit WHERE elder_id = ? AND state = 'scheduled' ORDER BY scheduled_start DESC LIMIT 1",
            (elder_id,),
        )
    )


def list_live_past_window(now_iso_: str) -> list[Visit]:
    """Visits still scheduled/briefed whose token window has passed."""
    rows = query(
        "SELECT * FROM visit WHERE state IN ('scheduled', 'briefed') AND token_expires_at < ?",
        (now_iso_,),
    )
    return [_visit(r) for r in rows]


def count_visits(elder_id: int) -> int:
    row = query_one("SELECT COUNT(*) AS n FROM visit WHERE elder_id = ?", (elder_id,))
    return int(row["n"]) if row else 0


# --- brief cache --------------------------------------------------------------


def save_brief(
    visit_id: int,
    statement_ids: list[int],
    lines: list[BriefLine],
    model: str | None,
    fallback_used: bool,
) -> None:
    execute(
        """INSERT INTO brief (visit_id, selected_statement_ids, rendered_lines_json, model, generated_at, fallback_used)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(visit_id) DO UPDATE SET
             selected_statement_ids = excluded.selected_statement_ids,
             rendered_lines_json = excluded.rendered_lines_json,
             model = excluded.model,
             generated_at = excluded.generated_at,
             fallback_used = excluded.fallback_used""",
        (
            visit_id,
            _dump(statement_ids),
            _dump([line.__dict__ for line in lines]),
            model,
            now_iso(),
            1 if fallback_used else 0,
        ),
    )


def get_brief(visit_id: int) -> Brief | None:
    row = query_one("SELECT * FROM brief WHERE visit_id = ?", (visit_id,))
    if not row:
        return None
    _load_json(row, "selected_statement_ids", "rendered_lines_json")
    row["fallback_used"] = bool(row["fallback_used"])
    return Brief.from_row(row)

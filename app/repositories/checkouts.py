"""checkout (B10) -- append-only. There is deliberately no update or delete here."""

from __future__ import annotations

from ..db import _dump, _load_json, execute, now_iso, query, query_one
from ..models import Checkout


def _row(row: dict | None) -> Checkout | None:
    return Checkout.from_row(_load_json(row, "observation_codes")) if row else None


def create_checkout(
    visit_id: int,
    completion: str,
    observation_codes: list[str],
    note_text: str | None,
    handover_note: str | None,
    submitted_at: str | None = None,
    checkout_id: int | None = None,
) -> int:
    return execute(
        """INSERT INTO checkout
             (id, visit_id, completion, observation_codes, note_text, handover_note, submitted_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (checkout_id, visit_id, completion, _dump(list(dict.fromkeys(observation_codes))),
         (note_text or "").strip() or None, (handover_note or "").strip() or None,
         submitted_at or now_iso()),
    )


def get_checkout(checkout_id: int) -> Checkout | None:
    return _row(query_one("SELECT * FROM checkout WHERE id = ?", (checkout_id,)))


def get_checkout_for_visit(visit_id: int) -> Checkout | None:
    return _row(query_one("SELECT * FROM checkout WHERE visit_id = ?", (visit_id,)))


def list_checkouts(elder_id: int, limit: int = 20) -> list[Checkout]:
    """Joins visit to filter by elder. Newest first."""
    rows = query(
        """SELECT c.* FROM checkout c JOIN visit v ON v.id = c.visit_id
            WHERE v.elder_id = ? ORDER BY c.submitted_at DESC, c.id DESC LIMIT ?""",
        (elder_id, limit),
    )
    return [_row(r) for r in rows]


def count_code_occurrences(elder_id: int, code: str, last_n: int = 5) -> int:
    """How many of the most recent ``last_n`` check-outs carry ``code``.
    Drives pattern detection."""
    return sum(1 for c in list_checkouts(elder_id, limit=last_n) if code in c.observation_codes)

"""proposed_update (B11)."""

from __future__ import annotations

from ..db import execute, now_iso, query, query_one
from ..models import Proposal


def _row(row: dict | None) -> Proposal | None:
    return Proposal.from_row(row) if row else None


def create_proposal(
    elder_id: int,
    source_checkout_id: int | None,
    origin_kind: str,
    suggested_kind: str,
    suggested_statement: str,
    status: str = "pending",
    proposal_id: int | None = None,
) -> int:
    return execute(
        """INSERT INTO proposed_update
             (id, elder_id, source_checkout_id, origin_kind, suggested_kind,
              suggested_statement, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (proposal_id, elder_id, source_checkout_id, origin_kind, suggested_kind,
         suggested_statement.strip(), status, now_iso()),
    )


def list_pending(elder_id: int) -> list[Proposal]:
    rows = query(
        """SELECT * FROM proposed_update WHERE elder_id = ? AND status = 'pending'
            ORDER BY created_at DESC, id DESC""",
        (elder_id,),
    )
    return [_row(r) for r in rows]


def get_proposal(proposal_id: int) -> Proposal | None:
    return _row(query_one("SELECT * FROM proposed_update WHERE id = ?", (proposal_id,)))


def decide(proposal_id: int, status: str, decided_by: str) -> None:
    execute(
        "UPDATE proposed_update SET status = ?, decided_by = ?, decided_at = ? WHERE id = ?",
        (status, decided_by, now_iso(), proposal_id),
    )


def exists_pending_like(elder_id: int, suggested_statement: str) -> bool:
    """Cheap duplicate guard -- exact match is sufficient."""
    row = query_one(
        """SELECT 1 AS x FROM proposed_update
            WHERE elder_id = ? AND status = 'pending' AND suggested_statement = ?""",
        (elder_id, suggested_statement.strip()),
    )
    return row is not None

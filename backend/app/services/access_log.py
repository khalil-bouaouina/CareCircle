"""Append-only access log writer. Rows are never edited or deleted (P3)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AccessLog


def record(
    db: Session,
    elder_id: int,
    actor_label: str,
    action: str,
    target_summary: str,
    *,
    commit: bool = True,
) -> AccessLog:
    row = AccessLog(
        elder_id=elder_id,
        actor_label=actor_label,
        action=action,
        target_summary=target_summary,
        at=datetime.now().replace(microsecond=0),
    )
    db.add(row)
    if commit:
        db.commit()
    return row


def list_for_elder(db: Session, elder_id: int, limit: int = 200) -> list[AccessLog]:
    return list(
        db.scalars(
            select(AccessLog)
            .where(AccessLog.elder_id == elder_id)
            .order_by(AccessLog.at.desc(), AccessLog.id.desc())
            .limit(limit)
        )
    )


_VERBS = {
    "view": "viewed",
    "brief": "was briefed on",
    "export": "exported",
    "approved_proposal": "approved",
    "rejected_proposal": "rejected",
    "visibility_change": "changed who can see",
}


def to_sentence(row: AccessLog) -> str:
    """'Marie-Ève viewed your bathing preferences at 9:52'."""
    verb = _VERBS.get(row.action, row.action.replace("_", " "))
    when = f"{row.at.hour}:{row.at.minute:02d}"
    return f"{row.actor_label} {verb} {row.target_summary} at {when}"

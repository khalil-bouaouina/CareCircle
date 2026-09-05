"""Check-out ingestion. Rows are append-only (P3)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Checkout, ObservationCode, Visit
from ..schemas import CheckoutIn


def known_codes(db: Session) -> set[str]:
    return set(db.scalars(select(ObservationCode.code)))


def append(db: Session, visit: Visit, data: CheckoutIn) -> Checkout:
    row = Checkout(
        visit_id=visit.id,
        completion=data.completion,
        observation_codes=list(dict.fromkeys(data.observation_codes)),
        note_text=(data.note_text or None),
        submitted_at=datetime.now().replace(microsecond=0),
    )
    db.add(row)
    db.flush()
    return row


def recent_for_elder(db: Session, elder_id: int, *, exclude_id: int | None = None, limit: int = 10) -> list[dict]:
    """Most recent check-outs for this elder, as plain dicts for ``suggest_statement``."""
    query = (
        select(Checkout)
        .join(Visit, Visit.id == Checkout.visit_id)
        .where(Visit.elder_id == elder_id)
        .order_by(Checkout.submitted_at.desc(), Checkout.id.desc())
        .limit(limit + 1)
    )
    rows = [c for c in db.scalars(query) if c.id != exclude_id][:limit]
    return [
        {
            "checkout_id": c.id,
            "visit_id": c.visit_id,
            "task_type": c.visit.task_type,
            "completion": c.completion,
            "observation_codes": list(c.observation_codes or []),
            "note_text": c.note_text,
            "submitted_at": c.submitted_at.isoformat(),
        }
        for c in rows
    ]

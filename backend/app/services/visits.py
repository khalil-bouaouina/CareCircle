"""Visit creation and the state machine: scheduled -> briefed -> completed -> expired."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Visit
from ..schemas import VisitCreate
from ..security import tokens

TRANSITIONS: dict[str, set[str]] = {
    "scheduled": {"briefed", "expired"},
    "briefed": {"completed", "expired"},
    "completed": set(),
    "expired": set(),
}


class IllegalTransition(Exception):
    pass


def create_visit(db: Session, elder_id: int, data: VisitCreate) -> tuple[Visit, str]:
    """Create a visit and return (visit, raw_token). The raw token is never stored."""
    if data.scheduled_end <= data.scheduled_start:
        raise ValueError("scheduled_end must be after scheduled_start")
    raw = tokens.generate()
    _, expires_at = tokens.window(data.scheduled_start, data.scheduled_end)
    visit = Visit(
        elder_id=elder_id,
        worker_name=data.worker_name,
        worker_role=data.worker_role,
        worker_language=data.worker_language,
        task_type=data.task_type,
        scheduled_start=data.scheduled_start,
        scheduled_end=data.scheduled_end,
        token_hash=tokens.hash_token(raw),
        token_expires_at=expires_at,
        state="scheduled",
    )
    db.add(visit)
    db.commit()
    db.refresh(visit)
    return visit, raw


def transition(db: Session, visit: Visit, to: str, *, commit: bool = True) -> Visit:
    if to not in TRANSITIONS.get(visit.state, set()):
        raise IllegalTransition(f"{visit.state} -> {to}")
    visit.state = to
    if commit:
        db.commit()
    return visit


def burn_token(db: Session, visit: Visit, *, commit: bool = True) -> None:
    visit.token_hash = None
    if commit:
        db.commit()


def expire_stale(db: Session, now: datetime | None = None) -> int:
    """Sweep: any live visit whose window has passed becomes expired. Returns count."""
    now = now or datetime.now()
    stale = db.scalars(
        select(Visit).where(Visit.state.in_(["scheduled", "briefed"]), Visit.token_expires_at < now)
    ).all()
    for visit in stale:
        visit.state = "expired"
        visit.token_hash = None
    if stale:
        db.commit()
    return len(stale)


def list_visits(db: Session, elder_id: int) -> list[Visit]:
    return list(
        db.scalars(
            select(Visit).where(Visit.elder_id == elder_id).order_by(Visit.scheduled_start.desc())
        )
    )


def get_visit(db: Session, elder_id: int, visit_id: int) -> Visit | None:
    visit = db.get(Visit, visit_id)
    if visit is None or visit.elder_id != elder_id:
        return None
    return visit

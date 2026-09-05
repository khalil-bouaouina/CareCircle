"""Write side of preference statements. All READS go through the resolver."""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import PreferenceStatement
from ..schemas import StatementCreate, StatementUpdate


def create(db: Session, elder_id: int, data: StatementCreate) -> PreferenceStatement:
    row = PreferenceStatement(elder_id=elder_id, status="active", **data.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_for_write(db: Session, elder_id: int, statement_id: int) -> PreferenceStatement | None:
    """Primary-key lookup used only to mutate a row; not a read surface."""
    row = db.get(PreferenceStatement, statement_id)
    if row is None or row.elder_id != elder_id:
        return None
    return row


def update(db: Session, row: PreferenceStatement, data: StatementUpdate) -> PreferenceStatement:
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row


def set_visibility(db: Session, row: PreferenceStatement, hidden_from: list[int]) -> PreferenceStatement:
    row.hidden_from = sorted(set(hidden_from))
    db.commit()
    db.refresh(row)
    return row

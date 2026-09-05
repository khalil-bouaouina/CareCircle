"""Elder view API (architecture.md section 9, "Elder"). Large-type UI, her own record."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import schemas
from ..db import get_db
from ..deps import Session_, elder_session
from ..security.resolver import Purpose, resolve
from ..services import access_log
from ..services import proposals as proposal_service
from ..services import statements as statement_service

router = APIRouter(prefix="/me", tags=["elder"])


@router.get("/statements", response_model=list[schemas.StatementOut])
def my_statements(session: Session_ = Depends(elder_session), db: Session = Depends(get_db)):
    """The elder sees everything about herself, including retired and proposed rows."""
    return resolve(db, session.elder.id, session.actor, Purpose.view(), include_inactive=True)


@router.patch("/statements/{statement_id}/visibility", response_model=schemas.StatementOut)
def set_visibility(
    statement_id: int,
    data: schemas.VisibilityUpdate,
    session: Session_ = Depends(elder_session),
    db: Session = Depends(get_db),
):
    row = statement_service.get_for_write(db, session.elder.id, statement_id)
    if row is None:
        raise HTTPException(404, "Statement not found")
    row = statement_service.set_visibility(db, row, data.hidden_from)
    access_log.record(
        db,
        session.elder.id,
        actor_label=session.actor.label,
        action="visibility_change",
        target_summary=f'"{row.statement[:50]}"',
    )
    return row


@router.get("/access-log", response_model=list[schemas.AccessLogOut])
def my_access_log(session: Session_ = Depends(elder_session), db: Session = Depends(get_db)):
    rows = access_log.list_for_elder(db, session.elder.id)
    out = []
    for row in rows:
        item = schemas.AccessLogOut.model_validate(row)
        item.sentence = access_log.to_sentence(row)
        out.append(item)
    return out


@router.get("/proposals", response_model=list[schemas.ProposalOut])
def my_proposals(
    status: str | None = "pending",
    session: Session_ = Depends(elder_session),
    db: Session = Depends(get_db),
):
    return proposal_service.list_for_elder(db, session.elder.id, status or None)

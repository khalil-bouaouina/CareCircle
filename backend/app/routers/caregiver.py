"""Caregiver console API (architecture.md section 9, "Caregiver").

Family members (role=family) can read; only the primary caregiver can write.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import schemas
from ..config import settings
from ..db import get_db
from ..deps import Session_, caregiver_session, current_session, person_session
from ..models import Person
from ..security.resolver import Purpose, resolve
from ..services import proposals as proposal_service
from ..services import statements as statement_service
from ..services import visits as visit_service

router = APIRouter(tags=["caregiver"])


def _visit_out(visit) -> schemas.VisitOut:
    out = schemas.VisitOut.model_validate(visit)
    out.has_brief = visit.brief is not None
    return out


# --- people (so the UI knows ids for hidden_from) ----------------------------


@router.get("/persons", response_model=list[schemas.PersonOut])
def list_persons(session: Session_ = Depends(current_session), db: Session = Depends(get_db)):
    return list(db.scalars(select(Person).where(Person.elder_id == session.elder.id).order_by(Person.id)))


# --- statements --------------------------------------------------------------


@router.get("/statements", response_model=list[schemas.StatementOut])
def list_statements(session: Session_ = Depends(person_session), db: Session = Depends(get_db)):
    return resolve(db, session.elder.id, session.actor, Purpose.view())


@router.post("/statements", response_model=schemas.StatementOut, status_code=201)
def create_statement(
    data: schemas.StatementCreate,
    session: Session_ = Depends(caregiver_session),
    db: Session = Depends(get_db),
):
    if (data.time_start is None) != (data.time_end is None):
        raise HTTPException(422, "time_start and time_end must be set together")
    return statement_service.create(db, session.elder.id, data)


@router.patch("/statements/{statement_id}", response_model=schemas.StatementOut)
def update_statement(
    statement_id: int,
    data: schemas.StatementUpdate,
    session: Session_ = Depends(caregiver_session),
    db: Session = Depends(get_db),
):
    row = statement_service.get_for_write(db, session.elder.id, statement_id)
    if row is None:
        raise HTTPException(404, "Statement not found")
    return statement_service.update(db, row, data)


# --- visits ------------------------------------------------------------------


@router.post("/visits", response_model=schemas.VisitCreated, status_code=201)
def create_visit(
    data: schemas.VisitCreate,
    session: Session_ = Depends(caregiver_session),
    db: Session = Depends(get_db),
):
    try:
        visit, raw_token = visit_service.create_visit(db, session.elder.id, data)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    link = f"{settings.frontend_base_url.rstrip('/')}/v/{raw_token}"
    return schemas.VisitCreated(visit=_visit_out(visit), token=raw_token, link=link)


@router.get("/visits", response_model=list[schemas.VisitOut])
def list_visits(session: Session_ = Depends(person_session), db: Session = Depends(get_db)):
    visit_service.expire_stale(db)
    return [_visit_out(v) for v in visit_service.list_visits(db, session.elder.id)]


@router.get("/visits/{visit_id}", response_model=schemas.VisitOut)
def get_visit(visit_id: int, session: Session_ = Depends(person_session), db: Session = Depends(get_db)):
    visit_service.expire_stale(db)
    visit = visit_service.get_visit(db, session.elder.id, visit_id)
    if visit is None:
        raise HTTPException(404, "Visit not found")
    return _visit_out(visit)


# --- proposals ---------------------------------------------------------------


@router.get("/proposals", response_model=list[schemas.ProposalOut])
def list_proposals(
    status: str | None = "pending",
    session: Session_ = Depends(current_session),
    db: Session = Depends(get_db),
):
    return proposal_service.list_for_elder(db, session.elder.id, status or None)


@router.post("/proposals/{proposal_id}/decide", response_model=schemas.ProposalOut)
def decide_proposal(
    proposal_id: int,
    data: schemas.ProposalDecision,
    session: Session_ = Depends(current_session),
    db: Session = Depends(get_db),
):
    """Shared by the elder and the caregiver; who may decide depends on capacity_mode."""
    proposal = proposal_service.get(db, session.elder.id, proposal_id)
    if proposal is None:
        raise HTTPException(404, "Proposal not found")
    try:
        proposal, _ = proposal_service.decide(
            db, session.elder, proposal, session.actor, session.role, data.decision, data.category
        )
    except proposal_service.NotAllowed as exc:
        raise HTTPException(403, exc.detail) from exc
    return proposal

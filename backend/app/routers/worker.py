"""Worker API -- the only token-scoped router. Two endpoints; that is the whole
surface a stranger can reach (architecture.md section 9).

Ordering in GET /v/{token} is load-bearing: the resolver (consent gate) runs
BEFORE build_brief. Hidden statements never reach the brief builder, and so
never reach any model behind it.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from brief_builder import BriefLine, VisitContext, build_brief, suggest_statement

from .. import schemas
from ..db import get_db
from ..models import Brief, Elder, ObservationCode, Person, Visit
from ..security import tokens
from ..security.resolver import Actor, Purpose, resolve, to_contract
from ..services import checkouts as checkout_service
from ..services import proposals as proposal_service
from ..services import visits as visit_service

router = APIRouter(prefix="/v", tags=["worker"])


def _visit_for(token: str, db: Session) -> Visit:
    try:
        return tokens.validate(db, token)
    except tokens.TokenError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc


def _worker_actor(db: Session, visit: Visit) -> Actor:
    """Workers hold no account; if a Person row with the same name exists we use
    its id so per-person ``hidden_from`` applies, otherwise they are anonymous."""
    person = db.scalar(
        select(Person).where(
            Person.elder_id == visit.elder_id, Person.role == "worker", Person.name == visit.worker_name
        )
    )
    return Actor.worker(visit.worker_name, person.id if person else None)


def _generate_brief(db: Session, visit: Visit) -> Brief:
    # 1. consent gate -- the resolver. Runs first. Writes the access-log row.
    rows = resolve(
        db,
        visit.elder_id,
        _worker_actor(db, visit),
        Purpose.brief(visit.task_type, visit.scheduled_start, visit.scheduled_end),
    )
    # 2. + 3. selection and validation (or fallback), on already-filtered rows only.
    result = build_brief(
        [to_contract(r) for r in rows],
        VisitContext(
            task_type=visit.task_type,
            scheduled_start=visit.scheduled_start.strftime("%H:%M"),
            scheduled_end=visit.scheduled_end.strftime("%H:%M"),
            worker_role=visit.worker_role,
            worker_language=visit.worker_language,
        ),
    )
    brief = Brief(
        visit_id=visit.id,
        selected_statement_ids=[line.statement_id for line in result.lines],
        rendered_lines_json=[line.__dict__ for line in result.lines],
        model=result.model,
        fallback_used=result.fallback_used,
        generated_at=datetime.now().replace(microsecond=0),
    )
    db.add(brief)
    db.commit()
    db.refresh(brief)
    return brief


@router.get("/{token}", response_model=schemas.BriefOut)
def get_brief(token: str, db: Session = Depends(get_db)):
    visit = _visit_for(token, db)
    if visit.state == "scheduled":
        visit_service.transition(db, visit, "briefed")

    brief = visit.brief or _generate_brief(db, visit)  # cache hit or generate once
    elder = db.get(Elder, visit.elder_id)
    codes = list(db.scalars(select(ObservationCode).order_by(ObservationCode.category, ObservationCode.code)))

    return schemas.BriefOut(
        elder_first_name=elder.display_name.split()[0],
        task_type=visit.task_type,
        worker_name=visit.worker_name,
        scheduled_start=visit.scheduled_start,
        scheduled_end=visit.scheduled_end,
        lines=[schemas.BriefLineOut(**BriefLine(**line).__dict__) for line in brief.rendered_lines_json],
        fallback_used=brief.fallback_used,
        model=brief.model,
        generated_at=brief.generated_at,
        observation_codes=codes,
    )


@router.post("/{token}/checkout", response_model=schemas.CheckoutAccepted, status_code=201)
def submit_checkout(token: str, data: schemas.CheckoutIn, db: Session = Depends(get_db)):
    visit = _visit_for(token, db)
    if visit.state != "briefed":
        raise HTTPException(409, "Open the brief before checking out")

    unknown = set(data.observation_codes) - checkout_service.known_codes(db)
    if unknown:
        raise HTTPException(422, f"Unknown observation codes: {sorted(unknown)}")

    # append the check-out (immutable), complete the visit, burn the token -- one transaction
    checkout = checkout_service.append(db, visit, data)
    visit_service.transition(db, visit, "completed", commit=False)
    visit_service.burn_token(db, visit, commit=False)
    db.commit()

    # fold-back: durable observation -> proposal (never a direct write to the record)
    suggestion = suggest_statement(
        checkout.observation_codes,
        checkout.note_text,
        checkout_service.recent_for_elder(db, visit.elder_id, exclude_id=checkout.id),
    )
    if suggestion:
        proposal_service.create_pending(db, visit.elder_id, checkout.id, suggestion)

    return schemas.CheckoutAccepted(
        checkout_id=checkout.id, visit_state=visit.state, proposal_created=bool(suggestion)
    )

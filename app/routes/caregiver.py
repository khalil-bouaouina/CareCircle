"""Caregiver console (B15). Family members can read; only the primary caregiver writes."""

from __future__ import annotations

import re
from datetime import datetime

from fastapi import APIRouter, Depends, Form, HTTPException

from .. import config
from ..deps import Session_, caregiver_session, person_session
from ..models import Purpose
from ..repositories import checkouts, people, proposals, statements, visits
from ..services import foldback, tokens, visibility
from . import proposal_out, statement_out, visit_out

router = APIRouter(prefix="/caregiver", tags=["caregiver"])

_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _hhmm(value: str | None, name: str) -> str | None:
    value = (value or "").strip() or None
    if value is not None and not _HHMM.match(value):
        raise HTTPException(422, f"{name} must be HH:MM")
    return value


def _in(value: str, allowed: list[str], name: str) -> str:
    if value not in allowed:
        raise HTTPException(422, f"{name} must be one of {allowed}")
    return value


def _iso(value: str, name: str) -> str:
    try:
        return datetime.fromisoformat(value).replace(microsecond=0).isoformat()
    except ValueError as exc:
        raise HTTPException(422, f"{name} must be an ISO 8601 datetime") from exc


# --- people --------------------------------------------------------------------


@router.get("/people")
def list_people(session: Session_ = Depends(person_session)):
    return [p.to_dict() for p in people.list_people(session.elder.id)]


# --- the record ------------------------------------------------------------------


@router.get("/record")
def record(session: Session_ = Depends(person_session)):
    """The caregiver's view goes through resolve() too -- she can have things hidden from her."""
    rows = visibility.resolve(session.elder.id, session.actor, Purpose())
    grouped = {c: [statement_out(s) for s in rows if s.category == c] for c in config.CATEGORIES}
    return {
        "elder": session.elder.to_dict(),
        "viewing_as": session.actor.label,
        "statements_by_category": grouped,
        "total": len(rows),
    }


@router.post("/statements", status_code=201)
def create_statement(
    statement: str = Form(min_length=3, max_length=500),
    category: str = Form(...),
    applies_to_tasks: list[str] = Form(default=[]),
    excluded_tasks: list[str] = Form(default=[]),
    time_start: str | None = Form(default=None),
    time_end: str | None = Form(default=None),
    hidden_from: list[int] = Form(default=[]),
    session: Session_ = Depends(caregiver_session),
):
    _in(category, config.CATEGORIES, "category")
    for t in [*applies_to_tasks, *excluded_tasks]:
        _in(t, config.TASK_TYPES, "task")
    ts, te = _hhmm(time_start, "time_start"), _hhmm(time_end, "time_end")
    if (ts is None) != (te is None):
        raise HTTPException(422, "time_start and time_end must be set together")
    new_id = statements.create_statement(
        session.elder.id, statement.strip(), category, applies_to_tasks, excluded_tasks, ts, te, hidden_from
    )
    return statement_out(statements.get_statement(new_id))


@router.post("/statements/{statement_id}/visibility")
def set_visibility(
    statement_id: int,
    visible_to: list[int] = Form(default=[]),
    session: Session_ = Depends(caregiver_session),
):
    """Store the negative, present the positive: hidden_from = everyone - visible_to."""
    row = statements.get_statement(statement_id)
    if row is None or row.elder_id != session.elder.id:
        raise HTTPException(404, "Statement not found")
    everyone = {p.id for p in people.list_people(session.elder.id) if p.role != "worker"}
    statements.set_hidden_from(statement_id, sorted(everyone - set(visible_to)))
    return statement_out(statements.get_statement(statement_id))


# --- visits ----------------------------------------------------------------------


@router.get("/visits")
def list_visits(session: Session_ = Depends(person_session)):
    tokens.expire_stale()
    out = []
    for v in visits.list_visits(session.elder.id):
        out.append(visit_out(v, checkouts.get_checkout_for_visit(v.id), visits.get_brief(v.id) is not None))
    return out


@router.post("/visits", status_code=201)
def create_visit(
    worker_name: str = Form(min_length=1, max_length=120),
    worker_role: str = Form(min_length=1, max_length=64),
    worker_language: str = Form(default="fr"),
    task_type: str = Form(...),
    scheduled_start: str = Form(...),
    scheduled_end: str = Form(...),
    session: Session_ = Depends(caregiver_session),
):
    _in(task_type, config.TASK_TYPES, "task_type")
    start, end = _iso(scheduled_start, "scheduled_start"), _iso(scheduled_end, "scheduled_end")
    if end <= start:
        raise HTTPException(422, "scheduled_end must be after scheduled_start")
    raw, token_hash = tokens.new_token()
    valid_from, valid_until = tokens.compute_window(start, end)
    visit_id = visits.create_visit(
        session.elder.id, worker_name.strip(), worker_role, worker_language, task_type,
        start, end, token_hash, valid_from, valid_until,
    )
    # The raw token is returned once, here, and never stored.
    return {
        "visit": visit_out(visits.get_visit(visit_id)),
        "token": raw,
        "link": f"{config.FRONTEND_BASE_URL.rstrip('/')}/v/{raw}",
        "valid_from": valid_from,
        "valid_until": valid_until,
    }


@router.get("/visits/{visit_id}")
def get_visit(visit_id: int, session: Session_ = Depends(person_session)):
    tokens.expire_stale()
    v = visits.get_visit(visit_id)
    if v is None or v.elder_id != session.elder.id:
        raise HTTPException(404, "Visit not found")
    return visit_out(v, checkouts.get_checkout_for_visit(v.id), visits.get_brief(v.id) is not None)


# --- proposals -------------------------------------------------------------------


@router.get("/proposals")
def list_proposals(status: str | None = "pending", session: Session_ = Depends(person_session)):
    return [proposal_out(p) for p in proposals.list_for_elder(session.elder.id, status or None)]


@router.post("/proposals/{proposal_id}/decide")
def decide_proposal(
    proposal_id: int,
    decision: str = Form(...),
    category: str | None = Form(default=None),
    session: Session_ = Depends(person_session),
):
    """Who may decide depends on capacity_mode; foldback enforces it."""
    _in(decision, ["approve", "reject"], "decision")
    proposal = proposals.get_proposal(proposal_id)
    if proposal is None or proposal.elder_id != session.elder.id:
        raise HTTPException(404, "Proposal not found")
    try:
        if decision == "approve":
            if category:
                _in(category, config.CATEGORIES, "category")
            statement_id = foldback.approve_proposal(proposal, session.actor, session.role, category or None)
            return {"proposal": proposal_out(proposals.get_proposal(proposal_id)), "statement_id": statement_id}
        foldback.reject_proposal(proposal, session.actor, session.role)
        return {"proposal": proposal_out(proposals.get_proposal(proposal_id)), "statement_id": None}
    except foldback.NotAllowed as exc:
        raise HTTPException(403, exc.detail) from exc

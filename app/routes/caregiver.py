"""Caregiver console (B15). Family members can read; only the primary caregiver writes."""

from __future__ import annotations

import re
from datetime import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from .. import config
from ..deps import Session_, caregiver_session, person_session
from ..models import Purpose
from ..repositories import checkouts, people, proposals, statements, visits
from ..services import auth, foldback, tokens, visibility
from ..web import templates
from . import statement_out, visit_out

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


@router.get("")
def caregiver_home():
    return RedirectResponse("/caregiver/record", status_code=303)


@router.get("/people")
def list_people(session: Session_ = Depends(person_session)):
    return [p.to_dict() for p in people.list_people(session.elder.id)]


# --- the record ------------------------------------------------------------------


@router.get("/record")
def record(request: Request, session: Session_ = Depends(person_session)):
    """The caregiver's view goes through resolve() too -- she can have things hidden from her."""
    rows = visibility.resolve(session.elder.id, session.actor, Purpose())
    grouped = {c: [statement_out(s) for s in rows if s.category == c] for c in config.CATEGORIES}
    return templates.TemplateResponse(request=request, name="caregiver/record.html", context={
        "elder": session.elder,
        "viewing_as": session.actor.label,
        "statements_by_category": grouped,
        "categories": config.CATEGORIES,
        "task_types": config.TASK_TYPES,
        "people": [p for p in people.list_people(session.elder.id) if p.role != "worker"],
        "user": session.user,
        "user_elders": session.user_elders,
        "current_role": session.role,
    })


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
    statements.create_statement(
        session.elder.id, statement.strip(), category, applies_to_tasks, excluded_tasks, ts, te, hidden_from
    )
    return RedirectResponse("/caregiver/record", status_code=303)



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
    return RedirectResponse("/caregiver/record", status_code=303)


# --- visits ----------------------------------------------------------------------


@router.get("/visits")
def list_visits(request: Request, session: Session_ = Depends(person_session)):
    tokens.expire_stale()
    out: list[dict] = []
    for v in visits.list_visits(session.elder.id):
        out.append({
            "visit": v,
            "checkout": checkouts.get_checkout_for_visit(v.id),
            "has_brief": visits.get_brief(v.id) is not None,
        })
    return templates.TemplateResponse(request=request, name="caregiver/visits.html", context={
        "elder": session.elder,
        "visits": out,
        "task_types": config.TASK_TYPES,
        "user": session.user,
        "user_elders": session.user_elders,
        "current_role": session.role,
    })



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
    return RedirectResponse(
        f"/caregiver/visits/{visit_id}/created?token={raw}&valid_from={valid_from}&valid_until={valid_until}",
        status_code=303,
    )


@router.get("/visits/{visit_id}/created")
def visit_created(visit_id: int, token: str, valid_from: str, valid_until: str, request: Request,
                  session: Session_ = Depends(person_session)):
    visit = visits.get_visit(visit_id)
    if visit is None or visit.elder_id != session.elder.id:
        raise HTTPException(404, "Visit not found")
    return templates.TemplateResponse(request=request, name="caregiver/visit_created.html", context={
        "link": f"{config.FRONTEND_BASE_URL.rstrip('/')}/v/{token}", "valid_from": valid_from,
        "valid_until": valid_until,
    })





@router.get("/visits/{visit_id}")
def get_visit(visit_id: int, session: Session_ = Depends(person_session)):
    tokens.expire_stale()
    v = visits.get_visit(visit_id)
    if v is None or v.elder_id != session.elder.id:
        raise HTTPException(404, "Visit not found")
    return visit_out(v, checkouts.get_checkout_for_visit(v.id), visits.get_brief(v.id) is not None)


# --- proposals -------------------------------------------------------------------


@router.get("/proposals")
def list_proposals(request: Request, status: str | None = "pending", session: Session_ = Depends(person_session)):
    return templates.TemplateResponse(request=request, name="caregiver/proposals.html", context={
        "elder": session.elder,
        "proposals": proposals.list_for_elder(session.elder.id, status or None),
        "categories": config.CATEGORIES,
        "user": session.user,
        "user_elders": session.user_elders,
        "current_role": session.role,
    })


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
            foldback.approve_proposal(proposal, session.actor, session.role, category or None)
            return RedirectResponse("/caregiver/proposals", status_code=303)
        foldback.reject_proposal(proposal, session.actor, session.role)
        return RedirectResponse("/caregiver/proposals", status_code=303)
    except foldback.NotAllowed as exc:
        raise HTTPException(403, exc.detail) from exc


# --- elder & family circle management -----------------------------------------


@router.post("/elders/new")
def new_elder(
    display_name: str = Form(min_length=2, max_length=120),
    capacity_mode: str = Form(default="assisted"),
    language: str = Form(default="fr"),
    session: Session_ = Depends(caregiver_session),
):
    _in(capacity_mode, config.CAPACITY_MODES, "capacity_mode")
    if not session.user:
        raise HTTPException(400, "Compte utilisateur requis pour créer un dossier")
    elder, _person = auth.create_elder_for_user(session.user.id, display_name, capacity_mode, language)
    token = auth.create_session_token({
        "user_id": session.user.id,
        "active_elder_id": elder.id,
        "role": "primary_caregiver",
    })
    resp = RedirectResponse("/caregiver/record", status_code=303)
    resp.set_cookie(config.SESSION_COOKIE_NAME, token, httponly=True, samesite="lax", max_age=86400 * 30)
    return resp


@router.post("/people/invite")
def invite_person(
    name: str = Form(min_length=2, max_length=120),
    email: str = Form(...),
    password: str = Form(min_length=6),
    role: str = Form(default="family"),
    session: Session_ = Depends(caregiver_session),
):
    _in(role, ["family", "primary_caregiver", "elder"], "role")
    auth.add_family_member(session.elder.id, name, email, password, role)

    return RedirectResponse("/caregiver/record", status_code=303)

"""Caregiver console (B18). Every handler thin: parse, call a service, redirect."""

from __future__ import annotations

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from .. import config
from ..models import Actor, Purpose
from ..repositories import checkouts, people, proposals, statements, visits, workers
from ..services import brief, foldback, tokens, visibility
from ..web import templates
from . import ELDER_ID

router = APIRouter(prefix="/caregiver", tags=["caregiver"])

CAREGIVER = Actor(kind="person", person_id=1, label="Leila")


def _redirect(path: str) -> RedirectResponse:
    """Redirect after POST so refreshing doesn't repeat the write."""
    return RedirectResponse(path, status_code=303)


@router.get("")
def index():
    return _redirect("/caregiver/record")


@router.get("/record")
def record(request: Request):
    """Goes through resolve() -- the caregiver can have things hidden from her too."""
    rows = visibility.resolve(ELDER_ID, CAREGIVER, Purpose())
    origins = {v.id: workers.get_worker(v.worker_id) for v in visits.list_visits(ELDER_ID)}
    return templates.TemplateResponse(request=request, name="caregiver/record.html", context={
        "elder": people.get_elder(ELDER_ID),
        "preferences": {c: [s for s in rows if s.kind == "preference" and s.category == c]
                        for c in config.CATEGORIES},
        "approaches": sorted([s for s in rows if s.kind == "approach"], key=lambda s: -s.id),
        "authors": origins,
        "people": people.list_people(ELDER_ID),
        "categories": config.CATEGORIES,
        "task_types": config.TASK_TYPES,
        "note_count": statements.count_active(ELDER_ID),
        "contributor_count": workers.count_contributing_workers(ELDER_ID),
        "family_count": len(people.list_people(ELDER_ID)),
        "pending_count": len(proposals.list_pending(ELDER_ID)),
    })


@router.post("/statements")
def create_statement(
    statement: str = Form(min_length=3, max_length=500),
    kind: str = Form(default="preference"),
    category: str = Form(...),
    applies_to_tasks: list[str] = Form(default=[]),
    time_start: str = Form(default=""),
    time_end: str = Form(default=""),
    hidden_from: list[int] = Form(default=[]),
):
    _one_of(kind, config.STATEMENT_KINDS, "kind")
    _one_of(category, config.CATEGORIES, "category")
    for task in applies_to_tasks:
        _one_of(task, config.TASK_TYPES, "task")
    statements.create_statement(
        ELDER_ID, statement.strip(), kind, category, source="family",
        applies_to_tasks=applies_to_tasks,
        time_start=time_start.strip() or None, time_end=time_end.strip() or None,
        hidden_from=hidden_from,
    )
    return _redirect("/caregiver/record")


@router.post("/statements/{statement_id}/visibility")
def set_visibility(statement_id: int, visible_to: list[int] = Form(default=[])):
    """Store the negative, present the positive: hidden_from = everyone - visible_to."""
    everyone = {p.id for p in people.list_people(ELDER_ID)}
    statements.set_hidden_from(statement_id, sorted(everyone - set(visible_to)))
    return _redirect("/caregiver/record")


@router.get("/visits")
def list_visits(request: Request):
    tokens.expire_stale()
    rows = []
    for v in visits.list_visits(ELDER_ID):
        rows.append({
            "visit": v,
            "worker": workers.get_worker(v.worker_id),
            "checkout": checkouts.get_checkout_for_visit(v.id),
            "prior_visits": visits.count_visits_by_worker(ELDER_ID, v.worker_id),
        })
    return templates.TemplateResponse(request=request, name="caregiver/visits.html", context={
        "elder": people.get_elder(ELDER_ID),
        "rows": rows,
        "workers": workers.list_workers_for_elder(ELDER_ID),
        "task_types": config.TASK_TYPES,
        "observation_labels": dict(config.OBSERVATION_CODES),
    })


@router.post("/visits")
def create_visit(
    task_type: str = Form(...),
    scheduled_start: str = Form(...),
    scheduled_end: str = Form(...),
    worker_id: str = Form(default=""),
    new_worker_name: str = Form(default=""),
    new_worker_role: str = Form(default="care worker"),
    new_worker_language: str = Form(default="fr"),
):
    """The "someone new" path is not an edge case -- it is the problem."""
    _one_of(task_type, config.TASK_TYPES, "task_type")
    if worker_id.strip().isdigit():
        wid = int(worker_id)
    elif new_worker_name.strip():
        wid = workers.create_worker(new_worker_name, new_worker_role, new_worker_language)
    else:
        raise HTTPException(422, "Pick a worker or name a new one")

    raw, token_hash = tokens.new_token()
    valid_from, valid_until = tokens.compute_window(scheduled_start, scheduled_end)
    visit_id = visits.create_visit(ELDER_ID, wid, task_type, scheduled_start, scheduled_end,
                                   token_hash, valid_from, valid_until)
    # The raw token travels in the query string; it never touches the database.
    return _redirect(f"/caregiver/visits/{visit_id}/created?token={raw}")


@router.get("/visits/{visit_id}/created")
def visit_created(visit_id: int, token: str, request: Request):
    visit = visits.get_visit(visit_id)
    if visit is None:
        raise HTTPException(404, "Visit not found")
    worker = workers.get_worker(visit.worker_id)
    return templates.TemplateResponse(request=request, name="caregiver/visit_created.html", context={
        "elder": people.get_elder(ELDER_ID),
        "visit": visit,
        "worker": worker,
        "link": f"{config.BASE_URL.rstrip('/')}/v/{token}",
        "continuity": {
            "note_count": statements.count_active(ELDER_ID),
            "contributor_count": workers.count_contributing_workers(ELDER_ID),
            "prior_visits": visits.count_visits_by_worker(ELDER_ID, visit.worker_id),
        },
        "valid_from": visit.token_valid_from,
        "valid_until": visit.token_expires_at,
    })


@router.get("/visits/{visit_id}/preview")
def preview_brief(visit_id: int, request: Request):
    """"Preview what the worker will see." Same template, no token burned."""
    result = brief.build_brief(visit_id)
    visit = visits.get_visit(visit_id)
    elder = people.get_elder(ELDER_ID)
    return templates.TemplateResponse(request=request, name="worker/brief.html", context={
        "preview": True, "visit": visit, "elder": elder,
        "worker": workers.get_worker(visit.worker_id), "result": result, "token": None,
        "visit_ordinal": "",
    })


@router.post("/corrections")
def create_correction(visit_id: int = Form(...), text: str = Form(min_length=3, max_length=300)):
    foldback.from_correction(ELDER_ID, visit_id, text, decided_by=CAREGIVER.label)
    return _redirect("/caregiver/visits")


@router.get("/proposals")
def list_proposals(request: Request):
    return templates.TemplateResponse(request=request, name="caregiver/proposals.html", context={
        "elder": people.get_elder(ELDER_ID),
        "proposals": proposals.list_pending(ELDER_ID),
        "sources": {p.id: _origin_source(p) for p in proposals.list_pending(ELDER_ID)},
    })


@router.post("/proposals/{proposal_id}/decide")
def decide_proposal(proposal_id: int, decision: str = Form(...)):
    _one_of(decision, ("approve", "reject"), "decision")
    if decision == "approve":
        foldback.approve_proposal(proposal_id, CAREGIVER.label)
    else:
        foldback.reject_proposal(proposal_id, CAREGIVER.label)
    return _redirect("/caregiver/proposals")


# --- helpers -------------------------------------------------------------------


def _one_of(value: str, allowed, name: str) -> None:
    if value not in allowed:
        raise HTTPException(422, f"{name} must be one of {list(allowed)}")


def _origin_source(proposal) -> dict | None:
    """Who and when, for the "From a handover note" card."""
    if proposal.source_checkout_id is None:
        return None
    checkout = checkouts.get_checkout(proposal.source_checkout_id)
    visit = visits.get_visit(checkout.visit_id) if checkout else None
    if visit is None:
        return None
    worker = workers.get_worker(visit.worker_id)
    return {"worker": worker.name if worker else "a worker", "date": visit.date, "visit_id": visit.id}

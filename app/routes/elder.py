"""Elder view (B19). Her own record, and the access log in plain sentences."""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from ..models import Actor, AccessEntry, Purpose
from ..repositories import access_log, people, proposals, statements, visits, workers
from ..services import foldback, visibility
from ..web import templates
from . import ELDER_ID

router = APIRouter(prefix="/elder", tags=["elder"])


def _elder_actor() -> Actor:
    elder = people.get_elder(ELDER_ID)
    return Actor(kind="elder", person_id=None, label=elder.first_name if elder else "Elder")


@router.get("")
def my_record(request: Request):
    rows = visibility.resolve(ELDER_ID, _elder_actor(), Purpose())
    authors = {}
    for s in rows:
        if s.origin_visit_id:
            visit = visits.get_visit(s.origin_visit_id)
            worker = workers.get_worker(visit.worker_id) if visit else None
            authors[s.id] = worker.first_name if worker else None
    return templates.TemplateResponse(request=request, name="elder/record.html", context={
        "elder": people.get_elder(ELDER_ID),
        "statements": rows,
        "people": people.list_people(ELDER_ID),
        "authors": authors,
        "pending_count": len(proposals.list_pending(ELDER_ID)),
    })


@router.post("/statements/{statement_id}/visibility")
def set_visibility(statement_id: int, visible_to: list[int] = Form(default=[])):
    everyone = {p.id for p in people.list_people(ELDER_ID)}
    statements.set_hidden_from(statement_id, sorted(everyone - set(visible_to)))
    return RedirectResponse("/elder", status_code=303)


@router.get("/access-log")
def my_access_log(request: Request, limit: int = 50):
    entries = access_log.list_access(ELDER_ID, limit=limit)
    return templates.TemplateResponse(request=request, name="elder/access_log.html", context={
        "elder": people.get_elder(ELDER_ID),
        "sentences": [format_access_sentence(e) for e in entries],
    })


@router.get("/proposals")
def my_proposals(request: Request):
    """One card at a time -- the route slices, the template renders."""
    pending = proposals.list_pending(ELDER_ID)
    return templates.TemplateResponse(request=request, name="elder/proposals.html", context={
        "elder": people.get_elder(ELDER_ID),
        "proposal": pending[0] if pending else None,
        "remaining": max(0, len(pending) - 1),
    })


@router.post("/proposals/{proposal_id}/decide")
def decide_proposal(proposal_id: int, decision: str = Form(...)):
    elder = people.get_elder(ELDER_ID)
    label = elder.first_name if elder else "Elder"
    if decision == "approve":
        foldback.approve_proposal(proposal_id, label)
    else:
        foldback.reject_proposal(proposal_id, label)
    return RedirectResponse("/elder/proposals", status_code=303)


# --- sentences ------------------------------------------------------------------
# Built in Python, not Jinja, so they can be eyeballed in a REPL at hour thirteen.

_VERBS = {"view": "viewed", "brief": "viewed"}


def _when(at: datetime, today: date) -> str:
    clock = f"{(at.hour - 1) % 12 + 1}:{at.minute:02d} {'am' if at.hour < 12 else 'pm'}"
    days = (today - at.date()).days
    if days == 0:
        return f"at {clock} today"
    if days == 1:
        return f"yesterday at {clock}"
    if days < 7:
        return f"on {at.strftime('%A')} at {clock}"
    return f"on {at.strftime('%B')} {at.day} at {clock}"


def format_access_sentence(entry: AccessEntry, today: date | None = None) -> str:
    """"Marie-Ève viewed your bathing preferences at 9:52 today"."""
    verb = _VERBS.get(entry.action, entry.action.replace("_", " "))
    when = _when(datetime.fromisoformat(entry.at), today or date.today())
    return f"{entry.actor_label} {verb} {entry.target_summary} {when}"

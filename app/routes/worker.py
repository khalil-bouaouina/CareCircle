"""The token-scoped worker surface (B20).

Two endpoints. The entire attack surface a stranger can reach, so keep it boring.
"""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from .. import config
from ..models import Actor, Purpose
from ..repositories import checkouts, people, statements, visits, workers
from ..services import brief, familiarity, foldback, tokens, visibility
from ..web import templates

router = APIRouter(prefix="/v", tags=["worker"])

KNOWN_CODES = {code for code, _label in config.OBSERVATION_CODES}


def _expired(request: Request) -> HTMLResponse:
    """One centred line and nothing else. Status 200, not 404 -- don't leak
    whether the token ever existed."""
    return templates.TemplateResponse(
        request=request, name="worker/brief.html", context={"expired": True}, status_code=200,
    )


@router.get("/{token}")
def get_brief(token: str, request: Request):
    visit = tokens.validate(token)
    if visit is None:
        return _expired(request)
    result = brief.build_brief(visit.id)
    return templates.TemplateResponse(request=request, name="worker/brief.html", context={
        "visit": visit,
        "elder": people.get_elder(visit.elder_id),
        "worker": workers.get_worker(visit.worker_id),
        "result": result,
        "visit_ordinal": _ordinal(familiarity.assess(visit.elder_id, visit.worker_id).visit_count + 1),
        "token": token,
    })


def _ordinal(n: int) -> str:
    if 11 <= n % 100 <= 13:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"


@router.get("/{token}/checkout")
def get_checkout(token: str, request: Request):
    visit = tokens.validate(token)
    if visit is None:
        return _expired(request)
    shown = [s for s in _shown_approaches(visit) if s.kind == "approach"]
    return templates.TemplateResponse(request=request, name="worker/checkout.html", context={
        "token": token,
        "completions": config.COMPLETIONS,
        "observation_codes": config.OBSERVATION_CODES,
        "shown_approaches": shown,
    })


@router.post("/{token}/checkout")
async def submit_checkout(
    token: str,
    request: Request,
    completion: str = Form(...),
    observation_codes: list[str] = Form(default=[]),
    note_text: str = Form(default=""),
    handover_note: str = Form(default=""),
):
    # Validate again -- never trust that the GET happened, and a form left open
    # past the window must not submit.
    visit = tokens.validate(token)
    if visit is None:
        return _expired(request)

    codes = [c for c in observation_codes if c in KNOWN_CODES]
    checkout_id = checkouts.create_checkout(
        visit.id, completion if completion in config.COMPLETIONS else "no",
        codes, note_text, handover_note,
    )

    for key, value in (await request.form()).multi_items():
        if key.startswith("confirm_") and value == "worked":
            statements.increment_confirmations(int(key.removeprefix("confirm_")))

    visits.set_state(visit.id, "completed")  # this burns the token
    foldback.from_handover_note(checkout_id)
    foldback.from_observation_patterns(checkout_id)

    return templates.TemplateResponse(request=request, name="worker/done.html", context={
        "left_note": bool(handover_note.strip()),
    })


def _shown_approaches(visit):
    """The approach lines that appeared in this worker's brief. Statement reads
    go through the resolver, never straight to the repository."""
    cached = visits.get_brief(visit.id)
    if cached is None:
        return []
    worker = workers.get_worker(visit.worker_id)
    rows = visibility.resolve(
        visit.elder_id,
        Actor(kind="worker", person_id=None, label=worker.name if worker else "Worker"),
        Purpose(task_type=visit.task_type, window_start=visit.start_hhmm, window_end=visit.end_hhmm),
    )
    shown = set(cached.selected_statement_ids)
    return [s for s in rows if s.id in shown]

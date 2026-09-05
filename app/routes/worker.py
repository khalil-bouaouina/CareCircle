"""The isolated, token-scoped worker surface."""

from __future__ import annotations

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse

from .. import config
from ..repositories import checkouts, observation_codes, people, visits
from ..services import brief, foldback, tokens
from ..web import templates

router = APIRouter(prefix="/v", tags=["worker"])


def _expired(request: Request) -> HTMLResponse:
    """A neutral 200 response that does not disclose token existence."""
    return templates.TemplateResponse(
        request=request, name="worker/brief.html", context={"expired": True}, status_code=200
    )


@router.get("/{token}")
def get_brief(token: str, request: Request, screen: str = "brief"):
    visit = tokens.validate(token)
    if visit is None:
        return _expired(request)

    if screen == "checkout":
        if visit.state != "briefed":
            return _expired(request)
        return templates.TemplateResponse(request=request, name="worker/checkout.html", context={
            "token": token,
            "completions": config.COMPLETIONS,
            "observation_codes": observation_codes.list_codes(),
        })
    if screen != "brief":
        return _expired(request)

    lines, _fallback_used, total = brief.build_brief(visit.id)
    elder = people.get_elder(visit.elder_id)
    return templates.TemplateResponse(request=request, name="worker/brief.html", context={
        "visit": visit,
        "header": f"{elder.first_name} · {visit.task_type.replace('_', ' ')} · {visit.start_hhmm}",
        "lines": lines,
        "total_statements": total,
        "footer": f"{len(lines)} of {total} notes, chosen for this visit.",
        "token": token,
    })


@router.post("/{token}/checkout")
def submit_checkout(
    token: str,
    request: Request,
    completion: str = Form(...),
    observation_codes_: list[str] = Form(default=[], alias="observation_codes"),
    note_text: str | None = Form(default=None, max_length=2000),
):
    # Validate again: the form may have remained open past the token window.
    visit = tokens.validate(token)
    if visit is None:
        return _expired(request)
    if visit.state != "briefed":
        raise HTTPException(409, "Open the brief before checking out")
    if completion not in config.COMPLETIONS:
        raise HTTPException(422, f"completion must be one of {config.COMPLETIONS}")
    unknown = set(observation_codes_) - observation_codes.known_codes()
    if unknown:
        raise HTTPException(422, f"Unknown observation codes: {sorted(unknown)}")

    checkout_id = checkouts.create_checkout(visit.id, completion, observation_codes_, note_text)
    visits.set_state(visit.id, "completed")
    foldback.proposals_from_checkout(checkout_id)
    return templates.TemplateResponse(request=request, name="worker/done.html", context={})

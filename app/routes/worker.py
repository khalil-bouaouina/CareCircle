"""Worker surface (B17) -- the only token-scoped router. Two endpoints; this is
the entire attack surface a stranger can reach, so keep it boring.

An invalid, expired, or burned token gets the same 200 "This link has expired."
response -- never a 404 -- so nothing leaks about whether the token ever existed.
"""

from __future__ import annotations

from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import JSONResponse

from .. import config
from ..repositories import checkouts, observation_codes, people, visits
from ..services import brief, foldback, tokens

router = APIRouter(prefix="/v", tags=["worker"])

EXPIRED = {"ok": False, "expired": True, "message": "This link has expired."}


def _expired() -> JSONResponse:
    return JSONResponse(EXPIRED, status_code=200)


@router.get("/{token}")
def get_brief(token: str):
    visit = tokens.validate(token)
    if visit is None:
        return _expired()

    lines, fallback_used, total = brief.build_brief(visit.id)
    elder = people.get_elder(visit.elder_id)
    return {
        "ok": True,
        "header": f"{elder.first_name} · {visit.task_type.replace('_', ' ')} · {visit.start_hhmm}",
        "elder_first_name": elder.first_name,
        "task_type": visit.task_type,
        "scheduled_start": visit.scheduled_start,
        "scheduled_end": visit.scheduled_end,
        "lines": [l.__dict__ for l in lines],
        "footer": f"{len(lines)} of {total} notes, chosen for this visit.",
        "fallback_used": fallback_used,
        "completions": config.COMPLETIONS,
        "observation_codes": [c.to_dict() for c in observation_codes.list_codes()],
    }


@router.post("/{token}/checkout", status_code=201)
def submit_checkout(
    token: str,
    completion: str = Form(...),
    observation_codes_: list[str] = Form(default=[], alias="observation_codes"),
    note_text: str | None = Form(default=None, max_length=2000),
):
    # validate again -- never trust that the GET happened; a form left open past the window must not submit
    visit = tokens.validate(token)
    if visit is None:
        return _expired()
    if visit.state != "briefed":
        raise HTTPException(409, "Open the brief before checking out")
    if completion not in config.COMPLETIONS:
        raise HTTPException(422, f"completion must be one of {config.COMPLETIONS}")
    unknown = set(observation_codes_) - observation_codes.known_codes()
    if unknown:
        raise HTTPException(422, f"Unknown observation codes: {sorted(unknown)}")

    checkout_id = checkouts.create_checkout(visit.id, completion, observation_codes_, note_text)
    visits.set_state(visit.id, "completed")  # this burns the token
    created = foldback.proposals_from_checkout(checkout_id)

    return {
        "ok": True,
        "checkout_id": checkout_id,
        "visit_state": "completed",
        "proposals_created": created,
        "message": "Thank you. This link is now closed.",
    }

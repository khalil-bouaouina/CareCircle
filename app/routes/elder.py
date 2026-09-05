"""Elder view (B16). Her own record, large type in the UI, plain sentences in the log."""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, Form, HTTPException

from .. import config
from ..deps import Session_, elder_session
from ..models import AccessEntry, Purpose
from ..repositories import access_log, people, proposals, statements
from ..services import foldback, visibility
from . import proposal_out, statement_out

router = APIRouter(prefix="/elder", tags=["elder"])


@router.get("")
def my_record(session: Session_ = Depends(elder_session)):
    rows = visibility.resolve(session.elder.id, session.actor, Purpose())
    everyone = [p.to_dict() for p in people.list_people(session.elder.id) if p.role != "worker"]
    return {"elder": session.elder.to_dict(), "people": everyone, "statements": [statement_out(s) for s in rows]}


@router.post("/statements/{statement_id}/visibility")
def set_visibility(
    statement_id: int,
    visible_to: list[int] = Form(default=[]),
    session: Session_ = Depends(elder_session),
):
    row = statements.get_statement(statement_id)
    if row is None or row.elder_id != session.elder.id:
        raise HTTPException(404, "Statement not found")
    everyone = {p.id for p in people.list_people(session.elder.id) if p.role != "worker"}
    statements.set_hidden_from(statement_id, sorted(everyone - set(visible_to)))
    row = statements.get_statement(statement_id)
    access_log.log_access(
        session.elder.id, session.actor.label, "visibility_change", f'who can see "{row.statement[:50]}"'
    )
    return statement_out(row)


@router.get("/access-log")
def my_access_log(limit: int = 50, session: Session_ = Depends(elder_session)):
    entries = access_log.list_access(session.elder.id, limit=limit)
    return [{**e.to_dict(), "sentence": format_access_sentence(e)} for e in entries]


@router.get("/proposals")
def my_proposals(session: Session_ = Depends(elder_session)):
    """The UI shows one at a time; ``first`` is the one to render, ``pending`` the rest."""
    pending = [proposal_out(p) for p in proposals.list_pending(session.elder.id)]
    return {"first": pending[0] if pending else None, "pending": pending, "count": len(pending)}


@router.post("/proposals/{proposal_id}/decide")
def decide_proposal(
    proposal_id: int,
    decision: str = Form(...),
    category: str | None = Form(default=None),
    session: Session_ = Depends(elder_session),
):
    if decision not in ("approve", "reject"):
        raise HTTPException(422, "decision must be approve or reject")
    if category and category not in config.CATEGORIES:
        raise HTTPException(422, f"category must be one of {config.CATEGORIES}")
    proposal = proposals.get_proposal(proposal_id)
    if proposal is None or proposal.elder_id != session.elder.id:
        raise HTTPException(404, "Proposal not found")
    try:
        if decision == "approve":
            statement_id = foldback.approve_proposal(proposal, session.actor, None, category or None)
        else:
            foldback.reject_proposal(proposal, session.actor, None)
            statement_id = None
    except foldback.NotAllowed as exc:
        raise HTTPException(403, exc.detail) from exc
    return {"proposal": proposal_out(proposals.get_proposal(proposal_id)), "statement_id": statement_id}


# --- sentences ------------------------------------------------------------------

_VERBS = {
    "view": "viewed",
    "brief": "viewed",
    "export": "exported",
    "approved_proposal": "approved",
    "rejected_proposal": "rejected",
    "visibility_change": "changed",
}


def _when(at: datetime, today: date | None = None) -> str:
    today = today or date.today()
    clock = f"{at.hour}:{at.minute:02d}"
    if at.date() == today:
        return f"at {clock} today"
    if (today - at.date()).days == 1:
        return f"yesterday at {clock}"
    if (today - at.date()).days < 7:
        return f"on {at.strftime('%A')} at {clock}"
    return f"on {at.strftime('%B')} {at.day} at {clock}"


def format_access_sentence(entry: AccessEntry, today: date | None = None) -> str:
    """'Marie-Ève viewed your bathing preferences (7) at 9:52 today'."""
    verb = _VERBS.get(entry.action, entry.action.replace("_", " "))
    return f"{entry.actor_label} {verb} {entry.target_summary} {_when(datetime.fromisoformat(entry.at), today)}"

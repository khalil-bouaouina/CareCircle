"""Pending record changes awaiting human approval (P4).

Who approves depends on ``capacity_mode`` (architecture.md section 6):
  self      -> the elder
  assisted  -> the elder; the caregiver can only reject (cull noise), not approve
  mandated  -> the representative (primary caregiver); the elder still sees it happened
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Checkout, Elder, ObservationCode, PreferenceStatement, ProposedUpdate
from ..security.resolver import Actor
from . import access_log


class NotAllowed(Exception):
    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


def create_pending(db: Session, elder_id: int, checkout_id: int | None, text: str, *, commit: bool = True) -> ProposedUpdate:
    row = ProposedUpdate(
        elder_id=elder_id,
        source_checkout_id=checkout_id,
        suggested_statement=text,
        status="pending",
    )
    db.add(row)
    if commit:
        db.commit()
    return row


def list_for_elder(db: Session, elder_id: int, status: str | None = "pending") -> list[ProposedUpdate]:
    query = select(ProposedUpdate).where(ProposedUpdate.elder_id == elder_id)
    if status:
        query = query.where(ProposedUpdate.status == status)
    return list(db.scalars(query.order_by(ProposedUpdate.created_at.desc(), ProposedUpdate.id.desc())))


def get(db: Session, elder_id: int, proposal_id: int) -> ProposedUpdate | None:
    row = db.get(ProposedUpdate, proposal_id)
    if row is None or row.elder_id != elder_id:
        return None
    return row


def _may_decide(elder: Elder, actor: Actor, actor_role: str | None, decision: str) -> None:
    mode = elder.capacity_mode
    is_elder = actor.kind == "elder"
    is_rep = actor.kind == "person" and actor_role == "primary_caregiver"

    if mode == "self":
        if not is_elder:
            raise NotAllowed("Only the elder decides on proposals (capacity mode: self)")
    elif mode == "assisted":
        if is_elder:
            return
        if is_rep and decision == "reject":
            return
        raise NotAllowed("In assisted mode the elder confirms proposals; the caregiver may only reject")
    elif mode == "mandated":
        if not is_rep:
            raise NotAllowed("A legal representative decides on proposals (capacity mode: mandated)")
    else:  # pragma: no cover
        raise NotAllowed(f"Unknown capacity mode {mode!r}")


def _infer_category(db: Session, proposal: ProposedUpdate) -> str:
    """Match the template back to its observation code; default to 'care'."""
    code = db.scalar(
        select(ObservationCode).where(ObservationCode.suggested_statement == proposal.suggested_statement)
    )
    if code:
        return code.category
    return "care"


def _infer_tasks(db: Session, proposal: ProposedUpdate) -> list[str]:
    """A proposal born from one task's check-out is scoped to that task by default."""
    if proposal.source_checkout_id is None:
        return []
    checkout = db.get(Checkout, proposal.source_checkout_id)
    return [checkout.visit.task_type] if checkout and checkout.visit else []


def decide(
    db: Session,
    elder: Elder,
    proposal: ProposedUpdate,
    actor: Actor,
    actor_role: str | None,
    decision: str,
    category: str | None = None,
) -> tuple[ProposedUpdate, PreferenceStatement | None]:
    if proposal.status != "pending":
        raise NotAllowed(f"Proposal already {proposal.status}")
    _may_decide(elder, actor, actor_role, decision)

    now = datetime.now().replace(microsecond=0)
    proposal.decided_by = actor.label
    proposal.decided_at = now
    created: PreferenceStatement | None = None

    if decision == "approve":
        proposal.status = "approved"
        created = PreferenceStatement(
            elder_id=elder.id,
            statement=proposal.suggested_statement,
            category=category or _infer_category(db, proposal),
            applies_to_tasks=_infer_tasks(db, proposal),
            excluded_tasks=[],
            hidden_from=[],
            status="active",
            source_checkout_id=proposal.source_checkout_id,
        )
        db.add(created)
    else:
        proposal.status = "rejected"

    access_log.record(
        db,
        elder.id,
        actor_label=actor.label,
        action=f"{proposal.status}_proposal",
        target_summary=f'a proposed statement: "{proposal.suggested_statement[:60]}"',
        commit=False,
    )
    db.commit()
    if created:
        db.refresh(created)
    return proposal, created

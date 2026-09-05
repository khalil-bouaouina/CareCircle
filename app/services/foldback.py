"""Check-out -> proposal -> statement (B13). Rule-based; the AI does not decide
what enters the record (P4).

A code that appears in at least ``PROPOSAL_THRESHOLD`` of the last
``PROPOSAL_WINDOW`` check-outs is a pattern, not an incident, and becomes a
pending proposal using the template on the observation code. Nothing here
writes a statement without a human decision.

Who may decide depends on ``capacity_mode`` (architecture.md section 6):
  self      -> the elder
  assisted  -> the elder; the primary caregiver may only reject (cull noise)
  mandated  -> the primary caregiver (representative); the elder still sees it in her log
"""

from __future__ import annotations

from .. import config
from ..models import Actor, Elder, Proposal
from ..repositories import access_log, checkouts, observation_codes, people, proposals, statements, visits


class NotAllowed(Exception):
    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


# --- check-out -> proposals ------------------------------------------------------


def proposals_from_checkout(checkout_id: int) -> list[int]:
    checkout = checkouts.get_checkout(checkout_id)
    if checkout is None:
        return []
    visit = visits.get_visit(checkout.visit_id)
    if visit is None:
        return []

    created: list[int] = []
    for code in checkout.observation_codes:
        count = checkouts.count_code_occurrences(visit.elder_id, code, last_n=config.PROPOSAL_WINDOW)
        if count < config.PROPOSAL_THRESHOLD:
            continue
        template = observation_codes.template_for(code)
        if not template:
            continue  # a code with no template simply produces no proposal
        if proposals.pending_exists(visit.elder_id, template):
            continue
        created.append(proposals.create_proposal(visit.elder_id, checkout_id, template))
    return created


# --- human decision -------------------------------------------------------------


def _may_decide(elder: Elder, actor: Actor, actor_role: str | None, decision: str) -> None:
    is_elder = actor.kind == "elder"
    is_rep = actor.kind == "person" and actor_role == "primary_caregiver"
    mode = elder.capacity_mode

    if mode == "self":
        if not is_elder:
            raise NotAllowed("Only the elder decides on proposals (capacity mode: self)")
    elif mode == "assisted":
        if is_elder or (is_rep and decision == "reject"):
            return
        raise NotAllowed("In assisted mode the elder confirms proposals; the caregiver may only reject")
    elif mode == "mandated":
        if not is_rep:
            raise NotAllowed("A legal representative decides on proposals (capacity mode: mandated)")
    else:
        raise NotAllowed(f"Unknown capacity mode {mode!r}")


def _infer_category(proposal: Proposal) -> str:
    code = observation_codes.code_for_template(proposal.suggested_statement)
    return code.category if code else "care"


def _infer_tasks(proposal: Proposal) -> list[str]:
    """A proposal born from one task's check-out is scoped to that task by default."""
    if proposal.source_checkout_id is None:
        return []
    checkout = checkouts.get_checkout(proposal.source_checkout_id)
    visit = visits.get_visit(checkout.visit_id) if checkout else None
    return [visit.task_type] if visit else []


def approve_proposal(
    proposal: Proposal, actor: Actor, actor_role: str | None, category: str | None = None
) -> int:
    """Marks the proposal approved, creates an active statement, returns its id."""
    elder = _elder_or_raise(proposal.elder_id)
    _check_pending(proposal)
    _may_decide(elder, actor, actor_role, "approve")

    statement_id = statements.create_statement(
        elder_id=elder.id,
        statement=proposal.suggested_statement,
        category=category or _infer_category(proposal),
        applies_to_tasks=_infer_tasks(proposal),
        excluded_tasks=[],
        time_start=None,
        time_end=None,
        status="active",
        source_checkout_id=proposal.source_checkout_id,
    )
    proposals.decide(proposal.id, "approved", actor.label)
    access_log.log_access(
        elder.id, actor.label, "approved_proposal", f'a proposed statement: "{proposal.suggested_statement[:60]}"'
    )
    return statement_id


def reject_proposal(proposal: Proposal, actor: Actor, actor_role: str | None) -> None:
    elder = _elder_or_raise(proposal.elder_id)
    _check_pending(proposal)
    _may_decide(elder, actor, actor_role, "reject")
    proposals.decide(proposal.id, "rejected", actor.label)
    access_log.log_access(
        elder.id, actor.label, "rejected_proposal", f'a proposed statement: "{proposal.suggested_statement[:60]}"'
    )


def _elder_or_raise(elder_id: int) -> Elder:
    elder = people.get_elder(elder_id)
    if elder is None:
        raise NotAllowed("Unknown elder")
    return elder


def _check_pending(proposal: Proposal) -> None:
    if proposal.status != "pending":
        raise NotAllowed(f"Proposal already {proposal.status}")

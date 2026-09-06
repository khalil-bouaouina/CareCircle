"""Check-out -> proposal -> statement (B16).

Rule-based, no AI. **The model does not decide what enters the record.**

Two product decisions are embedded here, worth naming so nobody "fixes" them
later. A threshold of three is what makes a proposal read as *"this is a
pattern"* rather than *"this happened once."* And corrections skip the queue
entirely, because a caregiver writing *"this must never happen again"* has
already given approval; a second confirmation step is friction with no purpose.
"""

from __future__ import annotations

from .. import config
from ..repositories import checkouts, proposals, statements, visits

# A code with no template produces no proposal. Three or four entries is enough.
PATTERN_TEMPLATES: dict[str, str] = {
    "refused_equipment": "She has refused the equipment several times. Offer it once, "
                         "then let it go rather than insisting.",
    "didnt_finish_meal": "She has been leaving meals unfinished. Sit down with her and "
                         "offer a smaller portion.",
    "unsteady_on_feet": "She has been unsteady on her feet. Stay within arm's reach "
                        "whenever she is standing.",
    "seemed_more_tired": "She has seemed more tired than usual. Allow extra time and "
                         "let her set the pace.",
}


# --- check-out -> proposals ---------------------------------------------------


def from_handover_note(checkout_id: int) -> int | None:
    """The note a departing worker leaves for the next person becomes a proposal."""
    checkout = checkouts.get_checkout(checkout_id)
    if checkout is None:
        return None
    note = (checkout.handover_note or "").strip()
    if not note:
        return None
    visit = visits.get_visit(checkout.visit_id)
    if visit is None or proposals.exists_pending_like(visit.elder_id, note):
        return None
    return proposals.create_proposal(
        visit.elder_id, checkout_id, origin_kind="handover",
        suggested_kind="approach", suggested_statement=note,
    )


def from_observation_patterns(checkout_id: int) -> list[int]:
    """A code seen PATTERN_THRESHOLD times in the recent window is a pattern."""
    checkout = checkouts.get_checkout(checkout_id)
    if checkout is None:
        return []
    visit = visits.get_visit(checkout.visit_id)
    if visit is None:
        return []

    created: list[int] = []
    for code in checkout.observation_codes:
        template = PATTERN_TEMPLATES.get(code)
        if not template:
            continue
        seen = checkouts.count_code_occurrences(visit.elder_id, code, last_n=config.PATTERN_WINDOW)
        if seen < config.PATTERN_THRESHOLD:
            continue
        if proposals.exists_pending_like(visit.elder_id, template):
            continue
        created.append(proposals.create_proposal(
            visit.elder_id, checkout_id, origin_kind="pattern",
            suggested_kind="preference", suggested_statement=template,
        ))
    return created


def from_correction(elder_id: int, visit_id: int, text: str, decided_by: str) -> int:
    """Creates an active statement directly, bypassing the proposal queue."""
    return statements.create_statement(
        elder_id=elder_id,
        statement=text.strip(),
        kind="preference",
        category="care",
        source="correction",
        origin_visit_id=visit_id,
    )


# --- proposal -> statement ----------------------------------------------------


def approve_proposal(proposal_id: int, decided_by: str) -> int:
    """Marks accepted and creates the active statement. Returns its id."""
    proposal = proposals.get_proposal(proposal_id)
    if proposal is None or proposal.status != "pending":
        raise LookupError(f"no pending proposal {proposal_id}")

    origin_visit_id = None
    applies_to_tasks: list[str] = []
    if proposal.source_checkout_id is not None:
        checkout = checkouts.get_checkout(proposal.source_checkout_id)
        visit = visits.get_visit(checkout.visit_id) if checkout else None
        if visit is not None:
            origin_visit_id = visit.id
            # A proposal born from one task's check-out is scoped to that task.
            applies_to_tasks = [visit.task_type]

    statement_id = statements.create_statement(
        elder_id=proposal.elder_id,
        statement=proposal.suggested_statement,
        kind=proposal.suggested_kind,
        category="care",
        source="worker",
        applies_to_tasks=applies_to_tasks,
        origin_visit_id=origin_visit_id,
        source_checkout_id=proposal.source_checkout_id,
    )
    proposals.decide(proposal_id, "accepted", decided_by)
    return statement_id


def reject_proposal(proposal_id: int, decided_by: str) -> None:
    proposals.decide(proposal_id, "rejected", decided_by)

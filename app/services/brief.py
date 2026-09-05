"""Brief pipeline orchestration (B14). No SQL, no HTTP, no prompt text.

    build_brief(visit_id) -> (lines, fallback_used, total_active_statements)

Ordering is load-bearing: ``visibility.resolve`` runs BEFORE the AI module is
called. The model is only ever handed statements that already passed the
consent gate. Hidden data never leaves the database, so it cannot leak through
a model response, a prompt injection, or a logging accident. Do not "optimize"
by resolving after the call.
"""

from __future__ import annotations

from brief_builder import Statement as ContractStatement
from brief_builder import VisitContext, build_brief as _ai_build_brief

from ..models import Actor, BriefLine, Purpose, Statement, Visit
from ..repositories import people, statements, visits
from . import visibility


def worker_actor(visit: Visit) -> Actor:
    """Workers hold no account. If a Person row with the same name exists we use
    its id so per-person ``hidden_from`` applies; otherwise they are anonymous."""
    person = people.find_worker_person(visit.elder_id, visit.worker_name)
    return Actor(kind="worker", person_id=person.id if person else None, label=visit.worker_name)


def _to_contract(s: Statement) -> ContractStatement:
    return ContractStatement(
        id=s.id,
        statement=s.statement,
        category=s.category,
        applies_to_tasks=list(s.applies_to_tasks),
        excluded_tasks=list(s.excluded_tasks),
        time_start=s.time_start,
        time_end=s.time_end,
    )


def build_brief(visit_id: int, force: bool = False) -> tuple[list[BriefLine], bool, int]:
    visit = visits.get_visit(visit_id)
    if visit is None:
        raise LookupError(f"visit {visit_id} not found")
    total = statements.count_active(visit.elder_id)

    # 1. cache
    if not force:
        cached = visits.get_brief(visit_id)
        if cached is not None:
            return cached.lines, cached.fallback_used, total

    # 2. + 3. consent gate FIRST. Writes the access-log row.
    candidates = visibility.resolve(
        visit.elder_id,
        worker_actor(visit),
        Purpose(task_type=visit.task_type, window_start=visit.start_hhmm, window_end=visit.end_hhmm),
    )

    # 4. nothing to say -> skip the model entirely
    if not candidates:
        lines: list[BriefLine] = []
        fallback_used = False
        model = None
    else:
        # 5. + 6. selection + validation (or fallback) on already-filtered rows only.
        # brief_builder never raises because of the model; it falls back internally.
        result = _ai_build_brief(
            [_to_contract(s) for s in candidates],
            VisitContext(
                task_type=visit.task_type,
                scheduled_start=visit.start_hhmm,
                scheduled_end=visit.end_hhmm,
                worker_role=visit.worker_role,
                worker_language=visit.worker_language,
            ),
        )
        allowed = {s.id for s in candidates}
        lines = [
            BriefLine(statement_id=l.statement_id, text=l.text, critical=bool(l.critical))
            for l in result.lines
            if l.statement_id in allowed  # belt and braces on P2
        ]
        fallback_used = result.fallback_used
        model = result.model

    # 7. persist, transition, return
    visits.save_brief(visit_id, [l.statement_id for l in lines], lines, model, fallback_used)
    if visit.state == "scheduled":
        visits.set_state(visit_id, "briefed")
    return lines, fallback_used, total

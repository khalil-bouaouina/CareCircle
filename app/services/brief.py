"""Brief pipeline orchestration (B17). No SQL, no HTTP, no prompt text.

    build_brief(visit_id, force=False) -> BriefResult
"""

from __future__ import annotations

from .. import config
from ..ai import selector, validator
from ..models import Actor, BriefResult, Purpose
from ..repositories import statements, visits, workers
from . import familiarity as familiarity_service
from . import visibility


def build_brief(visit_id: int, force: bool = False) -> BriefResult:
    visit = visits.get_visit(visit_id)
    if visit is None:
        raise LookupError(f"visit {visit_id} not found")
    worker = workers.get_worker(visit.worker_id)
    if worker is None:
        raise LookupError(f"worker {visit.worker_id} not found")

    note_count = statements.count_active(visit.elder_id)
    contributor_count = workers.count_contributing_workers(visit.elder_id)
    fam = familiarity_service.assess(visit.elder_id, visit.worker_id)

    # 1. cache
    if not force:
        cached = visits.get_brief(visit_id)
        if cached is not None:
            return BriefResult(
                lines=cached.lines,
                fallback_used=cached.fallback_used,
                note_count=note_count,
                contributor_count=contributor_count,
                changed_count=len(cached.lines),
                is_first_visit=fam.is_first_visit,
            )

    # 2. + 3. The consent gate runs BEFORE the model is called. The model is only
    # ever handed statements that already passed it, so hidden data cannot leak
    # through a model response, a prompt injection, or a logging accident.
    # Do not "optimize" by resolving after the call.
    candidates = visibility.resolve(
        visit.elder_id,
        Actor(kind="worker", person_id=None, label=worker.name),
        Purpose(task_type=visit.task_type, window_start=visit.start_hhmm, window_end=visit.end_hhmm),
    )

    # 4. + 5. split by familiarity
    changed_ids = familiarity_service.changed_since(candidates, fam.last_visit_at)
    if not fam.is_first_visit:
        candidates = [
            s for s in candidates
            if s.source == "correction"
            or s.id in changed_ids
            or (s.kind == "approach" and s.confirmations >= 2
                and s.created_at > (fam.last_visit_at or ""))
        ]
    changed_count = len(candidates)

    # 6. an empty set is a valid, correct brief -- skip the model entirely
    lines = []
    fallback_used = False
    model = None
    if candidates:
        by_id = {s.id: s for s in candidates}
        try:
            raw = selector.select_lines(visit, worker, candidates, fam, changed_ids)
            model = config.ANTHROPIC_MODEL
        except Exception:
            fallback_used = True
            raw = None

        if raw is None:
            lines = validator.fallback_lines(candidates)
        else:
            # 8. enforcement: every id must come from the candidate set
            lines = validator.validate_lines(raw, set(by_id), by_id)
            # An empty answer is a correct answer -- the model may have decided
            # nothing here is worth saying. But a non-empty response that
            # validated down to nothing is malformed, and that falls back.
            if raw and not lines:
                fallback_used = True
                model = None
                lines = validator.fallback_lines(candidates)

    # 10. persist, transition, return
    visits.save_brief(visit_id, [l.statement_id for l in lines], lines, model, fallback_used)
    if visit.state == "scheduled":
        visits.set_state(visit_id, "briefed")

    return BriefResult(
        lines=lines,
        fallback_used=fallback_used,
        note_count=note_count,
        contributor_count=contributor_count,
        changed_count=changed_count,
        is_first_visit=fam.is_first_visit,
    )

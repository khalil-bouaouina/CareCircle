"""THE resolver -- the only read path for statement data (B13).

    resolve(elder_id, actor, purpose) -> list[Statement]

Every surface that shows a statement -- the caregiver console, a family member
browsing, the elder's own view, brief generation for a worker -- calls this
function and nothing else. No route imports ``repositories.statements`` for a
read. That is what makes the privacy claim demonstrable rather than
aspirational: there is exactly one function to audit, and this is it.

Order applied, exactly:
  1. fetch the elder's active statements
  2. identity filter -- per-statement ``hidden_from``; never applied to the elder
  3. purpose filter  -- task scoping, when the purpose names a task
  4. time filter     -- window overlap, when the purpose names a window
  5. log             -- one access_log row. Unconditional.
  6. return the survivors

Two things to hold firm on. Logging has no ``if``: if this function ran, a row
exists. And there is no bypass parameter -- nobody gets to pass
``skip_filters=True``. If a caller needs unfiltered statements, that caller is
wrong.

Corrections and approaches pass through this filter exactly like preferences.
Worker-authored knowledge is subject to the elder's visibility control the same
as anything else; there is no privileged class of statement.
"""

from __future__ import annotations

from ..models import Actor, Purpose, Statement
from ..repositories import access_log, statements


def resolve(elder_id: int, actor: Actor, purpose: Purpose) -> list[Statement]:
    # 1. all active statements for the elder
    rows = statements.list_statements(elder_id, status="active")

    # 2. identity -- the elder never has anything hidden from her
    if actor.kind != "elder":
        rows = [s for s in rows if actor.person_id not in s.hidden_from]

    # 3. purpose -- task scoping
    if purpose.task_type:
        rows = [s for s in rows if _task_applies(s, purpose.task_type)]

    # 4. time window -- "HH:MM" compares correctly as a zero-padded string
    if purpose.window_start and purpose.window_end:
        rows = [s for s in rows if _time_applies(s, purpose.window_start, purpose.window_end)]

    # 5. the access-log row. Always.
    access_log.log_access(
        elder_id,
        actor_label=actor.label,
        action="brief" if purpose.task_type else "view",
        target_summary=_summary(purpose),
    )

    # 6.
    return rows


# --- helpers -------------------------------------------------------------------


def _task_applies(s: Statement, task_type: str) -> bool:
    if task_type in s.excluded_tasks:
        return False
    if s.applies_to_tasks and task_type not in s.applies_to_tasks:
        return False
    return True


def _time_applies(s: Statement, window_start: str, window_end: str) -> bool:
    if not s.time_start or not s.time_end:
        return True
    return s.time_start < window_end and window_start < s.time_end


def _summary(purpose: Purpose) -> str:
    """What the elder reads in her log: "your bathing preferences"."""
    if purpose.task_type:
        return f"your {purpose.task_type.replace('_', ' ')} preferences"
    return "your record"

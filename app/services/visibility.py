"""THE visibility resolver -- the only read path for preference statement data (P1).

    resolve(elder_id, actor, purpose) -> list[Statement]

Every surface that shows a statement -- the caregiver console, a family member
browsing, the elder's own view, brief generation for a worker -- calls this
function and nothing else. No route imports ``repositories.statements``. This
is what makes the privacy claim demonstrable rather than aspirational: there is
exactly one function to audit.

Order applied, exactly:
  1. fetch the elder's active statements
  2. identity filter   -- per-statement ``hidden_from``; never applied to the elder
  3. purpose filter    -- task scoping, when the purpose names a task
  4. time filter       -- window overlap, when the purpose names a window
  5. log               -- one access_log row. Unconditional.
  6. return survivors

Two things held firm: logging has no ``if``; and there is no bypass parameter.
If a caller needs unfiltered statements, that caller is wrong.
"""

from __future__ import annotations

from ..models import Actor, Purpose, Statement
from ..repositories import access_log, people, statements

MINUTES_PER_DAY = 24 * 60


def resolve(elder_id: int, actor: Actor, purpose: Purpose) -> list[Statement]:
    # 1. all active statements for the elder
    rows = statements.list_statements(elder_id, status="active")

    # 2. identity -- the elder (or her representative in mandated mode) has nothing hidden from her
    if not _acts_as_elder(elder_id, actor):
        rows = [s for s in rows if actor.person_id not in s.hidden_from]

    # 3. purpose -- task scoping
    if purpose.task_type:
        rows = [s for s in rows if _task_applies(s, purpose.task_type)]

    # 4. time window
    if purpose.window_start and purpose.window_end:
        rows = [s for s in rows if _time_applies(s, purpose.window_start, purpose.window_end)]

    # 5. the access-log row. Always.
    access_log.log_access(
        elder_id,
        actor_label=actor.label,
        action=_action(purpose),
        target_summary=_summary(purpose, len(rows)),
    )

    # 6.
    return rows


# --- helpers -------------------------------------------------------------------


def _acts_as_elder(elder_id: int, actor: Actor) -> bool:
    if actor.kind == "elder":
        return True
    if actor.kind != "person" or actor.person_id is None:
        return False
    elder = people.get_elder(elder_id)
    if elder is None or elder.capacity_mode != "mandated":
        return False
    person = people.get_person(actor.person_id)
    return bool(person and person.role == "primary_caregiver")


def _task_applies(s: Statement, task_type: str) -> bool:
    if task_type in s.excluded_tasks:
        return False
    if s.applies_to_tasks and task_type not in s.applies_to_tasks:
        return False
    return True


def _to_minutes(hhmm: str) -> int:
    hours, minutes = hhmm.strip().split(":")
    return int(hours) * 60 + int(minutes)


def _intervals(start: int, end: int) -> list[tuple[int, int]]:
    if start == end:
        return [(0, MINUTES_PER_DAY)]
    if start < end:
        return [(start, end)]
    return [(start, MINUTES_PER_DAY), (0, end)]  # wraps midnight


def _time_applies(s: Statement, window_start: str, window_end: str) -> bool:
    if s.time_start is None or s.time_end is None:
        return True
    a = _intervals(_to_minutes(s.time_start), _to_minutes(s.time_end))
    b = _intervals(_to_minutes(window_start), _to_minutes(window_end))
    return any(s1 < e2 and s2 < e1 for (s1, e1) in a for (s2, e2) in b)


def _action(purpose: Purpose) -> str:
    return "brief" if purpose.task_type else "view"


def _summary(purpose: Purpose, count: int) -> str:
    noun = "preferences" if count != 1 else "preference"
    if purpose.task_type:
        return f"your {purpose.task_type.replace('_', ' ')} {noun} ({count})"
    return f"your {noun} ({count})"

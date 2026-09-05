"""THE visibility resolver -- the one choke point for reading preference data (P1).

    resolve(db, elder_id, actor, purpose) -> statements[]

Every path in (brief generation, the elder's own view, a family member
browsing, an export) calls this. No other module issues a SELECT against
``preference_statement``; ``backend/tests/test_resolver.py`` enforces that.

Order applied: capacity mode, actor identity, per-statement ``hidden_from``,
purpose scoping (task and time for workers; unrestricted for the elder),
then an access-log row. The log write is not optional and not conditional.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from brief_builder.contract import Statement, VisitContext
from brief_builder.scope import task_applies, time_applies

from ..models import Elder, Person, PreferenceStatement
from ..services import access_log

ActorKind = Literal["elder", "person", "worker"]
PurposeKind = Literal["view", "brief", "export"]


@dataclass(frozen=True)
class Actor:
    kind: ActorKind
    person_id: int | None
    label: str  # what the elder will read in her access log

    @classmethod
    def elder(cls, elder: Elder) -> "Actor":
        return cls("elder", None, elder.display_name)

    @classmethod
    def person(cls, person: Person) -> "Actor":
        return cls("person", person.id, person.name)

    @classmethod
    def worker(cls, name: str, person_id: int | None = None) -> "Actor":
        return cls("worker", person_id, name)


@dataclass(frozen=True)
class Purpose:
    kind: PurposeKind
    task_type: str | None = None
    start: datetime | None = None
    end: datetime | None = None

    @classmethod
    def view(cls) -> "Purpose":
        return cls("view")

    @classmethod
    def brief(cls, task_type: str, start: datetime, end: datetime) -> "Purpose":
        return cls("brief", task_type, start, end)


def _is_representative(db: Session, elder: Elder, actor: Actor) -> bool:
    """In ``mandated`` mode the primary caregiver acts for the elder."""
    if elder.capacity_mode != "mandated" or actor.kind != "person" or actor.person_id is None:
        return False
    person = db.get(Person, actor.person_id)
    return bool(person and person.role == "primary_caregiver")


def _summary(purpose: Purpose, count: int) -> str:
    noun = "preferences" if count != 1 else "preference"
    if purpose.kind == "brief" and purpose.task_type:
        return f"your {purpose.task_type.replace('_', ' ')} {noun} ({count})"
    return f"your {noun} ({count})"


def resolve(
    db: Session,
    elder_id: int,
    actor: Actor,
    purpose: Purpose,
    *,
    include_inactive: bool = False,
) -> list[PreferenceStatement]:
    elder = db.get(Elder, elder_id)
    if elder is None:
        return []

    # 1. capacity mode -- decides who counts as "the elder".
    elder_equivalent = actor.kind == "elder" or _is_representative(db, elder, actor)

    # 2. actor identity -- the elder sees her whole record; everyone else sees active rows.
    query = select(PreferenceStatement).where(PreferenceStatement.elder_id == elder_id)
    if not (elder_equivalent and include_inactive):
        query = query.where(PreferenceStatement.status == "active")
    rows = list(db.scalars(query.order_by(PreferenceStatement.id)))

    # 3. per-statement hidden_from -- never applied to the elder herself.
    if not elder_equivalent and actor.person_id is not None:
        rows = [r for r in rows if actor.person_id not in (r.hidden_from or [])]

    # 4. purpose scoping -- task and time window, workers only.
    if actor.kind == "worker":
        if purpose.task_type is None or purpose.start is None or purpose.end is None:
            rows = []  # a worker with no visit scope sees nothing
        else:
            ctx = VisitContext(
                task_type=purpose.task_type,
                scheduled_start=purpose.start.strftime("%H:%M"),
                scheduled_end=purpose.end.strftime("%H:%M"),
                worker_role="",
                worker_language="",
            )
            rows = [r for r in rows if task_applies(to_contract(r), ctx.task_type) and time_applies(to_contract(r), ctx)]

    # 5. the access-log row. Always.
    access_log.record(
        db,
        elder_id,
        actor_label=actor.label,
        action=purpose.kind,
        target_summary=_summary(purpose, len(rows)),
    )
    return rows


def to_contract(row: PreferenceStatement) -> Statement:
    """Convert an ORM row into the dataclass the brief builder understands."""
    return Statement(
        id=row.id,
        statement=row.statement,
        category=row.category,
        applies_to_tasks=list(row.applies_to_tasks or []),
        excluded_tasks=list(row.excluded_tasks or []),
        time_start=row.time_start,
        time_end=row.time_end,
    )

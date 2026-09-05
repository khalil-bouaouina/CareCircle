"""Request-scoped dependencies: the demo "session" and actor identification.

Real authentication is deliberately out of scope (architecture.md section 11).
For the demo, a caller identifies itself with headers:

    X-Actor-Person-Id: <person id>     -- caregiver or family member
    X-Actor: elder                     -- the elder herself
    X-Elder-Id: <elder id>             -- optional, defaults to 1

Workers never send these; they are identified only by the token in the URL.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .db import get_db
from .models import Elder, Person
from .security.resolver import Actor


@dataclass
class Session_:
    """Who is calling, and about which elder."""

    elder: Elder
    actor: Actor
    person: Person | None  # None when the actor is the elder

    @property
    def role(self) -> str | None:
        return self.person.role if self.person else None


def get_elder(
    db: Session = Depends(get_db),
    x_elder_id: int = Header(default=1, alias="X-Elder-Id"),
) -> Elder:
    elder = db.get(Elder, x_elder_id)
    if elder is None:
        raise HTTPException(404, "Unknown elder")
    return elder


def current_session(
    db: Session = Depends(get_db),
    elder: Elder = Depends(get_elder),
    x_actor: str | None = Header(default=None, alias="X-Actor"),
    x_actor_person_id: int | None = Header(default=None, alias="X-Actor-Person-Id"),
) -> Session_:
    if x_actor == "elder":
        return Session_(elder=elder, actor=Actor.elder(elder), person=None)
    if x_actor_person_id is not None:
        person = db.get(Person, x_actor_person_id)
        if person is None or person.elder_id != elder.id or person.role == "worker":
            raise HTTPException(403, "Unknown person for this elder")
        return Session_(elder=elder, actor=Actor.person(person), person=person)
    raise HTTPException(401, "Send X-Actor: elder or X-Actor-Person-Id: <id>")


def elder_session(session: Session_ = Depends(current_session)) -> Session_:
    if session.actor.kind != "elder":
        raise HTTPException(403, "This surface is for the elder")
    return session


def person_session(session: Session_ = Depends(current_session)) -> Session_:
    if session.actor.kind != "person":
        raise HTTPException(403, "This surface is for family and caregivers")
    return session


def caregiver_session(session: Session_ = Depends(person_session)) -> Session_:
    if session.role != "primary_caregiver":
        raise HTTPException(403, "Only the primary caregiver can do this")
    return session

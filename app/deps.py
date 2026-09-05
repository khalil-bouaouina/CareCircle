"""Demo identity (architecture.md section 11: real auth is out of scope).

    X-Elder-Id: <id>            optional, defaults to 1
    X-Actor-Person-Id: <id>     caregiver routes only; defaults to the primary caregiver.
                                Send 2 to browse as the family member (Karim) and see hidden_from at work.

Workers never send these; they are identified only by the token in the URL.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException

from .models import Actor, Elder, Person
from .repositories import people


@dataclass
class Session_:
    elder: Elder
    actor: Actor
    person: Person | None  # None when the actor is the elder

    @property
    def role(self) -> str | None:
        return self.person.role if self.person else None


def current_elder(x_elder_id: int = Header(default=1, alias="X-Elder-Id")) -> Elder:
    elder = people.get_elder(x_elder_id)
    if elder is None:
        raise HTTPException(404, "Unknown elder")
    return elder


def elder_session(elder: Elder = Depends(current_elder)) -> Session_:
    return Session_(elder=elder, actor=Actor("elder", None, elder.display_name), person=None)


def person_session(
    elder: Elder = Depends(current_elder),
    x_actor_person_id: int | None = Header(default=None, alias="X-Actor-Person-Id"),
) -> Session_:
    """Caregiver console caller: a family member or the primary caregiver."""
    person = people.get_person(x_actor_person_id) if x_actor_person_id else people.get_primary_caregiver(elder.id)
    if person is None or person.elder_id != elder.id or person.role == "worker":
        raise HTTPException(403, "Unknown person for this elder")
    return Session_(elder=elder, actor=Actor("person", person.id, person.name), person=person)


def caregiver_session(session: Session_ = Depends(person_session)) -> Session_:
    if session.role != "primary_caregiver":
        raise HTTPException(403, "Only the primary caregiver can do this")
    return session

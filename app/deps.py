"""Identity and session resolution.

Supports:
1. Production authentication via signed session cookies (web browser).
2. Header fallback (X-Elder-Id, X-Actor-Person-Id) for API clients and demo tooling.
Workers never send these; they are identified only by the token in the URL.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import Depends, HTTPException, Request

from . import config
from .models import Actor, Elder, Person, UserAccount, UserElderLink
from .repositories import accounts, people
from .services import auth


@dataclass
class Session_:
    elder: Elder
    actor: Actor
    person: Person | None  # None when the actor is the elder
    user: UserAccount | None = None
    user_elders: list[tuple[Elder, UserElderLink]] = field(default_factory=list)

    @property
    def role(self) -> str | None:
        if self.person:
            return self.person.role
        if self.actor.kind == "elder":
            return "elder"
        return None


def _get_cookie_session(request: Request) -> dict | None:
    cookie = request.cookies.get(config.SESSION_COOKIE_NAME)
    return auth.decode_session_token(cookie) if cookie else None


def _require_auth_or_redirect(request: Request) -> None:
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        raise HTTPException(
            status_code=303,
            headers={"Location": f"/login?next={request.url.path}"},
        )
    raise HTTPException(status_code=401, detail="Authentication required")


def person_session(request: Request) -> Session_:
    """Caregiver console caller: family member or primary caregiver."""
    cookie_data = _get_cookie_session(request)

    if cookie_data:
        user_id = cookie_data.get("user_id")
        user = accounts.get_user_by_id(user_id) if user_id else None
        if user:
            user_elders = accounts.list_elders_for_user(user.id)
            active_elder_id = cookie_data.get("active_elder_id")

            elder: Elder | None = None
            active_link: UserElderLink | None = None
            if active_elder_id:
                for el, link in user_elders:
                    if el.id == active_elder_id:
                        elder = el
                        active_link = link
                        break
            if elder is None and user_elders:
                elder, active_link = user_elders[0]

            if elder is not None and active_link is not None:
                person = people.get_person(active_link.person_id) if active_link.person_id else None
                # If the user is linked as elder, they shouldn't view caregiver console unless they also have a caregiver person
                if active_link.role in ("primary_caregiver", "family"):
                    actor = Actor(
                        kind="person",
                        person_id=person.id if person else None,
                        label=person.name if person else user.name,
                    )
                    return Session_(
                        elder=elder,
                        actor=actor,
                        person=person,
                        user=user,
                        user_elders=user_elders,
                    )

    # Header fallback
    x_elder_id = request.headers.get("X-Elder-Id")
    x_actor_person_id = request.headers.get("X-Actor-Person-Id")

    if x_elder_id or "text/html" not in request.headers.get("accept", ""):
        elder_id = int(x_elder_id) if x_elder_id else 1
        elder = people.get_elder(elder_id)
        if elder is None:
            raise HTTPException(404, "Unknown elder")
        person = (
            people.get_person(int(x_actor_person_id))
            if x_actor_person_id
            else people.get_primary_caregiver(elder.id)
        )
        if person is None or person.elder_id != elder.id or person.role == "worker":
            raise HTTPException(403, "Unknown person for this elder")
        return Session_(
            elder=elder,
            actor=Actor("person", person.id, person.name),
            person=person,
            user=None,
            user_elders=[],
        )

    _require_auth_or_redirect(request)
    raise HTTPException(status_code=401, detail="Authentication required")


def caregiver_session(session: Session_ = Depends(person_session)) -> Session_:
    if session.role != "primary_caregiver":
        raise HTTPException(403, "Only the primary caregiver can do this")
    return session


def elder_session(request: Request) -> Session_:
    """Elder view caller: the elderly person herself."""
    cookie_data = _get_cookie_session(request)

    if cookie_data:
        user_id = cookie_data.get("user_id")
        user = accounts.get_user_by_id(user_id) if user_id else None
        if user:
            user_elders = accounts.list_elders_for_user(user.id)
            active_elder_id = cookie_data.get("active_elder_id")

            elder: Elder | None = None
            if active_elder_id:
                for el, _link in user_elders:
                    if el.id == active_elder_id:
                        elder = el
                        break
            if elder is None and user_elders:
                elder, _link = user_elders[0]

            if elder is not None:
                return Session_(
                    elder=elder,
                    actor=Actor("elder", None, elder.display_name),
                    person=None,
                    user=user,
                    user_elders=user_elders,
                )

    # Header fallback
    x_elder_id = request.headers.get("X-Elder-Id")
    if x_elder_id or "text/html" not in request.headers.get("accept", ""):
        elder_id = int(x_elder_id) if x_elder_id else 1
        elder = people.get_elder(elder_id)
        if elder is None:
            raise HTTPException(404, "Unknown elder")
        return Session_(
            elder=elder,
            actor=Actor("elder", None, elder.display_name),
            person=None,
            user=None,
            user_elders=[],
        )

    _require_auth_or_redirect(request)
    raise HTTPException(status_code=401, detail="Authentication required")

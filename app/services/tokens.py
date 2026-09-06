"""Visit tokens (B14).

The token carries no data; it is a lookup key into a scope the server owns.
Only the SHA-256 hash is stored. The raw token exists in exactly two places:
the URL, and the caregiver's screen at creation time.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta

from .. import config
from ..models import Visit
from ..repositories import visits


def new_token() -> tuple[str, str]:
    """(raw, hash)."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compute_window(scheduled_start: str, scheduled_end: str) -> tuple[str, str]:
    """(valid_from, valid_until), applying TOKEN_LEAD_MINUTES and TOKEN_TRAIL_HOURS."""
    start = datetime.fromisoformat(scheduled_start) - timedelta(minutes=config.TOKEN_LEAD_MINUTES)
    end = datetime.fromisoformat(scheduled_end) + timedelta(hours=config.TOKEN_TRAIL_HOURS)
    return start.isoformat(), end.isoformat()


def issue(visit_id: int, scheduled_start: str, scheduled_end: str) -> str:
    """Mint a token for an existing visit and return the raw value once."""
    raw, token_hash = new_token()
    valid_from, valid_until = compute_window(scheduled_start, scheduled_end)
    visits.set_token(visit_id, token_hash, valid_from, valid_until)
    return raw


def validate(raw: str, now: datetime | None = None) -> Visit | None:
    """Return the visit for a live token, else None.

    None when: unknown hash, state is completed or expired, or now is outside
    the window. Callers must not distinguish these cases to the worker.
    """
    now = now or datetime.now()
    visit = visits.get_visit_by_token_hash(hash_token(raw))
    if visit is None:
        return None
    if visit.state in ("completed", "expired"):
        return None
    if visit.token_valid_from and now < datetime.fromisoformat(visit.token_valid_from):
        return None
    if visit.token_expires_at and now > datetime.fromisoformat(visit.token_expires_at):
        visits.set_state(visit.id, "expired")
        return None
    return visit


def expire_stale(now: datetime | None = None) -> int:
    """Sweep: live visits whose window has passed become expired."""
    now = now or datetime.now()
    stale = visits.list_live_past_window(now.replace(microsecond=0).isoformat())
    for visit in stale:
        visits.set_state(visit.id, "expired")
    return len(stale)

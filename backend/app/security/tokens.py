"""Visit tokens (architecture.md section 8).

The token carries no data. It is a lookup key into a scope the server owns.
We store only the SHA-256 of the raw token; the raw value is returned once,
at visit creation, and never again.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Visit


def generate() -> str:
    return secrets.token_urlsafe(32)  # 32 random bytes


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def window(scheduled_start: datetime, scheduled_end: datetime) -> tuple[datetime, datetime]:
    """(valid_from, expires_at) = (start - 30 min, end + 2 h)."""
    return (
        scheduled_start - timedelta(minutes=settings.token_window_before_min),
        scheduled_end + timedelta(hours=settings.token_window_after_hours),
    )


@dataclass
class TokenError(Exception):
    status_code: int
    detail: str


def validate(db: Session, raw: str, now: datetime | None = None) -> Visit:
    """Return the visit for a live token or raise ``TokenError``.

    Lazily transitions a visit to ``expired`` when its window has passed.
    """
    from ..services import visits as visit_service  # local import: avoids a cycle

    now = now or datetime.now()
    visit = db.scalar(select(Visit).where(Visit.token_hash == hash_token(raw)))
    if visit is None:
        raise TokenError(404, "Unknown or burned link")

    if visit.state in ("completed", "expired"):
        raise TokenError(410, f"This link is no longer valid (visit {visit.state})")

    valid_from, _ = window(visit.scheduled_start, visit.scheduled_end)
    if visit.token_expires_at and now > visit.token_expires_at:
        visit_service.transition(db, visit, "expired")
        visit_service.burn_token(db, visit)
        raise TokenError(410, "This link has expired")
    if now < valid_from:
        raise TokenError(425, f"This link becomes active at {valid_from.strftime('%H:%M')}")

    return visit

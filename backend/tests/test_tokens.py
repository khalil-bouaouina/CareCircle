"""A5 -- token lifecycle and the visit state machine."""

from datetime import datetime, timedelta

import pytest

from app.models import Visit
from app.schemas import VisitCreate
from app.security import tokens
from app.services import visits as visit_service


def _create(db, start: datetime, end: datetime):
    return visit_service.create_visit(
        db,
        1,
        VisitCreate(
            worker_name="Test Worker",
            worker_role="personal_support_worker",
            task_type="bathing",
            scheduled_start=start,
            scheduled_end=end,
        ),
    )


def test_only_hash_is_stored(db):
    start = datetime(2026, 9, 10, 10)
    visit, raw = _create(db, start, start + timedelta(hours=1))
    assert visit.token_hash == tokens.hash_token(raw)
    assert raw not in (visit.token_hash or "")
    assert len(raw) >= 43  # 32 bytes urlsafe
    assert visit.token_expires_at == start + timedelta(hours=3)  # end + 2h


def test_window_before_and_after(db):
    start = datetime(2026, 9, 10, 10)
    visit, raw = _create(db, start, start + timedelta(hours=1))

    with pytest.raises(tokens.TokenError) as early:
        tokens.validate(db, raw, now=start - timedelta(minutes=31))
    assert early.value.status_code == 425

    assert tokens.validate(db, raw, now=start - timedelta(minutes=29)).id == visit.id
    assert tokens.validate(db, raw, now=start + timedelta(hours=2, minutes=59)).id == visit.id

    with pytest.raises(tokens.TokenError) as late:
        tokens.validate(db, raw, now=start + timedelta(hours=3, minutes=1))
    assert late.value.status_code == 410
    db.refresh(visit)
    assert visit.state == "expired" and visit.token_hash is None


def test_unknown_token(db):
    with pytest.raises(tokens.TokenError) as exc:
        tokens.validate(db, "nope")
    assert exc.value.status_code == 404


def test_state_machine(db):
    start = datetime(2026, 9, 10, 10)
    visit, _ = _create(db, start, start + timedelta(hours=1))
    assert visit.state == "scheduled"
    with pytest.raises(visit_service.IllegalTransition):
        visit_service.transition(db, visit, "completed")  # must be briefed first
    visit_service.transition(db, visit, "briefed")
    visit_service.transition(db, visit, "completed")
    with pytest.raises(visit_service.IllegalTransition):
        visit_service.transition(db, visit, "expired")  # terminal


def test_expire_stale_sweep(db):
    past = datetime.now() - timedelta(days=1)
    _create(db, past, past + timedelta(hours=1))
    assert visit_service.expire_stale(db) == 1
    assert db.query(Visit).filter(Visit.state == "expired", Visit.worker_name == "Test Worker").count() == 1


def test_end_before_start_rejected(db):
    start = datetime(2026, 9, 10, 10)
    with pytest.raises(ValueError):
        _create(db, start, start - timedelta(hours=1))

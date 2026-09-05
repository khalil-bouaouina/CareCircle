"""A4 -- the visibility resolver is the single read path, and it always logs."""

import re
from datetime import datetime
from pathlib import Path

from sqlalchemy import func, select

from app.models import AccessLog, Elder, Person
from app.security.resolver import Actor, Purpose, resolve

APP_DIR = Path(__file__).resolve().parents[1] / "app"


def _log_count(db) -> int:
    return db.scalar(select(func.count()).select_from(AccessLog))


def test_no_other_module_reads_preference_statements():
    """P1: exactly one function to audit. Anything else selecting the table is a bug."""
    pattern = re.compile(r"select\(\s*PreferenceStatement|query\(\s*PreferenceStatement")
    offenders = []
    for path in APP_DIR.rglob("*.py"):
        if path.name == "resolver.py":
            continue
        if pattern.search(path.read_text(encoding="utf-8")):
            offenders.append(str(path.relative_to(APP_DIR)))
    assert offenders == []


def test_elder_sees_everything_and_it_is_logged(db):
    elder = db.get(Elder, 1)
    before = _log_count(db)
    rows = resolve(db, 1, Actor.elder(elder), Purpose.view(), include_inactive=True)
    ids = {r.id for r in rows}
    assert {28, 29, 31} <= ids  # hidden-from-Karim rows and the retired one
    assert _log_count(db) == before + 1
    last = db.scalars(select(AccessLog).order_by(AccessLog.id.desc())).first()
    assert last.actor_label == "Fatima" and last.action == "view"


def test_family_member_does_not_see_rows_hidden_from_him(db):
    karim = db.get(Person, 2)
    leila = db.get(Person, 1)
    k_ids = {r.id for r in resolve(db, 1, Actor.person(karim), Purpose.view())}
    l_ids = {r.id for r in resolve(db, 1, Actor.person(leila), Purpose.view())}
    assert 28 not in k_ids and 29 not in k_ids
    assert 28 in l_ids and 29 in l_ids
    assert 31 not in l_ids  # retired rows are not shown to family


def test_worker_scope_task_and_time(db):
    day = datetime(2026, 9, 10)
    bathing = Purpose.brief("bathing", day.replace(hour=10), day.replace(hour=11))
    nursing = Purpose.brief("nursing_visit", day.replace(hour=16), day.replace(hour=16, minute=45))

    b_ids = {r.id for r in resolve(db, 1, Actor.worker("Marie-Ève Tremblay", 3), bathing)}
    n_ids = {r.id for r in resolve(db, 1, Actor.worker("Jonathan Roy", 4), nursing)}

    assert 1 in b_ids and 1 not in n_ids  # female worker: bathing only
    assert 2 in n_ids and 2 not in b_ids  # male nurse fine: nursing only
    assert 3 in n_ids and 3 not in b_ids  # prayer window 13:00-17:00 hits the 4pm visit only
    assert 14 in b_ids and 14 not in n_ids  # bathroom door: bathing only
    assert 8 in n_ids and 8 not in b_ids  # medication: nursing/medication only
    assert 31 not in b_ids and 31 not in n_ids  # retired never reaches a worker


def test_worker_without_visit_scope_sees_nothing(db):
    assert resolve(db, 1, Actor.worker("Someone"), Purpose.view()) == []


def test_mandated_mode_makes_representative_elder_equivalent(db):
    elder = db.get(Elder, 1)
    elder.capacity_mode = "mandated"
    db.commit()
    leila = db.get(Person, 1)
    karim = db.get(Person, 2)
    l_ids = {r.id for r in resolve(db, 1, Actor.person(leila), Purpose.view(), include_inactive=True)}
    k_ids = {r.id for r in resolve(db, 1, Actor.person(karim), Purpose.view(), include_inactive=True)}
    assert 31 in l_ids  # sees retired rows like the elder would
    assert 31 not in k_ids and 28 not in k_ids  # Karim is still just family


def test_access_log_summary_names_the_task(db):
    day = datetime(2026, 9, 10)
    resolve(db, 1, Actor.worker("Marie-Ève Tremblay", 3), Purpose.brief("bathing", day.replace(hour=10), day.replace(hour=11)))
    last = db.scalars(select(AccessLog).order_by(AccessLog.id.desc())).first()
    assert last.action == "brief"
    assert "bathing" in last.target_summary
    assert last.actor_label == "Marie-Ève Tremblay"

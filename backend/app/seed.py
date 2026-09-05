"""Loads data/seed_data.json and data/observation_codes.json. Person C authors, Person A loads."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import settings
from .db import drop_db, init_db
from .models import (
    Checkout,
    Elder,
    ObservationCode,
    Person,
    PreferenceStatement,
    ProposedUpdate,
    Visit,
)


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _read(path: Path):
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def is_seeded(db: Session) -> bool:
    return db.scalar(select(func.count()).select_from(Elder)) > 0


def load_seed(db: Session, data_dir: Path | None = None) -> None:
    data_dir = data_dir or settings.data_dir
    seed = _read(data_dir / "seed_data.json")
    codes = _read(data_dir / "observation_codes.json")

    for row in codes:
        db.add(ObservationCode(**row))

    db.add(Elder(**seed["elder"]))
    for row in seed.get("persons", []):
        db.add(Person(**row))
    db.flush()

    # Visits + check-outs come before statements so source_checkout_id can resolve.
    for row in seed.get("visits", []):
        checkout = row.pop("checkout", None)
        visit = Visit(
            **{**row, "scheduled_start": _dt(row["scheduled_start"]), "scheduled_end": _dt(row["scheduled_end"])}
        )
        db.add(visit)
        if checkout:
            db.add(
                Checkout(
                    **{**checkout, "visit_id": visit.id, "submitted_at": _dt(checkout["submitted_at"])}
                )
            )
    db.flush()

    elder_id = seed["elder"]["id"]
    for row in seed.get("statements", []):
        db.add(PreferenceStatement(elder_id=elder_id, **row))

    for row in seed.get("proposed_updates", []):
        db.add(ProposedUpdate(**row))

    db.commit()


def seed_if_empty(db: Session) -> bool:
    if is_seeded(db):
        return False
    load_seed(db)
    return True


def reset(db: Session) -> None:
    """Drop everything, recreate, reseed. For demo runs."""
    db.close()
    drop_db()
    init_db()
    load_seed(db)

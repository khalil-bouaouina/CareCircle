"""Demo dataset (B18). Loads data/seed_data.json and data/observation_codes.json.

Do not undervalue this file: a believable dataset is worth more than any single
feature. Guarded so it does not double-seed on reload.

Fold-back demo note: the seeded visits carry ``refused_bath`` twice. With
``PROPOSAL_THRESHOLD = 3`` a live check-out reporting ``refused_bath`` is the
third occurrence and fires a proposal on stage. The seeded pending proposal must
therefore NOT use the ``refused_bath`` template, or the "identical pending
proposal" rule would suppress it.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import config
from .db import drop_db, init_db, query_one
from .repositories import accounts, checkouts, observation_codes, people, proposals, statements, visits
from .services import auth, tokens



def _read(path: Path):
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def is_seeded() -> bool:
    row = query_one("SELECT COUNT(*) AS n FROM elder")
    return bool(row and row["n"] > 0)


def seed_demo_users_if_missing(elder_id: int = 1) -> None:
    if accounts.get_user_by_email("sarah@carecircle.demo") is None:
        demo_users = [
            ("sarah@carecircle.demo", "Sarah B.", "primary_caregiver", 1, elder_id),
            ("karim@carecircle.demo", "Karim B.", "family", 2, elder_id),
            ("fatima@carecircle.demo", "Fatima B.", "elder", None, elder_id),
        ]
        for email, name, role, person_id, e_id in demo_users:
            uid = accounts.create_user(email, auth.hash_password("demo1234"), name)
            accounts.link_user_to_elder(uid, e_id, person_id, role)


def seed(reset: bool = False, data_dir: Path | None = None) -> bool:
    """Seed if empty. With ``reset`` delete the database file first. Returns True if seeded."""
    if reset:
        drop_db()
        init_db()
    elif is_seeded():
        seed_demo_users_if_missing()
        return False


    data_dir = data_dir or config.DATA_DIR
    data = _read(data_dir / "seed_data.json")
    codes = _read(data_dir / "observation_codes.json")

    for row in codes:
        observation_codes.create_code(
            row["code"], row["label_en"], row["label_fr"], row["category"], row.get("suggested_statement")
        )

    e = data["elder"]
    people.create_elder(e["id"], e["display_name"], e.get("primary_language", "fr"), e.get("capacity_mode", "self"))
    for p in data.get("persons", []):
        people.create_person(p["id"], p["elder_id"], p["name"], p["role"], p.get("language", "fr"))

    # Visits + check-outs before statements so source_checkout_id can resolve.
    for v in data.get("visits", []):
        valid_from, valid_until = tokens.compute_window(v["scheduled_start"], v["scheduled_end"])
        visits.create_visit(
            v["elder_id"], v["worker_name"], v["worker_role"], v.get("worker_language", "fr"), v["task_type"],
            v["scheduled_start"], v["scheduled_end"],
            token_hash=None, token_valid_from=valid_from, token_expires_at=valid_until,
            state=v.get("state", "completed"), visit_id=v["id"],
        )
        c = v.get("checkout")
        if c:
            checkouts.create_checkout(
                v["id"], c["completion"], c.get("observation_codes", []), c.get("note_text"),
                submitted_at=c["submitted_at"], checkout_id=c["id"],
            )

    for s in data.get("statements", []):
        statements.create_statement(
            e["id"], s["statement"], s["category"], s.get("applies_to_tasks", []), s.get("excluded_tasks", []),
            s.get("time_start"), s.get("time_end"), s.get("hidden_from", []),
            status=s.get("status", "active"), source_checkout_id=s.get("source_checkout_id"),
            statement_id=s["id"],
        )

    for p in data.get("proposed_updates", []):
        proposals.create_proposal(
            p["elder_id"], p.get("source_checkout_id"), p["suggested_statement"],
            status=p.get("status", "pending"), proposal_id=p["id"],
        )

    # Seed user accounts for authentication
    demo_users = [
        ("sarah@carecircle.demo", "Sarah B.", "primary_caregiver", 1, e["id"]),
        ("karim@carecircle.demo", "Karim B.", "family", 2, e["id"]),
        ("fatima@carecircle.demo", "Fatima B.", "elder", None, e["id"]),
    ]
    for email, name, role, person_id, elder_id in demo_users:
        uid = accounts.create_user(email, auth.hash_password("demo1234"), name)
        accounts.link_user_to_elder(uid, elder_id, person_id, role)

    return True


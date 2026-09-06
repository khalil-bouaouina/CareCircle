"""The demo history (B21).

Do not undervalue this file. A believable history is worth more than any single
feature, and for this problem the history *is* the demo: six workers have been
through this apartment, and the seventh should arrive knowing what they learned.

Fold-back rehearsal note: two seeded check-outs carry ``refused_equipment``.
With ``PATTERN_THRESHOLD = 3`` a live check-out reporting it is the third
occurrence and fires a proposal on stage. If you raise the seed to three, the
demo produces nothing.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from . import config
from .db import drop_db, init_db, query_one
from .repositories import (checkouts, observation_codes, people, proposals,
                           statements, visits, workers)
from .services import tokens

# --- the cast -----------------------------------------------------------------

ELDER = ("Amina Belkacem", "fr", "assisted")

FAMILY = [
    ("Leila", "primary_caregiver"),   # 1 - the daughter, runs the console
    ("Karim", "family"),              # 2 - the son, lives out of province
    ("Nadia", "family"),              # 3 - the niece
    ("Youssef", "family"),            # 4 - the grandson
]

# Six workers. Six matters: it is the number in the continuity counter, and a
# counter that says "6 previous workers" is only honest if six workers exist.
WORKERS = [
    ("Marie-Ève Tremblay", "care worker", "fr"),   # 1
    ("Jonathan Roy", "care worker", "fr"),         # 2
    ("Fatima Diallo", "care worker", "fr"),        # 3
    ("Sophie Lambert", "nurse", "fr"),             # 4
    ("Amadou Sy", "care worker", "fr"),            # 5
    ("Claire Bergeron", "care worker", "fr"),      # 6
    ("Nour Haddad", "care worker", "fr"),          # 7 - arrives today, has never been here
]

# --- past visits, oldest first. (worker_id, task, days_ago, hour, checkout) ----
# checkout = (completion, [codes], note_text, handover_note)

VISITS = [
    (2, "meal", 34, 12, ("yes", ["ate_well", "in_good_spirits"], None,
                         "Sit down at the table with her. She won't eat if you stand over her.")),
    (4, "nursing_visit", 27, 9, ("yes", ["family_member_present"], None, None)),
    (1, "bathing", 21, 10, ("partial", ["refused_equipment", "needed_more_time"], None,
                            "She said yes to the shower chair and then wouldn't sit on it. "
                            "Offering it once is enough.")),
    (3, "dressing", 14, 9, ("yes", ["seemed_more_tired"], None,
                            "Lay the clothes out in the order she puts them on. "
                            "She dresses herself if you do.")),
    (5, "bathing", 9, 10, ("partial", ["refused_equipment"], None, None)),
    (6, "housekeeping", 4, 14, ("yes", ["low_on_supplies"], "Detergent is nearly out.", None)),
]

# The seventh worker. She is the whole argument: she has never met this person,
# and her brief carries what the first six worked out. Scheduled to start shortly
# so the demo link on the role picker is live the moment the app boots.
UPCOMING = (7, "bathing", 15)   # (worker_id, task, minutes from now)

# --- ~30 statements -----------------------------------------------------------
# (statement, kind, category, source, tasks, time_start, time_end, hidden_from,
#  origin_visit_index, confirmations)

_P = "preference"
_A = "approach"

STATEMENTS = [
    # -- preferences, written by the family (18) --
    ("A woman for bathing and dressing, please. Maman is very uncomfortable otherwise.",
     _P, "care", "family", ["bathing", "dressing"], None, None, [], None, 0),
    ("A male nurse is fine for blood draws, injections and blood pressure.",
     _P, "care", "family", ["nursing_visit"], None, None, [], None, 0),
    ("She prays in the early afternoon. If she is on the mat, wait — it takes about ten minutes.",
     _P, "observance", "family", [], "13:00", "17:00", [], None, 0),
    ("Shoes off at the door. There is a basket of slippers just inside.",
     _P, "routine", "family", [], None, None, [], None, 0),
    ("No pork and no alcohol in the apartment, including in cooking.",
     _P, "observance", "family", ["meal", "housekeeping"], None, None, [], None, 0),
    ("She agrees to everything to be polite. Check twice before you leave.",
     _P, "communication", "family", [], None, None, [], None, 0),
    ("Speak French. Her English goes when she is tired.",
     _P, "communication", "family", [], None, None, [], None, 0),
    ("Knock and wait. Don't use the key unless she doesn't answer twice.",
     _P, "routine", "family", [], None, None, [], None, 0),
    ("Tea first, tasks after. It is not optional to her.",
     _P, "routine", "family", [], None, None, [], None, 0),
    ("She keeps her headscarf by the door. Hand it to her before anyone else comes in.",
     _P, "observance", "family", [], None, None, [], None, 0),
    ("The hallway rug slides. Please check it before she walks the corridor.",
     _P, "safety", "family", [], None, None, [], None, 0),
    ("Her hearing aid is in the blue dish. She forgets it.",
     _P, "care", "family", [], None, None, [], None, 0),
    ("Don't move anything in the kitchen. She needs to find it where she left it.",
     _P, "routine", "family", ["housekeeping", "meal"], None, None, [], None, 0),
    ("Call me, not my brother, if anything is wrong. My number is on the fridge.",
     _P, "communication", "family", [], None, None, [], None, 0),
    ("She fasts during Ramadan. Don't offer food or drink before sunset.",
     _P, "observance", "family", ["meal"], None, None, [], None, 0),
    ("Morning visits before 9:30 are too early. She is not up.",
     _P, "routine", "family", [], "06:00", "09:30", [], None, 0),
    # two hidden from a specific family member (Karim, person 2)
    ("She has been low since Papa died and doesn't want it discussed.",
     _P, "communication", "family", [], None, None, [2], None, 0),
    ("She is embarrassed about the incontinence pads. Don't mention them in front of visitors.",
     _P, "care", "family", ["bathing", "dressing"], None, None, [2, 4], None, 0),

    # -- approaches, written by workers (10) --
    ("Sit down at the table with her — she won't eat if you stand over her.",
     _A, "care", "worker", ["meal"], None, None, [], 0, 3),
    ("Lay her clothes out in the order she puts them on. She dresses herself if you do.",
     _A, "care", "worker", ["dressing"], None, None, [], 3, 2),
    ("Say your name and why you're there at the door, every time. She won't ask.",
     _A, "communication", "worker", [], None, None, [], 1, 2),
    ("Run the water before she comes in. The noise startles her.",
     _A, "care", "worker", ["bathing"], None, None, [], 2, 1),
    ("She'll refuse the shower chair the first time. Offer it once, then leave it.",
     _A, "care", "worker", ["bathing"], None, None, [], 2, 0),
    ("Put the radio on low while you clean. She'll stay in the room and talk.",
     _A, "communication", "worker", ["housekeeping"], None, None, [], 5, 0),
    ("Write the date on the whiteboard when you arrive. It saves ten minutes of worry.",
     _A, "communication", "worker", [], None, None, [], 4, 1),
    ("Warm the towels on the radiator first. She stops bracing against the cold.",
     _A, "care", "worker", ["bathing"], None, None, [], 4, 0),
    ("She takes the pills with yoghurt, not water. Ask her.",
     _A, "care", "worker", ["medication_support"], None, None, [], 1, 2),
    ("Take the bins out on the way in, not on the way out. She hates the smell during tea.",
     _A, "routine", "worker", ["housekeeping"], None, None, [], 5, 0),

    # -- corrections, written by the caregiver (2) --
    ("Never let her walk to the bathroom alone after a bath. This must not happen again.",
     _P, "safety", "correction", ["bathing"], None, None, [], 2, 0),
    ("Do not reschedule a visit without calling me first.",
     _P, "communication", "correction", [], None, None, [], 5, 0),
]

# Indexes into STATEMENTS that were edited two days ago -- after every seeded
# visit, so any returning worker has exactly these to catch up on.
RECENTLY_CHANGED = {10, 25}   # the sliding hallway rug; warming the towels

# Observation code categories, for the reference table only.
_CODE_CATEGORY = {
    "didnt_finish_meal": "care", "ate_well": "care", "seemed_more_tired": "care",
    "in_good_spirits": "routine", "unsteady_on_feet": "safety",
    "refused_equipment": "care", "skin_looks_irritated": "care",
    "confused_about_date": "care", "low_on_supplies": "routine",
    "needed_more_time": "routine", "seemed_in_pain": "care",
    "family_member_present": "communication",
}
_CODE_FR = {
    "didnt_finish_meal": "N'a pas fini son repas", "ate_well": "A bien mangé",
    "seemed_more_tired": "Semblait plus fatiguée", "in_good_spirits": "De bonne humeur",
    "unsteady_on_feet": "Instable sur ses jambes", "refused_equipment": "A refusé l'équipement",
    "skin_looks_irritated": "Peau irritée", "confused_about_date": "Confuse sur la date",
    "low_on_supplies": "Fournitures presque épuisées", "needed_more_time": "A eu besoin de plus de temps",
    "seemed_in_pain": "Semblait souffrir", "family_member_present": "Un proche était présent",
}


def is_seeded() -> bool:
    row = query_one("SELECT COUNT(*) AS n FROM preference_statement")
    return bool(row and row["n"] > 0)


def seed(force: bool = False) -> bool:
    """Build the demo history. Guarded against double-seeding unless ``force``."""
    if force:
        drop_db()
        init_db()
    elif is_seeded():
        return False

    for code, label in config.OBSERVATION_CODES:
        observation_codes.upsert_code(code, label, _CODE_FR.get(code, label),
                                      _CODE_CATEGORY.get(code, "care"))

    name, language, capacity = ELDER
    elder_id = people.create_elder(name, language, capacity)
    for person_name, role in FAMILY:
        people.create_person(elder_id, person_name, role)
    for worker_name, role, lang in WORKERS:
        workers.create_worker(worker_name, role, lang)

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    visit_ids: list[int] = []
    for worker_id, task, days_ago, hour, checkout in VISITS:
        start = today - timedelta(days=days_ago) + timedelta(hours=hour)
        end = start + timedelta(hours=1)
        visit_id = visits.create_visit(
            elder_id, worker_id, task, start.isoformat(), end.isoformat(),
            token_hash=None, token_valid_from=None, token_expires_at=None, state="completed",
        )
        visit_ids.append(visit_id)
        completion, codes, note, handover = checkout
        checkouts.create_checkout(visit_id, completion, codes, note, handover,
                                  submitted_at=end.isoformat())

    # Everything is backdated to before the oldest visit, EXCEPT the two rows in
    # RECENTLY_CHANGED. That is what makes a returning worker's brief read
    # "2 things have changed" instead of repeating the whole record at her.
    recent = (today - timedelta(days=2)).isoformat()
    for i, row in enumerate(STATEMENTS):
        text, kind, category, source, tasks, t0, t1, hidden, origin, confirms = row
        created = (today - timedelta(days=120 - i)).isoformat()
        statements.create_statement(
            elder_id, text, kind, category, source,
            applies_to_tasks=list(tasks or []),
            time_start=t0, time_end=t1, hidden_from=hidden,
            origin_visit_id=visit_ids[origin] if origin is not None else None,
            confirmations=confirms, created_at=created,
            updated_at=recent if i in RECENTLY_CHANGED else created,
        )

    worker_id, task, minutes = UPCOMING
    start = datetime.now().replace(second=0, microsecond=0) + timedelta(minutes=minutes)
    end = start + timedelta(hours=1)
    valid_from, valid_until = tokens.compute_window(start.isoformat(), end.isoformat())
    visits.create_visit(elder_id, worker_id, task, start.isoformat(), end.isoformat(),
                        token_hash=None, token_valid_from=valid_from,
                        token_expires_at=valid_until, state="scheduled")

    # One pending proposal so the inbox isn't empty on stage. It must NOT reuse
    # a PATTERN_TEMPLATES phrasing, or the duplicate guard would suppress the
    # live one.
    proposals.create_proposal(
        elder_id, source_checkout_id=6, origin_kind="handover", suggested_kind="approach",
        suggested_statement="Check the detergent and the bin bags before you leave — "
                            "she won't ask for them.",
    )
    return True

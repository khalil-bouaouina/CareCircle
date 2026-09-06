"""Environment and closed lists (B1). Module-level constants, no class.

Nothing here may crash when ``ANTHROPIC_API_KEY`` is None -- that is the
fallback path, and the demo must work with the key removed.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(REPO_ROOT / ".env")


# --- closed lists -------------------------------------------------------------

TASK_TYPES: list[str] = [
    "bathing",
    "dressing",
    "meal",
    "medication_support",
    "housekeeping",
    "nursing_visit",
    "transport",
    "companionship",
]

CATEGORIES: list[str] = ["care", "communication", "routine", "observance", "safety"]

# A worker cannot invent a code. That is what makes the visit log countable
# later, and what keeps a worker from typing something that reads like a
# clinical judgement.
OBSERVATION_CODES: list[tuple[str, str]] = [
    ("didnt_finish_meal", "Didn't finish meal"),
    ("ate_well", "Ate well"),
    ("seemed_more_tired", "Seemed more tired"),
    ("in_good_spirits", "In good spirits"),
    ("unsteady_on_feet", "Unsteady on feet"),
    ("refused_equipment", "Refused equipment"),
    ("skin_looks_irritated", "Skin looks irritated"),
    ("confused_about_date", "Confused about the date"),
    ("low_on_supplies", "Low on supplies"),
    ("needed_more_time", "Needed more time than usual"),
    ("seemed_in_pain", "Seemed in pain"),
    ("family_member_present", "Family member present"),
]

STATEMENT_KINDS: tuple[str, ...] = ("preference", "approach")
STATEMENT_SOURCES: tuple[str, ...] = ("family", "worker", "correction")

CAPACITY_MODES: list[str] = ["self", "assisted", "mandated"]
COMPLETIONS: list[str] = ["yes", "partial", "no"]
VISIT_STATES: list[str] = ["scheduled", "briefed", "completed", "expired"]

MAX_BRIEF_LINES: int = 6

# Three occurrences read as "this is a pattern"; two read as "this happened".
PATTERN_THRESHOLD: int = 3
PATTERN_WINDOW: int = 5

# --- token window -------------------------------------------------------------

TOKEN_LEAD_MINUTES: int = 30
TOKEN_TRAIL_HOURS: int = 2

# --- environment --------------------------------------------------------------

DATA_DIR: Path = Path(os.getenv("ELDERCARE_DATA_DIR", REPO_ROOT / "data"))
DB_PATH: str = os.getenv("ELDERCARE_DB_PATH", str(DATA_DIR / "carecircle.db"))
BASE_URL: str = os.getenv("ELDERCARE_BASE_URL", "http://127.0.0.1:8000")

ANTHROPIC_API_KEY: str | None = os.getenv("ANTHROPIC_API_KEY") or None
ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")

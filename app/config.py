"""Environment and closed lists. Module-level constants, no class (B1).

Nothing in the app may crash when ``ANTHROPIC_API_KEY`` is None -- that is the
fallback path and the demo must work with the key removed.
"""

from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(REPO_ROOT / ".env")


# --- closed lists (architecture.md section 4) --------------------------------

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

CAPACITY_MODES: list[str] = ["self", "assisted", "mandated"]
COMPLETIONS: list[str] = ["yes", "partial", "no"]
VISIT_STATES: list[str] = ["scheduled", "briefed", "completed", "expired"]

MAX_BRIEF_LINES: int = 6

# --- token window (architecture.md section 8) ---------------------------------

TOKEN_LEAD_MINUTES: int = 30
TOKEN_TRAIL_HOURS: int = 2

# --- fold-back (guide B13) ----------------------------------------------------

PROPOSAL_THRESHOLD: int = 3  # a code seen this many times in the recent window is a pattern
PROPOSAL_WINDOW: int = 5  # ...over this many most-recent check-outs

# --- environment --------------------------------------------------------------

DATA_DIR: Path = Path(os.getenv("ELDERCARE_DATA_DIR", REPO_ROOT / "data"))
DB_PATH: str = os.getenv("ELDERCARE_DB_PATH", str(DATA_DIR / "eldercare.db"))
FRONTEND_BASE_URL: str = os.getenv("ELDERCARE_FRONTEND_BASE_URL", "http://127.0.0.1:8000")
SEED_ON_STARTUP: bool = os.getenv("ELDERCARE_SEED_ON_STARTUP", "1") not in ("0", "false", "False")
ANTHROPIC_API_KEY: str | None = os.getenv("ANTHROPIC_API_KEY") or None

# --- authentication & security ------------------------------------------------
SESSION_SECRET_KEY: str = os.getenv("ELDERCARE_SECRET_KEY", "carecircle-secret-key-change-in-production-2026")
SESSION_COOKIE_NAME: str = "carecircle_session"
ENABLE_DEMO_RESET: bool = os.getenv("ELDERCARE_ENABLE_DEMO_RESET", "1") not in ("0", "false", "False")


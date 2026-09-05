"""Check-out -> suggested statement.

Rules over repeated observation codes. The model is not involved: a code
that has now been reported at least ``REPEAT_THRESHOLD`` times across this
check-out and the recent ones is durable enough to propose. The phrasing
comes from the ``suggested_statement`` template on the observation code.
Free-text notes alone never produce a proposal (that is model territory,
to be added later).
"""

from __future__ import annotations

import json
from collections import Counter
from functools import lru_cache
from pathlib import Path

REPEAT_THRESHOLD = 2

_DEFAULT_CODES_PATH = Path(__file__).resolve().parent.parent / "data" / "observation_codes.json"


@lru_cache(maxsize=4)
def load_observation_codes(path: str | None = None) -> dict[str, dict]:
    """Return observation codes keyed by code. Empty dict if the file is missing."""
    p = Path(path) if path else _DEFAULT_CODES_PATH
    if not p.exists():
        return {}
    with p.open(encoding="utf-8") as fh:
        rows = json.load(fh)
    return {row["code"]: row for row in rows if isinstance(row, dict) and "code" in row}


def suggest_statement(
    observation_codes: list[str],
    note_text: str | None,
    recent_checkouts: list[dict],
    *,
    codes_path: str | None = None,
    threshold: int = REPEAT_THRESHOLD,
) -> str | None:
    """Returns a suggested statement, or None if nothing durable.

    ``recent_checkouts`` are dicts with at least an ``observation_codes`` list,
    ordered most recent first. The current check-out is NOT in that list.
    """
    if not observation_codes:
        return None

    counts: Counter[str] = Counter(dict.fromkeys(observation_codes, 1))
    for prior in recent_checkouts:
        for code in set(prior.get("observation_codes") or []):
            if code in counts:
                counts[code] += 1

    catalogue = load_observation_codes(codes_path)

    # Most repeated first; ties broken by the order the worker listed them.
    for code in sorted(observation_codes, key=lambda c: -counts[c]):
        if counts[code] < threshold:
            continue
        template = (catalogue.get(code) or {}).get("suggested_statement")
        if template:
            return template
    return None

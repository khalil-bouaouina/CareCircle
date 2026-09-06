"""Enforcement and fallback (A4). The enforcement point for the whole
no-hallucination guarantee.

Three properties this file holds:

* it never raises, so a bad response degrades rather than crashes;
* it never repairs a malformed line, it drops it, because repairing means
  inventing;
* the id membership check on line 1 of the loop is the single line that makes
  *"the model cannot invent facts"* a true statement about the system rather
  than a claim about the prompt.

The correction and confirmation flags are set here, **from the database
record**, not taken from the model's response. The model may suggest that
something is critical; it cannot demote a correction.
"""

from __future__ import annotations

from .. import config
from ..models import BriefLine, Statement

MAX_TEXT_LEN = 120


def validate_lines(
    raw_lines: list[dict],
    candidate_ids: set[int],
    statements_by_id: dict[int, Statement],
) -> list[BriefLine]:
    kept: list[BriefLine] = []
    seen: set[int] = set()

    for entry in raw_lines or []:
        if not isinstance(entry, dict):
            continue
        sid = entry.get("statement_id")
        if not isinstance(sid, int) or isinstance(sid, bool) or sid not in candidate_ids:
            continue
        if sid in seen:
            continue
        text = entry.get("text")
        if not isinstance(text, str) or not text.strip() or len(text.strip()) > MAX_TEXT_LEN:
            continue

        source = statements_by_id[sid]
        is_correction = source.source == "correction"
        seen.add(sid)
        kept.append(BriefLine(
            statement_id=sid,
            text=text.strip(),
            critical=bool(entry.get("critical", False)) or is_correction,
            is_correction=is_correction,
            confirmations=source.confirmations,
        ))

    # Stable sort: corrections first, then criticals, model order preserved within groups.
    kept.sort(key=lambda l: (not l.is_correction, not l.critical))
    return kept[: config.MAX_BRIEF_LINES]


def fallback_lines(candidates: list[Statement]) -> list[BriefLine]:
    """Render candidates verbatim: corrections first, then by config.CATEGORIES order."""
    order = {c: i for i, c in enumerate(config.CATEGORIES)}
    ordered = sorted(
        candidates,
        key=lambda s: (s.source != "correction", order.get(s.category, len(order)), s.id),
    )
    return [
        BriefLine(
            statement_id=s.id,
            text=s.statement,
            critical=s.source == "correction",
            is_correction=s.source == "correction",
            confirmations=s.confirmations,
        )
        for s in ordered[: config.MAX_BRIEF_LINES]
    ]

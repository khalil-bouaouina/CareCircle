"""Deterministic render used when the model is unavailable or unusable.

Renders the Stage 1 candidates verbatim, in category order, safety first.
This is what makes the product work with the API key removed.

The fallback deliberately does NOT slice to six: without a model to rank
relevance, dropping lines would silently hide scoped, consented statements
from the worker. Showing every candidate is the safe degraded behaviour.
"""

from __future__ import annotations

from .contract import BriefLine, Statement

CATEGORY_ORDER: tuple[str, ...] = (
    "safety",
    "care",
    "observance",
    "routine",
    "communication",
)

CRITICAL_CATEGORIES: frozenset[str] = frozenset({"safety"})


def _rank(category: str) -> int:
    try:
        return CATEGORY_ORDER.index(category)
    except ValueError:
        return len(CATEGORY_ORDER)


def render_fallback(candidates: list[Statement]) -> list[BriefLine]:
    ordered = sorted(candidates, key=lambda s: _rank(s.category))
    return [
        BriefLine(
            statement_id=s.id,
            text=s.statement,
            critical=s.category in CRITICAL_CATEGORIES,
        )
        for s in ordered
    ]

"""brief_builder -- pure Python, no database, no HTTP, no FastAPI import.

Exposes ``build_brief`` and ``suggest_statement`` (see ``contract.py``).
"""

from __future__ import annotations

from .contract import (
    CATEGORIES,
    MAX_BRIEF_LINES,
    TASK_TYPES,
    BriefLine,
    BriefResult,
    Statement,
    VisitContext,
)
from .fallback import render_fallback
from .proposals import suggest_statement
from .scope import filter_scope
from .select import ModelClient, get_default_client, select_lines
from .validate import validate_lines

__all__ = [
    "CATEGORIES",
    "MAX_BRIEF_LINES",
    "TASK_TYPES",
    "BriefLine",
    "BriefResult",
    "Statement",
    "VisitContext",
    "build_brief",
    "suggest_statement",
]


def build_brief(
    statements: list[Statement],
    visit: VisitContext,
    client: ModelClient | None = None,
) -> BriefResult:
    """Stage 1 scope -> Stage 2 select -> Stage 3 validate, else fallback.

    ``statements`` must already be consent-filtered by the caller (Person A's
    guarantee). Every returned ``statement_id`` is in ``statements`` (Person
    C's guarantee, enforced by ``validate_lines``).
    """
    candidates = filter_scope(statements, visit)

    if client is None:
        client = get_default_client()

    lines, model_name = select_lines(candidates, visit, client)
    if lines is not None:
        validated = validate_lines(lines, candidates)
        if validated:
            return BriefResult(lines=validated, fallback_used=False, model=model_name)

    return BriefResult(lines=render_fallback(candidates), fallback_used=True, model=None)

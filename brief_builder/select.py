"""Stage 2 -- selection and phrasing by a model.

No provider is wired in yet. ``ModelClient`` is the seam: a provider adapter
implements ``complete(system, user) -> str`` and reports a ``name``. Until one
exists, ``NullModelClient`` is used and Stage 3 falls back to the
deterministic render. The rest of the pipeline does not care which.
"""

from __future__ import annotations

import json
from typing import Protocol

from .contract import BriefLine, Statement, VisitContext
from .prompts import SYSTEM_PROMPT, build_prompt


class ModelClient(Protocol):
    name: str

    def complete(self, system: str, user: str) -> str:
        """Return the raw model text for a system + user prompt. May raise."""
        ...


class NullModelClient:
    """Stand-in used when no provider is configured. Always signals 'no model'."""

    name = "none"

    def complete(self, system: str, user: str) -> str:  # pragma: no cover
        raise RuntimeError("no model provider configured")


def get_default_client() -> ModelClient | None:
    """Return the configured provider, or None when the model is disabled.

    Provider selection (env var, SDK import) is to be added later. Returning
    None keeps the fallback path as the live path.
    """
    return None


def parse_lines(raw: str) -> list[BriefLine] | None:
    """Strictly parse the model's JSON. Return None if unusable."""
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("lines"), list):
        return None
    lines: list[BriefLine] = []
    for item in data["lines"]:
        if not isinstance(item, dict):
            continue
        sid = item.get("statement_id")
        text = item.get("text")
        if not isinstance(sid, int) or isinstance(sid, bool):
            continue
        if not isinstance(text, str) or not text.strip():
            continue
        lines.append(
            BriefLine(statement_id=sid, text=text.strip(), critical=bool(item.get("critical", False)))
        )
    return lines


def select_lines(
    candidates: list[Statement],
    visit: VisitContext,
    client: ModelClient | None,
) -> tuple[list[BriefLine] | None, str | None]:
    """Ask the model to select lines. Returns (lines, model_name).

    ``(None, None)`` means "no usable model output" and the caller must fall
    back. This function never raises because of the model.
    """
    if client is None or not candidates:
        return None, None
    try:
        raw = client.complete(SYSTEM_PROMPT, build_prompt(candidates, visit))
    except Exception:
        return None, None
    lines = parse_lines(raw)
    if lines is None:
        return None, None
    return lines, client.name

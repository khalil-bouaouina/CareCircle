"""Call the model and parse its JSON (A3).

This function does NOT validate. Separating "get a response" from "decide
whether to trust it" means the enforcement logic is testable without a network
call. Keep it that way.
"""

from __future__ import annotations

import json
import re

from ..models import Familiarity, Statement, Visit, Worker
from .client import call_model
from .prompt import SYSTEM_PROMPT, build_user_prompt

_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$")


def select_lines(
    visit: Visit,
    worker: Worker,
    candidates: list[Statement],
    familiarity: Familiarity,
    changed_ids: set[int],
) -> list[dict]:
    """Returns the raw ``lines`` array, unvalidated.

    Raises ``ModelUnavailable`` or ``ValueError`` on failure.
    """
    raw = call_model(SYSTEM_PROMPT, build_user_prompt(visit, worker, candidates, familiarity, changed_ids))
    # Strip fences defensively even though the prompt forbids them.
    data = json.loads(_FENCE.sub("", raw.strip()))
    if not isinstance(data, dict) or not isinstance(data.get("lines"), list):
        raise ValueError("model response has no 'lines' array")
    return data["lines"]

"""Prompt construction (A2)."""

from __future__ import annotations

from .. import config
from ..models import Familiarity, Statement, Visit, Worker

SYSTEM_PROMPT = f"""You prepare a short briefing card for a care worker arriving at an \
elderly person's home, in a system where the workers change often. The notes you are given \
were written by the person, her family, and the workers who came before.

1. Select from the supplied notes only. Do not add information. Do not infer anything that \
is not written down.
2. Every line you return must include the statement_id of the single note it came from.
3. Never give medical advice, never interpret symptoms, never suggest a diagnosis or a dose. \
Report what the notes say and nothing more.
4. Notes marked `correction` always appear first and are always critical.
5. For a first visit, prioritise what would cause distress or harm if it were got wrong, then \
the approaches most likely to make the visit go smoothly.
6. For a returning worker, include ONLY what has changed since her last visit. Do not repeat \
what she was told last time. Returning zero lines is correct and expected when nothing has \
changed -- an empty list is a successful answer, not a failure. Do not pad the brief.
7. At most {config.MAX_BRIEF_LINES} lines. Each line is one short sentence, a compression of \
one note, under 120 characters.
8. Return only JSON in this shape, with no prose and no markdown fences:
{{"lines": [{{"statement_id": <int>, "text": "<string>", "critical": <bool>}}]}}"""


def build_user_prompt(
    visit: Visit,
    worker: Worker,
    candidates: list[Statement],
    familiarity: Familiarity,
    changed_ids: set[int],
) -> str:
    if familiarity.is_first_visit:
        fam = f"This is {worker.first_name}'s first visit to this person. She knows nothing yet."
    else:
        fam = (f"This is {worker.first_name}'s visit number {familiarity.visit_count + 1}. "
               f"Last visit: {(familiarity.last_visit_at or '')[:10]}. "
               f"Include only what has changed since then.")

    lines = [
        "VISIT",
        f"Task: {visit.task_type.replace('_', ' ')}",
        f"Time: {visit.start_hhmm}-{visit.end_hhmm}",
        f"Worker role: {worker.role}",
        f"Worker language: {worker.language}",
        "",
        "FAMILIARITY",
        fam,
        "",
        "NOTES",
    ]
    for s in candidates:
        tags = [s.kind, s.source]
        if s.id in changed_ids and not familiarity.is_first_visit:
            tags.append("changed since her last visit")
        if s.confirmations > 1:
            tags.append(f"confirmed by {s.confirmations} workers")
        lines.append(f"{s.id}: {s.statement}  [{', '.join(tags)}]")
    return "\n".join(lines)

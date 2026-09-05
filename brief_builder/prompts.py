"""Prompt construction for Stage 2.

The prompt carries three constraints (architecture.md section 5):
  1. every line carries an id from the supplied set;
  2. the text is a rephrasing introducing no new fact;
  3. six lines maximum, criticals first.
"""

from __future__ import annotations

import json

from .contract import MAX_BRIEF_LINES, Statement, VisitContext

SYSTEM_PROMPT = (
    "You prepare a short care brief for a home-care worker about to visit an "
    "elderly person. You are given a numbered list of preference statements "
    "written by the person or her family, and the visit context. Your job is "
    "to SELECT and COMPRESS, never to invent.\n\n"
    "Rules:\n"
    f"- Return at most {MAX_BRIEF_LINES} lines. Put critical lines (safety, "
    "consent, hard requirements) first.\n"
    "- Every line MUST carry the statement_id of exactly one statement from the "
    "list. Lines without a valid id are discarded.\n"
    "- The text of a line must be a shorter rephrasing of that one statement. "
    "Do not add facts, do not merge statements, do not speculate.\n"
    "- Prefer statements relevant to this task, this time of day and this "
    "worker's role. Omit the rest.\n"
    "- Write in the worker's language.\n"
    '- Respond with JSON only: {"lines": [{"statement_id": <int>, '
    '"text": <string>, "critical": <bool>}]}'
)


def build_prompt(candidates: list[Statement], visit: VisitContext) -> str:
    payload = {
        "visit": {
            "task_type": visit.task_type,
            "scheduled_start": visit.scheduled_start,
            "scheduled_end": visit.scheduled_end,
            "worker_role": visit.worker_role,
            "worker_language": visit.worker_language,
        },
        "statements": [
            {
                "statement_id": s.id,
                "category": s.category,
                "statement": s.statement,
            }
            for s in candidates
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)

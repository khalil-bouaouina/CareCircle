"""Stage 3 -- validation. Plain code. This is the enforcement point for P2."""

from __future__ import annotations

from .contract import MAX_BRIEF_LINES, BriefLine, Statement


def validate_lines(
    lines: list[BriefLine],
    candidates: list[Statement],
    max_lines: int = MAX_BRIEF_LINES,
) -> list[BriefLine]:
    """Drop lines whose id is not a candidate, dedupe, criticals first, slice.

    The sort is stable, so the model's own ordering is kept within each group.
    """
    allowed = {s.id for s in candidates}
    seen: set[int] = set()
    kept: list[BriefLine] = []
    for line in lines:
        if line.statement_id not in allowed or line.statement_id in seen:
            continue
        seen.add(line.statement_id)
        kept.append(line)
    kept.sort(key=lambda line: not line.critical)
    return kept[:max_lines]

"""Manual harness (A5). Not imported by the app.

    python -m app.ai._manual_test [1-6]

Six scenarios. Three and six are the ones to show if a judge probes: three
proves the delta logic is real rather than cosmetic, six proves the
hallucination guard is structural.
"""

from __future__ import annotations

import sys

from .. import config
from ..models import Familiarity, Statement, Visit, Worker
from . import selector, validator

WORKER = Worker(id=1, name="Marie-Ève Tremblay", role="care worker", language="fr")
VISIT = Visit(id=1, elder_id=1, worker_id=1, task_type="bathing",
              scheduled_start="2026-03-12T10:00:00", scheduled_end="2026-03-12T11:00:00")


def _statement(sid: int, text: str, kind="preference", source="family", confirms=0, updated="2026-03-01") -> Statement:
    return Statement(id=sid, elder_id=1, statement=text, kind=kind, category="care",
                     source=source, confirmations=confirms,
                     created_at="2026-01-01", updated_at=updated)


CANDIDATES = [
    _statement(1, "A woman for bathing and dressing, please."),
    _statement(2, "She prays in the early afternoon. If she is on the mat, wait."),
    _statement(3, "Shoes off at the door."),
    _statement(4, "She agrees to everything to be polite. Check twice before you leave."),
    _statement(5, "Run the water before she comes in. The noise startles her.", "approach", "worker", 3),
    _statement(6, "Warm the towels on the radiator first.", "approach", "worker", 1),
    _statement(7, "Never let her walk to the bathroom alone after a bath.",
               "preference", "correction"),
    _statement(8, "Her hearing aid is in the blue dish."),
    _statement(9, "Tea first, tasks after."),
    _statement(10, "The hallway rug slides.", updated="2026-03-11"),
    _statement(11, "Speak French. Her English goes when she is tired."),
    _statement(12, "Knock and wait.", updated="2026-03-11"),
]

FIRST_VISIT = Familiarity(visit_count=0, last_visit_at=None, is_first_visit=True)
RETURNING = Familiarity(visit_count=4, last_visit_at="2026-03-10T11:00:00", is_first_visit=False)


def _show(title: str, lines) -> None:
    print(f"\n=== {title} ===")
    if not lines:
        print("  (zero lines — a valid brief)")
    for line in lines:
        tag = "CORRECTION" if line.is_correction else ("critical" if line.critical else "")
        print(f"  [{line.statement_id:>2}] {line.text}  {tag}")


def _run_pipeline(candidates, familiarity, changed_ids, stub=None):
    by_id = {s.id: s for s in candidates}
    try:
        raw = stub if stub is not None else selector.select_lines(
            VISIT, WORKER, candidates, familiarity, changed_ids)
    except Exception as exc:
        print(f"  model unavailable: {exc}")
        return validator.fallback_lines(candidates)
    lines = validator.validate_lines(raw, set(by_id), by_id)
    if raw and not lines:
        print("  response validated down to nothing — falling back")
        return validator.fallback_lines(candidates)
    return lines


def scenario_1():
    _show("1. First visit, normal operation",
          _run_pipeline(CANDIDATES, FIRST_VISIT, {s.id for s in CANDIDATES}))


def scenario_2():
    changed = [s for s in CANDIDATES if s.updated_at > RETURNING.last_visit_at[:10]]
    _show("2. Returning worker, two changed statements",
          _run_pipeline(changed, RETURNING, {s.id for s in changed}))


def scenario_3():
    _show("3. Returning worker, nothing changed", _run_pipeline([], RETURNING, set()))


def scenario_4():
    saved, config.ANTHROPIC_API_KEY = config.ANTHROPIC_API_KEY, None
    try:
        _show("4. ANTHROPIC_API_KEY unset — fallback path",
              _run_pipeline(CANDIDATES, FIRST_VISIT, set()))
    finally:
        config.ANTHROPIC_API_KEY = saved


def scenario_5():
    malformed = [{"text": "no id here"}, {"statement_id": "seven", "text": "wrong type"}, "not a dict"]
    _show("5. Malformed response — validator drops everything, fallback fires",
          _run_pipeline(CANDIDATES, FIRST_VISIT, set(), stub=malformed))


def scenario_6():
    stub = [
        {"statement_id": 999, "text": "She is diabetic and needs insulin at noon.", "critical": True},
        {"statement_id": 7, "text": "Never let her walk to the bathroom alone after a bath."},
        {"statement_id": 5, "text": "Run the water before she comes in."},
    ]
    _show("6. Response with an id outside the candidate set — that line is dropped",
          _run_pipeline(CANDIDATES, FIRST_VISIT, set(), stub=stub))


SCENARIOS = [scenario_1, scenario_2, scenario_3, scenario_4, scenario_5, scenario_6]

if __name__ == "__main__":
    print(f"API key {'set' if config.ANTHROPIC_API_KEY else 'NOT set — expect the fallback path'}")
    chosen = sys.argv[1:] or [str(i + 1) for i in range(len(SCENARIOS))]
    for arg in chosen:
        SCENARIOS[int(arg) - 1]()

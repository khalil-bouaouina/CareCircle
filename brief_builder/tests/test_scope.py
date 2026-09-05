from brief_builder.contract import Statement, VisitContext
from brief_builder.scope import filter_scope, windows_overlap


def _visit(task="bathing", start="10:00", end="11:00") -> VisitContext:
    return VisitContext(task, start, end, "personal_support_worker", "fr")


def test_fixture_cases_scope(statements, cases):
    for case in cases:
        ids = {s.id for s in filter_scope(statements, case["visit"])}
        assert set(case["expect_included"]) <= ids, case["name"]
        assert not (set(case["expect_excluded"]) & ids), case["name"]


def test_empty_applies_means_all_tasks():
    s = Statement(1, "x", "care")
    assert filter_scope([s], _visit("transport")) == [s]


def test_applies_to_tasks_restricts():
    s = Statement(1, "x", "care", applies_to_tasks=["bathing"])
    assert filter_scope([s], _visit("bathing")) == [s]
    assert filter_scope([s], _visit("meal")) == []


def test_excluded_tasks_wins_over_applies():
    s = Statement(1, "x", "care", applies_to_tasks=["bathing"], excluded_tasks=["bathing"])
    assert filter_scope([s], _visit("bathing")) == []


def test_time_window_overlap():
    s = Statement(1, "x", "observance", time_start="13:00", time_end="17:00")
    assert filter_scope([s], _visit(start="16:00", end="16:45")) == [s]
    assert filter_scope([s], _visit(start="12:00", end="13:00")) == []  # touching, no overlap
    assert filter_scope([s], _visit(start="12:30", end="13:30")) == [s]
    assert filter_scope([s], _visit(start="10:00", end="11:00")) == []


def test_window_wrapping_midnight():
    assert windows_overlap("22:00", "06:00", "23:00", "23:30")
    assert windows_overlap("22:00", "06:00", "05:00", "07:00")
    assert not windows_overlap("22:00", "06:00", "10:00", "11:00")


def test_order_preserved(statements):
    out = filter_scope(statements, _visit())
    ids = [s.id for s in out]
    assert ids == sorted(ids)

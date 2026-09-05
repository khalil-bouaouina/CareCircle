import json

from brief_builder import build_brief, suggest_statement
from brief_builder.contract import Statement, VisitContext
from brief_builder import contract


class FakeModel:
    name = "fake-model"

    def __init__(self, payload):
        self.payload = payload

    def complete(self, system, user):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload if isinstance(self.payload, str) else json.dumps(self.payload)


def test_fixture_cases_via_fallback(statements, cases):
    for case in cases:
        result = build_brief(statements, case["visit"])  # no model configured
        ids = [l.statement_id for l in result.lines]
        assert result.fallback_used is True and result.model is None
        assert set(case["expect_included"]) <= set(ids), case["name"]
        assert not (set(case["expect_excluded"]) & set(ids)), case["name"]
        first = next(s for s in statements if s.id == ids[0])
        assert first.category == case["expect_first_category"]


def test_task_flip_between_cases(statements, cases):
    bathing, nursing = cases
    b_ids = {l.statement_id for l in build_brief(statements, bathing["visit"]).lines}
    n_ids = {l.statement_id for l in build_brief(statements, nursing["visit"]).lines}
    assert 1 in b_ids and 1 not in n_ids  # female-worker line disappears for nursing
    assert 3 in n_ids and 3 not in b_ids  # prayer line appears at 4pm


def test_every_returned_id_is_an_input_id(statements, cases):
    allowed = {s.id for s in statements}
    for case in cases:
        for line in build_brief(statements, case["visit"]).lines:
            assert line.statement_id in allowed


def test_model_path_validated_and_sliced(statements, cases):
    visit = cases[0]["visit"]
    payload = {
        "lines": [
            {"statement_id": 1, "text": "Female worker required", "critical": True},
            {"statement_id": 999, "text": "Invented", "critical": True},
            {"statement_id": 3, "text": "Prayer (out of scope at 10am)", "critical": False},
            {"statement_id": 4, "text": "Shoes off", "critical": False},
        ]
    }
    result = build_brief(statements, visit, client=FakeModel(payload))
    assert result.fallback_used is False and result.model == "fake-model"
    assert [l.statement_id for l in result.lines] == [1, 4]
    assert result.lines[0].text == "Female worker required"


def test_model_failure_falls_back(statements, cases):
    visit = cases[0]["visit"]
    for bad in (RuntimeError("boom"), "garbage", {"lines": []}, {"lines": [{"statement_id": 999, "text": "x"}]}):
        result = build_brief(statements, visit, client=FakeModel(bad))
        assert result.fallback_used is True
        assert result.lines  # still a usable brief


def test_contract_entry_points_delegate(statements, cases):
    result = contract.build_brief(statements, cases[0]["visit"])
    assert result.lines
    assert contract.suggest_statement([], None, []) is None


def test_suggest_statement_rules():
    assert suggest_statement(["good_day"], None, []) is None  # no template
    assert suggest_statement(["refused_bath"], "one-off", []) is None  # seen once
    out = suggest_statement(
        ["refused_bath"], None, [{"observation_codes": ["refused_bath", "good_day"]}]
    )
    assert out and "bath" in out.lower()
    # the most repeated code wins
    out = suggest_statement(
        ["ate_little", "unsteady_walking"],
        None,
        [{"observation_codes": ["unsteady_walking"]}, {"observation_codes": ["unsteady_walking", "ate_little"]}],
    )
    assert out and "unsteady" in out.lower()
    assert suggest_statement([], "a long note", [{"observation_codes": ["refused_bath"]}]) is None

from brief_builder.contract import BriefLine, Statement
from brief_builder.fallback import render_fallback
from brief_builder.select import parse_lines
from brief_builder.validate import validate_lines

CANDS = [Statement(i, f"s{i}", "care") for i in range(1, 11)]


def test_unknown_ids_dropped():
    lines = [BriefLine(1, "a", False), BriefLine(99, "invented", True), BriefLine(2, "b", False)]
    out = validate_lines(lines, CANDS)
    assert [l.statement_id for l in out] == [1, 2]


def test_duplicates_dropped():
    lines = [BriefLine(1, "a", False), BriefLine(1, "a again", True)]
    assert len(validate_lines(lines, CANDS)) == 1


def test_criticals_first_stable():
    lines = [
        BriefLine(1, "a", False),
        BriefLine(2, "b", True),
        BriefLine(3, "c", False),
        BriefLine(4, "d", True),
    ]
    out = validate_lines(lines, CANDS)
    assert [l.statement_id for l in out] == [2, 4, 1, 3]


def test_hard_slice_to_six():
    lines = [BriefLine(i, f"s{i}", False) for i in range(1, 11)]
    assert len(validate_lines(lines, CANDS)) == 6


def test_parse_lines_strict():
    assert parse_lines("not json") is None
    assert parse_lines('{"nope": []}') is None
    assert parse_lines('{"lines": "x"}') is None
    out = parse_lines(
        '{"lines": [{"statement_id": 1, "text": "ok", "critical": true},'
        ' {"statement_id": "1", "text": "bad id"},'
        ' {"statement_id": 2, "text": ""},'
        ' {"statement_id": 3, "text": "no flag"}]}'
    )
    assert out is not None
    assert [(l.statement_id, l.critical) for l in out] == [(1, True), (3, False)]


def test_fallback_category_order_and_criticals():
    cands = [
        Statement(1, "talk", "communication"),
        Statement(2, "pray", "observance"),
        Statement(3, "rug", "safety"),
        Statement(4, "tea", "routine"),
        Statement(5, "bruise", "care"),
    ]
    out = render_fallback(cands)
    assert [l.statement_id for l in out] == [3, 5, 2, 4, 1]
    assert out[0].critical and not out[1].critical
    assert out[0].text == "rug"  # verbatim

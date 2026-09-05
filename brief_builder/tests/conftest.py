import json
from pathlib import Path

import pytest

from brief_builder.contract import Statement, VisitContext

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "cases.json"


@pytest.fixture(scope="session")
def fixture_data() -> dict:
    with FIXTURES.open(encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="session")
def statements(fixture_data) -> list[Statement]:
    return [Statement(**row) for row in fixture_data["statements"]]


@pytest.fixture(scope="session")
def cases(fixture_data) -> list[dict]:
    return [
        {**case, "visit": VisitContext(**case["visit"])}
        for case in fixture_data["cases"]
    ]

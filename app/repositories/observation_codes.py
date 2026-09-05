"""observation_code -- the fixed vocabulary a worker can tap at check-out."""

from __future__ import annotations

from ..db import execute, query, query_one
from ..models import ObservationCode


def create_code(code: str, label_en: str, label_fr: str, category: str, suggested_statement: str | None) -> None:
    execute(
        """INSERT OR REPLACE INTO observation_code (code, label_en, label_fr, category, suggested_statement)
           VALUES (?, ?, ?, ?, ?)""",
        (code, label_en, label_fr, category, suggested_statement),
    )


def list_codes() -> list[ObservationCode]:
    rows = query("SELECT * FROM observation_code ORDER BY category, code")
    return [ObservationCode.from_row(r) for r in rows]


def known_codes() -> set[str]:
    return {r["code"] for r in query("SELECT code FROM observation_code")}


def template_for(code: str) -> str | None:
    row = query_one("SELECT suggested_statement FROM observation_code WHERE code = ?", (code,))
    return row["suggested_statement"] if row else None


def code_for_template(suggested_statement: str) -> ObservationCode | None:
    row = query_one("SELECT * FROM observation_code WHERE suggested_statement = ?", (suggested_statement,))
    return ObservationCode.from_row(row) if row else None

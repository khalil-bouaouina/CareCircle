"""observation_code -- the fixed vocabulary, mirrored into the database from
``config.OBSERVATION_CODES`` at seed time so the schema records it too."""

from __future__ import annotations

from ..db import execute, query


def upsert_code(code: str, label_en: str, label_fr: str, category: str) -> None:
    execute(
        """INSERT OR REPLACE INTO observation_code (code, label_en, label_fr, category)
           VALUES (?, ?, ?, ?)""",
        (code, label_en, label_fr, category),
    )


def known_codes() -> set[str]:
    return {r["code"] for r in query("SELECT code FROM observation_code")}

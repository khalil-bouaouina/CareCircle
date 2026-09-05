"""access_log -- append-only, elder-readable. There is deliberately no update or delete here."""

from __future__ import annotations

from ..db import execute, now_iso, query
from ..models import AccessEntry


def log_access(elder_id: int, actor_label: str, action: str, target_summary: str) -> None:
    execute(
        "INSERT INTO access_log (elder_id, actor_label, action, target_summary, at) VALUES (?, ?, ?, ?, ?)",
        (elder_id, actor_label, action, target_summary, now_iso()),
    )


def list_access(elder_id: int, limit: int = 50) -> list[AccessEntry]:
    rows = query(
        "SELECT * FROM access_log WHERE elder_id = ? ORDER BY at DESC, id DESC LIMIT ?",
        (elder_id, limit),
    )
    return [AccessEntry.from_row(r) for r in rows]

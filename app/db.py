"""SQLite connection and query helpers (B3). No SQL outside ``repositories/``."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from . import config

SCHEMA_PATH = Path(__file__).with_name("schema.sql")

_conn: sqlite3.Connection | None = None


def get_conn() -> sqlite3.Connection:
    """One process-wide connection. ``check_same_thread=False`` because FastAPI
    runs sync handlers in a threadpool."""
    global _conn
    if _conn is None:
        Path(config.DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
    return _conn


def close_conn() -> None:
    global _conn
    if _conn is not None:
        _conn.close()
        _conn = None


def query(sql: str, params: tuple = ()) -> list[dict]:
    cur = get_conn().execute(sql, params)
    return [dict(row) for row in cur.fetchall()]


def query_one(sql: str, params: tuple = ()) -> dict | None:
    row = get_conn().execute(sql, params).fetchone()
    return dict(row) if row is not None else None


def execute(sql: str, params: tuple = ()) -> int:
    """Execute, commit, return ``lastrowid``."""
    conn = get_conn()
    cur = conn.execute(sql, params)
    conn.commit()
    return cur.lastrowid


def init_db() -> None:
    """Create tables if missing. Idempotent."""
    get_conn().executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


def drop_db() -> None:
    """Close and delete the database file. Resetting is deleting a file."""
    close_conn()
    for suffix in ("", "-wal", "-shm", "-journal"):
        p = Path(config.DB_PATH + suffix)
        if p.exists():
            p.unlink()


# --- helpers every repository uses so nothing else sees raw JSON strings ------


def _load_json(row: dict | None, *fields: str) -> dict | None:
    if row is None:
        return None
    for f in fields:
        value = row.get(f)
        row[f] = json.loads(value) if isinstance(value, str) else (value or [])
    return row


def _dump(value: Any) -> str:
    return json.dumps(list(value or []), ensure_ascii=False)


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()

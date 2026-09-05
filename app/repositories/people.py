from __future__ import annotations

from ..db import execute, query, query_one
from ..models import Elder, Person


def get_elder(elder_id: int) -> Elder | None:
    row = query_one("SELECT * FROM elder WHERE id = ?", (elder_id,))
    return Elder.from_row(row) if row else None


def create_elder(elder_id: int | None, display_name: str, primary_language: str, capacity_mode: str) -> int:
    return execute(
        "INSERT INTO elder (id, display_name, primary_language, capacity_mode) VALUES (?, ?, ?, ?)",
        (elder_id, display_name, primary_language, capacity_mode),
    )


def list_people(elder_id: int) -> list[Person]:
    rows = query("SELECT * FROM person WHERE elder_id = ? ORDER BY id", (elder_id,))
    return [Person.from_row(r) for r in rows]


def get_person(person_id: int) -> Person | None:
    row = query_one("SELECT * FROM person WHERE id = ?", (person_id,))
    return Person.from_row(row) if row else None


def get_primary_caregiver(elder_id: int) -> Person | None:
    row = query_one(
        "SELECT * FROM person WHERE elder_id = ? AND role = 'primary_caregiver' ORDER BY id LIMIT 1",
        (elder_id,),
    )
    return Person.from_row(row) if row else None


def find_worker_person(elder_id: int, name: str) -> Person | None:
    row = query_one(
        "SELECT * FROM person WHERE elder_id = ? AND role = 'worker' AND name = ? LIMIT 1",
        (elder_id, name),
    )
    return Person.from_row(row) if row else None


def create_person(person_id: int | None, elder_id: int, name: str, role: str, language: str) -> int:
    return execute(
        "INSERT INTO person (id, elder_id, name, role, language) VALUES (?, ?, ?, ?, ?)",
        (person_id, elder_id, name, role, language),
    )

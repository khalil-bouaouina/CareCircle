from __future__ import annotations

from ..db import execute, now_iso, query, query_one
from ..models import Elder, UserAccount, UserElderLink


def get_user_by_email(email: str) -> UserAccount | None:
    row = query_one("SELECT * FROM user_account WHERE lower(email) = lower(?)", (email.strip(),))
    return UserAccount.from_row(row) if row else None


def get_user_by_id(user_id: int) -> UserAccount | None:
    row = query_one("SELECT * FROM user_account WHERE id = ?", (user_id,))
    return UserAccount.from_row(row) if row else None


def create_user(email: str, password_hash: str, name: str) -> int:
    return execute(
        "INSERT INTO user_account (email, password_hash, name, created_at) VALUES (?, ?, ?, ?)",
        (email.strip().lower(), password_hash, name.strip(), now_iso()),
    )


def link_user_to_elder(user_id: int, elder_id: int, person_id: int | None, role: str) -> None:
    execute(
        "INSERT OR REPLACE INTO user_elder_link (user_id, elder_id, person_id, role) VALUES (?, ?, ?, ?)",
        (user_id, elder_id, person_id, role),
    )


def get_user_elder_link(user_id: int, elder_id: int) -> UserElderLink | None:
    row = query_one(
        "SELECT * FROM user_elder_link WHERE user_id = ? AND elder_id = ?",
        (user_id, elder_id),
    )
    return UserElderLink.from_row(row) if row else None


def list_elders_for_user(user_id: int) -> list[tuple[Elder, UserElderLink]]:
    rows = query(
        """
        SELECT e.*, l.role as link_role, l.person_id as link_person_id
        FROM user_elder_link l
        JOIN elder e ON e.id = l.elder_id
        WHERE l.user_id = ?
        ORDER BY e.id
        """,
        (user_id,),
    )
    results = []
    for r in rows:
        elder = Elder(
            id=r["id"],
            display_name=r["display_name"],
            primary_language=r["primary_language"],
            capacity_mode=r["capacity_mode"],
        )
        link = UserElderLink(
            user_id=user_id,
            elder_id=r["id"],
            person_id=r["link_person_id"],
            role=r["link_role"],
        )
        results.append((elder, link))
    return results


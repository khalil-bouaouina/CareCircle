"""The nine tables from architecture.md section 4.

Notes worth defending (kept from the architecture doc):
- There is no religion column.
- ``capacity_mode`` is three-valued, not boolean.
- Scope lives on the statement, not in the query.
- ``checkout`` and ``access_log`` are append-only; nothing updates or deletes them.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _now() -> datetime:
    return datetime.now().replace(microsecond=0)


class Elder(Base):
    __tablename__ = "elder"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    display_name: Mapped[str] = mapped_column(String(120))
    primary_language: Mapped[str] = mapped_column(String(8), default="fr")
    capacity_mode: Mapped[str] = mapped_column(String(16), default="self")  # self|assisted|mandated


class Person(Base):
    __tablename__ = "person"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    elder_id: Mapped[int] = mapped_column(ForeignKey("elder.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(32))  # primary_caregiver|family|worker
    language: Mapped[str] = mapped_column(String(8), default="fr")


class PreferenceStatement(Base):
    __tablename__ = "preference_statement"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    elder_id: Mapped[int] = mapped_column(ForeignKey("elder.id"), index=True)
    statement: Mapped[str] = mapped_column(Text)  # one plain sentence, written by a human
    category: Mapped[str] = mapped_column(String(32))  # care|communication|routine|observance|safety
    applies_to_tasks: Mapped[list] = mapped_column(JSON, default=list)  # empty = all tasks
    excluded_tasks: Mapped[list] = mapped_column(JSON, default=list)
    time_start: Mapped[str | None] = mapped_column(String(5), nullable=True)  # "13:00"
    time_end: Mapped[str | None] = mapped_column(String(5), nullable=True)
    hidden_from: Mapped[list] = mapped_column(JSON, default=list)  # person ids
    status: Mapped[str] = mapped_column(String(16), default="active")  # active|proposed|rejected|retired
    source_checkout_id: Mapped[int | None] = mapped_column(ForeignKey("checkout.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class Visit(Base):
    __tablename__ = "visit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    elder_id: Mapped[int] = mapped_column(ForeignKey("elder.id"), index=True)
    worker_name: Mapped[str] = mapped_column(String(120))
    worker_role: Mapped[str] = mapped_column(String(64))
    worker_language: Mapped[str] = mapped_column(String(8), default="fr")
    task_type: Mapped[str] = mapped_column(String(32))
    scheduled_start: Mapped[datetime] = mapped_column(DateTime)
    scheduled_end: Mapped[datetime] = mapped_column(DateTime)
    token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True, index=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    state: Mapped[str] = mapped_column(String(16), default="scheduled")  # scheduled|briefed|completed|expired
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    brief: Mapped["Brief | None"] = relationship(back_populates="visit", uselist=False)
    checkout: Mapped["Checkout | None"] = relationship(back_populates="visit", uselist=False)


class Brief(Base):
    __tablename__ = "brief"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("visit.id"), unique=True, index=True)
    selected_statement_ids: Mapped[list] = mapped_column(JSON, default=list)
    rendered_lines_json: Mapped[list] = mapped_column(JSON, default=list)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False)

    visit: Mapped[Visit] = relationship(back_populates="brief")


class Checkout(Base):
    """Append-only."""

    __tablename__ = "checkout"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("visit.id"), unique=True, index=True)
    completion: Mapped[str] = mapped_column(String(8))  # yes|partial|no
    observation_codes: Mapped[list] = mapped_column(JSON, default=list)
    note_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    visit: Mapped[Visit] = relationship(back_populates="checkout")


class ObservationCode(Base):
    """Seed table, ~20 rows."""

    __tablename__ = "observation_code"

    code: Mapped[str] = mapped_column(String(48), primary_key=True)
    label_en: Mapped[str] = mapped_column(String(120))
    label_fr: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(32))
    suggested_statement: Mapped[str | None] = mapped_column(Text, nullable=True)


class ProposedUpdate(Base):
    __tablename__ = "proposed_update"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    elder_id: Mapped[int] = mapped_column(ForeignKey("elder.id"), index=True)
    source_checkout_id: Mapped[int | None] = mapped_column(ForeignKey("checkout.id"), nullable=True)
    suggested_statement: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|approved|rejected
    decided_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class AccessLog(Base):
    """Append-only, elder-readable."""

    __tablename__ = "access_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    elder_id: Mapped[int] = mapped_column(ForeignKey("elder.id"), index=True)
    actor_label: Mapped[str] = mapped_column(String(160))
    action: Mapped[str] = mapped_column(String(48))
    target_summary: Mapped[str] = mapped_column(String(240))
    at: Mapped[datetime] = mapped_column(DateTime, default=_now)

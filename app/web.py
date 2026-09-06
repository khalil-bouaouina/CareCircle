"""Shared Jinja environment. Templates are presentation only; routes prepare
every value they need."""

from __future__ import annotations

from pathlib import Path

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

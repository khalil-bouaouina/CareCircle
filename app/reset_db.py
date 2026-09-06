"""Drop, recreate, reseed -- one command (B4).

    python -m app.reset_db

The team's answer to schema drift. Anyone who edits ``schema.sql`` or
``seed.py`` says so, and everyone runs this. There is no state worth preserving.
"""

from __future__ import annotations

from . import config
from .db import init_db
from .seed import seed

if __name__ == "__main__":
    init_db()
    seed(force=True)
    print(f"Reset and reseeded {config.DB_PATH}")

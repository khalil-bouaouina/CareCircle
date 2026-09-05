"""Eldercare backend.

Makes the repo root importable so ``brief_builder`` resolves when the server is
started from ``backend/`` (``uvicorn app.main:app``) -- the one-line import the
task split depends on.
"""

import sys
from pathlib import Path

_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

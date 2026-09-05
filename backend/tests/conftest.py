import os
import tempfile
from pathlib import Path

# Must be set before ``app`` is imported: settings are read at import time.
_TMP = Path(tempfile.mkdtemp(prefix="eldercare-test-"))
os.environ["ELDERCARE_DATABASE_URL"] = f"sqlite:///{(_TMP / 'test.db').as_posix()}"
os.environ["ELDERCARE_SEED_ON_STARTUP"] = "true"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app import seed  # noqa: E402

ELDER = {"X-Actor": "elder"}
LEILA = {"X-Actor-Person-Id": "1"}  # primary caregiver
KARIM = {"X-Actor-Person-Id": "2"}  # family


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def fresh(client):
    """Reset to the seed dataset before a test."""
    r = client.post("/reset")
    assert r.status_code == 200, r.text
    return client


@pytest.fixture()
def db(fresh):
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

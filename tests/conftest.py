"""Shared fixtures for the whole test suite.

Two things here exist specifically because of lessons learned earlier
in this project, not just convention:

1. DATABASE_PATH is set before anything from `app` is imported.
   app.config reads it once, at import time, and every other module
   imports that resolved value transitively. conftest.py is always
   collected by pytest before any test module, so this is the one
   place ordering can be guaranteed.

2. There are two different "give me a working app" fixtures:
   `settings_row` (bootstraps Settings only) and `client` (the full
   app, including the real background scheduler loop). Tests that call
   scheduler.tick() directly should use `settings_row`, not `client`,
   the real loop running concurrently would race the same schedules
   against a manual tick() call in the same test.
"""

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))  # fallback; `pip install -e .` is the real fix

TEST_DB_PATH = "/tmp/wled_scheduler_test.db"
os.environ["DATABASE_PATH"] = TEST_DB_PATH
os.environ.setdefault("SCHEDULER_POLL_INTERVAL_SECONDS", "30")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal, engine, ensure_default_settings  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402
from tests.mock_wled import server as mock_wled  # noqa: E402


@pytest.fixture(scope="session")
def mock_wled_host() -> str:
    """One fake WLED device, shared for the whole test session."""
    _, port = mock_wled.start()
    return f"127.0.0.1:{port}"


@pytest.fixture
def clean_schema():
    """Fresh tables before a test, regardless of what the previous
    test left behind. A fixture, not autouse, so it can be an explicit
    dependency of `db` and `client` below and the ordering is
    guaranteed rather than left to autouse-fixture luck."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


@pytest.fixture
def db(clean_schema):
    with SessionLocal() as session:
        yield session


@pytest.fixture
def settings_row(db):
    """Bootstraps the Settings singleton without starting the full app
    or its background scheduler loop. Use for tests that drive
    scheduler.tick() directly."""
    return ensure_default_settings(db)


@pytest.fixture
def client(clean_schema):
    """The full app via TestClient, entered as a context manager so
    its lifespan actually runs (TestClient only triggers startup and
    shutdown that way, not on plain instantiation). This both
    bootstraps Settings and starts the real background scheduler loop."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def configured_settings(client):
    """Most schedule tests need a real latitude/longitude/timezone in
    place before a sunrise/sunset trigger can be created."""
    response = client.patch(
        "/api/settings",
        json={"latitude": 35.4676, "longitude": -97.5164, "timezone": "America/Chicago"},
    )
    assert response.status_code == 200
    return response.json()


@pytest.fixture
def device(client, mock_wled_host):
    response = client.post("/api/devices", json={"name": "Porch", "host": mock_wled_host})
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def preset_action(client):
    response = client.post(
        "/api/actions", json={"name": "Movie mode", "type": "preset", "payload": {"ps": 5}}
    )
    assert response.status_code == 201
    return response.json()

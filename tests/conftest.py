"""
Shared test fixtures.

Every test runs against a **temporary** database seeded from the real CSVs in
``data/``. Nothing here touches ``data/gbd.db``, so running the suite can never
disturb a database you are using.

The mechanism: ``app.config`` reads its paths from the environment at import
time, so ``GBD_DB_PATH`` is set *before* anything from ``app`` or ``etl`` is
imported -- which is why those imports live inside the fixture rather than at
the top of the file.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def client(tmp_path_factory: pytest.TempPathFactory) -> Iterator[TestClient]:
    """A TestClient backed by a freshly seeded temporary database."""
    db_path = tmp_path_factory.mktemp("gbd") / "test.db"
    os.environ["GBD_DB_PATH"] = str(db_path)

    from etl.load_seed import load_seed

    load_seed()

    from app.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def any_indicator(client: TestClient) -> str:
    """The ID of an indicator that is definitely present."""
    return client.get("/api/indicators").json()[0]["indicator_id"]

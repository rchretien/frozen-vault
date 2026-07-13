"""Shared pytest fixtures for the test suite."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from frozen_vault_backend.api.app import app
from frozen_vault_backend.orm.database import reset_db


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Provide a TestClient instance with a clean database."""
    reset_db()
    with TestClient(app) as test_client:
        yield test_client
    reset_db()

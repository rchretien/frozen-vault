"""Tests for configuration helpers."""

from pathlib import Path

import pytest
from sqlalchemy.pool import NullPool, StaticPool

from frozen_vault_backend.config import AVAILABLE_DB_TYPES, Config, create_database_engine
from frozen_vault_backend.exceptions import BadDBTypeError, BadEnvironmentError


def test_config_rejects_invalid_environment() -> None:
    """Ensure invalid environments raise the custom error."""
    with pytest.raises(BadEnvironmentError):
        Config(environment="invalid")


def test_config_rejects_invalid_db_type() -> None:
    """Ensure invalid database types raise the custom error."""
    with pytest.raises(BadDBTypeError):
        Config(db_type="oracle")


def test_create_database_engine_in_memory_uses_static_pool() -> None:
    """In-memory configuration should leverage StaticPool."""
    engine = create_database_engine(
        db_type="in_memory", environment="local", db_url="sqlite:///:memory:", db_conn_args={}
    )
    try:
        assert isinstance(engine.pool, StaticPool)
    finally:
        engine.dispose()


def test_create_database_engine_sqlite_uses_null_pool(tmp_path: Path) -> None:
    """File-based SQLite should use NullPool and respect provided URL."""
    db_file = tmp_path / "test.db"
    engine = create_database_engine(
        db_type="sqlite",
        environment="local",
        db_url=f"sqlite+pysqlite:///{db_file}",
        db_conn_args={"check_same_thread": False},
    )
    try:
        assert isinstance(engine.pool, NullPool)
    finally:
        engine.dispose()


def test_create_database_engine_unknown_type_raises() -> None:
    """Unsupported DB types should raise BadDBTypeError."""
    with pytest.raises(BadDBTypeError):
        create_database_engine(
            db_type="unknown", environment="local", db_url="sqlite:///:memory:", db_conn_args={}
        )


def test_available_db_types_constant_is_consistent() -> None:
    """Sanity check that available DB types include expected values."""
    assert {"in_memory", "sqlite", "postgres"}.issubset(AVAILABLE_DB_TYPES)

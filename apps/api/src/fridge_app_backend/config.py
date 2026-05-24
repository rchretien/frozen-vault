"""Module containing API configuration variables."""

import logging
from functools import lru_cache
from os import getenv
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pytz import timezone
from sqlalchemy import Engine, create_engine
from sqlalchemy.pool import NullPool, StaticPool

from fridge_app_backend.exceptions import BadDBTypeError, BadEnvironmentError

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

AVAILABLE_ENVIRONMENTS = {"local", "test", "dev", "prod"}
DEPLOYED_ENVIRONMENTS = {"prod"}
AVAILABLE_DB_TYPES = {"in_memory", "sqlite", "postgres"}
ROOT_DIR = Path(__file__).resolve().parent.parent.parent


class Config(BaseSettings):
    """Configuration class for the API."""

    model_config = SettingsConfigDict(
        env_file=Path(f"{ROOT_DIR}/.env-{getenv('ENVIRONMENT', 'local')}"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API specic variables
    api_name: str = "FrozenVault Backend"
    api_description: str = "CRUD API for managing the FrozenVault inventory."
    api_version: str = "0.1.0"
    api_root_path: str = ""
    brussels_tz_name: str = "Europe/Brussels"
    commit_sha: str | None = None

    # Environment specific variables
    environment: str = "local"
    db_type: str = "in_memory"

    # Postgres configuration (used only if db_type == "postgres")
    db_user: str | None = None
    db_password: str | None = None
    db_name: str | None = None
    db_host: str | None = None
    db_port: str | None = None
    db_sslmode: str | None = None

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, value: str) -> str:
        """Validate the environment."""
        if value not in AVAILABLE_ENVIRONMENTS:
            raise BadEnvironmentError(
                current_environment=value, allowed_environments=AVAILABLE_ENVIRONMENTS
            )
        return value

    @field_validator("db_type")
    @classmethod
    def validate_db_type(cls, value: str) -> str:
        """Validate db type."""
        if value not in AVAILABLE_DB_TYPES:
            raise BadDBTypeError(db_type=value, allowed_types=AVAILABLE_DB_TYPES)
        return value

    @property
    def brussels_tz(self):
        return timezone(self.brussels_tz_name)

    # ---------------------------------------------
    # 🔗 Database connection logic
    # ---------------------------------------------
    @property
    def db_url(self) -> str:
        """Return the correct database URL based on the db_type."""
        if self.db_type == "in_memory":
            return "sqlite:///:memory:"

        if self.db_type == "sqlite":
            db_path = Path("database.db")
            if db_path.exists():
                db_path.unlink()
            return f"sqlite+pysqlite:///{db_path.absolute()}"

        if self.db_type == "postgres":
            if not self.db_password:
                raise ValueError("Database password is required for PostgreSQL connections")
            base = (
                f"postgresql+psycopg2://{self.db_user}:{self.db_password}@"
                f"{self.db_host}:{self.db_port}/{self.db_name}"
            )

            # Optional SSL mode (Supabase requires it)
            if self.db_sslmode:
                return f"{base}?sslmode={self.db_sslmode}"
            return base

        raise BadDBTypeError(db_type=self.db_type, allowed_types=AVAILABLE_DB_TYPES)

    @property
    def db_conn_args(self) -> dict[str, str | bool]:
        """Return the connection arguments for SQLAlchemy."""
        if self.db_type.startswith("sqlite") or self.db_type == "in_memory":
            return {"check_same_thread": False}
        return {}


def create_database_engine(
    db_type: str, environment: str, db_url: str, db_conn_args: dict
) -> Engine:
    """Create and configure a SQLAlchemy engine based on database type and environment.

    This function centralises all engine/pool construction logic, making it the single
    source of truth for database configuration. When adding new database types (e.g., Postgres),
    modifications are localized to this function only.

    Supported Combinations
    ----------------------
    - in_memory + any environment: Uses StaticPool (all connections share same in-memory DB)
    - sqlite + any environment: Uses NullPool (avoids SQLite file locking issues)
    - postgres + prod: Uses connection pooling (pool_size=20, max_overflow=10)
    - postgres + dev/test/local: Uses NullPool (simpler, no pooling overhead)

    Notes
    -----
    - StaticPool: Required for in-memory SQLite to maintain state across connections
    - NullPool: Recommended for SQLite file databases and non-production environments
    - Connection pooling: Only enabled in production for performance optimization
    """
    logger.info(f"Creating engine for db_type={db_type}, environment={environment}")

    # In-memory SQLite: MUST use StaticPool to share state across connections
    if db_type == "in_memory":
        logger.debug("Using StaticPool for in-memory database")
        return create_engine(
            url=db_url, future=True, connect_args=db_conn_args, poolclass=StaticPool
        )

    # File-based SQLite: Use NullPool to avoid locking issues
    if db_type == "sqlite":
        logger.debug("Using NullPool for SQLite file database")
        return create_engine(url=db_url, future=True, connect_args=db_conn_args, poolclass=NullPool)

    # PostgreSQL: Use connection pooling in production, NullPool otherwise
    if db_type == "postgres":
        if environment in DEPLOYED_ENVIRONMENTS:
            logger.info("Using connection pooling for production PostgreSQL")
            return create_engine(
                url=db_url,
                future=True,
                connect_args=db_conn_args,
                pool_size=20,
                max_overflow=10,
                pool_timeout=30,
                pool_recycle=1800,
            )
        logger.debug("Using NullPool for non-production PostgreSQL")
        return create_engine(url=db_url, future=True, connect_args=db_conn_args, poolclass=NullPool)

    # This should never be reached due to validation in Config class
    raise BadDBTypeError(db_type=db_type, allowed_types=AVAILABLE_DB_TYPES)


@lru_cache
def get_settings() -> Config:
    """Return the settings."""
    return Config()


config = get_settings()

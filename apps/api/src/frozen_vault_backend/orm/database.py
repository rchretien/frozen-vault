"""Instantiate the necessary SQLAlchemy singleton objects for communicating with the database."""

import logging
from collections.abc import Generator

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from frozen_vault_backend.config import config, create_database_engine
from frozen_vault_backend.orm.models.db_models import (
    Base,
    ProductLocation,
    ProductType,
    init_product_location_table,
    init_product_type_table,
)

logger = logging.getLogger(__name__)


# Singleton engine object - all engine/pool construction is centralized in create_database_engine()
engine = create_database_engine(
    db_type=config.db_type,
    environment=config.environment,
    db_url=config.db_url,
    db_conn_args=config.db_conn_args,
)

# We name it SessionLocal to distinguish it from the Session we are importing from SQLAlchemy.
SessionLocal = sessionmaker(bind=engine)


def initialise_db() -> None:
    """Recreate the database based on structure defined by models."""
    logger.info(f"Database URL: {engine.url}")
    logger.info("Creating database tables...")
    # Emit DDL to the DB - create DB
    # emit CREATE statements given ORM registry
    Base.metadata.create_all(engine)
    logger.info("Database tables created successfully")

    # Fill all default tables with initial/default data if they are empty
    with SessionLocal.begin() as session:
        product_type_count = session.scalar(select(func.count()).select_from(ProductType)) or 0
        if product_type_count == 0:
            init_product_type_table(session=session)
        product_location_count = (
            session.scalar(select(func.count()).select_from(ProductLocation)) or 0
        )
        if product_location_count == 0:
            init_product_location_table(session=session)


def reset_db() -> None:
    """Recreate the database based on structure defined by models."""
    # Emit DDL to the DB - create DB
    # emit CREATE statements given ORM registry
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    # Fill all default tables with initial/default data if they are empty
    with SessionLocal.begin() as session:
        init_product_location_table(session=session)
        init_product_type_table(session=session)


def get_session() -> Generator[Session]:
    """Get a DB Session.

    Yields
    ------
    DB session object.
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


if __name__ == "__main__":
    reset_db()

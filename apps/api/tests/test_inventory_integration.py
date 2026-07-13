"""Integration tests for the product CRUD layer."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import delete

from frozen_vault_backend.config import config
from frozen_vault_backend.exceptions import InvalidProductTypeError
from frozen_vault_backend.orm.crud.product_crud import product_crud
from frozen_vault_backend.orm.database import SessionLocal, reset_db
from frozen_vault_backend.orm.enums.base_enums import (
    OrderByEnum,
    ProductLocationEnum,
    ProductTypeEnum,
    ProductUnitEnum,
)
from frozen_vault_backend.orm.models.db_models import ProductType
from frozen_vault_backend.orm.schemas.product_schemas import ProductCreate, ProductUpdate


def _future_expiry(days: int = 5) -> datetime:
    """Return a timezone-aware datetime in the future."""
    return datetime.now(tz=config.brussels_tz) + timedelta(days=days)


def test_product_crud_create_persists_lookup_relations() -> None:
    """Creating a product via the CRUD layer should populate relationships correctly."""
    reset_db()
    session = SessionLocal()
    try:
        payload = ProductCreate(
            product_name="Parmigiano",
            description="Aged Italian cheese",
            quantity=1,
            unit=ProductUnitEnum.GRAM,
            expiry_date=_future_expiry(14),
            product_location=ProductLocationEnum.REFRIGERATOR,
            product_type=ProductTypeEnum.DAIRY,
        )

        product = product_crud.create(session=session, obj_in=payload)

        assert product.name == payload.product_name
        assert product.description == payload.description
        assert product.product_type.name == payload.product_type
        assert product.product_location.name == payload.product_location
        assert product.unit == payload.unit
        assert product.image_location == "file_path"
        assert product.expiry_date == payload.expiry_date.replace(tzinfo=None)
    finally:
        session.close()


def test_product_crud_update_missing_lookup_raises_error() -> None:
    """Updating a product with a removed product type must surface InvalidProductTypeError."""
    reset_db()
    session = SessionLocal()
    try:
        payload = ProductCreate(
            product_name="Rump Steak",
            description="Beef steak cut",
            quantity=2,
            unit=ProductUnitEnum.GRAM,
            expiry_date=_future_expiry(10),
            product_location=ProductLocationEnum.REFRIGERATOR,
            product_type=ProductTypeEnum.MEAT,
        )

        product = product_crud.create(session=session, obj_in=payload)

        session.execute(delete(ProductType).where(ProductType.name == ProductTypeEnum.FRUIT))
        session.commit()

        update_payload = ProductUpdate(product_type=ProductTypeEnum.FRUIT)

        with pytest.raises(InvalidProductTypeError):
            product_crud.update(session=session, row_id=product.id, obj_in=update_payload)
    finally:
        session.close()


def test_get_names_starting_with_is_case_insensitive() -> None:
    """The name-prefix helper should return consistent results regardless of letter case."""
    reset_db()
    session = SessionLocal()
    try:
        base_payload = {
            "description": "Test product",
            "quantity": 1,
            "unit": ProductUnitEnum.BOXES,
            "expiry_date": _future_expiry(3),
            "product_location": ProductLocationEnum.REFRIGERATOR,
            "product_type": ProductTypeEnum.FRUIT,
        }

        product_crud.create(
            session=session, obj_in=ProductCreate(product_name="Strawberry Jam", **base_payload)
        )
        product_crud.create(
            session=session, obj_in=ProductCreate(product_name="Stone Fruit Mix", **base_payload)
        )

        results_lower = product_crud.get_names_starting_with("st", session=session)
        results_upper = product_crud.get_names_starting_with("ST", session=session)

        assert set(results_lower) == {"Strawberry Jam", "Stone Fruit Mix"}
        assert results_upper == results_lower
    finally:
        session.close()


def test_get_multi_paginated_orders_and_offsets() -> None:
    """Pagination helper should respect ordering, offset, and limit parameters."""
    reset_db()
    session = SessionLocal()
    try:
        entries = [
            ("Bananas", ProductTypeEnum.FRUIT),
            ("Apples", ProductTypeEnum.FRUIT),
            ("Carrots", ProductTypeEnum.VEGETABLE),
        ]

        for name, product_type in entries:
            product_crud.create(
                session=session,
                obj_in=ProductCreate(
                    product_name=name,
                    description=f"{name} description",
                    quantity=2,
                    unit=ProductUnitEnum.GRAM,
                    expiry_date=_future_expiry(5),
                    product_location=ProductLocationEnum.REFRIGERATOR,
                    product_type=product_type,
                ),
            )

        first_page = product_crud.get_multi_paginated(
            session=session, limit=2, offset=0, ascending=True, order_by=OrderByEnum.NAME
        )

        assert [product.name for product in first_page.data] == ["Apples", "Bananas"]
        assert first_page.total == 3
        assert first_page.offset == 0

        second_page = product_crud.get_multi_paginated(
            session=session, limit=2, offset=2, ascending=True, order_by=OrderByEnum.NAME
        )

        assert [product.name for product in second_page.data] == ["Carrots"]
        assert second_page.total == 3
        assert second_page.offset == 2
    finally:
        session.close()

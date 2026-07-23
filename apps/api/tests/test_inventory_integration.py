"""Integration tests for the product CRUD layer."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import delete
from sqlalchemy.orm import Session

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


def _create_analytics_product(
    *,
    session: Session,
    name: str,
    quantity: int,
    unit: ProductUnitEnum,
    location: ProductLocationEnum,
    product_type: ProductTypeEnum,
    expiry_date: datetime,
) -> None:
    """Create a product for freezer analytics tests."""
    product_crud.create(
        session=session,
        obj_in=ProductCreate(
            product_name=name,
            description=f"{name} description",
            quantity=quantity,
            unit=unit,
            expiry_date=expiry_date,
            product_location=location,
            product_type=product_type,
        ),
    )


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


def test_get_freezer_analytics_aggregates_scopes_units_types_and_expiry_dates() -> None:
    """Freezer analytics should reconcile mixed units and expiry dates by scope."""
    reset_db()
    session = SessionLocal()
    now = datetime.now(tz=config.brussels_tz).replace(microsecond=0)
    try:
        products = [
            (
                "Berries",
                750,
                ProductUnitEnum.GRAM,
                ProductLocationEnum.BIG_FREEZER,
                ProductTypeEnum.FRUIT,
                now + timedelta(days=1),
            ),
            (
                "Steak",
                250,
                ProductUnitEnum.GRAM,
                ProductLocationEnum.BIG_FREEZER,
                ProductTypeEnum.MEAT,
                now + timedelta(days=1),
            ),
            (
                "Peas",
                2,
                ProductUnitEnum.BOXES,
                ProductLocationEnum.BIG_FREEZER,
                ProductTypeEnum.VEGETABLE,
                now + timedelta(days=7),
            ),
            (
                "Stock",
                3,
                ProductUnitEnum.BOTTLES,
                ProductLocationEnum.SMALL_FREEZER,
                ProductTypeEnum.LIQUID,
                now + timedelta(days=30),
            ),
            (
                "Yogurt",
                100,
                ProductUnitEnum.GRAM,
                ProductLocationEnum.SMALL_FREEZER,
                ProductTypeEnum.DAIRY,
                now + timedelta(days=31),
            ),
            (
                "Fridge cake",
                500,
                ProductUnitEnum.GRAM,
                ProductLocationEnum.REFRIGERATOR,
                ProductTypeEnum.DESSERT,
                now + timedelta(days=2),
            ),
        ]
        for name, quantity, unit, location, product_type, expiry_date in products:
            _create_analytics_product(
                session=session,
                name=name,
                quantity=quantity,
                unit=unit,
                location=location,
                product_type=product_type,
                expiry_date=expiry_date,
            )

        analytics = product_crud.get_freezer_analytics(session=session, now=now)

        combined = analytics["all"]
        assert combined["entry_count"] == 6
        assert combined["weight_g"] == 1600
        assert combined["boxes"] == 2
        assert combined["bottles"] == 3
        assert combined["type_count"] == 6
        assert combined["name_count"] == 6

        assert analytics[ProductLocationEnum.BIG_FREEZER.value]["entry_count"] == 3
        assert analytics[ProductLocationEnum.BIG_FREEZER.value]["weight_g"] == 1000
        assert analytics[ProductLocationEnum.SMALL_FREEZER.value]["entry_count"] == 2
        assert analytics[ProductLocationEnum.SMALL_FREEZER.value]["weight_g"] == 100
        assert analytics[ProductLocationEnum.REFRIGERATOR.value]["entry_count"] == 1
        assert analytics[ProductLocationEnum.REFRIGERATOR.value]["weight_g"] == 500

        type_breakdown = {row["type"]: row for row in combined["type_breakdown"]}
        assert type_breakdown[ProductTypeEnum.FRUIT.value]["weight_g"] == 750
        assert type_breakdown[ProductTypeEnum.VEGETABLE.value]["boxes"] == 2
        assert type_breakdown[ProductTypeEnum.LIQUID.value]["bottles"] == 3
        assert type_breakdown[ProductTypeEnum.DESSERT.value]["weight_g"] == 500
        assert type_breakdown[ProductTypeEnum.FRUIT.value]["weight_percentage"] == 100
        assert type_breakdown[ProductTypeEnum.MEAT.value]["weight_percentage"] == 33.3
        assert [item["name"] for item in type_breakdown[ProductTypeEnum.FRUIT.value]["items"]] == [
            "Berries"
        ]

        expiry_distribution = {
            bucket["date"]: bucket["entry_count"] for bucket in combined["expiry_distribution"]
        }
        assert expiry_distribution == {
            (now + timedelta(days=1)).date().isoformat(): 2,
            (now + timedelta(days=2)).date().isoformat(): 1,
            (now + timedelta(days=7)).date().isoformat(): 1,
            (now + timedelta(days=30)).date().isoformat(): 1,
            (now + timedelta(days=31)).date().isoformat(): 1,
        }
        chart_heights = {
            bucket["date"]: bucket["height_percentage"]
            for bucket in combined["expiry_distribution"]
        }
        assert chart_heights[(now + timedelta(days=1)).date().isoformat()] == 100
        assert chart_heights[(now + timedelta(days=7)).date().isoformat()] == 50
    finally:
        session.close()


def test_get_freezer_analytics_returns_zeroed_empty_scopes() -> None:
    """Empty analytics should keep every freezer scope and chart bucket renderable."""
    reset_db()
    session = SessionLocal()
    try:
        analytics = product_crud.get_freezer_analytics(
            session=session, now=datetime.now(tz=config.brussels_tz)
        )

        assert set(analytics) == {
            "all",
            ProductLocationEnum.BIG_FREEZER.value,
            ProductLocationEnum.SMALL_FREEZER.value,
            ProductLocationEnum.REFRIGERATOR.value,
        }
        for summary in analytics.values():
            assert summary["entry_count"] == 0
            assert summary["type_breakdown"] == []
            assert summary["name_breakdown"] == []
            assert summary["expiry_distribution"] == []
    finally:
        session.close()


def test_get_freezer_analytics_strictly_groups_similar_names_within_type() -> None:
    """Names should merge only for one unambiguous 95% match in the same category."""
    reset_db()
    session = SessionLocal()
    expiry_date = _future_expiry(20)
    try:
        products = [
            ("  Chicken   Wings ", 500, ProductTypeEnum.POULTRY),
            ("chicken wings", 250, ProductTypeEnum.POULTRY),
            ("Chicken Wing", 300, ProductTypeEnum.POULTRY),
            ("Chicken Thighs", 400, ProductTypeEnum.POULTRY),
            ("Chicken Wing", 200, ProductTypeEnum.MEAT),
            ("Organic chicken breast 500g", 100, ProductTypeEnum.POULTRY),
            ("Organic chicken brest 500g", 100, ProductTypeEnum.POULTRY),
            ("Organic chicken breast 500", 100, ProductTypeEnum.POULTRY),
        ]
        for name, quantity, product_type in products:
            _create_analytics_product(
                session=session,
                name=name,
                quantity=quantity,
                unit=ProductUnitEnum.GRAM,
                location=ProductLocationEnum.BIG_FREEZER,
                product_type=product_type,
                expiry_date=expiry_date,
            )

        summary = product_crud.get_freezer_analytics(session=session)["all"]

        assert summary["name_count"] == 6
        names = {(row["type"], row["name"]): row for row in summary["name_breakdown"]}
        poultry_wings = names[(ProductTypeEnum.POULTRY.value, "Chicken Wings")]
        assert poultry_wings["entry_count"] == 3
        assert poultry_wings["weight_g"] == 1050
        assert {item["name"] for item in poultry_wings["items"]} == {
            "Chicken Wings",
            "chicken wings",
            "Chicken Wing",
        }
        assert names[(ProductTypeEnum.POULTRY.value, "Chicken Thighs")]["weight_g"] == 400
        assert names[(ProductTypeEnum.MEAT.value, "Chicken Wing")]["weight_g"] == 200
        assert all(
            (ProductTypeEnum.POULTRY.value, name) in names
            for name in (
                "Organic chicken breast 500g",
                "Organic chicken brest 500g",
                "Organic chicken breast 500",
            )
        )
    finally:
        session.close()


def test_get_freezer_analytics_groups_short_prefix_variants() -> None:
    """One-character short-name variants should group around one canonical name."""
    reset_db()
    session = SessionLocal()
    try:
        for name, quantity in (("Pork", 500), ("Por", 250), ("Pork1", 100)):
            _create_analytics_product(
                session=session,
                name=name,
                quantity=quantity,
                unit=ProductUnitEnum.GRAM,
                location=ProductLocationEnum.REFRIGERATOR,
                product_type=ProductTypeEnum.MEAT,
                expiry_date=_future_expiry(20),
            )

        summary = product_crud.get_freezer_analytics(session=session)["all"]

        assert summary["name_count"] == 1
        assert summary["name_breakdown"][0]["name"] == "Pork"
        assert summary["name_breakdown"][0]["entry_count"] == 3
        assert summary["name_breakdown"][0]["weight_g"] == 850
        assert {item["name"] for item in summary["name_breakdown"][0]["items"]} == {
            "Pork",
            "Por",
            "Pork1",
        }
    finally:
        session.close()

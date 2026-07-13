"""Unit tests for CRUDBase behaviour."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy.exc import NoResultFound

from frozen_vault_backend.config import config
from frozen_vault_backend.exceptions import ModelNotHavingAttributeError
from frozen_vault_backend.orm.crud.product_crud import CRUDProduct, product_crud
from frozen_vault_backend.orm.database import SessionLocal, reset_db
from frozen_vault_backend.orm.enums.base_enums import (
    ProductLocationEnum,
    ProductTypeEnum,
    ProductUnitEnum,
)
from frozen_vault_backend.orm.schemas.product_schemas import ProductCreate, ProductUpdate


def _product_payload(name: str) -> ProductCreate:
    """Build a ProductCreate payload with minimal variation."""
    return ProductCreate(
        product_name=name,
        description=f"{name} description",
        quantity=1,
        unit=ProductUnitEnum.GRAM,
        expiry_date=datetime.now(tz=config.brussels_tz) + timedelta(days=5),
        product_location=ProductLocationEnum.REFRIGERATOR,
        product_type=ProductTypeEnum.FRUIT,
    )


def test_create_multi_persists_all_items() -> None:
    """CRUDBase.create_multi should return refreshed objects for each payload."""
    reset_db()
    session = SessionLocal()
    try:
        payloads = [_product_payload(f"Item {idx}") for idx in range(2)]
        products = product_crud.create_multi(session=session, obj_in=payloads)

        assert len(products) == 2
        assert {product.name for product in products} == {"Item 0", "Item 1"}
    finally:
        session.close()


def test_update_nonexistent_row_raises_no_result_found() -> None:
    """Updating a missing record should raise NoResultFound."""
    reset_db()
    session = SessionLocal()
    try:
        with pytest.raises(NoResultFound):
            product_crud.update(
                session=session, row_id=999, obj_in=ProductUpdate(description="irrelevant")
            )
    finally:
        session.close()


def test_remove_deletes_record() -> None:
    """CRUDBase.remove should delete the row from the database."""
    reset_db()
    session = SessionLocal()
    try:
        created = product_crud.create(session=session, obj_in=_product_payload("ToDelete"))
        product_crud.remove(session=session, row_id=created.id)

        assert product_crud.get(session=session, row_id=created.id) is None
    finally:
        session.close()


def test_get_order_by_expression_validates_attributes() -> None:
    """Invalid order_by values should raise ModelNotHavingAttributeError."""
    reset_db()
    fake_order_by = type("OrderByFake", (), {"value": "nonexistent"})

    with pytest.raises(ModelNotHavingAttributeError):
        product_crud._get_order_by_expression(fake_order_by())  # type: ignore[arg-type]


def test_update_skips_unknown_fields() -> None:
    """Ensure unknown keys from encode_update_model are ignored gracefully."""
    reset_db()
    session = SessionLocal()

    class NoisyCrud(CRUDProduct):
        def encode_update_model(self, *args, **kwargs):
            data = super().encode_update_model(*args, **kwargs)
            data["nonexistent"] = "ignored"
            return data

    noisy_crud = NoisyCrud(product_crud.model)

    try:
        product = product_crud.create(session=session, obj_in=_product_payload("Noisy"))
        updated = noisy_crud.update(
            session=session,
            row_id=product.id,
            obj_in=ProductUpdate(description="Updated description"),
        )

        assert updated.description == "Updated description"
        assert getattr(updated, "nonexistent", None) is None
    finally:
        session.close()

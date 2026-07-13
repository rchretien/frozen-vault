"""End-to-end tests for the inventory HTTP API."""

from datetime import datetime, timedelta
from typing import Any

import httpx
from fastapi.testclient import TestClient

from frozen_vault_backend.config import config
from frozen_vault_backend.orm.database import SessionLocal
from frozen_vault_backend.orm.enums.base_enums import (
    ProductLocationEnum,
    ProductTypeEnum,
    ProductUnitEnum,
)
from frozen_vault_backend.orm.models.db_models import Product


def _product_payload(**overrides: Any) -> dict[str, Any]:
    """Build a product payload with defaults suitable for API requests."""
    payload = {
        "product_name": "Cheddar",
        "description": "Matured cheddar cheese",
        "quantity": 2,
        "unit": ProductUnitEnum.GRAM.value,
        "expiry_date": (datetime.now(tz=config.brussels_tz) + timedelta(days=30)).isoformat(),
        "product_location": ProductLocationEnum.REFRIGERATOR.value,
        "product_type": ProductTypeEnum.DAIRY.value,
    }
    payload.update(overrides)
    return payload


def test_inventory_end_to_end_flow(client: TestClient) -> None:
    """Exercise create, update, list, and search endpoints together."""
    cheddar_payload = _product_payload()
    almond_payload = _product_payload(
        product_name="Almond Milk",
        description="Plant-based milk alternative",
        quantity=1,
        unit=ProductUnitEnum.BOTTLES.value,
        product_type=ProductTypeEnum.LIQUID.value,
    )

    cheddar_response = client.post("/inventory/create", json=cheddar_payload)
    almond_response = client.post("/inventory/create", json=almond_payload)

    assert cheddar_response.status_code == httpx.codes.CREATED
    assert almond_response.status_code == httpx.codes.CREATED

    cheddar_id = cheddar_response.json()["product_id"]

    update_response = client.patch(
        "/inventory/update",
        params={"product_id": cheddar_id},
        json={"quantity": 5, "product_location": ProductLocationEnum.BIG_FREEZER.value},
    )

    assert update_response.status_code == httpx.codes.OK
    updated_payload = update_response.json()
    assert updated_payload["quantity"] == 5
    assert updated_payload["product_location"] == ProductLocationEnum.BIG_FREEZER.value

    list_response = client.get(
        "/inventory/list", params={"limit": 10, "ascending": True, "order_by": "name"}
    )
    assert list_response.status_code == httpx.codes.OK
    body = list_response.json()

    assert body["total"] == 2
    assert [product["product_name"] for product in body["products"]] == ["Almond Milk", "Cheddar"]

    names_response = client.get("/inventory/startswith", params={"name": "che"})
    assert names_response.status_code == httpx.codes.OK
    assert names_response.json()["names"] == [{"name": "Cheddar"}]

    with SessionLocal() as session:
        stored_product = session.get(Product, cheddar_id)
        assert stored_product is not None
        assert stored_product.quantity == 5
        assert stored_product.product_location.name == ProductLocationEnum.BIG_FREEZER


def test_update_unknown_product_returns_404(client: TestClient) -> None:
    """Attempting to update a non-existent product should return a 404 response."""
    response = client.patch("/inventory/update", params={"product_id": 999}, json={"quantity": 1})

    assert response.status_code == httpx.codes.NOT_FOUND
    assert response.json()["detail"] == "Product not found in the database."

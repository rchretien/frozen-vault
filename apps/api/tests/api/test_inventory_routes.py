"""API tests for inventory endpoints."""

from datetime import datetime, timedelta
from typing import Any

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import delete

from fridge_app_backend.config import config
from fridge_app_backend.orm.database import SessionLocal
from fridge_app_backend.orm.enums.base_enums import (
    ProductLocationEnum,
    ProductTypeEnum,
    ProductUnitEnum,
)
from fridge_app_backend.orm.models.db_models import ProductType


def _product_payload(**overrides: Any) -> dict[str, Any]:
    """Build a product payload with sensible defaults."""
    payload = {
        "product_name": "Peaches",
        "description": "Juicy yellow peaches",
        "quantity": 3,
        "unit": ProductUnitEnum.BOXES.value,
        "expiry_date": (datetime.now(tz=config.brussels_tz) + timedelta(days=3)).isoformat(),
        "product_location": ProductLocationEnum.REFRIGERATOR.value,
        "product_type": ProductTypeEnum.FRUIT.value,
    }
    payload.update(overrides)
    return payload


def test_read_root(client: TestClient) -> None:
    """Test that reading the root returns the inventory HTML app."""
    response = client.get("/")
    assert httpx.codes.is_success(response.status_code)
    assert response.headers["content-type"].startswith("text/html")
    assert "FrozenVault" in response.text
    assert "Keep your fridge feeling fresh." in response.text


def test_create_product_and_list(client: TestClient) -> None:
    """Ensure creating a product persists it and returns it in the list endpoint."""
    payload = _product_payload()
    create_response = client.post("/inventory/create", json=payload)

    assert create_response.status_code == httpx.codes.CREATED
    assert create_response.json()["message"] == "Product created successfully"

    list_response = client.get("/inventory/list")
    assert list_response.status_code == httpx.codes.OK

    body = list_response.json()
    assert body["total"] == 1
    assert body["next_offset"] == 1
    product = body["products"][0]

    assert product["product_name"] == payload["product_name"]
    assert product["description"] == payload["description"]
    assert product["product_type"] == payload["product_type"]
    assert product["product_location"] == payload["product_location"]
    assert product["unit"] == payload["unit"]
    assert product["quantity"] == payload["quantity"]
    assert product["image_location"] == "file_path"


def test_get_names_starting_with_returns_sentence_case(client: TestClient) -> None:
    """The /startswith endpoint should normalise product names to sentence case."""
    payload = _product_payload(product_name="spinach")
    create_response = client.post("/inventory/create", json=payload)
    assert create_response.status_code == httpx.codes.CREATED

    names_response = client.get("/inventory/startswith", params={"name": "sp"})
    assert names_response.status_code == httpx.codes.OK

    body = names_response.json()
    assert body["names"] == [{"name": "Spinach"}]


def test_update_product_rejects_past_expiry(client: TestClient) -> None:
    """Updating a product with an expiry date before creation must fail."""
    payload = _product_payload()
    create_response = client.post("/inventory/create", json=payload)
    assert create_response.status_code == httpx.codes.CREATED
    product_id = create_response.json()["product_id"]

    invalid_expiry = (datetime.now(tz=config.brussels_tz) - timedelta(days=1)).isoformat()
    update_response = client.patch(
        "/inventory/update", params={"product_id": product_id}, json={"expiry_date": invalid_expiry}
    )

    assert update_response.status_code == httpx.codes.BAD_REQUEST
    assert "cannot be earlier than creation date" in update_response.json()["detail"]


def test_create_product_with_missing_type_returns_400(client: TestClient) -> None:
    """Creating a product with a removed lookup value should trigger the custom error handler."""
    with SessionLocal.begin() as session:
        session.execute(delete(ProductType).where(ProductType.name == ProductTypeEnum.FRUIT))

    payload = _product_payload(product_type=ProductTypeEnum.FRUIT.value)
    response = client.post("/inventory/create", json=payload)

    assert response.status_code == httpx.codes.BAD_REQUEST
    detail = response.json()["detail"]
    assert "Invalid product_type" in detail
    assert "ProductTypeEnum.FRUIT" in detail
    assert "Product type not found in database." in detail


def test_create_product_with_past_expiry_returns_400(client: TestClient) -> None:
    """Creating a product with an expiry date before now must fail cleanly."""
    payload = _product_payload(
        expiry_date=(datetime.now(tz=config.brussels_tz) - timedelta(hours=1)).isoformat()
    )

    response = client.post("/inventory/create", json=payload)

    assert response.status_code == httpx.codes.BAD_REQUEST
    assert "cannot be earlier than creation date" in response.json()["detail"]


def test_delete_product_removes_record(client: TestClient) -> None:
    """Deleting a product via the JSON API should remove it from the database."""
    payload = _product_payload(product_name="Delete me")
    create_response = client.post("/inventory/create", json=payload)
    assert create_response.status_code == httpx.codes.CREATED

    product_id = create_response.json()["product_id"]
    delete_response = client.delete("/inventory/delete", params={"product_id": product_id})

    assert delete_response.status_code == httpx.codes.NO_CONTENT

    list_response = client.get("/inventory/list")
    assert list_response.status_code == httpx.codes.OK
    assert list_response.json()["total"] == 0


def test_delete_unknown_product_returns_404(client: TestClient) -> None:
    """Deleting a missing product should return a 404 response."""
    response = client.delete("/inventory/delete", params={"product_id": 999})

    assert response.status_code == httpx.codes.NOT_FOUND
    assert response.json()["detail"] == "Product not found in the database."

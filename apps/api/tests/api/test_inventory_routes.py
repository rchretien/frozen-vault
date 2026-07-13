"""API tests for inventory endpoints."""

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, text

from frozen_vault_backend.config import config
from frozen_vault_backend.orm.database import SessionLocal
from frozen_vault_backend.orm.enums.base_enums import (
    ProductLocationEnum,
    ProductTypeEnum,
    ProductUnitEnum,
)
from frozen_vault_backend.orm.models.db_models import ProductType
from frozen_vault_backend.orm.schemas.product_schemas import calculate_best_quality_until


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


@pytest.mark.parametrize(
    ("product_type", "storage_days"),
    [
        (ProductTypeEnum.POULTRY, 270),
        (ProductTypeEnum.MEAT, 270),
        (ProductTypeEnum.FISH, 180),
        (ProductTypeEnum.SEAFOOD, 120),
        (ProductTypeEnum.VEGETABLE, 60),
        (ProductTypeEnum.LIQUID, 120),
        (ProductTypeEnum.FRUIT, 90),
        (ProductTypeEnum.DESSERT, 120),
        (ProductTypeEnum.DAIRY, 90),
    ],
)
def test_product_exposes_derived_best_quality_date(
    client: TestClient, product_type: ProductTypeEnum, storage_days: int
) -> None:
    """Products should use their category's quality window from creation."""
    payload = _product_payload(
        expiry_date=(datetime.now(tz=config.brussels_tz) + timedelta(days=3)).isoformat(),
        product_location=ProductLocationEnum.BIG_FREEZER.value,
        product_type=product_type.value,
    )
    create_response = client.post("/inventory/create", json=payload)
    assert create_response.status_code == httpx.codes.CREATED

    product = client.get("/inventory/list").json()["products"][0]
    creation_date = datetime.fromisoformat(product["creation_date"])
    best_quality_until = datetime.fromisoformat(product["best_quality_until"])

    assert best_quality_until == creation_date + timedelta(days=storage_days)


def test_refrigerator_product_uses_category_quality_date(client: TestClient) -> None:
    """Refrigerator products should use the same category window as freezer products."""
    payload = _product_payload()
    create_response = client.post("/inventory/create", json=payload)
    assert create_response.status_code == httpx.codes.CREATED

    product = client.get("/inventory/list").json()["products"][0]
    creation_date = datetime.fromisoformat(product["creation_date"])

    assert datetime.fromisoformat(product["best_quality_until"]) == creation_date + timedelta(
        days=90
    )


def test_freezer_duration_overrides_later_vendor_expiry(client: TestClient) -> None:
    """Freezer guidance should remain bounded by the configured quality window."""
    payload = _product_payload(
        expiry_date=(datetime.now(tz=config.brussels_tz) + timedelta(days=365)).isoformat(),
        product_location=ProductLocationEnum.BIG_FREEZER.value,
        product_type=ProductTypeEnum.DAIRY.value,
    )
    create_response = client.post("/inventory/create", json=payload)
    assert create_response.status_code == httpx.codes.CREATED

    product = client.get("/inventory/list").json()["products"][0]
    creation_date = datetime.fromisoformat(product["creation_date"])

    assert datetime.fromisoformat(product["best_quality_until"]) == creation_date + timedelta(
        days=90
    )


def test_expiry_sort_uses_best_quality_date_before_pagination(client: TestClient) -> None:
    """The first expiry page should match the effective date displayed to users."""
    freezer_payload = _product_payload(
        product_name="Frozen yogurt",
        expiry_date=(datetime.now(tz=config.brussels_tz) + timedelta(days=1)).isoformat(),
        product_location=ProductLocationEnum.BIG_FREEZER.value,
        product_type=ProductTypeEnum.DAIRY.value,
    )
    refrigerator_payload = _product_payload(
        product_name="Fresh peaches",
        expiry_date=(datetime.now(tz=config.brussels_tz) + timedelta(days=10)).isoformat(),
        product_type=ProductTypeEnum.VEGETABLE.value,
    )
    assert client.post("/inventory/create", json=freezer_payload).status_code == httpx.codes.CREATED
    assert (
        client.post("/inventory/create", json=refrigerator_payload).status_code
        == httpx.codes.CREATED
    )

    response = client.get(
        "/inventory/list", params={"ascending": True, "limit": 1, "order_by": "expiry_date"}
    )

    assert response.status_code == httpx.codes.OK
    assert [product["product_name"] for product in response.json()["products"]] == ["Fresh peaches"]


def test_freezer_quality_date_normalises_brussels_dst_offset() -> None:
    """Freezer date arithmetic should use the correct Brussels offset after DST changes."""
    creation_date = config.brussels_tz.localize(datetime(2026, 1, 1, 12))

    result = calculate_best_quality_until(
        creation_date=creation_date, product_type=ProductTypeEnum.POULTRY
    )

    assert result.utcoffset() == timedelta(hours=2)


def test_create_product_persists_unit_value(client: TestClient) -> None:
    """Persist unit values using the same strings allowed by the DB constraint."""
    payload = _product_payload(unit=ProductUnitEnum.BOXES.value)

    create_response = client.post("/inventory/create", json=payload)

    assert create_response.status_code == httpx.codes.CREATED
    with SessionLocal() as session:
        raw_unit = session.execute(text("select unit from product")).scalar_one()
    assert raw_unit == ProductUnitEnum.BOXES.value


def test_get_names_starting_with_returns_sentence_case(client: TestClient) -> None:
    """The /startswith endpoint should normalise product names to sentence case."""
    payload = _product_payload(product_name="spinach")
    create_response = client.post("/inventory/create", json=payload)
    assert create_response.status_code == httpx.codes.CREATED

    names_response = client.get("/inventory/startswith", params={"name": "sp"})
    assert names_response.status_code == httpx.codes.OK

    body = names_response.json()
    assert body["names"] == [{"name": "Spinach"}]


def test_update_product_rejects_vendor_expiry_change(client: TestClient) -> None:
    """The vendor expiry date must remain immutable after creation."""
    payload = _product_payload()
    create_response = client.post("/inventory/create", json=payload)
    assert create_response.status_code == httpx.codes.CREATED
    product_id = create_response.json()["product_id"]

    changed_expiry = (datetime.now(tz=config.brussels_tz) + timedelta(days=30)).isoformat()
    update_response = client.patch(
        "/inventory/update", params={"product_id": product_id}, json={"expiry_date": changed_expiry}
    )

    assert update_response.status_code == httpx.codes.BAD_REQUEST
    assert "cannot be changed" in update_response.json()["detail"]


def test_update_product_does_not_rewrite_equivalent_vendor_expiry(client: TestClient) -> None:
    """An equivalent timestamp with another offset must not alter the stored vendor expiry."""
    create_response = client.post("/inventory/create", json=_product_payload())
    assert create_response.status_code == httpx.codes.CREATED
    product_id = create_response.json()["product_id"]
    original_expiry = client.get("/inventory/list").json()["products"][0]["expiry_date"]
    equivalent_expiry = datetime.fromisoformat(original_expiry).astimezone(UTC).isoformat()

    update_response = client.patch(
        "/inventory/update",
        params={"product_id": product_id},
        json={"expiry_date": equivalent_expiry},
    )

    assert update_response.status_code == httpx.codes.OK
    assert client.get("/inventory/list").json()["products"][0]["expiry_date"] == original_expiry


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

"""API tests for utility endpoints."""

import httpx
import pytest
from fastapi.testclient import TestClient


def test_get_deployment_info(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    """Ensure public deployment metadata is exposed without secrets."""
    monkeypatch.setenv("IMAGE_REF", "ghcr.io/rchretien/fridge-app:latest")
    monkeypatch.setenv("IMAGE_DIGEST", "ghcr.io/rchretien/fridge-app@sha256:test")
    monkeypatch.setenv("DEPLOYED_AT", "2026-06-14T12:00:00Z")

    response = client.get("/utils/deployment")
    assert response.status_code == httpx.codes.OK

    body = response.json()
    assert body["image_ref"] == "ghcr.io/rchretien/fridge-app:latest"
    assert body["image_digest"] == "ghcr.io/rchretien/fridge-app@sha256:test"
    assert body["deployed_at"] == "2026-06-14T12:00:00Z"
    assert body["api_version"]
    assert body["environment"]
    assert body["db_type"]
    assert body["docs_url"] == "/docs"
    assert body["deployment_info_url"] == "/utils/deployment"
    assert "db_password" not in body
    assert "db_user" not in body
    assert "db_host" not in body


def test_get_product_type_list(client: TestClient) -> None:
    """Ensure the product type list endpoint returns seeded values."""
    response = client.get("/utils/product_type_list")
    assert response.status_code == httpx.codes.OK

    body = response.json()
    assert len(body["product_type_list"]) >= 1
    assert any("poultry" in item["name"].lower() for item in body["product_type_list"])


def test_get_product_location_list(client: TestClient) -> None:
    """Ensure the product location endpoint returns the expected locations."""
    response = client.get("/utils/product_location_list")
    assert response.status_code == httpx.codes.OK

    body = response.json()
    assert len(body["product_location_list"]) == 3
    assert {item["name"] for item in body["product_location_list"]} == {
        "refrigerator",
        "big freezer",
        "small freezer",
    }

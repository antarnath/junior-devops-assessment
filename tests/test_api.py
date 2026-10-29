"""Tests for the operations API."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_create_operation(client: TestClient, sample_operation: dict) -> None:
    """A valid operation is created with a 201."""
    response = client.post("/api/v1/operations", json=sample_operation)
    assert response.status_code == 201
    assert response.json()["reference"] == "OPS-1001"
    assert response.json()["status"] == "pending"


def test_get_operation_by_id(client: TestClient, sample_operation: dict) -> None:
    """A created operation can be fetched back by ID."""
    created = client.post("/api/v1/operations", json=sample_operation).json()
    response = client.get(f"/api/v1/operations/{created['id']}")
    assert response.status_code == 200
    assert response.json()["title"] == sample_operation["title"]


def test_list_operations(client: TestClient, sample_operation: dict) -> None:
    """Operations are returned in a list."""
    client.post("/api/v1/operations", json=sample_operation)
    response = client.get("/api/v1/operations")
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_duplicate_reference_is_rejected(client: TestClient, sample_operation: dict) -> None:
    """Creating the same reference twice returns 409."""
    client.post("/api/v1/operations", json=sample_operation)
    response = client.post("/api/v1/operations", json=sample_operation)
    assert response.status_code == 409


def test_unknown_operation_returns_404(client: TestClient) -> None:
    """Fetching an ID that does not exist returns 404."""
    response = client.get("/api/v1/operations/999999")
    assert response.status_code == 404


def test_missing_title_is_rejected(client: TestClient) -> None:
    """A payload without a title returns 400."""
    response = client.post("/api/v1/operations", json={"reference": "OPS-2002"})
    assert response.status_code == 400


def test_reference_is_made_uppercase(client: TestClient) -> None:
    """References are stored uppercase so lookups are consistent."""
    response = client.post(
        "/api/v1/operations",
        json={"reference": "ops-2003", "title": "Uppercase check"},
    )
    assert response.status_code == 201
    assert response.json()["reference"] == "OPS-2003"

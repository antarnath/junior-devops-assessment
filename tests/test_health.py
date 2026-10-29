"""Tests for the health and readiness endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_healthz_returns_ok(client: TestClient) -> None:
    """The liveness endpoint reports the service is up."""
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_healthz_includes_service_name(client: TestClient) -> None:
    """The liveness response names the service."""
    response = client.get("/healthz")
    assert response.json()["service"] == "apex-operations-api"


def test_healthz_sets_request_id_header(client: TestClient) -> None:
    """Every response carries a correlation ID for tracing."""
    response = client.get("/healthz")
    assert response.headers.get("X-Request-ID")


def test_readyz_checks_the_database(client: TestClient) -> None:
    """The readiness endpoint reports the database check."""
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["checks"]["database"] == "ok"

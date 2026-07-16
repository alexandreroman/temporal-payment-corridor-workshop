"""Tests for the web UI foundation."""

from __future__ import annotations

from fastapi.testclient import TestClient

from webui.app import app

client = TestClient(app)


def test_index_renders_landing_page() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Payment Corridor" in response.text


def test_index_wires_the_anomaly_list() -> None:
    response = client.get("/")
    assert response.status_code == 200
    body = response.text
    assert "Payment Corridor" in body
    assert "alpinejs" in body  # Alpine CDN present
    assert "/api/payments/v1/anomalies" in body  # same-origin polling
    assert "powered by" in body


def test_healthz_reports_ok() -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

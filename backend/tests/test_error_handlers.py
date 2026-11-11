from fastapi.testclient import TestClient

from backend import main
from services.suppliers.api import app as suppliers_app


def test_validation_errors_keep_field_locations_without_echoing_input():
    response = TestClient(main.app).post(
        "/users",
        json={"email": "not-an-email-sensitive", "password": "pw"},
    )

    assert response.status_code == 422
    payload = response.json()
    assert "email" in str(payload["detail"])
    assert "password" in str(payload["detail"])
    assert "not-an-email-sensitive" not in response.text
    assert '"pw"' not in response.text
    assert "input" not in payload["detail"][0]


def test_unexpected_backend_exception_returns_generic_json(monkeypatch):
    def fail_lookup(email):
        raise RuntimeError("sensitive internal exception text")

    monkeypatch.setattr(main, "get_user_by_email", fail_lookup)
    response = TestClient(main.app, raise_server_exceptions=False).post(
        "/auth/login",
        json={"email": "test@example.com", "password": "password123"},
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "An unexpected server error occurred. Please try again."}
    assert "sensitive internal exception text" not in response.text
    assert "Traceback" not in response.text


def test_supplier_validation_error_does_not_echo_invalid_input():
    response = TestClient(suppliers_app).post(
        "/suppliers",
        json={
            "name": "PackSource",
            "country": "USA",
            "categories": ["packaging_materials"],
            "rate_per_shipment": -987654,
            "currency": "USD",
        },
    )

    assert response.status_code == 422
    assert "rate_per_shipment" in response.text
    assert "987654" not in response.text

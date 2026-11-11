from datetime import datetime, timezone

from fastapi.testclient import TestClient
from tinydb import Query, TinyDB
from tinydb.storages import MemoryStorage

from backend import candidates, main
from backend.auth import get_current_user


def test_auth_me_response_filters_private_user_fields(auth_environment):
    user = auth_environment["create_user"]()
    auth_environment["users"].update({"internal_flag": "must-not-leak"}, Query().id == user["id"])
    main.app.dependency_overrides[get_current_user] = lambda: auth_environment["users"].get(Query().id == user["id"])
    try:
        response = TestClient(main.app).get("/auth/me")
    finally:
        main.app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"id", "email", "is_active", "role", "created_at", "profile"}
    assert "hashed_password" not in response.text
    assert "internal_flag" not in response.text


def test_registration_endpoint_does_not_echo_email_or_credentials(auth_environment):
    response = TestClient(main.app).post(
        "/users",
        json={"email": "private-register@example.com", "password": "register-secret-123"},
    )

    assert response.status_code == 201
    assert "email" not in response.json()
    assert "private-register@example.com" not in response.text
    assert "register-secret-123" not in response.text
    assert "hashed_password" not in response.text


def test_unauthenticated_auth_responses_do_not_echo_email_or_tokens(auth_environment, monkeypatch):
    user = auth_environment["create_user"](email="private-reset@example.com")
    client = TestClient(main.app)

    forgot = client.post("/auth/forgot-password", json={"email": user["email"]})
    monkeypatch.setattr(main, "redeem_reset_token", lambda token, password: None)
    reset = client.post("/auth/reset-password", json={"token": "secret-reset-token", "new_password": "new-secret-123"})

    assert forgot.status_code == 200
    assert reset.status_code == 200
    assert "email" not in forgot.json()
    assert user["email"] not in forgot.text
    assert "token" not in forgot.text.lower()
    assert "secret-reset-token" not in reset.text
    assert "new-secret-123" not in reset.text


def test_candidate_responses_preserve_camel_case_and_filter_unknown_fields(monkeypatch):
    db = TinyDB(storage=MemoryStorage)
    table = db.table("candidates")
    monkeypatch.setattr(candidates, "candidates_table", table)
    main.app.dependency_overrides[get_current_user] = lambda: {"id": "test-user"}
    try:
        client = TestClient(main.app)
        created = client.post(
            "/candidates/",
            json={
                "companyName": "Parcel Co",
                "contactPerson": "Taylor",
                "corporateEmail": "taylor@example.com",
                "phone": "+1 213 555 0188",
                "operatingCountry": "United States",
                "productType": "ecommerce",
                "monthlyVolume": "1000",
                "servicesOfInterest": ["last-mile-delivery"],
                "current3pl": "Other",
                "privacyAccepted": True,
            },
        )
        assert created.status_code == 201
        candidate_id = created.json()["id"]
        table.update({"private_internal": "do-not-return"}, lambda row: row["id"] == candidate_id)

        fetched = client.get(f"/candidates/{candidate_id}")
        deleted = client.delete(f"/candidates/{candidate_id}")
    finally:
        main.app.dependency_overrides.pop(get_current_user, None)
        db.close()

    assert fetched.status_code == 200
    assert fetched.json()["companyName"] == "Parcel Co"
    assert fetched.json()["createdAt"]
    assert "company_name" not in fetched.text
    assert "private_internal" not in fetched.text
    assert deleted.status_code == 204
    assert deleted.content == b""

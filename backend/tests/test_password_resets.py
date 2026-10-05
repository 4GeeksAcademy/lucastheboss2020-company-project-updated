from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from passlib.hash import bcrypt
from tinydb import Query, TinyDB
from tinydb.storages import MemoryStorage
from fastapi import HTTPException

from backend import password_resets
from backend.config import get_settings
from backend import main
from backend.mailer import EmailDeliveryError
from backend.models import ChangePasswordRequest, ForgotPasswordRequest
from backend.password_resets import InvalidPasswordResetToken


@pytest.fixture
def reset_store(monkeypatch):
    db = TinyDB(storage=MemoryStorage)
    users = db.table("users")
    tokens = db.table("password_reset_tokens")
    monkeypatch.setattr(password_resets, "users_table", users)
    monkeypatch.setattr(password_resets, "password_reset_tokens_table", tokens)
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-for-password-reset-tests")
    monkeypatch.setenv("PASSWORD_RESET_TOKEN_EXPIRE_MINUTES", "30")
    get_settings.cache_clear()
    user_id = str(uuid4())
    users.insert({"id": user_id, "hashed_password": bcrypt.hash("old-password-123")})
    yield db, users, tokens, user_id
    get_settings.cache_clear()
    db.close()


def test_reset_token_updates_password_and_cannot_be_reused(reset_store):
    _, users, _, user_id = reset_store
    token, _ = password_resets.create_reset_token(user_id)

    password_resets.redeem_reset_token(token, "new-password-456")

    assert bcrypt.verify("new-password-456", users.get(doc_id=1)["hashed_password"])
    with pytest.raises(InvalidPasswordResetToken):
        password_resets.redeem_reset_token(token, "another-password-789")


def test_expired_reset_token_is_rejected(reset_store, monkeypatch):
    _, _, _, user_id = reset_store
    token, _ = password_resets.create_reset_token(user_id)
    expired_time = datetime.now(timezone.utc) + timedelta(hours=1)
    monkeypatch.setattr(password_resets, "_now", lambda: expired_time)

    with pytest.raises(InvalidPasswordResetToken):
        password_resets.redeem_reset_token(token, "new-password-456")


def test_requesting_new_reset_invalidates_previous_link(reset_store):
    _, _, _, user_id = reset_store
    first_token, _ = password_resets.create_reset_token(user_id)
    second_token, _ = password_resets.create_reset_token(user_id)

    with pytest.raises(InvalidPasswordResetToken):
        password_resets.redeem_reset_token(first_token, "new-password-456")

    password_resets.redeem_reset_token(second_token, "new-password-456")


def test_authenticated_password_change_invalidates_reset_links(reset_store):
    _, users, _, user_id = reset_store
    token, _ = password_resets.create_reset_token(user_id)

    password_resets.invalidate_user_reset_tokens(user_id)

    with pytest.raises(InvalidPasswordResetToken):
        password_resets.redeem_reset_token(token, "new-password-456")
    assert bcrypt.verify("old-password-123", users.get(doc_id=1)["hashed_password"])


def test_invalid_or_tampered_token_is_rejected(reset_store):
    _, _, _, user_id = reset_store
    token, _ = password_resets.create_reset_token(user_id)

    with pytest.raises(InvalidPasswordResetToken):
        password_resets.redeem_reset_token(f"{token}tampered", "new-password-456")


def test_forgot_password_has_same_response_for_known_and_unknown_email(monkeypatch):
    sent_emails = []
    known_user = {"id": "registered-user", "is_active": True}
    monkeypatch.setattr(
        main,
        "get_user_by_email",
        lambda email: known_user if email == "known@example.com" else None,
    )
    monkeypatch.setattr(main, "create_reset_token", lambda user_id: ("signed-reset-token", datetime.now(timezone.utc)))
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: {"frontend_base_url": "https://trackflow.example"},
    )
    monkeypatch.setattr(main, "send_password_reset_email", lambda email, url: sent_emails.append((email, url)))

    unknown_response = main.forgot_password(ForgotPasswordRequest(email="unknown@example.com"))
    known_response = main.forgot_password(ForgotPasswordRequest(email="known@example.com"))

    assert unknown_response == known_response
    assert unknown_response["message"] == "If that address is registered, you'll receive a reset link shortly."
    assert sent_emails == [
        (
            "known@example.com",
            "https://trackflow.example/reset-password?token=signed-reset-token",
        )
    ]


def test_forgot_password_keeps_confirmation_when_email_delivery_fails(monkeypatch):
    monkeypatch.setattr(
        main,
        "get_user_by_email",
        lambda email: {"id": "registered-user", "is_active": True},
    )
    monkeypatch.setattr(main, "create_reset_token", lambda user_id: ("signed-reset-token", datetime.now(timezone.utc)))
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: {"frontend_base_url": "https://trackflow.example"},
    )

    def fail_delivery(email, url):
        raise EmailDeliveryError("provider unavailable")

    monkeypatch.setattr(main, "send_password_reset_email", fail_delivery)

    response = main.forgot_password(ForgotPasswordRequest(email="known@example.com"))

    assert response["message"] == "If that address is registered, you'll receive a reset link shortly."


def test_change_password_rejects_incorrect_current_password(monkeypatch):
    monkeypatch.setattr(main, "update_user", lambda user_id, payload: pytest.fail("must not update password"))
    user = {"id": "user-id", "hashed_password": bcrypt.hash("correct-password-123")}

    with pytest.raises(HTTPException) as error:
        main.change_password(
            ChangePasswordRequest(
                current_password="wrong-password",
                new_password="new-password-456",
            ),
            user,
        )

    assert error.value.status_code == 400


def test_change_password_rehashes_password_and_invalidates_reset_token(reset_store, monkeypatch):
    _, users, _, user_id = reset_store
    reset_token, _ = password_resets.create_reset_token(user_id)

    def update_test_user(target_user_id, payload):
        users.update(
            {"hashed_password": bcrypt.hash(payload.password)},
            Query().id == target_user_id,
        )
        return users.get(Query().id == target_user_id)

    monkeypatch.setattr(main, "update_user", update_test_user)
    user = users.get(Query().id == user_id)
    response = main.change_password(
        ChangePasswordRequest(
            current_password="old-password-123",
            new_password="new-password-456",
        ),
        user,
    )

    assert response["message"] == "Password changed successfully"
    assert bcrypt.verify("new-password-456", users.get(Query().id == user_id)["hashed_password"])
    with pytest.raises(InvalidPasswordResetToken):
        password_resets.redeem_reset_token(reset_token, "another-password-789")


def test_forgot_password_endpoint_returns_200_for_known_and_unknown_emails(monkeypatch):
    sent_emails = []
    known_user = {"id": "registered-user", "is_active": True}
    monkeypatch.setattr(
        main,
        "get_user_by_email",
        lambda email: known_user if email == "known@example.com" else None,
    )
    monkeypatch.setattr(main, "create_reset_token", lambda user_id: ("signed-reset-token", datetime.now(timezone.utc)))
    monkeypatch.setattr(main, "get_settings", lambda: {"frontend_base_url": "https://trackflow.example"})
    monkeypatch.setattr(main, "send_password_reset_email", lambda email, url: sent_emails.append((email, url)))
    client = TestClient(main.app)

    unknown = client.post("/auth/forgot-password", json={"email": "unknown@example.com"})
    known = client.post("/auth/forgot-password", json={"email": "known@example.com"})

    assert unknown.status_code == known.status_code == 200
    assert unknown.json() == known.json()
    assert len(sent_emails) == 1


def test_reset_password_endpoint_returns_400_for_invalid_token(monkeypatch):
    def reject_token(token, new_password):
        raise InvalidPasswordResetToken("invalid")

    monkeypatch.setattr(main, "redeem_reset_token", reject_token)
    response = TestClient(main.app).post(
        "/auth/reset-password",
        json={"token": "invalid-token", "new_password": "new-password-456"},
    )

    assert response.status_code == 400


def test_change_password_endpoint_requires_authentication():
    response = TestClient(main.app).post(
        "/auth/change-password",
        json={
            "current_password": "old-password-123",
            "new_password": "new-password-456",
        },
    )

    assert response.status_code == 401


def test_change_password_endpoint_verifies_and_updates_password(monkeypatch):
    user = {
        "id": "user-id",
        "hashed_password": bcrypt.hash("old-password-123"),
    }
    invalidated = []

    def update_user(user_id, payload):
        user["hashed_password"] = bcrypt.hash(payload.password)
        return user

    monkeypatch.setattr(main, "update_user", update_user)
    monkeypatch.setattr(main, "invalidate_user_reset_tokens", invalidated.append)
    app_client = TestClient(main.app)
    app_client.app.dependency_overrides[main.get_current_user] = lambda: user

    try:
        wrong_password = app_client.post(
            "/auth/change-password",
            json={
                "current_password": "wrong-password",
                "new_password": "new-password-456",
            },
        )
        changed = app_client.post(
            "/auth/change-password",
            json={
                "current_password": "old-password-123",
                "new_password": "new-password-456",
            },
        )
    finally:
        app_client.app.dependency_overrides.pop(main.get_current_user, None)

    assert wrong_password.status_code == 400
    assert changed.status_code == 200
    assert bcrypt.verify("new-password-456", user["hashed_password"])
    assert invalidated == ["user-id"]
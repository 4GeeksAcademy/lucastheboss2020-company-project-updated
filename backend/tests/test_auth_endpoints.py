from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException
from jose import jwt
from passlib.hash import bcrypt
from pydantic import ValidationError
from tinydb import Query

from backend import auth, main, password_resets, services
from backend.config import get_settings
from backend.models import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    ProfileUpdate,
    ResetPasswordRequest,
    UserCreate,
)
from backend.password_resets import InvalidPasswordResetToken


ACCESS_USER_FIELDS = {"id", "email", "is_active", "role", "created_at"}


def test_create_access_token_has_user_claim_and_future_expiry(auth_environment):
    user_id = str(uuid4())
    token = auth.create_access_token(user_id)
    claims = jwt.decode(token, "unit-test-jwt-secret-never-used-outside-tests", algorithms=["HS256"])

    assert claims["user_uuid"] == user_id
    assert claims["exp"] > int(datetime.now(timezone.utc).timestamp())


def test_access_token_creation_requires_a_jwt_secret(auth_environment, monkeypatch):
    monkeypatch.delenv("JWT_SECRET_KEY")
    get_settings.cache_clear()

    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY must be configured"):
        auth.create_access_token("user-id")


def test_current_user_accepts_a_valid_active_user(auth_environment):
    user = auth_environment["create_user"]()
    token = auth.create_access_token(user["id"])

    assert auth.get_current_user(token)["id"] == user["id"]


def test_current_user_rejects_non_string_identity_claim(auth_environment):
    token = jwt.encode(
        {"user_uuid": 123, "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        "unit-test-jwt-secret-never-used-outside-tests",
        algorithm="HS256",
    )

    with pytest.raises(HTTPException) as error:
        auth.get_current_user(token)

    assert error.value.status_code == 401


def test_current_user_rejects_when_jwt_configuration_is_unavailable(auth_environment, monkeypatch):
    monkeypatch.delenv("JWT_SECRET_KEY")
    get_settings.cache_clear()

    with pytest.raises(HTTPException) as error:
        auth.get_current_user("malformed-token")

    assert error.value.status_code == 401


@pytest.mark.parametrize("token_kind", ["malformed", "expired", "bad_signature"])
def test_current_user_rejects_invalid_tokens(auth_environment, token_kind):
    user = auth_environment["create_user"]()
    if token_kind == "malformed":
        token = "not-a-jwt"
    elif token_kind == "expired":
        token = jwt.encode(
            {"user_uuid": user["id"], "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
            "unit-test-jwt-secret-never-used-outside-tests",
            algorithm="HS256",
        )
    else:
        token = jwt.encode(
            {"user_uuid": user["id"], "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
            "different-unit-test-secret",
            algorithm="HS256",
        )

    with pytest.raises(HTTPException) as error:
        auth.get_current_user(token)

    assert error.value.status_code == 401


def test_current_user_rejects_missing_and_inactive_users(auth_environment):
    missing_token = auth.create_access_token("missing-user")
    with pytest.raises(HTTPException) as missing:
        auth.get_current_user(missing_token)
    assert missing.value.status_code == 401

    user = auth_environment["create_user"]()
    auth_environment["users"].update({"is_active": False}, Query().id == user["id"])
    inactive_token = auth.create_access_token(user["id"])
    with pytest.raises(HTTPException) as inactive:
        auth.get_current_user(inactive_token)
    assert inactive.value.status_code == 401


def test_admin_guard_accepts_admin_and_rejects_regular_user(auth_environment):
    assert auth.require_admin({"id": "admin", "role": "admin"})["id"] == "admin"
    with pytest.raises(HTTPException) as error:
        auth.require_admin({"id": "user", "role": "user"})
    assert error.value.status_code == 403


def test_login_returns_token_for_correct_credentials(auth_environment):
    user = auth_environment["create_user"](email="login@example.com", password="correct-password-123")

    result = main.login(LoginRequest(email="login@example.com", password="correct-password-123"))
    claims = jwt.decode(
        result.access_token,
        "unit-test-jwt-secret-never-used-outside-tests",
        algorithms=["HS256"],
    )

    assert claims["user_uuid"] == user["id"]
    assert result.token_type == "bearer"


@pytest.mark.parametrize("email,password", [
    ("unknown@example.com", "correct-password-123"),
    ("login-failure@example.com", "incorrect-password"),
])
def test_login_rejects_unknown_or_wrong_credentials(auth_environment, email, password):
    if email.startswith("login-failure"):
        auth_environment["create_user"](email=email)

    with pytest.raises(HTTPException) as error:
        main.login(LoginRequest(email=email, password=password))

    assert error.value.status_code == 401


def test_login_rejects_inactive_user(auth_environment):
    user = auth_environment["create_user"](email="inactive-login@example.com")
    auth_environment["users"].update({"is_active": False}, Query().id == user["id"])

    with pytest.raises(HTTPException) as error:
        main.login(LoginRequest(email=user["email"], password="correct-password-123"))

    assert error.value.status_code == 403


def test_auth_me_returns_public_user_and_profile_only(auth_environment):
    user = auth_environment["create_user"](name="Test User", phone="+1 213 555 0111", address="Los Angeles")

    result = main.me(user)

    assert set(result) == ACCESS_USER_FIELDS | {"profile"}
    assert result["profile"]["name"] == "Test User"
    assert "hashed_password" not in result


def test_auth_me_handles_missing_profile(auth_environment):
    user = auth_environment["create_user"]()
    auth_environment["profiles"].remove(Query().user_id == user["id"])

    result = main.me(user)

    assert result["profile"] is None


def test_registration_creates_user_profile_and_password_hash(auth_environment):
    payload = UserCreate(
        email="new-user@example.com",
        password="registration-password-123",
        name="New User",
        phone="+1 213 555 0147",
        address="Zaragoza",
    )

    public = main.register_user(payload)
    stored = auth_environment["users"].get(Query().id == public["id"])

    assert public["email"] == "new-user@example.com"
    assert public["role"] == "user"
    assert bcrypt.verify(payload.password, stored["hashed_password"])
    assert payload.password not in stored["hashed_password"]
    assert auth_environment["profiles"].get(Query().user_id == public["id"])["name"] == "New User"


def test_registration_rejects_duplicate_email(auth_environment):
    user = auth_environment["create_user"](email="duplicate@example.com")

    with pytest.raises(HTTPException) as error:
        main.register_user(UserCreate(email=user["email"], password="another-password-123"))

    assert error.value.status_code == 409


@pytest.mark.parametrize("email,password", [("invalid-email", "valid-password-123"), ("valid@example.com", "short")])
def test_registration_model_rejects_invalid_email_or_short_password(email, password):
    with pytest.raises(ValidationError):
        UserCreate(email=email, password=password)


def test_profile_update_changes_only_supplied_fields(auth_environment):
    user = auth_environment["create_user"](name="Existing Name", phone="+1 213 555 0100", address="LA")

    profile = main.update_my_profile(ProfileUpdate(phone="+34 976 123 456"), user)

    assert profile["phone"] == "+34 976 123 456"
    assert profile["name"] == "Existing Name"
    assert profile["address"] == "LA"


def test_profile_update_creates_a_missing_profile(auth_environment):
    user = auth_environment["create_user"]()
    auth_environment["profiles"].remove(Query().user_id == user["id"])

    profile = main.update_my_profile(ProfileUpdate(name="Created Profile"), user)

    assert profile["user_id"] == user["id"]
    assert profile["name"] == "Created Profile"


def test_profile_update_rejects_invalid_field_type():
    with pytest.raises(ValidationError):
        ProfileUpdate(phone=12345)


def test_forgot_password_sends_link_only_for_active_registered_user(auth_environment):
    user = auth_environment["create_user"](email="reset-user@example.com")

    result = main.forgot_password(ForgotPasswordRequest(email=user["email"]))

    assert result["message"] == "If that address is registered, you'll receive a reset link shortly."
    sent_to, reset_link = auth_environment["sent_emails"][0]
    assert sent_to == user["email"]
    assert "/reset-password?token=" in reset_link


def test_forgot_password_unknown_and_inactive_users_get_identical_response(auth_environment):
    inactive = auth_environment["create_user"](email="inactive-reset@example.com")
    auth_environment["users"].update({"is_active": False}, Query().id == inactive["id"])

    unknown_result = main.forgot_password(ForgotPasswordRequest(email="unknown-reset@example.com"))
    inactive_result = main.forgot_password(ForgotPasswordRequest(email=inactive["email"]))

    assert unknown_result == inactive_result
    assert auth_environment["sent_emails"] == []


def test_reset_password_changes_hash_and_token_is_single_use(auth_environment):
    user = auth_environment["create_user"]()
    token, _ = password_resets.create_reset_token(user["id"])

    assert main.reset_password(ResetPasswordRequest(token=token, new_password="new-password-123"))["message"]
    stored = auth_environment["users"].get(Query().id == user["id"])
    assert bcrypt.verify("new-password-123", stored["hashed_password"])
    with pytest.raises(HTTPException) as reused:
        main.reset_password(ResetPasswordRequest(token=token, new_password="other-password-123"))
    assert reused.value.status_code == 400


def test_reset_password_rejects_expired_and_tampered_tokens(auth_environment, monkeypatch):
    user = auth_environment["create_user"]()
    expired_token, _ = password_resets.create_reset_token(user["id"])
    monkeypatch.setattr(password_resets, "_now", lambda: datetime.now(timezone.utc) + timedelta(hours=1))
    with pytest.raises(HTTPException) as expired:
        main.reset_password(ResetPasswordRequest(token=expired_token, new_password="new-password-123"))
    assert expired.value.status_code == 400

    with pytest.raises(HTTPException) as tampered:
        main.reset_password(ResetPasswordRequest(token=f"{expired_token}bad", new_password="new-password-123"))
    assert tampered.value.status_code == 400


def test_reset_password_rejects_short_password():
    with pytest.raises(ValidationError):
        ResetPasswordRequest(token="valid-looking-token", new_password="short")


def test_change_password_updates_hash_and_invalidates_reset_links(auth_environment):
    user = auth_environment["create_user"]()
    reset_token, _ = password_resets.create_reset_token(user["id"])

    result = main.change_password(
        ChangePasswordRequest(current_password="correct-password-123", new_password="replacement-password-123"),
        user,
    )

    stored = auth_environment["users"].get(Query().id == user["id"])
    assert result["message"] == "Password changed successfully"
    assert bcrypt.verify("replacement-password-123", stored["hashed_password"])
    with pytest.raises(InvalidPasswordResetToken):
        password_resets.redeem_reset_token(reset_token, "another-password-123")


def test_change_password_rejects_wrong_current_password_without_mutation(auth_environment):
    user = auth_environment["create_user"]()
    original_hash = user["hashed_password"]

    with pytest.raises(HTTPException) as error:
        main.change_password(
            ChangePasswordRequest(current_password="wrong-password-123", new_password="replacement-password-123"),
            user,
        )

    assert error.value.status_code == 400
    assert auth_environment["users"].get(Query().id == user["id"])["hashed_password"] == original_hash


def test_change_password_rejects_short_replacement():
    with pytest.raises(ValidationError):
        ChangePasswordRequest(current_password="current-password", new_password="short")

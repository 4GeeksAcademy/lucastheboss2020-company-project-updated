from uuid import uuid4

import pytest
from tinydb import TinyDB
from tinydb.storages import MemoryStorage

from backend import main, password_resets, services
from backend.config import get_settings


@pytest.fixture
def auth_environment(monkeypatch):
    db = TinyDB(storage=MemoryStorage)
    users = db.table("users")
    profiles = db.table("profiles")
    reset_tokens = db.table("password_reset_tokens")

    monkeypatch.setattr(services, "users_table", users)
    monkeypatch.setattr(services, "profiles_table", profiles)
    monkeypatch.setattr(password_resets, "users_table", users)
    monkeypatch.setattr(password_resets, "password_reset_tokens_table", reset_tokens)
    monkeypatch.setenv("JWT_SECRET_KEY", "unit-test-jwt-secret-never-used-outside-tests")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    monkeypatch.setenv("PASSWORD_RESET_TOKEN_EXPIRE_MINUTES", "30")
    get_settings.cache_clear()

    sent_emails = []
    monkeypatch.setattr(main, "send_password_reset_email", lambda email, url: sent_emails.append((email, url)))

    def create_test_user(email=None, password="correct-password-123", **profile):
        email = email or f"auth-test-{uuid4()}@example.com"
        from backend.models import UserCreate

        return services.create_user(UserCreate(email=email, password=password, **profile))

    yield {
        "db": db,
        "users": users,
        "profiles": profiles,
        "reset_tokens": reset_tokens,
        "sent_emails": sent_emails,
        "create_user": create_test_user,
    }

    get_settings.cache_clear()
    db.close()

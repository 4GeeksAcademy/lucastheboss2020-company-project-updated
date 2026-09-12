import os
from datetime import datetime, timedelta, timezone
os.environ["JWT_SECRET_KEY"] = "test-secret-that-is-long-enough"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"

from fastapi.testclient import TestClient
from jose import jwt
from backend.main import app
from backend.storage import db
from backend.services import get_user_by_email

client = TestClient(app)


def setup_function():
    db.drop_tables()


def test_register_login_and_protection():
    response = client.get("/users")
    assert response.status_code == 401
    response = client.post("/users", json={"email": "user@example.com", "password": "password123", "name": "User"})
    assert response.status_code == 201
    assert "hashed_password" not in response.json()
    response = client.post("/auth/login", json={"email": "user@example.com", "password": "password123"})
    assert response.status_code == 200
    token = response.json()["access_token"]
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_malformed_token_is_unauthorized():
    assert client.get("/auth/me", headers={"Authorization": "Bearer malformed"}).status_code == 401


def test_password_is_hashed_and_expired_token_is_rejected():
    client.post("/users", json={"email": "hashed@example.com", "password": "password123"})
    stored = get_user_by_email("hashed@example.com")
    assert stored is not None
    assert stored["hashed_password"] != "password123"
    expired = jwt.encode(
        {"user_uuid": stored["id"], "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        "test-secret-that-is-long-enough",
        algorithm="HS256",
    )
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401


def test_profile_and_user_ownership_are_enforced():
    first = client.post("/users", json={"email": "first@example.com", "password": "password123"}).json()
    second = client.post("/users", json={"email": "second@example.com", "password": "password123"}).json()
    token = client.post("/auth/login", json={"email": "first@example.com", "password": "password123"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get(f"/users/{second['id']}", headers=headers).status_code == 403
    assert client.put(f"/profiles/{second['id']}", headers=headers, json={"name": "Nope"}).status_code == 403
    assert client.put(f"/users/{second['id']}", headers=headers, json={"email": "changed@example.com"}).status_code == 403

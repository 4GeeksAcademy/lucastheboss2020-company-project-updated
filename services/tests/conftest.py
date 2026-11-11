import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

os.environ["DATABASE_URL"] = "sqlite://"

from backend.auth import get_current_user
from services.database import engine as configured_engine, get_db
from services.main import app

TEST_USER = {"id": "inventory-test-user-uuid", "email": "inventory-test@example.com", "is_active": True, "role": "user"}


@pytest.fixture
def inventory_client() -> Generator[TestClient, None, None]:
    SQLModel.metadata.drop_all(configured_engine)
    SQLModel.metadata.create_all(configured_engine)

    def override_db():
        with Session(configured_engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        SQLModel.metadata.drop_all(configured_engine)


@pytest.fixture
def sqlite_inventory_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    yield engine
    engine.dispose()

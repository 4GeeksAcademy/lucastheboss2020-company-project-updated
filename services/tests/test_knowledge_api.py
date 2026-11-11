from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite://")

from backend.auth import get_current_user
from services.main import app
import services.routers.knowledge as knowledge_route


TEST_USER = {"id": "rag-test-user", "email": "rag-test@example.com", "is_active": True, "role": "user"}


@pytest.fixture

def client(monkeypatch: pytest.MonkeyPatch):
    calls: list[str] = []

    def fake_query(question: str) -> str:
        calls.append(question)
        return "Grounded answer. [returns-policy | Returns Policy]"

    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    monkeypatch.setattr(knowledge_route, "query", fake_query)
    with TestClient(app) as test_client:
        yield test_client, calls
    app.dependency_overrides.clear()


def test_knowledge_endpoint_returns_exact_answer_contract(client) -> None:
    test_client, calls = client

    response = test_client.post("/knowledge/query", json={"question": "What is the return window?"})

    assert response.status_code == 200
    assert set(response.json()) == {"answer"}
    assert response.json()["answer"] == "Grounded answer. [returns-policy | Returns Policy]"
    assert calls == ["What is the return window?"]


def test_knowledge_endpoint_validates_question() -> None:
    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    with TestClient(app) as test_client:
        response = test_client.post("/knowledge/query", json={"question": "   "})
    app.dependency_overrides.clear()
    assert response.status_code == 422


def test_knowledge_endpoint_rejects_unauthenticated_query() -> None:
    with TestClient(app) as test_client:
        response = test_client.post("/knowledge/query", json={"question": "What is the return window?"})
    assert response.status_code == 401


def test_knowledge_endpoint_returns_actionable_503_without_generation_config(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("RAG_API_BASE_URL", "RAG_API_KEY", "RAG_GENERATION_MODEL"):
        monkeypatch.delenv(name, raising=False)
    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    with TestClient(app) as test_client:
        response = test_client.post("/knowledge/query", json={"question": "What is the return window?"})
    app.dependency_overrides.clear()
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert "RAG_API_BASE_URL" in detail
    assert "RAG_API_KEY" in detail
    assert "RAG_GENERATION_MODEL" in detail

"""Tests for the reporting API endpoints (Part 2 — Business Performance Pipeline).

Tests cover:
- GET  /reporting/weekly-warehouse-client-performance  — shape, validation, auth
- GET  /reporting/pipeline-runs/latest                  — shape, auth
- POST /reporting/pipeline-runs                         — triggers, validation, auth
"""

from __future__ import annotations
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from services.main import app
from backend.auth import get_current_user

TEST_USER = {"id": "reporting-test-user-uuid", "email": "reporting-test@example.com", "is_active": True, "role": "user"}


@pytest.fixture(autouse=True)
def _override_auth_and_mock_db():
    """Override auth dependency and mock DSN to None for all tests.

    This ensures tests never attempt real PostgreSQL connections.
    """
    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    # Patch _get_dsn so all pipeline functions think there's no DB
    patcher = patch("data.pipelines.pipeline._get_dsn", return_value=None)
    patcher.start()
    yield
    patcher.stop()
    app.dependency_overrides.clear()


@pytest.fixture
def client() -> TestClient:
    """Provide a fresh TestClient per test."""
    return TestClient(app)


# ── GET /reporting/weekly-warehouse-client-performance ───────────────────────


class TestGetWeeklyPerformance:
    """Tests for the GET /reporting/weekly-warehouse-client-performance endpoint."""

    def test_returns_200_with_valid_week(self, client: TestClient) -> None:
        """A valid Monday returns 200 with the expected response shape."""
        response = client.get("/reporting/weekly-warehouse-client-performance?week_start=2026-07-13")
        assert response.status_code == 200
        body = response.json()
        assert "week_start" in body
        assert "computed_at" in body
        assert "entries" in body
        assert body["week_start"] == "2026-07-13"
        assert isinstance(body["entries"], list)

    def test_returns_empty_entries_when_no_db(self, client: TestClient) -> None:
        """Without a database, entries is an empty list."""
        response = client.get("/reporting/weekly-warehouse-client-performance?week_start=2026-07-13")
        assert response.status_code == 200
        body = response.json()
        assert body["entries"] == []

    def test_invalid_date_format_returns_400(self, client: TestClient) -> None:
        """A non-date string for week_start returns 400."""
        response = client.get("/reporting/weekly-warehouse-client-performance?week_start=not-a-date")
        assert response.status_code == 400
        assert "Invalid week_start format" in response.text

    def test_non_monday_returns_400(self, client: TestClient) -> None:
        """A date that is not a Monday returns 400."""
        response = client.get("/reporting/weekly-warehouse-client-performance?week_start=2026-07-14")  # Tuesday
        assert response.status_code == 400
        assert "not a Monday" in response.text

    def test_requires_authentication(self, client: TestClient) -> None:
        """Without auth override, the endpoint returns 401."""
        app.dependency_overrides.clear()
        response = client.get("/reporting/weekly-warehouse-client-performance?week_start=2026-07-13")
        assert response.status_code == 401


# ── GET /reporting/pipeline-runs/latest ──────────────────────────────────────


class TestGetLatestPipelineRun:
    """Tests for the GET /reporting/pipeline-runs/latest endpoint."""

    def test_returns_200_with_expected_shape(self, client: TestClient) -> None:
        """Returns 200 with all expected fields including pipeline_run_log metadata."""
        response = client.get("/reporting/pipeline-runs/latest")
        assert response.status_code == 200
        body = response.json()
        assert "pipeline_name" in body
        assert "last_completed_week" in body
        assert "last_run_at" in body
        assert "status" in body
        # New fields from pipeline_run_log
        assert "rows_extracted" in body
        assert "rows_upserted" in body
        assert "started_at" in body
        assert "completed_at" in body
        assert "error_message" in body

    def test_status_is_never_run_when_no_db(self, client: TestClient) -> None:
        """Without a database, status is 'never_run'."""
        response = client.get("/reporting/pipeline-runs/latest")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "never_run"

    def test_pipeline_name_is_correct(self, client: TestClient) -> None:
        """The pipeline_name is always 'weekly_client_performance'."""
        response = client.get("/reporting/pipeline-runs/latest")
        assert response.status_code == 200
        body = response.json()
        assert body["pipeline_name"] == "weekly_client_performance"


# ── POST /reporting/pipeline-runs ────────────────────────────────────────────


class TestTriggerPipelineRun:
    """Tests for the POST /reporting/pipeline-runs endpoint."""

    def test_accepts_empty_json_body(self, client: TestClient) -> None:
        """POST with an empty JSON body returns 202 and triggers a run."""
        response = client.post("/reporting/pipeline-runs", json={})
        assert response.status_code == 202
        body = response.json()
        assert "week_start" in body
        assert "status" in body

    def test_accepts_week_start(self, client: TestClient) -> None:
        """POST with a week_start returns 202 and reports it back."""
        response = client.post("/reporting/pipeline-runs", json={"week_start": "2026-07-13"})
        assert response.status_code == 202
        body = response.json()
        assert body["week_start"] == "2026-07-13"

    def test_returns_row_count(self, client: TestClient) -> None:
        """A successful run returns rows_upserted of 0 (no DB)."""
        response = client.post("/reporting/pipeline-runs", json={})
        assert response.status_code == 202
        assert response.json()["rows_upserted"] == 0

    def test_requires_authentication(self, client: TestClient) -> None:
        """Without auth override, returns 401."""
        app.dependency_overrides.clear()
        response = client.post("/reporting/pipeline-runs", json={})
        assert response.status_code == 401
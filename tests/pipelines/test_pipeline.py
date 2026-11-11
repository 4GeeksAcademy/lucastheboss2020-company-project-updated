"""Unit tests for the TrackFlow business performance pipeline transformation tasks.

Tests cover the pure KPI computation functions in ``data/process/kpi_functions.py``:

- ``compute_inbound_volume``
- ``compute_outbound_throughput``
- ``compute_stockout_frequency``
- ``compute_discrepancy_frequency``
- ``compute_discrepancy_rate``
- ``aggregate_weekly_kpis``

Every test uses **in-memory** DataFrames with no database or network dependencies.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from data.process.kpi_functions import (
    aggregate_weekly_kpis,
    compute_discrepancy_frequency,
    compute_discrepancy_rate,
    compute_inbound_volume,
    compute_outbound_throughput,
    compute_stockout_frequency,
)


# ── fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_events() -> pd.DataFrame:
    """Return a deterministic set of telemetry events for two warehouses.

    Warehouse ``los_angeles`` with client ``fashion-co``:
        - 3 inbound events (qty 100 + 50 + 200 = 350 units)
        - 2 outbound events
        - 1 stockout trigger
        - 1 discrepancy detected

    Warehouse ``zaragoza`` with client ``soundwave-electronics``:
        - 1 inbound event (qty 500)
        - 3 outbound events
        - 0 stockout triggers
        - 0 discrepancies

    Warehouse ``los_angeles`` with client ``glowlab-cosmetics``:
        - 0 inbound events
        - 0 outbound events
        - 2 stockout triggers
        - 0 discrepancies
    """
    return pd.DataFrame([
        # los_angeles / fashion-co
        {"event_type": "inbound_order_created",      "warehouse": "los_angeles", "client_id": "fashion-co",  "week_start": "2026-07-13", "quantity": 100},
        {"event_type": "inbound_order_created",      "warehouse": "los_angeles", "client_id": "fashion-co",  "week_start": "2026-07-13", "quantity": 50},
        {"event_type": "inbound_order_created",      "warehouse": "los_angeles", "client_id": "fashion-co",  "week_start": "2026-07-13", "quantity": 200},
        {"event_type": "outbound_order_created",     "warehouse": "los_angeles", "client_id": "fashion-co",  "week_start": "2026-07-13", "quantity": 0},
        {"event_type": "outbound_order_created",     "warehouse": "los_angeles", "client_id": "fashion-co",  "week_start": "2026-07-13", "quantity": 0},
        {"event_type": "stock_threshold_triggered",  "warehouse": "los_angeles", "client_id": "fashion-co",  "week_start": "2026-07-13", "quantity": 0},
        {"event_type": "inventory_discrepancy_detected", "warehouse": "los_angeles", "client_id": "fashion-co", "week_start": "2026-07-13", "quantity": 0},
        # zaragoza / soundwave-electronics
        {"event_type": "inbound_order_created",      "warehouse": "zaragoza", "client_id": "soundwave-electronics", "week_start": "2026-07-13", "quantity": 500},
        {"event_type": "outbound_order_created",     "warehouse": "zaragoza", "client_id": "soundwave-electronics", "week_start": "2026-07-13", "quantity": 0},
        {"event_type": "outbound_order_created",     "warehouse": "zaragoza", "client_id": "soundwave-electronics", "week_start": "2026-07-13", "quantity": 0},
        {"event_type": "outbound_order_created",     "warehouse": "zaragoza", "client_id": "soundwave-electronics", "week_start": "2026-07-13", "quantity": 0},
        # los_angeles / glowlab-cosmetics (stockouts only)
        {"event_type": "stock_threshold_triggered",  "warehouse": "los_angeles", "client_id": "glowlab-cosmetics", "week_start": "2026-07-13", "quantity": 0},
        {"event_type": "stock_threshold_triggered",  "warehouse": "los_angeles", "client_id": "glowlab-cosmetics", "week_start": "2026-07-13", "quantity": 0},
    ])


@pytest.fixture
def empty_events() -> pd.DataFrame:
    """Return an empty DataFrame with correct columns."""
    return pd.DataFrame(columns=["event_type", "warehouse", "client_id", "week_start", "quantity"])


# ── compute_inbound_volume ───────────────────────────────────────────────────


class TestComputeInboundVolume:
    """Tests for ``compute_inbound_volume``."""

    def test_sums_quantities_for_inbound_events(self, sample_events: pd.DataFrame) -> None:
        """fashion-co in los_angeles should have 350 inbound units."""
        result = compute_inbound_volume(sample_events)
        la_row = result[(result["warehouse"] == "los_angeles") & (result["client_id"] == "fashion-co")]
        assert len(la_row) == 1
        assert la_row.iloc[0]["inbound_units_count"] == 350

    def test_no_inbound_events_returns_empty(self, empty_events: pd.DataFrame) -> None:
        """Empty events should return an empty DataFrame."""
        result = compute_inbound_volume(empty_events)
        assert len(result) == 0

    def test_missing_quantity_column_raises(self) -> None:
        """Missing 'quantity' column should raise ValueError."""
        bad = pd.DataFrame([{"event_type": "inbound_order_created", "warehouse": "la", "client_id": "c", "week_start": "2026-07-13"}])
        with pytest.raises(ValueError, match="quantity"):
            compute_inbound_volume(bad)


# ── compute_outbound_throughput ──────────────────────────────────────────────


class TestComputeOutboundThroughput:
    """Tests for ``compute_outbound_throughput``."""

    def test_counts_outbound_events(self, sample_events: pd.DataFrame) -> None:
        """fashion-co in los_angeles should have 2 outbound orders."""
        result = compute_outbound_throughput(sample_events)
        la_row = result[(result["warehouse"] == "los_angeles") & (result["client_id"] == "fashion-co")]
        assert len(la_row) == 1
        assert la_row.iloc[0]["outbound_orders_count"] == 2

    def test_zaragoza_has_three_outbound(self, sample_events: pd.DataFrame) -> None:
        """soundwave-electronics in zaragoza should have 3 outbound orders."""
        result = compute_outbound_throughput(sample_events)
        zgz_row = result[(result["warehouse"] == "zaragoza") & (result["client_id"] == "soundwave-electronics")]
        assert len(zgz_row) == 1
        assert zgz_row.iloc[0]["outbound_orders_count"] == 3

    def test_no_outbound_events_returns_empty(self, empty_events: pd.DataFrame) -> None:
        """Empty events should return an empty DataFrame."""
        result = compute_outbound_throughput(empty_events)
        assert len(result) == 0


# ── compute_stockout_frequency ───────────────────────────────────────────────


class TestComputeStockoutFrequency:
    """Tests for ``compute_stockout_frequency``."""

    def test_counts_stockout_triggers(self, sample_events: pd.DataFrame) -> None:
        """fashion-co in los_angeles should have 1 stockout event."""
        result = compute_stockout_frequency(sample_events)
        la_row = result[(result["warehouse"] == "los_angeles") & (result["client_id"] == "fashion-co")]
        assert len(la_row) == 1
        assert la_row.iloc[0]["stockout_events_count"] == 1

    def test_glowlab_has_two_stockouts(self, sample_events: pd.DataFrame) -> None:
        """glowlab-cosmetics in los_angeles should have 2 stockout events."""
        result = compute_stockout_frequency(sample_events)
        gl_row = result[(result["warehouse"] == "los_angeles") & (result["client_id"] == "glowlab-cosmetics")]
        assert len(gl_row) == 1
        assert gl_row.iloc[0]["stockout_events_count"] == 2

    def test_zaragoza_has_zero_stockouts(self, sample_events: pd.DataFrame) -> None:
        """soundwave-electronics in zaragoza should not appear (0 stockouts)."""
        result = compute_stockout_frequency(sample_events)
        zgz_rows = result[result["warehouse"] == "zaragoza"]
        assert len(zgz_rows) == 0


# ── compute_discrepancy_frequency ────────────────────────────────────────────


class TestComputeDiscrepancyFrequency:
    """Tests for ``compute_discrepancy_frequency``."""

    def test_counts_discrepancy_events(self, sample_events: pd.DataFrame) -> None:
        """fashion-co in los_angeles should have 1 discrepancy event."""
        result = compute_discrepancy_frequency(sample_events)
        la_row = result[(result["warehouse"] == "los_angeles") & (result["client_id"] == "fashion-co")]
        assert len(la_row) == 1
        assert la_row.iloc[0]["discrepancy_events_count"] == 1


# ── compute_discrepancy_rate ─────────────────────────────────────────────────


class TestComputeDiscrepancyRate:
    """Tests for ``compute_discrepancy_rate``."""

    def test_known_rate_matches_briefing(self, sample_events: pd.DataFrame) -> None:
        """fashion-co: 1 discrepancy / 2 outbound orders = 0.5.

        This is a hand-calculated assertion matching the BRIEFING definition:
        discrepancy_rate = discrepancy_events_count / outbound_orders_count.
        """
        d_events = compute_discrepancy_frequency(sample_events)
        o_orders = compute_outbound_throughput(sample_events)
        result = compute_discrepancy_rate(d_events, o_orders)

        la_row = result[(result["warehouse"] == "los_angeles") & (result["client_id"] == "fashion-co")]
        assert len(la_row) == 1
        # 1 / 2 = 0.5
        assert la_row.iloc[0]["discrepancy_rate"] == 0.5

    def test_zero_outbound_gives_zero_rate(self) -> None:
        """If there are no outbound orders, discrepancy_rate should be 0."""
        events = pd.DataFrame([
            {"event_type": "inventory_discrepancy_detected", "warehouse": "la", "client_id": "c", "week_start": "2026-07-13", "quantity": 0},
        ])
        d_events = compute_discrepancy_frequency(events)
        o_orders = compute_outbound_throughput(events)
        result = compute_discrepancy_rate(d_events, o_orders)

        assert len(result) == 1
        assert result.iloc[0]["discrepancy_rate"] == 0.0
        assert result.iloc[0]["outbound_orders_count"] == 0


# ── aggregate_weekly_kpis (full orchestration) ───────────────────────────────


class TestAggregateWeeklyKpis:
    """Tests for the full ``aggregate_weekly_kpis`` orchestrator."""

    def test_aggregate_shape_and_counts(self, sample_events: pd.DataFrame) -> None:
        """The aggregated result should have 3 rows (one per unique combo)."""
        result = aggregate_weekly_kpis(sample_events)
        assert len(result) == 3  # 3 unique (warehouse, client_id) combos
        expected_cols = {
            "warehouse", "client_id", "week_start",
            "inbound_units_count", "outbound_orders_count",
            "stockout_events_count", "discrepancy_events_count",
            "discrepancy_rate", "computed_at",
        }
        assert expected_cols.issubset(set(result.columns))

    def test_fashion_co_kpis(self, sample_events: pd.DataFrame) -> None:
        """fashion-co in los_angeles: expected KPI values from hand calculation."""
        result = aggregate_weekly_kpis(sample_events)
        row = result[(result["warehouse"] == "los_angeles") & (result["client_id"] == "fashion-co")].iloc[0]
        assert row["inbound_units_count"] == 350
        assert row["outbound_orders_count"] == 2
        assert row["stockout_events_count"] == 1
        assert row["discrepancy_events_count"] == 1
        assert row["discrepancy_rate"] == 0.5

    def test_soundwave_electronics_kpis(self, sample_events: pd.DataFrame) -> None:
        """soundwave-electronics in zaragoza: inbound only, no stockouts/discrepancies."""
        result = aggregate_weekly_kpis(sample_events)
        row = result[(result["warehouse"] == "zaragoza") & (result["client_id"] == "soundwave-electronics")].iloc[0]
        assert row["inbound_units_count"] == 500
        assert row["outbound_orders_count"] == 3
        assert row["stockout_events_count"] == 0
        assert row["discrepancy_events_count"] == 0
        assert row["discrepancy_rate"] == 0.0

    def test_glowlab_cosmetics_kpis(self, sample_events: pd.DataFrame) -> None:
        """glowlab-cosmetics in los_angeles: no in/out, only stockouts."""
        result = aggregate_weekly_kpis(sample_events)
        row = result[(result["warehouse"] == "los_angeles") & (result["client_id"] == "glowlab-cosmetics")].iloc[0]
        assert row["inbound_units_count"] == 0
        assert row["outbound_orders_count"] == 0
        assert row["stockout_events_count"] == 2
        assert row["discrepancy_events_count"] == 0
        assert row["discrepancy_rate"] == 0.0

    def test_empty_events(self, empty_events: pd.DataFrame) -> None:
        """Empty events should return an empty DataFrame (zero rows)."""
        result = aggregate_weekly_kpis(empty_events)
        assert len(result) == 0

    def test_aggregate_handles_nulls_gracefully(self) -> None:
        """Defensive: null event_type should be treated as unknown and ignored."""
        bad = pd.DataFrame([
            {"event_type": None, "warehouse": "la", "client_id": "c", "week_start": "2026-07-13", "quantity": 10},
        ])
        result = aggregate_weekly_kpis(bad)
        # null event_type doesn't match any known KPI filter, so result is empty
        assert len(result) == 0


# ── defensive / malformed input ──────────────────────────────────────────────


class TestDefensiveBehaviour:
    """Tests that verify defensive handling of invalid or malformed input."""

    def test_null_warehouse_is_acceptable(self) -> None:
        """Null warehouse results in 0 KPI rows (groupby drops NaN by default)."""
        bad = pd.DataFrame([
            {"event_type": "inbound_order_created", "warehouse": None, "client_id": "c", "week_start": "2026-07-13", "quantity": 10},
        ])
        result = aggregate_weekly_kpis(bad)
        # groupby silently drops NaN keys, so the row doesn't appear
        assert len(result) == 0

    def test_string_in_quantity_does_not_crash(self) -> None:
        """Non-numeric quantity should be coerced or produce 0."""
        bad = pd.DataFrame([
            {"event_type": "inbound_order_created", "warehouse": "la", "client_id": "c", "week_start": "2026-07-13", "quantity": "abc"},
        ])
        # The function should handle this gracefully (try/except on astype)
        result = aggregate_weekly_kpis(bad)
        assert len(result) == 1
        assert result.iloc[0]["inbound_units_count"] == 0

    def test_unknown_event_type_is_ignored(self, sample_events: pd.DataFrame) -> None:
        """Events with unrecognised event_type should be filtered out."""
        extra = pd.DataFrame([
            {"event_type": "some_unknown_event", "warehouse": "la", "client_id": "c", "week_start": "2026-07-13", "quantity": 999},
        ])
        combined = pd.concat([sample_events, extra], ignore_index=True)
        result = aggregate_weekly_kpis(combined)
        # The unknown event should not affect counts (no new warehouse/client combos)
        assert len(result) == 3
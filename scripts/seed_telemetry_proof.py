#!/usr/bin/env python3
"""Seed + verify telemetry events in Supabase for the Phase 3 storage proof.

This script is the companion to the ``create_telemetry_table.sql`` DDL.  It:

1. **Seeds** a small, deterministic batch of real telemetry events through the
   *same* persistence path the ``POST /telemetry/events`` endpoint uses
   (``services.telemetry_storage.insert_telemetry_events``), so you can prove
   rows land in Supabase with the correct ``event_type`` and allowlist-trimmed
   ``tags`` JSONB.

2. **Verifies** by querying ``telemetry_events`` back and printing a tabular
   summary (event_type, service, tags) suitable for a screenshot, plus explicit
   **trimming evidence**: one seeded event intentionally carries an out-of-plan
   key (e.g. ``password_raw`` / ``tracking_number``) and the report shows that
   key is ABSENT from ``tags`` — proving the storage boundary filters it.

Requirements:
- ``TELEMETRY_DATABASE_URL`` (preferred) or ``DATABASE_URL`` set to the Supabase
  PostgreSQL DSN.  The table must already exist (run ``create_telemetry_table.sql``
  in the Supabase SQL editor first).

Usage::

    # Seed a deterministic batch (default) and print the verification table:
    TELEMETRY_DATABASE_URL=postgresql://... python -m scripts.seed_telemetry_proof

    # Only verify what is already in the table (no inserts):
    TELEMETRY_DATABASE_URL=postgresql://... python -m scripts.seed_telemetry_proof --verify-only

    # Also seed a larger batch (N events, default 6):
    TELEMETRY_DATABASE_URL=postgresql://... python -m scripts.seed_telemetry_proof --count 20

Exit codes: 0 on success, 1 on any failure (connection, missing table, seed error).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from uuid import uuid4

# ── a representative slice of the event-schema catalogue ──────────────────────
# Each entry: (event_type, properties).  ``trim_me``/``password_raw``/
# ``tracking_number`` are deliberately OUT of the allowlist for those events —
# the verification step proves they are stripped before JSONB insert.
SEED_EVENTS: list[tuple[str, dict]] = [
    (
        "inbound_order_created",
        {
            "warehouse": "los_angeles",
            "client_id": "purestep_footwear",
            "product_id": 1,
            "product_category": "fashion",
            "quantity": 50,
            "order_id": "PO-2024-0098",
            "tracking_number": "1Z999AA10123456784",  # NOT allowlisted (§6.1)
        },
    ),
    (
        "outbound_order_created",
        {
            "warehouse": "zaragoza",
            "client_id": "soundwave_electronics",
            "product_id": 3,
            "product_category": "electronics",
            "quantity": 8,
        },
    ),
    (
        "stock_threshold_triggered",
        {
            "warehouse": "los_angeles",
            "client_id": "purestep_footwear",
            "product_id": 1,
            "product_category": "fashion",
            "quantity": 5,
            "threshold_value": 20,
            "country": "US",
        },
    ),
    (
        "inventory_discrepancy_detected",
        {
            "warehouse": "zaragoza",
            "client_id": "glowlab_cosmetics",
            "product_id": 9,
            "product_category": "cosmetics",
            "quantity": 12,
            "physical_stock": 10,
            "variance": -2,
            "audit_reference": "AUD-2024-0712",
        },
    ),
    (
        "auth_login_succeeded",
        {
            "method": "password",
            "role": "warehouse_staff",
            "region": "US",
            "password_raw": "supersecret",  # NOT allowlisted — trim evidence
        },
    ),
    (
        "page_view",
        {
            "route": "/uis/backoffice/dashboard",
            "section": "dashboard",
            "locale": "en",
        },
    ),
]


def _build_envelope(event_type: str, properties: dict, when: datetime) -> dict:
    """Build a full event envelope consistent with event-schemas.json."""
    return {
        "eventId": str(uuid4()),
        "timestamp": when.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "sessionId": str(uuid4()),
        "userId": "anonymous",
        "event_type": event_type,
        "schemaVersion": 1,
        "requestId": str(uuid4()),
        "properties": properties,
    }


def _seed(conn, count: int) -> int:
    """Insert ``count`` events (cycling SEED_EVENTS) via the storage layer.

    Uses the same ``insert_telemetry_events`` the endpoint calls, so the
    trimmed ``tags`` are produced by the exact production code path.
    """
    from services.telemetry_storage import insert_telemetry_events

    now = datetime.now(timezone.utc)
    events: list[dict] = []
    for i in range(count):
        et, props = SEED_EVENTS[i % len(SEED_EVENTS)]
        events.append(_build_envelope(et, dict(props), now - timedelta(minutes=i)))
    # We already hold a connection to check DSN/table; the storage layer opens
    # its own connection, which is fine (bulk insert is one transaction).
    return insert_telemetry_events(events)


def _verify(conn) -> list[dict]:
    """Read back the most recent telemetry rows, newest first."""
    with conn.cursor() as cur:
        cur.execute(
            """\
            SELECT event_id::text, timestamp::text, event_type, service, tags::text, created_at::text
              FROM telemetry_events
             ORDER BY timestamp DESC
             LIMIT 25
            """
        )
        columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def _print_report(rows: list[dict], seeded_total: int) -> None:
    """Render the proof table to stdout (screenshot-friendly)."""
    print("=" * 78)
    print("PHASE 3 STORAGE PROOF — telemetry_events  (Supabase)")
    print("=" * 78)
    if seeded_total:
        print(f"Seeded via insert_telemetry_events: {seeded_total} event(s)")
    print(f"Rows shown (most recent): {len(rows)}")
    print("-" * 78)

    if not rows:
        print("(no rows returned — is the table empty or the DSN wrong?)")
        print("-" * 78)
        return

    header = f"{'event_type':<32} {'service':<11} tags"
    print(header)
    print("-" * 78)
    for row in rows:
        et = row["event_type"]
        service = row["service"]
        try:
            tags_obj = json.loads(row["tags"]) if row["tags"] else {}
        except json.JSONDecodeError:
            tags_obj = {"<unparsed>": row["tags"]}
        # Compact JSON in the column so the table stays narrow.
        tags_str = json.dumps(tags_obj, sort_keys=True)
        print(f"{et:<32} {service:<11} {tags_str}")

    print("-" * 78)

    # ── trimming evidence ────────────────────────────────────────────────────
    print("TRIMMING EVIDENCE (allowlist filter before insert):")
    forbidden_markers = ("password_raw", "tracking_number")
    leaked = []
    for row in rows:
        tags_text = row["tags"] or ""
        for marker in forbidden_markers:
            if f'"{marker}"' in tags_text:
                leaked.append((row["event_type"], marker))
    if leaked:
        print(f"  ❌ LEAK DETECTED — {', '.join(f'{et}.{marker}' for et, marker in leaked)}")
        print("    Out-of-plan keys reached the database. Do not screenshot this.")
    else:
        print("  ✅ No out-of-plan keys present in any row's tags — storage boundary trims correctly.")
    print("=" * 78)


def main() -> int:
    """Entry point: connect, optionally seed, then print the verification table."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Do not insert anything; only query and print the current table.",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=6,
        help="Number of events to seed (default 6). Ignored with --verify-only.",
    )
    args = parser.parse_args()

    from services.telemetry_storage import _connect

    try:
        conn = _connect()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    conn.autocommit = True  # verification reads don't need a transaction
    try:
        # Fail fast with a helpful message if the table is missing.
        with conn.cursor() as cur:
            cur.execute(
                """\
                SELECT to_regclass('public.telemetry_events')
                """
            )
            exists = cur.fetchone()[0]
        if not exists:
            print(
                "ERROR: table 'telemetry_events' does not exist. Run "
                "scripts/create_telemetry_table.sql in the Supabase SQL editor first.",
                file=sys.stderr,
            )
            return 1

        seeded_total = 0
        if not args.verify_only:
            seeded_total = _seed(conn, args.count)

        rows = _verify(conn)
        _print_report(rows, seeded_total)
        return 0
    except Exception as exc:  # noqa: BLE001 — report any DB/seed failure cleanly
        conn.rollback()
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())

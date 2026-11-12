# MCP Playground validation

Validation session: November 11, 2026 (America/New_York).

- [x] Port 8001 made public with user approval; port 8000 remains private.
- [x] Logto OAuth bearer token connected MCP Playground to TrackFlow Company Tools.
- [x] Discovery displayed all four tools.
- [x] create_incident succeeded with a disposable local evaluation record.
- [x] get_incident returned that record.
- [x] update_incident_status completed open -> in_progress -> resolved.
- [x] query_inventory succeeded with ok=true, read_only=true, count=0 for an intentional no-match SKU.
- [x] Inventory modification attempt rejected with read_only error, status 405.
- [x] 35 automated MCP tests passed, including browser CORS preflight regression checks.
- [x] Live missing/invalid bearer tokens rejected (401); insufficient scope rejected (403).
- [x] Private configuration validator: 10 passed, 0 failed.

The backend session expired during testing. It was renewed through the existing TrackFlow login form, saved privately, and the MCP server restarted. Subsequent lifecycle calls passed.

Evaluation record ID: 2ca478c6-e57c-4bba-b56d-15e7568efc38 (resolved).

Temporary-token limitations: renew the Logto MCP token and sign in to TrackFlow again when their respective tokens expire. Restart the MCP server after changing MCP_BACKEND_TOKEN. The endpoint also requires the Codespace and both servers to remain running.

This documents observed local and Playground checks; it does not claim a grade awarded by 4Geeks.

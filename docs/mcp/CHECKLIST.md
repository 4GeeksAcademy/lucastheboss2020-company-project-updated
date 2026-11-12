# MCP Delivery Checklist — Actual Outcomes

| Area | Status | Evidence |
|------|--------|----------|
| Streamable HTTP transport | ✅ Done | `FastMCP(transport="streamable-http")` in `mcps/server.py` |
| OAuth resource-server JWT validation | ✅ Done | `mcpauth` middleware with JWKS, issuer, audience, expiry |
| Per-tool scope gates | ✅ Done | `incidents:write`, `incidents:read`, `inventory:read` + `mcp:connect` for discovery |
| Incident lifecycle (create/get/status) | ✅ Done | 3 tools: `create_incident`, `get_incident`, `update_incident_status` |
| Inventory read-only boundary | ✅ Done | `query_inventory` tool; backend client rejects writes |
| Typed discovery envelopes | ✅ Done | Pydantic `ToolResult`/`ToolError` with ok/data/error/count/read_only |
| LangGraph MCP/RAG routing | ✅ Done | `mcps/agent.py` routes via `MultiServerMCPClient` |
| **CORS: metadata no Origin → `*`** | ✅ Done | `ProtectedResourceMetadataApp._cors_for_request` returns `*` |
| **CORS: metadata allowed origin → echo + Vary** | ✅ Done | Returns origin with `Vary: Origin` header |
| **CORS: metadata disallowed origin → no ACAO** | ✅ Done | Returns `{}`, so no ACAO header emitted |
| **CORS: middleware order (CORS outermost)** | ✅ Done | CORSMiddleware → bearer_auth → ToolScope → FastMCP |
| **CLI: validate_config** | ✅ Done | `mcps/tools/validate_config.py` — PASS/FAIL per setting |
| **CLI: check_readiness** | ✅ Done | `mcps/tools/check_readiness.py` — ready: true/false |
| **CLI: oauth_fixture_server** | ✅ Done | `mcps/tools/oauth_fixture_server.py` — tested in integration tests |
| Protocol tests (26 collected) | ✅ 26/26 pass | `test_protocol.py` — auth, scopes, CORS, agent, adapter |
| Integration tests (7) | ✅ 7/7 pass | `test_local_integration.py` — real backend on disposable storage |
| Agent tests (2) | ✅ 2/2 pass | Agent token/loopback validation |
| **Combined MCPS regression** | **✅ 35/35 pass** | All `tests/mcps/` collected |

## ❌ Not delivered (requires external setup)

| Requirement | Blocked by |
|------------|-----------|
| External OAuth provider (Logto) configuration | Requires: tenant, API resource, M2M app, callback URIs, roles — none provisioned |
| MCP Playground OAuth flow | Requires: public Codespaces URL, registered callback, PKCE S256 flow end-to-end |
| Real backend on disposable records | Requires real API key / environment — tested locally via ASGI transport instead |
| Production-addressable MCP endpoint | Requires: public HTTPS, DNS, TLS — implementation not requestable during this pass |
| CI pipeline integration | Requires: configured CI runner (not in scope) |

## Configuration required to complete

```bash
# 1. Set real OAuth provider values (Logto example)
export MCP_OAUTH_ISSUER=https://<tenant>.logto.app/oidc
export MCP_OAUTH_AUTHORIZATION_URL=https://<tenant>.logto.app/oidc/auth
export MCP_OAUTH_TOKEN_URL=https://<tenant>.logto.app/oidc/token
export MCP_OAUTH_JWKS_URL=https://<tenant>.logto.app/oidc/jwks
export MCP_OAUTH_AUDIENCE=https://<codespace-url>.app.github.dev/mcp
export MCP_RESOURCE_URL=https://<codespace-url>.app.github.dev/mcp

# 2. Set backend connectivity
export MCP_BACKEND_URL=http://127.0.0.1:8000
export MCP_BACKEND_TOKEN=<token-from-backend-auth-flow>

# 3. Set CORS for Playground browser access
export MCP_ALLOWED_ORIGINS=https://<codespace-url>.app.github.dev

# 4. Start publicly
#    Set MCP_HOST=0.0.0.0 (only for Playground evaluation, never in production)
#    Forward port via Codespaces "Ports" panel → make public → Port visibility: Public
#    Use the public URL as the MCP endpoint in the Playground client
```

## Test counts by file

| File | Count | Status |
|------|-------|--------|
| `tests/mcps/test_protocol.py` | 26 | ✅ 26/26 |
| `tests/mcps/test_local_integration.py` | 7 | ✅ 7/7 |
| `tests/mcps/test_agent.py` | 2 | ✅ 2/2 |
| **Total** | **35** | **✅ 35/35** |
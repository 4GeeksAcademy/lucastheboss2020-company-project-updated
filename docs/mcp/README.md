# TrackFlow company-tools MCP

This Python service wraps the existing TrackFlow APIs; it does not replace them. The LangGraph CLI routes knowledge questions to the existing RAG pipeline and operational questions to tools discovered with langchain-mcp-adapters. There was no pre-existing LangGraph agent to migrate. Human Incident Manager navigation is preserved.

## Architecture and transport

Agent -> Streamable HTTP /mcp -> mcpauth JWT validation -> per-tool scope gate -> allowlisted backend client -> existing TrackFlow API.

Streamable HTTP supports independent remote clients and the course Playground requirement. stdio is not the delivery transport. OAuth protected-resource metadata is public at /.well-known/oauth-protected-resource and /.well-known/oauth-protected-resource/mcp. Tool listing and invocation require a valid token with mcp:connect. Tokens are checked against JWKS, issuer, audience, expiry and tool scopes; expiry is explicitly mandatory. The server fails startup when OAuth settings are absent. The application JWT and the 4Geeks generation key are not MCP OAuth credentials.

## Tools and permissions

| Tool | Extra scope | Downstream operation |
| --- | --- | --- |
| create_incident | incidents:write | POST /api/incidents |
| update_incident_status | incidents:write | PATCH /api/incidents/{UUID}/status |
| get_incident | incidents:read | GET /api/incidents/{UUID} |
| query_inventory | inventory:read | GET /inventory/products |

Discovery includes descriptions and typed input/output envelopes. Results contain ok and either data or error; inventory adds count/read_only. Incident enums and validation reuse the existing service models. Inventory permits read filters only; non-read operations, modification-style requests and unsupported write fields are rejected. Its downstream client also rejects arbitrary methods, paths and inventory write payloads.

The server uses a separately configured MCP_BACKEND_TOKEN for the internal API. Do not pass the MCP OAuth token through to that API. Use a dedicated, least-privilege TrackFlow principal and a local/test backend for initial validation. This is a single-company deployment; per-user or per-tenant backend identity isolation is not implemented by this service credential.

## Local commands

Use uv sync --frozen from the repository root. Copy mcps/.env.example to an ignored local environment file, fill it privately, then run:

    uv run --env-file mcps/.env.local --no-sync python -m mcps.server
    uv run --env-file mcps/.env.local --env-file backend/.env --no-sync python -m mcps.agent "Show inventory for SKU EXAMPLE"
    uv run --no-sync python -m pytest tests/mcps tests/pipelines/test_rag.py services/tests/test_knowledge_api.py -q --tb=short

The default listener is 127.0.0.1:8001. Keep Codespaces port visibility private during implementation. Existing RAG configuration remains in backend/.env and is needed for generated agent answers. The CLI's keyword router is intentionally minimal; it is not a general intent classifier or a conversational memory system.

## OAuth provider setup (Logto example)

1. In your Logto tenant, register a global API resource named TrackFlow MCP. Set its resource identifier to the exact eventual MCP endpoint URL, including /mcp. Use that same value for MCP_RESOURCE_URL and MCP_OAUTH_AUDIENCE. Do not use the LLM gateway URL.
2. Define mcp:connect, incidents:read, incidents:write and inventory:read on that API resource. Give a read-only client only mcp:connect plus the reads it needs. Grant incidents:write only to a role authorized to change incidents.
3. Register a public/native or SPA OAuth application for the chosen interactive MCP client, with Authorization Code and PKCE S256. Register the exact callback URI supplied by that client. Do not guess the Playground callback URI. Request this API resource and its selected scopes during authorization. For an external third-party client, follow Logto's third-party-app consent/registration guide. If the client supports only a different registration mechanism, validate compatibility before claiming Playground completion.
4. Read the tenant's OIDC discovery document. Copy its exact issuer, authorization_endpoint, token_endpoint and jwks_uri into the matching MCP_OAUTH_* settings. For Logto these are typically under /oidc; use discovery values rather than guessing or trimming the issuer.
5. Sign in through the registered client with state and a fresh PKCE verifier/challenge. Exchange the authorization code using that verifier and the same redirect URI/resource. The resulting access token must target the MCP resource, contain exp, and include the requested permitted scopes. An ID token is not an API access token.
6. Set MCP_ACCESS_TOKEN privately for the CLI. The current CLI accepts an already-issued token; it does not implement browser login or automatic refresh. Obtain a new token when it expires, or use the provider refresh-token flow if the registered client was authorized for offline_access and refresh. Never put tokens into screenshots, Git or chat.
7. Configure MCP_BACKEND_TOKEN separately using the existing TrackFlow authentication flow for the intended dedicated principal. The MCP service cannot mint or convert that credential. Configure MCP_BACKEND_URL for the test API, not an unrelated production endpoint.
8. Start privately and test metadata, valid discovery, 401 without/invalid token, 403 without a required tool scope, and controlled inventory-write rejection. Verify backend calls against disposable local/test records.
9. Only after those checks and approval to expose the service, forward the MCP port for the course Playground test. Set MCP_HOST=0.0.0.0 only for that deployment. Set MCP_ALLOWED_ORIGINS to the comma-separated origin URLs of the browser-based MCP Playground (e.g. your Codespaces preview domain); no CORS middleware is added when the variable is empty or unset. Never disable host validation or add a broad wildcard. Keep OAuth protection enabled. Update the resource/audience registration consistently if the endpoint URL changes.
10. Connect MCP Playground to the forwarded HTTPS /mcp URL, complete OAuth using the registered callback, and run create -> get -> allowed status transition plus inventory read and rejected write. Record sanitized results. Do not call this step complete using localhost or mocked APIs.

Official references: https://docs.logto.io/use-cases/ai/mcp-server-enable-third-party-ai-agent-access ; https://docs.logto.io/authorization/global-api-resources ; https://docs.logto.io/integrate-logto/third-party-applications ; https://modelcontextprotocol.io/specification/latest/basic/authorization .

## Errors and traceability

Missing/invalid/expired tokens return HTTP 401 with a protected-resource metadata challenge. Insufficient tool scopes return HTTP 403. Tool failures use an error envelope with code, message and status (e.g. invalid_input, read_only, not_found, invalid_status_transition, backend_unavailable). Authentication failures must not be confused with validation failures or generic provider errors. Valid tools log verified client ID, tool name and outcome; tokens, auth headers and request bodies are not audit fields. See tests/mcps for exact assertions.

## CLI tools

Three command-line utilities ship under `mcps.tools`:

| Tool | Purpose |
| --- | --- |
| `python -m mcps.tools.validate_config` | Check all MCP env vars; prints PASS/FAIL per setting name (never values/secrets). Exits 0 only when all pass. |
| `python -m mcps.tools.check_readiness` | Print `ready: true/false`, list missing required/recommended vars. Exits 0 when ready. |
| `python -m mcps.tools.oauth_fixture_server` | Start disposable OAuth provider (`.well-known/openid-configuration`, `/jwks`, `/token`, `/authorize`) on a random port. Generates an RSA key pair and issues test JWTs. Used by integration tests, not for production. |

## Acceptance and remaining external checks

- Implemented: Python server under mcps, Streamable HTTP, mcpauth resource-server validation, per-tool scopes, incident lifecycle route, read-only inventory boundary, typed discovery envelopes, LangGraph MCP/RAG routing, 3 CLI tools.
- CORS middleware added via MCP_ALLOWED_ORIGINS env var (comma-separated origins). Empty/unset adds no CORS. Only required for browser-based MCP Playground.
- CORS boundary on metadata endpoint: no `Origin` → `*` (public discovery); matching origin → echoed origin with `Vary: Origin`; disallowed origin → no `Access-Control-Allow-Origin` header. Middleware order: CORSMiddleware (outermost) → bearer_auth → ToolScopeMiddleware → FastMCP (innermost).
- Audience is enforced to match MCP_RESOURCE_URL exactly — prevents silent JWT audience misconfiguration.
- Local tests use generated RSA/JWKS tokens and isolated mocked downstream data; the actual LangChain MCP adapter connects over loopback. They do not prove a real provider's consent/registration configuration or production permissions.
- Integration tests use the real TrackFlow FastAPI backend on disposable TinyDB MemoryStorage + SQLite `:memory:`, with ASGI transport proxying through the MCP server — no server processes required.
- Combined regression: **35 tests** (26 MCP protocol tests + 7 local integration + 2 MCP agent on loopback adapter). All pass with `.venv/bin/python`. The original RAG pipeline (26 tests) passes separately.
- Pending: configure real OAuth issuer/resource/client/roles, issue least-privilege MCP and backend credentials, and test the real backend on disposable records.
- Pending: authorized public Codespaces forwarding and complete OAuth-enabled Playground flows per tool.
- No commit, push, merge or production database mutation is part of this implementation pass.

# Private MCP validation

- Configuration validator: 10 passed, 0 failed.
- MCP test suite: 35 passed (isolated in-memory backend fixtures).
- Test command: REDIS_URL=redis://127.0.0.1:6379/15 uv run --no-sync python -m pytest tests/mcps -q --tb=short
- Live Logto token accepted; discovery returned all four MCP tools.
- Missing and invalid tokens rejected with HTTP 401.
- A real Logto token missing inventory:read was rejected with HTTP 403.
- Live local backend: inventory query, incident create/get/status update succeeded; disposable incident resolved.
- Browser CORS regression fixed: MCP protocol/session/reconnect headers allowed and session header exposed.
- Playground origin preflight HTTP 200; untrusted origin rejected HTTP 400 without allowed-origin header.
- Private environment file remains ignored and contains separate MCP and backend tokens.

Completed: public port approval, MCP Playground connection and live tool checks. See PLAYGROUND_VALIDATION.md.
Tokens are temporary; refresh/relogin when expired.

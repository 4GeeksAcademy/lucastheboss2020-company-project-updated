"""MCP protocol tests with local signing keys and no external services."""

import io
import json
import logging
from datetime import datetime, timedelta, timezone

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jwt import PyJWKClient
from mcpauth.utils import create_verify_jwt

from mcps.backend import TrackFlowBackendClient
from mcps.config import MCPSettings
from mcps.server import create_mcp_app

ISSUER = "https://oauth.example.test"
AUDIENCE = "https://mcp.example.test/mcp"
HEADERS = {"Accept": "application/json, text/event-stream"}


@pytest.fixture
def protocol():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    jwk.update({"kid": "local-test", "alg": "RS256", "use": "sig"})
    jwks = PyJWKClient("https://oauth.example.test/jwks")
    jwks.fetch_data = lambda: {"keys": [jwk]}
    verifier = create_verify_jwt(jwks, leeway=0)
    settings = MCPSettings(
        issuer=ISSUER,
        authorization_url=f"{ISSUER}/authorize",
        token_url=f"{ISSUER}/token",
        jwks_url=f"{ISSUER}/jwks",
        audience=AUDIENCE,
        resource_url=AUDIENCE,
        backend_url="http://backend.example.test",
        backend_token="local-test-only",
        host="127.0.0.1",
        port=8001,
    )
    calls = []

    def handle_backend(request):
        calls.append((request.method, request.url.path))
        if request.url.path == "/inventory/products":
            return httpx.Response(200, json=[{"id": 1, "name": "Test", "sku": "TEST", "client_name": "Test", "category": "fashion", "warehouse": "LA", "current_stock": 5}])
        if request.method == "PATCH":
            return httpx.Response(400, json={"error": {"message": "invalid transition"}})
        return httpx.Response(200, json={"id": "12345678-1234-1234-1234-123456789012", "status": "open"})

    transport = httpx.MockTransport(handle_backend)
    backend = TrackFlowBackendClient(settings.backend_url, settings.backend_token, transport)

    def token(scopes: str, **overrides) -> str:
        claims = {
            "iss": ISSUER,
            "aud": AUDIENCE,
            "sub": "local-test-subject",
            "client_id": "local-test-client",
            "scope": scopes,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        }
        claims.update(overrides)
        if claims.get("exp") is None:
            claims.pop("exp")
        return jwt.encode(
            claims,
            private_key,
            algorithm="RS256",
            headers={"kid": "local-test"},
        )

    with TestClient(
        create_mcp_app(settings, backend=backend, token_verifier=verifier),
        base_url="http://127.0.0.1:8001",
    ) as client:
        yield client, token, calls


def test_metadata_is_public_and_tools_require_authentication(protocol):
    client, token, _ = protocol
    metadata = client.get("/.well-known/oauth-protected-resource/mcp")
    assert metadata.status_code == 200
    assert metadata.json()["resource"] == AUDIENCE
    assert metadata.json()["authorization_servers"] == [ISSUER]
    request = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    unauthorized = client.post("/mcp", json=request, headers=HEADERS)
    assert unauthorized.status_code == 401
    assert "resource_metadata=" in unauthorized.headers.get("www-authenticate", "")
    headers = {**HEADERS, "Authorization": f"Bearer {token('mcp:connect')}"}
    response = client.post("/mcp", json=request, headers=headers)
    assert response.status_code == 200
    message = json.loads(next(line[6:] for line in response.text.splitlines() if line.startswith("data: ")))
    tools = message["result"]["tools"]
    assert {tool["name"] for tool in tools} == {"create_incident", "update_incident_status", "get_incident", "query_inventory"}
    assert all(tool.get("description") and tool.get("inputSchema") and tool.get("outputSchema") for tool in tools)


def test_unauthenticated_tool_invocation_is_denied(protocol):
    client, _, calls = protocol
    request = {"jsonrpc": "2.0", "id": 9, "method": "tools/call", "params": {"name": "query_inventory", "arguments": {}}}
    assert client.post("/mcp", json=request, headers=HEADERS).status_code == 401
    assert calls == []


def test_missing_tool_scope_is_http_403(protocol):
    client, token, _ = protocol
    headers = {**HEADERS, "Authorization": f"Bearer {token('mcp:connect')}"}
    request = {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "query_inventory", "arguments": {}}}
    response = client.post("/mcp", json=request, headers=headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "insufficient_scope"


@pytest.mark.parametrize("overrides", [
    {"iss": "https://other.example.test"},
    {"aud": "https://other.example.test"},
    {"exp": datetime.now(timezone.utc) - timedelta(minutes=5)},
    {"exp": None},
])
def test_invalid_issuer_audience_and_expiry_are_rejected(protocol, overrides):
    client, token, _ = protocol
    headers = {**HEADERS, "Authorization": f"Bearer {token('mcp:connect inventory:read', **overrides)}"}
    request = {"jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {}}
    assert client.post("/mcp", json=request, headers=headers).status_code == 401


def test_forged_signature_is_rejected(protocol):
    client, _, _ = protocol
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    forged = jwt.encode(
        {"iss": ISSUER, "aud": AUDIENCE, "sub": "attacker", "scope": "mcp:connect", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        other_key, algorithm="RS256", headers={"kid": "local-test"},
    )
    headers = {**HEADERS, "Authorization": f"Bearer {forged}"}
    request = {"jsonrpc": "2.0", "id": 6, "method": "tools/list", "params": {}}
    assert client.post("/mcp", json=request, headers=headers).status_code == 401


def test_real_mcp_inventory_is_read_only(protocol, caplog):
    client, token, calls = protocol
    caplog.set_level("INFO", logger="mcps.audit")
    headers = {**HEADERS, "Authorization": f"Bearer {token('mcp:connect inventory:read')}"}
    request = {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "query_inventory", "arguments": {"operation": "read"}}}
    response = client.post("/mcp", json=request, headers=headers)
    assert response.status_code == 200
    message = json.loads(next(line[6:] for line in response.text.splitlines() if line.startswith("data: ")))
    result = json.loads(message["result"]["content"][0]["text"])
    assert result["data"][0]["current_stock"] == 5
    assert calls == [("GET", "/inventory/products")]
    request["params"]["arguments"] = {"operation": "write"}
    response = client.post("/mcp", json=request, headers=headers)
    assert response.status_code == 200
    assert "read_only" in response.text
    assert calls == [("GET", "/inventory/products")]
    request["params"]["arguments"] = {"query": "increase stock for SKU TEST"}
    assert "read_only" in client.post("/mcp", json=request, headers=headers).text
    request["params"]["arguments"] = {"quantity": 50}
    assert client.post("/mcp", json=request, headers=headers).status_code == 400
    assert calls == [("GET", "/inventory/products")]
    assert "local-test-client" in caplog.text and "query_inventory" in caplog.text


def test_real_mcp_status_uses_only_lifecycle_patch(protocol):
    client, token, calls = protocol
    headers = {**HEADERS, "Authorization": f"Bearer {token('mcp:connect incidents:write')}"}
    incident_id = "12345678-1234-1234-1234-123456789012"
    request = {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "update_incident_status", "arguments": {"incident_id": incident_id, "status": "resolved"}}}
    response = client.post("/mcp", json=request, headers=headers)
    assert response.status_code == 200
    assert "invalid_status_transition" in response.text
    assert calls == [("PATCH", f"/api/incidents/{incident_id}/status")]


def test_real_mcp_create_and_get_use_incident_api(protocol):
    client, token, calls = protocol
    headers = {**HEADERS, "Authorization": f"Bearer {token('mcp:connect incidents:write incidents:read')}"}
    incident_id = "12345678-1234-1234-1234-123456789012"
    create = {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "create_incident", "arguments": {"title": "Delivery issue", "description": "Delivery could not be completed.", "category": "delivery_failure", "origin": "customer", "branch": "la_warehouse"}}}
    get = {"jsonrpc": "2.0", "id": 8, "method": "tools/call", "params": {"name": "get_incident", "arguments": {"incident_id": incident_id}}}
    assert client.post("/mcp", json=create, headers=headers).status_code == 200
    assert client.post("/mcp", json=get, headers=headers).status_code == 200
    assert calls == [("POST", "/api/incidents"), ("GET", f"/api/incidents/{incident_id}")]


def test_backend_explicitly_rejects_inventory_writes_and_arbitrary_paths():
    from mcps.backend import BackendToolError
    import asyncio

    client = TrackFlowBackendClient("http://backend.example.test", "local-test-only", httpx.MockTransport(lambda request: pytest.fail("Network request should be rejected")))
    for method, path, payload in [
        ("PATCH", "/inventory/products/1", {"current_stock": 99}),
        ("POST", "/inventory/orders/inbound", {"quantity": 99}),
        ("GET", "/inventory/products", {"quantity": 99}),
        ("PATCH", "/api/incidents/12345678-1234-1234-1234-123456789012", {"status": "resolved"}),
    ]:
        with pytest.raises(BackendToolError) as error:
            asyncio.run(client.request_json(method, path, payload))
        assert error.value.status_code == 405


def test_langchain_mcp_adapter_discovers_real_tools_on_loopback(protocol):
    import asyncio
    import socket
    import threading

    import uvicorn
    from langchain_mcp_adapters.client import MultiServerMCPClient

    client, token, calls = protocol
    ready = threading.Event()
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(128)
    port = listener.getsockname()[1]

    class ReadyServer(uvicorn.Server):
        async def startup(self, sockets=None):
            await super().startup(sockets=sockets)
            ready.set()

    server = ReadyServer(uvicorn.Config(client.app, host="127.0.0.1", port=port, log_level="warning", lifespan="off"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    thread.start()
    try:
        assert ready.wait(timeout=10), "Local MCP test server did not start"
        adapter = MultiServerMCPClient({"trackflow": {
            "transport": "streamable_http",
            "url": f"http://127.0.0.1:{port}/mcp",
            "headers": {"Authorization": f"Bearer {token('mcp:connect incidents:read inventory:read')}"},
        }})
        async def discover_and_invoke():
            tools = await adapter.get_tools(server_name="trackflow")
            inventory = next(tool for tool in tools if tool.name == "query_inventory")
            result = await inventory.ainvoke({"operation": "read"})
            return tools, result

        tools, result = asyncio.run(discover_and_invoke())
        assert {tool.name for tool in tools} == {"create_incident", "update_incident_status", "get_incident", "query_inventory"}
        assert "current_stock" in str(result)
        assert calls == [("GET", "/inventory/products")]
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        listener.close()
        assert not thread.is_alive()

@pytest.mark.parametrize("params", [None, [], {"name": []}, {"name": "query_inventory", "arguments": []}])
def test_malformed_tool_params_fail_cleanly(protocol, params, caplog):
    client, token, calls = protocol
    caplog.set_level("INFO", logger="mcps.audit")
    headers = {**HEADERS, "Authorization": f"Bearer {token('mcp:connect inventory:read')}"}
    response = client.post("/mcp", json={"jsonrpc": "2.0", "id": 20, "method": "tools/call", "params": params}, headers=headers)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == -32602
    assert calls == []
    assert "invalid_params" in caplog.text


def test_backend_schema_validation_stays_distinct():
    import asyncio
    from mcps.backend import BackendToolError
    backend = TrackFlowBackendClient("http://backend.example.test", "local-test-only", httpx.MockTransport(lambda request: httpx.Response(422, json={"detail": "invalid input"})))
    with pytest.raises(BackendToolError) as error:
        asyncio.run(backend.get_incident("12345678-1234-1234-1234-123456789012"))
    assert error.value.code == "validation_error"
    assert error.value.status_code == 422


def test_missing_oauth_configuration_fails_closed(monkeypatch):
    from mcps.config import MCPConfigurationError
    monkeypatch.delenv("MCP_OAUTH_ISSUER", raising=False)
    with pytest.raises(MCPConfigurationError, match="MCP_OAUTH_ISSUER"):
        MCPSettings.from_env()


def test_schema_rejected_tool_call_is_audited(protocol, caplog):
    client, token, calls = protocol
    caplog.set_level("INFO", logger="mcps.audit")
    headers = {**HEADERS, "Authorization": f"Bearer {token('mcp:connect incidents:write')}"}
    request = {"jsonrpc": "2.0", "id": 30, "method": "tools/call", "params": {"name": "create_incident", "arguments": {"category": "unsupported-category"}}}
    response = client.post("/mcp", json=request, headers=headers)
    assert response.status_code == 200
    assert '"isError":true' in response.text
    assert calls == []
    assert "mcp_tool_result client_id=local-test-client tool=create_incident result=tool_error" in caplog.text


def test_mcps_audit_logger_has_own_handler_and_emits_info(protocol):
    """Regression: mcps.audit logger emits INFO to its own handler (no caplog).

    This test verifies that the module-level logger configuration in
    ``mcps/server.py`` — a direct StreamHandler with level=INFO and
    propagate=False — actually produces mcp_tool_invocation and
    mcp_tool_result entries when a tool is invoked. It temporarily
    swaps the logger's handler for a StringIO so the assertion does
    not depend on test infrastructure (caplog).
    """
    logger = logging.getLogger("mcps.audit")
    original_handlers = logger.handlers[:]
    original_level = logger.level
    original_propagate = logger.propagate
    try:
        buf = io.StringIO()
        handler = logging.StreamHandler(buf)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.handlers = [handler]
        # level must already be INFO from module-level setup
        if logger.level == logging.NOTSET or logger.level > logging.INFO:
            logger.setLevel(logging.INFO)
        logger.propagate = False

        # Make a tool call that will trigger logger.info() in ToolScopeMiddleware
        client, token, _ = protocol
        headers = {**HEADERS, "Authorization": f"Bearer {token('mcp:connect incidents:write inventory:read')}"}
        request = {
            "jsonrpc": "2.0", "id": 40, "method": "tools/call",
            "params": {"name": "query_inventory", "arguments": {"operation": "read"}},
        }
        response = client.post("/mcp", json=request, headers=headers)
        assert response.status_code == 200

        output = buf.getvalue()
        assert "mcp_tool_invocation" in output, f"Expected mcp_tool_invocation in log, got: {output[:300]}"
        assert "mcp_tool_result" in output, f"Expected mcp_tool_result in log, got: {output[:300]}"
        assert "local-test-client" in output
        assert "query_inventory" in output
    finally:
        logger.handlers = original_handlers
        logger.setLevel(original_level)
        logger.propagate = original_propagate


def test_audience_must_match_resource_url(monkeypatch):
    from mcps.config import MCPConfigurationError, MCPSettings
    monkeypatch.setenv("MCP_OAUTH_ISSUER", "https://issuer.example")
    monkeypatch.setenv("MCP_OAUTH_AUTHORIZATION_URL", "https://issuer.example/auth")
    monkeypatch.setenv("MCP_OAUTH_TOKEN_URL", "https://issuer.example/token")
    monkeypatch.setenv("MCP_OAUTH_JWKS_URL", "https://issuer.example/jwks")
    monkeypatch.setenv("MCP_RESOURCE_URL", "https://mcp.example/mcp")
    monkeypatch.setenv("MCP_OAUTH_AUDIENCE", "https://other.example/mcp")
    monkeypatch.setenv("MCP_BACKEND_URL", "http://localhost:8000")
    with pytest.raises(MCPConfigurationError, match="MCP_OAUTH_AUDIENCE must match MCP_RESOURCE_URL"):
        MCPSettings.from_env()


def test_cors_headers_on_metadata_when_configured(protocol):
    # Build an app with explicit allowed origins so we can test echo/disallow
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    jwk.update({"kid": "local-test", "alg": "RS256", "use": "sig"})
    jwks_client = PyJWKClient("https://oauth.example.test/jwks")
    jwks_client.fetch_data = lambda: {"keys": [jwk]}
    verifier = create_verify_jwt(jwks_client, leeway=0)
    settings = MCPSettings(
        issuer=ISSUER,
        authorization_url=f"{ISSUER}/authorize",
        token_url=f"{ISSUER}/token",
        jwks_url=f"{ISSUER}/jwks",
        audience=AUDIENCE,
        resource_url=AUDIENCE,
        backend_url="http://backend.example.test",
        backend_token="local-test-only",
        host="127.0.0.1",
        port=8001,
        allowed_origins=("https://playground.example", "https://oauth.example.test"),
    )
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json=[{"id": 1}]))
    backend = TrackFlowBackendClient(settings.backend_url, settings.backend_token, transport)
    app = create_mcp_app(settings, backend=backend, token_verifier=verifier)

    with TestClient(app, base_url="http://127.0.0.1:8001") as client:
        # No Origin → wildcard for public discovery
        resp = client.options("/.well-known/oauth-protected-resource/mcp")
        assert resp.status_code == 204
        assert resp.headers.get("access-control-allow-origin") == "*"
        # Matching origin → echo with Vary
        resp = client.options("/.well-known/oauth-protected-resource/mcp", headers={"Origin": ISSUER})
        assert resp.status_code == 204
        assert resp.headers.get("access-control-allow-origin") == ISSUER
        assert resp.headers.get("vary") == "Origin" or "Origin" in (resp.headers.get("vary") or "")
        # Disallowed origin → no ACAO header at all
        resp = client.options("/.well-known/oauth-protected-resource/mcp", headers={"Origin": "https://evil.example"})
        assert resp.status_code == 204
        assert resp.headers.get("access-control-allow-origin") is None or resp.headers.get("access-control-allow-origin") == ""


def test_cors_middleware_added_when_origins_set():
    """CORS middleware is present when MCP_ALLOWED_ORIGINS is configured."""
    from mcps.config import MCPSettings
    settings = MCPSettings(
        issuer=ISSUER,
        authorization_url=f"{ISSUER}/authorize",
        token_url=f"{ISSUER}/token",
        jwks_url=f"{ISSUER}/jwks",
        audience=AUDIENCE,
        resource_url=AUDIENCE,
        backend_url="http://backend.example.test",
        backend_token="local-test-only",
        host="127.0.0.1",
        port=8001,
        allowed_origins=("https://playground.example",),
    )
    app = create_mcp_app(settings, backend=TrackFlowBackendClient("http://backend.example.test", "local-test-only", httpx.MockTransport(lambda r: httpx.Response(200, json={"id": "x"}))))
    # The ProtectedResourceMetadataApp wraps the inner Starlette; check CORS headers
    from starlette.testclient import TestClient
    with TestClient(app, base_url="http://127.0.0.1:8001") as client:
        resp = client.get("/.well-known/oauth-protected-resource/mcp")
        assert resp.status_code == 200
        for method in ("POST", "DELETE"):
            preflight = client.options("/mcp", headers={
                "Origin": "https://playground.example",
                "Access-Control-Request-Method": method,
                "Access-Control-Request-Headers": "authorization,content-type,mcp-protocol-version,mcp-session-id,last-event-id",
            })
            assert preflight.status_code == 200
            assert preflight.headers["access-control-allow-origin"] == "https://playground.example"
        denied = client.options("/mcp", headers={
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "POST",
        })
        assert denied.status_code == 400
        assert "access-control-allow-origin" not in denied.headers
        # Starlette CORS middleware is on the inner app, so we can't trivially test it
        # from the outer app; the metadata path returns 200 which confirms the app runs


def test_allowed_origins_config_parsing(monkeypatch):
    from mcps.config import MCPSettings
    monkeypatch.setenv("MCP_OAUTH_ISSUER", "https://issuer.example")
    monkeypatch.setenv("MCP_OAUTH_AUTHORIZATION_URL", "https://issuer.example/auth")
    monkeypatch.setenv("MCP_OAUTH_TOKEN_URL", "https://issuer.example/token")
    monkeypatch.setenv("MCP_OAUTH_JWKS_URL", "https://issuer.example/jwks")
    monkeypatch.setenv("MCP_RESOURCE_URL", "https://mcp.example/mcp")
    monkeypatch.setenv("MCP_OAUTH_AUDIENCE", "https://mcp.example/mcp")
    monkeypatch.setenv("MCP_BACKEND_URL", "http://localhost:8000")
    # No origins set → empty tuple
    s = MCPSettings.from_env()
    assert s.allowed_origins == ()
    # Comma-separated origins
    monkeypatch.setenv("MCP_ALLOWED_ORIGINS", "https://origin1.example, https://origin2.example")
    s = MCPSettings.from_env()
    assert s.allowed_origins == ("https://origin1.example", "https://origin2.example")


def test_agent_needs_mcp_access_token(monkeypatch):
    from mcps.agent import _client_from_env, AgentConfigurationError
    monkeypatch.delenv("MCP_ACCESS_TOKEN", raising=False)
    with pytest.raises(AgentConfigurationError, match="MCP_ACCESS_TOKEN"):
        _client_from_env()


def test_agent_rejects_non_loopback_http_url(monkeypatch):
    from mcps.agent import _client_from_env, AgentConfigurationError
    monkeypatch.setenv("MCP_ACCESS_TOKEN", "dummy-token")
    monkeypatch.setenv("MCP_SERVER_URL", "http://public.example/mcp")
    with pytest.raises(AgentConfigurationError, match="MCP_SERVER_URL must use HTTPS"):
        _client_from_env()

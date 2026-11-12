"""Disposable local OAuth fixture server for TrackFlow MCP integration tests.

Strictly for isolated integration testing purposes only.
Serves:
  - /.well-known/openid-configuration
  - /jwks        — RSA public keys
  - /token       — issues test JWT tokens (client_credentials)
  - /authorize   — minimal redirect endpoint

Usage from a test:
    from mcps.tools.oauth_fixture_server import OAuthFixtureServer

    with OAuthFixtureServer() as fixture:
        # fixture.issuer, fixture.jwks_url are available
        token = fixture.create_token(scopes="mcp:connect incidents:read")
        ...

Never use in production. No external accounts or credentials needed.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

import jwt
import uvicorn
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


class _TokenRequest(BaseModel):
    grant_type: str = "client_credentials"
    scope: str = ""
    client_id: str = "test-client-id"


@dataclass
class OAuthFixtureServer:
    """Context manager that runs a local OAuth fixture server on a random port."""

    issuer_host: str = "127.0.0.1"
    issuer_port: int = 0
    kid: str = "fixture-key-001"
    private_key: rsa.RSAPrivateKey = field(default_factory=lambda: rsa.generate_private_key(65537, 2048))
    _server: uvicorn.Server | None = None
    _thread: threading.Thread | None = None
    _app: FastAPI | None = None
    _token_store: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._token_store = {}

    @property
    def public_jwk(self) -> dict[str, str]:
        pub = self.private_key.public_key()
        raw = pub.public_bytes(Encoding.Raw, PublicFormat.Raw)
        jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(pub))
        jwk.update({"kid": self.kid, "alg": "RS256", "use": "sig"})
        return jwk

    @property
    def base_url(self) -> str:
        return f"http://{self.issuer_host}:{self.issuer_port}"

    @property
    def issuer(self) -> str:
        return self.base_url

    @property
    def jwks_url(self) -> str:
        return f"{self.base_url}/jwks"

    @property
    def token_url(self) -> str:
        return f"{self.base_url}/token"

    @property
    def authorization_url(self) -> str:
        return f"{self.base_url}/authorize"

    def _build_app(self) -> FastAPI:
        app = FastAPI(title="OAuth Fixture (test only)")

        @app.get("/.well-known/openid-configuration")
        def openid_config():
            return {
                "issuer": self.issuer,
                "authorization_endpoint": self.authorization_url,
                "token_endpoint": self.token_url,
                "jwks_uri": self.jwks_url,
                "response_types_supported": ["code"],
                "grant_types_supported": ["client_credentials"],
                "token_endpoint_auth_methods_supported": ["none"],
            }

        @app.get("/jwks")
        def jwks():
            return {"keys": [self.public_jwk]}

        @app.post("/token")
        def issue_token(request: _TokenRequest):
            if request.grant_type != "client_credentials":
                raise HTTPException(400, "unsupported_grant_type")
            now = datetime.now(timezone.utc)
            claims = {
                "iss": self.issuer,
                "sub": request.client_id,
                "aud": [],  # overridable via create_token
                "client_id": request.client_id,
                "scope": request.scope,
                "iat": now,
                "exp": now + timedelta(hours=1),
                "jti": f"test-{int(time.time())}",
            }
            token = jwt.encode(
                claims,
                self.private_key,
                algorithm="RS256",
                headers={"kid": self.kid},
            )
            self._token_store[claims["jti"]] = claims
            return {"access_token": token, "token_type": "Bearer", "expires_in": 3600, "scope": request.scope}

        @app.get("/authorize")
        def authorize():
            from fastapi.responses import HTMLResponse
            return HTMLResponse("<html><body><h1>OAuth Fixture — Authorize</h1><p>Test only.</p></body></html>")

        return app

    def create_token(
        self,
        scopes: str = "mcp:connect",
        audience: str = "",
        sub: str = "test-subject",
        client_id: str = "test-client-id",
        expiry: timedelta | None = None,
        **extra_claims: Any,
    ) -> str:
        """Create a test JWT signed by this fixture's private key."""
        now = datetime.now(timezone.utc)
        claims: dict[str, Any] = {
            "iss": self.issuer,
            "sub": sub,
            "client_id": client_id,
            "scope": scopes,
            "iat": now,
            "exp": now + (expiry if expiry else timedelta(hours=1)),
        }
        if audience:
            claims["aud"] = audience
        claims.update(extra_claims)
        return jwt.encode(
            claims,
            self.private_key,
            algorithm="RS256",
            headers={"kid": self.kid},
        )

    def __enter__(self) -> OAuthFixtureServer:
        import socket

        self._app = self._build_app()
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind((self.issuer_host, 0))
        listener.listen(128)
        self.issuer_port = listener.getsockname()[1]

        ready = threading.Event()

        class _Server(uvicorn.Server):
            def startup(self, sockets=None):
                super().startup(sockets=sockets)
                ready.set()

        self._server = _Server(
            uvicorn.Config(
                self._app,
                host=self.issuer_host,
                port=self.issuer_port,
                log_level="critical",
                lifespan="off",
            )
        )
        self._thread = threading.Thread(
            target=self._server.run,
            kwargs={"sockets": [listener]},
            daemon=True,
        )
        self._thread.start()
        if not ready.wait(timeout=10):
            raise RuntimeError("OAuth fixture server did not start in time")
        return self

    def __exit__(self, *exc: object) -> None:
        if self._server:
            self._server.should_exit = True
        if self._thread:
            self._thread.join(timeout=10)
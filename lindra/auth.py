"""Minimal authentication (ADR 0005): one application token, one session.

Every page and API route is guarded by default. Only the paths listed in
OPEN_PATHS are reachable without the token. A request proves the token either
through the session cookie the login page sets or through an
`Authorization: Bearer <token>` header, which the environment checks use.
"""

from __future__ import annotations

import hashlib
import hmac

from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse
from starlette.types import ASGIApp, Receive, Scope, Send

LOGIN_PATH = "/anmelden"
LOGOUT_PATH = "/abmelden"
HEALTH_PATH = "/health"
STATIC_PREFIX = "/static/"
API_PREFIX = "/api/"
SESSION_KEY = "angemeldet"

OPEN_PATHS = frozenset({HEALTH_PATH, LOGIN_PATH})


def token_matches(expected: str, presented: str | None) -> bool:
    if presented is None:
        return False
    return hmac.compare_digest(expected.encode(), presented.encode())


def session_secret(token: str) -> str:
    """Derive the cookie signing key from the one secret the operator manages."""
    return hashlib.sha256(b"lindra-session:" + token.encode()).hexdigest()


def bearer_token(scope: Scope) -> str | None:
    for name, value in scope.get("headers", []):
        if name == b"authorization":
            scheme, _, credentials = value.decode("latin-1").partition(" ")
            if scheme.lower() == "bearer":
                return credentials.strip()
    return None


def log_in(request: Request) -> None:
    request.session[SESSION_KEY] = True


def log_out(request: Request) -> None:
    request.session.clear()


def is_logged_in(request: Request) -> bool:
    return bool(request.session.get(SESSION_KEY))


class AuthGuard:
    """ASGI middleware: refuses every request that proves no token.

    API routes get a 401 with a German message; pages are sent to the login page.
    Must run inside SessionMiddleware so the session is already loaded.
    """

    def __init__(self, app: ASGIApp, token: str) -> None:
        self.app = app
        self.token = token

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or self.is_allowed(scope):
            await self.app(scope, receive, send)
            return
        if scope["path"].startswith(API_PREFIX):
            response = JSONResponse({"detail": "Anmeldung erforderlich"}, status_code=401)
        else:
            response = RedirectResponse(LOGIN_PATH, status_code=303)
        await response(scope, receive, send)

    def is_allowed(self, scope: Scope) -> bool:
        path = scope["path"]
        if path in OPEN_PATHS or path.startswith(STATIC_PREFIX):
            return True
        if scope.get("session", {}).get(SESSION_KEY):
            return True
        return token_matches(self.token, bearer_token(scope))

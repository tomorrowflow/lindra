"""Shared fixtures: an application with a known token and HTTP clients.

Tests drive the HTTP API the way the physician's browser would and assert only
what she would observe (status codes, redirects, page text, JSON bodies). They
never reach into sessions, templates or other internals.
"""

import pytest
from fastapi.testclient import TestClient

from lindra.app import create_app
from lindra.config import Settings

TOKEN = "test-token-for-the-suite"


@pytest.fixture
def app():
    return create_app(Settings(token=TOKEN))


@pytest.fixture
def anonymous(app):
    """A browser that has never logged in."""
    return TestClient(app)


@pytest.fixture
def api_client(app):
    """A client that sends the application token on every request."""
    return TestClient(app, headers={"Authorization": f"Bearer {TOKEN}"})

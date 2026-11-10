"""Shared fixtures: an application with a known token and HTTP clients.

Tests drive the HTTP API the way the physician's browser would and assert only
what she would observe (status codes, redirects, page text, JSON bodies). They
never reach into sessions, templates or other internals.
"""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from lindra.app import create_app
from lindra.config import Settings

TOKEN = "test-token-for-the-suite"
# The application's clock in every test: a Tuesday afternoon in the middle of November.
NOW = datetime(2026, 11, 10, 14, 30, 41)


@pytest.fixture
def app(tmp_path):
    return create_app(Settings(token=TOKEN, data_dir=tmp_path), clock=lambda: NOW)


@pytest.fixture
def anonymous(app):
    """A browser that has never logged in."""
    return TestClient(app)


@pytest.fixture
def browser(app):
    """A browser logged in through the login page."""
    client = TestClient(app)
    client.post("/anmelden", data={"token": TOKEN})
    return client


@pytest.fixture
def api_client(app):
    """A client that sends the application token on every request."""
    return TestClient(app, headers={"Authorization": f"Bearer {TOKEN}"})

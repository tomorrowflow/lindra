"""The Lindra web service: health endpoint, login, the case pages and the JSON API."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from lindra import (
    auth,
    badges,
    case_api,
    cases,
    drafts,
    formatting,
    pages,
    review,
    review_api,
    review_pages,
    seed,
)
from lindra.cast import load_cast
from lindra.config import Settings
from lindra.pages import Clock
from lindra.standins import FixtureTextModel
from lindra.store import DATABASE_FILE, Store
from lindra.textmodel import TextModel

PACKAGE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=PACKAGE_DIR / "templates")
TEMPLATES.env.filters["german_date"] = formatting.german_date
TEMPLATES.env.filters["german_datetime"] = formatting.german_datetime
TEMPLATES.env.globals["german_period"] = formatting.german_period
TEMPLATES.env.globals["encounter_labels"] = cases.ENCOUNTER_LABELS
TEMPLATES.env.globals["encounter_badge"] = badges.encounter_badge
TEMPLATES.env.globals["badge_states"] = badges.STATES
TEMPLATES.env.globals["section_badges"] = badges.section_badges
TEMPLATES.env.globals["section_state"] = badges.section_state
TEMPLATES.env.globals["section_text"] = drafts.section_text
TEMPLATES.env.filters["excerpt"] = drafts.excerpt
TEMPLATES.env.globals["outdated_reason"] = drafts.OUTDATED_REASON
LOGIN_ERROR = "Der Zugangsschlüssel ist nicht gültig"


def wall_clock(timezone: str) -> Clock:
    """The physician's local date and time, without a zone: what the forms compare against."""
    zone = ZoneInfo(timezone)
    return lambda: datetime.now(zone).replace(tzinfo=None)


def create_app(
    settings: Settings | None = None,
    clock: Clock | None = None,
    text_model: TextModel | None = None,
) -> FastAPI:
    """Build the service. `clock` is "now" for the pages; tests and screenshots pass a fixed
    one. `text_model` replaces the configured adapter; tests pass one that fails."""
    settings = settings or Settings.from_env()
    app = FastAPI(title="Lindra", docs_url=None, redoc_url=None, openapi_url=None)
    app.mount("/static", StaticFiles(directory=PACKAGE_DIR / "static"), name="static")
    store = Store(settings.data_dir / DATABASE_FILE)
    model = text_model or FixtureTextModel(load_cast())
    generations = review.Generations()
    app.include_router(case_api.build_router(store))
    app.include_router(review_api.build_router(store, model, generations))
    now = clock or wall_clock(settings.timezone)
    app.include_router(pages.build_router(store, TEMPLATES, now, generations))
    app.include_router(review_pages.build_router(store, TEMPLATES, generations))

    # Middleware added later wraps the earlier ones, so the session is loaded
    # before the guard looks at it.
    app.add_middleware(auth.AuthGuard, token=settings.token)
    app.add_middleware(
        SessionMiddleware,
        secret_key=auth.session_secret(settings.token),
        session_cookie="lindra_session",
        same_site="lax",
        https_only=False,
    )

    @app.get(auth.HEALTH_PATH)
    def health() -> dict[str, str]:
        return {"status": "ok"}

    # The smallest authenticated route: the environment check and the tests use
    # it to prove a token is accepted.
    @app.get("/api/session")
    def session_state() -> dict[str, bool]:
        return {"authenticated": True}

    # What `scripts/env.py check` reads: which stand-ins and commit run here, and
    # whether the seed hook has run on this volume.
    @app.get("/api/environment")
    def environment() -> dict[str, Any]:
        return {
            "tier": settings.tier,
            "commit": settings.commit,
            "text_backend": settings.text_backend,
            "speech_backend": settings.speech_backend,
            "seed": seed.read_report(store, settings.data_dir),
        }

    # The seed hook `scripts/env.py reset` calls: the fictional cast, nothing else.
    @app.post("/api/seed")
    def seed_cast() -> dict[str, Any]:
        try:
            report = seed.run(store, settings.data_dir)
            # The cases are stored again under new ids; nothing of the old runs applies.
            generations.reset()
            return report
        except seed.InvalidCast as error:
            raise HTTPException(status_code=500, detail=str(error)) from error

    @app.get(auth.LOGIN_PATH, response_class=HTMLResponse)
    def login_page(request: Request) -> Response:
        if auth.is_logged_in(request):
            return RedirectResponse("/", status_code=303)
        return TEMPLATES.TemplateResponse(request, "login.html")

    @app.post(auth.LOGIN_PATH, response_class=HTMLResponse)
    def login(request: Request, token: Annotated[str, Form()] = "") -> Response:
        if not auth.token_matches(settings.token, token):
            return TEMPLATES.TemplateResponse(
                request, "login.html", {"error": LOGIN_ERROR}, status_code=400
            )
        auth.log_in(request)
        return RedirectResponse("/", status_code=303)

    @app.post(auth.LOGOUT_PATH)
    def logout(request: Request) -> Response:
        auth.log_out(request)
        return RedirectResponse(auth.LOGIN_PATH, status_code=303)

    return app


# `uvicorn lindra.app:app --factory` builds the application from the environment.
app = create_app

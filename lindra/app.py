"""The Lindra web service: health endpoint, login and the application shell."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from lindra import auth, seed
from lindra.config import Settings

PACKAGE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=PACKAGE_DIR / "templates")
LOGIN_ERROR = "Der Zugangsschlüssel ist nicht gültig"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    app = FastAPI(title="Lindra", docs_url=None, redoc_url=None, openapi_url=None)
    app.mount("/static", StaticFiles(directory=PACKAGE_DIR / "static"), name="static")

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

    # The one authenticated API route of the scaffold: the environment check
    # (ticket 02) and the tests use it to prove a token is accepted.
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
            "seed": seed.read_report(settings.data_dir),
        }

    # The seed hook `scripts/env.py reset` calls: the fictional cast, nothing else.
    @app.post("/api/seed")
    def seed_cast() -> dict[str, Any]:
        try:
            return seed.run(settings.data_dir)
        except seed.InvalidCast as error:
            raise HTTPException(status_code=500, detail=str(error)) from error

    @app.get("/", response_class=HTMLResponse)
    def shell(request: Request) -> Response:
        return TEMPLATES.TemplateResponse(request, "shell.html")

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

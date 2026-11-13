"""Settings read once at the process boundary (ADR 0005: one token, one user).

The values come from the environment, which the gitignored `.env` file feeds.
Nothing else in the application reads the environment.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ENV_FILE = Path(".env")
TOKEN_VARIABLE = "LINDRA_TOKEN"
TEXT_BACKEND_VARIABLE = "LINDRA_TEXT_BACKEND"
SPEECH_BACKEND_VARIABLE = "LINDRA_SPEECH_BACKEND"
DATA_DIR_VARIABLE = "LINDRA_DATA_DIR"
COMMIT_VARIABLE = "LINDRA_COMMIT"
TIER_VARIABLE = "LINDRA_TIER"
TIMEZONE_VARIABLE = "LINDRA_TIMEZONE"
# "Now" for a new visit is the physician's wall clock, whatever zone the host runs in.
DEFAULT_TIMEZONE = "Europe/Berlin"

TEXT_URL_VARIABLE = "LINDRA_TEXT_URL"
TEXT_MODEL_VARIABLE = "LINDRA_TEXT_MODEL"
SPEECH_URL_VARIABLE = "LINDRA_SPEECH_URL"
SPEECH_PATH_VARIABLE = "LINDRA_SPEECH_PATH"
SPEECH_MODEL_VARIABLE = "LINDRA_SPEECH_MODEL"
HOSTED_URL_VARIABLE = "LINDRA_HOSTED_URL"
HOSTED_MODEL_VARIABLE = "LINDRA_HOSTED_MODEL"
# The hosted account's key is read from the process environment only, never from the env file:
# the operator supplies it at launch (ADR 0003, ADR 0007).
HOSTED_KEY_VARIABLE = "LINDRA_HOSTED_KEY"

# The name of the deterministic stand-in backends in lindra/standins.py.
STAND_IN = "fixture"
SELF_HOSTED = "selfhosted"
HOSTED = "hosted"
# The product offers the fixture model and the self-hosted model; the hosted comparison is a
# third text backend that exists for the evaluation only. Speech recognition is never hosted.
TEXT_BACKENDS = frozenset({STAND_IN, SELF_HOSTED, HOSTED})
SPEECH_BACKENDS = frozenset({STAND_IN, SELF_HOSTED})

# The explicitly launched evaluation configuration (ADR 0003, ADR 0007). It is the only tier
# in which a backend other than the stand-in starts, and it is never the default of any tier.
EVALUATION_TIER = "evaluation"
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
DEFAULT_TEXT_URL = "http://127.0.0.1:11434"
DEFAULT_SPEECH_URL = "http://127.0.0.1:8080"
DEFAULT_SPEECH_PATH = "/inference"


class MissingToken(RuntimeError):
    """Raised when the application starts without an application token."""


class UnsupportedBackend(RuntimeError):
    """Raised when a backend that does not exist is requested."""


class OutsideEvaluation(UnsupportedBackend):
    """Raised when a real or hosted backend is requested outside the evaluation configuration."""


class IncompleteBackend(RuntimeError):
    """Raised when a real backend lacks a setting it cannot start without."""


class HostedKeyMissing(IncompleteBackend):
    """Raised when the hosted comparison starts without the operator's account key."""


class UnknownTimezone(RuntimeError):
    """Raised when the configured time zone does not exist."""


@dataclass(frozen=True)
class Settings:
    token: str
    data_dir: Path = Path("data")
    text_backend: str = STAND_IN
    speech_backend: str = STAND_IN
    commit: str = "unknown"
    tier: str = "development"
    timezone: str = DEFAULT_TIMEZONE
    text_url: str = DEFAULT_TEXT_URL
    text_model: str = ""
    speech_url: str = DEFAULT_SPEECH_URL
    speech_path: str = DEFAULT_SPEECH_PATH
    speech_model: str = ""
    hosted_url: str = ""
    hosted_model: str = ""
    # Never shown by repr, so a log line or a traceback cannot leak it.
    hosted_key: str = field(default="", repr=False)

    def __post_init__(self) -> None:
        check_backends(self)

    @property
    def evaluation(self) -> bool:
        return self.tier == EVALUATION_TIER

    @classmethod
    def from_env(cls, env_file: Path = ENV_FILE) -> Settings:
        values = read_env_file(env_file)
        if values.get(TIER_VARIABLE, "").strip() == EVALUATION_TIER:
            # A file that stays on disk must not switch the real backends on by itself.
            raise OutsideEvaluation(
                f"{TIER_VARIABLE}={EVALUATION_TIER} in {env_file} is refused. The evaluation "
                "configuration is launched explicitly, through the process environment, "
                "with scripts/evaluation.py."
            )
        values.update(os.environ)
        token = values.get(TOKEN_VARIABLE, "").strip()
        if not token:
            raise MissingToken(
                f"{TOKEN_VARIABLE} is not set. Copy .env.example to .env and put a token in it."
            )
        return cls(
            token=token,
            data_dir=Path(values.get(DATA_DIR_VARIABLE, "").strip() or "data"),
            text_backend=values.get(TEXT_BACKEND_VARIABLE, "").strip() or STAND_IN,
            speech_backend=values.get(SPEECH_BACKEND_VARIABLE, "").strip() or STAND_IN,
            commit=values.get(COMMIT_VARIABLE, "").strip() or "unknown",
            tier=values.get(TIER_VARIABLE, "").strip() or "development",
            timezone=timezone(values),
            text_url=values.get(TEXT_URL_VARIABLE, "").strip() or DEFAULT_TEXT_URL,
            text_model=values.get(TEXT_MODEL_VARIABLE, "").strip(),
            speech_url=values.get(SPEECH_URL_VARIABLE, "").strip() or DEFAULT_SPEECH_URL,
            speech_path=values.get(SPEECH_PATH_VARIABLE, "").strip() or DEFAULT_SPEECH_PATH,
            speech_model=values.get(SPEECH_MODEL_VARIABLE, "").strip(),
            hosted_url=values.get(HOSTED_URL_VARIABLE, "").strip(),
            hosted_model=values.get(HOSTED_MODEL_VARIABLE, "").strip(),
            hosted_key=os.environ.get(HOSTED_KEY_VARIABLE, "").strip(),
        )


def timezone(values: dict[str, str]) -> str:
    chosen = values.get(TIMEZONE_VARIABLE, "").strip() or DEFAULT_TIMEZONE
    try:
        ZoneInfo(chosen)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise UnknownTimezone(f"{TIMEZONE_VARIABLE}={chosen} is not a time zone.") from error
    return chosen


def check_backends(settings: Settings) -> None:
    """Refuse a backend configuration that must not start (ADR 0003, ADR 0007).

    Any backend but the stand-in needs the evaluation configuration, and the hosted comparison
    needs the operator's own address, model and key besides. There is no fallback from one
    backend to another: what is configured is what runs, or the service does not start.
    """
    for variable, chosen, offered in (
        (TEXT_BACKEND_VARIABLE, settings.text_backend, TEXT_BACKENDS),
        (SPEECH_BACKEND_VARIABLE, settings.speech_backend, SPEECH_BACKENDS),
    ):
        if chosen not in offered:
            names = ", ".join(sorted(offered))
            raise UnsupportedBackend(f"{variable}={chosen} does not exist. Choose one of: {names}.")
        if chosen != STAND_IN and not settings.evaluation:
            raise OutsideEvaluation(
                f"{variable}={chosen} runs only in the evaluation configuration "
                f"({TIER_VARIABLE}={EVALUATION_TIER}), which is launched explicitly with "
                "scripts/evaluation.py and is never the default of a tier. Outside it only "
                f"the '{STAND_IN}' stand-in runs."
            )
    if settings.text_backend == SELF_HOSTED and not settings.text_model:
        raise IncompleteBackend(
            f"{TEXT_BACKEND_VARIABLE}={SELF_HOSTED} needs {TEXT_MODEL_VARIABLE}."
        )
    if settings.text_backend == HOSTED:
        for variable, value in (
            (HOSTED_URL_VARIABLE, settings.hosted_url),
            (HOSTED_MODEL_VARIABLE, settings.hosted_model),
        ):
            if not value:
                raise IncompleteBackend(f"{TEXT_BACKEND_VARIABLE}={HOSTED} needs {variable}.")
        address = urlsplit(settings.hosted_url)
        if address.username or address.password:
            raise IncompleteBackend(
                f"{HOSTED_URL_VARIABLE} must not carry a user name or password."
            )
        if address.scheme != "https" and address.hostname not in LOOPBACK_HOSTS:
            raise IncompleteBackend(
                f"{HOSTED_URL_VARIABLE} must be an https address: the account key travels with "
                "every request."
            )
        if not settings.hosted_key:
            raise HostedKeyMissing(
                f"{TEXT_BACKEND_VARIABLE}={HOSTED} needs the operator's own account key in "
                f"{HOSTED_KEY_VARIABLE}, supplied at launch. It is never read from a file."
            )


def read_env_file(path: Path) -> dict[str, str]:
    """Parse `KEY=VALUE` lines; comments and blank lines are skipped."""
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values

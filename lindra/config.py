"""Settings read once at the process boundary (ADR 0005: one token, one user).

The values come from the environment, which the gitignored `.env` file feeds.
Nothing else in the application reads the environment.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from lindra.standins import STAND_IN

ENV_FILE = Path(".env")
TOKEN_VARIABLE = "LINDRA_TOKEN"
TEXT_BACKEND_VARIABLE = "LINDRA_TEXT_BACKEND"
SPEECH_BACKEND_VARIABLE = "LINDRA_SPEECH_BACKEND"
DATA_DIR_VARIABLE = "LINDRA_DATA_DIR"
COMMIT_VARIABLE = "LINDRA_COMMIT"
TIER_VARIABLE = "LINDRA_TIER"

# Only the stand-ins exist. The self-hosted and hosted backends arrive with
# ticket 11 and never become selectable in the throwaway or test tier (ADR 0003).
SUPPORTED_BACKENDS = frozenset({STAND_IN})


class MissingToken(RuntimeError):
    """Raised when the application starts without an application token."""


class UnsupportedBackend(RuntimeError):
    """Raised when a backend other than the stand-in is requested."""


@dataclass(frozen=True)
class Settings:
    token: str
    data_dir: Path = Path("data")
    text_backend: str = STAND_IN
    speech_backend: str = STAND_IN
    commit: str = "unknown"
    tier: str = "development"

    @classmethod
    def from_env(cls, env_file: Path = ENV_FILE) -> Settings:
        values = read_env_file(env_file)
        values.update(os.environ)
        token = values.get(TOKEN_VARIABLE, "").strip()
        if not token:
            raise MissingToken(
                f"{TOKEN_VARIABLE} is not set. Copy .env.example to .env and put a token in it."
            )
        return cls(
            token=token,
            data_dir=Path(values.get(DATA_DIR_VARIABLE, "").strip() or "data"),
            text_backend=backend(values, TEXT_BACKEND_VARIABLE),
            speech_backend=backend(values, SPEECH_BACKEND_VARIABLE),
            commit=values.get(COMMIT_VARIABLE, "").strip() or "unknown",
            tier=values.get(TIER_VARIABLE, "").strip() or "development",
        )


def backend(values: dict[str, str], variable: str) -> str:
    chosen = values.get(variable, "").strip() or STAND_IN
    if chosen not in SUPPORTED_BACKENDS:
        raise UnsupportedBackend(
            f"{variable}={chosen} is not available. Only the '{STAND_IN}' stand-in exists; "
            "real backends arrive with a later ticket and never run in the throwaway or "
            "test tier."
        )
    return chosen


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

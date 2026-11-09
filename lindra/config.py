"""Settings read once at the process boundary (ADR 0005: one token, one user).

The token comes from the environment, which the gitignored `.env` file feeds.
Nothing else in the application reads the environment.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ENV_FILE = Path(".env")
TOKEN_VARIABLE = "LINDRA_TOKEN"


class MissingToken(RuntimeError):
    """Raised when the application starts without an application token."""


@dataclass(frozen=True)
class Settings:
    token: str

    @classmethod
    def from_env(cls, env_file: Path = ENV_FILE) -> Settings:
        values = read_env_file(env_file)
        values.update(os.environ)
        token = values.get(TOKEN_VARIABLE, "").strip()
        if not token:
            raise MissingToken(
                f"{TOKEN_VARIABLE} is not set. Copy .env.example to .env and put a token in it."
            )
        return cls(token=token)


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

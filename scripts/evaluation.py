#!/usr/bin/env python3
"""Launch the evaluation configuration and measure the real backends (ADR 0003, ADR 0007).

    serve     run the service with a real text model and recogniser on the fictional cast
    measure   run the cast through them and print the tables for docs/evaluation/real-backends.md

The evaluation configuration is the only one in which a self-hosted or hosted backend starts. It
is never the default of the throwaway, test or production tier: nothing but this script sets
`LINDRA_TIER=evaluation`. It refuses to start when the data directory holds anything but the
fictional cast. The hosted comparison also needs `--approved`, which states that the operator
approved the comparison run and its spend, and the operator's own account key in
`LINDRA_HOSTED_KEY` (asked for on the terminal when unset, never read from a file, never
printed). Speech recognition is self-hosted in every configuration.

Exit codes: 0 success, 1 a run failed, 2 the command cannot run as asked.
"""

from __future__ import annotations

import argparse
import getpass
import os
import secrets
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from lindra import backends, cast, evaluation, measure, seed  # noqa: E402
from lindra.config import (  # noqa: E402
    EVALUATION_TIER,
    HOSTED,
    HOSTED_KEY_VARIABLE,
    TOKEN_VARIABLE,
    Settings,
)
from lindra.store import DATABASE_FILE, Store  # noqa: E402

DEFAULT_PORT = 8790

BACKEND_OPTIONS = {
    "--text-backend": "LINDRA_TEXT_BACKEND",
    "--text-url": "LINDRA_TEXT_URL",
    "--text-model": "LINDRA_TEXT_MODEL",
    "--speech-backend": "LINDRA_SPEECH_BACKEND",
    "--speech-url": "LINDRA_SPEECH_URL",
    "--speech-path": "LINDRA_SPEECH_PATH",
    "--speech-model": "LINDRA_SPEECH_MODEL",
    "--hosted-url": "LINDRA_HOSTED_URL",
    "--hosted-model": "LINDRA_HOSTED_MODEL",
}
NOT_APPROVED = (
    "The hosted comparison needs --approved: it states that the operator approved this run and "
    "its spend (ADR 0003). Nothing was started."
)


class CannotRun(Exception):
    """The command cannot run as asked; the message says why."""


def add_backend_options(parser: argparse.ArgumentParser) -> None:
    for option, variable in BACKEND_OPTIONS.items():
        parser.add_argument(option, help=f"sets {variable}")
    parser.add_argument(
        "--approved",
        action="store_true",
        help="the operator approved the hosted comparison run and its spend",
    )


def settings_from(args: argparse.Namespace, data_dir: Path) -> Settings:
    """The evaluation configuration's settings: the options, then the environment."""
    for option, variable in BACKEND_OPTIONS.items():
        value = getattr(args, option.lstrip("-").replace("-", "_"))
        if value:
            os.environ[variable] = value
    os.environ["LINDRA_TIER"] = EVALUATION_TIER
    os.environ["LINDRA_DATA_DIR"] = str(data_dir)
    os.environ.setdefault(TOKEN_VARIABLE, secrets.token_urlsafe(32))
    if os.environ.get("LINDRA_TEXT_BACKEND") == HOSTED:
        if not args.approved:
            raise CannotRun(NOT_APPROVED)
        if not os.environ.get(HOSTED_KEY_VARIABLE) and sys.stdin.isatty():
            os.environ[HOSTED_KEY_VARIABLE] = getpass.getpass("Account key for the comparison: ")
    return Settings.from_env(Path(os.devnull))


def prepare_data_dir(data_dir: Path) -> Store:
    """Open the data directory's database, refusing anything but the fictional cast."""
    data_dir.mkdir(parents=True, exist_ok=True)
    store = Store(data_dir / DATABASE_FILE)
    evaluation.require_fictional_only(store, cast.load_cast())
    return store


def serve(args: argparse.Namespace) -> int:
    import uvicorn

    data_dir = Path(args.data_dir)
    settings = settings_from(args, data_dir)
    store = prepare_data_dir(data_dir)
    seed.run(store, data_dir)
    print(
        f"Evaluation configuration: text {settings.text_backend}, "
        f"speech {settings.speech_backend}, data {data_dir}. Only the fictional cast is stored."
    )
    print(f"Login token: {os.environ[TOKEN_VARIABLE]}")
    uvicorn.run("lindra.app:app", factory=True, host=args.host, port=args.port)
    return 0


def measure_run(args: argparse.Namespace) -> int:
    settings = settings_from(args, Path(args.data_dir))
    fictional = cast.load_cast()
    model = backends.build_text_model(settings, fictional)
    typed = measure.measure_text(model, fictional, measure.TYPED)
    speech_rows = []
    rows = typed
    if args.audio_dir:
        recogniser = backends.build_speech(settings, fictional)
        audio_dir = Path(args.audio_dir)
        speech_rows = measure.measure_speech(recogniser, fictional, audio_dir)
        rows = typed + measure.measure_dictated(model, recogniser, fictional, audio_dir)
    text_model = settings.hosted_model if settings.text_backend == HOSTED else settings.text_model
    header = (
        f"Text backend `{settings.text_backend}` (model `{text_model or 'none'}`), "
        f"speech backend `{settings.speech_backend}` "
        f"(model `{settings.speech_model or 'server default'}`).\n\n"
    )
    report = header + measure.render(rows, speech_rows)
    print(report)
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
    return 0 if all(row.outcome == measure.OK for row in rows) else 1


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = root.add_subparsers(dest="command", required=True)
    serving = commands.add_parser("serve", help="run the service in the evaluation configuration")
    serving.add_argument("--data-dir", required=True, help="empty, or holding only the cast")
    serving.add_argument("--host", default="127.0.0.1")
    serving.add_argument("--port", type=int, default=DEFAULT_PORT)
    add_backend_options(serving)
    serving.set_defaults(run=serve)
    measuring = commands.add_parser("measure", help="run the cast through the backends")
    measuring.add_argument("--data-dir", default=".", help="unused; the settings need one")
    measuring.add_argument("--audio-dir", help="recordings of the cast's clips, <clip key>.<ext>")
    measuring.add_argument("--out", help="also write the tables to this file")
    add_backend_options(measuring)
    measuring.set_defaults(run=measure_run)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return args.run(args)
    except (CannotRun, evaluation.NonFictionalData) as error:
        print(error, file=sys.stderr)
        return 2
    except RuntimeError as error:
        # A refused configuration (lindra.config): the message is the plain explanation.
        print(error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

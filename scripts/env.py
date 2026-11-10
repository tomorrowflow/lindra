#!/usr/bin/env python3
"""Bring up, check, reset and tear down a Lindra stack (ADR 0007).

One compose file and this one script serve every tier:

    up            build and start the stack, then seed the cast on a fresh volume
    check         health, an authenticated route, the stand-ins and the seed hook
    reset         run the seed hook: the fictional cast and nothing else
    down          remove the stack and its volume (production keeps the volume)
    ensure-test   test tier only: fetch origin/main, redeploy when it moved, check
    install-timer install the user timer that runs ensure-test every 5 minutes

Every command converges to the same state when run twice. Exit codes: 0 success,
1 a check or an action failed, 2 the command cannot run as asked. The script needs
only Python 3.12, git and Docker with the compose plugin (rootless Docker is the
supported setup). Secrets live in `.lindra-env/<project>.env`, which git ignores.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
STATE_DIR = REPO / ".lindra-env"
COMPOSE_FILE = "compose.yaml"
TEST_OVERRIDE = "compose.test.yaml"
PROD_OVERRIDE = "compose.prod.yaml"

TEST_PROJECT = "lindra-test"
TEST_PORT = 8780
TEST_BIND = "0.0.0.0"
PROD_PROJECT = "lindra-prod"
PROD_PORT = 8790
LOCAL_BIND = "127.0.0.1"

TEST_URL_VARIABLE = "LINDRA_TEST_URL"
TEST_TOKEN_VARIABLE = "LINDRA_TEST_TOKEN"

TIMER_NAME = "lindra-test-env.timer"
SERVICE_NAME = "lindra-test-env.service"
USER_UNIT_DIR = Path.home() / ".config" / "systemd" / "user"

STAND_IN = "fixture"
HEALTH_WAIT_SECONDS = 60


@dataclass(frozen=True)
class Target:
    tier: str
    project: str
    port: int | None
    bind: str
    overrides: tuple[str, ...]

    @property
    def env_file(self) -> Path:
        return STATE_DIR / f"{self.project}.env"


def slug(text: str) -> str:
    """A compose project name: lowercase letters, digits, hyphen and underscore."""
    return re.sub(r"[^a-z0-9_-]+", "-", text.lower()).strip("-_")[:40] or "stack"


def resolve_target(tier: str, project: str | None) -> Target:
    """The tier's defaults. `up` can pin another port or bind address (see ensure_env_file)."""
    if tier == "test":
        return Target("test", TEST_PROJECT, TEST_PORT, TEST_BIND, (TEST_OVERRIDE,))
    if tier == "production":
        name = slug(project) if project else PROD_PROJECT
        return Target("production", name, PROD_PORT, LOCAL_BIND, (PROD_OVERRIDE,))
    name = slug(project) if project else "lindra-" + slug(REPO.name)
    return Target("throwaway", name, None, LOCAL_BIND, ())


# ---------------------------------------------------------------- process and HTTP


def run(
    command: list[str], *, env: dict[str, str] | None = None, check: bool = True
) -> subprocess.CompletedProcess[str]:
    """The one place the script starts other programs (docker, systemd, itself)."""
    return subprocess.run(command, env=env, check=check, text=True)


def capture(command: list[str], cwd: Path = REPO) -> str:
    result = subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def http(method: str, url: str, token: str | None = None, timeout: float = 5.0) -> tuple[int, Any]:
    """Return the status and the JSON body; raise OSError when nothing answers."""
    request = urllib.request.Request(url, method=method, data=b"" if method == "POST" else None)
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read() or b"null")
    except urllib.error.HTTPError as error:
        try:
            body = json.loads(error.read() or b"null")
        except ValueError:
            body = None
        return error.code, body
    except urllib.error.URLError as error:
        raise ConnectionError(str(error.reason)) from error


def wait_for_health(url: str) -> bool:
    deadline = time.monotonic() + HEALTH_WAIT_SECONDS
    while time.monotonic() < deadline:
        try:
            if http("GET", f"{url}/health", timeout=2.0)[0] == 200:
                return True
        except OSError:
            pass
        time.sleep(1)
    return False


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind((LOCAL_BIND, 0))
        return probe.getsockname()[1]


def head_commit() -> str:
    commit = capture(["git", "rev-parse", "HEAD"])
    dirty = capture(["git", "status", "--porcelain", "--untracked-files=no"])
    return f"{commit}+dirty" if dirty else commit


# ---------------------------------------------------------------- env file


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def ensure_env_file(
    target: Target, port: int | None = None, bind: str | None = None
) -> dict[str, str]:
    """Create the private env file with a generated token when it is missing.

    An existing file keeps its token, port and bind address; `port` and `bind` (from
    `up --port` and `--bind`) replace the stored values when given.
    """
    stored = read_env(target.env_file)
    values = {
        "LINDRA_TOKEN": stored.get("LINDRA_TOKEN") or secrets.token_urlsafe(32),
        "LINDRA_PORT": str(port or stored.get("LINDRA_PORT") or target.port or free_port()),
        "LINDRA_BIND": format_bind(bind or stored.get("LINDRA_BIND") or target.bind),
        "LINDRA_TIER": target.tier,
    }
    if all(stored.get(key) == value for key, value in values.items()):
        return stored
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    body = "# Generated by scripts/env.py. Never commit this file.\n"
    body += "".join(f"{key}={value}\n" for key, value in values.items())
    descriptor = os.open(target.env_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(body)
    os.chmod(target.env_file, 0o600)
    return values


def local_endpoint(target: Target) -> tuple[str, str] | None:
    values = read_env(target.env_file)
    if not values.get("LINDRA_TOKEN") or not values.get("LINDRA_PORT"):
        return None
    return base_url(values), values["LINDRA_TOKEN"]


def format_bind(bind: str) -> str:
    """An IPv6 address needs brackets in a compose port mapping and in a URL."""
    return f"[{bind}]" if ":" in bind and not bind.startswith("[") else bind


def base_url(values: dict[str, str]) -> str:
    """The URL that reaches the stack: its bind address, or loopback for a wildcard bind.

    A stack bound to one address answers only there, so `127.0.0.1` would miss it.
    """
    bind = values.get("LINDRA_BIND") or LOCAL_BIND
    host = {"0.0.0.0": LOCAL_BIND, "[::]": "[::1]"}.get(bind, bind)
    return f"http://{host}:{values['LINDRA_PORT']}"


# ---------------------------------------------------------------- compose


def compose_command(target: Target, *arguments: str) -> list[str]:
    command = ["docker", "compose", "-p", target.project]
    if target.env_file.exists():
        command += ["--env-file", str(target.env_file)]
    for name in (COMPOSE_FILE, *target.overrides):
        command += ["-f", str(REPO / name)]
    return [*command, *arguments]


def compose(target: Target, *arguments: str, commit: str | None = None) -> None:
    environment = {**os.environ, "LINDRA_COMMIT": commit} if commit else None
    run(compose_command(target, *arguments), env=environment)


# ---------------------------------------------------------------- checks


def run_checks(url: str, token: str) -> list[tuple[str, bool, str]]:
    """Each check as (name, passed, detail). The token is never printed."""
    results: list[tuple[str, bool, str]] = []

    def record(name: str, passed: bool, detail: str) -> None:
        results.append((name, passed, detail))

    try:
        status, _ = http("GET", f"{url}/health")
        record("health", status == 200, f"HTTP {status}")
        authenticated_checks(url, token, record)
    except OSError as error:
        record("connection", False, f"no answer from {url}: {error}")
    return results


def authenticated_checks(url: str, token: str, record) -> None:
    status, _ = http("GET", f"{url}/api/session", token)
    record("session", status == 200, f"HTTP {status} with the token")
    if status != 200:
        return

    status, body = http("GET", f"{url}/api/environment", token)
    if status != 200 or not isinstance(body, dict):
        record("environment", False, f"HTTP {status}")
        return
    stand_ins = body.get("text_backend") == STAND_IN and body.get("speech_backend") == STAND_IN
    record(
        "stand-ins",
        stand_ins,
        f"text {body.get('text_backend')}, speech {body.get('speech_backend')}",
    )
    seed = body.get("seed") or {}
    record(
        "seed",
        bool(seed.get("ran")),
        f"hook ran, {seed.get('totals', {}).get('cases', 0)} cases, digest "
        f"{str(seed.get('digest', ''))[:12]}"
        if seed.get("ran")
        else "seed hook has not run; run `scripts/env.py reset`",
    )
    record("commit", True, f"{body.get('tier')} tier at {body.get('commit')}")


def deployed_commit() -> str | None:
    """The commit the running test stack reports, or None when it does not answer."""
    endpoint = local_endpoint(resolve_target("test", None))
    if endpoint is None:
        return None
    url, token = endpoint
    try:
        status, body = http("GET", f"{url}/api/environment", token)
    except OSError:
        return None
    return body.get("commit") if status == 200 and isinstance(body, dict) else None


# ---------------------------------------------------------------- commands


def cmd_up(args: argparse.Namespace) -> int:
    target = resolve_target(args.tier, args.project)
    values = ensure_env_file(target, args.port, args.bind)
    commit = head_commit()
    compose(target, "up", "-d", "--build", "--wait", "--remove-orphans", commit=commit)
    url = base_url(values)
    if not wait_for_health(url):
        print(f"up: the stack did not answer on {url}/health within {HEALTH_WAIT_SECONDS} s")
        return 1
    print(f"up: {target.project} runs {commit} on {url} (env file {target.env_file})")
    status, body = http("GET", f"{url}/api/environment", values["LINDRA_TOKEN"])
    if status != 200:
        print(f"up: the environment route answered HTTP {status}")
        return 1
    if body["seed"].get("ran"):
        print(f"up: seed hook already ran on this volume, digest {body['seed']['digest'][:12]}")
        return 0
    return seed_cast(url, values["LINDRA_TOKEN"], "seeded the fictional cast")


def seed_cast(url: str, token: str, verb: str) -> int:
    status, body = http("POST", f"{url}/api/seed", token, timeout=30.0)
    if status != 200:
        detail = body.get("detail") if isinstance(body, dict) else body
        print(f"reset: the seed hook answered HTTP {status}: {detail}")
        return 1
    totals = body["totals"]
    print(f"reset: {verb}, digest {body['digest'][:12]}")
    for case in body["cases"]:
        period = f"{case['period']['start']} to {case['period']['end']}"
        print(
            f"  {case['case_number']}  {case['patient_name']}  {period}  "
            f"visits {case['visits']}, backdated {case['backdated_visits']}, "
            f"clarification items {case['clarification_items']}, audio {case['audio']}"
        )
    print(
        f"  {totals['cases']} cases, {totals['encounters']} encounters, "
        f"{totals['changed_background']} with changed background; "
        "validated and reported, not stored until case storage exists"
    )
    return 0


def endpoint_for(args: argparse.Namespace) -> tuple[str, str] | None:
    """Where a command talks to: the node's test URL (`--remote`) or the local stack."""
    if getattr(args, "remote", False):
        url = os.environ.get(TEST_URL_VARIABLE, "").strip().rstrip("/")
        token = os.environ.get(TEST_TOKEN_VARIABLE, "").strip()
        if not url or not token:
            print(
                f"--remote needs {TEST_URL_VARIABLE} and {TEST_TOKEN_VARIABLE} in the node profile"
            )
            return None
        return url, token
    endpoint = local_endpoint(resolve_target(args.tier, args.project))
    if endpoint is None:
        print("no stack here: run `scripts/env.py up` first (there is no env file)")
    return endpoint


def cmd_check(args: argparse.Namespace) -> int:
    endpoint = endpoint_for(args)
    if endpoint is None:
        return 2
    url, token = endpoint
    failed = False
    for name, passed, detail in run_checks(url, token):
        print(f"{'ok  ' if passed else 'FAIL'} {name}: {detail}")
        failed = failed or not passed
    print("check: failed" if failed else f"check: passed against {url}")
    return 1 if failed else 0


def cmd_reset(args: argparse.Namespace) -> int:
    endpoint = endpoint_for(args)
    if endpoint is None:
        return 2
    url, token = endpoint
    try:
        return seed_cast(url, token, "ran the seed hook")
    except OSError as error:
        print(f"reset: no answer from {url}: {error}")
        return 1


def cmd_down(args: argparse.Namespace) -> int:
    target = resolve_target(args.tier, args.project)
    arguments = ["down", "--remove-orphans"]
    # Production keeps its volume unless the operator asks for --purge. The
    # other tiers hold only the fictional cast, so their volume goes with the stack.
    if target.tier != "production" or args.purge:
        arguments.append("--volumes")
    if target.tier == "throwaway":
        arguments += ["--rmi", "local"]
    compose(target, *arguments)
    # The test and production tokens stay so the published values keep working; a
    # throwaway stack leaves nothing behind for a later `up` to trip over.
    if target.tier == "throwaway" or args.purge:
        target.env_file.unlink(missing_ok=True)
    print(f"down: {target.project} removed")
    return 0


def git(repo: Path, *arguments: str) -> str:
    return capture(["git", *arguments], cwd=repo)


def ensure_test(repo: Path = REPO) -> int:
    """Redeploy the test tier when origin/main moved, then check it."""
    branch = git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    if branch not in ("HEAD", "main"):
        print(
            f"ensure-test: this checkout is on {branch}; run it only in the dedicated test checkout"
        )
        return 2
    if git(repo, "status", "--porcelain", "--untracked-files=no"):
        print("ensure-test: the test checkout has uncommitted changes; refusing to overwrite them")
        return 2
    git(repo, "fetch", "--quiet", "origin", "main")
    wanted = git(repo, "rev-parse", "origin/main")
    if deployed_commit() == wanted:
        print(f"ensure-test: {wanted[:12]} is deployed; nothing to do")
        return 0
    git(repo, "checkout", "--quiet", "--force", "--detach", wanted)
    script = str(repo / "scripts" / "env.py")
    # The new checkout's own script redeploys, so changes to this script apply at once.
    for command in ("up", "check"):
        result = run([sys.executable, script, command, "--tier", "test"], check=False)
        if result.returncode != 0:
            print(f"ensure-test: {command} failed for {wanted[:12]}")
            return 1
    print(f"ensure-test: deployed {wanted[:12]}")
    return 0


def render_units(python: str, repo: Path) -> tuple[str, str]:
    service = f"""[Unit]
Description=Refresh the Lindra test environment from origin/main

[Service]
Type=oneshot
WorkingDirectory={repo}
Environment=DOCKER_HOST=unix://%t/docker.sock
Environment=PATH=%h/bin:/usr/local/bin:/usr/bin:/bin
ExecStart={python} {repo}/scripts/env.py ensure-test
"""
    timer = f"""[Unit]
Description=Run ensure-test for the Lindra test environment every 5 minutes

[Timer]
OnActiveSec=30s
OnBootSec=1min
OnUnitActiveSec=5min
Unit={SERVICE_NAME}

[Install]
WantedBy=timers.target
"""
    return service, timer


def write_if_changed(path: Path, text: str) -> None:
    if not path.exists() or path.read_text(encoding="utf-8") != text:
        path.write_text(text, encoding="utf-8")


def cmd_install_timer(args: argparse.Namespace) -> int:
    service, timer = render_units(sys.executable, REPO)
    if args.unit_dir:
        unit_dir = Path(args.unit_dir)
    elif args.dry_run:
        unit_dir = Path(tempfile.mkdtemp(prefix="lindra-units-"))
    else:
        unit_dir = USER_UNIT_DIR
    unit_dir.mkdir(parents=True, exist_ok=True)
    service_path, timer_path = unit_dir / SERVICE_NAME, unit_dir / TIMER_NAME
    write_if_changed(service_path, service)
    write_if_changed(timer_path, timer)
    print(f"install-timer: units written to {unit_dir}")
    if args.dry_run:
        print(f"--- {SERVICE_NAME}\n{service}--- {TIMER_NAME}\n{timer}---")
        run(["systemd-analyze", "--user", "verify", str(service_path), str(timer_path)])
        print("install-timer: units verified; dry run, nothing installed or started")
        return 0
    run(["systemctl", "--user", "daemon-reload"])
    run(["systemctl", "--user", "enable", "--now", TIMER_NAME])
    print(f"install-timer: {TIMER_NAME} is enabled and started")
    return 0


# ---------------------------------------------------------------- command line


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], prog="env.py")
    commands = parser.add_subparsers(dest="command", required=True)

    def add(name: str, help_text: str, *, stack: bool = True) -> argparse.ArgumentParser:
        sub = commands.add_parser(name, help=help_text)
        if stack:
            sub.add_argument(
                "--tier",
                choices=("throwaway", "test", "production"),
                default="throwaway",
                help="throwaway (default), test (project lindra-test, port 8780) or "
                "production (the operator's runbook, project lindra-prod)",
            )
            sub.add_argument(
                "--project",
                help="compose project of a throwaway stack; default lindra-<checkout directory>",
            )
        return sub

    up = add("up", "build and start the stack, then seed the cast on a fresh volume")
    up.add_argument("--port", type=int, help="host port; stored in the env file")
    up.add_argument("--bind", help="host address to listen on; stored in the env file")
    check = add("check", "check health, an authenticated route, the stand-ins and the seed hook")
    check.add_argument(
        "--remote",
        action="store_true",
        help=f"check the test tier through {TEST_URL_VARIABLE} and {TEST_TOKEN_VARIABLE}",
    )
    reset = add("reset", "run the seed hook: the fictional cast and nothing else")
    reset.add_argument("--remote", action="store_true", help=argparse.SUPPRESS)
    down = add("down", "remove the stack and its volume")
    down.add_argument(
        "--purge", action="store_true", help="also delete the env file and a production volume"
    )
    add("ensure-test", "redeploy the test tier when origin/main moved", stack=False)
    timer = add("install-timer", "install the user timer that runs ensure-test", stack=False)
    timer.add_argument("--dry-run", action="store_true", help="write and verify the units only")
    timer.add_argument("--unit-dir", help="write the units here instead of ~/.config/systemd/user")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    handlers = {
        "up": cmd_up,
        "check": cmd_check,
        "reset": cmd_reset,
        "down": cmd_down,
        "ensure-test": lambda _: ensure_test(),
        "install-timer": cmd_install_timer,
    }
    try:
        return handlers[args.command](args)
    except subprocess.CalledProcessError as error:
        print(f"{args.command}: `{' '.join(map(str, error.cmd))}` exited with {error.returncode}")
        return 1
    except OSError as error:
        print(f"{args.command}: {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

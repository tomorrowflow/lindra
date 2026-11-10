"""`scripts/env.py`: what a developer or the timer sees (ADR 0007).

Docker and systemd are stubbed at the one `run` seam; HTTP goes to the real
application through a test client, so `check` and `reset` exercise the real
routes. The throwaway stack on the developer's node is the end-to-end proof.
"""

import importlib.util
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lindra.app import create_app
from lindra.config import Settings
from tests.conftest import TOKEN

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "env.py"


@pytest.fixture
def env(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("lindra_env_script", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "STATE_DIR", tmp_path / "state")
    return module


class Stack:
    """Stands in for docker compose and the running service."""

    def __init__(self, env, data_dir, tier="throwaway"):
        self.env = env
        self.commands = []
        self.up = False
        self.tier = tier
        self.data_dir = data_dir
        self.commit = "unknown"
        self.token = TOKEN

    def run(self, command, *, env=None, check=True):
        self.commands.append(command)
        if command[:2] == ["docker", "compose"]:
            if "up" in command:
                self.up = True
                self.commit = (env or {}).get("LINDRA_COMMIT", "unknown")
                # The service starts with the token from the env file compose is given.
                env_file = Path(command[command.index("--env-file") + 1])
                self.token = self.env.read_env(env_file)["LINDRA_TOKEN"]
            if "down" in command:
                self.up = False
        return subprocess.CompletedProcess(command, 0, "", "")

    def http(self, method, url, token=None, timeout=5.0):
        if not self.up:
            raise ConnectionError("connection refused")
        settings = Settings(
            token=self.token, data_dir=self.data_dir, commit=self.commit, tier=self.tier
        )
        client = TestClient(create_app(settings))
        path = url.split("/", 3)[3] if url.count("/") >= 3 else ""
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        response = client.request(method, "/" + path, headers=headers)
        return response.status_code, response.json()


@pytest.fixture
def stack(env, tmp_path, monkeypatch):
    fake = Stack(env, tmp_path / "data")
    monkeypatch.setattr(env, "run", fake.run)
    monkeypatch.setattr(env, "http", fake.http)
    monkeypatch.setattr(env, "head_commit", lambda: "abc123")
    monkeypatch.setattr(env, "free_port", lambda: 40123)
    monkeypatch.setattr(env, "wait_for_health", lambda url: True)
    return fake


def run_main(env, *argv):
    return env.main(list(argv))


def test_script_is_executable_python():
    assert os.access(SCRIPT, os.X_OK)
    assert SCRIPT.read_text().startswith("#!/usr/bin/env python3")
    assert stat.S_IMODE(SCRIPT.stat().st_mode) & stat.S_IXUSR


def test_every_command_exists(env):
    parser = env.build_parser()
    for name in ("up", "check", "reset", "down", "ensure-test", "install-timer"):
        assert parser.parse_args([name]).command == name


def test_test_tier_uses_the_lindra_test_project_on_port_8780(env):
    target = env.resolve_target(tier="test", project=None)

    assert target.project == "lindra-test"
    assert target.port == 8780
    assert target.overrides == ("compose.test.yaml",)


def test_throwaway_project_is_specific_to_the_checkout(env):
    default = env.resolve_target(tier="throwaway", project=None)
    named = env.resolve_target(tier="throwaway", project="Lindra LFR-02!")

    assert default.project.startswith("lindra-")
    assert default.project != "lindra-test"
    assert named.project == "lindra-lfr-02"
    assert default.overrides == ()


def test_up_writes_a_private_env_file_with_a_generated_token(env, stack):
    assert run_main(env, "up", "--project", "lindra-lfr-02") == 0

    path = env.STATE_DIR / "lindra-lfr-02.env"
    values = env.read_env(path)
    assert len(values["LINDRA_TOKEN"]) >= 32
    assert values["LINDRA_PORT"] == "40123"
    assert values["LINDRA_TIER"] == "throwaway"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_env_file_location_is_gitignored(env):
    repo = SCRIPT.parent.parent
    probe = repo / ".lindra-env" / "lindra-lfr-02.env"

    ignored = subprocess.run(["git", "check-ignore", "-q", str(probe)], cwd=repo)

    assert ignored.returncode == 0


def test_up_twice_converges_to_the_same_state(env, stack):
    run_main(env, "up", "--project", "p")
    first = (env.STATE_DIR / "p.env").read_text()
    commands_once = len(stack.commands)

    assert run_main(env, "up", "--project", "p") == 0

    assert (env.STATE_DIR / "p.env").read_text() == first
    assert stack.commands[commands_once:] == stack.commands[:commands_once]


def test_up_seeds_a_fresh_volume_and_does_not_reseed_a_seeded_one(env, stack, capsys):
    run_main(env, "up", "--project", "p")
    first = capsys.readouterr().out
    run_main(env, "up", "--project", "p")
    second = capsys.readouterr().out

    assert "seeded" in first
    assert "seeded" not in second


def test_up_runs_the_stand_ins_only(env, stack):
    compose = (SCRIPT.parent.parent / "compose.yaml").read_text()

    assert "LINDRA_TEXT_BACKEND: fixture" in compose
    assert "LINDRA_SPEECH_BACKEND: fixture" in compose
    assert "${LINDRA_TEXT_BACKEND" not in compose
    assert "${LINDRA_SPEECH_BACKEND" not in compose


def test_up_passes_the_commit_and_the_project_to_compose(env, stack):
    run_main(env, "up", "--project", "p")

    compose = next(c for c in stack.commands if "up" in c)
    assert compose[:4] == ["docker", "compose", "-p", "p"]
    assert stack.commit == "abc123"
    assert any(part.endswith("compose.yaml") for part in compose)
    assert not any(part.endswith("compose.test.yaml") for part in compose)


def test_up_on_the_test_tier_adds_the_override(env, stack):
    run_main(env, "up", "--tier", "test")

    compose = next(c for c in stack.commands if "up" in c)
    assert any(part.endswith("compose.test.yaml") for part in compose)
    values = env.read_env(env.STATE_DIR / "lindra-test.env")
    assert values["LINDRA_PORT"] == "8780"
    assert values["LINDRA_BIND"] == "0.0.0.0"


def test_check_passes_after_up_and_fails_while_the_stack_is_down(env, stack, capsys):
    run_main(env, "up", "--project", "p")

    assert run_main(env, "check", "--project", "p") == 0
    assert "health" in capsys.readouterr().out

    stack.up = False
    assert run_main(env, "check", "--project", "p") == 1


def test_check_fails_cleanly_when_the_connection_drops_after_health(
    env, stack, monkeypatch, capsys
):
    run_main(env, "up", "--project", "p")
    real = stack.http

    def dropping(method, url, token=None, timeout=5.0):
        if url.endswith("/api/session"):
            raise ConnectionResetError("reset by peer")
        return real(method, url, token, timeout)

    monkeypatch.setattr(env, "http", dropping)

    assert run_main(env, "check", "--project", "p") == 1
    assert "FAIL connection" in capsys.readouterr().out


def test_check_fails_when_the_token_is_refused(env, stack, capsys):
    run_main(env, "up", "--project", "p")
    path = env.STATE_DIR / "p.env"
    path.write_text(path.read_text().replace("LINDRA_TOKEN=", "LINDRA_TOKEN=wrong"))

    assert run_main(env, "check", "--project", "p") == 1
    assert "401" in capsys.readouterr().out


def test_check_fails_when_the_seed_hook_has_not_run(env, stack, capsys):
    run_main(env, "up", "--project", "p")
    (stack.data_dir / "seed-report.json").unlink()

    assert run_main(env, "check", "--project", "p") == 1
    assert "seed" in capsys.readouterr().out


def test_check_without_a_stack_says_to_run_up(env, stack, capsys):
    assert run_main(env, "check", "--project", "never-started") == 2
    assert "up" in capsys.readouterr().out


def test_remote_check_reads_the_test_url_and_token_from_the_node(env, stack, monkeypatch, capsys):
    run_main(env, "up", "--project", "p")
    monkeypatch.setenv("LINDRA_TEST_URL", "http://lindra-test.example:8780")
    monkeypatch.setenv("LINDRA_TEST_TOKEN", stack.token)
    seen = []
    real = stack.http

    def recording(method, url, token=None, timeout=5.0):
        seen.append((url, token))
        return real(method, url, token, timeout)

    monkeypatch.setattr(env, "http", recording)

    assert run_main(env, "check", "--remote") == 0
    assert seen[0][0].startswith("http://lindra-test.example:8780")
    assert all(token in (None, stack.token) for _, token in seen)
    assert stack.token not in capsys.readouterr().out


def test_remote_check_needs_both_variables(env, stack, monkeypatch, capsys):
    monkeypatch.delenv("LINDRA_TEST_URL", raising=False)
    monkeypatch.delenv("LINDRA_TEST_TOKEN", raising=False)

    assert run_main(env, "check", "--remote") == 2
    out = capsys.readouterr().out
    assert "LINDRA_TEST_URL" in out and "LINDRA_TEST_TOKEN" in out


def test_reset_seeds_the_cast_and_reports_it(env, stack, capsys):
    run_main(env, "up", "--project", "p")
    capsys.readouterr()

    assert run_main(env, "reset", "--project", "p") == 0

    out = capsys.readouterr().out
    assert "FIK-2026-001" in out and "FIK-2026-002" in out and "FIK-2026-003" in out
    assert "not stored" in out


def test_reset_twice_converges_to_the_same_state(env, stack, capsys):
    run_main(env, "up", "--project", "p")
    capsys.readouterr()
    run_main(env, "reset", "--project", "p")
    first = capsys.readouterr().out
    run_main(env, "reset", "--project", "p")
    second = capsys.readouterr().out

    assert first == second


def test_reset_fails_while_the_stack_is_down(env, stack):
    run_main(env, "up", "--project", "p")
    stack.up = False

    assert run_main(env, "reset", "--project", "p") == 1


def test_down_removes_the_stack_and_the_throwaway_env_file(env, stack):
    run_main(env, "up", "--project", "p")

    assert run_main(env, "down", "--project", "p") == 0

    command = next(c for c in stack.commands if "down" in c)
    assert "--volumes" in command
    assert not (env.STATE_DIR / "p.env").exists()


def test_down_twice_converges(env, stack):
    run_main(env, "up", "--project", "p")
    run_main(env, "down", "--project", "p")

    assert run_main(env, "down", "--project", "p") == 0


def test_second_up_after_down_starts_clean(env, stack, capsys):
    run_main(env, "up", "--project", "p")
    run_main(env, "down", "--project", "p")
    stack.data_dir.joinpath("seed-report.json").unlink()
    capsys.readouterr()

    assert run_main(env, "up", "--project", "p") == 0
    assert run_main(env, "check", "--project", "p") == 0


def test_down_keeps_the_test_token_unless_purged(env, stack):
    run_main(env, "up", "--tier", "test")
    run_main(env, "down", "--tier", "test")
    assert (env.STATE_DIR / "lindra-test.env").exists()

    run_main(env, "down", "--tier", "test", "--purge")
    assert not (env.STATE_DIR / "lindra-test.env").exists()


def test_production_tier_has_its_own_project_and_override(env):
    target = env.resolve_target(tier="production", project=None)

    assert target.project == "lindra-prod"
    assert target.port == 8790
    assert target.bind == "127.0.0.1"
    assert target.overrides == ("compose.prod.yaml",)


def test_up_pins_a_port_and_bind_address_and_keeps_the_token(env, stack):
    run_main(env, "up", "--tier", "production")
    token = env.read_env(env.STATE_DIR / "lindra-prod.env")["LINDRA_TOKEN"]

    run_main(env, "up", "--tier", "production", "--port", "9001", "--bind", "10.0.0.5")
    pinned = env.read_env(env.STATE_DIR / "lindra-prod.env")
    run_main(env, "up", "--tier", "production")

    assert pinned["LINDRA_TOKEN"] == token
    assert pinned["LINDRA_PORT"] == "9001"
    assert pinned["LINDRA_BIND"] == "10.0.0.5"
    assert pinned["LINDRA_TIER"] == "production"
    assert env.read_env(env.STATE_DIR / "lindra-prod.env") == pinned


@pytest.mark.parametrize(
    ("bind", "host"),
    [
        ("10.0.0.5", "10.0.0.5"),
        ("127.0.0.1", "127.0.0.1"),
        ("0.0.0.0", "127.0.0.1"),
        ("::", "[::1]"),
        ("fd00::5", "[fd00::5]"),
    ],
)
def test_commands_reach_the_stack_on_the_address_it_is_bound_to(
    env, stack, monkeypatch, capsys, bind, host
):
    urls = []
    real = stack.http

    def recording(method, url, token=None, timeout=5.0):
        urls.append(url)
        return real(method, url, token, timeout)

    monkeypatch.setattr(env, "http", recording)
    waited = []
    monkeypatch.setattr(env, "wait_for_health", lambda url: waited.append(url) or True)

    assert run_main(env, "up", "--tier", "production", "--port", "9001", "--bind", bind) == 0
    assert run_main(env, "check", "--tier", "production") == 0
    assert run_main(env, "reset", "--tier", "production") == 0

    assert waited == [f"http://{host}:9001"]
    assert urls
    assert all(url.startswith(f"http://{host}:9001/") for url in urls)
    assert "up: lindra-prod runs" in capsys.readouterr().out


def test_down_keeps_the_production_volume_unless_purged(env, stack):
    run_main(env, "up", "--tier", "production")

    run_main(env, "down", "--tier", "production")
    kept = next(c for c in stack.commands if "down" in c)
    run_main(env, "down", "--tier", "production", "--purge")
    purged = [c for c in stack.commands if "down" in c][-1]

    assert "--volumes" not in kept
    assert "--volumes" in purged


def test_timer_units_run_ensure_test_every_five_minutes(env):
    service, timer = env.render_units(
        python="/usr/bin/python3", repo=Path("/srv/lindra-test/lindra")
    )

    assert (
        "ExecStart=/usr/bin/python3 /srv/lindra-test/lindra/scripts/env.py ensure-test" in service
    )
    assert "Type=oneshot" in service
    assert "OnUnitActiveSec=5min" in timer
    assert "Unit=lindra-test-env.service" in timer
    assert "WantedBy=timers.target" in timer


def test_install_timer_dry_run_writes_and_verifies_the_units(env, stack, tmp_path, capsys):
    target = tmp_path / "units"

    assert run_main(env, "install-timer", "--dry-run", "--unit-dir", str(target)) == 0

    assert (target / "lindra-test-env.service").exists()
    assert (target / "lindra-test-env.timer").exists()
    verify = next(c for c in stack.commands if "verify" in c)
    assert verify[:3] == ["systemd-analyze", "--user", "verify"]
    assert not any("enable" in c for c in stack.commands)
    assert "nothing installed" in capsys.readouterr().out


def test_install_timer_enables_and_starts_the_timer(env, stack, tmp_path):
    target = tmp_path / "units"

    assert run_main(env, "install-timer", "--unit-dir", str(target)) == 0
    assert run_main(env, "install-timer", "--unit-dir", str(target)) == 0

    enable = [c for c in stack.commands if "enable" in c]
    assert enable[0] == ["systemctl", "--user", "enable", "--now", "lindra-test-env.timer"]
    assert len(enable) == 2
    assert (target / "lindra-test-env.timer").exists()


def git(cwd, *args):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def checkout(tmp_path):
    origin = tmp_path / "origin"
    origin.mkdir()
    git(origin, "init", "-q", "-b", "main")
    git(origin, "config", "user.email", "t@example.test")
    git(origin, "config", "user.name", "t")
    (origin / "a.txt").write_text("1")
    git(origin, "add", ".")
    git(origin, "commit", "-q", "-m", "one")
    clone = tmp_path / "clone"
    git(tmp_path, "clone", "-q", str(origin), str(clone))
    return origin, clone


def advance(origin):
    (origin / "a.txt").write_text(str(len(git(origin, "log", "--oneline"))))
    git(origin, "commit", "-q", "-am", "next")
    return git(origin, "rev-parse", "HEAD")


def test_ensure_test_does_nothing_when_the_deployed_commit_is_current(
    env, stack, checkout, monkeypatch
):
    origin, clone = checkout
    monkeypatch.setattr(env, "deployed_commit", lambda: git(origin, "rev-parse", "HEAD"))

    assert env.ensure_test(clone) == 0
    assert stack.commands == []


def test_ensure_test_redeploys_a_new_origin_main_and_runs_check(env, stack, checkout, monkeypatch):
    origin, clone = checkout
    monkeypatch.setattr(env, "deployed_commit", lambda: "old")
    newest = advance(origin)

    assert env.ensure_test(clone) == 0

    assert git(clone, "rev-parse", "HEAD") == newest
    flat = [" ".join(map(str, c)) for c in stack.commands]
    assert any(line.endswith("env.py up --tier test") for line in flat)
    assert any(line.endswith("env.py check --tier test") for line in flat)
    assert flat.index(next(x for x in flat if x.endswith("up --tier test"))) < flat.index(
        next(x for x in flat if x.endswith("check --tier test"))
    ), "check runs after the redeploy"


def test_ensure_test_redeploys_when_nothing_is_deployed(env, stack, checkout, monkeypatch):
    _, clone = checkout
    monkeypatch.setattr(env, "deployed_commit", lambda: None)

    assert env.ensure_test(clone) == 0
    assert any(" up --tier test" in " ".join(map(str, c)) for c in stack.commands)


def test_ensure_test_refuses_a_checkout_on_a_feature_branch(env, stack, checkout, capsys):
    _, clone = checkout
    git(clone, "checkout", "-q", "-b", "feature")

    assert env.ensure_test(clone) == 2
    assert "dedicated" in capsys.readouterr().out
    assert stack.commands == []


def test_ensure_test_refuses_a_dirty_checkout(env, stack, checkout, capsys):
    _, clone = checkout
    (clone / "a.txt").write_text("edited")

    assert env.ensure_test(clone) == 2
    assert "uncommitted" in capsys.readouterr().out

"""The time zone setting: "now" for a new visit is the physician's wall clock."""

import pytest

from lindra.config import Settings, UnknownTimezone


def settings(monkeypatch, tmp_path, **env):
    monkeypatch.setenv("LINDRA_TOKEN", "t")
    monkeypatch.delenv("LINDRA_TIMEZONE", raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return Settings.from_env(tmp_path / "no-env-file")


def test_the_clock_runs_in_berlin_unless_told_otherwise(monkeypatch, tmp_path):
    assert settings(monkeypatch, tmp_path).timezone == "Europe/Berlin"


def test_the_time_zone_can_be_set(monkeypatch, tmp_path):
    chosen = settings(monkeypatch, tmp_path, LINDRA_TIMEZONE="Europe/Vienna")

    assert chosen.timezone == "Europe/Vienna"


def test_an_unknown_time_zone_stops_the_service_at_start(monkeypatch, tmp_path):
    with pytest.raises(UnknownTimezone, match="Mars/Olympus"):
        settings(monkeypatch, tmp_path, LINDRA_TIMEZONE="Mars/Olympus")

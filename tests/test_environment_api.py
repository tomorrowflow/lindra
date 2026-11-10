"""What the environment script sees: the environment report and the seed hook.

`scripts/env.py check` reads `/api/environment`; `scripts/env.py reset` calls
`POST /api/seed`. The hook validates the fictional cast, stores its cases (the case
tests are in `tests/test_cases_api.py`) and reports it.
"""

import pytest
from fastapi.testclient import TestClient

from lindra import cast
from lindra.app import create_app
from lindra.config import MissingToken, Settings, UnsupportedBackend
from tests.conftest import TOKEN


def test_environment_report_needs_the_token(anonymous):
    assert anonymous.get("/api/environment").status_code == 401


def test_environment_names_the_stand_ins_and_the_commit(api_client):
    body = api_client.get("/api/environment").json()

    assert body["text_backend"] == "fixture"
    assert body["speech_backend"] == "fixture"
    assert body["commit"] == "unknown"
    assert body["tier"] == "development"


def test_environment_reports_the_commit_and_tier_it_was_started_with(tmp_path):
    settings = Settings(token=TOKEN, data_dir=tmp_path, commit="abc1234", tier="throwaway")
    client = TestClient(create_app(settings), headers={"Authorization": f"Bearer {TOKEN}"})

    body = client.get("/api/environment").json()

    assert body["commit"] == "abc1234"
    assert body["tier"] == "throwaway"


def test_seed_has_not_run_on_a_fresh_volume(api_client):
    body = api_client.get("/api/environment").json()

    assert body["seed"] == {"ran": False}


def test_seed_needs_the_token(anonymous):
    assert anonymous.post("/api/seed").status_code == 401


def test_seed_stores_the_three_cases_and_reports_them(api_client):
    response = api_client.post("/api/seed")

    assert response.status_code == 200
    report = response.json()
    assert report["ran"] is True
    assert report["stored"] is True
    assert [c["case_number"] for c in report["cases"]] == [
        case.case_number for case in cast.load_cast().cases
    ]
    for case in report["cases"]:
        assert case["patient_name"]
        assert case["period"]["start"] <= case["period"]["end"]
        assert case["visits"] >= 1
        assert case["audio"] >= 1
    assert report["totals"]["cases"] == 3
    assert report["totals"]["backdated_visits"] >= 1
    assert report["totals"]["changed_background"] == 1


def test_seed_twice_converges_to_the_same_report(api_client):
    first = api_client.post("/api/seed").json()
    second = api_client.post("/api/seed").json()

    assert first == second


def test_environment_confirms_the_hook_ran(api_client):
    seeded = api_client.post("/api/seed").json()

    assert api_client.get("/api/environment").json()["seed"] == seeded


def test_seed_report_survives_a_restart_on_the_same_volume(tmp_path):
    headers = {"Authorization": f"Bearer {TOKEN}"}
    first = TestClient(create_app(Settings(token=TOKEN, data_dir=tmp_path)), headers=headers)
    seeded = first.post("/api/seed").json()

    restarted = TestClient(create_app(Settings(token=TOKEN, data_dir=tmp_path)), headers=headers)

    assert restarted.get("/api/environment").json()["seed"] == seeded


def test_a_seed_report_of_an_older_cast_counts_as_not_run(tmp_path):
    headers = {"Authorization": f"Bearer {TOKEN}"}
    client = TestClient(create_app(Settings(token=TOKEN, data_dir=tmp_path)), headers=headers)
    client.post("/api/seed")
    report = tmp_path / "seed-report.json"
    report.write_text(report.read_text().replace('"digest": "', '"digest": "old'))

    assert client.get("/api/environment").json()["seed"] == {"ran": False}
    assert client.post("/api/seed").status_code == 200
    assert client.get("/api/environment").json()["seed"]["ran"] is True


def test_seed_hook_refuses_a_broken_cast(tmp_path, monkeypatch):
    import dataclasses

    from lindra import seed

    real = cast.load_cast()
    monkeypatch.setattr(seed.cast, "load_cast", lambda: dataclasses.replace(real, cases=()))
    client = TestClient(
        create_app(Settings(token=TOKEN, data_dir=tmp_path)),
        headers={"Authorization": f"Bearer {TOKEN}"},
    )

    response = client.post("/api/seed")

    assert response.status_code == 500
    assert "three cases" in response.json()["detail"]
    assert client.get("/api/environment").json()["seed"] == {"ran": False}


@pytest.mark.parametrize("name", ["LINDRA_TEXT_BACKEND", "LINDRA_SPEECH_BACKEND"])
@pytest.mark.parametrize("value", ["ollama", "hosted", "whisper"])
def test_no_configuration_enables_a_real_or_hosted_backend(name, value, tmp_path, monkeypatch):
    monkeypatch.setenv("LINDRA_TOKEN", TOKEN)
    monkeypatch.setenv(name, value)

    with pytest.raises(UnsupportedBackend):
        Settings.from_env(tmp_path / "missing.env")


def test_an_empty_backend_setting_keeps_the_stand_in(tmp_path, monkeypatch):
    monkeypatch.setenv("LINDRA_TOKEN", TOKEN)
    monkeypatch.setenv("LINDRA_TEXT_BACKEND", "")

    assert Settings.from_env(tmp_path / "missing.env").text_backend == "fixture"


def test_settings_default_to_the_stand_ins(tmp_path, monkeypatch):
    monkeypatch.setenv("LINDRA_TOKEN", TOKEN)
    monkeypatch.delenv("LINDRA_TEXT_BACKEND", raising=False)
    monkeypatch.delenv("LINDRA_SPEECH_BACKEND", raising=False)

    settings = Settings.from_env(tmp_path / "missing.env")

    assert settings.text_backend == "fixture"
    assert settings.speech_backend == "fixture"


def test_settings_still_require_a_token(tmp_path, monkeypatch):
    monkeypatch.delenv("LINDRA_TOKEN", raising=False)

    with pytest.raises(MissingToken):
        Settings.from_env(tmp_path / "missing.env")

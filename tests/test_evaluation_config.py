"""The evaluation configuration: where the real backends may run (ADR 0003, ADR 0007).

The self-hosted and the hosted backends start only in the explicitly launched evaluation
configuration, and only the fictional cast may be in its database. These tests use no real
model: the guards are checked at start, before any adapter is called.
"""

import pytest
from fastapi.testclient import TestClient

from lindra import cast
from lindra.app import create_app
from lindra.config import (
    HostedKeyMissing,
    IncompleteBackend,
    OutsideEvaluation,
    Settings,
    UnsupportedBackend,
)
from lindra.evaluation import NonFictionalData
from lindra.store import DATABASE_FILE, Store
from tests.conftest import TOKEN

SELF_HOSTED_TEXT = {
    "LINDRA_TEXT_BACKEND": "selfhosted",
    "LINDRA_TEXT_MODEL": "some-model:1b",
}
HOSTED_TEXT = {
    "LINDRA_TEXT_BACKEND": "hosted",
    "LINDRA_HOSTED_URL": "https://inference.example.invalid",
    "LINDRA_HOSTED_MODEL": "some-model:1b",
    "LINDRA_HOSTED_KEY": "key-for-the-test-only",
}
SELF_HOSTED_SPEECH = {"LINDRA_SPEECH_BACKEND": "selfhosted"}


def settings(monkeypatch, tmp_path, **env):
    for name in (
        "LINDRA_TIER",
        "LINDRA_TEXT_BACKEND",
        "LINDRA_SPEECH_BACKEND",
        "LINDRA_TEXT_MODEL",
        "LINDRA_HOSTED_URL",
        "LINDRA_HOSTED_MODEL",
        "LINDRA_HOSTED_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("LINDRA_TOKEN", TOKEN)
    monkeypatch.setenv("LINDRA_DATA_DIR", str(tmp_path))
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return Settings.from_env(tmp_path / "no-env-file")


@pytest.mark.parametrize("tier", ["", "development", "throwaway", "test", "production", "preview"])
@pytest.mark.parametrize("real", [SELF_HOSTED_TEXT, HOSTED_TEXT, SELF_HOSTED_SPEECH])
def test_no_tier_but_the_evaluation_runs_a_real_backend(monkeypatch, tmp_path, tier, real):
    with pytest.raises(OutsideEvaluation, match="evaluation configuration"):
        settings(monkeypatch, tmp_path, LINDRA_TIER=tier, **real)


def test_the_hosted_adapter_refuses_to_start_outside_the_evaluation_configuration(
    monkeypatch, tmp_path
):
    with pytest.raises(OutsideEvaluation) as refused:
        settings(monkeypatch, tmp_path, LINDRA_TIER="test", **HOSTED_TEXT)

    assert "hosted" in str(refused.value)
    assert "LINDRA_TIER=evaluation" in str(refused.value)
    assert "key-for-the-test-only" not in str(refused.value)


def test_settings_built_directly_obey_the_same_rule(tmp_path):
    with pytest.raises(OutsideEvaluation):
        Settings(
            token=TOKEN,
            data_dir=tmp_path,
            tier="production",
            text_backend="hosted",
            hosted_url="https://inference.example.invalid",
            hosted_model="m",
            hosted_key="k",
        )


def test_the_evaluation_configuration_runs_the_self_hosted_backends(monkeypatch, tmp_path):
    chosen = settings(
        monkeypatch,
        tmp_path,
        LINDRA_TIER="evaluation",
        **SELF_HOSTED_TEXT,
        **SELF_HOSTED_SPEECH,
    )

    assert chosen.evaluation
    assert chosen.text_backend == "selfhosted"
    assert chosen.speech_backend == "selfhosted"


def test_the_evaluation_configuration_runs_the_hosted_comparison(monkeypatch, tmp_path):
    chosen = settings(monkeypatch, tmp_path, LINDRA_TIER="evaluation", **HOSTED_TEXT)

    assert chosen.text_backend == "hosted"
    assert chosen.speech_backend == "fixture"


def test_speech_recognition_stays_self_hosted_in_every_configuration(monkeypatch, tmp_path):
    with pytest.raises(UnsupportedBackend):
        settings(monkeypatch, tmp_path, LINDRA_TIER="evaluation", LINDRA_SPEECH_BACKEND="hosted")


def test_the_hosted_comparison_needs_the_operators_key(monkeypatch, tmp_path):
    env = {name: value for name, value in HOSTED_TEXT.items() if name != "LINDRA_HOSTED_KEY"}

    with pytest.raises(HostedKeyMissing, match="LINDRA_HOSTED_KEY"):
        settings(monkeypatch, tmp_path, LINDRA_TIER="evaluation", **env)


def test_the_key_never_comes_from_the_env_file(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("LINDRA_HOSTED_KEY=key-from-a-file\n", encoding="utf-8")
    monkeypatch.delenv("LINDRA_HOSTED_KEY", raising=False)
    monkeypatch.setenv("LINDRA_TOKEN", TOKEN)
    monkeypatch.setenv("LINDRA_TIER", "evaluation")
    monkeypatch.setenv("LINDRA_TEXT_BACKEND", "hosted")
    monkeypatch.setenv("LINDRA_HOSTED_URL", "https://inference.example.invalid")
    monkeypatch.setenv("LINDRA_HOSTED_MODEL", "m")

    with pytest.raises(HostedKeyMissing):
        Settings.from_env(env_file)


def test_the_key_does_not_appear_in_the_settings_text(monkeypatch, tmp_path):
    chosen = settings(monkeypatch, tmp_path, LINDRA_TIER="evaluation", **HOSTED_TEXT)

    assert "key-for-the-test-only" not in repr(chosen)


def test_a_self_hosted_text_backend_needs_a_model(monkeypatch, tmp_path):
    with pytest.raises(IncompleteBackend, match="LINDRA_TEXT_MODEL"):
        settings(
            monkeypatch,
            tmp_path,
            LINDRA_TIER="evaluation",
            LINDRA_TEXT_BACKEND="selfhosted",
        )


def test_the_hosted_comparison_needs_its_address_and_model(monkeypatch, tmp_path):
    env = {name: value for name, value in HOSTED_TEXT.items() if name not in ("LINDRA_HOSTED_URL",)}

    with pytest.raises(IncompleteBackend, match="LINDRA_HOSTED_URL"):
        settings(monkeypatch, tmp_path, LINDRA_TIER="evaluation", **env)


def test_the_stand_ins_run_in_the_evaluation_configuration_too(monkeypatch, tmp_path):
    chosen = settings(monkeypatch, tmp_path, LINDRA_TIER="evaluation")

    assert chosen.text_backend == "fixture"
    assert chosen.speech_backend == "fixture"


# ---- the database may hold only the fictional cast ----


def evaluation_settings(tmp_path):
    return Settings(token=TOKEN, data_dir=tmp_path, tier="evaluation")


def store_case(tmp_path, case_number, patient_name):
    store = Store(tmp_path / DATABASE_FILE)
    with store.write() as tx:
        tx.add_case(case_number, patient_name, "", *_period())


def _period():
    first = cast.load_cast().cases[0]
    return first.period_start, first.period_end


def test_the_evaluation_configuration_starts_on_an_empty_database(tmp_path):
    client = TestClient(
        create_app(evaluation_settings(tmp_path)), headers={"Authorization": f"Bearer {TOKEN}"}
    )

    assert client.get("/api/environment").json()["evaluation"] is True


def test_the_evaluation_configuration_starts_on_the_fictional_cast(tmp_path):
    first = cast.load_cast().cases[0]
    store_case(tmp_path, first.case_number, first.patient_name)

    client = TestClient(
        create_app(evaluation_settings(tmp_path)), headers={"Authorization": f"Bearer {TOKEN}"}
    )

    assert client.get("/api/environment").json()["evaluation"] is True


def test_the_evaluation_configuration_refuses_a_database_with_another_case(tmp_path):
    first = cast.load_cast().cases[0]
    store_case(tmp_path, first.case_number, first.patient_name)
    store_case(tmp_path, "K-4711", "Erika Beispiel")

    with pytest.raises(NonFictionalData) as refused:
        create_app(evaluation_settings(tmp_path))

    # The message names the case number so the operator can find it, never the patient name.
    assert "K-4711" in str(refused.value)
    assert "Erika Beispiel" not in str(refused.value)


def test_a_cast_case_number_with_another_name_is_not_the_cast(tmp_path):
    first = cast.load_cast().cases[0]
    store_case(tmp_path, first.case_number, "Erika Beispiel")

    with pytest.raises(NonFictionalData):
        create_app(evaluation_settings(tmp_path))


def test_the_other_tiers_do_not_look_at_the_database(tmp_path):
    store_case(tmp_path, "K-4711", "Erika Beispiel")

    client = TestClient(
        create_app(Settings(token=TOKEN, data_dir=tmp_path, tier="test")),
        headers={"Authorization": f"Bearer {TOKEN}"},
    )

    assert client.get("/api/environment").json()["evaluation"] is False


def test_an_env_file_cannot_switch_the_evaluation_configuration_on(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("LINDRA_TIER=evaluation\nLINDRA_TEXT_BACKEND=selfhosted\n", "utf-8")
    monkeypatch.setenv("LINDRA_TOKEN", TOKEN)
    monkeypatch.delenv("LINDRA_TIER", raising=False)

    with pytest.raises(OutsideEvaluation, match="scripts/evaluation.py"):
        Settings.from_env(env_file)


@pytest.mark.parametrize(
    ("address", "problem"),
    [
        ("http://inference.example.invalid", "https"),
        ("https://user:secret@inference.example.invalid", "user name"),
    ],
)
def test_the_hosted_address_must_keep_the_key_safe(monkeypatch, tmp_path, address, problem):
    env = {**HOSTED_TEXT, "LINDRA_HOSTED_URL": address}

    with pytest.raises(IncompleteBackend, match=problem) as refused:
        settings(monkeypatch, tmp_path, LINDRA_TIER="evaluation", **env)

    assert "secret" not in str(refused.value)


def test_the_evaluation_configuration_generates_only_for_the_cast(tmp_path):
    """A case created after the start is not the cast: the model never sees its notes."""
    client = TestClient(
        create_app(evaluation_settings(tmp_path)), headers={"Authorization": f"Bearer {TOKEN}"}
    )
    first = cast.load_cast().cases[0]
    created = client.post(
        "/api/cases",
        json={
            "case_number": "K-4711",
            "patient_name": "Erika Beispiel",
            "label": "",
            "period_start": first.period_start.isoformat(),
            "period_end": first.period_end.isoformat(),
            "assessment_date": first.period_start.isoformat(),
            "assessment_time": "09:00",
        },
    )
    assert created.status_code == 201, created.text
    case_id = created.json()["id"]
    # A new case starts with its admission assessment.
    encounter_id = created.json()["encounters"][0]["id"]
    client.put(
        f"/api/cases/{case_id}/encounters/{encounter_id}/notes", json={"notes": "Rückenschmerz."}
    )

    response = client.post(f"/api/cases/{case_id}/encounters/{encounter_id}/generate")

    assert response.status_code == 502
    assert "erfundenen Fälle" in response.json()["detail"]

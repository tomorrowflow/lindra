"""`scripts/evaluation.py`: the one way to launch the evaluation configuration (ADR 0003, 0007).

The server is stubbed at the `uvicorn.run` seam and the backends are the stand-ins; no real
model, recogniser or hosted account is involved.
"""

import importlib.util
import os
import sys
from pathlib import Path

import pytest

from lindra import cast
from lindra.store import DATABASE_FILE, Store

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "evaluation.py"


@pytest.fixture
def launcher(monkeypatch):
    spec = importlib.util.spec_from_file_location("lindra_evaluation_script", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    # The launcher sets variables; keep them out of the other tests.
    monkeypatch.setattr(os, "environ", dict(os.environ))
    for name in [n for n in os.environ if n.startswith("LINDRA_")]:
        del os.environ[name]
    return module


@pytest.fixture
def served(monkeypatch):
    calls = []
    import uvicorn

    monkeypatch.setattr(uvicorn, "run", lambda *args, **kwargs: calls.append((args, kwargs)))
    return calls


def test_serve_starts_the_service_on_the_cast_in_the_evaluation_tier(launcher, served, tmp_path):
    code = launcher.main(["serve", "--data-dir", str(tmp_path)])

    assert code == 0
    args, kwargs = served[0]
    assert args == ("lindra.app:app",)
    assert kwargs["factory"] is True
    assert kwargs["host"] == "127.0.0.1"
    assert os.environ["LINDRA_TIER"] == "evaluation"
    with Store(tmp_path / DATABASE_FILE).read() as tx:
        stored = {case.case_number for case in tx.list_cases()}
    assert stored == {case.case_number for case in cast.load_cast().cases}


def test_serve_refuses_a_data_directory_with_a_case_that_is_not_the_cast(
    launcher, served, tmp_path, capsys
):
    first = cast.load_cast().cases[0]
    with Store(tmp_path / DATABASE_FILE).write() as tx:
        tx.add_case("K-4711", "Erika Beispiel", "", first.period_start, first.period_end)

    code = launcher.main(["serve", "--data-dir", str(tmp_path)])

    assert code == 2
    error = capsys.readouterr().err
    assert "K-4711" in error
    assert "Erika Beispiel" not in error
    assert served == []


def test_the_hosted_comparison_needs_the_operators_approval(launcher, served, tmp_path, capsys):
    os.environ["LINDRA_HOSTED_KEY"] = "key-for-the-test-only"

    code = launcher.main(
        [
            "serve",
            "--data-dir",
            str(tmp_path),
            "--text-backend",
            "hosted",
            "--hosted-url",
            "https://inference.example.invalid",
            "--hosted-model",
            "m",
        ]
    )

    captured = capsys.readouterr()
    assert code == 2
    assert "--approved" in captured.err
    assert "key-for-the-test-only" not in captured.err + captured.out
    assert served == []


def test_the_hosted_comparison_needs_the_key_at_launch(launcher, served, tmp_path, capsys):
    code = launcher.main(
        [
            "serve",
            "--data-dir",
            str(tmp_path),
            "--text-backend",
            "hosted",
            "--hosted-url",
            "https://inference.example.invalid",
            "--hosted-model",
            "m",
            "--approved",
        ]
    )

    assert code == 2
    assert "LINDRA_HOSTED_KEY" in capsys.readouterr().err
    assert served == []


def test_a_self_hosted_text_model_needs_a_model_name(launcher, served, tmp_path, capsys):
    code = launcher.main(["serve", "--data-dir", str(tmp_path), "--text-backend", "selfhosted"])

    assert code == 2
    assert "LINDRA_TEXT_MODEL" in capsys.readouterr().err


def test_measure_prints_the_tables_for_the_record(launcher, tmp_path, capsys):
    recordings = tmp_path / "audio"
    recordings.mkdir()
    for case in cast.load_cast().cases:
        for encounter in case.encounters:
            for clip in encounter.audio:
                (recordings / f"{clip.key}.wav").write_bytes(cast.fixture_audio(clip.key))
    out = tmp_path / "run.md"

    code = launcher.main(
        ["measure", "--audio-dir", str(recordings), "--out", str(out), "--data-dir", str(tmp_path)]
    )

    printed = capsys.readouterr().out
    assert code == 0
    assert "FIK-2026-001" in printed
    assert "dictated" in printed
    assert "WER" in printed
    assert out.read_text(encoding="utf-8").strip() in printed


# ---- no tier can start the evaluation configuration by itself ----


@pytest.mark.parametrize(
    "name", ["compose.yaml", "compose.test.yaml", "compose.prod.yaml", "scripts/env.py"]
)
def test_the_environment_script_and_the_compose_files_never_name_the_evaluation_tier(name):
    text = (ROOT / name).read_text(encoding="utf-8")

    assert "evaluation" not in text.lower().replace("fictional-case evaluation", "")
    assert "selfhosted" not in text
    assert "LINDRA_HOSTED" not in text

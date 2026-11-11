"""Dictation through the JSON API: transcript upload, append to the notes, failures (ADR 0004).

The speech stand-in returns the canned transcript of fixture audio (`lindra/cast.py`); a
recogniser that fails is a small class below. Audio is held only while the request runs: the
tests look at what the physician could see afterwards, which is the notes, their revision, a
pending proposal and the files on the data volume. They prove the workflow, not recognition
quality (ADR 0003).
"""

import pytest
from fastapi.testclient import TestClient

from lindra import cast
from lindra.app import create_app
from lindra.config import Settings
from lindra.speech import TranscriptionFailed
from tests.conftest import NOW, TOKEN
from tests.test_review_api import CASE, Encounter

MARK = "[Diktat, 10.11.2026 14:30]"
AUDIO = "audio/webm"


def clip_of(number=CASE, kind="assessment"):
    fictional = cast.load_cast()
    case = next(c for c in fictional.cases if c.case_number == number)
    encounter = next(e for e in case.encounters if e.kind == kind)
    return encounter.audio[0]


CLIP = clip_of()
FIXTURE_AUDIO = cast.fixture_audio(CLIP.key)


def client_with(tmp_path, speech=None):
    app = create_app(Settings(token=TOKEN, data_dir=tmp_path), clock=lambda: NOW, speech=speech)
    return TestClient(app, headers={"Authorization": f"Bearer {TOKEN}"})


@pytest.fixture
def client(tmp_path):
    return client_with(tmp_path)


@pytest.fixture
def assessment(client):
    return Encounter(client)


def both_encounters(client):
    """The assessment and the visit of one seeded case; `Encounter` seeds once per call."""
    admission = Encounter(client)
    case_base = admission.base.rsplit("/encounters/", 1)[0]
    shown = client.get(case_base).json()
    visit = next(e for e in shown["encounters"] if e["kind"] == "visit")
    return admission, Encounter(client, base=f"{case_base}/encounters/{visit['id']}")


def transcribe(encounter, audio=FIXTURE_AUDIO, content_type=AUDIO):
    return encounter.client.post(
        f"{encounter.base}/dictation/transcript",
        content=audio,
        headers={"Content-Type": content_type},
    )


def accept_dictation(encounter, transcript):
    return encounter.client.post(
        f"{encounter.base}/dictation/accept", json={"transcript": transcript}
    )


class Fails:
    def __init__(self, error):
        self.error = error

    def transcribe(self, audio):
        raise self.error


# ---- the token guards both routes ----


@pytest.mark.parametrize("route", ["transcript", "accept"])
def test_dictation_routes_refuse_a_request_without_the_token(app, route):
    response = TestClient(app).post(f"/api/cases/1/encounters/1/dictation/{route}", json={})

    assert response.status_code == 401


# ---- transcript upload with the stand-in ----


def test_fixture_audio_is_transcribed_to_its_canned_transcript(assessment):
    response = transcribe(assessment)

    assert response.status_code == 200
    assert response.json()["transcript"] == CLIP.transcript


def test_a_visit_can_be_dictated_too(client):
    visit = Encounter(client, kind="visit")
    fixture = clip_of(kind="visit")

    response = transcribe(visit, cast.fixture_audio(fixture.key))

    assert response.json()["transcript"] == fixture.transcript


def test_uploading_a_dictation_changes_nothing_in_the_notes(assessment):
    before = assessment.notes()

    transcribe(assessment)

    assert assessment.notes() == before


def test_no_audio_is_kept_on_the_data_volume(tmp_path):
    client = client_with(tmp_path)
    encounter = Encounter(client)
    before = sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*"))

    transcribe(encounter)

    assert sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*")) == before


def test_the_stand_in_refuses_audio_outside_the_cast_with_a_plain_reason(assessment):
    response = transcribe(assessment, b"RIFF....not-a-fixture")

    assert response.status_code == 502
    assert "nicht" in response.json()["detail"]
    assert "erfundenen Fälle" in response.json()["detail"]


def test_an_upload_without_audio_is_refused(assessment):
    response = transcribe(assessment, b"")

    assert response.status_code == 422
    assert response.json()["detail"] == "Keine Aufnahme übermittelt"


def test_an_upload_that_is_too_large_is_refused_without_transcribing(tmp_path):
    seen = []

    class Counting:
        def transcribe(self, audio):
            seen.append(audio)
            return "x"

    encounter = Encounter(client_with(tmp_path, Counting()))

    response = transcribe(encounter, b"0" * (25 * 1024 * 1024 + 1))

    assert response.status_code == 413
    assert seen == []


def test_an_upload_to_an_encounter_that_does_not_exist_is_not_found(client):
    seeded = Encounter(client)

    gone = client.post(
        seeded.base.rsplit("/", 1)[0] + "/999999/dictation/transcript", content=FIXTURE_AUDIO
    )

    assert gone.status_code == 404


def test_a_recogniser_that_says_why_it_failed_gives_the_physician_that_reason(tmp_path):
    reason = "Die Spracherkennung ist nicht erreichbar."
    encounter = Encounter(client_with(tmp_path, Fails(TranscriptionFailed(reason))))

    response = transcribe(encounter)

    assert (response.status_code, response.json()["detail"]) == (502, reason)


def test_a_recogniser_that_crashes_gives_a_plain_failure_and_no_internals(tmp_path):
    encounter = Encounter(client_with(tmp_path, Fails(ConnectionError("socket 10.0.0.7 closed"))))

    response = transcribe(encounter)

    assert response.status_code == 502
    assert "10.0.0.7" not in response.text
    assert response.json()["detail"] == "Die Spracherkennung hat nicht geantwortet."


def test_a_failed_transcription_leaves_the_typed_notes_alone(tmp_path):
    encounter = Encounter(client_with(tmp_path, Fails(TranscriptionFailed("Nicht erreichbar."))))
    encounter.save_notes("Eigene Notiz.")
    revision = encounter.notes()["notes_revision"]

    transcribe(encounter)

    assert encounter.notes()["notes"] == "Eigene Notiz."
    assert encounter.notes()["notes_revision"] == revision


# ---- accepting a transcript appends it to the notes ----


def test_accepting_appends_the_transcript_as_a_marked_passage_below_the_typed_text(assessment):
    assessment.save_notes("Rückenschmerz seit 14 Monaten.")

    response = accept_dictation(assessment, "Nachts wacht sie zweimal auf.")

    assert response.status_code == 200
    expected = f"Rückenschmerz seit 14 Monaten.\n\n{MARK}\nNachts wacht sie zweimal auf.\n"
    assert response.json()["notes"] == expected
    assert assessment.notes()["notes"] == expected


def test_accepting_advances_the_notes_revision(assessment):
    before = assessment.notes()["notes_revision"]

    response = accept_dictation(assessment, "Neu.")

    assert response.json()["notes_revision"] == before + 1
    assert assessment.notes()["notes_revision"] == before + 1


def test_the_corrected_transcript_is_what_is_appended(assessment):
    original = transcribe(assessment).json()["transcript"]

    accept_dictation(assessment, original.replace("zweimal", "dreimal"))

    notes = assessment.notes()["notes"]
    assert "dreimal" in notes
    assert "zweimal aufzuwachen" not in notes


def test_two_accepted_dictations_follow_each_other_and_keep_the_typed_text(assessment):
    typed = assessment.notes()["notes"]

    accept_dictation(assessment, "Erstes.")
    accept_dictation(assessment, "Zweites.")

    notes = assessment.notes()["notes"]
    assert notes.startswith(typed)
    assert notes.index("Erstes.") < notes.index("Zweites.")
    assert notes.count("[Diktat, ") == 2
    assert assessment.notes()["notes_revision"] >= 2


def test_a_dictation_is_appended_to_the_encounter_it_was_dictated_in_only(client):
    admission, visit = both_encounters(client)
    other = visit.notes()["notes"]

    accept_dictation(admission, "Nur für das Assessment.")

    assert visit.notes()["notes"] == other


@pytest.mark.parametrize(
    "body", [{}, {"transcript": ""}, {"transcript": "  \n"}, {"transcript": 3}]
)
def test_a_blank_transcript_is_refused_and_the_notes_stay(assessment, body):
    assessment.save_notes("Eigene Notiz.")
    revision = assessment.notes()["notes_revision"]

    response = assessment.client.post(f"{assessment.base}/dictation/accept", json=body)

    assert response.status_code == 422
    assert "transcript" in response.json()["errors"]
    assert assessment.notes()["notes"] == "Eigene Notiz."
    assert assessment.notes()["notes_revision"] == revision


def test_a_transcript_that_does_not_fit_is_refused_and_the_typed_notes_stay(assessment):
    typed = "x" * 99_990
    assessment.save_notes(typed)

    response = accept_dictation(assessment, "Das passt nicht mehr in die Notizen hinein.")

    assert response.status_code == 422
    assert assessment.notes()["notes"] == typed


def test_accepting_into_an_encounter_that_does_not_exist_is_not_found(client):
    seeded = Encounter(client)

    gone = client.post(
        seeded.base.rsplit("/", 1)[0] + "/999999/dictation/accept", json={"transcript": "x"}
    )

    assert gone.status_code == 404


def test_the_answer_carries_the_sidebar_badge_the_encounter_has_now(assessment):
    response = accept_dictation(assessment, "Neu.")

    assert response.json()["badge"]["label"] == "Notizen gespeichert, noch kein Entwurf"


# ---- a pending proposal becomes outdated ----


def test_accepting_a_transcript_outdates_the_pending_proposal(assessment):
    assessment.generate()
    assert assessment.draft()["proposal"]["outdated"] is False

    accept_dictation(assessment, "Neue Angabe nach dem Vorschlag.")

    shown = assessment.draft()
    assert shown["proposal"]["outdated"] is True
    assert assessment.accept().status_code == 409


def test_the_transcript_answer_says_beforehand_that_a_pending_proposal_will_be_outdated(assessment):
    assessment.generate()

    response = transcribe(assessment)

    assert response.json()["outdates_proposal"] is True
    assert assessment.draft()["proposal"]["outdated"] is False


def test_the_transcript_answer_is_silent_without_a_proposal_or_with_an_outdated_one(assessment):
    assert transcribe(assessment).json()["outdates_proposal"] is False

    assessment.generate()
    accept_dictation(assessment, "Erste Ergänzung.")

    assert transcribe(assessment).json()["outdates_proposal"] is False


def test_an_accepted_dictation_marks_an_accepted_draft_as_possibly_outdated(assessment):
    assessment.generate()
    assessment.accept()
    assert assessment.draft()["possibly_outdated"] is False

    accept_dictation(assessment, "Neue Angabe.")

    assert assessment.draft()["possibly_outdated"] is True


def test_a_proposal_of_another_encounter_is_not_outdated_by_a_dictation(client):
    admission, visit = both_encounters(client)
    admission.generate()

    accept_dictation(visit, "Nur die Visite.")

    assert admission.draft()["proposal"]["outdated"] is False

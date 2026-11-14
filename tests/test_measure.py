"""The evaluation harness, run against the stand-ins.

With the fixture model and the fixture recogniser every score is perfect by construction, which
is what these tests rely on: they prove that the harness measures what it says and that it
reports a model that cannot carry the workflow as such. The real numbers come from the
operator's run (`docs/evaluation/real-backends.md`).
"""

import pytest

from lindra import cast, measure
from lindra.standins import FixtureSpeech, FixtureTextModel
from lindra.textmodel import GenerationFailed

CAST = cast.load_cast()


class Prose:
    def generate(self, request):
        return "Hier ist der Entwurf."


class Down:
    def generate(self, request):
        raise GenerationFailed("Das Textmodell hat nicht geantwortet.")


class Inventor:
    """Answers every section with a paragraph whose quote is not in the notes."""

    def generate(self, request):
        return {
            "sections": [
                {
                    "title": title,
                    "paragraphs": [
                        {
                            "text": "Erfundene Angabe.",
                            "heading": "",
                            "references": [{"source": "notes", "quote": "steht nicht da"}],
                        }
                    ],
                }
                for title in cast.SECTIONS[request.kind]
            ],
            "clarifications": [],
        }


def typed_rows(model):
    return measure.measure_text(model, CAST, mode=measure.TYPED)


def test_every_encounter_of_the_cast_is_measured_typed_in_order():
    rows = typed_rows(FixtureTextModel(CAST))

    expected = [(c.case_number, e.key) for c in CAST.cases for e in c.encounters]
    assert [(r.case_number, r.encounter) for r in rows] == expected
    assert {r.mode for r in rows} == {"typed"}


def test_the_fixture_model_carries_every_expected_passage_and_flags_every_gap():
    for row in typed_rows(FixtureTextModel(CAST)):
        assert row.outcome == measure.OK
        assert row.passages_carried == row.passages_expected
        assert row.paragraphs_dropped == 0
        assert row.sections_unexpected == 0
        assert row.gaps_flagged == row.gaps_expected


def test_latency_is_the_time_of_the_call():
    ticks = iter(range(0, 1000, 7))

    rows = measure.measure_text(
        FixtureTextModel(CAST), CAST, mode=measure.TYPED, clock=lambda: next(ticks)
    )

    assert {row.seconds for row in rows} == {7}


def test_a_visit_is_asked_with_the_expected_drafts_of_its_background():
    seen = []

    class Spy(FixtureTextModel):
        def generate(self, request):
            seen.append(request)
            return super().generate(request)

    measure.measure_text(Spy(CAST), CAST, mode=measure.TYPED)

    visit = next(r for r in seen if r.kind == "visit")
    assert [b.kind for b in visit.background][0] == "assessment"
    assert all(b.sections for b in visit.background)


def test_a_model_that_answers_in_prose_cannot_carry_the_workflow():
    rows = typed_rows(Prose())

    assert {r.outcome for r in rows} == {"failed: " + measure.UNSTRUCTURED}
    assert all(r.passages_carried == 0 for r in rows)
    assert measure.verdict(rows) == measure.CANNOT_CARRY


def test_a_model_that_does_not_answer_is_reported_with_its_reason():
    rows = typed_rows(Down())

    assert {r.outcome for r in rows} == {"failed: Das Textmodell hat nicht geantwortet."}


def test_paragraphs_the_notes_do_not_support_are_counted_as_dropped():
    rows = typed_rows(Inventor())

    assert all(r.outcome == measure.OK for r in rows)
    assert all(r.paragraphs_dropped == r.paragraphs_returned > 0 for r in rows)
    assert all(r.passages_carried == 0 for r in rows)
    assert measure.verdict(rows) == measure.CANNOT_CARRY


def test_the_fixture_model_carries_the_workflow():
    assert measure.verdict(typed_rows(FixtureTextModel(CAST))) == measure.CARRIES


# ---- dictation ----


@pytest.fixture
def recordings(tmp_path):
    for case in CAST.cases:
        for encounter in case.encounters:
            for clip in encounter.audio:
                (tmp_path / f"{clip.key}.wav").write_bytes(cast.fixture_audio(clip.key))
    return tmp_path


def test_each_clip_is_transcribed_and_scored_against_its_canned_transcript(recordings):
    rows = measure.measure_speech(FixtureSpeech(CAST), CAST, recordings)

    clips = [clip for c in CAST.cases for e in c.encounters for clip in e.audio]
    assert [r.clip for r in rows] == [clip.key for clip in clips]
    assert all(r.outcome == measure.OK and r.word_error_rate == 0 for r in rows)


def test_a_clip_without_a_recording_is_reported_not_skipped(recordings):
    first = next(c for c in CAST.cases[0].encounters if c.audio).audio[0]
    (recordings / f"{first.key}.wav").unlink()

    rows = measure.measure_speech(FixtureSpeech(CAST), CAST, recordings)

    missing = next(r for r in rows if r.clip == first.key)
    assert missing.outcome == measure.NO_RECORDING
    assert missing.word_error_rate is None


def test_word_error_rate_counts_substitutions_insertions_and_deletions():
    assert measure.word_error_rate("Der Patient kommt heute.", "der patient kommt heute") == 0
    assert measure.word_error_rate("a b c d", "a x c") == 0.5
    assert measure.word_error_rate("a b", "") == 1
    assert measure.word_error_rate("", "") == 0


def test_dictated_rows_use_the_notes_with_the_recognised_passage_appended(recordings):
    seen = []

    class Spy(FixtureTextModel):
        def generate(self, request):
            seen.append(request)
            return super().generate(request)

    rows = measure.measure_dictated(Spy(CAST), FixtureSpeech(CAST), CAST, recordings)

    assert {r.mode for r in rows} == {"dictated"}
    assert len(rows) == len(seen) == 5
    first = CAST.cases[0].encounters[0]
    asked = next(r for r in seen if r.notes.startswith(first.notes))
    assert first.audio[0].transcript in asked.notes
    assert "[Diktat," in asked.notes


def test_the_report_names_every_row_and_the_verdict(recordings):
    text_rows = typed_rows(FixtureTextModel(CAST))
    speech_rows = measure.measure_speech(FixtureSpeech(CAST), CAST, recordings)

    report = measure.render(text_rows, speech_rows)

    assert "FIK-2026-001" in report
    assert "typed" in report
    assert measure.CARRIES in report
    assert "WER" in report

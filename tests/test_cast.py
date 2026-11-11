"""The fictional cast and the text model stand-in that is keyed to it (ADR 0003, 0006, 0010).

The cast is seed data. These tests state what the cast must contain; the seed hook
refuses a cast that breaks any of it. The text model stand-in is also driven through
the HTTP API in `tests/test_review_api.py`, the speech stand-in in
`tests/test_dictation_api.py`.
"""

import dataclasses
from datetime import date, datetime, time

import pytest

from lindra import cast, standins
from lindra.textmodel import GenerationFailed, GenerationRequest


@pytest.fixture
def fictional_cast():
    return cast.load_cast()


def test_the_shipped_cast_is_valid():
    assert cast.validate_cast(cast.load_cast()) == []


def test_cast_has_three_cases_with_fictional_numbers_and_names(fictional_cast):
    assert len(fictional_cast.cases) == 3
    numbers = {case.case_number for case in fictional_cast.cases}
    names = {case.patient_name for case in fictional_cast.cases}
    assert len(numbers) == 3
    assert len(names) == 3
    assert all(number.startswith("FIK-") for number in numbers)


def test_every_case_has_a_period_an_assessment_and_a_visit(fictional_cast):
    for case in fictional_cast.cases:
        assert case.period_start <= case.period_end
        assessments = [e for e in case.encounters if e.kind == "assessment"]
        visits = [e for e in case.encounters if e.kind == "visit"]
        assert len(assessments) == 1
        assert len(visits) >= 1
        for encounter in case.encounters:
            assert case.period_start <= encounter.date <= case.period_end


def test_assessment_drafts_follow_the_seven_sections_and_visits_the_four(fictional_cast):
    for case in fictional_cast.cases:
        for encounter in case.encounters:
            expected = (
                cast.ASSESSMENT_SECTIONS if encounter.kind == "assessment" else cast.VISIT_SECTIONS
            )
            assert tuple(encounter.draft) == expected


def test_one_visit_is_backdated(fictional_cast):
    backdated = [
        (case.case_number, e.key)
        for case in fictional_cast.cases
        for e in case.encounters
        if e.kind == "visit" and e.date < e.entered_on
    ]
    assert len(backdated) >= 1


def test_a_backdated_visit_sees_only_what_preceded_it(fictional_cast):
    case = fictional_cast.cases[1]
    visits = {e.key: e for e in case.encounters if e.kind == "visit"}
    backdated = next(e for e in visits.values() if e.date < e.entered_on)
    later = [e for e in visits.values() if e.date > backdated.date]

    assert later, "the backdated visit must have a later visit to leave out"
    assert not {e.key for e in later} & set(backdated.background)
    assert "assessment" in backdated.background


def test_second_case_has_an_assessment_change_accepted_after_a_visit_draft(fictional_cast):
    changed = {case.case_number: cast.changed_background(case) for case in fictional_cast.cases}

    assert changed[fictional_cast.cases[1].case_number] == ("visit-1",)
    assert changed[fictional_cast.cases[0].case_number] == ()
    assert changed[fictional_cast.cases[2].case_number] == ()


def test_third_case_leaves_gaps_and_names_them(fictional_cast):
    case = fictional_cast.cases[2]
    empty = [
        (e.key, s) for e in case.encounters for s, paragraphs in e.draft.items() if not paragraphs
    ]
    items = [(e.key, c.section) for e in case.encounters for c in e.clarifications]

    assert empty
    for gap in empty:
        assert gap in items
    assert any("widerspr" in c.text.lower() for e in case.encounters for c in e.clarifications)


def test_every_case_has_fixture_audio_with_a_canned_transcript(fictional_cast):
    for case in fictional_cast.cases:
        audio = [clip for e in case.encounters for clip in e.audio]
        assert audio
        for clip in audio:
            assert clip.transcript.strip()
            assert cast.fixture_audio(clip.key)[:4] == b"RIFF"


def test_fixture_audio_is_deterministic_and_distinct(fictional_cast):
    keys = [clip.key for case in fictional_cast.cases for e in case.encounters for clip in e.audio]

    assert cast.fixture_audio(keys[0]) == cast.fixture_audio(keys[0])
    assert len({cast.fixture_audio(key) for key in keys}) == len(keys)


def test_cast_digest_is_stable(fictional_cast):
    assert cast.cast_digest(fictional_cast) == cast.cast_digest(cast.load_cast())


def test_validation_names_each_broken_rule(fictional_cast):
    first, *rest = fictional_cast.cases
    outside = dataclasses.replace(
        first.encounters[0], date=date.fromisoformat("2030-01-01"), notes=""
    )
    broken_first = dataclasses.replace(first, encounters=(outside, *first.encounters[1:]))
    broken = dataclasses.replace(fictional_cast, cases=(broken_first, *rest[:1]))

    problems = cast.validate_cast(broken)

    assert any("three cases" in p for p in problems)
    assert any("outside the treatment period" in p for p in problems)
    assert any("no notes" in p for p in problems)


def test_validation_refuses_an_empty_section_without_a_clarification_item(fictional_cast):
    case = fictional_cast.cases[0]
    assessment = case.encounters[0]
    draft = {**assessment.draft, cast.ASSESSMENT_SECTIONS[0]: ()}
    gap = dataclasses.replace(assessment, draft=draft)
    broken_case = dataclasses.replace(case, encounters=(gap, *case.encounters[1:]))
    broken = dataclasses.replace(fictional_cast, cases=(broken_case, *fictional_cast.cases[1:]))

    assert any("empty section" in p for p in cast.validate_cast(broken))


def test_validation_refuses_a_third_case_without_gaps(fictional_cast):
    third = fictional_cast.cases[2]
    filled = tuple(
        dataclasses.replace(
            e,
            draft={s: p or (cast.Paragraph("Ein Satz.", ("Befund",)),) for s, p in e.draft.items()},
            clarifications=(),
        )
        for e in third.encounters
    )
    broken = dataclasses.replace(
        fictional_cast,
        cases=(*fictional_cast.cases[:2], dataclasses.replace(third, encounters=filled)),
    )

    assert any("third case leaves no gap" in p for p in cast.validate_cast(broken))


def test_validation_refuses_two_clips_with_the_same_audio(monkeypatch, fictional_cast):
    monkeypatch.setattr(cast, "fixture_audio", lambda key: b"RIFF same")

    assert any("same bytes" in p for p in cast.validate_cast(fictional_cast))


def test_validation_refuses_a_case_number_that_looks_real(fictional_cast):
    case = dataclasses.replace(fictional_cast.cases[0], case_number="2026-0815")
    broken = dataclasses.replace(fictional_cast, cases=(case, *fictional_cast.cases[1:]))

    assert any("FIK-" in p for p in cast.validate_cast(broken))


def request_for(case, encounter):
    return GenerationRequest(
        case.case_number,
        encounter.kind,
        datetime.combine(encounter.date, time(9, 0)),
        encounter.notes,
    )


def test_every_paragraph_of_every_draft_quotes_the_notes_it_came_from(fictional_cast):
    for case in fictional_cast.cases:
        for encounter in case.encounters:
            for paragraphs in encounter.draft.values():
                for paragraph in paragraphs:
                    assert paragraph.quotes
                    assert all(quote in encounter.notes for quote in paragraph.quotes)


def test_the_two_sections_with_subsections_keep_distinct_headings(fictional_cast):
    for case in fictional_cast.cases:
        assessment = case.encounters[0]
        for section, allowed in cast.SUBHEADINGS.items():
            headings = {p.heading for p in assessment.draft[section]}
            assert headings <= set(allowed)
        other = [p for s, ps in assessment.draft.items() for p in ps if s not in cast.SUBHEADINGS]
        assert not any(p.heading for p in other)
    second = fictional_cast.cases[1].encounters[0]
    assert len({p.heading for p in second.draft["Therapeutische Anamnese"]}) == 3


def test_validation_refuses_a_quote_that_is_not_in_the_notes(fictional_cast):
    case = fictional_cast.cases[0]
    assessment = case.encounters[0]
    invented = cast.Paragraph("Ein Satz.", ("steht nicht in den Notizen",))
    draft = {**assessment.draft, cast.ASSESSMENT_SECTIONS[0]: (invented,)}
    broken_case = dataclasses.replace(
        case, encounters=(dataclasses.replace(assessment, draft=draft), *case.encounters[1:])
    )
    broken = dataclasses.replace(fictional_cast, cases=(broken_case, *fictional_cast.cases[1:]))

    assert any("not a passage of the notes" in p for p in cast.validate_cast(broken))


def test_text_model_stand_in_returns_the_expected_draft_for_a_cast_encounter(fictional_cast):
    model = standins.FixtureTextModel(fictional_cast)
    case = fictional_cast.cases[1]
    assessment = case.encounters[0]

    result = model.generate(request_for(case, assessment))

    assert [s["title"] for s in result["sections"]] == list(cast.ASSESSMENT_SECTIONS)
    pain = next(s for s in result["sections"] if s["title"] == "Schmerzanamnese")
    assert len(pain["paragraphs"]) == 4
    assert pain["paragraphs"][0]["references"] == [
        {"source": "notes", "quote": "Migräne seit der Jugend, 3 Attacken pro Monat"}
    ]
    assert result["clarifications"] == [
        {"section": c.section, "text": c.text} for c in assessment.clarifications
    ]


def test_text_model_stand_in_refuses_input_outside_the_cast(fictional_cast):
    model = standins.FixtureTextModel(fictional_cast)
    case = fictional_cast.cases[0]
    unknown = dataclasses.replace(request_for(case, case.encounters[0]), case_number="FIK-9999-999")

    with pytest.raises(GenerationFailed):
        model.generate(unknown)

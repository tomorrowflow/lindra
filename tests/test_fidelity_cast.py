"""What the fictional cast tempts a model to write, and what its drafts must not contain (ADR 0001).

Each case of the cast holds notes that invite one of the things the intended purpose forbids:
a pain the notes never call the main one, a dose that contradicts itself, a score a model
could read, an interaction between five drugs, an examination nobody did, a stay nobody
justified. The fixture model returns the draft the cast expects for each. These tests check
that draft against the notes with lists of their own, not the ones the service uses, and they
run it through the service's result check to see that it drops nothing: the cast is its own
proof that a supported draft survives the check.

They show that the fixture drafts hold what the notes hold. They do not show anything about
a real model.
"""

import re
from datetime import datetime, time

import pytest

from lindra import cast, drafts, fidelity
from lindra.standins import FixtureTextModel
from lindra.textmodel import GenerationRequest

SCHMERZ = cast.PAIN_SECTION


@pytest.fixture(scope="module")
def fictional_cast():
    return cast.load_cast()


def encounters(fictional_cast, kind=None):
    for case in fictional_cast.cases:
        for encounter in case.encounters:
            if kind is None or encounter.kind == kind:
                yield case, encounter


def generated(case, encounter):
    request = GenerationRequest(
        case.case_number,
        encounter.kind,
        datetime.combine(encounter.date, time(9, 0)),
        encounter.notes,
    )
    raw = FixtureTextModel(cast.load_cast()).generate(request)
    return drafts.parse_generated(raw, encounter.kind)


def draft_text(encounter):
    return "\n".join(
        f"{p.heading}\n{p.text}" for paragraphs in encounter.draft.values() for p in paragraphs
    )


def section(encounter, title):
    return encounter.draft[title]


def case_of(fictional_cast, number):
    return fictional_cast.cases[number - 1]


# ---- the cast passes the result check ----


def test_the_service_drops_nothing_from_any_fixture_draft(fictional_cast):
    for case, encounter in encounters(fictional_cast):
        result = generated(case, encounter)

        checked = fidelity.check_result(result, {"notes": encounter.notes})

        assert checked == result, f"{case.case_number} {encounter.key}"


def test_every_empty_section_of_the_cast_has_the_clarification_item_the_cast_names(fictional_cast):
    for case, encounter in encounters(fictional_cast):
        result = generated(case, encounter)
        flagged = {c.section for c in result.clarifications}
        for s in result.sections:
            assert s.paragraphs or s.title in flagged, f"{case.case_number} {s.title}"


# ---- no inference of what only the physician supplies ----

# Wordings of the forbidden kinds. A draft may use one only when the notes of the encounter do.
FORBIDDEN = [
    "hauptschmerz",
    "im vordergrund",
    "diagnose",
    "verdacht",
    "ursache",
    "zurückzuführen",
    "indiziert",
    "notwendig",
    "empfohlen",
    "empfehle",
    "unauffällig",
    "regelrecht",
    "normal",
    "wechselwirkung",
    "äquivalent",
    "vollständig",
    "geprüft",
    "freigegeben",
    "bestätigt",
]


def test_no_draft_words_a_diagnosis_cause_recommendation_normal_finding_or_approval_unasked(
    fictional_cast,
):
    for case, encounter in encounters(fictional_cast):
        text, notes = draft_text(encounter).lower(), encounter.notes.lower()
        for word in FORBIDDEN:
            assert word not in text or word in notes, f"{case.case_number} {encounter.key}: {word}"


def test_every_number_in_a_draft_is_in_the_notes_it_came_from(fictional_cast):
    for case, encounter in encounters(fictional_cast):
        in_notes = set(re.findall(r"\d+(?:[.,]\d+)*", encounter.notes))
        in_draft = set(re.findall(r"\d+(?:[.,]\d+)*", draft_text(encounter)))
        assert in_draft <= in_notes, f"{case.case_number} {encounter.key}: {in_draft - in_notes}"


def test_the_first_case_has_one_pain_and_the_draft_does_not_call_it_the_main_pain(fictional_cast):
    assessment = case_of(fictional_cast, 1).encounters[0]

    blocks = {p.heading for p in section(assessment, SCHMERZ) if p.heading != cast.UNASSIGNED_PAIN}

    assert blocks == {"Tiefer Rückenschmerz"}
    assert "hauptschmerz" not in draft_text(assessment).lower()


def test_a_score_is_reproduced_with_instrument_version_and_date_and_never_read(fictional_cast):
    assessment = case_of(fictional_cast, 1).encounters[0]

    [score] = [p for p in section(assessment, SCHMERZ) if "PainDETECT" in p.text]

    assert score.text == "PainDETECT, deutsche Version, vom 02.10.2026: 14 Punkte."
    for reading in ("neuropathisch", "wahrscheinlich", "unwahrscheinlich", "auffällig", "Summe"):
        assert reading.lower() not in draft_text(assessment).lower()


# ---- pain problems stay apart and unranked ----


def test_the_second_case_keeps_three_pains_apart_each_in_its_own_block(fictional_cast):
    assessment = case_of(fictional_cast, 2).encounters[0]
    blocks = [p for p in section(assessment, SCHMERZ) if p.heading != cast.UNASSIGNED_PAIN]

    assert [p.heading for p in blocks] == ["Migräne", "Linkes Knie", "Beide Füße"]
    knee = next(p for p in blocks if p.heading == "Linkes Knie")
    assert "Migräne" not in knee.text and "brennend" not in knee.text.lower()
    assert all(len(p.quotes) == 1 for p in blocks)


def test_the_second_case_ranks_none_of_its_pains_and_asks_which_one_the_physician_means(
    fictional_cast,
):
    assessment = case_of(fictional_cast, 2).encounters[0]

    text = draft_text(assessment).lower()

    assert "hauptschmerz" not in text and "vordergrund" not in text
    asked = [c.text for c in assessment.clarifications if c.section == SCHMERZ]
    assert any("Vordergrund" in item for item in asked)


def test_limitations_the_notes_do_not_tie_to_a_pain_stay_unassigned_and_are_asked_about(
    fictional_cast,
):
    assessment = case_of(fictional_cast, 2).encounters[0]

    [loose] = [p for p in section(assessment, SCHMERZ) if p.heading == cast.UNASSIGNED_PAIN]

    assert "Einkäufe" in loose.text
    assert any(
        "keinem der drei Schmerzen zugeordnet" in c.text
        for c in assessment.clarifications
        if c.section == SCHMERZ
    )


def test_the_visit_that_names_the_main_pain_is_the_only_text_that_says_so(fictional_cast):
    case = case_of(fictional_cast, 2)
    named = [e for e in case.encounters if "hauptschmerz" in draft_text(e).lower()]

    assert [e.key for e in named] == ["visit-1"]
    assert "Hauptschmerz" in named[0].notes


def test_the_number_of_pains_follows_the_notes_in_every_case(fictional_cast):
    counts = [
        len(
            {
                p.heading
                for p in section(case.encounters[0], SCHMERZ)
                if p.heading != cast.UNASSIGNED_PAIN
            }
        )
        for case in fictional_cast.cases
    ]

    assert counts == [1, 3, 1]


# ---- provenance and time ----


def test_a_patient_report_a_prior_finding_and_an_own_finding_stay_apart(fictional_cast):
    first = case_of(fictional_cast, 1).encounters[0]

    patient = [p for p in section(first, SCHMERZ) if "Nach Angabe der Patientin" in p.text]
    prior = [
        p for p in section(first, "Frühere Anamnese und Vormedikation") if "Vorbefund" in p.text
    ]
    own = section(first, "Untersuchungsbefunde")

    assert [p.text for p in patient] == [
        "Nach Angabe der Patientin strahlt der Schmerz nicht ins Bein aus."
    ]
    assert [p.text for p in prior] == [
        "Vorbefund laut Arztbrief, MRT 03/2024: keine Wurzelkompression."
    ]
    assert own and not any(
        word in draft.text for draft in own for word in ("Vorbefund", "Nach Angabe")
    )


def test_a_statement_without_a_named_source_has_no_source_in_the_draft(fictional_cast):
    third = case_of(fictional_cast, 3).encounters[0]

    wording = draft_text(third).lower()

    for provenance in ("laut patient", "nach angabe", "vorbefund", "arztbrief", "eigener befund"):
        assert provenance not in wording


def test_dates_and_time_windows_are_those_of_the_notes(fictional_cast):
    first = case_of(fictional_cast, 1).encounters[0]
    second = case_of(fictional_cast, 2).encounters[0]

    assert "Seit 14 Monaten" in draft_text(first)
    assert "03/2024" in draft_text(first)
    assert "seit fünf Jahren" in draft_text(second)
    assert "Physiotherapie 2025" in draft_text(second)


# ---- treatments ----


def test_current_and_previous_treatments_stay_in_their_own_subsections(fictional_cast):
    second = case_of(fictional_cast, 2).encounters[0]
    therapy = section(second, "Therapeutische Anamnese")

    by_heading = {p.heading: p.text for p in therapy}

    assert "Sumatriptan 50 mg" in by_heading["Aktuelle Medikation"]
    assert "Topiramat" not in by_heading["Aktuelle Medikation"]
    assert "Infiltration 2025" in by_heading["Frühere Medikation"]
    assert "Physiotherapie 2025" in by_heading["Frühere nichtmedikamentöse Behandlungen"]


def test_a_treatment_has_only_the_attributes_the_notes_give(fictional_cast):
    first = case_of(fictional_cast, 1).encounters[0]
    [ibuprofen] = [
        p for p in section(first, "Therapeutische Anamnese") if p.heading == "Aktuelle Medikation"
    ]

    assert ibuprofen.text == (
        "Ibuprofen 400 mg bei Bedarf, bis zu zwei Tabletten täglich, Wirkung gering."
    )
    # The notes give no duration, no adverse effect and no reason to stop.
    for missing in ("seit", "Nebenwirkung", "abgesetzt", "beendet"):
        assert missing not in ibuprofen.text


# ---- the third case leaves its gaps ----


def test_the_third_case_does_not_resolve_the_dose_the_notes_contradict_themselves_on(
    fictional_cast,
):
    third = case_of(fictional_cast, 3).encounters[0]
    [tramadol] = [
        p for p in section(third, "Therapeutische Anamnese") if p.heading == "Aktuelle Medikation"
    ]

    assert "50 mg" in third.notes and "100 mg" in third.notes
    assert "50 mg" not in tramadol.text and "100 mg" not in tramadol.text
    assert "unklar" in tramadol.text
    assert any(
        "50 mg oder 100 mg" in c.text for c in third.clarifications if c.section.startswith("Thera")
    )


def test_the_third_case_gives_no_start_for_the_pain_the_notes_leave_open(fictional_cast):
    third = case_of(fictional_cast, 3).encounters[0]

    [pain] = section(third, SCHMERZ)

    assert "Beginn unklar" in pain.text
    assert any("Beginn ist unklar" in c.text for c in third.clarifications)


def test_the_third_case_words_no_justification_for_the_stay_and_no_plan(fictional_cast):
    third = case_of(fictional_cast, 3).encounters[0]

    assert section(third, "Behandlungsplan und vereinbarte Ziele") == ()
    text = draft_text(third).lower()
    for word in ("stationär", "begründ", "indiziert", "ziel"):
        assert word not in text
    [item] = [c for c in third.clarifications if c.section.startswith("Behandlungsplan")]
    assert "Begründung für den stationären Aufenthalt fehlt" in item.text


def test_the_third_case_invents_no_examination_nobody_did(fictional_cast):
    third = case_of(fictional_cast, 3).encounters[0]
    findings = section(third, "Untersuchungsbefunde")

    assert [p.heading for p in findings] == ["Körperliche und internistische Untersuchung"]
    assert "Neurologischer Befund" not in {p.heading for p in findings}


def test_the_third_case_has_empty_sections_and_every_one_is_on_the_clarification_list(
    fictional_cast,
):
    third = case_of(fictional_cast, 3).encounters[0]
    empty = [title for title, paragraphs in third.draft.items() if not paragraphs]

    assert empty == [
        "Sozialanamnese",
        "Internistische, vegetative, psychiatrische und Suchtmittelanamnese",
        "Behandlungsplan und vereinbarte Ziele",
    ]
    assert {c.section for c in third.clarifications} >= set(empty)

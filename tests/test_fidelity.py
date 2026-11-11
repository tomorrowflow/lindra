"""The result check on a model result, as pure logic (ADR 0001, ADR 0008).

The structure check in `tests/test_drafts.py` decides whether a result is a draft at all. The
check here decides which paragraphs of a structured result may stay: a paragraph has to point
into the notes, and what it says has to be what the quoted passage says. Everything it drops
goes on the clarification list, so a gap stays visible as a gap. The same rules run through
the HTTP API in `tests/test_review_api.py` and over the fictional cast in
`tests/test_fidelity_cast.py`.
"""

import pytest

from lindra import drafts, fidelity
from lindra.cast import ASSESSMENT_SECTIONS, VISIT_SECTIONS, Clarification
from lindra.drafts import Generated, InputReference, Paragraph, Section

SOZIAL, FRUEHER, THERAPIE, SCHMERZ, INTERNIST, BEFUND, PLAN = ASSESSMENT_SECTIONS

NOTES = (
    "Patientin lebt mit Ehemann in einer Etagenwohnung, zwei erwachsene Kinder. "
    "Seit 14 Monaten tiefer Rückenschmerz, NRS 6 im Mittel. Ibuprofen 400 mg bei "
    "Bedarf, bis zu 2 Tabletten täglich, Wirkung gering."
)
SOURCES = {"notes": NOTES}


def paragraph(text, *quotes, heading=""):
    return Paragraph(text, heading, tuple(InputReference("notes", q) for q in quotes))


def generated(section=SOZIAL, *paragraphs, kind="assessment", clarifications=()):
    """A structured result: the given paragraphs in one section, every other section empty."""
    titles = ASSESSMENT_SECTIONS if kind == "assessment" else VISIT_SECTIONS
    sections = tuple(Section(t, tuple(paragraphs) if t == section else ()) for t in titles)
    return Generated(sections, tuple(clarifications))


def checked(section, *paragraphs, **kwargs):
    return fidelity.check_result(generated(section, *paragraphs, **kwargs), SOURCES)


def kept(result, section=SOZIAL):
    return [p.text for s in result.sections if s.title == section for p in s.paragraphs]


def items_for(result, section):
    return [c.text for c in result.clarifications if c.section == section]


# ---- references that do not point into the notes ----


def test_a_paragraph_that_quotes_the_notes_stays():
    good = paragraph("Lebt mit dem Ehemann.", "Patientin lebt mit Ehemann in einer Etagenwohnung")

    assert kept(checked(SOZIAL, good)) == ["Lebt mit dem Ehemann."]


def test_a_paragraph_whose_quote_is_not_in_the_notes_is_dropped_and_the_gap_is_named():
    invented = paragraph("Raucht seit 20 Jahren.", "Raucht seit 20 Jahren")

    result = checked(SOZIAL, invented)

    assert kept(result) == []
    [item] = items_for(result, SOZIAL)
    assert "Notizen" in item


def test_a_paragraph_without_any_reference_is_dropped():
    result = checked(SOZIAL, paragraph("Lebt allein."))

    assert kept(result) == []
    assert len(items_for(result, SOZIAL)) == 1


def test_one_quote_outside_the_notes_drops_the_paragraph_even_when_another_is_inside():
    mixed = paragraph(
        "Lebt mit dem Ehemann und arbeitet nicht.",
        "Patientin lebt mit Ehemann",
        "arbeitet nicht mehr",
    )

    assert kept(checked(SOZIAL, mixed)) == []


def test_a_quote_matches_across_line_breaks_and_repeated_spaces_in_the_notes():
    notes = "Patientin lebt mit\nEhemann   in einer Etagenwohnung."
    good = paragraph("Lebt mit dem Ehemann.", "lebt mit Ehemann in einer Etagenwohnung")

    result = fidelity.check_result(generated(SOZIAL, good), {"notes": notes})

    assert kept(result) == ["Lebt mit dem Ehemann."]


def test_a_reference_to_a_source_the_encounter_does_not_have_is_dropped():
    background = Paragraph("Lebt allein.", "", (InputReference("encounter-3", "Lebt allein"),))

    assert kept(checked(SOZIAL, background)) == []


def test_the_other_paragraphs_of_the_section_stay_when_one_is_dropped():
    good = paragraph("Lebt mit dem Ehemann.", "lebt mit Ehemann")
    bad = paragraph("Hat vier Geschwister.", "vier Geschwister")

    result = checked(SOZIAL, good, bad)

    assert kept(result) == ["Lebt mit dem Ehemann."]
    assert len(items_for(result, SOZIAL)) == 1


def test_several_dropped_paragraphs_of_one_section_give_one_item_each_reason_once():
    bad = [paragraph("A.", "nicht da"), paragraph("B.", "auch nicht da")]

    result = checked(SOZIAL, *bad)

    assert len(items_for(result, SOZIAL)) == 1


# ---- a section the notes do not support ----


def test_a_section_without_paragraphs_gets_a_clarification_item():
    result = checked(SOZIAL)

    for title in ASSESSMENT_SECTIONS:
        assert len(items_for(result, title)) == 1
        assert kept(result, title) == []


def test_a_section_the_model_already_flagged_gets_no_second_item():
    flagged = Clarification(SOZIAL, "Die Notizen enthalten keine Sozialanamnese.")

    result = checked(SOZIAL, clarifications=[flagged])

    assert items_for(result, SOZIAL) == [flagged.text]


def test_clarification_items_of_the_model_are_kept_in_order_and_ours_follow():
    first = Clarification(FRUEHER, "Wann war die Operation?")

    result = checked(SOZIAL, clarifications=[first])

    assert result.clarifications[0] == first


def test_a_supported_section_gets_no_item():
    good = paragraph("Lebt mit dem Ehemann.", "lebt mit Ehemann")

    assert items_for(checked(SOZIAL, good), SOZIAL) == []


def test_the_check_runs_for_the_visit_sections_as_well():
    good = paragraph("Zwei erwachsene Kinder.", "zwei erwachsene Kinder")
    visit = generated(VISIT_SECTIONS[0], good, kind="visit")

    result = fidelity.check_result(visit, SOURCES)

    assert kept(result, VISIT_SECTIONS[0]) == ["Zwei erwachsene Kinder."]
    assert len(items_for(result, VISIT_SECTIONS[1])) == 1


# ---- numbers: no dose, duration or score the notes do not give ----


def test_a_number_the_quoted_passage_does_not_contain_drops_the_paragraph():
    converted = paragraph("Ibuprofen 0,4 g bei Bedarf.", "Ibuprofen 400 mg bei Bedarf", heading="")

    result = checked(THERAPIE, converted)

    assert kept(result, THERAPIE) == []
    [item] = items_for(result, THERAPIE)
    assert "0,4" in item


def test_a_dose_the_notes_give_is_reproduced():
    same = paragraph("Ibuprofen 400 mg bei Bedarf.", "Ibuprofen 400 mg bei Bedarf")

    assert kept(checked(THERAPIE, same), THERAPIE) == ["Ibuprofen 400 mg bei Bedarf."]


def test_a_summed_or_invented_score_is_dropped():
    total = paragraph("NRS 6, im Mittel 8 Punkte.", "NRS 6 im Mittel")

    assert kept(checked(SCHMERZ, total), SCHMERZ) == []


def test_number_words_and_digits_are_the_same_number():
    spelled = paragraph(
        "Seit vierzehn Monaten tiefer Rückenschmerz, bis zu zwei Tabletten täglich.",
        "Seit 14 Monaten tiefer Rückenschmerz",
        "bis zu 2 Tabletten täglich",
    )
    assert kept(checked(SCHMERZ, spelled), SCHMERZ)
    twice = paragraph("Bis zu zweimal täglich.", "bis zu 2 Tabletten täglich")
    assert kept(checked(THERAPIE, twice), THERAPIE) == ["Bis zu zweimal täglich."]


def test_a_number_word_the_quote_does_not_give_is_dropped():
    invented = paragraph("Bis zu drei Tabletten täglich.", "bis zu 2 Tabletten täglich")

    assert kept(checked(THERAPIE, invented), THERAPIE) == []


def test_dates_and_time_windows_stay_when_the_quote_has_them():
    notes = "Vorbefund MRT vom 12.03.2024, seit dem Sommer schlechter."
    dated = paragraph("MRT am 12.03.2024.", "MRT vom 12.03.2024")

    assert kept(fidelity.check_result(generated(FRUEHER, dated), {"notes": notes}), FRUEHER)


def test_a_date_that_is_not_in_the_quote_is_dropped():
    notes = "MRT im Frühjahr."
    dated = paragraph("MRT am 12.03.2024.", "MRT im Frühjahr")

    assert kept(fidelity.check_result(generated(FRUEHER, dated), {"notes": notes}), FRUEHER) == []


def test_a_season_or_month_the_quote_does_not_give_is_dropped():
    notes = "Beginn des Schmerzes vor einiger Zeit."
    seasonal = paragraph("Beginn im Frühjahr.", "Beginn des Schmerzes vor einiger Zeit")

    assert (
        kept(fidelity.check_result(generated(SCHMERZ, seasonal), {"notes": notes}), SCHMERZ) == []
    )


# ---- terms that carry a clinical judgement the physician did not make ----

JUDGEMENTS = [
    ("Hauptschmerz", "Der Rückenschmerz ist der Hauptschmerz."),
    ("im Vordergrund", "Der Rückenschmerz steht im Vordergrund."),
    ("Verdacht", "Verdacht auf eine Radikulopathie."),
    ("zurückzuführen", "Der Schmerz ist auf den Bandscheibenvorfall zurückzuführen."),
    ("indiziert", "Die stationäre Therapie ist indiziert."),
    ("empfohlen", "Eine Psychotherapie wird empfohlen."),
    ("unauffällig", "Neurologisch unauffällig."),
    ("Wechselwirkung", "Eine Wechselwirkung mit Ibuprofen ist möglich."),
    ("vollständig", "Die Angaben sind vollständig."),
    ("geprüft", "Vom Arzt geprüft."),
    ("freigegeben", "Der Entwurf ist freigegeben."),
]


@pytest.mark.parametrize(("term", "text"), JUDGEMENTS)
def test_a_judgement_the_quoted_passage_does_not_make_drops_the_paragraph(term, text):
    result = checked(SCHMERZ, paragraph(text, "Seit 14 Monaten tiefer Rückenschmerz"))

    assert kept(result, SCHMERZ) == []
    [item] = items_for(result, SCHMERZ)
    assert term in item


@pytest.mark.parametrize(("term", "text"), JUDGEMENTS)
def test_the_same_term_stays_when_the_physician_wrote_it(term, text):
    notes = f"Seit 14 Monaten tiefer Rückenschmerz. {term} so notiert."
    quote = f"{term} so notiert"
    # The paragraph's numbers come from the first quote; only the term is under test.
    ok = paragraph(text, "Seit 14 Monaten tiefer Rückenschmerz", quote)

    result = fidelity.check_result(generated(SCHMERZ, ok), {"notes": notes})

    assert kept(result, SCHMERZ) == [text]


def test_a_pain_block_is_not_called_the_main_pain_unless_the_physician_said_so():
    named = "Einschätzung: Knieschmerz ist der Hauptschmerz."
    notes = f"Linkes Knie, seit 5 Jahren. Rechte Schulter. {named}"
    knee = paragraph(
        "Seit 5 Jahren, Hauptschmerz.",
        "Linkes Knie, seit 5 Jahren",
        "Knieschmerz ist der Hauptschmerz",
        heading="Linkes Knie",
    )
    shoulder = paragraph("Rechte Schulter, Hauptschmerz.", "Rechte Schulter", heading="Schulter")

    result = fidelity.check_result(generated(SCHMERZ, knee, shoulder), {"notes": notes})

    assert [p.heading for s in result.sections for p in s.paragraphs] == ["Linkes Knie"]


def test_a_heading_is_held_to_the_same_rules_as_the_text():
    notes = "Linkes Knie seit 5 Jahren."
    ranked = paragraph("Seit 5 Jahren.", "Linkes Knie seit 5 Jahren", heading="Hauptschmerz Knie")

    assert kept(fidelity.check_result(generated(SCHMERZ, ranked), {"notes": notes}), SCHMERZ) == []


# ---- provenance: patient report, prior finding, physician finding, unknown ----


def test_a_report_of_the_patient_is_worded_so_only_when_the_notes_say_so():
    notes = "Die Patientin berichtet, der Schmerz strahle nicht aus."
    said = paragraph(
        "Nach Angabe der Patientin keine Ausstrahlung.",
        "Die Patientin berichtet, der Schmerz strahle nicht aus",
    )
    unsaid = paragraph(
        "Nach Angabe der Patientin keine Ausstrahlung.", "der Schmerz strahle nicht aus"
    )

    assert kept(fidelity.check_result(generated(SCHMERZ, said), {"notes": notes}), SCHMERZ)
    assert kept(fidelity.check_result(generated(SCHMERZ, unsaid), {"notes": notes}), SCHMERZ) == []


def test_a_prior_finding_is_worded_so_only_when_the_notes_say_so():
    notes = "MRT 03/2024 laut Arztbrief: keine Wurzelkompression. Befund: Druckschmerz L4."
    prior = paragraph(
        "Vorbefund, MRT 03/2024: keine Wurzelkompression.", "MRT 03/2024 laut Arztbrief"
    )
    own = paragraph("Vorbefund: Druckschmerz L4.", "Druckschmerz L4")

    assert kept(fidelity.check_result(generated(FRUEHER, prior), {"notes": notes}), FRUEHER)
    assert kept(fidelity.check_result(generated(BEFUND, own), {"notes": notes}), BEFUND) == []


def test_a_finding_is_not_worded_as_the_physicians_own_unless_the_notes_say_so():
    notes = "Druckschmerz paravertebral L4."
    own = paragraph(
        "Eigener Befund: Druckschmerz paravertebral L4.", "Druckschmerz paravertebral L4"
    )

    assert kept(fidelity.check_result(generated(BEFUND, own), {"notes": notes}), BEFUND) == []


def test_a_statement_without_a_source_stays_without_one():
    plain = paragraph("Druckschmerz paravertebral L4.", "Druckschmerz paravertebral L4")

    result = fidelity.check_result(
        generated(BEFUND, plain), {"notes": "Druckschmerz paravertebral L4."}
    )

    assert kept(result, BEFUND) == ["Druckschmerz paravertebral L4."]


# ---- a contradiction the model flagged is not settled by one of its sides ----

TRAMADOL_NOTES = (
    "Tramadol retard 50 mg zweimal täglich, an anderer Stelle steht 100 mg zweimal täglich."
)
CONFLICT = Clarification(THERAPIE, "Die Angaben zu Tramadol widersprechen sich: 50 mg oder 100 mg.")


def tramadol(text, *quotes):
    result = generated(THERAPIE, paragraph(text, *quotes), clarifications=[CONFLICT])
    return fidelity.check_result(result, {"notes": TRAMADOL_NOTES})


def test_a_paragraph_that_names_one_side_of_a_flagged_contradiction_is_dropped():
    result = tramadol("Tramadol retard 100 mg zweimal täglich.", "steht 100 mg zweimal täglich")

    assert kept(result, THERAPIE) == []
    assert "widersprechen" in items_for(result, THERAPIE)[-1]


def test_a_paragraph_that_names_both_sides_or_neither_stays():
    both = tramadol(
        "Tramadol retard zweimal täglich, 50 mg oder 100 mg.",
        "Tramadol retard 50 mg zweimal täglich, an anderer Stelle steht 100 mg zweimal täglich",
    )
    neither = tramadol(
        "Tramadol retard zweimal täglich, Dosis unklar.", "Tramadol retard 50 mg zweimal täglich"
    )

    assert kept(both, THERAPIE)
    assert kept(neither, THERAPIE)


def test_a_dose_in_another_section_is_not_held_to_a_contradiction_of_this_one():
    notes = TRAMADOL_NOTES + " Ibuprofen 400 mg."
    other = paragraph("Ibuprofen 400 mg.", "Ibuprofen 400 mg")

    result = fidelity.check_result(
        generated(FRUEHER, other, clarifications=[CONFLICT]), {"notes": notes}
    )

    assert kept(result, FRUEHER) == ["Ibuprofen 400 mg."]


def test_a_flagged_question_without_two_measures_holds_no_paragraph_back():
    asked = Clarification(THERAPIE, "Welche Dosis gilt für Tramadol?")
    result = generated(
        THERAPIE, paragraph("Tramadol 100 mg.", "steht 100 mg"), clarifications=[asked]
    )

    assert kept(fidelity.check_result(result, {"notes": TRAMADOL_NOTES}), THERAPIE) == [
        "Tramadol 100 mg."
    ]


# ---- the check is pure and leaves a good result as it is ----


def test_a_result_that_passes_is_returned_unchanged():
    good = paragraph("Lebt mit dem Ehemann.", "lebt mit Ehemann")
    flagged = [Clarification(t, "Frage?") for t in ASSESSMENT_SECTIONS if t != SOZIAL]
    result = generated(SOZIAL, good, clarifications=flagged)

    assert fidelity.check_result(result, SOURCES) == result


def test_the_input_is_not_changed():
    bad = paragraph("Lebt allein.", "nicht da")
    original = generated(SOZIAL, bad)

    fidelity.check_result(original, SOURCES)

    assert drafts.section_text(original.sections[0]) == "Lebt allein."
    assert original.clarifications == ()

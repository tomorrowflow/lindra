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
from lindra.cast import ASSESSMENT_SECTIONS, UNASSIGNED_PAIN, VISIT_SECTIONS, Clarification
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
    notes = f"Seit 14 Monaten tiefer Rückenschmerz. {text}"
    ok = paragraph(text, text.removesuffix("."))

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
        "Nach Angabe der Patientin strahlt der Schmerz nicht aus.",
        "Die Patientin berichtet, der Schmerz strahle nicht aus",
    )
    unsaid = paragraph(
        "Nach Angabe der Patientin strahlt der Schmerz nicht aus.", "der Schmerz strahle nicht aus"
    )

    assert kept(fidelity.check_result(generated(SCHMERZ, said), {"notes": notes}), SCHMERZ)
    assert kept(fidelity.check_result(generated(SCHMERZ, unsaid), {"notes": notes}), SCHMERZ) == []


def test_a_prior_finding_is_worded_so_only_when_the_notes_say_so():
    notes = "MRT 03/2024 laut Arztbrief: keine Wurzelkompression. Befund: Druckschmerz L4."
    prior = paragraph(
        "Vorbefund, MRT 03/2024: keine Wurzelkompression.",
        "MRT 03/2024 laut Arztbrief: keine Wurzelkompression",
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


# Two sentences that say nothing about a disagreement: only the model's own item flags it.
SPLIT_NOTES = "Tramadol retard 50 mg zweimal täglich. Tramadol retard 100 mg zweimal täglich."


def flagged(text, *quotes):
    result = generated(THERAPIE, paragraph(text, *quotes), clarifications=[CONFLICT])
    return fidelity.check_result(result, {"notes": SPLIT_NOTES})


def test_a_paragraph_that_names_one_side_of_a_flagged_contradiction_is_dropped():
    result = flagged("Tramadol retard 100 mg zweimal täglich.", "Tramadol retard 100 mg zweimal")

    assert kept(result, THERAPIE) == []
    assert "widersprechen" in items_for(result, THERAPIE)[-1]


def test_a_paragraph_that_names_both_sides_or_neither_stays():
    both = flagged(
        "Tramadol retard zweimal täglich, 50 mg oder 100 mg.",
        "Tramadol retard 50 mg zweimal täglich",
        "Tramadol retard 100 mg zweimal täglich",
    )
    neither = flagged(
        "Tramadol retard zweimal täglich, Dosis unklar.", "Tramadol retard 50 mg zweimal täglich"
    )

    assert kept(both, THERAPIE)
    assert kept(neither, THERAPIE)


def test_a_dose_the_contradiction_does_not_concern_stays_in_any_section():
    notes = TRAMADOL_NOTES + " Ibuprofen 400 mg."
    other = paragraph("Ibuprofen 400 mg.", "Ibuprofen 400 mg")

    result = fidelity.check_result(
        generated(FRUEHER, other, clarifications=[CONFLICT]), {"notes": notes}
    )

    assert kept(result, FRUEHER) == ["Ibuprofen 400 mg."]


def test_a_flagged_question_without_two_measures_holds_no_paragraph_back():
    asked = Clarification(THERAPIE, "Welche Dosis gilt für Tramadol?")
    result = generated(
        THERAPIE, paragraph("Tramadol 100 mg.", "Tramadol retard 100 mg"), clarifications=[asked]
    )

    assert kept(fidelity.check_result(result, {"notes": SPLIT_NOTES}), THERAPIE) == [
        "Tramadol 100 mg."
    ]


# ---- a reference is a passage, and the units are part of the numbers ----


def test_a_quote_that_is_most_of_the_notes_is_not_a_passage_and_drops_the_paragraph():
    notes = "Satz eins. " * 60 + "Hauptschmerz ist das Knie."
    sweeping = paragraph("Das Knie ist der Hauptschmerz.", notes)

    result = fidelity.check_result(generated(SCHMERZ, sweeping), {"notes": notes})

    assert kept(result, SCHMERZ) == []


def test_a_unit_the_quote_does_not_give_drops_the_paragraph():
    wrong = paragraph("Ibuprofen 400 g bei Bedarf.", "Ibuprofen 400 mg bei Bedarf")

    assert kept(checked(THERAPIE, wrong), THERAPIE) == []


def test_a_unit_in_another_inflection_is_the_same_unit():
    notes = "Seit 3 Monaten Schmerzen."
    said = paragraph("Seit 3 Monate Schmerzen.", "Seit 3 Monaten Schmerzen")

    assert kept(fidelity.check_result(generated(SCHMERZ, said), {"notes": notes}), SCHMERZ)


@pytest.mark.parametrize(
    "text",
    [
        "Die Aufnahme erfolgt wegen des Sturzes.",
        "Aufgrund des Sturzes ist die Aufnahme nötig.",
        "Schlafstörung als Folge.",
        "Die Begründung ist der Sturz.",
        "Das Mittel ist wirkungslos.",
    ],
)
def test_causal_and_justifying_wordings_need_the_physicians_words(text):
    result = checked(PLAN, paragraph(text, "Ibuprofen 400 mg bei Bedarf"))

    assert kept(result, PLAN) == []


def test_a_contradiction_flagged_in_one_section_holds_back_the_measure_in_any_section():
    notes = TRAMADOL_NOTES
    elsewhere = paragraph("Tramadol 100 mg.", "steht 100 mg zweimal täglich")

    result = fidelity.check_result(
        generated(FRUEHER, elsewhere, clarifications=[CONFLICT]), {"notes": notes}
    )

    assert kept(result, FRUEHER) == []


# ---- every word has to come from the quoted passage ----

BACK_NOTES = "Seit 14 Monaten tiefer Rückenschmerz, belastungsabhängig. Kinder leben in der Nähe."


def back(text, *quotes, heading="", section=SCHMERZ, notes=BACK_NOTES):
    result = generated(section, paragraph(text, *quotes, heading=heading))
    return fidelity.check_result(result, {"notes": notes})


@pytest.mark.parametrize(
    "text",
    [
        "Fibromyalgie.",
        "Tiefer Rückenschmerz, Fibromyalgie.",
        "Radikulopathie bei tiefem Rückenschmerz.",
        "Tiefer Rückenschmerz mit Bandscheibenprotrusion.",
    ],
)
def test_a_word_the_quoted_passage_does_not_contain_drops_the_paragraph(text):
    result = back(text, "Seit 14 Monaten tiefer Rückenschmerz")

    assert kept(result, SCHMERZ) == []
    [item] = items_for(result, SCHMERZ)
    assert "Notizen" in item and "das Wort «" in item


def test_the_item_for_an_ungrounded_word_names_the_word():
    result = back("Fibromyalgie.", "Seit 14 Monaten tiefer Rückenschmerz")

    assert "«Fibromyalgie»" in items_for(result, SCHMERZ)[0]


@pytest.mark.parametrize(
    "text",
    [
        "Seit 14 Monaten tiefer Rückenschmerz.",
        "Tiefe Rückenschmerzen seit 14 Monaten, belastungsabhängig.",
        "Rückenschmerz, belastungsabhängig, seit vierzehn Monaten.",
        "Die Kinder leben in der Nähe.",
        "Kindern in der Nähe.",
        "Schmerz seit 14 Monaten.",
    ],
)
def test_inflections_compounds_and_function_words_do_not_drop_a_paragraph(text):
    quotes = (
        "Seit 14 Monaten tiefer Rückenschmerz, belastungsabhängig",
        "Kinder leben in der Nähe",
    )

    assert kept(back(text, *quotes), SCHMERZ) == [text]


@pytest.mark.parametrize(
    "text",
    [
        "Schulterarthrose rechts.",
        "Kniegelenkarthrose links.",
        "Schmerzchronifizierung seit Jahren.",
        "Rückenschmerz bei PNP.",
        "HWS-Syndrom links.",
        "Ménièresche Schwindelattacken.",
    ],
)
def test_a_longer_compound_or_an_abbreviation_the_quote_does_not_hold_is_dropped(text):
    notes = "Schulter rechts, Knie links, Schmerzen seit Jahren, Rückenschmerz."
    quotes = ("Schulter rechts, Knie links", "Schmerzen seit Jahren", "Rückenschmerz")

    result = fidelity.check_result(generated(SCHMERZ, paragraph(text, *quotes)), {"notes": notes})

    assert kept(result, SCHMERZ) == []


def test_a_part_of_a_compound_the_quote_holds_is_supported():
    result = back(
        "Schmerz im Rücken, belastungsabhängig.", "tiefer Rückenschmerz, belastungsabhängig"
    )

    assert kept(result, SCHMERZ)


def test_an_abbreviation_the_quote_holds_is_supported():
    notes = "Befund MRT der HWS, NRS 6."
    result = fidelity.check_result(
        generated(BEFUND, paragraph("MRT der HWS, NRS 6.", "MRT der HWS, NRS 6")), {"notes": notes}
    )

    assert kept(result, BEFUND) == ["MRT der HWS, NRS 6."]


@pytest.mark.parametrize(
    "text",
    [
        "Schmerz ohne Ausstrahlung.",
        "Keine Ausstrahlung des Schmerzes.",
        "Der Schmerz strahlt nicht aus.",
    ],
)
def test_a_negation_the_quote_does_not_make_drops_the_paragraph(text):
    notes = "Der Schmerz strahlt ins Bein aus."
    result = fidelity.check_result(
        generated(SCHMERZ, paragraph(text, "Der Schmerz strahlt ins Bein aus")), {"notes": notes}
    )

    assert kept(result, SCHMERZ) == []
    assert "verneint" in items_for(result, SCHMERZ)[0]


def test_a_negation_the_paragraph_leaves_out_drops_it_too():
    notes = "Der Schmerz strahlt nicht ins Bein aus."
    result = fidelity.check_result(
        generated(SCHMERZ, paragraph("Der Schmerz strahlt ins Bein aus.", notes.rstrip("."))),
        {"notes": notes},
    )

    assert kept(result, SCHMERZ) == []


def test_a_negation_the_quote_makes_stays():
    notes = "Der Schmerz strahlt nicht ins Bein aus."
    said = paragraph("Der Schmerz strahlt nicht aus.", notes.rstrip("."))

    assert kept(fidelity.check_result(generated(SCHMERZ, said), {"notes": notes}), SCHMERZ)


def test_an_abbreviation_does_not_end_a_sentence_of_the_notes():
    notes = "Tramadol retard 50 mg zweimal täglich, ggf. 100 mg zweimal täglich."
    one = alone("Tramadol retard 50 mg zweimal täglich.", notes.rstrip("."), notes=notes)

    assert kept(one, THERAPIE) == []


def test_an_alternative_in_the_notes_is_an_uncertainty():
    notes = "Pregabalin 75 mg abends, alternativ 150 mg."
    cut = alone("Pregabalin 75 mg abends.", "Pregabalin 75 mg abends", notes=notes)

    assert kept(cut, THERAPIE) == []


def test_a_gap_word_that_only_says_something_is_unclear_is_allowed():
    notes = "Tramadol retard 50 mg zweimal täglich, an anderer Stelle steht 100 mg zweimal täglich."
    whole = notes[:-1]
    said = paragraph("Tramadol retard zweimal täglich, Dosis unklar.", whole)

    result = fidelity.check_result(generated(THERAPIE, said), {"notes": notes})

    assert kept(result, THERAPIE) == ["Tramadol retard zweimal täglich, Dosis unklar."]


def test_a_pain_heading_is_grounded_but_the_forms_own_headings_are_not():
    own = back(
        "Seit 14 Monaten.",
        "Seit 14 Monaten tiefer Rückenschmerz",
        heading="Fibromyalgie",
        section=SCHMERZ,
    )
    form = back(
        "Seit 14 Monaten tiefer Rückenschmerz.",
        "Seit 14 Monaten tiefer Rückenschmerz",
        heading="Aktuelle Medikation",
        section=THERAPIE,
    )
    unassigned = back(
        "Seit 14 Monaten tiefer Rückenschmerz.",
        "Seit 14 Monaten tiefer Rückenschmerz",
        heading=UNASSIGNED_PAIN,
    )

    assert kept(own, SCHMERZ) == []
    assert kept(form, THERAPIE)
    assert kept(unassigned, SCHMERZ)


def test_a_provenance_wording_the_quote_licenses_is_not_a_word_to_ground():
    notes = "Die Patientin berichtet, der Schmerz strahle nicht ins Bein aus."
    said = paragraph(
        "Nach Angabe der Patientin strahlt der Schmerz nicht ins Bein aus.",
        notes.removesuffix("."),
    )

    assert kept(fidelity.check_result(generated(SCHMERZ, said), {"notes": notes}), SCHMERZ)


# ---- an uncertainty or contradiction in the notes cannot be cut away ----

TRAMADOL_SENTENCE = TRAMADOL_NOTES.removesuffix(".")


def alone(text, *quotes, notes=TRAMADOL_NOTES, section=THERAPIE):
    """A result without any clarification item of the model's own."""
    return fidelity.check_result(generated(section, paragraph(text, *quotes)), {"notes": notes})


def test_a_paragraph_that_quotes_one_dose_of_a_contradictory_sentence_is_dropped_without_an_item():
    for text, quote in (
        ("Tramadol retard 100 mg zweimal täglich.", "steht 100 mg zweimal täglich"),
        ("Tramadol retard 50 mg zweimal täglich.", "Tramadol retard 50 mg zweimal täglich"),
    ):
        result = alone(text, quote)

        assert kept(result, THERAPIE) == []
        assert "Unsicherheit oder einen Widerspruch" in items_for(result, THERAPIE)[0]


def test_a_paragraph_that_quotes_the_whole_sentence_but_names_one_dose_is_dropped():
    result = alone("Tramadol retard 100 mg zweimal täglich.", TRAMADOL_SENTENCE)

    assert kept(result, THERAPIE) == []
    assert "50mg" in items_for(result, THERAPIE)[0]


def test_a_paragraph_that_quotes_the_whole_sentence_and_names_both_doses_or_none_stays():
    both = alone("Tramadol retard zweimal täglich, 50 mg oder 100 mg.", TRAMADOL_SENTENCE)
    none = alone("Tramadol retard zweimal täglich, Dosis unklar.", TRAMADOL_SENTENCE)

    assert kept(both, THERAPIE)
    assert kept(none, THERAPIE)


def test_two_drugs_in_one_sentence_are_not_a_contradiction():
    notes = "Ibuprofen 400 mg bei Bedarf, Metamizol 500 mg bei Bedarf."
    one = alone("Ibuprofen 400 mg bei Bedarf.", "Ibuprofen 400 mg bei Bedarf", notes=notes)

    assert kept(one, THERAPIE) == ["Ibuprofen 400 mg bei Bedarf."]


def test_a_hedge_the_quote_cuts_off_drops_the_paragraph():
    notes = "Chronischer Schulterschmerz seit dem Sommer, vielleicht schon länger."
    cut = alone("Schulterschmerz seit dem Sommer.", "Schulterschmerz seit dem Sommer", notes=notes)

    assert kept(cut, THERAPIE) == []
    assert "«vielleicht»" in items_for(cut, THERAPIE)[0]


def test_a_hedge_the_quote_keeps_has_to_show_in_the_paragraph():
    notes = "Chronischer Schulterschmerz seit dem Sommer, vielleicht schon länger."
    whole = notes.removesuffix(".")
    hidden = alone("Schulterschmerz seit dem Sommer.", whole, notes=notes, section=SCHMERZ)
    shown = alone(
        "Schulterschmerz seit dem Sommer, Beginn unklar.", whole, notes=notes, section=SCHMERZ
    )
    worded = alone(
        "Schulterschmerz seit dem Sommer, vielleicht schon länger.",
        whole,
        notes=notes,
        section=SCHMERZ,
    )

    assert kept(hidden, SCHMERZ) == []
    assert kept(shown, SCHMERZ)
    assert kept(worded, SCHMERZ)


def test_a_sentence_without_an_uncertainty_can_be_quoted_in_part():
    notes = "Seit 14 Monaten tiefer Rückenschmerz, belastungsabhängig."
    part = alone("Tiefer Rückenschmerz.", "tiefer Rückenschmerz", notes=notes, section=SCHMERZ)

    assert kept(part, SCHMERZ) == ["Tiefer Rückenschmerz."]


# ---- words, numbers and denials stay with the words they belong to in the quote ----


def bound(text, notes, section=THERAPIE):
    """A paragraph that quotes the whole of the notes, which is short enough for a quote."""
    said = paragraph(text, notes.removesuffix("."))
    return fidelity.check_result(generated(section, said), {"notes": notes})


TWO_DRUGS = "Ibuprofen 400 mg bei Bedarf, Metamizol 500 mg bei Bedarf."


@pytest.mark.parametrize(
    "text",
    [
        "Ibuprofen 500 mg bei Bedarf.",
        "Metamizol 400 mg bei Bedarf.",
        "Ibuprofen 500 mg bei Bedarf, Metamizol 400 mg bei Bedarf.",
    ],
)
def test_a_dose_moved_to_another_drug_of_the_same_quote_drops_the_paragraph(text):
    result = bound(text, TWO_DRUGS)

    assert kept(result, THERAPIE) == []
    assert "nicht zusammen" in items_for(result, THERAPIE)[0]


@pytest.mark.parametrize(
    "text",
    [
        "Ibuprofen 400 mg bei Bedarf.",
        "Metamizol 500 mg bei Bedarf.",
        "Metamizol 500 mg bei Bedarf, Ibuprofen 400 mg bei Bedarf.",
        "Ibuprofen 400 mg bei Bedarf, Metamizol 500 mg bei Bedarf.",
    ],
)
def test_a_dose_with_its_own_drug_stays_whatever_the_order(text):
    assert kept(bound(text, TWO_DRUGS), THERAPIE) == [text]


def test_a_dose_moved_between_two_drugs_without_any_punctuation_is_dropped_too():
    notes = "Ibuprofen 400 mg Metamizol 500 mg bei Bedarf."

    assert kept(bound("Ibuprofen 500 mg Metamizol 400 mg bei Bedarf.", notes), THERAPIE) == []
    assert kept(bound("Metamizol 500 mg Ibuprofen 400 mg bei Bedarf.", notes), THERAPIE)
    assert kept(bound("Ibuprofen 400 mg Metamizol 500 mg bei Bedarf.", notes), THERAPIE)


def test_a_dose_moved_across_an_und_is_dropped_too():
    notes = "Ibuprofen 400 mg und Metamizol 500 mg."

    assert kept(bound("Ibuprofen 500 mg und Metamizol 400 mg.", notes), THERAPIE) == []
    assert kept(bound("Ibuprofen 400 mg und Metamizol 500 mg.", notes), THERAPIE)


def test_a_denial_moved_to_another_word_of_the_quote_drops_the_paragraph():
    notes = "Kein Nikotin, Alkohol gelegentlich."

    assert kept(bound("Nikotin gelegentlich, kein Alkohol.", notes, INTERNIST), INTERNIST) == []
    assert kept(bound("Kein Nikotin, Alkohol gelegentlich.", notes, INTERNIST), INTERNIST)


def test_an_attribute_moved_to_another_part_of_the_quote_drops_the_paragraph():
    notes = "Knie links Erguss gering, Füße Hypästhesie strumpfförmig."

    assert kept(bound("Füße: Erguss gering.", notes, BEFUND), BEFUND) == []
    assert kept(bound("Füße: strumpfförmige Hypästhesie.", notes, BEFUND), BEFUND)


def test_a_side_moved_to_another_part_of_the_quote_drops_the_paragraph():
    notes = "Schulter rechts schmerzhaft, Knie links frei."

    assert kept(bound("Schulter links schmerzhaft.", notes, BEFUND), BEFUND) == []
    assert kept(bound("Knie links frei.", notes, BEFUND), BEFUND)


def test_a_decimal_and_a_date_are_not_split_into_clauses():
    notes = "Am 12.03.2024 Ibuprofen 0,5 g bei Bedarf."

    assert kept(bound("Ibuprofen 0,5 g bei Bedarf, am 12.03.2024.", notes), THERAPIE)


def test_a_clause_of_only_function_words_or_gap_words_needs_no_clause_of_the_quote():
    notes = "Tramadol retard 50 mg zweimal täglich, an anderer Stelle steht 100 mg zweimal täglich."
    said = paragraph("Tramadol retard zweimal täglich, Dosis unklar.", notes.removesuffix("."))

    assert kept(fidelity.check_result(generated(THERAPIE, said), {"notes": notes}), THERAPIE)


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

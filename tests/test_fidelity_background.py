"""The result check for a visit, which may quote its background as well as its notes (ADR 0010).

A reference names its source: `notes` for today's notes, `encounter:<id>` for the accepted
draft of an earlier encounter. The same rules as for the notes hold for a historical quote:
it has to be in the draft it names, and the paragraph has to say what the quote says.
What a visit finds, judges and agrees today comes from today's notes only. A contradiction
between the two sources is never settled by the paragraph: it stays a clarification item that
names both statements.
"""

from lindra import drafts, fidelity
from lindra.cast import VISIT_SECTIONS, Clarification
from lindra.drafts import Generated, InputReference, Paragraph, Section

VERLAUF, BEFUNDE, EINSCHAETZUNG, VORGEHEN = VISIT_SECTIONS
TODAY_ONLY = frozenset({BEFUNDE, EINSCHAETZUNG, VORGEHEN})

ASSESSMENT = "encounter:1"
EARLIER_VISIT = "encounter:2"
NOTES = "Schmerz im Verlauf unverändert, NRS 5 bis 6. Nimmt kein Ibuprofen mehr seit dem 7.10."
BACKGROUND = {
    ASSESSMENT: (
        "Therapeutische Anamnese\nAktuelle Medikation\n"
        "Ibuprofen 400 mg bei Bedarf, bis zu zwei Tabletten täglich, Wirkung gering.\n\n"
        "Schmerzanamnese\nNach Angabe der Patientin strahlt der Schmerz nicht ins Bein aus."
    ),
    EARLIER_VISIT: "Verlauf seit letzter Visite\nSchlaf fünf Stunden.",
}
SOURCES = {"notes": NOTES, **BACKGROUND}

TODAY = "Schmerz im Verlauf unverändert, NRS 5 bis 6."
HISTORY = "Ibuprofen 400 mg bei Bedarf, bis zu zwei Tabletten täglich, Wirkung gering."


def paragraph(text, *references):
    return Paragraph(text, "", tuple(InputReference(s, q) for s, q in references))


def result(section, *paragraphs, clarifications=()):
    sections = tuple(Section(t, tuple(paragraphs) if t == section else ()) for t in VISIT_SECTIONS)
    return Generated(sections, tuple(clarifications))


def check(section, *paragraphs, sources=SOURCES, **kwargs):
    return fidelity.check_result(
        result(section, *paragraphs, **kwargs), sources, today_only=TODAY_ONLY
    )


def kept(checked, section=VERLAUF):
    return [p.text for s in checked.sections if s.title == section for p in s.paragraphs]


def items_for(checked, section):
    return [c.text for c in checked.clarifications if c.section == section]


# ---- a historical reference must hold ----


def test_a_paragraph_that_quotes_an_earlier_draft_stays():
    history = paragraph(f"Zuvor: {HISTORY}", (ASSESSMENT, HISTORY))

    assert kept(check(VERLAUF, history)) == [f"Zuvor: {HISTORY}"]


def test_a_quote_that_is_not_in_the_draft_it_names_is_dropped_and_the_gap_is_named():
    wrong_encounter = paragraph("Zuvor: Schlaf fünf Stunden.", (ASSESSMENT, "Schlaf fünf Stunden."))

    result = check(VERLAUF, wrong_encounter)

    assert kept(result) == []
    assert items_for(result, VERLAUF)


def test_a_reference_to_an_encounter_that_is_not_background_is_dropped():
    later_visit = paragraph("Zuvor: Schlaf fünf Stunden.", ("encounter:9", "Schlaf fünf Stunden."))

    assert kept(check(VERLAUF, later_visit)) == []


def test_the_numbers_of_a_historical_paragraph_have_to_be_in_its_quote():
    converted = paragraph("Zuvor: Ibuprofen 600 mg bei Bedarf.", (ASSESSMENT, HISTORY))

    assert kept(check(VERLAUF, converted)) == []


def test_a_word_the_historical_quote_does_not_hold_is_dropped():
    inferred = paragraph(
        "Zuvor: Ibuprofen bei Bedarf, Verdacht auf Magenreizung.", (ASSESSMENT, HISTORY)
    )

    assert kept(check(VERLAUF, inferred)) == []


def test_a_paragraph_that_draws_on_notes_and_background_stays_when_both_hold():
    both = paragraph(
        "Kein Ibuprofen mehr seit dem 7.10. Zuvor: Ibuprofen bei Bedarf.",
        ("notes", "Nimmt kein Ibuprofen mehr seit dem 7.10."),
        (ASSESSMENT, "Ibuprofen 400 mg bei Bedarf"),
    )

    # The number 400 does not appear in the paragraph, so nothing contradicts the quote.
    assert len(kept(check(VERLAUF, both))) == 1


def test_a_denial_in_a_historical_quote_cannot_be_turned_around():
    flipped = paragraph(
        "Zuvor strahlte der Schmerz ins Bein aus.",
        (ASSESSMENT, "Nach Angabe der Patientin strahlt der Schmerz nicht ins Bein aus."),
    )

    assert kept(check(VERLAUF, flipped)) == []


# ---- what is found, judged and agreed today comes from today's notes ----


def test_a_decision_that_rests_on_the_background_alone_is_dropped_with_its_reason():
    carried_over = paragraph(f"Zuvor: {HISTORY}", (ASSESSMENT, HISTORY))

    result = check(VORGEHEN, carried_over)

    assert kept(result, VORGEHEN) == []
    [item] = items_for(result, VORGEHEN)
    assert item == fidelity.BACKGROUND_ONLY


def test_the_findings_and_the_assessment_of_today_cannot_rest_on_the_background_alone_either():
    history = paragraph(f"Zuvor: {HISTORY}", (ASSESSMENT, HISTORY))

    for section in (BEFUNDE, EINSCHAETZUNG):
        assert kept(check(section, history), section) == []


def test_a_decision_that_quotes_today_s_notes_stays_even_with_a_historical_quote_beside_it():
    notes = "Vereinbart: Gehstrecke steigern."
    both = paragraph(
        "Gehstrecke steigern.",
        ("notes", "Vereinbart: Gehstrecke steigern"),
    )
    sources = {"notes": notes, **BACKGROUND}

    assert kept(check(VORGEHEN, both, sources=sources), VORGEHEN) == ["Gehstrecke steigern."]


def test_the_first_section_may_rest_on_the_background_alone():
    history = paragraph(f"Zuvor: {HISTORY}", (ASSESSMENT, HISTORY))

    assert len(kept(check(VERLAUF, history))) == 1


def test_without_today_only_sections_nothing_is_added_to_the_rules_of_the_notes():
    history = paragraph(f"Zuvor: {HISTORY}", (ASSESSMENT, HISTORY))

    plain = fidelity.check_result(result(VORGEHEN, history), SOURCES)

    assert kept(plain, VORGEHEN) == [f"Zuvor: {HISTORY}"]


# ---- contradictions between the background and today's notes ----

NOTES_RADIATES = "Heute berichtet sie von Ausstrahlung ins linke Bein."
CONTRADICTION = Clarification(
    VERLAUF,
    "Die Angaben widersprechen sich. Aufnahmeassessment: «strahlt der Schmerz nicht ins Bein "
    "aus». Notizen dieser Visite: «Ausstrahlung ins linke Bein». Welche gilt?",
)


def test_a_contradiction_item_of_the_model_stays_on_the_list_when_the_check_drops_nothing():
    good = paragraph(TODAY, ("notes", TODAY.removesuffix(".")))

    result = check(VERLAUF, good, clarifications=[CONTRADICTION])

    assert kept(result) == [TODAY]
    assert items_for(result, VERLAUF) == [CONTRADICTION.text]


def test_the_contradiction_item_is_not_repeated_when_a_paragraph_is_dropped():
    invented = paragraph("Raucht täglich.", ("notes", "Raucht täglich"))

    result = check(VERLAUF, invented, clarifications=[CONTRADICTION])

    assert items_for(result, VERLAUF).count(CONTRADICTION.text) == 1
    assert len(items_for(result, VERLAUF)) == 2


CONFLICTING_NOTES = "Ibuprofen 600 mg bei Bedarf, bis zu zwei Tabletten täglich."
DOSE_ITEM = Clarification(
    VERLAUF,
    "Aufnahmeassessment: Ibuprofen 400 mg, Notizen dieser Visite: Ibuprofen 600 mg. Die Angaben "
    "widersprechen sich: 400 mg oder 600 mg.",
)
DOSE_SOURCES = {"notes": CONFLICTING_NOTES, ASSESSMENT: BACKGROUND[ASSESSMENT]}


def test_a_paragraph_that_names_only_one_side_of_a_dose_contradiction_is_dropped():
    settled = paragraph("Ibuprofen 600 mg bei Bedarf.", ("notes", "Ibuprofen 600 mg bei Bedarf"))

    result = check(VERLAUF, settled, sources=DOSE_SOURCES, clarifications=[DOSE_ITEM])

    assert kept(result) == []
    assert any("400mg" in text and "600mg" in text for text in items_for(result, VERLAUF))


def test_a_historical_paragraph_that_names_only_the_other_side_is_dropped_too():
    settled = paragraph(f"Zuvor: {HISTORY}", (ASSESSMENT, HISTORY))

    result = check(VERLAUF, settled, sources=DOSE_SOURCES, clarifications=[DOSE_ITEM])

    assert kept(result) == []


def test_a_paragraph_that_names_both_sides_of_the_contradiction_stays():
    both = paragraph(
        "Ibuprofen bei Bedarf, 400 mg oder 600 mg.",
        ("notes", "Ibuprofen 600 mg bei Bedarf"),
        (ASSESSMENT, "Ibuprofen 400 mg bei Bedarf"),
    )

    result = check(VERLAUF, both, sources=DOSE_SOURCES, clarifications=[DOSE_ITEM])

    assert len(kept(result)) == 1
    assert DOSE_ITEM.text in items_for(result, VERLAUF)


def test_a_section_left_empty_gets_an_item_so_nothing_is_padded():
    result = check(VERLAUF)

    for section in VISIT_SECTIONS:
        assert items_for(result, section) == [fidelity.EMPTY_SECTION]
        assert kept(result, section) == []


# ---- the stored and the structural side ----


def test_the_structure_check_accepts_a_reference_to_an_earlier_encounter():
    raw = {
        "sections": [
            {
                "title": title,
                "paragraphs": (
                    [
                        {
                            "text": "Zuvor.",
                            "heading": "",
                            "references": [{"source": "encounter:12", "quote": "Zuvor."}],
                        }
                    ]
                    if title == VERLAUF
                    else []
                ),
            }
            for title in VISIT_SECTIONS
        ],
        "clarifications": [],
    }

    parsed = drafts.parse_generated(raw, "visit")

    reference = parsed.sections[0].paragraphs[0].references[0]
    assert reference.source == "encounter:12"
    assert reference.encounter_id == 12


def test_the_structure_check_refuses_a_reference_to_some_other_source():
    for source in ("encounter:", "encounter:x", "elsewhere", "", 5):
        raw = {
            "sections": [
                {
                    "title": title,
                    "paragraphs": (
                        [
                            {
                                "text": "Zuvor.",
                                "heading": "",
                                "references": [{"source": source, "quote": "Zuvor."}],
                            }
                        ]
                        if title == VERLAUF
                        else []
                    ),
                }
                for title in VISIT_SECTIONS
            ],
            "clarifications": [],
        }

        try:
            drafts.parse_generated(raw, "visit")
        except Exception as error:
            assert type(error).__name__ == "GenerationFailed"
        else:
            raise AssertionError(f"source {source!r} was accepted")


def test_where_a_paragraph_comes_from_depends_on_the_sources_of_its_references():
    assert drafts.origin_of(["notes"]) == "notes"
    assert drafts.origin_of(["encounter:3"]) == "background"
    assert drafts.origin_of(["notes", "encounter:3"]) == "notes_and_background"
    assert drafts.origin_of([]) == "hand"


def test_the_reason_a_proposal_is_outdated_names_what_moved():
    assert drafts.outdated_reason(notes=True, background=False) == (
        "Veraltet: Notizen seit diesem Vorschlag geändert"
    )
    assert drafts.outdated_reason(notes=False, background=True) == (
        "Veraltet: Hintergrund seit diesem Vorschlag geändert"
    )
    assert drafts.outdated_reason(notes=True, background=True) == (
        "Veraltet: Notizen und Hintergrund seit diesem Vorschlag geändert"
    )

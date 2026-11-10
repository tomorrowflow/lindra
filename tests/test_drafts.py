"""The rules between a draft and its proposal, as pure logic (ADR 0008, ADR 0010).

No storage and no model: values in, values out. The same rules are driven through the HTTP
API in `tests/test_review_api.py`; these tests pin the edge cases of each rule.
"""

import pytest

from lindra import drafts
from lindra.cast import ASSESSMENT_SECTIONS, VISIT_SECTIONS, Clarification
from lindra.drafts import Draft, Paragraph, Proposal, Section
from lindra.textmodel import GenerationFailed

SOZIAL, FRUEHER, THERAPIE = ASSESSMENT_SECTIONS[:3]


def result(**changes):
    """A model result with the seven sections, each with one paragraph."""
    raw = {
        "sections": [
            {
                "title": title,
                "paragraphs": [
                    {
                        "text": f"Text zu {title}.",
                        "heading": "",
                        "references": [{"source": "notes", "quote": "Satz"}],
                    }
                ],
            }
            for title in ASSESSMENT_SECTIONS
        ],
        "clarifications": [{"section": SOZIAL, "text": "Was ist mit dem Wohnort?"}],
    }
    return {**raw, **changes}


def sections(**texts):
    """A draft section per title; `texts` maps an index to (text, manual)."""
    built = []
    for index, title in enumerate(ASSESSMENT_SECTIONS):
        text, manual = texts.get(f"s{index}", (f"Alt {index}.", False))
        paragraphs = (Paragraph(text),) if text else ()
        built.append(Section(title, paragraphs, manual=manual))
    return tuple(built)


def proposal_of(revision=1):
    generated = drafts.parse_generated(result(), "assessment")
    return Proposal(revision, generated.sections, generated.clarifications)


# ---- the structure check ----


def test_a_structured_result_becomes_sections_with_references_and_clarifications():
    generated = drafts.parse_generated(result(), "assessment")

    assert [s.title for s in generated.sections] == list(ASSESSMENT_SECTIONS)
    first = generated.sections[0].paragraphs[0]
    assert first.text == "Text zu Sozialanamnese."
    assert first.references == (drafts.InputReference("notes", "Satz"),)
    assert generated.clarifications == (Clarification(SOZIAL, "Was ist mit dem Wohnort?"),)


@pytest.mark.parametrize(
    "raw",
    [
        "Die Patientin hat Rückenschmerzen. Sie nimmt Ibuprofen.",
        ["a", "b"],
        None,
        {},
        {"sections": "Fließtext", "clarifications": []},
        {"sections": [], "clarifications": []},
    ],
)
def test_prose_or_any_other_unstructured_result_is_a_failed_generation(raw):
    with pytest.raises(GenerationFailed):
        drafts.parse_generated(raw, "assessment")


def test_sections_in_another_order_or_missing_are_refused():
    raw = result()
    swapped = {**raw, "sections": [raw["sections"][1], raw["sections"][0], *raw["sections"][2:]]}
    short = {**raw, "sections": raw["sections"][:-1]}

    for broken in (swapped, short):
        with pytest.raises(GenerationFailed):
            drafts.parse_generated(broken, "assessment")


def test_the_visit_sections_are_not_the_assessment_sections():
    with pytest.raises(GenerationFailed):
        drafts.parse_generated(result(), "visit")
    assert VISIT_SECTIONS != ASSESSMENT_SECTIONS


def test_a_malformed_paragraph_or_reference_or_clarification_is_refused():
    def with_paragraph(paragraph):
        raw = result()
        raw["sections"][0]["paragraphs"] = [paragraph]
        return raw

    good = {"text": "Text.", "heading": "", "references": []}
    for broken in (
        with_paragraph({**good, "text": "  "}),
        with_paragraph({**good, "text": 3}),
        with_paragraph({**good, "references": "Notizen"}),
        with_paragraph({**good, "references": [{"source": "memory", "quote": "x"}]}),
        with_paragraph({**good, "references": [{"source": "notes", "quote": ""}]}),
        with_paragraph("Text."),
        result(clarifications=[{"section": "Unbekannt", "text": "Frage"}]),
        result(clarifications=[{"section": SOZIAL, "text": ""}]),
        result(clarifications="keine"),
    ):
        with pytest.raises(GenerationFailed):
            drafts.parse_generated(broken, "assessment")


def test_a_subsection_heading_is_only_valid_in_the_two_sections_that_have_them():
    def with_heading(section_index, heading):
        raw = result()
        raw["sections"][section_index]["paragraphs"][0]["heading"] = heading
        return raw

    drafts.parse_generated(with_heading(2, "Aktuelle Medikation"), "assessment")
    drafts.parse_generated(with_heading(5, "Orthopädischer Befund"), "assessment")
    for broken in (
        with_heading(0, "Aktuelle Medikation"),
        with_heading(2, "Orthopädischer Befund"),
        with_heading(2, "Eigene Überschrift"),
    ):
        with pytest.raises(GenerationFailed):
            drafts.parse_generated(broken, "assessment")


# ---- section text and copy text ----


def test_section_text_puts_each_subsection_heading_on_its_own_line_once():
    section = Section(
        THERAPIE,
        (
            Paragraph("Ibuprofen 400 mg.", "Aktuelle Medikation"),
            Paragraph("Metformin.", "Aktuelle Medikation"),
            Paragraph("Physiotherapie 2024.", "Frühere nichtmedikamentöse Behandlungen"),
        ),
    )

    assert drafts.section_text(section) == (
        "Aktuelle Medikation\nIbuprofen 400 mg.\n\n"
        "Metformin.\n\n"
        "Frühere nichtmedikamentöse Behandlungen\nPhysiotherapie 2024."
    )


def test_section_text_has_no_title_and_an_empty_section_has_no_text():
    assert drafts.section_text(Section(SOZIAL, (Paragraph("Wohnt allein."),))) == "Wohnt allein."
    assert drafts.section_text(Section(SOZIAL)) == ""
    assert drafts.is_empty(Section(SOZIAL, (Paragraph("  \n"),)))


def test_copy_texts_are_none_without_a_draft_and_one_text_per_section_with_one():
    assert drafts.copy_texts(None) is None
    assert drafts.copy_texts(Draft(sections())) == [f"Alt {i}." for i in range(7)]


# ---- editing ----


def test_a_hand_edit_marks_the_section_and_drops_its_references():
    draft = drafts.accept(None, proposal_of())

    edited = drafts.edit_section(draft, "assessment", 1, "Mein eigener Text.")

    section = edited.sections[1]
    assert section.manual
    assert section.paragraphs == (Paragraph("Mein eigener Text."),)
    assert not any(p.references for p in section.paragraphs)
    assert not edited.sections[0].manual
    assert draft.sections[0].paragraphs[0].references


def test_saving_the_text_a_section_already_has_changes_nothing_and_creates_no_draft():
    draft = drafts.accept(None, proposal_of())
    same = drafts.section_text(draft.sections[0])

    assert drafts.edit_section(draft, "assessment", 0, same) is draft
    assert drafts.edit_section(None, "assessment", 3, "") is None


def test_a_hand_edit_without_a_draft_starts_one_with_seven_sections():
    started = drafts.edit_section(None, "assessment", 2, "Eigener Text.")

    assert [s.title for s in started.sections] == list(ASSESSMENT_SECTIONS)
    assert [s.manual for s in started.sections] == [False, False, True, False, False, False, False]


def test_a_section_cleared_by_hand_stays_manual_and_empty():
    draft = drafts.accept(None, proposal_of())

    cleared = drafts.edit_section(draft, "assessment", 0, "")

    assert cleared.sections[0].manual
    assert drafts.is_empty(cleared.sections[0])


def test_an_edit_clears_the_copied_mark_of_that_section_only():
    draft = drafts.accept(None, proposal_of())
    draft = drafts.mark_copied(drafts.mark_copied(draft, 0), 1)

    edited = drafts.edit_section(draft, "assessment", 0, "Neu.")

    assert [s.copied for s in edited.sections[:2]] == [False, True]


# ---- acceptance ----


def test_accepting_without_a_draft_replaces_every_section_and_marks_none():
    accepted = drafts.accept(None, proposal_of())

    assert [drafts.section_text(s) for s in accepted.sections] == [
        f"Text zu {t}." for t in ASSESSMENT_SECTIONS
    ]
    assert not any(s.manual or s.not_updated or s.copied for s in accepted.sections)


def test_accepting_replaces_only_sections_without_the_manual_flag():
    draft = Draft(sections(s1=("Meine Fassung.", True), s4=("Auch meine.", True)))

    accepted = drafts.accept(draft, proposal_of())

    texts = [drafts.section_text(s) for s in accepted.sections]
    assert texts[1] == "Meine Fassung."
    assert texts[4] == "Auch meine."
    assert texts[0] == "Text zu Sozialanamnese."
    assert texts[6] == "Text zu Behandlungsplan und vereinbarte Ziele."
    assert [s.not_updated for s in accepted.sections] == [i in (1, 4) for i in range(7)]
    assert [s.manual for s in accepted.sections] == [i in (1, 4) for i in range(7)]


def test_a_manual_section_keeps_its_text_even_when_the_proposal_has_none_for_it():
    generated = drafts.parse_generated(result(), "assessment")
    emptied = generated.sections[:1] + (Section(FRUEHER),) + generated.sections[2:]
    proposal = Proposal(1, emptied, ())
    draft = Draft(sections(s1=("Meine Fassung.", True)))

    assert drafts.section_text(drafts.accept(draft, proposal).sections[1]) == "Meine Fassung."


def test_accepting_resets_the_copied_mark_of_replaced_sections_and_keeps_it_on_retained_ones():
    draft = Draft(sections(s1=("Meine Fassung.", True)))
    draft = drafts.mark_copied(drafts.mark_copied(draft, 0), 1)

    accepted = drafts.accept(draft, proposal_of())

    assert [s.copied for s in accepted.sections[:2]] == [False, True]


def test_the_plan_names_what_is_replaced_and_what_stays():
    draft = Draft(sections(s2=("Meine Fassung.", True)))

    plan = drafts.plan(draft, proposal_of())

    assert THERAPIE not in plan.replaced
    assert plan.retained == (THERAPIE,)
    assert len(plan.replaced) == 6
    assert drafts.plan(None, proposal_of()).retained == ()


# ---- outdated proposal and stale draft ----


def test_a_proposal_is_outdated_when_its_notes_revision_is_not_the_current_one():
    proposal = proposal_of(revision=2)

    assert not drafts.proposal_outdated(proposal, 2)
    assert drafts.proposal_outdated(proposal, 3)


def test_a_draft_is_possibly_outdated_only_when_notes_moved_past_its_revision():
    assert not drafts.draft_possibly_outdated(2, 2)
    assert drafts.draft_possibly_outdated(2, 3)
    # A draft the physician only wrote by hand was never generated from notes.
    assert not drafts.draft_possibly_outdated(None, 5)


def test_the_stored_form_round_trips_a_draft_and_a_proposal():
    draft = drafts.accept(None, proposal_of())
    draft = drafts.edit_section(draft, "assessment", 0, "Von Hand.")
    proposal = proposal_of(revision=4)

    assert drafts.draft_from_json(drafts.draft_to_json(draft)) == draft
    stored = drafts.proposal_to_json(proposal)
    assert drafts.proposal_from_json(stored, 4) == proposal

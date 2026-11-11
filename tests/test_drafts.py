"""The rules between a draft and its proposal, as pure logic (ADR 0008, ADR 0010).

No storage and no model: values in, values out. The same rules are driven through the HTTP
API in `tests/test_review_api.py`; these tests pin the edge cases of each rule.
"""

from datetime import datetime

import pytest

from lindra import drafts
from lindra.cast import ASSESSMENT_SECTIONS, VISIT_SECTIONS, Clarification
from lindra.drafts import Draft, Paragraph, Proposal, Section
from lindra.store import Encounter
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


def encounter(**revisions):
    return Encounter(1, "assessment", datetime(2026, 10, 5, 9, 0), **revisions)


def test_a_proposal_is_outdated_when_its_notes_revision_is_not_the_current_one():
    assert not encounter(notes_revision=2, proposal_revision=2).proposal_outdated
    assert encounter(notes_revision=3, proposal_revision=2).proposal_outdated
    # Without a proposal there is nothing to be outdated.
    assert not encounter(notes_revision=3).proposal_outdated


def test_a_draft_is_possibly_outdated_only_when_notes_moved_past_its_revision():
    assert not encounter(notes_revision=2, draft_revision=2).draft_possibly_outdated
    assert encounter(notes_revision=3, draft_revision=2).draft_possibly_outdated
    # A draft the physician only wrote by hand was never generated from notes.
    assert not encounter(notes_revision=5).draft_possibly_outdated


# ---- a hand edit keeps the reference of every paragraph it did not touch ----


def drafted_therapy():
    """A draft whose Therapeutische Anamnese has three paragraphs, each with its own reference."""
    raw = result()
    raw["sections"][2]["paragraphs"] = [
        {
            "text": "Ibuprofen 400 mg.",
            "heading": "Aktuelle Medikation",
            "references": [{"source": "notes", "quote": "Ibuprofen 400 mg"}],
        },
        {
            "text": "Metformin.",
            "heading": "Aktuelle Medikation",
            "references": [{"source": "notes", "quote": "Metformin"}],
        },
        {
            "text": "Physiotherapie 2024.",
            "heading": "Frühere nichtmedikamentöse Behandlungen",
            "references": [{"source": "notes", "quote": "Physiotherapie 2024"}],
        },
    ]
    generated = drafts.parse_generated(raw, "assessment")
    return drafts.accept(None, Proposal(1, generated.sections, generated.clarifications))


def quotes_by_block(section):
    return [[r.quote for r in p.references] for p in section.paragraphs]


def test_rewriting_one_paragraph_removes_only_its_reference():
    draft = drafted_therapy()
    text = drafts.section_text(draft.sections[2]).replace("Metformin.", "Metformin 500 mg.")

    edited = drafts.edit_section(draft, "assessment", 2, text)

    section = edited.sections[2]
    assert section.manual
    assert drafts.section_text(section) == text
    assert quotes_by_block(section) == [["Ibuprofen 400 mg"], [], ["Physiotherapie 2024"]]


def test_a_paragraph_added_by_hand_has_no_reference_and_the_others_keep_theirs():
    draft = drafted_therapy()
    text = drafts.section_text(draft.sections[2]) + "\n\nNeue Zeile von Hand."

    edited = drafts.edit_section(draft, "assessment", 2, text)

    assert quotes_by_block(edited.sections[2]) == [
        ["Ibuprofen 400 mg"],
        ["Metformin"],
        ["Physiotherapie 2024"],
        [],
    ]


def test_a_removed_paragraph_takes_its_reference_with_it():
    draft = drafted_therapy()
    text = drafts.section_text(draft.sections[2]).replace("Metformin.\n\n", "")

    edited = drafts.edit_section(draft, "assessment", 2, text)

    assert quotes_by_block(edited.sections[2]) == [["Ibuprofen 400 mg"], ["Physiotherapie 2024"]]


def test_a_paragraph_that_changed_in_one_character_has_no_reference():
    draft = drafted_therapy()
    text = drafts.section_text(draft.sections[2]).replace("400 mg", "400 mg.")

    edited = drafts.edit_section(draft, "assessment", 2, text)

    assert quotes_by_block(edited.sections[2])[0] == []


@pytest.mark.parametrize(
    "text",
    ["", "Ein Satz.", "\nErste Zeile\n\n\nZweite Zeile  \n", "\n\n", "A\n\nB\n\n", "x\r\n\r\ny"],
)
def test_a_hand_edit_gives_back_exactly_the_text_that_was_typed(text):
    draft = drafted_therapy()

    edited = drafts.edit_section(draft, "assessment", 2, text)

    assert drafts.section_text(edited.sections[2]) == text


def test_the_reference_of_an_untouched_paragraph_survives_a_second_edit():
    draft = drafted_therapy()
    once_text = drafts.section_text(draft.sections[2]).replace("Metformin.", "M.")
    once = drafts.edit_section(draft, "assessment", 2, once_text)

    twice = drafts.edit_section(once, "assessment", 2, drafts.section_text(once.sections[2]) + "!")

    assert quotes_by_block(twice.sections[2]) == [["Ibuprofen 400 mg"], [], []]


# ---- a pain problem is a block with its own heading ----


def test_every_pain_problem_may_have_its_own_heading_and_no_other_section_may():
    def with_heading(section_index, heading):
        raw = result()
        raw["sections"][section_index]["paragraphs"][0]["heading"] = heading
        return raw

    generated = drafts.parse_generated(with_heading(3, "Linkes Knie"), "assessment")

    assert generated.sections[3].paragraphs[0].heading == "Linkes Knie"
    for broken in (with_heading(0, "Linkes Knie"), with_heading(3, "K" * 81), with_heading(3, 4)):
        with pytest.raises(GenerationFailed):
            drafts.parse_generated(broken, "assessment")


def test_pain_problems_stay_separate_blocks_in_the_section_text():
    section = Section(
        ASSESSMENT_SECTIONS[3],
        (
            Paragraph("Drei Attacken pro Monat.", "Migräne"),
            Paragraph("Seit fünf Jahren belastungsabhängig.", "Linkes Knie"),
            Paragraph("Brennend, seit zwei Jahren.", "Beide Füße"),
        ),
    )

    assert drafts.section_text(section) == (
        "Migräne\nDrei Attacken pro Monat.\n\n"
        "Linkes Knie\nSeit fünf Jahren belastungsabhängig.\n\n"
        "Beide Füße\nBrennend, seit zwei Jahren."
    )

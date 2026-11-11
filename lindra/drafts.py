"""The draft of an encounter, its proposal and the rules between them (ADR 0008, ADR 0010).

Everything here is pure: values in, values out, no storage and no model. A draft holds the
fixed sections of its encounter kind in the form's order. A proposal is one generation for the
whole draft, bound to the notes revision it was generated from. Accepting it replaces the
sections the physician has not edited by hand and keeps the others.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any

from lindra.cast import PAIN_HEADING_LIMIT, PAIN_SECTION, SECTIONS, SUBHEADINGS, Clarification
from lindra.textmodel import NOTES_SOURCE, GenerationFailed

OUTDATED_REASON = "Veraltet: Notizen seit diesem Vorschlag geändert"
ORIGIN_NOTES, ORIGIN_HAND = "notes", "hand"
UNSTRUCTURED = "Das Ergebnis des Textmodells hat nicht die erwartete Struktur."


@dataclass(frozen=True)
class InputReference:
    """Where a generated paragraph comes from: a passage of the encounter's notes."""

    source: str
    quote: str


@dataclass(frozen=True)
class Paragraph:
    text: str
    heading: str = ""
    references: tuple[InputReference, ...] = ()


@dataclass(frozen=True)
class Section:
    title: str
    paragraphs: tuple[Paragraph, ...] = ()
    # Edited by hand: acceptance leaves it alone.
    manual: bool = False
    # Kept as it was by the last acceptance although the proposal had another text.
    not_updated: bool = False
    copied: bool = False


@dataclass(frozen=True)
class Draft:
    sections: tuple[Section, ...]


@dataclass(frozen=True)
class Generated:
    """A model result that passed the structure check."""

    sections: tuple[Section, ...]
    clarifications: tuple[Clarification, ...]


@dataclass(frozen=True)
class Proposal:
    """One generation for the whole draft, bound to the notes revision it was made from."""

    notes_revision: int
    sections: tuple[Section, ...]
    clarifications: tuple[Clarification, ...]


@dataclass(frozen=True)
class Plan:
    """What accepting a proposal does, by section title."""

    replaced: tuple[str, ...]
    retained: tuple[str, ...]


def empty_draft(kind: str) -> Draft:
    return Draft(tuple(Section(title) for title in SECTIONS[kind]))


# ---- the structure check on a model result ----


def parse_generated(raw: Any, kind: str) -> Generated:
    """Check a model result against the sections of the encounter kind.

    Anything else than the exact sections in the form's order, each with well-formed
    paragraphs and references, is a failed generation. Whether a reference points into the
    notes is not checked here.
    """
    if not isinstance(raw, dict):
        raise GenerationFailed(UNSTRUCTURED)
    titles = SECTIONS[kind]
    raw_sections = raw.get("sections")
    raw_clarifications = raw.get("clarifications")
    if not isinstance(raw_sections, list) or not isinstance(raw_clarifications, list):
        raise GenerationFailed(UNSTRUCTURED)
    given = [s.get("title") if isinstance(s, dict) else None for s in raw_sections]
    if given != list(titles):
        raise GenerationFailed(UNSTRUCTURED)
    sections = tuple(_parse_section(s, kind) for s in raw_sections)
    clarifications = tuple(_parse_clarification(c, titles) for c in raw_clarifications)
    return Generated(sections, clarifications)


def _parse_section(raw: dict[str, Any], kind: str) -> Section:
    title = raw["title"]
    paragraphs = raw.get("paragraphs")
    if not isinstance(paragraphs, list):
        raise GenerationFailed(UNSTRUCTURED)
    allowed = SUBHEADINGS.get(title, ()) if kind == "assessment" else ()
    pain = kind == "assessment" and title == PAIN_SECTION
    return Section(title, tuple(_parse_paragraph(p, allowed, pain) for p in paragraphs))


def _parse_paragraph(raw: Any, allowed_headings: Sequence[str], any_heading: bool) -> Paragraph:
    """A paragraph's heading is one of the form's subsection headings, or in the
    Schmerzanamnese (`any_heading`) the name of the pain problem the paragraph describes."""
    if not isinstance(raw, dict):
        raise GenerationFailed(UNSTRUCTURED)
    text = raw.get("text")
    heading = raw.get("heading", "")
    references = raw.get("references")
    if not isinstance(text, str) or not text.strip():
        raise GenerationFailed(UNSTRUCTURED)
    if not isinstance(heading, str):
        raise GenerationFailed(UNSTRUCTURED)
    if heading and any_heading:
        if len(heading) > PAIN_HEADING_LIMIT or "\n" in heading:
            raise GenerationFailed(UNSTRUCTURED)
    elif heading and heading not in allowed_headings:
        raise GenerationFailed(UNSTRUCTURED)
    if not isinstance(references, list):
        raise GenerationFailed(UNSTRUCTURED)
    return Paragraph(text, heading, tuple(_parse_reference(r) for r in references))


def _parse_reference(raw: Any) -> InputReference:
    if not isinstance(raw, dict):
        raise GenerationFailed(UNSTRUCTURED)
    source, quote = raw.get("source"), raw.get("quote")
    if source != NOTES_SOURCE or not isinstance(quote, str) or not quote.strip():
        raise GenerationFailed(UNSTRUCTURED)
    return InputReference(source, quote)


def _parse_clarification(raw: Any, titles: Sequence[str]) -> Clarification:
    if not isinstance(raw, dict):
        raise GenerationFailed(UNSTRUCTURED)
    section, text = raw.get("section"), raw.get("text")
    if section not in titles or not isinstance(text, str) or not text.strip():
        raise GenerationFailed(UNSTRUCTURED)
    return Clarification(section, text)


# ---- section text ----


def section_text(section: Section) -> str:
    """A section as plain text: subsection headings on their own line, paragraphs apart.

    This is what the current-draft pane shows, what a hand edit starts from and what the
    copy controls put on the clipboard. The section's own title is not part of it: the
    hospital system has that heading already.
    """
    return "\n\n".join(block for block, _ in _blocks(section))


def _blocks(section: Section) -> list[tuple[str, Paragraph]]:
    """Each paragraph with the block of text it is shown as. A subsection heading opens the
    first block under it and is not repeated for the paragraphs that follow."""
    blocks: list[tuple[str, Paragraph]] = []
    heading = ""
    for paragraph in section.paragraphs:
        if paragraph.heading and paragraph.heading != heading:
            blocks.append((f"{paragraph.heading}\n{paragraph.text}", paragraph))
        else:
            blocks.append((paragraph.text, paragraph))
        heading = paragraph.heading
    return blocks


def is_empty(section: Section) -> bool:
    return not section_text(section).strip()


def excerpt(paragraph: Paragraph, limit: int = 60) -> str:
    """The start of a paragraph on one line, with its heading, to say which one a reference
    belongs to."""
    flat = " ".join(paragraph.text.split())
    if paragraph.heading:
        flat = f"{paragraph.heading} · {flat}"
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "…"


def origin_of(references: Sequence[Any]) -> str:
    """`notes` for a paragraph generated from the notes, `hand` for one without a reference."""
    return ORIGIN_NOTES if references else ORIGIN_HAND


# ---- editing, acceptance, outdated and stale ----


def edit_section(draft: Draft | None, kind: str, index: int, text: str) -> Draft | None:
    """The draft after the physician rewrote one section as free text.

    The section counts as manually edited. The text splits into paragraphs at blank lines; a
    paragraph she left exactly as it was keeps its input references, every other one has none
    ("von Hand"). Text identical to what the pane showed returns the draft as it was (still
    none when there was none), so opening a section and leaving it again never marks it.
    """
    current = draft or empty_draft(kind)
    section = current.sections[index]
    if text == section_text(section):
        return draft
    # Each paragraph is stored as the block the pane showed, so the section text reads back
    # exactly as she typed it, subsection headings included.
    shown = {block: paragraph.references for block, paragraph in reversed(_blocks(section))}
    paragraphs = tuple(Paragraph(block, "", shown.get(block, ())) for block in text.split("\n\n"))
    edited = replace(section, paragraphs=paragraphs if text else (), manual=True, copied=False)
    return replace(current, sections=_with(current.sections, index, edited))


def mark_copied(draft: Draft, index: int) -> Draft:
    section = draft.sections[index]
    return replace(draft, sections=_with(draft.sections, index, replace(section, copied=True)))


def plan(draft: Draft | None, proposal: Proposal) -> Plan:
    """Which sections accepting the proposal replaces and which stay as the physician wrote them."""
    manual = {s.title for s in draft.sections if s.manual} if draft else set()
    titles = [s.title for s in proposal.sections]
    return Plan(
        replaced=tuple(t for t in titles if t not in manual),
        retained=tuple(t for t in titles if t in manual),
    )


def accept(draft: Draft | None, proposal: Proposal) -> Draft:
    """The draft after accepting the proposal as a whole.

    A section the physician edited by hand, also while the proposal was pending, stays and
    is marked as not updated. Every other section takes the proposal's text.
    """
    current = {s.title: s for s in draft.sections} if draft else {}
    merged: list[Section] = []
    for proposed in proposal.sections:
        kept = current.get(proposed.title)
        if kept is not None and kept.manual:
            merged.append(replace(kept, not_updated=True))
        else:
            merged.append(replace(proposed, manual=False, not_updated=False, copied=False))
    return Draft(tuple(merged))


def _with(sections: tuple[Section, ...], index: int, section: Section) -> tuple[Section, ...]:
    return (*sections[:index], section, *sections[index + 1 :])


# ---- stored form ----


def section_to_json(section: Section) -> dict[str, Any]:
    return {
        "title": section.title,
        "paragraphs": [
            {
                "text": p.text,
                "heading": p.heading,
                "references": [{"source": r.source, "quote": r.quote} for r in p.references],
            }
            for p in section.paragraphs
        ],
        "manual": section.manual,
        "not_updated": section.not_updated,
        "copied": section.copied,
    }


def section_from_json(raw: dict[str, Any]) -> Section:
    paragraphs = tuple(
        Paragraph(
            p["text"],
            p["heading"],
            tuple(InputReference(r["source"], r["quote"]) for r in p["references"]),
        )
        for p in raw["paragraphs"]
    )
    return Section(raw["title"], paragraphs, raw["manual"], raw["not_updated"], raw["copied"])


def draft_to_json(draft: Draft) -> dict[str, Any]:
    return {"sections": [section_to_json(s) for s in draft.sections]}


def draft_from_json(raw: dict[str, Any]) -> Draft:
    return Draft(tuple(section_from_json(s) for s in raw["sections"]))


def clarifications_to_json(items: Sequence[Clarification]) -> list[dict[str, str]]:
    return [{"section": c.section, "text": c.text} for c in items]


def clarifications_from_json(raw: list[dict[str, str]]) -> tuple[Clarification, ...]:
    return tuple(Clarification(c["section"], c["text"]) for c in raw)


def proposal_to_json(proposal: Proposal) -> dict[str, Any]:
    """The stored form; the notes revision lives in its own column."""
    return {
        "sections": [section_to_json(s) for s in proposal.sections],
        "clarifications": clarifications_to_json(proposal.clarifications),
    }


def proposal_from_json(raw: dict[str, Any], notes_revision: int) -> Proposal:
    return Proposal(
        notes_revision,
        tuple(section_from_json(s) for s in raw["sections"]),
        clarifications_from_json(raw["clarifications"]),
    )

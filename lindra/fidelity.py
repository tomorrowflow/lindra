"""The result check: what may stay of a structured model result (ADR 0001, ADR 0008).

`lindra/drafts.py` decides whether a model result has the structure of a draft. This module
decides which of its paragraphs the physician's notes support. A paragraph stays only when

- every input reference points into a source the encounter has and quotes it word for word,
- every number and date in it is in the passages it quotes,
- it says nothing of the clinical kinds that only the physician supplies (a ranking of pains,
  a diagnosis or cause, a justification, a recommendation, a normal finding, an interaction or
  conversion, a score interpretation, a claim of completeness or approval) unless a quoted
  passage says it, and
- it names no provenance (the patient's report, a prior finding, the physician's own finding)
  that a quoted passage does not name, and
- it does not settle a contradiction, whether the model put it on the clarification list or
  the notes show it in one sentence, by naming only one of the measures set against each
  other,
- it does not cut a quote out of a sentence whose rest says the notes are uncertain ("an
  anderer Stelle", "vielleicht", "unklar"), and it does not drop an uncertainty its quote
  carries, and
- every word of it that is not a function word comes from the passages it quotes, so a
  diagnosis, a cause or any other fact the quote does not hold cannot enter by a name the
  term lists never heard of.

Whatever the check drops goes on the clarification list as a gap, and a section left without
a paragraph and without an item gets one. The draft therefore holds only what the notes
carry, and a missing fact stays visible as missing. Dropping too much is the safe way to
fail: the physician sees a gap and an item, never an invented fact.

The term lists are a lexicon. They name the wordings of the forbidden kinds, and the word
check covers the rest. Neither says whether a quoted passage supports its paragraph, and a
word may stand behind a word of the passage that means something else. A reference shows
origin, not correctness.
"""

from __future__ import annotations

import math
import os.path
import re
from collections.abc import Mapping, Sequence
from dataclasses import replace
from difflib import SequenceMatcher

from lindra import drafts
from lindra.cast import SUBHEADINGS, UNASSIGNED_PAIN, Clarification

NO_REFERENCE = (
    "Eine Angabe verweist auf keine Stelle der Notizen und steht nicht im Entwurf. "
    "Ergänzen Sie sie in den Notizen, wenn sie gelten soll."
)
TOO_BROAD = (
    "Eine Angabe zitiert eine zu lange Stelle der Notizen, um sich auf sie zu stützen, und steht "
    "nicht im Entwurf. Ergänzen Sie sie in den Notizen, wenn sie gelten soll."
)
EMPTY_SECTION = "Die Notizen enthalten keine Angaben für diesen Abschnitt."


def _cut_off(cue: str) -> str:
    return (
        "Eine Angabe zitierte nur einen Teil eines Satzes der Notizen. Der Rest nennt eine "
        f"Unsicherheit oder einen Widerspruch («{cue}»). Sie steht nicht im Entwurf. Legen Sie "
        "in den Notizen fest, was gilt."
    )


def _hidden(cue: str) -> str:
    return (
        f"Eine Angabe ließ eine Unsicherheit der Notizen («{cue}») aus. Sie steht nicht im "
        "Entwurf. Legen Sie in den Notizen fest, was gilt."
    )


def _not_in_the_notes(what: str) -> str:
    return (
        f"Eine Angabe enthielt {what}, das an der zitierten Stelle der Notizen nicht steht. "
        "Sie steht nicht im Entwurf. Ergänzen Sie sie in den Notizen, wenn sie gelten soll."
    )


# Wordings of what only the physician may supply. Matched in lower case from the start of a
# word, so "empfohlen" also finds "empfohlene" and "normal" finds "normalerweise".
_JUDGEMENTS = (
    # a ranking of pain problems
    "hauptschmerz",
    "hauptproblem",
    "hauptbeschwerde",
    "hauptsächlich",
    "im vordergrund",
    "führend",
    "vorrangig",
    "primär",
    "wichtigste",
    "schwerste",
    "stärkste",
    "schlimmste",
    # a diagnosis or a cause
    "diagnose",
    "diagnostiziert",
    "verdacht",
    "v. a.",
    "v.a.",
    "vereinbar mit",
    "spricht für",
    "hinweis auf",
    "ursächlich",
    "ursache",
    "zurückzuführen",
    "verursacht",
    "bedingt durch",
    "typisch für",
    "passend zu",
    "differenzialdiagn",
    "differentialdiagn",
    "syndrom",
    "störung",
    "neuropathisch",
    "psychosomatisch",
    "depressiv",
    # a justification, or a cause given as a reason
    "weil",
    "wegen",
    "aufgrund",
    "infolge",
    "dadurch",
    "deshalb",
    "begründung",
    "begründet",
    "indiziert",
    "indikation",
    "medizinisch notwendig",
    "notwendig",
    "erforderlich",
    "rechtfertigt",
    # a recommendation
    "empfohlen",
    "empfehle",
    "empfehlung",
    "sollte",
    "ratsam",
    "angezeigt",
    "erwägen",
    # a normal finding
    "unauffällig",
    "regelrecht",
    "o. b.",
    "o.b.",
    "ohne befund",
    "ohne pathologisch",
    "altersentsprechend",
    "physiologisch",
    "normal",
    "keine auffälligkeit",
    # an interaction, a conversion, a dose assessment
    "wechselwirkung",
    "interaktion",
    "kontraindi",
    "äquivalent",
    "umgerechnet",
    "dosisanpassung",
    "höchstdosis",
    "maximaldosis",
    # the reading of a score
    "klinisch relevant",
    "auffällig",
    "pathologisch",
    "grenzwertig",
    "mittelgradig",
    "schwergradig",
    "leichtgradig",
    # an effect or tolerance the physician did not give
    "wirksam",
    "unwirksam",
    "wirkungslos",
    "ohne wirkung",
    "gut verträglich",
    "ohne nebenwirkung",
    "unverträglich",
    "erfolglos",
    "erfolgreich",
    # a claim of completeness or approval
    "vollständig",
    "geprüft",
    "freigegeben",
    "bestätigt",
    "genehmigt",
    "abgenommen",
    "verifiziert",
    "alle angaben",
    "keine weiteren angaben",
    # a time the physician did not give
    "frühjahr",
    "sommer",
    "herbst",
    "winter",
    "januar",
    "februar",
    "märz",
    "april",
    "juni",
    "juli",
    "august",
    "september",
    "oktober",
    "november",
    "dezember",
    "frühling",
    "heute",
    "gestern",
    "vorgestern",
    "kürzlich",
    "vor kurzem",
)

# Who a statement comes from. A paragraph may word one of these only when a quoted passage
# gives the same kind of source; otherwise the provenance stays unknown. Each entry is the
# wordings in a paragraph and the wordings in a passage that give the source.
_PROVENANCE = (
    (
        ("nach angabe der patient", "laut patient", "patientin berichtet", "patient berichtet"),
        ("berichtet", "gibt an", "angabe", "schildert", "beschreibt", "erzählt", "klagt"),
    ),
    (
        (
            "vorbefund",
            "fremdbefund",
            "externer befund",
            "laut arztbrief",
            "aus dem arztbrief",
            "laut entlassbrief",
            "aus dem entlassbrief",
        ),
        ("vorbefund", "fremdbefund", "extern", "arztbrief", "entlassbrief", "an anderer stelle"),
    ),
    (
        ("eigener befund", "eigener untersuchungsbefund", "eigene untersuchung"),
        ("eigene", "untersuchung", "befund", "palpation", "einschätzung"),
    ),
)

# Wordings with which the notes say that something is uncertain or that two statements
# disagree. A quote must not cut one off from the statement it qualifies, and a paragraph that
# quotes one must not drop it.
_HEDGES = (
    "an anderer stelle",
    "andernorts",
    "widerspr",
    "dagegen",
    "vielleicht",
    "unklar",
    "eventuell",
    "möglicherweise",
    "unsicher",
    "nicht sicher",
    "ungewiss",
)
# Words a paragraph may use to say that something is open, though the quote does not.
_HEDGE_MARKERS = ("offen", "widersprüchlich", " oder ")

# Words without a clinical claim, which no quoted passage has to contain: articles,
# prepositions, conjunctions, pronouns, auxiliary verbs and common adverbs of four letters or
# more. Every other word of a paragraph has to come from a passage it quotes.
_FUNCTION_WORDS = frozenset(
    """
    aber alle allem allen aller alles also andere anderen anderer anderes auch bald bereits
    bislang bisher dabei dafür dagegen daher damit danach dann dass davon davor dazu deren
    dessen diese diesem diesen dieser dieses doch dort durch ebenso eher eine einem einen einer
    eines einige erst etwa euch ganz gegen gern gibt habe haben habt hast hatte hatten hier
    ihre ihrem ihren ihrer ihres immer indem jedoch jetzt kann keine keinem keinen keiner
    können konnte machen manche mehr mein meist muss müssen nach nicht nichts noch nur oder
    ohne sehr sein seine seinem seinen seiner seit seitdem selbst sich sind sollen sollte
    somit sondern sonst soweit sowie statt über unter viel viele vielen vom vor weiter
    weiterhin waren wäre wären weder wenn werden wird wohl wurde wurden zudem zuvor zwar
    zwischen zusätzlich
    """.split()
)
# Words that name an attribute only to say it is unclear ("Dosis unklar") or that point at
# the notes.
_GAP_WORDS = frozenset(
    "unklar offen widersprüchlich beginn dosis dauer zeitpunkt angabe angaben notizen".split()
)

_WORD = re.compile(r"[A-Za-zÄÖÜäöüß]{4,}")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
# A quantity with a unit. The plural endings of "Monate", "Tabletten" and the like count as
# the same unit.
_MEASURE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(mg|µg|mcg|ml|mmol|g|ie|%|tropfen|tablette|kapsel|stunde|tag|woche|"
    r"monat|jahr)(?:e|en|n)?(?!\w)",
    re.IGNORECASE,
)
# A quoted passage is a sentence or two, not a stretch of the notes that would carry every
# wording and number in them.
MAX_QUOTE = 300
# Words that say two statements in the notes disagree.
_DISAGREE = ("widerspr", "abweich", "unterschiedlich", "uneinheitlich", " oder ")
_NUMBER_WORDS = {
    "null": 0,
    "einmal": 1,
    "zwei": 2,
    "drei": 3,
    "vier": 4,
    "fünf": 5,
    "sechs": 6,
    "sieben": 7,
    "acht": 8,
    "neun": 9,
    "zehn": 10,
    "elf": 11,
    "zwölf": 12,
    "dreizehn": 13,
    "vierzehn": 14,
    "fünfzehn": 15,
    "sechzehn": 16,
    "siebzehn": 17,
    "achtzehn": 18,
    "neunzehn": 19,
    "zwanzig": 20,
    "dreißig": 30,
    "vierzig": 40,
    "fünfzig": 50,
    "sechzig": 60,
    "siebzig": 70,
    "achtzig": 80,
    "neunzig": 90,
    "hundert": 100,
}
# "zweimal" and "dreifach" are the number too.
_SPELLED = "|".join(sorted(_NUMBER_WORDS, key=len, reverse=True))
_NUMBER_WORD = re.compile(r"(?<!\w)(" + _SPELLED + r")(?:mal|fach)?(?!\w)")
_SPELLED_NUMBER = re.compile(r"(?:" + _SPELLED + r")(?:mal|fach)?")
# The form's own headings come from the form, not from the notes.
_FORM_HEADINGS = frozenset(h for headings in SUBHEADINGS.values() for h in headings) | {
    UNASSIGNED_PAIN
}


def check_result(generated: drafts.Generated, sources: Mapping[str, str]) -> drafts.Generated:
    """The result with the paragraphs the notes do not support taken out.

    `sources` maps a reference's source key to the text it quotes from: for now the key
    `notes` and the encounter's notes. A paragraph that fails goes on the clarification list
    under its section; a section left with no paragraph and no item gets one. The model's own
    items come first, then ours in section order.
    """
    items = list(generated.clarifications)
    conflicts = _conflicts(items) + [c for text in sources.values() for c in _disagreements(text)]
    sections: list[drafts.Section] = []
    dropped: list[Clarification] = []
    for section in generated.sections:
        kept = []
        for paragraph in section.paragraphs:
            problem = _problem(paragraph, sources, conflicts)
            if problem is None:
                kept.append(paragraph)
            else:
                dropped.append(Clarification(section.title, problem))
        sections.append(replace(section, paragraphs=tuple(kept)))
    items += [item for index, item in enumerate(dropped) if item not in dropped[:index]]
    items = [item for index, item in enumerate(items) if item not in items[:index]]
    flagged = {item.section for item in items}
    for section in sections:
        if not section.paragraphs and section.title not in flagged:
            items.append(Clarification(section.title, EMPTY_SECTION))
    return replace(generated, sections=tuple(sections), clarifications=tuple(items))


def _problem(
    paragraph: drafts.Paragraph,
    sources: Mapping[str, str],
    conflicts: Sequence[frozenset[str]],
) -> str | None:
    """The clarification text for a paragraph the notes do not support, or None when it stays.

    `conflicts` are the measures the notes or the model set against each other."""
    if not paragraph.references:
        return NO_REFERENCE
    quotes = []
    for reference in paragraph.references:
        source = sources.get(reference.source)
        if source is None or _squash(reference.quote) not in _squash(source):
            return NO_REFERENCE
        if len(_squash(reference.quote)) > MAX_QUOTE:
            return TOO_BROAD
        quotes.append(_squash(reference.quote))
    said = _squash(f"{paragraph.heading} {paragraph.text}")
    quoted = " ".join(quotes)
    lower_said, lower_quoted = said.lower(), quoted.lower()

    for term in _JUDGEMENTS:
        found = _find(term, lower_said)
        if found is not None and _find(term, lower_quoted) is None:
            return _not_in_the_notes(f"«{said[found : found + len(term)]}»")
    # What a quoted passage licenses as provenance is not a word to ground in the passage.
    text = _squash(paragraph.text)
    for wordings, passages in _PROVENANCE:
        for wording in wordings:
            found = _find(wording, lower_said)
            if found is None:
                continue
            if not any(_find(p, lower_quoted) is not None for p in passages):
                return _not_in_the_notes(
                    f"die Herkunftsangabe «{said[found : found + len(wording)]}»"
                )
            at = _find(wording, text.lower())
            if at is not None:
                text = text[:at] + " " * len(wording) + text[at + len(wording) :]
    unknown = sorted(_numbers(said) - _numbers(quoted))
    if unknown:
        return _not_in_the_notes(f"die Zahl {unknown[0]}")
    stated = _measures(said)
    unsaid = sorted(stated - _measures(quoted))
    if unsaid:
        return _not_in_the_notes(f"die Angabe {unsaid[0]}")
    for reference in paragraph.references:
        cue = _cut_off_cue(_squash(sources[reference.source]), _squash(reference.quote), quoted)
        if cue:
            return _cut_off(cue)
    for conflict in conflicts:
        if stated & conflict and not conflict <= stated:
            return (
                f"Eine Angabe nannte nur {_join(sorted(stated & conflict))} von "
                f"{_join(sorted(conflict))}, die sich in den Notizen widersprechen. Sie steht "
                "nicht im Entwurf. Legen Sie in den Notizen fest, was gilt."
            )
    quoted_cue = _hedge_in(lower_quoted)
    if quoted_cue and not (
        _hedge_in(lower_said) or any(m in f" {lower_said} " for m in _HEDGE_MARKERS)
    ):
        return _hidden(quoted_cue)
    # Every word of the text stands behind a quoted passage. A pain problem's heading is the
    # physician's name for it, so it may come from anywhere in the notes; the form's own
    # headings come from the form.
    word = _ungrounded(text, quoted)
    if not word and paragraph.heading not in _FORM_HEADINGS:
        word = _ungrounded(paragraph.heading, " ".join(sources.values()))
    if word:
        return _not_in_the_notes(f"das Wort «{word}»")
    return None


def _hedge_in(lower_text: str) -> str | None:
    """The first wording of an uncertainty or disagreement in the lower-cased text."""
    return next((cue for cue in _HEDGES if cue in lower_text), None)


def _cut_off_cue(source: str, quote: str, quoted: str) -> str | None:
    """A wording of uncertainty in the quote's sentence that the paragraph's quotes leave out."""
    start = source.find(quote)
    end = start + len(quote)
    first, last = 0, len(source)
    for boundary in re.finditer(r"(?<=[.!?])\s+", source):
        if boundary.end() <= start:
            first = boundary.end()
        elif boundary.start() >= end:
            last = boundary.start()
            break
    outside = f"{source[first:start]} {source[end:last]}".lower()
    cue = _hedge_in(outside)
    return cue if cue and cue not in quoted.lower() else None


def _disagreements(source: str) -> list[frozenset[str]]:
    """The measures of each sentence of the notes that names two or more of them and says in
    the same sentence that the notes are uncertain or disagree."""
    found = []
    for sentence in re.split(r"(?<=[.!?])\s+", _squash(source)):
        lower = f" {sentence.lower()} "
        measures = _measures(sentence)
        if len(measures) >= 2 and (_hedge_in(lower) or any(w in lower for w in _DISAGREE)):
            found.append(frozenset(measures))
    return found


def _ungrounded(text: str, quoted: str) -> str | None:
    """The first word of the text that no word of the quoted passages stands behind."""
    known = [word.lower() for word in _WORD.findall(quoted)]
    for match in _WORD.finditer(text):
        word = match.group().lower()
        if word in _FUNCTION_WORDS or word in _GAP_WORDS or _SPELLED_NUMBER.fullmatch(word):
            continue
        if not any(_same_word(word, other) for other in known):
            return match.group()
    return None


def _same_word(a: str, b: str) -> bool:
    """Whether two words are one word inflected or one compound of the other.

    Short words must share their start ("lebt" and "leben"). Longer ones need a stretch in
    common that is most of the shorter word and at least five letters, so "Schmerz" stands
    behind "Rückenschmerz" and "Ausstrahlung" behind "strahlt aus", and "Fibromyalgie" behind
    nothing."""
    shorter = min(len(a), len(b))
    if shorter <= 5:
        prefix = len(os.path.commonprefix([a, b]))
        return prefix >= max(3, shorter - 1)
    match = SequenceMatcher(None, a, b, autojunk=False).find_longest_match(0, len(a), 0, len(b))
    return match.size >= max(5, math.ceil(0.75 * shorter))


def _conflicts(items: Sequence[Clarification]) -> list[frozenset[str]]:
    """The measures each flagged contradiction sets against each other.

    An item counts when it says the notes disagree and names two or more measures, as in "50 mg
    oder 100 mg". A paragraph of any section that names some of them but not all would settle
    the contradiction, which only the physician may do.
    """
    found: list[frozenset[str]] = []
    for item in items:
        measures = _measures(item.text)
        if len(measures) >= 2 and any(word in f" {item.text.lower()} " for word in _DISAGREE):
            found.append(frozenset(measures))
    return found


def _measures(text: str) -> set[str]:
    """Quantities with a unit, like "50mg" or "3monat" for "3 Monaten"."""
    return {f"{number}{unit.lower()}" for number, unit in _MEASURE.findall(text)}


def _join(measures: Sequence[str]) -> str:
    return " und ".join(measures)


def _squash(text: str) -> str:
    """Runs of whitespace as one space, so a line break in the notes does not hide a quote."""
    return " ".join(text.split())


def _find(term: str, lower_text: str) -> int | None:
    """Where `term` is in the lower-cased text, or None. A short term has to start a word, so
    "wegen" does not match "bewegen". A long one may sit inside a compound, so "störung" finds
    "Schlafstörung"."""
    if len(term) >= 7:
        at = lower_text.find(term)
        return at if at >= 0 else None
    match = re.search(r"(?<!\w)" + re.escape(term), lower_text)
    return match.start() if match else None


def _numbers(text: str) -> set[str]:
    """The numbers in a text, digits and spelled-out ones alike, as digit strings."""
    found = set(_NUMBER.findall(text))
    found |= {str(_NUMBER_WORDS[word]) for word in _NUMBER_WORD.findall(text.lower())}
    return found

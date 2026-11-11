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
  term lists never heard of, and
- its words, numbers and denials stay together as the quote has them: each clause of the
  paragraph has to be held by one clause of a quote, each number has to stand next to the
  words it stands next to in the quote, and the denial that begins before a quote has to be
  in it, so a dose cannot move to the other drug, a score to the other pain, a "kein" to the
  other substance or a finding to the other side.

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
from dataclasses import dataclass, replace
from difflib import SequenceMatcher

from lindra import drafts
from lindra.cast import SUBHEADINGS, UNASSIGNED_PAIN, Clarification
from lindra.textmodel import NOTES_SOURCE

NO_REFERENCE = (
    "Eine Angabe verweist auf keine Stelle der Notizen und steht nicht im Entwurf. "
    "Ergänzen Sie sie in den Notizen, wenn sie gelten soll."
)
TOO_BROAD = (
    "Eine Angabe zitiert eine zu lange Stelle der Notizen, um sich auf sie zu stützen, und steht "
    "nicht im Entwurf. Ergänzen Sie sie in den Notizen, wenn sie gelten soll."
)
EMPTY_SECTION = "Die Notizen enthalten keine Angaben für diesen Abschnitt."
BACKGROUND_ONLY = (
    "Eine Angabe stützt sich nur auf frühere Kontakte. Was eine Visite heute findet, "
    "einschätzt und vereinbart, stammt aus ihren Notizen, deshalb steht sie nicht im Entwurf. "
    "Ergänzen Sie sie in den Notizen, wenn sie heute gilt."
)
NEGATION = (
    "Eine Angabe verneinte oder bejahte etwas anders als die zitierte Stelle der Notizen. Sie "
    "steht nicht im Entwurf. Ergänzen Sie sie in den Notizen, wenn sie gelten soll."
)


def _not_together(clause: str) -> str:
    return (
        "Eine Angabe verband Wörter, Zahlen oder eine Verneinung, die an der zitierten Stelle "
        f"der Notizen nicht zusammen stehen («{clause}»). Sie steht nicht im Entwurf. Ergänzen "
        "Sie sie in den Notizen, wenn sie gelten soll."
    )


def _cut_off_denial(word: str) -> str:
    return (
        "Eine Angabe zitierte nur einen Teil eines Satzes der Notizen. Der Rest enthält eine "
        f"Verneinung («{word}»), die für das Zitierte gelten kann. Sie steht nicht im Entwurf. "
        "Legen Sie in den Notizen fest, was gilt."
    )


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
    "ggf",
    "bzw",
    "evtl",
    "alternativ",
    "teils",
)
# Words a paragraph may use to say that something is open, though the quote does not.
_HEDGE_MARKER = re.compile(r"\b(?:offen|widersprüchlich|oder)\b")

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

_LETTERS = r"[^\W\d_]"
# A word of four letters or more, and the short sides and body parts that carry a finding
# ("li", "re", "bds", "Arm", "Fuß", "Ohr").
_WORD = re.compile(rf"{_LETTERS}{{4,}}|(?i:\b(?:li|re|bds|arm|fuß|ohr)\b)")
# An abbreviation of capitals ("MRT", "HWS", "NRS") has to appear as it is.
_ABBREVIATION = re.compile(rf"(?<!{_LETTERS})[A-ZÄÖÜ]{{3,}}(?!{_LETTERS})")
# Where one clause ends and the next begins: a comma or full stop that is not inside a number
# ("0,5", "12.03.2024"), the other punctuation, and "und" and "sowie".
_CLAUSE_BREAK = re.compile(r"(?<!\d)[,.]|[,.](?!\d)|[;!?()\n]|\b(?:und|sowie)\b")
# Words that make a statement a denial. A paragraph and its quote must agree on whether
# there is one: "strahlt aus" must not become "strahlt nicht aus", or the reverse.
_NEGATION = re.compile(
    r"\b(?:nicht|nichts|nie|niemals|weder|ohne|kaum|negativ|fehlt|fehlen|ausgeschlossen|"
    r"nirgend\w*|kein\w*)\b|\bfrei von\b"
)
# Where one sentence of the notes ends and the next begins. The abbreviations of notes do not
# end one ("ca.", "ggf.", "z. B.").
_SENTENCE_BREAK = re.compile(
    r"(?<=[.!?])"
    r"(?<!\bca\.)(?<!\bggf\.)(?<!\bbzw\.)(?<!\bevtl\.)(?<!\binkl\.)(?<!\bDr\.)(?<!\bNr\.)"
    r"(?<!\bz\. B\.)(?<!\bd\. h\.)(?<!\bu\. a\.)(?<!\bv\. a\.)"
    rf"\s+(?!{_LETTERS}\.)"
)
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


def check_result(
    generated: drafts.Generated,
    sources: Mapping[str, str],
    today_only: frozenset[str] = frozenset(),
) -> drafts.Generated:
    """The result with the paragraphs the notes and the background do not support taken out.

    `sources` maps a reference's source key to the text it quotes from: the key `notes` with
    the encounter's notes and, for a visit, the key of each background encounter with its
    accepted draft. A paragraph that fails goes on the clarification list under its section; a
    section left with no paragraph and no item gets one. The model's own items come first,
    then ours in section order. A paragraph in a `today_only` section that quotes no notes
    passage, only earlier encounters, is dropped as well.
    """
    items = list(generated.clarifications)
    conflicts = _conflicts(items) + [c for text in sources.values() for c in _disagreements(text)]
    sections: list[drafts.Section] = []
    dropped: list[Clarification] = []
    for section in generated.sections:
        kept = []
        for paragraph in section.paragraphs:
            problem = _problem(paragraph, sources, conflicts)
            if problem is None and section.title in today_only:
                if not any(r.source == NOTES_SOURCE for r in paragraph.references):
                    problem = BACKGROUND_ONLY
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
        found = _cut_off_cue(_squash(sources[reference.source]), _squash(reference.quote), quoted)
        if found and found[0] == "hedge":
            return _cut_off(found[1])
        if found:
            return _cut_off_denial(found[1])
    for conflict in conflicts:
        if stated & conflict and not conflict <= stated:
            return (
                f"Eine Angabe nannte nur {_join(sorted(stated & conflict))} von "
                f"{_join(sorted(conflict))}, die sich widersprechen. Sie steht "
                "nicht im Entwurf. Legen Sie in den Notizen fest, was gilt."
            )
    quoted_cue = _hedge_in(lower_quoted)
    if quoted_cue and not (_hedge_in(lower_said) or _HEDGE_MARKER.search(lower_said)):
        return _hidden(quoted_cue)
    if _negated(text) != _negated(quoted):
        return NEGATION
    # Every word of the text stands behind a quoted passage. A pain problem's heading is the
    # physician's name for it, so it may come from anywhere in the notes; the form's own
    # headings come from the form.
    word = _ungrounded(text, quoted)
    if not word and paragraph.heading not in _FORM_HEADINGS:
        word = _ungrounded(paragraph.heading, " ".join(sources.values()))
    if word:
        return _not_in_the_notes(f"das Wort «{word}»")
    loose = _unbound(text, quotes)
    if loose:
        return _not_together(loose)
    return None


def _hedge_in(lower_text: str) -> str | None:
    """The first wording of an uncertainty or disagreement in the lower-cased text."""
    return next((cue for cue in _HEDGES if cue in lower_text), None)


def _cut_off_cue(source: str, quote: str, quoted: str) -> tuple[str, str] | None:
    """A wording of uncertainty ("hedge") or of denial ("denial") in the quote's sentence that
    the paragraph's quotes leave out: the quote would carry on the statement without it."""
    start = source.find(quote)
    end = start + len(quote)
    first, last = 0, len(source)
    for boundary in _SENTENCE_BREAK.finditer(source):
        if boundary.end() <= start:
            first = boundary.end()
        elif boundary.start() >= end:
            last = boundary.start()
            break
    outside = f"{source[first:start]} {source[end:last]}".lower()
    cue = _hedge_in(outside)
    if cue and cue not in quoted.lower():
        return "hedge", cue
    # A denial reaches along a list ("keine Übelkeit, Erbrechen, Schwindel"), but not to every
    # item of a long one: only the clause the quote starts in or ends in, and the clause before
    # the quote, count.
    near = " ".join(
        [*_CLAUSE_BREAK.split(source[first:start])[-2:], _CLAUSE_BREAK.split(source[end:last])[0]]
    )
    denial = _NEGATION.search(near.lower())
    if denial and not _NEGATION.search(quoted.lower()):
        return "denial", denial.group()
    return None


def _disagreements(source: str) -> list[frozenset[str]]:
    """The measures of each sentence of the notes that names two or more of them and says in
    the same sentence that the notes are uncertain or disagree."""
    found = []
    for sentence in _SENTENCE_BREAK.split(_squash(source)):
        lower = f" {sentence.lower()} "
        measures = _measures(sentence)
        if len(measures) >= 2 and (_hedge_in(lower) or any(w in lower for w in _DISAGREE)):
            found.append(frozenset(measures))
    return found


def _carries_no_claim(word: str) -> bool:
    """Function words, words that only say something is unclear and spelled-out numbers are
    checked elsewhere or say nothing."""
    return word in _FUNCTION_WORDS or word in _GAP_WORDS or bool(_SPELLED_NUMBER.fullmatch(word))


def _ungrounded(text: str, quoted: str) -> str | None:
    """The first word or abbreviation of the text that no word of the quoted passages stands
    behind."""
    known = [word.lower() for word in _WORD.findall(quoted)]
    abbreviations = set(_ABBREVIATION.findall(quoted))
    for match in _ABBREVIATION.finditer(text):
        if match.group() not in abbreviations:
            return match.group()
    for match in _WORD.finditer(text):
        word = match.group().lower()
        if _carries_no_claim(word):
            continue
        if not any(_same_word(word, other) for other in known):
            return match.group()
    return None


@dataclass(frozen=True)
class _Clause:
    """What one clause of a text says: its words, numbers and abbreviations, and whether it
    denies something."""

    text: str
    words: tuple[str, ...]
    numbers: frozenset[str]
    abbreviations: frozenset[str]
    negated: bool
    # Each number with the words and abbreviations it stands next to: the nearest run of them
    # before it, or after it when nothing comes before. "Tramadol retard 100 mg" binds 100 to
    # tramadol and retard, and a list without punctuation between its drugs keeps each dose
    # with its own drug.
    numbered: tuple[tuple[str, frozenset[str]], ...]

    @property
    def says_something(self) -> bool:
        return bool(self.words or self.numbers or self.abbreviations)

    def stands_behind(self, other: _Clause) -> bool:
        """Whether `other`, a clause of a quote, holds all of this clause's words, numbers and
        abbreviations, agrees on denial and keeps each number with the words it stands next
        to."""
        return (
            self.negated == other.negated
            and self.numbers <= other.numbers
            and self.abbreviations <= other.abbreviations
            and all(any(_same_word(w, o) for o in other.words) for w in self.words)
            and all(
                any(
                    not run or not held or any(_same_word(a, b) for a in run for b in held)
                    for value, held in other.numbered
                    if value == number
                )
                for number, run in self.numbered
            )
        )


def _content_words(text: str) -> list[str]:
    return [w for w in (m.lower() for m in _WORD.findall(text)) if not _carries_no_claim(w)]


# The things a clause is made of, in order: numbers (digits or spelled out), abbreviations and
# words. Whatever else stands between them is skipped.
_TOKEN = re.compile(
    rf"(?P<number>\d+(?:[.,]\d+)*)"
    rf"|(?P<spelled>(?i:(?<!\w)(?:{_SPELLED})(?:mal|fach)?(?!\w)))"
    rf"|(?P<abbreviation>(?<!{_LETTERS})[A-ZÄÖÜ]{{3,}}(?!{_LETTERS}))"
    rf"|(?P<word>{_WORD.pattern})"
)


def _numbered(part: str) -> tuple[tuple[str, frozenset[str]], ...]:
    """Each number of the clause with the nearest run of words and abbreviations next to it."""
    tokens: list[tuple[bool, str]] = []
    for match in _TOKEN.finditer(part):
        if match["number"] or match["spelled"]:
            tokens.append((True, next(iter(_numbers(match.group())))))
        elif match["abbreviation"]:
            tokens.append((False, match.group().lower()))
        elif not _carries_no_claim(match.group().lower()):
            tokens.append((False, match.group().lower()))

    def run_from(start: int, step: int) -> frozenset[str]:
        at = start
        while 0 <= at < len(tokens) and tokens[at][0]:
            at += step
        found = []
        while 0 <= at < len(tokens) and not tokens[at][0]:
            found.append(tokens[at][1])
            at += step
        return frozenset(found)

    return tuple(
        (value, run_from(i - 1, -1) or run_from(i + 1, 1))
        for i, (is_number, value) in enumerate(tokens)
        if is_number
    )


def _clause(part: str) -> _Clause:
    return _Clause(
        part.strip(),
        tuple(_content_words(part)),
        frozenset(_numbers(part)),
        frozenset(_ABBREVIATION.findall(part)),
        _negated(part),
        _numbered(part),
    )


def _clauses(text: str) -> list[_Clause]:
    return [_clause(part) for part in _CLAUSE_BREAK.split(text)]


def _unbound(text: str, quotes: Sequence[str]) -> str | None:
    """The first clause of the text whose words, numbers and denial no single clause of a
    quote holds together.

    Each word of the paragraph may stand behind some word of the quote and the paragraph can
    still say what the quote does not: a dose moved to the other drug, a denial moved to the
    other word, a finding moved to the other side. Within a clause they have to stay together."""
    held = [clause for quote in quotes for clause in _clauses(quote)]
    parts = _CLAUSE_BREAK.split(text)
    for index, part in enumerate(parts):
        clause = _clause(part)
        if not clause.says_something:
            continue
        if not clause.words and len(clause.numbers) == 1:
            # A number with no word of its own ("Knie, NRS 7", "Seit dem 7.10., kein
            # Ibuprofen") belongs to the clause before it or the one after it, unless the quote
            # sets it apart in the same way. New punctuation must not detach a number from the
            # word it belonged to.
            neighbours = [
                _clause(f"{parts[at]} {part}" if at < index else f"{part} {parts[at]}")
                for at in (index - 1, index + 1)
                if 0 <= at < len(parts) and parts[at].strip()
            ]
            apart = any(not other.words and clause.stands_behind(other) for other in held)
            joined = any(c.stands_behind(other) for c in neighbours for other in held)
            if not (apart or joined):
                return clause.text
        elif not clause.words and len(clause.numbers) > 1:
            # Bare alternatives ("50 mg oder 100 mg") bind to nothing; each has to be in a quote.
            if not all(any(n in other.numbers for other in held) for n in clause.numbers):
                return clause.text
        elif not any(clause.stands_behind(other) for other in held):
            return clause.text
    return None


def _same_word(word: str, other: str) -> bool:
    """Whether `other`, a word of a quoted passage, stands behind `word`, a word of the text.

    A short word must share its start with `other` ("lebt" and "leben"). A longer one needs a
    stretch in common that is most of the word itself and at least five letters, so "Schmerz"
    stands behind "Rückenschmerz" and "Kinder" behind "Kindern", while "Schulterarthrose" has
    no word behind it in "Schulter" and "Fibromyalgie" none in "Rückenschmerz". The text may
    name a part of a compound of the passage, never a longer compound than the passage has."""
    if len(word) < 4:
        return word == other
    if len(word) <= 5:
        return len(os.path.commonprefix([word, other])) >= max(3, len(word) - 1)
    match = SequenceMatcher(None, word, other, autojunk=False).find_longest_match(
        0, len(word), 0, len(other)
    )
    return match.size >= max(5, math.ceil(0.7 * len(word)))


def _negated(text: str) -> bool:
    return bool(_NEGATION.search(text.lower()))


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

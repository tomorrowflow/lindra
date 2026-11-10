"""The fictional cast: three invented German cases (ADR 0006, ADR 0010).

This is the only dataset the environments seed. Every case number, name, note and
draft below is invented; no real, pseudonymised or production-copied data belongs
here, and neither do the ward's forms or the operator's documents. The cast is
seed data now; ticket 05 connects the seed hook to case storage.

Each encounter carries what the fixture text model returns for it (the expected
draft and the clarification items) and the fixture audio the speech stand-in
transcribes.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import wave
from dataclasses import asdict, dataclass
from datetime import date

CASE_NUMBER_PREFIX = "FIK-"

ASSESSMENT_SECTIONS = (
    "Sozialanamnese",
    "Frühere Anamnese und Vormedikation",
    "Therapeutische Anamnese",
    "Schmerzanamnese",
    "Internistische, vegetative, psychiatrische und Suchtmittelanamnese",
    "Untersuchungsbefunde",
    "Behandlungsplan und vereinbarte Ziele",
)
VISIT_SECTIONS = (
    "Verlauf seit letzter Visite",
    "Aktuelle Befunde",
    "Ärztliche Einschätzung",
    "Vereinbartes Vorgehen und Ziele",
)
SECTIONS = {"assessment": ASSESSMENT_SECTIONS, "visit": VISIT_SECTIONS}


@dataclass(frozen=True)
class Clarification:
    section: str
    text: str


@dataclass(frozen=True)
class FixtureClip:
    """A dictation clip. The audio bytes come from `fixture_audio(key)`."""

    key: str
    transcript: str


@dataclass(frozen=True)
class Encounter:
    key: str
    kind: str
    date: date
    entered_on: date
    notes: str
    draft: dict[str, str]
    clarifications: tuple[Clarification, ...] = ()
    audio: tuple[FixtureClip, ...] = ()
    background: tuple[str, ...] = ()


@dataclass(frozen=True)
class Case:
    case_number: str
    patient_name: str
    label: str
    period_start: date
    period_end: date
    encounters: tuple[Encounter, ...]
    # What happened in which order: ("accept", key) or ("generate", key).
    timeline: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Cast:
    cases: tuple[Case, ...]


def fixture_audio(key: str) -> bytes:
    """A short deterministic WAV clip: a tone whose pitch comes from the key.

    The clip is not speech. The speech stand-in maps its bytes to the canned
    transcript, so no audio file is committed.
    """
    digest = hashlib.sha256(key.encode()).digest()
    frequency = 220 + digest[0] * 2
    rate = 8000
    frames = bytearray()
    for n in range(rate // 2):
        sample = int(8000 * math.sin(2 * math.pi * frequency * n / rate))
        frames += sample.to_bytes(2, "little", signed=True)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as clip:
        clip.setnchannels(1)
        clip.setsampwidth(2)
        clip.setframerate(rate)
        clip.writeframes(bytes(frames))
    return buffer.getvalue()


def changed_background(case: Case) -> tuple[str, ...]:
    """Visits whose background was accepted again after their draft was generated."""
    changed = []
    for encounter in case.encounters:
        generated = [
            i for i, event in enumerate(case.timeline) if event == ("generate", encounter.key)
        ]
        if (
            encounter.kind == "visit"
            and generated
            and any(
                what == "accept" and key in encounter.background and i > generated[-1]
                for i, (what, key) in enumerate(case.timeline)
            )
        ):
            changed.append(encounter.key)
    return tuple(changed)


def validate_cast(cast: Cast) -> list[str]:
    """Every way the cast breaks the rules of ADR 0006 and ADR 0010; empty when valid."""
    problems: list[str] = []
    if len(cast.cases) != 3:
        problems.append(f"the cast needs three cases, it has {len(cast.cases)}")
    numbers = [case.case_number for case in cast.cases]
    names = [case.patient_name for case in cast.cases]
    if len(set(numbers)) != len(numbers):
        problems.append("case numbers repeat")
    if len(set(names)) != len(names):
        problems.append("patient names repeat")
    clip_keys: list[str] = []
    for case in cast.cases:
        problems += _validate_case(case)
        clip_keys += [clip.key for e in case.encounters for clip in e.audio]
    if len(set(clip_keys)) != len(clip_keys):
        problems.append("fixture audio keys repeat")
    # The speech stand-in maps audio bytes to transcripts, so two clips must not share bytes.
    if len({fixture_audio(key) for key in clip_keys}) != len(clip_keys):
        problems.append("two fixture audio clips have the same bytes")
    if not any(
        e.kind == "visit" and e.date < e.entered_on for c in cast.cases for e in c.encounters
    ):
        problems.append("no visit is backdated")
    if not any(changed_background(case) for case in cast.cases):
        problems.append("no case has an assessment change accepted after a visit draft")
    if len(cast.cases) == 3 and not any(
        not text for e in cast.cases[2].encounters for text in e.draft.values()
    ):
        problems.append("the third case leaves no gap")
    return problems


def _validate_case(case: Case) -> list[str]:
    where = case.case_number
    problems: list[str] = []
    if not case.case_number.startswith(CASE_NUMBER_PREFIX):
        problems.append(f"{where}: a fictional case number starts with {CASE_NUMBER_PREFIX}")
    if not case.patient_name.strip():
        problems.append(f"{where}: no patient name")
    if case.period_start > case.period_end:
        problems.append(f"{where}: the treatment period ends before it starts")
    kinds = [e.kind for e in case.encounters]
    if kinds.count("assessment") != 1:
        problems.append(f"{where}: a case has exactly one admission assessment")
    if kinds.count("visit") < 1:
        problems.append(f"{where}: a case has at least one visit")
    if not any(e.audio for e in case.encounters):
        problems.append(f"{where}: no fixture audio")
    keys = [e.key for e in case.encounters]
    if len(set(keys)) != len(keys):
        problems.append(f"{where}: encounter keys repeat")
    by_key = {e.key: e for e in case.encounters}
    for encounter in case.encounters:
        problems += _validate_encounter(case, encounter, by_key)
    for what, key in case.timeline:
        if what not in ("accept", "generate") or key not in by_key:
            problems.append(f"{where}: timeline entry {what} {key} is not an event of this case")
    return problems


def _validate_encounter(
    case: Case, encounter: Encounter, by_key: dict[str, Encounter]
) -> list[str]:
    where = f"{case.case_number} {encounter.key}"
    problems: list[str] = []
    if not case.period_start <= encounter.date <= case.period_end:
        problems.append(f"{where}: date lies outside the treatment period")
    if not encounter.notes.strip():
        problems.append(f"{where}: no notes")
    sections = SECTIONS.get(encounter.kind)
    if sections is None:
        return [*problems, f"{where}: unknown encounter kind {encounter.kind}"]
    if tuple(encounter.draft) != sections:
        problems.append(f"{where}: draft sections do not match the {encounter.kind} sections")
    flagged = {c.section for c in encounter.clarifications}
    for section in flagged - set(sections):
        problems.append(f"{where}: clarification item names unknown section {section}")
    for section, text in encounter.draft.items():
        if not text and section not in flagged:
            problems.append(f"{where}: empty section {section} has no clarification item")
    for clip in encounter.audio:
        if not clip.transcript.strip():
            problems.append(f"{where}: clip {clip.key} has no canned transcript")
    for key in encounter.background:
        earlier = by_key.get(key)
        if earlier is None or earlier.date > encounter.date or key == encounter.key:
            problems.append(f"{where}: background {key} is not an earlier encounter")
    if encounter.kind == "visit" and "assessment" not in encounter.background:
        problems.append(f"{where}: a visit's background includes the admission assessment")
    if encounter.kind == "assessment" and encounter.background:
        problems.append(f"{where}: the admission assessment has no background")
    return problems


def cast_digest(cast: Cast) -> str:
    """A hash of the whole cast; two seeds of the same cast report the same digest."""
    payload = json.dumps(asdict(cast), sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def _d(value: str) -> date:
    return date.fromisoformat(value)


def load_cast() -> Cast:
    return Cast(cases=(_CASE_BACK, _CASE_MULTIPLE, _CASE_GAPS))


_CASE_BACK = Case(
    case_number="FIK-2026-001",
    patient_name="Hanna Erlenbach",
    label="Einzelnes Schmerzproblem",
    period_start=_d("2026-10-05"),
    period_end=_d("2026-10-16"),
    encounters=(
        Encounter(
            key="assessment",
            kind="assessment",
            date=_d("2026-10-05"),
            entered_on=_d("2026-10-05"),
            notes=(
                "Patientin lebt mit Ehemann in einer Etagenwohnung, zwei erwachsene Kinder, "
                "arbeitet halbtags im Büro, aktuell krankgeschrieben. Vor 3 Jahren "
                "Bandscheibenvorfall L4/5 konservativ behandelt. Seit 14 Monaten tiefer "
                "Rückenschmerz, belastungsabhängig, NRS 6 im Mittel. Ibuprofen 400 mg bei "
                "Bedarf, bis zu 2 Tabletten täglich, Wirkung gering. Physiotherapie 2024 mit "
                "kurzer Besserung, Wärmeanwendungen. Keine Vorerkrankungen internistisch, "
                "kein Nikotin, kein Alkohol. Untersuchung: Druckschmerz paravertebral L4 bis S1, "
                "Lasègue negativ, Reflexe seitengleich. Stationäre Aufnahme zur multimodalen "
                "Schmerztherapie, weil ambulant über 12 Monate ausgeschöpft. Ziel: Gehstrecke "
                "von 500 m auf 2 km steigern."
            ),
            draft={
                "Sozialanamnese": (
                    "Lebt mit dem Ehemann in einer Etagenwohnung, zwei erwachsene Kinder. Arbeitet "
                    "halbtags im Büro, aktuell krankgeschrieben."
                ),
                "Frühere Anamnese und Vormedikation": (
                    "Bandscheibenvorfall L4/5 vor drei Jahren, konservativ behandelt."
                ),
                "Therapeutische Anamnese": (
                    "Ibuprofen 400 mg bei Bedarf, bis zu zwei Tabletten täglich, Wirkung gering. "
                    "Physiotherapie 2024 mit kurzer Besserung, Wärmeanwendungen."
                ),
                "Schmerzanamnese": (
                    "Tiefer Rückenschmerz seit 14 Monaten, belastungsabhängig, NRS im Mittel 6."
                ),
                "Internistische, vegetative, psychiatrische und Suchtmittelanamnese": (
                    "Keine internistischen Vorerkrankungen. Kein Nikotin, kein Alkohol."
                ),
                "Untersuchungsbefunde": (
                    "Druckschmerz paravertebral L4 bis S1, Lasègue negativ, Reflexe seitengleich."
                ),
                "Behandlungsplan und vereinbarte Ziele": (
                    "Stationäre multimodale Schmerztherapie, weil die ambulanten Möglichkeiten "
                    "über zwölf Monate ausgeschöpft sind. Ziel: Gehstrecke von 500 m auf 2 km."
                ),
            },
            audio=(
                FixtureClip(
                    key="fik-001-assessment-dictation",
                    transcript=(
                        "Ergänzung zur Aufnahme: Die Patientin gibt an, nachts durch den Schmerz "
                        "etwa zweimal aufzuwachen."
                    ),
                ),
            ),
        ),
        Encounter(
            key="visit-1",
            kind="visit",
            date=_d("2026-10-09"),
            entered_on=_d("2026-10-09"),
            notes=(
                "Schmerz im Verlauf unverändert, NRS 5 bis 6. Nimmt kein Ibuprofen mehr seit "
                "dem 7.10. Teilnahme an der Bewegungstherapie gut. Befund: Druckschmerz L4 bis "
                "S1 etwas geringer. Einschätzung nach Gespräch: Bewegungstherapie wird "
                "fortgeführt. Vereinbart: tägliche Gehstrecke um 100 m steigern."
            ),
            draft={
                "Verlauf seit letzter Visite": (
                    "Schmerz unverändert, NRS 5 bis 6. Seit dem 7.10. kein Ibuprofen mehr. "
                    "Teilnahme an der Bewegungstherapie gut."
                ),
                "Aktuelle Befunde": "Druckschmerz L4 bis S1 etwas geringer.",
                "Ärztliche Einschätzung": "Die Bewegungstherapie wird fortgeführt.",
                "Vereinbartes Vorgehen und Ziele": "Tägliche Gehstrecke um 100 m steigern.",
            },
            background=("assessment",),
            audio=(
                FixtureClip(
                    key="fik-001-visit-1-dictation",
                    transcript=(
                        "Visite vom neunten Oktober. Die Patientin schläft seit drei Nächten durch."
                    ),
                ),
            ),
        ),
    ),
    timeline=(("accept", "assessment"), ("generate", "visit-1")),
)

_CASE_MULTIPLE = Case(
    case_number="FIK-2026-002",
    patient_name="Bruno Tannenfeld",
    label="Mehrere Schmerzprobleme",
    period_start=_d("2026-10-12"),
    period_end=_d("2026-10-23"),
    encounters=(
        Encounter(
            key="assessment",
            kind="assessment",
            date=_d("2026-10-12"),
            entered_on=_d("2026-10-12"),
            notes=(
                "Patient wohnt allein, Frührentner seit 2023 (ehemals Lagerarbeiter), Schwester "
                "wohnt in der Nähe. Migräne seit der Jugend, 3 Attacken pro Monat, Sumatriptan "
                "50 mg wirksam, Prophylaxe mit Topiramat 2022 wegen Nebenwirkungen beendet. "
                "Linkes Knie, Gonarthrose, seit 5 Jahren belastungsabhängig, Diclofenac 75 mg "
                "bei Bedarf, Physiotherapie 2025, Infiltration 2025 ohne Dauerwirkung. "
                "Brennende Schmerzen beider Füße seit 2 Jahren bei Polyneuropathie, Pregabalin "
                "75 mg zweimal täglich, Wirkung teilweise. Schlaf auf 4 bis 5 Stunden "
                "verkürzt, Alltag eingeschränkt, Einkäufe nur mit Hilfe. Diabetes mellitus "
                "Typ 2, Metformin. Kein Nikotin, gelegentlich Bier. Befund: Knie links "
                "Erguss gering, Streckung frei, Beugung 110 Grad, Füße Hypästhesie "
                "strumpfförmig. Ziele: Schlaf verbessern, Gehstrecke steigern, "
                "Einkäufe selbständig."
            ),
            draft={
                "Sozialanamnese": (
                    "Wohnt allein, seit 2023 Frührentner, zuvor Lagerarbeiter. Die Schwester "
                    "wohnt in der Nähe."
                ),
                "Frühere Anamnese und Vormedikation": (
                    "Migräne seit der Jugend. Diabetes mellitus Typ 2. Topiramat zur Prophylaxe "
                    "2022 wegen Nebenwirkungen beendet."
                ),
                "Therapeutische Anamnese": (
                    "Sumatriptan 50 mg bei Migräne wirksam. Diclofenac 75 mg bei Bedarf, "
                    "Physiotherapie 2025 und Infiltration 2025 am linken Knie ohne "
                    "Dauerwirkung. Pregabalin 75 mg zweimal täglich, Wirkung teilweise. "
                    "Metformin."
                ),
                "Schmerzanamnese": (
                    "Migräne, drei Attacken pro Monat. Linkes Knie bei Gonarthrose seit fünf "
                    "Jahren, belastungsabhängig. Brennende Schmerzen beider Füße seit zwei "
                    "Jahren bei Polyneuropathie. Schlaf auf vier bis fünf Stunden verkürzt, "
                    "Einkäufe nur mit Hilfe."
                ),
                "Internistische, vegetative, psychiatrische und Suchtmittelanamnese": (
                    "Diabetes mellitus Typ 2. Kein Nikotin, gelegentlich Bier."
                ),
                "Untersuchungsbefunde": (
                    "Linkes Knie: geringer Erguss, Streckung frei, Beugung 110 Grad. Füße: "
                    "strumpfförmige Hypästhesie."
                ),
                "Behandlungsplan und vereinbarte Ziele": (
                    "Ziele: Schlaf verbessern, Gehstrecke steigern, Einkäufe selbständig."
                ),
            },
            clarifications=(
                Clarification(
                    "Schmerzanamnese",
                    "Welcher der drei Schmerzen steht im Vordergrund, und welche Zahl gilt je "
                    "Schmerz auf der numerischen Skala?",
                ),
            ),
            audio=(
                FixtureClip(
                    key="fik-002-assessment-dictation",
                    transcript=(
                        "Nachtrag zur Aufnahme: Die Fußschmerzen sind abends am stärksten, "
                        "Sumatriptan wird höchstens zweimal pro Woche genommen."
                    ),
                ),
            ),
        ),
        Encounter(
            key="visit-1",
            kind="visit",
            date=_d("2026-10-16"),
            entered_on=_d("2026-10-16"),
            notes=(
                "Migräne in dieser Woche 1 Attacke, Sumatriptan wirksam. Knie unverändert, "
                "Schlaf 5 Stunden. Heute Beugung links 115 Grad. Einschätzung nach Gespräch: "
                "Knieschmerz ist der Hauptschmerz. Vereinbart: Kniegymnastik täglich."
            ),
            draft={
                "Verlauf seit letzter Visite": (
                    "Eine Migräneattacke in dieser Woche, Sumatriptan wirksam. Knie "
                    "unverändert, Schlaf fünf Stunden."
                ),
                "Aktuelle Befunde": "Beugung links 115 Grad.",
                "Ärztliche Einschätzung": "Der Knieschmerz ist der Hauptschmerz.",
                "Vereinbartes Vorgehen und Ziele": "Kniegymnastik täglich.",
            },
            background=("assessment",),
        ),
        Encounter(
            key="visit-2",
            kind="visit",
            date=_d("2026-10-14"),
            entered_on=_d("2026-10-19"),
            notes=(
                "Nachgetragen für den 14.10. Pregabalin auf Wunsch des Patienten abends "
                "vorgezogen, Schlaf 4 Stunden. Fußschmerz brennend, NRS 7. Befund nicht "
                "erhoben. Vereinbart: Schlafprotokoll führen."
            ),
            draft={
                "Verlauf seit letzter Visite": (
                    "Pregabalin auf Wunsch des Patienten abends vorgezogen. Schlaf vier Stunden. "
                    "Fußschmerz brennend, NRS 7."
                ),
                "Aktuelle Befunde": "",
                "Ärztliche Einschätzung": "",
                "Vereinbartes Vorgehen und Ziele": "Schlafprotokoll führen.",
            },
            clarifications=(
                Clarification("Aktuelle Befunde", "Für diese Visite ist kein Befund notiert."),
                Clarification(
                    "Ärztliche Einschätzung", "Für diese Visite ist keine Einschätzung notiert."
                ),
            ),
            background=("assessment",),
            audio=(
                FixtureClip(
                    key="fik-002-visit-2-dictation",
                    transcript=(
                        "Nachtrag zum vierzehnten Oktober: Der Patient hat gut mitgearbeitet."
                    ),
                ),
            ),
        ),
    ),
    # The assessment is corrected and accepted again after visit-1's draft was
    # generated, so visit-1 shows the changed background. visit-2 came later.
    timeline=(
        ("accept", "assessment"),
        ("generate", "visit-1"),
        ("accept", "assessment"),
        ("generate", "visit-2"),
    ),
)

_CASE_GAPS = Case(
    case_number="FIK-2026-003",
    patient_name="Rosa Lindenau",
    label="Lücken in den Angaben",
    period_start=_d("2026-10-19"),
    period_end=_d("2026-10-30"),
    encounters=(
        Encounter(
            key="assessment",
            kind="assessment",
            date=_d("2026-10-19"),
            entered_on=_d("2026-10-19"),
            notes=(
                "Chronischer Schulter-Nacken-Schmerz rechts seit dem Sommer, vielleicht "
                "schon länger. Tramadol retard 50 mg zweimal täglich, an anderer Stelle "
                "steht 100 mg zweimal täglich. Vorher Ibuprofen, Dauer unklar. Seit einem "
                "Sturz im Frühjahr schlechter. Befund: Hartspann Trapezius rechts, Rotation "
                "endgradig schmerzhaft. Begründung für den stationären Aufenthalt "
                "bislang nicht dokumentiert."
            ),
            draft={
                "Sozialanamnese": "",
                "Frühere Anamnese und Vormedikation": (
                    "Ibuprofen vor der aktuellen Medikation, Dauer unklar."
                ),
                "Therapeutische Anamnese": "Tramadol retard zweimal täglich, Dosis unklar.",
                "Schmerzanamnese": (
                    "Chronischer Schulter-Nacken-Schmerz rechts, Beginn unklar. Verschlechterung "
                    "nach einem Sturz im Frühjahr."
                ),
                "Internistische, vegetative, psychiatrische und Suchtmittelanamnese": "",
                "Untersuchungsbefunde": (
                    "Hartspann im rechten Trapezius, Rotation endgradig schmerzhaft."
                ),
                "Behandlungsplan und vereinbarte Ziele": "",
            },
            clarifications=(
                Clarification("Sozialanamnese", "Die Notizen enthalten keine Sozialanamnese."),
                Clarification(
                    "Therapeutische Anamnese",
                    "Die Angaben zu Tramadol widersprechen sich: 50 mg oder 100 mg zweimal "
                    "täglich.",
                ),
                Clarification(
                    "Schmerzanamnese",
                    "Der Beginn ist unklar: seit dem Sommer oder länger. Welcher Zeitpunkt "
                    "gilt für den Sturz im Frühjahr?",
                ),
                Clarification(
                    "Internistische, vegetative, psychiatrische und Suchtmittelanamnese",
                    "Die Notizen enthalten keine internistische, psychiatrische oder "
                    "Suchtmittelanamnese.",
                ),
                Clarification(
                    "Behandlungsplan und vereinbarte Ziele",
                    "Die Begründung für den stationären Aufenthalt fehlt, ebenso Ziele und "
                    "Behandlungsplan.",
                ),
            ),
            audio=(
                FixtureClip(
                    key="fik-003-assessment-dictation",
                    transcript=(
                        "Zur Aufnahme: Die Patientin kann sich an den genauen Beginn der "
                        "Schmerzen nicht erinnern."
                    ),
                ),
            ),
        ),
        Encounter(
            key="visit-1",
            kind="visit",
            date=_d("2026-10-23"),
            entered_on=_d("2026-10-23"),
            notes=(
                "Schmerz im Nacken etwas besser, genaue Zahl nicht erfragt. Tramadol "
                "unverändert, die Dosis wurde heute nicht geklärt."
            ),
            draft={
                "Verlauf seit letzter Visite": (
                    "Nackenschmerz etwas besser. Tramadol unverändert."
                ),
                "Aktuelle Befunde": "",
                "Ärztliche Einschätzung": "",
                "Vereinbartes Vorgehen und Ziele": "",
            },
            clarifications=(
                Clarification("Aktuelle Befunde", "Für diese Visite ist kein Befund notiert."),
                Clarification(
                    "Ärztliche Einschätzung", "Für diese Visite ist keine Einschätzung notiert."
                ),
                Clarification(
                    "Vereinbartes Vorgehen und Ziele",
                    "Für diese Visite ist kein Vorgehen und kein Ziel notiert.",
                ),
                Clarification(
                    "Verlauf seit letzter Visite",
                    "Die Tramadol-Dosis widerspricht sich weiterhin zwischen den Quellen.",
                ),
            ),
            background=("assessment",),
        ),
    ),
    timeline=(("accept", "assessment"), ("generate", "visit-1")),
)

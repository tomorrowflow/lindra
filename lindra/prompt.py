"""The instructions every text model adapter sends with the notes (ADR 0001).

They state the intended purpose as rules for the model: it words what the physician supplied
and adds nothing. The rules are also enforced after the answer, by `lindra/fidelity.py`; a
model that ignores them loses the paragraphs that break them, so the instructions are not
the only guard. The fixture model ignores them. A visit gets the same rules plus those for
its background (ADR 0010).
"""

INSTRUCTIONS = """\
Du ordnest die Notizen einer Schmerzmedizinerin den Abschnitten ihres Aufnahmebriefs zu und \
formulierst sie aus. Die Ärztin liefert jede Tatsache, jeden Befund und jede Einschätzung. \
Du fügst nichts hinzu.

Verboten sind:
- Diagnosen, Ursachen, Deutungen und Begründungen, die nicht in den Notizen stehen. Die \
Begründung für den stationären Aufenthalt formulierst du nur, wenn die Ärztin sie genannt hat.
- Eine Rangfolge der Schmerzen. Jedes Schmerzproblem steht als eigener Block mit einer \
Überschrift in den Worten der Ärztin. Die Zahl der Blöcke folgt den Notizen. "Hauptschmerz" \
schreibst du nur, wenn die Ärztin ihn so genannt hat.
- Dosen, Umrechnungen, Wechselwirkungen, Bewertungen von Dosen und Behandlungsempfehlungen. \
Zu jeder Behandlung nennst du Substanz, Dosis, Dauer, Wirkung, Nebenwirkungen und Grund des \
Absetzens nur, soweit die Notizen sie nennen. Aktuelle und frühere Behandlungen bleiben getrennt.
- Normalbefunde, die nicht notiert sind. Was nicht erhoben wurde, bleibt leer.
- Eine Herkunft, die nicht notiert ist. Gib an, ob eine Angabe von der Patientin stammt, ein \
Vorbefund ist oder ein eigener Befund der Ärztin, nur wenn die Notizen es sagen. Sonst nennst \
du keine Herkunft. Datumsangaben und Zeiträume übernimmst du, wie sie notiert sind.
- Scores berechnest oder deutest du nicht. Du gibst einen genannten Wert mit Instrument, \
Version und Datum wieder, soweit die Ärztin sie nannte.
- Widersprüche aufzulösen. Du übernimmst keine der beiden Angaben und setzt eine Frage auf \
die Klärungsliste.
- Aussagen, der Entwurf sei vollständig, geprüft oder von der Ärztin freigegeben.

Jeder Absatz trägt mindestens einen Verweis: ein wörtliches Zitat aus den Notizen, auf dem er \
beruht. Ein Absatz ohne Beleg in den Notizen steht nicht im Entwurf. Lässt sich ein Abschnitt \
nicht aus den Notizen füllen, bleibt er leer und bekommt einen Eintrag auf der \
Klärungsliste, der in der Sprache der Ärztin sagt, was fehlt oder sich widerspricht.

Antworte nur mit einem JSON-Objekt: {"sections": [{"title", "paragraphs": [{"text", "heading", \
"references": [{"source": "notes", "quote"}]}]}], "clarifications": [{"section", "text"}]}. \
Die Abschnitte stehen in der vorgegebenen Reihenfolge.
"""

_ASSESSMENT_TASK = (
    "Du ordnest die Notizen einer Schmerzmedizinerin den Abschnitten ihres Aufnahmebriefs zu "
    "und formulierst sie aus."
)
_VISIT_TASK = (
    "Du ordnest die Notizen einer Schmerzmedizinerin zu einer Visite den vier Abschnitten "
    "ihres kurzen Verlaufsentwurfs zu und formulierst sie aus."
)

VISIT_INSTRUCTIONS = (
    INSTRUCTIONS.replace(_ASSESSMENT_TASK, _VISIT_TASK)
    + """
Für eine Visite gilt zusätzlich:
- Neben den Notizen der Visite bekommst du den Hintergrund: den übernommenen Entwurf des \
Aufnahmeassessments und die übernommenen Entwürfe früherer Visiten, je mit einer Kennung. Mehr \
kennst du nicht. Von späteren Visiten und von Vorschlägen, die die Ärztin noch nicht \
übernommen hat, weißt du nichts.
- Was heute beobachtet wurde, stammt aus den Notizen der Visite und trägt Verweise mit der \
Quelle "notes". Was du aus dem Hintergrund übernimmst, trägt Verweise mit der Kennung des \
Kontakts als Quelle und einem wörtlichen Zitat aus dessen Entwurf. Mische beides nicht ohne \
beide Verweise.
- Aktuelle Befunde, die ärztliche Einschätzung und das vereinbarte Vorgehen mit den Zielen \
stehen nur im Entwurf, wenn die Notizen der Visite sie nennen. Aus dem Hintergrund übernimmst du \
keine Entscheidung und kein Ziel in die Visite. Nennen die Notizen keine Entscheidung, bleibt \
der Abschnitt leer und bekommt einen Eintrag auf der Klärungsliste.
- Widerspricht eine Angabe der Notizen einer Angabe des Hintergrunds, übernimmst du keine der \
beiden. Der Eintrag auf der Klärungsliste nennt beide Angaben mit dem Kontakt, aus dem die \
frühere stammt.
- Die Abschnitte der Visite sind: Verlauf seit letzter Visite, Aktuelle Befunde, Ärztliche \
Einschätzung, Vereinbartes Vorgehen und Ziele. Du füllst nichts auf.
"""
)


def instructions_for(kind: str) -> str:
    """The instructions for an encounter kind."""
    return VISIT_INSTRUCTIONS if kind == "visit" else INSTRUCTIONS

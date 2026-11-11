# The result check

Every generation result passes two checks before it becomes a proposal. Both run whichever text model answered (ADR 0003), and both enforce the intended purpose of ADR 0001: Lindra words what the physician supplied and adds nothing.

## Structure check

`lindra/drafts.py` (`parse_generated`) decides whether the result is a draft at all. It needs the exact sections of the encounter kind in the form's order, paragraphs with text, well-formed input references and clarification items that name a real section. Prose, a missing section or a malformed reference is a failed generation. The notes, the draft and the earlier proposal stay as they were, and the status area shows the reason with a retry button.

Inside the Schmerzanamnese a paragraph may carry any heading of up to 80 characters, the name the physician gave a pain problem. Every other section allows only the form's subsection headings, and only Therapeutische Anamnese and Untersuchungsbefunde have any.

## Support check

`lindra/fidelity.py` (`check_result`) decides which paragraphs of a structured result may stay. A paragraph stays only when all of these hold.

1. Every input reference points into a source the encounter has and quotes it word for word, in at most 300 characters. Runs of whitespace count as one space. A longer quote would carry every wording and number of the notes and switch the other checks off. At the moment the only source is the encounter's notes. Ticket 09 adds the background encounters of a visit.
2. Every number and date in the paragraph is in the passages it quotes, and every quantity keeps its unit ("400 g" does not match "400 mg"; "Monate" matches "Monaten"). Spelled-out numbers count as the digits they stand for, so "zweimal" matches "2". This catches a converted dose, an invented duration and a summed score.
3. It uses none of the wordings that only the physician supplies (listed below) unless a quoted passage uses the same wording.
4. It words no provenance (the patient's report, a prior finding, the physician's own finding) that a quoted passage does not name. A statement without a named source stays without one.
5. It does not settle a contradiction. A sentence of the notes that names two or more measures and says it is uncertain or disagrees ("Tramadol retard 50 mg zweimal täglich, an anderer Stelle steht 100 mg zweimal täglich") sets those measures against each other, and so does a model item like "50 mg oder 100 mg". A paragraph of any section that names only some of them is dropped, whether or not the model flagged the contradiction. Two drugs in one sentence ("Ibuprofen 400 mg, Metamizol 500 mg") are not a contradiction.
6. It does not cut a quote out of a sentence whose rest says the notes are uncertain. If the sentence holds "an anderer Stelle", "vielleicht", "unklar" or a similar wording that the paragraph's quotes leave out, the paragraph is dropped. If a quote holds such a wording, the paragraph must carry the uncertainty too ("unklar", "offen", "oder" or the wording itself).
7. Every word of four letters or more that is not a function word comes from the passages the paragraph quotes. A word counts as coming from a passage when it is the same word inflected ("lebt" and "leben", "Monate" and "Monaten") or when most of it sits in a word of the passage ("Schmerz" in "Rückenschmerz"). "Fibromyalgie" or "Radikulopathie" is dropped when its quote holds no such word. Words that only say something is unclear ("Dosis unklar") and the wording of a provenance the quote licenses do not need a source. A pain problem's heading may come from anywhere in the notes, because it is the physician's name for the pain. The form's own headings come from the form.

Each dropped paragraph becomes a clarification item for its section that says what was missing and that the paragraph is not in the draft. A section left with no paragraph and no item gets "Die Notizen enthalten keine Angaben für diesen Abschnitt." The model's own items come first. The check errs toward dropping, which shows the physician a gap. It never errs toward keeping a fact the notes do not hold.

### Wordings that need the physician's own words

| Kind | Examples |
| --- | --- |
| Ranking of pains | Hauptschmerz, im Vordergrund, führend, vorrangig |
| Diagnosis or cause | Diagnose, Verdacht, Ursache, zurückzuführen, spricht für, Syndrom, Störung |
| Justification or a cause given as a reason | weil, wegen, aufgrund, Begründung, indiziert, Indikation, notwendig, erforderlich |
| Recommendation | empfohlen, Empfehlung, sollte, ratsam, angezeigt |
| Normal finding | unauffällig, regelrecht, o. B., physiologisch, normal |
| Interaction, conversion | Wechselwirkung, Interaktion, kontraindiziert, äquivalent, umgerechnet |
| Reading of a score | klinisch relevant, auffällig, pathologisch, mittelgradig |
| Effect or tolerance | wirksam, ohne Wirkung, gut verträglich, ohne Nebenwirkung |
| Completeness or approval | vollständig, geprüft, freigegeben, bestätigt |
| Time | the seasons, the months, gestern, kürzlich |

## What the check does not prove

- The lists are a lexicon. They name the wordings the intended purpose forbids, and the word check (rule 7) covers the facts they do not name. Neither can know every wording.
- A valid reference shows that the passage exists in the notes. It does not show that the passage supports the paragraph. A paragraph can rearrange real words of its quote into a statement the notes do not make ("Schmerz" and "links" from two places of one quote). ADR 0008 says an input reference shows origin, not correctness, and the interface says nothing more.
- The word match is by spelling, not by meaning. A word that shares most of its letters with a different word of the passage passes, and a correct synonym ("Beschwerden" for "Schmerzen") is dropped. A real model will lose paragraphs to this. The loss shows as a gap with a clarification item, and the real-backend evaluation (ticket 11 and after) measures how often.
- A short term has to start a word ("wegen" does not match "bewegen"). A term of seven letters or more may sit inside a compound ("Störung" finds "Schlafstörung").
- A date written another way ("2.10.2026" for "02.10.2026") counts as a different number and drops the paragraph.
- A contradiction is held back when the notes show it in one sentence with a cue ("an anderer Stelle", "oder", "widerspricht") or the model flagged it. A contradiction that sits in two separate sentences without a cue, and that the model did not flag, is not caught.
- The fixture model returns the cast's expected drafts, so the tests prove the check and the workflow, not the fidelity of a real model. Ticket 11 and the evaluation measure that.

## Instructions to the model

`lindra/prompt.py` holds the instructions every adapter sends with the notes. They state the same rules to the model. The support check does not rely on them; a model that ignores them loses the paragraphs that break them.

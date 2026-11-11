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
5. It does not settle a contradiction. When the model put an item on the clarification list that sets two or more measures against each other ("50 mg oder 100 mg"), a paragraph of any section that names only some of them is dropped.

Each dropped paragraph becomes a clarification item for its section that says what was missing and that the paragraph is not in the draft. A section left with no paragraph and no item gets "Die Notizen enthalten keine Angaben für diesen Abschnitt." The model's own items come first.

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

- The lists are a lexicon. They catch the wordings the intended purpose forbids. They cannot know every wording, and a model can phrase a diagnosis the lists do not contain.
- A valid reference shows that the passage exists in the notes. It does not show that the passage supports the paragraph: a paragraph that quotes real notes and says something unrelated passes unless it uses one of the listed wordings or an unquoted number. ADR 0008 says an input reference shows origin, not correctness, and the interface says nothing more.
- A short term has to start a word ("wegen" does not match "bewegen"). A term of seven letters or more may sit inside a compound ("Störung" finds "Schlafstörung"). The lists name no diagnoses, so "Fibromyalgie" passes unless the notes name it elsewhere in the quoted passage.
- A date written another way ("2.10.2026" for "02.10.2026") counts as a different number and drops the paragraph.
- A contradiction is held back only when the model flagged it. A model that settles a contradiction without flagging it is not caught here.
- The fixture model returns the cast's expected drafts, so the tests prove the check and the workflow, not the fidelity of a real model. Ticket 11 and the evaluation measure that.

## Instructions to the model

`lindra/prompt.py` holds the instructions every adapter sends with the notes. They state the same rules to the model. The support check does not rely on them; a model that ignores them loses the paragraphs that break them.

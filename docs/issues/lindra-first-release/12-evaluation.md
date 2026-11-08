# 12: Evaluation: the protocol, Ella's timed run on the fictional cases and the recorded result

**Track:** evaluation

**What to build:** A written evaluation protocol and timing sheet that Ella follows on the long-lived test environment: for each of the three fictional cases she prepares the admission assessment and the visits with her template workflow and with Lindra, typed and dictated, and the sheet captures total time including review, correction and transcript correction, plus her judgement of fabricated statements, lost facts, consistency between visits and the assessment, and usability. The result is recorded in the repository against the release target (at least 30 percent less total preparation time, no fabricated clinical statement, no lost relevant fact); a missed target creates focused follow-up tickets and is never weakened after the fact.

**Blocked by:** 01 (Scaffold), 02 (Environments), 03 (Install test), 05 to 11 (through 11, Real backends)

**Status:** ready-for-agent

**Spec:** PRD stories 37, 38; ADR 0006 (evaluation release and target), ADR 0010 (cast with periods and visits).

## Acceptance criteria

- [ ] The protocol describes the three fictional cases, the order of tasks (assessment, then each visit), both input modes (typed, dictated with transcript correction), what counts as a fabricated statement and as a lost relevant fact, and how time is measured from first note to last copied section.
- [ ] The timing sheet has one row per case, encounter and mode for the template workflow and for Lindra, with total time, counts of fabricated statements and lost facts, consistency findings, and a usability note.
- [ ] The evaluation runs on the long-lived test environment with the deterministic stand-ins for the workflow timing and, where the operator chooses, on the evaluation configuration of ticket 11 for output quality; which configuration was used is recorded per row.
- [ ] Operator-run, at the end of the release: Ella performs the protocol on her iPad and desktop against `LINDRA_TEST_URL`; the operator records the sheet in the repository.
- [ ] The result compares against the target per encounter kind; a met target is stated plainly; a missed target is stated plainly with the numbers, and focused follow-up tickets are drafted under `docs/issues/` for the causes found; the target text is not changed.
- [ ] Real patient data is not used at any point; the record states that the evaluation release remains fictional-only and that real use needs the separate approval of ADR 0006.
- [ ] Unslop: the unslop skill and `references/signs.md` were read before writing the protocol and the record; the proof names the signs checked and remaining findings with reasons.

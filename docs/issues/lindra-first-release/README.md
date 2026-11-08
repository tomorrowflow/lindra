# Tickets for Lindra's first release (SPEC-1)

Twelve tracer-bullet tickets, one file each, numbered in dependency order. They come from the spec `docs/prd/lindra-first-release.md`, approved in grill 6 and reworked in review round 1 (authentication owned by 01, dictation waiting for 07). Terms are as in `CONTEXT.md`; decisions as in `docs/adr/`.

| # | File | Track | Blocked by |
| --- | --- | --- | --- |
| 01 | `01-scaffold.md` | scaffold | none |
| 02 | `02-environments.md` | environment | 01 |
| 03 | `03-install-test.md` | environment | 02 (blocks only 12) |
| 04 | `04-install-prod.md` | environment | 02 (blocks nothing) |
| 05 | `05-cases-and-periods.md` | case | 01, 02 |
| 06 | `06-encounters-and-notes.md` | case | 01, 02, 05 |
| 07 | `07-assessment-review.md` | draft | 01, 02, 05, 06 |
| 08 | `08-fidelity-and-clarifications.md` | draft | 01, 02, 05, 06, 07 |
| 09 | `09-visit-review-and-background.md` | draft | 01, 02, 05, 06, 07, 08 |
| 10 | `10-dictation.md` | dictation | 01, 02, 05, 06, 07 |
| 11 | `11-real-backends.md` | inference | 01, 02, 05 to 09, 10 |
| 12 | `12-evaluation.md` | evaluation | 01, 02, 03, 05 to 11 |

Every ticket after 01 depends on 01; every ticket after 02 also depends on 02. The frontier after 01 and 02 is 03, 04 and 05.

## What every ticket carries

- A `Track`, the `Blocked by` list, acceptance criteria as checkboxes, and a `Proof` section naming the commands, throwaway-stack evidence, screenshots and operator-run confirmations the ticket closes with.
- `Operator-run` items for checks no factory node can perform (physical iPad, inference hardware, the test and production installs, Ella's evaluation), each saying when it happens.
- The unslop requirement for UI and documentation work (ADR 0009).

## Ticket proof for SPEC-1 itself

The spec ticket is proven by its documents alone: `git diff --check` from the review base is clean, and the diff touches only `docs/` and `CONTEXT.md`. Implementation evidence belongs to the tickets above, not to SPEC-1.

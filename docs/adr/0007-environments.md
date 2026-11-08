---
status: accepted
date: 2026-11-08
---

# Environments: throwaway, test and production tiers for a hosted web service

Lindra has a hosted runtime (the web service, its SQLite file and the model adapters), so it has three environment tiers, each its own Linux identity, sharing one compose file and one executable Python script `scripts/env.py` with the commands `up`, `check`, `reset`, `down`, `ensure-test` and `install-timer`.

## Tiers

| Tier | Who runs it | Where | What it runs |
| --- | --- | --- | --- |
| Throwaway | the `factory` user, per ticket | the ticket's own stack in rootless Docker on the ticket's node | the ticket branch |
| Test | user and OpenClaw node `lindra-test` | rootless Docker on Linux 790, port 8780, compose project `lindra-test` | only `origin/main`, refreshed by `scripts/env.py ensure-test` from the user timer `lindra-test-env.timer` every 5 minutes |
| Production | the operator as `frogger`, never a ticket or agent | open, see below | a `main` commit that is green on test, deployed by the operator following the runbook in `docs/environments.md` |

The test host is Linux 790 on the operator's choice, conditional on a suitability check (free port 8780, rootless Docker, no production service running there). If it is unsuitable the host is a new decision; nobody substitutes another host silently. The test port 8780 is the preferred port and may change if it is taken, in which case the ADR is updated.

## Outside services and their stand-ins

| Service | Stand-in in tests and in the test tier |
| --- | --- |
| Text model (self-hosted, ADR 0003) | fixture model: deterministic drafts keyed to the fictional cast |
| Hosted text model, evaluation comparison only (ADR 0003) | the same fixture model; the hosted adapter never runs in tests or in the test tier |
| Speech recognition (self-hosted, ADR 0003) | canned transcripts keyed to fixture audio |

There is no other outside service. The persistent test stack always runs the stand-ins. A real-backend evaluation configuration (self-hosted, or the hosted comparison) is launched separately and explicitly, uses only the fictional cast, and is never the test tier's default. The hosted comparison needs a vendor account; the operator approved its use for the evaluation but not any spending, so the account and its key stay with the operator and are never committed.

## Data, secrets, access

- `reset` seeds the fictional cast and nothing else; never real, pseudonymised or production-copied data.
- Nodes read `LINDRA_TEST_URL` and `LINDRA_TEST_TOKEN`. `up` writes a gitignored env file with a generated test token when it is missing; test secrets are generated on the test node and never committed. Production secrets stay with the operator.
- Production holds no real patient data until the separate approval in ADR 0006 exists.

## Open decision: the production host

The host for real clinical use is open pending the legal and organisational check (ADR 0006, `docs/research/2026-11-04-legal-frame-patient-data-and-llms.md`): a cloud host would have to meet §393 SGB V, an in-hospital or physician-side box would not, and the hospital's own approval is needed either way. Until then, `04-install-prod` installs the evaluation configuration on a host the operator names, and `env.py check` passing there does not imply authorisation for real data.

# 02: Environments: compose, `scripts/env.py`, stand-ins, fictional cast and the runbook

**Track:** environment

**What to build:** A developer brings up a throwaway Lindra stack on their node with one command, checks it, resets it to the fictional cast and tears it down, all through `scripts/env.py`. The same compose file and script serve the long-lived test tier (user and node `lindra-test`, refreshed from `origin/main` by a user timer) and the operator's production runbook. The stack runs on deterministic stand-ins for the text model and speech recognition, so nothing needs a GPU or an outside service. The fictional cast is defined here as seed data and loaded by a seed hook that `reset` calls; ticket 05 connects that hook to case storage.

**Blocked by:** 01 (Scaffold)

**Status:** ready-for-agent

**Spec:** ADR 0007 (environments), ADR 0003 (stand-ins), ADR 0006 and ADR 0010 (fictional cast), `docs/prd/lindra-first-release.md` Environments.

## Acceptance criteria

- [ ] One compose file (with the compose override the tiers need) runs the service and its SQLite volume in rootless Docker; the throwaway stack uses a ticket-specific compose project name, the test tier uses `lindra-test` on port 8780.
- [ ] `scripts/env.py` is executable Python with the commands `up`, `check`, `reset`, `down`, `ensure-test` and `install-timer`; each is idempotent (running it twice converges to the same state).
- [ ] `up` creates a gitignored env file with a generated test token when it is missing and never commits secrets; `check` calls the health endpoint and the login with the token and exits non-zero on failure; `down` removes the stack and keeps nothing that a later `up` would trip over.
- [ ] `reset` seeds the fictional cast and nothing else, through a seed hook the application exposes; the cast is three invented German cases, each with a fictional case number, a fictional patient name, a treatment period, an admission assessment and at least one visit (one backdated), with notes, expected fixture drafts, expected clarification items and fixture audio with canned transcripts; one case carries an assessment change accepted after a visit draft; the third case leaves gaps. No real, pseudonymised or production-copied data; no reproduction of the ward's forms or the operator's documents.
- [ ] Until case storage exists (ticket 05), `reset` proves the mechanism: the seed hook validates and reports the cast without storing it, and `check` confirms the hook ran; the ticket's proof shows `up`, `check`, `reset`, `down` passing on a throwaway stack on the developer's node.
- [ ] The text model stand-in (fixture model keyed to the cast) and the speech stand-in (canned transcripts keyed to fixture audio) are selected by configuration and are the default of the throwaway and test tiers; no configuration path enables a real or hosted backend in these tiers.
- [ ] `ensure-test` fetches `origin/main`, redeploys when the deployed commit differs, runs `check`, and does nothing otherwise; `install-timer` installs and starts the user timer `lindra-test-env.timer` running `ensure-test` every 5 minutes.
- [ ] Nodes read `LINDRA_TEST_URL` and `LINDRA_TEST_TOKEN`; the documentation names them.
- [ ] `docs/environments.md` documents every tier: user, node, host, port, compose project, commands, data rule and stand-ins; the throwaway and test procedures; the production runbook for the operator as `frogger` (deploy a `main` commit that is green on test, run `check`); and that the production host is an open decision and that production holds no real data without the separate approval (ADR 0006, ADR 0007). `AGENTS.md` points to it.
- [ ] Unslop: the unslop skill and `references/signs.md` were read before work for the changed documentation; the proof names the signs checked and remaining findings with reasons.

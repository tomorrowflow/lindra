# 03: Install the long-lived test environment on Linux 790

**Track:** environment

**What to build:** The long-lived test tier exists: user and OpenClaw node `lindra-test` on Linux 790 run the stack from `origin/main`, refreshed every 5 minutes, and every factory node can reach it through `LINDRA_TEST_URL` and `LINDRA_TEST_TOKEN`. Every check in this ticket is operator-run or runs on the test node itself; no factory node can perform them from a worktree.

**Blocked by:** 02 (Environments). Blocks only 12 (Evaluation), the one ticket whose proof uses the long-lived test environment.

**Status:** ready-for-agent

**Spec:** ADR 0007 (test tier on Linux 790, conditional on suitability), `docs/environments.md` from ticket 02.

## Acceptance criteria

- [ ] Operator-run, before anything is installed: the operator checks Linux 790 for suitability, no production service running there, rootless Docker available, port 8780 free. If it is unsuitable, the ticket stops and the host becomes a new decision; nobody substitutes another host silently.
- [ ] Operator-run: the operator runs `~/linux-test-node-wizard.sh tomorrowflow/lindra` on Linux 790, creating the user and OpenClaw node `lindra-test` with rootless Docker.
- [ ] Operator-run: as node `lindra-test`, dev runs `scripts/env.py up`, then `check`, then `install-timer`; `up` generates the test token on the test node, `check` passes against port 8780, and `lindra-test-env.timer` is active and runs `ensure-test` every 5 minutes.
- [ ] Operator-run: the operator puts the URL and the token into the node profile as `LINDRA_TEST_URL` and `LINDRA_TEST_TOKEN`; from another node, `scripts/env.py check` against those values passes.
- [ ] Operator-run: after a new commit on `origin/main`, the test tier shows that commit within 5 minutes without anyone touching it, and `reset` on the test node seeds only the fictional cast.
- [ ] The test tier runs the deterministic stand-ins; no real or hosted backend is configured there.
- [ ] `docs/environments.md` records the installed host, port, compose project and the date of installation.

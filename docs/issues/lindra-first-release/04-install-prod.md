# 04: Install production by the operator's runbook

**Track:** environment

**What to build:** The operator, as `frogger`, follows the runbook in `docs/environments.md` on the host they name and ends with a running Lindra stack against which `scripts/env.py check` passes. Every check is operator-run; tickets and agents never touch production.

**Why this ticket exists while the host is open:** ADR 0007 leaves the production host for real clinical use open pending the legal and organisational check (§393 SGB V for a cloud host, the hospital's own approval either way). This ticket installs the evaluation configuration on whatever host the operator names; passing it authorises no real patient data (ADR 0006). The open host decision is named here so nobody reads a green check as clearance.

**Blocked by:** 02 (Environments). Blocks nothing.

**Status:** ready-for-agent

**Spec:** ADR 0006, ADR 0007, `docs/environments.md` production runbook.

## Acceptance criteria

- [ ] Operator-run: the operator names the host and records in `docs/environments.md` that it is the evaluation host, not a cleared clinical host, while ADR 0007's open decision stands.
- [ ] Operator-run: as `frogger`, the operator follows the runbook step by step to deploy a `main` commit that is green on the test tier; production secrets are generated or held by the operator and never committed.
- [ ] Operator-run: `scripts/env.py check` passes against production.
- [ ] Operator-run: production runs the deterministic stand-ins unless the operator explicitly configures the self-hosted backends; no hosted-inference adapter is configured in production.
- [ ] Operator-run: `reset` on production seeds only the fictional cast; the runbook states that no real, pseudonymised or production-copied patient data may be loaded without the separate approval of ADR 0006.
- [ ] The runbook is corrected in the repository wherever the operator had to deviate from it.

## Proof

Every item is operator-run as `frogger`; the card comment that closes this ticket quotes them.

- The named host and the note in `docs/environments.md` that it is the evaluation host while ADR 0007's decision is open.
- The deployed `main` commit and the test-tier check that was green for it.
- The output of `scripts/env.py check` against production, exit code zero.
- The configuration in use (stand-ins or self-hosted backends; no hosted adapter) and the `reset` output showing only the fictional cast.
- Any runbook correction committed on this ticket's branch.

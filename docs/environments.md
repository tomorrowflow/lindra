# Environments

Lindra runs in three tiers: a throwaway stack per ticket, one long-lived test stack and the operator's production stack. All three use the same `compose.yaml` and the same script, `scripts/env.py`. The decision is in `docs/adr/0007-environments.md`; this file is the procedure.

## The tiers

| | Throwaway | Test | Production |
| --- | --- | --- | --- |
| User | `factory` | `lindra-test` | `frogger`, the operator |
| Node | the node that runs the ticket | OpenClaw node `lindra-test` | none; no ticket and no agent touches it |
| Host | the developer's node | Linux 790, `minisforum790.tail974337.ts.net` | open for clinical use. The evaluation host is `zotac1070`; see "The production host is open" |
| Port | a free port that `up` picks, on `127.0.0.1` | 8780, on all addresses | 8790 on `127.0.0.1` unless `up --port` and `--bind` say otherwise |
| Compose project | `lindra-<checkout directory>`, or the name given with `--project` (`lindra-lfr-02` for LFR-02) | `lindra-test` | `lindra-prod` |
| Compose files | `compose.yaml` | `compose.yaml` and `compose.test.yaml` | `compose.yaml` and `compose.prod.yaml` |
| Runs | the ticket branch | only `origin/main`, refreshed every 5 minutes by the user timer `lindra-test-env.timer` | a `main` commit that is green on the test tier |
| Commands | `scripts/env.py up`, `check`, `reset`, `down` | `scripts/env.py ... --tier test`, plus `ensure-test` and `install-timer` | `scripts/env.py ... --tier production` |
| Data rule | the fictional cast and nothing else | the fictional cast and nothing else | the fictional cast and nothing else, until the separate approval of ADR 0006 exists |
| Text model and speech recognition | stand-ins | stand-ins | stand-ins; the real backends arrive with a later ticket |
| Installed | not applicable | 2026-11-10 by ticket 03: host `minisforum790.tail974337.ts.net`, port 8780, compose project `lindra-test` | not yet. Ticket 04 names `zotac1070` as the evaluation host; the install is the operator's, as `frogger` |

The test port 8780 is the preferred port. If it is taken, the ADR and this table change together.

## Commands

Run them from a checkout with `python3 scripts/env.py <command>`. The script needs Python 3.12, git and Docker with the compose plugin; rootless Docker is the supported setup. Every command can run twice and ends in the same state. An exit code of 0 means success, 1 means a check or an action failed, and 2 means the command cannot run as asked.

| Command | What it does |
| --- | --- |
| `up` | Builds the image, starts the stack and waits until it is healthy. It creates the env file with a generated token when none exists, and runs the seed hook when the volume has not been seeded. `--tier test` and `--tier production` pick the other tiers; `--project`, `--port` and `--bind` adjust a stack. |
| `check` | Calls `/health`, the authenticated route `/api/session` with the token, and `/api/environment`. It fails unless both backends are the stand-ins and the seed hook has run for the current cast, so a redeploy that changes the cast fails `check` until `reset` or `up` seeds again. It exits non-zero on any failure, including a stack that is down. With `--remote` it checks the test tier through `LINDRA_TEST_URL` and `LINDRA_TEST_TOKEN` instead of a local stack. |
| `reset` | Calls the seed hook, which loads the fictional cast and nothing else. Until case storage exists (ticket 05) the hook validates the cast and reports it without storing it; `check` then confirms that the hook ran. |
| `down` | Removes the containers, the network and the volume. A throwaway stack also loses its image and env file, so a later `up` starts clean. The test tier keeps its env file so the published token stays valid, and production keeps its volume and env file; `--purge` removes those too. |
| `ensure-test` | Test tier only. Fetches `origin/main` and compares it with the commit the running stack reports. If they differ, or nothing answers, it checks out `origin/main`, runs `up --tier test` and then `check --tier test`. Otherwise it does nothing. It refuses to run in a checkout that is on a branch other than `main`, or that has uncommitted changes. |
| `install-timer` | Writes `lindra-test-env.service` and `lindra-test-env.timer` into `~/.config/systemd/user`, reloads systemd and enables and starts the timer. The timer runs `ensure-test` every 5 minutes. `--dry-run` writes the units to a temporary directory (or `--unit-dir`), prints them, runs `systemd-analyze --user verify` on them and installs nothing. |

The user running the timer needs lingering so the timer survives logout: `loginctl enable-linger lindra-test`. Ticket 03 does this when it installs the test tier.

## Files and variables

`up` writes `.lindra-env/<compose project>.env` with the token, the port, the bind address and the tier. Git ignores the directory, and the file is readable by its owner only. The token comes from `secrets.token_urlsafe(32)`. Nothing in the repository holds a token, a URL of a real stack or a real name.

Nodes read two variables from their profile to reach the test tier:

| Variable | Value |
| --- | --- |
| `LINDRA_TEST_URL` | The base URL of the test tier, for example `http://<host>:8780` |
| `LINDRA_TEST_TOKEN` | The token in `.lindra-env/lindra-test.env` on the test node |

The operator puts both into the node profile when ticket 03 is done. `scripts/env.py check --remote` reads them and never prints the token.

The service reads `LINDRA_TOKEN`, `LINDRA_DATA_DIR`, `LINDRA_TIER`, `LINDRA_COMMIT`, `LINDRA_TEXT_BACKEND` and `LINDRA_SPEECH_BACKEND` (see `.env.example`). `compose.yaml` sets both backends to `fixture` and takes no value for them from the env file.

## Stand-ins and the fictional cast

The throwaway, test and production stacks run two deterministic stand-ins (ADR 0003):

| Service | Stand-in | Source |
| --- | --- | --- |
| Text model | fixture model that returns the expected draft and clarification items of a cast encounter | `lindra/standins.py` |
| Speech recognition | canned transcripts, keyed to the fixture audio of the cast | `lindra/standins.py` |

Input outside the cast is refused, so a test cannot pass on invented output. `LINDRA_TEXT_BACKEND` and `LINDRA_SPEECH_BACKEND` accept only `fixture`; any other value stops the service at start. A real or hosted backend is a separate, explicitly launched evaluation configuration, never the default of a tier (ticket 11).

The cast lives in `lindra/cast.py` and is the only dataset: three invented German cases with case numbers `FIK-2026-001` to `FIK-2026-003`, invented patient names, a treatment period, an admission assessment and at least one visit each. One visit is backdated. The second case has an assessment change accepted after a visit draft was generated. The third case leaves gaps and carries contradictory doses and an unclear time reference. Every encounter has notes, an expected draft and clarification items, and every case has fixture audio with a canned transcript. The audio is generated from a key (a short tone) and no audio file is committed. The seed hook refuses a cast that breaks these rules.

Real, pseudonymised or production-copied patient data never goes into a tier or into the repository, and neither do the ward's forms or the operator's documents (ADR 0006).

## Throwaway procedure

Use this on the node that runs the ticket. It never touches the test tier or production.

1. `python3 scripts/env.py up --project lindra-<ticket>` builds and starts the stack and seeds the cast. The output names the URL and the env file.
2. `python3 scripts/env.py check --project lindra-<ticket>` must exit 0.
3. `python3 scripts/env.py reset --project lindra-<ticket>` runs the seed hook again. A second run reports the same digest.
4. `python3 scripts/env.py down --project lindra-<ticket>` removes everything. `check` now exits non-zero.

## Test procedure

The test tier was installed by ticket 03 on 2026-11-10, as node `lindra-test` on Linux 790 after the operator's suitability check.

| Item | Value |
| --- | --- |
| Host | Linux 790, `minisforum790.tail974337.ts.net` |
| URL | `http://minisforum790.tail974337.ts.net:8780` (the value of `LINDRA_TEST_URL`) |
| Port | 8780 |
| Compose project | `lindra-test` |
| Installed | 2026-11-10 |

1. In the dedicated checkout on `main`, run `scripts/env.py up --tier test`, then `check --tier test`, then `install-timer`.
2. From then on the timer runs `ensure-test` every 5 minutes. A new commit on `origin/main` is deployed without anyone touching the stack. Read the result with `journalctl --user -u lindra-test-env.service` on the test node.
3. From another node, set `LINDRA_TEST_URL` and `LINDRA_TEST_TOKEN` and run `scripts/env.py check --remote`. The `commit` line of the output names the deployed commit.
4. `scripts/env.py reset --tier test` on the test node seeds the fictional cast again.

Nobody edits the test checkout by hand; `ensure-test` stops when it finds uncommitted changes.

## Production runbook

The operator follows this as `frogger`. Production is never deployed by a ticket or an agent.

Before the first run, name the host and record it in "The production host is open" below, with the note that it is the evaluation host and not a cleared clinical host. Docker must run rootless for `frogger`.

1. Clone the repository: `git clone https://github.com/tomorrowflow/lindra.git`, then work in the checkout.
2. Choose the commit. It must be a `main` commit that the test tier runs and that passes `check`. With `LINDRA_TEST_URL` and `LINDRA_TEST_TOKEN` in the profile of `frogger`, run `scripts/env.py check --remote` and read the commit in its last `ok` line. Confirm that the continuous integration run for that commit is green.
3. Check it out: `git fetch origin main`, then `git checkout --detach <commit>`.
4. Deploy: `python3 scripts/env.py up --tier production --port <port> --bind <address>`. The first run generates the production token in `.lindra-env/lindra-prod.env`. Keep that file with the operator and never commit it. Later runs reuse the token, port and address. `check` and `reset` reach the stack on that address; a wildcard address (`0.0.0.0` or `::`) is reached through loopback.
5. Verify: `python3 scripts/env.py check --tier production` must exit 0. A passing check says the stack works. It does not authorise real patient data.
6. To update, repeat steps 2 to 5 with a newer commit. To roll back, check out the earlier commit and run step 4 again. The volume stays.
7. To stop the stack, run `scripts/env.py down --tier production`. Add `--purge` to remove the volume and the env file as well.

`reset --tier production` seeds the fictional cast and nothing else. No real, pseudonymised or production-copied patient data may be loaded into production without the separate approval of ADR 0006, and a host that meets the legal and organisational check (ADR 0007).

## The production host is open

The host for real clinical use is an open decision. It depends on the legal and organisational check in `docs/research/2026-11-04-legal-frame-patient-data-and-llms.md`: a cloud host would have to meet §393 SGB V, an in-hospital or physician-side box would not, and the hospital's own approval is needed either way. Until the decision exists, ticket 04 installs the evaluation configuration on a host the operator names, and a passing `check` there is not an authorisation for real data (ADR 0006, ADR 0007).

| Item | Value |
| --- | --- |
| Production host | open |
| Evaluation host | `zotac1070`, named by the operator on 2026-11-10 (ticket 04). It is the evaluation host, not a cleared clinical host, while ADR 0007's decision is open. |
| Real patient data | not allowed |

`zotac1070` is not connected to the OpenClaw environment, so no factory node, ticket or agent reaches it. The operator installs and checks the stack there as `frogger`.

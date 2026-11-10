# Working in this repository

Lindra is one Python web service (FastAPI, Jinja2 templates, server-driven German UI) with a SQLite database to come (ADR 0005). Terms are defined in `CONTEXT.md`; decisions live in `docs/adr/`; the release plan in `docs/prd/` and `docs/issues/`.

## Commands

Run Python through the project virtualenv. Nothing needs Node or a network at runtime.

| Task | Command |
| --- | --- |
| Install | `python3 -m venv .venv && .venv/bin/python -m pip install -e ".[dev]"` |
| Configure | `cp .env.example .env`, then put a token in `LINDRA_TOKEN` (see the file) |
| Run | `.venv/bin/python -m uvicorn lindra.app:app --factory --reload` and open `http://127.0.0.1:8000/` |
| Test | `.venv/bin/python -m pytest -q` |
| Lint | `.venv/bin/python -m ruff check .` |
| Format | `.venv/bin/python -m ruff format .` (CI runs `--check`) |
| Contrast check | `.venv/bin/python scripts/contrast_check.py` |
| Vendor assets | `python3 scripts/fetch_assets.py --check` verifies the pins; without `--check` it refetches |
| Screenshots | `.venv/bin/python -m playwright install chromium` once, then `.venv/bin/python scripts/screenshots.py` |
| CI lint | `docker run --rm -v "$PWD:/repo" -w /repo rhysd/actionlint:1.7.12 -no-color` |
| Throwaway stack | `python3 scripts/env.py up --project lindra-<ticket>`, then `check`, `reset` and `down` with the same `--project` |

CI (`.github/workflows/ci.yml`) runs install, lint, format check, vendor check, contrast check and tests on every push and pull request.

## Environments

`docs/environments.md` documents every tier (throwaway, test, production): user, node, host, port, compose project, commands, data rule and stand-ins, and the production runbook. A ticket runs only its own throwaway stack through `scripts/env.py` and never touches the test tier or production. The stack runs on the stand-ins and the fictional cast in `lindra/cast.py`; nothing real, pseudonymised or production-copied goes into any tier or into the repository (ADR 0006, ADR 0007).

## Code and tests

- Tests drive the HTTP API with the fixture stand-ins and assert what the physician would observe: status codes, page text, JSON bodies, what is saved. No assertions on sessions, templates, database rows or adapter internals. `tests/test_api.py` is the pattern.
- Every page and API route is guarded by `lindra/auth.py` by default; only `/health`, `/anmelden` and `/static/` are open. Do not add a second authentication mechanism.
- Settings are read once at the boundary (`lindra/config.py`); the rest of the code receives values.
- User-facing text is German. Follow `CONTEXT.md` for the words to use and the words to avoid.

## UI work: foundation and unslop

The UI is daisyUI 5 component CSS over native semantic HTML controls, pinned and self-hosted (`lindra/static/vendor/`, pins in `scripts/fetch_assets.py`), with the Quiet Clarity tokens in `lindra/static/css/quiet-clarity.css` (ADR 0009). No runtime CDN asset, no React or Web Awesome runtime, light theme only. The contrast results are in `docs/ui/contrast.md`, the browser check in `docs/ui/browser-check.md`. The operator's brand kit and design documents live in `docs/design/`; `docs/brand/README.md` says which of them the shell uses and where the copies in `lindra/static/img/` come from.

Every ticket that changes the UI, app copy, documentation or a report:

1. Reads both unslop skills before work. For UI: `~/.claude/library/unslop/unslop/SKILL.md` and its `references/signs.md` (CC BY 4.0, Damir Sokolovsky). For writing (app copy, documentation, reports): the pstack `unslop` skill, node-local copy at `~/.claude/library/pstack/unslop/SKILL.md`, source `/workspace/shared/syncthing/software-factory/pstack/skills/unslop/SKILL.md`. If a file is not readable, say so in the report; never claim a skill ran when it was unavailable.
2. Checks the final diff against both sets of signs.
3. Names in the proof the signs checked and every remaining finding with its reason.

Keep the approved layout (ADR 0008), libraries and brand kit. No unrelated redesign, no story videos, no image generation.

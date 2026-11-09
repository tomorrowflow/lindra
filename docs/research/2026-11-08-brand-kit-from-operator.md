# Research: Lindra brand kit supplied by the operator

Supplied by the operator on 8 November 2026 as `lindra-logo/brand-kit/` (operator's OneDrive, `openclaw/`), with a `README.md` describing its structure. Grill 6 read that README; the SPEC-1 session could not (outside its allowed paths). This note records what grill 6 relayed, with attribution. The kit complements the design research and the UI foundation; it does not replace them.

## What the kit says (as relayed by grill 6)

- Concept name: **Editorial Brackets**.
- Palette: Teal `#245B57`, Sage `#A8B9A7`, Ink `#243331`, Paper `#F7F5F0`, White.
- Wordmark: outlined lowercase Source Sans 3 SemiBold. The wordmark does not prescribe the UI font.
- Assets supplied: logo exports; use the full symbol at 24 px and above, the simplified mark below; keep the writing-line clear space around the mark.
- Asset exports do not add native-app scope.

## How it is used

- ADR 0009 reconciles the palette with the Quiet Clarity tokens: Teal is the accent candidate for forest teal, Paper the warm off-white, Ink the text colour, Sage a muted state or surface tint. Every combination is contrast-checked before it ships; the kit's values are proposals until then.
- The scaffold ticket needs readable repo-local copies of the assets and guidance. The worker obtains them from the operator; nobody claims to have read the kit without access.
- Logo and brand exploration stays non-blocking for the writing workflow (ADR 0009).

## Update, 9 November 2026

The operator pushed the complete kit to `docs/design/lindra-logo/brand-kit/` (`README.md`, preview sheet, `symbol/`, `lockup/`, `web/`, `app/`), together with the round 1 to 3 logo explorations and the theme kit (`docs/design/lindra/design-theme-prompt-kit.md`). `docs/brand/README.md` lists what the shell takes from it.

## Related

- `docs/research/2026-11-08-design-direction-from-operator-reports.md`
- `docs/adr/0009-ui-foundation-quiet-clarity-daisyui.md`

# Brand kit: what the shell uses and where it comes from

The operator pushed the brand kit "Editorial Brackets" and the design documents to `docs/design/` (commits `713999b`, `17168ea`, `45fa297`, 9 November 2026). The kit's own guidance is `docs/design/lindra-logo/brand-kit/README.md`. This note says what the application takes from it.

## In the repository

| What | Where | Used for |
| --- | --- | --- |
| Brand kit guidance: palette, wordmark, minimum size, clear space | `docs/design/lindra-logo/brand-kit/README.md` | the tokens and the logo rules |
| Symbol, lockups, wordmark, favicons, app icons (SVG and PNG) | `docs/design/lindra-logo/brand-kit/symbol/`, `lockup/`, `web/`, `app/` | source of the copies below |
| Quiet Clarity theme kit (draft recommendation, 8 November 2026) | `docs/design/lindra/design-theme-prompt-kit.md` | typography, spacing, the amber and red semantic colours |
| Logo explorations, rounds 1 to 3 | `docs/design/lindra-logo/svg/`, `round2/`, `round3/`, `lindra-concepts.*` | history; round 3's Editorial Brackets became the kit |
| Source Sans 3, the wordmark's typeface (SIL OFL 1.1) | `lindra/static/vendor/source-sans-3/` | the shell's text; the wordmark itself is outlined and needs no font |

## Copies the application serves

Ticket LFR-01 copied these files byte for byte from the kit into `lindra/static/img/` on 9 November 2026. When the kit changes, copy again from the same paths.

| File in `lindra/static/img/` | Kit source | Where it appears |
| --- | --- | --- |
| `lindra-horizontal-color.svg` | `lockup/lindra-horizontal-color.svg` | top bar of the shell (32 px high) and the login card (40 px) |
| `lindra-symbol-color.svg` | `symbol/lindra-symbol-color.svg` | reserved for places that fit only the symbol; not used yet |
| `favicon.svg`, `favicon.ico`, `apple-touch-icon.png` | `web/` | browser tab and iPad home screen, linked from `lindra/templates/base.html` with the kit's `theme-color` |

The shell follows the kit's rules. The full symbol never appears under 24 px (the top bar shows it at 32 px). The clear space around the lockup is at least the height of one of its writing lines. The Ink wordmark sits on Paper in the top bar and on White in the login card, which `docs/ui/contrast.md` records at 12.10 and 13.18 to 1.

Not taken over: `site.webmanifest`, the Open Graph image and the app icons. Lindra is a private web application with no install flow and no public page in the first release; a later ticket that adds a home-screen install takes `web/site.webmanifest` and the `icon-*.png` files from the kit.

## Tokens

`docs/ui/contrast.md` records how the palette became the Quiet Clarity tokens and the contrast of every text-on-surface pair. Where the theme kit and the brand kit disagree (the theme kit proposes `#24665B` for the primary, `#F7F8F5` for paper, `#203532` for ink), the brand kit wins per ADR 0009. Warning and error use the theme kit's amber `#865810` and red `#B43F46` because the brand kit has no semantic colours and both pass.

## Known leftovers in the kit folder

`docs/design/lindra-logo/brand-kit/` contains a few empty or few-byte files with cut-off names (`symbol/lindra-symbol-`, `symbol/lindra-symbol-whi`, `lockup/lindra-horizon`, `lockup/lindra-s`, `web/favicon-`). The operator will remove them; nothing references them.

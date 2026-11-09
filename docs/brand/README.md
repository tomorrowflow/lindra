# Brand kit: what is in the repository and what is not

The operator pushed the design documents to `docs/design/` on 9 November 2026 (commit `713999b`). This note says which part of the brand kit "Editorial Brackets" that covers and how the shell uses it.

## Present in the repository

| What | Where | Used for |
| --- | --- | --- |
| Brand kit guidance: palette, wordmark, minimum size, clear space | `docs/design/lindra-logo/brand-kit/README.md` | the tokens and the logo rules below |
| Preview sheet of the chosen mark and lockups (raster) | `docs/design/lindra-logo/brand-kit/_preview.jpg` | visual reference only; not a source for the shell |
| Quiet Clarity theme kit (draft recommendation, 8 November 2026) | `docs/design/lindra/design-theme-prompt-kit.md` | typography, spacing, the amber and red semantic colours |
| Round 1 logo concepts: Ordered Strands, Folded L, Open Frame, Quiet Convergence, Distinctive Wordmark | `docs/design/lindra-logo/svg/`, `lindra-concepts.html`, `lindra-concepts.png` | history; none of these is the chosen mark |
| Round 2 and round 3 exploration sheets (raster) | `docs/design/lindra-logo/round2/`, `round3/` | history |
| Source Sans 3, the wordmark's typeface (SIL OFL 1.1) | `lindra/static/vendor/source-sans-3/` | the shell's text and the product name in the top bar |

How the kit became tokens, with every pair contrast-checked: `docs/ui/contrast.md`. Where the theme kit and the brand kit disagree (the theme kit proposes `#24665B` for the primary, `#F7F8F5` for paper, `#203532` for ink), the brand kit wins per ADR 0009; the theme kit's amber `#865810` and red `#B43F46` were adopted for warning and error because the brand kit has no semantic colours and both pass.

## Not present

The brand kit README lists folders `symbol/`, `lockup/`, `web/` and `app/` with the vector mark, the lockups, the outlined wordmark, the favicons and the app icons. These folders are not in `docs/design/`; only the README and the preview sheet arrived. The round 1 SVGs are earlier concepts, not the Editorial Brackets mark.

So the shell still shows the product name as text (lowercase, Source Sans 3 SemiBold, Teal) and no symbol. The layout keeps one place for the mark, in front of the name in the top bar, at 24 px or more with the writing-line clear space the kit asks for. No favicon is served. Nobody redrew the mark from the preview image: that would be logo work, which ADR 0009 keeps out of the writing workflow.

## To complete

The operator adds the kit's `symbol/`, `lockup/` and `web/` folders under `docs/design/lindra-logo/brand-kit/`. A follow-up then copies `symbol/small-color.svg` and the full symbol into `lindra/static/img/`, places the symbol in the top bar and serves `web/favicon.svg`.

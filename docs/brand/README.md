# Brand kit: what is in the repository and what is not

The operator supplied the brand kit "Editorial Brackets" on 8 November 2026 in `lindra-logo/brand-kit/` on their OneDrive (`openclaw/`). What grill 6 relayed from it is recorded in `docs/research/2026-11-08-brand-kit-from-operator.md`.

## Present in the repository

- The palette as tokens, contrast-checked: `lindra/static/css/quiet-clarity.css` and `docs/ui/contrast.md`.
- Source Sans 3 (the wordmark's typeface, SIL OFL 1.1), self-hosted in `lindra/static/vendor/source-sans-3/` with its licence. The shell sets the product name in it, lowercase, SemiBold, in Teal.

## Not present

The scaffold session (LFR-01) had no access to the operator's OneDrive, so the kit's files were not read and are not copied here:

- the kit's `README.md` and guidance,
- the logo exports (full symbol for 24 px and above, simplified mark below, writing-line clear space),
- the outlined wordmark.

The shell therefore shows the product name as plain text, not the outlined wordmark, and shows no logo. The layout has one place for a mark, in front of the name in the top bar; it stays empty until the exports are in `docs/brand/`.

## To complete

The operator copies the kit's `README.md` and the logo exports into `docs/brand/`, keeping the kit's own file names, and notes the licence or ownership of the artwork in this file. A follow-up then replaces the text name with the wordmark export where the kit's guidance says so.

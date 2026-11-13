# ADR 0009 amendment, icon language: draft for the operator's decision (LFR-13)

Status: draft, not applied. `docs/adr/0009-ui-foundation-quiet-clarity-daisyui.md` is unchanged until the operator picks an option. The comparison page and the contrast table come from `scripts/kubai_icons.mjs` and are written to this folder (`index.html`, `results.md`).

## What the Kubai sources are (read in `docs/kubai-icons/`, 12 November 2026)

- `packages/static/package.json` says `kubai-icons-static` 0.5.1, licence MIT. The ticket named 0.4.1. The pinned version is the one in the repository commit. The built `svg/`, `icons.json` and `categories.json` are not committed (`.gitignore`); `tools/build.mjs` writes them. The icon definitions in `icons/*.js` (910 base icons plus badge composites) and the renderer `packages/core/src/render.js` are committed.
- Licences by folder (`LICENSING.md`). Icons, badges and the four packages are MIT (`LICENSE-ICONS`). `site/`, `tools/`, `tests/` and `docs/` are all rights reserved and need written permission to copy or host. `SKILL.md`, `PROMPT.md`, `src/`, `index.html`, `scripts/` and `history/` are under the source-available Kubai Icons License. The commit `8d2a2fd` put the whole upstream repository under `docs/kubai-icons/`, which includes the all-rights-reserved and source-available parts. See "Licence scope" below.
- An icon is layered. A back piece and a front piece carry gradient fills, an outline sits outside the shape, white marks sit inside, and a blurred drop shadow in the accent colour sits under the whole icon. Badged icons (`file-check`, `clipboard-check`) add a solid disc in `#33363D` that does not follow the accent unless a badge colour is set.
- Colour comes from one accent. `renderSVG(def, { accent })` writes exact hex values at build time. `renderInner(def, { paint: 'css' })` writes `color-mix()` steps over `currentColor`, which is the form Kubai's own element uses, so inline markup follows the text colour.
- Motion is not CSS. `packages/core/src/runtime.js` calls each icon's `draw()` on every animation frame for 460 ms, and `draw()` rewrites path data (`d`) and transforms. With `prefers-reduced-motion: reduce` the runtime jumps to the end pose without animating. The static SVG files contain no motion.

## Mapping of the 27 icons

Generated list in `results.md`; renders in `index.html` and `docs/screenshots/LFR-13/`. Summary: 21 have a Kubai icon of the same name (`file-check` and `cloud-off` are badge and slash composites). Six have only an icon under another name. No Kubai icon is missing outright. Same name does not mean same drawing; the renders show these differences:

- `menu` is a list card, not three lines. Its hover end pose is an x, so it reads as a close control.
- `chevron-left` and `chevron-right` are arrows inside a disc, and `circle-*` icons are filled discs. At 18 px the Teal and Ink recolours of all of them read as dark grey dots with a faint mark.
- `rotate-cw` is a disc with a letter-like arc that reads as a "C" or a copyright sign at 18 px. `sync` is a disc with two small arrows that does not resolve at 18 px.
- `log-out` is a door with a small arrow. The arrow is a few pixels wide at 18 px.
- `clipboard-check` is a plain clipboard at rest. The check mark appears only in the hover end pose, so a static icon cannot say "copied". The status area uses this icon for exactly that state.
- `file-check` and `cloud-off` keep their meaning at rest (badge disc, slash).

| Lucide now | Kubai | Why it is only near |
| --- | --- | --- |
| `plus` | `circle-plus` | no bare plus; the badge `plus` exists only on a corner |
| `x` | `circle-x` | no bare x |
| `check` | `circle-check` | no bare check; it repeats row `circle-check` |
| `loader-circle` | `loader` | spinner drawn differently; the busy status shows it without any rotation today |
| `refresh-cw` | `sync` | two-arrow cycle drawn differently |
| `file-pen` | `notebook-pen` | no file with a pen; the badge list of `file` has no pen |

## Contrast and size

Full tables in `results.md`. The recoloured outline is the part that carries the shape. In Teal it is 7.11 to 1 on Paper at the least and 10.69 to 1 where the engine deepens it (7.75 and 11.65 on White). In Ink it is 12.10 to 14.74 to 1 on Paper (13.18 and 16.06 on White). The usual gradient body is 2.88 to 1 on Paper and 3.14 to 1 on White for Teal, and the lightest fill is 1.4 to 1 to 1.6 to 1. So the body fill alone does not reach the 3 to 1 that WCAG asks of a graphic that carries meaning; the outline does. Kubai derives the deepest outlines from the accent by lightness, which turns Teal into `#1C3D45`, a bluer step than any brand kit colour, and badge discs are a fixed `#33363D`. Both would have to be recorded in `docs/ui/contrast.md` as added tokens.

At 18 px the drawing is small. The static file keeps 31 of 36 units for the drawing, and the 18 px column in `index.html` shows the glyphs as blobs next to Lucide's lines. At 24 px they read, but the icon column then needs 24 px boxes, which changes the layout rhythm of the action bar and the status line (ADR 0008).

## How the five conflicts in the ticket resolve

1. **Restrained local icons.** Kubai is coloured, shaded and has a drop shadow. This is a real change of the Quiet Clarity rule, not a reading of it. The unslop skill's icon rules (one stroke, text role colour, never their own colours) and its sign "coloured glows and shadows" would also need an exception for the icon set.
2. **Brand tokens.** Resolved. Recolour to Teal or Ink at build time. Inline markup in `color-mix()` form also follows `currentColor`, so the status tones (error, warning, success, secondary) keep working from CSS.
3. **No runtime CDN.** Resolved. Vendor the pinned files under `lindra/static/vendor/`. No call to `icons.kubai.design` or jsdelivr.
4. **No component runtime.** Resolved for static and inline markup, which need no script. Not resolved for hover motion (see options).
5. **Reduced motion and colour alone.** Static icons have no motion. For motion, the end pose must replace the animation under `prefers-reduced-motion`. Icons still sit beside text, so no state depends on icon colour alone.

## Options

**(a) Adopt Kubai, recoloured, no animation.** The macro in `icons.html` keeps its signature and emits Kubai inline markup (or inlines vendored SVG). One set, one accent (Teal), status tones through `currentColor`. Needs: the amended wording below, six near-match decisions, a box-size decision (a static file keeps 31 of 36 units for the drawing, so it looks about 14 percent smaller than inline markup in the same box), and a contrast pass on every tone.

**(b) Adopt Kubai with hover animation.** The ticket describes this as "self-hosted CSS". The sources do not allow that. Hover motion is JavaScript that rewrites path data per frame, and CSS cannot animate `d` in Safari. The real cost is vendoring `kubai-icons` core (`runtime.js`, `motion.js` and each icon's `target`/`draw`, MIT) and running it. That reopens the "no component runtime" decision for decoration on a documentation screen, and every animated state needs the reduced-motion rule. Not recommended unless the operator wants the motion itself.

**(c) Keep Lucide and close.** No change to the ADR. Add one line to it that records this evaluation and why Kubai was not adopted.

## Recommendation

(c), unless the operator wants the Kubai look for its own sake. The shell is a documentation tool for a physician, with icons beside text at 18 px, and the evidence gives four reasons. The icons shrink to blobs at 18 px. The recoloured set loses Kubai's identity, since Teal and Ink icons read as grey discs. Four icons change meaning (`menu`, `rotate-cw`, `sync`, `clipboard-check`). The set conflicts with the unslop icon rules and with the ADR's "restrained" wording. If the operator picks (a), use 24 px inline markup and choose other Kubai names for `menu`, `rotate-cw`, `sync` and `clipboard-check`. The ticket rules out a mixed set, so no Lucide icon stays.

## Proposed amendment text, for (a)

Replace the clause "a few restrained local SVG icons" in the first paragraph with "one local icon set, Kubai Icons (MIT, `kubai-icons-static` sources pinned in the repository), recoloured to the Teal accent at build time".

Add this section after "Brand kit":

> ## Icon language (added 2026-11-12, LFR-13)
>
> The shell uses one icon set, Kubai Icons, in the Teal recolour, drawn at one size, with its drop shadow. The set replaces the 27 Lucide icons; no template mixes the two. Icons are decorative, sit next to text and carry no state alone. The macro `icon(name)` in `lindra/templates/icons.html` stays the only entry point.
>
> The files are vendored and pinned under `lindra/static/vendor/kubai-icons-static/<version>/` with the MIT licence text. No icon, colour or script loads from `icons.kubai.design`, jsdelivr or any other host at runtime. Hover motion is not used; the web component and the runtime are not vendored. Icons take their colour from `currentColor`, so status tones stay in CSS and are contrast-checked in `docs/ui/contrast.md`.
>
> This is an exception to the unslop icon rules (one stroke weight, text-role colour, no coloured shadow). The exception covers the icon set only.

## Licence scope of `docs/kubai-icons/`

Commit `8d2a2fd` added the whole upstream repository. The operator decided on 13 November 2026 to cut it to `icons/`, `badges/`, `packages/`, `LICENSE-ICONS` and `LICENSING.md` on `main`. `scripts/kubai_icons.mjs` reads only those folders (`icons/`, `badges/`, `packages/core/src/`), so it keeps working after the cut. It does not use the upstream `tools/` folder, which is all rights reserved. Phase 2 vendors MIT files only.

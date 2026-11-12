# ADR 0009 amendment, icon language: draft for the operator's decision (LFR-13)

Status: draft, not applied. `docs/adr/0009-ui-foundation-quiet-clarity-daisyui.md` is unchanged until the operator picks an option. The comparison page and the contrast table come from `scripts/kubai_icons.mjs` and are written to this folder (`index.html`, `results.md`).

## What the Kubai sources are (read in `docs/kubai-icons/`, 12 November 2026)

- `packages/static/package.json` says `kubai-icons-static` 0.5.1, licence MIT. The ticket named 0.4.1. The pinned version is the one in the repository commit. The built `svg/`, `icons.json` and `categories.json` are not committed (`.gitignore`); `tools/build.mjs` writes them. The icon definitions in `icons/*.js` (910 base icons plus badge composites) and the renderer `packages/core/src/render.js` are committed.
- Licences by folder (`LICENSING.md`). Icons, badges and the four packages are MIT (`LICENSE-ICONS`). `site/`, `tools/`, `tests/` and `docs/` are all rights reserved and need written permission to copy or host. `SKILL.md`, `PROMPT.md`, `src/`, `index.html`, `scripts/` and `history/` are under the source-available Kubai Icons License. The commit `8d2a2fd` put the whole upstream repository under `docs/kubai-icons/`, which includes the all-rights-reserved and source-available parts. See "Open point for the operator" below.
- An icon is layered. A back piece and a front piece carry gradient fills, an outline sits outside the shape, white marks sit inside, and a blurred drop shadow in the accent colour sits under the whole icon. Badged icons (`file-check`, `clipboard-check`) add a solid disc in `#33363D` that does not follow the accent unless a badge colour is set.
- Colour comes from one accent. `renderSVG(def, { accent })` writes exact hex values at build time. `renderInner(def, { paint: 'css' })` writes `color-mix()` steps over `currentColor`, which is the form Kubai's own element uses, so inline markup follows the text colour.
- Motion is not CSS. `packages/core/src/runtime.js` calls each icon's `draw()` on every animation frame for 460 ms, and `draw()` rewrites path data (`d`) and transforms. With `prefers-reduced-motion: reduce` the runtime jumps to the end pose without animating. The static SVG files contain no motion.

## Mapping of the 27 icons

Generated list in `results.md`. Summary: 21 have an exact Kubai counterpart (same object, `file-check` and `cloud-off` as badge and slash composites). Six have only a near one. No Kubai icon is missing outright.

| Lucide now | Kubai | Why it is only near |
| --- | --- | --- |
| `plus` | `circle-plus` | no bare plus; the badge `plus` exists only on a corner |
| `x` | `circle-x` | no bare x |
| `check` | `circle-check` | no bare check; it repeats row `circle-check` |
| `loader-circle` | `loader` | spinner drawn differently; the busy status shows it without any rotation today |
| `refresh-cw` | `sync` | two-arrow cycle drawn differently |
| `file-pen` | `notebook-pen` | no file with a pen; the badge list of `file` has no pen |

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

## Open point for the operator: licence scope of `docs/kubai-icons/`

Commit `8d2a2fd` added the whole upstream repository. Under `LICENSING.md`, copying `site/`, `tools/`, `tests/` and `docs/` of that repository needs written permission, and `SKILL.md`, `PROMPT.md` and `src/` are source-available, with `PROMPT.md` and `SKILL.md` text not to be copied into a product repository. Only `icons/`, `badges/` and `packages/` are MIT. Phase 2 vendors MIT files only. Decide whether `docs/kubai-icons/` stays in the repository, shrinks to the MIT folders, or moves out of it before the branch is merged.

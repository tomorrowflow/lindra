---
status: accepted
date: 2026-11-08
---

# UI foundation: light "Quiet Clarity" theme on daisyUI 5 component CSS, self-hosted, native controls

Settled in grilling 3 from two operator-supplied design reports (see `docs/research/2026-11-08-design-direction-from-operator-reports.md`). Release one has a single light theme called Quiet Clarity: warm off-white background, opaque writing surfaces, forest-teal actions, readable typography, a few restrained local SVG icons. No glass or refraction effects, no dark theme, no rich-text editor, no onboarding flow, no generated artwork. Brand and logo exploration is separate and does not block the writing workflow.

The component layer is daisyUI 5 component CSS over native semantic HTML controls, conditional on a target-browser check. Assets (CSS, fonts, icons) are pinned and self-hosted; no runtime third-party CDN and no React or Web Awesome runtime by default. System fonts are acceptable; Source Sans 3 is a candidate, not a requirement. If the compatibility check fails, the findings are reported and a Bootstrap alternative is brought back for decision; nothing is substituted silently.

Support policy: the latest two major Safari and iPadOS releases, and current desktop Chrome, Firefox, Edge and Safari. Older iPads are not promised. Accessibility is part of the foundation: visible keyboard focus, states that do not rely on colour alone, reduced-motion behaviour, touch targets of at least 44 by 44 CSS pixels, and contrast validated in the actual token combinations (the reports' hex values are proposals until checked).

We chose a CSS-only component layer because the UI is server-driven (ADR 0005, PRD) and a framework runtime would reopen that decision for one author's screen. We chose self-hosting because the application runs on a private network and must not pull assets from the internet at runtime. The compatibility and physical-iPad checks exist because the reports document upstream claims, not tested guarantees; CSS alone does not supply focus handling, autosave, accessibility or conflict-safe state.

## Brand kit (added 2026-11-08, grill 6)

The operator supplied a brand kit, "Editorial Brackets" (`docs/research/2026-11-08-brand-kit-from-operator.md`): Teal `#245B57`, Sage `#A8B9A7`, Ink `#243331`, Paper `#F7F5F0`, White; an outlined lowercase Source Sans 3 SemiBold wordmark that does not prescribe the UI font; logo exports with the full symbol at 24 px and above and a simplified mark below, with the writing-line clear space kept. The kit becomes the source of the Quiet Clarity tokens where it fits: Teal as the accent, Paper as the warm off-white, Ink as the text colour, Sage as a muted tint. Every token combination is contrast-checked before it ships; where a kit value fails, a darker or lighter step of the same hue is used and recorded. The logo appears in the shell only where the layout already has a place for it; brand exploration stays non-blocking.

## Writing and interface quality (added 2026-11-08, grill 6)

Every UI implementation ticket reads the unslop skill (`~/.claude/library/unslop/unslop/SKILL.md` and its `references/signs.md`) before work and checks its final diff against the signs; its proof names the signs checked and any remaining finding with the reason. The same applies to changed app copy, documentation and reports. The scaffold ticket writes this into the repository's `AGENTS.md`. The skill is CC BY 4.0 by Damir Sokolovsky; copies keep the credit. No unrelated redesign, no story videos, no image generation.

## Icon set (evaluated 2026-11-13, LFR-13)

The shell keeps its 27 Lucide icons (ISC licence, `lindra/templates/icons.html`). Kubai Icons 0.5.1 were compared with them and not adopted: at 18 px the Teal and Ink recolours read as grey discs, four icons change meaning (`menu`, `rotate-cw`, `sync`, `clipboard-check`), and the coloured, shaded set conflicts with "a few restrained local SVG icons". The evidence is in `docs/ui/icon-comparison/`.

## Consequences

- The scaffold ticket pins and self-hosts the chosen CSS, derives the tokens from the brand kit, records the browser check and the contrast results, and obtains readable repo-local copies of the brand assets from the operator; the physical-iPad compatibility check is operator-run before the CSS distribution is committed to.
- Keep the approved layout (ADR 0008); no new layout exploration and no mandatory sidebar.

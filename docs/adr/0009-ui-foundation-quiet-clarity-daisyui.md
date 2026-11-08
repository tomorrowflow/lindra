---
status: accepted
date: 2026-11-08
---

# UI foundation: light "Quiet Clarity" theme on daisyUI 5 component CSS, self-hosted, native controls

Settled in grilling 3 from two operator-supplied design reports (see `docs/research/2026-11-08-design-direction-from-operator-reports.md`). Release one has a single light theme called Quiet Clarity: warm off-white background, opaque writing surfaces, forest-teal actions, readable typography, a few restrained local SVG icons. No glass or refraction effects, no dark theme, no rich-text editor, no onboarding flow, no generated artwork. Brand and logo exploration is separate and does not block the writing workflow.

The component layer is daisyUI 5 component CSS over native semantic HTML controls, conditional on a target-browser check. Assets (CSS, fonts, icons) are pinned and self-hosted; no runtime third-party CDN and no React or Web Awesome runtime by default. System fonts are acceptable; Source Sans 3 is a candidate, not a requirement. If the compatibility check fails, the findings are reported and a Bootstrap alternative is brought back for decision; nothing is substituted silently.

Support policy: the latest two major Safari and iPadOS releases, and current desktop Chrome, Firefox, Edge and Safari. Older iPads are not promised. Accessibility is part of the foundation: visible keyboard focus, states that do not rely on colour alone, reduced-motion behaviour, touch targets of at least 44 by 44 CSS pixels, and contrast validated in the actual token combinations (the reports' hex values are proposals until checked).

We chose a CSS-only component layer because the UI is server-driven (ADR 0005, PRD) and a framework runtime would reopen that decision for one author's screen. We chose self-hosting because the application runs on a private network and must not pull assets from the internet at runtime. The compatibility and physical-iPad checks exist because the reports document upstream claims, not tested guarantees; CSS alone does not supply focus handling, autosave, accessibility or conflict-safe state.

## Consequences

- The scaffold ticket pins and self-hosts the chosen CSS and records the browser check; the physical-iPad compatibility check is operator-run before the CSS distribution is committed to.
- Keep the approved layout (ADR 0008); no new layout exploration and no mandatory sidebar.

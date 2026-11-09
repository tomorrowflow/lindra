# Research: design direction from two operator-supplied reports

Supplied by the operator during grilling 3 (8 November 2026) and reviewed there:

- `design-theme-prompt-kit.md` (operator's OneDrive, `openclaw/lindra/`)
- `lindra-design-system-library-research.md` (Fróði, via Syncthing)

The SPEC-1 session could not read the files themselves (outside its allowed paths), so this note records what grilling 3 took from them and decided. They are source reports and proposals, not adopted wholesale. On 9 November 2026 the operator pushed the first report to `docs/design/lindra/design-theme-prompt-kit.md`; the library research report is not in the repository yet.

## What the reports contributed

- A theme direction the grill named Quiet Clarity: warm off-white, opaque writing surfaces, forest-teal actions, readable typography, restrained local SVG icons. The proposed hex tokens are subject to contrast checks in the actual combinations.
- A component-library comparison recommending daisyUI 5 component CSS over native semantic HTML controls, with React and Web Awesome runtimes as alternatives that the grill rejected for release one, and Bootstrap as the fallback if compatibility fails.
- Source Sans 3 as a font candidate; system fonts remain acceptable.
- The library report permits glass or refraction effects; the theme kit does not. Grilling 3 resolved this by excluding them for release one.

## Limits noted in the grill

- The library report documents upstream evidence (versions, licences, activity, iPad and accessibility claims) that the grill did not independently reverify. The scaffold ticket verifies the selected distribution and records its limitations.
- CSS alone does not supply focus handling, autosave, accessibility or conflict-safe state management; those are application work.

## Where the decisions live

- `docs/adr/0009-ui-foundation-quiet-clarity-daisyui.md`
- `docs/adr/0008-case-screen-and-proposal-semantics.md` (the approved layout the theme is applied to)

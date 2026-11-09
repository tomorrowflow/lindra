# Lindra — design theme and image prompt kit

Draft recommendation · 8 November 2026 · Not an approved brand decision.

## Basis

Reviewed tomorrowflow/lindra's PRD at refs/workboard/grill/a883b96d-da8b-4ccc-b93d-bb4ee8fa8d3e, the active SPEC-1 workboard card, and both grilling results in its grilling attachment. The latest grilling supersedes the PRD where they differ: a case-screen prototype comes before final tickets; explicitly selected Ollama Cloud text-model comparison is permitted for fictional evaluation cases only. These are product constraints, not reasons to put infrastructure controls into the main writing interface.

Lindra's first release helps Ella, a physician in inpatient multimodal pain therapy, turn her own post-assessment notes into the initial physician-authored admission-letter sections. It is a German responsive web app for iPad and desktop. Typed notes and explicit dictation are equal inputs. The hospital system remains the record; individual sections are copied as plain text. This is initially a fictional-case evaluation release, not approval for real clinical use.

## Recommended direction: Quiet Clarity

A calm editorial writing instrument with clinical precision and human warmth. The visual idea is **information becoming legible without losing its origin**. An open, gently folded ribbon or a few parallel strands settling into ordered lines can express this. Avoid making the brand about illness, pain, or AI machinery.

Starting palette (proposed tokens; contrast must be checked in the implemented combinations):

| Token | Hex | Role |
|---|---|---|
| paper | #F7F8F5 | Main background |
| surface | #FFFFFF | Editing surfaces |
| ink | #203532 | Primary text |
| muted-ink | #526560 | Secondary text |
| primary | #24665B | Primary actions, brand |
| tint | #E6F0EB | Selected surfaces, gentle illustration fill |
| border | #D5DFDA | Decorative dividers; not sufficient alone for essential control boundaries |
| amber | #865810 | Stale drafts and clarification text |
| amber-tint | #FFF2D9 | Caution surface |
| red | #B43F46 | Recording and errors, always paired with labels/icons |

Use a readable humanist sans-serif (self-hosted Source Sans 3 is a candidate; system sans-serif fallback). Comfortable text density, 17–18 px writing text as a starting point, generous line height, clear headings, 8 px spacing rhythm, restrained 8–12 px panel radii. No ornamental font inside clinical text. Prefer legibility to large empty dashboard tiles.

Brand illustration and application icons are different asset families. Brand illustrations may use layered flat shapes and subtle curves. Functional icons must use a consistent 24×24 grid, approximately 1.75 px stroke, round caps and joins, and minimal detail. Produce final functional icons as SVG, not generated raster images. Generated images are concept references, not precise SVG deliverables.

## 1. Master prompt — give this to a design-capable language model

Act as a senior product designer and visual identity designer. Create a coherent draft design system for Lindra using the following brief. Work from the actual workflow, not generic medical SaaS conventions. Do not invent additional product scope. Make concrete recommendations rather than asking preliminary questions. Clearly label proposed visual choices as proposals.

PRODUCT: Lindra is a German responsive browser workspace for a physician in inpatient multimodal pain therapy. After assessment, she types/pastes or explicitly dictates her own notes, corrects the transcript, requests a draft, reviews and edits letter sections, and copies individual sections into the hospital system. Notes and editable draft sit side by side when space permits. It is not a diagnostic tool, patient chatbot, full EHR, ambient scribe, scheduling app or treatment recommender. The first release uses fictional cases only.

VISUAL DIRECTION: Quiet Clarity. Warm paper, deep forest-teal, clear dark text, muted sage accents, restrained editorial geometry, flat vector-style artwork, generous negative space. Convey order, traceability and physician control. Explore an open folded ribbon or strands becoming ordered lines as a distinctive mark. Avoid generic medical crosses, hearts, ECG waves, brains, robots, magic sparkles, shields implying certification, wellness leaves and glossy AI gradients. Use the starting palette and typography recommendations above.

DESIGN THE ACTUAL WORKSPACE: Small saved-case list; notes editor with typing and dictation actions equally discoverable; draft sections; compact clarification list; paragraph-level links back to notes. Show explicit generation, a pending proposal with accept/discard, preservation of current manual edits, stale-draft marking after notes change, and one-action section copying. Distinguish saved, saving and not-saved. Dictation states are idle, recording, transcribing and reviewing/correcting before acceptance into notes. Never communicate medical correctness with a green checkmark or confidence percentage. An input reference means origin, not verification. No mandatory wizard, fake analytics, PDF export or sending button.

DELIVER:
1. A concise design rationale and three mark variations within this one direction: open ribbon, ordered strands and abstract L. Recommend one for small-size recognition.
2. Light-theme tokens for backgrounds, text, action, focus, disabled, borders and semantic states. Include a proposed dark-theme mapping without spending the initial exploration budget on it. Specify WCAG AA contrast checks, visible keyboard focus, non-colour state cues, and touch targets at least 44×44 CSS px.
3. Typography, spacing, radius, elevation, icon and illustration rules. Include reduced-motion behaviour and a static recording indicator with text.
4. Desktop and landscape-iPad case-screen concepts, plus a narrow-screen arrangement preserving notes/draft context without tiny two-column editors. Use fictional identifiers only. German labels; suggested examples: Notizen, Diktat starten, Diktat stoppen, Transkript prüfen, In Notizen übernehmen, Entwurf erstellen, Vorschlag übernehmen, Verwerfen, Abschnitt kopieren, Klärungsbedarf, Änderungen nicht gespeichert. Draft headings: Aufnahmegrund, Schmerzanamnese, Relevante Anamnese und Befunde, Bisherige Therapieversuche, Funktionelle und psychosoziale Auswirkungen, Begründung der stationären Behandlung, Therapieziele when supplied.
5. Functional icon specifications for cases, notes, microphone, stop, transcription, transcript review, generation, source reference, clarification, stale draft, accept, discard, copy, saved, unsaved and delete. Distinguish transcript acceptance from draft acceptance by labels/context, not colour alone.
6. ComfyUI-ready natural-language positive prompts for one app-mark concept, one onboarding illustration, one empty-state illustration and one desktop visual concept. Provide shared style prefix, asset-specific subject/composition, exclusions and aspect ratio separately. Do not assume a checkpoint, LoRA or node exists. Do not include clinical narratives or real patient data.
7. A compact asset manifest naming purpose, filename, ratio, background and production format. Do not claim generated images are usable vectors, transparent PNGs or finished accessible UI.

## 2. ComfyUI reusable style prefix

Use this unchanged across an image batch; append ONE asset subject below:

“Lindra visual identity, Quiet Clarity design direction, calm editorial precision with human warmth, restrained contemporary European design, flat vector-style geometric illustration, deep forest teal and muted sage on warm off-white, clearly separated silhouettes, rounded consistent contours, minimal composition, deliberate generous negative space, information becoming ordered while retaining its origin, clean solid colour fields.”

Names and exact hex values alone do not enforce a palette. Use the selected reference image and a palette reference where the workflow supports them; normalise final colours in vector production.

### A. App-mark concept — square 1:1

“One standalone abstract brand symbol: a single broad open ribbon folding into a subtle lowercase l silhouette, one clear bend and a small deliberate gap, balanced compact silhouette, forest-teal shape on a solid warm off-white field, centred with 20 percent clear margin, front-facing orthographic graphic, legible as a tiny icon, no lettering, no enclosing rounded-square tile, no shadow.”

Generate the mark without a platform tile first; compose platform-specific app icons later. Also explore ordered parallel strands as an alternative, not combined with the ribbon in the same mark.

### B. Onboarding illustration — landscape 3:2

“Three loose abstract note fragments gently resolve into three orderly parallel text-like bars, a subtle curved connection preserves their relationship, a metaphor for organising physician-supplied information rather than inventing it, composition weighted to the right with empty space on the left for separately typeset interface copy, no readable text, no people, no medical instruments.”

### C. Empty state — square 1:1

“One simple open document shape with three short ordered lines and a small offset note fragment, understated reassuring editorial illustration, centred compact subject with extensive empty space, warm off-white background, no checkmark, no badge, no lettering.”

Use only on a genuinely empty case list or draft panel; never decorate an occupied writing surface.

### D. Functional icon exploration — square 1:1, one glyph per image

“One standalone interface glyph representing [SUBJECT], uniform monoline stroke with rounded caps and joins, no fill, dark forest-teal linework on plain white, front view, simple geometry, strong recognisable silhouette at 24 pixels, generous equal margins, no enclosing tile, no text.”

Subjects: microphone; solid stop square; two overlapping pages for copy; short document with pencil for notes; two linked small rectangles for source reference; document with small clock for stale draft. These override the shared prefix's solid-fill illustration treatment. Redraw selected concepts on the shared SVG grid; do not mix independently generated stroke weights.

### E. Desktop design mood image — landscape 16:10

“Straight-on desktop browser application concept, calm professional writing workspace, narrow saved-case sidebar and two large adjacent editing panels, left notes and compact dictation toolbar, right structured draft with clear section hierarchy and a small clarification area, warm off-white canvas, white surfaces, dark readable text-like lines, restrained forest-teal controls, realistic practical text density, no dashboard charts, no photographs, no device mockup perspective.”

This is a mood/layout image only. Typeset real German text in an actual prototype; do not rely on image-model lettering or treat the image as interaction proof.

## 3. Shared exclusions

No medical cross, red-cross emblem, heart, ECG, brain, stethoscope, robot, AI sparkle, diagnostic heatmap, certification badge, wellness spa, leaf logo, cute mascot, distressed patient, glossy 3D, glassmorphism, neon, purple-blue AI gradient, photorealism, heavy shadows, fine texture, tiny detail, watermark, stock branding or clinical claims. For standalone assets: no lettering, typography or UI screenshots.

Where the model supports a negative-conditioning input, put exclusions there. Otherwise express key constraints naturally in the positive prompt. Do not assume every model benefits from negative prompting or weighting syntax.

## 4. Consistent exploration workflow

1. Generate only the app mark first: three concepts × four seeds. Keep checkpoint, dimensions, prompt structure and generation settings fixed; record them. Compare shape, not random styling.
2. Pick a direction for exploration, then create one palette/mark reference sheet. This choice is a draft, not final brand approval.
3. Reuse the approved exploration reference through image conditioning if supported. A shared seed does not by itself preserve identity across different prompts.
4. Produce illustrations separately from functional glyphs. Keep angle, palette, shape language and margins fixed. Do not generate entire icon sheets when individual reusable assets are the goal.
5. Use model-appropriate native sizes, typically a roughly 1024 px square starting canvas where supported. Use the stated ratios for larger compositions; do not stretch images to fit.
6. Record checkpoint/version, workflow JSON, seed, dimensions, prompts, sampler/scheduler, steps, guidance and any reference strength. Select settings for the actual installed model, not a universal preset.
7. Check marks at 32 and 64 px, monochrome and inverted. Check icons at 16/24/32 px. Reject ambiguous silhouettes. Build final marks/icons in SVG; generate raster exports from those. Create alpha transparency explicitly if needed; a white background is not transparency.
8. Verify contrast, touch targets, German text, focus and workflow states in the actual prototype. Keep generated artwork off the clinical writing surfaces. No patient information goes into asset-generation prompts.

Suggested filenames: lindra-mark-ribbon-concept-01.png; lindra-onboarding-order-01.png; lindra-empty-cases-01.png; lindra-icon-copy-concept-01.png; lindra-workspace-mood-01.png. Export final vectors separately as .svg after redraw.

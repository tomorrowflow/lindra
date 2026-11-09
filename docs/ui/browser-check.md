# Target-browser check for the CSS distribution

ADR 0009 makes daisyUI 5 conditional on a check against the support policy: the latest two major Safari and iPadOS releases, and current desktop Chrome, Firefox, Edge and Safari. Ticket LFR-01 recorded this check on 8 November 2026.

## What was checked

The distribution is daisyUI 5.7.50. `scripts/fetch_assets.py` assembles it from the package's own per-component CSS (base layer plus button, drawer, menu, fieldset, label, input, alert). The author read the assembled file for the CSS features it relies on:

| Feature | Where daisyUI uses it | Shipped in |
| --- | --- | --- |
| `@layer` cascade layers | every rule | Safari 15.4, Chrome 99, Firefox 97 |
| CSS nesting (`&`) | most components | Safari 17.2, Chrome 120, Firefox 117 |
| `color-mix()` | borders, hover, disabled, placeholder | Safari 16.2, Chrome 111, Firefox 113 |
| `oklch()` colours | overlay, shadows | Safari 15.4, Chrome 111, Firefox 113 |
| `@property` | two registered custom properties | Safari 16.4, Chrome 85, Firefox 128 |
| `:has()` | drawer scroll lock | Safari 15.4, Chrome 105, Firefox 121 |
| `translate` property | drawer slide | Safari 14.1, Chrome 104, Firefox 72 |
| `100dvh` | drawer and shell height | Safari 15.4, Chrome 108, Firefox 101 |
| `transition-behavior: allow-discrete` | drawer visibility | Safari 17.4, Chrome 117, Firefox 129 |
| `animation-timeline: scroll()` | root scroll-gutter helper only | Chrome 115; Safari 26; Firefox behind a flag |

The upstream statement is "daisyUI 5 requires a browser that supports Tailwind CSS 4: Safari 16.4, Chrome 111, Firefox 128 or newer". The version numbers above are MDN compatibility data as the author remembers them; this network allowed no live check against MDN.

## Verdict

- The two latest major Safari and iPadOS releases and current Chrome, Edge and Firefox all exceed every minimum. The one feature outside the policy (`animation-timeline`) only sets the scrollbar gutter; a browser without it shows the default gutter and nothing else changes.
- The check passes on the version table. No Bootstrap alternative is needed.

## What was not checked here

- No Safari, Firefox or Edge could run on the factory node. Playwright rendered the pages in Chrome Headless Shell 156 only (`docs/screenshots/LFR-01/`).
- The operator checks the real iPad, as `docs/issues/lindra-first-release/01-scaffold.md` asks: on Ella's iPad in Safari, the sample page renders, controls are tappable at 44 by 44 CSS pixels, keyboard focus is visible with an external keyboard, reduced motion is respected and the drawer opens and closes in portrait. The operator records the result in a card comment naming the iPad model and the Safari version. A failure goes back to the operator with a Bootstrap alternative; nobody substitutes silently.

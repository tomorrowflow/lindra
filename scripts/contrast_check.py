#!/usr/bin/env python3
"""Check the WCAG contrast of every text-on-surface pair the shell uses.

The Quiet Clarity tokens derive from the brand kit (ADR 0009). The kit values
are proposals until checked; this script is the check. It exits non-zero when
a pair falls under the 4.5 to 1 minimum for text, and prints a Markdown table
that docs/ui/contrast.md records.

Usage: python3 scripts/contrast_check.py
"""

from __future__ import annotations

import sys

MINIMUM = 4.5

# Quiet Clarity tokens. Keep in step with lindra/static/css/quiet-clarity.css.
TOKENS = {
    "Paper (brand kit)": "#F7F5F0",
    "White": "#FFFFFF",
    "Paper, darker step": "#EAE6DD",
    "Ink (brand kit)": "#243331",
    "Teal (brand kit)": "#245B57",
    "Sage (brand kit)": "#A8B9A7",
    "Ink, secondary text": "#4F5F5D",
    "Teal, text on Sage tint": "#1B4542",
    "Sage tint, selected row": "#E3E9E2",
    "Error": "#9B2C20",
    "Warning text": "#7A4F00",
    "Success text": "#2F6B4F",
}

# (where it is used, text token, surface token)
PAIRS = [
    ("Body text on the page", "Ink (brand kit)", "Paper (brand kit)"),
    ("Body text on a writing surface", "Ink (brand kit)", "White"),
    ("Secondary text on the page", "Ink, secondary text", "Paper (brand kit)"),
    ("Secondary text on a writing surface", "Ink, secondary text", "White"),
    ("Primary button label", "White", "Teal (brand kit)"),
    ("Teal as text or icon on the page", "Teal (brand kit)", "Paper (brand kit)"),
    ("Teal as text on a writing surface", "Teal (brand kit)", "White"),
    ("Selected sidebar row", "Teal, text on Sage tint", "Sage tint, selected row"),
    ("Body text on the darker paper step", "Ink (brand kit)", "Paper, darker step"),
    ("Error text on the page", "Error", "Paper (brand kit)"),
    ("Error text on a writing surface", "Error", "White"),
    ("Warning text on the page", "Warning text", "Paper (brand kit)"),
    ("Success text on the page", "Success text", "Paper (brand kit)"),
    ("Sage as text on Paper (rejected, recorded)", "Sage (brand kit)", "Paper (brand kit)"),
]

# Pairs that are expected to fail and are therefore not used for text.
REJECTED = {"Sage as text on Paper (rejected, recorded)"}


def channel(value: int) -> float:
    c = value / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex_colour: str) -> float:
    r, g, b = (int(hex_colour[i : i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def main() -> int:
    rows = []
    failures = []
    for use, text, surface in PAIRS:
        ratio = contrast(TOKENS[text], TOKENS[surface])
        passed = ratio >= MINIMUM
        if not passed and use not in REJECTED:
            failures.append(use)
        verdict = "passes" if passed else ("rejected" if use in REJECTED else "FAILS")
        rows.append(
            f"| {use} | {text} `{TOKENS[text]}` | {surface} `{TOKENS[surface]}` "
            f"| {ratio:.2f} to 1 | {verdict} |"
        )
    print("| Use | Text | Surface | Contrast | Result |")
    print("| --- | --- | --- | --- | --- |")
    print("\n".join(rows))
    if failures:
        print(f"\n{len(failures)} pair(s) under {MINIMUM} to 1: " + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

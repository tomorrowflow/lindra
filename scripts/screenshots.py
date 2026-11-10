#!/usr/bin/env python3
"""Screenshot the case screens on an iPad-sized portrait viewport and a desktop viewport.

Also measures what the tickets ask of the shell and the case forms: the action bar's
buttons keep their size and position while the step body scrolls, the status area
keeps its width when its text changes, every control is at least 44 by 44 CSS
pixels, a form error or a period conflict never moves the dialog's buttons, and a
case can be opened from the portrait drawer.

Usage: .venv/bin/python scripts/screenshots.py [output-dir]
Needs `playwright install chromium` once.
"""

from __future__ import annotations

import socket
import sys
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path

import httpx
import uvicorn
from playwright.sync_api import Page, sync_playwright

from lindra.app import create_app
from lindra.config import Settings

TOKEN = "screenshot-token"
VIEWPORTS = {
    "ipad-portrait": {"viewport": {"width": 820, "height": 1180}, "device_scale_factor": 2},
    "desktop": {"viewport": {"width": 1440, "height": 900}, "device_scale_factor": 1},
}
LONG_SAMPLE = " ".join(["Beispielabsatz, nur zum Scrollen der Vorschau."] * 400)
# FIK-2026-002 has an assessment on 12.10. and visits on 14.10. and 16.10.2026.
CASE_NUMBER = "FIK-2026-002"


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@contextmanager
def running_server():
    """Serve the application on a free port with the cast seeded; yield its base URL."""
    port = free_port()
    with tempfile.TemporaryDirectory() as data_dir:
        settings = Settings(token=TOKEN, data_dir=Path(data_dir))
        config = uvicorn.Config(create_app(settings), port=port, log_level="warning")
        server = uvicorn.Server(config)
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        while not server.started:
            thread.join(0.05)
        base_url = f"http://127.0.0.1:{port}"
        seeded = httpx.post(f"{base_url}/api/seed", headers={"Authorization": f"Bearer {TOKEN}"})
        seeded.raise_for_status()
        try:
            yield base_url
        finally:
            server.should_exit = True
            thread.join(5)


def log_in(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/anmelden")
    page.fill("#token", TOKEN)
    page.click("button[type=submit]")
    page.wait_for_url(f"{base_url}/")


def boxes(page: Page, selector: str) -> list[dict]:
    return page.eval_on_selector_all(
        selector,
        "els => els.map(e => { const r = e.getBoundingClientRect();"
        " return {x: r.x, y: r.y, w: r.width, h: r.height}; })",
    )


def check_shell_requirements(page: Page, name: str) -> list[str]:
    """Stable action bar, non-shifting status area, 44 px targets (ticket 01)."""
    findings = []
    before = boxes(page, ".action-bar .btn")
    page.evaluate(
        "text => { const p = document.createElement('p'); p.textContent = text;"
        " document.querySelector('.step-body').appendChild(p); }",
        LONG_SAMPLE,
    )
    page.evaluate("document.querySelector('.step-body').scrollTop = 99999")
    after = boxes(page, ".action-bar .btn")
    if before != after:
        findings.append(f"{name}: action bar moved while scrolling: {before} -> {after}")

    status_before = boxes(page, ".status-area")[0]
    buttons_before = boxes(page, ".topbar .btn")
    page.evaluate(
        "document.querySelector('.status-indicator span:last-child').textContent"
        " = 'Verbindung unterbrochen, Änderungen nicht gespeichert'"
    )
    status_after = boxes(page, ".status-area")[0]
    buttons_after = boxes(page, ".topbar .btn")
    if status_before != status_after or buttons_before != buttons_after:
        findings.append(f"{name}: status text change shifted the top bar")
    return findings


def check_targets(page: Page, name: str) -> list[str]:
    small = [
        b
        for b in boxes(page, "button, a.btn, .drawer-button, .input")
        if b["w"] > 0 and (b["w"] < 44 or b["h"] < 44)
    ]
    return [f"{name}: controls under 44 by 44 CSS px: {small}"] if small else []


def open_drawer(page: Page, portrait: bool) -> None:
    if portrait:
        page.click(".drawer-button")
        page.wait_for_timeout(400)


def close_drawer(page: Page, portrait: bool) -> None:
    if portrait:
        page.click(".drawer-overlay", position={"x": 700, "y": 600})
        page.wait_for_timeout(400)


def case_screens(page: Page, base_url: str, out: Path, name: str) -> list[str]:
    """Start, new-case error, overview and refused period change; the drawer in portrait."""
    findings: list[str] = []
    portrait = name == "ipad-portrait"

    page.goto(f"{base_url}/")
    page.screenshot(path=out / f"start-{name}.png")
    findings += check_targets(page, f"{name} start")
    if portrait:
        open_drawer(page, portrait)
        page.screenshot(path=out / f"start-{name}-drawer.png")
        close_drawer(page, portrait)
    # The shell check edits the page, so it runs last and the page is loaded again.
    findings += check_shell_requirements(page, name)
    page.goto(f"{base_url}/")

    # The new-case form refuses an empty submit inline; the buttons stay where they were.
    page.goto(f"{base_url}/faelle/neu")
    page.wait_for_selector("dialog[open]")
    page.fill("#case_number", "FIK-2026-100")
    before = boxes(page, ".dialog-actions .btn")
    page.click("button:has-text('Fall anlegen')")
    page.wait_for_selector(".field-error:not(:empty)")
    page.wait_for_selector("dialog[open]")
    after = boxes(page, ".dialog-actions .btn")
    if before != after:
        findings.append(f"{name}: a form error moved the dialog buttons: {before} -> {after}")
    page.wait_for_timeout(400)
    page.screenshot(path=out / f"new-case-error-{name}.png")
    findings += check_targets(page, f"{name} new case")

    # Open the case from the sidebar (the drawer in portrait).
    page.goto(f"{base_url}/")
    open_drawer(page, portrait)
    page.click(f".case-link:has-text('{CASE_NUMBER}')")
    page.wait_for_url("**/faelle/*")
    page.screenshot(path=out / f"overview-{name}.png")
    if portrait:
        open_drawer(page, portrait)
        page.screenshot(path=out / f"overview-{name}-drawer.png")
        # Switching case works from the drawer too.
        page.click(".case-link:has-text('FIK-2026-001')")
        page.wait_for_url("**/faelle/*")
        if "FIK-2026-001" not in page.inner_text(".step-title"):
            findings.append(f"{name}: switching case from the drawer did not open the case")
        open_drawer(page, portrait)
        page.click(f".case-link:has-text('{CASE_NUMBER}')")
        page.wait_for_url("**/faelle/*")
    findings += check_targets(page, f"{name} overview")

    # The period change that would strand the last visit: named, saving disabled.
    page.click("a:has-text('Ändern')")
    page.wait_for_selector("dialog[open]")
    before = boxes(page, ".dialog-actions .btn")
    page.fill("#period_end", "2026-10-15")
    page.wait_for_selector("#period-feedback .alert")
    after = boxes(page, ".dialog-actions .btn")
    if before != after:
        findings.append(f"{name}: a period conflict moved the dialog buttons: {before} -> {after}")
    if not page.is_disabled("[data-save]"):
        findings.append(f"{name}: saving stayed enabled with a conflicting period")
    if "Visite am 16.10.2026" not in page.inner_text("#period-feedback"):
        findings.append(f"{name}: the conflicting visit was not named")
    page.wait_for_timeout(400)
    page.screenshot(path=out / f"period-refused-{name}.png")
    findings += check_targets(page, f"{name} period")

    # A fitting period enables saving again.
    page.fill("#period_end", "2026-10-24")
    page.wait_for_selector("#period-feedback[data-ok=true]", state="attached")
    if page.is_disabled("[data-save]"):
        findings.append(f"{name}: saving stayed disabled with a fitting period")
    return findings


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("docs/screenshots/LFR-05")
    out.mkdir(parents=True, exist_ok=True)
    findings: list[str] = []
    with running_server() as base_url, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for name, viewport in VIEWPORTS.items():
            context = browser.new_context(**viewport, locale="de-DE")
            page = context.new_page()
            page.goto(f"{base_url}/anmelden")
            page.screenshot(path=out / f"login-{name}.png")
            log_in(page, base_url)
            page.keyboard.press("Tab")
            page.screenshot(path=out / f"start-{name}-focus.png")
            findings.extend(case_screens(page, base_url, out, name))
            context.close()
        browser.close()
    for finding in findings:
        print(finding)
    print(f"screenshots written to {out}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

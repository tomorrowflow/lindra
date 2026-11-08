#!/usr/bin/env python3
"""Screenshot the shell on an iPad-sized portrait viewport and a desktop viewport.

Also measures what the ticket asks of the shell: the action bar's buttons keep
their size and position while the step body scrolls, the status area keeps its
width when its text changes, and every control is at least 44 by 44 CSS pixels.

Usage: .venv/bin/python scripts/screenshots.py [output-dir]
Needs `playwright install chromium` once.
"""

from __future__ import annotations

import socket
import sys
import threading
from contextlib import contextmanager
from pathlib import Path

import uvicorn
from playwright.sync_api import Page, sync_playwright

from lindra.app import create_app
from lindra.config import Settings

TOKEN = "screenshot-token"
BASE = ""
VIEWPORTS = {
    "ipad-portrait": {"viewport": {"width": 820, "height": 1180}, "device_scale_factor": 2},
    "desktop": {"viewport": {"width": 1440, "height": 900}, "device_scale_factor": 1},
}
LONG_SAMPLE = " ".join(["Beispielabsatz, nur zum Scrollen der Vorschau."] * 400)


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@contextmanager
def running_server():
    global BASE
    port = free_port()
    BASE = f"http://127.0.0.1:{port}"
    config = uvicorn.Config(create_app(Settings(token=TOKEN)), port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        thread.join(0.05)
    try:
        yield
    finally:
        server.should_exit = True
        thread.join(5)


def log_in(page: Page) -> None:
    page.goto(f"{BASE}/anmelden")
    page.fill("#token", TOKEN)
    page.click("button[type=submit]")
    page.wait_for_url(f"{BASE}/")


def boxes(page: Page, selector: str) -> list[dict]:
    return page.eval_on_selector_all(
        selector,
        "els => els.map(e => { const r = e.getBoundingClientRect();"
        " return {x: r.x, y: r.y, w: r.width, h: r.height}; })",
    )


def check_stability(page: Page, name: str) -> list[str]:
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

    small = [
        b
        for b in boxes(page, "button, .drawer-button, .input")
        if b["w"] > 0 and (b["w"] < 44 or b["h"] < 44)
    ]
    if small:
        findings.append(f"{name}: controls under 44 by 44 CSS px: {small}")
    return findings


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("docs/screenshots/LFR-01")
    out.mkdir(parents=True, exist_ok=True)
    findings: list[str] = []
    with running_server(), sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for name, viewport in VIEWPORTS.items():
            context = browser.new_context(**viewport, locale="de-DE")
            page = context.new_page()
            page.goto(f"{BASE}/anmelden")
            page.screenshot(path=out / f"login-{name}.png")
            log_in(page)
            page.screenshot(path=out / f"shell-{name}.png")
            if name == "ipad-portrait":
                page.click(".drawer-button")
                page.wait_for_timeout(400)
                page.screenshot(path=out / f"shell-{name}-drawer.png")
                page.click(".drawer-overlay", position={"x": 700, "y": 600})
                page.wait_for_timeout(400)
            page.keyboard.press("Tab")
            page.screenshot(path=out / f"shell-{name}-focus.png")
            findings.extend(check_stability(page, name))
            page.screenshot(path=out / f"shell-{name}-scrolled.png")
            context.close()
        browser.close()
    for finding in findings:
        print(finding)
    print(f"screenshots written to {out}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

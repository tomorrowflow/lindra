#!/usr/bin/env python3
"""Screenshot the case and encounter screens on an iPad-sized portrait and a desktop viewport.

Also measures what the tickets ask of the shell, the case forms and the notes step: the
action bar's buttons keep their size and position while the step body scrolls and while
the save status changes, the status area keeps its width when its text changes, every
control is at least 44 by 44 CSS pixels, a form error or a period conflict never moves
the dialog's buttons, a case and an encounter can be opened from the portrait drawer, a
visit outside the period is refused, a backdated visit sorts by its date, and the notes
autosave through saving, saved, not saved (network lost) and failed save with retry.

The application runs on a fixed clock (10.11.2026 14:30), so both default states of the
new-visit form are reproducible. The case screens (ticket 05) are checked on every run
but their pictures are not kept; the encounter screens are written to the output directory.

Usage: .venv/bin/python scripts/screenshots.py [output-dir]
Needs `playwright install chromium` once.
"""

from __future__ import annotations

import socket
import sys
import tempfile
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import httpx
import uvicorn
from playwright.sync_api import Page, sync_playwright

from lindra.app import create_app
from lindra.config import Settings

TOKEN = "screenshot-token"
NOW = datetime(2026, 11, 10, 14, 30)
# A case whose period contains NOW; the cast's cases ran in October, before it.
INSIDE_CASE = {
    "case_number": "FIK-2026-100",
    "patient_name": "Marta Lindqvist",
    "label": "Kopfschmerz",
    "assessment_date": "2026-11-09",
    "assessment_time": "10:30",
    "period_start": "2026-11-09",
    "period_end": "2026-11-20",
}
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
        config = uvicorn.Config(
            create_app(settings, clock=lambda: NOW), port=port, log_level="warning"
        )
        server = uvicorn.Server(config)
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        while not server.started:
            thread.join(0.05)
        base_url = f"http://127.0.0.1:{port}"
        reseed(base_url)
        try:
            yield base_url
        finally:
            server.should_exit = True
            thread.join(5)


def reseed(base_url: str) -> None:
    """The cast as the seed hook stores it, plus the case that has "now" in its period."""
    headers = {"Authorization": f"Bearer {TOKEN}"}
    httpx.post(f"{base_url}/api/seed", headers=headers).raise_for_status()
    cases = httpx.get(f"{base_url}/api/cases", headers=headers).json()["cases"]
    for case in cases:
        if case["case_number"] == INSIDE_CASE["case_number"]:
            httpx.delete(f"{base_url}/api/cases/{case['id']}", headers=headers).raise_for_status()
    httpx.post(f"{base_url}/api/cases", json=INSIDE_CASE, headers=headers).raise_for_status()


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


def open_case(page: Page, base_url: str, number: str, portrait: bool) -> None:
    """Open a case from the sidebar (the drawer in portrait), as the physician does."""
    page.goto(f"{base_url}/")
    open_drawer(page, portrait)
    page.click(f".case-link:has-text('{number}')")
    page.wait_for_url("**/faelle/*")


def encounter_dates(page: Page) -> list[str]:
    return page.eval_on_selector_all(
        ".encounter-menu .encounter-when", "els => els.map(e => e.textContent.trim())"
    )


def status_text(page: Page) -> str:
    return page.inner_text("[data-save-indicator]").strip()


def layout_of_notes_step(page: Page) -> dict:
    """Everything a status change must leave where it is."""
    return {
        "action bar": boxes(page, ".action-bar .btn"),
        "status area": boxes(page, ".status-area"),
        "top bar": boxes(page, ".topbar .btn"),
        "text area": boxes(page, ".notes-area"),
        "title": boxes(page, ".notes-step .step-title"),
    }


def moved(before: dict, after: dict) -> list[str]:
    return [key for key in before if before[key] != after[key]]


def visit_screens(page: Page, base_url: str, out: Path, name: str) -> list[str]:
    """Neue Visite in both default states, a refusal, a backdated visit, the drawer."""
    findings: list[str] = []
    portrait = name == "ipad-portrait"

    # The cast case ran before "now": no default, and a note that says so.
    open_case(page, base_url, CASE_NUMBER, portrait)
    if encounter_dates(page) != ["12.10.2026 09:00", "14.10.2026 09:00", "16.10.2026 09:00"]:
        findings.append(
            f"{name}: the sidebar does not list the encounters by date: {encounter_dates(page)}"
        )
    if page.locator(".encounter-menu .badge-button").count() != 3:
        findings.append(f"{name}: an encounter has no state badge in the sidebar")
    if page.locator(".encounter-row .badge-button").count() != 3:
        findings.append(f"{name}: an encounter has no state badge in the overview")
    findings += check_targets(page, f"{name} overview with encounters")
    page.screenshot(path=out / f"overview-encounters-{name}.png")
    if portrait:
        open_drawer(page, portrait)
        page.click(".drawer-side .badge-button")
        page.wait_for_selector(".drawer-side .badge-explanation:not([hidden])")
        page.screenshot(path=out / f"sidebar-badges-{name}.png")
        close_drawer(page, portrait)
    else:
        page.click(".encounter-menu .badge-button")
        page.wait_for_selector(".encounter-menu .badge-explanation:not([hidden])")
        page.screenshot(path=out / f"sidebar-badges-{name}.png")

    page.click("main a:has-text('Neue Visite')")
    page.wait_for_selector("dialog[open]")
    if page.input_value("#visit_date") or page.input_value("#visit_time"):
        findings.append(
            f"{name}: the new-visit form has a default although now is outside the period"
        )
    if "kein Datum vorbelegt" not in page.inner_text("#visit-note"):
        findings.append(f"{name}: no note says why the date is empty")
    limits = (page.get_attribute("#visit_date", "min"), page.get_attribute("#visit_date", "max"))
    if limits != ("2026-10-12", "2026-10-23"):
        findings.append(f"{name}: the date picker is not limited to the period: {limits}")
    page.wait_for_timeout(300)
    page.screenshot(path=out / f"new-visit-outside-{name}.png")
    findings += check_targets(page, f"{name} new visit")

    # A date outside the period is refused inline; the buttons stay where they were.
    before = boxes(page, ".dialog-actions .btn")
    page.fill("#visit_date", "2026-11-25")
    page.fill("#visit_time", "09:30")
    page.click("button:has-text('Visite anlegen')")
    page.wait_for_selector(".field-error:not(:empty)")
    after = boxes(page, ".dialog-actions .btn")
    if before != after:
        findings.append(f"{name}: a refused visit moved the dialog buttons: {before} -> {after}")
    if "Behandlungszeitraum" not in page.inner_text("#visit_date-error"):
        findings.append(f"{name}: the refusal does not name the period")
    if page.input_value("#visit_date") != "2026-11-25":
        findings.append(f"{name}: the refused form lost the entered date")
    page.wait_for_timeout(300)
    page.screenshot(path=out / f"new-visit-refused-{name}.png")

    # A backdated visit inside the period is created and sorts by its date.
    page.fill("#visit_date", "2026-10-13")
    page.fill("#visit_time", "08:00")
    page.click("button:has-text('Visite anlegen')")
    page.wait_for_url("**/notizen")
    if encounter_dates(page) != [
        "12.10.2026 09:00",
        "13.10.2026 08:00",
        "14.10.2026 09:00",
        "16.10.2026 09:00",
    ]:
        findings.append(
            f"{name}: the backdated visit is not in date order: {encounter_dates(page)}"
        )
    if page.locator(".step-link").count() != 1:
        findings.append(f"{name}: steps show beneath more than the selected encounter")
    page.screenshot(path=out / f"visit-backdated-{name}.png")

    # Now inside the period: the form starts with now.
    open_case(page, base_url, INSIDE_CASE["case_number"], portrait)
    page.click("main a:has-text('Neue Visite')")
    page.wait_for_selector("dialog[open]")
    if (page.input_value("#visit_date"), page.input_value("#visit_time")) != (
        "2026-11-10",
        "14:30",
    ):
        findings.append(f"{name}: the form does not start with now inside the period")
    if "Vorbelegt mit jetzt" not in page.inner_text("#visit-note"):
        findings.append(f"{name}: no note says the date is now")
    page.wait_for_timeout(300)
    page.screenshot(path=out / f"new-visit-inside-{name}.png")
    findings += check_targets(page, f"{name} new visit inside")
    return findings


def notes_screens(page: Page, base_url: str, out: Path, name: str) -> list[str]:
    """The notes step through its save states, measured against the saved layout."""
    findings: list[str] = []
    portrait = name == "ipad-portrait"
    context = page.context
    notes_route = "**/api/cases/*/encounters/*/notes"

    open_case(page, base_url, INSIDE_CASE["case_number"], portrait)
    open_drawer(page, portrait)
    page.click(".encounter-link:has-text('Aufnahmeassessment')")
    page.wait_for_url("**/notizen")
    page.wait_for_selector("[data-save-indicator]")
    if page.input_value("#notes") != "" or page.get_attribute("#notes", "data-revision") != "0":
        findings.append(f"{name}: a new encounter does not start with empty notes at revision 0")
    saved_layout = layout_of_notes_step(page)
    findings += check_targets(page, f"{name} notes")

    # Typing autosaves without a button; the revision advances by one.
    page.click("#notes")
    page.keyboard.type("Seit drei Jahren Rückenschmerz, links betont.", delay=15)
    page.wait_for_function(
        "document.querySelector('[data-save-indicator]').textContent.includes('Gespeichert')"
    )
    if page.get_attribute("#notes", "data-revision") != "1":
        findings.append(f"{name}: the first autosave did not give revision 1")
    if status_text(page) != "Gespeichert":
        findings.append(f"{name}: saved state reads {status_text(page)!r}")
    if page.locator("button:text-is('Speichern')").count() != 0:
        findings.append(f"{name}: the notes step has a save button")
    findings += [
        f"{name}: saving moved the {k}" for k in moved(saved_layout, layout_of_notes_step(page))
    ]
    badge = page.get_attribute(".encounter-link.current ~ .badge-button", "aria-label")
    if badge != "Zustand: Notizen gespeichert, noch kein Entwurf":
        findings.append(f"{name}: the sidebar badge did not follow the saved notes: {badge!r}")
    page.screenshot(path=out / f"notes-saved-{name}.png")

    # The save is in flight: held back until the picture is taken.
    held = []
    page.route(notes_route, lambda route: held.append(route))
    page.keyboard.type(" Keine Ausstrahlung.", delay=15)
    page.wait_for_function(
        "document.querySelector('[data-save-indicator]').textContent.includes('Speichert')"
    )
    page.screenshot(path=out / f"notes-saving-{name}.png")
    findings += [
        f"{name}: the saving state moved the {k}"
        for k in moved(saved_layout, layout_of_notes_step(page))
    ]
    page.unroute(notes_route)
    for route in held:
        route.continue_()
    page.wait_for_function(
        "document.querySelector('[data-save-indicator]').textContent.includes('Gespeichert')"
    )
    if page.get_attribute("#notes", "data-revision") != "2":
        findings.append(f"{name}: the second save did not give revision 2")

    # The network is gone: not saved, with the separate retry button.
    context.set_offline(True)
    page.keyboard.type(" Nachts schlechter.", delay=15)
    page.wait_for_function(
        "document.querySelector('[data-save-indicator]').textContent.includes('Nicht gespeichert')"
    )
    if page.is_hidden("[data-retry]"):
        findings.append(f"{name}: no retry button after the network was lost")
    if page.locator(".status-area button").count() != 0:
        findings.append(f"{name}: the status area holds a button")
    findings += [
        f"{name}: the not-saved state moved the {k}"
        for k in moved(saved_layout, layout_of_notes_step(page))
    ]
    findings += check_targets(page, f"{name} notes not saved")
    page.screenshot(path=out / f"notes-not-saved-{name}.png")
    # Retrying while the network is still gone fails again and keeps the text.
    page.click("[data-retry]")
    page.wait_for_function(
        "document.querySelector('[data-save-indicator]').textContent.includes('Nicht gespeichert')"
    )
    if page.is_hidden("[data-retry]"):
        findings.append(f"{name}: the retry button vanished although the save failed again")
    # Coming back online saves what is waiting, without another tap.
    context.set_offline(False)
    page.wait_for_function(
        "document.querySelector('[data-save-indicator]').textContent.includes('Gespeichert')"
    )
    if page.is_visible("[data-retry]"):
        findings.append(f"{name}: the retry button stays after a successful save")
    if page.get_attribute("#notes", "data-revision") != "3":
        findings.append(f"{name}: the save after the network came back did not give revision 3")

    # The service answers with an error: failed save, then retry.
    page.route(notes_route, lambda route: route.fulfill(status=500, body="{}"))
    page.keyboard.type(" Besser nach Wärme.", delay=15)
    page.wait_for_function(
        "document.querySelector('[data-save-indicator]').textContent.includes('fehlgeschlagen')"
    )
    if page.is_hidden("[data-retry]"):
        findings.append(f"{name}: no retry button after a failed save")
    findings += [
        f"{name}: the failed-save state moved the {k}"
        for k in moved(saved_layout, layout_of_notes_step(page))
    ]
    page.screenshot(path=out / f"notes-failed-{name}.png")
    # Typing on after a failure does not flip the status back and forth.
    page.keyboard.type(" Besser", delay=15)
    page.wait_for_timeout(1500)
    if "fehlgeschlagen" not in status_text(page):
        findings.append(
            f"{name}: typing after a failed save changed the status: {status_text(page)!r}"
        )
    page.unroute(notes_route)
    page.click("[data-retry]")
    page.wait_for_function(
        "document.querySelector('[data-save-indicator]').textContent.includes('Gespeichert')"
    )
    if page.get_attribute("#notes", "data-revision") != "4":
        findings.append(f"{name}: the retry after a failed save did not give revision 4")

    # What was typed is there after a reload, and each encounter has its own notes.
    page.reload()
    if "Besser nach Wärme." not in page.input_value("#notes"):
        findings.append(
            f"{name}: the saved notes are not there after a reload: {page.input_value('#notes')!r}"
        )
    open_drawer(page, portrait)
    page.click(".encounter-link:has-text('Aufnahmeassessment') >> nth=0")
    page.wait_for_url("**/notizen")
    findings += [
        f"{name}: reload moved the {k}" for k in moved(saved_layout, layout_of_notes_step(page))
    ]

    # Opening notes changes nothing: the text area holds exactly the saved text, also when
    # it starts with a line break, and an untouched step sends no save.
    saved_url = page.url
    for notes in ("", "\nzweite Zeile", "Text\n"):
        httpx.put(
            f"{base_url}{page.get_attribute('#notes', 'data-save-url')}",
            json={"notes": notes},
            headers={"Authorization": f"Bearer {TOKEN}"},
        ).raise_for_status()
        saves: list[str] = []
        page.on("request", lambda request, saves=saves: saves.append(request.method))
        page.goto(saved_url)
        page.wait_for_timeout(1500)
        if page.input_value("#notes") != notes:
            findings.append(
                f"{name}: the text area shows {page.input_value('#notes')!r}, not {notes!r}"
            )
        if "PUT" in saves:
            findings.append(f"{name}: opening the notes step sent a save for {notes!r}")
        if status_text(page) != "Gespeichert":
            findings.append(f"{name}: opening the notes step reads {status_text(page)!r}")
    return findings


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("docs/screenshots/LFR-06")
    out.mkdir(parents=True, exist_ok=True)
    findings: list[str] = []
    with (
        running_server() as base_url,
        sync_playwright() as playwright,
        tempfile.TemporaryDirectory() as scratch,
    ):
        browser = playwright.chromium.launch()
        for name, viewport in VIEWPORTS.items():
            reseed(base_url)
            context = browser.new_context(**viewport, locale="de-DE")
            page = context.new_page()
            log_in(page, base_url)
            findings.extend(case_screens(page, base_url, Path(scratch), name))
            reseed(base_url)
            findings.extend(visit_screens(page, base_url, out, name))
            findings.extend(notes_screens(page, base_url, out, name))
            context.close()
        browser.close()
    for finding in findings:
        print(finding)
    print(f"screenshots written to {out}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

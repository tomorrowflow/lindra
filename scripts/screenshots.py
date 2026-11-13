#!/usr/bin/env python3
"""Screenshot the case and encounter screens on an iPad-sized portrait and a desktop viewport.

Also measures what the tickets ask of the shell, the case forms and the notes step: the
action bar's buttons keep their size and position while the step body scrolls and while
the save status changes, the status area keeps its width when its text changes, every
control is at least 44 by 44 CSS pixels, a form error or a period conflict never moves
the dialog's buttons, a case and an encounter can be opened from the portrait drawer, a
visit outside the period is refused, a backdated visit sorts by its date, and the notes
autosave through saving, saved, not saved (network lost) and failed save with retry. It also
runs the review of an assessment and the dictation flow (ticket 10): the overlay blocks the
step while it records, transcribes and shows the transcript, a corrected transcript is
appended to the notes and outdates a pending proposal, discarding changes nothing, and a
denied microphone and a recording that cannot be transcribed are told in the overlay.

The application runs on a fixed clock (10.11.2026 14:30), so both default states of the
new-visit form are reproducible. The case screens (ticket 05) and the encounter screens
(ticket 06) are checked on every run but their pictures are not kept.

The review steps (ticket 07), the fidelity steps (ticket 08: input references, pain
problems, the clarification list) and the dictation overlay (ticket 10) write their pictures
to `LFR-07`, `LFR-08` and `LFR-10` under the output directory, which defaults to
`docs/screenshots`.

Usage: .venv/bin/python scripts/screenshots.py [output-dir]
Needs `playwright install chromium` once.
"""

from __future__ import annotations

import base64
import re
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
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from lindra import cast
from lindra.app import create_app
from lindra.cast import load_cast
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
# Runs in every page before its own scripts. It counts the requests for the microphone, can
# answer one with the denial a physician gives in Safari, and lets a test hand the overlay a
# fixture clip as "the recording": a recorder set to `window.__fixtureAudio` (base64) returns
# that clip, otherwise the browser's own recorder records from the fake microphone.
INIT_SCRIPT = """
(() => {
  window.__micRequests = 0;
  const media = navigator.mediaDevices;
  if (media && media.getUserMedia) {
    const real = media.getUserMedia.bind(media);
    media.getUserMedia = async (constraints) => {
      window.__micRequests += 1;
      if (window.__denyMicrophone) throw new DOMException("Permission denied", "NotAllowedError");
      const stream = await real(constraints);
      window.__streams.push(stream);
      return stream;
    };
  }
  // The microphone tracks still open, which is what the browser shows as "recording".
  window.__streams = [];
  window.__liveTracks = () =>
    window.__streams.flatMap((s) => s.getTracks()).filter((t) => t.readyState === "live").length;
  const Real = window.MediaRecorder;
  class FixtureRecorder extends EventTarget {
    constructor() {
      super();
      this.state = "inactive";
      this.mimeType = "audio/wav";
      window.__recorder = this;
    }
    // A recorder that breaks while recording: the error comes first, and the browser still
    // delivers the data and the stop event afterwards, `late` milliseconds later.
    breakDown(late) {
      this.state = "inactive";
      this.dispatchEvent(new Event("error"));
      setTimeout(() => this.stop(), late);
    }
    start() {
      if (window.__recorderFault === "start") {
        throw new DOMException("The recorder cannot start", "InvalidStateError");
      }
      this.state = "recording";
    }
    stop() {
      this.state = "inactive";
      const bytes = Uint8Array.from(atob(window.__fixtureAudio), (c) => c.charCodeAt(0));
      const chunk = new Event("dataavailable");
      chunk.data = new Blob([bytes], { type: this.mimeType });
      this.dispatchEvent(chunk);
      this.dispatchEvent(new Event("stop"));
    }
  }
  if (Real) {
    window.MediaRecorder = new Proxy(Real, {
      construct: (target, args) => {
        if (window.__recorderFault === "construct") {
          throw new DOMException("No recorder for this stream", "NotSupportedError");
        }
        return window.__fixtureAudio ? new FixtureRecorder() : new target(...args);
      },
    });
  }
})();
"""
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
    # A visit has the notes, its four sections and the last step, and only the selected
    # encounter shows them.
    if page.locator(".step-list").count() != 1 or page.locator(".step-link").count() != 6:
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
    # A browser turns a carriage return in the text area into a line feed.
    saved_url = page.url
    save_url = f"{base_url}{page.get_attribute('#notes', 'data-save-url')}"
    methods: list[str] = []
    page.on("request", lambda request: methods.append(request.method))
    for notes, shown in (
        ("", ""),
        ("\nzweite Zeile", "\nzweite Zeile"),
        ("\r\nzweite Zeile", "\nzweite Zeile"),
        ("Text\n", "Text\n"),
    ):
        httpx.put(
            save_url, json={"notes": notes}, headers={"Authorization": f"Bearer {TOKEN}"}
        ).raise_for_status()
        methods.clear()
        page.goto(saved_url)
        # Longer than the pause before an autosave, so a save on open would show up.
        page.wait_for_timeout(1500)
        if page.input_value("#notes") != shown:
            findings.append(
                f"{name}: the text area shows {page.input_value('#notes')!r}, not {shown!r}"
            )
        if "PUT" in methods:
            findings.append(f"{name}: opening the notes step sent a save for {notes!r}")
        if status_text(page) != "Gespeichert":
            findings.append(f"{name}: opening the notes step reads {status_text(page)!r}")
    return findings


def go_to_step(page: Page, portrait: bool, number: int) -> None:
    """Open a review step from the sidebar (the drawer in portrait), as the physician does."""
    open_drawer(page, portrait)
    previous = page.url
    page.click(f".step-link:has(.step-number:text-is('{number}'))")
    page.wait_for_function("url => location.href !== url", arg=previous)
    page.wait_for_load_state()


def bar_layout(page: Page) -> list[dict]:
    return boxes(page, ".action-bar .btn")


def status_words(page: Page) -> str:
    return page.inner_text(".status-area .status-indicator").strip()


def head_badges(page: Page) -> list[str]:
    return page.eval_on_selector_all(
        "#section-head .section-badge", "els => els.map(e => e.getAttribute('aria-label'))"
    )


def generate_and_wait(page: Page) -> None:
    """Tap "Entwurf erzeugen" or "Neu erzeugen" and wait for the page to show the proposal."""
    page.click("[data-generate]")
    page.wait_for_selector("[data-generation=idle] [data-generate]:not([disabled])")
    page.wait_for_load_state()


def review_screens(page: Page, base_url: str, out: Path, name: str) -> list[str]:
    """The first half of the browser flow: open a case, type notes, generate, hand-edit a
    section, accept with that section retained and badged, change notes while a proposal is
    pending and see acceptance disabled with its reason, copy a section from the handover."""
    findings: list[str] = []
    portrait = name == "ipad-portrait"
    context = page.context
    context.grant_permissions(["clipboard-read", "clipboard-write"])
    generate_route = "**/api/cases/*/encounters/*/generate"

    # Fall auswählen: the case from the sidebar, then its assessment.
    open_case(page, base_url, "FIK-2026-001", portrait)
    open_drawer(page, portrait)
    page.click(".encounter-link:has-text('Aufnahmeassessment')")
    page.wait_for_url("**/notizen")
    notes_url = page.url
    if page.locator("[data-save-indicator]").count() != 1:
        findings.append(f"{name}: the notes step has no status indicator")
    if [s["w"] > 0 for s in boxes(page, "[data-retry-generation]")] != [False]:
        findings.append(f"{name}: the generation retry button shows before a failure")
    bars = {"notes": bar_layout(page)}
    findings += check_targets(page, f"{name} notes step with the generation strip")

    # Type notes: the seeded text gets one more sentence; nothing is generated by it.
    page.click("#notes")
    page.keyboard.press("Control+End")
    page.keyboard.type(" Nachts wacht sie zweimal auf.", delay=10)
    page.wait_for_function(
        "document.querySelector('[data-save-indicator]').textContent.includes('Gespeichert')"
    )
    if page.locator("[data-generate]").inner_text().strip() != "Entwurf erzeugen":
        findings.append(f"{name}: the generate button does not say Entwurf erzeugen")
    page.reload()
    badge = page.get_attribute(".encounter-link.current ~ .badge-button", "aria-label")
    if badge != "Zustand: Notizen gespeichert, noch kein Entwurf":
        findings.append(f"{name}: saving or opening notes changed the badge to {badge!r}")

    # A failed generation: plain report in the status area, a separate retry button.
    saved_layout = layout_of_notes_step(page)
    page.route(
        generate_route,
        lambda route: route.fulfill(
            status=502,
            content_type="application/json",
            body='{"detail": "Das Textmodell hat nicht geantwortet."}',
        ),
    )
    page.click("[data-generate]")
    page.wait_for_function(
        "document.querySelector('[data-save-indicator]').textContent.includes('nicht erzeugt')"
    )
    if page.is_hidden("[data-retry-generation]"):
        findings.append(f"{name}: no retry button after a failed generation")
    if "nicht geantwortet" not in page.inner_text("[data-generation-reason]"):
        findings.append(f"{name}: the failure reason is not shown")
    if page.locator(".status-area button").count() != 0:
        findings.append(f"{name}: the status area holds a button")
    findings += [
        f"{name}: a failed generation moved the {k}"
        for k in moved(saved_layout, layout_of_notes_step(page))
    ]
    if page.input_value("#notes").endswith("zweimal auf.") is False:
        findings.append(f"{name}: a failed generation changed the notes")
    page.screenshot(path=out / f"generation-failed-{name}.png")
    page.unroute(generate_route)

    # The retry works; while it runs the status area says so and the notes stay editable.
    held = []
    page.route(generate_route, lambda route: held.append(route))
    page.click("[data-retry-generation]")
    page.wait_for_function(
        "document.querySelector('[data-save-indicator]').textContent.includes('wird erzeugt')"
    )
    if page.is_enabled("#notes") is False or page.is_enabled("[data-generate]"):
        findings.append(f"{name}: while generating the notes lock or the button stays enabled")
    findings += [
        f"{name}: the generating state moved the {k}"
        for k in moved(saved_layout, layout_of_notes_step(page))
    ]
    with page.expect_navigation():
        for route in held:
            route.continue_()
    page.unroute(generate_route)
    page.wait_for_load_state()
    badge = page.get_attribute(".encounter-link.current ~ .badge-button", "aria-label")
    if badge != "Zustand: Vorschlag liegt vor":
        findings.append(f"{name}: after generating the sidebar badge reads {badge!r}")

    # The section step with the proposal (step 5 is Schmerzanamnese): two large panes, side by
    # side or stacked.
    go_to_step(page, portrait, 5)
    bars["section"] = bar_layout(page)
    panes = boxes(page, ".pane")
    if len(panes) != 2:
        findings.append(f"{name}: a section step has {len(panes)} panes, not two")
    elif portrait and not (panes[0]["x"] == panes[1]["x"] and panes[1]["y"] > panes[0]["y"]):
        findings.append(f"{name}: the panes are not stacked in portrait: {panes}")
    elif not portrait and not (panes[0]["y"] == panes[1]["y"] and panes[1]["x"] > panes[0]["x"]):
        findings.append(f"{name}: the panes are not side by side: {panes}")
    elif (
        min(p["w"] for p in panes) < (700 if portrait else 380) or min(p["h"] for p in panes) < 200
    ):
        findings.append(f"{name}: a pane is too small to read: {panes}")
    if "Tiefer Rückenschmerz" not in page.inner_text(".proposal-text"):
        findings.append(f"{name}: the proposal pane does not show the proposal")
    if page.input_value("#section-text") != "":
        findings.append(f"{name}: the draft pane is not empty before any acceptance")
    if head_badges(page) != ["Vorschlag ändert diesen Abschnitt"]:
        findings.append(f"{name}: the section badges read {head_badges(page)}")
    if page.is_enabled(".action-bar [data-copy]"):
        findings.append(f"{name}: copy is enabled on an empty draft pane")
    if page.locator("main form[action*=uebernehmen], main button:text-is('Übernehmen')").count():
        findings.append(f"{name}: a section step has an accept control")
    page.click(".state-line .more")
    page.wait_for_selector("#state-explanation-4:not([hidden])")
    findings += check_targets(page, f"{name} section step")
    page.screenshot(path=out / f"section-proposal-{name}.png")
    page.click(".state-line .more")

    # Hand-edit another section; its badge follows without a reload.
    go_to_step(page, portrait, 3)
    page.click("#section-text")
    page.keyboard.type("Bandscheibenvorfall vor drei Jahren, dazu eigene Anmerkung.", delay=10)
    page.wait_for_function(
        "document.querySelector('[data-save-indicator]').textContent.includes('Gespeichert')"
    )
    page.wait_for_selector("#section-head .section-badge[aria-label='Manuell bearbeitet']")
    if not page.is_enabled(".action-bar [data-copy]"):
        findings.append(f"{name}: copy stays disabled after typing in the draft pane")
    if "Manuell bearbeitet" not in page.inner_text(".state-line"):
        findings.append(f"{name}: the state line does not follow the hand edit")
    if "Bandscheibenvorfall L4/5" not in page.inner_text(".proposal-text"):
        findings.append(f"{name}: the proposal's alternative vanished after the hand edit")
    if bars["section"] != bar_layout(page):
        findings.append(f"{name}: typing in the draft pane moved the action bar")

    # The final step names what is replaced and what stays; one action accepts.
    go_to_step(page, portrait, 9)
    bars["accept"] = bar_layout(page)
    retained = page.inner_text("#retained-title + ul")
    replaced = page.inner_text("#replaced-title + ul")
    if "Frühere Anamnese und Vormedikation" not in retained or "Schmerzanamnese" not in replaced:
        findings.append(f"{name}: the final step lists {replaced!r} and {retained!r}")
    if "Frühere Anamnese und Vormedikation" in replaced:
        findings.append(f"{name}: the final step replaces a manually edited section")
    if page.locator(".step-body form").count() != 0:
        findings.append(f"{name}: the final step body holds a form")
    findings += check_targets(page, f"{name} final step")
    page.screenshot(path=out / f"final-accept-{name}.png")
    page.click(".action-bar button:has-text('Übernehmen')")
    page.wait_for_url("**/abschluss")
    if page.locator("h1").first.inner_text().strip() != "Übergabe":
        findings.append(f"{name}: after accepting the last step is not Übergabe")

    # The retained section says Nicht aktualisiert, spelled out; the others are replaced.
    go_to_step(page, portrait, 3)
    if head_badges(page) != ["Manuell bearbeitet", "Nicht aktualisiert"]:
        findings.append(f"{name}: the retained section carries {head_badges(page)}")
    if "Nicht aktualisiert" not in page.inner_text("#section-head .badge-word"):
        findings.append(f"{name}: Nicht aktualisiert is not spelled out on the active section")
    if "eigene Anmerkung" not in page.input_value("#section-text"):
        findings.append(f"{name}: acceptance overwrote the hand edit")
    page.screenshot(path=out / f"section-retained-{name}.png")
    go_to_step(page, portrait, 5)
    if "Tiefer Rückenschmerz" not in page.input_value("#section-text"):
        findings.append(f"{name}: acceptance did not replace a section that was not edited")
    if head_badges(page):
        findings.append(f"{name}: an accepted section carries badges {head_badges(page)}")

    # Change notes while a proposal is pending: acceptance is disabled with its reason.
    page.goto(notes_url)
    generate_and_wait(page)
    if "Neu erzeugen" not in page.inner_text("[data-generate]"):
        findings.append(f"{name}: with a proposal the generate button does not say Neu erzeugen")
    page.click("#notes")
    page.keyboard.press("Control+End")
    page.keyboard.type(" Neue Angabe nach dem Vorschlag.", delay=10)
    page.wait_for_function(
        "document.querySelector('[data-save-indicator]').textContent.includes('Gespeichert')"
    )
    badge = page.get_attribute(".encounter-link.current ~ .badge-button", "aria-label")
    if badge != "Zustand: Vorschlag veraltet":
        findings.append(f"{name}: the sidebar badge after changing notes reads {badge!r}")
    go_to_step(page, portrait, 9)
    bars["outdated"] = bar_layout(page)
    if not page.is_disabled(".action-bar button:has-text('Übernehmen')"):
        findings.append(f"{name}: acceptance is enabled for an outdated proposal")
    reason = page.inner_text("#outdated-reason")
    if "Veraltet: Notizen seit diesem Vorschlag geändert" not in reason:
        findings.append(f"{name}: the outdated reason reads {reason!r}")
    note, bar = boxes(page, "#outdated-reason")[0], boxes(page, ".action-bar")[0]
    if not 0 <= bar["y"] - (note["y"] + note["h"]) <= 1:
        findings.append(f"{name}: the reason is not directly above the action bar")
    if page.locator(".marker").count() != 1:
        findings.append(f"{name}: no draft-possibly-outdated marker on the final step")
    findings += check_targets(page, f"{name} outdated proposal")
    page.screenshot(path=out / f"final-outdated-{name}.png")
    go_to_step(page, portrait, 2)
    if "Veraltet" not in page.inner_text("#section-head .badge-word"):
        findings.append(f"{name}: a section step does not say Veraltet")

    # Discard, then the handover: copy a section and see the acknowledgement.
    page.click(".action-bar button:has-text('Verwerfen')")
    page.wait_for_load_state()
    go_to_step(page, portrait, 9)
    bars["handover"] = bar_layout(page)
    if page.locator("h1").first.inner_text().strip() != "Übergabe":
        findings.append(f"{name}: the final step without a proposal is not Übergabe")
    if page.locator(".handover-row").count() != 7:
        findings.append(f"{name}: the handover has no row per section")
    page.screenshot(path=out / f"handover-{name}.png")
    row = page.locator(".handover-row").nth(2)
    row.locator("[data-copy]").click()
    page.wait_for_function(
        "document.querySelector('[data-save-indicator]').textContent.includes('Kopiert')"
    )
    clipboard = page.evaluate("navigator.clipboard.readText()")
    if not clipboard.startswith("Aktuelle Medikation\nIbuprofen 400 mg"):
        findings.append(f"{name}: the clipboard holds {clipboard[:60]!r}")
    if "Bandscheibenvorfall" in clipboard or "Frühere Anamnese" in clipboard:
        findings.append(f"{name}: the copied text is another section")
    if row.locator("[data-copy]").inner_text().strip() != "Kopiert":
        findings.append(f"{name}: the copy control does not acknowledge the copy")
    page.screenshot(path=out / f"handover-copied-{name}.png")
    page.wait_for_function(
        "document.querySelector('[data-save-indicator]').textContent.includes('Gespeichert')"
    )
    # The copy is recorded: the section carries the copied badge afterwards, and the copy
    # control of a section step copies what its draft pane shows (step 5 is Schmerzanamnese).
    go_to_step(page, portrait, 4)
    if head_badges(page) != ["Kopiert"]:
        findings.append(f"{name}: the copied section carries {head_badges(page)}")
    go_to_step(page, portrait, 5)
    page.click(".action-bar [data-copy]")
    page.wait_for_function(
        "document.querySelector('[data-save-indicator]').textContent.includes('Kopiert')"
    )
    if not page.evaluate("navigator.clipboard.readText()").startswith("Tiefer Rückenschmerz"):
        findings.append(f"{name}: the section step copied the wrong text")

    # Leaving a step with unsaved text saves it first: no pause, straight on to Weiter.
    go_to_step(page, portrait, 6)
    page.click("#section-text")
    page.keyboard.type("Sofort weitergegangen.")
    page.click(".action-bar a:has-text('Weiter')")
    page.wait_for_url("**/abschnitte/6")
    go_to_step(page, portrait, 6)
    if "Sofort weitergegangen." not in page.input_value("#section-text"):
        findings.append(f"{name}: text typed just before Weiter was lost")

    # Buttons keep their size and place across every step.
    for step, layout in bars.items():
        if layout != bars["notes"]:
            findings.append(
                f"{name}: the action bar on the {step} step differs from the notes step"
            )
    return findings


def api_encounter(base_url: str, page: Page) -> dict:
    """The encounter the page shows, as the JSON API has it: notes, revision and badge."""
    case_id, encounter_id = re.search(r"/faelle/(\d+)/kontakte/(\d+)/", page.url).groups()
    response = httpx.get(
        f"{base_url}/api/cases/{case_id}/encounters/{encounter_id}",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    response.raise_for_status()
    return response.json()


def use_fixture_audio(page: Page, clip: cast.FixtureClip | None) -> None:
    """The next recording is this fixture clip; None records from the browser's fake device."""
    encoded = base64.b64encode(cast.fixture_audio(clip.key)).decode() if clip else None
    page.evaluate("encoded => { window.__fixtureAudio = encoded; }", encoded)


def dictation_states(page: Page) -> list[str]:
    """The overlay panels that are showing; exactly one while the overlay is open."""
    return page.eval_on_selector_all(
        "dialog.dictation[open] .dictation-state:not([hidden])",
        "els => els.map(e => e.dataset.state)",
    )


def wait_for_panel(page: Page, state: str) -> None:
    page.wait_for_selector(f"dialog.dictation[open] [data-state={state}]:not([hidden])")


def check_overlay_blocks(page: Page, name: str, state: str) -> list[str]:
    """While the overlay is open nothing behind it can be tapped, tabbed to or escaped to."""
    findings: list[str] = []
    where = f"{name} overlay {state}"
    state_key = "failed" if state == "denied" else state
    url = page.url
    viewport = page.viewport_size
    for selector in (".action-bar .action-button", ".topbar .btn", ".case-link", ".step-link"):
        for box in boxes(page, selector):
            x, y = box["x"] + box["w"] / 2, box["y"] + box["h"] / 2
            if not (0 <= x <= viewport["width"] and 0 <= y <= viewport["height"]):
                continue
            hit = page.evaluate(
                "([x, y]) => !!document.elementFromPoint(x, y)?.closest('dialog.dictation')",
                [x, y],
            )
            if not hit:
                findings.append(f"{where}: {selector} can be tapped at {x:.0f},{y:.0f}")
    try:
        page.click(".action-bar a:has-text('Weiter')", timeout=600)
        findings.append(f"{where}: Weiter could be clicked")
    except PlaywrightTimeout:
        pass
    # Twice: a second Escape without a tap in between closes a dialog whatever `cancel` did.
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    page.wait_for_timeout(150)
    if not page.locator("dialog.dictation[open]").count() or dictation_states(page) != [state_key]:
        findings.append(f"{where}: Escape closed the overlay")
    for _ in range(12):
        page.keyboard.press("Tab")
        # A panel with nothing to tap (the wait) leaves focus on the page itself, whose
        # content is inert.
        inside = (
            "document.activeElement === document.body"
            " || document.activeElement.closest('dialog.dictation')"
        )
        if not page.evaluate(f"!!({inside})"):
            findings.append(f"{where}: Tab moved focus out of the overlay")
            break
    if page.url != url:
        findings.append(f"{where}: the page behind navigated")
    return findings


def overlay_layout(page: Page) -> dict:
    return {
        "dialog": boxes(page, "dialog.dictation")[0],
        "actions": boxes(page, ".dictation-state:not([hidden]) .dialog-actions")[0],
    }


def dictation_screens(page: Page, base_url: str, out: Path, name: str) -> list[str]:
    """The dictation flow: the microphone control on a review step, the overlay blocking the
    step, recording, transcribing, reviewing and correcting the canned transcript, accepting it
    into the notes (with a refused accept first), discarding, and the failures: microphone
    denied and a recording the speech stand-in cannot transcribe. Typed notes survive each."""
    findings: list[str] = []
    portrait = name == "ipad-portrait"
    transcript_route = "**/api/cases/*/encounters/*/dictation/transcript"
    accept_route = "**/api/cases/*/encounters/*/dictation/accept"
    clip = next(
        clip
        for case in cast.load_cast().cases
        if case.case_number == "FIK-2026-001"
        for encounter in case.encounters
        if encounter.kind == "assessment"
        for clip in encounter.audio
    )
    corrected = clip.transcript.replace("zweimal", "dreimal")

    open_case(page, base_url, "FIK-2026-001", portrait)
    open_drawer(page, portrait)
    page.click(".encounter-link:has-text('Aufnahmeassessment')")
    page.wait_for_url("**/notizen")
    notes_url = page.url
    generate_and_wait(page)
    go_to_step(page, portrait, 5)
    section_url = page.url
    bar = bar_layout(page)
    if page.is_disabled("[data-dictate]"):
        findings.append(f"{name}: the microphone control is disabled on a review step")
    if page.locator("dialog.dictation[open]").count() or page.evaluate("window.__micRequests"):
        findings.append(f"{name}: the page opened the overlay or the microphone before the tap")
    before = api_encounter(base_url, page)

    # Microphone permission denied: told in the overlay, with a way out; nothing is lost.
    page.evaluate("window.__denyMicrophone = true")
    page.click("[data-dictate]")
    wait_for_panel(page, "failed")
    shown = page.inner_text("dialog.dictation [data-state=failed]")
    if "Mikrofon nicht erlaubt" not in shown or "Lindra darf das Mikrofon nicht" not in shown:
        findings.append(f"{name}: the denied-permission message reads {shown!r}")
    for label in ("Schließen", "Erneut versuchen"):
        button = page.locator(f"dialog.dictation [data-state=failed] .btn:has-text('{label}')")
        if not button.is_visible():
            findings.append(f"{name}: the denied-permission overlay has no {label}")
    findings += check_overlay_blocks(page, name, "denied")
    findings += check_targets(page, f"{name} overlay denied")
    page.screenshot(path=out / f"dictation-denied-{name}.png")
    page.click("[data-retry-dictation]")
    wait_for_panel(page, "failed")
    if page.evaluate("window.__micRequests") != 2:
        findings.append(f"{name}: retry after a denial did not ask for the microphone again")
    page.click("[data-close]")
    if page.locator("dialog.dictation[open]").count() or page.url != section_url:
        findings.append(f"{name}: closing the denied-permission overlay did not end on the step")
    if api_encounter(base_url, page) != before:
        findings.append(f"{name}: a denied microphone changed the encounter")
    page.evaluate("window.__denyMicrophone = false")

    # The recorder cannot be made or started although the microphone was granted: the overlay
    # says so with a way out, and the microphone is released, so the browser stops showing it.
    for fault in ("construct", "start"):
        use_fixture_audio(page, clip)
        page.evaluate("fault => { window.__recorderFault = fault; }", fault)
        page.click("[data-dictate]")
        wait_for_panel(page, "failed")
        shown = page.inner_text("dialog.dictation [data-state=failed]")
        if (
            "Aufnahme nicht möglich" not in shown
            or "Die Aufnahme lässt sich nicht starten" not in shown
        ):
            findings.append(f"{name}: a recorder fault ({fault}) reads {shown!r}")
        for label in ("Schließen", "Erneut versuchen"):
            button = page.locator(f"dialog.dictation [data-state=failed] .btn:has-text('{label}')")
            if not button.is_visible():
                findings.append(f"{name}: a recorder fault ({fault}) leaves no {label}")
        if page.evaluate("window.__liveTracks()") != 0:
            findings.append(f"{name}: a recorder fault ({fault}) leaves the microphone open")
        if fault == "construct":
            page.click("[data-close]")
        else:
            # The retry works once the fault is gone, and the recording ends released too.
            page.evaluate("window.__recorderFault = null")
            page.click("[data-retry-dictation]")
            wait_for_panel(page, "recording")
            page.click("[data-stop]")
            wait_for_panel(page, "reviewing")
            page.click("[data-discard]")
        if page.locator("dialog.dictation[open]").count():
            findings.append(f"{name}: the overlay stays open after a recorder fault ({fault})")
    page.evaluate("window.__recorderFault = null")
    if page.evaluate("window.__liveTracks()") != 0:
        findings.append(f"{name}: the microphone stays open after the recorder faults")
    if api_encounter(base_url, page) != before:
        findings.append(f"{name}: a recorder fault changed the encounter")

    # A recorder that breaks while recording still delivers its data and a stop event a moment
    # later. The broken recording is not transcribed, and those late events change neither the
    # failure panel, nor a closed overlay, nor the dictation started again meanwhile.
    uploads: list = []
    page.on(
        "request",
        lambda request: uploads.append(request) if "dictation/transcript" in request.url else None,
    )
    for then in ("waits", "closes", "restarts"):
        use_fixture_audio(page, clip)
        page.click("[data-dictate]")
        wait_for_panel(page, "recording")
        page.evaluate("window.__recorder.breakDown(600)")
        wait_for_panel(page, "failed")
        if "Aufnahme abgebrochen" not in page.inner_text("dialog.dictation [data-state=failed]"):
            findings.append(f"{name}: a broken recorder ({then}) is not reported as interrupted")
        if page.evaluate("window.__liveTracks()") != 0:
            findings.append(f"{name}: a broken recorder ({then}) leaves the microphone open")
        if then == "waits":
            page.wait_for_timeout(900)
            if dictation_states(page) != ["failed"]:
                findings.append(f"{name}: late recorder events changed the failure panel")
            page.click("[data-close]")
        elif then == "closes":
            page.click("[data-close]")
            page.wait_for_timeout(900)
            if page.locator("dialog.dictation[open]").count():
                findings.append(f"{name}: late recorder events reopened a closed overlay")
        else:
            page.click("[data-retry-dictation]")
            wait_for_panel(page, "recording")
            page.wait_for_timeout(900)
            if dictation_states(page) != ["recording"]:
                findings.append(f"{name}: late recorder events broke the new recording")
            if page.evaluate("window.__liveTracks()") != 1:
                findings.append(f"{name}: late recorder events closed the new microphone stream")
            page.click("[data-stop]")
            wait_for_panel(page, "reviewing")
            page.click("[data-discard]")
    if len(uploads) != 1:
        findings.append(f"{name}: {len(uploads)} recordings were sent, only the good one belongs")
    if api_encounter(base_url, page) != before:
        findings.append(f"{name}: a broken recorder changed the encounter")

    # The canned transcript for fixture audio, through every state of the overlay.
    use_fixture_audio(page, clip)
    held: list = []
    page.route(transcript_route, lambda route: held.append(route))
    layouts = {}
    page.click("[data-dictate]")
    wait_for_panel(page, "recording")
    layouts["recording"] = overlay_layout(page)
    page.wait_for_timeout(1200)
    if page.inner_text("[data-elapsed]") == "0:00":
        findings.append(f"{name}: the recording time does not run")
    findings += check_overlay_blocks(page, name, "recording")
    findings += check_targets(page, f"{name} overlay recording")
    page.screenshot(path=out / f"dictation-recording-{name}.png")
    page.click("[data-stop]")
    wait_for_panel(page, "transcribing")
    layouts["transcribing"] = overlay_layout(page)
    while not held:
        page.wait_for_timeout(50)
    # A recorder error that arrives after the stop has nothing left to interrupt.
    page.evaluate("window.__recorder.dispatchEvent(new Event('error'))")
    page.wait_for_timeout(150)
    if dictation_states(page) != ["transcribing"]:
        findings.append(f"{name}: a recorder error after the stop replaced the waiting panel")
    findings += check_overlay_blocks(page, name, "transcribing")
    page.screenshot(path=out / f"dictation-transcribing-{name}.png")
    for route in held:
        route.continue_()
    page.unroute(transcript_route)
    wait_for_panel(page, "reviewing")
    layouts["reviewing"] = overlay_layout(page)
    if page.input_value("[data-transcript]") != clip.transcript:
        findings.append(f"{name}: the transcript is {page.input_value('[data-transcript]')!r}")
    if not page.is_visible("[data-outdates]"):
        findings.append(f"{name}: the overlay does not say the pending proposal becomes outdated")
    findings += check_overlay_blocks(page, name, "reviewing")
    findings += check_targets(page, f"{name} overlay reviewing")
    page.screenshot(path=out / f"dictation-reviewing-{name}.png")
    if any(layout != layouts["recording"] for layout in layouts.values()):
        findings.append(f"{name}: the overlay or its buttons moved between states: {layouts}")
    box = layouts["recording"]["dialog"]
    if not (0 <= box["x"] and box["x"] + box["w"] <= page.viewport_size["width"]):
        findings.append(f"{name}: the overlay does not fit the viewport: {box}")
    if api_encounter(base_url, page) != before:
        findings.append(f"{name}: recording and transcribing changed the encounter")

    # Correct the transcript. A refusal (422) says the notes are unchanged and keeps the text
    # editable; a server error (500) says it is unclear and locks the text; neither loses it.
    page.fill("[data-transcript]", corrected)
    page.route(
        accept_route,
        lambda route: route.fulfill(
            status=422,
            content_type="application/json",
            body='{"errors": {"transcript": "Kein Text zum Übernehmen"}}',
        ),
    )
    page.click("[data-accept]")
    page.wait_for_selector("[data-accept-error]:not([hidden])")
    refused = page.inner_text("[data-accept-error]")
    if "Kein Text zum Übernehmen" not in refused or "Die Notizen sind unverändert" not in refused:
        findings.append(f"{name}: a refused accept reads {refused!r}")
    if page.is_editable("[data-transcript]") is False:
        findings.append(f"{name}: a refused accept locked the text")
    page.unroute(accept_route)
    page.route(accept_route, lambda route: route.fulfill(status=500, body="{}"))
    page.click("[data-accept]")
    page.wait_for_selector("[data-accept-error]:not([hidden])")
    if not page.evaluate("document.querySelector('[data-transcript]').readOnly"):
        findings.append(f"{name}: the text is not locked while the outcome is unclear")
    if page.input_value("[data-transcript]") != corrected or page.is_disabled("[data-accept]"):
        findings.append(f"{name}: a server error lost the corrected text or its button")
    if api_encounter(base_url, page) != before:
        findings.append(f"{name}: a refused accept changed the notes")
    unsure = page.inner_text("[data-accept-error]")
    if "unklar" not in unsure or "Die Notizen sind unverändert" in unsure:
        findings.append(f"{name}: a server error reads {unsure!r}")
    page.unroute(accept_route)

    # The answer is lost after the service appended: the overlay does not claim the notes are
    # unchanged, and the retry adds nothing a second time.
    def lose_answer(route):
        route.fetch()
        route.abort()

    page.route(accept_route, lose_answer)
    page.click("[data-accept]")
    page.wait_for_selector("[data-accept-error]:not([hidden])")
    if "unklar" not in page.inner_text("[data-accept-error]"):
        findings.append(f"{name}: a lost answer is not reported as unclear")
    if "nicht doppelt" not in page.inner_text("[data-accept-error]"):
        findings.append(f"{name}: the lost-answer message does not say a retry is safe")
    if page.input_value("[data-transcript]") != corrected or page.is_disabled("[data-accept]"):
        findings.append(f"{name}: a lost answer lost the corrected text or its button")
    message = boxes(page, "[data-accept-error]")[0]
    body = boxes(page, "[data-state=reviewing] .dialog-body")[0]
    if message["y"] < body["y"] or message["y"] + message["h"] > body["y"] + body["h"] + 1:
        findings.append(f"{name}: the lost-answer message is cut off: {message} in {body}")
    appended = api_encounter(base_url, page)
    if appended["notes"].count(corrected) != 1:
        findings.append(f"{name}: the lost-answer accept did not append once")
    page.screenshot(path=out / f"dictation-unsure-{name}.png")
    page.unroute(accept_route)
    with page.expect_navigation():
        page.click("[data-accept]")
    page.wait_for_load_state()
    if api_encounter(base_url, page) != appended:
        findings.append(f"{name}: the retry after a lost answer changed the notes again")
    if page.url != notes_url:
        findings.append(f"{name}: accepting did not show the notes step: {page.url}")
    after = api_encounter(base_url, page)
    notes = page.input_value("#notes")
    expected_tail = f"\n\n[Diktat, 10.11.2026 14:30]\n{corrected}\n"
    if notes != after["notes"] or not notes.startswith(before["notes"]):
        findings.append(f"{name}: the notes do not start with the typed text")
    if not notes.endswith(expected_tail) or "zweimal aufzuwachen" in notes:
        findings.append(f"{name}: the notes end with {notes[-120:]!r}")
    if after["notes_revision"] != before["notes_revision"] + 1:
        findings.append(f"{name}: the notes revision is {after['notes_revision']}")
    badge = page.get_attribute(".encounter-link.current ~ .badge-button", "aria-label")
    if badge != "Zustand: Vorschlag veraltet":
        findings.append(f"{name}: the sidebar badge after dictating reads {badge!r}")
    page.eval_on_selector("#notes", "e => e.scrollTop = e.scrollHeight")
    page.screenshot(path=out / f"notes-dictated-{name}.png")
    go_to_step(page, portrait, 9)
    if not page.is_disabled(".action-bar button:has-text('Übernehmen')"):
        findings.append(f"{name}: the proposal can be accepted after the notes changed")
    if bar_layout(page) != bar:
        findings.append(f"{name}: the action bar differs on the final step after dictating")
    page.goto(notes_url)

    # Discarding changes nothing.
    before = api_encounter(base_url, page)
    use_fixture_audio(page, clip)
    page.click("[data-dictate]")
    wait_for_panel(page, "recording")
    page.click("[data-stop]")
    wait_for_panel(page, "reviewing")
    page.click("[data-discard]")
    if page.locator("dialog.dictation[open]").count():
        findings.append(f"{name}: discarding left the overlay open")
    if api_encounter(base_url, page) != before or page.input_value("#notes") != before["notes"]:
        findings.append(f"{name}: discarding a transcript changed the notes")

    # Typed text that is not saved yet is saved first and stays above the dictated passage.
    page.click("#notes")
    page.keyboard.press("Control+End")
    page.keyboard.type(" Gerade getippt.", delay=5)
    page.click("[data-dictate]")
    wait_for_panel(page, "recording")
    page.click("[data-stop]")
    wait_for_panel(page, "reviewing")
    with page.expect_navigation():
        page.click("[data-accept]")
    page.wait_for_load_state()
    notes = page.input_value("#notes")
    if " Gerade getippt.\n\n[Diktat, 10.11.2026 14:30]\n" not in notes:
        findings.append(f"{name}: text typed just before dictating is not above the passage")
    if notes.count("[Diktat, ") != 2 or not notes.startswith(before["notes"]):
        findings.append(f"{name}: a second dictation did not follow the first: {notes[-200:]!r}")

    # A recording the speech stand-in cannot transcribe: told in the overlay, retry, close.
    before = api_encounter(base_url, page)
    use_fixture_audio(page, None)
    sent: list = []
    page.on(
        "request",
        lambda request: sent.append(request) if "dictation/transcript" in request.url else None,
    )
    page.click("[data-dictate]")
    wait_for_panel(page, "recording")
    page.wait_for_timeout(1200)
    page.click("[data-stop]")
    wait_for_panel(page, "failed")
    shown = page.inner_text("dialog.dictation [data-state=failed]")
    if "Text nicht erstellt" not in shown or "erfundenen Fälle" not in shown:
        findings.append(f"{name}: the failed-transcription message reads {shown!r}")
    findings += check_overlay_blocks(page, name, "failed")
    findings += check_targets(page, f"{name} overlay failed")
    page.screenshot(path=out / f"dictation-failed-{name}.png")
    page.click("[data-retry-dictation]")
    wait_for_panel(page, "failed")
    if len(sent) != 2 or sent[0].post_data_buffer != sent[1].post_data_buffer:
        findings.append(f"{name}: retry did not send the same recording again ({len(sent)})")
    page.click("[data-close]")
    if page.locator("dialog.dictation[open]").count():
        findings.append(f"{name}: closing the failure left the overlay open")
    if api_encounter(base_url, page) != before:
        findings.append(f"{name}: a failed transcription changed the notes")

    # The answer is lost after the service appended and the physician then discards the
    # dictation: the page must show the notes as saved, or her next edit would save the stale
    # text over the passage.
    use_fixture_audio(page, clip)
    page.click("[data-dictate]")
    wait_for_panel(page, "recording")
    page.click("[data-stop]")
    wait_for_panel(page, "reviewing")
    page.route(accept_route, lose_answer)
    page.click("[data-accept]")
    page.wait_for_selector("[data-accept-error]:not([hidden])")
    page.unroute(accept_route)
    with page.expect_navigation():
        page.click("[data-discard]")
    page.wait_for_load_state()
    held_back = api_encounter(base_url, page)
    if (
        held_back["notes"].count("[Diktat, ") != 3
        or page.input_value("#notes") != held_back["notes"]
    ):
        findings.append(f"{name}: after a lost answer and a discard the page shows stale notes")
    page.click("#notes")
    page.keyboard.press("Control+End")
    page.keyboard.type(" Danach getippt.", delay=5)
    page.wait_for_function(
        "document.querySelector('[data-save-indicator]').textContent.includes('Gespeichert')"
    )
    saved = api_encounter(base_url, page)["notes"]
    if saved != held_back["notes"] + " Danach getippt.":
        findings.append(f"{name}: typing after a lost answer and a discard changed the passage")

    # While the accept is on its way the dictation cannot be discarded: the service may save the
    # passage after the overlay was closed over the old notes. The page then shows the saved notes.
    use_fixture_audio(page, clip)
    page.click("[data-dictate]")
    wait_for_panel(page, "recording")
    page.click("[data-stop]")
    wait_for_panel(page, "reviewing")
    waiting: list = []
    page.route(accept_route, lambda route: waiting.append(route))
    page.click("[data-accept]")
    while not waiting:
        page.wait_for_timeout(50)
    if page.is_enabled("[data-discard]") or page.is_enabled("[data-accept]"):
        findings.append(f"{name}: discard or accept stays enabled while the accept is on its way")
    page.evaluate("document.querySelector('[data-discard]').click()")
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    page.wait_for_timeout(150)
    if not page.locator("dialog.dictation[open]").count():
        findings.append(f"{name}: the overlay closed while the accept was on its way")
    if not page.evaluate("document.querySelector('[data-transcript]').readOnly"):
        findings.append(f"{name}: the transcript stays editable while the accept is on its way")
    page.evaluate("document.querySelector('[data-transcript]').dispatchEvent(new Event('input'))")
    if page.is_enabled("[data-accept]") or page.is_enabled("[data-discard]"):
        findings.append(f"{name}: an input event re-enabled accept or discard in flight")
    with page.expect_navigation():
        for route in waiting:
            route.continue_()
    page.unroute(accept_route)
    page.wait_for_load_state()
    after_flight = api_encounter(base_url, page)
    if (
        after_flight["notes"].count("[Diktat, ") != 4
        or page.input_value("#notes") != after_flight["notes"]
    ):
        findings.append(f"{name}: the notes after an accept in flight are not the saved notes")
    return findings


def small_targets(page: Page, selector: str) -> list[dict]:
    return [b for b in boxes(page, selector) if b["w"] > 0 and (b["w"] < 44 or b["h"] < 44)]


def fidelity_screens(page: Page, base_url: str, out: Path, name: str) -> list[str]:
    """Input references, pain problems and the clarification list (ticket 08), on the second
    fictional case: three pains and an open question. Taps a reference and reads the quoted
    passage, hand-rewrites one paragraph and sees only its reference go, and checks that the
    clarification list stays as it was."""
    findings: list[str] = []
    portrait = name == "ipad-portrait"
    open_case(page, base_url, "FIK-2026-002", portrait)
    open_drawer(page, portrait)
    page.click(".encounter-link:has-text('Aufnahmeassessment')")
    page.wait_for_url("**/notizen")
    notes_bar = bar_layout(page)
    generate_and_wait(page)

    # The Schmerzanamnese (step 5): every pain problem is its own block, none is the main pain.
    go_to_step(page, portrait, 5)
    headings = page.eval_on_selector_all(
        ".proposal-text .para-heading", "els => els.map(e => e.textContent.trim())"
    )
    if headings != ["Migräne", "Linkes Knie", "Beide Füße", "Ohne Zuordnung zu einem Schmerz"]:
        findings.append(f"{name}: the proposal's pain blocks are {headings}")
    if "Hauptschmerz" in page.inner_text(".proposal-text"):
        findings.append(f"{name}: the proposal names a main pain nobody named")
    if bar_layout(page) != notes_bar:
        findings.append(f"{name}: the pain step moved the action bar")
    page.screenshot(path=out / f"pain-problems-proposal-{name}.png")

    # Tap a reference: the quoted passage of the notes opens.
    toggle = page.locator(".proposal-text .origin-toggle").first
    quote = page.locator(".proposal-text .origin-quote").first
    if quote.is_visible():
        findings.append(f"{name}: a reference shows its passage before it is tapped")
    toggle.click()
    page.wait_for_function("document.querySelector('.proposal-text details.origin').open")
    if "Migräne seit der Jugend, 3 Attacken pro Monat" not in quote.inner_text():
        findings.append(f"{name}: the reference shows {quote.inner_text()!r}")
    if not quote.is_visible():
        findings.append(f"{name}: the quoted passage is not visible after the tap")
    if small_targets(page, ".origin-toggle"):
        findings.append(f"{name}: a reference toggle is under 44 by 44 CSS px")
    if "aus Notizen" not in toggle.inner_text():
        findings.append(f"{name}: the reference reads {toggle.inner_text()!r}")
    for claim in ("korrekt", "geprüft", "Konfidenz", "%"):
        if claim in page.inner_text(".proposal-text"):
            findings.append(f"{name}: the proposal pane says {claim!r}")
    page.screenshot(path=out / f"reference-open-{name}-proposal.png")

    # Accept; the draft pane lists where each paragraph came from.
    go_to_step(page, portrait, 9)
    page.click(".action-bar button:has-text('Übernehmen')")
    page.wait_for_url("**/abschluss")
    go_to_step(page, portrait, 5)
    page.screenshot(path=out / f"pain-problems-draft-{name}.png")
    asked = page.inner_text(".clarifications")
    if "Welcher der drei Schmerzen steht im Vordergrund" not in asked:
        findings.append(f"{name}: the pain step does not show its clarification item")

    # Therapeutische Anamnese (step 4): three paragraphs, each "aus Notizen"; rewrite one.
    go_to_step(page, portrait, 4)
    if page.locator("#section-origins .origin-toggle").count() != 3:
        findings.append(f"{name}: the draft pane does not list three references")
    if page.locator("#section-origins .origin-hand").count() != 0:
        findings.append(f"{name}: a generated paragraph reads von Hand")
    go_to_step(page, portrait, 9)
    list_before = page.inner_text(".clarifications")
    go_to_step(page, portrait, 4)
    page.click("#section-text")
    page.keyboard.press("Control+End")
    page.keyboard.type(" Zweimal pro Woche.", delay=10)
    page.wait_for_function(
        "document.querySelector('[data-save-indicator]').textContent.includes('Gespeichert')"
    )
    page.wait_for_selector("#section-origins .origin-hand")
    hand = page.locator("#section-origins .origin-hand")
    if hand.count() != 1 or "von Hand, keine Herkunft" not in hand.inner_text():
        findings.append(f"{name}: the rewritten paragraph does not read von Hand, keine Herkunft")
    if page.locator("#section-origins .origin-toggle").count() != 2:
        findings.append(f"{name}: the other paragraphs lost their reference")
    if "Zweimal pro Woche." not in page.input_value("#section-text"):
        findings.append(f"{name}: the hand edit is not in the draft pane")
    page.screenshot(path=out / f"hand-rewritten-{name}.png")
    page.locator("#section-origins .origin-toggle").first.click()
    page.screenshot(path=out / f"reference-open-{name}-draft.png")

    # The edit removed no clarification item; the final step shows the whole list.
    go_to_step(page, portrait, 9)
    if page.inner_text(".clarifications") != list_before:
        findings.append(f"{name}: a manual edit changed the clarification list")
    page.evaluate("document.querySelector('.step-body').scrollTop = 99999")
    page.screenshot(path=out / f"clarification-list-{name}.png")
    if bar_layout(page) != notes_bar:
        findings.append(f"{name}: the final step moved the action bar")
    findings += check_targets(page, f"{name} fidelity final step")
    return findings


def accept_proposal(page: Page, portrait: bool, final_step: int) -> None:
    """Open the last step, which is "Übernehmen" while a proposal is pending, and accept it."""
    go_to_step(page, portrait, final_step)
    page.click(".action-bar button:has-text('Übernehmen')")
    page.wait_for_url("**/abschluss")


def encounter_badge_label(page: Page, when: str) -> str:
    """The label of the state badge the sidebar shows beside the encounter dated `when`."""
    item = page.locator(".encounter-item", has=page.locator(".encounter-link", has_text=when))
    return item.locator(".badge-button").get_attribute("aria-label") or ""


def open_encounter(page: Page, portrait: bool, label: str) -> None:
    """Switch to another encounter of the open case from the sidebar (the drawer in portrait)."""
    open_drawer(page, portrait)
    previous = page.url
    page.click(f".encounter-link:has-text('{label}')")
    page.wait_for_function("url => location.href !== url", arg=previous)
    page.wait_for_load_state()


def background_screens(page: Page, base_url: str, out: Path, name: str) -> list[str]:
    """The second half of the browser flow (ticket 09), on the first fictional case: accept the
    assessment, be refused a visit outside the period and create a backdated one inside it,
    generate the visit and read a historical reference, accept the assessment again and see the
    visit's background marker, badge and refused proposal, switch encounters through the
    drawer, and open an encounter without an accepted draft."""
    findings: list[str] = []
    portrait = name == "ipad-portrait"
    case_number = "FIK-2026-001"
    assessment, seeded_visit, new_visit = (
        "Aufnahmeassessment",
        "09.10.2026 09:00",
        "09.10.2026 08:00",
    )

    # The accepted assessment is what the visit draws on.
    open_case(page, base_url, case_number, portrait)
    open_drawer(page, portrait)
    page.click(f".encounter-link:has-text('{assessment}')")
    page.wait_for_url("**/notizen")
    generate_and_wait(page)
    accept_proposal(page, portrait, 9)

    # A visit outside the period is refused and keeps what was typed; backdated inside it, it
    # is created.
    open_case(page, base_url, case_number, portrait)
    page.click("main a:has-text('Neue Visite')")
    page.wait_for_selector("dialog[open]")
    page.fill("#visit_date", "2026-10-20")
    page.fill("#visit_time", "08:00")
    page.click("button:has-text('Visite anlegen')")
    page.wait_for_selector(".field-error:not(:empty)")
    if "Behandlungszeitraum" not in page.inner_text("#visit_date-error"):
        findings.append(f"{name}: the refusal outside the period does not name the period")
    page.fill("#visit_date", "2026-10-09")
    page.click("button:has-text('Visite anlegen')")
    page.wait_for_url("**/notizen")
    # The fixture model answers with the cast's draft, whose references point into the notes of
    # the cast's visit, so those are the notes entered.
    page.fill("#notes", load_cast().cases[0].encounters[1].notes)
    page.wait_for_function(
        "document.querySelector('[data-save-indicator]').textContent.includes('Gespeichert')"
    )
    notes_bar = bar_layout(page)
    if encounter_badge_label(page, new_visit) != "Zustand: Notizen gespeichert, noch kein Entwurf":
        findings.append(f"{name}: the new visit does not show the notes-only badge")

    # Generating the visit: its four sections, a historical reference beside today's.
    generate_and_wait(page)
    go_to_step(page, portrait, 2)
    if (
        page.locator(".section-step .step-title").inner_text().strip()
        != "Verlauf seit letzter Visite"
    ):
        findings.append(f"{name}: the first visit step is not Verlauf seit letzter Visite")
    labels = page.eval_on_selector_all(
        ".step-list .step-label", "els => els.map(e => e.textContent.trim())"
    )
    if labels != [
        "Notizen",
        "Verlauf seit letzter Visite",
        "Aktuelle Befunde",
        "Ärztliche Einschätzung",
        "Vereinbartes Vorgehen und Ziele",
        "Übernehmen",
    ]:
        findings.append(f"{name}: the visit steps are {labels}")
    if bar_layout(page) != notes_bar:
        findings.append(f"{name}: the visit step moved the action bar")
    earlier = page.locator(".proposal-text details.origin-earlier")
    today = page.locator(".proposal-text details.origin:not(.origin-earlier)")
    if earlier.count() != 1 or today.count() < 1:
        findings.append(f"{name}: the proposal does not show one historical and a notes reference")
    else:
        toggle, quote = earlier.locator(".origin-toggle"), earlier.locator(".origin-quote")
        if "aus früherem Kontakt" not in toggle.inner_text():
            findings.append(f"{name}: the historical reference reads {toggle.inner_text()!r}")
        if "aus Notizen" not in today.first.locator(".origin-toggle").inner_text():
            findings.append(f"{name}: today's reference no longer reads aus Notizen")
        if quote.is_visible():
            findings.append(f"{name}: the historical quote shows before it is tapped")
        toggle.click()
        page.wait_for_function(
            "document.querySelector('.proposal-text details.origin-earlier').open"
        )
        if "Ibuprofen 400 mg bei Bedarf" not in quote.inner_text():
            findings.append(f"{name}: the historical reference shows {quote.inner_text()!r}")
        caption = earlier.locator(".origin-caption").inner_text()
        if caption.strip() != "Aufnahmeassessment, 05.10.2026 09:00":
            findings.append(f"{name}: the reference names {caption!r}, not encounter and date")
        looks = page.evaluate(
            "() => { const s = sel => getComputedStyle(document.querySelector(sel));"
            " return [s('.proposal-text details.origin-earlier > summary').backgroundColor,"
            " s('.proposal-text details.origin:not(.origin-earlier) > summary').backgroundColor]; }"
        )
        if looks[0] == looks[1]:
            findings.append(f"{name}: the two kinds of reference look the same: {looks}")
        if small_targets(page, ".origin-toggle"):
            findings.append(f"{name}: a reference toggle is under 44 by 44 CSS px")
    page.screenshot(path=out / f"visit-historical-reference-{name}.png")
    findings += check_targets(page, f"{name} visit proposal step")

    # Accept it. The contradiction with the background is on the list, naming both statements.
    accept_proposal(page, portrait, 6)
    go_to_step(page, portrait, 2)
    kept_text = page.input_value("#section-text")
    asked = page.inner_text(".clarifications")
    if "strahlt der Schmerz nicht ins Bein aus" not in asked or "Ausstrahlung" not in asked:
        findings.append(f"{name}: the contradiction item does not name both statements")
    if page.locator("#section-origins .origin-earlier").count() != 1:
        findings.append(f"{name}: the draft pane does not list the historical reference")
    if page.locator("[data-background-changed]").count() != 0:
        findings.append(f"{name}: the marker shows before the background changed")

    # A second proposal on the current background; then the assessment is accepted again.
    generate_and_wait(page)
    if encounter_badge_label(page, new_visit) != "Zustand: Vorschlag liegt vor":
        findings.append(f"{name}: a pending visit proposal does not show its badge")
    open_encounter(page, portrait, assessment)
    page.click("#notes")
    page.keyboard.press("Control+End")
    page.keyboard.type(" Nachts wacht sie zweimal auf.", delay=10)
    page.wait_for_function(
        "document.querySelector('[data-save-indicator]').textContent.includes('Gespeichert')"
    )
    generate_and_wait(page)
    accept_proposal(page, portrait, 9)

    # The visit: its draft carries the marker with the text kept, its proposal is refused.
    open_encounter(page, portrait, new_visit)
    if (
        encounter_badge_label(page, new_visit)
        != "Zustand: Vorschlag veraltet, Hintergrund geändert"
    ):
        findings.append(
            f"{name}: the sidebar badge of the visit is {encounter_badge_label(page, new_visit)!r}"
        )
    marker = page.locator("[data-background-changed]")
    if marker.count() != 1 or "Hintergrund seit Erstellung geändert" not in marker.inner_text():
        findings.append(f"{name}: the visit does not show Hintergrund seit Erstellung geändert")
    page.screenshot(path=out / f"visit-background-marker-{name}.png")
    go_to_step(page, portrait, 2)
    if page.input_value("#section-text") != kept_text:
        findings.append(f"{name}: the visit text changed with its background")
    if "Veraltet" not in page.inner_text("#section-head"):
        findings.append(f"{name}: a section of the outdated proposal does not say Veraltet")
    go_to_step(page, portrait, 6)
    reason = page.locator("[data-outdated-reason]")
    if "Veraltet: Hintergrund seit diesem Vorschlag geändert" not in reason.inner_text():
        findings.append(f"{name}: the refused proposal does not spell out its reason")
    elif not reason.is_visible():
        findings.append(f"{name}: the reason is not visible")
    if not page.is_disabled(".action-bar button:has-text('Übernehmen')"):
        findings.append(f"{name}: an outdated visit proposal can be accepted")
    if bar_layout(page) != notes_bar:
        findings.append(f"{name}: the refused proposal moved the action bar")
    page.screenshot(path=out / f"proposal-refused-background-{name}.png")
    findings += check_targets(page, f"{name} refused visit proposal")

    # Discarding the proposal leaves the marker, the text and the badge of the draft.
    page.click(".action-bar button:has-text('Verwerfen')")
    page.wait_for_load_state()
    if page.locator("[data-background-changed]").count() != 1:
        findings.append(f"{name}: discarding the outdated proposal cleared the marker")
    label = encounter_badge_label(page, new_visit)
    if label != "Zustand: Hintergrund seit Erstellung geändert":
        findings.append(f"{name}: the visit's badge after discarding is {label!r}")
    open_drawer(page, portrait)
    item = page.locator(".encounter-item", has=page.locator(".encounter-link", has_text=new_visit))
    item.locator(".badge-button").click()
    page.wait_for_selector(".encounter-item .badge-explanation:not([hidden])")
    page.screenshot(path=out / f"sidebar-background-badge-{name}.png")
    close_drawer(page, portrait)
    go_to_step(page, portrait, 2)
    if page.input_value("#section-text") != kept_text:
        findings.append(f"{name}: discarding the proposal changed the draft")

    # Switching encounters through the drawer; the assessment has no marker of its own.
    open_drawer(page, portrait)
    page.screenshot(path=out / f"encounter-switch-{name}.png")
    page.click(f".encounter-link:has-text('{assessment}')")
    page.wait_for_url("**/notizen")
    if page.locator("[data-background-changed]").count() != 0:
        findings.append(f"{name}: the assessment shows a background marker")
    if assessment not in page.inner_text(".case-subtitle"):
        findings.append(f"{name}: the encounter switch did not open the assessment")

    # An encounter without an accepted draft has nothing to copy.
    open_encounter(page, portrait, seeded_visit)
    go_to_step(page, portrait, 6)
    if page.locator("[data-nothing-to-copy]").count() != 1:
        findings.append(f"{name}: an encounter without a draft does not say there is nothing")
    if page.locator("[data-copy]").count() != 0:
        findings.append(f"{name}: an encounter without a draft offers a copy control")
    if not page.is_disabled(".action-bar button:has-text('Kopieren')"):
        findings.append(f"{name}: the action bar's copy button is enabled without a draft")
    page.screenshot(path=out / f"nothing-to-copy-{name}.png")
    findings += check_targets(page, f"{name} encounter without a draft")
    return findings


def main(argv: list[str]) -> int:
    root = Path(argv[0]) if argv else Path("docs/screenshots")
    out, fidelity_out, dictation_out = root / "LFR-07", root / "LFR-08", root / "LFR-10"
    background_out = root / "LFR-09"
    out.mkdir(parents=True, exist_ok=True)
    dictation_out.mkdir(parents=True, exist_ok=True)
    fidelity_out.mkdir(parents=True, exist_ok=True)
    background_out.mkdir(parents=True, exist_ok=True)
    findings: list[str] = []
    with (
        running_server() as base_url,
        sync_playwright() as playwright,
        tempfile.TemporaryDirectory() as scratch,
    ):
        # A fake microphone that records a tone, and no permission prompt (headless Chromium
        # has no prompt to show; a denial is simulated in `INIT_SCRIPT`).
        browser = playwright.chromium.launch(
            args=["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"]
        )
        for name, viewport in VIEWPORTS.items():
            reseed(base_url)
            context = browser.new_context(**viewport, locale="de-DE")
            context.add_init_script(INIT_SCRIPT)
            page = context.new_page()
            log_in(page, base_url)
            # Tickets 05 and 06 are checked on every run; their pictures are not kept.
            findings.extend(case_screens(page, base_url, Path(scratch), name))
            reseed(base_url)
            findings.extend(visit_screens(page, base_url, Path(scratch), name))
            findings.extend(notes_screens(page, base_url, Path(scratch), name))
            reseed(base_url)
            findings.extend(review_screens(page, base_url, out, name))
            reseed(base_url)
            findings.extend(fidelity_screens(page, base_url, fidelity_out, name))
            reseed(base_url)
            findings.extend(background_screens(page, base_url, background_out, name))
            reseed(base_url)
            findings.extend(dictation_screens(page, base_url, dictation_out, name))
            context.close()
        browser.close()
    for finding in findings:
        print(finding)
    print(f"screenshots written to {out}, {fidelity_out}, {background_out} and {dictation_out}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

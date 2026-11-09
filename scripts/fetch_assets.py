#!/usr/bin/env python3
"""Fetch the pinned, self-hosted UI assets into lindra/static/vendor/.

Nothing is loaded from a CDN at runtime (ADR 0009). This script downloads the
pinned releases, verifies their SHA-256, and copies only the files the
application uses. The output is committed, so a clean clone needs no network
and no Node toolchain; rerun the script only to change a pin.

Usage: python3 scripts/fetch_assets.py [--check]

--check verifies that the committed vendor files match this script's pins
without downloading anything.
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "lindra" / "static" / "vendor"

DAISYUI_VERSION = "5.7.50"
DAISYUI_URL = f"https://registry.npmjs.org/daisyui/-/daisyui-{DAISYUI_VERSION}.tgz"
DAISYUI_SHA256 = "e8e51df2ac7b077a512242bca51433a95c9b35f6d5b76faec98ce964aba8424c"
# daisyUI ships one CSS file per component. The shell uses this subset; a later
# ticket that needs another component adds it here and reruns the script.
DAISYUI_BASE = [
    "base/properties.css",
    "base/rootscrollgutter.css",
    "base/scrollbar.css",
    "base/rootscrolllock.css",
    "base/rootcolor.css",
    "base/reset.css",
    "base/svg.css",
]
DAISYUI_COMPONENTS = [
    "button",
    "drawer",
    "menu",
    "fieldset",
    "label",
    "input",
    "alert",
]

SOURCE_SANS_VERSION = "3.052R"
SOURCE_SANS_URL = (
    "https://github.com/adobe-fonts/source-sans/releases/download/"
    f"{SOURCE_SANS_VERSION}/WOFF2-source-sans-{SOURCE_SANS_VERSION}.zip"
)
SOURCE_SANS_SHA256 = "d7f6724027fe5ca0bab44d6121284f1fa8f66dec5f2864aa969aed347041ac95"
SOURCE_SANS_LICENSE_URL = (
    "https://raw.githubusercontent.com/adobe-fonts/source-sans/release/LICENSE.md"
)
SOURCE_SANS_FILES = {
    "WOFF2/TTF/SourceSans3-Regular.ttf.woff2": "SourceSans3-Regular.woff2",
    "WOFF2/TTF/SourceSans3-Medium.ttf.woff2": "SourceSans3-Medium.woff2",
    "WOFF2/TTF/SourceSans3-Semibold.ttf.woff2": "SourceSans3-Semibold.woff2",
}

MANIFEST = VENDOR / "manifest.json"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def download(url: str, expected_sha256: str | None) -> bytes:
    print(f"fetch {url}")
    with urllib.request.urlopen(url, timeout=120) as response:
        data = response.read()
    if expected_sha256 is not None and sha256(data) != expected_sha256:
        sys.exit(f"checksum mismatch for {url}: got {sha256(data)}")
    return data


def write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    print(f"wrote {path.relative_to(ROOT)} ({len(data)} bytes)")


def fetch_daisyui() -> dict[str, str]:
    archive = download(DAISYUI_URL, DAISYUI_SHA256)
    files: dict[str, bytes] = {}
    with tempfile.TemporaryDirectory() as scratch:
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
            tar.extractall(scratch, filter="data")
        package = Path(scratch) / "package"
        wanted = DAISYUI_BASE + [f"components/{name}.css" for name in DAISYUI_COMPONENTS]
        parts = [f"/* daisyUI {DAISYUI_VERSION}, MIT License. Assembled by fetch_assets.py */"]
        for relative in wanted:
            parts.append((package / relative).read_text(encoding="utf-8").strip())
        files["daisyui/daisyui.css"] = "\n".join(parts).encode("utf-8") + b"\n"
        files["daisyui/LICENSE"] = (package / "LICENSE").read_bytes()
    return write_all(files)


def fetch_source_sans() -> dict[str, str]:
    archive = download(SOURCE_SANS_URL, SOURCE_SANS_SHA256)
    files: dict[str, bytes] = {}
    with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
        for inside, target in SOURCE_SANS_FILES.items():
            files[f"source-sans-3/{target}"] = zipped.read(inside)
    files["source-sans-3/LICENSE.md"] = strip_trailing_whitespace(
        download(SOURCE_SANS_LICENSE_URL, None)
    )
    return write_all(files)


def strip_trailing_whitespace(text: bytes) -> bytes:
    """Trailing spaces in upstream text would fail the repository's whitespace check."""
    lines = text.decode("utf-8").splitlines()
    return ("\n".join(line.rstrip() for line in lines) + "\n").encode("utf-8")


def write_all(files: dict[str, bytes]) -> dict[str, str]:
    checksums = {}
    for relative, data in files.items():
        write(VENDOR / relative, data)
        checksums[relative] = sha256(data)
    return checksums


def check() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    failures = []
    for relative, expected in manifest["files"].items():
        path = VENDOR / relative
        if not path.exists():
            failures.append(f"missing {relative}")
        elif sha256(path.read_bytes()) != expected:
            failures.append(f"changed {relative}")
    if failures:
        sys.exit("vendor assets differ from manifest:\n  " + "\n  ".join(failures))
    print(f"vendor assets match manifest ({len(manifest['files'])} files)")


def main(argv: list[str]) -> None:
    if "--check" in argv:
        check()
        return
    checksums = {}
    checksums.update(fetch_daisyui())
    checksums.update(fetch_source_sans())
    manifest = {
        "daisyui": {"version": DAISYUI_VERSION, "sha256": DAISYUI_SHA256, "url": DAISYUI_URL},
        "source-sans-3": {
            "version": SOURCE_SANS_VERSION,
            "sha256": SOURCE_SANS_SHA256,
            "url": SOURCE_SANS_URL,
        },
        "files": dict(sorted(checksums.items())),
    }
    write(MANIFEST, json.dumps(manifest, indent=2).encode("utf-8") + b"\n")


if __name__ == "__main__":
    main(sys.argv[1:])

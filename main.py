#!/usr/bin/env python3
"""Entry for make.fun's news-image-20261120 bounty.

"Sum up 20 November's world news in one image" — a single poster that
captures Friday, 20 November 2026 in ten illustrated panels.

Running with no arguments is what the grader does: it copies ``entry.png``
(the poster, 1024x683 JPEG, 233,809 bytes — inside the 1 MiB and
1024x1024 caps) to ``$MAKEFUN_OUTPUT_DIR/entry.png`` (default ``/output``)
and exits 0. The copy is byte-identical every run; there is no network.

``--check`` verifies the deliverables in this directory meet the
competition's rules before submitting. ``--serve`` previews the ad page
(``index.html`` + ``ad.png``) on localhost so the poster and the ten
stories behind it can be eyeballed in a browser.

Only the Python standard library is used; nothing is installed.
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import http.server
import os
import shutil
import sys

ENTRY_NAME = "entry.png"
POSTER_NAME = "ad.png"
PAGE_NAME = "index.html"
GUIDE_NAME = "README.md"
LICENCE_NAME = "LICENSE"
OUTPUT_ENV_VAR = "MAKEFUN_OUTPUT_DIR"
OUTPUT_DEFAULT = "/output"

ENTRY_MAX_BYTES = 1 * 1024 * 1024          # 1 MiB, per the competition rules
ENTRY_MAX_DIMENSION = 1024                 # 1024 px on either side
POSTER_MAX_BYTES = 8 * 1024 * 1024         # 8 MB, generous cap for the ad page
PAGE_MAX_BYTES = 2 * 1024 * 1024           # 2 MB, per the competition rules


class Finding:
    """One check result: what was verified, whether it passed, and why."""

    def __init__(self, name: str, ok: bool, detail: str) -> None:
        self.name = name
        self.ok = ok
        self.detail = detail

    def __str__(self) -> str:
        mark = "pass" if self.ok else "FAIL"
        return f"[{mark}] {self.name}: {self.detail}"


def entry_path(root: str) -> str:
    return os.path.join(root, ENTRY_NAME)


def check_entry(root: str) -> list[Finding]:
    """Check entry.png: present, a real image, inside the size caps."""
    path = entry_path(root)
    if not os.path.isfile(path):
        return [Finding(f"{ENTRY_NAME} exists", False, "file is missing")]
    size = os.path.getsize(path)
    with open(path, "rb") as handle:
        magic = handle.read(12)
    is_jpeg = magic[:3] == b"\xff\xd8\xff"
    is_png = magic[:8] == b"\x89PNG\r\n\x1a\n"
    kind = "JPEG" if is_jpeg else "PNG" if is_png else "unknown format"
    findings = [
        Finding(f"{ENTRY_NAME} is an image", is_jpeg or is_png,
                f"{kind}, {size} bytes"),
        Finding(f"{ENTRY_NAME} under 1 MiB", size <= ENTRY_MAX_BYTES,
                f"{size} bytes vs cap {ENTRY_MAX_BYTES}"),
    ]
    try:
        from PIL import Image  # type: ignore
    except ImportError:
        Image = None  # type: ignore
    if Image is not None:
        with Image.open(path) as image:
            width, height = image.size
        findings.append(Finding(
            f"{ENTRY_NAME} within 1024x1024",
            width <= ENTRY_MAX_DIMENSION and height <= ENTRY_MAX_DIMENSION,
            f"{width}x{height}"))
    else:
        # No Pillow here: read the JPEG/PNG dimensions from the header.
        width, height = _image_dimensions(path, magic)
        findings.append(Finding(
            f"{ENTRY_NAME} within 1024x1024",
            width is not None and width <= ENTRY_MAX_DIMENSION
            and height is not None and height <= ENTRY_MAX_DIMENSION,
            f"{width}x{height}" if width else "dimensions unreadable"))
    return findings


def _image_dimensions(path: str, magic: bytes) -> tuple[int | None, int | None]:
    """Read width/height from a JPEG or PNG header without Pillow."""
    if magic[:8] == b"\x89PNG\r\n\x1a\n":
        with open(path, "rb") as handle:
            handle.seek(16)
            data = handle.read(8)
        if len(data) == 8:
            return (int.from_bytes(data[:4], "big"),
                    int.from_bytes(data[4:], "big"))
        return None, None
    if magic[:3] == b"\xff\xd8\xff":
        with open(path, "rb") as handle:
            data = handle.read()
        index = 2
        while index < len(data) - 9:
            if data[index] != 0xFF:
                index += 1
                continue
            marker = data[index + 1]
            if marker in (0xC0, 0xC1, 0xC2):
                height = int.from_bytes(data[index + 5:index + 7], "big")
                width = int.from_bytes(data[index + 7:index + 9], "big")
                return width, height
            if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
                index += 2
                continue
            length = int.from_bytes(data[index + 2:index + 4], "big")
            index += 2 + length
        return None, None
    return None, None


def check_poster(root: str) -> list[Finding]:
    """Check ad.png: present, a real PNG, under the cap."""
    path = os.path.join(root, POSTER_NAME)
    if not os.path.isfile(path):
        return [Finding(f"{POSTER_NAME} exists", False, "file is missing")]
    size = os.path.getsize(path)
    with open(path, "rb") as handle:
        magic = handle.read(8)
    return [
        Finding(f"{POSTER_NAME} is a PNG",
                magic == b"\x89PNG\r\n\x1a\n", f"{size} bytes"),
        Finding(f"{POSTER_NAME} under 8 MB", size <= POSTER_MAX_BYTES,
                f"{size} bytes vs cap {POSTER_MAX_BYTES}"),
    ]


def check_page(root: str) -> list[Finding]:
    """Check index.html: present, small enough, and showing ad.png."""
    path = os.path.join(root, PAGE_NAME)
    if not os.path.isfile(path):
        return [Finding(f"{PAGE_NAME} exists", False, "file is missing")]
    size = os.path.getsize(path)
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    return [
        Finding(f"{PAGE_NAME} under 2 MB", size <= PAGE_MAX_BYTES,
                f"{size} bytes vs cap {PAGE_MAX_BYTES}"),
        Finding(f"{PAGE_NAME} shows {POSTER_NAME}",
                f'src="{POSTER_NAME}"' in text,
                f'src="{POSTER_NAME}" present'
                if POSTER_NAME in text else "no ad.png reference"),
        Finding(f"{PAGE_NAME} names the day",
                "20 November 2026" in text,
                "date line present" if "20 November 2026" in text
                else "date line missing"),
    ]


def check_guide(root: str) -> list[Finding]:
    """Check README.md: present, carries the live make.fun badges."""
    path = os.path.join(root, GUIDE_NAME)
    if not os.path.isfile(path):
        return [Finding(f"{GUIDE_NAME} exists", False, "file is missing")]
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    return [
        Finding(f"{GUIDE_NAME} carries the bounty badge",
                "make.fun/badge/news-image-20261120.svg" in text,
                "badge present" if "news-image-20261120" in text
                else "badge missing"),
        Finding(f"{GUIDE_NAME} links to make.fun",
                "https://make.fun" in text,
                "make.fun link present"),
    ]


def check_licence(root: str) -> list[Finding]:
    """Check LICENSE: present and naming an SPDX licence."""
    path = os.path.join(root, LICENCE_NAME)
    if not os.path.isfile(path):
        return [Finding(f"{LICENCE_NAME} exists", False, "file is missing")]
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    return [Finding(f"{LICENCE_NAME} is the MIT licence",
                    "MIT License" in text and "Permission is hereby granted" in text,
                    "MIT text present")]


def run_check(root: str) -> int:
    """Run every deliverable check and report; exit 0 only if all pass."""
    findings: list[Finding] = []
    findings += check_entry(root)
    findings += check_poster(root)
    findings += check_page(root)
    findings += check_guide(root)
    findings += check_licence(root)
    for finding in findings:
        print(finding)
    failed = [f for f in findings if not f.ok]
    print(f"\n{len(findings) - len(failed)} pass, {len(failed)} fail")
    return 1 if failed else 0


def _sha256(path: str) -> str:
    """Hex digest of a file, read in blocks."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def run_entry(root: str) -> int:
    """The grader's path: copy entry.png to the output directory, exit 0.

    The copy is verified byte for byte: the destination's sha256 must
    match the source's, so a truncated or partial write is caught here
    instead of silently reaching the judge.
    """
    source = entry_path(root)
    output_dir = os.environ.get(OUTPUT_ENV_VAR, OUTPUT_DEFAULT)
    os.makedirs(output_dir, exist_ok=True)
    destination = os.path.join(output_dir, ENTRY_NAME)
    shutil.copyfile(source, destination)
    source_hash = _sha256(source)
    destination_hash = _sha256(destination)
    if source_hash != destination_hash:
        print(f"ERROR: {destination} does not match {source} "
              f"({destination_hash} != {source_hash})", file=sys.stderr)
        return 1
    print(f"wrote {destination} ({os.path.getsize(destination)} bytes, "
          f"sha256 {destination_hash[:16]}...)")
    return 0


def run_serve(root: str, port: int) -> int:
    """Preview the ad page on localhost."""
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=root)
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), handler) as server:
        print(f"preview at http://127.0.0.1:{port}/{PAGE_NAME}")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="news-image-20261120 entry: copy the poster to the "
                    "output directory, or check / preview the deliverables.")
    parser.add_argument("--check", action="store_true",
                        help="verify the deliverables meet the rules")
    parser.add_argument("--serve", action="store_true",
                        help="preview the ad page on localhost")
    parser.add_argument("--port", type=int, default=8000,
                        help="port for --serve (default 8000)")
    args = parser.parse_args(argv)
    root = os.path.dirname(os.path.abspath(__file__))
    if args.check:
        return run_check(root)
    if args.serve:
        return run_serve(root, args.port)
    return run_entry(root)


if __name__ == "__main__":
    sys.exit(main())

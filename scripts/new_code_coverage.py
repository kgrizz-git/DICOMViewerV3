#!/usr/bin/env python3
"""Approximate SonarQube "coverage on new code" locally.

SonarQube computes coverage on *new code* on the server: it intersects the
uploaded per-line coverage with the lines a git diff marks as new for the
project's New Code period. Neither the scanner nor SonarLint reports that
number locally, so this advisory helper reproduces it well enough to
sanity-check a branch before it is pushed and analyzed.

It reads a Cobertura ``coverage.xml`` (produced by ``pytest --cov-report=xml``)
and a ``git diff`` against a base ref, then reports the ratio of *covered*
new coverable lines to *all* new coverable lines under ``src/``. "Coverable"
means the line appears in the coverage report; blank lines, comments, and
other non-executable lines are excluded, matching SonarQube's "lines to
cover".

This is an approximation, not a replacement for the server number:

* The base ref (default ``main``) is a stand-in for the project's New Code
  period, which is ``previous_version`` on SonarQube Cloud.
* Only lines added or changed on the *new* side of the diff are considered.

The command reads only ``coverage.xml`` and git history; it never contacts
SonarQube or uploads anything.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASE_REF = "main"
DEFAULT_COVERAGE_FILE = "coverage.xml"
SOURCE_PREFIX = "src/"

_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def parse_coverage(coverage_path: Path) -> dict[str, dict[int, bool]]:
    """Map each repo-relative source file to ``{line_number: is_covered}``.

    Cobertura records filenames relative to one or more ``<source>`` roots.
    Each root is normalized to a repo-relative directory so line data keys
    match the paths ``git diff`` reports (e.g. ``src/core/foo.py``).
    """
    tree = ET.parse(coverage_path)
    root = tree.getroot()

    source_dirs: list[str] = []
    for source in root.findall("./sources/source"):
        raw = (source.text or "").strip()
        if not raw:
            continue
        try:
            rel = Path(raw).resolve().relative_to(REPO_ROOT)
            source_dirs.append(rel.as_posix())
        except ValueError:
            # A source root outside the repo cannot be mapped; skip it.
            continue
    if not source_dirs:
        source_dirs = [""]

    coverage: dict[str, dict[int, bool]] = {}
    for cls in root.iter("class"):
        filename = cls.get("filename")
        if not filename:
            continue
        rel_path = _resolve_repo_path(filename, source_dirs)
        lines = coverage.setdefault(rel_path, {})
        for line in cls.findall("./lines/line"):
            number = line.get("number")
            hits = line.get("hits")
            if number is None or hits is None:
                continue
            lineno = int(number)
            # A line can appear under multiple class entries; covered wins.
            lines[lineno] = lines.get(lineno, False) or int(hits) > 0
    return coverage


def _resolve_repo_path(filename: str, source_dirs: list[str]) -> str:
    """Join a Cobertura filename with the first source root that fits."""
    if filename.startswith(SOURCE_PREFIX):
        return filename
    for source_dir in source_dirs:
        candidate = f"{source_dir}/{filename}" if source_dir else filename
        if (REPO_ROOT / candidate).is_file():
            return candidate
    first = source_dirs[0]
    return f"{first}/{filename}" if first else filename


def changed_lines(base_ref: str) -> dict[str, set[int]]:
    """Return ``{repo_relative_path: {new_line_numbers}}`` for src/*.py.

    Uses ``git diff --unified=0`` so only added/changed lines on the new side
    of the diff are reported, keyed by their line number in the working tree.
    """
    result = subprocess.run(
        [
            "git",
            "diff",
            "--unified=0",
            "--no-color",
            base_ref,
            "--",
            "src/**/*.py",
            "src/*.py",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    changed: dict[str, set[int]] = {}
    current_file: str | None = None
    next_line = 0
    remaining = 0
    for raw in result.stdout.splitlines():
        if raw.startswith("+++ "):
            path = raw[4:].strip()
            current_file = None if path == "/dev/null" else path[2:]  # drop "b/"
            continue
        hunk = _HUNK_RE.match(raw)
        if hunk:
            next_line = int(hunk.group(1))
            remaining = int(hunk.group(2)) if hunk.group(2) is not None else 1
            continue
        if raw.startswith("+") and not raw.startswith("+++") and current_file:
            if remaining > 0:
                changed.setdefault(current_file, set()).add(next_line)
                next_line += 1
                remaining -= 1
    return changed


def compute(
    coverage: dict[str, dict[int, bool]], changed: dict[str, set[int]]
) -> tuple[int, int, dict[str, list[int]]]:
    """Return ``(covered, coverable, {file: sorted uncovered new lines})``."""
    covered_total = 0
    coverable_total = 0
    uncovered: dict[str, list[int]] = {}
    for path, lines in sorted(changed.items()):
        file_coverage = coverage.get(path, {})
        file_uncovered: list[int] = []
        for lineno in sorted(lines):
            if lineno not in file_coverage:
                continue  # not a coverable line (blank/comment/etc.)
            coverable_total += 1
            if file_coverage[lineno]:
                covered_total += 1
            else:
                file_uncovered.append(lineno)
        if file_uncovered:
            uncovered[path] = file_uncovered
    return covered_total, coverable_total, uncovered


def build_parser() -> argparse.ArgumentParser:
    """Return the command-line parser."""
    parser = argparse.ArgumentParser(
        description="Approximate SonarQube coverage on new code locally."
    )
    parser.add_argument(
        "--base",
        default=DEFAULT_BASE_REF,
        help=f"Git ref approximating the New Code period (default: {DEFAULT_BASE_REF}).",
    )
    parser.add_argument(
        "--coverage-file",
        default=DEFAULT_COVERAGE_FILE,
        help=f"Cobertura coverage XML path (default: {DEFAULT_COVERAGE_FILE}).",
    )
    parser.add_argument(
        "--fail-under",
        type=float,
        default=None,
        metavar="PCT",
        help="Exit non-zero if new-code coverage is below this percentage.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Report approximate new-code coverage; see module docstring."""
    args = build_parser().parse_args(argv)

    coverage_path = Path(args.coverage_file)
    if not coverage_path.is_absolute():
        coverage_path = REPO_ROOT / coverage_path
    if not coverage_path.is_file():
        print(  # privacy-check: allow[unsafe-print-argument] review=kgrizz-git
            f"coverage file not found: {coverage_path}\n"
            "Generate it first, e.g. "
            "PYTHONPATH=src pytest tests --cov=src --cov-report=xml:coverage.xml",
            file=sys.stderr,
        )
        return 2

    coverage = parse_coverage(coverage_path)
    changed = changed_lines(args.base)
    covered, coverable, uncovered = compute(coverage, changed)

    print(f"New-code coverage vs '{args.base}' (approximation of SonarQube new_coverage):")
    if coverable == 0:
        print("  No new coverable src/ lines detected — new-code coverage is N/A.")
        return 0

    pct = 100.0 * covered / coverable
    print(f"  Covered {covered} of {coverable} new coverable lines = {pct:.1f}%")
    if uncovered:
        print("  Uncovered new lines:")
        for path, lines in uncovered.items():
            joined = ", ".join(str(n) for n in lines)
            print(f"    {path}: {joined}")  # privacy-check: allow[unsafe-print-argument] review=kgrizz-git

    if args.fail_under is not None and pct < args.fail_under:
        print(f"  FAIL: below --fail-under {args.fail_under:.1f}%", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

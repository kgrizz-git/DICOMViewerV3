#!/usr/bin/env python3
"""
Check that the documentation ownership register is self-consistent and that
accuracy review is still happening on a cadence.

This guards the failure mode that motivated it: 15 of 23 inventory rows sat at
``Baseline`` (never assessed) for months with nothing surfacing that fact,
because the only machine-enforced documentation check was the link checker.

Three checks:

1. **Unowned Baseline rows.** Every ``DOC-*`` row in
   ``dev-docs/DOCUMENTATION_INVENTORY.md`` whose review state is ``Baseline``
   must be named by an open ``deferred`` row in
   ``dev-docs/DOCUMENTATION_TRIAGE.md``. A row that is neither assessed nor
   explicitly deferred has no owner and is the state this check exists to catch.
2. **Unbounded deferrals.** The triage ledger's own rules make a
   repository-relative follow-up mandatory for a ``deferred`` row. This verifies
   that, so a deferral cannot silently become permanent. A placeholder such as
   ``TBD`` or ``later`` is treated the same as an empty cell, since it bounds the
   deferral no better.
3. **Assessment cadence.** Reports the age of the newest
   ``dev-docs/doc-assessments/doc-assessment-*.md``.

Note on check 3: the plan asks for an assessment after each minor/major release,
but this repository currently has no Git tags, so there is no release boundary to
anchor to. Age is used as a proxy. If tagging starts, switch this to compare
against the most recent tag rather than raising the age threshold.

Usage (from repository root):
    python scripts/check_documentation_freshness.py
    python scripts/check_documentation_freshness.py --strict
    python scripts/check_documentation_freshness.py --max-age-days 60

Exit code: 0 when advisory (default), or when strict and all checks pass.
1 only under ``--strict`` with at least one finding. The default is warning-only
so it can be adopted in CI without blocking while false positives are reviewed.

Inputs: the inventory, triage ledger, and assessment filenames on disk.
Outputs: stdout findings; exit status as above.
Requirements: Python 3.9+ standard library only.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

INVENTORY_REL = "dev-docs/DOCUMENTATION_INVENTORY.md"
TRIAGE_REL = "dev-docs/DOCUMENTATION_TRIAGE.md"
ASSESSMENT_DIR_REL = "dev-docs/doc-assessments"

DOC_ID = re.compile(r"DOC-\d+")
TRIAGE_ID = re.compile(r"TRIAGE-\d+")
ASSESSMENT_DATE = re.compile(r"doc-assessment-(\d{4})-(\d{2})-(\d{2})")
DEFAULT_MAX_AGE_DAYS = 90

# A follow-up cell that is present but says nothing. These satisfy a naive
# "is the cell non-empty" test while leaving the deferral just as unbounded as an
# empty cell, so they are treated the same way.
PLACEHOLDER_FOLLOW_UPS = {
    "",
    "\u2014",
    "-",
    "--",
    "?",
    "tbd",
    "tba",
    "todo",
    "later",
    "n/a",
    "na",
    "none",
    "pending",
    "unknown",
}


def split_row(line: str) -> list[str]:
    """Cells of a Markdown table row, outer pipes stripped and cells trimmed."""
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def is_table_row(line: str) -> bool:
    """True for a Markdown table body row (not a separator such as | --- |)."""
    stripped = line.strip()
    if not stripped.startswith("|"):
        return False
    return set(stripped) - set("|- :") != set()


def inventory_states(repo_root: Path) -> dict[str, str]:
    """Map each inventory DOC id to its review-state cell (the last column)."""
    path = repo_root / INVENTORY_REL
    states: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not is_table_row(line):
            continue
        cells = split_row(line)
        if len(cells) < 2:
            continue
        match = DOC_ID.fullmatch(cells[0])
        if match:
            states[cells[0]] = cells[-1]
    return states


def deferred_rows(repo_root: Path) -> list[tuple[str, list[str], str]]:
    """Open ``deferred`` triage rows as (triage id, inventory ids, follow-up)."""
    path = repo_root / TRIAGE_REL
    rows: list[tuple[str, list[str], str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not is_table_row(line):
            continue
        cells = split_row(line)
        # id | signal | inventory ids | disposition | evidence | follow-up | reviewed
        if len(cells) < 7 or not TRIAGE_ID.fullmatch(cells[0]):
            continue
        if cells[3] != "deferred":
            continue
        rows.append((cells[0], DOC_ID.findall(cells[2]), cells[5]))
    return rows


def newest_assessment(repo_root: Path) -> tuple[str, dt.date] | None:
    """Filename and date of the most recent assessment, or None if there are none."""
    directory = repo_root / ASSESSMENT_DIR_REL
    if not directory.is_dir():
        return None
    found: list[tuple[str, dt.date]] = []
    for candidate in directory.glob("doc-assessment-*.md"):
        match = ASSESSMENT_DATE.match(candidate.name)
        if not match:
            continue
        year, month, day = (int(part) for part in match.groups())
        try:
            found.append((candidate.name, dt.date(year, month, day)))
        except ValueError:
            continue
    if not found:
        return None
    return max(found, key=lambda pair: pair[1])


def check_unowned_baseline(baseline: list[str], covered: set[str]) -> list[str]:
    """Findings for Baseline rows that no deferred triage row claims."""
    unowned = [doc for doc in baseline if doc not in covered]
    if not unowned:
        return []
    return [
        f"{len(unowned)} inventory row(s) at 'Baseline' with no open deferred "
        f"triage row: {', '.join(unowned)}. Assess the row, or add a deferred "
        f"row naming it in {TRIAGE_REL}."
    ]


def check_deferrals(deferrals: list[tuple[str, list[str], str]]) -> list[str]:
    """Findings for deferred rows that are unbounded or unlinked."""
    findings: list[str] = []
    for triage_id, docs, follow_up in deferrals:
        if follow_up.strip().rstrip(".").lower() in PLACEHOLDER_FOLLOW_UPS:
            findings.append(
                f"{triage_id} is deferred but has no follow-up (found "
                f"{follow_up or 'an empty cell'!r}). The triage ledger requires a "
                f"bounded repository-relative follow-up, not a placeholder."
            )
        if not docs:
            findings.append(
                f"{triage_id} is deferred but names no inventory ID, so nothing "
                f"links it back to the register."
            )
    return findings


def check_cadence(
    newest: tuple[str, dt.date] | None, today: dt.date, max_age_days: int
) -> tuple[list[str], str]:
    """Findings and a human-readable note for assessment age."""
    if newest is None:
        return (
            [f"No assessment found under {ASSESSMENT_DIR_REL}."],
            "none on disk",
        )
    name, date = newest
    age = (today - date).days
    note = f"{name} ({age} day(s) old)"
    if age > max_age_days:
        return (
            [
                f"Newest assessment {name} is {age} day(s) old, over the "
                f"{max_age_days}-day cadence. Run a new assessment or record "
                f"a dated waiver."
            ],
            note,
        )
    return [], note


def build_parser() -> argparse.ArgumentParser:
    """Command-line interface."""
    parser = argparse.ArgumentParser(
        description="Check documentation register consistency and review cadence."
    )
    parser.add_argument(
        "--root", default=".", help="Repository root (default: current directory)."
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero on findings. Default is warning-only.",
    )
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=DEFAULT_MAX_AGE_DAYS,
        help=f"Assessment age before it is reported (default: {DEFAULT_MAX_AGE_DAYS}).",
    )
    parser.add_argument(
        "--today",
        default=None,
        help="Override today's date as YYYY-MM-DD (for testing).",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    repo_root = Path(args.root).resolve()
    for rel in (INVENTORY_REL, TRIAGE_REL):
        if not (repo_root / rel).is_file():
            print(f"ERROR: missing required file: {rel}", file=sys.stderr)
            return 2

    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()

    states = inventory_states(repo_root)
    deferrals = deferred_rows(repo_root)
    covered: set[str] = {doc for _, docs, _ in deferrals for doc in docs}
    baseline = sorted(
        doc for doc, state in states.items() if state.startswith("Baseline")
    )

    cadence_findings, age_note = check_cadence(
        newest_assessment(repo_root), today, args.max_age_days
    )
    findings = (
        check_unowned_baseline(baseline, covered)
        + check_deferrals(deferrals)
        + cadence_findings
    )
    unowned_count = len([doc for doc in baseline if doc not in covered])

    print("Documentation freshness report:")
    print(
        f"  inventory rows: {len(states)} "
        f"({len(states) - len(baseline)} assessed, {len(baseline)} baseline)"
    )
    print(f"  baseline rows covered by a deferral: {len(baseline) - unowned_count}")
    print(f"  open deferred triage rows: {len(deferrals)}")
    print(f"  newest assessment: {age_note}")

    if not findings:
        print("OK: documentation register is self-consistent and review is current.")
        return 0

    print(f"\n{len(findings)} finding(s):")
    for finding in findings:
        print(f"  - {finding}")
    if args.strict:
        return 1
    print("\n(advisory: re-run with --strict to make these blocking)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

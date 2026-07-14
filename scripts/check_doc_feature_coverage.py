#!/usr/bin/env python3
"""
Report-only feature -> user-doc coverage gap report.

Extracts user-facing ``QAction`` labels from the source tree (the menu / action
inventory) and checks whether each cleaned label is mentioned anywhere under
``user-docs/``. Labels with no mention are reported as *candidate* documentation
gaps. This is a heuristic aid for the documentation audit, **not** a blocking
gate: the exit code is always 0 unless ``--fail-under`` is given.

Why heuristic: a menu label ("Open File(s)…") may be documented under different
wording, and trivial actions (theme names, layout glyphs) rarely warrant prose.
Treat the "uncovered" list as a worklist to review, not a hard failure set.

Usage (from repository root):
    python scripts/check_doc_feature_coverage.py
    python scripts/check_doc_feature_coverage.py --show-covered
    python scripts/check_doc_feature_coverage.py --fail-under 0.5   # CI gate (opt-in)

Exit code: 0 normally; 1 only when ``--fail-under`` is set and the covered
fraction is below the given threshold.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# First string-literal argument of a QAction(...) constructor. ``\s`` spans the
# newline so multi-line constructors (label on the following line) still match.
ACTION_PATTERN = re.compile(
    r"""QAction\(\s*(?P<q>["'])(?P<label>(?:\\.|(?!\1).)*)(?P=q)""",
    re.S,
)

TRAILING_ELLIPSIS = re.compile(r"\s*(?:\.\.\.|…)\s*$")

# Directories under src/ are scanned for QAction labels.
SOURCE_DIR = "src"
# Markdown under these folders counts as user-facing documentation.
USER_DOC_DIR = "user-docs"


def normalize_action_label(label: str) -> str:
    """Clean a raw QAction label into prose-comparable text.

    Resolves Qt mnemonics (``&&`` is a literal ampersand, a lone ``&`` is a
    mnemonic marker) and strips a trailing ellipsis (``...`` or ``…``).
    """
    # Protect literal ampersands, drop mnemonic markers, restore literals.
    label = label.replace("&&", "\x00").replace("&", "").replace("\x00", "&")
    label = TRAILING_ELLIPSIS.sub("", label)
    return label.strip()


def collect_actions(repo_root: Path) -> list[tuple[str, str, str, int]]:
    """Return (raw_label, normalized, relative_path, line_number) per QAction.

    Line numbers point at the ``QAction(`` call site.
    """
    found: list[tuple[str, str, str, int]] = []
    src = repo_root / SOURCE_DIR
    for path in sorted(src.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(repo_root).as_posix()
        for match in ACTION_PATTERN.finditer(text):
            raw = match.group("label")
            normalized = normalize_action_label(raw)
            if not normalized:
                continue
            line = text.count("\n", 0, match.start()) + 1
            found.append((raw, normalized, rel, line))
    return found


def load_user_docs_text(repo_root: Path) -> str:
    """Concatenate all user-docs markdown into one lowercased blob."""
    docs_root = repo_root / USER_DOC_DIR
    parts: list[str] = []
    if docs_root.is_dir():
        for path in sorted(docs_root.rglob("*.md")):
            parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts).lower()


def build_coverage_report(repo_root: Path, show_covered: bool = False) -> tuple[list[str], float]:
    """Build the report lines and the covered fraction of unique actions."""
    actions = collect_actions(repo_root)
    docs_text = load_user_docs_text(repo_root)

    # Deduplicate by normalized label; keep the first source location seen.
    first_seen: dict[str, tuple[str, int]] = {}
    for _raw, normalized, rel, line in actions:
        first_seen.setdefault(normalized, (rel, line))

    covered: list[str] = []
    uncovered: list[tuple[str, str, int]] = []
    for normalized, (rel, line) in sorted(first_seen.items(), key=lambda kv: kv[0].lower()):
        if normalized.lower() in docs_text:
            covered.append(normalized)
        else:
            uncovered.append((normalized, rel, line))

    total = len(first_seen)
    fraction = (len(covered) / total) if total else 1.0

    report = [
        "Doc feature-coverage report:",
        f"  QAction call sites scanned: {len(actions)}",
        f"  unique action labels: {total}",
        f"  mentioned in user-docs: {len(covered)}",
        f"  no user-docs mention: {len(uncovered)}",
        f"  coverage: {fraction * 100:.1f}%",
    ]
    if uncovered:
        report.append("  candidate gaps (label — source):")
        for normalized, rel, line in uncovered:
            report.append(f'    - "{normalized}"  ({rel}:{line})')
    if show_covered and covered:
        report.append("  covered labels:")
        for normalized in covered:
            report.append(f'    - "{normalized}"')
    return report, fraction


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Repository root",
    )
    parser.add_argument(
        "--show-covered",
        action="store_true",
        help="Also list the action labels that are mentioned in user-docs.",
    )
    parser.add_argument(
        "--fail-under",
        type=float,
        default=None,
        metavar="RATIO",
        help="Exit non-zero if covered fraction < RATIO (0-1). Opt-in gate; "
        "default is report-only (always exit 0).",
    )
    args = parser.parse_args()
    repo_root: Path = args.root.resolve()

    # Labels contain non-ASCII (×, °, —); avoid mojibake on a cp1252 console.
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]  # pyright: ignore[reportAttributeAccessIssue]
    except (AttributeError, ValueError):
        pass

    report, fraction = build_coverage_report(repo_root, show_covered=args.show_covered)
    for line in report:
        print(line)

    if args.fail_under is not None and fraction < args.fail_under:
        print(
            f"\nFAIL: coverage {fraction * 100:.1f}% < threshold "
            f"{args.fail_under * 100:.1f}%",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

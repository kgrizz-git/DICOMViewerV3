#!/usr/bin/env python3
"""
Block runtime artifacts and PHI-bearing data files from entering the repository.

The existing privacy gate (``git_hook_privacy_checks.py``) inspects *Python source*
for PII in log lines and docs. It has no concept of committed **data files**, which
is how three ``.pytest-tmp-*/dicom_viewer_config_test_signals.json`` files -- each
holding a real ``recent_files`` list with local drive paths and an identifiable
filename -- were committed in May 2026 and survived in history. A .gitignore rule
does not help: it does not untrack what is already in the index.

This checker closes that gap with two independent rules:

  1. **Path denylist.** Runtime artifacts that capture user state (pytest temp dirs,
     the app's own config JSON, generated reports) may never be tracked, wherever
     they appear.
  2. **Content scan.** Data files are searched for PHI/PII indicators: home-directory
     absolute paths, the app config's ``recent_files``/``last_path`` keys, and
     populated DICOM patient tags.

Usage:
    python scripts/check_no_phi_artifacts.py            # scan all tracked files (CI)
    python scripts/check_no_phi_artifacts.py --staged   # scan staged files (pre-commit)

Exit code: 0 clean, 1 if anything is flagged.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# --- Rule 1: paths that must never be tracked -------------------------------
# Matched with Path.match / prefix semantics against the repo-relative posix path.
FORBIDDEN_PATH_PATTERNS: list[tuple[str, str]] = [
    (r"^\.pytest-tmp", "pytest temp dir: captures live app config (recent_files)"),
    (r"^pytest-of-", "pytest temp dir"),
    (r"(^|/)\.pytest_cache/", "pytest cache"),
    (r"(^|/)dicom_viewer_config.*\.json$", "app config: contains recent_files / local paths"),
    (r"^pyright-report\.txt$", "generated type-check report (absolute local paths)"),
    (r"^backups/", "local source backups: not for version control"),
    (r"(^|/)\.DS_Store$", "macOS metadata"),
]

# --- Rule 2: PHI/PII indicators inside data files ---------------------------
DATA_SUFFIXES = {".json", ".csv", ".txt", ".log", ".yaml", ".yml", ".ini", ".cfg", ".xml"}

# Paths whose contents are exempt: synthetic fixtures, dependency manifests, CI config.
CONTENT_SCAN_EXEMPT = (
    "tests/fixtures/",
    "requirements",
    ".github/",
    "scripts/check_no_phi_artifacts.py",
    "dev-docs/architecture_boundary_baseline.txt",
)

CONTENT_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r'"(recent_files|last_path|last_export_path|last_pylinac_output_path)"'),
     "app config key that records user file paths"),
    (re.compile(r"[A-Za-z]:\\+Users\\+|[A-Za-z]:\\+To\b", re.I),
     "Windows absolute user path"),
    (re.compile(r"/(Users|home)/(?!runner\b|user\b)[A-Za-z0-9._-]+/"),
     "POSIX absolute home path"),
    (re.compile(r'"Patient(Name|ID|BirthDate)"\s*:\s*"(?!\s*")[^"]+'),
     "populated DICOM patient tag"),
]


def _run(args: list[str], root: Path) -> str:
    return subprocess.run(
        args, cwd=root, capture_output=True, text=True, check=True
    ).stdout


def tracked_files(root: Path) -> list[str]:
    return [p for p in _run(["git", "ls-files"], root).splitlines() if p]


def staged_files(root: Path) -> list[str]:
    out = _run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"], root
    )
    return [p for p in out.splitlines() if p]


def check_paths(paths: list[str]) -> list[str]:
    """Rule 1: forbidden paths, regardless of content."""
    problems = []
    for path in paths:
        for pattern, why in FORBIDDEN_PATH_PATTERNS:
            if re.search(pattern, path):
                problems.append(f"{path}: forbidden artifact ({why})")
                break
    return problems


def check_contents(paths: list[str], root: Path) -> list[str]:
    """Rule 2: PHI/PII indicators inside data files."""
    problems = []
    for path in paths:
        if any(path.startswith(x) or x in path for x in CONTENT_SCAN_EXEMPT):
            continue
        if Path(path).suffix.lower() not in DATA_SUFFIXES:
            continue
        full = root / path
        if not full.is_file():
            continue
        try:
            text = full.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            for pattern, why in CONTENT_RULES:
                if pattern.search(line):
                    problems.append(f"{path}:{lineno}: possible PHI/PII ({why})")
                    break
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged", action="store_true",
                        help="scan staged files only (pre-commit hook)")
    parser.add_argument("--root", default=None, help="repository root")
    args = parser.parse_args()

    root = Path(args.root) if args.root else Path(
        _run(["git", "rev-parse", "--show-toplevel"], Path.cwd()).strip()
    )

    paths = staged_files(root) if args.staged else tracked_files(root)
    scope = "staged" if args.staged else "tracked"

    problems = check_paths(paths) + check_contents(paths, root)

    if problems:
        print(f"BLOCKED: {len(problems)} PHI/artifact issue(s) in {scope} files:\n",
              file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        print(
            "\nThese files must not be committed. Remove them from the index:\n"
            "  git rm --cached <path>\n"
            "and confirm the path is covered by .gitignore.\n"
            "If this is a false positive, add an exemption in "
            "scripts/check_no_phi_artifacts.py.",
            file=sys.stderr,
        )
        return 1

    print(f"OK: no PHI artifacts ({len(paths)} {scope} file(s) scanned)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

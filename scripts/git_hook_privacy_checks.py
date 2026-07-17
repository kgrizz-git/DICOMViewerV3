#!/usr/bin/env python3
"""Privacy-safe static output checks for staged changes or the full tree.

The no-argument CLI remains staged-mode compatible with the local Git hooks.
Findings deliberately contain only repository-relative path, line, and rule.
"""

from __future__ import annotations

import argparse
import os
import subprocess  # noqa: F401  # pyright: ignore[reportUnusedImport]  # Compatibility API.
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.privacy_checks import (
    Violation,
    check_absolute_path_in_doc_line,
    check_dialog_raw_exception,
    check_path_literal_in_logger_line,
    check_patient_fields_in_log_line,
    check_python_ast,
    check_traceback_print_exc,
    critical_violations,
    format_violations,
    git_diff_cached,
    git_show_staged,
    parse_added_line_numbers,
    patient_fields,
    reset_patient_fields_cache,
    staged_absolute_path_check_paths,
    staged_doc_like_paths,
    staged_python_scan_paths,
)
from scripts.privacy_checks.git_paths import repo_root
from scripts.privacy_checks.scanner import (
    check_staged_doc_file,
    check_staged_python_file,
    scan_all,
    scan_staged,
)

__all__ = [
    "Violation",
    "check_absolute_path_in_doc_line",
    "check_dialog_raw_exception",
    "check_logger_sanitize_ast",
    "check_path_literal_in_logger_line",
    "check_patient_fields_in_log_line",
    "check_python_ast",
    "check_staged_doc_file",
    "check_staged_file",
    "check_traceback_print_exc",
    "critical_violations",
    "format_violations",
    "git_diff_cached",
    "git_show_staged",
    "main",
    "parse_added_line_numbers",
    "patient_fields",
    "reset_patient_fields_cache",
    "staged_absolute_path_check_paths",
    "staged_doc_like_paths",
    "staged_python_src_paths",
]

# Compatibility aliases imported by existing hook tests and integrations.
staged_python_src_paths = staged_python_scan_paths
check_staged_file = check_staged_python_file


def check_logger_sanitize_ast(
    relpath: str, source: str, added_lines: set[int]
) -> list[Violation]:
    """Compatibility wrapper for the former logger-only AST function."""

    return [
        Violation("logger-needs-sanitize", violation.path, violation.line)
        for violation in check_python_ast(relpath, source, added_lines)
        if violation.rule == "unsafe-logger-argument"
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Privacy-safe Python output checks (staged by default)"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--staged", action="store_true", help="scan staged added lines (default)"
    )
    mode.add_argument(
        "--all", action="store_true", help="scan all covered Python files"
    )
    parser.add_argument(
        "--critical",
        action="store_true",
        help="report only blocking raw exception/dialog/logger/stream categories",
    )
    args = parser.parse_args(argv)

    root = repo_root()
    violations = scan_all(root) if args.all else scan_staged(root)
    if args.critical:
        violations = critical_violations(violations)
    if not violations:
        return 0

    warn_only = os.environ.get("DICOMVIEWER_PRIVACY_HOOK", "").strip().lower() in {
        "warn",
        "warning",
        "1-soft",
    }
    status = "WARN" if warn_only else "FAIL"
    print(
        f"[privacy hook] {status} ({len(violations)} issue(s)):\n"
        f"{format_violations(violations)}",
        file=sys.stderr,
    )
    return 0 if warn_only else 1


if __name__ == "__main__":
    raise SystemExit(main())

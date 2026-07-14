#!/usr/bin/env python3
"""Run basedpyright and fail only when it reports type errors.

basedpyright exits non-zero for warnings, but this repository currently gates on
zero errors while allowing warnings. This script mirrors the CI policy and is
safe to use from local git hooks.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

CHECKED_PATHS = ("src", "scripts")
BASEDPYRIGHT_COMMAND = (
    "-m",
    "basedpyright",
    "--outputjson",
    "src",
    "scripts",
)


def _format_error(diag: dict[str, Any]) -> str:
    start = diag.get("range", {}).get("start", {})
    file_path = diag.get("file", "")
    line = int(start.get("line", 0)) + 1
    rule = diag.get("rule", "unknown")
    message = (diag.get("message", "") or "").splitlines()[0]
    return f"::error file={file_path},line={line}::[{rule}] {message}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run basedpyright and fail when summary.errorCount is non-zero."
    )
    parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    proc = subprocess.run(
        [sys.executable, *BASEDPYRIGHT_COMMAND],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    try:
        report = json.loads(proc.stdout)
    except json.JSONDecodeError:
        print("[pyright] Could not parse basedpyright JSON output.", file=sys.stderr)
        if proc.stderr:
            print(proc.stderr, file=sys.stderr, end="" if proc.stderr.endswith("\n") else "\n")
        if proc.stdout:
            print(proc.stdout, file=sys.stderr, end="" if proc.stdout.endswith("\n") else "\n")
        return proc.returncode or 1

    summary = report.get("summary", {})
    errors = int(summary.get("errorCount", 0))
    warnings = int(summary.get("warningCount", 0))
    print(f"basedpyright: {errors} error(s), {warnings} warning(s) across {' + '.join(CHECKED_PATHS)}")

    if errors:
        for diag in report.get("generalDiagnostics", []):
            if diag.get("severity") == "error":
                print(_format_error(diag))

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

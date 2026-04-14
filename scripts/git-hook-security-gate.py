#!/usr/bin/env python3
"""Git hook security gate for main branch operations.

This script is shared by pre-commit and pre-push hooks.
It runs the local security scan suite only when:
- committing directly on branch `main`
- pushing updates to `refs/heads/main` (covers FF merge pushes)
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def run_git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def repo_root() -> Path:
    return Path(run_git("rev-parse", "--show-toplevel"))


def project_python(root: Path) -> Path | None:
    candidates = [
        root / ".venv" / "Scripts" / "python.exe",
        root / ".venv" / "bin" / "python",
        root / "venv" / "Scripts" / "python.exe",
        root / "venv" / "bin" / "python",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def should_scan_pre_commit() -> bool:
    branch = run_git("branch", "--show-current")
    return branch == "main"


def should_scan_pre_push(stdin_data: str) -> bool:
    for line in stdin_data.splitlines():
        parts = line.strip().split()
        if len(parts) >= 4 and parts[2] == "refs/heads/main":
            return True
    return False


def run_scan(root: Path, python_bin: Path) -> int:
    scan_script = root / "scripts" / "run_security_scan.py"
    proc = subprocess.run(
        [str(python_bin), str(scan_script), "--all", "--report"],
        text=True,
    )
    return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hook-type", choices=["pre-commit", "pre-push"], required=True)
    args = parser.parse_args()

    root = repo_root()
    should_scan = False
    if args.hook_type == "pre-commit":
        should_scan = should_scan_pre_commit()
    else:
        should_scan = should_scan_pre_push(sys.stdin.read())

    if not should_scan:
        return 0

    py = project_python(root)
    if py is None:
        print("[security hook] No project Python found under .venv or venv.", file=sys.stderr)
        return 1

    print("[security hook] Running full local security scan...")
    exit_code = run_scan(root, py)
    if exit_code != 0:
        print("[security hook] Security scan failed. Blocking git operation.", file=sys.stderr)
        return exit_code
    print("[security hook] Security scan passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Git hook security gate for main branch operations.

This script is shared by pre-commit and pre-push hooks.
It runs the local security scan suite only when:
- committing directly on branch `main`
- pushing updates to `refs/heads/main` (covers FF merge pushes)

Pre-commit uses a **light** scan (`run_security_scan.py --pre-commit`: debug flags +
detect-secrets on staged files). Pre-push uses the **full** suite (`--all`).
Set ``DICOMVIEWER_PRECOMMIT_FULL_SECURITY_SCAN=1`` to run the full suite on
pre-commit as well.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def run_git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
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


def _pre_commit_wants_full_scan() -> bool:
    val = os.environ.get("DICOMVIEWER_PRECOMMIT_FULL_SECURITY_SCAN", "").strip().lower()
    return val in ("1", "true", "yes", "on")


def run_scan(root: Path, python_bin: Path, *, hook_type: str) -> int:
    scan_script = root / "scripts" / "run_security_scan.py"
    if hook_type == "pre-commit" and not _pre_commit_wants_full_scan():
        args = [str(python_bin), str(scan_script), "--pre-commit", "--report"]
        label = "light pre-commit security scan (debug flags + detect-secrets on staged files)"
    else:
        args = [str(python_bin), str(scan_script), "--all", "--report"]
        label = "full local security scan"
    print(f"[security hook] Running {label}...")
    proc = subprocess.run(args, text=True, cwd=str(root), encoding="utf-8")
    return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hook-type", choices=["pre-commit", "pre-push"], required=True)
    args = parser.parse_args()

    root = repo_root()
    py = project_python(root)
    if py is None:
        print("[security hook] No project Python found under .venv or venv.", file=sys.stderr)
        return 1

    # Privacy / logging checks on staged src/*.py — all branches, fast.
    privacy_script = root / "scripts" / "git_hook_privacy_checks.py"
    proc_priv = subprocess.run(
        [str(py), str(privacy_script)],
        cwd=str(root),
        text=True,
        encoding="utf-8",
    )
    if proc_priv.returncode != 0:
        return proc_priv.returncode

    should_scan = False
    if args.hook_type == "pre-commit":
        should_scan = should_scan_pre_commit()
    else:
        should_scan = should_scan_pre_push(sys.stdin.read())

    if not should_scan:
        return 0

    exit_code = run_scan(root, py, hook_type=args.hook_type)
    if exit_code != 0:
        print("[security hook] Security scan failed. Blocking git operation.", file=sys.stderr)
        return exit_code
    print("[security hook] Security scan passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

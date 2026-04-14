#!/usr/bin/env python3
"""Git hook helper: remove stale files under ``backups/`` by modification time.

This script supports the local ``pre-commit`` hook. It deletes **files** under
the repository ``backups/`` directory whose **mtime** is strictly older than a
cutoff of **now minus N days** (local time), then removes **empty directories**
inside ``backups/`` (deepest first). The repository root is discovered via
``git rev-parse --show-toplevel``.

The hook then runs ``git add -u -- backups`` so **tracked** paths removed from
disk are staged and recorded in the same commit (untracked files are unchanged).

Inputs (CLI):
    ``--days`` — positive integer: keep files touched within this many days;
    anything strictly older is removed. If ``--days`` is less than 1, the
    script exits successfully without doing work.
    ``--dry-run`` — list paths that would be removed (no deletes).

Outputs:
    Deletes matching files; prints a short summary to stderr when files are
    removed. Missing ``backups/`` is a no-op (exit 0).

Requirements:
    ``git`` on PATH; standard library only. Intended to run with the same
    project interpreter as ``git-hook-security-gate.py`` (``.venv`` / ``venv``).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path


def _repo_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(result.stdout.strip()).resolve()


def _prune_backups(backups_dir: Path, *, days: int, dry_run: bool) -> int:
    """Return number of files deleted (or that would be deleted if dry_run)."""
    if days < 1 or not backups_dir.is_dir():
        return 0

    cutoff = datetime.now() - timedelta(days=days)
    removed = 0

    # Delete old files (files only; walk bottom-up for dirs later)
    for path in sorted(backups_dir.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if not path.is_file():
            continue
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
        except OSError:
            continue
        if mtime >= cutoff:
            continue
        if dry_run:
            print(f"[backup hook] dry-run would remove: {path}", file=sys.stderr)
            removed += 1
            continue
        try:
            path.unlink()
            removed += 1
        except OSError as exc:
            print(f"[backup hook] skip delete {path}: {exc}", file=sys.stderr)

    if dry_run:
        return removed

    # Remove empty directories under backups (not the root itself)
    dirs = [p for p in backups_dir.rglob("*") if p.is_dir()]
    for d in sorted(dirs, key=lambda p: len(p.parts), reverse=True):
        try:
            if not any(d.iterdir()):
                d.rmdir()
        except OSError:
            pass

    return removed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--days",
        type=int,
        required=True,
        help="Delete files under backups/ strictly older than this many days.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print paths that would be removed; do not delete.",
    )
    args = parser.parse_args()

    try:
        root = _repo_root()
    except (subprocess.CalledProcessError, OSError) as exc:
        print(f"[backup hook] could not resolve repo root: {exc}", file=sys.stderr)
        return 1

    backups = root / "backups"
    try:
        n = _prune_backups(backups, days=args.days, dry_run=args.dry_run)
    except OSError as exc:
        print(f"[backup hook] prune failed: {exc}", file=sys.stderr)
        return 1

    if n:
        verb = "Would remove" if args.dry_run else "Removed"
        print(f"[backup hook] {verb} {n} file(s) under backups/ (>{args.days} day(s) old).", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

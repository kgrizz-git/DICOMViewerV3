#!/usr/bin/env python3
"""Git hook helper: remove stale files under ``backups/`` by backup *intent* age.

This script supports the local ``pre-commit`` hook. Age is **not** raw filesystem
mtime (checkout/restore refreshes mtime). Instead:

- **Tracked** paths under ``backups/`` (as reported by ``git ls-files``): use the
  **committer timestamp of the latest Git commit that touched that path** (one
  ``git log`` over ``backups/``). If a path does not appear in history (e.g. new
  and not yet committed), **mtime** is used as a fallback.
- **Untracked** files: use the **newest valid ``YYYYMMDD``** substring found anywhere
  in the path string (relative to repo, POSIX slashes); if none, use **mtime**.
  For each candidate, ``max(embedded dates, mtime)`` is used so a recent checkout
  does not immediately delete an obviously old backup named with an old date.

Anything strictly older than **now minus N days** (local time) is removed; then
empty directories under ``backups/`` are removed (deepest first).

**Shallow clones** (``--depth``) may lack full history; Git-derived ages can be
newer than the true first introduction of a file.

The hook then runs ``git add -u -- backups`` so **tracked** paths removed from
disk are staged for the same commit (see ``.githooks/pre-commit``).

Inputs (CLI):
    ``--days`` — positive integer: keep backups whose intent-age is within this
    many days; anything strictly older is removed. If ``--days`` is less than 1,
    the script exits successfully without doing work.
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
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Eight-digit calendar dates 19xx / 20xx embedded in paths or filenames.
_YYYYMMDD = re.compile(r"(?:19|20)\d{6}")


def newest_embedded_yyyymmdd_datetime(text: str, *, now: datetime | None = None) -> datetime | None:
    """Return the newest valid calendar date (midnight local) from all YYYYMMDD matches in *text*."""
    now = now or datetime.now()
    best: datetime | None = None
    for m in _YYYYMMDD.finditer(text):
        raw = m.group(0)
        try:
            dt = datetime.strptime(raw, "%Y%m%d")
        except ValueError:
            continue
        if dt > now:
            continue
        if best is None or dt > best:
            best = dt
    return best


def git_log_latest_commit_datetimes(repo_root: Path) -> dict[str, datetime]:
    """Map ``backups/...`` path (POSIX, relative to repo) -> latest commit time.

    ``git log`` is newest-first; the first time we see a path is its latest
    touching commit.
    """
    proc = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "log",
            "--format=%ct",
            "--name-only",
            "--",
            "backups/",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        return {}
    latest: dict[str, datetime] = {}
    current_ts: int | None = None
    for line in proc.stdout.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.isdigit() and len(s) >= 9:
            current_ts = int(s)
            continue
        if current_ts is None:
            continue
        norm = s.replace("\\", "/")
        if norm not in latest:
            latest[norm] = datetime.fromtimestamp(current_ts)
    return latest


def git_tracked_backup_paths(repo_root: Path) -> set[str]:
    """POSIX paths (relative to repo) tracked under ``backups/``."""
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "-z", "--", "backups/"],
        check=False,
        capture_output=True,
    )
    if proc.returncode != 0:
        return set()
    out: set[str] = set()
    for chunk in proc.stdout.split(b"\0"):
        if not chunk:
            continue
        out.add(chunk.decode("utf-8", errors="replace").replace("\\", "/"))
    return out


def _mtime_datetime(path: Path) -> datetime | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime)
    except OSError:
        return None


def backup_intent_datetime(
    path: Path,
    *,
    rel_posix: str,
    tracked: bool,
    git_latest: dict[str, datetime],
    now: datetime | None = None,
) -> datetime | None:
    """Single instant used to decide whether *path* is older than the cutoff.

    *now* is optional for tests (embedded dates are not allowed past *now*).
    """
    now = now or datetime.now()
    mt = _mtime_datetime(path)
    if tracked:
        if rel_posix in git_latest:
            return git_latest[rel_posix]
        return mt
    embedded = newest_embedded_yyyymmdd_datetime(rel_posix, now=now)
    if embedded is None:
        return mt
    if mt is None:
        return embedded
    return embedded if embedded > mt else mt


def _repo_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(result.stdout.strip()).resolve()


def _prune_backups(
    repo_root: Path,
    backups_dir: Path,
    *,
    days: int,
    dry_run: bool,
) -> int:
    """Return number of files deleted (or that would be deleted if dry_run)."""
    if days < 1 or not backups_dir.is_dir():
        return 0

    cutoff = datetime.now() - timedelta(days=days)
    tracked = git_tracked_backup_paths(repo_root)
    git_latest = git_log_latest_commit_datetimes(repo_root)
    removed = 0
    repo_resolved = repo_root.resolve()

    for path in sorted(backups_dir.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if not path.is_file():
            continue
        try:
            rel = path.resolve().relative_to(repo_resolved).as_posix()
        except ValueError:
            continue
        if not rel.startswith("backups/") and rel != "backups":
            continue
        is_tracked = rel in tracked
        intent = backup_intent_datetime(
            path,
            rel_posix=rel,
            tracked=is_tracked,
            git_latest=git_latest,
        )
        if intent is None:
            continue
        if intent >= cutoff:
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

    dirs = [p for p in backups_dir.rglob("*") if p.is_dir()]
    for d in sorted(dirs, key=lambda p: len(p.parts), reverse=True):
        try:
            if not any(d.iterdir()):
                d.rmdir()
        except OSError:
            pass

    return removed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prune backups/ by Git commit time (tracked) or embedded dates / mtime (untracked).",
    )
    parser.add_argument(
        "--days",
        type=int,
        required=True,
        help="Delete backups whose intent-age is strictly older than this many days.",
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
        n = _prune_backups(root, backups, days=args.days, dry_run=args.dry_run)
    except OSError as exc:
        print(f"[backup hook] prune failed: {exc}", file=sys.stderr)
        return 1

    if n:
        verb = "Would remove" if args.dry_run else "Removed"
        print(
            f"[backup hook] {verb} {n} file(s) under backups/ "
            f"(intent age strictly older than {args.days} day(s)).",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

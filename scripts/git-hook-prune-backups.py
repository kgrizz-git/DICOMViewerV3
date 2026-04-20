#!/usr/bin/env python3
"""Git hook helper: remove stale files under ``backups/`` by backup *intent* age.

This script supports the local ``pre-commit`` hook. Age is **not** raw filesystem
mtime (checkout/restore refreshes mtime). Instead:

- **Tracked** paths under ``backups/`` (as reported by ``git ls-files``):
  A file is removed if **either**:

  1. **Commit depth:** more than ``--max-commits`` commits have landed on **HEAD**
     since the **latest commit that touched that path** (``git rev-list
     <touch_hash>..HEAD``), or
  2. **Busy-branch time cutoff:** the branch had **more than** ``--velocity-commits``
     commits in the last ``--days`` days **and** the path's intent instant
     (committer time of that latest touch, or mtime fallback) is **strictly
     older** than ``now - days``.

  If the branch is quiet (commit count in the window ≤ ``--velocity-commits``),
  rule (2) does not apply—only rule (1) can remove tracked backups by age.

- **Untracked** files: use the **newest valid ``YYYYMMDD``** substring found anywhere
  in the path string (relative to repo, POSIX slashes); if none, use **mtime**.
  When both exist, use the **older** of the two instants — ``min(embedded date,
  mtime)``. Removed when that intent is **strictly older** than ``now - days``
  (same as before; no commit-based rule).

**Shallow clones** (``--depth``) may lack full history; Git-derived ages and
counts can be wrong.

The hook then runs ``git add -u -- backups`` so **tracked** paths removed from
disk are staged for the same commit (see ``.githooks/pre-commit``).

Inputs (CLI):
    ``--days`` — calendar window for untracked pruning and for tracked rule (2);
        must be ≥ 1 or the script exits without work.
    ``--max-commits`` — tracked rule (1); if < 1, commit-depth pruning is disabled.
    ``--velocity-commits`` — optional; defaults to ``--max-commits``. Branch
        commit count in the last ``--days`` must exceed this to enable rule (2).
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
# Full hash + Unix committer time from ``git log --format=%H %ct``.
_COMMIT_LINE = re.compile(r"^([0-9a-f]{40}) (\d+)$")


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


def git_log_latest_touch_per_path(repo_root: Path) -> dict[str, tuple[str, datetime]]:
    """Map ``backups/...`` path (POSIX) -> (commit_hash, committer time).

    ``git log`` is newest-first; the first time we see a path is its latest
    touching commit.
    """
    proc = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "log",
            "--format=%H %ct",
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
    latest: dict[str, tuple[str, datetime]] = {}
    current_hash: str | None = None
    current_ts: int | None = None
    for line in proc.stdout.splitlines():
        s = line.strip()
        if not s:
            continue
        m = _COMMIT_LINE.match(s)
        if m:
            current_hash, current_ts = m.group(1), int(m.group(2))
            continue
        if current_hash is None or current_ts is None:
            continue
        norm = s.replace("\\", "/")
        if norm not in latest:
            latest[norm] = (current_hash, datetime.fromtimestamp(current_ts))
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


def git_commit_count_in_last_days(repo_root: Path, *, days: int, now: datetime | None = None) -> int:
    """Number of commits reachable from HEAD with committer date after ``now - days``."""
    now = now or datetime.now()
    since = now - timedelta(days=days)
    since_s = since.strftime("%Y-%m-%d %H:%M:%S")
    proc = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "rev-list",
            "--count",
            "--since",
            since_s,
            "HEAD",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        return 0
    try:
        return max(0, int(proc.stdout.strip()))
    except ValueError:
        return 0


def commits_on_branch_after(repo_root: Path, commit_hash: str) -> int | None:
    """Count commits reachable from HEAD but not from *commit_hash* (exclusive of *commit_hash*)."""
    proc = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "rev-list",
            "--count",
            f"{commit_hash}..HEAD",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        return None
    try:
        return max(0, int(proc.stdout.strip()))
    except ValueError:
        return None


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
    git_touch: dict[str, tuple[str, datetime]],
    now: datetime | None = None,
) -> datetime | None:
    """Single instant used for time comparisons and untracked day cutoff.

    *now* is optional for tests (embedded dates are not allowed past *now*).
    """
    now = now or datetime.now()
    mt = _mtime_datetime(path)
    if tracked:
        if rel_posix in git_touch:
            return git_touch[rel_posix][1]
        return mt
    embedded = newest_embedded_yyyymmdd_datetime(rel_posix, now=now)
    if embedded is None:
        return mt
    if mt is None:
        return embedded
    # Older instant = more conservative pruning (do not let the newer signal hide staleness).
    return embedded if embedded < mt else mt


def tracked_should_prune(
    *,
    commits_since_touch: int | None,
    intent: datetime | None,
    cutoff: datetime,
    commits_in_window: int,
    max_commits: int,
    velocity_threshold: int,
) -> bool:
    """Whether a **tracked** backup should be removed (pure logic for tests)."""
    # Require a positive threshold so ``0`` does not mean "always busy" when aligned with --max-commits 0.
    high_velocity = velocity_threshold > 0 and commits_in_window > velocity_threshold
    too_old_by_time = high_velocity and intent is not None and intent < cutoff

    if commits_since_touch is None:
        # No known touch commit: fall back to classic days-only retention.
        return intent is not None and intent < cutoff

    if max_commits < 1:
        return too_old_by_time

    too_old_by_commits = commits_since_touch > max_commits
    return too_old_by_commits or too_old_by_time


def _prune_backups(
    repo_root: Path,
    backups_dir: Path,
    *,
    days: int,
    max_commits: int,
    velocity_threshold: int,
    dry_run: bool,
    now: datetime | None = None,
) -> int:
    """Return number of files deleted (or that would be deleted if dry_run)."""
    if days < 1 or not backups_dir.is_dir():
        return 0

    now = now or datetime.now()
    cutoff = now - timedelta(days=days)
    tracked = git_tracked_backup_paths(repo_root)
    git_touch = git_log_latest_touch_per_path(repo_root)
    commits_in_window = git_commit_count_in_last_days(repo_root, days=days, now=now)
    rev_cache: dict[str, int | None] = {}
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
            git_touch=git_touch,
            now=now,
        )

        if is_tracked:
            touch_hash: str | None = None
            if rel in git_touch:
                touch_hash = git_touch[rel][0]
            commits_since: int | None = None
            if touch_hash:
                if touch_hash not in rev_cache:
                    rev_cache[touch_hash] = commits_on_branch_after(repo_root, touch_hash)
                commits_since = rev_cache[touch_hash]
            prune = tracked_should_prune(
                commits_since_touch=commits_since,
                intent=intent,
                cutoff=cutoff,
                commits_in_window=commits_in_window,
                max_commits=max_commits,
                velocity_threshold=velocity_threshold,
            )
        else:
            if intent is None:
                continue
            prune = intent < cutoff

        if not prune:
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


def _repo_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(result.stdout.strip()).resolve()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Prune backups/: tracked = max-commits depth and optional busy-branch "
            "time cutoff; untracked = min(embedded date, mtime) vs --days."
        ),
    )
    parser.add_argument(
        "--days",
        type=int,
        required=True,
        help="Untracked cutoff age; window for counting branch velocity; tracked time cutoff when busy.",
    )
    parser.add_argument(
        "--max-commits",
        type=int,
        default=10,
        help="Remove tracked backup if more than this many commits since last touch (<1 disables).",
    )
    parser.add_argument(
        "--velocity-commits",
        type=int,
        default=None,
        help="If branch had more than this many commits in the last --days, apply time cutoff to tracked "
        "files too. Defaults to --max-commits.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print paths that would be removed; do not delete.",
    )
    args = parser.parse_args()

    vel = args.velocity_commits if args.velocity_commits is not None else args.max_commits

    try:
        root = _repo_root()
    except (subprocess.CalledProcessError, OSError) as exc:
        print(f"[backup hook] could not resolve repo root: {exc}", file=sys.stderr)
        return 1

    backups = root / "backups"
    try:
        n = _prune_backups(
            root,
            backups,
            days=args.days,
            max_commits=args.max_commits,
            velocity_threshold=vel,
            dry_run=args.dry_run,
        )
    except OSError as exc:
        print(f"[backup hook] prune failed: {exc}", file=sys.stderr)
        return 1

    if n:
        verb = "Would remove" if args.dry_run else "Removed"
        print(
            f"[backup hook] {verb} {n} file(s) under backups/ "
            f"(tracked: >{args.max_commits} commits since touch and/or "
            f"time cutoff when branch had >{vel} commit(s) in last {args.days} day(s); "
            f"untracked: older than {args.days} day(s) by intent).",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

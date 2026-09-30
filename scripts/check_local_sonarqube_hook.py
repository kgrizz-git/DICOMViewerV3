"""Check local SonarQube scan revision for advisory commits and pushed refs."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

if __package__:
    from scripts.run_local_sonarqube import (
        DEFAULT_MAX_COMMITS_BEHIND,
        DEFAULT_PROJECT_KEY,
        commits_behind,
        read_last_submission,
    )
else:
    from run_local_sonarqube import (
        DEFAULT_MAX_COMMITS_BEHIND,
        DEFAULT_PROJECT_KEY,
        commits_behind,
        read_last_submission,
    )

REPO_ROOT = Path(__file__).resolve().parents[1]
SCAN_COMMAND = "python scripts/run_local_sonarqube.py --with-coverage"
REPORT_COMMAND = "python scripts/report_local_sonarqube_issues.py --fail-on-findings"
HEAD_REVISION = '"$(git rev-parse HEAD)"'


def recorded_revision(repo_root: Path) -> str | None:
    """Return the last submitted Git revision, if the local record has one."""
    record = read_last_submission(repo_root)
    if not record or record.get("project_key") != DEFAULT_PROJECT_KEY:
        return None
    revision = record.get("revision")
    return revision if isinstance(revision, str) and revision else None


def commit_for_ref(repo_root: Path, object_id: str) -> str | None:
    """Peel an update's object ID to a commit without using shell evaluation."""
    result = subprocess.run(
        ["git", "rev-parse", "--verify", f"{object_id}^{{commit}}"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def advise_before_commit(repo_root: Path) -> int:
    """Suggest a scan when missing, unrelated to HEAD, or over five commits old."""
    revision = recorded_revision(repo_root)
    if revision is None:
        print(f"[sonarqube advisory] No valid local scan. Run {SCAN_COMMAND} and review issues.")
        return 0
    behind = commits_behind(repo_root, revision)
    if behind is None:
        print(f"[sonarqube advisory] Scan revision cannot be compared with HEAD. Run {SCAN_COMMAND} and review issues.")
    elif behind > DEFAULT_MAX_COMMITS_BEHIND:
        print(
            f"[sonarqube advisory] Local scan is {behind} commits behind HEAD. "
            f"Run {SCAN_COMMAND}, then {REPORT_COMMAND} --expected-revision {HEAD_REVISION} "
            "and review new issues."
        )
    return 0


def check_push_updates(repo_root: Path, updates: str) -> int:
    """Require each pushed ref tip to match this checkout's last scan exactly."""
    revision = recorded_revision(repo_root)
    for line in updates.splitlines():
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != 4:
            print("[sonarqube] Invalid pre-push ref update; push blocked.", file=sys.stderr)
            return 1
        local_ref, object_id, _, _ = parts
        if object_id in {"0" * 40, "0" * 64}:  # A deletion adds no commits.
            continue
        if revision is None:
            print(
                f"[sonarqube] No valid {DEFAULT_PROJECT_KEY} local scan record; "
                f"{local_ref} push blocked. Run {SCAN_COMMAND}, then {REPORT_COMMAND} "
                f"--expected-revision {HEAD_REVISION}.",
                file=sys.stderr,
            )
            return 1
        commit = commit_for_ref(repo_root, object_id)
        if commit is None:
            print(
                f"[sonarqube] Cannot resolve {local_ref} to a commit; push blocked. "
                "Check the local ref and Git object ID.",
                file=sys.stderr,
            )
            return 1
        if revision != commit:
            print(
                f"[sonarqube] {local_ref} has no matching local scan; push blocked. "
                f"Run {SCAN_COMMAND}, then {REPORT_COMMAND} --expected-revision {commit} "
                "and review new issues.",
                file=sys.stderr,
            )
            return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--pre-commit", action="store_true")
    mode.add_argument("--pre-push", action="store_true")
    args = parser.parse_args()
    if args.pre_commit:
        return advise_before_commit(REPO_ROOT)
    return check_push_updates(REPO_ROOT, sys.stdin.read())


if __name__ == "__main__":
    raise SystemExit(main())

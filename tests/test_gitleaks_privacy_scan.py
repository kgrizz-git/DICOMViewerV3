"""Tests for content-bound Gitleaks false-positive review and history scoping."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts import gitleaks_privacy_scan as scan


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=True
    ).stdout.strip()


def test_blob_review_survives_commit_identity_change(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.name", "Synthetic")
    _git(tmp_path, "config", "user.email", "synthetic@users.noreply.github.com")
    target = tmp_path / "reviewed.txt"
    target.write_text("synthetic-digest\n", encoding="utf-8")
    _git(tmp_path, "add", "reviewed.txt")
    _git(tmp_path, "commit", "-q", "-m", "first")
    first_commit = _git(tmp_path, "rev-parse", "HEAD")
    blob_oid = _git(tmp_path, "rev-parse", "HEAD:reviewed.txt")
    finding = {
        "Commit": first_commit,
        "File": "reviewed.txt",
        "RuleID": "synthetic-rule",
        "StartLine": 1,
    }

    assert scan.finding_blob_key(tmp_path, finding, "history") == (
        blob_oid,
        "reviewed.txt",
        "synthetic-rule",
        1,
    )

    _git(tmp_path, "commit", "--allow-empty", "-q", "-m", "identity changes")
    later_key = scan.finding_blob_key(tmp_path, finding, "history")
    assert later_key is not None
    assert later_key[0] == blob_oid


def test_loads_reviewed_blob_manifest(tmp_path: Path) -> None:
    manifest = tmp_path / scan.APPROVAL_MANIFEST
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "reviewed": [],
                "reviewed_blobs": [
                    {
                        "blob_oid": "a" * 40,
                        "path": "synthetic.txt",
                        "rule_id": "synthetic-rule",
                        "start_line": 2,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    approvals = scan.load_approvals(tmp_path)

    assert approvals.blobs == frozenset(
        {("a" * 40, "synthetic.txt", "synthetic-rule", 2)}
    )


def test_history_log_opts_since_main_uses_main_branch(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.name", "Synthetic")
    _git(tmp_path, "config", "user.email", "synthetic@users.noreply.github.com")
    (tmp_path / "a.txt").write_text("a\n", encoding="utf-8")
    _git(tmp_path, "add", "a.txt")
    _git(tmp_path, "commit", "-q", "-m", "main tip")
    _git(tmp_path, "checkout", "-q", "-b", "feature")
    (tmp_path / "b.txt").write_text("b\n", encoding="utf-8")
    _git(tmp_path, "add", "b.txt")
    _git(tmp_path, "commit", "-q", "-m", "feature tip")

    opts = scan.history_log_opts_since_main(tmp_path)
    assert opts.endswith("..HEAD")
    assert "main" in opts


def test_history_log_opts_for_pre_push_existing_remote_tip(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.name", "Synthetic")
    _git(tmp_path, "config", "user.email", "synthetic@users.noreply.github.com")
    (tmp_path / "a.txt").write_text("a\n", encoding="utf-8")
    _git(tmp_path, "add", "a.txt")
    _git(tmp_path, "commit", "-q", "-m", "one")
    old = _git(tmp_path, "rev-parse", "HEAD")
    (tmp_path / "b.txt").write_text("b\n", encoding="utf-8")
    _git(tmp_path, "add", "b.txt")
    _git(tmp_path, "commit", "-q", "-m", "two")
    new = _git(tmp_path, "rev-parse", "HEAD")

    stdin = f"refs/heads/main {new} refs/heads/main {old}\n"
    assert scan.history_log_opts_for_pre_push(tmp_path, stdin) == f"{old}..{new}"


def test_history_log_opts_for_pre_push_new_branch_uses_mainline(
    tmp_path: Path,
) -> None:
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.name", "Synthetic")
    _git(tmp_path, "config", "user.email", "synthetic@users.noreply.github.com")
    (tmp_path / "a.txt").write_text("a\n", encoding="utf-8")
    _git(tmp_path, "add", "a.txt")
    _git(tmp_path, "commit", "-q", "-m", "main tip")
    _git(tmp_path, "checkout", "-q", "-b", "feature")
    (tmp_path / "b.txt").write_text("b\n", encoding="utf-8")
    _git(tmp_path, "add", "b.txt")
    _git(tmp_path, "commit", "-q", "-m", "feature tip")
    new = _git(tmp_path, "rev-parse", "HEAD")
    zero = "0" * 40

    stdin = f"refs/heads/feature {new} refs/heads/feature {zero}\n"
    opts = scan.history_log_opts_for_pre_push(tmp_path, stdin)
    assert opts.endswith(f"..{new}")
    assert "main" in opts


def test_history_log_opts_for_pre_push_skips_ref_deletion(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.name", "Synthetic")
    _git(tmp_path, "config", "user.email", "synthetic@users.noreply.github.com")
    (tmp_path / "a.txt").write_text("a\n", encoding="utf-8")
    _git(tmp_path, "add", "a.txt")
    _git(tmp_path, "commit", "-q", "-m", "one")
    old = _git(tmp_path, "rev-parse", "HEAD")
    (tmp_path / "b.txt").write_text("b\n", encoding="utf-8")
    _git(tmp_path, "add", "b.txt")
    _git(tmp_path, "commit", "-q", "-m", "two")
    new = _git(tmp_path, "rev-parse", "HEAD")
    zero = "0" * 40

    stdin = (
        f"refs/heads/feature {zero} refs/heads/feature {old}\n"
        f"refs/heads/main {new} refs/heads/main {old}\n"
    )
    opts = scan.history_log_opts_for_pre_push(tmp_path, stdin)
    assert opts == f"{old}..{new}"
    assert zero not in opts

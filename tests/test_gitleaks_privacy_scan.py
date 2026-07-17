"""Tests for content-bound Gitleaks false-positive review."""

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

"""Tests for the redacted, read-only pre-push Git metadata gate."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from scripts import git_hook_pre_push_privacy as pre_push

ROOT = Path(__file__).resolve().parent.parent
ZERO_OID = "0" * 40


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _init_repo(tmp_path: Path, email: str = "1+synthetic@users.noreply.github.com") -> Path:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.name", "Synthetic Author")
    _git(tmp_path, "config", "user.email", email)
    (tmp_path / "README.md").write_text("synthetic\n", encoding="utf-8")
    _git(tmp_path, "add", "README.md")
    _git(tmp_path, "commit", "-qm", "Initial synthetic snapshot")
    return tmp_path


def _line(repo: Path, old_oid: str = ZERO_OID, ref: str = "refs/heads/main") -> str:
    return f"{ref} {_git(repo, 'rev-parse', 'HEAD')} {ref} {old_oid}\n"


def test_initial_push_zero_oid_covers_all_reachable_commits(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    first = _git(repo, "rev-parse", "HEAD")
    (repo / "README.md").write_text("synthetic update\n", encoding="utf-8")
    _git(repo, "commit", "-qam", "Synthetic update")

    assert pre_push.validate_push(repo, _line(repo), remote_url="https://github.com/example/repo.git") == {}
    assert first != _git(repo, "rev-parse", "HEAD")


def test_nonzero_base_checks_only_new_commits(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path, email="legacy@example.test")
    base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "config", "user.email", "1+synthetic@users.noreply.github.com")
    (repo / "README.md").write_text("new safe commit\n", encoding="utf-8")
    _git(repo, "commit", "-qam", "New safe commit")

    assert pre_push.validate_push(repo, _line(repo, base)) == {}


def test_initial_push_blocks_non_noreply_author_without_echoing_value(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    marker = "SentinelAuthor9876"
    repo = _init_repo(tmp_path, email=f"{marker}@example.test")
    monkeypatch.setattr(sys, "stdin", __import__("io").StringIO(_line(repo)))

    assert pre_push.main(["--root", str(repo)]) == 1
    stderr = capsys.readouterr().err
    assert "author email policy" in stderr
    assert marker not in stderr


def test_sensitive_ref_is_blocked_without_echoing_value(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _init_repo(tmp_path)
    marker = "SentinelRef9876"
    ref = f"refs/heads/mrn-{marker}"
    monkeypatch.setattr(sys, "stdin", __import__("io").StringIO(_line(repo, ref=ref)))

    assert pre_push.main(["--root", str(repo)]) == 1
    stderr = capsys.readouterr().err
    assert "patient or study identifier in ref" in stderr
    assert marker not in stderr


def test_remote_url_userinfo_is_blocked_without_echoing_value(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _init_repo(tmp_path)
    marker = "SentinelRemote9876"
    monkeypatch.setattr(sys, "stdin", __import__("io").StringIO(_line(repo)))

    assert (
        pre_push.main(
            [
                "--root",
                str(repo),
                "--remote-url",
                f"https://{marker}:credential@example.test/repo.git",
            ]
        )
        == 1
    )
    stderr = capsys.readouterr().err
    assert "remote URL userinfo" in stderr
    assert marker not in stderr


def test_cli_reads_stdin_and_does_not_mutate_refs(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    before = _git(repo, "show-ref")
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "git_hook_pre_push_privacy.py"),
            "--root",
            str(repo),
            "--remote-url",
            "https://github.com/example/repo.git",
        ],
        cwd=ROOT,
        input=_line(repo),
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    assert "CLEAN" in completed.stdout
    assert _git(repo, "show-ref") == before


def test_tracked_hook_replays_ref_updates_to_both_stdin_consumers() -> None:
    hook = (ROOT / ".githooks" / "pre-push").read_text(encoding="utf-8")

    capture = 'PUSH_UPDATES="$(cat)"'
    metadata = '"$REPO_ROOT/scripts/git_hook_pre_push_privacy.py"'
    security = '"$REPO_ROOT/scripts/git-hook-security-gate.py"'
    assert capture in hook
    assert hook.index(capture) < hook.index(metadata) < hook.index(security)
    assert hook.count("printf '%s\\n' \"$PUSH_UPDATES\"") == 2

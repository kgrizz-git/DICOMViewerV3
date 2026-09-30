"""Contract tests for the local SonarQube commit and push hook checks."""

from __future__ import annotations

import subprocess
from pathlib import Path

from scripts import check_local_sonarqube_hook as hook


def test_scan_record_must_belong_to_this_project(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        hook,
        "read_last_submission",
        lambda _root: {"project_key": "other-project", "revision": "scanned"},
    )
    assert hook.recorded_revision(tmp_path) is None


def test_pre_commit_advises_only_after_five_commits(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setattr(hook, "recorded_revision", lambda _root: "scanned")
    monkeypatch.setattr(hook, "commits_behind", lambda _root, _revision: 5)
    assert hook.advise_before_commit(tmp_path) == 0
    assert capsys.readouterr().out == ""

    monkeypatch.setattr(hook, "commits_behind", lambda _root, _revision: 6)
    assert hook.advise_before_commit(tmp_path) == 0
    advisory = capsys.readouterr().out
    assert "review new issues" in advisory
    assert '--expected-revision "$(git rev-parse HEAD)"' in advisory

    monkeypatch.setattr(hook, "commits_behind", lambda _root, _revision: None)
    assert hook.advise_before_commit(tmp_path) == 0
    assert "cannot be compared" in capsys.readouterr().out


def test_pre_push_requires_exact_scanned_commit(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setattr(hook, "recorded_revision", lambda _root: "scanned")
    monkeypatch.setattr(hook, "commit_for_ref", lambda _root, oid: oid)
    update = "refs/heads/feature scanned refs/heads/feature previous"
    assert hook.check_push_updates(tmp_path, update) == 0

    stale_update = "refs/heads/feature newer refs/heads/feature previous"
    assert hook.check_push_updates(tmp_path, stale_update) == 1
    assert "push blocked" in capsys.readouterr().err


def test_pre_push_handles_deletions_and_rejects_unknown_refs(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(hook, "recorded_revision", lambda _root: None)
    deletion = f"(delete) {'0' * 40} refs/heads/old previous"
    assert hook.check_push_updates(tmp_path, deletion) == 0
    assert hook.check_push_updates(tmp_path, f"(delete) {'0' * 64} refs/heads/old previous") == 0
    assert hook.check_push_updates(tmp_path, "") == 0
    assert hook.check_push_updates(tmp_path, "malformed") == 1


def test_pre_push_blocks_without_a_scan_and_names_the_failing_ref(
    monkeypatch, tmp_path, capsys
) -> None:
    monkeypatch.setattr(hook, "recorded_revision", lambda _root: None)
    monkeypatch.setattr(hook, "commit_for_ref", lambda _root, oid: oid)
    branch = "refs/heads/feature scanned refs/heads/feature previous"
    assert hook.check_push_updates(tmp_path, branch) == 1
    error = capsys.readouterr().err
    assert "No valid dicom-viewer-v3 local scan record; refs/heads/feature" in error
    assert '--expected-revision "$(git rev-parse HEAD)"' in error

    monkeypatch.setattr(hook, "recorded_revision", lambda _root: "scanned")
    tag = "refs/tags/v1 newer refs/tags/v1 previous"
    assert hook.check_push_updates(tmp_path, f"{branch}\n{tag}") == 1
    assert "refs/tags/v1" in capsys.readouterr().err


def test_pre_push_reports_unresolvable_object_separately(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setattr(hook, "recorded_revision", lambda _root: "scanned")
    monkeypatch.setattr(hook, "commit_for_ref", lambda _root, _oid: None)
    update = "refs/heads/feature invalid refs/heads/feature previous"
    assert hook.check_push_updates(tmp_path, update) == 1
    assert "Cannot resolve refs/heads/feature to a commit" in capsys.readouterr().err


def test_multi_ref_push_passes_when_both_tips_were_scanned(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(hook, "recorded_revision", lambda _root: "scanned")
    monkeypatch.setattr(hook, "commit_for_ref", lambda _root, oid: oid)
    updates = (
        "refs/heads/feature scanned refs/heads/feature previous\n"
        "refs/tags/v1 scanned refs/tags/v1 previous"
    )
    assert hook.check_push_updates(tmp_path, updates) == 0


def test_annotated_tag_is_peeled_to_its_commit(tmp_path) -> None:
    def git(*args: str) -> str:
        result = subprocess.run(
            ["git", *args], cwd=tmp_path, capture_output=True, text=True, check=True
        )
        return result.stdout.strip()

    git("init")
    git("config", "user.name", "Hook Test")
    git("config", "user.email", "hook-test@example.invalid")
    (tmp_path / "file.txt").write_text("test\n", encoding="utf-8")
    git("add", "file.txt")
    git("commit", "-m", "Test commit")
    git("tag", "-a", "v1", "-m", "Test tag")
    assert hook.commit_for_ref(tmp_path, git("rev-parse", "v1")) == git("rev-parse", "HEAD")


def test_git_hooks_wire_advisory_and_blocking_checks() -> None:
    root = Path(__file__).resolve().parents[1]
    pre_commit = (root / ".githooks/pre-commit").read_text(encoding="utf-8")
    pre_push = (root / ".githooks/pre-push").read_text(encoding="utf-8")
    assert "check_local_sonarqube_hook.py\" --pre-commit || true" in pre_commit
    assert "check_local_sonarqube_hook.py\" --pre-push || exit 1" in pre_push
    assert pre_push.index('check_local_sonarqube_hook.py" --pre-push') < pre_push.index(
        "check_no_phi_artifacts.py"
    )

"""
Tests for scripts/check_docs_impact.py.

Covers path classification, waiver parsing, advisory vs ``--strict`` exit codes,
feature-coverage wiring, and the synthetic ``--changed-files-file`` injection
path used in CI-less tests.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_docs_impact.py"
_RANGE_SCRIPT = (
    Path(__file__).resolve().parent.parent / "scripts" / "docs_impact_ci_range.py"
)
_spec = importlib.util.spec_from_file_location("check_docs_impact", _SCRIPT)
assert _spec and _spec.loader
impact = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(impact)

_range_spec = importlib.util.spec_from_file_location(
    "docs_impact_ci_range", _RANGE_SCRIPT
)
assert _range_spec and _range_spec.loader
ci_range = importlib.util.module_from_spec(_range_spec)
_range_spec.loader.exec_module(ci_range)


def run(
    repo: Path,
    *extra: str,
    files: list[str] | None = None,
    body: str | None = None,
) -> int:
    """Invoke main() against a temp repo with optional changed-files injection."""
    argv = ["check_docs_impact.py", "--root", str(repo), *extra]
    if files is not None:
        listing = repo / "changed.txt"
        listing.write_text("\n".join(files) + "\n", encoding="utf-8")
        argv.extend(["--changed-files-file", str(listing)])
    if body is not None:
        body_path = repo / "pr-body.txt"
        body_path.write_text(body, encoding="utf-8")
        argv.extend(["--pr-body-file", str(body_path)])
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(sys, "argv", argv)
        return impact.main()


def test_normalize_repo_path():
    assert impact.normalize_repo_path(r"src\gui\foo.py") == "src/gui/foo.py"
    assert impact.normalize_repo_path("./user-docs/USER_GUIDE.md") == "user-docs/USER_GUIDE.md"
    assert impact.normalize_repo_path("src/gui/foo.py") == "src/gui/foo.py"
    assert impact.normalize_repo_path(".github/workflows/ci.yml") == ".github/workflows/ci.yml"
    assert impact.normalize_repo_path("./.github/PULL_REQUEST_TEMPLATE.md") == (
        ".github/PULL_REQUEST_TEMPLATE.md"
    )


def test_gui_path_is_docs_risk():
    assert impact.is_docs_risk_path("src/gui/main_window_menu_builder.py")
    assert impact.is_docs_risk_path("src/main_app_file_ops.py")
    assert impact.is_docs_risk_path("src/utils/doc_urls.py")
    assert impact.is_docs_risk_path("resources/help/quick_start_guide.html")
    assert not impact.is_docs_risk_path("scripts/check_docs_impact.py")
    assert not impact.is_docs_risk_path("tests/test_foo.py")


def test_satisfaction_paths():
    assert impact.is_docs_satisfaction_path("user-docs/USER_GUIDE.md")
    assert impact.is_docs_satisfaction_path("CHANGELOG.md")
    assert impact.is_docs_satisfaction_path("resources/help/quick_start_guide.html")
    assert not impact.is_docs_satisfaction_path("src/gui/foo.py")


def test_waiver_parsing_variants():
    assert impact.has_docs_impact_waiver(
        "docs-impact: not needed — comment-only GUI cleanup"
    )
    assert impact.has_docs_impact_waiver(
        "docs-impact: not needed - typo in unused string"
    )
    assert impact.has_docs_impact_waiver(
        "Preface\ndocs-impact: not needed – refactor only\n"
    )
    assert impact.has_docs_impact_waiver(
        "Preface\r\ndocs-impact: not needed – refactor only\r\n"
    )
    assert impact.has_docs_impact_waiver("docs-impact: not needed — foo bar\r\n")
    assert not impact.has_docs_impact_waiver("docs-impact: not needed")
    assert not impact.has_docs_impact_waiver("docs-impact: not needed — alone")
    assert not impact.has_docs_impact_waiver("docs-impact: not needed — x")
    assert not impact.has_docs_impact_waiver("docs-impact: not needed — x\ny")
    assert not impact.has_docs_impact_waiver("docs-impact: not needed — x\r\ny\r\n")
    assert not impact.has_docs_impact_waiver("no waiver here")
    # Indented declarations are rejected (line-anchored at column 0).
    assert not impact.has_docs_impact_waiver(
        "  docs-impact: not needed — indented false positive"
    )


def test_empty_changed_files_ok(tmp_path, capsys):
    assert run(tmp_path, "--strict", files=[]) == 0
    out = capsys.readouterr().out
    assert "no docs-risk paths" in out


def test_risk_without_docs_or_waiver_is_attention_advisory_zero(tmp_path, capsys):
    repo = tmp_path
    assert (
        run(
            repo,
            files=["src/gui/dialogs/export_dialog.py"],
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "ATTENTION" in out
    assert "docs-impact: not needed" in out


def test_strict_fails_without_docs_or_waiver(tmp_path):
    assert (
        run(
            tmp_path,
            "--strict",
            files=["src/gui/dialogs/export_dialog.py"],
        )
        == 1
    )


def test_same_diff_user_docs_satisfies(tmp_path, capsys):
    code = run(
        tmp_path,
        "--strict",
        files=[
            "src/gui/main_window_menu_builder.py",
            "user-docs/USER_GUIDE_SHORTCUTS.md",
        ],
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "OK (docs-risk paths accompany documentation updates)" in out


def test_waiver_satisfies_without_docs(tmp_path, capsys):
    code = run(
        tmp_path,
        "--strict",
        files=["src/utils/config/customizations_config.py"],
        body="docs-impact: not needed — internal config key rename only",
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "waived" in out


def test_no_risk_paths_ok(tmp_path, capsys):
    assert run(tmp_path, "--strict", files=["scripts/check_repo_harness.py"]) == 0
    out = capsys.readouterr().out
    assert "no docs-risk paths" in out


def test_injected_gui_path_triggers_attention(tmp_path, capsys):
    """Synthetic changed-files lists treat GUI paths as docs-risk (incl. removals)."""
    assert (
        run(
            tmp_path,
            files=["src/gui/legacy_export_dialog.py"],
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "ATTENTION" in out
    assert "src/gui/legacy_export_dialog.py" in out


def test_git_diff_filter_includes_deletions(tmp_path, monkeypatch):
    seen: list[list[str]] = []

    class _Result:
        returncode = 0
        stdout = "src/gui/removed_widget.py\n"
        stderr = ""

    def _fake_run(cmd, **_kwargs):
        seen.append(list(cmd))
        return _Result()

    monkeypatch.setattr(impact.subprocess, "run", _fake_run)
    files = impact.changed_files_from_git(tmp_path, diff_range="abc...HEAD")
    assert files == ["src/gui/removed_widget.py"]
    assert seen and f"--diff-filter={impact._GIT_DIFF_NAME_FILTER}" in seen[0]
    assert impact._GIT_DIFF_NAME_FILTER == "ACMRD"

    seen.clear()
    files = impact.changed_files_from_git(tmp_path, staged=True)
    assert files == ["src/gui/removed_widget.py"]
    assert seen and f"--diff-filter={impact._GIT_DIFF_NAME_FILTER}" in seen[0]


def test_is_all_zero_oid():
    assert ci_range.is_all_zero_oid("0" * 40)
    assert ci_range.is_all_zero_oid("0" * 64)
    assert not ci_range.is_all_zero_oid("")
    assert not ci_range.is_all_zero_oid("a" + "0" * 39)


def test_resolve_ci_range_push_normal(tmp_path, monkeypatch):
    before = "a" * 40
    monkeypatch.setattr(ci_range, "try_fetch_commit", lambda _r, oid: oid == before)
    monkeypatch.setattr(
        ci_range, "git_merge_base_exists", lambda _r, a, b="HEAD": a == before
    )
    status, rng, msg = ci_range.resolve_ci_diff_range(
        tmp_path,
        event_name="push",
        push_before_sha=before,
        default_branch="main",
    )
    assert status == "ok"
    assert rng == f"{before}...HEAD"
    assert "push before" in msg


def test_resolve_ci_range_push_first_empty_before(tmp_path, monkeypatch):
    monkeypatch.setattr(ci_range, "git_empty_tree_oid", lambda _r: "emptytree")
    status, rng, msg = ci_range.resolve_ci_diff_range(
        tmp_path,
        event_name="push",
        push_before_sha="0" * 40,
        default_branch="main",
    )
    assert status == "ok"
    assert rng == "emptytree...HEAD"
    assert "empty" in msg.lower()


def test_resolve_ci_range_push_missing_before_falls_back(tmp_path, monkeypatch):
    before = "b" * 40
    monkeypatch.setattr(ci_range, "try_fetch_commit", lambda _r, _oid: False)
    monkeypatch.setattr(
        ci_range, "git_rev_parse_ok", lambda _r, ref: ref == "origin/main"
    )
    monkeypatch.setattr(
        ci_range,
        "git_merge_base_exists",
        lambda _r, a, b="HEAD": a == "origin/main",
    )
    status, rng, msg = ci_range.resolve_ci_diff_range(
        tmp_path,
        event_name="push",
        push_before_sha=before,
        default_branch="main",
    )
    assert status == "ok"
    assert rng == "origin/main...HEAD"
    assert "fell back" in msg


def test_resolve_ci_range_push_missing_before_errors_without_fallback(
    tmp_path, monkeypatch
):
    before = "c" * 40
    monkeypatch.setattr(ci_range, "try_fetch_commit", lambda _r, _oid: False)
    monkeypatch.setattr(ci_range, "git_rev_parse_ok", lambda _r, _ref: False)
    status, rng, msg = ci_range.resolve_ci_diff_range(
        tmp_path,
        event_name="push",
        push_before_sha=before,
        default_branch="main",
    )
    assert status == "error"
    assert rng is None
    assert "unavailable" in msg


def test_resolve_ci_range_pull_request_ok(tmp_path, monkeypatch):
    base = "d" * 40
    monkeypatch.setattr(ci_range, "git_commit_exists", lambda _r, oid: oid == base)
    monkeypatch.setattr(
        ci_range, "git_merge_base_exists", lambda _r, a, b="HEAD": a == base
    )
    status, rng, msg = ci_range.resolve_ci_diff_range(
        tmp_path,
        event_name="pull_request",
        pr_base_sha=base,
    )
    assert status == "ok"
    assert rng == f"{base}...HEAD"
    assert "PR base" in msg


def test_resolve_ci_range_pull_request_missing_base_skips(tmp_path):
    status, rng, msg = ci_range.resolve_ci_diff_range(
        tmp_path,
        event_name="pull_request",
        pr_base_sha="",
    )
    assert status == "skip"
    assert rng is None
    assert "missing PR base" in msg


def test_resolve_ci_range_schedule_ok(tmp_path, monkeypatch):
    monkeypatch.setattr(
        ci_range, "git_rev_parse_ok", lambda _r, ref: ref == "origin/main"
    )
    monkeypatch.setattr(
        ci_range,
        "git_merge_base_exists",
        lambda _r, a, b="HEAD": a == "origin/main",
    )
    status, rng, msg = ci_range.resolve_ci_diff_range(
        tmp_path,
        event_name="schedule",
        default_branch="main",
    )
    assert status == "ok"
    assert rng == "origin/main...HEAD"


def test_resolve_ci_range_workflow_dispatch_missing_origin_skips(tmp_path, monkeypatch):
    monkeypatch.setattr(ci_range, "git_rev_parse_ok", lambda _r, _ref: False)
    status, rng, msg = ci_range.resolve_ci_diff_range(
        tmp_path,
        event_name="workflow_dispatch",
        default_branch="main",
    )
    assert status == "skip"
    assert rng is None
    assert "missing origin/main" in msg


def test_resolve_ci_range_unsupported_event_skips(tmp_path):
    status, rng, msg = ci_range.resolve_ci_diff_range(
        tmp_path,
        event_name="issue_comment",
    )
    assert status == "skip"
    assert rng is None
    assert "unsupported event" in msg


def test_fallback_origin_default_errors_without_merge_base(tmp_path, monkeypatch):
    monkeypatch.setattr(
        ci_range, "git_rev_parse_ok", lambda _r, ref: ref == "origin/main"
    )
    monkeypatch.setattr(ci_range, "git_merge_base_exists", lambda *_a, **_k: False)
    status, rng, msg = ci_range._fallback_origin_default(
        tmp_path, "main", why="push before SHA unavailable"
    )
    assert status == "error"
    assert rng is None
    assert "no merge-base" in msg


def test_resolve_ci_range_cli_exit_codes(tmp_path, monkeypatch, capsys):
    """CLI maps resolve status to exit 0 (ok), 2 (skip), 1 (error)."""

    def _ok(_root, **_kwargs):
        return "ok", "abc...HEAD", "unit"

    def _skip(_root, **_kwargs):
        return "skip", None, "missing PR base SHA"

    def _err(_root, **_kwargs):
        return "error", None, "push before SHA unavailable"

    monkeypatch.setattr(impact, "resolve_ci_diff_range", _ok)
    assert (
        impact.main(
            [
                "--root",
                str(tmp_path),
                "--resolve-ci-range",
                "--event-name",
                "push",
            ]
        )
        == 0
    )
    assert "abc...HEAD" in capsys.readouterr().out

    monkeypatch.setattr(impact, "resolve_ci_diff_range", _skip)
    assert (
        impact.main(
            [
                "--root",
                str(tmp_path),
                "--resolve-ci-range",
                "--event-name",
                "pull_request",
            ]
        )
        == 2
    )

    monkeypatch.setattr(impact, "resolve_ci_diff_range", _err)
    assert (
        impact.main(
            [
                "--root",
                str(tmp_path),
                "--resolve-ci-range",
                "--event-name",
                "push",
            ]
        )
        == 1
    )


def test_github_pr_body_env(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "GITHUB_PR_BODY",
        "docs-impact: not needed — CI body from GITHUB_PR_BODY",
    )
    listing = tmp_path / "changed.txt"
    listing.write_text("src/gui/foo.py\n", encoding="utf-8")
    argv = [
        "check_docs_impact.py",
        "--root",
        str(tmp_path),
        "--changed-files-file",
        str(listing),
        "--strict",
    ]
    with pytest.MonkeyPatch.context() as patch:
        # Keep GITHUB_PR_BODY from outer monkeypatch; only replace argv.
        patch.setattr(sys, "argv", argv)
        assert impact.main() == 0


def test_evaluate_wants_feature_coverage_for_gui():
    risk, _sat, _w, _need, want = impact.evaluate_docs_impact(
        ["src/gui/x.py"], ""
    )
    assert risk == ["src/gui/x.py"]
    assert want is True
    _r, _s, _w, _n, want2 = impact.evaluate_docs_impact(
        ["src/utils/doc_urls.py"], ""
    )
    assert want2 is False


def test_with_feature_coverage_includes_helper_output(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(
        impact,
        "run_feature_coverage_report",
        lambda _root: ["FEATURE_COVERAGE_STUB_LINE"],
    )
    code = run(
        tmp_path,
        "--with-feature-coverage",
        files=["src/gui/foo.py", "user-docs/USER_GUIDE.md"],
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "feature-coverage" in out
    assert "FEATURE_COVERAGE_STUB_LINE" in out


def test_with_feature_coverage_skipped_for_non_ui_risk(tmp_path, capsys, monkeypatch):
    called: list[int] = []

    def _stub(_root: Path) -> list[str]:
        called.append(1)
        return ["SHOULD_NOT_APPEAR"]

    monkeypatch.setattr(impact, "run_feature_coverage_report", _stub)
    code = run(
        tmp_path,
        "--with-feature-coverage",
        files=["src/utils/doc_urls.py"],
        body="docs-impact: not needed — doc_urls comment only",
    )
    assert code == 0
    assert called == []
    out = capsys.readouterr().out
    assert "SHOULD_NOT_APPEAR" not in out


def test_feature_coverage_failure_does_not_include_stderr(tmp_path, monkeypatch):
    """Failed helper: surface exit/cmd on stdout path only; never merge stderr."""

    class _Result:
        returncode = 2
        stdout = "partial stdout line\n"
        stderr = "secret-looking stderr\n"

    monkeypatch.setattr(
        impact.subprocess,
        "run",
        lambda *_a, **_k: _Result(),
    )
    # Ensure the script path is considered present.
    script = tmp_path / "scripts" / "check_doc_feature_coverage.py"
    script.parent.mkdir(parents=True)
    script.write_text("# stub\n", encoding="utf-8")
    lines = impact.run_feature_coverage_report(tmp_path)
    joined = "\n".join(lines)
    assert "partial stdout line" in joined
    assert "secret-looking stderr" not in joined
    assert "feature coverage failed: exit 2" in joined

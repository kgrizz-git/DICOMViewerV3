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
_spec = importlib.util.spec_from_file_location("check_docs_impact", _SCRIPT)
assert _spec and _spec.loader
impact = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(impact)


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
    assert not impact.has_docs_impact_waiver("docs-impact: not needed")
    assert not impact.has_docs_impact_waiver("docs-impact: not needed — alone")
    assert not impact.has_docs_impact_waiver("docs-impact: not needed — x")
    assert not impact.has_docs_impact_waiver("no waiver here")


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

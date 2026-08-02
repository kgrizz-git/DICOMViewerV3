"""Tests for the local new-code coverage approximation CLI."""

from __future__ import annotations

import subprocess

from scripts import new_code_coverage


def test_missing_coverage_instructs_the_user_to_activate_the_venv(
    tmp_path, capsys
) -> None:
    assert new_code_coverage.main(["--coverage-file", str(tmp_path / "missing.xml")]) == 2
    assert "source .venv/bin/activate" in capsys.readouterr().err


def test_main_reports_an_unavailable_base_ref(tmp_path, monkeypatch, capsys) -> None:
    """An invalid git ref should return a concise recovery error, not a traceback."""
    coverage_file = tmp_path / "coverage.xml"
    coverage_file.write_text("<coverage />", encoding="utf-8")
    error = subprocess.CalledProcessError(
        128,
        ["git", "diff", "missing-ref"],
        stderr="fatal: bad revision 'missing-ref'",
    )
    seen_bases: list[str] = []

    def fail_changed_lines(base: str):
        seen_bases.append(base)
        raise error

    monkeypatch.setattr(new_code_coverage, "parse_coverage", lambda _: {})
    monkeypatch.setattr(new_code_coverage, "changed_lines", fail_changed_lines)

    assert (
        new_code_coverage.main(
            ["--coverage-file", str(coverage_file), "--base", "missing-ref"]
        )
        == 2
    )
    stderr = capsys.readouterr().err
    assert seen_bases == ["missing-ref"]
    assert "Could not compare against base ref 'missing-ref'" in stderr
    assert "fatal: bad revision 'missing-ref'" in stderr
    assert "Traceback" not in stderr

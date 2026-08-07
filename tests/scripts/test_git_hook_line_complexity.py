"""Tests for the line-count and complexity pre-commit gate."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

from scripts import git_hook_line_complexity as ghlc


def _analyze(relpath: str, body: str) -> list[ghlc.Violation]:
    return ghlc.analyze_content(relpath, textwrap.dedent(body))


def test_small_clean_file_has_no_violations() -> None:
    violations = _analyze(
        "small.py",
        """\
        '''A small module.'''

        def add(a, b):
            return a + b

        def sub(a, b):
            return a - b
        """,
    )
    assert violations == []


def test_file_at_warn_threshold_is_not_blocking() -> None:
    body = '"""Module."""\n' + "\n".join(f"# line {i}" for i in range(620))
    violations = ghlc.analyze_content("warn_only.py", body)
    assert len(violations) == 1
    v = violations[0]
    assert v.kind == "file_lines"
    assert v.blocking is False
    assert v.grandfathered is False
    assert v.value == 621
    assert v.threshold == ghlc.WARN_LINES


def test_file_at_block_threshold_is_blocking() -> None:
    body = '"""Module."""\n' + "\n".join(f"# line {i}" for i in range(800))
    violations = ghlc.analyze_content("big.py", body)
    assert len(violations) == 1
    v = violations[0]
    assert v.kind == "file_lines"
    assert v.blocking is True
    assert v.threshold == ghlc.BLOCK_LINES


def test_function_over_ccn_threshold_is_blocking() -> None:
    body = textwrap.dedent(
        """\
        def complex_fn(a, b, c, d, e, f, g):
            r = 0
            if a > 0:
                if b > 0:
                    if c > 0:
                        if d > 0:
                            r = 1
                        elif e > 0:
                            r = 2
                        elif f > 0:
                            r = 3
                        else:
                            r = 4
                    elif c < 0:
                        if d > 0:
                            r = 5
                        elif e > 0:
                            r = 6
                        else:
                            r = 7
                    else:
                        r = 8
                elif b < 0:
                    if c > 0:
                        r = 9
                    elif d > 0:
                        r = 10
                    else:
                        r = 11
                else:
                    r = 12
            elif a < 0:
                if b > 0:
                    if c > 0:
                        r = 13
                    elif d > 0:
                        r = 14
                    else:
                        r = 15
                elif b < 0:
                    if c > 0:
                        r = 16
                    elif d > 0:
                        r = 17
                    else:
                        r = 18
                else:
                    r = 19
            else:
                r = 20
            if f > 0:
                r += 100
            return r
        """
    )
    violations = ghlc.analyze_content("ccn.py", body)
    func_violations = [v for v in violations if v.kind == "function_ccn"]
    assert len(func_violations) == 1
    v = func_violations[0]
    assert v.label == "complex_fn"
    assert v.value > ghlc.BLOCK_CCN
    assert v.blocking is True


def test_grandfather_marks_item_without_clearing_blocking_flag() -> None:
    """``apply_grandfather`` sets ``grandfathered``; callers exclude those from FAIL.

    The ``blocking`` flag stays True so the finding remains a threshold hit; only
    ``check_files`` (``blocking and not grandfathered``) treats it as warn-only.
    """

    body = '"""Module."""\n' + "\n".join(f"# line {i}" for i in range(800))
    violations = ghlc.analyze_content("big.py", body)
    data = {"files": {"big.py": 801}, "functions": {}}
    violations = ghlc.apply_grandfather(violations, data)
    assert violations[0].value == 801
    assert violations[0].grandfathered is True
    assert violations[0].regressed is False
    assert violations[0].blocking is True


def test_grandfather_equal_baseline_is_not_regression() -> None:
    body = '"""Module."""\n' + "\n".join(f"# line {i}" for i in range(800))
    violations = ghlc.analyze_content("big.py", body)
    data = {"files": {"big.py": 801}, "functions": {}}
    violations = ghlc.apply_grandfather(violations, data)
    assert violations[0].regressed is False
    assert violations[0].grandfathered is True


def test_grandfather_increase_is_regression() -> None:
    body = '"""Module."""\n' + "\n".join(f"# line {i}" for i in range(850))
    violations = ghlc.analyze_content("big.py", body)
    data = {"files": {"big.py": 801}, "functions": {}}
    violations = ghlc.apply_grandfather(violations, data)
    assert violations[0].value == 851
    assert violations[0].baseline == 801
    assert violations[0].regressed is True
    assert violations[0].grandfathered is False
    assert violations[0].blocking is True
    assert "regression: was 801" in violations[0].format()


def test_grandfather_ccn_increase_is_regression() -> None:
    body = textwrap.dedent(
        """\
        def complex_fn(a, b, c, d, e, f, g):
            r = 0
            if a > 0:
                if b > 0:
                    if c > 0:
                        if d > 0:
                            r = 1
                        elif e > 0:
                            r = 2
                        elif f > 0:
                            r = 3
                        else:
                            r = 4
                    elif c < 0:
                        if d > 0:
                            r = 5
                        elif e > 0:
                            r = 6
                        else:
                            r = 7
                    else:
                        r = 8
                elif b < 0:
                    if c > 0:
                        r = 9
                    elif d > 0:
                        r = 10
                    else:
                        r = 11
                else:
                    r = 12
            elif a < 0:
                if b > 0:
                    if c > 0:
                        r = 13
                    elif d > 0:
                        r = 14
                    else:
                        r = 15
                elif b < 0:
                    if c > 0:
                        r = 16
                    elif d > 0:
                        r = 17
                    else:
                        r = 18
                else:
                    r = 19
            else:
                r = 20
            if f > 0:
                r += 100
            return r
        """
    )
    violations = ghlc.analyze_content("ccn.py", body)
    func = next(v for v in violations if v.kind == "function_ccn")
    data = {
        "files": {},
        "functions": {"ccn.py::complex_fn": func.value - 1},
    }
    updated = ghlc.apply_grandfather([func], data)[0]
    assert updated.regressed is True
    assert updated.blocking is True
    assert updated.grandfathered is False


def test_grandfather_does_not_apply_to_unknown_file() -> None:
    body = '"""Module."""\n' + "\n".join(f"# line {i}" for i in range(800))
    violations = ghlc.analyze_content("new_file.py", body)
    data = {"files": {}, "functions": {}}
    violations = ghlc.apply_grandfather(violations, data)
    assert violations[0].grandfathered is False
    assert violations[0].regressed is False
    assert violations[0].blocking is True


def test_mark_grandfathered_skips_warning_tier() -> None:
    body = '"""Module."""\n' + "\n".join(f"# line {i}" for i in range(620))
    violations = ghlc.analyze_content("warn_only.py", body)
    data: dict = {"files": {}, "functions": {}}
    ghlc.mark_grandfathered(violations, data)
    assert "warn_only.py" not in data["files"]


def test_mark_grandfathered_captures_blocking_file() -> None:
    body = '"""Module."""\n' + "\n".join(f"# line {i}" for i in range(800))
    violations = ghlc.analyze_content("big.py", body)
    data: dict = {"files": {}, "functions": {}}
    ghlc.mark_grandfathered(violations, data)
    assert data["files"]["big.py"] == 801


def test_mark_grandfathered_captures_high_ccn_function() -> None:
    body = textwrap.dedent(
        """\
        def big(a, b, c, d, e, f, g):
            r = 0
            if a > 0:
                if b > 0:
                    if c > 0:
                        if d > 0:
                            r = 1
                        elif e > 0:
                            r = 2
                        elif f > 0:
                            r = 3
                        else:
                            r = 4
                    elif c < 0:
                        if d > 0:
                            r = 5
                        elif e > 0:
                            r = 6
                        else:
                            r = 7
                    else:
                        r = 8
                elif b < 0:
                    if c > 0:
                        r = 9
                    elif d > 0:
                        r = 10
                    else:
                        r = 11
                else:
                    r = 12
            elif a < 0:
                if b > 0:
                    if c > 0:
                        r = 13
                    elif d > 0:
                        r = 14
                    else:
                        r = 15
                elif b < 0:
                    if c > 0:
                        r = 16
                    elif d > 0:
                        r = 17
                    else:
                        r = 18
                else:
                    r = 19
            else:
                r = 20
            if f > 0:
                r += 100
            return r
        """
    )
    violations = ghlc.analyze_content("mod.py", body)
    data: dict = {"files": {}, "functions": {}}
    ghlc.mark_grandfathered(violations, data)
    assert "mod.py::big" in data["functions"]


def test_generate_grandfather_writes_only_to_override_path(tmp_path: Path) -> None:
    """Regression: generation must never clobber the repo grandfather by accident."""

    big = tmp_path / "big.py"
    big.write_text(
        '"""Module."""\n' + "\n".join(f"# line {i}" for i in range(800)),
        encoding="utf-8",
    )
    small = tmp_path / "small.py"
    small.write_text('"""Module."""\n', encoding="utf-8")

    out = tmp_path / "grandfather.json"
    before = (
        ghlc.GRANDFATHER_PATH.read_text(encoding="utf-8")
        if ghlc.GRANDFATHER_PATH.exists()
        else None
    )

    result = ghlc.generate_grandfather(
        tmp_path, ["big.py", "small.py"], grandfather_path=out
    )

    assert result == 0
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert "big.py" in saved["files"]
    assert "small.py" not in saved["files"]
    after = (
        ghlc.GRANDFATHER_PATH.read_text(encoding="utf-8")
        if ghlc.GRANDFATHER_PATH.exists()
        else None
    )
    assert after == before


def test_worktree_file_content_reads_disk(tmp_path: Path) -> None:
    target = tmp_path / "sample.py"
    target.write_text("x = 1\n", encoding="utf-8")
    assert ghlc.worktree_file_content(tmp_path, "sample.py") == "x = 1\n"
    assert ghlc.worktree_file_content(tmp_path, "missing.py") is None


def test_check_files_blocks_new_violation(tmp_path: Path, capsys) -> None:
    tmp_gf = tmp_path / "grandfather.json"
    tmp_gf.write_text('{"files": {}, "functions": {}}', encoding="utf-8")
    big = tmp_path / "new_big.py"
    big.write_text(
        '"""Module."""\n' + "\n".join(f"# line {i}" for i in range(800)),
        encoding="utf-8",
    )

    result = ghlc.check_files(
        tmp_path,
        ["new_big.py"],
        from_index=False,
        grandfather_path=tmp_gf,
    )

    assert result == 1
    assert "FAIL" in capsys.readouterr().out


def test_check_files_passes_grandfathered_violation(tmp_path: Path, capsys) -> None:
    tmp_gf = tmp_path / "grandfather.json"
    tmp_gf.write_text(
        '{"files": {"big.py": 801}, "functions": {}}', encoding="utf-8"
    )
    big = tmp_path / "big.py"
    big.write_text(
        '"""Module."""\n' + "\n".join(f"# line {i}" for i in range(800)),
        encoding="utf-8",
    )

    result = ghlc.check_files(
        tmp_path,
        ["big.py"],
        from_index=False,
        grandfather_path=tmp_gf,
    )

    assert result == 0
    assert "WARN" in capsys.readouterr().out


def test_check_files_blocks_grandfather_regression(tmp_path: Path, capsys) -> None:
    tmp_gf = tmp_path / "grandfather.json"
    tmp_gf.write_text(
        '{"files": {"big.py": 801}, "functions": {}}', encoding="utf-8"
    )
    big = tmp_path / "big.py"
    big.write_text(
        '"""Module."""\n' + "\n".join(f"# line {i}" for i in range(900)),
        encoding="utf-8",
    )

    result = ghlc.check_files(
        tmp_path,
        ["big.py"],
        from_index=False,
        grandfather_path=tmp_gf,
    )

    captured = capsys.readouterr().out
    assert result == 1
    assert "FAIL" in captured
    assert "regression: was 801" in captured


def test_check_files_all_mode_uses_worktree_not_index(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """``from_index=False`` must read disk even when the index reader would fail."""

    tmp_gf = tmp_path / "grandfather.json"
    tmp_gf.write_text('{"files": {}, "functions": {}}', encoding="utf-8")
    dirty = tmp_path / "dirty.py"
    dirty.write_text(
        '"""Module."""\n' + "\n".join(f"# line {i}" for i in range(800)),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        ghlc, "staged_file_content", lambda *_args, **_kwargs: None
    )

    result = ghlc.check_files(
        tmp_path,
        ["dirty.py"],
        from_index=False,
        grandfather_path=tmp_gf,
    )

    assert result == 1
    assert "FAIL" in capsys.readouterr().out


def test_ratchet_lowers_file_cap_on_improvement() -> None:
    body = '"""Module."""\n' + "\n".join(f"# line {i}" for i in range(780))
    violations = ghlc.analyze_content("big.py", body)
    data: dict = {"files": {"big.py": 900}, "functions": {}}
    notes = ghlc.ratchet_grandfather(data, "big.py", violations)
    assert data["files"]["big.py"] == 781
    assert any("900 -> 781" in note for note in notes)


def test_ratchet_removes_file_cap_when_under_block_threshold() -> None:
    body = '"""Module."""\n' + "\n".join(f"# line {i}" for i in range(700))
    violations = ghlc.analyze_content("big.py", body)
    data: dict = {"files": {"big.py": 900}, "functions": {}}
    notes = ghlc.ratchet_grandfather(data, "big.py", violations)
    assert "big.py" not in data["files"]
    assert any("removed file cap" in note for note in notes)


def test_ratchet_removes_stale_function_cap() -> None:
    body = '"""Module."""\n\ndef small():\n    return 1\n'
    violations = ghlc.analyze_content("mod.py", body)
    data: dict = {
        "files": {},
        "functions": {"mod.py::gone": 25},
    }
    notes = ghlc.ratchet_grandfather(data, "mod.py", violations)
    assert "mod.py::gone" not in data["functions"]
    assert any("removed function cap" in note for note in notes)


def test_check_files_ratchet_persists_lower_cap(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    tmp_gf = tmp_path / "grandfather.json"
    tmp_gf.write_text(
        '{"files": {"big.py": 900}, "functions": {}}', encoding="utf-8"
    )
    big = tmp_path / "big.py"
    big.write_text(
        '"""Module."""\n' + "\n".join(f"# line {i}" for i in range(800)),
        encoding="utf-8",
    )
    staged: list[str] = []
    monkeypatch.setattr(
        ghlc,
        "stage_grandfather_file",
        lambda root, path: staged.append(str(path)),
    )
    monkeypatch.setattr(
        ghlc,
        "staged_file_content",
        lambda root, relpath: (tmp_path / relpath).read_text(encoding="utf-8"),
    )

    result = ghlc.check_files(
        tmp_path,
        ["big.py"],
        from_index=True,
        grandfather_path=tmp_gf,
        ratchet=True,
    )

    saved = json.loads(tmp_gf.read_text(encoding="utf-8"))
    assert result == 0
    assert saved["files"]["big.py"] == 801
    assert staged == [str(tmp_gf)]
    assert "Ratcheted" in capsys.readouterr().out

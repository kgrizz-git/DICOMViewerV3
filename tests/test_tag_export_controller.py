"""Qt-free unit tests for core.tag_export_controller (refactor Stream A).

Covers format resolution and writer dispatch without importing Qt or writing a
real workbook — the underlying writers are tested in test_tag_export_writer.py.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core import tag_export_controller as tec
from core.tag_export_controller import (
    FORMAT_CSV,
    FORMAT_TXT,
    FORMAT_XLSX,
    TagExportController,
    resolve_export_format,
)

# --- resolve_export_format -------------------------------------------------

@pytest.mark.parametrize(
    "path,flt,expected_fmt,expected_path",
    [
        ("out", "CSV Files (*.csv)", FORMAT_CSV, "out.csv"),
        ("out", "Text Files (*.txt)", FORMAT_TXT, "out.txt"),
        ("out", "Excel Files (*.xlsx)", FORMAT_XLSX, "out.xlsx"),
        ("out", "All Files (*)", FORMAT_XLSX, "out.xlsx"),  # default
        ("data.csv", "All Files (*)", FORMAT_CSV, "data.csv"),  # by extension
        ("data.txt", "All Files (*)", FORMAT_TXT, "data.txt"),
        ("data.xlsx", "Excel Files (*.xlsx)", FORMAT_XLSX, "data.xlsx"),  # no double ext
        ("REPORT.CSV", "All Files (*)", FORMAT_CSV, "REPORT.CSV"),  # case-insensitive ext
    ],
)
def test_resolve_export_format(path, flt, expected_fmt, expected_path):
    fmt, out = resolve_export_format(path, flt)
    assert fmt == expected_fmt
    assert out == expected_path


def test_resolve_export_format_filter_wins_over_extension():
    # CSV filter selected but path has no extension -> csv appended
    fmt, out = resolve_export_format("export", "CSV Files (*.csv)")
    assert fmt == FORMAT_CSV and out == "export.csv"


# --- TagExportController.export dispatch ------------------------------------

def _controller():
    return TagExportController(
        studies={"st": {"se": []}},
        selected_series={"st": {"se": [0]}},
        selected_tags=["(0010,0010)"],
        include_private=True,
        include_missing_rows=False,
    )


def test_export_csv_dispatches_to_csv_writer(monkeypatch):
    calls = {}

    def fake_csv(
        path, var, studies, series, tags, priv, include_missing_selected_tags, include_sequences
    ):
        calls.update(
            path=path,
            priv=priv,
            include_missing=include_missing_selected_tags,
            include_sequences=include_sequences,
        )
        return [Path("a.csv"), Path("b.csv")]

    monkeypatch.setattr(tec, "write_csv_files", fake_csv)
    out = _controller().export("x.csv", {"se": {}}, FORMAT_CSV)
    assert out == [Path("a.csv"), Path("b.csv")]
    assert calls["path"] == "x.csv"
    assert calls["priv"] is True
    assert calls["include_missing"] is False  # options threaded through
    assert calls["include_sequences"] is False  # default off


def test_export_csv_dispatches_with_include_sequences_on(monkeypatch):
    calls = {}

    def fake_csv(
        path, var, studies, series, tags, priv, include_missing_selected_tags, include_sequences
    ):
        calls.update(include_sequences=include_sequences)
        return [Path("a.csv")]

    monkeypatch.setattr(tec, "write_csv_files", fake_csv)
    controller = TagExportController(
        studies={"st": {"se": []}},
        selected_series={"st": {"se": [0]}},
        selected_tags=["(0010,0010)"],
        include_private=True,
        include_missing_rows=False,
        include_sequences=True,
    )
    controller.export("x.csv", {"se": {}}, FORMAT_CSV)
    assert calls["include_sequences"] is True


def test_export_txt_dispatches_to_txt_writer(monkeypatch):
    monkeypatch.setattr(tec, "write_txt_files", lambda *a, **k: [Path("a.txt")])
    out = _controller().export("x.txt", {"se": {}}, FORMAT_TXT)
    assert out == [Path("a.txt")]


def test_export_xlsx_writes_workbook_and_returns_single_path(monkeypatch):
    seen = {}
    monkeypatch.setattr(tec, "write_excel_file", lambda *a, **k: seen.update(called=True))
    out = _controller().export("x.xlsx", {"se": {}}, FORMAT_XLSX)
    assert seen.get("called") is True
    assert out == [Path("x.xlsx")]  # single workbook -> single path


def test_export_unknown_format_raises():
    with pytest.raises(ValueError):
        _controller().export("x.bin", {"se": {}}, "bin")


# --- delegation ------------------------------------------------------------

def test_analyze_variations_delegates_with_options(monkeypatch):
    captured = {}

    def fake_analyze(studies, series, tags, include_private, include_sequences=False):
        captured.update(
            studies=studies,
            series=series,
            tags=tags,
            priv=include_private,
            sequences=include_sequences,
        )
        return {"se": {"varying_tags": [], "constant_tags": tags}}

    monkeypatch.setattr(tec, "analyze_tag_variations", fake_analyze)
    result = _controller().analyze_variations()
    assert captured["priv"] is True
    assert captured["tags"] == ["(0010,0010)"]
    assert "se" in result
    # The analysis must see sequences exactly as the writer does; if it doesn't, an
    # SQ tag collects no values and is silently bucketed constant.
    assert captured["sequences"] is False  # controller default

    captured.clear()
    tec.TagExportController(
        studies=_controller().studies,
        selected_series=_controller().selected_series,
        selected_tags=_controller().selected_tags,
        include_private=True,
        include_sequences=True,
    ).analyze_variations()
    assert captured["sequences"] is True


def test_default_filename_delegates(monkeypatch):
    monkeypatch.setattr(tec, "generate_default_filename", lambda studies, series: "CT Export 123.xlsx")
    assert _controller().default_filename() == "CT Export 123.xlsx"

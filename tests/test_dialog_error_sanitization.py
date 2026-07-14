from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

from gui.dialogs import radiation_dose_report_dialog as dose_dialog
from gui.dialogs import screenshot_export_dialog as screenshot_dialog
from gui.dialogs import structured_report_browser_dialog as sr_dialog
from gui.dialogs import study_index_search_dialog as study_index_dialog


class _ValueBox:
    def __init__(self, value):
        self._value = value

    def text(self):
        return self._value

    def currentData(self):
        return self._value

    def isChecked(self):
        return bool(self._value)


def test_screenshot_export_failure_dialog_sanitizes_paths(monkeypatch, qapp) -> None:
    captured: list[tuple[str, str]] = []

    def _critical(_parent, title: str, text: str) -> None:
        captured.append((title, text))

    fake_dialog = SimpleNamespace(
        MODE_FULL_WINDOW=screenshot_dialog.ScreenshotExportDialog.MODE_FULL_WINDOW,
        MODE_COMPOSITE=screenshot_dialog.ScreenshotExportDialog.MODE_COMPOSITE,
        MODE_SEPARATE=screenshot_dialog.ScreenshotExportDialog.MODE_SEPARATE,
        prefix_edit=_ValueBox("shot"),
        format_combo=_ValueBox("PNG"),
        resolution_combo=_ValueBox(1.0),
        output_path="exports",
        config_manager=None,
        prefix="",
        format="PNG",
        export_scale=1.0,
        _current_export_mode=lambda: screenshot_dialog.ScreenshotExportDialog.MODE_SEPARATE,
        _selected_indices=lambda: [0],
        _paths_for_overwrite_prompt=lambda prefix, ext, mode: [],
        _set_subwindow_focus_borders_suppressed=lambda enabled: None,
        _export_separate=lambda prefix, ext, selected: (_ for _ in ()).throw(
            RuntimeError("C:\\Users\\alice\\Desktop\\secret\\scan.dcm failed")
        ),
        accept=lambda: None,
    )

    monkeypatch.setattr(screenshot_dialog.QMessageBox, "critical", staticmethod(_critical))
    monkeypatch.setattr(screenshot_dialog.QApplication, "processEvents", staticmethod(lambda: None))

    screenshot_dialog.ScreenshotExportDialog._on_export(fake_dialog)

    assert captured
    title, text = captured[0]
    assert title == "Export failed"
    assert "C:\\Users\\alice\\Desktop\\secret\\scan.dcm" not in text
    assert "[REDACTED]" in text


def test_radiation_dose_json_export_sanitizes_paths(monkeypatch, qapp) -> None:
    captured: list[tuple[str, str]] = []

    def _warning(_parent, title: str, text: str) -> None:
        captured.append((title, text))

    fake_dialog = SimpleNamespace(
        _summary=object(),
        _anonymize_cb=_ValueBox(True),
    )

    monkeypatch.setattr(
        dose_dialog.QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *args, **kwargs: ("dose_summary.json", "JSON (*.json)")),
    )
    monkeypatch.setattr(
        dose_dialog,
        "write_dose_summary_json",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            OSError("Permission denied for C:\\Users\\alice\\Desktop\\dose_summary.json")
        ),
    )
    monkeypatch.setattr(dose_dialog.QMessageBox, "warning", staticmethod(_warning))

    dose_dialog.RadiationDoseReportDialog._export_json(fake_dialog)

    assert captured
    title, text = captured[0]
    assert title == "Export"
    assert "Could not write file" in text
    assert "C:\\Users\\alice\\Desktop\\dose_summary.json" not in text
    assert "[REDACTED]" in text


def test_structured_report_tree_export_sanitizes_paths(monkeypatch, qapp) -> None:
    captured: list[tuple[str, str]] = []

    def _warning(_parent, title: str, text: str) -> None:
        captured.append((title, text))

    fake_dialog = SimpleNamespace(_tree_data=object())

    monkeypatch.setattr(
        sr_dialog.QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *args, **kwargs: ("tree.json", "JSON (*.json)")),
    )
    monkeypatch.setattr(sr_dialog, "sr_tree_to_json_dict", lambda tree: {"ok": True})

    def _raising_open(*args, **kwargs):
        raise OSError("/Users/alice/Documents/private/tree.json")

    monkeypatch.setattr("builtins.open", _raising_open)
    monkeypatch.setattr(sr_dialog.QMessageBox, "warning", staticmethod(_warning))

    sr_dialog.StructuredReportBrowserDialog._export_tree_json(fake_dialog)

    assert captured
    title, text = captured[0]
    assert title == "Export"
    assert "Could not write file" in text
    assert "/Users/alice/Documents/private/tree.json" not in text
    assert "[REDACTED]" in text


def test_study_index_remove_failure_sanitizes_paths(monkeypatch, qapp) -> None:
    captured: list[tuple[str, str]] = []

    def _critical(_parent, title: str, text: str) -> None:
        captured.append((title, text))

    fake_dialog = SimpleNamespace(
        _backend_ok_or_warn=lambda: True,
        _model=SimpleNamespace(
            group_row_snapshot=lambda row: {
                "study_uid": "1.2.3",
                "study_root_path": "relative/study",
                "instance_count": 7,
                "patient_name": "Jane^Doe",
            }
        ),
        _service=SimpleNamespace(
            delete_grouped_study=lambda study_uid, study_root: (_ for _ in ()).throw(
                RuntimeError("Failed to remove C:\\Users\\alice\\Desktop\\study")
            )
        ),
        _run_browse=lambda reset, strict_dates: None,
    )

    monkeypatch.setattr(
        study_index_dialog.QMessageBox,
        "question",
        staticmethod(lambda *args, **kwargs: study_index_dialog.QMessageBox.StandardButton.Yes),
    )
    monkeypatch.setattr(study_index_dialog.QMessageBox, "critical", staticmethod(_critical))

    study_index_dialog.StudyIndexSearchDialog._remove_study_at_row(fake_dialog, 0)

    assert captured
    title, text = captured[0]
    assert title == "Study index"
    assert "Remove failed" in text
    assert "C:\\Users\\alice\\Desktop\\study" not in text
    assert "[REDACTED]" in text

"""Additional focused coverage for ScreenshotExportDialog choices and handoffs."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QMessageBox, QWidget

from gui.dialogs.screenshot_export_dialog import ScreenshotExportDialog
from utils.config_manager import ConfigManager


class _Viewer(QWidget):
    def __init__(self, has_image: bool) -> None:
        super().__init__()
        self.image_item = object() if has_image else None

    def viewport(self) -> _Viewer:
        return self

    def grab(self) -> QPixmap:
        pixmap = QPixmap(8, 6)
        pixmap.fill()
        return pixmap


class _Subwindow:
    def __init__(self, has_image: bool) -> None:
        self.image_viewer = _Viewer(has_image)
        self.focus_border_calls: list[bool] = []

    def set_suppress_focus_border_for_export(self, suppress: bool) -> None:
        self.focus_border_calls.append(suppress)


def _config(tmp_path: Path) -> ConfigManager:
    config = ConfigManager()
    config.config_path = tmp_path / "config.json"
    config.config = config.default_config.copy()
    return config


def _dialog(tmp_path: Path, subwindows: list[_Subwindow] | None = None) -> ScreenshotExportDialog:
    return ScreenshotExportDialog(
        subwindows or [_Subwindow(True), _Subwindow(False)],
        config_manager=_config(tmp_path),
    )


@pytest.mark.qt
def test_mode_choices_toggle_subwindow_options_and_mode(qapp, tmp_path) -> None:
    dlg = _dialog(tmp_path)

    assert dlg._current_export_mode() == dlg.MODE_SEPARATE
    assert dlg._subwindow_group.isEnabled()
    assert dlg._checkboxes[0].isEnabled()
    assert not dlg._checkboxes[1].isEnabled()

    dlg._radio_composite.setChecked(True)
    assert dlg._current_export_mode() == dlg.MODE_COMPOSITE
    assert not dlg._subwindow_group.isEnabled()
    assert "always includes" in dlg._subwindow_group.toolTip()

    dlg._radio_full.setChecked(True)
    assert dlg._current_export_mode() == dlg.MODE_FULL_WINDOW
    assert not dlg._subwindow_group.isEnabled()
    assert "entire application" in dlg._subwindow_group.toolTip()

    dlg._radio_separate.setChecked(True)
    assert dlg._current_export_mode() == dlg.MODE_SEPARATE
    assert dlg._subwindow_group.isEnabled()
    assert dlg._subwindow_group.toolTip() == ""


@pytest.mark.qt
def test_field_choices_update_export_state_and_output_names(qapp, tmp_path) -> None:
    dlg = _dialog(tmp_path)
    dlg.output_path = str(tmp_path)

    dlg.prefix_edit.setText("")
    dlg.format_combo.setCurrentText("JPG")
    dlg.resolution_combo.setCurrentIndex(2)
    dlg.include_annotations_cb.setChecked(False)
    dlg._checkboxes[1].setChecked(False)

    assert dlg.prefix == "screenshot"
    assert dlg.format == "JPG"
    assert dlg.export_scale == pytest.approx(2.0)
    assert dlg.include_annotations is False
    assert dlg._selected_indices() == [0]
    assert dlg._paths_for_overwrite_prompt("series", ".jpg", dlg.MODE_SEPARATE) == [
        str(tmp_path / "series_view1.jpg")
    ]
    assert dlg._paths_for_overwrite_prompt("series", ".jpg", dlg.MODE_COMPOSITE) == [
        str(tmp_path / "series_grid.jpg")
    ]
    assert dlg._paths_for_overwrite_prompt("series", ".jpg", dlg.MODE_FULL_WINDOW) == [
        str(tmp_path / "series_fullwindow.jpg")
    ]


@pytest.mark.qt
def test_browse_selected_directory_updates_label(qapp, tmp_path, monkeypatch) -> None:
    selected = tmp_path / "chosen"
    selected.mkdir()
    monkeypatch.setattr(
        "gui.dialogs.screenshot_export_dialog.QFileDialog.getExistingDirectory",
        lambda *args, **kwargs: str(selected),
    )
    dlg = _dialog(tmp_path)

    dlg._browse()

    assert dlg.output_path == str(selected)
    assert dlg.path_label.text() == str(selected)


@pytest.mark.qt
def test_export_requires_directory_then_requires_selected_view(qapp, tmp_path, monkeypatch) -> None:
    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda _parent, title, text: warnings.append((title, text)),
    )
    dlg = _dialog(tmp_path)

    dlg._on_export()
    assert warnings[-1] == ("No directory", "Please select an output directory.")

    dlg.output_path = str(tmp_path)
    dlg._checkboxes[0].setChecked(False)
    dlg._on_export()
    assert warnings[-1] == ("No selection", "Please select at least one view to export.")


@pytest.mark.qt
def test_existing_destination_can_cancel_without_exporting(qapp, tmp_path, monkeypatch) -> None:
    destination = tmp_path / "screenshot_view1.png"
    destination.write_bytes(b"synthetic")
    questions: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda _parent, title, text, *_args: questions.append(text)
        and QMessageBox.StandardButton.No,
    )
    dlg = _dialog(tmp_path)
    dlg.output_path = str(tmp_path)
    dlg._export_separate = MagicMock()  # type: ignore[method-assign]

    dlg._on_export()

    assert len(questions) == 1
    dlg._export_separate.assert_not_called()
    assert dlg.result() == int(dlg.DialogCode.Rejected)


@pytest.mark.qt
def test_successful_export_persists_destination_and_accepts(qapp, tmp_path, monkeypatch) -> None:
    messages: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda _parent, title, text: messages.append((title, text)),
    )
    dlg = _dialog(tmp_path)
    dlg.output_path = str(tmp_path)
    dlg.prefix_edit.setText("synthetic")
    dlg._export_separate = MagicMock(return_value=(1, None, ["scale note"]))  # type: ignore[method-assign]

    dlg._on_export()

    dlg._export_separate.assert_called_once_with("synthetic", ".png", [0])
    assert messages[0][0] == "Export complete"
    assert "scale note" in messages[0][1]
    assert dlg.config_manager.get_last_export_path() == str(tmp_path)
    assert dlg.result() == int(dlg.DialogCode.Accepted)


@pytest.mark.qt
def test_export_result_error_warns_and_keeps_dialog_open(qapp, tmp_path, monkeypatch) -> None:
    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda _parent, title, text: warnings.append((title, text)),
    )
    dlg = _dialog(tmp_path)
    dlg.output_path = str(tmp_path)
    dlg._export_composite = MagicMock(  # type: ignore[method-assign]
        return_value=(0, "Synthetic writer failure", [])
    )
    dlg._radio_composite.setChecked(True)

    dlg._on_export()

    assert warnings == [("Export incomplete", "Synthetic writer failure")]
    assert dlg.result() == int(dlg.DialogCode.Rejected)
    assert all(sw.focus_border_calls == [True, False] for sw in dlg.subwindows)


@pytest.mark.qt
def test_export_exception_reports_sanitized_failure_and_restores_focus_borders(
    qapp, tmp_path, monkeypatch
) -> None:
    failures: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        lambda _parent, title, text: failures.append((title, text)),
    )
    dlg = _dialog(tmp_path)
    dlg.output_path = str(tmp_path)
    dlg._export_separate = MagicMock(  # type: ignore[method-assign]
        side_effect=RuntimeError(f"could not write {tmp_path / 'secret.png'}")
    )

    dlg._on_export()

    assert failures[0][0] == "Export failed"
    assert "[REDACTED]" in failures[0][1]
    assert str(tmp_path) not in failures[0][1]
    assert all(sw.focus_border_calls == [True, False] for sw in dlg.subwindows)
    assert dlg.result() == int(dlg.DialogCode.Rejected)


@pytest.mark.qt
def test_full_window_mode_ignores_view_selection_and_accepts_mock_result(qapp, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(QMessageBox, "information", lambda *args: None)
    dlg = _dialog(tmp_path)
    dlg.output_path = str(tmp_path)
    dlg._checkboxes[0].setChecked(False)
    dlg._export_full_window = MagicMock(return_value=(1, None, []))  # type: ignore[method-assign]
    dlg._radio_full.setChecked(True)

    dlg._on_export()

    dlg._export_full_window.assert_called_once_with("screenshot", ".png")
    assert dlg.result() == int(dlg.DialogCode.Accepted)

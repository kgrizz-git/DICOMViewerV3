"""Final bounded coverage for ScreenshotExportDialog capture and writer seams."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QMessageBox, QWidget

from gui.dialogs.screenshot_export_dialog import ScreenshotExportDialog
from utils.config_manager import ConfigManager


class _Viewport:
    def __init__(self, pixmap: QPixmap) -> None:
        self.pixmap = pixmap

    def grab(self) -> QPixmap:
        return self.pixmap


class _Viewer:
    def __init__(self, pixmap: QPixmap | None) -> None:
        self.image_item = object()
        self._viewport = _Viewport(pixmap or QPixmap())

    def viewport(self) -> _Viewport:
        return self._viewport


class _Subwindow:
    def __init__(self, viewer: _Viewer | None) -> None:
        self.image_viewer = viewer


class _Layout:
    def __init__(self, pixmap: QPixmap | None, cells: list[tuple[int, int, int]]) -> None:
        self.pixmap = pixmap
        self.cells = cells

    def grab_layout_grid_pixmap(self) -> QPixmap | None:
        return self.pixmap

    def get_screenshot_grid_cells(self) -> list[tuple[int, int, int]]:
        return self.cells


class _Window(QWidget):
    def __init__(self, pixmap: QPixmap) -> None:
        super().__init__()
        self.pixmap = pixmap

    def grab(self) -> QPixmap:
        return self.pixmap


def _config(tmp_path: Path) -> ConfigManager:
    config = ConfigManager()
    config.config_path = tmp_path / "config.json"
    config.config = config.default_config.copy()
    return config


def _dialog(tmp_path: Path, subwindows=None, parent=None, layout=None) -> ScreenshotExportDialog:
    return ScreenshotExportDialog(
        subwindows or [], config_manager=_config(tmp_path), multi_window_layout=layout, parent=parent
    )


def _pixmap(width: int = 8, height: int = 6) -> QPixmap:
    pixmap = QPixmap(width, height)
    pixmap.fill()
    return pixmap


@pytest.mark.qt
def test_capture_and_viewport_guards_handle_invalid_and_unloaded_views(qapp, tmp_path) -> None:
    dlg = _dialog(tmp_path, [_Subwindow(None), _Subwindow(_Viewer(_pixmap()))])

    assert dlg._grab_viewport(-1) is None
    assert dlg._grab_viewport(2) is None
    assert dlg._grab_viewport(0) is None
    assert dlg._grab_viewport(1).size() == _pixmap().size()
    assert dlg._viewport_for_view(-1) is None
    assert dlg._viewport_for_view(2) is None
    assert dlg._viewport_for_view(0) is None
    assert dlg._viewport_for_view(1) is not None


@pytest.mark.qt
def test_scale_controls_resize_pixmap_and_qimage_with_cap_note(qapp, tmp_path) -> None:
    dlg = _dialog(tmp_path)
    dlg.export_scale = 2.0

    scaled, note = dlg._scale_pixmap_for_export(_pixmap(10, 5))
    image, image_note = dlg._scale_qimage_for_export(QImage(10, 5, QImage.Format.Format_ARGB32))
    assert scaled.size().width() == 20
    assert scaled.size().height() == 10
    assert note is None
    assert image.size().width() == 20
    assert image.size().height() == 10
    assert image_note is None

    capped, capped_note = dlg._scale_pixmap_for_export(_pixmap(5000, 2))
    assert capped.width() <= 8192
    assert capped_note is not None
    assert "8192" in capped_note


@pytest.mark.qt
def test_separate_writer_skips_null_capture_and_saves_valid_view(qapp, tmp_path) -> None:
    dlg = _dialog(tmp_path, [_Subwindow(_Viewer(_pixmap())), _Subwindow(_Viewer(None))])
    dlg.output_path = str(tmp_path)

    saved, error, notes = dlg._export_separate("synthetic", ".png", [0, 1])

    assert (saved, error, notes) == (1, None, [])
    assert (tmp_path / "synthetic_view1.png").is_file()
    assert not (tmp_path / "synthetic_view2.png").exists()


@pytest.mark.qt
def test_composite_preconditions_return_actionable_errors(qapp, tmp_path) -> None:
    no_layout = _dialog(tmp_path)
    assert no_layout._export_composite("grid", ".png") == (
        0,
        "Composite export requires layout information (internal error).",
        [],
    )

    empty_layout = _dialog(tmp_path, layout=_Layout(None, []))
    assert empty_layout._export_composite_tiled_fallback("grid", ".png") == (
        0,
        "No grid cells for composite export.",
        [],
    )


@pytest.mark.qt
def test_composite_pixmap_writer_uses_jpg_destination(qapp, tmp_path) -> None:
    layout = _Layout(_pixmap(7, 4), [(0, 0, 0)])
    dlg = _dialog(tmp_path, layout=layout)
    dlg.output_path = str(tmp_path)

    saved, error, notes = dlg._export_composite("grid", ".jpg")

    assert (saved, error, notes) == (1, None, [])
    assert (tmp_path / "grid_grid.jpg").is_file()


@pytest.mark.qt
def test_full_window_guards_report_missing_parent_and_failed_grab(qapp, tmp_path) -> None:
    no_parent = _dialog(tmp_path)
    assert no_parent._export_full_window("full", ".png") == (
        0,
        "No parent window for full-window capture.",
        [],
    )

    window = _Window(QPixmap())
    failed_grab = _dialog(tmp_path, parent=window)
    assert failed_grab._export_full_window("full", ".png") == (
        0,
        "Full-window grab failed.",
        [],
    )


@pytest.mark.qt
def test_partial_result_warns_then_accepts_with_saved_count(qapp, tmp_path, monkeypatch) -> None:
    messages: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda _parent, title, text: messages.append((title, text)),
    )
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda _parent, title, text: messages.append((title, text)),
    )
    dlg = _dialog(tmp_path, [_Subwindow(_Viewer(_pixmap()))])
    dlg.output_path = str(tmp_path)
    dlg._export_separate = MagicMock(  # type: ignore[method-assign]
        return_value=(1, "One synthetic view failed", ["requested scale note"])
    )

    dlg._on_export()

    assert messages[0] == ("Export incomplete", "One synthetic view failed")
    assert messages[1][0] == "Export complete"
    assert "requested scale note" in messages[1][1]
    assert dlg.result() == int(dlg.DialogCode.Accepted)

"""
Signal-to-slot wiring smoke tests for DICOMViewerApp (Phase 0 safety net).

Pins representative ``wire_all_signals`` entry points on the current monolithic
``main.py`` without duplicating coverage in ``test_main_signals_view.py``.
"""

from __future__ import annotations

import pytest
from main_test_helpers import with_test_config_manager

import main as main_module


@pytest.mark.qt
def test_layout_changed_signal_invokes_on_layout_changed(tmp_path, monkeypatch):
    """``multi_window_layout.layout_changed`` must reach ``_on_layout_changed``."""
    restore, _ = with_test_config_manager(tmp_path)
    calls: list[str] = []

    def _spy(layout_mode: str) -> None:
        calls.append(layout_mode)

    try:
        app = main_module.DICOMViewerApp()
        monkeypatch.setattr(app, "_on_layout_changed", _spy)
        app.multi_window_layout.layout_changed.emit("2x1")
        assert calls == ["2x1"]
    finally:
        restore()


@pytest.mark.qt
def test_main_window_layout_changed_signal_invokes_handler(tmp_path, monkeypatch):
    """``main_window.layout_changed`` must reach ``_on_main_window_layout_changed``."""
    restore, _ = with_test_config_manager(tmp_path)
    calls: list[str] = []

    def _spy(layout_mode: str) -> None:
        calls.append(layout_mode)

    try:
        app = main_module.DICOMViewerApp()
        monkeypatch.setattr(app, "_on_main_window_layout_changed", _spy)
        app.main_window.layout_changed.emit("1x2")
        assert calls == ["1x2"]
    finally:
        restore()


@pytest.mark.qt
def test_open_file_requested_signal_invokes_open_files(tmp_path, monkeypatch):
    """``main_window.open_file_requested`` must reach ``_open_files``."""
    restore, _ = with_test_config_manager(tmp_path)
    called: list[bool] = []

    def _spy() -> None:
        called.append(True)

    try:
        app = main_module.DICOMViewerApp()
        monkeypatch.setattr(app, "_open_files", _spy)
        app.main_window.open_file_requested.emit()
        assert called == [True]
    finally:
        restore()


@pytest.mark.qt
def test_open_files_from_paths_signal_forwards_paths(tmp_path, monkeypatch):
    """``open_files_from_paths_requested`` must forward the path list to the slot."""
    restore, _ = with_test_config_manager(tmp_path)
    received: list[list[str]] = []

    def _spy(paths: list[str]) -> None:
        received.append(list(paths))

    try:
        app = main_module.DICOMViewerApp()
        monkeypatch.setattr(app, "_open_files_from_paths", _spy)
        paths = ["/tmp/a.dcm", "/tmp/b.dcm"]
        app.main_window.open_files_from_paths_requested.emit(paths)
        assert received == [paths]
    finally:
        restore()


@pytest.mark.qt
def test_focused_subwindow_changed_signal_invokes_handler(tmp_path, monkeypatch):
    """``focused_subwindow_changed`` must reach ``_on_focused_subwindow_changed``."""
    restore, _ = with_test_config_manager(tmp_path)
    received: list[object] = []

    def _spy(subwindow: object) -> None:
        received.append(subwindow)

    try:
        app = main_module.DICOMViewerApp()
        monkeypatch.setattr(app, "_on_focused_subwindow_changed", _spy)
        subwindow = app.multi_window_layout.subwindows[0]
        app.multi_window_layout.focused_subwindow_changed.emit(subwindow)
        assert received == [subwindow]
    finally:
        restore()


@pytest.mark.qt
def test_export_requested_signal_invokes_open_export(tmp_path, monkeypatch):
    """``export_requested`` must reach ``_open_export`` (dialog wiring smoke)."""
    restore, _ = with_test_config_manager(tmp_path)
    called: list[bool] = []

    def _spy() -> None:
        called.append(True)

    try:
        app = main_module.DICOMViewerApp()
        monkeypatch.setattr(app, "_open_export", _spy)
        app.main_window.export_requested.emit()
        assert called == [True]
    finally:
        restore()


@pytest.mark.qt
def test_close_series_requested_signal_forwards_args(tmp_path, monkeypatch):
    """Series navigator close signal must reach ``_close_series`` with UIDs."""
    restore, _ = with_test_config_manager(tmp_path)
    received: list[tuple[str, str]] = []

    def _spy(study_uid: str, series_key: str) -> None:
        received.append((study_uid, series_key))

    try:
        app = main_module.DICOMViewerApp()
        monkeypatch.setattr(app, "_close_series", _spy)
        app.series_navigator.close_series_requested.emit("study-1", "series-1")
        assert received == [("study-1", "series-1")]
    finally:
        restore()

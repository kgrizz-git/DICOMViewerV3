"""
Signal-to-slot wiring smoke tests for DICOMViewerApp (Phase 0 safety net).

Pins representative ``wire_all_signals`` entry points on the current monolithic
``main.py`` without duplicating coverage in ``test_main_signals_view.py``.

Six of the seven tests exercise the individual ``_wire_*`` helpers in
``gui.app_signal_wiring`` using lightweight ``QObject`` signal stubs so that
xdist workers never need to construct the real ``DICOMViewerApp``.  The
remaining test constructs the real app once to anchor the smoke suite.
"""

from __future__ import annotations

import pytest
from main_test_helpers import viewer_app
from PySide6.QtCore import QObject, Signal

from gui.app_signal_wiring import (
    _wire_dialog_signals,
    _wire_file_signals,
    _wire_layout_signals,
)

# ---------------------------------------------------------------------------
# Lightweight stubs (QObject-based so PySide6 signals work without QApplication)
# ---------------------------------------------------------------------------

class SlotRecorder:
    """Callable that records every invocation for assertion."""

    def __init__(self) -> None:
        self.calls: list = []

    def __call__(self, *args: object) -> None:
        self.calls.append(args if len(args) > 1 else args[0] if args else ())


# ---- Per-function signal collaborators (carry only Qt signals) ----

class MultiWindowLayoutStub(QObject):
    layout_changed = Signal(str)
    focused_subwindow_changed = Signal(object)


class MainWindowStub(QObject):
    layout_changed = Signal(str)
    open_file_requested = Signal()
    open_folder_requested = Signal()
    open_recent_file_requested = Signal()
    open_files_from_paths_requested = Signal(list)
    close_requested = Signal()
    export_requested = Signal()
    # Every signal _wire_dialog_signals touches must exist on the stub.
    settings_requested = Signal()
    overlay_settings_requested = Signal()
    tag_viewer_requested = Signal()
    study_index_search_requested = Signal()
    overlay_config_requested = Signal()
    annotation_options_requested = Signal()
    quick_start_guide_requested = Signal()
    keyboard_shortcuts_requested = Signal()
    _apply_wl_preset_requested = Signal()
    user_documentation_requested = Signal()
    fusion_technical_doc_requested = Signal()
    tag_export_requested = Signal()
    histogram_requested = Signal()
    structured_report_browser_requested = Signal()
    export_roi_statistics_requested = Signal()
    acr_ct_phantom_requested = Signal()
    acr_ct_batch_requested = Signal()
    acr_mri_phantom_requested = Signal()
    acr_mri_batch_requested = Signal()
    nuclear_qc_requested = Signal()
    deep_anonymizer_export_requested = Signal()
    export_screenshots_requested = Signal()
    save_mpr_dicom_requested = Signal()
    export_cine_video_requested = Signal()
    about_this_file_requested = Signal()
    create_mpr_view_requested = Signal()
    create_3d_view_requested = Signal()


class DialogCoordinatorStub(QObject):
    open_histogram = lambda self: None  # noqa: E731


class MprControllerStub(QObject):
    open_mpr_dialog = lambda self, idx: None  # noqa: E731


class VolumeRenderFacadeStub(QObject):
    launch_3d_view = lambda self: None  # noqa: E731


class SeriesNavigatorStub(QObject):
    close_series_requested = Signal(str, str)
    close_study_requested = Signal()
    mpr_thumbnail_clicked = Signal()
    mpr_thumbnail_clear_requested = Signal()


class FakeQApp(QObject):
    """Bare stand-in for ``app.app`` (the QApplication) — provides ``aboutToQuit``."""
    aboutToQuit = Signal()  # noqa: N815 – must match Qt signal name


# ---- One real-app smoke test (Phase 0 anchor) ----

@pytest.mark.qt
def test_layout_changed_signal_invokes_on_layout_changed(tmp_path, monkeypatch):
    """``multi_window_layout.layout_changed`` must reach ``_on_layout_changed``.

    Constructs the real DICOMViewerApp once to anchor the smoke suite.
    """
    calls: list[str] = []

    def _spy(layout_mode: str) -> None:
        calls.append(layout_mode)

    with viewer_app(tmp_path) as app:
        monkeypatch.setattr(app, "_on_layout_changed", _spy)
        app.multi_window_layout.layout_changed.emit("2x1")
        assert calls == ["2x1"]


# ---- Stub-based wiring tests (no DICOMViewerApp construction) ----

def _build_layout_app():
    """Create a minimal app-like object for ``_wire_layout_signals``."""
    mw = MainWindowStub()
    mwl = MultiWindowLayoutStub()
    on_layout = SlotRecorder()
    on_main_window_layout = SlotRecorder()
    on_focused = SlotRecorder()

    class _App:
        main_window = mw
        multi_window_layout = mwl
        _on_layout_changed = on_layout
        _on_main_window_layout_changed = on_main_window_layout
        _on_focused_subwindow_changed = on_focused

    return _App(), mw, mwl, on_layout, on_main_window_layout, on_focused


@pytest.mark.qt
def test_main_window_layout_changed_signal_invokes_handler():
    """``_wire_layout_signals`` connects ``main_window.layout_changed`` to the handler."""
    app, mw, mwl, _, on_main_window_layout, _ = _build_layout_app()
    _wire_layout_signals(app)  # type: ignore[arg-type]
    mw.layout_changed.emit("1x2")
    assert on_main_window_layout.calls == ["1x2"]


@pytest.mark.qt
def test_focused_subwindow_changed_signal_invokes_handler():
    """``_wire_layout_signals`` connects ``focused_subwindow_changed`` to the handler."""
    app, mw, mwl, _, _, on_focused = _build_layout_app()
    _wire_layout_signals(app)  # type: ignore[arg-type]
    sentinel = object()
    mwl.focused_subwindow_changed.emit(sentinel)
    assert on_focused.calls == [sentinel]


def _build_file_app():
    """Create a minimal app-like object for ``_wire_file_signals``."""
    mw = MainWindowStub()
    open_files = SlotRecorder()
    open_from_paths = SlotRecorder()

    class _App:
        main_window = mw
        app = FakeQApp()
        _open_files = open_files
        _open_files_from_paths = open_from_paths
        _open_folder = lambda self: None  # noqa: E731
        _open_recent_file = lambda self: None  # noqa: E731
        _close_files = lambda self: None  # noqa: E731
        _on_app_about_to_quit = lambda self: None  # noqa: E731

    return _App(), mw, open_files, open_from_paths


@pytest.mark.qt
def test_open_file_requested_signal_invokes_open_files():
    """``_wire_file_signals`` connects ``main_window.open_file_requested`` to the handler."""
    app, mw, open_files, _ = _build_file_app()
    _wire_file_signals(app)  # type: ignore[arg-type]
    mw.open_file_requested.emit()
    assert open_files.calls == [()]


@pytest.mark.qt
def test_open_files_from_paths_signal_forwards_paths():
    """``_wire_file_signals`` forwards the path list from ``open_files_from_paths_requested``."""
    app, mw, _, open_from_paths = _build_file_app()
    _wire_file_signals(app)  # type: ignore[arg-type]
    paths = ["/tmp/a.dcm", "/tmp/b.dcm"]
    mw.open_files_from_paths_requested.emit(paths)
    assert open_from_paths.calls == [paths]


def _build_dialog_app():
    """Create a minimal app-like object for ``_wire_dialog_signals``."""
    mw = MainWindowStub()
    sn = SeriesNavigatorStub()
    dc = DialogCoordinatorStub()
    open_export = SlotRecorder()
    close_series = SlotRecorder()

    class _App:
        main_window = mw
        series_navigator = sn
        dialog_coordinator = dc
        _mpr_controller = MprControllerStub()
        _volume_render_facade = VolumeRenderFacadeStub()
        # Slot recorders for the two signals under test
        _open_export = open_export
        _close_series = close_series
        # Remaining slots wired by _wire_dialog_signals — no-ops
        _open_settings = lambda self: None  # noqa: E731
        _open_overlay_settings = lambda self: None  # noqa: E731
        _open_tag_viewer = lambda self: None  # noqa: E731
        _open_study_index_search = lambda self: None  # noqa: E731
        _open_overlay_config = lambda self: None  # noqa: E731
        _open_annotation_options = lambda self: None  # noqa: E731
        _open_quick_start_guide = lambda self: None  # noqa: E731
        _on_keyboard_shortcuts_requested = lambda self: None  # noqa: E731
        _on_window_level_preset_selected = lambda self, *_a: None  # noqa: E731
        _open_user_documentation_in_browser = lambda self: None  # noqa: E731
        _open_fusion_technical_doc = lambda self: None  # noqa: E731
        _open_tag_export = lambda self: None  # noqa: E731
        _open_structured_report_browser = lambda self: None  # noqa: E731
        _open_export_roi_statistics = lambda self: None  # noqa: E731
        _open_acr_ct_phantom_analysis = lambda self: None  # noqa: E731
        _open_acr_ct_batch_analysis = lambda self: None  # noqa: E731
        _open_acr_mri_phantom_analysis = lambda self: None  # noqa: E731
        _open_acr_mri_batch_analysis = lambda self: None  # noqa: E731
        _open_nuclear_qc_analysis = lambda self: None  # noqa: E731
        _open_deep_anonymizer_export = lambda self: None  # noqa: E731
        _open_export_screenshots = lambda self: None  # noqa: E731
        _on_save_mpr_as_dicom = lambda self: None  # noqa: E731
        _on_export_cine_video = lambda self: None  # noqa: E731
        _open_about_this_file = lambda self: None  # noqa: E731
        _close_study = lambda self: None  # noqa: E731
        _on_mpr_thumbnail_clicked = lambda self, *_a: None  # noqa: E731
        _on_mpr_clear_from_navigator_thumbnail = lambda self, *_a: None  # noqa: E731

    return _App(), mw, sn, open_export, close_series


@pytest.mark.qt
def test_export_requested_signal_invokes_open_export():
    """``_wire_dialog_signals`` connects ``main_window.export_requested`` to the handler."""
    app, mw, sn, open_export, _ = _build_dialog_app()
    _wire_dialog_signals(app)  # type: ignore[arg-type]
    mw.export_requested.emit()
    assert open_export.calls == [()]


@pytest.mark.qt
def test_close_series_requested_signal_forwards_args():
    """``_wire_dialog_signals`` connects ``series_navigator.close_series_requested`` with UIDs."""
    app, mw, sn, _, close_series = _build_dialog_app()
    _wire_dialog_signals(app)  # type: ignore[arg-type]
    sn.close_series_requested.emit("study-1", "series-1")
    assert close_series.calls == [("study-1", "series-1")]

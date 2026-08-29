"""Tests for VolumeRenderDialog lifecycle seams without native rendering."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pydicom.dataset import Dataset
from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QDialog, QLabel, QMessageBox, QWidget

from gui.dialogs.volume_render_dialog import (
    VolumeRenderDialog,
    _initial_dialog_size_for_screen,
    _VolumeBuilderWorker,
)


def _dialog(monkeypatch, qapp, datasets=None, config_manager=None) -> VolumeRenderDialog:
    """Build only the initial Qt UI; worker/native rendering is covered by slots."""
    monkeypatch.setattr(VolumeRenderDialog, "_start_build", lambda self: None)
    dialog = VolumeRenderDialog(
        datasets or [], "Synthetic series", config_manager=config_manager
    )
    dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
    return dialog


@pytest.mark.qt
def test_initial_ui_uses_title_default_geometry_and_progress_widget(qapp, monkeypatch) -> None:
    monkeypatch.setattr(
        "gui.dialogs.volume_render_dialog._initial_dialog_size",
        lambda: QSize(1200, 850),
    )
    dialog = _dialog(monkeypatch, qapp)

    try:
        assert dialog.windowTitle() == "3D Volume Render — Synthetic series"
        assert dialog.isModal() is False
        assert dialog.size() == QSize(1200, 850)
        assert dialog._progress_label.text() == "Building 3D volume…"
        assert dialog._progress_bar.minimum() == 0
        assert dialog._progress_bar.maximum() == 0
    finally:
        dialog.close()


@pytest.mark.parametrize(
    ("available", "expected"),
    [
        (QRect(0, 0, 1512, 982), QSize(756, 756)),
        (QRect(0, 0, 3440, 1440), QSize(1440, 1440)),
        (QRect(0, 0, 800, 600), QSize(480, 480)),
        (None, QSize(800, 800)),
    ],
)
def test_initial_dialog_size_uses_screen_fraction_and_bounds(available, expected) -> None:
    assert _initial_dialog_size_for_screen(available) == expected


@pytest.mark.qt
def test_initial_ui_restores_valid_saved_geometry(qapp, monkeypatch) -> None:
    config = MagicMock()
    config.get.return_value = "c3ludGhldGljLWdlb21ldHJ5"
    restore = MagicMock(return_value=True)
    monkeypatch.setattr(QDialog, "restoreGeometry", restore)

    dialog = _dialog(monkeypatch, qapp, config_manager=config)

    try:
        config.get.assert_called_once_with("volume_render_dialog/geometry")
        restore.assert_called_once()
        assert bytes(restore.call_args.args[0]) == b"synthetic-geometry"
        assert dialog.size().width() != 900
    finally:
        dialog.close()


@pytest.mark.qt
def test_release_worker_waits_and_clears_reference(qapp, monkeypatch) -> None:
    dialog = _dialog(monkeypatch, qapp)
    worker = MagicMock()
    dialog._worker = worker

    try:
        dialog._release_worker()

        worker.wait.assert_called_once_with()
        assert dialog._worker is None
    finally:
        dialog.close()


@pytest.mark.qt
def test_volume_builder_worker_skips_work_after_cancellation(qapp, monkeypatch) -> None:
    worker = _VolumeBuilderWorker([Dataset()])
    worker.cancel()
    import core.mpr_volume

    build = MagicMock()
    monkeypatch.setattr(core.mpr_volume.MprVolume, "from_datasets", build)

    worker.run()

    build.assert_not_called()


@pytest.mark.qt
def test_volume_builder_worker_emits_prepared_volume_data(qapp, monkeypatch) -> None:
    worker = _VolumeBuilderWorker([Dataset()])
    volume = SimpleNamespace(sitk_image="synthetic-image", source_datasets=["source"])
    prepared = SimpleNamespace()
    emitted: list[object] = []
    worker.build_finished.connect(emitted.append)
    import core.mpr_volume
    import core.volume_renderer

    monkeypatch.setattr(
        core.mpr_volume.MprVolume, "from_datasets", lambda datasets: volume
    )
    prepare = MagicMock(return_value=prepared)
    monkeypatch.setattr(core.volume_renderer.VolumeRenderer, "prepare_volume_data", prepare)

    worker.run()

    prepare.assert_called_once_with(
        "synthetic-image", source_datasets=["source"], apply_rescale=True
    )
    assert emitted == [prepared]


@pytest.mark.qt
def test_volume_builder_worker_emits_sanitized_error_on_build_failure(qapp, monkeypatch) -> None:
    worker = _VolumeBuilderWorker([Dataset()])
    messages: list[str] = []
    worker.error.connect(messages.append)
    import core.mpr_volume

    monkeypatch.setattr(
        core.mpr_volume.MprVolume,
        "from_datasets",
        MagicMock(side_effect=RuntimeError("private synthetic detail")),
    )

    worker.run()

    assert messages == ["Failed to build 3D volume; details withheld"]


@pytest.mark.qt
def test_finished_build_replaces_progress_and_initializes_viewer(qapp, monkeypatch) -> None:
    dataset = Dataset()
    dataset.Modality = "CT"
    config = MagicMock()
    dialog = _dialog(monkeypatch, qapp, [dataset], config)
    worker = MagicMock()
    dialog._worker = worker

    class _Renderer:
        attached = None

        def attach_volume(self, volume_data) -> None:
            self.attached = volume_data

    class _Viewer(QWidget):
        def __init__(self, renderer, parent=None, config_manager=None) -> None:
            super().__init__(parent)
            self.renderer = renderer
            self.config_manager = config_manager
            self.initialized = None

        def initialize(self, **kwargs) -> None:
            self.initialized = kwargs

        def cleanup(self) -> None:
            pass

    import core.volume_renderer
    import gui.volume_viewer_widget

    monkeypatch.setattr(core.volume_renderer, "VolumeRenderer", _Renderer)
    monkeypatch.setattr(gui.volume_viewer_widget, "VolumeViewerWidget", _Viewer)
    volume_data = SimpleNamespace(rescale_applied=True, downsample_factor=2)

    try:
        dialog._on_build_finished(volume_data)

        worker.wait.assert_called_once_with()
        assert dialog._progress_container is None
        assert isinstance(dialog._viewer_widget, _Viewer)
        assert dialog._viewer_widget.renderer.attached is volume_data
        assert dialog._viewer_widget.initialized == {
            "modality": "CT",
            "rescale_applied": True,
        }
        notices = [
            dialog._layout.itemAt(index).widget().text()
            for index in range(dialog._layout.count())
            if isinstance(dialog._layout.itemAt(index).widget(), QLabel)
        ]
        assert any("downsampled 2×" in text for text in notices)
    finally:
        dialog.close()


@pytest.mark.qt
def test_finished_build_warns_when_frames_are_not_spatial(qapp, monkeypatch) -> None:
    dataset = SimpleNamespace(Modality="MR", _original_dataset=object())
    dialog = _dialog(monkeypatch, qapp, [dataset])
    dialog._worker = MagicMock()

    class _Renderer:
        def attach_volume(self, volume_data) -> None:
            pass

    class _Viewer(QWidget):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(kwargs["parent"])

        def initialize(self, **kwargs) -> None:
            pass

        def cleanup(self) -> None:
            pass

    import core.multiframe_handler
    import core.volume_renderer
    import gui.volume_viewer_widget

    monkeypatch.setattr(
        core.multiframe_handler,
        "classify_frame_type",
        lambda _dataset: core.multiframe_handler.FrameType.TEMPORAL,
    )
    monkeypatch.setattr(core.volume_renderer, "VolumeRenderer", _Renderer)
    monkeypatch.setattr(gui.volume_viewer_widget, "VolumeViewerWidget", _Viewer)

    try:
        dialog._on_build_finished(SimpleNamespace(rescale_applied=False))

        warnings = [
            dialog._layout.itemAt(index).widget().text()
            for index in range(dialog._layout.count())
            if isinstance(dialog._layout.itemAt(index).widget(), QWidget)
            and hasattr(dialog._layout.itemAt(index).widget(), "text")
        ]
        assert any("rather than spatial slices" in text for text in warnings)
    finally:
        dialog.close()


@pytest.mark.qt
def test_build_error_releases_worker_shows_sanitized_message_and_closes(
    qapp, monkeypatch
) -> None:
    dialog = _dialog(monkeypatch, qapp)
    worker = MagicMock()
    dialog._worker = worker
    shown: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        lambda _parent, title, text: shown.append((title, text)),
    )

    dialog._on_build_error("synthetic failure")
    qapp.processEvents()

    worker.wait.assert_called_once_with()
    assert dialog._worker is None
    assert shown == [
        ("3D Volume Render Error", "Could not build 3D volume:\n\nsynthetic failure")
    ]
    assert dialog.isVisible() is False


@pytest.mark.qt
def test_close_event_persists_geometry_cancels_worker_and_cleans_viewer(
    qapp, monkeypatch
) -> None:
    config = MagicMock()
    dialog = _dialog(monkeypatch, qapp, config_manager=config)
    worker = MagicMock()
    viewer = MagicMock()
    dialog._worker = worker
    dialog._viewer_widget = viewer
    event = QCloseEvent()

    dialog.closeEvent(event)

    config.set.assert_called_once()
    assert config.set.call_args.args[0] == "volume_render_dialog/geometry"
    assert isinstance(config.set.call_args.args[1], str)
    worker.cancel.assert_called_once_with()
    worker.quit.assert_called_once_with()
    worker.wait.assert_called_once_with(3000)
    viewer.cleanup.assert_called_once_with()
    assert dialog._worker is None
    assert dialog._viewer_widget is None

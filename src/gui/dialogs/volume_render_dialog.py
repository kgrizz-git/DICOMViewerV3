"""
Volume Render Dialog

Non-modal, resizable top-level window that hosts a ``VolumeViewerWidget``
for 3D volume rendering of a DICOM series.  Builds the ``MprVolume`` in a
background ``QThread`` (following the ``MprBuilderWorker`` pattern) and
shows a progress indicator during construction.

Note: This is intentionally a top-level ``QDialog`` (no *parent*) because
``QVTKRenderWindowInteractor`` creates a native child window that requires
its host to be a top-level widget on Windows.  Passing a parent would
trigger "QWidgetWindow must be a top level window" warnings and a blank
viewport.

Inputs:
    - ``List[pydicom.Dataset]`` — the series to render.
    - ``series_description`` — human-readable title string.

Outputs:
    - Interactive 3D volume rendering window.

Requirements:
    - PySide6
    - VTK >= 9.3.0
    - SimpleITK (for MprVolume)
"""

from __future__ import annotations

import logging
from typing import Any

from pydicom.dataset import Dataset
from PySide6.QtCore import QByteArray, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QMessageBox,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

_SETTINGS_GEOMETRY_KEY = "volume_render_dialog/geometry"

from utils.debug_flags import DEBUG_VOLUME_3D

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Background worker — builds MprVolume in a separate thread
# ---------------------------------------------------------------------------

class _VolumeBuilderWorker(QThread):
    """
    Background thread that builds an ``MprVolume`` from DICOM datasets and
    prepares volume data (numpy arrays + spatial metadata) for VTK.

    The expensive sitk-to-numpy conversion runs here so the main thread
    only needs to perform the fast VTK-attach step.

    Signals:
        build_finished (object, object): Emitted with ``(MprVolume, VolumeData)``
            on success.  Named to avoid shadowing ``QThread.finished``.
        error (str): Emitted with a human-readable error message on failure.
    """

    build_finished = Signal(object, object)
    error = Signal(str)

    def __init__(self, datasets: list[Dataset]) -> None:
        super().__init__()
        self._datasets = datasets
        self._cancelled = False

    def cancel(self) -> None:
        """Request cancellation (checked between steps)."""
        self._cancelled = True

    def run(self) -> None:
        try:
            from core.mpr_volume import MprVolume
            from core.volume_renderer import VolumeRenderer

            if self._cancelled:
                return
            volume = MprVolume.from_datasets(self._datasets)
            if self._cancelled:
                return
            # Perform the expensive sitk -> numpy conversion on the
            # background thread so the main thread stays responsive.
            volume_data = VolumeRenderer.prepare_volume_data(
                volume.sitk_image,
                source_datasets=volume.source_datasets,
                apply_rescale=True,
            )
            if self._cancelled:
                return
            self.build_finished.emit(volume, volume_data)
        except Exception:
            msg = "Failed to build 3D volume; details withheld"
            _log.error(msg)
            self.error.emit(msg)


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------

class VolumeRenderDialog(QDialog):
    """
    Non-modal top-level dialog for 3D volume rendering of a DICOM series.

    Created without a *parent* so the ``QVTKRenderWindowInteractor`` can
    host a native render window without "must be a top level window" errors
    on Windows.

    Usage::

        dlg = VolumeRenderDialog(datasets, "CT Chest")
        dlg.show()
    """

    def __init__(
        self,
        datasets: list[Dataset],
        series_description: str = "",
        parent: QWidget | None = None,
        config_manager: Any = None,
    ) -> None:
        # Intentionally do NOT pass parent to QDialog.  The VTK interactor
        # creates a native child window that requires its host to be a true
        # top-level widget.  We keep *parent* in the signature so the facade
        # call-site does not need to change.
        super().__init__(None)
        self._datasets = datasets
        self._series_description = series_description
        self._config_manager = config_manager
        self._worker: _VolumeBuilderWorker | None = None
        self._viewer_widget: Any = None  # VolumeViewerWidget, set after build

        self.setWindowTitle(f"3D Volume Render \u2014 {series_description}" if series_description else "3D Volume Render")
        self.setMinimumSize(480, 360)
        # Non-modal.
        self.setModal(False)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        # Restore remembered geometry if available; otherwise use a sensible
        # default that fits comfortably on a 1280\u00d7720 display.
        restored = False
        if self._config_manager is not None and hasattr(
            self._config_manager, "get"
        ):
            raw = self._config_manager.get(_SETTINGS_GEOMETRY_KEY)
            if raw:
                try:
                    self.restoreGeometry(QByteArray.fromBase64(raw.encode()))
                    restored = True
                except Exception:
                    pass
        if not restored:
            self.resize(900, 650)

        self._setup_ui()
        self._start_build()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        """Build the initial layout with a progress indicator."""
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

        # Progress container (replaced after build).
        self._progress_container = QWidget(self)
        progress_layout = QVBoxLayout(self._progress_container)
        progress_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._progress_label = QLabel("Building 3D volume\u2026", self._progress_container)
        self._progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        progress_layout.addWidget(self._progress_label)

        self._progress_bar = QProgressBar(self._progress_container)
        self._progress_bar.setRange(0, 0)  # indeterminate
        self._progress_bar.setFixedWidth(300)
        progress_layout.addWidget(self._progress_bar)

        self._layout.addWidget(self._progress_container)

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _start_build(self) -> None:
        """Launch the background volume build."""
        self._worker = _VolumeBuilderWorker(self._datasets)
        self._worker.build_finished.connect(self._on_build_finished)
        self._worker.error.connect(self._on_build_error)
        self._worker.start()

    def _release_worker(self) -> None:
        """Safely tear down the build worker.

        The build_finished/error signals are emitted as the last action of
        ``run()`` and delivered to the main thread via a queued connection, so
        when these slots run the worker thread is finishing but may still be
        briefly alive at the C++ level.  We must ``wait()`` for it to fully
        terminate before dropping the last Python reference; otherwise the
        QThread is destroyed while still running ("QThread: Destroyed while
        thread is still running"), which aborts the process.
        """
        worker = self._worker
        if worker is not None:
            worker.wait()
        self._worker = None

    def _on_build_finished(self, volume: Any, volume_data: Any) -> None:
        """Handle successful volume construction.

        ``volume_data`` is a :class:`VolumeData` prepared on the background
        thread so that only the fast VTK-attach step runs here on the main
        thread.
        """
        self._release_worker()
        if DEBUG_VOLUME_3D:
            print(f"[DEBUG-VOLUME-3D] Volume build finished — sitk_image size: {volume.sitk_image.GetSize()}")

        # Remove progress indicator.
        if self._progress_container is not None:
            self._progress_container.setParent(None)
            self._progress_container.deleteLater()
        self._progress_container = None

        # Show warning banner for non-spatial multiframe datasets.
        if self._datasets and hasattr(self._datasets[0], '_original_dataset'):
            from core.multiframe_handler import FrameType, classify_frame_type
            original = self._datasets[0]._original_dataset
            frame_type = classify_frame_type(original)
            if frame_type != FrameType.SPATIAL:
                warning_label = QLabel(
                    f"Warning: These frames appear to be {frame_type.value} rather than "
                    "spatial slices. The 3D reconstruction may not be anatomically meaningful.",
                    self,
                )
                warning_label.setStyleSheet(
                    "background-color: #665500; color: #FFD700; padding: 6px; font-size: 12px;"
                )
                warning_label.setWordWrap(True)
                self._layout.addWidget(warning_label)

        # Determine the modality so the viewer can select the right default preset.
        modality: str = ""
        if self._datasets:
            modality = str(getattr(self._datasets[0], "Modality", "") or "")

        try:
            from core.volume_renderer import VolumeRenderer
            from gui.volume_viewer_widget import VolumeViewerWidget

            renderer = VolumeRenderer()
            # Use attach_volume() with pre-computed data (numpy work already
            # done on the background thread by _VolumeBuilderWorker).
            renderer.attach_volume(volume_data)
            if DEBUG_VOLUME_3D:
                print(f"[DEBUG-VOLUME-3D] VolumeRenderer.attach_volume() complete.  modality={modality!r}")

            self._viewer_widget = VolumeViewerWidget(
                renderer,
                parent=self,
                config_manager=self._config_manager,
            )
            self._layout.addWidget(self._viewer_widget)
            if DEBUG_VOLUME_3D:
                print("[DEBUG-VOLUME-3D] VolumeViewerWidget added to layout, calling initialize().")
            self._viewer_widget.initialize(
                modality=modality,
                rescale_applied=bool(getattr(volume_data, "rescale_applied", False)),
            )
            if DEBUG_VOLUME_3D:
                print("[DEBUG-VOLUME-3D] VolumeViewerWidget.initialize() complete.")
        except Exception:
            _log.error("Failed to set up 3D renderer; details withheld")
            QMessageBox.critical(
                self,
                "3D Volume Render Error",
                "Failed to initialize 3D rendering. Details were withheld to protect private data.",
            )
            self.close()

    def _on_build_error(self, message: str) -> None:
        """Handle volume build failure."""
        self._release_worker()
        QMessageBox.critical(
            self,
            "3D Volume Render Error",
            f"Could not build 3D volume:\n\n{message}",
        )
        self.close()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def closeEvent(self, event: Any) -> None:
        """Cancel any running worker, save geometry, and clean up VTK resources."""
        if DEBUG_VOLUME_3D:
            import traceback as _tb
            print("[DEBUG-VOLUME-3D] VolumeRenderDialog.closeEvent() fired!")
            _tb.print_stack()
        # Persist dialog geometry so the next open restores size + position.
        if self._config_manager is not None and hasattr(
            self._config_manager, "set"
        ):
            try:
                geo_b64 = bytes(self.saveGeometry().toBase64().data()).decode()
                self._config_manager.set(_SETTINGS_GEOMETRY_KEY, geo_b64)
            except Exception:
                pass
        if self._worker is not None:
            self._worker.cancel()
            self._worker.quit()
            self._worker.wait(3000)
            self._worker = None
        if self._viewer_widget is not None:
            self._viewer_widget.cleanup()
            self._viewer_widget = None
        super().closeEvent(event)

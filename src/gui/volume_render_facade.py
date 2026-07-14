"""
GUI facade for launching 3D volume render dialogs from ``DICOMViewerApp``.

Validation logic lives in ``core.volume_render_eligibility`` (no gui imports).
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtWidgets import QApplication, QMessageBox

from core.volume_render_eligibility import (
    can_launch_3d_volume_render,
    get_datasets_for_subwindow,
)
from gui.dialogs.volume_render_dialog import VolumeRenderDialog

_log = logging.getLogger(__name__)


class VolumeRenderFacade:
    """Manages the lifecycle of 3D volume render dialogs."""

    def __init__(self, app: Any) -> None:
        self._app = app
        # Maps series_key -> VolumeRenderDialog to prevent duplicates.
        self._open_dialogs: dict[str, Any] = {}
        # Strong refs for all open dialogs (parentless dialogs would
        # otherwise be garbage-collected immediately by Python).
        self._alive: list[Any] = []

    def launch_3d_view(self, subwindow_idx: int | None = None) -> None:
        """
        Validate the target subwindow's series and open a 3D volume
        render dialog for it.

        Called from the toolbar / menu / context-menu action signals.
        """
        app = self._app
        ok, reason = can_launch_3d_volume_render(app, subwindow_idx)
        if not ok:
            title = "3D Volume Render"
            if "vtk" in reason.lower():
                QMessageBox.warning(
                    app.main_window,
                    "VTK Not Installed",
                    "3D volume rendering requires the 'vtk' package.\n\n"
                    "Install it with:\n  pip install vtk",
                )
            else:
                QMessageBox.information(app.main_window, title, reason)
            return

        focused_idx = (
            int(subwindow_idx)
            if subwindow_idx is not None
            else int(app.get_focused_subwindow_index())
        )
        datasets = get_datasets_for_subwindow(app, focused_idx)
        assert datasets is not None  # guarded by can_launch_3d_volume_render

        # Synthesize geometry for multiframe frame wrappers that lack IPP/IOP.
        from core.volume_render_eligibility import synthesize_frame_geometry
        if datasets and hasattr(datasets[0], '_original_dataset'):
            synthesize_frame_geometry(datasets)

        # Check for duplicate dialog.
        series_key = self._get_series_key(focused_idx)
        if series_key and series_key in self._open_dialogs:
            existing = self._open_dialogs[series_key]
            if existing is not None and existing.isVisible():
                existing.raise_()
                existing.activateWindow()
                return
            del self._open_dialogs[series_key]

        description = self._get_series_description(datasets)

        dialog = VolumeRenderDialog(
            datasets,
            series_description=description,
            parent=app.main_window,
            config_manager=getattr(app, "config_manager", None),
        )

        self._alive.append(dialog)
        if series_key:
            self._open_dialogs[series_key] = dialog

        def _on_destroyed() -> None:
            self._open_dialogs.pop(series_key, None) if series_key else None
            try:
                self._alive.remove(dialog)
            except ValueError:
                pass

        dialog.destroyed.connect(_on_destroyed)
        dialog.show()

    def _get_series_key(self, idx: int) -> str | None:
        """Return a unique key for the series in subwindow *idx*."""
        data = self._app.subwindow_data.get(idx, {})
        study_uid = data.get("study_uid")
        series_uid = data.get("series_uid")
        if study_uid and series_uid:
            return f"{study_uid}|{series_uid}"
        return None

    def close_all_dialogs(self) -> None:
        """Close all open 3D volume render dialogs.

        Called when the main application is about to quit so that orphaned
        parentless dialogs are cleaned up properly.
        """
        dialogs = list(self._alive)
        app = QApplication.instance()
        if app is not None:
            for widget in QApplication.topLevelWidgets():
                if isinstance(widget, VolumeRenderDialog) and widget not in dialogs:
                    dialogs.append(widget)

        for dialog in dialogs:
            try:
                closed = dialog.close()
                if not closed and hasattr(dialog, "hide"):
                    dialog.hide()
            except RuntimeError:
                pass  # already deleted by Qt

        if app is not None:
            app.processEvents()

        self._alive.clear()
        self._open_dialogs.clear()

    @staticmethod
    def _get_series_description(datasets: list[Any]) -> str:
        """Extract a human-readable series description."""
        if not datasets:
            return ""
        ds = datasets[0]
        parts = []
        desc = getattr(ds, "SeriesDescription", None)
        if desc:
            parts.append(str(desc))
        modality = getattr(ds, "Modality", None)
        if modality:
            parts.append(str(modality))
        if not parts:
            parts.append("Unknown")
        return " - ".join(parts)

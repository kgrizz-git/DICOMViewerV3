"""
GUI facade for launching 3D volume render dialogs from ``DICOMViewerApp``.

Validation logic lives in ``core.volume_render_eligibility`` (no gui imports).
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from core.volume_render_eligibility import (
    can_launch_3d_volume_render,
    get_datasets_for_subwindow,
)
from gui.dialogs.volume_render_dialog import VolumeRenderDialog

_log = logging.getLogger(__name__)


class _ActivationTracker(QObject):
    """Records the most recently activated 3D dialog.

    Opening the main window's File menu activates the main window, so the
    3D dialog the user was just using is no longer the active window when
    File → Save 3D View… runs.
    """

    def __init__(self, facade: VolumeRenderFacade) -> None:
        super().__init__()
        self._facade = facade

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.WindowActivate:
            self._facade._last_active = watched
        return False


class VolumeRenderFacade:
    """Manages the lifecycle of 3D volume render dialogs."""

    def __init__(self, app: Any) -> None:
        self._app = app
        # Maps series_key -> VolumeRenderDialog to prevent duplicates.
        self._open_dialogs: dict[str, Any] = {}
        # Strong refs for all open dialogs (parentless dialogs would
        # otherwise be garbage-collected immediately by Python).
        self._alive: list[Any] = []
        # Most recently activated 3D dialog (see _ActivationTracker).
        self._last_active: Any | None = None
        self._activation_tracker = _ActivationTracker(self)

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
            if existing is not None and self._is_alive(existing):
                # Hidden or minimized dialogs are reused, never rebuilt.
                self._last_active = existing
                self.restore_dialog(existing)
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
            if self._last_active is dialog:
                self._last_active = None
            try:
                self._alive.remove(dialog)
            except ValueError:
                pass

        dialog.destroyed.connect(_on_destroyed)
        dialog.installEventFilter(self._activation_tracker)
        self._last_active = dialog
        dialog.show()

    @staticmethod
    def _is_alive(dialog: Any) -> bool:
        """False once Qt has deleted the dialog's C++ object."""
        try:
            dialog.isVisible()
        except RuntimeError:
            return False
        return True

    def _existing_dialogs(self) -> list[Any]:
        """Live (not deleted) 3D dialogs, visible or hidden, most recently opened last."""
        return [d for d in self._alive if self._is_alive(d)]

    def _live_dialogs(self) -> list[Any]:
        """Visible 3D dialogs, most recently opened last."""
        return [d for d in self._existing_dialogs() if d.isVisible()]

    def has_open_dialog(self) -> bool:
        """True while at least one 3D window exists (visible, minimized, or hidden)."""
        return bool(self._existing_dialogs())

    def has_visible_dialog(self) -> bool:
        """True while at least one 3D window is shown (a minimized one still counts)."""
        return bool(self._live_dialogs())

    @staticmethod
    def restore_dialog(dialog: Any) -> None:
        """Show, raise and activate *dialog*, clearing only the minimized state.

        A maximized or fullscreen window keeps that state.
        """
        if dialog.isMinimized():
            dialog.setWindowState(dialog.windowState() & ~Qt.WindowState.WindowMinimized)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def toggle_dialog_visibility(self, subwindow_idx: int | None = None) -> bool | None:
        """Hide the target 3D window, or show it if hidden or minimized.

        Returns ``True`` if it is now shown, ``False`` if hidden, ``None`` if no
        3D window exists. Hiding keeps the dialog and its volume alive.
        """
        dialog = self.target_dialog(subwindow_idx)
        if dialog is None:
            return None
        if dialog.isVisible() and not dialog.isMinimized():
            dialog.hide()
            return False
        self.restore_dialog(dialog)
        return True

    def target_is_shown(self, subwindow_idx: int | None = None) -> bool:
        """True if the target 3D window is visible and not minimized."""
        dialog = self.target_dialog(subwindow_idx)
        return dialog is not None and dialog.isVisible() and not dialog.isMinimized()

    def refresh_stay_on_top(self) -> None:
        """Re-apply the keep-in-front setting to every live 3D dialog."""
        for dialog in self._existing_dialogs():
            dialog.refresh_stay_on_top()

    def target_dialog(self, subwindow_idx: int | None = None) -> Any | None:
        """The 3D window File → Save 3D View… and Show 3D Viewer act on.

        Considers every existing dialog, including hidden ones. Prefers the
        active 3D window, then the most recently activated one, then the one
        for the focused pane's series, then the most recently opened one.
        """
        live = self._existing_dialogs()
        if not live:
            return None
        for candidate in (QApplication.activeWindow(), self._last_active):
            if candidate in live:
                return candidate
        if subwindow_idx is not None:
            key = self._get_series_key(int(subwindow_idx))
            focused = self._open_dialogs.get(key) if key else None
            if focused in live:
                return focused
        return live[-1]

    def save_3d_view(self, subwindow_idx: int | None = None) -> bool:
        """Run the target 3D window's Save Image… flow; ``True`` if a file was written."""
        dialog = self.target_dialog(subwindow_idx)
        if dialog is None:
            QMessageBox.information(
                self._app.main_window,
                "Save 3D View",
                "Open a 3D view first (Tools → 3D Volume Render…).",
            )
            return False
        if not dialog.can_save_image():
            QMessageBox.information(
                self._app.main_window,
                "Save 3D View",
                "The 3D view is not ready yet. Wait for the first frame to appear.",
            )
            return False
        # A hidden or minimized window is shown first so the user sees what is saved.
        self.restore_dialog(dialog)
        return bool(dialog.save_image())

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
        self._last_active = None

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

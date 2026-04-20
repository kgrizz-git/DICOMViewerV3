"""
Export-related entry points and path helpers for DICOMViewerApp.

Owns focused-series path resolution, save-as prompts used by QA and other
features, and thin wrappers for ROI statistics export, primary Export dialog,
and multi-window screenshot export. ``DICOMViewerApp`` keeps methods with the
same names as one-line delegates so ``app_signal_wiring`` and
``dialog_action_handlers.open_export(app)`` unchanged.

Inputs:
    - ``DICOMViewerApp`` reference (``main_window``, ``multi_window_layout``,
      ``dialog_coordinator``, ``subwindow_managers``, ``subwindow_data``,
      ``focused_subwindow_index``, ``_file_series_coordinator``, subwindow UID
      getters).

Outputs:
    - Paths tuple for QA flows; user-selected save paths; opens coordinator /
      handler entry points.

Requirements:
    - PySide6, pydicom; ``FileSeriesLoadingCoordinator`` available on the app.
"""

from __future__ import annotations

import os
from typing import Any, List, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog
from pydicom.dataset import Dataset

from core import dialog_action_handlers


class ExportAppFacade:
    """Cohesive export path / dialogs cut from ``DICOMViewerApp`` (Phase 4c)."""

    __slots__ = ("_app",)

    def __init__(self, app: Any) -> None:
        self._app = app

    def resolve_focused_series_ordered_paths(
        self,
    ) -> Tuple[str, str, str, List[str], List[Dataset]]:
        """
        Resolve focused-subwindow series identity and ordered source file paths.

        Returns:
            Tuple of (study_uid, series_uid, modality, ordered_file_paths, datasets).
        """
        app = self._app
        focused_idx = app.focused_subwindow_index
        study_uid = app._get_subwindow_study_uid(focused_idx)
        series_uid = app._get_subwindow_series_uid(focused_idx)
        datasets = app.subwindow_data.get(focused_idx, {}).get("current_datasets", [])
        if not isinstance(datasets, list):
            datasets = []

        ordered_paths: List[str] = []
        modality = ""
        for slice_index, dataset in enumerate(datasets):
            if not modality:
                modality = str(getattr(dataset, "Modality", "") or "")
            path = app._file_series_coordinator.get_file_path_for_dataset(
                dataset,
                study_uid,
                series_uid,
                slice_index,
            )
            if path:
                ordered_paths.append(path)

        return study_uid, series_uid, modality, ordered_paths, datasets

    def prompt_save_path(
        self,
        title: str,
        default_name: str,
        filter_text: str,
        *,
        remember_pylinac_output_dir: bool = False,
    ) -> str:
        """
        Open a Save dialog that appears on top initially and return selected path.

        When ``remember_pylinac_output_dir`` is True, the dialog starts in the
        last pylinac QA output directory (falling back to last export path or
        cwd), and the chosen file's directory is saved for the next session.
        """
        app = self._app
        dialog = QFileDialog(app.main_window)
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        dialog.setFileMode(QFileDialog.FileMode.AnyFile)
        dialog.setNameFilter(filter_text)
        selection = default_name
        if remember_pylinac_output_dir:
            cm = app.config_manager
            start = cm.get_last_pylinac_output_path() or ""
            if not start or not os.path.exists(start):
                start = cm.get_last_export_path() or ""
            if not start or not os.path.exists(start):
                start = os.getcwd()
            if os.path.isfile(start):
                start = os.path.dirname(start)
            elif not os.path.isdir(start):
                start = os.getcwd()
            base = os.path.basename(default_name) or default_name
            selection = os.path.join(start, base)
            dialog.setDirectory(start)
        dialog.selectFile(selection)
        dialog.setWindowTitle(title)
        dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        dialog.activateWindow()
        dialog.raise_()
        if dialog.exec():
            selected = dialog.selectedFiles()
            if selected:
                path = selected[0]
                if remember_pylinac_output_dir:
                    parent = os.path.dirname(os.path.abspath(path))
                    if parent:
                        app.config_manager.set_last_pylinac_output_path(parent)
                return path
        return ""

    def open_export_roi_statistics(self) -> None:
        """Export ROI statistics (menu / context menu)."""
        app = self._app
        app.dialog_coordinator.open_export_roi_statistics(app.subwindow_managers)

    def open_export(self) -> None:
        """Open main Export dialog (resolution options inside the dialog)."""
        dialog_action_handlers.open_export(self._app)

    def open_export_screenshots(self) -> None:
        """Export screenshots (per-view, composite grid, or full main window)."""
        app = self._app
        subwindows = app.multi_window_layout.get_all_subwindows()
        app.dialog_coordinator.open_export_screenshots(
            subwindows,
            multi_window_layout=app.multi_window_layout,
        )

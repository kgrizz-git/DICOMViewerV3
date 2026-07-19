"""
MPR Controller

Orchestrates the lifecycle of MPR views in the DICOM viewer.

Responsibilities:
  - Owns a per-subwindow dict of active MprResult instances.
  - Opens the MPR dialog, builds the MPR via MprBuilderWorker, caches it,
    and loads the result into the target subwindow.
  - Displays individual MPR slices via ImageViewer.set_image() (bypassing
    the normal DICOM display path for MPR slices).
  - Draws the "MPR – <Orientation>" banner using the overlay manager.
  - Disables ROI/measurement/annotation tools while a subwindow is in MPR mode.
  - Provides ``is_mpr(idx)`` and ``clear_mpr(idx)`` for callers.

Inputs:
    app — DICOMViewerApp instance (provides subwindow_managers,
          subwindow_data, config_manager, focused_subwindow_index, etc.).

Outputs:
    Mutates subwindow_data[idx] with MPR-specific keys ("is_mpr",
    "mpr_result", "mpr_slice_index") and drives the ImageViewer + SliceNavigator
    for MPR subwindows.

Requirements:
    PySide6, numpy, PIL, pydicom (all already project dependencies).
    SimpleITK (for MprBuilder/MprVolume).
"""

from __future__ import annotations

import copy
import logging
import os
from typing import Any

import numpy as np
from PIL import Image
from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QMessageBox,
    QProgressDialog,
)

from core.dicom_parser import DICOMParser
from core.mpr_builder import MprBuilder, MprBuilderWorker, MprResult
from core.mpr_cache import MprCache
from core.mpr_combine_slice_count import normalize_mpr_combine_slice_count
from core.mpr_dicom_export import (
    MprDicomExportError,
    MprDicomExportOptions,
    write_mpr_series,
)
from core.mpr_stack_combine import apply_mpr_stack_combine
from core.mpr_view_math import (
    array_to_pil,
    auto_window_level,
    build_mpr_banner_text,
    compute_mpr_combine_range,
)
from core.mpr_volume import (
    MprVolume,
    MprVolumeError,
    get_orientation_groups,
    has_slice_location_fallback_available,
)
from gui.dialogs.mpr_orientation_choice_dialog import MprOrientationChoiceDialog
from utils.debug_flags import DEBUG_MPR
from utils.dicom_utils import get_composite_series_key
from utils.privacy.console import print_redacted
from utils.privacy.safe_storage import DeletionResult

_logger = logging.getLogger(__name__)



_TITLE_SAVE_MPR_DICOM = "Save MPR as DICOM"
_TITLE_MPR_ERROR = "MPR Error"

def seed_mpr_combine_state(
    data: dict[str, Any], request: Any | None, output_thickness_mm: float
) -> None:
    """
    Initialise ``mpr_combine_*`` keys on *data* from *request* (dialog)
    or defaults. Used when MPR is activated so runtime slab matches dialog.

    Prefer ``combine_slice_count`` on the request (same allowed values as the
    right-pane Combine Slices widget). Older requests may only provide
    ``slab_thickness_mm``; that is converted to a plane count using
    *output_thickness_mm*.
    """
    if request is not None:
        cm = (getattr(request, "combine_mode", None) or "none").lower()
        if cm in ("mip", "minip", "aip"):
            data["mpr_combine_enabled"] = True
            data["mpr_combine_mode"] = cm
            n_raw = getattr(request, "combine_slice_count", None)
            if n_raw is not None:
                data["mpr_combine_slice_count"] = normalize_mpr_combine_slice_count(
                    int(n_raw)
                )
            else:
                slab_mm = float(getattr(request, "slab_thickness_mm", 0.0) or 0.0)
                if slab_mm > 0:
                    n = max(
                        1,
                        int(
                            round(
                                slab_mm / max(float(output_thickness_mm), 1e-6)
                            )
                        ),
                    )
                    data["mpr_combine_slice_count"] = normalize_mpr_combine_slice_count(
                        n
                    )
                else:
                    data["mpr_combine_slice_count"] = 4
            return
    data["mpr_combine_enabled"] = False
    data["mpr_combine_mode"] = "aip"
    data["mpr_combine_slice_count"] = 4


def _mpr_log(message: str) -> None:
    """Print an MPR debug message when DEBUG_MPR is enabled."""
    if DEBUG_MPR:
        print(f"[DEBUG-MPR] {message}")

class MprController(QObject):
    """
    Manages MPR view state and lifecycle for all subwindows.

    Each subwindow may independently be in "MPR mode", indicated by
    ``subwindow_data[idx].get("is_mpr") == True``.

    MPR-mode subwindow_data extra keys:
        is_mpr (bool):           Always True when in MPR mode.
        mpr_result (MprResult):  The current MprResult.
        mpr_orientation (str):   Human-readable label ("Axial", etc.)
        mpr_slice_index (int):   Current MPR stack index (0-based).

    Signals:
        mpr_activated(int):  Emitted with the subwindow index after MPR is
                             successfully loaded and the first slice displayed.
        mpr_cleared(int):    Emitted with the subwindow index after MPR state
                             has been fully removed from that subwindow.
    """

    mpr_activated = Signal(int)  # subwindow index
    mpr_cleared = Signal(int)    # subwindow index
    # Emitted when MPR is detached from a pane (Clear Window). Session stays
    # alive; navigator stores it under key -1, laid out after the source series.
    mpr_detached = Signal(int)  # former subwindow index

    def __init__(self, app: Any) -> None:
        """
        Args:
            app: The DICOMViewerApp instance (provides access to all
                 subwindow managers, config, etc.).
        """
        super().__init__()
        self._app = app
        self._workers: dict[int, MprBuilderWorker] = {}  # idx → active worker
        self._cache: MprCache | None = None
        # MPR session detached from all panes (Clear Window); reassigned via drag-drop.
        self._detached_mpr_payload: dict[str, Any] | None = None
        self._init_cache()

    # ------------------------------------------------------------------
    # Cache initialisation
    # ------------------------------------------------------------------

    def _init_cache(self) -> None:
        """Set up the protected disk cache only after explicit opt-in."""
        try:
            if not self._app.config_manager.get_mpr_cache_enabled():
                result = self._app.config_manager.clear_mpr_cache_storage()
                if not result.success:
                    _logger.warning(
                        "Disabled MPR cache storage could not be fully cleared",
                        extra={"operation": "mpr_cache.clear", "failed": result.failed},
                    )
                self._cache = None
                return
            cache_dir = self._app.config_manager.get_mpr_cache_path()
            max_mb = self._app.config_manager.get_mpr_cache_max_mb()
            self._cache = MprCache(cache_dir=cache_dir, max_size_mb=max_mb)
            _mpr_log(f"Cache initialised: enabled=True max_mb={max_mb}")
        except Exception as exc:
            _logger.warning(
                "MPR cache initialization failed",
                extra={"operation": "mpr_cache.init", "error_class": type(exc).__name__},
            )
            self._cache = None

    def clear_persistent_cache(self) -> DeletionResult:
        """Clear active and legacy derived-pixel files with truthful counts."""

        self._cache = None
        result = self._app.config_manager.clear_mpr_cache_storage()
        if result.success and self._app.config_manager.get_mpr_cache_enabled():
            try:
                self._cache = MprCache(
                    cache_dir=self._app.config_manager.get_mpr_cache_path(),
                    max_size_mb=self._app.config_manager.get_mpr_cache_max_mb(),
                )
            except Exception as exc:
                _logger.warning(
                    "MPR cache could not be reinitialized after clearing",
                    extra={
                        "operation": "mpr_cache.reinitialize",
                        "error_class": type(exc).__name__,
                    },
                )
                return DeletionResult(removed=result.removed, failed=result.failed + 1)
        return result

    def apply_cache_settings(self) -> None:
        """Apply an explicit cache setting change immediately."""

        if not self._app.config_manager.get_mpr_cache_enabled():
            self.clear_persistent_cache()
            self._cache = None
            return
        if self._cache is None:
            self._init_cache()
            return
        self._cache.set_max_size_mb(
            self._app.config_manager.get_mpr_cache_max_mb()
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_mpr(self, idx: int) -> bool:
        """Return True if subwindow *idx* is currently in MPR mode."""
        data = self._app.subwindow_data.get(idx, {})
        return bool(data.get("is_mpr", False))

    def get_orientation_label(self, idx: int) -> str:
        """Return the orientation label for the MPR view, or "" if not MPR."""
        data = self._app.subwindow_data.get(idx, {})
        return data.get("mpr_orientation", "") if data.get("is_mpr") else ""

    def open_mpr_dialog(self, target_subwindow_idx: int) -> None:
        """
        Open the MPR dialog for the given subwindow.

        Collects all loaded series from the app state, pre-selects the
        focused subwindow's series, and shows the dialog.

        Args:
            target_subwindow_idx: Which subwindow will host the MPR view.
        """
        from gui.dialogs.mpr_dialog import MprDialog

        # Ensure subwindow data exists and is properly initialized
        if target_subwindow_idx not in self._app.subwindow_data:
            self._app.subwindow_data[target_subwindow_idx] = {}

        # Clear any stale MPR state (inconsistent state where is_mpr is True but mpr_result is None)
        data = self._app.subwindow_data[target_subwindow_idx]
        if data.get("is_mpr") and data.get("mpr_result") is None:
            # Inconsistent state - clear it
            _mpr_log(f"Clearing stale MPR state in window {target_subwindow_idx}")
            self.clear_mpr(target_subwindow_idx)

        loaded_series = self._collect_loaded_series()
        _mpr_log(
            f"Open MPR dialog for window {target_subwindow_idx}: "
            f"loaded_series={len(loaded_series)}"
        )
        if not loaded_series:
            QMessageBox.information(
                self._app.main_window,
                "MPR",
                "No series are currently loaded. Open a DICOM series first.",
            )
            return

        # Pre-select the focused subwindow's series.
        initial_key = self._app.subwindow_data.get(
            target_subwindow_idx, {}
        ).get("current_series_uid", None)

        dlg = MprDialog(
            loaded_series=loaded_series,
            initial_series_key=initial_key,
            parent=self._app.main_window,
        )
        dlg.mpr_requested.connect(
            lambda req, idx=target_subwindow_idx: self._on_mpr_requested(idx, req)
        )
        dlg.exec()

    def prompt_save_mpr_as_dicom(self) -> None:
        """
        Save the focused subwindow's MPR stack as a new DICOM series (File menu).

        Requires a completed ``MprResult`` on the focused pane. Prompts for an
        output root folder (mirrors export path memory), then a small options
        dialog, then writes one file per plane with progress / cancel.
        """
        from gui.dialogs.mpr_dicom_save_dialog import MprDicomSaveDialog

        app = self._app
        mw = app.main_window
        ctx = self._save_mpr_resolve_export_context(mw)
        if ctx is None:
            return
        data, result, template = ctx

        output_root = self._save_mpr_pick_output_root(mw)
        if output_root is None:
            return

        orient = str(data.get("mpr_orientation", "") or "")
        opt_dialog = MprDicomSaveDialog(parent=mw, orientation_label=orient)
        if opt_dialog.exec() != QDialog.DialogCode.Accepted:
            return
        opts: MprDicomExportOptions = opt_dialog.build_options(orient)
        self._save_mpr_write_series(mw, output_root, result, template, opts)

    def _save_mpr_resolve_export_context(self, mw) -> tuple[dict, Any, Any] | None:
        """Validate focused MPR pane and resolve export template dataset."""
        app = self._app
        idx = app.get_focused_subwindow_index()
        data = app.subwindow_data.get(idx, {})
        if not data.get("is_mpr"):
            QMessageBox.information(
                mw,
                _TITLE_SAVE_MPR_DICOM,
                "The focused window is not an MPR view.\n"
                "Create an MPR in a pane and focus it, then try again.",
            )
            return None
        result = data.get("mpr_result")
        if result is None or getattr(result, "n_slices", 0) < 1:
            QMessageBox.information(
                mw,
                _TITLE_SAVE_MPR_DICOM,
                "No MPR slice stack is available to export yet.",
            )
            return None

        template = data.get("mpr_source_dataset")
        if template is None:
            try:
                template = result.source_volume.source_datasets[0]
            except Exception:
                template = None
        if template is None:
            QMessageBox.warning(
                mw,
                _TITLE_SAVE_MPR_DICOM,
                "Could not resolve a source DICOM dataset for metadata export.",
            )
            return None
        return data, result, template

    def _save_mpr_pick_output_root(self, mw) -> str | None:
        """Prompt for an export folder and remember it in config."""
        app = self._app
        start = app.config_manager.get_last_export_path() or ""
        if not start or not os.path.exists(start):
            start = os.getcwd()
        folder_dialog = QFileDialog(mw)
        folder_dialog.setFileMode(QFileDialog.FileMode.Directory)
        folder_dialog.setWindowTitle("Select folder for MPR DICOM export")
        folder_dialog.setDirectory(start)
        folder_dialog.setWindowFlags(
            folder_dialog.windowFlags() | Qt.WindowType.WindowStaysOnTopHint
        )
        folder_dialog.activateWindow()
        folder_dialog.raise_()
        if not folder_dialog.exec():
            return None
        selected = folder_dialog.selectedFiles()
        if not selected:
            return None
        output_root = selected[0]
        app.config_manager.set_last_export_path(output_root)
        return output_root

    def _save_mpr_write_series(
        self,
        mw,
        output_root: str,
        result: MprResult,
        template: Any,
        opts: MprDicomExportOptions,
    ) -> None:
        """Write MPR DICOM files with progress UI and success/error messaging."""
        progress = QProgressDialog(
            "Writing MPR DICOM files…",
            "Cancel",
            0,
            result.n_slices,
            mw,
        )
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)

        def _progress_cb(cur: int, total: int, msg: str) -> bool:
            progress.setMaximum(max(total, 1))
            progress.setValue(min(cur, total))
            progress.setLabelText(msg)
            QApplication.processEvents()
            return not progress.wasCanceled()

        template_copy = copy.deepcopy(template)
        try:
            paths = write_mpr_series(
                output_root,
                result,
                template_copy,
                opts,
                progress_callback=_progress_cb,
            )
        except MprDicomExportError as exc:
            progress.close()
            if "cancelled" in str(exc).lower():
                return
            QMessageBox.critical(
                mw,
                _TITLE_SAVE_MPR_DICOM,
                "Export failed. Details were withheld to protect private data.",
            )
            return

        progress.close()
        QMessageBox.information(
            mw,
            _TITLE_SAVE_MPR_DICOM,
            f"Successfully wrote {len(paths)} file(s).\n\n"
            f"First file:\n{paths[0]}",
        )

    def _cancel_mpr_worker(self, idx: int) -> None:
        """Cancel and remove any in-progress MPR build for *idx*."""
        worker = self._workers.pop(idx, None)
        if worker is not None:
            worker.cancel()
            worker.quit()
            worker.wait(2000)


    def _tear_down_mpr_at_subwindow(self, idx: int) -> None:
        """
        Remove MPR keys from *idx*, restore the pre-MPR 2-D state (if any), and
        refresh dependent UI. Does not emit signals.
        """
        data = self._app.subwindow_data.get(idx)
        if data is None:
            return

        self._tear_down_remove_slice_location_manager(idx)
        previous_state = data.get("mpr_previous_state")
        image_viewer = self._get_image_viewer(idx)
        self._tear_down_clear_mpr_keys(data)
        self._set_tools_enabled(idx, enabled=True)
        self._tear_down_clear_mpr_banner(idx)

        if isinstance(previous_state, dict):
            self._tear_down_restore_previous_state(idx, data, previous_state)
        else:
            self._tear_down_clear_dataset_fields(data)

        if data.get("current_dataset") is None and image_viewer is not None:
            self._tear_down_clear_empty_viewer(idx, image_viewer)

        self._tear_down_refresh_navigators_and_ui(idx, data)

    def _tear_down_remove_slice_location_manager(self, idx: int) -> None:
        """Drop slice-location line manager before scene changes."""
        try:
            line_coord = getattr(self._app, "_slice_location_line_coordinator", None)
            if line_coord is not None:
                line_coord.remove_manager(idx)
        except Exception:
            pass

    def _tear_down_clear_mpr_keys(self, data: dict[str, Any]) -> None:
        """Remove MPR-specific keys from subwindow data."""
        for key in (
            "is_mpr",
            "mpr_result",
            "mpr_orientation",
            "mpr_slice_index",
            "mpr_source_dataset",
            "mpr_previous_state",
            "mpr_combine_enabled",
            "mpr_combine_mode",
            "mpr_combine_slice_count",
        ):
            data.pop(key, None)

    def _tear_down_clear_mpr_banner(self, idx: int) -> None:
        """Clear the MPR banner on the overlay manager, if present."""
        managers = self._app.subwindow_managers.get(idx, {})
        overlay_manager = managers.get("overlay_manager")
        if overlay_manager is not None and hasattr(overlay_manager, "set_mpr_banner"):
            overlay_manager.set_mpr_banner(None)

    def _tear_down_clear_dataset_fields(self, data: dict[str, Any]) -> None:
        """Reset current dataset fields when no previous state exists."""
        data["current_dataset"] = None
        data["current_slice_index"] = 0
        data["current_study_uid"] = ""
        data["current_series_uid"] = ""
        data["current_datasets"] = []

    def _tear_down_restore_previous_state(
        self, idx: int, data: dict[str, Any], previous_state: dict[str, Any]
    ) -> None:
        """Restore pre-MPR 2-D state and redisplay the prior slice when possible."""
        data.update(previous_state)
        previous_dataset = previous_state.get("current_dataset")
        previous_slice_index = previous_state.get("current_slice_index", 0)
        previous_study_uid = previous_state.get("current_study_uid", "")
        previous_series_uid = previous_state.get("current_series_uid", "")

        sdm = self._app.subwindow_managers.get(idx, {}).get("slice_display_manager")
        if sdm is not None and previous_dataset is not None:
            try:
                sdm.display_slice(
                    previous_dataset,
                    self._app.current_studies,
                    previous_study_uid,
                    previous_series_uid,
                    previous_slice_index,
                    preserve_view_override=True,
                    update_controls=(idx == getattr(self._app, "focused_subwindow_index", -1)),
                    update_metadata=(idx == getattr(self._app, "focused_subwindow_index", -1)),
                )
            except Exception as exc:
                print_redacted(
                    f"[MprController] Failed to restore prior slice in window {idx}: {exc}"
                )

        if idx == getattr(self._app, "focused_subwindow_index", -1):
            self._app.current_dataset = previous_dataset
            self._app.current_slice_index = previous_slice_index
            self._app.current_study_uid = previous_study_uid
            self._app.current_series_uid = previous_series_uid
            self._app.current_datasets = previous_state.get("current_datasets", [])

    def _tear_down_clear_empty_viewer(self, idx: int, image_viewer: Any) -> None:
        """Clear the viewer and view-state when no dataset remains after tear-down."""
        managers = self._app.subwindow_managers.get(idx, {})
        overlay_manager = managers.get("overlay_manager")
        try:
            if overlay_manager is not None:
                overlay_manager.clear_overlay_items(image_viewer.scene)
            image_viewer.scene.clear()
            image_viewer.image_item = None
            image_viewer.original_image = None
            image_viewer.viewport().update()
        except Exception as exc:
            print_redacted(f"[MprController] Failed to clear MPR view in window {idx}: {exc}")

        view_state_manager = managers.get("view_state_manager")
        if view_state_manager is not None:
            try:
                view_state_manager.set_current_data_context(None, {}, "", "", 0)
                view_state_manager.set_current_series_identifier(None)
            except Exception as exc:
                print_redacted(
                    f"[MprController] Failed to reset view state for window {idx}: {exc}"
                )

        if idx == getattr(self._app, "focused_subwindow_index", -1):
            self._app.current_dataset = None
            self._app.current_slice_index = 0
            self._app.current_study_uid = ""
            self._app.current_series_uid = ""
            self._app.current_datasets = []

    def _tear_down_refresh_navigators_and_ui(self, idx: int, data: dict[str, Any]) -> None:
        """Refresh navigators, slot map, lines, and slider after tear-down."""
        try:
            if (
                hasattr(self._app, "slice_navigator")
                and idx == getattr(self._app, "focused_subwindow_index", -1)
            ):
                datasets = data.get("current_datasets") or []
                self._app.slice_navigator.set_total_slices(len(datasets))
                self._app.slice_navigator.blockSignals(True)
                self._app.slice_navigator.current_slice_index = data.get(
                    "current_slice_index", 0
                )
                self._app.slice_navigator.blockSignals(False)
        except Exception:
            pass

        try:
            if hasattr(self._app, "series_navigator") and hasattr(
                self._app, "_get_subwindow_assignments"
            ):
                assignments = self._app._get_subwindow_assignments()
                self._app.series_navigator.set_subwindow_assignments(assignments)
        except Exception:
            pass

        try:
            refresh_window_slot_map = getattr(
                self._app, "_refresh_window_slot_map_widgets", None
            )
            if callable(refresh_window_slot_map):
                refresh_window_slot_map()
        except Exception:
            pass

        try:
            line_coord = getattr(self._app, "_slice_location_line_coordinator", None)
            if line_coord is not None:
                line_coord.refresh_all()
        except Exception:
            pass

        try:
            sync = getattr(self._app, "_sync_navigation_slider_for_subwindow", None)
            if callable(sync):
                sync(idx)
        except Exception:
            pass

    def clear_mpr(self, idx: int) -> None:
        """
        Clear MPR mode from subwindow *idx* and restore normal display.

        Cancels any in-progress build for this subwindow.

        Args:
            idx: Subwindow index to clear.
        """
        self._cancel_mpr_worker(idx)
        data = self._app.subwindow_data.get(idx)
        if data is None:
            return

        self._tear_down_mpr_at_subwindow(idx)
        self.mpr_cleared.emit(idx)

    def has_detached_mpr(self) -> bool:
        """Return True if an MPR session exists without an assigned subwindow."""
        return self._detached_mpr_payload is not None

    def clear_detached_mpr(self) -> None:
        """Discard a detached (unassigned) MPR session."""
        self._detached_mpr_payload = None

    def get_detached_mpr_thumbnail_pixels(self, use_rescaled: bool) -> np.ndarray | None:
        """
        Return a 2-D array for the navigator thumbnail of the detached MPR
        session (mid-stack slice), or None if none.
        """
        payload = self._detached_mpr_payload
        if not payload:
            return None
        result = payload.get("mpr_result")
        if result is None:
            return None
        n_slices = int(getattr(result, "n_slices", 0) or 0)
        if n_slices <= 0:
            return None
        mid = n_slices // 2
        raw = apply_mpr_stack_combine(
            result.slices,
            mid,
            enabled=bool(payload.get("mpr_combine_enabled", False)),
            mode=str(payload.get("mpr_combine_mode", "aip") or "aip"),
            n_planes=int(payload.get("mpr_combine_slice_count", 4) or 4),
        )
        if use_rescaled:
            return result.apply_rescale(raw)
        return raw.astype(np.float32)

    def _capture_mpr_payload(self, idx: int) -> dict[str, Any] | None:
        """Snapshot live MPR fields from *idx* for relocate / detach."""
        data = self._app.subwindow_data.get(idx, {})
        if not data.get("is_mpr") or data.get("mpr_result") is None:
            return None
        return {
            "mpr_result": data["mpr_result"],
            "mpr_orientation": data.get("mpr_orientation", ""),
            "mpr_slice_index": int(data.get("mpr_slice_index", 0)),
            "mpr_combine_enabled": bool(data.get("mpr_combine_enabled", False)),
            "mpr_combine_mode": str(data.get("mpr_combine_mode", "aip") or "aip"),
            "mpr_combine_slice_count": int(data.get("mpr_combine_slice_count", 4) or 4),
            "mpr_source_dataset": data.get("mpr_source_dataset"),
            "current_study_uid": str(data.get("current_study_uid", "") or ""),
            "current_series_uid": str(data.get("current_series_uid", "") or ""),
            "current_datasets": list(data.get("current_datasets") or []),
        }

    def relocate_mpr_subwindow(self, from_idx: int, to_idx: int) -> None:
        """
        Move an active MPR from *from_idx* to *to_idx*.

        If the destination already shows MPR, it is cleared first. If *from_idx*
        equals *to_idx*, only focuses that subwindow.
        """
        if from_idx == to_idx:
            try:
                sub = self._app.multi_window_layout.get_subwindow(to_idx)
                if sub is not None:
                    sub.set_focused(True)
            except Exception:
                pass
            return
        if not self.is_mpr(from_idx):
            return

        payload = self._capture_mpr_payload(from_idx)
        if payload is None:
            return

        try:
            sub = self._app.multi_window_layout.get_subwindow(to_idx)
            if sub is not None:
                sub.set_focused(True)
        except Exception:
            pass

        if self.is_mpr(to_idx):
            self.clear_mpr(to_idx)

        self._cancel_mpr_worker(from_idx)
        self._tear_down_mpr_at_subwindow(from_idx)
        self.mpr_cleared.emit(from_idx)

        ok = self._install_mpr_payload_at_subwindow(to_idx, payload)
        if ok:
            self.mpr_activated.emit(to_idx)

    def attach_floating_mpr(self, to_idx: int) -> None:
        """Assign a detached MPR session to *to_idx*."""
        payload = self._detached_mpr_payload
        if payload is None:
            return

        self._attach_focus_destination(to_idx)
        dest_backup = self._attach_backup_existing_mpr(to_idx)
        ok = self._install_mpr_payload_at_subwindow(to_idx, payload)
        if ok:
            self._detached_mpr_payload = None
            self._attach_clear_detached_thumbnail()
            self.mpr_activated.emit(to_idx)
            return
        self._attach_restore_or_warn(to_idx, dest_backup)

    def _attach_focus_destination(self, to_idx: int) -> None:
        """Best-effort focus the destination subwindow before attach."""
        try:
            sub = self._app.multi_window_layout.get_subwindow(to_idx)
            if sub is not None:
                sub.set_focused(True)
        except Exception:
            pass

    def _attach_backup_existing_mpr(self, to_idx: int) -> dict[str, Any] | None:
        """Capture and clear an existing MPR at *to_idx*, if present."""
        if not self.is_mpr(to_idx):
            return None
        dest_backup = self._capture_mpr_payload(to_idx)
        self.clear_mpr(to_idx)
        return dest_backup

    def _attach_clear_detached_thumbnail(self) -> None:
        """Clear the navigator's detached-MPR thumbnail slot."""
        try:
            if hasattr(self._app, "series_navigator"):
                self._app.series_navigator.clear_mpr_thumbnail(-1)
        except Exception:
            pass

    def _attach_restore_or_warn(
        self, to_idx: int, dest_backup: dict[str, Any] | None
    ) -> None:
        """Restore a prior MPR backup if possible and warn about attach failure."""
        if dest_backup is not None:
            restored = self._install_mpr_payload_at_subwindow(to_idx, dest_backup)
            if restored:
                self.mpr_activated.emit(to_idx)
        try:
            QMessageBox.warning(
                self._app.main_window,
                "MPR",
                "Could not attach the detached MPR to this window.\n"
                "The detached session is still available in the navigator."
                + (
                    "\nThe previous MPR in this window was restored."
                    if dest_backup is not None
                    else ""
                ),
            )
        except Exception:
            pass

    def detach_mpr_from_subwindow(self, idx: int) -> None:
        """
        Remove MPR from *idx* while keeping the MPR volume in memory for
        reassignment (navigator uses internal key -1; same in-study placement).
        """
        if not self.is_mpr(idx):
            return
        payload = self._capture_mpr_payload(idx)
        if payload is None:
            return

        self._detached_mpr_payload = payload
        self._cancel_mpr_worker(idx)
        self._tear_down_mpr_at_subwindow(idx)
        self.mpr_detached.emit(idx)


    def _install_mpr_payload_at_subwindow(self, idx: int, payload: dict[str, Any]) -> bool:
        """
        Apply a captured MPR payload to *idx* (same end state as _activate_mpr).

        Returns:
            True if the MPR view was installed; False on missing data or install error.
        """
        data = self._app.subwindow_data.get(idx)
        if data is None:
            return False

        result: MprResult | None = payload.get("mpr_result")
        if result is None:
            return False

        orientation_label = str(payload.get("mpr_orientation", "MPR") or "MPR")
        self._ensure_mpr_previous_state(data)

        try:
            source_ds = result.source_volume.source_datasets[0]
        except Exception:
            return False
        n_sl = max(int(getattr(result, "n_slices", 0) or 0), 0)
        if n_sl < 1:
            return False
        si = int(payload.get("mpr_slice_index", 0))
        si = max(0, min(si, n_sl - 1))

        self._install_write_payload_fields(
            data, payload, result, orientation_label, source_ds, si
        )

        try:
            self._sync_slice_navigator_for_mpr(idx, result.n_slices, data["mpr_slice_index"])
            self._set_tools_enabled(idx, enabled=False)
            self._reset_window_level_for_mpr(idx, source_ds)

            self.display_mpr_slice(idx, data["mpr_slice_index"])
            self._fit_image_viewer_after_mpr(idx)
            self._apply_mpr_banner(idx, data)
            self._sync_intensity_projection_if_focused(idx, data)
        except Exception as exc:
            _mpr_log(f"_install_mpr_payload_at_subwindow failed: {exc}")
            return False
        return True

    def _ensure_mpr_previous_state(self, data: dict[str, Any]) -> None:
        """Snapshot pre-MPR 2-D state once per subwindow session."""
        if "mpr_previous_state" in data:
            return
        data["mpr_previous_state"] = {
            "current_dataset": data.get("current_dataset"),
            "current_slice_index": data.get("current_slice_index", 0),
            "current_series_uid": data.get("current_series_uid", ""),
            "current_study_uid": data.get("current_study_uid", ""),
            "current_datasets": list(data.get("current_datasets", [])),
        }

    def _install_write_payload_fields(
        self,
        data: dict[str, Any],
        payload: dict[str, Any],
        result: MprResult,
        orientation_label: str,
        source_ds: Any,
        slice_index: int,
    ) -> None:
        """Copy payload / result fields into subwindow_data for install."""
        data["is_mpr"] = True
        data["mpr_result"] = result
        data["mpr_orientation"] = orientation_label
        data["mpr_slice_index"] = slice_index
        data["mpr_source_dataset"] = payload.get("mpr_source_dataset") or source_ds
        data["current_study_uid"] = str(payload.get("current_study_uid", "") or "")
        data["current_series_uid"] = str(payload.get("current_series_uid", "") or "")
        data["current_datasets"] = list(payload.get("current_datasets") or [])
        data["mpr_combine_enabled"] = bool(payload.get("mpr_combine_enabled", False))
        data["mpr_combine_mode"] = str(payload.get("mpr_combine_mode", "aip") or "aip")
        data["mpr_combine_slice_count"] = int(
            payload.get("mpr_combine_slice_count", 4) or 4
        )

    def _sync_slice_navigator_for_mpr(
        self, idx: int, n_slices: int, slice_index: int
    ) -> None:
        """Update the shared slice navigator when *idx* is focused."""
        try:
            if hasattr(self._app, "slice_navigator") and idx == getattr(
                self._app, "focused_subwindow_index", -1
            ):
                self._app.slice_navigator.set_total_slices(n_slices)
                self._app.slice_navigator.blockSignals(True)
                self._app.slice_navigator.current_slice_index = slice_index
                self._app.slice_navigator.blockSignals(False)
        except Exception:
            pass

    def _fit_image_viewer_after_mpr(self, idx: int) -> None:
        """Fit the image viewer after installing/activating an MPR stack."""
        image_viewer = self._get_image_viewer(idx)
        if image_viewer is None:
            return
        try:
            image_viewer.fit_to_view(center_image=True)
        except Exception:
            pass

    def _apply_mpr_banner(self, idx: int, data: dict[str, Any]) -> None:
        """Show or clear the MPR banner based on overlay visibility settings."""
        managers = self._app.subwindow_managers.get(idx, {})
        overlay_manager = managers.get("overlay_manager")
        if overlay_manager is None or not hasattr(overlay_manager, "set_mpr_banner"):
            return
        if getattr(overlay_manager, "should_show_text_overlays", lambda: True)():
            overlay_manager.set_mpr_banner(self._build_mpr_banner_text(data))
        else:
            overlay_manager.set_mpr_banner(None)

    def _sync_intensity_projection_if_focused(
        self, idx: int, data: dict[str, Any]
    ) -> None:
        """Sync the intensity-projection widget when *idx* is focused."""
        if idx != getattr(self._app, "focused_subwindow_index", -1):
            return
        sync = getattr(
            self._app, "_sync_intensity_projection_widget_from_mpr_data", None
        )
        if callable(sync):
            sync(data)


    def display_mpr_slice(self, idx: int, slice_index: int) -> None:
        """
        Display a single MPR slice in subwindow *idx*.

        Called when the slice navigator advances within an MPR view.

        Window/level follows the global controls (same policy as normal 2D slices
        when changing Combine Slices mode or slice count: W/L stays fixed).

        Args:
            idx:         Subwindow index.
            slice_index: Zero-based index into the MprResult.slices list.
        """
        data = self._app.subwindow_data.get(idx, {})
        if not data.get("is_mpr"):
            return
        result: MprResult | None = data.get("mpr_result")
        if result is None or slice_index >= result.n_slices:
            return

        data["mpr_slice_index"] = slice_index

        image_viewer = self._get_image_viewer(idx)
        wl_controls = getattr(self._app, "window_level_controls", None)
        managers = self._app.subwindow_managers.get(idx, {})

        if image_viewer is None:
            return

        self._display_mpr_sync_measurement_spacing(managers, result)
        array = self._display_mpr_prepare_array(data, result, slice_index, managers)
        wc, ww = self._get_preferred_mpr_window_level(
            managers.get("view_state_manager"),
            wl_controls,
            array,
        )
        pil_image = self._array_to_pil(array, wc, ww)
        if pil_image is None:
            return

        overlay_dataset = self._display_mpr_apply_image_and_context(
            idx, data, result, slice_index, managers, image_viewer, pil_image
        )
        self._display_mpr_render_annotations(
            managers, overlay_dataset, data.get("current_study_uid", ""),
            data.get("current_series_uid", ""), slice_index,
        )
        self._display_mpr_refresh_overlay(
            idx, data, result, slice_index, managers, image_viewer, overlay_dataset
        )
        self._display_mpr_post_display_sync(idx, result, slice_index, overlay_dataset, array)

    def _display_mpr_sync_measurement_spacing(
        self, managers: dict[str, Any], result: MprResult
    ) -> None:
        """Set measurement-tool spacing for the displayed MPR plane."""
        try:
            measurement_tool = managers.get("measurement_tool")
            if measurement_tool is not None:
                measurement_tool.set_pixel_spacing(result.output_spacing_mm)
        except Exception:
            pass

    def _display_mpr_prepare_array(
        self,
        data: dict[str, Any],
        result: MprResult,
        slice_index: int,
        managers: dict[str, Any],
    ) -> np.ndarray:
        """Combine raw planes then optionally rescale (order must be preserved)."""
        raw_array = apply_mpr_stack_combine(
            result.slices,
            slice_index,
            enabled=bool(data.get("mpr_combine_enabled", False)),
            mode=str(data.get("mpr_combine_mode", "aip") or "aip"),
            n_planes=int(data.get("mpr_combine_slice_count", 4) or 4),
        )
        view_state_manager = managers.get("view_state_manager")
        use_rescaled_values = bool(
            getattr(view_state_manager, "use_rescaled_values", True)
        )
        if use_rescaled_values:
            return result.apply_rescale(raw_array)
        if raw_array.dtype == np.float32:
            return raw_array
        return raw_array.astype(np.float32)

    def _display_mpr_apply_image_and_context(
        self,
        idx: int,
        data: dict[str, Any],
        result: MprResult,
        slice_index: int,
        managers: dict[str, Any],
        image_viewer: Any,
        pil_image: Any,
    ) -> Any:
        """Write overlay dataset/context and put the PIL image on the viewer."""
        overlay_dataset = self._build_overlay_dataset(result, slice_index)
        data["current_slice_index"] = slice_index
        data["current_dataset"] = overlay_dataset
        data["mpr_source_dataset"] = result.source_volume.source_datasets[0]
        current_study_uid = data.get("current_study_uid", "")
        current_series_uid = data.get("current_series_uid", "")

        view_state_manager = managers.get("view_state_manager")
        if view_state_manager is not None:
            try:
                view_state_manager.set_current_data_context(
                    overlay_dataset,
                    self._app.current_studies,
                    current_study_uid,
                    current_series_uid,
                    slice_index,
                )
                view_state_manager.set_current_series_identifier(
                    view_state_manager.get_series_identifier(overlay_dataset)
                )
            except Exception as exc:
                print_redacted(
                    f"[MprController] Failed to update MPR view state in window {idx}: {exc}"
                )

        image_viewer.set_image(pil_image, preserve_view=True)
        return overlay_dataset

    def _display_mpr_render_annotations(
        self,
        managers: dict[str, Any],
        overlay_dataset: Any,
        current_study_uid: str,
        current_series_uid: str,
        slice_index: int,
    ) -> None:
        """Render ROI / measurement / annotation overlays for the MPR slice."""
        slice_display_manager = managers.get("slice_display_manager")
        roi_coordinator = managers.get("roi_coordinator")
        if slice_display_manager is None:
            return
        try:
            slice_display_manager.set_current_data_context(
                self._app.current_studies,
                current_study_uid,
                current_series_uid,
                slice_index,
            )
            slice_display_manager.display_rois_for_slice(overlay_dataset)
            slice_display_manager.display_measurements_for_slice(overlay_dataset)
            slice_display_manager.display_text_annotations_for_slice(overlay_dataset)
            slice_display_manager.display_arrow_annotations_for_slice(overlay_dataset)
            if roi_coordinator is not None and hasattr(
                roi_coordinator, "update_roi_statistics_overlays"
            ):
                roi_coordinator.update_roi_statistics_overlays()
        except Exception as exc:
            print_redacted(
                f"[MprController] Failed to render ROIs/measurements for MPR slice: {exc}"
            )

    def _display_mpr_refresh_overlay(
        self,
        idx: int,
        data: dict[str, Any],
        result: MprResult,
        slice_index: int,
        managers: dict[str, Any],
        image_viewer: Any,
        overlay_dataset: Any,
    ) -> None:
        """Refresh DICOM overlay items and MPR banner for the current slice."""
        overlay_manager = managers.get("overlay_manager")
        if overlay_manager is None:
            return
        try:
            combine_enabled = bool(data.get("mpr_combine_enabled", False))
            combine_mode = str(data.get("mpr_combine_mode", "aip") or "aip")
            combine_slice_count = int(data.get("mpr_combine_slice_count", 4) or 4)
            projection_start_slice = None
            projection_end_slice = None
            projection_total_thickness = None
            if combine_enabled:
                projection_start_slice, projection_end_slice = (
                    self._compute_mpr_combine_range(
                        result.n_slices, slice_index, combine_slice_count
                    )
                )
                n_combined = max(0, projection_end_slice - projection_start_slice + 1)
                projection_total_thickness = (
                    float(n_combined) * float(result.output_thickness_mm)
                )
            overlay_manager.create_overlay_items(
                image_viewer.scene,
                DICOMParser(overlay_dataset),
                total_slices=result.n_slices,
                projection_enabled=combine_enabled,
                projection_start_slice=projection_start_slice,
                projection_end_slice=projection_end_slice,
                projection_total_thickness=projection_total_thickness,
                projection_type=combine_mode if combine_enabled else None,
                stack_position=slice_index + 1,
            )
            if hasattr(overlay_manager, "set_mpr_banner"):
                if getattr(overlay_manager, "should_show_text_overlays", lambda: True)():
                    overlay_manager.set_mpr_banner(self._build_mpr_banner_text(data))
                else:
                    overlay_manager.set_mpr_banner(None)
        except Exception as exc:
            print_redacted(
                f"[MprController] Failed to refresh MPR overlay in window {idx}: {exc}"
            )

    def _display_mpr_post_display_sync(
        self,
        idx: int,
        result: MprResult,
        slice_index: int,
        overlay_dataset: Any,
        array: np.ndarray,
    ) -> None:
        """Sync focused app state, histogram, slider, and deferred line refresh."""
        if idx == getattr(self._app, "focused_subwindow_index", -1):
            self._app.current_dataset = overlay_dataset
            self._app.current_slice_index = slice_index
        try:
            self._app.dialog_coordinator.update_histogram_for_subwindow(idx)
        except Exception:
            pass
        _mpr_log(
            f"Display slice window={idx} "
            f"index={slice_index + 1}/{result.n_slices} "
            f"shape={array.shape} min={float(np.min(array)):.4f} "
            f"max={float(np.max(array)):.4f} mean={float(np.mean(array)):.4f}"
        )
        try:
            sync = getattr(self._app, "_sync_navigation_slider_for_subwindow", None)
            if callable(sync):
                sync(idx)
        except Exception:
            pass
        try:
            line_coord = getattr(self._app, "_slice_location_line_coordinator", None)
            if line_coord is not None:
                QTimer.singleShot(0, line_coord.refresh_all)
        except Exception:
            pass

    def _on_mpr_requested(self, target_idx: int, request) -> None:
        """
        Validate the request, check cache, and start the build (or load from cache).

        Args:
            target_idx: Subwindow to host the MPR view.
            request:    MprRequest from the dialog.
        """
        self._mpr_request_cancel_prior_worker(target_idx)

        resolved = self._mpr_request_resolve_datasets(request)
        if resolved is None:
            return
        datasets_to_use, use_slice_location_fallback = resolved

        volume = self._mpr_request_build_volume(
            datasets_to_use, use_slice_location_fallback
        )
        if volume is None:
            return

        _mpr_log(
            "MPR request: "
            f"target_window={target_idx} "
            f"orientation={request.orientation_label} "
            f"spacing={request.output_spacing_mm:.4f} mm "
            f"thickness={request.output_thickness_mm:.4f} mm "
            f"interpolation={request.interpolation} "
            f"combine_mode={getattr(request, 'combine_mode', 'none')} "
            f"slab_thickness_mm={getattr(request, 'slab_thickness_mm', 0.0):.4f} mm "
            f"source_slices={len(datasets_to_use)}"
        )

        if self._mpr_request_try_cache(target_idx, request, volume, datasets_to_use):
            return

        self._mpr_request_start_worker(target_idx, request, volume)

    def _mpr_request_cancel_prior_worker(self, target_idx: int) -> None:
        """Cancel any in-flight MPR build for *target_idx*."""
        old_worker = self._workers.pop(target_idx, None)
        if old_worker:
            old_worker.cancel()
            old_worker.quit()
            old_worker.wait(1000)

    def _mpr_request_resolve_datasets(
        self, request
    ) -> tuple[list[Any], bool] | None:
        """
        Resolve a single-orientation dataset list for the MPR build.

        Returns:
            ``(datasets, use_slice_location_fallback)`` or ``None`` if the user
            cancels or geometry cannot be resolved.
        """
        use_slice_location_fallback = False
        groups = get_orientation_groups(request.datasets)
        if len(groups) == 0:
            if has_slice_location_fallback_available(request.datasets):
                reply = QMessageBox.question(
                    self._app.main_window,
                    "MPR — Use SliceLocation?",
                    "This series has no ImagePositionPatient. Use SliceLocation for "
                    "slice order and MPR? (SliceLocation is populated for these images.)",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    use_slice_location_fallback = True
                    groups = get_orientation_groups(
                        request.datasets,
                        use_slice_location_if_no_position=True,
                    )
            if len(groups) == 0:
                QMessageBox.critical(
                    self._app.main_window,
                    _TITLE_MPR_ERROR,
                    "No slices with valid orientation could be used. "
                    "Ensure the series has ImagePositionPatient (or SliceLocation) and "
                    "ImageOrientationPatient.",
                )
                return None
        if len(groups) > 1:
            dlg = MprOrientationChoiceDialog(groups, self._app.main_window)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return None
            datasets_to_use = dlg.get_selected_datasets()
            if not datasets_to_use:
                return None
        else:
            datasets_to_use = groups[0][1]
        return datasets_to_use, use_slice_location_fallback

    def _mpr_request_build_volume(
        self, datasets_to_use: list[Any], use_slice_location_fallback: bool
    ):
        """Build ``MprVolume`` or show an error and return ``None``."""
        try:
            return MprVolume.from_datasets(
                datasets_to_use,
                use_slice_location_if_no_position=use_slice_location_fallback,
            )
        except MprVolumeError:
            QMessageBox.critical(
                self._app.main_window,
                _TITLE_MPR_ERROR,
                "Cannot build the MPR volume. Details were withheld to protect private data.",
            )
            return None

    def _mpr_request_try_cache(
        self,
        target_idx: int,
        request,
        volume,
        datasets_to_use: list[Any],
    ) -> bool:
        """
        Attempt a disk-cache hit and activate if found.

        Returns:
            True when a cache hit activated MPR (caller should return).
        """
        if self._cache is None:
            return False
        try:
            cache_normal = request.output_plane.normal
            n_ds = len(datasets_to_use)
            try:
                series_uid = str(datasets_to_use[0].SeriesInstanceUID)
            except (AttributeError, IndexError):
                series_uid = "__unknown__"
            from core.mpr_cache import _make_cache_key
            key = _make_cache_key(
                series_uid=series_uid,
                normal=cache_normal,
                output_spacing_mm=request.output_spacing_mm,
                output_thickness_mm=request.output_thickness_mm,
                interpolation=request.interpolation,
                source_dataset_count=n_ds,
            )
            hit = self._cache.load(key)
            if hit is not None:
                _mpr_log(f"Cache hit: key={key[:12]}...")
                slices, stack, meta = hit
                cached_result = MprResult(
                    slices=slices,
                    slice_stack=stack,
                    output_spacing_mm=tuple(meta["output_spacing_mm"]),
                    output_thickness_mm=float(meta["output_thickness_mm"]),
                    source_volume=volume,
                    interpolation=meta["interpolation"],
                    rescale_slope=meta.get("rescale_slope"),
                    rescale_intercept=meta.get("rescale_intercept"),
                    combine_mode=meta.get("combine_mode", "none"),
                    slab_thickness_mm=float(meta.get("slab_thickness_mm", 0.0)),
                )
                self._activate_mpr(
                    target_idx,
                    cached_result,
                    request.orientation_label,
                    request=request,
                )
                return True
            _mpr_log(f"Cache miss: key={key[:12]}...")
        except Exception as exc:
            print_redacted(f"[MprController] Cache lookup error: {exc}")
        return False

    def _mpr_request_start_worker(self, target_idx: int, request, volume) -> None:
        """Create the background MPR worker, progress dialog, and start the build."""
        worker = MprBuilder.create_worker(
            source_volume=volume,
            output_plane=request.output_plane,
            output_spacing_mm=request.output_spacing_mm,
            output_thickness_mm=request.output_thickness_mm,
            interpolation=request.interpolation,
            combine_mode=getattr(request, "combine_mode", "none"),
            slab_thickness_mm=float(getattr(request, "slab_thickness_mm", 0.0)),
        )

        progress_dlg = QProgressDialog(
            f"Building MPR ({request.orientation_label})…",
            "Cancel",
            0,
            100,
            self._app.main_window,
        )
        progress_dlg.setWindowTitle("MPR Build")
        progress_dlg.setMinimumDuration(0)
        progress_dlg.setAutoClose(True)
        progress_dlg.setAutoReset(True)
        progress_dlg.setModal(True)
        progress_dlg.show()

        worker.progress.connect(progress_dlg.setValue)
        progress_dlg.canceled.connect(worker.cancel)

        orientation_label = request.orientation_label

        def on_finished(result: MprResult) -> None:
            progress_dlg.close()
            self._workers.pop(target_idx, None)
            _mpr_log(
                f"Build finished for window {target_idx}: "
                f"slices={result.n_slices} interpolation={result.interpolation}"
            )
            if self._cache is not None:
                try:
                    self._cache.save(result)
                except Exception as exc:
                    print_redacted(f"[MprController] Cache save error: {exc}")

            image_viewer = self._get_image_viewer(target_idx)
            if image_viewer is None:
                QMessageBox.critical(
                    self._app.main_window,
                    _TITLE_MPR_ERROR,
                    "Cannot activate MPR: image viewer not ready. Please try again.",
                )
                return

            self._activate_mpr(
                target_idx, result, orientation_label, request=request
            )

        def on_error(msg: str) -> None:
            progress_dlg.close()
            self._workers.pop(target_idx, None)
            if "cancelled" in msg.lower() or "canceled" in msg.lower():
                return
            QMessageBox.critical(
                self._app.main_window,
                _TITLE_MPR_ERROR,
                f"MPR build failed:\n{msg}",
            )

        worker.finished.connect(on_finished)
        worker.error.connect(on_error)

        self._workers[target_idx] = worker
        worker.start()

    # ------------------------------------------------------------------
    # Internal: activate MPR in a subwindow
    # ------------------------------------------------------------------


    def _activate_mpr(
        self,
        idx: int,
        result: MprResult,
        orientation_label: str,
        request: Any | None = None,
    ) -> None:
        """
        Load an MprResult into subwindow *idx* and switch it to MPR mode.

        Args:
            idx:               Target subwindow index.
            result:            Completed MPR build result.
            orientation_label: Human-readable orientation string.
            request:           Optional ``MprRequest`` from the dialog (seeds
                               ``mpr_combine_*`` from dialog slab settings).
        """
        data = self._app.subwindow_data.get(idx)
        if data is None:
            return

        self._detached_mpr_payload = None
        _mpr_log(
            f"Activating MPR: window={idx} "
            f"has_image_viewer={self._get_image_viewer(idx) is not None} "
            f"has_subwindow_data={idx in self._app.subwindow_data} "
            f"result_slices={result.n_slices}"
        )

        self._ensure_mpr_previous_state(data)
        source_ds = result.source_volume.source_datasets[0]
        self._activate_write_mpr_fields(
            idx, data, result, orientation_label, request, source_ds
        )
        self._sync_slice_navigator_for_mpr(idx, result.n_slices, 0)
        self._set_tools_enabled(idx, enabled=False)
        self._reset_window_level_for_mpr(idx, source_ds)
        self.display_mpr_slice(idx, 0)
        self._fit_image_viewer_after_mpr(idx)
        self._apply_mpr_banner(idx, data)
        self._activate_focus_subwindow(idx)
        self._sync_intensity_projection_if_focused(idx, data)
        self.mpr_activated.emit(idx)

    def _activate_write_mpr_fields(
        self,
        idx: int,
        data: dict[str, Any],
        result: MprResult,
        orientation_label: str,
        request: Any | None,
        source_ds: Any,
    ) -> None:
        """Install MPR result fields and seed combine state on *data*."""
        data["is_mpr"] = True
        data["mpr_result"] = result
        data["mpr_orientation"] = orientation_label
        data["mpr_slice_index"] = 0
        data["mpr_source_dataset"] = source_ds
        data["current_study_uid"] = str(getattr(source_ds, "StudyInstanceUID", ""))
        data["current_series_uid"] = get_composite_series_key(source_ds)
        data["current_datasets"] = result.source_volume.source_datasets
        seed_mpr_combine_state(data, request, float(result.output_thickness_mm))
        _mpr_log(
            f"Activate MPR in window {idx}: "
            f"orientation={orientation_label} "
            f"output_slices={result.n_slices} "
            f"output_spacing={result.output_spacing_mm} "
            f"output_thickness={result.output_thickness_mm:.4f}"
        )

    def _activate_focus_subwindow(self, idx: int) -> None:
        """Focus the target subwindow after MPR activation."""
        try:
            subwindow = self._app.multi_window_layout.get_subwindow(idx)
            if subwindow is not None:
                subwindow.setFocus()
        except Exception:
            pass

    def _get_image_viewer(self, idx: int):
        """
        Return the ImageViewer widget for subwindow *idx*.

        Uses multi_window_layout rather than the managers dict, since
        image_viewer is not stored in the managers dict by default.

        Args:
            idx: Subwindow index.

        Returns:
            ImageViewer instance, or None if not found.
        """
        try:
            subwindow = self._app.multi_window_layout.get_subwindow(idx)
            if subwindow is not None:
                return getattr(subwindow, "image_viewer", None)
        except Exception:
            pass
        return None

    def _collect_loaded_series(self) -> dict[str, dict[str, Any]]:
        """
        Build the ``loaded_series`` dict required by MprDialog.

        Returns a mapping of ``series_key → info_dict`` for all currently
        loaded series across all studies.

        Returns:
            Dict with keys: "description", "modality", "n_slices",
            "study_uid", "datasets".
        """
        result: dict[str, dict[str, Any]] = {}
        try:
            current_studies = self._app.current_studies
        except AttributeError:
            return result

        for study_uid, series_dict in current_studies.items():
            for series_key, datasets in series_dict.items():
                if not datasets:
                    continue
                ds0 = datasets[0]
                description = getattr(ds0, "SeriesDescription", "") or ""
                modality = getattr(ds0, "Modality", "") or ""
                result[series_key] = {
                    "description": description,
                    "modality": modality,
                    "n_slices": len(datasets),
                    "study_uid": study_uid,
                    "datasets": datasets,
                }
        return result


    def _build_overlay_dataset(self, result: MprResult, slice_index: int):
        """
        Build a synthetic dataset for MPR overlay text.

        The source metadata is preserved for patient/study/series text, but
        slice-specific DICOM fields that are meaningless for a resampled stack
        are replaced or removed:
        - ``InstanceNumber`` becomes the MPR stack index (1-based).
        - ``ImageOrientationPatient`` matches the **displayed** MPR plane (row/column
          cosines from ``slice_stack.planes[slice_index]``) so direction labels and
          geometry match the reformatted view.
        - ``PixelSpacing`` matches ``result.output_spacing_mm`` for scale markers.
        - ``SliceLocation`` is removed.
        - ``ImagePositionPatient`` is removed.

        Args:
            result:      Current MPR result.
            slice_index: Zero-based MPR stack index.

        Returns:
            Dataset-like object suitable for ``DICOMParser``.
        """
        # pydicom Dataset.copy() is ``copy.copy`` (shallow): mutating tags on the
        # copy still updates the original dataset in ``current_studies``, which
        # corrupts native-series overlays (InstanceNumber / IOP). Deep-copy the
        # first source slice so MPR-only metadata edits stay isolated.
        source_ds = copy.deepcopy(result.source_volume.source_datasets[0])
        source_ds.InstanceNumber = int(slice_index + 1)
        self._overlay_apply_thickness(source_ds, result)
        self._overlay_apply_orientation(source_ds, result, slice_index)
        self._overlay_apply_spacing(source_ds, result)
        self._overlay_strip_location_attrs(source_ds)
        return source_ds

    def _overlay_apply_thickness(self, source_ds: Any, result: MprResult) -> None:
        """Set SliceThickness / SpacingBetweenSlices from MPR output thickness."""
        try:
            source_ds.SliceThickness = float(result.output_thickness_mm)
        except Exception:
            pass
        try:
            source_ds.SpacingBetweenSlices = float(result.output_thickness_mm)
        except Exception:
            pass

    def _overlay_apply_orientation(
        self, source_ds: Any, result: MprResult, slice_index: int
    ) -> None:
        """Set ImageOrientationPatient from the displayed MPR plane."""
        planes = getattr(result.slice_stack, "planes", None) or []
        si = int(slice_index)
        if not planes or not (0 <= si < len(planes)):
            return
        plane = planes[si]
        rc = np.asarray(plane.row_cosine, dtype=float).reshape(-1)
        cc = np.asarray(plane.col_cosine, dtype=float).reshape(-1)
        if rc.size != 3 or cc.size != 3:
            return
        try:
            source_ds.ImageOrientationPatient = [
                float(rc[0]),
                float(rc[1]),
                float(rc[2]),
                float(cc[0]),
                float(cc[1]),
                float(cc[2]),
            ]
        except Exception:
            pass

    def _overlay_apply_spacing(self, source_ds: Any, result: MprResult) -> None:
        """Set PixelSpacing from MPR output spacing."""
        try:
            rs, cs = result.output_spacing_mm[0], result.output_spacing_mm[1]
            source_ds.PixelSpacing = [float(rs), float(cs)]
        except Exception:
            pass

    def _overlay_strip_location_attrs(self, source_ds: Any) -> None:
        """Remove SliceLocation / ImagePositionPatient from the overlay dataset."""
        for attr in ("SliceLocation", "ImagePositionPatient"):
            if hasattr(source_ds, attr):
                try:
                    delattr(source_ds, attr)
                except Exception:
                    setattr(source_ds, attr, "")

    @staticmethod
    def _compute_mpr_combine_range(
        n_slices: int, slice_index: int, n_planes: int
    ) -> tuple[int, int]:
        """Slab [start, end] for MPR combine — delegates to ``core.mpr_view_math``."""
        return compute_mpr_combine_range(n_slices, slice_index, n_planes)

    @staticmethod
    def _build_mpr_banner_text(data: dict[str, Any]) -> str:
        """Active-MPR banner text — delegates to ``core.mpr_view_math``."""
        return build_mpr_banner_text(data)

    def _set_tools_enabled(self, idx: int, enabled: bool) -> None:
        """
        Enable or disable interactive tools for a subwindow.

        When ``enabled=False``, the subwindow's ROI manager, measurement tool,
        and annotation tools are deactivated.  The image_viewer is put into
        "pan" mode (the only safe mode for MPR).

        Args:
            idx:     Subwindow index.
            enabled: True to restore normal tool access; False to restrict.
        """
        image_viewer = self._get_image_viewer(idx)

        if image_viewer is None:
            return

        if not enabled:
            # Force pan mode — all ROI/annotation modes are disabled.
            image_viewer.set_mouse_mode("pan")
            # Optionally disable the mode-switching signals so the user
            # can't accidentally activate ROI tools from the context menu.
            # (The context menu will not show tool options for MPR views;
            # that gate is handled in the view's context menu builder via
            # the image_viewer.is_mpr_view_callback below.)
            if not hasattr(image_viewer, "_mpr_mode_override"):
                image_viewer._mpr_mode_override = False
            image_viewer._mpr_mode_override = True
        else:
            if hasattr(image_viewer, "_mpr_mode_override"):
                image_viewer._mpr_mode_override = False

    def _reset_window_level_for_mpr(self, idx: int, source_dataset) -> None:
        """
        Reset window/level controls to defaults from the MPR source dataset.

        This ensures that when a new MPR is created, we use the window/level
        from the new source series, not stale values from a previous series.

        Per-pane rescale / HU alignment: ``ViewStateManager`` and the target
        ``ImageViewer`` rescale toggle are **always** updated for *idx* so MPR
        created in an unfocused pane still applies slope/intercept before the
        first ``display_mpr_slice``. Global toolbar W/L spinboxes and the main
        window rescale toggle are updated only when *idx* is the focused pane.

        Args:
            idx: Subwindow index
            source_dataset: Source DICOM dataset for the MPR
        """
        focused = getattr(self._app, "focused_subwindow_index", -1)
        wl_controls = getattr(self._app, "window_level_controls", None)

        try:
            from core.dicom_processor import DICOMProcessor
            from core.dicom_rescale import get_rescale_parameters
            from core.dicom_window_level import (
                get_window_level_from_dataset,
                get_window_level_presets_from_dataset,
            )

            rescale_slope, rescale_intercept, rescale_type = get_rescale_parameters(
                source_dataset
            )
            if (
                rescale_type is None
                and rescale_slope is not None
                and rescale_intercept is not None
            ):
                rescale_type = DICOMProcessor.infer_rescale_type(
                    source_dataset, rescale_slope, rescale_intercept, None
                )

            view_state_manager = self._mpr_wl_sync_pane_rescale(
                idx, focused, rescale_slope, rescale_intercept, rescale_type
            )
            wc, ww, is_rescaled = self._mpr_wl_resolve_center_width(
                source_dataset,
                rescale_slope,
                rescale_intercept,
                get_window_level_presets_from_dataset,
                get_window_level_from_dataset,
            )
            self._mpr_wl_apply_values(
                idx,
                focused,
                wl_controls,
                view_state_manager,
                wc,
                ww,
                is_rescaled,
                rescale_slope,
                rescale_intercept,
                rescale_type,
            )
        except Exception as exc:
            print_redacted(f"[MprController] Failed to reset W/L for MPR in window {idx}: {exc}")

    def _mpr_wl_sync_pane_rescale(
        self,
        idx: int,
        focused: int,
        rescale_slope,
        rescale_intercept,
        rescale_type,
    ):
        """Sync per-pane rescale state; also sync main-window toggle when focused."""
        managers = self._app.subwindow_managers.get(idx, {})
        view_state_manager = managers.get("view_state_manager")
        if view_state_manager is None:
            return None
        view_state_manager.set_rescale_parameters(
            rescale_slope, rescale_intercept, rescale_type
        )
        use_rescaled_default = (
            rescale_slope is not None and rescale_intercept is not None
        )
        view_state_manager.use_rescaled_values = use_rescaled_default
        if idx == focused and hasattr(self._app, "main_window"):
            self._app.main_window.set_rescale_toggle_state(use_rescaled_default)
        image_viewer = self._get_image_viewer(idx)
        if image_viewer is not None:
            image_viewer.set_rescale_toggle_state(use_rescaled_default)
        return view_state_manager

    @staticmethod
    def _mpr_wl_resolve_center_width(
        source_dataset,
        rescale_slope,
        rescale_intercept,
        get_presets,
        get_single_wl,
    ) -> tuple[Any, Any, Any]:
        """Resolve window center/width from presets or single-tag fallback."""
        presets = get_presets(source_dataset, rescale_slope, rescale_intercept)
        if presets:
            wc, ww, is_rescaled, _preset_name = presets[0]
            return wc, ww, is_rescaled
        wc, ww, is_rescaled = get_single_wl(
            source_dataset, rescale_slope, rescale_intercept
        )
        return wc, ww, is_rescaled

    def _mpr_wl_apply_values(
        self,
        idx: int,
        focused: int,
        wl_controls,
        view_state_manager,
        wc,
        ww,
        is_rescaled,
        rescale_slope,
        rescale_intercept,
        rescale_type,
    ) -> None:
        """Write W/L into pane view state and optionally sync shared toolbar."""
        if wc is None or ww is None or ww <= 0:
            return
        if view_state_manager is not None:
            view_state_manager.current_window_center = wc
            view_state_manager.current_window_width = ww
            view_state_manager.window_level_user_modified = False
        if idx != focused or wl_controls is None:
            return
        unit = None
        if rescale_slope is not None and rescale_intercept is not None:
            unit = rescale_type
        wl_controls.set_window_level(wc, ww, block_signals=False, unit=unit)
        _mpr_log(f"Reset W/L for MPR: center={wc:.1f} width={ww:.1f} rescaled={is_rescaled}")

    @staticmethod
    def _get_preferred_mpr_window_level(view_state_manager, wl_controls, array: np.ndarray):
        """
        Return the window/level to use for MPR display.

        Preference order:
        1. The target pane's own stored window/level in ``ViewStateManager``.
        2. The shared toolbar controls (focused pane behavior).
        3. Auto window/level from the current pixel data.
        """
        if view_state_manager is not None:
            try:
                wc = float(view_state_manager.current_window_center)
                ww = float(view_state_manager.current_window_width)
                if ww > 0:
                    return wc, ww
            except (AttributeError, TypeError, ValueError):
                pass
        return MprController._get_window_level(wl_controls, array)

    @staticmethod
    def _get_window_level(wl_controls, array: np.ndarray):
        """
        Read the current window centre/width from the window-level controls.

        Falls back to (percentile-based) auto W/L from the array if controls
        are unavailable.

        Args:
            wl_controls: WindowLevelControls widget (may be None).
            array:       The pixel array to compute auto W/L from.

        Returns:
            (window_center, window_width) as floats.
        """
        if wl_controls is not None:
            try:
                wc = float(wl_controls.window_center)
                ww = float(wl_controls.window_width)
                if ww > 0:
                    return wc, ww
            except (AttributeError, TypeError, ValueError):
                pass

        # Auto W/L (percentile) — delegates to core.mpr_view_math.
        return auto_window_level(array)

    @staticmethod
    def _array_to_pil(
        array: np.ndarray, window_center: float, window_width: float
    ) -> Image.Image | None:
        """
        Convert a 2-D float32 array to an 8-bit grayscale PIL Image.

        Applies a linear window/level mapping:
            out = clip((val - (wc - ww/2)) / ww * 255, 0, 255).

        Args:
            array:         2-D float32 pixel array.
            window_center: Window centre (HU or raw value).
            window_width:  Window width (> 0).

        Returns:
            8-bit grayscale PIL Image, or None on failure.
        """
        return array_to_pil(array, window_center, window_width)

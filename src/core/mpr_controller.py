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

from typing import TYPE_CHECKING, Dict, Optional

import numpy as np
from PIL import Image
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QDialog, QMessageBox, QProgressDialog

from core.mpr_builder import MprBuilder, MprBuilderWorker, MprResult
from core.mpr_cache import MprCache
from core.mpr_volume import (
    MprVolume,
    MprVolumeError,
    get_orientation_groups,
    has_slice_location_fallback_available,
)
from core.dicom_parser import DICOMParser
from gui.dialogs.mpr_orientation_choice_dialog import MprOrientationChoiceDialog
from utils.dicom_utils import get_composite_series_key
from utils.debug_flags import DEBUG_MPR


def _mpr_log(message: str) -> None:
    """Print an MPR debug message when DEBUG_MPR is enabled."""
    if DEBUG_MPR:
        print(f"[DEBUG-MPR] {message}")

if TYPE_CHECKING:
    from main import DICOMViewerApp


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
    """

    def __init__(self, app: "DICOMViewerApp") -> None:
        """
        Args:
            app: The DICOMViewerApp instance (provides access to all
                 subwindow managers, config, etc.).
        """
        super().__init__()
        self._app = app
        self._workers: Dict[int, MprBuilderWorker] = {}  # idx → active worker
        self._cache: Optional[MprCache] = None
        self._init_cache()

    # ------------------------------------------------------------------
    # Cache initialisation
    # ------------------------------------------------------------------

    def _init_cache(self) -> None:
        """Set up the disk cache in the app's config directory."""
        try:
            cache_dir = self._app.config_manager.config_dir / "mpr_cache"
            max_mb = int(self._app.config_manager.get("mpr_cache_max_mb", 500))
            self._cache = MprCache(cache_dir=cache_dir, max_size_mb=max_mb)
            _mpr_log(f"Cache initialised: dir={cache_dir} max_mb={max_mb}")
        except Exception as exc:
            print(f"[MprController] Cache init failed: {exc}; caching disabled.")
            self._cache = None

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

    def clear_mpr(self, idx: int) -> None:
        """
        Clear MPR mode from subwindow *idx* and restore normal display.

        Cancels any in-progress build for this subwindow.

        Args:
            idx: Subwindow index to clear.
        """
        # Cancel any active build.
        worker = self._workers.pop(idx, None)
        if worker is not None:
            worker.cancel()
            worker.quit()
            worker.wait(2000)

        data = self._app.subwindow_data.get(idx)
        if data is None:
            return

        previous_state = data.get("mpr_previous_state")
        image_viewer = self._get_image_viewer(idx)

        # Remove MPR-specific keys.
        for key in (
            "is_mpr",
            "mpr_result",
            "mpr_orientation",
            "mpr_slice_index",
            "mpr_source_dataset",
            "mpr_previous_state",
        ):
            data.pop(key, None)

        # Re-enable tools.
        self._set_tools_enabled(idx, enabled=True)

        # Reset the overlay banner.
        managers = self._app.subwindow_managers.get(idx, {})
        overlay_manager = managers.get("overlay_manager")
        if overlay_manager is not None and hasattr(overlay_manager, "set_mpr_banner"):
            overlay_manager.set_mpr_banner(None)

        if isinstance(previous_state, dict):
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
                    print(f"[MprController] Failed to restore prior slice in window {idx}: {exc}")

            if idx == getattr(self._app, "focused_subwindow_index", -1):
                self._app.current_dataset = previous_dataset
                self._app.current_slice_index = previous_slice_index
                self._app.current_study_uid = previous_study_uid
                self._app.current_series_uid = previous_series_uid
                self._app.current_datasets = previous_state.get("current_datasets", [])
        else:
            data["current_dataset"] = None
            data["current_slice_index"] = 0
            data["current_study_uid"] = ""
            data["current_series_uid"] = ""
            data["current_datasets"] = []

        # If there was no prior regular-series state to restore, actively clear
        # the view so the last rendered MPR slice does not remain visible.
        if data.get("current_dataset") is None and image_viewer is not None:
            try:
                if overlay_manager is not None:
                    overlay_manager.clear_overlay_items(image_viewer.scene)
                image_viewer.scene.clear()
                image_viewer.image_item = None
                image_viewer.original_image = None
                image_viewer.viewport().update()
            except Exception as exc:
                print(f"[MprController] Failed to clear MPR view in window {idx}: {exc}")

            view_state_manager = self._app.subwindow_managers.get(idx, {}).get("view_state_manager")
            if view_state_manager is not None:
                try:
                    view_state_manager.set_current_data_context(None, {}, "", "", 0)
                    view_state_manager.set_current_series_identifier(None)
                except Exception as exc:
                    print(f"[MprController] Failed to reset view state for window {idx}: {exc}")

            if idx == getattr(self._app, "focused_subwindow_index", -1):
                self._app.current_dataset = None
                self._app.current_slice_index = 0
                self._app.current_study_uid = ""
                self._app.current_series_uid = ""
                self._app.current_datasets = []

        # Reset shared slice navigator if this is the focused window.
        try:
            if (
                hasattr(self._app, "slice_navigator")
                and idx == getattr(self._app, "focused_subwindow_index", -1)
            ):
                datasets = data.get("current_datasets") or []
                self._app.slice_navigator.set_total_slices(len(datasets))
                self._app.slice_navigator.blockSignals(True)
                self._app.slice_navigator.current_slice_index = data.get("current_slice_index", 0)
                self._app.slice_navigator.blockSignals(False)
        except Exception:
            pass

        # Update series navigator dot indicators now that this window's content changed.
        try:
            if hasattr(self._app, "series_navigator") and hasattr(self._app, "_get_subwindow_assignments"):
                assignments = self._app._get_subwindow_assignments()
                self._app.series_navigator.set_subwindow_assignments(assignments)
        except Exception:
            # Dot indicators are non-critical; ignore failures here.
            pass

    def display_mpr_slice(self, idx: int, slice_index: int) -> None:
        """
        Display a single MPR slice in subwindow *idx*.

        Called when the slice navigator advances within an MPR view.

        Args:
            idx:         Subwindow index.
            slice_index: Zero-based index into the MprResult.slices list.
        """
        data = self._app.subwindow_data.get(idx, {})
        if not data.get("is_mpr"):
            return
        result: Optional[MprResult] = data.get("mpr_result")
        if result is None or slice_index >= result.n_slices:
            return

        data["mpr_slice_index"] = slice_index

        image_viewer = self._get_image_viewer(idx)
        wl_controls = getattr(self._app, "window_level_controls", None)
        managers = self._app.subwindow_managers.get(idx, {})

        if image_viewer is None:
            return

        raw_array = result.slices[slice_index]
        # Apply rescale slope/intercept from source series.
        array = result.apply_rescale(raw_array)

        # Determine window/level from controls (or fall back to data min/max).
        wc, ww = self._get_window_level(wl_controls, array)

        pil_image = self._array_to_pil(array, wc, ww)
        if pil_image is None:
            return

        overlay_dataset = self._build_overlay_dataset(result, slice_index)
        data["current_slice_index"] = slice_index
        data["current_dataset"] = overlay_dataset
        data["mpr_source_dataset"] = result.source_volume.source_datasets[0]
        current_study_uid = data.get("current_study_uid", "")
        current_series_uid = data.get("current_series_uid", "")

        # Keep the normal view-state pipeline informed even though MPR bypasses
        # SliceDisplayManager. This preserves overlay anchoring on pan/zoom and
        # keeps viewer state in sync with what is on screen.
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
                print(f"[MprController] Failed to update MPR view state in window {idx}: {exc}")

        is_same_series = True  # Always preserve zoom when scrolling MPR.
        image_viewer.set_image(pil_image, preserve_view=is_same_series)

        overlay_manager = managers.get("overlay_manager")
        if overlay_manager is not None:
            try:
                overlay_manager.create_overlay_items(
                    image_viewer.scene,
                    DICOMParser(overlay_dataset),
                    total_slices=result.n_slices,
                )
                if hasattr(overlay_manager, "set_mpr_banner"):
                    orientation_label = data.get("mpr_orientation", "MPR")
                    overlay_manager.set_mpr_banner(f"MPR - {orientation_label}")
            except Exception as exc:
                print(f"[MprController] Failed to refresh MPR overlay in window {idx}: {exc}")

        if idx == getattr(self._app, "focused_subwindow_index", -1):
            self._app.current_dataset = overlay_dataset
            self._app.current_slice_index = slice_index
        _mpr_log(
            f"Display slice window={idx} "
            f"index={slice_index + 1}/{result.n_slices} "
            f"shape={array.shape} min={float(np.min(array)):.4f} "
            f"max={float(np.max(array)):.4f} mean={float(np.mean(array)):.4f}"
        )

    # ------------------------------------------------------------------
    # Internal: dialog response handler
    # ------------------------------------------------------------------

    def _on_mpr_requested(self, target_idx: int, request) -> None:
        """
        Validate the request, check cache, and start the build (or load from cache).

        Args:
            target_idx: Subwindow to host the MPR view.
            request:    MprRequest from the dialog.
        """
        # Cancel any existing build for this subwindow.
        old_worker = self._workers.pop(target_idx, None)
        if old_worker:
            old_worker.cancel()
            old_worker.quit()
            old_worker.wait(1000)

        # If the series has no valid geometry, offer SliceLocation fallback when available.
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
                    "MPR Error",
                    "No slices with valid orientation could be used. "
                    "Ensure the series has ImagePositionPatient (or SliceLocation) and "
                    "ImageOrientationPatient.",
                )
                return
        if len(groups) > 1:
            dlg = MprOrientationChoiceDialog(groups, self._app.main_window)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            datasets_to_use = dlg.get_selected_datasets()
            if not datasets_to_use:
                return
        else:
            datasets_to_use = groups[0][1]

        # Build the source volume from the chosen (single-orientation) slice set.
        try:
            volume = MprVolume.from_datasets(
                datasets_to_use,
                use_slice_location_if_no_position=use_slice_location_fallback,
            )
        except MprVolumeError as exc:
            QMessageBox.critical(
                self._app.main_window,
                "MPR Error",
                f"Cannot build MPR volume:\n{exc}",
            )
            return

        _mpr_log(
            "MPR request: "
            f"target_window={target_idx} "
            f"orientation={request.orientation_label} "
            f"spacing={request.output_spacing_mm:.4f} mm "
            f"thickness={request.output_thickness_mm:.4f} mm "
            f"interpolation={request.interpolation} "
            f"source_slices={len(datasets_to_use)}"
        )

        # Check disk cache.
        if self._cache is not None:
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
                    # Reconstruct MprResult from cache hit.
                    cached_result = MprResult(
                        slices=slices,
                        slice_stack=stack,
                        output_spacing_mm=tuple(meta["output_spacing_mm"]),
                        output_thickness_mm=float(meta["output_thickness_mm"]),
                        source_volume=volume,
                        interpolation=meta["interpolation"],
                        rescale_slope=meta.get("rescale_slope"),
                        rescale_intercept=meta.get("rescale_intercept"),
                    )
                    self._activate_mpr(target_idx, cached_result, request.orientation_label)
                    return
                _mpr_log(f"Cache miss: key={key[:12]}...")
            except Exception as exc:
                print(f"[MprController] Cache lookup error: {exc}")

        # No cache hit — run the builder in a background thread.
        worker = MprBuilder.create_worker(
            source_volume=volume,
            output_plane=request.output_plane,
            output_spacing_mm=request.output_spacing_mm,
            output_thickness_mm=request.output_thickness_mm,
            interpolation=request.interpolation,
        )

        # Progress dialog.
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
            # Save to cache.
            if self._cache is not None:
                try:
                    self._cache.save(result)
                except Exception as exc:
                    print(f"[MprController] Cache save error: {exc}")
            self._activate_mpr(target_idx, result, orientation_label)

        def on_error(msg: str) -> None:
            progress_dlg.close()
            self._workers.pop(target_idx, None)
            if "cancelled" in msg.lower() or "canceled" in msg.lower():
                return
            QMessageBox.critical(
                self._app.main_window,
                "MPR Error",
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
        self, idx: int, result: MprResult, orientation_label: str
    ) -> None:
        """
        Load an MprResult into subwindow *idx* and switch it to MPR mode.

        Args:
            idx:               Target subwindow index.
            result:            Completed MPR build result.
            orientation_label: Human-readable orientation string.
        """
        data = self._app.subwindow_data.get(idx)
        if data is None:
            return

        if "mpr_previous_state" not in data:
            data["mpr_previous_state"] = {
                "current_dataset": data.get("current_dataset"),
                "current_slice_index": data.get("current_slice_index", 0),
                "current_series_uid": data.get("current_series_uid", ""),
                "current_study_uid": data.get("current_study_uid", ""),
                "current_datasets": list(data.get("current_datasets", [])),
            }

        source_ds = result.source_volume.source_datasets[0]

        # Store MPR state in subwindow_data.
        data["is_mpr"] = True
        data["mpr_result"] = result
        data["mpr_orientation"] = orientation_label
        data["mpr_slice_index"] = 0
        data["mpr_source_dataset"] = source_ds
        data["current_study_uid"] = str(getattr(source_ds, "StudyInstanceUID", ""))
        data["current_series_uid"] = get_composite_series_key(source_ds)
        data["current_datasets"] = result.source_volume.source_datasets
        _mpr_log(
            f"Activate MPR in window {idx}: "
            f"orientation={orientation_label} "
            f"output_slices={result.n_slices} "
            f"output_spacing={result.output_spacing_mm} "
            f"output_thickness={result.output_thickness_mm:.4f}"
        )

        managers = self._app.subwindow_managers.get(idx, {})

        # Update shared slice navigator to MPR stack length (only when this
        # subwindow is the focused one; if not, it will update on next focus).
        try:
            if hasattr(self._app, "slice_navigator") and idx == getattr(
                self._app, "focused_subwindow_index", -1
            ):
                self._app.slice_navigator.set_total_slices(result.n_slices)
                self._app.slice_navigator.blockSignals(True)
                self._app.slice_navigator.current_slice_index = 0
                self._app.slice_navigator.blockSignals(False)
        except Exception:
            pass

        # Disable ROI/measurement/annotation tools.
        self._set_tools_enabled(idx, enabled=False)

        # Reset window/level from the new MPR source series to avoid using
        # stale values from a previous series.
        self._reset_window_level_for_mpr(idx, source_ds)

        # Display first slice.
        self.display_mpr_slice(idx, 0)
        image_viewer = self._get_image_viewer(idx)
        if image_viewer is not None:
            try:
                image_viewer.fit_to_view(center_image=True)
            except Exception:
                pass

        # Show MPR banner via OverlayManager.
        overlay_manager = managers.get("overlay_manager")
        if overlay_manager is not None and hasattr(overlay_manager, "set_mpr_banner"):
            overlay_manager.set_mpr_banner(f"MPR - {orientation_label}")

        # Focus the subwindow so the user sees the result immediately.
        try:
            subwindow = self._app.multi_window_layout.get_subwindow(idx)
            if subwindow is not None:
                subwindow.setFocus()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

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

    def _collect_loaded_series(self) -> dict:
        """
        Build the ``loaded_series`` dict required by MprDialog.

        Returns a mapping of ``series_key → info_dict`` for all currently
        loaded series across all studies.

        Returns:
            Dict with keys: "description", "modality", "n_slices",
            "study_uid", "datasets".
        """
        result: dict = {}
        try:
            current_studies: dict = self._app.current_studies
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
        - ``SliceLocation`` is removed.
        - ``ImagePositionPatient`` is removed.

        Args:
            result:      Current MPR result.
            slice_index: Zero-based MPR stack index.

        Returns:
            Dataset-like object suitable for ``DICOMParser``.
        """
        source_ds = result.source_volume.source_datasets[0].copy()
        source_ds.InstanceNumber = int(slice_index + 1)
        for attr in ("SliceLocation", "ImagePositionPatient"):
            if hasattr(source_ds, attr):
                try:
                    delattr(source_ds, attr)
                except Exception:
                    setattr(source_ds, attr, "")
        return source_ds

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

        Args:
            idx: Subwindow index
            source_dataset: Source DICOM dataset for the MPR
        """
        # Only update controls if this is the focused window
        if idx != getattr(self._app, "focused_subwindow_index", -1):
            return

        wl_controls = getattr(self._app, "window_level_controls", None)
        if wl_controls is None:
            return

        try:
            from core.dicom_window_level import get_window_level_presets_from_dataset, get_window_level_from_dataset
            from core.dicom_rescale import get_rescale_parameters

            # Get rescale parameters
            rescale_slope, rescale_intercept, rescale_type = get_rescale_parameters(source_dataset)

            # Update view_state_manager with rescale parameters so it knows the values are rescaled
            managers = self._app.subwindow_managers.get(idx, {})
            view_state_manager = managers.get("view_state_manager")
            if view_state_manager is not None:
                view_state_manager.set_rescale_parameters(rescale_slope, rescale_intercept, rescale_type)
                # Set use_rescaled_values to True if rescale parameters exist
                if rescale_slope is not None and rescale_intercept is not None:
                    view_state_manager.use_rescaled_values = True

            # Try to get presets first
            presets = get_window_level_presets_from_dataset(
                source_dataset, rescale_slope, rescale_intercept
            )

            if presets:
                # Use first preset
                wc, ww, is_rescaled, preset_name = presets[0]
            else:
                # Fall back to single window/level or auto-calculation
                wc, ww, is_rescaled = get_window_level_from_dataset(
                    source_dataset, rescale_slope, rescale_intercept
                )

            if wc is not None and ww is not None and ww > 0:
                wl_controls.set_window_level(wc, ww, block_signals=False)
                _mpr_log(f"Reset W/L for MPR: center={wc:.1f} width={ww:.1f} rescaled={is_rescaled}")
        except Exception as exc:
            print(f"[MprController] Failed to reset W/L for MPR in window {idx}: {exc}")

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

        # Auto W/L: use 2nd–98th percentile of non-zero pixels.
        flat = array.ravel()
        flat = flat[np.isfinite(flat)]
        if flat.size == 0:
            return 0.0, 1.0
        p2, p98 = float(np.percentile(flat, 2)), float(np.percentile(flat, 98))
        ww = max(p98 - p2, 1.0)
        wc = (p2 + p98) / 2.0
        return wc, ww

    @staticmethod
    def _array_to_pil(
        array: np.ndarray, window_center: float, window_width: float
    ) -> Optional[Image.Image]:
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
        try:
            lo = window_center - window_width / 2.0
            scale = 255.0 / max(window_width, 1e-6)
            mapped = np.clip((array.astype(np.float32) - lo) * scale, 0.0, 255.0)
            uint8_arr = mapped.astype(np.uint8)
            return Image.fromarray(uint8_arr, mode="L")
        except Exception as exc:
            print(f"[MprController] array_to_pil failed: {exc}")
            return None

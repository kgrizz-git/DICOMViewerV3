"""
MPR Controller

Orchestrates the lifecycle of MPR views in the DICOM viewer.

Responsibilities:
  - Owns the MPR session/view registry (every MprResult, view IDs, pane
    mapping, admission); attached panes' subwindow_data is its live adapter.
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

import logging
from typing import Any

import numpy as np
from PIL import Image
from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog,
    QMessageBox,
    QProgressDialog,
)

from core.dicom_parser import DICOMParser
from core.mpr_builder import MprBuilder, MprBuilderWorker, MprResult
from core.mpr_cache import MprCache, resolve_cached_photometric_interpretation
from core.mpr_combine_slice_count import normalize_mpr_combine_slice_count
from core.mpr_overlay_dataset import build_overlay_dataset
from core.mpr_session_types import MprCombineState, MprDisplayState, MprViewMetadata
from core.mpr_stack_combine import apply_mpr_stack_combine
from core.mpr_view_display_state import restore_mpr_combine_state
from core.mpr_view_drag import new_drag_origin
from core.mpr_view_math import (
    array_to_pil,
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
from gui.lut_view_state import mpr_display_kwargs
from gui.mpr_activation import activate_built_mpr
from gui.mpr_controller_display_state import (
    install_apply_display_state,
    preferred_mpr_window_level,
    reset_window_level_for_mpr,
)
from gui.mpr_controller_sessions import (
    all_view_ids,
    clear_view,
    create_registry,
    detached_view_ids,
    discard_detached,
    emit_tiles_changed,
    pane_view_metadata,
    release_pane_reservation,
    reserve_pane_build,
    view_display_state,
    view_metadata,
    view_thumbnail_pixels,
)
from gui.mpr_controller_transactions import (
    attach_detached_view,
    capture_destination_snapshot,
    capture_mpr_payload,
    detach_mpr_view,
    detach_view_on_pane_reset,
    move_view,
    relocate_mpr_view,
    restore_failed_install,
    validate_install_request,
)
from gui.mpr_dicom_save_flow import prompt_save_mpr_as_dicom
from gui.mpr_pane_teardown import tear_down_mpr_at_subwindow
from gui.mpr_source_closure import release_all_mpr, release_closed_source_sessions
from gui.mpr_view_duplication import duplicate_view_into_pane
from gui.mpr_view_links import (
    SliceUpdate,
    flush_tile_refresh,
    link_group_of_pane,
    set_pane_slice,
    set_view_slice,
    unlink_view,
)
from gui.mpr_worker_fencing import (
    dataset_source_key,
    drop_build_registration,
    is_current_pane_build,
    note_build_started,
    retain_build_worker,
    retire_pane_worker,
    volume_source_key,
)
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

    Views are owned by the session/view registry; ``subwindow_data`` is the
    live display adapter of an attached view.

    Signals:
        mpr_activated(int):  Emitted with the subwindow index after an MPR view
                             was installed there and its first slice displayed.
        mpr_cleared(int):    Emitted with the subwindow index after that
                             view was discarded or moved away.
        mpr_detached(int):   Emitted with the former subwindow index when a view
                             leaves a pane but stays alive (detached).
        mpr_tiles_changed(object): Emitted once per transaction that can change
                             navigator tiles (frozenset of dirty view IDs).
    """

    mpr_activated = Signal(int)  # subwindow index
    mpr_cleared = Signal(int)    # subwindow index
    # Emitted when a view leaves a pane but stays alive (Clear Window, or it
    # was displaced by a successful build/drop). Argument: that pane index.
    mpr_detached = Signal(int)
    # Emitted once at the end of every transaction that can change navigator
    # tiles; the payload is a frozenset of attached view IDs whose tile pixels
    # must be regenerated. Tiles are keyed by stable view ID.
    mpr_tiles_changed = Signal(object)

    def __init__(self, app: Any) -> None:
        """
        Args:
            app: The DICOMViewerApp instance (provides access to all
                 subwindow managers, config, etc.).
        """
        super().__init__()
        self._app = app
        self._workers: dict[int, MprBuilderWorker] = {}  # idx → active worker
        # Fencing for in-flight builds: pane generations invalidate replaced
        # or cancelled builds; source generations invalidate closed sources.
        self._build_generations: dict[int, int] = {}
        self._source_generations: dict[tuple[str, str], int] = {}
        # Retired native workers kept alive until actually terminated.
        self._retiring_builds: list[Any] = []
        # Progress dialogs for in-flight builds (closed on retire/finish).
        self._build_progress: dict[int, Any] = {}
        # Authoritative build sources per pane (study/series of the volume).
        self._build_sources: dict[int, tuple[str, str]] = {}
        # GUI-owned retire poller (created on demand, parented to self).
        self._retire_poller: Any = None
        self._cache: MprCache | None = None
        # Live session/view registry: owns every constructed MprResult, view
        # IDs, pane mapping and admission. Pane ``subwindow_data`` is its live
        # display adapter while attached (see ``gui.mpr_controller_sessions``).
        self._registry = create_registry(app)
        # Opaque per-controller drag-origin token (see ``core.mpr_view_drag``): view
        # IDs collide across controllers/instances, so drops must prove their origin.
        self._drag_origin = new_drag_origin()
        # Canonical slice setter / link state (see ``gui.mpr_view_links``): the
        # re-entrancy guard is deliberately separate from global sync's ``_syncing``.
        self._slice_propagating = False
        self._tile_refresh_dirty: set[int] = set()
        self._tile_refresh_timer: QTimer | None = None
        # Pane -> (reservation id, source key) for an in-flight/just-loaded build.
        self._build_reservations: dict[int, tuple[int, tuple[str, str]]] = {}
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
        """Save the focused pane's MPR stack as a DICOM series (see ``gui.mpr_dicom_save_flow``)."""
        prompt_save_mpr_as_dicom(self)

    def _cancel_mpr_worker(self, idx: int) -> None:
        """Retire any in-progress MPR build for *idx* (see transactions helper)."""
        retire_pane_worker(self, idx)

    def cancel_pending_build(self, idx: int) -> None:
        """Cancel a pending MPR build for *idx*, even with no MPR view present.

        Used by Clear Window and source closure before touching pane state.
        """
        retire_pane_worker(self, idx)


    def _tear_down_mpr_at_subwindow(self, idx: int) -> None:
        """Remove MPR keys from *idx* and restore the pre-MPR state (see helper)."""
        tear_down_mpr_at_subwindow(self, idx)

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

        view = self._registry.view_for_pane(idx)
        self._tear_down_mpr_at_subwindow(idx)
        if view is not None:
            # Clear MPR discards only this view; its session goes with the last view.
            self._registry.discard_view(view.view_id)
        self.mpr_cleared.emit(idx)
        emit_tiles_changed(self)

    # ------------------------------------------------------------------
    # Public per-view API (navigator-facing; exact view IDs, stale IDs no-op)
    # ------------------------------------------------------------------

    @property
    def drag_origin(self) -> str:
        """This controller's opaque drag-origin token (never reset; no patient content)."""
        return self._drag_origin

    def has_detached_mpr(self) -> bool:
        """Return True if any MPR view exists without an assigned subwindow."""
        return bool(detached_view_ids(self))

    def detached_view_ids(self) -> list[int]:
        """Detached view IDs in creation order."""
        return detached_view_ids(self)

    def all_view_ids(self) -> list[int]:
        """Every view ID (attached and detached) in creation order."""
        return all_view_ids(self)

    def clear_view(self, view_id: int) -> bool:
        """Clear one view by exact ID (pane clear or detached discard); stale IDs no-op."""
        return clear_view(self, view_id)

    def move_view(self, view_id: int, to_idx: int) -> None:
        """Move/attach a view by stable ID to pane *to_idx* (see transactions)."""
        move_view(self, view_id, to_idx)

    def duplicate_view(self, view_id: int, to_idx: int, *, linked: bool = False) -> bool:
        """Duplicate a view into pane *to_idx* sharing its result (no new session).

        ``linked=True`` also joins the duplicate to the source's link group
        (creating it) in the same transaction; any failure rolls both back.
        """
        return duplicate_view_into_pane(self, view_id, to_idx, linked=linked)

    def set_view_slice(self, view_id: int, slice_index: int) -> SliceUpdate | None:
        """Canonical slice setter: clamps, moves the view's whole link group once."""
        return set_view_slice(self, view_id, slice_index)

    def set_pane_slice(self, idx: int, slice_index: int) -> SliceUpdate | None:
        """:meth:`set_view_slice` for the view attached to pane *idx* (None if empty)."""
        return set_pane_slice(self, idx, slice_index)

    def link_group_of_pane(self, idx: int) -> int | None:
        """Explicit link-group ID of the view in pane *idx*, or None."""
        return link_group_of_pane(self, idx)

    def unlink_view(self, view_id: int) -> bool:
        """Remove a view from its link group (a pair dissolves); False if not linked."""
        return unlink_view(self, view_id)

    def flush_tile_refresh(self) -> None:
        """Emit any debounced tile refresh now (linked scrolling of detached views)."""
        flush_tile_refresh(self)

    def attached_view_id(self, idx: int) -> int | None:
        """View ID attached to pane *idx*, or None."""
        view = self._registry.view_for_pane(idx)
        return None if view is None else view.view_id

    def get_view_metadata(self, view_id: int) -> MprViewMetadata | None:
        """Read-only metadata for an exact view ID, or None if unknown."""
        return view_metadata(self, view_id)

    def get_pane_view_metadata(self, idx: int) -> MprViewMetadata | None:
        """Read-only metadata for the view attached to pane *idx*, or None."""
        return pane_view_metadata(self, idx)

    def get_view_display_state(self, view_id: int) -> MprDisplayState | None:
        """Copy of a view's own display state (never the focused pane's)."""
        return view_display_state(self, view_id)

    def get_view_thumbnail_pixels(
        self, view_id: int, use_rescaled: bool | None = None
    ) -> np.ndarray | None:
        """Mid-stack slice for a view's navigator tile, or None if unknown."""
        return view_thumbnail_pixels(self, view_id, use_rescaled)

    def discard_detached_view(self, view_id: int) -> bool:
        """Discard one detached view; stale or attached IDs are no-ops (False)."""
        return discard_detached(self, view_id)

    def release_mpr_for_closed_source(
        self, study_uid: str, series_uid: str | None = None
    ) -> dict[str, int]:
        """Release MPR builds, views, and payloads tied to a closed source.

        See ``gui.mpr_controller_transactions.release_closed_source_sessions``.
        """
        return release_closed_source_sessions(self, study_uid, series_uid)

    def release_all_mpr(self) -> dict[str, int]:
        """Release every MPR build, payload, override, and spec (Close All).

        See ``gui.mpr_source_closure.release_all_mpr``.
        """
        return release_all_mpr(self)

    def _capture_mpr_payload(self, idx: int) -> dict[str, Any] | None:
        """Snapshot live MPR fields from *idx* for relocate / detach (see helper)."""
        return capture_mpr_payload(self, idx)

    def relocate_mpr_subwindow(self, from_idx: int, to_idx: int) -> None:
        """Move an active MPR from *from_idx* to *to_idx*, transactionally.

        See ``gui.mpr_controller_transactions.relocate_mpr_view``: the source
        is preserved until the destination install succeeds, and a failed
        install restores the destination without signals.
        """
        relocate_mpr_view(self, from_idx, to_idx)

    def attach_detached_view(self, view_id: int, to_idx: int) -> None:
        """Attach detached view *view_id* to *to_idx*, transactionally.

        See ``gui.mpr_controller_transactions.attach_detached_view``.
        """
        attach_detached_view(self, view_id, to_idx)

    def detach_view_for_pane_reset(self, idx: int) -> None:
        """Detach a view still mapped to *idx* just before its pane data is reset.

        See ``gui.mpr_controller_transactions.detach_view_on_pane_reset``.
        """
        detach_view_on_pane_reset(self, idx)

    def detach_mpr_from_subwindow(self, idx: int) -> None:
        """Detach the view in *idx*; the registry keeps it and its session."""
        detach_mpr_view(self, idx)


    def _install_mpr_payload_at_subwindow(self, idx: int, payload: dict[str, Any]) -> bool:
        """
        Apply a captured MPR payload to *idx* (same end state as _activate_mpr).

        Validates the target and payload before any mutation, including
        before ``mpr_previous_state`` is written. On install failure the
        destination is rolled back (pane teardown plus captured display
        state) and no success signal is emitted.

        Returns:
            True if the MPR view was installed; False on missing data or install error.
        """
        validated = validate_install_request(self._app, self._get_image_viewer, idx, payload)
        if validated is None:
            return False
        result, si, source_ds = validated
        data = self._app.subwindow_data.get(idx)
        if data is None:  # pragma: no cover (validated above)
            return False

        orientation_label = str(payload.get("mpr_orientation", "MPR") or "MPR")
        snapshot = capture_destination_snapshot(
            self._app, self._get_image_viewer, idx
        )
        try:
            self._ensure_mpr_previous_state(data)
            self._install_write_payload_fields(
                data, payload, result, orientation_label, source_ds, si
            )
            self._sync_slice_navigator_for_mpr(idx, result.n_slices, data["mpr_slice_index"])
            self._set_tools_enabled(idx, enabled=False)
            self._install_apply_display_state(idx, payload, source_ds)

            if self.display_mpr_slice(idx, data["mpr_slice_index"]) is False:
                raise RuntimeError("MPR slice could not be rendered")
            self._fit_image_viewer_after_mpr(idx)
            self._apply_mpr_banner(idx, data)
            self._sync_intensity_projection_if_focused(idx, data)
        except Exception as exc:
            _mpr_log(f"_install_mpr_payload_at_subwindow failed: {exc}")
            if not restore_failed_install(self, idx, snapshot, self._get_image_viewer):
                QMessageBox.warning(
                    self._app.main_window, "MPR",
                    "The MPR could not be installed and the previous display could "
                    "not be fully restored. Reload this window's series.",
                )
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
        combine = payload.get("mpr_combine")
        if isinstance(combine, MprCombineState):
            restore_mpr_combine_state(data, combine)
            return
        # Legacy payloads predate the combine snapshot; keep the flat keys.
        data["mpr_combine_enabled"] = bool(payload.get("mpr_combine_enabled", False))
        data["mpr_combine_mode"] = str(payload.get("mpr_combine_mode", "aip") or "aip")
        data["mpr_combine_slice_count"] = int(
            payload.get("mpr_combine_slice_count", 4) or 4
        )

    def _install_apply_display_state(
        self, idx: int, payload: dict[str, Any], source_ds: Any
    ) -> None:
        """Restore carried display state, or reset to source defaults (see helper)."""
        install_apply_display_state(
            self._app,
            self._get_image_viewer,
            idx,
            payload,
            source_ds,
            reset=self._reset_window_level_for_mpr,
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


    def display_mpr_slice(self, idx: int, slice_index: int) -> bool:
        """
        Display a single MPR slice in subwindow *idx*.

        Called when the slice navigator advances within an MPR view.

        Window/level follows the global controls (same policy as normal 2D slices
        when changing Combine Slices mode or slice count: W/L stays fixed).

        Args:
            idx:         Subwindow index.
            slice_index: Zero-based index into the MprResult.slices list.

        Returns:
            True only when the slice image was produced and applied to the
            viewer. False for a non-MPR pane, an unusable result or index, a
            missing viewer, or an image that could not be built. Activation and
            install rely on this to avoid confirming a view that never rendered.
        """
        data = self._app.subwindow_data.get(idx, {})
        if not data.get("is_mpr"):
            return False
        result: MprResult | None = data.get("mpr_result")
        if result is None or slice_index >= result.n_slices:
            return False

        data["mpr_slice_index"] = slice_index

        image_viewer = self._get_image_viewer(idx)
        wl_controls = getattr(self._app, "window_level_controls", None)
        managers = self._app.subwindow_managers.get(idx, {})

        if image_viewer is None:
            return False

        self._display_mpr_sync_measurement_spacing(managers, result)
        array = self._display_mpr_prepare_array(data, result, slice_index, managers)
        wc, ww = self._get_preferred_mpr_window_level(
            managers.get("view_state_manager"),
            wl_controls,
            array,
        )
        pil_image = self._array_to_pil(array, wc, ww, photometric_interpretation=result.photometric_interpretation, **mpr_display_kwargs(managers, result.photometric_interpretation))
        if pil_image is None:
            return False

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
        return True

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

        image_viewer.set_display_final_image(pil_image, preserve_view=True, image_inverted=bool(getattr(image_viewer, "image_inverted", False)))
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

        # Admission is reserved before any volume construction or cache load.
        if not reserve_pane_build(
            self, target_idx, dataset_source_key(datasets_to_use)
        ):
            return
        try:
            self._mpr_request_admitted(
                target_idx, request, datasets_to_use, use_slice_location_fallback
            )
        except Exception:
            # Retire any worker and release the reservation exactly once.
            self._cancel_mpr_worker(target_idx)
            raise

    def _mpr_request_admitted(
        self,
        target_idx: int,
        request,
        datasets_to_use: list[Any],
        use_slice_location_fallback: bool,
    ) -> None:
        """Build/cache-load/start the worker for an admitted (reserved) request."""
        volume = self._mpr_request_build_volume(
            datasets_to_use, use_slice_location_fallback
        )
        if volume is None:
            release_pane_reservation(self, target_idx)
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
        """Cancel any in-flight MPR build for *target_idx* (retires the worker)."""
        self._cancel_mpr_worker(target_idx)

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
            n_ds = len(datasets_to_use)
            try:
                series_uid = str(datasets_to_use[0].SeriesInstanceUID)
            except (AttributeError, IndexError):
                series_uid = "__unknown__"
            from core.mpr_cache import _make_cache_key
            key = _make_cache_key(
                series_uid=series_uid,
                normal=request.output_plane.normal,
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
                    photometric_interpretation=resolve_cached_photometric_interpretation(meta, volume.source_datasets),
                    combine_mode=meta.get("combine_mode", "none"),
                    slab_thickness_mm=float(meta.get("slab_thickness_mm", 0.0)),
                )
            else:
                _mpr_log(f"Cache miss: key={key[:12]}...")
                return False
        except Exception as exc:
            print_redacted(f"[MprController] Cache lookup error: {exc}")
            return False
        # A hit activates through the same admission as a worker build.
        self._activate_mpr(
            target_idx, cached_result, request.orientation_label, request=request
        )
        return True

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
        # Dialog Cancel retires through the controller so generations bump
        # and a queued completion can no longer activate after Cancel.
        progress_dlg.canceled.connect(lambda: self._cancel_mpr_worker(target_idx))
        self._build_progress[target_idx] = progress_dlg

        orientation_label = request.orientation_label
        source_key = volume_source_key(volume)
        pane_generation, source_generation = note_build_started(
            self, target_idx, source_key
        )

        def on_finished(result: MprResult) -> None:
            self._on_mpr_build_finished(
                target_idx, worker, pane_generation, source_key,
                source_generation, result, request, orientation_label,
                progress_dlg,
            )

        def on_error(msg: str) -> None:
            self._on_mpr_build_error(
                target_idx, worker, pane_generation, source_key,
                source_generation, msg, progress_dlg,
            )

        worker.finished.connect(on_finished)
        worker.error.connect(on_error)

        self._workers[target_idx] = worker
        worker.start()

    def _on_mpr_build_finished(
        self,
        target_idx: int,
        worker: Any,
        pane_generation: int,
        source_key: tuple[str, str],
        source_generation: int,
        result: MprResult,
        request: Any,
        orientation_label: str,
        progress_dlg: Any,
    ) -> None:
        """Activate a completed build only when it still owns its pane.

        Late callbacks from replaced, cancelled, or closed builds are
        dropped before popping any worker or touching pane state.
        """
        progress_dlg.close()
        if not is_current_pane_build(
            self, target_idx, worker, pane_generation, source_key, source_generation
        ):
            _mpr_log(f"Ignoring stale build finish for window {target_idx}")
            return
        drop_build_registration(self, target_idx)
        retain_build_worker(self, worker)
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
            release_pane_reservation(self, target_idx)
            QMessageBox.critical(
                self._app.main_window,
                _TITLE_MPR_ERROR,
                "Cannot activate MPR: image viewer not ready. Please try again.",
            )
            return

        self._activate_mpr(
            target_idx, result, orientation_label, request=request
        )

    def _on_mpr_build_error(
        self,
        target_idx: int,
        worker: Any,
        pane_generation: int,
        source_key: tuple[str, str],
        source_generation: int,
        msg: str,
        progress_dlg: Any,
    ) -> None:
        """Report a build error only when it still owns its pane."""
        progress_dlg.close()
        if not is_current_pane_build(
            self, target_idx, worker, pane_generation, source_key, source_generation
        ):
            _mpr_log(f"Ignoring stale build error for window {target_idx}")
            return
        drop_build_registration(self, target_idx)
        release_pane_reservation(self, target_idx)
        retain_build_worker(self, worker)
        if "cancelled" in msg.lower() or "canceled" in msg.lower():
            return
        QMessageBox.critical(
            self._app.main_window,
            _TITLE_MPR_ERROR,
            f"MPR build failed:\n{msg}",
        )

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
        Load a completed ``MprResult`` into subwindow *idx* as a new session.

        Consumes the pane's admission reservation only on success (reserving
        first when called without one). On failure the pane and registry are
        restored and the reservation released. See ``gui.mpr_activation``.

        Args:
            idx:               Target subwindow index.
            result:            Completed MPR build result.
            orientation_label: Human-readable orientation string.
            request:           Optional ``MprRequest`` from the dialog (seeds
                               ``mpr_combine_*`` from dialog slab settings).
        """
        activate_built_mpr(self, idx, result, orientation_label, request)

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
        """Synthetic overlay dataset for one MPR slice (see ``core.mpr_overlay_dataset``)."""
        return build_overlay_dataset(result, slice_index)

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
        """Reset window/level controls to defaults from the MPR source dataset.

        See ``gui.mpr_controller_display_state`` for the full contract: pane
        rescale/toggle always syncs for *idx*; shared toolbar and main-window
        toggle sync only when *idx* is focused.
        """
        reset_window_level_for_mpr(
            self._app, self._get_image_viewer, idx, source_dataset
        )

    @staticmethod
    def _get_preferred_mpr_window_level(view_state_manager, wl_controls, array: np.ndarray):
        """Return the window/level to use for MPR display (see helper)."""
        return preferred_mpr_window_level(view_state_manager, wl_controls, array)

    @staticmethod
    def _array_to_pil(
        array: np.ndarray, window_center: float, window_width: float,
        *, photometric_interpretation: str | None = None,
        image_inverted: bool = False, lut=None,
    ) -> Image.Image | None:
        """Wrapper over ``array_to_pil``. Patched by tests; polarity then LUT stay in core."""
        return array_to_pil(array, window_center, window_width, photometric_interpretation=photometric_interpretation, image_inverted=image_inverted, lut=lut)

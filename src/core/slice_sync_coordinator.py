"""
Slice Sync Coordinator

Manages anatomic slice synchronisation across linked groups of subwindows.
When the user scrolls a slice in a subwindow that belongs to a linked group,
the coordinator updates every other subwindow in that group to the anatomically
nearest slice using 3-D patient-space geometry.

Inputs:
    - Slice-changed notifications from the application (call on_slice_changed).
    - Linked-group configuration (set_groups / from ConfigManager).
    - App references for subwindow data and slice display managers.

Outputs:
    - Programmatic slice index changes on non-source subwindows.

Requirements:
    - core.slice_geometry  (SlicePlane, SliceStack, find_nearest_slice)
    - PySide6 (no Qt imports at module level; app handles Qt objects)
    - numpy (via slice_geometry)

Design notes
------------
* Sync is **off by default**; call ``set_enabled(True)`` to activate.
* A subwindow can belong to at most one linked group.
* Sync works for any angle between stacks (even 90°, which simply produces
  no update in the target window since all source planes project to the
  same target slice).
* Tolerance = target stack's ``slice_thickness * 0.5`` mm. If the source
  plane falls further than that outside the target stack, the target is
  not updated (prevents spurious jumps when stacks don't overlap).
* A ``_syncing`` reentrancy guard prevents feedback loops when slices are
  set programmatically.
* SliceStack geometry is cached per ``(study_uid, series_uid)`` and
  invalidated when a series is closed or reassigned.
"""

from typing import Any, Dict, List, Optional, Tuple

from core.slice_geometry import SlicePlane, SliceStack, find_nearest_slice


class SliceSyncCoordinator:
    """
    Coordinates anatomic slice sync across user-defined linked groups.

    Attributes:
        enabled (bool): Whether sync is globally active.
        groups  (List[List[int]]): Current linked groups (each is a list of
                subwindow indices).
    """

    def __init__(self, app: Any) -> None:
        """
        Initialise the coordinator.

        Args:
            app: DICOMViewerApp instance.  The coordinator reads:
                 - app.subwindow_data     (dict idx → data dict)
                 - app.subwindow_managers (dict idx → managers dict)
                 - app.current_studies    (dict of all loaded studies)
                 It writes current_slice_index and calls display_slice on
                 non-focused subwindows.
        """
        self.app = app
        self.enabled: bool = False
        self.groups: List[List[int]] = []

        # Reentrancy guard: prevents a programmatic slice update in target B
        # from triggering another sync from B's perspective.
        self._syncing: bool = False

        # Geometry cache: (study_uid, series_uid) → Optional[SliceStack].
        # None means "already attempted but geometry unavailable".
        self._stack_cache: Dict[Tuple[str, str], Optional[SliceStack]] = {}

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable global slice sync."""
        self.enabled = enabled

    def set_groups(self, groups: List[List[int]]) -> None:
        """
        Update the linked-group assignments.

        Groups with fewer than 2 members are silently discarded.

        Args:
            groups: List of groups, each a list of subwindow indices.
        """
        self.groups = [g for g in groups if isinstance(g, list) and len(g) >= 2]

    def get_current_plane(self, idx: int) -> Optional[SlicePlane]:
        """
        Return the SlicePlane for the current slice in subwindow ``idx``.

        Used by the slice location line feature to compute plane-plane
        intersections. Returns None if geometry is unavailable.

        Args:
            idx: Subwindow index (0–3).

        Returns:
            SlicePlane for the current slice, or None.
        """
        stack = self._get_stack(idx)
        if stack is None:
            return None
        slice_idx = self._get_slice_index(idx)
        sorted_pos = self._dataset_idx_to_sorted_pos(idx, slice_idx, stack)
        if sorted_pos is None:
            return None
        return stack.planes[sorted_pos]

    def get_slice_thickness(self, idx: int) -> Optional[float]:
        """
        Return the nominal slice thickness in mm for subwindow ``idx``.

        Used by the slice location line feature when "begin_end" mode is
        active to compute ±(thickness/2) boundary offsets for each source
        plane.  Returns None if geometry is unavailable.

        Args:
            idx: Subwindow index (0–3).

        Returns:
            Slice thickness in mm (> 0), or None.
        """
        stack = self._get_stack(idx)
        if stack is None:
            return None
        return stack.slice_thickness

    def invalidate_cache(self, study_uid: str = "", series_uid: str = "") -> None:
        """
        Remove one or all entries from the geometry cache.

        Call when a series is closed or reassigned so stale geometry is
        not used for sync.

        Args:
            study_uid: Study UID to invalidate.  If empty, clear all.
            series_uid: Series UID to invalidate.  If empty, invalidate
                        all series for the given study.
        """
        if not study_uid:
            self._stack_cache.clear()
            return
        keys_to_remove = [
            (s, r) for (s, r) in self._stack_cache
            if s == study_uid and (not series_uid or r == series_uid)
        ]
        for key in keys_to_remove:
            del self._stack_cache[key]

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def on_slice_changed(self, source_idx: int) -> None:
        """
        React to a user-driven slice change in ``source_idx``.

        Finds all other subwindows in the same linked group and updates
        each to the anatomically nearest slice.

        Args:
            source_idx: Index (0–3) of the subwindow whose slice changed.
        """
        if not self.enabled or self._syncing:
            return

        group = self._find_group(source_idx)
        if group is None:
            return  # this subwindow is not in any group

        targets = [idx for idx in group if idx != source_idx]
        if not targets:
            return

        # Build source geometry.
        source_stack = self._get_stack(source_idx)
        if source_stack is None:
            return  # no geometry available for source

        source_slice_idx = self._get_slice_index(source_idx)
        if source_slice_idx < 0 or source_slice_idx >= len(source_stack.planes):
            # Map navigator index to sorted geometry index.
            # original_indices maps sorted_pos → dataset_idx; we need dataset_idx → sorted_pos.
            sorted_pos = self._dataset_idx_to_sorted_pos(source_idx, source_slice_idx, source_stack)
            if sorted_pos is None:
                return
            source_plane = source_stack.planes[sorted_pos]
        else:
            sorted_pos = self._dataset_idx_to_sorted_pos(source_idx, source_slice_idx, source_stack)
            if sorted_pos is None:
                return
            source_plane = source_stack.planes[sorted_pos]

        # Update each target.
        self._syncing = True
        try:
            for target_idx in targets:
                self._update_target(target_idx, source_plane)
        finally:
            self._syncing = False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_group(self, idx: int) -> Optional[List[int]]:
        """Return the group containing ``idx``, or None."""
        for group in self.groups:
            if idx in group:
                return group
        return None

    def _get_slice_index(self, idx: int) -> int:
        """Return current dataset-list slice index for subwindow ``idx``."""
        data = self.app.subwindow_data.get(idx, {})
        return data.get("current_slice_index", 0)

    def _get_datasets(self, idx: int) -> Optional[List[Any]]:
        """Return current datasets list for subwindow ``idx``."""
        data = self.app.subwindow_data.get(idx, {})
        return data.get("current_datasets") or None

    def _get_stack(self, idx: int) -> Optional[SliceStack]:
        """Return (cached) SliceStack for subwindow ``idx``."""
        data = self.app.subwindow_data.get(idx, {})
        if data.get("is_mpr") and data.get("mpr_result") is not None:
            cache_key = ("__mpr__", str(idx))
            stack = data["mpr_result"].slice_stack
            self._stack_cache[cache_key] = stack
            return stack

        study_uid = data.get("current_study_uid", "")
        series_uid = data.get("current_series_uid", "")
        if not study_uid and not series_uid:
            return None

        cache_key = (study_uid, series_uid)
        if cache_key in self._stack_cache:
            return self._stack_cache[cache_key]

        datasets = data.get("current_datasets")
        if not datasets:
            self._stack_cache[cache_key] = None
            return None

        stack = SliceStack.from_datasets(datasets)
        self._stack_cache[cache_key] = stack
        return stack

    def _dataset_idx_to_sorted_pos(
        self, idx: int, dataset_idx: int, stack: SliceStack
    ) -> Optional[int]:
        """
        Map a dataset-list index (used as current_slice_index) to the sorted
        position inside ``stack.planes``.

        ``stack.original_indices[sorted_pos] == dataset_idx``.
        """
        try:
            return stack.original_indices.index(dataset_idx)
        except ValueError:
            # dataset_idx not in original_indices (e.g. slice skipped due to
            # missing geometry).  Clamp to nearest valid entry.
            if not stack.original_indices:
                return None
            # Find the closest valid original index.
            best = min(
                range(len(stack.original_indices)),
                key=lambda i: abs(stack.original_indices[i] - dataset_idx),
            )
            return best

    def _update_target(self, target_idx: int, source_plane: SlicePlane) -> None:
        """
        Update subwindow ``target_idx`` to the nearest slice to ``source_plane``.

        Silently returns without changes if:
        - the target has no series loaded,
        - geometry is missing or unavailable,
        - the source plane is outside the target stack's tolerance,
        - the computed index equals the target's current index (no change needed).
        """
        target_stack = self._get_stack(target_idx)
        if target_stack is None:
            return

        tolerance_mm = target_stack.slice_thickness * 0.5

        new_dataset_idx = find_nearest_slice(source_plane, target_stack, tolerance_mm)
        if new_dataset_idx is None:
            return  # outside tolerance or empty stack

        current_idx = self._get_slice_index(target_idx)
        if new_dataset_idx == current_idx:
            return  # already on the correct slice

        target_data = self.app.subwindow_data.get(target_idx, {})
        if target_data.get("is_mpr") and hasattr(self.app, "_mpr_controller"):
            try:
                self.app._mpr_controller.display_mpr_slice(target_idx, new_dataset_idx)
            except Exception as exc:  # pragma: no cover
                print(f"[SliceSyncCoordinator] Error updating MPR subwindow {target_idx}: {exc}")
            return

        datasets = self._get_datasets(target_idx)
        if datasets is None or new_dataset_idx >= len(datasets):
            return

        # Update the subwindow state and redisplay.
        data = self.app.subwindow_data.get(target_idx, {})
        data["current_slice_index"] = new_dataset_idx
        data["current_dataset"] = datasets[new_dataset_idx]

        sdm = self.app.subwindow_managers.get(target_idx, {}).get("slice_display_manager")
        if sdm is None:
            return

        try:
            sdm.display_slice(
                datasets[new_dataset_idx],
                self.app.current_studies,
                data.get("current_study_uid", ""),
                data.get("current_series_uid", ""),
                new_dataset_idx,
                preserve_view_override=True,
                update_controls=False,   # don't disrupt the focused window's W/L UI
                update_metadata=False,   # don't overwrite the metadata panel
            )
        except Exception as exc:  # pragma: no cover
            print(f"[SliceSyncCoordinator] Error updating subwindow {target_idx}: {exc}")

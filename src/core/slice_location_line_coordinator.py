"""
Slice Location Line Coordinator

App-level coordinator for the slice location line feature. Holds per-subwindow
SliceLocationLineManager instances, refreshes them when slice/layout/toggle
changes, and reads visibility from config.

Inputs:
    - App reference
    - Config manager (slice_location_lines_visible, slice_location_lines_same_group_only)
    - Slice change, layout change, toggle change events

Outputs:
    - Line items updated in each subwindow's scene

Requirements:
    - core.slice_location_line_helper
    - gui.slice_location_line_manager
"""

from typing import Any, Dict, Optional

from core.slice_location_line_helper import get_slice_location_line_segments
from gui.slice_location_line_manager import SliceLocationLineManager


class SliceLocationLineCoordinator:
    """
    Coordinates slice location line display across all subwindows.

    Refreshes line items when:
    - Any subwindow's slice index changes
    - Master toggle or per-view toggle changes
    - Layout or subwindow content changes (series loaded/closed)
    """

    def __init__(self, app: Any) -> None:
        """
        Initialize the coordinator.

        Args:
            app: DICOMViewerApp instance with subwindow_data, subwindow_managers,
                 config_manager, _slice_sync_coordinator.
        """
        self.app = app
        self._managers: Dict[int, SliceLocationLineManager] = {}
        self._refreshing = False

    def ensure_manager(self, idx: int, scene: Optional[Any] = None) -> SliceLocationLineManager:
        """
        Ensure a SliceLocationLineManager exists for subwindow idx.

        Creates one if missing. Sets scene if provided.

        Args:
            idx: Subwindow index.
            scene: Optional QGraphicsScene for the subwindow.

        Returns:
            The manager for this subwindow.
        """
        if idx not in self._managers:
            self._managers[idx] = SliceLocationLineManager(scene)
        if scene is not None:
            self._managers[idx].set_scene(scene)
        return self._managers[idx]

    def remove_manager(self, idx: int) -> None:
        """Remove and clear the manager for subwindow idx."""
        if idx in self._managers:
            self._managers[idx].clear()
            del self._managers[idx]

    def refresh_all(self) -> None:
        """
        Refresh slice location lines for all subwindows that have an image
        and visibility enabled.
        """
        if self._refreshing:
            return
        visible = self._is_visible()
        if not visible:
            self._clear_all_visible()
            return

        self._refreshing = True
        try:
            only_same_group = self._get_same_group_only()
            subwindows = self._get_all_subwindows()
            for idx, subwindow in enumerate(subwindows):
                if subwindow is None:
                    continue
                scene = None
                if hasattr(subwindow, "image_viewer") and subwindow.image_viewer:
                    scene = getattr(subwindow.image_viewer, "scene", None)
                self.ensure_manager(idx, scene)
                self._refresh_for_subwindow(idx, only_same_group)
        finally:
            self._refreshing = False

    def refresh_for_subwindow(self, target_idx: int) -> None:
        """Refresh slice location lines for a single target subwindow."""
        if self._refreshing:
            return
        if not self._is_visible():
            self._clear_all_visible()
            return

        self._refreshing = True
        try:
            only_same_group = self._get_same_group_only()
            self._refresh_for_subwindow(target_idx, only_same_group)
        finally:
            self._refreshing = False

    def _refresh_for_subwindow(self, target_idx: int, only_same_group: bool) -> None:
        """Internal: refresh one target subwindow."""
        manager = self._managers.get(target_idx)
        if manager is None:
            return

        # Ensure manager has a scene (from subwindow's image_viewer).
        if not manager.has_scene():
            sub = self._get_subwindow_container(target_idx)
            if sub and hasattr(sub, "image_viewer") and sub.image_viewer:
                scene = getattr(sub.image_viewer, "scene", None)
                if scene:
                    manager.set_scene(scene)

        if not manager.has_scene():
            return

        mode = self._get_line_mode()
        segments = get_slice_location_line_segments(
            target_idx,
            self.app,
            only_same_group=only_same_group,
            mode=mode,
        )

        # Filter to focused subwindow only when that option is enabled.
        if self._get_focused_only():
            focused_idx = getattr(self.app, "focused_subwindow_index", -1)
            if focused_idx >= 0:
                segments = [s for s in segments if s.get("source_idx") == focused_idx]
            else:
                segments = []

        lw = self._get_line_width_px()
        manager.set_line_width_px(lw)
        manager.set_visible(True)
        manager.update_lines(segments, lw)

    def _clear_all_visible(self) -> None:
        """Clear all line items (visibility off)."""
        for manager in self._managers.values():
            manager.update_lines([])
            manager.set_visible(False)

    def _is_visible(self) -> bool:
        """Return whether slice location lines are globally visible."""
        cm = getattr(self.app, "config_manager", None)
        if cm is None:
            return False
        return cm.get_slice_location_lines_visible()

    def _get_same_group_only(self) -> bool:
        """Return whether to scope to same linked group only."""
        cm = getattr(self.app, "config_manager", None)
        if cm is None:
            return False
        return cm.get_slice_location_lines_same_group_only()

    def _get_focused_only(self) -> bool:
        """Return whether to show only the focused subwindow's line."""
        cm = getattr(self.app, "config_manager", None)
        if cm is None:
            return False
        return cm.get_slice_location_lines_focused_only()

    def _get_line_mode(self) -> str:
        """Return slice position line rendering mode ('middle' or 'begin_end')."""
        cm = getattr(self.app, "config_manager", None)
        if cm is None:
            return "middle"
        return cm.get_slice_location_line_mode()

    def _get_line_width_px(self) -> int:
        """Return configured stroke width for slice position lines (pixels)."""
        cm = getattr(self.app, "config_manager", None)
        if cm is None:
            return 1
        return cm.get_slice_location_line_width_px()

    def _get_subwindow_container(self, idx: int) -> Optional[Any]:
        """Return the SubWindowContainer for subwindow idx."""
        layout = getattr(self.app, "multi_window_layout", None)
        if layout is None:
            return None
        subwindows = layout.get_all_subwindows()
        if 0 <= idx < len(subwindows):
            return subwindows[idx]
        return None

    def _get_all_subwindows(self) -> list[Any]:
        """Return list of all subwindow containers."""
        layout = getattr(self.app, "multi_window_layout", None)
        if layout is None:
            return []
        return layout.get_all_subwindows()

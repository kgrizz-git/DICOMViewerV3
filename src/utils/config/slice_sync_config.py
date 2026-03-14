"""
Slice Sync Config Mixin

Persists settings for the anatomic slice-sync feature:
  - whether sync is globally enabled (default: off)
  - user-defined linked groups (list of lists of subwindow indices)
  - slice location lines visibility (default: off)
  - slice location lines same-group-only (default: True when sync enabled)

Mixin contract:
    Expects ``self.config`` (dict) and ``self.save_config()`` from ConfigManager.

Config keys
-----------
slice_sync_enabled  : bool  – master on/off toggle (default False)
slice_sync_groups   : list of list[int]  – each inner list is one linked group
                      of subwindow indices, e.g. [[0, 1], [2, 3]].
                      Default: [] (no groups defined).
slice_location_lines_visible : bool  – show slice location lines across views (default False)
slice_location_lines_same_group_only : bool  – only show lines from same linked group (default True)
"""

from typing import List


class SliceSyncConfigMixin:
    """Config mixin: slice sync enabled flag and linked group assignments."""

    # ------------------------------------------------------------------
    # Master toggle
    # ------------------------------------------------------------------

    def get_slice_sync_enabled(self) -> bool:
        """
        Return whether global anatomic slice sync is enabled.

        Default is ``False`` (sync off).
        """
        return bool(self.config.get("slice_sync_enabled", False))

    def set_slice_sync_enabled(self, enabled: bool) -> None:
        """
        Set the global slice sync enabled flag and persist.

        Args:
            enabled: True to enable sync, False to disable.
        """
        self.config["slice_sync_enabled"] = bool(enabled)
        self.save_config()

    # ------------------------------------------------------------------
    # Linked groups
    # ------------------------------------------------------------------

    def get_slice_sync_groups(self) -> List[List[int]]:
        """
        Return the current linked-group assignments.

        Each inner list is a set of subwindow indices that form one group.
        A subwindow may belong to at most one group.

        Returns:
            List of groups, e.g. [[0, 2], [1, 3]].  May be empty.
        """
        raw = self.config.get("slice_sync_groups", [])
        if not isinstance(raw, list):
            return []
        validated: List[List[int]] = []
        for group in raw:
            if isinstance(group, list) and len(group) >= 2:
                try:
                    validated.append([int(i) for i in group])
                except (TypeError, ValueError):
                    pass
        return validated

    def set_slice_sync_groups(self, groups: List[List[int]]) -> None:
        """
        Persist linked-group assignments.

        Args:
            groups: List of groups, each a list of subwindow indices.
                    Groups with fewer than 2 members are discarded.
        """
        cleaned = [
            [int(i) for i in group]
            for group in groups
            if isinstance(group, list) and len(group) >= 2
        ]
        self.config["slice_sync_groups"] = cleaned
        self.save_config()

    # ------------------------------------------------------------------
    # Slice location lines
    # ------------------------------------------------------------------

    def get_slice_location_lines_visible(self) -> bool:
        """
        Return whether slice location lines are visible across views.

        Default is ``False`` (off).
        """
        return bool(self.config.get("slice_location_lines_visible", False))

    def set_slice_location_lines_visible(self, visible: bool) -> None:
        """
        Set slice location lines visibility and persist.

        Args:
            visible: True to show lines, False to hide.
        """
        self.config["slice_location_lines_visible"] = bool(visible)
        self.save_config()

    def get_slice_location_lines_same_group_only(self) -> bool:
        """
        Return whether slice location lines are scoped to the same linked group.

        When True, only subwindows in the same sync group show their slice
        line on the target. Default is ``True``.
        """
        return bool(self.config.get("slice_location_lines_same_group_only", True))

    def set_slice_location_lines_same_group_only(self, same_group_only: bool) -> None:
        """
        Set slice location lines same-group-only and persist.

        Args:
            same_group_only: True to scope to linked group only.
        """
        self.config["slice_location_lines_same_group_only"] = bool(same_group_only)
        self.save_config()

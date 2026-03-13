"""
Slice Sync Config Mixin

Persists settings for the anatomic slice-sync feature:
  - whether sync is globally enabled (default: off)
  - user-defined linked groups (list of lists of subwindow indices)

Mixin contract:
    Expects ``self.config`` (dict) and ``self.save_config()`` from ConfigManager.

Config keys
-----------
slice_sync_enabled  : bool  – master on/off toggle (default False)
slice_sync_groups   : list of list[int]  – each inner list is one linked group
                      of subwindow indices, e.g. [[0, 1], [2, 3]].
                      Default: [] (no groups defined).
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

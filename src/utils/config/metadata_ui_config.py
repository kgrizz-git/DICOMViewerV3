"""
Metadata UI Config Mixin

Manages metadata panel UI state: column widths and column order.

Mixin contract:
    Expects `self.config` (dict) and `self.save_config()` to be provided by
    the concrete ConfigManager class that inherits this mixin.
"""

from collections.abc import Callable
from typing import Any, cast


class MetadataUIConfigMixin:
    """Config mixin: metadata panel column widths and column order."""

    def _config(self) -> dict[str, Any]:
        return cast(dict[str, Any], getattr(self, "config"))

    def _save_config(self) -> None:
        save_func = cast(Callable[[], None], getattr(self, "save_config"))
        save_func()

    def get_metadata_panel_column_widths(self) -> list[int]:
        """
        Get saved column widths for the metadata panel.

        Returns:
            List of column widths [Tag, Name, VR, Value]
        """
        return self._config().get("metadata_panel_column_widths", [100, 200, 50, 200])

    def set_metadata_panel_column_widths(self, widths: list[int]) -> None:
        """
        Save column widths for the metadata panel.

        Args:
            widths: List of column widths [Tag, Name, VR, Value]
        """
        self._config()["metadata_panel_column_widths"] = widths
        self._save_config()

    def get_metadata_panel_column_order(self) -> list[int]:
        """
        Get saved column order for the metadata panel.

        Returns:
            List of logical indices in visual order; default [0, 1, 2, 3]
        """
        return self._config().get("metadata_panel_column_order", [0, 1, 2, 3])

    def set_metadata_panel_column_order(self, order: list[int]) -> None:
        """
        Save column order for the metadata panel.

        Args:
            order: List of logical indices in visual order
                   (e.g. [1, 0, 2, 3] means Name column is first visually)
        """
        self._config()["metadata_panel_column_order"] = order
        self._save_config()

    def get_metadata_panel_group_expanded(self) -> dict[str, bool]:
        """
        Get saved per-group expand/collapse state for the metadata panel.

        Only *tag group* headings are persisted. Sequence rows deliberately are not:
        they always reopen collapsed, so a study with large sequences can't restore into
        a wall of nested rows.

        Returns:
            {group bucket key (e.g. "(0010"): expanded}; empty when nothing is saved.
        """
        saved = self._config().get("metadata_panel_group_expanded", {})
        if not isinstance(saved, dict):
            return {}
        return {str(k): bool(v) for k, v in saved.items()}

    def set_metadata_panel_group_expanded(self, expanded: dict[str, bool]) -> None:
        """
        Save per-group expand/collapse state for the metadata panel.

        Args:
            expanded: {group bucket key: expanded}
        """
        self._config()["metadata_panel_group_expanded"] = dict(expanded)
        self._save_config()

"""
Metadata UI Config Mixin

Manages metadata panel UI state: column widths and column order.

Mixin contract:
    Expects `self.config` (dict) and `self.save_config()` to be provided by
    the concrete ConfigManager class that inherits this mixin.
"""

from typing import List


class MetadataUIConfigMixin:
    """Config mixin: metadata panel column widths and column order."""

    def get_metadata_panel_column_widths(self) -> List[int]:
        """
        Get saved column widths for the metadata panel.

        Returns:
            List of column widths [Tag, Name, VR, Value]
        """
        return self.config.get("metadata_panel_column_widths", [100, 200, 50, 200])

    def set_metadata_panel_column_widths(self, widths: List[int]) -> None:
        """
        Save column widths for the metadata panel.

        Args:
            widths: List of column widths [Tag, Name, VR, Value]
        """
        self.config["metadata_panel_column_widths"] = widths
        self.save_config()

    def get_metadata_panel_column_order(self) -> List[int]:
        """
        Get saved column order for the metadata panel.

        Returns:
            List of logical indices in visual order; default [0, 1, 2, 3]
        """
        return self.config.get("metadata_panel_column_order", [0, 1, 2, 3])

    def set_metadata_panel_column_order(self, order: List[int]) -> None:
        """
        Save column order for the metadata panel.

        Args:
            order: List of logical indices in visual order
                   (e.g. [1, 0, 2, 3] means Name column is first visually)
        """
        self.config["metadata_panel_column_order"] = order
        self.save_config()

"""
Layout Config Mixin

Manages multi-window layout settings: layout mode and view-slot order.

Mixin contract:
    Expects `self.config` (dict) and `self.save_config()` to be provided by
    the concrete ConfigManager class that inherits this mixin.
"""

from typing import List


class LayoutConfigMixin:
    """Config mixin: multi-window layout mode and 2x2 view-slot order."""

    def get_multi_window_layout(self) -> str:
        """
        Get the multi-window layout mode.

        Returns:
            Layout mode ("1x1", "1x2", "2x1", or "2x2")
        """
        return self.config.get("multi_window_layout", "1x1")

    def set_multi_window_layout(self, layout_mode: str) -> None:
        """
        Set the multi-window layout mode.

        Args:
            layout_mode: Layout mode ("1x1", "1x2", "2x1", or "2x2")
        """
        if layout_mode in ["1x1", "1x2", "2x1", "2x2"]:
            self.config["multi_window_layout"] = layout_mode
            self.save_config()

    def get_view_slot_order(self) -> List[int]:
        """
        Get the 2x2 view slot order (slot index → view index).

        Used to restore which view occupies which grid cell after restart.

        Returns:
            List of 4 ints, a permutation of [0, 1, 2, 3]; default [0, 1, 2, 3]
        """
        return list(self.config.get("view_slot_order", [0, 1, 2, 3]))

    def set_view_slot_order(self, order: List[int]) -> None:
        """
        Save the 2x2 view slot order (slot index → view index).

        Args:
            order: List of 4 ints, a permutation of [0, 1, 2, 3]
        """
        if (
            isinstance(order, list)
            and len(order) == 4
            and set(order) == {0, 1, 2, 3}
        ):
            self.config["view_slot_order"] = list(order)
            self.save_config()

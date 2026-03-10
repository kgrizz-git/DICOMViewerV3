"""
Layout Config Mixin

Manages multi-window layout settings: layout mode, view-slot order,
and layout map popup position.

Mixin contract:
    Expects `self.config` (dict) and `self.save_config()` to be provided by
    the concrete ConfigManager class that inherits this mixin.
"""

from typing import List, Optional, Tuple


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

    def get_layout_map_popup_position(self) -> Optional[Tuple[int, int]]:
        """
        Get the last saved position (x, y) of the layout map thumbnail popup,
        in global/screen coordinates. Used when opening the popup from the context menu.

        Returns:
            (x, y) tuple or None if not set (e.g. first use)
        """
        raw = self.config.get("layout_map_popup_position")
        if isinstance(raw, (list, tuple)) and len(raw) >= 2:
            try:
                return (int(raw[0]), int(raw[1]))
            except (TypeError, ValueError):
                pass
        return None

    def set_layout_map_popup_position(self, x: int, y: int) -> None:
        """
        Save the position of the layout map thumbnail popup (e.g. after user drag).

        Args:
            x: Global x coordinate
            y: Global y coordinate
        """
        self.config["layout_map_popup_position"] = [x, y]
        self.save_config()

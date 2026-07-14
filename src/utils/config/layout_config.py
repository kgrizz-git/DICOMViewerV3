"""
Layout Config Mixin

Manages multi-window layout settings: layout mode, view-slot order,
last-used 2-pane / 3-pane modes, and layout map popup position.

Mixin contract:
    Expects ``self.config`` (dict) and ``self.save_config()`` to be provided by
    the concrete ConfigManager class that inherits this mixin.
"""

from collections.abc import Callable
from typing import Any, Literal, cast

# Standard 2-pane and 4-pane modes plus four asymmetric 3-pane modes (T0 locked 2026-06-04).
LayoutMode = Literal[
    "1x1",
    "1x2",
    "2x1",
    "2x2",
    "1+2R",
    "2L+1",
    "2T+1",
    "1+2B",
]

TWO_PANE_LAYOUT_MODES: tuple[str, ...] = ("1x2", "2x1")
THREE_PANE_LAYOUT_MODES: tuple[LayoutMode, ...] = ("1+2R", "2L+1", "2T+1", "1+2B")
THREE_PANE_CYCLE_ORDER: tuple[LayoutMode, ...] = THREE_PANE_LAYOUT_MODES

ALL_LAYOUT_MODES: tuple[str, ...] = (
    "1x1",
    "1x2",
    "2x1",
    "2x2",
    *THREE_PANE_LAYOUT_MODES,
)


class LayoutConfigMixin:
    """Config mixin: multi-window layout mode and 2x2 view-slot order."""

    def _config(self) -> dict[str, Any]:
        return cast(dict[str, Any], getattr(self, "config"))

    def _save_config(self) -> None:
        save_func = cast(Callable[[], None], getattr(self, "save_config"))
        save_func()

    def get_multi_window_layout(self) -> LayoutMode:
        """
        Get the multi-window layout mode.

        Returns:
            Layout mode; unknown persisted values fall back to ``1x1``.
        """
        raw = self._config().get("multi_window_layout", "1x1")
        if raw in ALL_LAYOUT_MODES:
            return cast(LayoutMode, raw)
        return "1x1"

    def set_multi_window_layout(self, layout_mode: str) -> None:
        """
        Set the multi-window layout mode.

        Args:
            layout_mode: Any value in ``ALL_LAYOUT_MODES``.
        """
        if layout_mode in ALL_LAYOUT_MODES:
            self._config()["multi_window_layout"] = layout_mode
            self._save_config()

    def get_last_two_pane_layout(self) -> Literal["1x2", "2x1"]:
        """Last-used 1×2 or 2×1 mode (for key **2** exit from 3-pane)."""
        raw = self._config().get("last_two_pane_layout", "1x2")
        if raw in TWO_PANE_LAYOUT_MODES:
            return cast(Literal["1x2", "2x1"], raw)
        return "1x2"

    def set_last_two_pane_layout(self, layout_mode: str) -> None:
        """Persist last-used 2-pane layout when user selects 1×2 or 2×1."""
        if layout_mode in TWO_PANE_LAYOUT_MODES:
            self._config()["last_two_pane_layout"] = layout_mode
            self._save_config()

    def get_last_three_pane_layout(self) -> LayoutMode:
        """Last-used 3-pane mode (for first key **3** from 1×1 / 2×2)."""
        raw = self._config().get("last_three_pane_layout", "1+2R")
        if raw in THREE_PANE_LAYOUT_MODES:
            return cast(LayoutMode, raw)
        return "1+2R"

    def set_last_three_pane_layout(self, layout_mode: str) -> None:
        """Persist last-used 3-pane layout when user enters a 3-pane mode."""
        if layout_mode in THREE_PANE_LAYOUT_MODES:
            self._config()["last_three_pane_layout"] = layout_mode
            self._save_config()

    def get_view_slot_order(self) -> list[int]:
        """
        Get the 2x2 view slot order (slot index → view index).

        Used to restore which view occupies which grid cell after restart.

        Returns:
            List of 4 ints, a permutation of [0, 1, 2, 3]; default [0, 1, 2, 3]
        """
        return list(self._config().get("view_slot_order", [0, 1, 2, 3]))

    def set_view_slot_order(self, order: list[int]) -> None:
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
            self._config()["view_slot_order"] = list(order)
            self._save_config()

    def get_layout_map_popup_position(self) -> tuple[int, int] | None:
        """
        Get the last saved position (x, y) of the layout map thumbnail popup,
        in global/screen coordinates. Used when opening the popup from the context menu.

        Returns:
            (x, y) tuple or None if not set (e.g. first use)
        """
        raw = self._config().get("layout_map_popup_position")
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
        self._config()["layout_map_popup_position"] = [x, y]
        self._save_config()

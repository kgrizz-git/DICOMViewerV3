"""
Display Config Mixin

Manages visual display settings: theme, image smoothing, privacy view,
scroll-wheel mode, and histogram window geometry.

Mixin contract:
    Expects ``self.config`` (dict) and ``self.save_config()`` to be provided by
    the concrete ConfigManager class that inherits this mixin.
"""

from typing import Any, Callable, Optional, Tuple, cast


class DisplayConfigMixin:
    """Config mixin: theme, image smoothing, privacy view, scroll-wheel mode."""

    def _config(self) -> dict[str, Any]:
        return cast(dict[str, Any], getattr(self, "config"))

    def _save_config(self) -> None:
        save_func = cast(Callable[[], None], getattr(self, "save_config"))
        save_func()

    def get_theme(self) -> str:
        """
        Get the current theme preference.

        Returns:
            Theme name ("light" or "dark")
        """
        return self._config().get("theme", "light")

    def set_theme(self, theme: str) -> None:
        """
        Set the theme preference.

        Args:
            theme: Theme name ("light" or "dark")
        """
        if theme in ["light", "dark"]:
            self._config()["theme"] = theme
            self._save_config()

    def get_smooth_image_when_zoomed(self) -> bool:
        """
        Get whether image smoothing when zoomed is enabled.

        Returns:
            True if smoothing when zoomed is enabled, False otherwise
        """
        return self._config().get("smooth_image_when_zoomed", False)

    def set_smooth_image_when_zoomed(self, enabled: bool) -> None:
        """
        Set whether image smoothing when zoomed is enabled.

        Args:
            enabled: True to enable smoothing when zoomed, False to disable
        """
        self._config()["smooth_image_when_zoomed"] = enabled
        self._save_config()

    def get_show_scale_markers(self) -> bool:
        """
        Get whether viewer scale markers are enabled.

        Returns:
            True if scale markers are enabled, False otherwise
        """
        return self._config().get("show_scale_markers", False)

    def set_show_scale_markers(self, enabled: bool) -> None:
        """
        Set whether viewer scale markers are enabled.

        Args:
            enabled: True to enable scale markers, False to disable
        """
        self._config()["show_scale_markers"] = enabled
        self._save_config()

    def get_show_direction_labels(self) -> bool:
        """
        Get whether viewer direction labels are enabled.

        Returns:
            True if direction labels are enabled, False otherwise
        """
        return self._config().get("show_direction_labels", False)

    def set_show_direction_labels(self, enabled: bool) -> None:
        """
        Set whether viewer direction labels are enabled.

        Args:
            enabled: True to enable direction labels, False to disable
        """
        self._config()["show_direction_labels"] = enabled
        self._save_config()

    def get_scale_markers_color(self) -> tuple[int, int, int]:
        """
        Get scale marker color as RGB tuple.

        Returns:
            Tuple of (r, g, b) values (0-255)
        """
        r = self._config().get("scale_markers_color_r", 255)
        g = self._config().get("scale_markers_color_g", 255)
        b = self._config().get("scale_markers_color_b", 0)
        return (r, g, b)

    def set_scale_markers_color(self, r: int, g: int, b: int) -> None:
        """
        Set scale marker color.

        Args:
            r: Red component (0-255)
            g: Green component (0-255)
            b: Blue component (0-255)
        """
        if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
            self._config()["scale_markers_color_r"] = r
            self._config()["scale_markers_color_g"] = g
            self._config()["scale_markers_color_b"] = b
            self._save_config()

    def get_direction_labels_color(self) -> tuple[int, int, int]:
        """
        Get direction labels color as RGB tuple.

        Returns:
            Tuple of (r, g, b) values (0-255)
        """
        r = self._config().get("direction_labels_color_r", 255)
        g = self._config().get("direction_labels_color_g", 255)
        b = self._config().get("direction_labels_color_b", 0)
        return (r, g, b)

    def set_direction_labels_color(self, r: int, g: int, b: int) -> None:
        """
        Set direction labels color.

        Args:
            r: Red component (0-255)
            g: Green component (0-255)
            b: Blue component (0-255)
        """
        if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
            self._config()["direction_labels_color_r"] = r
            self._config()["direction_labels_color_g"] = g
            self._config()["direction_labels_color_b"] = b
            self._save_config()

    def get_direction_label_size(self) -> int:
        """
        Get direction label font size.

        Returns:
            Font size in points
        """
        return self._config().get("direction_label_size", 16)

    def set_direction_label_size(self, size: int) -> None:
        """
        Set direction label font size.

        Args:
            size: Font size in points
        """
        if size > 0:
            self._config()["direction_label_size"] = size
            self._save_config()

    def get_scale_markers_major_tick_interval_mm(self) -> int:
        """
        Get scale markers major tick interval in millimetres.

        Returns:
            Major tick interval in mm
        """
        return self._config().get("scale_markers_major_tick_interval_mm", 10)

    def set_scale_markers_major_tick_interval_mm(self, interval_mm: int) -> None:
        """
        Set scale markers major tick interval in millimetres.

        Args:
            interval_mm: Major tick interval in mm
        """
        if interval_mm > 0:
            self._config()["scale_markers_major_tick_interval_mm"] = interval_mm
            self._save_config()

    def get_scale_markers_minor_tick_interval_mm(self) -> int:
        """
        Get scale markers minor tick interval in millimetres.

        Returns:
            Minor tick interval in mm
        """
        return self._config().get("scale_markers_minor_tick_interval_mm", 5)

    def set_scale_markers_minor_tick_interval_mm(self, interval_mm: int) -> None:
        """
        Set scale markers minor tick interval in millimetres.

        Args:
            interval_mm: Minor tick interval in mm
        """
        if interval_mm > 0:
            self._config()["scale_markers_minor_tick_interval_mm"] = interval_mm
            self._save_config()

    def get_show_instances_separately(self) -> bool:
        """Get whether multi-frame instances should be shown separately in the navigator."""
        return self._config().get("show_instances_separately", False)

    def set_show_instances_separately(self, enabled: bool) -> None:
        """Set whether multi-frame instances should be shown separately in the navigator."""
        self._config()["show_instances_separately"] = enabled
        self._save_config()

    def get_privacy_view(self) -> bool:
        """
        Get whether privacy view mode is enabled.

        Returns:
            True if privacy view is enabled, False otherwise
        """
        return self._config().get("privacy_view_enabled", False)

    def set_privacy_view(self, enabled: bool) -> None:
        """
        Set whether privacy view mode is enabled.

        Args:
            enabled: True to enable privacy view, False to disable
        """
        self._config()["privacy_view_enabled"] = enabled
        self._save_config()

    def get_scroll_wheel_mode(self) -> str:
        """
        Get the scroll wheel mode.

        Returns:
            Mode ("slice" or "zoom")
        """
        return self._config().get("scroll_wheel_mode", "slice")

    def set_scroll_wheel_mode(self, mode: str) -> None:
        """
        Set the scroll wheel mode.

        Args:
            mode: Mode ("slice" or "zoom")
        """
        if mode in ["slice", "zoom"]:
            self._config()["scroll_wheel_mode"] = mode
            self._save_config()

    def get_histogram_window_geometry(self) -> Optional[Tuple[int, int, int, int]]:
        """
        Get the last saved histogram dialog geometry (x, y, width, height).
        Used to restore the histogram window position and size when reopened.

        Returns:
            (x, y, width, height) or None if not set
        """
        raw = self._config().get("histogram_window_geometry")
        if isinstance(raw, (list, tuple)) and len(raw) >= 4:
            try:
                return (int(raw[0]), int(raw[1]), int(raw[2]), int(raw[3]))
            except (TypeError, ValueError):
                pass
        return None

    def set_histogram_window_geometry(self, x: int, y: int, width: int, height: int) -> None:
        """
        Save the histogram dialog geometry for next time.

        Args:
            x, y: Window position (global/screen)
            width, height: Window size
        """
        self._config()["histogram_window_geometry"] = [x, y, width, height]
        self._save_config()

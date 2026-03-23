"""
Display Config Mixin

Manages visual display settings: theme, image smoothing, privacy view,
scroll-wheel mode, and histogram window geometry.

Mixin contract:
    Expects `self.config` (dict) and `self.save_config()` to be provided by
    the concrete ConfigManager class that inherits this mixin.
"""

from typing import Optional, Tuple


class DisplayConfigMixin:
    """Config mixin: theme, image smoothing, privacy view, scroll-wheel mode."""

    def get_theme(self) -> str:
        """
        Get the current theme preference.

        Returns:
            Theme name ("light" or "dark")
        """
        return self.config.get("theme", "light")

    def set_theme(self, theme: str) -> None:
        """
        Set the theme preference.

        Args:
            theme: Theme name ("light" or "dark")
        """
        if theme in ["light", "dark"]:
            self.config["theme"] = theme
            self.save_config()

    def get_smooth_image_when_zoomed(self) -> bool:
        """
        Get whether image smoothing when zoomed is enabled.

        Returns:
            True if smoothing when zoomed is enabled, False otherwise
        """
        return self.config.get("smooth_image_when_zoomed", False)

    def set_smooth_image_when_zoomed(self, enabled: bool) -> None:
        """
        Set whether image smoothing when zoomed is enabled.

        Args:
            enabled: True to enable smoothing when zoomed, False to disable
        """
        self.config["smooth_image_when_zoomed"] = enabled
        self.save_config()

    def get_show_scale_markers(self) -> bool:
        """
        Get whether viewer scale markers are enabled.

        Returns:
            True if scale markers are enabled, False otherwise
        """
        return self.config.get("show_scale_markers", False)

    def set_show_scale_markers(self, enabled: bool) -> None:
        """
        Set whether viewer scale markers are enabled.

        Args:
            enabled: True to enable scale markers, False to disable
        """
        self.config["show_scale_markers"] = enabled
        self.save_config()

    def get_show_direction_labels(self) -> bool:
        """
        Get whether viewer direction labels are enabled.

        Returns:
            True if direction labels are enabled, False otherwise
        """
        return self.config.get("show_direction_labels", False)

    def set_show_direction_labels(self, enabled: bool) -> None:
        """
        Set whether viewer direction labels are enabled.

        Args:
            enabled: True to enable direction labels, False to disable
        """
        self.config["show_direction_labels"] = enabled
        self.save_config()

    def get_show_instances_separately(self) -> bool:
        """Get whether multi-frame instances should be shown separately in the navigator."""
        return self.config.get("show_instances_separately", False)

    def set_show_instances_separately(self, enabled: bool) -> None:
        """Set whether multi-frame instances should be shown separately in the navigator."""
        self.config["show_instances_separately"] = enabled
        self.save_config()

    def get_privacy_view(self) -> bool:
        """
        Get whether privacy view mode is enabled.

        Returns:
            True if privacy view is enabled, False otherwise
        """
        return self.config.get("privacy_view_enabled", False)

    def set_privacy_view(self, enabled: bool) -> None:
        """
        Set whether privacy view mode is enabled.

        Args:
            enabled: True to enable privacy view, False to disable
        """
        self.config["privacy_view_enabled"] = enabled
        self.save_config()

    def get_scroll_wheel_mode(self) -> str:
        """
        Get the scroll wheel mode.

        Returns:
            Mode ("slice" or "zoom")
        """
        return self.config.get("scroll_wheel_mode", "slice")

    def set_scroll_wheel_mode(self, mode: str) -> None:
        """
        Set the scroll wheel mode.

        Args:
            mode: Mode ("slice" or "zoom")
        """
        if mode in ["slice", "zoom"]:
            self.config["scroll_wheel_mode"] = mode
            self.save_config()

    def get_histogram_window_geometry(self) -> Optional[Tuple[int, int, int, int]]:
        """
        Get the last saved histogram dialog geometry (x, y, width, height).
        Used to restore the histogram window position and size when reopened.

        Returns:
            (x, y, width, height) or None if not set
        """
        raw = self.config.get("histogram_window_geometry")
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
        self.config["histogram_window_geometry"] = [x, y, width, height]
        self.save_config()

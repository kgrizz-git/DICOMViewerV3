"""
Display Config Mixin

Manages visual display settings: theme, image smoothing, privacy view,
and scroll-wheel mode.

Mixin contract:
    Expects `self.config` (dict) and `self.save_config()` to be provided by
    the concrete ConfigManager class that inherits this mixin.
"""


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

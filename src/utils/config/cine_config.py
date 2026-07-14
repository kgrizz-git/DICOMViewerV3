"""
Cine Config Mixin

Manages cine (multi-frame) playback defaults: speed multiplier and loop toggle.

Mixin contract:
    Expects `self.config` (dict) and `self.save_config()` to be provided by
    the concrete ConfigManager class that inherits this mixin.
"""

from collections.abc import Callable
from typing import Any, cast


class CineConfigMixin:
    """Config mixin: cine playback default speed and loop setting."""

    def _config(self) -> dict[str, Any]:
        return cast(dict[str, Any], getattr(self, "config"))

    def _save_config(self) -> None:
        save_func = cast(Callable[[], None], getattr(self, "save_config"))
        save_func()

    def get_cine_default_speed(self) -> float:
        """
        Get default cine playback speed multiplier.

        Returns:
            Default speed multiplier (default: 1.0)
        """
        return self._config().get("cine_default_speed", 1.0)

    def set_cine_default_speed(self, speed: float) -> None:
        """
        Set default cine playback speed multiplier.

        Args:
            speed: Speed multiplier (e.g. 0.25, 0.5, 1.0, 2.0, 4.0)
        """
        self._config()["cine_default_speed"] = speed
        self._save_config()

    def get_cine_default_loop(self) -> bool:
        """
        Get default cine loop setting.

        Returns:
            Default loop setting (default: True)
        """
        return self._config().get("cine_default_loop", True)

    def set_cine_default_loop(self, loop: bool) -> None:
        """
        Set default cine loop setting.

        Args:
            loop: True to enable looping by default, False to disable
        """
        self._config()["cine_default_loop"] = loop
        self._save_config()

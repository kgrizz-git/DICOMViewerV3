"""
App Config Mixin

Manages application-level settings that do not belong to a specific feature
domain: currently the disclaimer-accepted flag.

Mixin contract:
    Expects `self.config` (dict) and `self.save_config()` to be provided by
    the concrete ConfigManager class that inherits this mixin.
"""

from collections.abc import Callable
from typing import Any, cast


class AppConfigMixin:
    """Config mixin: application-level settings (disclaimer acceptance)."""

    def _config(self) -> dict[str, Any]:
        return cast(dict[str, Any], getattr(self, "config"))

    def _save_config(self) -> None:
        save_func = cast(Callable[[], None], getattr(self, "save_config"))
        save_func()

    def get_disclaimer_accepted(self) -> bool:
        """
        Get whether the user has accepted the disclaimer and chosen not to see it again.

        Returns:
            True if disclaimer was accepted, False otherwise
        """
        return self._config().get("disclaimer_accepted", False)

    def set_disclaimer_accepted(self, accepted: bool) -> None:
        """
        Set whether the user has accepted the disclaimer.

        Args:
            accepted: True if user accepted and chose not to see it again
        """
        self._config()["disclaimer_accepted"] = accepted
        self._save_config()

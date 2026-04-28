"""
Measurement Config Mixin

Manages measurement tool appearance: font size/color and line
thickness/color for the distance/angle measurement tool.

Mixin contract:
    Expects ``self.config`` (dict) and ``self.save_config()`` to be provided by
    the concrete ConfigManager class that inherits this mixin.
"""

from typing import Any, Callable, cast


class MeasurementConfigMixin:
    """Config mixin: measurement font and line appearance settings."""

    def _config(self) -> dict[str, Any]:
        return cast(dict[str, Any], getattr(self, "config"))

    def _save_config(self) -> None:
        save_func = cast(Callable[[], None], getattr(self, "save_config"))
        save_func()

    def get_measurement_font_size(self) -> int:
        """Get measurement text font size."""
        return self._config().get("measurement_font_size", 12)

    def set_measurement_font_size(self, size: int) -> None:
        """Set measurement text font size."""
        if size > 0:
            self._config()["measurement_font_size"] = size
            self._save_config()

    def get_measurement_font_color(self) -> tuple[int, int, int]:
        """Get measurement text color as RGB tuple."""
        r = self._config().get("measurement_font_color_r", 0)
        g = self._config().get("measurement_font_color_g", 255)
        b = self._config().get("measurement_font_color_b", 0)
        return (r, g, b)

    def set_measurement_font_color(self, r: int, g: int, b: int) -> None:
        """Set measurement text color."""
        if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
            self._config()["measurement_font_color_r"] = r
            self._config()["measurement_font_color_g"] = g
            self._config()["measurement_font_color_b"] = b
            self._save_config()

    def get_measurement_line_thickness(self) -> int:
        """Get measurement line thickness in viewport pixels."""
        return self._config().get("measurement_line_thickness", 3)

    def set_measurement_line_thickness(self, thickness: int) -> None:
        """Set measurement line thickness in viewport pixels."""
        if thickness > 0:
            self._config()["measurement_line_thickness"] = thickness
            self._save_config()

    def get_measurement_line_color(self) -> tuple[int, int, int]:
        """Get measurement line color as RGB tuple."""
        r = self._config().get("measurement_line_color_r", 0)
        g = self._config().get("measurement_line_color_g", 255)
        b = self._config().get("measurement_line_color_b", 0)
        return (r, g, b)

    def set_measurement_line_color(self, r: int, g: int, b: int) -> None:
        """Set measurement line color."""
        if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
            self._config()["measurement_line_color_r"] = r
            self._config()["measurement_line_color_g"] = g
            self._config()["measurement_line_color_b"] = b
            self._save_config()

    def get_measurement_font_family(self) -> str:
        """Get measurement text font family."""
        return self._config().get("measurement_font_family", "IBM Plex Sans")

    def set_measurement_font_family(self, family: str) -> None:
        """Set measurement text font family."""
        from utils.bundled_fonts import get_font_families
        if family in get_font_families():
            self._config()["measurement_font_family"] = family
            self._save_config()

    def get_measurement_font_variant(self) -> str:
        """Get measurement font variant (e.g. "Bold", "Regular")."""
        from utils.bundled_fonts import resolve_font
        family = self.get_measurement_font_family()
        variant = self._config().get("measurement_font_variant", "Bold")
        _, variant = resolve_font(family, variant)
        return variant

    def set_measurement_font_variant(self, variant: str) -> None:
        """Set measurement font variant."""
        from utils.bundled_fonts import get_font_variants
        if variant in get_font_variants(self.get_measurement_font_family()):
            self._config()["measurement_font_variant"] = variant
            self._save_config()

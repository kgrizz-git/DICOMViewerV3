"""
ROI Config Mixin

Manages ROI (Region of Interest) appearance settings: font size/color,
line thickness/color, and default visible statistics.

Mixin contract:
    Expects `self.config` (dict) and `self.save_config()` to be provided by
    the concrete ConfigManager class that inherits this mixin.
"""

from typing import Any, Callable, List, cast


class ROIConfigMixin:
    """Config mixin: ROI font, line appearance, and default statistics visibility."""
    def _config(self) -> dict[str, Any]:
        return cast(dict[str, Any], getattr(self, "config"))

    def _save_config(self) -> None:
        save_func = cast(Callable[[], None], getattr(self, "save_config"))
        save_func()

    def get_roi_font_size(self) -> int:
        """Get ROI statistics overlay font size."""
        return self._config().get("roi_font_size", 12)

    def set_roi_font_size(self, size: int) -> None:
        """Set ROI statistics overlay font size."""
        if size > 0:
            self._config()["roi_font_size"] = size
            self._save_config()

    def get_roi_font_color(self) -> tuple[int, int, int]:
        """Get ROI statistics overlay font color as RGB tuple."""
        cfg = self._config()
        r = cfg.get("roi_font_color_r", 255)
        g = cfg.get("roi_font_color_g", 255)
        b = cfg.get("roi_font_color_b", 0)
        return (r, g, b)

    def set_roi_font_color(self, r: int, g: int, b: int) -> None:
        """Set ROI statistics overlay font color."""
        if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
            cfg = self._config()
            cfg["roi_font_color_r"] = r
            cfg["roi_font_color_g"] = g
            cfg["roi_font_color_b"] = b
            self._save_config()

    def get_roi_line_thickness(self) -> int:
        """Get ROI line thickness in viewport pixels."""
        return self._config().get("roi_line_thickness", 3)

    def set_roi_line_thickness(self, thickness: int) -> None:
        """Set ROI line thickness in viewport pixels."""
        if thickness > 0:
            self._config()["roi_line_thickness"] = thickness
            self._save_config()

    def get_roi_line_color(self) -> tuple[int, int, int]:
        """Get ROI line color as RGB tuple."""
        cfg = self._config()
        r = cfg.get("roi_line_color_r", 255)
        g = cfg.get("roi_line_color_g", 0)
        b = cfg.get("roi_line_color_b", 0)
        return (r, g, b)

    def set_roi_line_color(self, r: int, g: int, b: int) -> None:
        """Set ROI line color."""
        if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
            cfg = self._config()
            cfg["roi_line_color_r"] = r
            cfg["roi_line_color_g"] = g
            cfg["roi_line_color_b"] = b
            self._save_config()

    def get_roi_default_visible_statistics(self) -> List[str]:
        """Get default visible statistics for new ROIs."""
        stats = self._config().get(
            "roi_default_visible_statistics",
            ["mean", "std", "min", "max", "count", "area"],
        )
        if isinstance(stats, list):
            return stats
        return ["mean", "std", "min", "max", "count", "area"]

    def set_roi_default_visible_statistics(self, statistics: List[str]) -> None:
        """Set default visible statistics for new ROIs."""
        self._config()["roi_default_visible_statistics"] = statistics
        self._save_config()

    def get_roi_show_per_channel_statistics(self) -> bool:
        """
        When True (default), multi-channel (e.g. RGB) slices show per-channel ROI stats
        in the statistics panel and overlay when available.
        """
        return bool(self._config().get("roi_show_per_channel_statistics", True))

    def set_roi_show_per_channel_statistics(self, enabled: bool) -> None:
        """Enable or disable per-channel ROI statistics display."""
        self._config()["roi_show_per_channel_statistics"] = bool(enabled)
        self._save_config()

    def get_roi_font_family(self) -> str:
        """Get ROI statistics overlay font family."""
        return self._config().get("roi_font_family", "IBM Plex Sans")

    def set_roi_font_family(self, family: str) -> None:
        """Set ROI statistics overlay font family."""
        from utils.bundled_fonts import get_font_families
        if family in get_font_families():
            self._config()["roi_font_family"] = family
            self._save_config()

    def get_roi_font_variant(self) -> str:
        """Get ROI statistics font variant (e.g. "Bold", "Regular")."""
        from utils.bundled_fonts import resolve_font
        family = self.get_roi_font_family()
        variant = self._config().get("roi_font_variant", "Bold")
        _, variant = resolve_font(family, variant)
        return variant

    def set_roi_font_variant(self, variant: str) -> None:
        """Set ROI statistics font variant."""
        from utils.bundled_fonts import get_font_variants
        if variant in get_font_variants(self.get_roi_font_family()):
            self._config()["roi_font_variant"] = variant
            self._save_config()

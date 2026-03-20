"""
ROI Config Mixin

Manages ROI (Region of Interest) appearance settings: font size/color,
line thickness/color, and default visible statistics.

Mixin contract:
    Expects `self.config` (dict) and `self.save_config()` to be provided by
    the concrete ConfigManager class that inherits this mixin.
"""

from typing import List


class ROIConfigMixin:
    """Config mixin: ROI font, line appearance, and default statistics visibility."""

    def get_roi_font_size(self) -> int:
        """Get ROI statistics overlay font size."""
        return self.config.get("roi_font_size", 14)

    def set_roi_font_size(self, size: int) -> None:
        """Set ROI statistics overlay font size."""
        if size > 0:
            self.config["roi_font_size"] = size
            self.save_config()

    def get_roi_font_color(self) -> tuple:
        """Get ROI statistics overlay font color as RGB tuple."""
        r = self.config.get("roi_font_color_r", 255)
        g = self.config.get("roi_font_color_g", 255)
        b = self.config.get("roi_font_color_b", 0)
        return (r, g, b)

    def set_roi_font_color(self, r: int, g: int, b: int) -> None:
        """Set ROI statistics overlay font color."""
        if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
            self.config["roi_font_color_r"] = r
            self.config["roi_font_color_g"] = g
            self.config["roi_font_color_b"] = b
            self.save_config()

    def get_roi_line_thickness(self) -> int:
        """Get ROI line thickness in viewport pixels."""
        return self.config.get("roi_line_thickness", 6)

    def set_roi_line_thickness(self, thickness: int) -> None:
        """Set ROI line thickness in viewport pixels."""
        if thickness > 0:
            self.config["roi_line_thickness"] = thickness
            self.save_config()

    def get_roi_line_color(self) -> tuple:
        """Get ROI line color as RGB tuple."""
        r = self.config.get("roi_line_color_r", 255)
        g = self.config.get("roi_line_color_g", 0)
        b = self.config.get("roi_line_color_b", 0)
        return (r, g, b)

    def set_roi_line_color(self, r: int, g: int, b: int) -> None:
        """Set ROI line color."""
        if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
            self.config["roi_line_color_r"] = r
            self.config["roi_line_color_g"] = g
            self.config["roi_line_color_b"] = b
            self.save_config()

    def get_roi_default_visible_statistics(self) -> List[str]:
        """Get default visible statistics for new ROIs."""
        stats = self.config.get(
            "roi_default_visible_statistics",
            ["mean", "std", "min", "max", "count", "area"],
        )
        if isinstance(stats, list):
            return stats
        return ["mean", "std", "min", "max", "count", "area"]

    def set_roi_default_visible_statistics(self, statistics: List[str]) -> None:
        """Set default visible statistics for new ROIs."""
        self.config["roi_default_visible_statistics"] = statistics
        self.save_config()

    def get_roi_font_family(self) -> str:
        """Get ROI statistics overlay font family."""
        return self.config.get("roi_font_family", "IBM Plex Sans")

    def set_roi_font_family(self, family: str) -> None:
        """Set ROI statistics overlay font family."""
        from utils.bundled_fonts import get_font_families
        if family in get_font_families():
            self.config["roi_font_family"] = family
            self.save_config()

    def get_roi_font_variant(self) -> str:
        """Get ROI statistics font variant (e.g. "Bold", "Regular")."""
        from utils.bundled_fonts import resolve_font
        family = self.get_roi_font_family()
        variant = self.config.get("roi_font_variant", "Bold")
        _, variant = resolve_font(family, variant)
        return variant

    def set_roi_font_variant(self, variant: str) -> None:
        """Set ROI statistics font variant."""
        from utils.bundled_fonts import get_font_variants
        if variant in get_font_variants(self.get_roi_font_family()):
            self.config["roi_font_variant"] = variant
            self.save_config()

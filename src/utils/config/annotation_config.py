"""
Annotation Config Mixin

Manages text and arrow annotation appearance settings: color and font size
for text annotations; color and size for arrow annotations.

Mixin contract:
    Expects `self.config` (dict) and `self.save_config()` to be provided by
    the concrete ConfigManager class that inherits this mixin.
"""

from collections.abc import Callable
from typing import Any, cast

from utils.bundled_fonts import get_font_families, get_font_variants, resolve_font
from utils.debug_flags import DEBUG_FONT_VARIANT
from utils.debug_log import debug_log


class AnnotationConfigMixin:
    """Config mixin: text annotation and arrow annotation appearance."""

    def _config(self) -> dict[str, Any]:
        return cast(dict[str, Any], getattr(self, "config"))

    def _save_config(self) -> None:
        save_func = cast(Callable[[], None], getattr(self, "save_config"))
        save_func()

    def get_text_annotation_color(self) -> tuple[int, int, int]:
        """Get text annotation color as RGB tuple."""
        cfg = self._config()
        r = cfg.get("text_annotation_color_r", 255)
        g = cfg.get("text_annotation_color_g", 255)
        b = cfg.get("text_annotation_color_b", 0)
        return (r, g, b)

    def set_text_annotation_color(self, r: int, g: int, b: int) -> None:
        """Set text annotation color."""
        if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
            cfg = self._config()
            cfg["text_annotation_color_r"] = r
            cfg["text_annotation_color_g"] = g
            cfg["text_annotation_color_b"] = b
            self._save_config()

    def get_text_annotation_font_size(self) -> int:
        """Get text annotation font size."""
        return self._config().get("text_annotation_font_size", 12)

    def set_text_annotation_font_size(self, size: int) -> None:
        """Set text annotation font size."""
        if size > 0:
            self._config()["text_annotation_font_size"] = size
            self._save_config()

    def get_arrow_annotation_color(self) -> tuple[int, int, int]:
        """Get arrow annotation color as RGB tuple."""
        cfg = self._config()
        r = cfg.get("arrow_annotation_color_r", 255)
        g = cfg.get("arrow_annotation_color_g", 255)
        b = cfg.get("arrow_annotation_color_b", 0)
        return (r, g, b)

    def set_arrow_annotation_color(self, r: int, g: int, b: int) -> None:
        """Set arrow annotation color."""
        if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
            cfg = self._config()
            cfg["arrow_annotation_color_r"] = r
            cfg["arrow_annotation_color_g"] = g
            cfg["arrow_annotation_color_b"] = b
            self._save_config()

    def get_arrow_annotation_size(self) -> int:
        """Get arrow annotation size (line thickness; arrowhead scales via multiplier)."""
        return self._config().get("arrow_annotation_size", 6)

    def set_arrow_annotation_size(self, size: int) -> None:
        """Set arrow annotation size (arrowhead size and line thickness). Valid range 4-30."""
        if 4 <= size <= 30:
            self._config()["arrow_annotation_size"] = size
            self._save_config()

    def get_text_annotation_font_family(self) -> str:
        """Get text annotation font family name."""
        return self._config().get("text_annotation_font_family", "IBM Plex Sans")

    def set_text_annotation_font_family(self, family: str) -> None:
        """Set text annotation font family name."""
        if family in get_font_families():
            self._config()["text_annotation_font_family"] = family
            self._save_config()

    def get_text_annotation_font_variant(self) -> str:
        """Get text annotation font variant (e.g. "Bold", "Regular")."""
        family = self.get_text_annotation_font_family()
        variant = self._config().get("text_annotation_font_variant", "Bold")
        _, variant = resolve_font(family, variant)
        return variant

    def set_text_annotation_font_variant(self, variant: str) -> None:
        """Set text annotation font variant."""
        family = self.get_text_annotation_font_family()
        valid = get_font_variants(family)
        if DEBUG_FONT_VARIANT:
            debug_log(
                "annotation_config.py:set_text_annotation_font_variant",
                "Attempting to save text annotation font variant",
                {
                    "variant": variant,
                    "family": family,
                    "valid_variants": valid,
                    "accepted": variant in valid,
                },
                hypothesis_id="FONTVAR",
            )
        if variant in valid:
            self._config()["text_annotation_font_variant"] = variant
            self._save_config()

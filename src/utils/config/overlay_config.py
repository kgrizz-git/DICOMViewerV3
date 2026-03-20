"""
Overlay Config Mixin

Manages image overlay settings: display mode, visibility state, custom fields,
font size/color, and per-modality tag layouts.

Mixin contract:
    Expects `self.config` (dict) and `self.save_config()` to be provided by
    the concrete ConfigManager class that inherits this mixin.
"""

from typing import Dict, List


class OverlayConfigMixin:
    """Config mixin: overlay display mode, visibility, font, and per-modality tags."""

    def get_overlay_mode(self) -> str:
        """
        Get the overlay display mode.

        Returns:
            Overlay mode ("minimal", "detailed", or "hidden")
        """
        return self.config.get("overlay_mode", "minimal")

    def set_overlay_mode(self, mode: str) -> None:
        """
        Set the overlay display mode.

        Args:
            mode: Overlay mode ("minimal", "detailed", or "hidden")
        """
        if mode in ["minimal", "detailed", "hidden"]:
            self.config["overlay_mode"] = mode
            self.save_config()

    def get_overlay_visibility_state(self) -> int:
        """
        Get the overlay visibility state.

        Returns:
            Visibility state (0=show all, 1=hide corner text, 2=hide all text)
        """
        return self.config.get("overlay_visibility_state", 0)

    def set_overlay_visibility_state(self, state: int) -> None:
        """
        Set the overlay visibility state.

        Args:
            state: Visibility state (0=show all, 1=hide corner text, 2=hide all text)
        """
        if state in [0, 1, 2]:
            self.config["overlay_visibility_state"] = state
            self.save_config()

    def get_overlay_custom_fields(self) -> list:
        """
        Get the list of custom overlay fields.

        Returns:
            List of field names
        """
        return self.config.get("overlay_custom_fields", [])

    def set_overlay_custom_fields(self, fields: list) -> None:
        """
        Set the list of custom overlay fields.

        Args:
            fields: List of field names
        """
        self.config["overlay_custom_fields"] = fields
        self.save_config()

    def get_overlay_font_size(self) -> int:
        """
        Get overlay font size.

        Returns:
            Font size in points
        """
        return self.config.get("overlay_font_size", 10)

    def set_overlay_font_size(self, size: int) -> None:
        """
        Set overlay font size.

        Args:
            size: Font size in points
        """
        if size > 0:
            self.config["overlay_font_size"] = size
            self.save_config()

    def get_overlay_font_color(self) -> tuple:
        """
        Get overlay font color as RGB tuple.

        Returns:
            Tuple of (r, g, b) values (0-255)
        """
        r = self.config.get("overlay_font_color_r", 255)
        g = self.config.get("overlay_font_color_g", 255)
        b = self.config.get("overlay_font_color_b", 0)
        return (r, g, b)

    def set_overlay_font_color(self, r: int, g: int, b: int) -> None:
        """
        Set overlay font color.

        Args:
            r: Red component (0-255)
            g: Green component (0-255)
            b: Blue component (0-255)
        """
        if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
            self.config["overlay_font_color_r"] = r
            self.config["overlay_font_color_g"] = g
            self.config["overlay_font_color_b"] = b
            self.save_config()

    def get_overlay_font_family(self) -> str:
        """Get overlay font family name."""
        return self.config.get("overlay_font_family", "IBM Plex Sans")

    def set_overlay_font_family(self, family: str) -> None:
        """Set overlay font family name."""
        from utils.bundled_fonts import get_font_families
        if family in get_font_families():
            self.config["overlay_font_family"] = family
            self.save_config()

    def get_overlay_font_variant(self) -> str:
        """Get overlay font variant (e.g. "Bold", "Regular")."""
        from utils.bundled_fonts import resolve_font
        family = self.get_overlay_font_family()
        variant = self.config.get("overlay_font_variant", "Bold")
        _, variant = resolve_font(family, variant)
        return variant

    def set_overlay_font_variant(self, variant: str) -> None:
        """Set overlay font variant."""
        from utils.bundled_fonts import get_font_variants
        from utils.debug_flags import DEBUG_FONT_VARIANT
        from utils.debug_log import debug_log
        family = self.get_overlay_font_family()
        valid = get_font_variants(family)
        if DEBUG_FONT_VARIANT:
            debug_log(
                "overlay_config.py:set_overlay_font_variant",
                "Attempting to save overlay font variant",
                {
                    "variant": variant,
                    "family": family,
                    "valid_variants": valid,
                    "accepted": variant in valid,
                },
                hypothesis_id="FONTVAR",
            )
        if variant in valid:
            self.config["overlay_font_variant"] = variant
            self.save_config()

    def get_overlay_tags(self, modality: str = "default") -> Dict[str, List[str]]:
        """
        Get overlay tags for a modality, organised by corner.

        Args:
            modality: Modality name (e.g. "CT", "MR", "default")

        Returns:
            Dictionary with keys "upper_left", "upper_right", "lower_left",
            "lower_right" and values as lists of tag keywords.
        """
        if "overlay_tags" not in self.config:
            self.config["overlay_tags"] = {}

        if modality not in self.config["overlay_tags"]:
            return {
                "upper_left": ["PatientName", "PatientID", "StudyDate"],
                "upper_right": ["StationName", "PerformedStationName"],
                "lower_left": ["InstanceNumber", "SliceThickness", "SliceLocation"],
                "lower_right": ["SeriesNumber", "SeriesDescription", "StudyDescription"],
            }

        tags = self.config["overlay_tags"][modality]
        return {
            "upper_left": tags.get("upper_left", []),
            "upper_right": tags.get("upper_right", []),
            "lower_left": tags.get("lower_left", []),
            "lower_right": tags.get("lower_right", []),
        }

    def set_overlay_tags(self, modality: str, corner_tags: Dict[str, List[str]]) -> None:
        """
        Set overlay tags for a modality.

        Args:
            modality: Modality name (e.g. "CT", "MR")
            corner_tags: Dict with keys "upper_left", "upper_right", "lower_left",
                         "lower_right" and values as lists of tag keywords.
        """
        if "overlay_tags" not in self.config:
            self.config["overlay_tags"] = {}
        self.config["overlay_tags"][modality] = corner_tags
        self.save_config()

    def get_all_modalities(self) -> List[str]:
        """
        Get list of all modalities with saved overlay configurations.

        Returns:
            List of modality names
        """
        if "overlay_tags" not in self.config:
            return []
        return list(self.config["overlay_tags"].keys())

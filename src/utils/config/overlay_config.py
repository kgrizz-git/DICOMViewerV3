"""
Overlay Config Mixin

Manages image overlay settings: display mode, visibility state, custom fields,
font size/color, and per-modality tag layouts.

Mixin contract:
    Expects `self.config` (dict) and `self.save_config()` to be provided by
    the concrete ConfigManager class that inherits this mixin.
"""

from typing import Any, Callable, Dict, List, MutableMapping, cast

from utils.bundled_fonts import get_font_families, get_font_variants, resolve_font
from utils.debug_flags import DEBUG_FONT_VARIANT
from utils.debug_log import debug_log


class OverlayConfigMixin:
    """Config mixin: overlay display mode, visibility, font, and per-modality tags."""

    def _config(self) -> dict[str, Any]:
        return cast(dict[str, Any], getattr(self, "config"))

    def _save_config(self) -> None:
        save_func = cast(Callable[[], None], getattr(self, "save_config"))
        save_func()

    def get_overlay_mode(self) -> str:
        """
        Get the overlay display mode.

        Returns:
            Overlay mode ("minimal", "detailed", or "hidden")
        """
        return self._config().get("overlay_mode", "minimal")

    def set_overlay_mode(self, mode: str) -> None:
        """
        Set the overlay display mode.

        Args:
            mode: Overlay mode ("minimal", "detailed", or "hidden")
        """
        if mode in ["minimal", "detailed", "hidden"]:
            self._config()["overlay_mode"] = mode
            self._save_config()

    def get_overlay_visibility_state(self) -> int:
        """
        Get the overlay visibility state.

        Returns:
            Visibility state (0=show all, 1=hide corner text, 2=hide all text)
        """
        return self._config().get("overlay_visibility_state", 0)

    def set_overlay_visibility_state(self, state: int) -> None:
        """
        Set the overlay visibility state.

        Args:
            state: Visibility state (0=show all, 1=hide corner text, 2=hide all text)
        """
        if state in [0, 1, 2]:
            self._config()["overlay_visibility_state"] = state
            self._save_config()

    def get_overlay_custom_fields(self) -> List[str]:
        """
        Get the list of custom overlay fields.

        Returns:
            List of field names
        """
        return self._config().get("overlay_custom_fields", [])

    def set_overlay_custom_fields(self, fields: List[str]) -> None:
        """
        Set the list of custom overlay fields.

        Args:
            fields: List of field names
        """
        self._config()["overlay_custom_fields"] = fields
        self._save_config()

    def get_overlay_font_size(self) -> int:
        """
        Get overlay font size.

        Returns:
            Font size in points
        """
        return self._config().get("overlay_font_size", 10)

    def set_overlay_font_size(self, size: int) -> None:
        """
        Set overlay font size.

        Args:
            size: Font size in points
        """
        if size > 0:
            self._config()["overlay_font_size"] = size
            self._save_config()

    def get_overlay_font_color(self) -> tuple[int, int, int]:
        """
        Get overlay font color as RGB tuple.

        Returns:
            Tuple of (r, g, b) values (0-255)
        """
        cfg = self._config()
        r = cfg.get("overlay_font_color_r", 255)
        g = cfg.get("overlay_font_color_g", 255)
        b = cfg.get("overlay_font_color_b", 0)
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
            cfg = self._config()
            cfg["overlay_font_color_r"] = r
            cfg["overlay_font_color_g"] = g
            cfg["overlay_font_color_b"] = b
            self._save_config()

    def get_overlay_font_family(self) -> str:
        """Get overlay font family name."""
        return self._config().get("overlay_font_family", "IBM Plex Sans")

    def set_overlay_font_family(self, family: str) -> None:
        """Set overlay font family name."""
        if family in get_font_families():
            self._config()["overlay_font_family"] = family
            self._save_config()

    def get_overlay_font_variant(self) -> str:
        """Get overlay font variant (e.g. "Bold", "Regular")."""
        family = self.get_overlay_font_family()
        variant = self._config().get("overlay_font_variant", "Bold")
        _, variant = resolve_font(family, variant)
        return variant

    def set_overlay_font_variant(self, variant: str) -> None:
        """Set overlay font variant."""
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
            self._config()["overlay_font_variant"] = variant
            self._save_config()

    def get_overlay_tags(self, modality: str = "default") -> Dict[str, List[str]]:
        """
        Get overlay tags for a modality, organised by corner.

        Args:
            modality: Modality name (e.g. "CT", "MR", "default")

        Returns:
            Dictionary with keys "upper_left", "upper_right", "lower_left",
            "lower_right" and values as lists of tag keywords.
        """
        cfg = self._config()
        if "overlay_tags" not in cfg:
            cfg["overlay_tags"] = {}

        overlay_tags = cast(MutableMapping[str, Any], cfg["overlay_tags"])
        if modality not in overlay_tags:
            return {
                "upper_left": ["PatientName", "PatientID", "StudyDate"],
                "upper_right": ["StationName", "PerformedStationName"],
                "lower_left": ["InstanceNumber", "SliceThickness", "SliceLocation"],
                "lower_right": ["SeriesNumber", "SeriesDescription", "StudyDescription"],
            }

        tags = cast(MutableMapping[str, Any], overlay_tags[modality])
        return {
            "upper_left": list(tags.get("upper_left", [])),
            "upper_right": list(tags.get("upper_right", [])),
            "lower_left": list(tags.get("lower_left", [])),
            "lower_right": list(tags.get("lower_right", [])),
        }

    def set_overlay_tags(self, modality: str, corner_tags: Dict[str, List[str]]) -> None:
        """
        Set overlay tags for a modality.

        Args:
            modality: Modality name (e.g. "CT", "MR")
            corner_tags: Dict with keys "upper_left", "upper_right", "lower_left",
                         "lower_right" and values as lists of tag keywords.
        """
        cfg = self._config()
        if "overlay_tags" not in cfg:
            cfg["overlay_tags"] = {}
        cast(MutableMapping[str, Any], cfg["overlay_tags"])[modality] = corner_tags
        self._save_config()

    def get_overlay_tags_detailed_extra(self, modality: str = "default") -> Dict[str, List[str]]:
        """
        Get additional overlay tags per corner for Detailed mode only.

        These append after Simple tags (deduplicated at render time). Same four
        corner keys as ``get_overlay_tags``.

        Args:
            modality: Modality name (e.g. "CT", "MR", "default").

        Returns:
            Dict with keys upper_left, upper_right, lower_left, lower_right
            (lists may be empty).
        """
        empty = {
            "upper_left": [],
            "upper_right": [],
            "lower_left": [],
            "lower_right": [],
        }
        cfg = self._config()
        root = cfg.get("overlay_tags_detailed_extra")
        if not isinstance(root, dict):
            return {k: list(v) for k, v in empty.items()}
        by_mod = cast(MutableMapping[str, Any], root)
        if modality not in by_mod:
            return {k: list(v) for k, v in empty.items()}
        tags = cast(MutableMapping[str, Any], by_mod[modality])
        return {
            "upper_left": list(tags.get("upper_left", [])),
            "upper_right": list(tags.get("upper_right", [])),
            "lower_left": list(tags.get("lower_left", [])),
            "lower_right": list(tags.get("lower_right", [])),
        }

    def set_overlay_tags_detailed_extra(
        self, modality: str, corner_tags: Dict[str, List[str]]
    ) -> None:
        """
        Set additional per-corner tags for Detailed overlay mode.

        Args:
            modality: Modality name (e.g. "CT", "MR").
            corner_tags: Dict with keys upper_left, upper_right, lower_left,
                lower_right and values as lists of tag keywords.
        """
        cfg = self._config()
        if "overlay_tags_detailed_extra" not in cfg:
            cfg["overlay_tags_detailed_extra"] = {}
        cast(MutableMapping[str, Any], cfg["overlay_tags_detailed_extra"])[modality] = corner_tags
        self._save_config()

    def get_all_modalities(self) -> List[str]:
        """
        Get list of all modalities with saved overlay configurations.

        Returns:
            List of modality names
        """
        cfg = self._config()
        keys: set[str] = set()
        if "overlay_tags" in cfg and isinstance(cfg["overlay_tags"], dict):
            keys.update(cast(MutableMapping[str, Any], cfg["overlay_tags"]).keys())
        if "overlay_tags_detailed_extra" in cfg and isinstance(
            cfg["overlay_tags_detailed_extra"], dict
        ):
            keys.update(
                cast(MutableMapping[str, Any], cfg["overlay_tags_detailed_extra"]).keys()
            )
        return sorted(keys)

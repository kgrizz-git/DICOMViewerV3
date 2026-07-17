"""
Customizations Config Mixin

Handles bulk export and import of all visual customisation settings
(overlay, annotation, metadata panel, theme) to/from a JSON file.

The ``overlay`` object may include **slice sync group strip height** (viewport px)
alongside font and modality overlay fields; older export files omit it and import
leaves the current config value unchanged. Exports may include ``tags_detailed_extra``
(Additional tags in Detailed overlay mode); older files omit it.

Mixin contract:
    Expects ``self.config`` (dict) and ``self.save_config()`` to be provided by
    the concrete ConfigManager class that inherits this mixin.
    Also expects the getter/setter methods provided by the other mixins
    (OverlayConfigMixin, ROIConfigMixin, MeasurementConfigMixin,
    AnnotationConfigMixin, MetadataUIConfigMixin, DisplayConfigMixin).
"""
import json
from typing import Any, Protocol, cast

from utils.privacy.console import print_redacted


class _CustomizationsHost(Protocol):
    """Typing contract for ConfigManager combining all customisation mixins."""

    def get_overlay_mode(self) -> str: ...
    def get_overlay_visibility_state(self) -> int: ...
    def get_overlay_custom_fields(self) -> list[Any]: ...
    def get_overlay_font_size(self) -> int: ...
    def get_slice_sync_group_strip_height_px(self) -> int: ...
    def get_metadata_panel_column_widths(self) -> list[int]: ...
    def get_roi_font_size(self) -> int: ...
    def get_roi_line_thickness(self) -> int: ...
    def get_roi_default_visible_statistics(self) -> list[str]: ...
    def get_roi_show_per_channel_statistics(self) -> bool: ...
    def get_measurement_font_size(self) -> int: ...
    def get_measurement_line_thickness(self) -> int: ...
    def get_text_annotation_font_size(self) -> int: ...
    def get_theme(self) -> str: ...

    def set_overlay_mode(self, mode: str, *, persist: bool = True) -> None: ...
    def set_overlay_visibility_state(self, state: int) -> None: ...
    def set_overlay_custom_fields(self, fields: list[Any]) -> None: ...
    def set_overlay_tags(
        self, modality: str, corner_tags: dict[str, list[str]], *, persist: bool = True
    ) -> None: ...
    def set_overlay_tags_detailed_extra(
        self, modality: str, corner_tags: dict[str, list[str]], *, persist: bool = True
    ) -> None: ...
    def set_overlay_font_size(self, size: int) -> None: ...
    def set_overlay_font_color(self, r: int, g: int, b: int) -> None: ...
    def set_slice_sync_group_strip_height_px(self, height_px: int) -> None: ...
    def set_roi_font_size(self, size: int) -> None: ...
    def set_roi_font_color(self, r: int, g: int, b: int) -> None: ...
    def set_roi_line_thickness(self, thickness: int) -> None: ...
    def set_roi_line_color(self, r: int, g: int, b: int) -> None: ...
    def set_roi_default_visible_statistics(self, statistics: list[str]) -> None: ...
    def set_roi_show_per_channel_statistics(self, enabled: bool) -> None: ...
    def set_measurement_font_size(self, size: int) -> None: ...
    def set_measurement_font_color(self, r: int, g: int, b: int) -> None: ...
    def set_measurement_line_thickness(self, thickness: int) -> None: ...
    def set_measurement_line_color(self, r: int, g: int, b: int) -> None: ...
    def set_text_annotation_font_size(self, size: int) -> None: ...
    def set_text_annotation_color(self, r: int, g: int, b: int) -> None: ...
    def set_arrow_annotation_color(self, r: int, g: int, b: int) -> None: ...
    def set_arrow_annotation_size(self, size: int) -> None: ...
    def set_metadata_panel_column_widths(self, widths: list[int]) -> None: ...
    def set_theme(self, theme: str) -> None: ...


RGB = tuple[int, int, int]

# Allow-lists are domain rules, kept explicit rather than folded into helpers.
_OVERLAY_MODES = ("minimal", "detailed", "hidden")
_VISIBILITY_STATES = (0, 1, 2)
_THEMES = ("light", "dark")


def _apply_rgb(raw: Any, setter: Any, defaults: RGB) -> None:
    """
    Apply an ``{"r": .., "g": .., "b": ..}`` colour object via ``setter(r, g, b)``.

    Missing components fall back to ``defaults``. Out-of-range components cause the
    colour to be *rejected* (setter not called), leaving the existing value intact —
    values are never clamped.
    """
    if not isinstance(raw, dict):
        return
    r = raw.get("r", defaults[0])
    g = raw.get("g", defaults[1])
    b = raw.get("b", defaults[2])
    if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
        setter(r, g, b)


def _apply_int(raw: Any, setter: Any, lo: int | None = None, hi: int | None = None) -> None:
    """Apply an int via ``setter(value)`` when it is an int within ``[lo, hi]``."""
    if not isinstance(raw, int):
        return
    if lo is not None and raw < lo:
        return
    if hi is not None and raw > hi:
        return
    setter(raw)


def _apply_modality_tags(raw: Any, setter: Any) -> None:
    """Apply a ``{modality: {corner: [tags]}}`` mapping one modality at a time."""
    if not isinstance(raw, dict):
        return
    for modality, corner_tags in raw.items():
        if isinstance(modality, str) and isinstance(corner_tags, dict):
            setter(modality, corner_tags)


def _import_overlay(h: "_CustomizationsHost", overlay: dict[str, Any]) -> None:
    """Import the ``overlay`` section."""
    if overlay.get("mode") in _OVERLAY_MODES:
        h.set_overlay_mode(overlay["mode"])
    if overlay.get("visibility_state") in _VISIBILITY_STATES:
        h.set_overlay_visibility_state(overlay["visibility_state"])
    if isinstance(overlay.get("custom_fields"), list):
        h.set_overlay_custom_fields(overlay["custom_fields"])
    _apply_modality_tags(overlay.get("tags"), h.set_overlay_tags)
    _apply_modality_tags(overlay.get("tags_detailed_extra"), h.set_overlay_tags_detailed_extra)
    _apply_int(overlay.get("font_size"), h.set_overlay_font_size, lo=1)
    _apply_rgb(overlay.get("font_color"), h.set_overlay_font_color, (255, 255, 0))
    # Intentionally unbounded: type-checked only, matching historical behaviour.
    _apply_int(
        overlay.get("slice_sync_group_strip_height_px"),
        h.set_slice_sync_group_strip_height_px,
    )


def _import_roi(h: "_CustomizationsHost", roi: dict[str, Any]) -> None:
    """Import the ``annotation.roi`` sub-section."""
    _apply_int(roi.get("font_size"), h.set_roi_font_size, lo=1)
    _apply_rgb(roi.get("font_color"), h.set_roi_font_color, (255, 255, 0))
    _apply_int(roi.get("line_thickness"), h.set_roi_line_thickness, lo=1)
    _apply_rgb(roi.get("line_color"), h.set_roi_line_color, (255, 0, 0))
    if isinstance(roi.get("default_visible_statistics"), list):
        h.set_roi_default_visible_statistics(roi["default_visible_statistics"])
    if isinstance(roi.get("show_per_channel_statistics"), bool):
        h.set_roi_show_per_channel_statistics(bool(roi["show_per_channel_statistics"]))


def _import_measurement(h: "_CustomizationsHost", meas: dict[str, Any]) -> None:
    """Import the ``annotation.measurement`` sub-section."""
    _apply_int(meas.get("font_size"), h.set_measurement_font_size, lo=1)
    _apply_rgb(meas.get("font_color"), h.set_measurement_font_color, (0, 255, 0))
    _apply_int(meas.get("line_thickness"), h.set_measurement_line_thickness, lo=1)
    _apply_rgb(meas.get("line_color"), h.set_measurement_line_color, (0, 255, 0))


def _import_text_annotation(h: "_CustomizationsHost", ta: dict[str, Any]) -> None:
    """Import the ``annotation.text_annotation`` sub-section."""
    _apply_int(ta.get("font_size"), h.set_text_annotation_font_size, lo=1)
    _apply_rgb(ta.get("color"), h.set_text_annotation_color, (255, 255, 0))


def _import_arrow_annotation(h: "_CustomizationsHost", aa: dict[str, Any]) -> None:
    """Import the ``annotation.arrow_annotation`` sub-section."""
    _apply_rgb(aa.get("color"), h.set_arrow_annotation_color, (255, 255, 0))
    _apply_int(aa.get("size"), h.set_arrow_annotation_size, lo=4, hi=30)


_ANNOTATION_HANDLERS = {
    "roi": _import_roi,
    "measurement": _import_measurement,
    "text_annotation": _import_text_annotation,
    "arrow_annotation": _import_arrow_annotation,
}


def _import_annotation(h: "_CustomizationsHost", annotation: dict[str, Any]) -> None:
    """Import the ``annotation`` section by delegating to its sub-section handlers."""
    for name, handler in _ANNOTATION_HANDLERS.items():
        sub = annotation.get(name)
        if isinstance(sub, dict):
            handler(h, sub)


def _import_metadata_panel(h: "_CustomizationsHost", mp: dict[str, Any]) -> None:
    """Import the ``metadata_panel`` section (column widths: exactly 4 positive ints)."""
    widths = mp.get("column_widths")
    if (
        isinstance(widths, list)
        and len(widths) == 4
        and all(isinstance(w, int) and w > 0 for w in widths)
    ):
        h.set_metadata_panel_column_widths(widths)


_SECTION_HANDLERS = {
    "overlay": _import_overlay,
    "annotation": _import_annotation,
    "metadata_panel": _import_metadata_panel,
}


class CustomizationsConfigMixin:
    """Config mixin: export and import of all visual customisations."""

    def _config(self) -> dict[str, Any]:
        return cast(dict[str, Any], getattr(self, "config"))

    def export_customizations(self, file_path: str) -> bool:
        """
        Export customisation settings to a JSON file.

        Exports overlay configuration (including slice-sync group strip height),
        annotation options, metadata panel settings, and theme.  Does NOT export
        disclaimer_accepted or other non-customisation settings.

        Args:
            file_path: Path where the customisation file should be saved

        Returns:
            True if export was successful, False otherwise
        """
        h = cast(_CustomizationsHost, cast(object, self))
        cfg = self._config()
        try:
            overlay_data = {
                "mode": h.get_overlay_mode(),
                "visibility_state": h.get_overlay_visibility_state(),
                "custom_fields": h.get_overlay_custom_fields(),
                "tags": cfg.get("overlay_tags", {}),
                "tags_detailed_extra": cfg.get("overlay_tags_detailed_extra", {}),
                "font_size": h.get_overlay_font_size(),
                "font_color": {
                    "r": cfg.get("overlay_font_color_r", 255),
                    "g": cfg.get("overlay_font_color_g", 255),
                    "b": cfg.get("overlay_font_color_b", 0),
                },
                "slice_sync_group_strip_height_px": h.get_slice_sync_group_strip_height_px(),
            }

            metadata_panel_data = {
                "column_widths": h.get_metadata_panel_column_widths()
            }

            annotation_data = {
                "roi": {
                    "font_size": h.get_roi_font_size(),
                    "font_color": {
                        "r": cfg.get("roi_font_color_r", 255),
                        "g": cfg.get("roi_font_color_g", 255),
                        "b": cfg.get("roi_font_color_b", 0),
                    },
                    "line_thickness": h.get_roi_line_thickness(),
                    "line_color": {
                        "r": cfg.get("roi_line_color_r", 255),
                        "g": cfg.get("roi_line_color_g", 0),
                        "b": cfg.get("roi_line_color_b", 0),
                    },
                    "default_visible_statistics": h.get_roi_default_visible_statistics(),
                    "show_per_channel_statistics": h.get_roi_show_per_channel_statistics(),
                },
                "measurement": {
                    "font_size": h.get_measurement_font_size(),
                    "font_color": {
                        "r": cfg.get("measurement_font_color_r", 0),
                        "g": cfg.get("measurement_font_color_g", 255),
                        "b": cfg.get("measurement_font_color_b", 0),
                    },
                    "line_thickness": h.get_measurement_line_thickness(),
                    "line_color": {
                        "r": cfg.get("measurement_line_color_r", 0),
                        "g": cfg.get("measurement_line_color_g", 255),
                        "b": cfg.get("measurement_line_color_b", 0),
                    },
                },
                "text_annotation": {
                    "font_size": h.get_text_annotation_font_size(),
                    "color": {
                        "r": cfg.get("text_annotation_color_r", 255),
                        "g": cfg.get("text_annotation_color_g", 255),
                        "b": cfg.get("text_annotation_color_b", 0),
                    },
                },
                "arrow_annotation": {
                    "color": {
                        "r": cfg.get("arrow_annotation_color_r", 255),
                        "g": cfg.get("arrow_annotation_color_g", 255),
                        "b": cfg.get("arrow_annotation_color_b", 0),
                    },
                    "size": cfg.get("arrow_annotation_size", 6),
                },
            }

            export_data = {
                "version": "1.0",
                "overlay": overlay_data,
                "annotation": annotation_data,
                "metadata_panel": metadata_panel_data,
                "theme": h.get_theme(),
            }

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=4, ensure_ascii=False)
            return True
        except (OSError, TypeError, ValueError) as e:
            print_redacted(f"Error exporting customizations: {e}")
            return False

    def import_customizations(self, file_path: str) -> bool:
        """
        Import customisation settings from a JSON file.

        Validates file structure and updates config with imported values.
        Does NOT import disclaimer_accepted or other non-customisation settings.

        Args:
            file_path: Path to the customisation file to import

        Returns:
            True if import was successful, False otherwise
        """
        h = cast(_CustomizationsHost, cast(object, self))
        try:
            with open(file_path, encoding="utf-8") as f:
                import_data = json.load(f)

            if not isinstance(import_data, dict):
                print("Error: Import file is not a valid JSON object")
                return False

            for name, handler in _SECTION_HANDLERS.items():
                section = import_data.get(name)
                if isinstance(section, dict):
                    handler(h, section)

            # Theme is a bare string, not a section dict.
            if import_data.get("theme") in _THEMES:
                h.set_theme(import_data["theme"])

            return True
        except (OSError, json.JSONDecodeError) as e:
            print_redacted(f"Error importing customizations: {e}")
            return False

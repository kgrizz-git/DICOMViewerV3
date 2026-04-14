"""
Customizations Config Mixin

Handles bulk export and import of all visual customisation settings
(overlay, annotation, metadata panel, theme) to/from a JSON file.

The ``overlay`` object may include **slice sync group strip height** (viewport px)
alongside font and modality overlay fields; older export files omit it and import
leaves the current config value unchanged.

Mixin contract:
    Expects ``self.config`` (dict) and ``self.save_config()`` to be provided by
    the concrete ConfigManager class that inherits this mixin.
    Also expects the getter/setter methods provided by the other mixins
    (OverlayConfigMixin, ROIConfigMixin, MeasurementConfigMixin,
    AnnotationConfigMixin, MetadataUIConfigMixin, DisplayConfigMixin).
"""

import json
from typing import Any, Dict, List, Protocol, cast


class _CustomizationsHost(Protocol):
    """Typing contract for ConfigManager combining all customisation mixins."""

    def get_overlay_mode(self) -> str: ...
    def get_overlay_visibility_state(self) -> int: ...
    def get_overlay_custom_fields(self) -> List[Any]: ...
    def get_overlay_font_size(self) -> int: ...
    def get_slice_sync_group_strip_height_px(self) -> int: ...
    def get_metadata_panel_column_widths(self) -> List[int]: ...
    def get_roi_font_size(self) -> int: ...
    def get_roi_line_thickness(self) -> int: ...
    def get_roi_default_visible_statistics(self) -> List[str]: ...
    def get_measurement_font_size(self) -> int: ...
    def get_measurement_line_thickness(self) -> int: ...
    def get_text_annotation_font_size(self) -> int: ...
    def get_theme(self) -> str: ...

    def set_overlay_mode(self, mode: str) -> None: ...
    def set_overlay_visibility_state(self, state: int) -> None: ...
    def set_overlay_custom_fields(self, fields: List[Any]) -> None: ...
    def set_overlay_tags(self, modality: str, corner_tags: Dict[str, List[str]]) -> None: ...
    def set_overlay_font_size(self, size: int) -> None: ...
    def set_overlay_font_color(self, r: int, g: int, b: int) -> None: ...
    def set_slice_sync_group_strip_height_px(self, height_px: int) -> None: ...
    def set_roi_font_size(self, size: int) -> None: ...
    def set_roi_font_color(self, r: int, g: int, b: int) -> None: ...
    def set_roi_line_thickness(self, thickness: int) -> None: ...
    def set_roi_line_color(self, r: int, g: int, b: int) -> None: ...
    def set_roi_default_visible_statistics(self, statistics: List[str]) -> None: ...
    def set_measurement_font_size(self, size: int) -> None: ...
    def set_measurement_font_color(self, r: int, g: int, b: int) -> None: ...
    def set_measurement_line_thickness(self, thickness: int) -> None: ...
    def set_measurement_line_color(self, r: int, g: int, b: int) -> None: ...
    def set_text_annotation_font_size(self, size: int) -> None: ...
    def set_text_annotation_color(self, r: int, g: int, b: int) -> None: ...
    def set_arrow_annotation_color(self, r: int, g: int, b: int) -> None: ...
    def set_arrow_annotation_size(self, size: int) -> None: ...
    def set_metadata_panel_column_widths(self, widths: List[int]) -> None: ...
    def set_theme(self, theme: str) -> None: ...


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
            print(f"Error exporting customizations: {e}")
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
            with open(file_path, "r", encoding="utf-8") as f:
                import_data = json.load(f)

            if not isinstance(import_data, dict):
                print("Error: Import file is not a valid JSON object")
                return False

            if "overlay" in import_data:
                overlay = import_data["overlay"]
                if isinstance(overlay, dict):
                    if "mode" in overlay and overlay["mode"] in ["minimal", "detailed", "hidden"]:
                        h.set_overlay_mode(overlay["mode"])
                    if "visibility_state" in overlay and overlay["visibility_state"] in [0, 1, 2]:
                        h.set_overlay_visibility_state(overlay["visibility_state"])
                    if "custom_fields" in overlay and isinstance(overlay["custom_fields"], list):
                        h.set_overlay_custom_fields(overlay["custom_fields"])
                    if "tags" in overlay and isinstance(overlay["tags"], dict):
                        for modality, corner_tags in overlay["tags"].items():
                            if isinstance(modality, str) and isinstance(corner_tags, dict):
                                h.set_overlay_tags(modality, corner_tags)
                    if "font_size" in overlay and isinstance(overlay["font_size"], int) and overlay["font_size"] > 0:
                        h.set_overlay_font_size(overlay["font_size"])
                    if "font_color" in overlay and isinstance(overlay["font_color"], dict):
                        fc = overlay["font_color"]
                        r, g, b = fc.get("r", 255), fc.get("g", 255), fc.get("b", 0)
                        if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
                            h.set_overlay_font_color(r, g, b)
                    if "slice_sync_group_strip_height_px" in overlay and isinstance(
                        overlay["slice_sync_group_strip_height_px"], int
                    ):
                        h.set_slice_sync_group_strip_height_px(
                            int(overlay["slice_sync_group_strip_height_px"])
                        )

            if "annotation" in import_data:
                annotation = import_data["annotation"]
                if isinstance(annotation, dict):
                    if "roi" in annotation and isinstance(annotation["roi"], dict):
                        roi = annotation["roi"]
                        if "font_size" in roi and isinstance(roi["font_size"], int) and roi["font_size"] > 0:
                            h.set_roi_font_size(roi["font_size"])
                        if "font_color" in roi and isinstance(roi["font_color"], dict):
                            fc = roi["font_color"]
                            r, g, b = fc.get("r", 255), fc.get("g", 255), fc.get("b", 0)
                            if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
                                h.set_roi_font_color(r, g, b)
                        if "line_thickness" in roi and isinstance(roi["line_thickness"], int) and roi["line_thickness"] > 0:
                            h.set_roi_line_thickness(roi["line_thickness"])
                        if "line_color" in roi and isinstance(roi["line_color"], dict):
                            lc = roi["line_color"]
                            r, g, b = lc.get("r", 255), lc.get("g", 0), lc.get("b", 0)
                            if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
                                h.set_roi_line_color(r, g, b)
                        if "default_visible_statistics" in roi and isinstance(roi["default_visible_statistics"], list):
                            h.set_roi_default_visible_statistics(roi["default_visible_statistics"])

                    if "measurement" in annotation and isinstance(annotation["measurement"], dict):
                        meas = annotation["measurement"]
                        if "font_size" in meas and isinstance(meas["font_size"], int) and meas["font_size"] > 0:
                            h.set_measurement_font_size(meas["font_size"])
                        if "font_color" in meas and isinstance(meas["font_color"], dict):
                            fc = meas["font_color"]
                            r, g, b = fc.get("r", 0), fc.get("g", 255), fc.get("b", 0)
                            if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
                                h.set_measurement_font_color(r, g, b)
                        if "line_thickness" in meas and isinstance(meas["line_thickness"], int) and meas["line_thickness"] > 0:
                            h.set_measurement_line_thickness(meas["line_thickness"])
                        if "line_color" in meas and isinstance(meas["line_color"], dict):
                            lc = meas["line_color"]
                            r, g, b = lc.get("r", 0), lc.get("g", 255), lc.get("b", 0)
                            if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
                                h.set_measurement_line_color(r, g, b)

                    if "text_annotation" in annotation and isinstance(annotation["text_annotation"], dict):
                        ta = annotation["text_annotation"]
                        if "font_size" in ta and isinstance(ta["font_size"], int) and ta["font_size"] > 0:
                            h.set_text_annotation_font_size(ta["font_size"])
                        if "color" in ta and isinstance(ta["color"], dict):
                            c = ta["color"]
                            r, g, b = c.get("r", 255), c.get("g", 255), c.get("b", 0)
                            if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
                                h.set_text_annotation_color(r, g, b)

                    if "arrow_annotation" in annotation and isinstance(annotation["arrow_annotation"], dict):
                        aa = annotation["arrow_annotation"]
                        if "color" in aa and isinstance(aa["color"], dict):
                            c = aa["color"]
                            r, g, b = c.get("r", 255), c.get("g", 255), c.get("b", 0)
                            if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
                                h.set_arrow_annotation_color(r, g, b)
                        if "size" in aa and isinstance(aa["size"], int) and 4 <= aa["size"] <= 30:
                            h.set_arrow_annotation_size(aa["size"])

            if "metadata_panel" in import_data:
                mp = import_data["metadata_panel"]
                if isinstance(mp, dict) and "column_widths" in mp:
                    widths = mp["column_widths"]
                    if isinstance(widths, list) and len(widths) == 4 and all(
                        isinstance(w, int) and w > 0 for w in widths
                    ):
                        h.set_metadata_panel_column_widths(widths)

            if "theme" in import_data and import_data["theme"] in ["light", "dark"]:
                h.set_theme(import_data["theme"])

            return True
        except (OSError, json.JSONDecodeError) as e:
            print(f"Error importing customizations: {e}")
            return False

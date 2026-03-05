"""
Tag Export Config Mixin

Manages tag export preset settings: save, retrieve, delete, and
import/export presets to/from JSON files.

Mixin contract:
    Expects `self.config` (dict) and `self.save_config()` to be provided by
    the concrete ConfigManager class that inherits this mixin.
"""

import json
from typing import Dict, List, Optional


class TagExportConfigMixin:
    """Config mixin: tag export presets (CRUD and file import/export)."""

    def get_tag_export_presets(self) -> Dict[str, List[str]]:
        """
        Get tag export presets.

        Returns:
            Dictionary mapping preset names to lists of tag strings
        """
        return self.config.get("tag_export_presets", {})

    def save_tag_export_preset(self, preset_name: str, tag_list: List[str]) -> None:
        """
        Save a tag export preset.

        Args:
            preset_name: Name of the preset
            tag_list: List of tag strings to save
        """
        if "tag_export_presets" not in self.config:
            self.config["tag_export_presets"] = {}
        self.config["tag_export_presets"][preset_name] = tag_list
        self.save_config()

    def delete_tag_export_preset(self, preset_name: str) -> None:
        """
        Delete a tag export preset.

        Args:
            preset_name: Name of the preset to delete
        """
        if "tag_export_presets" in self.config:
            if preset_name in self.config["tag_export_presets"]:
                del self.config["tag_export_presets"][preset_name]
                self.save_config()

    def export_tag_export_presets(self, file_path: str) -> bool:
        """
        Export all tag export presets to a JSON file.

        The exported file contains only tag export presets so it can be
        shared or backed up independently of other customisations.

        Args:
            file_path: Path where the presets file should be saved.

        Returns:
            True if export was successful, False otherwise.
        """
        try:
            presets = self.get_tag_export_presets()
            export_data = {"version": "1.0", "presets": presets}
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=4, ensure_ascii=False)
            return True
        except (IOError, TypeError, ValueError) as e:
            print(f"Error exporting tag export presets: {e}")
            return False

    def import_tag_export_presets(self, file_path: str) -> Optional[Dict[str, int]]:
        """
        Import tag export presets from a JSON file.

        Existing presets are preserved.  If an imported preset name already
        exists it is skipped (keeps existing value).

        Args:
            file_path: Path to the presets file to import.

        Returns:
            Dictionary with:
                - "imported": number of presets successfully imported
                - "skipped_conflicts": number of presets skipped due to
                  existing names
            or None if import failed due to I/O or validation errors.
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                import_data = json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            print(f"Error importing tag export presets: {e}")
            return None

        if not isinstance(import_data, dict):
            print("Error importing tag export presets: root JSON object must be a dict")
            return None

        presets_obj = import_data.get("presets")
        if not isinstance(presets_obj, dict):
            print("Error importing tag export presets: 'presets' key missing or not a dict")
            return None

        if "tag_export_presets" not in self.config or not isinstance(
            self.config.get("tag_export_presets"), dict
        ):
            self.config["tag_export_presets"] = {}

        existing_presets: Dict[str, List[str]] = self.config["tag_export_presets"]
        imported_count = 0
        skipped_conflicts = 0

        for name, tag_list in presets_obj.items():
            if not isinstance(name, str):
                continue
            if not isinstance(tag_list, list) or not all(
                isinstance(tag, str) for tag in tag_list
            ):
                continue
            if name in existing_presets:
                skipped_conflicts += 1
                continue
            existing_presets[name] = tag_list
            imported_count += 1

        if imported_count > 0:
            self.save_config()

        return {"imported": imported_count, "skipped_conflicts": skipped_conflicts}

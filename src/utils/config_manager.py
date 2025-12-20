"""
Configuration Manager

This module handles persistent storage and retrieval of user preferences and settings.
Settings are stored in a JSON file in the user's application data directory.

Inputs:
    - User preferences (last opened path, theme, overlay settings, etc.)
    
Outputs:
    - Loaded configuration values
    - Saved configuration file
    
Requirements:
    - json module (standard library)
    - pathlib module (standard library)
    - os module (standard library)
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, List


class ConfigManager:
    """
    Manages application configuration and user preferences.
    
    Handles loading and saving of settings including:
    - Last opened file/folder path
    - Theme preference (dark/light)
    - Overlay customization settings
    - Window geometry
    - Other user preferences
    """
    
    def __init__(self, config_filename: str = "dicom_viewer_config.json"):
        """
        Initialize the configuration manager.
        
        Args:
            config_filename: Name of the configuration file to use
        """
        # Get application data directory
        if os.name == 'nt':  # Windows
            app_data = os.getenv('APPDATA', os.path.expanduser('~'))
            self.config_dir = Path(app_data) / "DICOMViewerV3"
        else:  # Mac/Linux
            self.config_dir = Path.home() / ".config" / "DICOMViewerV3"
        
        # Create config directory if it doesn't exist
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Full path to config file
        self.config_path = self.config_dir / config_filename
        
        # Default configuration values
        self.default_config = {
            "last_path": "",
            "last_export_path": "",  # Last directory used for exporting images
            "theme": "dark",
        "overlay_mode": "minimal",  # minimal, detailed, hidden
        "overlay_visibility_state": 0,  # 0=show all, 1=hide corner text, 2=hide all text
        "overlay_custom_fields": [],
        "overlay_font_size": 10,  # Default font size (10pt)
            "overlay_font_color_r": 255,  # Yellow default
            "overlay_font_color_g": 255,
            "overlay_font_color_b": 0,
            # Overlay tag configuration: modality -> corner -> list of tags
            # Default: current minimal fields go to upper-left for all modalities
            "overlay_tags": {},  # Will store {modality: {corner: [tags]}}
            "window_width": 1200,
            "window_height": 700,
            "scroll_wheel_mode": "slice",  # slice or zoom
            "window_level_default": None,
            "window_width_default": None,
            "recent_files": [],  # List of recently opened file/folder paths (max 20)
            "metadata_panel_column_widths": [100, 200, 50, 200],  # Column widths for Tag, Name, VR, Value
            "cine_default_speed": 1.0,  # Default cine playback speed multiplier
            "cine_default_loop": True,  # Default cine loop setting
            # Annotation options
            "roi_font_size": 14,  # ROI statistics overlay font size
            "roi_font_color_r": 255,  # ROI statistics overlay font color (yellow default)
            "roi_font_color_g": 255,
            "roi_font_color_b": 0,
            "roi_line_thickness": 6,  # ROI line thickness in viewport pixels
            "roi_line_color_r": 255,  # ROI line color (red default)
            "roi_line_color_g": 0,
            "roi_line_color_b": 0,
            "measurement_font_size": 14,  # Measurement text font size
            "measurement_font_color_r": 0,  # Measurement text color (green default)
            "measurement_font_color_g": 255,
            "measurement_font_color_b": 0,
            "measurement_line_thickness": 6,  # Measurement line thickness in viewport pixels
            "measurement_line_color_r": 0,  # Measurement line color (green default)
            "measurement_line_color_g": 255,
            "measurement_line_color_b": 0,
            # ROI statistics visibility defaults
            "roi_default_visible_statistics": ["mean", "std", "min", "max", "count", "area"],  # Default visible statistics for new ROIs
            "multi_window_layout": "1x1",  # Multi-window layout mode: "1x1", "1x2", "2x1", "2x2"
            "disclaimer_accepted": False,  # Whether user has accepted disclaimer and chosen not to see it again
            "privacy_view_enabled": False,  # Whether privacy view mode is enabled (masks patient tags in display)
        }
        
        # Load configuration
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """
        Load configuration from file, or return defaults if file doesn't exist.
        
        Returns:
            Dictionary containing configuration values
        """
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    config = self.default_config.copy()
                    config.update(loaded_config)
                    return config
            except (json.JSONDecodeError, IOError) as e:
                # If file is corrupted, use defaults
                print(f"Warning: Could not load config file: {e}")
                return self.default_config.copy()
        else:
            # File doesn't exist, use defaults
            return self.default_config.copy()
    
    def save_config(self) -> bool:
        """
        Save current configuration to file.
        
        Returns:
            True if save was successful, False otherwise
        """
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            return True
        except IOError as e:
            print(f"Error saving config file: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.
        
        Args:
            key: Configuration key to retrieve
            default: Default value if key doesn't exist
            
        Returns:
            Configuration value or default
        """
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value.
        
        Args:
            key: Configuration key to set
            value: Value to set
        """
        self.config[key] = value
    
    def get_last_path(self) -> str:
        """
        Get the last opened file or folder path.
        
        Returns:
            Path string, empty if not set
        """
        return self.config.get("last_path", "")
    
    def set_last_path(self, path: str) -> None:
        """
        Set the last opened file or folder path.
        
        Args:
            path: Path to save
        """
        self.config["last_path"] = path
        self.save_config()
    
    def get_last_export_path(self) -> str:
        """
        Get the last export directory path.
        
        Returns:
            Path string, empty if not set
        """
        return self.config.get("last_export_path", "")
    
    def set_last_export_path(self, path: str) -> None:
        """
        Set the last export directory path.
        
        Args:
            path: Path to save
        """
        self.config["last_export_path"] = path
        self.save_config()
    
    def get_theme(self) -> str:
        """
        Get the current theme preference.
        
        Returns:
            Theme name ("light" or "dark")
        """
        return self.config.get("theme", "light")
    
    def set_theme(self, theme: str) -> None:
        """
        Set the theme preference.
        
        Args:
            theme: Theme name ("light" or "dark")
        """
        if theme in ["light", "dark"]:
            self.config["theme"] = theme
            self.save_config()
    
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
    
    def get_scroll_wheel_mode(self) -> str:
        """
        Get the scroll wheel mode.
        
        Returns:
            Mode ("slice" or "zoom")
        """
        return self.config.get("scroll_wheel_mode", "slice")
    
    def set_scroll_wheel_mode(self, mode: str) -> None:
        """
        Set the scroll wheel mode.
        
        Args:
            mode: Mode ("slice" or "zoom")
        """
        if mode in ["slice", "zoom"]:
            self.config["scroll_wheel_mode"] = mode
            self.save_config()
    
    def get_multi_window_layout(self) -> str:
        """
        Get the multi-window layout mode.
        
        Returns:
            Layout mode ("1x1", "1x2", "2x1", or "2x2")
        """
        return self.config.get("multi_window_layout", "1x1")
    
    def set_multi_window_layout(self, layout_mode: str) -> None:
        """
        Set the multi-window layout mode.
        
        Args:
            layout_mode: Layout mode ("1x1", "1x2", "2x1", or "2x2")
        """
        if layout_mode in ["1x1", "1x2", "2x1", "2x2"]:
            self.config["multi_window_layout"] = layout_mode
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
        
        The exported file contains only tag export presets so it can be easily
        shared or backed up independently of other customizations.
        
        Args:
            file_path: Path where the presets file should be saved.
        
        Returns:
            True if export was successful, False otherwise.
        """
        try:
            presets = self.get_tag_export_presets()
            # Build export structure – simple and versioned for future changes
            export_data = {
                "version": "1.0",
                "presets": presets
            }
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=4, ensure_ascii=False)
            return True
        except (IOError, TypeError, ValueError) as e:
            print(f"Error exporting tag export presets: {e}")
            return False

    def import_tag_export_presets(self, file_path: str) -> Optional[Dict[str, int]]:
        """
        Import tag export presets from a JSON file.
        
        Existing presets are preserved. If an imported preset name already
        exists, it is skipped (keeps existing value). The method returns a
        dictionary with counts describing what happened.
        
        Args:
            file_path: Path to the presets file to import.
        
        Returns:
            Dictionary with:
                - \"imported\": number of presets successfully imported
                - \"skipped_conflicts\": number of presets skipped due to
                  existing names
            or None if import failed due to I/O or validation errors.
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                import_data = json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            print(f"Error importing tag export presets: {e}")
            return None

        # Basic structure validation
        if not isinstance(import_data, dict):
            print("Error importing tag export presets: root JSON object must be a dict")
            return None

        presets_obj = import_data.get("presets")
        if not isinstance(presets_obj, dict):
            print("Error importing tag export presets: 'presets' key missing or not a dict")
            return None

        # Ensure destination structure exists
        if "tag_export_presets" not in self.config or not isinstance(
            self.config.get("tag_export_presets"), dict
        ):
            self.config["tag_export_presets"] = {}

        existing_presets: Dict[str, List[str]] = self.config["tag_export_presets"]
        imported_count = 0
        skipped_conflicts = 0

        for name, tag_list in presets_obj.items():
            # Only accept string names and list-of-strings payloads
            if not isinstance(name, str):
                continue
            if not isinstance(tag_list, list) or not all(
                isinstance(tag, str) for tag in tag_list
            ):
                continue

            if name in existing_presets:
                # Skip conflicting names per design
                skipped_conflicts += 1
                continue

            existing_presets[name] = tag_list
            imported_count += 1

        # Persist changes if we imported anything
        if imported_count > 0:
            self.save_config()

        return {
            "imported": imported_count,
            "skipped_conflicts": skipped_conflicts,
        }
    
    def get_overlay_tags(self, modality: str = "default") -> Dict[str, List[str]]:
        """
        Get overlay tags for a modality, organized by corner.
        
        Args:
            modality: Modality name (e.g., "CT", "MR", "default")
            
        Returns:
            Dictionary with keys "upper_left", "upper_right", "lower_left", "lower_right"
            and values as lists of tag keywords
        """
        if "overlay_tags" not in self.config:
            self.config["overlay_tags"] = {}
        
        if modality not in self.config["overlay_tags"]:
            # Return default: tags distributed across corners
            return {
                "upper_left": ["PatientName", "PatientID", "StudyDate"],
                "upper_right": ["StationName", "PerformedStationName"],
                "lower_left": ["InstanceNumber", "SliceThickness", "SliceLocation"],
                "lower_right": ["SeriesNumber", "SeriesDescription", "StudyDescription"]
            }
        
        tags = self.config["overlay_tags"][modality]
        # Ensure all corners exist
        result = {
            "upper_left": tags.get("upper_left", []),
            "upper_right": tags.get("upper_right", []),
            "lower_left": tags.get("lower_left", []),
            "lower_right": tags.get("lower_right", [])
        }
        return result
    
    def set_overlay_tags(self, modality: str, corner_tags: Dict[str, List[str]]) -> None:
        """
        Set overlay tags for a modality.
        
        Args:
            modality: Modality name (e.g., "CT", "MR")
            corner_tags: Dictionary with keys "upper_left", "upper_right", "lower_left", "lower_right"
                        and values as lists of tag keywords
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
    
    def get_recent_files(self) -> List[str]:
        """
        Get list of recently opened files and folders.
        
        Returns:
            List of file/folder paths (most recent first)
        """
        return self.config.get("recent_files", [])
    
    def add_recent_file(self, file_path: str) -> None:
        """
        Add a file or folder to recent files list.
        
        Removes duplicates and keeps only the most recent 20 items.
        
        Args:
            file_path: Path to file or folder
        """
        recent_files = self.config.get("recent_files", [])
        
        # Remove if already exists (to move to top)
        if file_path in recent_files:
            recent_files.remove(file_path)
        
        # Add to beginning
        recent_files.insert(0, file_path)
        
        # Keep only last 20
        recent_files = recent_files[:20]
        
        self.config["recent_files"] = recent_files
        self.save_config()
    
    def remove_recent_file(self, file_path: str) -> None:
        """
        Remove a file or folder from recent files list.
        
        Args:
            file_path: Path to file or folder to remove
        """
        recent_files = self.config.get("recent_files", [])
        
        if file_path in recent_files:
            recent_files.remove(file_path)
            self.config["recent_files"] = recent_files
            self.save_config()
    
    def get_metadata_panel_column_widths(self) -> List[int]:
        """
        Get saved column widths for metadata panel.
        
        Returns:
            List of column widths [Tag, Name, VR, Value]
        """
        return self.config.get("metadata_panel_column_widths", [100, 200, 50, 200])
    
    def set_metadata_panel_column_widths(self, widths: List[int]) -> None:
        """
        Save column widths for metadata panel.
        
        Args:
            widths: List of column widths [Tag, Name, VR, Value]
        """
        self.config["metadata_panel_column_widths"] = widths
        self.save_config()
    
    def get_metadata_panel_column_order(self) -> List[int]:
        """
        Get saved column order for metadata panel.
        
        Returns:
            List of logical indices in visual order [Tag, Name, VR, Value]
            Default: [0, 1, 2, 3] (no reordering)
        """
        return self.config.get("metadata_panel_column_order", [0, 1, 2, 3])
    
    def set_metadata_panel_column_order(self, order: List[int]) -> None:
        """
        Save column order for metadata panel.
        
        Args:
            order: List of logical indices in visual order [Tag, Name, VR, Value]
                   e.g., [1, 0, 2, 3] means Name column is first visually
        """
        self.config["metadata_panel_column_order"] = order
        self.save_config()
    
    def get_cine_default_speed(self) -> float:
        """
        Get default cine playback speed multiplier.
        
        Returns:
            Default speed multiplier (default: 1.0)
        """
        return self.config.get("cine_default_speed", 1.0)
    
    def set_cine_default_speed(self, speed: float) -> None:
        """
        Set default cine playback speed multiplier.
        
        Args:
            speed: Speed multiplier (e.g., 0.25, 0.5, 1.0, 2.0, 4.0)
        """
        self.config["cine_default_speed"] = speed
        self.save_config()
    
    def get_cine_default_loop(self) -> bool:
        """
        Get default cine loop setting.
        
        Returns:
            Default loop setting (default: True)
        """
        return self.config.get("cine_default_loop", True)
    
    def set_cine_default_loop(self, loop: bool) -> None:
        """
        Set default cine loop setting.
        
        Args:
            loop: True to enable looping by default, False to disable
        """
        self.config["cine_default_loop"] = loop
        self.save_config()
    
    # Annotation options getters and setters
    
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
    
    def get_measurement_font_size(self) -> int:
        """Get measurement text font size."""
        return self.config.get("measurement_font_size", 14)
    
    def set_measurement_font_size(self, size: int) -> None:
        """Set measurement text font size."""
        if size > 0:
            self.config["measurement_font_size"] = size
            self.save_config()
    
    def get_measurement_font_color(self) -> tuple:
        """Get measurement text color as RGB tuple."""
        r = self.config.get("measurement_font_color_r", 0)
        g = self.config.get("measurement_font_color_g", 255)
        b = self.config.get("measurement_font_color_b", 0)
        return (r, g, b)
    
    def set_measurement_font_color(self, r: int, g: int, b: int) -> None:
        """Set measurement text color."""
        if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
            self.config["measurement_font_color_r"] = r
            self.config["measurement_font_color_g"] = g
            self.config["measurement_font_color_b"] = b
            self.save_config()
    
    def get_measurement_line_thickness(self) -> int:
        """Get measurement line thickness in viewport pixels."""
        return self.config.get("measurement_line_thickness", 6)
    
    def set_measurement_line_thickness(self, thickness: int) -> None:
        """Set measurement line thickness in viewport pixels."""
        if thickness > 0:
            self.config["measurement_line_thickness"] = thickness
            self.save_config()
    
    def get_measurement_line_color(self) -> tuple:
        """Get measurement line color as RGB tuple."""
        r = self.config.get("measurement_line_color_r", 0)
        g = self.config.get("measurement_line_color_g", 255)
        b = self.config.get("measurement_line_color_b", 0)
        return (r, g, b)
    
    def set_measurement_line_color(self, r: int, g: int, b: int) -> None:
        """Set measurement line color."""
        if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
            self.config["measurement_line_color_r"] = r
            self.config["measurement_line_color_g"] = g
            self.config["measurement_line_color_b"] = b
            self.save_config()
    
    def get_text_annotation_color(self) -> tuple:
        """Get text annotation color as RGB tuple."""
        r = self.config.get("text_annotation_color_r", 255)
        g = self.config.get("text_annotation_color_g", 255)
        b = self.config.get("text_annotation_color_b", 0)
        return (r, g, b)
    
    def set_text_annotation_color(self, r: int, g: int, b: int) -> None:
        """Set text annotation color."""
        if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
            self.config["text_annotation_color_r"] = r
            self.config["text_annotation_color_g"] = g
            self.config["text_annotation_color_b"] = b
            self.save_config()
    
    def get_text_annotation_font_size(self) -> int:
        """Get text annotation font size."""
        return self.config.get("text_annotation_font_size", 12)
    
    def set_text_annotation_font_size(self, size: int) -> None:
        """Set text annotation font size."""
        if size > 0:
            self.config["text_annotation_font_size"] = size
            self.save_config()
    
    def get_arrow_annotation_color(self) -> tuple:
        """Get arrow annotation color as RGB tuple."""
        r = self.config.get("arrow_annotation_color_r", 255)
        g = self.config.get("arrow_annotation_color_g", 255)
        b = self.config.get("arrow_annotation_color_b", 0)
        return (r, g, b)
    
    def set_arrow_annotation_color(self, r: int, g: int, b: int) -> None:
        """Set arrow annotation color."""
        if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
            self.config["arrow_annotation_color_r"] = r
            self.config["arrow_annotation_color_g"] = g
            self.config["arrow_annotation_color_b"] = b
            self.save_config()
    
    def get_roi_default_visible_statistics(self) -> List[str]:
        """Get default visible statistics for new ROIs."""
        stats = self.config.get("roi_default_visible_statistics", ["mean", "std", "min", "max", "count", "area"])
        # Ensure it's a list
        if isinstance(stats, list):
            return stats
        return ["mean", "std", "min", "max", "count", "area"]
    
    def set_roi_default_visible_statistics(self, statistics: List[str]) -> None:
        """Set default visible statistics for new ROIs."""
        self.config["roi_default_visible_statistics"] = statistics
        self.save_config()
    
    def get_disclaimer_accepted(self) -> bool:
        """
        Get whether the user has accepted the disclaimer and chosen not to see it again.
        
        Returns:
            True if disclaimer was accepted and user chose not to see it again, False otherwise
        """
        return self.config.get("disclaimer_accepted", False)
    
    def set_disclaimer_accepted(self, accepted: bool) -> None:
        """
        Set whether the user has accepted the disclaimer.
        
        Args:
            accepted: True if user accepted and chose not to see it again, False otherwise
        """
        self.config["disclaimer_accepted"] = accepted
        self.save_config()
    
    def get_privacy_view(self) -> bool:
        """
        Get whether privacy view mode is enabled.
        
        Returns:
            True if privacy view is enabled, False otherwise
        """
        return self.config.get("privacy_view_enabled", False)
    
    def set_privacy_view(self, enabled: bool) -> None:
        """
        Set whether privacy view mode is enabled.
        
        Args:
            enabled: True to enable privacy view, False to disable
        """
        self.config["privacy_view_enabled"] = enabled
        self.save_config()
    
    def export_customizations(self, file_path: str) -> bool:
        """
        Export customization settings to a JSON file.
        
        Exports overlay configuration, overlay font size/color, annotation options,
        and theme. Does NOT export disclaimer_accepted or other non-customization settings.
        
        Args:
            file_path: Path where the customization file should be saved
            
        Returns:
            True if export was successful, False otherwise
        """
        try:
            # Collect overlay settings
            overlay_data = {
                "mode": self.get_overlay_mode(),
                "visibility_state": self.get_overlay_visibility_state(),
                "custom_fields": self.get_overlay_custom_fields(),
                "tags": self.config.get("overlay_tags", {}),
                "font_size": self.get_overlay_font_size(),
                "font_color": {
                    "r": self.config.get("overlay_font_color_r", 255),
                    "g": self.config.get("overlay_font_color_g", 255),
                    "b": self.config.get("overlay_font_color_b", 0)
                }
            }
            
            # Collect metadata panel settings
            metadata_panel_data = {
                "column_widths": self.get_metadata_panel_column_widths()
            }
            
            # Collect annotation settings
            annotation_data = {
                "roi": {
                    "font_size": self.get_roi_font_size(),
                    "font_color": {
                        "r": self.config.get("roi_font_color_r", 255),
                        "g": self.config.get("roi_font_color_g", 255),
                        "b": self.config.get("roi_font_color_b", 0)
                    },
                    "line_thickness": self.get_roi_line_thickness(),
                    "line_color": {
                        "r": self.config.get("roi_line_color_r", 255),
                        "g": self.config.get("roi_line_color_g", 0),
                        "b": self.config.get("roi_line_color_b", 0)
                    },
                    "default_visible_statistics": self.get_roi_default_visible_statistics()
                },
                "measurement": {
                    "font_size": self.get_measurement_font_size(),
                    "font_color": {
                        "r": self.config.get("measurement_font_color_r", 0),
                        "g": self.config.get("measurement_font_color_g", 255),
                        "b": self.config.get("measurement_font_color_b", 0)
                    },
                    "line_thickness": self.get_measurement_line_thickness(),
                    "line_color": {
                        "r": self.config.get("measurement_line_color_r", 0),
                        "g": self.config.get("measurement_line_color_g", 255),
                        "b": self.config.get("measurement_line_color_b", 0)
                    }
                },
                "text_annotation": {
                    "font_size": self.get_text_annotation_font_size(),
                    "color": {
                        "r": self.config.get("text_annotation_color_r", 255),
                        "g": self.config.get("text_annotation_color_g", 255),
                        "b": self.config.get("text_annotation_color_b", 0)
                    }
                },
                "arrow_annotation": {
                    "color": {
                        "r": self.config.get("arrow_annotation_color_r", 255),
                        "g": self.config.get("arrow_annotation_color_g", 255),
                        "b": self.config.get("arrow_annotation_color_b", 0)
                    }
                }
            }
            
            # Build export data structure
            export_data = {
                "version": "1.0",
                "overlay": overlay_data,
                "annotation": annotation_data,
                "metadata_panel": metadata_panel_data,
                "theme": self.get_theme()
            }
            
            # Write to file
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=4, ensure_ascii=False)
            
            return True
        except (IOError, json.JSONEncodeError) as e:
            print(f"Error exporting customizations: {e}")
            return False
    
    def import_customizations(self, file_path: str) -> bool:
        """
        Import customization settings from a JSON file.
        
        Validates file structure and updates config with imported values.
        Does NOT import disclaimer_accepted or other non-customization settings.
        
        Args:
            file_path: Path to the customization file to import
            
        Returns:
            True if import was successful, False otherwise
        """
        try:
            # Read file
            with open(file_path, 'r', encoding='utf-8') as f:
                import_data = json.load(f)
            
            # Validate structure
            if not isinstance(import_data, dict):
                print("Error: Import file is not a valid JSON object")
                return False
            
            # Import overlay settings
            if "overlay" in import_data:
                overlay = import_data["overlay"]
                if isinstance(overlay, dict):
                    if "mode" in overlay and overlay["mode"] in ["minimal", "detailed", "hidden"]:
                        self.set_overlay_mode(overlay["mode"])
                    if "visibility_state" in overlay and overlay["visibility_state"] in [0, 1, 2]:
                        self.set_overlay_visibility_state(overlay["visibility_state"])
                    if "custom_fields" in overlay and isinstance(overlay["custom_fields"], list):
                        self.set_overlay_custom_fields(overlay["custom_fields"])
                    if "tags" in overlay and isinstance(overlay["tags"], dict):
                        # Import overlay tags for all modalities
                        for modality, corner_tags in overlay["tags"].items():
                            if isinstance(corner_tags, dict):
                                self.set_overlay_tags(modality, corner_tags)
                    if "font_size" in overlay and isinstance(overlay["font_size"], int) and overlay["font_size"] > 0:
                        self.set_overlay_font_size(overlay["font_size"])
                    if "font_color" in overlay and isinstance(overlay["font_color"], dict):
                        font_color = overlay["font_color"]
                        r = font_color.get("r", 255)
                        g = font_color.get("g", 255)
                        b = font_color.get("b", 0)
                        if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
                            self.set_overlay_font_color(r, g, b)
            
            # Import annotation settings
            if "annotation" in import_data:
                annotation = import_data["annotation"]
                if isinstance(annotation, dict):
                    # ROI settings
                    if "roi" in annotation and isinstance(annotation["roi"], dict):
                        roi = annotation["roi"]
                        if "font_size" in roi and isinstance(roi["font_size"], int) and roi["font_size"] > 0:
                            self.set_roi_font_size(roi["font_size"])
                        if "font_color" in roi and isinstance(roi["font_color"], dict):
                            font_color = roi["font_color"]
                            r = font_color.get("r", 255)
                            g = font_color.get("g", 255)
                            b = font_color.get("b", 0)
                            if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
                                self.set_roi_font_color(r, g, b)
                        if "line_thickness" in roi and isinstance(roi["line_thickness"], int) and roi["line_thickness"] > 0:
                            self.set_roi_line_thickness(roi["line_thickness"])
                        if "line_color" in roi and isinstance(roi["line_color"], dict):
                            line_color = roi["line_color"]
                            r = line_color.get("r", 255)
                            g = line_color.get("g", 0)
                            b = line_color.get("b", 0)
                            if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
                                self.set_roi_line_color(r, g, b)
                        if "default_visible_statistics" in roi and isinstance(roi["default_visible_statistics"], list):
                            self.set_roi_default_visible_statistics(roi["default_visible_statistics"])
                    
                    # Measurement settings
                    if "measurement" in annotation and isinstance(annotation["measurement"], dict):
                        measurement = annotation["measurement"]
                        if "font_size" in measurement and isinstance(measurement["font_size"], int) and measurement["font_size"] > 0:
                            self.set_measurement_font_size(measurement["font_size"])
                        if "font_color" in measurement and isinstance(measurement["font_color"], dict):
                            font_color = measurement["font_color"]
                            r = font_color.get("r", 0)
                            g = font_color.get("g", 255)
                            b = font_color.get("b", 0)
                            if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
                                self.set_measurement_font_color(r, g, b)
                        if "line_thickness" in measurement and isinstance(measurement["line_thickness"], int) and measurement["line_thickness"] > 0:
                            self.set_measurement_line_thickness(measurement["line_thickness"])
                        if "line_color" in measurement and isinstance(measurement["line_color"], dict):
                            line_color = measurement["line_color"]
                            r = line_color.get("r", 0)
                            g = line_color.get("g", 255)
                            b = line_color.get("b", 0)
                            if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
                                self.set_measurement_line_color(r, g, b)
                    
                    # Text annotation settings
                    if "text_annotation" in annotation and isinstance(annotation["text_annotation"], dict):
                        text_annotation = annotation["text_annotation"]
                        if "font_size" in text_annotation and isinstance(text_annotation["font_size"], int) and text_annotation["font_size"] > 0:
                            self.set_text_annotation_font_size(text_annotation["font_size"])
                        if "color" in text_annotation and isinstance(text_annotation["color"], dict):
                            color = text_annotation["color"]
                            r = color.get("r", 255)
                            g = color.get("g", 255)
                            b = color.get("b", 0)
                            if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
                                self.set_text_annotation_color(r, g, b)
                    
                    # Arrow annotation settings
                    if "arrow_annotation" in annotation and isinstance(annotation["arrow_annotation"], dict):
                        arrow_annotation = annotation["arrow_annotation"]
                        if "color" in arrow_annotation and isinstance(arrow_annotation["color"], dict):
                            color = arrow_annotation["color"]
                            r = color.get("r", 255)
                            g = color.get("g", 255)
                            b = color.get("b", 0)
                            if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
                                self.set_arrow_annotation_color(r, g, b)
            
            # Import metadata panel settings
            if "metadata_panel" in import_data:
                metadata_panel = import_data["metadata_panel"]
                if isinstance(metadata_panel, dict):
                    if "column_widths" in metadata_panel and isinstance(metadata_panel["column_widths"], list):
                        widths = metadata_panel["column_widths"]
                        # Validate it's a list of 4 integers
                        if len(widths) == 4 and all(isinstance(w, int) and w > 0 for w in widths):
                            self.set_metadata_panel_column_widths(widths)
            
            # Import theme
            if "theme" in import_data:
                theme = import_data["theme"]
                if theme in ["light", "dark"]:
                    self.set_theme(theme)
            
            return True
        except (IOError, json.JSONDecodeError) as e:
            print(f"Error importing customizations: {e}")
            return False


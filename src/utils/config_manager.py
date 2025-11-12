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
            "window_height": 800,
            "scroll_wheel_mode": "slice",  # slice or zoom
            "window_level_default": None,
            "window_width_default": None,
            "recent_files": [],  # List of recently opened file/folder paths (max 10)
            "metadata_panel_column_widths": [100, 200, 50, 200],  # Column widths for Tag, Name, VR, Value
            "cine_default_speed": 1.0,  # Default cine playback speed multiplier
            "cine_default_loop": False,  # Default cine loop setting
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
            # Return default: current minimal fields in upper-left
            return {
                "upper_left": ["PatientName", "StudyDate", "SeriesDescription", "InstanceNumber"],
                "upper_right": [],
                "lower_left": [],
                "lower_right": []
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
        
        Removes duplicates and keeps only the most recent 10 items.
        
        Args:
            file_path: Path to file or folder
        """
        recent_files = self.config.get("recent_files", [])
        
        # Remove if already exists (to move to top)
        if file_path in recent_files:
            recent_files.remove(file_path)
        
        # Add to beginning
        recent_files.insert(0, file_path)
        
        # Keep only last 10
        recent_files = recent_files[:10]
        
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
            Default loop setting (default: False)
        """
        return self.config.get("cine_default_loop", False)
    
    def set_cine_default_loop(self, loop: bool) -> None:
        """
        Set default cine loop setting.
        
        Args:
            loop: True to enable looping by default, False to disable
        """
        self.config["cine_default_loop"] = loop
        self.save_config()


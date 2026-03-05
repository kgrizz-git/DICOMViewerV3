"""
Configuration Manager

Manages persistent storage and retrieval of user preferences and settings.
Settings are stored in a JSON file in the user's application data directory.

This module provides a thin ConfigManager facade that composes twelve
feature-domain mixin classes.  All public getter/setter methods live in the
mixin files under ``src/utils/config/``; this file contains only the core
infrastructure (load, save, generic get/set) and the default configuration
dictionary.

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
from typing import Any, Dict

from utils.config.paths_config import PathsConfigMixin
from utils.config.display_config import DisplayConfigMixin
from utils.config.overlay_config import OverlayConfigMixin
from utils.config.layout_config import LayoutConfigMixin
from utils.config.roi_config import ROIConfigMixin
from utils.config.measurement_config import MeasurementConfigMixin
from utils.config.annotation_config import AnnotationConfigMixin
from utils.config.cine_config import CineConfigMixin
from utils.config.metadata_ui_config import MetadataUIConfigMixin
from utils.config.tag_export_config import TagExportConfigMixin
from utils.config.customizations_config import CustomizationsConfigMixin
from utils.config.app_config import AppConfigMixin


class ConfigManager(
    PathsConfigMixin,
    DisplayConfigMixin,
    OverlayConfigMixin,
    LayoutConfigMixin,
    ROIConfigMixin,
    MeasurementConfigMixin,
    AnnotationConfigMixin,
    CineConfigMixin,
    MetadataUIConfigMixin,
    TagExportConfigMixin,
    CustomizationsConfigMixin,
    AppConfigMixin,
):
    """
    Manages application configuration and user preferences.

    Acts as a thin facade over twelve feature-domain mixin classes, each of
    which owns the getter/setter methods for one area of settings.  All
    callers continue to use ``config_manager.get_roi_font_size()`` etc.
    without any changes.

    Core responsibilities (retained here):
        - Determine the platform-specific config file path.
        - Load configuration from JSON on startup, merging with defaults.
        - Persist configuration to JSON via ``save_config()``.
        - Provide generic ``get`` / ``set`` accessors for ad-hoc keys.

    Feature-domain mixins (in ``src/utils/config/``):
        PathsConfigMixin        – last path, export path, recent files
        DisplayConfigMixin      – theme, smoothing, privacy view, scroll mode
        OverlayConfigMixin      – overlay mode, visibility, font, tags
        LayoutConfigMixin       – multi-window layout, view slot order
        ROIConfigMixin          – ROI font, line, default statistics
        MeasurementConfigMixin  – measurement font and line
        AnnotationConfigMixin   – text/arrow annotation appearance
        CineConfigMixin         – cine speed and loop defaults
        MetadataUIConfigMixin   – metadata panel column widths/order
        TagExportConfigMixin    – tag export presets (CRUD + file I/O)
        CustomizationsConfigMixin – bulk export/import of all visual settings
        AppConfigMixin          – disclaimer acceptance flag
    """

    def __init__(self, config_filename: str = "dicom_viewer_config.json"):
        """
        Initialise the configuration manager.

        Args:
            config_filename: Name of the configuration file to use
        """
        # Platform-specific config directory
        if os.name == "nt":  # Windows
            app_data = os.getenv("APPDATA", os.path.expanduser("~"))
            self.config_dir = Path(app_data) / "DICOMViewerV3"
        else:  # macOS / Linux
            self.config_dir = Path.home() / ".config" / "DICOMViewerV3"

        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_path = self.config_dir / config_filename

        # Default configuration values (all feature domains)
        self.default_config: Dict[str, Any] = {
            # Paths
            "last_path": "",
            "last_export_path": "",
            "recent_files": [],
            # Display
            "theme": "dark",
            "scroll_wheel_mode": "slice",
            "privacy_view_enabled": False,
            "smooth_image_when_zoomed": False,
            # Overlay
            "overlay_mode": "minimal",
            "overlay_visibility_state": 0,
            "overlay_custom_fields": [],
            "overlay_font_size": 10,
            "overlay_font_color_r": 255,
            "overlay_font_color_g": 255,
            "overlay_font_color_b": 0,
            "overlay_tags": {},
            # Layout
            "multi_window_layout": "1x1",
            "view_slot_order": [0, 1, 2, 3],
            # ROI
            "roi_font_size": 14,
            "roi_font_color_r": 255,
            "roi_font_color_g": 255,
            "roi_font_color_b": 0,
            "roi_line_thickness": 6,
            "roi_line_color_r": 255,
            "roi_line_color_g": 0,
            "roi_line_color_b": 0,
            "roi_default_visible_statistics": ["mean", "std", "min", "max", "count", "area"],
            # Measurement
            "measurement_font_size": 14,
            "measurement_font_color_r": 0,
            "measurement_font_color_g": 255,
            "measurement_font_color_b": 0,
            "measurement_line_thickness": 6,
            "measurement_line_color_r": 0,
            "measurement_line_color_g": 255,
            "measurement_line_color_b": 0,
            # Annotation
            "arrow_annotation_size": 6,
            # Cine
            "cine_default_speed": 1.0,
            "cine_default_loop": True,
            # Metadata panel
            "metadata_panel_column_widths": [100, 200, 50, 200],
            # Window geometry (accessed via generic get/set)
            "window_width": 1200,
            "window_height": 700,
            "window_level_default": None,
            "window_width_default": None,
            # App
            "disclaimer_accepted": False,
        }

        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """
        Load configuration from file, or return defaults if file doesn't exist.

        Returns:
            Dictionary containing configuration values
        """
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    loaded_config = json.load(f)
                    config = self.default_config.copy()
                    config.update(loaded_config)
                    return config
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load config file: {e}")
                return self.default_config.copy()
        return self.default_config.copy()

    def save_config(self) -> bool:
        """
        Save current configuration to file.

        Returns:
            True if save was successful, False otherwise
        """
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
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

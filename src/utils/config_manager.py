"""
Configuration Manager

Manages persistent storage and retrieval of user preferences and settings.
Settings are stored in a JSON file in the user's application data directory.

This module provides a thin ConfigManager facade that composes thirteen
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
import logging
import os
from os import PathLike
from pathlib import Path
from typing import Any

from utils.config.annotation_config import AnnotationConfigMixin
from utils.config.app_config import AppConfigMixin
from utils.config.cine_config import CineConfigMixin
from utils.config.customizations_config import CustomizationsConfigMixin
from utils.config.display_config import DisplayConfigMixin
from utils.config.layout_config import LayoutConfigMixin
from utils.config.measurement_config import MeasurementConfigMixin
from utils.config.metadata_ui_config import MetadataUIConfigMixin
from utils.config.overlay_config import OverlayConfigMixin
from utils.config.paths_config import PathsConfigMixin
from utils.config.privacy_storage_config import PrivacyStorageConfigMixin
from utils.config.qa_pylinac_config import QaPylinacConfigMixin
from utils.config.roi_config import ROIConfigMixin
from utils.config.slice_sync_config import SliceSyncConfigMixin
from utils.config.study_index_config import StudyIndexConfigMixin
from utils.config.tag_export_config import TagExportConfigMixin
from utils.privacy.safe_storage import (
    assert_safe_internal_path,
    atomic_write_private_text,
    ensure_private_directory,
    get_private_app_dir,
)

_logger = logging.getLogger(__name__)
_SOURCE_ROOT = Path(__file__).resolve().parent.parent.parent


def _is_windows() -> bool:
    return os.name == "nt"


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
    SliceSyncConfigMixin,
    QaPylinacConfigMixin,
    StudyIndexConfigMixin,
    PrivacyStorageConfigMixin,
):
    """
    Manages application configuration and user preferences.

    Acts as a thin facade over thirteen feature-domain mixin classes, each of
    which owns the getter/setter methods for one area of settings.  All
    callers continue to use ``config_manager.get_roi_font_size()`` etc.
    without any changes.

    Core responsibilities (retained here):
        - Determine the platform-specific config file path.
        - Load configuration from JSON on startup, merging with defaults.
        - Persist configuration to JSON via ``save_config()``.
        - Provide generic ``get`` / ``set`` accessors for ad-hoc keys.

        Feature-domain mixins (in ``src/utils/config/``):
        PathsConfigMixin        – last path, export path, pylinac QA output dir, recent files
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
        SliceSyncConfigMixin    – slice sync enabled flag and linked groups
        QaPylinacConfigMixin    – persisted pylinac QA options (e.g. MRI LC method/threshold/sanity)
        StudyIndexConfigMixin   – local encrypted study index DB path, auto-add on open
    """

    def __init__(
        self,
        config_filename: str = "dicom_viewer_config.json",
        config_dir: str | PathLike[str] | None = None,
        private_storage_dir: str | PathLike[str] | None = None,
    ):
        """
        Initialise the configuration manager.

        Args:
            config_filename: Name of the configuration file to use
            config_dir: Optional directory override for the config file location
            private_storage_dir: Optional protected internal-storage override
        """
        if config_dir is not None:
            self.config_dir = Path(config_dir)
        else:
            # Platform-specific config directory
            if _is_windows():  # Windows
                app_data = os.getenv("APPDATA", os.path.expanduser("~"))
                self.config_dir = Path(app_data) / "DICOMViewerV3"
            else:  # macOS / Linux
                self.config_dir = Path.home() / ".config" / "DICOMViewerV3"

        assert_safe_internal_path(self.config_dir, source_root=_SOURCE_ROOT)
        try:
            ensure_private_directory(self.config_dir)
        except OSError as exc:
            # Sandboxed/managed installations may deny chmod on an existing
            # platform-owned directory. Keep the app usable, but report only
            # the failure class and retry on every launch/save.
            self.config_dir.mkdir(parents=True, exist_ok=True)
            _logger.warning(
                "Application configuration permissions could not be tightened",
                extra={
                    "operation": "config.permissions",
                    "error_class": type(exc).__name__,
                },
            )
        self.config_path = self.config_dir / config_filename
        if private_storage_dir is not None:
            self.private_storage_dir = Path(private_storage_dir)
        elif config_dir is not None:
            # Explicit config roots are used by tests and portable/managed setups;
            # keep all internal state under that caller-owned root.
            self.private_storage_dir = self.config_dir / "private-storage"
        else:
            self.private_storage_dir = get_private_app_dir(
                "private-storage", create=False
            )
        self._loaded_config_keys: set[str] = set()

        # Default configuration values (all feature domains)
        self.default_config: dict[str, Any] = {
            # Paths
            "last_path": "",
            "last_export_path": "",
            "last_pylinac_output_path": "",
            "recent_files": [],
            # Display
            "theme": "dark",
            "accent": "steel-blue",
            "scroll_wheel_mode": "slice",
            "privacy_view_enabled": False,
            "smooth_image_when_zoomed": True,
            "show_instances_separately": False,
            "navigator_show_slice_frame_count": True,
            "slice_slider_placement": "bottom",
            "slice_slider_direction": "first_at_start",
            "histogram_use_projection_pixels": False,
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
            "roi_font_size": 12,
            "roi_font_color_r": 255,
            "roi_font_color_g": 255,
            "roi_font_color_b": 0,
            "roi_line_thickness": 3,
            "roi_line_color_r": 255,
            "roi_line_color_g": 0,
            "roi_line_color_b": 0,
            "roi_default_visible_statistics": ["mean", "std", "min", "max", "count", "area"],
            "roi_show_per_channel_statistics": True,
            # Measurement
            "measurement_font_size": 12,
            "measurement_font_color_r": 0,
            "measurement_font_color_g": 255,
            "measurement_font_color_b": 0,
            "measurement_line_thickness": 3,
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
            # {group bucket key: expanded}; empty means every group starts collapsed
            "metadata_panel_group_expanded": {},
            # Window geometry (accessed via generic get/set)
            "window_width": 1200,
            "window_height": 700,
            "window_level_default": None,
            "window_width_default": None,
            # App
            "disclaimer_accepted": False,
            # QA / pylinac (ACR MRI Large low-contrast detectability; see QaPylinacConfigMixin)
            "acr_mri_low_contrast_method": "Weber",
            "acr_mri_low_contrast_visibility_threshold": 0.001,
            "acr_mri_low_contrast_visibility_sanity_multiplier": 3.0,
            "acr_qa_vanilla_pylinac": False,
            # Slice sync
            "slice_sync_enabled": False,
            "slice_sync_groups": [],
            # Slice location lines
            "slice_location_lines_visible": False,
            "slice_location_lines_same_group_only": False,
            "slice_location_lines_focused_only": False,
            "slice_location_line_width_px": 1,
            "slice_sync_group_strip_height_px": 5,
            # MPR cache
            "mpr_cache_enabled": False,
            "mpr_cache_max_mb": 500,
            # Optional redacted diagnostics
            "diagnostics_enabled": False,
            # Local study index (SQLCipher; see core/study_index)
            "study_index_db_path": "",
            "study_index_auto_add_on_open": False,
            "study_index_auto_add_consent": None,
            "study_index_browser_column_order": [],
            "study_index_passphrase_warning_dismissed": False,
        }

        self.config = self._load_config()

    def _load_config(self) -> dict[str, Any]:
        """
        Load configuration from file, or return defaults if file doesn't exist.

        Returns:
            Dictionary containing configuration values
        """
        if self.config_path.exists():
            try:
                with open(self.config_path, encoding="utf-8") as f:
                    loaded_config = json.load(f)
                    if not isinstance(loaded_config, dict):
                        raise ValueError("configuration root must be an object")
                    self._loaded_config_keys = set(loaded_config)
                    config = self.default_config.copy()
                    config.update(loaded_config)
                    return config
            except (OSError, ValueError) as e:
                _logger.warning(
                    "Application configuration could not be loaded",
                    extra={"operation": "config.load", "error_class": type(e).__name__},
                )
                return self.default_config.copy()
        return self.default_config.copy()

    def save_config(self) -> bool:
        """
        Atomically save current configuration to file.

        Writes to a sibling .tmp file first, then renames it over the real
        config file with os.replace().  This prevents partial/empty writes
        from corrupting the config on crash or power-loss mid-save.

        Returns:
            True if save was successful, False otherwise
        """
        try:
            payload = json.dumps(self.config, indent=4, ensure_ascii=False)
            atomic_write_private_text(
                self.config_path,
                payload,
                source_root=_SOURCE_ROOT,
            )
            return True
        except (OSError, ValueError) as e:
            _logger.error(
                "Application configuration could not be saved",
                extra={"operation": "config.save", "error_class": type(e).__name__},
            )
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

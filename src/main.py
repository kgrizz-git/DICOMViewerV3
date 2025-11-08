"""
DICOM Viewer V2 - Main Application Entry Point

This module is the main entry point for the DICOM viewer application.
It initializes the application, creates the main window, and sets up
the application event loop.

Inputs:
    - Command line arguments (optional)
    
Outputs:
    - Running DICOM viewer application
    
Requirements:
    - PySide6 for application framework
    - All other application modules
"""

import sys
import os
from pathlib import Path

# Add src directory to path
src_dir = Path(__file__).parent
sys.path.insert(0, str(src_dir))

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt, QPointF, QObject
from PySide6.QtGui import QKeyEvent
from typing import Optional, Dict
import pydicom
from pydicom.dataset import Dataset

from gui.main_window import MainWindow
from gui.dialogs.file_dialog import FileDialog
from gui.dialogs.settings_dialog import SettingsDialog
from gui.dialogs.tag_viewer_dialog import TagViewerDialog
from gui.dialogs.overlay_config_dialog import OverlayConfigDialog
from gui.image_viewer import ImageViewer
from gui.metadata_panel import MetadataPanel
from gui.window_level_controls import WindowLevelControls
from gui.roi_statistics_panel import ROIStatisticsPanel
from gui.roi_list_panel import ROIListPanel
from gui.slice_navigator import SliceNavigator
from core.dicom_loader import DICOMLoader
from core.dicom_organizer import DICOMOrganizer
from core.dicom_parser import DICOMParser
from core.dicom_processor import DICOMProcessor
from utils.config_manager import ConfigManager
from tools.roi_manager import ROIManager
from tools.measurement_tool import MeasurementTool
from tools.histogram_widget import HistogramWidget
from gui.overlay_manager import OverlayManager


class DICOMViewerApp(QObject):
    """
    Main application class for DICOM Viewer.
    
    Coordinates all components and handles application logic.
    """
    
    def __init__(self):
        """Initialize the application."""
        # Initialize QObject first
        super().__init__()
        
        # Create Qt application first (before any widgets)
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("DICOM Viewer V2")
        
        # Initialize managers
        self.config_manager = ConfigManager()
        self.dicom_loader = DICOMLoader()
        self.dicom_organizer = DICOMOrganizer()
        self.dicom_processor = DICOMProcessor()
        
        # Create main window
        self.main_window = MainWindow(self.config_manager)
        
        # Install event filter on main window for key events
        self.main_window.installEventFilter(self)
        
        # Create components
        self.file_dialog = FileDialog(self.config_manager)
        self.image_viewer = ImageViewer()
        self.metadata_panel = MetadataPanel()
        self.window_level_controls = WindowLevelControls()
        self.slice_navigator = SliceNavigator()
        self.roi_manager = ROIManager()
        self.measurement_tool = MeasurementTool()
        self.roi_statistics_panel = ROIStatisticsPanel()
        self.roi_list_panel = ROIListPanel()
        self.roi_list_panel.set_roi_manager(self.roi_manager)
        
        # Initialize overlay manager with config settings
        font_size = self.config_manager.get_overlay_font_size()
        font_color = self.config_manager.get_overlay_font_color()
        self.overlay_manager = OverlayManager(
            font_size=font_size, 
            font_color=font_color,
            config_manager=self.config_manager
        )
        
        # Set scroll wheel mode
        scroll_mode = self.config_manager.get_scroll_wheel_mode()
        self.image_viewer.set_scroll_wheel_mode(scroll_mode)
        self.slice_navigator.set_scroll_wheel_mode(scroll_mode)
        
        # Set up UI layout
        self._setup_ui()
        
        # Connect signals
        self._connect_signals()
        
        # Current data
        self.current_datasets: list = []
        self.current_studies: dict = {}
        self.current_slice_index = 0
        self.current_series_uid = ""
        self.current_study_uid = ""
        self.current_dataset: Optional[Dataset] = None
        
        # Window/level state - preserve between slices
        self.current_window_center: Optional[float] = None
        self.current_window_width: Optional[float] = None
        self.window_level_user_modified = False  # Track if user has manually changed window/level
        
        # Initial view state for reset functionality
        self.initial_zoom: Optional[float] = None
        self.initial_h_scroll: Optional[int] = None
        self.initial_v_scroll: Optional[int] = None
        self.initial_window_center: Optional[float] = None
        self.initial_window_width: Optional[float] = None
        
        # Series defaults storage: key is series identifier (StudyInstanceUID + SeriesInstanceUID)
        # Value is dict with: window_center, window_width, zoom, h_scroll, v_scroll
        self.series_defaults: Dict[str, Dict] = {}
        
        # Track current series identifier for comparison
        self.current_series_identifier: Optional[str] = None
        
        # Tag viewer dialog (persistent)
        self.tag_viewer_dialog: Optional[TagViewerDialog] = None
        
        # Rescale state management
        self.use_rescaled_values: bool = False  # Default to False, will be set based on dataset
        self.rescale_slope: Optional[float] = None
        self.rescale_intercept: Optional[float] = None
        self.rescale_type: Optional[str] = None
    
    def _setup_ui(self) -> None:
        """Set up the user interface layout."""
        # Add image viewer to center panel
        center_layout = self.main_window.center_panel.layout()
        if center_layout is None:
            from PySide6.QtWidgets import QVBoxLayout
            center_layout = QVBoxLayout(self.main_window.center_panel)
        center_layout.addWidget(self.image_viewer)
        
        # Add metadata panel to left panel
        left_layout = self.main_window.left_panel.layout()
        if left_layout is None:
            from PySide6.QtWidgets import QVBoxLayout
            left_layout = QVBoxLayout(self.main_window.left_panel)
        left_layout.addWidget(self.metadata_panel)
        
        # Add controls to right panel
        right_layout = self.main_window.right_panel.layout()
        if right_layout is None:
            from PySide6.QtWidgets import QVBoxLayout
            right_layout = QVBoxLayout(self.main_window.right_panel)
        right_layout.addWidget(self.window_level_controls)
        right_layout.addWidget(self.roi_list_panel)
        right_layout.addWidget(self.roi_statistics_panel)
    
    def _connect_signals(self) -> None:
        """Connect signals between components."""
        # File operations
        self.main_window.open_file_requested.connect(self._open_files)
        self.main_window.open_folder_requested.connect(self._open_folder)
        self.main_window.open_recent_file_requested.connect(self._open_recent_file)
        
        # Settings
        self.main_window.settings_requested.connect(self._open_settings)
        
        # Tag viewer
        self.main_window.tag_viewer_requested.connect(self._open_tag_viewer)
        
        # Overlay configuration
        self.main_window.overlay_config_requested.connect(self._open_overlay_config)
        
        # ROI drawing signals
        self.image_viewer.roi_drawing_started.connect(self._on_roi_drawing_started)
        self.image_viewer.roi_drawing_updated.connect(self._on_roi_drawing_updated)
        self.image_viewer.roi_drawing_finished.connect(self._on_roi_drawing_finished)
        
        # Measurement signals
        self.image_viewer.measurement_started.connect(self._on_measurement_started)
        self.image_viewer.measurement_updated.connect(self._on_measurement_updated)
        self.image_viewer.measurement_finished.connect(self._on_measurement_finished)
        
        # ROI click signal
        self.image_viewer.roi_clicked.connect(self._on_roi_clicked)
        self.image_viewer.image_clicked_no_roi.connect(self._on_image_clicked_no_roi)
        
        # ROI delete signal (from right-click context menu)
        self.image_viewer.roi_delete_requested.connect(self._on_roi_delete_requested)
        self.image_viewer.measurement_delete_requested.connect(self._on_measurement_delete_requested)
        
        # ROI list panel signals
        self.roi_list_panel.roi_selected.connect(self._on_roi_selected)
        self.roi_list_panel.roi_deleted.connect(self._on_roi_deleted)
        
        # Monitor ROI item changes for movement
        self.image_viewer.scene.selectionChanged.connect(self._on_scene_selection_changed)
        
        # Scroll wheel for slice navigation
        self.image_viewer.wheel_event_for_slice.connect(
            lambda delta: self.slice_navigator.handle_wheel_event(delta)
        )
        
        # Window/level
        self.window_level_controls.window_changed.connect(self._on_window_changed)
        
        # Slice navigation
        self.slice_navigator.slice_changed.connect(self._on_slice_changed)
        
        # Mouse mode changes
        self.main_window.mouse_mode_changed.connect(self._on_mouse_mode_changed)
        
        # Scroll wheel mode changes
        self.main_window.scroll_wheel_mode_changed.connect(self._on_scroll_wheel_mode_changed)
        
        # Context menu changes (from image viewer)
        self.image_viewer.context_menu_mouse_mode_changed.connect(self._on_context_menu_mouse_mode_changed)
        self.image_viewer.context_menu_scroll_wheel_mode_changed.connect(self._on_context_menu_scroll_wheel_mode_changed)
        self.image_viewer.context_menu_rescale_toggle_changed.connect(self._on_rescale_toggle_changed)
        
        # Rescale toggle from toolbar
        self.main_window.rescale_toggle_changed.connect(self._on_rescale_toggle_changed)
        
        # Zoom changes - update overlay positions to keep text anchored
        self.image_viewer.zoom_changed.connect(self._on_zoom_changed)
        
        # Transform changes (zoom/pan) - update overlay positions to keep text anchored
        # This signal fires after transform is applied, ensuring accurate viewport-to-scene mapping
        self.image_viewer.transform_changed.connect(self._on_transform_changed)
        
        # Arrow key navigation from image viewer
        self.image_viewer.arrow_key_pressed.connect(self._on_arrow_key_pressed)
        
        # Right mouse drag for window/level adjustment
        self.image_viewer.right_mouse_press_for_drag.connect(self._on_right_mouse_press_for_drag)
        self.image_viewer.window_level_drag_changed.connect(self._on_window_level_drag_changed)
        
        # Series navigation
        self.image_viewer.series_navigation_requested.connect(self._on_series_navigation_requested)
        self.main_window.series_navigation_requested.connect(self._on_series_navigation_requested)
        
        # Overlay font size and color changes
        self.main_window.overlay_font_size_changed.connect(self._on_overlay_font_size_changed)
        self.main_window.overlay_font_color_changed.connect(self._on_overlay_font_color_changed)
        
        # Reset view request (from toolbar and context menu)
        self.main_window.reset_view_requested.connect(self._reset_view)
        self.image_viewer.reset_view_requested.connect(self._reset_view)
        
        # Clear measurements signals
        self.main_window.clear_measurements_requested.connect(self._on_clear_measurements_requested)
        self.image_viewer.clear_measurements_requested.connect(self._on_clear_measurements_requested)
        
        # Viewport resize (when splitter moves)
        self.main_window.viewport_resized.connect(self._on_viewport_resized)
        
        # Initialize pan mode to match toolbar state (Pan button is checked by default)
        self.image_viewer.set_mouse_mode("pan")
    
    def _open_files(self) -> None:
        """Handle open files request."""
        file_paths = self.file_dialog.open_files(self.main_window)
        if not file_paths:
            return
        
        # Clear all ROIs when opening new files
        self.roi_manager.clear_all_rois(self.image_viewer.scene)
        self.roi_list_panel.update_roi_list("", "", 0)  # Clear list
        self.roi_statistics_panel.clear_statistics()
        self.measurement_tool.clear_measurements(self.image_viewer.scene)
        
        # Add first file to recent files (representing this file selection)
        if file_paths:
            self.config_manager.add_recent_file(file_paths[0])
            self.main_window.update_recent_menu()
        
        try:
            # Load files
            datasets = self.dicom_loader.load_files(file_paths)
            
            if not datasets:
                self.file_dialog.show_error(
                    self.main_window,
                    "Error",
                    "No DICOM files could be loaded."
                )
                return
            
            # Show warnings for failed files
            failed = self.dicom_loader.get_failed_files()
            if failed:
                warning_msg = f"Warning: {len(failed)} file(s) could not be loaded:\n"
                for path, error in failed[:5]:  # Show first 5
                    warning_msg += f"\n{os.path.basename(path)}: {error}"
                if len(failed) > 5:
                    warning_msg += f"\n... and {len(failed) - 5} more"
                
                self.file_dialog.show_warning(self.main_window, "Loading Warnings", warning_msg)
            
            # Organize into studies/series
            self.current_datasets = datasets
            self.current_studies = self.dicom_organizer.organize(datasets, file_paths)
            
            # Display first slice
            self._load_first_slice()
            
            self.main_window.update_status(f"Loaded {len(datasets)} DICOM file(s)")
        
        except Exception as e:
            self.file_dialog.show_error(
                self.main_window,
                "Error",
                f"Error loading files: {str(e)}"
            )
    
    def _open_folder(self) -> None:
        """Handle open folder request."""
        folder_path = self.file_dialog.open_folder(self.main_window)
        if not folder_path:
            return
        
        # Clear all ROIs when opening new folder
        self.roi_manager.clear_all_rois(self.image_viewer.scene)
        self.roi_list_panel.update_roi_list("", "", 0)  # Clear list
        self.roi_statistics_panel.clear_statistics()
        
        # Add folder to recent files
        self.config_manager.add_recent_file(folder_path)
        self.main_window.update_recent_menu()
        
        try:
            # Load folder (recursive)
            datasets = self.dicom_loader.load_directory(folder_path, recursive=True)
            
            if not datasets:
                self.file_dialog.show_error(
                    self.main_window,
                    "Error",
                    "No DICOM files found in folder."
                )
                return
            
            # Show warnings
            failed = self.dicom_loader.get_failed_files()
            if failed:
                warning_msg = f"Warning: {len(failed)} file(s) could not be loaded."
                self.file_dialog.show_warning(self.main_window, "Loading Warnings", warning_msg)
            
            # Organize
            self.current_datasets = datasets
            self.current_studies = self.dicom_organizer.organize(datasets)
            
            # Display first slice
            self._load_first_slice()
            
            self.main_window.update_status(f"Loaded {len(datasets)} DICOM file(s) from folder")
        
        except Exception as e:
            self.file_dialog.show_error(
                self.main_window,
                "Error",
                f"Error loading folder: {str(e)}"
            )
    
    def _open_recent_file(self, file_path: str) -> None:
        """
        Handle open recent file/folder request.
        
        Args:
            file_path: Path to file or folder to open
        """
        import os.path
        
        # Clear all ROIs when opening new file/folder
        self.roi_manager.clear_all_rois(self.image_viewer.scene)
        self.roi_list_panel.update_roi_list("", "", 0)  # Clear list
        self.roi_statistics_panel.clear_statistics()
        
        # Check if path exists
        if not os.path.exists(file_path):
            self.file_dialog.show_error(
                self.main_window,
                "Error",
                f"File or folder not found:\n{file_path}"
            )
            # Remove from recent files if it doesn't exist
            recent_files = self.config_manager.get_recent_files()
            if file_path in recent_files:
                recent_files.remove(file_path)
                self.config_manager.config["recent_files"] = recent_files
                self.config_manager.save_config()
                self.main_window.update_recent_menu()
            return
        
        # Determine if it's a file or folder
        if os.path.isfile(file_path):
            # Open as file
            try:
                datasets = self.dicom_loader.load_files([file_path])
                
                if not datasets:
                    self.file_dialog.show_error(
                        self.main_window,
                        "Error",
                        "No DICOM files could be loaded."
                    )
                    return
                
                # Organize into studies/series
                self.current_datasets = datasets
                self.current_studies = self.dicom_organizer.organize(datasets, [file_path])
                
                # Display first slice
                self._load_first_slice()
                
                self.main_window.update_status(f"Loaded {len(datasets)} DICOM file(s)")
                
            except Exception as e:
                self.file_dialog.show_error(
                    self.main_window,
                    "Error",
                    f"Error loading file: {str(e)}"
                )
        else:
            # Open as folder
            try:
                datasets = self.dicom_loader.load_directory(file_path, recursive=True)
                
                if not datasets:
                    self.file_dialog.show_error(
                        self.main_window,
                        "Error",
                        "No DICOM files found in folder."
                    )
                    return
                
                # Organize
                self.current_datasets = datasets
                self.current_studies = self.dicom_organizer.organize(datasets)
                
                # Display first slice
                self._load_first_slice()
                
                self.main_window.update_status(f"Loaded {len(datasets)} DICOM file(s) from folder")
                
            except Exception as e:
                self.file_dialog.show_error(
                    self.main_window,
                    "Error",
                    f"Error loading folder: {str(e)}"
                )
    
    def _load_first_slice(self) -> None:
        """Load and display the first slice."""
        if not self.current_studies:
            return
        
        # Reset window/level state when loading new files
        self.current_window_center = None
        self.current_window_width = None
        self.window_level_user_modified = False
        
        # Reset series tracking
        self.current_series_identifier = None
        # Note: We keep series_defaults to preserve across file loads if desired
        # If you want to clear them, uncomment: self.series_defaults.clear()
        
        # Get first study
        study_uid = list(self.current_studies.keys())[0]
        
        # Get all series for this study and sort by SeriesNumber
        series_list = []
        for series_uid, datasets in self.current_studies[study_uid].items():
            if datasets:
                # Extract SeriesNumber from first dataset
                first_dataset = datasets[0]
                series_number = getattr(first_dataset, 'SeriesNumber', None)
                # Convert to int if possible, otherwise use 0 (or a large number to put at end)
                try:
                    series_num = int(series_number) if series_number is not None else 0
                except (ValueError, TypeError):
                    series_num = 0
                series_list.append((series_num, series_uid, datasets))
        
        # Sort by SeriesNumber (ascending)
        series_list.sort(key=lambda x: x[0])
        
        # Select series with lowest SeriesNumber (first in sorted list)
        if not series_list:
            return
        
        _, series_uid, datasets = series_list[0]
        
        if not datasets:
            return
        
        self.current_study_uid = study_uid
        self.current_series_uid = series_uid
        self.current_slice_index = 0
        
        # Set up slice navigator
        self.slice_navigator.set_total_slices(len(datasets))
        self.slice_navigator.set_current_slice(0)
        
        # Display slice
        self._display_slice(datasets[0])
    
    def _display_slice(self, dataset) -> None:
        """
        Display a DICOM slice.
        
        Args:
            dataset: pydicom Dataset
        """
        try:
            # Store current dataset
            self.current_dataset = dataset
            
            # Extract and store rescale parameters from dataset
            self.rescale_slope, self.rescale_intercept, self.rescale_type = self.dicom_processor.get_rescale_parameters(dataset)
            
            # Get series UID from dataset to check if we're in the same series
            new_series_uid = getattr(dataset, 'SeriesInstanceUID', '')
            is_same_series = (new_series_uid == self.current_series_uid and self.current_series_uid != "")
            
            # Detect if this is a new study/series
            is_new_study_series = self._is_new_study_or_series(dataset)
            series_identifier = self._get_series_identifier(dataset)
            
            # Set default use_rescaled_values based on whether parameters exist
            # Default to True if parameters exist, False otherwise
            if is_new_study_series:
                self.use_rescaled_values = (self.rescale_slope is not None and self.rescale_intercept is not None)
                # Update UI toggle state
                self.main_window.set_rescale_toggle_state(self.use_rescaled_values)
                self.image_viewer.set_rescale_toggle_state(self.use_rescaled_values)
                
                # Store the default rescale state immediately to ensure it's the initial default,
                # not a user-modified value (in case user toggles before _store_initial_view_state() is called)
                if series_identifier and series_identifier not in self.series_defaults:
                    self.series_defaults[series_identifier] = {
                        'use_rescaled_values': self.use_rescaled_values
                    }
                elif series_identifier and series_identifier in self.series_defaults:
                    # If series_defaults already exists, ensure use_rescaled_values is set to the default
                    # (don't overwrite if it was already stored, but set it if missing)
                    if 'use_rescaled_values' not in self.series_defaults[series_identifier]:
                        self.series_defaults[series_identifier]['use_rescaled_values'] = self.use_rescaled_values
            
            # If new study/series, check for stored defaults or calculate new ones
            stored_window_center = None
            stored_window_width = None
            stored_zoom = None
            stored_h_scroll = None
            stored_v_scroll = None
            
            if is_new_study_series:
                # Check if we have stored defaults for this series
                if series_identifier in self.series_defaults:
                    # Restore stored defaults
                    defaults = self.series_defaults[series_identifier]
                    stored_zoom = defaults.get('zoom')
                    stored_h_scroll = defaults.get('h_scroll')
                    stored_v_scroll = defaults.get('v_scroll')
                    stored_window_center = defaults.get('window_center')
                    stored_window_width = defaults.get('window_width')
                    
                    # Reset window/level state
                    self.window_level_user_modified = False
                else:
                    # New series - need to calculate defaults
                    # Get all datasets for this series to calculate pixel range
                    study_uid = getattr(dataset, 'StudyInstanceUID', '')
                    if study_uid and new_series_uid and self.current_studies:
                        if study_uid in self.current_studies and new_series_uid in self.current_studies[study_uid]:
                            series_datasets = self.current_studies[study_uid][new_series_uid]
                            
                            # Calculate pixel range for entire series
                            series_pixel_min, series_pixel_max = self.dicom_processor.get_series_pixel_value_range(
                                series_datasets, apply_rescale=self.use_rescaled_values
                            )
                            
                            # Check for window/level in DICOM metadata (use first dataset)
                            wc, ww, _ = self.dicom_processor.get_window_level_from_dataset(
                                dataset,
                                rescale_slope=self.rescale_slope,
                                rescale_intercept=self.rescale_intercept
                            )
                            
                            if wc is not None and ww is not None:
                                # Use DICOM metadata window/level
                                stored_window_center = wc
                                stored_window_width = ww
                            elif series_pixel_min is not None and series_pixel_max is not None:
                                # Calculate from series pixel range
                                stored_window_center = (series_pixel_min + series_pixel_max) / 2.0
                                stored_window_width = series_pixel_max - series_pixel_min
                                if stored_window_width <= 0:
                                    stored_window_width = 1.0
                            else:
                                # Fallback to single slice
                                pixel_min, pixel_max = self.dicom_processor.get_pixel_value_range(
                                    dataset, apply_rescale=self.use_rescaled_values
                                )
                                if pixel_min is not None and pixel_max is not None:
                                    stored_window_center = (pixel_min + pixel_max) / 2.0
                                    stored_window_width = pixel_max - pixel_min
                                    if stored_window_width <= 0:
                                        stored_window_width = 1.0
                            
                            # Reset window/level state
                            self.window_level_user_modified = False
                
                # Update current series identifier
                self.current_series_identifier = series_identifier
            
            # Convert to image
            # If same series and we have preserved window/level values, use them
            if is_same_series and self.current_window_center is not None and self.current_window_width is not None:
                image = self.dicom_processor.dataset_to_image(
                    dataset,
                    window_center=self.current_window_center,
                    window_width=self.current_window_width,
                    apply_rescale=self.use_rescaled_values
                )
            else:
                image = self.dicom_processor.dataset_to_image(
                    dataset,
                    apply_rescale=self.use_rescaled_values
                )
            if image is None:
                return
            
            # Set image in viewer - preserve zoom/pan if same series
            self.image_viewer.set_image(image, preserve_view=is_same_series and not is_new_study_series)
            
            # If new study/series, fit to view and center
            if is_new_study_series:
                self.image_viewer.fit_to_view()
                # Center image
                self.image_viewer._update_scrollbar_ranges(center_image=True)
                # Store zoom after fit_to_view
                stored_zoom = self.image_viewer.current_zoom
                stored_h_scroll = self.image_viewer.horizontalScrollBar().value()
                stored_v_scroll = self.image_viewer.verticalScrollBar().value()
            
            # Update current series UID
            if new_series_uid:
                self.current_series_uid = new_series_uid
            
            # Update metadata panel
            self.metadata_panel.set_dataset(dataset)
            
            # Update tag viewer if open
            if self.tag_viewer_dialog is not None and self.tag_viewer_dialog.isVisible():
                self.tag_viewer_dialog.set_dataset(dataset)
            
            # Calculate pixel value range for window/level controls
            pixel_min, pixel_max = self.dicom_processor.get_pixel_value_range(
                dataset, apply_rescale=self.use_rescaled_values
            )
            if pixel_min is not None and pixel_max is not None:
                # Set ranges based on actual pixel values (no margins)
                center_range = (pixel_min, pixel_max)
                # Width range from 1 to the pixel range (not 2x)
                width_range = (1.0, max(1.0, pixel_max - pixel_min))
                self.window_level_controls.set_ranges(center_range, width_range)
            
            # Update window/level controls unit label
            unit = self.rescale_type if (self.use_rescaled_values and self.rescale_type) else None
            self.window_level_controls.set_unit(unit)
            
            # Update window/level controls
            if is_new_study_series and stored_window_center is not None and stored_window_width is not None:
                # New series - use stored defaults
                self.window_level_controls.set_window_level(
                    stored_window_center, stored_window_width, block_signals=True, unit=unit
                )
                self.current_window_center = stored_window_center
                self.current_window_width = stored_window_width
                self.window_level_user_modified = False  # Reset flag for new series
                # Store defaults for this series
                self.series_defaults[series_identifier] = {
                    'window_center': stored_window_center,
                    'window_width': stored_window_width,
                    'zoom': stored_zoom,
                    'h_scroll': stored_h_scroll,
                    'v_scroll': stored_v_scroll
                }
            elif is_same_series and self.current_window_center is not None and self.current_window_width is not None:
                # Same series - preserve existing window/level values (whether user-modified or not)
                # Update UI controls to reflect the preserved values
                self.window_level_controls.set_window_level(
                    self.current_window_center, self.current_window_width, block_signals=True, unit=unit
                )
                # Do NOT reset window_level_user_modified flag - preserve it
            else:
                # First time displaying or no existing values - use values from dataset or calculate defaults
                wc, ww, is_rescaled = self.dicom_processor.get_window_level_from_dataset(
                    dataset,
                    rescale_slope=self.rescale_slope,
                    rescale_intercept=self.rescale_intercept
                )
                if wc is not None and ww is not None:
                    # If default window/level is in rescaled units but we're using raw values, convert
                    if is_rescaled and not self.use_rescaled_values:
                        if (self.rescale_slope is not None and self.rescale_intercept is not None and 
                            self.rescale_slope != 0.0):
                            wc, ww = self.dicom_processor.convert_window_level_rescaled_to_raw(
                                wc, ww, self.rescale_slope, self.rescale_intercept
                            )
                    # If default window/level is in raw units but we're using rescaled values, convert
                    elif not is_rescaled and self.use_rescaled_values:
                        if (self.rescale_slope is not None and self.rescale_intercept is not None):
                            wc, ww = self.dicom_processor.convert_window_level_raw_to_rescaled(
                                wc, ww, self.rescale_slope, self.rescale_intercept
                            )
                    
                    self.window_level_controls.set_window_level(wc, ww, block_signals=True, unit=unit)
                    self.current_window_center = wc
                    self.current_window_width = ww
                elif pixel_min is not None and pixel_max is not None:
                    # Use default window/level based on pixel range
                    default_center = (pixel_min + pixel_max) / 2.0
                    default_width = pixel_max - pixel_min
                    if default_width <= 0:
                        default_width = 1.0
                    self.window_level_controls.set_window_level(default_center, default_width, block_signals=True, unit=unit)
                    self.current_window_center = default_center
                    self.current_window_width = default_width
                
                # Store defaults if this is a new series
                if is_new_study_series and stored_zoom is not None:
                    self.series_defaults[series_identifier] = {
                        'window_center': self.current_window_center,
                        'window_width': self.current_window_width,
                        'zoom': stored_zoom,
                        'h_scroll': stored_h_scroll,
                        'v_scroll': stored_v_scroll
                    }
                
                self.window_level_user_modified = False  # Reset flag after setting from dataset
            
            # Store initial view state if this is the first image
            if self.initial_zoom is None:
                # Wait a bit for view to settle, then store initial state
                from PySide6.QtCore import QTimer
                QTimer.singleShot(100, self._store_initial_view_state)
            
            # Update overlay
            parser = DICOMParser(dataset)
            # Get total slice count for current series
            total_slices = 0
            if self.current_studies and self.current_study_uid and self.current_series_uid:
                if (self.current_study_uid in self.current_studies and 
                    self.current_series_uid in self.current_studies[self.current_study_uid]):
                    total_slices = len(self.current_studies[self.current_study_uid][self.current_series_uid])
            self.overlay_manager.create_overlay_items(
                self.image_viewer.scene,
                parser,
                total_slices=total_slices if total_slices > 0 else None
            )
            
            # Extract pixel spacing and set on measurement tool
            from utils.dicom_utils import get_pixel_spacing
            pixel_spacing = get_pixel_spacing(dataset)
            self.measurement_tool.set_pixel_spacing(pixel_spacing)
            
            # Set current slice context for measurements
            study_uid = getattr(dataset, 'StudyInstanceUID', '')
            series_uid = getattr(dataset, 'SeriesInstanceUID', '')
            instance_number = getattr(dataset, 'InstanceNumber', None)
            if instance_number is None:
                instance_identifier = self.current_slice_index
            else:
                instance_identifier = int(instance_number)
            self.measurement_tool.set_current_slice(study_uid, series_uid, instance_identifier)
            
            # Clear measurements when switching to new series (not when switching slices)
            if is_new_study_series:
                self.measurement_tool.clear_measurements(self.image_viewer.scene)
            
            # Display ROIs for current slice
            self._display_rois_for_slice(dataset)
            
            # Display measurements for current slice
            self._display_measurements_for_slice(dataset)
        
        except Exception as e:
            self.main_window.update_status(f"Error displaying slice: {str(e)}")
    
    def _get_series_identifier(self, dataset: Dataset) -> str:
        """
        Get a unique identifier for a study/series combination.
        Uses StudyInstanceUID and SeriesInstanceUID.
        
        Args:
            dataset: pydicom Dataset
            
        Returns:
            Series identifier string
        """
        study_uid = getattr(dataset, 'StudyInstanceUID', '')
        series_uid = getattr(dataset, 'SeriesInstanceUID', '')
        return f"{study_uid}_{series_uid}"
    
    def _is_new_study_or_series(self, dataset: Dataset) -> bool:
        """
        Detect if this is a new study or series by comparing DICOM tags.
        
        Compares:
        - Study Date (0008,0020)
        - Modality (0008,0060)
        - Series Number (0020,0011)
        - Series Description (0008,103E)
        - Study Time (0008,0030)
        - Series Time (0008,0031)
        
        Args:
            dataset: pydicom Dataset
            
        Returns:
            True if this is a new study/series, False otherwise
        """
        if self.current_series_identifier is None:
            return True
        
        # Get current series identifier
        new_series_identifier = self._get_series_identifier(dataset)
        
        # If series identifier changed, it's a new study/series
        if new_series_identifier != self.current_series_identifier:
            return True
        
        return False
    
    def _store_initial_view_state(self) -> None:
        """
        Store the initial view state (zoom, pan, window/level) for reset functionality.
        Stores per-series defaults in addition to global initial values.
        
        Called after the first image is displayed and the view has settled.
        """
        if self.image_viewer.image_item is None:
            return
        
        # Store initial zoom (global fallback)
        if self.initial_zoom is None:
            self.initial_zoom = self.image_viewer.current_zoom
        
        # Store initial pan position (scrollbar values) - global fallback
        if self.initial_h_scroll is None:
            self.initial_h_scroll = self.image_viewer.horizontalScrollBar().value()
        if self.initial_v_scroll is None:
            self.initial_v_scroll = self.image_viewer.verticalScrollBar().value()
        
        # Store initial window/level (global fallback)
        if self.initial_window_center is None:
            self.initial_window_center = self.current_window_center
        if self.initial_window_width is None:
            self.initial_window_width = self.current_window_width
        
        # Store per-series defaults if we have a current series identifier
        if self.current_series_identifier:
            if self.current_series_identifier not in self.series_defaults:
                # Create new entry with all defaults
                self.series_defaults[self.current_series_identifier] = {
                    'window_center': self.current_window_center,
                    'window_width': self.current_window_width,
                    'zoom': self.image_viewer.current_zoom,
                    'h_scroll': self.image_viewer.horizontalScrollBar().value(),
                    'v_scroll': self.image_viewer.verticalScrollBar().value(),
                    'use_rescaled_values': self.use_rescaled_values
                }
            else:
                # Entry already exists (use_rescaled_values was stored earlier),
                # just update the other fields without overwriting use_rescaled_values
                defaults = self.series_defaults[self.current_series_identifier]
                defaults['window_center'] = self.current_window_center
                defaults['window_width'] = self.current_window_width
                defaults['zoom'] = self.image_viewer.current_zoom
                defaults['h_scroll'] = self.image_viewer.horizontalScrollBar().value()
                defaults['v_scroll'] = self.image_viewer.verticalScrollBar().value()
                # Don't overwrite use_rescaled_values - it was already set to the initial default
    
    def _reset_view(self) -> None:
        """
        Reset view to initial state (zoom, pan, window center/level).
        
        Uses series-specific defaults if available, otherwise falls back to global initial values.
        """
        if self.current_dataset is None:
            # No current dataset
            return
        
        # Get series identifier
        series_identifier = self._get_series_identifier(self.current_dataset)
        
        # Try to get series-specific defaults
        if series_identifier in self.series_defaults:
            defaults = self.series_defaults[series_identifier]
            reset_zoom = defaults.get('zoom')
            reset_h_scroll = defaults.get('h_scroll')
            reset_v_scroll = defaults.get('v_scroll')
            reset_window_center = defaults.get('window_center')
            reset_window_width = defaults.get('window_width')
            reset_use_rescaled_values = defaults.get('use_rescaled_values')
        else:
            # Fall back to global initial values
            reset_zoom = self.initial_zoom
            reset_h_scroll = self.initial_h_scroll
            reset_v_scroll = self.initial_v_scroll
            reset_window_center = self.initial_window_center
            reset_window_width = self.initial_window_width
            reset_use_rescaled_values = None
        
        # Ensure we have a valid rescale state value - calculate default if missing
        if reset_use_rescaled_values is None:
            # Default to True if rescale parameters exist, False otherwise
            reset_use_rescaled_values = (self.rescale_slope is not None and self.rescale_intercept is not None)
        
        if reset_zoom is None:
            # No reset values available
            return
        
        # Reset rescale state to default FIRST (before window/level to avoid incorrect conversion)
        # Always restore rescale state, even if it's the same as current
        # Restore rescale state directly without converting window/level values
        # (the stored window/level values are already in the correct units for the restored state)
        self.use_rescaled_values = reset_use_rescaled_values
        # Update UI toggle states
        self.main_window.set_rescale_toggle_state(reset_use_rescaled_values)
        self.image_viewer.set_rescale_toggle_state(reset_use_rescaled_values)
        
        # Recalculate pixel value ranges for window/level controls
        if self.current_dataset is not None:
            pixel_min, pixel_max = self.dicom_processor.get_pixel_value_range(
                self.current_dataset, apply_rescale=self.use_rescaled_values
            )
            if pixel_min is not None and pixel_max is not None:
                center_range = (pixel_min, pixel_max)
                width_range = (1.0, max(1.0, pixel_max - pixel_min))
                self.window_level_controls.set_ranges(center_range, width_range)
            
            # Update window/level unit labels
            unit = self.rescale_type if (self.use_rescaled_values and self.rescale_type) else None
            self.window_level_controls.set_unit(unit)
        
        # Reset window/level to initial values (already in correct units for current rescale state)
        if reset_window_center is not None and reset_window_width is not None:
            # Get unit for window/level display
            unit = self.rescale_type if (self.use_rescaled_values and self.rescale_type) else None
            self.window_level_controls.set_window_level(
                reset_window_center, 
                reset_window_width, 
                block_signals=True,
                unit=unit
            )
            self.current_window_center = reset_window_center
            self.current_window_width = reset_window_width
            self.window_level_user_modified = False
        
        # Re-display current slice with reset window/level and rescale state
        if self.current_studies and self.current_series_uid:
            datasets = self.current_studies[self.current_study_uid][self.current_series_uid]
            if self.current_slice_index < len(datasets):
                dataset = datasets[self.current_slice_index]
                # Use current window/level values (which have been reset)
                image = self.dicom_processor.dataset_to_image(
                    dataset,
                    window_center=self.current_window_center,
                    window_width=self.current_window_width,
                    apply_rescale=self.use_rescaled_values
                )
                if image:
                    # Set image first (without preserving view to avoid wrong centering)
                    self.image_viewer.set_image(image, preserve_view=False)
                    
                    # Now set up the view: zoom, transform, and scrollbar positions
                    # Reset zoom and pan
                    self.image_viewer.resetTransform()
                    self.image_viewer.scale(reset_zoom, reset_zoom)
                    self.image_viewer.current_zoom = reset_zoom
                    
                    # Update scrollbar ranges synchronously
                    self.image_viewer._update_scrollbar_ranges()
                    
                    # Set scrollbar positions synchronously
                    if reset_h_scroll is not None and reset_v_scroll is not None:
                        self.image_viewer.horizontalScrollBar().setValue(reset_h_scroll)
                        self.image_viewer.verticalScrollBar().setValue(reset_v_scroll)
                    
                    self.image_viewer.last_transform = self.image_viewer.transform()
                    self.image_viewer.zoom_changed.emit(self.image_viewer.current_zoom)
                    
                    # Recreate overlay
                    parser = DICOMParser(dataset)
                    # Get total slice count
                    total_slices = len(datasets) if datasets else 0
                    self.overlay_manager.create_overlay_items(
                        self.image_viewer.scene,
                        parser,
                        total_slices=total_slices if total_slices > 0 else None
                    )
                    # Re-display ROIs for current slice
                    self._display_rois_for_slice(dataset)
    
    def _display_rois_for_slice(self, dataset) -> None:
        """
        Display ROIs for a slice.
        
        Ensures all ROIs for the current slice are visible in the scene.
        
        Args:
            dataset: pydicom Dataset for the current slice
        """
        # Extract DICOM identifiers
        study_uid = getattr(dataset, 'StudyInstanceUID', '')
        series_uid = getattr(dataset, 'SeriesInstanceUID', '')
        # Try to get InstanceNumber from DICOM, fall back to slice_index
        instance_number = getattr(dataset, 'InstanceNumber', None)
        if instance_number is None:
            instance_identifier = self.current_slice_index
        else:
            instance_identifier = int(instance_number)
        
        # Get all ROIs for this slice using composite key
        rois = self.roi_manager.get_rois_for_slice(study_uid, series_uid, instance_identifier)
        
        # Remove ROIs from other slices from the scene
        # (but keep them in the manager's storage)
        current_scene_items = list(self.image_viewer.scene.items())
        for item in current_scene_items:
            # Check if this item is an ROI
            roi = self.roi_manager.find_roi_by_item(item)
            if roi is not None:
                # Check if this ROI belongs to current slice
                roi_belongs_to_current = False
                for key, roi_list in self.roi_manager.rois.items():
                    if roi in roi_list:
                        # Check if this key matches current slice
                        if key == (study_uid, series_uid, instance_identifier):
                            roi_belongs_to_current = True
                        break
                # Remove ROI if it's from a different slice
                if not roi_belongs_to_current:
                    # Only remove if item actually belongs to this scene
                    if item.scene() == self.image_viewer.scene:
                        self.image_viewer.scene.removeItem(item)
        
        # Add ROIs for current slice to scene if not already there
        # Force refresh to ensure visibility after image changes
        for roi in rois:
            if roi.item.scene() == self.image_viewer.scene:
                # Already in scene, but ensure it's visible and has correct Z-value
                roi.item.setZValue(100)  # Above image but below overlay
                roi.item.show()  # Ensure visible
            else:
                # Not in scene, add it
                self.image_viewer.scene.addItem(roi.item)
                # Ensure ROI is visible (set appropriate Z-value)
                roi.item.setZValue(100)  # Above image but below overlay
        
        # Check if there's a selected ROI for this slice and restore UI state
        selected_roi = self.roi_manager.get_selected_roi()
        if selected_roi is not None and selected_roi in rois:
            # Selected ROI belongs to current slice - restore UI state
            self.roi_list_panel.select_roi_in_list(selected_roi)
            self._update_roi_statistics(selected_roi)
        else:
            # No selected ROI for this slice - clear statistics
            self.roi_statistics_panel.clear_statistics()
    
    def _display_measurements_for_slice(self, dataset) -> None:
        """
        Display measurements for a slice.
        
        Ensures all measurements for the current slice are visible in the scene.
        Removes measurements from other slices before displaying current slice measurements.
        
        Args:
            dataset: pydicom Dataset for the current slice
        """
        # Extract DICOM identifiers
        study_uid = getattr(dataset, 'StudyInstanceUID', '')
        series_uid = getattr(dataset, 'SeriesInstanceUID', '')
        # Try to get InstanceNumber from DICOM, fall back to slice_index
        instance_number = getattr(dataset, 'InstanceNumber', None)
        if instance_number is None:
            instance_identifier = self.current_slice_index
        else:
            instance_identifier = int(instance_number)
        
        # Clear measurements from other slices first
        self.measurement_tool.clear_measurements_from_other_slices(
            study_uid, series_uid, instance_identifier, self.image_viewer.scene
        )
        
        # Display measurements for this slice
        self.measurement_tool.display_measurements_for_slice(
            study_uid, series_uid, instance_identifier, self.image_viewer.scene
        )
    
    def _open_settings(self) -> None:
        """Handle settings dialog request."""
        dialog = SettingsDialog(self.config_manager, self.main_window)
        dialog.settings_applied.connect(self._on_settings_applied)
        dialog.exec()
    
    def _open_tag_viewer(self) -> None:
        """Handle tag viewer dialog request."""
        if self.tag_viewer_dialog is None:
            self.tag_viewer_dialog = TagViewerDialog(self.main_window)
        
        # Update with current dataset if available
        if self.current_dataset is not None:
            self.tag_viewer_dialog.set_dataset(self.current_dataset)
        
        # Show dialog (brings to front if already open)
        self.tag_viewer_dialog.show()
        self.tag_viewer_dialog.raise_()
        self.tag_viewer_dialog.activateWindow()
    
    def _open_overlay_config(self) -> None:
        """Handle overlay configuration dialog request."""
        dialog = OverlayConfigDialog(self.config_manager, self.main_window)
        dialog.config_applied.connect(self._on_overlay_config_applied)
        dialog.exec()
    
    def _on_overlay_config_applied(self) -> None:
        """Handle overlay configuration being applied."""
        # Recreate overlay if we have a current dataset
        if self.current_studies and self.current_series_uid:
            datasets = self.current_studies[self.current_study_uid][self.current_series_uid]
            if self.current_slice_index < len(datasets):
                dataset = datasets[self.current_slice_index]
                parser = DICOMParser(dataset)
                total_slices = len(datasets)
                self.overlay_manager.create_overlay_items(
                    self.image_viewer.scene,
                    parser,
                    total_slices=total_slices if total_slices > 0 else None
                )
    
    def _on_settings_applied(self) -> None:
        """Handle settings being applied."""
        # Update overlay manager with new settings
        font_size = self.config_manager.get_overlay_font_size()
        font_color = self.config_manager.get_overlay_font_color()
        self.overlay_manager.set_font_size(font_size)
        self.overlay_manager.set_font_color(*font_color)
        
        # Recreate overlay if we have a current dataset
        if self.current_studies and self.current_series_uid:
            datasets = self.current_studies[self.current_study_uid][self.current_series_uid]
            if self.current_slice_index < len(datasets):
                dataset = datasets[self.current_slice_index]
                parser = DICOMParser(dataset)
                total_slices = len(datasets)
                self.overlay_manager.create_overlay_items(
                    self.image_viewer.scene,
                    parser,
                    total_slices=total_slices if total_slices > 0 else None
                )
    
    def _on_window_changed(self, center: float, width: float) -> None:
        """
        Handle window/level change.
        
        Args:
            center: Window center
            width: Window width
        """
        # Store current window/level values
        self.current_window_center = center
        self.current_window_width = width
        self.window_level_user_modified = True  # Mark as user-modified
        
        # Re-display current slice with new window/level
        if self.current_studies and self.current_series_uid:
            datasets = self.current_studies[self.current_study_uid][self.current_series_uid]
            if self.current_slice_index < len(datasets):
                dataset = datasets[self.current_slice_index]
                image = self.dicom_processor.dataset_to_image(
                    dataset,
                    window_center=center,
                    window_width=width,
                    apply_rescale=self.use_rescaled_values
                )
                if image:
                    # Preserve view when window/level changes (same slice)
                    self.image_viewer.set_image(image, preserve_view=True)
                    # Recreate overlay to ensure it stays on top
                    parser = DICOMParser(dataset)
                    total_slices = len(datasets)
                    self.overlay_manager.create_overlay_items(
                        self.image_viewer.scene,
                        parser,
                        total_slices=total_slices if total_slices > 0 else None
                    )
    
    def _on_mouse_mode_changed(self, mode: str) -> None:
        """
        Handle mouse mode change from toolbar.
        
        Args:
            mode: Mouse mode ("select", "roi_ellipse", "roi_rectangle", "measure", "zoom", "pan", "auto_window_level")
        """
        self.image_viewer.set_mouse_mode(mode)
    
    def _set_roi_mode(self, mode: Optional[str]) -> None:
        """
        Set ROI drawing mode (legacy method for backward compatibility).
        
        Args:
            mode: "rectangle", "ellipse", or None
        """
        self.image_viewer.set_roi_drawing_mode(mode)
    
    def _on_roi_drawing_started(self, pos: QPointF) -> None:
        """
        Handle ROI drawing start.
        
        Args:
            pos: Starting position
        """
        if self.current_dataset is None:
            return
        
        # Extract DICOM identifiers
        study_uid = getattr(self.current_dataset, 'StudyInstanceUID', '')
        series_uid = getattr(self.current_dataset, 'SeriesInstanceUID', '')
        # Try to get InstanceNumber from DICOM, fall back to slice_index
        instance_number = getattr(self.current_dataset, 'InstanceNumber', None)
        if instance_number is None:
            instance_identifier = self.current_slice_index
        else:
            instance_identifier = int(instance_number)
        
        self.roi_manager.set_current_slice(study_uid, series_uid, instance_identifier)
        self.roi_manager.start_drawing(pos, self.image_viewer.roi_drawing_mode)
    
    def _on_roi_drawing_updated(self, pos: QPointF) -> None:
        """
        Handle ROI drawing update.
        
        Args:
            pos: Current position
        """
        self.roi_manager.update_drawing(pos, self.image_viewer.scene)
    
    def _on_roi_drawing_finished(self) -> None:
        """Handle ROI drawing finish."""
        roi_item = self.roi_manager.finish_drawing()
        
        # Extract DICOM identifiers for updating ROI list
        study_uid = ""
        series_uid = ""
        instance_identifier = self.current_slice_index
        if self.current_dataset is not None:
            study_uid = getattr(self.current_dataset, 'StudyInstanceUID', '')
            series_uid = getattr(self.current_dataset, 'SeriesInstanceUID', '')
            instance_number = getattr(self.current_dataset, 'InstanceNumber', None)
            if instance_number is not None:
                instance_identifier = int(instance_number)
        
        # Check if we're in auto_window_level mode
        if self.image_viewer.mouse_mode == "auto_window_level" and roi_item is not None:
            # Auto window/level mode - calculate window/level from ROI and delete ROI
            try:
                # roi_item is already the ROIItem we need (finish_drawing returns ROIItem directly)
                roi = roi_item
                if roi is not None and self.current_dataset is not None:
                    # Get pixel array
                    pixel_array = self.dicom_processor.get_pixel_array(self.current_dataset)
                    if pixel_array is not None:
                        # Extract pixel spacing for area calculation
                        from utils.dicom_utils import get_pixel_spacing
                        pixel_spacing = get_pixel_spacing(self.current_dataset)
                        
                        # Calculate statistics with rescale parameters if using rescaled values
                        rescale_slope = self.rescale_slope if self.use_rescaled_values else None
                        rescale_intercept = self.rescale_intercept if self.use_rescaled_values else None
                        stats = self.roi_manager.calculate_statistics(
                            roi, pixel_array,
                            rescale_slope=rescale_slope,
                            rescale_intercept=rescale_intercept,
                            pixel_spacing=pixel_spacing
                        )
                        if stats and "min" in stats and "max" in stats:
                            # Set window width = max - min
                            window_width = stats["max"] - stats["min"]
                            # Set window center = midpoint (halfway between min and max)
                            window_center = (stats["min"] + stats["max"]) / 2.0
                            
                            # Update window/level controls
                            self.window_level_controls.set_window_level(window_center, window_width)
                            
                            # Delete the ROI (it was only used for calculation)
                            self.roi_manager.delete_roi(roi, self.image_viewer.scene)
                            
                            # Clear statistics panel since ROI was deleted
                            self.roi_statistics_panel.clear_statistics()
                            
                            # Update ROI list panel
                            self.roi_list_panel.update_roi_list(study_uid, series_uid, instance_identifier)
                            
                            # Switch back to pan mode
                            self.image_viewer.set_mouse_mode("pan")
                            # Update toolbar button state
                            self.main_window.mouse_mode_pan_action.setChecked(True)
                            self.main_window.mouse_mode_auto_window_level_action.setChecked(False)
            except Exception as e:
                print(f"Error in auto window/level: {e}")
                import traceback
                traceback.print_exc()
                # If error occurs, still delete ROI and switch back to pan mode
                if roi_item is not None:
                    # roi_item is already the ROIItem we need
                    self.roi_manager.delete_roi(roi_item, self.image_viewer.scene)
                    # Clear statistics panel since ROI was deleted
                    self.roi_statistics_panel.clear_statistics()
                    self.roi_list_panel.update_roi_list(study_uid, series_uid, instance_identifier)
                self.image_viewer.set_mouse_mode("pan")
                self.main_window.mouse_mode_pan_action.setChecked(True)
                self.main_window.mouse_mode_auto_window_level_action.setChecked(False)
            return
        
        # Normal ROI drawing finish (not auto window/level)
        # Update ROI list
        self.roi_list_panel.update_roi_list(study_uid, series_uid, instance_identifier)
        
        # Auto-select the newly drawn ROI: highlight in list and show statistics
        if roi_item is not None:
            self.roi_list_panel.select_roi_in_list(roi_item)
            if self.current_dataset is not None:
                self._update_roi_statistics(roi_item)
    
    def _on_roi_clicked(self, item) -> None:
        """
        Handle ROI click.
        
        Args:
            item: QGraphicsItem that was clicked
        """
        roi = self.roi_manager.find_roi_by_item(item)
        if roi:
            self.roi_manager.select_roi(roi)
            self.roi_list_panel.select_roi_in_list(roi)
            self._update_roi_statistics(roi)
    
    def _on_image_clicked_no_roi(self) -> None:
        """Handle image click when not on an ROI - deselect current ROI."""
        # Deselect ROI
        self.roi_manager.select_roi(None)
        # Clear scene selection to prevent Qt's default mouse release behavior from re-selecting the ROI
        if self.image_viewer.scene is not None:
            self.image_viewer.scene.clearSelection()
        # Clear ROI list selection
        self.roi_list_panel.select_roi_in_list(None)
        # Clear ROI statistics panel
        self.roi_statistics_panel.clear_statistics()
    
    def _on_measurement_started(self, pos: QPointF) -> None:
        """
        Handle measurement start.
        
        Args:
            pos: Starting position
        """
        # Set current slice context before starting measurement
        if self.current_dataset is not None:
            study_uid = getattr(self.current_dataset, 'StudyInstanceUID', '')
            series_uid = getattr(self.current_dataset, 'SeriesInstanceUID', '')
            instance_number = getattr(self.current_dataset, 'InstanceNumber', None)
            if instance_number is None:
                instance_identifier = self.current_slice_index
            else:
                instance_identifier = int(instance_number)
            self.measurement_tool.set_current_slice(study_uid, series_uid, instance_identifier)
        
        self.measurement_tool.start_measurement(pos)
    
    def _on_measurement_updated(self, pos: QPointF) -> None:
        """
        Handle measurement update.
        
        Args:
            pos: Current position
        """
        if self.image_viewer.scene is not None:
            self.measurement_tool.update_measurement(pos, self.image_viewer.scene)
    
    def _on_measurement_finished(self) -> None:
        """Handle measurement finish."""
        if self.image_viewer.scene is not None:
            measurement = self.measurement_tool.finish_measurement(self.image_viewer.scene)
            if measurement is not None:
                # Measurement completed successfully
                pass
    
    def _on_measurement_delete_requested(self, measurement_item) -> None:
        """
        Handle measurement deletion request from context menu.
        
        Args:
            measurement_item: MeasurementItem to delete
        """
        if self.image_viewer.scene is not None:
            self.measurement_tool.delete_measurement(measurement_item, self.image_viewer.scene)
    
    def _on_clear_measurements_requested(self) -> None:
        """
        Handle clear measurements request from toolbar or context menu.
        
        Clears all measurements on the current slice only.
        """
        if self.image_viewer.scene is not None and self.current_dataset is not None:
            # Extract DICOM identifiers for current slice
            study_uid = getattr(self.current_dataset, 'StudyInstanceUID', '')
            series_uid = getattr(self.current_dataset, 'SeriesInstanceUID', '')
            instance_number = getattr(self.current_dataset, 'InstanceNumber', None)
            if instance_number is None:
                instance_identifier = self.current_slice_index
            else:
                instance_identifier = int(instance_number)
            
            # Clear measurements for current slice
            self.measurement_tool.clear_slice_measurements(
                study_uid, series_uid, instance_identifier, self.image_viewer.scene
            )
    
    def _on_roi_selected(self, roi) -> None:
        """
        Handle ROI selection from list.
        
        Args:
            roi: Selected ROI item
        """
        self._update_roi_statistics(roi)
    
    def _on_roi_delete_requested(self, item) -> None:
        """
        Handle ROI deletion request from context menu.
        
        Args:
            item: QGraphicsItem to delete
        """
        roi = self.roi_manager.find_roi_by_item(item)
        if roi:
            self.roi_manager.delete_roi(roi, self.image_viewer.scene)
            # Update ROI list panel - extract identifiers from current dataset
            if self.current_dataset is not None:
                study_uid = getattr(self.current_dataset, 'StudyInstanceUID', '')
                series_uid = getattr(self.current_dataset, 'SeriesInstanceUID', '')
                instance_number = getattr(self.current_dataset, 'InstanceNumber', None)
                if instance_number is None:
                    instance_identifier = self.current_slice_index
                else:
                    instance_identifier = int(instance_number)
                self.roi_list_panel.update_roi_list(study_uid, series_uid, instance_identifier)
            if self.roi_manager.get_selected_roi() is None:
                self.roi_statistics_panel.clear_statistics()
    
    def _on_roi_deleted(self, roi) -> None:
        """
        Handle ROI deletion.
        
        Args:
            roi: Deleted ROI item
        """
        # Clear statistics if this was the selected ROI
        if self.roi_manager.get_selected_roi() is None:
            self.roi_statistics_panel.clear_statistics()
    
    def _on_scroll_wheel_mode_changed(self, mode: str) -> None:
        """
        Handle scroll wheel mode change.
        
        Args:
            mode: "slice" or "zoom"
        """
        self.config_manager.set_scroll_wheel_mode(mode)
        self.image_viewer.set_scroll_wheel_mode(mode)
        self.slice_navigator.set_scroll_wheel_mode(mode)
    
    def _on_context_menu_mouse_mode_changed(self, mode: str) -> None:
        """
        Handle mouse mode change from context menu.
        Updates toolbar to reflect the change.
        
        Args:
            mode: Mouse mode string
        """
        # Call main_window's _on_mouse_mode_changed() directly to update toolbar buttons
        # This method will update toolbar button states and then emit the signal
        # which will trigger the normal flow (setting mouse mode in image_viewer)
        self.main_window._on_mouse_mode_changed(mode)
    
    def _on_context_menu_scroll_wheel_mode_changed(self, mode: str) -> None:
        """
        Handle scroll wheel mode change from context menu.
        Updates toolbar combo box to reflect the change.
        
        Args:
            mode: "slice" or "zoom"
        """
        # Update toolbar combo box
        if mode == "slice":
            self.main_window.scroll_wheel_mode_combo.setCurrentText("Slice")
        else:  # zoom
            self.main_window.scroll_wheel_mode_combo.setCurrentText("Zoom")
        
        # Emit the main_window signal to trigger normal flow
        self.main_window.scroll_wheel_mode_changed.emit(mode)
    
    def _on_rescale_toggle_changed(self, checked: bool) -> None:
        """
        Handle rescale toggle change from toolbar or context menu.
        
        Converts current window/level values to preserve image appearance when toggling.
        
        Args:
            checked: True to use rescaled values, False to use raw values
        """
        # Get current window/level values before updating state
        current_center = self.current_window_center
        current_width = self.current_window_width
        
        # Convert window/level values if we have rescale parameters
        if (current_center is not None and current_width is not None and
            self.rescale_slope is not None and self.rescale_intercept is not None and
            self.rescale_slope != 0.0):
            
            # Determine conversion direction
            if self.use_rescaled_values and not checked:
                # Toggling from rescaled to raw: convert rescaled -> raw
                current_center, current_width = self.dicom_processor.convert_window_level_rescaled_to_raw(
                    current_center, current_width, self.rescale_slope, self.rescale_intercept
                )
            elif not self.use_rescaled_values and checked:
                # Toggling from raw to rescaled: convert raw -> rescaled
                current_center, current_width = self.dicom_processor.convert_window_level_raw_to_rescaled(
                    current_center, current_width, self.rescale_slope, self.rescale_intercept
                )
        
        # Update state
        self.use_rescaled_values = checked
        
        # Update UI toggle states
        self.main_window.set_rescale_toggle_state(checked)
        self.image_viewer.set_rescale_toggle_state(checked)
        
        # Recalculate and update everything
        if self.current_dataset is not None:
            # Recalculate pixel value ranges
            pixel_min, pixel_max = self.dicom_processor.get_pixel_value_range(
                self.current_dataset, apply_rescale=self.use_rescaled_values
            )
            if pixel_min is not None and pixel_max is not None:
                center_range = (pixel_min, pixel_max)
                width_range = (1.0, max(1.0, pixel_max - pixel_min))
                self.window_level_controls.set_ranges(center_range, width_range)
            
            # Update window/level unit labels
            unit = self.rescale_type if (self.use_rescaled_values and self.rescale_type) else None
            self.window_level_controls.set_unit(unit)
            
            # Update window/level controls with converted values
            if current_center is not None and current_width is not None:
                self.current_window_center = current_center
                self.current_window_width = current_width
                self.window_level_controls.set_window_level(
                    current_center, current_width, block_signals=True, unit=unit
                )
            
            # Re-display current slice with new rescale setting
            if self.current_studies and self.current_series_uid:
                datasets = self.current_studies[self.current_study_uid][self.current_series_uid]
                if self.current_slice_index < len(datasets):
                    dataset = datasets[self.current_slice_index]
                    # Re-display with converted window/level and new rescale setting
                    if self.current_window_center is not None and self.current_window_width is not None:
                        image = self.dicom_processor.dataset_to_image(
                            dataset,
                            window_center=self.current_window_center,
                            window_width=self.current_window_width,
                            apply_rescale=self.use_rescaled_values
                        )
                    else:
                        image = self.dicom_processor.dataset_to_image(
                            dataset,
                            apply_rescale=self.use_rescaled_values
                        )
                    if image:
                        # Preserve view when toggling rescale
                        self.image_viewer.set_image(image, preserve_view=True)
                        # Recreate overlay
                        parser = DICOMParser(dataset)
                        total_slices = len(datasets)
                        self.overlay_manager.create_overlay_items(
                            self.image_viewer.scene,
                            parser,
                            total_slices=total_slices if total_slices > 0 else None
                        )
                        # Re-display ROIs for current slice
                        self._display_rois_for_slice(dataset)
            
            # Update ROI statistics if ROI is selected and belongs to current slice
            selected_roi = self.roi_manager.get_selected_roi()
            if selected_roi is not None and self.current_dataset is not None:
                # Verify the selected ROI belongs to the current slice
                study_uid = getattr(self.current_dataset, 'StudyInstanceUID', '')
                series_uid = getattr(self.current_dataset, 'SeriesInstanceUID', '')
                instance_number = getattr(self.current_dataset, 'InstanceNumber', None)
                if instance_number is None:
                    instance_identifier = self.current_slice_index
                else:
                    instance_identifier = int(instance_number)
                
                # Check if selected ROI belongs to current slice
                current_slice_rois = self.roi_manager.get_rois_for_slice(study_uid, series_uid, instance_identifier)
                if selected_roi in current_slice_rois:
                    self._update_roi_statistics(selected_roi)
                else:
                    # Selected ROI doesn't belong to current slice - clear statistics
                    self.roi_statistics_panel.clear_statistics()
            else:
                # No selected ROI - clear statistics
                self.roi_statistics_panel.clear_statistics()
    
    def _on_zoom_changed(self, zoom_level: float) -> None:
        """
        Handle zoom level change.
        
        Args:
            zoom_level: Current zoom level
        """
        # Note: Overlay position updates are handled by _on_transform_changed
        # which fires after the transform is fully applied
        pass
    
    def _on_transform_changed(self) -> None:
        """
        Handle view transform change (zoom/pan).
        
        Updates overlay positions to keep text anchored to viewport edges.
        This is called after the transform is fully applied.
        """
        # Update overlay positions when transform changes
        if self.current_dataset is not None:
            self.overlay_manager.update_overlay_positions(self.image_viewer.scene)
    
    def _on_viewport_resized(self) -> None:
        """
        Handle viewport resize (when splitter moves).
        
        Updates overlay positions to keep text anchored to viewport edges
        when the left or right panels are resized.
        """
        # Update overlay positions when viewport size changes
        if self.current_dataset is not None:
            self.overlay_manager.update_overlay_positions(self.image_viewer.scene)
    
    def _on_arrow_key_pressed(self, direction: int) -> None:
        """
        Handle arrow key press from image viewer.
        
        Args:
            direction: 1 for up (next slice), -1 for down (previous slice)
        """
        if direction == 1:
            # Up arrow: next slice
            self.slice_navigator.next_slice()
        elif direction == -1:
            # Down arrow: previous slice
            self.slice_navigator.previous_slice()
    
    def _on_right_mouse_press_for_drag(self) -> None:
        """
        Handle right mouse press for drag - provide window/level values to image viewer.
        """
        # Get current window/level values and ranges
        center, width = self.window_level_controls.get_window_level()
        center_range = self.window_level_controls.center_range
        width_range = self.window_level_controls.width_range
        
        # Set values in image viewer for drag tracking
        self.image_viewer.set_window_level_for_drag(center, width, center_range, width_range)
    
    def _on_window_level_drag_changed(self, center_delta: float, width_delta: float) -> None:
        """
        Handle window/level drag adjustment from image viewer.
        
        Args:
            center_delta: Change in window center (positive = up, negative = down)
            width_delta: Change in window width (positive = right/wider, negative = left/narrower)
        """
        # Get initial values from image_viewer (these are set when drag starts)
        if (self.image_viewer.right_mouse_drag_start_center is None or 
            self.image_viewer.right_mouse_drag_start_width is None):
            return  # Drag not properly initialized
        
        # Apply deltas to initial values
        new_center = self.image_viewer.right_mouse_drag_start_center + center_delta
        new_width = self.image_viewer.right_mouse_drag_start_width + width_delta
        
        # Clamp to valid ranges
        center_range = self.window_level_controls.center_range
        width_range = self.window_level_controls.width_range
        
        new_center = max(center_range[0], min(center_range[1], new_center))
        new_width = max(width_range[0], min(width_range[1], new_width))
        
        # Update window/level controls (block signals to prevent recursive updates during drag)
        self.window_level_controls.set_window_level(new_center, new_width, block_signals=True)
        
        # Manually trigger window change to update image
        self._on_window_changed(new_center, new_width)
    
    def _on_series_navigation_requested(self, direction: int) -> None:
        """
        Handle series navigation request from image viewer.
        
        Args:
            direction: -1 for left/previous series, 1 for right/next series
        """
        if not self.current_studies or not self.current_study_uid:
            return
        
        # Get all series for current study
        study_series = self.current_studies[self.current_study_uid]
        
        # Check if there are multiple series
        if len(study_series) <= 1:
            return  # No navigation needed if only one series
        
        # Build list of series with SeriesNumber for sorting
        series_list = []
        for series_uid, datasets in study_series.items():
            if datasets:
                # Extract SeriesNumber from first dataset
                first_dataset = datasets[0]
                series_number = getattr(first_dataset, 'SeriesNumber', None)
                # Convert to int if possible, otherwise use 0
                try:
                    series_num = int(series_number) if series_number is not None else 0
                except (ValueError, TypeError):
                    series_num = 0
                series_list.append((series_num, series_uid, datasets))
        
        # Sort by SeriesNumber (ascending)
        series_list.sort(key=lambda x: x[0])
        
        # Find current series in sorted list
        current_index = None
        for idx, (_, series_uid, _) in enumerate(series_list):
            if series_uid == self.current_series_uid:
                current_index = idx
                break
        
        if current_index is None:
            return  # Current series not found
        
        # Calculate new series index
        new_index = current_index + direction
        
        # Clamp to valid range
        if new_index < 0 or new_index >= len(series_list):
            return  # Already at first or last series
        
        # Get new series UID and datasets
        _, new_series_uid, datasets = series_list[new_index]
        
        # Switch to new series
        self.current_series_uid = new_series_uid
        
        if not datasets:
            return
        
        # Reset slice index to 0 and display first slice
        self.current_slice_index = 0
        dataset = datasets[0]
        self._display_slice(dataset)
        
        # Update slice navigator with new series slice count
        self.slice_navigator.set_total_slices(len(datasets))
        self.slice_navigator.set_current_slice(0)
        
        # Display ROIs for this slice
        self._display_rois_for_slice(dataset)
    
    def _on_overlay_font_size_changed(self, font_size: int) -> None:
        """
        Handle overlay font size change from toolbar.
        
        Args:
            font_size: New font size in points
        """
        # Update overlay manager
        self.overlay_manager.set_font_size(font_size)
        
        # Recreate overlay if we have a current dataset
        if self.current_studies and self.current_series_uid:
            datasets = self.current_studies[self.current_study_uid][self.current_series_uid]
            if self.current_slice_index < len(datasets):
                dataset = datasets[self.current_slice_index]
                parser = DICOMParser(dataset)
                total_slices = len(datasets)
                self.overlay_manager.create_overlay_items(
                    self.image_viewer.scene,
                    parser,
                    total_slices=total_slices if total_slices > 0 else None
                )
    
    def _on_overlay_font_color_changed(self, r: int, g: int, b: int) -> None:
        """
        Handle overlay font color change from toolbar.
        
        Args:
            r: Red component (0-255)
            g: Green component (0-255)
            b: Blue component (0-255)
        """
        # Update overlay manager
        self.overlay_manager.set_font_color(r, g, b)
        
        # Recreate overlay if we have a current dataset
        if self.current_studies and self.current_series_uid:
            datasets = self.current_studies[self.current_study_uid][self.current_series_uid]
            if self.current_slice_index < len(datasets):
                dataset = datasets[self.current_slice_index]
                parser = DICOMParser(dataset)
                total_slices = len(datasets)
                self.overlay_manager.create_overlay_items(
                    self.image_viewer.scene,
                    parser,
                    total_slices=total_slices if total_slices > 0 else None
                )
    
    def _on_scene_selection_changed(self) -> None:
        """Handle scene selection change (e.g., when ROI is moved)."""
        try:
            # Check if scene is still valid
            if self.image_viewer.scene is None:
                return
            selected_items = self.image_viewer.scene.selectedItems()
            if selected_items:
                # Find ROI for selected item
                for item in selected_items:
                    roi = self.roi_manager.find_roi_by_item(item)
                    if roi:
                        # Update statistics when ROI is moved/selected
                        self._update_roi_statistics(roi)
                        # Update list panel selection
                        self.roi_list_panel.select_roi_in_list(roi)
                        break
        except RuntimeError:
            # Scene has been deleted or is invalid, ignore
            return
    
    def _update_roi_statistics(self, roi) -> None:
        """
        Update statistics panel for a ROI.
        
        Args:
            roi: ROI item
        """
        if roi is None or self.current_dataset is None:
            return
        
        try:
            # Extract DICOM identifiers
            study_uid = getattr(self.current_dataset, 'StudyInstanceUID', '')
            series_uid = getattr(self.current_dataset, 'SeriesInstanceUID', '')
            instance_number = getattr(self.current_dataset, 'InstanceNumber', None)
            if instance_number is None:
                instance_identifier = self.current_slice_index
            else:
                instance_identifier = int(instance_number)
            
            # Get ROI identifier (e.g., "ROI 1 (rectangle)")
            roi_identifier = None
            rois = self.roi_manager.get_rois_for_slice(study_uid, series_uid, instance_identifier)
            for i, r in enumerate(rois):
                if r == roi:
                    roi_identifier = f"ROI {i+1} ({roi.shape_type})"
                    break
            
            pixel_array = self.dicom_processor.get_pixel_array(self.current_dataset)
            if pixel_array is not None:
                # Extract pixel spacing for area calculation
                from utils.dicom_utils import get_pixel_spacing
                pixel_spacing = get_pixel_spacing(self.current_dataset)
                
                # Pass rescale parameters if using rescaled values
                rescale_slope = self.rescale_slope if self.use_rescaled_values else None
                rescale_intercept = self.rescale_intercept if self.use_rescaled_values else None
                stats = self.roi_manager.calculate_statistics(
                    roi, pixel_array, 
                    rescale_slope=rescale_slope,
                    rescale_intercept=rescale_intercept,
                    pixel_spacing=pixel_spacing
                )
                # Pass rescale_type for display
                rescale_type = self.rescale_type if self.use_rescaled_values else None
                self.roi_statistics_panel.update_statistics(stats, roi_identifier, rescale_type=rescale_type)
        except Exception as e:
            print(f"Error calculating ROI statistics: {e}")
    
    def _on_slice_changed(self, slice_index: int) -> None:
        """
        Handle slice index change.
        
        Args:
            slice_index: New slice index
        """
        if not self.current_studies or not self.current_series_uid:
            return
        
        datasets = self.current_studies[self.current_study_uid][self.current_series_uid]
        if 0 <= slice_index < len(datasets):
            self.current_slice_index = slice_index
            dataset = datasets[slice_index]
            self._display_slice(dataset)
            
            # Display ROIs for this slice (will update ROI manager and list panel internally)
            self._display_rois_for_slice(dataset)
    
    def eventFilter(self, obj, event) -> bool:
        """
        Event filter for handling key events.
        
        Args:
            obj: Object that received the event
            event: Event
            
        Returns:
            True if event was handled, False otherwise
        """
        from PySide6.QtGui import QKeyEvent
        if isinstance(event, QKeyEvent) and event.type() == QKeyEvent.Type.KeyPress:
            # Delete key to delete selected ROI or measurement
            if event.key() == Qt.Key.Key_Delete or event.key() == Qt.Key.Key_Backspace:
                # Check for selected ROI first (priority)
                selected_roi = self.roi_manager.get_selected_roi()
                if selected_roi:
                    self.roi_manager.delete_roi(selected_roi, self.image_viewer.scene)
                    # Update ROI list panel - extract identifiers from current dataset
                    if self.current_dataset is not None:
                        study_uid = getattr(self.current_dataset, 'StudyInstanceUID', '')
                        series_uid = getattr(self.current_dataset, 'SeriesInstanceUID', '')
                        instance_number = getattr(self.current_dataset, 'InstanceNumber', None)
                        if instance_number is None:
                            instance_identifier = self.current_slice_index
                        else:
                            instance_identifier = int(instance_number)
                        self.roi_list_panel.update_roi_list(study_uid, series_uid, instance_identifier)
                    self.roi_statistics_panel.clear_statistics()
                    return True
                
                # Check for selected measurement
                if self.image_viewer.scene is not None:
                    try:
                        selected_items = self.image_viewer.scene.selectedItems()
                        from tools.measurement_tool import MeasurementItem
                        for item in selected_items:
                            if isinstance(item, MeasurementItem):
                                self.measurement_tool.delete_measurement(item, self.image_viewer.scene)
                                return True
                    except RuntimeError:
                        # Scene may have been deleted, ignore
                        pass
            # Arrow keys for slice navigation
            elif event.key() == Qt.Key.Key_Up:
                # Up arrow: next slice
                self.slice_navigator.next_slice()
                return True
            elif event.key() == Qt.Key.Key_Down:
                # Down arrow: previous slice
                self.slice_navigator.previous_slice()
                return True
        
        return super().eventFilter(obj, event)
    
    def run(self) -> int:
        """
        Run the application.
        
        Returns:
            Exit code
        """
        # Show window maximized (full-screen)
        self.main_window.showMaximized()
        return self.app.exec()


def main():
    """Main entry point."""
    try:
        app = DICOMViewerApp()
        return app.run()
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())


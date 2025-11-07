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
from typing import Optional
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
        
        # Tag viewer dialog (persistent)
        self.tag_viewer_dialog: Optional[TagViewerDialog] = None
    
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
        
        # ROI click signal
        self.image_viewer.roi_clicked.connect(self._on_roi_clicked)
        
        # ROI delete signal (from right-click context menu)
        self.image_viewer.roi_delete_requested.connect(self._on_roi_delete_requested)
        
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
        
        # Zoom changes - update overlay positions to keep text anchored
        self.image_viewer.zoom_changed.connect(self._on_zoom_changed)
        
        # Transform changes (zoom/pan) - update overlay positions to keep text anchored
        # This signal fires after transform is applied, ensuring accurate viewport-to-scene mapping
        self.image_viewer.transform_changed.connect(self._on_transform_changed)
        
        # Arrow key navigation from image viewer
        self.image_viewer.arrow_key_pressed.connect(self._on_arrow_key_pressed)
        
        # Overlay font size and color changes
        self.main_window.overlay_font_size_changed.connect(self._on_overlay_font_size_changed)
        self.main_window.overlay_font_color_changed.connect(self._on_overlay_font_color_changed)
        
        # Reset view request (from toolbar and context menu)
        self.main_window.reset_view_requested.connect(self._reset_view)
        self.image_viewer.reset_view_requested.connect(self._reset_view)
        
        # Viewport resize (when splitter moves)
        self.main_window.viewport_resized.connect(self._on_viewport_resized)
    
    def _open_files(self) -> None:
        """Handle open files request."""
        file_paths = self.file_dialog.open_files(self.main_window)
        if not file_paths:
            return
        
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
        
        # Get first study and series
        study_uid = list(self.current_studies.keys())[0]
        series_uid = list(self.current_studies[study_uid].keys())[0]
        datasets = self.current_studies[study_uid][series_uid]
        
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
            
            # Get series UID from dataset to check if we're in the same series
            new_series_uid = getattr(dataset, 'SeriesInstanceUID', '')
            is_same_series = (new_series_uid == self.current_series_uid and self.current_series_uid != "")
            
            # Convert to image
            image = self.dicom_processor.dataset_to_image(dataset)
            if image is None:
                return
            
            # Set image in viewer - preserve zoom/pan if same series
            self.image_viewer.set_image(image, preserve_view=is_same_series)
            
            # Update current series UID
            if new_series_uid:
                self.current_series_uid = new_series_uid
            
            # Update metadata panel
            self.metadata_panel.set_dataset(dataset)
            
            # Update tag viewer if open
            if self.tag_viewer_dialog is not None and self.tag_viewer_dialog.isVisible():
                self.tag_viewer_dialog.set_dataset(dataset)
            
            # Calculate pixel value range for window/level controls
            pixel_min, pixel_max = self.dicom_processor.get_pixel_value_range(dataset)
            if pixel_min is not None and pixel_max is not None:
                # Set ranges based on actual pixel values (no margins)
                center_range = (pixel_min, pixel_max)
                # Width range from 1 to the pixel range (not 2x)
                width_range = (1.0, max(1.0, pixel_max - pixel_min))
                self.window_level_controls.set_ranges(center_range, width_range)
            
            # Update window/level controls
            # If user has modified window/level, preserve it when navigating between slices
            if self.window_level_user_modified and self.current_window_center is not None and self.current_window_width is not None:
                # Use preserved window/level values
                self.window_level_controls.set_window_level(self.current_window_center, self.current_window_width, block_signals=True)
            else:
                # Use values from dataset or calculate defaults
                wc, ww = self.dicom_processor.get_window_level_from_dataset(dataset)
                if wc is not None and ww is not None:
                    self.window_level_controls.set_window_level(wc, ww, block_signals=True)
                    self.current_window_center = wc
                    self.current_window_width = ww
                elif pixel_min is not None and pixel_max is not None:
                    # Use default window/level based on pixel range
                    default_center = (pixel_min + pixel_max) / 2.0
                    default_width = pixel_max - pixel_min
                    if default_width <= 0:
                        default_width = 1.0
                    self.window_level_controls.set_window_level(default_center, default_width, block_signals=True)
                    self.current_window_center = default_center
                    self.current_window_width = default_width
                self.window_level_user_modified = False  # Reset flag after setting from dataset
            
            # Store initial view state if this is the first image
            if self.initial_zoom is None:
                # Wait a bit for view to settle, then store initial state
                from PySide6.QtCore import QTimer
                QTimer.singleShot(100, self._store_initial_view_state)
            
            # Update overlay
            parser = DICOMParser(dataset)
            self.overlay_manager.create_overlay_items(
                self.image_viewer.scene,
                parser
            )
            
            # Display ROIs for current slice
            self._display_rois_for_slice(self.current_slice_index)
        
        except Exception as e:
            self.main_window.update_status(f"Error displaying slice: {str(e)}")
    
    def _store_initial_view_state(self) -> None:
        """
        Store the initial view state (zoom, pan, window/level) for reset functionality.
        
        Called after the first image is displayed and the view has settled.
        """
        if self.image_viewer.image_item is None:
            return
        
        # Store initial zoom
        self.initial_zoom = self.image_viewer.current_zoom
        
        # Store initial pan position (scrollbar values)
        self.initial_h_scroll = self.image_viewer.horizontalScrollBar().value()
        self.initial_v_scroll = self.image_viewer.verticalScrollBar().value()
        
        # Store initial window/level
        self.initial_window_center = self.current_window_center
        self.initial_window_width = self.current_window_width
    
    def _reset_view(self) -> None:
        """
        Reset view to initial state (zoom, pan, window center/level).
        
        Restores the view state that was stored when the first image was loaded.
        """
        if self.initial_zoom is None or self.current_dataset is None:
            # No initial state stored or no current dataset
            return
        
        # Reset zoom and pan
        self.image_viewer.resetTransform()
        self.image_viewer.scale(self.initial_zoom, self.initial_zoom)
        self.image_viewer.current_zoom = self.initial_zoom
        
        # Restore scrollbar positions
        from PySide6.QtCore import QTimer
        QTimer.singleShot(10, lambda: (
            self.image_viewer.horizontalScrollBar().setValue(self.initial_h_scroll),
            self.image_viewer.verticalScrollBar().setValue(self.initial_v_scroll),
            self.image_viewer._update_scrollbar_ranges()
        ))
        
        self.image_viewer.last_transform = self.image_viewer.transform()
        self.image_viewer.zoom_changed.emit(self.image_viewer.current_zoom)
        
        # Reset window/level to initial values
        if self.initial_window_center is not None and self.initial_window_width is not None:
            self.window_level_controls.set_window_level(
                self.initial_window_center, 
                self.initial_window_width, 
                block_signals=True
            )
            self.current_window_center = self.initial_window_center
            self.current_window_width = self.initial_window_width
            self.window_level_user_modified = False
            
            # Re-display current slice with reset window/level
            if self.current_studies and self.current_series_uid:
                datasets = self.current_studies[self.current_study_uid][self.current_series_uid]
                if self.current_slice_index < len(datasets):
                    dataset = datasets[self.current_slice_index]
                    image = self.dicom_processor.dataset_to_image(
                        dataset,
                        window_center=self.initial_window_center,
                        window_width=self.initial_window_width
                    )
                    if image:
                        # Preserve view when resetting window/level
                        self.image_viewer.set_image(image, preserve_view=True)
                        # Recreate overlay
                        parser = DICOMParser(dataset)
                        self.overlay_manager.create_overlay_items(
                            self.image_viewer.scene,
                            parser
                        )
    
    def _display_rois_for_slice(self, slice_index: int) -> None:
        """
        Display ROIs for a slice.
        
        Ensures all ROIs for the current slice are visible in the scene.
        
        Args:
            slice_index: Slice index
        """
        # Get all ROIs for this slice
        rois = self.roi_manager.get_rois_for_slice(slice_index)
        
        # Remove ROIs from other slices from the scene
        # (but keep them in the manager's storage)
        current_scene_items = list(self.image_viewer.scene.items())
        for item in current_scene_items:
            # Check if this item is an ROI from a different slice
            roi = self.roi_manager.find_roi_by_item(item)
            if roi is not None:
                # Check if this ROI belongs to current slice
                roi_slice = None
                for s_idx, roi_list in self.roi_manager.rois.items():
                    if roi in roi_list:
                        roi_slice = s_idx
                        break
                # Remove ROI if it's from a different slice
                if roi_slice is not None and roi_slice != slice_index:
                    self.image_viewer.scene.removeItem(item)
        
        # Add ROIs for current slice to scene if not already there
        for roi in rois:
            if roi.item.scene() != self.image_viewer.scene:
                self.image_viewer.scene.addItem(roi.item)
                # Ensure ROI is visible (set appropriate Z-value)
                roi.item.setZValue(100)  # Above image but below overlay
    
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
                self.overlay_manager.create_overlay_items(
                    self.image_viewer.scene,
                    parser
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
                self.overlay_manager.create_overlay_items(
                    self.image_viewer.scene,
                    parser
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
                    window_width=width
                )
                if image:
                    # Preserve view when window/level changes (same slice)
                    self.image_viewer.set_image(image, preserve_view=True)
                    # Recreate overlay to ensure it stays on top
                    parser = DICOMParser(dataset)
                    self.overlay_manager.create_overlay_items(
                        self.image_viewer.scene,
                        parser
                    )
    
    def _on_mouse_mode_changed(self, mode: str) -> None:
        """
        Handle mouse mode change from toolbar.
        
        Args:
            mode: Mouse mode ("roi_ellipse", "roi_rectangle", "measure", "zoom", "pan")
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
        self.roi_manager.set_current_slice(self.current_slice_index)
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
        
        # Update ROI list
        self.roi_list_panel.update_roi_list(self.current_slice_index)
        
        # Calculate and display statistics if ROI was created
        if roi_item is not None and self.current_dataset is not None:
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
            self.roi_list_panel.update_roi_list(self.current_slice_index)
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
                self.overlay_manager.create_overlay_items(
                    self.image_viewer.scene,
                    parser
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
                self.overlay_manager.create_overlay_items(
                    self.image_viewer.scene,
                    parser
                )
    
    def _on_scene_selection_changed(self) -> None:
        """Handle scene selection change (e.g., when ROI is moved)."""
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
    
    def _update_roi_statistics(self, roi) -> None:
        """
        Update statistics panel for a ROI.
        
        Args:
            roi: ROI item
        """
        if roi is None or self.current_dataset is None:
            return
        
        try:
            # Get ROI identifier (e.g., "ROI 1 (rectangle)")
            roi_identifier = None
            rois = self.roi_manager.get_rois_for_slice(self.current_slice_index)
            for i, r in enumerate(rois):
                if r == roi:
                    roi_identifier = f"ROI {i+1} ({roi.shape_type})"
                    break
            
            pixel_array = self.dicom_processor.get_pixel_array(self.current_dataset)
            if pixel_array is not None:
                stats = self.roi_manager.calculate_statistics(roi, pixel_array)
                self.roi_statistics_panel.update_statistics(stats, roi_identifier)
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
            self._display_slice(datasets[slice_index])
            
            # Update ROI manager for current slice
            self.roi_manager.set_current_slice(slice_index)
            
            # Update ROI list panel
            self.roi_list_panel.update_roi_list(slice_index)
            
            # Display ROIs for this slice
            self._display_rois_for_slice(slice_index)
    
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
            # Delete key to delete selected ROI
            if event.key() == Qt.Key.Key_Delete or event.key() == Qt.Key.Key_Backspace:
                selected_roi = self.roi_manager.get_selected_roi()
                if selected_roi:
                    self.roi_manager.delete_roi(selected_roi, self.image_viewer.scene)
                    self.roi_list_panel.update_roi_list(self.current_slice_index)
                    self.roi_statistics_panel.clear_statistics()
                    return True
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


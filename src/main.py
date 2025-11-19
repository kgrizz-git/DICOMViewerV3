"""
DICOM Viewer V3 - Main Application Entry Point

This module is the main entry point for the DICOM viewer application.
It initializes the application, creates the main window, and sets up
the application event loop.

Inputs:
    - Command line arguments (optional)
    
Outputs:
    - Running DICOM viewer application
    
Requirements:
    - PySide6 for application framework
    - pydicom for DICOM file handling
    - PIL/Pillow for image processing
    - numpy for array operations
    - openpyxl for Excel export (tag export feature)
    - All other application modules
"""

import sys
import os
from pathlib import Path

# Add src directory to path
src_dir = Path(__file__).parent
sys.path.insert(0, str(src_dir))

from PySide6.QtWidgets import QApplication, QMessageBox, QStyleFactory
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
from gui.dialogs.annotation_options_dialog import AnnotationOptionsDialog
from gui.image_viewer import ImageViewer
from gui.metadata_panel import MetadataPanel
from gui.window_level_controls import WindowLevelControls
from gui.roi_statistics_panel import ROIStatisticsPanel
from gui.roi_list_panel import ROIListPanel
from gui.slice_navigator import SliceNavigator
from gui.series_navigator import SeriesNavigator
from gui.zoom_display_widget import ZoomDisplayWidget
from gui.cine_player import CinePlayer
from gui.cine_controls_widget import CineControlsWidget
from gui.intensity_projection_controls_widget import IntensityProjectionControlsWidget
from core.dicom_loader import DICOMLoader
from core.dicom_organizer import DICOMOrganizer
from core.dicom_parser import DICOMParser
from core.dicom_processor import DICOMProcessor
from core.tag_edit_history import TagEditHistoryManager
from utils.config_manager import ConfigManager
from tools.roi_manager import ROIManager
from tools.measurement_tool import MeasurementTool
from tools.annotation_manager import AnnotationManager
from tools.histogram_widget import HistogramWidget
from gui.overlay_manager import OverlayManager

# Import handler classes
from core.view_state_manager import ViewStateManager
from core.file_operations_handler import FileOperationsHandler
from core.slice_display_manager import SliceDisplayManager
from gui.roi_coordinator import ROICoordinator
from gui.measurement_coordinator import MeasurementCoordinator
from gui.overlay_coordinator import OverlayCoordinator
from gui.dialog_coordinator import DialogCoordinator
from gui.mouse_mode_handler import MouseModeHandler
from gui.keyboard_event_handler import KeyboardEventHandler


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
        self.app.setApplicationName("DICOM Viewer V3")
        
        # Set Fusion style for consistent cross-platform appearance
        self.app.setStyle(QStyleFactory.create("Fusion"))
        
        # Initialize managers
        self.config_manager = ConfigManager()
        self.dicom_loader = DICOMLoader()
        self.dicom_organizer = DICOMOrganizer()
        self.dicom_processor = DICOMProcessor()
        self.tag_edit_history = TagEditHistoryManager(max_history=50)
        
        # Create main window
        self.main_window = MainWindow(self.config_manager)
        
        # Install event filter on main window for key events
        self.main_window.installEventFilter(self)
        
        # Create components
        self.file_dialog = FileDialog(self.config_manager)
        self.image_viewer = ImageViewer(config_manager=self.config_manager)
        
        # Set image viewer reference in main window for theme updates
        self.main_window.image_viewer = self.image_viewer
        # Apply theme again to set background color now that image_viewer is assigned
        self.main_window._apply_theme()
        self.metadata_panel = MetadataPanel(config_manager=self.config_manager)
        self.metadata_panel.set_history_manager(self.tag_edit_history)
        self.window_level_controls = WindowLevelControls()
        self.zoom_display_widget = ZoomDisplayWidget()
        self.slice_navigator = SliceNavigator()
        self.roi_manager = ROIManager(config_manager=self.config_manager)
        self.measurement_tool = MeasurementTool(config_manager=self.config_manager)
        self.annotation_manager = AnnotationManager()
        self.roi_statistics_panel = ROIStatisticsPanel()
        self.roi_list_panel = ROIListPanel()
        
        # Flag to track if we're in the middle of a reset operation
        self._resetting_projection_state = False
        self.roi_list_panel.set_roi_manager(self.roi_manager)
        self.series_navigator = SeriesNavigator(self.dicom_processor)
        self.cine_controls_widget = CineControlsWidget()
        self.intensity_projection_controls_widget = IntensityProjectionControlsWidget()
        
        # Initialize overlay manager with config settings
        font_size = self.config_manager.get_overlay_font_size()
        font_color = self.config_manager.get_overlay_font_color()
        self.overlay_manager = OverlayManager(
            font_size=font_size, 
            font_color=font_color,
            config_manager=self.config_manager
        )
        # Overlay manager initializes to state 0 (all shown) by default
        # Do not load state from config - always start with everything visible
        
        # Set scroll wheel mode
        scroll_mode = self.config_manager.get_scroll_wheel_mode()
        self.image_viewer.set_scroll_wheel_mode(scroll_mode)
        self.slice_navigator.set_scroll_wheel_mode(scroll_mode)
        
        # Set up UI layout
        self._setup_ui()
        
        # Current data
        self.current_datasets: list = []
        self.current_studies: dict = {}
        self.current_slice_index = 0
        self.current_series_uid = ""
        self.current_study_uid = ""
        self.current_dataset: Optional[Dataset] = None
        
        # Initialize handler classes
        self._initialize_handlers()
        
        # Connect signals
        self._connect_signals()
        
        # Initialize pan mode to match toolbar state (Pan button is checked by default)
        self.image_viewer.set_mouse_mode("pan")
    
    def _initialize_handlers(self) -> None:
        """Initialize all handler classes."""
        # Initialize ViewStateManager
        self.view_state_manager = ViewStateManager(
            self.dicom_processor,
            self.image_viewer,
            self.window_level_controls,
            self.main_window,
            self.overlay_manager,
            overlay_coordinator=None,  # Will be set after overlay coordinator is created
            roi_coordinator=None,  # Will be set after ROI coordinator is created
            display_rois_for_slice=None  # Will be set after slice display manager is created
        )
        
        # Initialize FileOperationsHandler
        self.file_operations_handler = FileOperationsHandler(
            self.dicom_loader,
            self.dicom_organizer,
            self.file_dialog,
            self.config_manager,
            self.main_window,
            clear_data_callback=self._clear_data,
            load_first_slice_callback=self._handle_load_first_slice,
            update_status_callback=self.main_window.update_status
        )
        
        # Initialize SliceDisplayManager
        self.slice_display_manager = SliceDisplayManager(
            self.dicom_processor,
            self.image_viewer,
            self.metadata_panel,
            self.slice_navigator,
            self.window_level_controls,
            self.roi_manager,
            self.measurement_tool,
            self.overlay_manager,
            self.view_state_manager,
            update_tag_viewer_callback=self._update_tag_viewer,
            display_rois_callback=None,  # Will use default
            display_measurements_callback=None,  # Will use default
            roi_list_panel=self.roi_list_panel,
            roi_statistics_panel=self.roi_statistics_panel,
            update_roi_statistics_overlays_callback=None,  # Will be set after ROI coordinator is created
            annotation_manager=self.annotation_manager,
            dicom_organizer=self.dicom_organizer
        )
        self.view_state_manager.set_redisplay_slice_callback(self._redisplay_current_slice)
        
        # Initialize ROICoordinator
        self.roi_coordinator = ROICoordinator(
            self.roi_manager,
            self.roi_list_panel,
            self.roi_statistics_panel,
            self.image_viewer,
            self.dicom_processor,
            self.window_level_controls,
            self.main_window,
            get_current_dataset=lambda: self.current_dataset,
            get_current_slice_index=lambda: self.current_slice_index,
            get_rescale_params=self._get_rescale_params,
            set_mouse_mode_callback=self._set_mouse_mode_via_handler,
            get_projection_enabled=lambda: self.slice_display_manager.projection_enabled,
            get_projection_type=lambda: self.slice_display_manager.projection_type,
            get_projection_slice_count=lambda: self.slice_display_manager.projection_slice_count,
            get_current_studies=lambda: self.current_studies
        )
        
        # Update view state manager with ROI coordinator
        self.view_state_manager.roi_coordinator = lambda dataset: self.roi_coordinator.update_roi_statistics(
            self.roi_manager.get_selected_roi()
        ) if self.roi_manager.get_selected_roi() else None
        
        # Update view state manager with display_rois_for_slice callback
        self.view_state_manager.display_rois_for_slice = self._display_rois_for_slice
        
        # Update view state manager with series_navigator reference
        self.view_state_manager.set_series_navigator(self.series_navigator)
        
        # Connect image viewer inversion callback to view state manager
        def on_inversion_state_changed(inverted: bool) -> None:
            """Handle inversion state change - store in ViewStateManager."""
            if self.view_state_manager.current_series_identifier:
                self.view_state_manager.set_series_inversion_state(
                    self.view_state_manager.current_series_identifier,
                    inverted
                )
        self.image_viewer.inversion_state_changed_callback = on_inversion_state_changed
        
        # Update slice display manager with ROI coordinator callback
        self.slice_display_manager.update_roi_statistics_overlays_callback = self.roi_coordinator.update_roi_statistics_overlays
        
        # Initialize MeasurementCoordinator
        self.measurement_coordinator = MeasurementCoordinator(
            self.measurement_tool,
            self.image_viewer,
            get_current_dataset=lambda: self.current_dataset,
            get_current_slice_index=lambda: self.current_slice_index
        )
        
        # Initialize OverlayCoordinator
        self.overlay_coordinator = OverlayCoordinator(
            self.overlay_manager,
            self.image_viewer,
            get_current_dataset=lambda: self.current_dataset,
            get_current_studies=lambda: self.current_studies,
            get_current_study_uid=lambda: self.current_study_uid,
            get_current_series_uid=lambda: self.current_series_uid,
            get_current_slice_index=lambda: self.current_slice_index,
            hide_measurement_labels=self.measurement_coordinator.hide_measurement_labels,
            hide_measurement_graphics=self.measurement_coordinator.hide_measurement_graphics,
            hide_roi_graphics=self.roi_coordinator.hide_roi_graphics if hasattr(self.roi_coordinator, 'hide_roi_graphics') else None,
            hide_roi_statistics_overlays=self.roi_coordinator.hide_roi_statistics_overlays
        )
        
        # Update view state manager with overlay coordinator
        self.view_state_manager.overlay_coordinator = self.overlay_coordinator.handle_overlay_config_applied
        
        # Initialize DialogCoordinator
        self.dialog_coordinator = DialogCoordinator(
            self.config_manager,
            self.main_window,
            get_current_studies=lambda: self.current_studies,
            settings_applied_callback=self._on_settings_applied,
            overlay_config_applied_callback=self._on_overlay_config_applied,
            tag_edit_history=self.tag_edit_history
        )
        # Set annotation options callback
        self.dialog_coordinator.annotation_options_applied_callback = self._on_annotation_options_applied
        
        # Initialize MouseModeHandler
        self.mouse_mode_handler = MouseModeHandler(
            self.image_viewer,
            self.main_window,
            self.slice_navigator,
            self.config_manager
        )
        
        # Initialize CinePlayer
        self.cine_player = CinePlayer(
            slice_navigator=self.slice_navigator,
            get_total_slices_callback=lambda: self.slice_navigator.total_slices,
            get_current_slice_callback=lambda: self.slice_navigator.get_current_slice()
        )
        
        # Set default cine settings from config
        default_speed = self.config_manager.get_cine_default_speed()
        default_loop = self.config_manager.get_cine_default_loop()
        self.cine_player.set_speed(default_speed)
        self.cine_player.set_loop(default_loop)
        # Update UI to match defaults
        self.cine_controls_widget.set_speed(default_speed)
        self.cine_controls_widget.set_loop(default_loop)
        
        # Initialize KeyboardEventHandler
        self.keyboard_event_handler = KeyboardEventHandler(
            self.roi_manager,
            self.measurement_tool,
            self.slice_navigator,
            self.overlay_manager,
            self.image_viewer,
            set_mouse_mode=self.mouse_mode_handler.set_mouse_mode,
            delete_all_rois_callback=self.roi_coordinator.delete_all_rois_current_slice,
            clear_measurements_callback=self.measurement_coordinator.handle_clear_measurements,
            toggle_overlay_callback=self.overlay_coordinator.handle_toggle_overlay,
            get_selected_roi=lambda: self.roi_manager.get_selected_roi(),
            delete_roi_callback=lambda roi: self.roi_coordinator.handle_roi_delete_requested(roi.item) if (hasattr(roi, 'item') and roi.item is not None) else (self.roi_manager.delete_roi(roi, self.image_viewer.scene) if roi else None),
            delete_measurement_callback=self.measurement_coordinator.handle_measurement_delete_requested,
            update_roi_list_callback=self._update_roi_list,
            clear_roi_statistics_callback=self.roi_statistics_panel.clear_statistics,
            reset_view_callback=self.view_state_manager.reset_view,
            toggle_series_navigator_callback=self.main_window.toggle_series_navigator,
            invert_image_callback=self.image_viewer.invert_image
        )
    
    def _clear_data(self) -> None:
        """Clear all ROIs, measurements, and related data."""
        self.roi_manager.clear_all_rois(self.image_viewer.scene)
        self.roi_list_panel.update_roi_list("", "", 0)  # Clear list
        self.roi_statistics_panel.clear_statistics()
        self.measurement_tool.clear_measurements(self.image_viewer.scene)
    
    def _close_files(self) -> None:
        """Close currently open files/folder and clear all data."""
        # Clear all ROIs, measurements, and related data
        self._clear_data()
        
        # Clear image viewer
        self.image_viewer.scene.clear()
        self.image_viewer.image_item = None
        
        # Clear overlay items list (items already cleared by scene.clear())
        self.overlay_manager.overlay_items.clear()
        
        # Clear metadata panel
        self.metadata_panel.set_dataset(None)
        
        # Reset view state
        self.view_state_manager.reset_window_level_state()
        self.view_state_manager.reset_series_tracking()
        
        # Reset projection state
        self.slice_display_manager.reset_projection_state()
        # Update widget to match reset state
        self.intensity_projection_controls_widget.set_enabled(False)
        self.intensity_projection_controls_widget.set_projection_type("aip")
        self.intensity_projection_controls_widget.set_slice_count(4)
        
        # Clear current dataset references
        self.current_dataset = None
        self.current_studies = {}
        self.current_study_uid = ""
        self.current_series_uid = ""
        self.current_slice_index = 0
        
        # Reset slice navigator
        self.slice_navigator.set_total_slices(0)
        self.slice_navigator.set_current_slice(0)
        
        # Clear series navigator
        self.series_navigator.update_series_list({}, "", "")
        
        # Clear tag edit history
        if self.tag_edit_history:
            self.tag_edit_history.clear_history()
        
        # Reset undo/redo state
        self._update_undo_redo_state()
        
        # Update status
        self.main_window.update_status("Ready")
    
    def _handle_load_first_slice(self, studies: dict) -> None:
        """Handle loading first slice after file operations."""
        # Reset projection state when new files are opened
        self.slice_display_manager.reset_projection_state()
        # Update widget to match reset state
        self.intensity_projection_controls_widget.set_enabled(False)
        self.intensity_projection_controls_widget.set_projection_type("aip")
        self.intensity_projection_controls_widget.set_slice_count(4)
        
        first_slice_info = self.file_operations_handler.load_first_slice(studies)
        if first_slice_info:
            self.current_studies = studies
            self.current_study_uid = first_slice_info['study_uid']
            self.current_series_uid = first_slice_info['series_uid']
            self.current_slice_index = first_slice_info['slice_index']
            
            # Load Presentation States and Key Objects into annotation manager
            # Collect all presentation states and key objects from all studies
            all_presentation_states = {}
            all_key_objects = {}
            
            for study_uid in studies.keys():
                presentation_states = self.dicom_organizer.get_presentation_states(study_uid)
                key_objects = self.dicom_organizer.get_key_objects(study_uid)
                
                if presentation_states:
                    # print(f"[ANNOTATIONS] Found {len(presentation_states)} Presentation State(s) for study {study_uid[:20]}...")
                    all_presentation_states[study_uid] = presentation_states
                if key_objects:
                    # print(f"[ANNOTATIONS] Found {len(key_objects)} Key Object(s) for study {study_uid[:20]}...")
                    all_key_objects[study_uid] = key_objects
            
            # Load into annotation manager
            if all_presentation_states:
                self.annotation_manager.load_presentation_states(all_presentation_states)
                # print(f"[ANNOTATIONS] Loaded Presentation States for {len(all_presentation_states)} studies")
            if all_key_objects:
                self.annotation_manager.load_key_objects(all_key_objects)
                # print(f"[ANNOTATIONS] Loaded Key Objects for {len(all_key_objects)} studies")
            
            # Reset view state
            self.view_state_manager.reset_window_level_state()
            self.view_state_manager.reset_series_tracking()
            
            # Set up slice navigator
            self.slice_navigator.set_total_slices(first_slice_info['total_slices'])
            self.slice_navigator.set_current_slice(0)
            
            # Display slice
            self.slice_display_manager.display_slice(
                first_slice_info['dataset'],
                self.current_studies,
                self.current_study_uid,
                self.current_series_uid,
                self.current_slice_index
            )
            
            # Update current dataset reference
            self.current_dataset = first_slice_info['dataset']
            
            # Update cine player context and check if series is cine-capable
            self._update_cine_player_context()
            
            # Clear tag edit history for new dataset
            if self.tag_edit_history:
                self.tag_edit_history.clear_history(self.current_dataset)
            self._update_undo_redo_state()
            
            # Store initial view state after a delay
            from PySide6.QtCore import QTimer
            QTimer.singleShot(100, self.view_state_manager.store_initial_view_state)
            
            # Update series navigator
            self.series_navigator.update_series_list(
                self.current_studies,
                self.current_study_uid,
                self.current_series_uid
            )
            
            # Show navigator by default if it's hidden
            navigator_was_hidden = not self.main_window.series_navigator_visible
            if navigator_was_hidden:
                self.main_window.toggle_series_navigator()
            
            # After navigator is shown (if it was hidden), fit image to viewport
            # Use QTimer to ensure viewport has fully resized
            if navigator_was_hidden:
                from PySide6.QtCore import QTimer
                QTimer.singleShot(50, lambda: self.image_viewer.fit_to_view(center_image=True))
    
    def _get_rescale_params(self) -> tuple[Optional[float], Optional[float], Optional[str], bool]:
        """Get rescale parameters for ROI operations."""
        return (
            self.view_state_manager.rescale_slope,
            self.view_state_manager.rescale_intercept,
            self.view_state_manager.rescale_type,
            self.view_state_manager.use_rescaled_values
        )
    
    def _set_mouse_mode_via_handler(self, mode: str) -> None:
        """Set mouse mode via mouse mode handler."""
        self.mouse_mode_handler.set_mouse_mode(mode)
    
    def _update_tag_viewer(self, dataset: Dataset) -> None:
        """Update tag viewer with dataset."""
        self.dialog_coordinator.update_tag_viewer(dataset)
    
    def _undo_tag_edit(self) -> None:
        """Handle undo tag edit request."""
        if self.current_dataset is not None and self.tag_edit_history:
            success = self.tag_edit_history.undo(self.current_dataset)
            if success:
                # Refresh metadata panel and tag viewer
                self.metadata_panel._populate_tags()
                if self.dialog_coordinator.tag_viewer_dialog:
                    search_text = self.dialog_coordinator.tag_viewer_dialog.search_edit.text()
                    self.dialog_coordinator.tag_viewer_dialog._populate_tags(search_text)
                # Update undo/redo state
                self._update_undo_redo_state()
    
    def _redo_tag_edit(self) -> None:
        """Handle redo tag edit request."""
        if self.current_dataset is not None and self.tag_edit_history:
            success = self.tag_edit_history.redo(self.current_dataset)
            if success:
                # Refresh metadata panel and tag viewer
                self.metadata_panel._populate_tags()
                if self.dialog_coordinator.tag_viewer_dialog:
                    search_text = self.dialog_coordinator.tag_viewer_dialog.search_edit.text()
                    self.dialog_coordinator.tag_viewer_dialog._populate_tags(search_text)
                # Update undo/redo state
                self._update_undo_redo_state()
    
    def _update_undo_redo_state(self) -> None:
        """Update undo/redo menu item states."""
        if self.current_dataset is not None and self.tag_edit_history:
            can_undo = self.tag_edit_history.can_undo(self.current_dataset)
            can_redo = self.tag_edit_history.can_redo(self.current_dataset)
            self.main_window.update_undo_redo_state(can_undo, can_redo)
        else:
            self.main_window.update_undo_redo_state(False, False)
    
    def _update_roi_list(self) -> None:
        """Update ROI list panel."""
        if self.current_dataset is not None:
            study_uid = getattr(self.current_dataset, 'StudyInstanceUID', '')
            series_uid = getattr(self.current_dataset, 'SeriesInstanceUID', '')
            # Use current slice index as instance identifier (array position)
            instance_identifier = self.current_slice_index
            self.roi_list_panel.update_roi_list(study_uid, series_uid, instance_identifier)
    
    def _setup_ui(self) -> None:
        """Set up the user interface layout."""
        # Add image viewer to center panel
        center_layout = self.main_window.center_panel.layout()
        if center_layout is None:
            from PySide6.QtWidgets import QVBoxLayout
            center_layout = QVBoxLayout(self.main_window.center_panel)
        center_layout.addWidget(self.image_viewer)
        
        # Add cine controls widget and metadata panel to left panel
        left_layout = self.main_window.left_panel.layout()
        if left_layout is None:
            from PySide6.QtWidgets import QVBoxLayout
            left_layout = QVBoxLayout(self.main_window.left_panel)
        # Add cine controls widget first (above metadata panel) with stretch 0
        left_layout.addWidget(self.cine_controls_widget, 0)
        # Add metadata panel below cine controls with stretch 1 to make it ~1.5x its current height
        left_layout.addWidget(self.metadata_panel, 1)
        
        # Add controls to right panel
        right_layout = self.main_window.right_panel.layout()
        if right_layout is None:
            from PySide6.QtWidgets import QVBoxLayout
            right_layout = QVBoxLayout(self.main_window.right_panel)
        right_layout.addWidget(self.window_level_controls)
        right_layout.addWidget(self.zoom_display_widget)
        right_layout.addWidget(self.intensity_projection_controls_widget)
        right_layout.addWidget(self.roi_list_panel)
        right_layout.addWidget(self.roi_statistics_panel)
        
        # Add series navigator to main window
        self.main_window.set_series_navigator(self.series_navigator)
    
    def _connect_signals(self) -> None:
        """Connect signals between components."""
        # File operations
        self.main_window.open_file_requested.connect(self._open_files)
        self.main_window.open_folder_requested.connect(self._open_folder)
        self.main_window.open_recent_file_requested.connect(self._open_recent_file)
        self.main_window.open_files_from_paths_requested.connect(self._open_files_from_paths)
        self.image_viewer.files_dropped.connect(self._open_files_from_paths)
        self.main_window.close_requested.connect(self._close_files)
        
        # Settings
        self.main_window.settings_requested.connect(self._open_settings)
        self.main_window.overlay_settings_requested.connect(self._open_overlay_settings)
        
        # Tag viewer
        self.main_window.tag_viewer_requested.connect(self._open_tag_viewer)
        
        # Overlay configuration
        self.main_window.overlay_config_requested.connect(self._open_overlay_config)
        
        # Annotation options
        self.main_window.annotation_options_requested.connect(self._open_annotation_options)
        self.image_viewer.annotation_options_requested.connect(self._open_annotation_options)
        
        # Quick Start Guide
        self.main_window.quick_start_guide_requested.connect(self._open_quick_start_guide)
        
        # Tag Export
        self.main_window.tag_export_requested.connect(self._open_tag_export)
        
        # Export
        self.main_window.export_requested.connect(self._open_export)
        
        # Undo/Redo tag edits
        self.main_window.undo_tag_edit_requested.connect(self._undo_tag_edit)
        self.main_window.redo_tag_edit_requested.connect(self._redo_tag_edit)
        
        # ROI drawing signals
        self.image_viewer.roi_drawing_started.connect(self.roi_coordinator.handle_roi_drawing_started)
        self.image_viewer.roi_drawing_updated.connect(self.roi_coordinator.handle_roi_drawing_updated)
        self.image_viewer.roi_drawing_finished.connect(self.roi_coordinator.handle_roi_drawing_finished)
        
        # Measurement signals
        self.image_viewer.measurement_started.connect(self.measurement_coordinator.handle_measurement_started)
        self.image_viewer.measurement_updated.connect(self.measurement_coordinator.handle_measurement_updated)
        self.image_viewer.measurement_finished.connect(self.measurement_coordinator.handle_measurement_finished)
        
        # ROI click signal
        self.image_viewer.roi_clicked.connect(self.roi_coordinator.handle_roi_clicked)
        self.image_viewer.image_clicked_no_roi.connect(self.roi_coordinator.handle_image_clicked_no_roi)
        
        # ROI delete signal (from right-click context menu)
        self.image_viewer.roi_delete_requested.connect(self.roi_coordinator.handle_roi_delete_requested)
        self.image_viewer.measurement_delete_requested.connect(self.measurement_coordinator.handle_measurement_delete_requested)
        
        # ROI statistics overlay signals
        self.image_viewer.roi_statistics_overlay_toggle_requested.connect(self.roi_coordinator.handle_roi_statistics_overlay_toggle)
        self.image_viewer.roi_statistics_selection_changed.connect(self.roi_coordinator.handle_roi_statistics_selection)
        
        # Set callback for getting ROI from item (for context menu)
        self.image_viewer.get_roi_from_item_callback = self.roi_manager.find_roi_by_item
        self.image_viewer.delete_all_rois_callback = self.roi_coordinator.delete_all_rois_current_slice
        
        # ROI list panel signals
        self.roi_list_panel.roi_selected.connect(self.roi_coordinator.handle_roi_selected)
        self.roi_list_panel.roi_deleted.connect(self.roi_coordinator.handle_roi_deleted)
        self.roi_list_panel.delete_all_requested.connect(self.roi_coordinator.delete_all_rois_current_slice)
        
        # Set ROI list panel context menu callbacks
        self.roi_list_panel.roi_delete_callback = lambda roi: self.roi_coordinator.handle_roi_delete_requested(roi.item) if roi.item else None
        self.roi_list_panel.delete_all_rois_callback = self.roi_coordinator.delete_all_rois_current_slice
        self.roi_list_panel.roi_statistics_overlay_toggle_callback = self.roi_coordinator.handle_roi_statistics_overlay_toggle
        
        def handle_statistic_toggle(roi, stat_name: str, checked: bool) -> None:
            """Handle statistic toggle from ROI list panel."""
            if checked:
                roi.visible_statistics.add(stat_name)
            else:
                roi.visible_statistics.discard(stat_name)
            self.roi_coordinator.handle_roi_statistics_selection(roi, roi.visible_statistics)
        
        self.roi_list_panel.roi_statistics_selection_callback = handle_statistic_toggle
        self.roi_list_panel.annotation_options_callback = self._open_annotation_options
        
        # Monitor ROI item changes for movement
        self.image_viewer.scene.selectionChanged.connect(self.roi_coordinator.handle_scene_selection_changed)
        
        # Scroll wheel for slice navigation
        self.image_viewer.wheel_event_for_slice.connect(
            lambda delta: self.slice_navigator.handle_wheel_event(delta)
        )
        
        # Pixel info display in status bar
        self.image_viewer.pixel_info_changed.connect(self._on_pixel_info_changed)
        
        # Set callbacks for pixel info
        self.image_viewer.set_pixel_info_callbacks(
            get_dataset=lambda: self.current_dataset,
            get_slice_index=lambda: self.current_slice_index,
            get_use_rescaled=lambda: self.view_state_manager.use_rescaled_values if self.view_state_manager else False
        )
        
        # Set callbacks for window/level presets
        def get_presets_callback():
            presets = self.view_state_manager.window_level_presets if self.view_state_manager else []
            # print(f"[DEBUG-WL-PRESETS] Main: get_presets_callback called, returning {len(presets)} preset(s)")
            return presets
        
        def get_current_index_callback():
            index = self.view_state_manager.current_preset_index if self.view_state_manager else 0
            # print(f"[DEBUG-WL-PRESETS] Main: get_current_index_callback called, returning index={index}")
            return index
        
        self.image_viewer.get_window_level_presets_callback = get_presets_callback
        self.image_viewer.get_current_preset_index_callback = get_current_index_callback
        # print(f"[DEBUG-WL-PRESETS] Main: Callbacks set for window/level presets")
        
        # Window/level
        self.window_level_controls.window_changed.connect(self.view_state_manager.handle_window_changed)
        
        # Window/Level preset selection
        self.image_viewer.window_level_preset_selected.connect(self._on_window_level_preset_selected)
        
        # Intensity projection controls
        self.intensity_projection_controls_widget.enabled_changed.connect(self._on_projection_enabled_changed)
        self.intensity_projection_controls_widget.projection_type_changed.connect(self._on_projection_type_changed)
        self.intensity_projection_controls_widget.slice_count_changed.connect(self._on_projection_slice_count_changed)
        
        # Intensity projection context menu signals
        self.image_viewer.projection_enabled_changed.connect(self._on_projection_enabled_changed)
        self.image_viewer.projection_type_changed.connect(self._on_projection_type_changed)
        self.image_viewer.projection_slice_count_changed.connect(self._on_projection_slice_count_changed)
        
        # Set callbacks for projection state (for context menu)
        self.image_viewer.get_projection_enabled_callback = lambda: self.slice_display_manager.projection_enabled
        self.image_viewer.get_projection_type_callback = lambda: self.slice_display_manager.projection_type
        self.image_viewer.get_projection_slice_count_callback = lambda: self.slice_display_manager.projection_slice_count
        
        # Slice navigation
        self.slice_navigator.slice_changed.connect(self._on_slice_changed)
        # Pause cine playback if user manually navigates slices
        self.slice_navigator.slice_changed.connect(self._on_manual_slice_navigation)
        
        # Mouse mode changes
        self.main_window.mouse_mode_changed.connect(self.mouse_mode_handler.handle_mouse_mode_changed)
        
        # Scroll wheel mode changes
        self.main_window.scroll_wheel_mode_changed.connect(self.mouse_mode_handler.handle_scroll_wheel_mode_changed)
        
        # Context menu changes (from image viewer)
        self.image_viewer.context_menu_mouse_mode_changed.connect(self.mouse_mode_handler.handle_context_menu_mouse_mode_changed)
        self.image_viewer.context_menu_scroll_wheel_mode_changed.connect(self.mouse_mode_handler.handle_context_menu_scroll_wheel_mode_changed)
        self.image_viewer.context_menu_rescale_toggle_changed.connect(self.view_state_manager.handle_rescale_toggle)
        
        # Rescale toggle from toolbar
        self.main_window.rescale_toggle_changed.connect(self.view_state_manager.handle_rescale_toggle)
        
        # Zoom changes - update overlay positions to keep text anchored
        self.image_viewer.zoom_changed.connect(self.view_state_manager.handle_zoom_changed)
        # Update zoom display widget
        self.image_viewer.zoom_changed.connect(self.zoom_display_widget.update_zoom)
        # Update status bar widget with zoom and preset info
        self.image_viewer.zoom_changed.connect(self._on_zoom_changed)
        # Zoom control from widget - update image viewer
        self.zoom_display_widget.zoom_changed.connect(self.image_viewer.set_zoom)
        
        # Transform changes (zoom/pan) - update overlay positions to keep text anchored
        # This signal fires after transform is applied, ensuring accurate viewport-to-scene mapping
        self.image_viewer.transform_changed.connect(self.view_state_manager.handle_transform_changed)
        
        # Arrow key navigation from image viewer
        self.image_viewer.arrow_key_pressed.connect(self.slice_display_manager.handle_arrow_key_pressed)
        
        # Right mouse drag for window/level adjustment
        self.image_viewer.right_mouse_press_for_drag.connect(self.view_state_manager.handle_right_mouse_press_for_drag)
        self.image_viewer.window_level_drag_changed.connect(self.view_state_manager.handle_window_level_drag)
        
        # Series navigation
        self.image_viewer.series_navigation_requested.connect(self._on_series_navigation_requested)
        self.main_window.series_navigation_requested.connect(self._on_series_navigation_requested)
        
        # Overlay font size and color changes
        self.main_window.overlay_font_size_changed.connect(self.overlay_coordinator.handle_overlay_font_size_changed)
        self.main_window.overlay_font_color_changed.connect(self.overlay_coordinator.handle_overlay_font_color_changed)
        
        # Reset view request (from toolbar and context menu)
        def handle_reset_view():
            # Reset view state only (zoom, pan, window/level)
            # Do NOT reset projection state or checkbox - leave them as user set them
            # Skip internal redisplay so we can redisplay through slice_display_manager to apply projection mode
            self.view_state_manager.reset_view(skip_redisplay=True)
            
            # Redisplay current slice to ensure projection mode (if enabled) is applied with refit
            if self.current_dataset is not None:
                self._display_slice(self.current_dataset, preserve_view_override=False)
        
        self.main_window.reset_view_requested.connect(handle_reset_view)
        self.image_viewer.reset_view_requested.connect(handle_reset_view)
        
        # Clear measurements signals
        self.main_window.clear_measurements_requested.connect(self.measurement_coordinator.handle_clear_measurements)
        self.image_viewer.clear_measurements_requested.connect(self.measurement_coordinator.handle_clear_measurements)
        
        # Toggle overlay signal
        self.image_viewer.toggle_overlay_requested.connect(self.overlay_coordinator.handle_toggle_overlay)
        
        # Viewport resize (when splitter moves)
        self.main_window.viewport_resizing.connect(self.view_state_manager.handle_viewport_resizing)
        self.main_window.viewport_resized.connect(self.view_state_manager.handle_viewport_resized)
        
        # Series navigator signals
        self.series_navigator.series_selected.connect(self._on_series_navigator_selected)
        self.image_viewer.toggle_series_navigator_requested.connect(self.main_window.toggle_series_navigator)
        
        # Tag edit signals
        self.metadata_panel.tag_edited.connect(lambda: self._update_undo_redo_state())
        
        # Cine player signals
        self.cine_player.frame_advance_requested.connect(self._on_cine_frame_advance)
        self.cine_player.playback_state_changed.connect(self._on_cine_playback_state_changed)
        
        # Cine control signals from cine controls widget
        self.cine_controls_widget.play_requested.connect(self._on_cine_play)
        self.cine_controls_widget.pause_requested.connect(self._on_cine_pause)
        self.cine_controls_widget.stop_requested.connect(self._on_cine_stop)
        self.cine_controls_widget.speed_changed.connect(self._on_cine_speed_changed)
        self.cine_controls_widget.loop_toggled.connect(self._on_cine_loop_toggled)
        self.cine_controls_widget.frame_position_changed.connect(self._on_frame_slider_changed)
        
        # Cine control signals from context menu
        self.image_viewer.cine_play_requested.connect(self._on_cine_play)
        self.image_viewer.cine_pause_requested.connect(self._on_cine_pause)
        self.image_viewer.cine_stop_requested.connect(self._on_cine_stop)
        self.image_viewer.cine_loop_toggled.connect(self._on_cine_loop_toggled)
        
        # Set callback to get cine loop state for context menu
        self.image_viewer.get_cine_loop_state_callback = self._get_cine_loop_state
    
    def _open_files(self) -> None:
        """Handle open files request."""
        datasets, studies = self.file_operations_handler.open_files()
        if datasets is not None and studies is not None:
            self.current_datasets = datasets
            self.current_studies = studies
    
    def _open_folder(self) -> None:
        """Handle open folder request."""
        datasets, studies = self.file_operations_handler.open_folder()
        if datasets is not None and studies is not None:
            self.current_datasets = datasets
            self.current_studies = studies
    
    def _open_recent_file(self, file_path: str) -> None:
        """
        Handle open recent file/folder request.
        
        Args:
            file_path: Path to file or folder to open
        """
        datasets, studies = self.file_operations_handler.open_recent_file(file_path)
        if datasets is not None and studies is not None:
            self.current_datasets = datasets
            self.current_studies = studies
    
    def _open_files_from_paths(self, paths: list[str]) -> None:
        """
        Handle open files/folders from drag-and-drop.
        
        Args:
            paths: List of file or folder paths to open
        """
        datasets, studies = self.file_operations_handler.open_paths(paths)
        if datasets is not None and studies is not None:
            self.current_datasets = datasets
            self.current_studies = studies
    
    def _on_series_navigation_requested(self, direction: int) -> None:
        """
        Handle series navigation request from image viewer.
        
        Args:
            direction: -1 for left/previous series, 1 for right/next series
        """
        new_series_uid, slice_index, dataset = self.slice_display_manager.handle_series_navigation(direction)
        if new_series_uid is not None and dataset is not None:
            self.current_series_uid = new_series_uid
            self.current_slice_index = slice_index
            
            # Reset projection state when switching series
            self.slice_display_manager.reset_projection_state()
            # Update widget to match reset state
            self.intensity_projection_controls_widget.set_enabled(False)
            self.intensity_projection_controls_widget.set_projection_type("aip")
            self.intensity_projection_controls_widget.set_slice_count(4)
            
            # Update slice display manager context
            self.slice_display_manager.set_current_data_context(
                self.current_studies,
                self.current_study_uid,
                self.current_series_uid,
                self.current_slice_index
            )
            
            # Display slice
            self.slice_display_manager.display_slice(
                dataset,
                self.current_studies,
                self.current_study_uid,
                self.current_series_uid,
                self.current_slice_index
            )
            
            # Update current dataset reference
            self.current_dataset = dataset
            
            # Update undo/redo state when dataset changes
            self._update_undo_redo_state()
            
            # Update slice navigator
            if self.current_studies and self.current_study_uid and self.current_series_uid:
                datasets = self.current_studies[self.current_study_uid][self.current_series_uid]
                self.slice_navigator.set_total_slices(len(datasets))
                self.slice_navigator.set_current_slice(slice_index)
            
            # Update series navigator highlighting
            self.series_navigator.set_current_series(self.current_series_uid)
            
            # Update cine player context and check if series is cine-capable
            self._update_cine_player_context()
        
            # Display ROIs for this slice (now handled by display_slice, but kept for compatibility)
            # self.slice_display_manager.display_rois_for_slice(dataset)
    
    def _on_series_navigator_selected(self, series_uid: str) -> None:
        """
        Handle series selection from series navigator.
        
        Args:
            series_uid: Selected series UID
        """
        if not self.current_studies or self.current_study_uid not in self.current_studies:
            return
        
        study_series = self.current_studies[self.current_study_uid]
        if series_uid not in study_series:
            return
        
        datasets = study_series[series_uid]
        if not datasets:
            return
        
        # Navigate to first slice of selected series
        self.current_series_uid = series_uid
        self.current_slice_index = 0
        self.current_dataset = datasets[0]
        
        # Reset projection state when switching series
        self.slice_display_manager.reset_projection_state()
        # Update widget to match reset state
        self.intensity_projection_controls_widget.set_enabled(False)
        self.intensity_projection_controls_widget.set_projection_type("aip")
        self.intensity_projection_controls_widget.set_slice_count(4)
        
        # Update slice display manager context
        self.slice_display_manager.set_current_data_context(
            self.current_studies,
            self.current_study_uid,
            self.current_series_uid,
            self.current_slice_index
        )
        
        # Display slice
        self.slice_display_manager.display_slice(
            self.current_dataset,
            self.current_studies,
            self.current_study_uid,
            self.current_series_uid,
            self.current_slice_index
        )
        
        # Update slice navigator
        self.slice_navigator.set_total_slices(len(datasets))
        self.slice_navigator.set_current_slice(0)
        
        # Update series navigator highlighting
        self.series_navigator.set_current_series(self.current_series_uid)
        
        # Update cine player context and check if series is cine-capable
        self._update_cine_player_context()
    
    def _display_slice(self, dataset, preserve_view_override: Optional[bool] = None) -> None:
        """
        Display a DICOM slice.
        
        Args:
            dataset: pydicom Dataset
        """
        try:
            # Update current dataset reference
            self.current_dataset = dataset
            
            # Update slice display manager context
            self.slice_display_manager.set_current_data_context(
                self.current_studies,
                self.current_study_uid,
                self.current_series_uid,
                self.current_slice_index
            )
            
            # Display slice using slice display manager
            self.slice_display_manager.display_slice(
                dataset,
                self.current_studies,
                self.current_study_uid,
                self.current_series_uid,
                self.current_slice_index,
                preserve_view_override=preserve_view_override
            )
            
            # Store initial view state if this is the first image
            if self.view_state_manager.initial_zoom is None:
                # Wait a bit for view to settle, then store initial state
                from PySide6.QtCore import QTimer
                QTimer.singleShot(100, self.view_state_manager.store_initial_view_state)
        except MemoryError as e:
            error_msg = f"Memory error displaying slice: {str(e)}"
            self.main_window.update_status(error_msg)
            # Show error dialog for memory errors
            from gui.dialogs.file_dialog import FileDialog
            file_dialog = FileDialog()
            file_dialog.show_error(
                self.main_window,
                "Memory Error",
                f"{error_msg}\n\nTry closing other applications or use a system with more memory."
            )
        except Exception as e:
            error_type = type(e).__name__
            error_msg = f"Error displaying slice: {str(e)}"
            if error_type not in error_msg:
                error_msg = f"{error_type}: {error_msg}"
            self.main_window.update_status(error_msg)
            # Log to console for debugging
            import traceback
            print(f"Error displaying slice: {error_msg}")
            traceback.print_exc()
    
    def _redisplay_current_slice(self, preserve_view: bool = True) -> None:
        """
        Redisplay the current slice via SliceDisplayManager with optional preserve_view override.
        
        Args:
            preserve_view: True to preserve zoom/pan, False to refit
        """
        if self.current_dataset is not None:
            self._display_slice(self.current_dataset, preserve_view_override=preserve_view)
    
    def _display_rois_for_slice(self, dataset) -> None:
        """
        Display ROIs for a slice.
        
        Args:
            dataset: pydicom Dataset for the current slice
        """
        self.slice_display_manager.display_rois_for_slice(dataset)
        # Check if there's a selected ROI for this slice and restore UI state
        study_uid = getattr(dataset, 'StudyInstanceUID', '')
        series_uid = getattr(dataset, 'SeriesInstanceUID', '')
        # Use current slice index as instance identifier (array position)
        instance_identifier = self.current_slice_index
        rois = self.roi_manager.get_rois_for_slice(study_uid, series_uid, instance_identifier)
        selected_roi = self.roi_manager.get_selected_roi()
        if selected_roi is not None and selected_roi in rois:
            self.roi_list_panel.select_roi_in_list(selected_roi)
            self.roi_coordinator.update_roi_statistics(selected_roi)
        else:
            self.roi_statistics_panel.clear_statistics()
    
    def _display_measurements_for_slice(self, dataset) -> None:
        """
        Display measurements for a slice.
        
        Args:
            dataset: pydicom Dataset for the current slice
        """
        self.slice_display_manager.display_measurements_for_slice(dataset)
    
    def _on_projection_enabled_changed(self, enabled: bool) -> None:
        """
        Handle projection enabled state change.
        
        This handler is called when the checkbox state changes (either user-initiated or programmatic).
        When user clicks checkbox, signal is emitted and we should update manager to match user's intent.
        When programmatically set (e.g., during reset), signals are blocked so this shouldn't be called.
        
        Args:
            enabled: True if projection mode enabled, False otherwise
        """
        # print(f"[DEBUG _on_projection_enabled_changed] Called from enabled_changed signal: enabled={enabled}, _resetting_projection_state={self._resetting_projection_state}")
        # import traceback
        # print(f"[DEBUG _on_projection_enabled_changed] Call stack:\n{''.join(traceback.format_stack()[-5:-1])}")
        
        # Check current states BEFORE updating manager
        current_widget_state = self.intensity_projection_controls_widget.get_enabled()
        current_manager_state = self.slice_display_manager.projection_enabled
        checkbox_visual_state = self.intensity_projection_controls_widget.enable_checkbox.isChecked()
        # print(f"[DEBUG _on_projection_enabled_changed] Current widget state={current_widget_state}, checkbox visual state={checkbox_visual_state}, manager state={current_manager_state}, signal enabled={enabled}")
        
        # If we're resetting and signal doesn't match manager state, sync widget to manager (ignore signal)
        if self._resetting_projection_state and current_manager_state != enabled:
            # print(f"[DEBUG _on_projection_enabled_changed] Reset in progress: ignoring signal ({enabled}), syncing widget to manager ({current_manager_state})")
            self.intensity_projection_controls_widget.set_enabled(current_manager_state)
        else:
            # Normal case: update manager state to match the signal (user's intent)
            # print(f"[DEBUG _on_projection_enabled_changed] Updating manager state to match signal ({enabled})")
            self.slice_display_manager.set_projection_enabled(enabled)
            
            # Widget state should already match signal, but verify and sync if needed
            if current_widget_state != enabled:
                # print(f"[DEBUG _on_projection_enabled_changed] Widget state ({current_widget_state}) != signal ({enabled}), syncing widget")
                self.intensity_projection_controls_widget.set_enabled(enabled)
            else:
                # print(f"[DEBUG _on_projection_enabled_changed] Widget state ({current_widget_state}) matches signal ({enabled}), no widget update needed")
                pass
        
        # Redisplay current slice with new projection state
        if self.current_dataset is not None:
            self._display_slice(self.current_dataset)
    
    def _on_projection_type_changed(self, projection_type: str) -> None:
        """
        Handle projection type change.
        
        Args:
            projection_type: "aip", "mip", or "minip"
        """
        self.slice_display_manager.set_projection_type(projection_type)
        # Update widget state
        self.intensity_projection_controls_widget.set_projection_type(projection_type)
        # Redisplay current slice with new projection type
        if self.current_dataset is not None and self.slice_display_manager.projection_enabled:
            self._display_slice(self.current_dataset)
    
    def _on_projection_slice_count_changed(self, count: int) -> None:
        """
        Handle projection slice count change.
        
        Args:
            count: Number of slices to combine (2, 3, 4, 6, or 8)
        """
        self.slice_display_manager.set_projection_slice_count(count)
        # Update widget state
        self.intensity_projection_controls_widget.set_slice_count(count)
        # Redisplay current slice with new slice count
        if self.current_dataset is not None and self.slice_display_manager.projection_enabled:
            self._display_slice(self.current_dataset)
    
    def _open_settings(self) -> None:
        """Handle settings dialog request."""
        self.dialog_coordinator.open_settings()
    
    def _open_overlay_settings(self) -> None:
        """Handle Overlay Settings dialog request."""
        self.dialog_coordinator.open_overlay_settings()
    
    def _open_tag_viewer(self) -> None:
        """Handle tag viewer dialog request."""
        self.dialog_coordinator.open_tag_viewer(self.current_dataset)
    
    def _open_overlay_config(self) -> None:
        """Handle overlay configuration dialog request."""
        # Extract modality from current dataset if available
        current_modality = None
        if self.current_dataset is not None:
            modality = getattr(self.current_dataset, 'Modality', None)
            if modality:
                # Normalize modality (strip whitespace)
                modality_str = str(modality).strip()
                # Valid modalities list (must match overlay_config_dialog.py, alphabetical order, default first)
                valid_modalities = ["default", "CR", "CT", "DX", "MG", "MR", "NM", "PT", "RF", "RT", "US", "XA"]
                if modality_str in valid_modalities:
                    current_modality = modality_str
                # If modality is not in valid list, current_modality remains None (will default to "default")
        
        self.dialog_coordinator.open_overlay_config(current_modality=current_modality)
    
    def _open_annotation_options(self) -> None:
        """Handle annotation options dialog request."""
        self.dialog_coordinator.open_annotation_options()
    
    def _open_quick_start_guide(self) -> None:
        """Handle Quick Start Guide dialog request."""
        self.dialog_coordinator.open_quick_start_guide()
    
    def _open_tag_export(self) -> None:
        """Handle Tag Export dialog request."""
        self.dialog_coordinator.open_tag_export()
    
    def _open_export(self) -> None:
        """Handle Export dialog request."""
        # Get current window/level values if available
        window_center, window_width = self.window_level_controls.get_window_level()
        # Get current rescale state to match viewer behavior
        use_rescaled_values = self.view_state_manager.use_rescaled_values
        self.dialog_coordinator.open_export(
            current_window_center=window_center,
            current_window_width=window_width,
            current_zoom=self.image_viewer.current_zoom,
            use_rescaled_values=use_rescaled_values,
            roi_manager=self.roi_manager,
            overlay_manager=self.overlay_manager,
            measurement_tool=self.measurement_tool
        )
    
    def _on_overlay_config_applied(self) -> None:
        """Handle overlay configuration being applied."""
        self.overlay_coordinator.handle_overlay_config_applied()
    
    def _on_annotation_options_applied(self) -> None:
        """Handle annotation options applied - refresh all annotations."""
        # Update default visible statistics for all existing ROIs
        default_stats_list = self.config_manager.get_roi_default_visible_statistics()
        default_stats_set = set(default_stats_list)
        
        # Update all ROIs to use new default statistics
        for key, roi_list in self.roi_manager.rois.items():
            for roi in roi_list:
                roi.visible_statistics = default_stats_set.copy()
        
        # Update ROI statistics overlays
        if self.current_dataset is not None:
            self.roi_coordinator.update_roi_statistics_overlays()
        
        # Update ROI line styles (will be done when ROIs are redrawn)
        # Update measurement styles (will be done when measurements are redrawn)
        # For now, we'll need to refresh the display
        if self.current_dataset is not None:
            self.slice_display_manager.display_rois_for_slice(self.current_dataset)
            self.slice_display_manager.display_measurements_for_slice(self.current_dataset)
    
    def _on_settings_applied(self) -> None:
        """Handle settings being applied."""
        # Update overlay manager with new settings
        font_size = self.config_manager.get_overlay_font_size()
        font_color = self.config_manager.get_overlay_font_color()
        self.overlay_manager.set_font_size(font_size)
        self.overlay_manager.set_font_color(*font_color)
        
        # Recreate overlay
        self.overlay_coordinator.handle_overlay_config_applied()
    
    def _on_window_changed(self, center: float, width: float) -> None:
        """
        Handle window/level change.
        
        Args:
            center: Window center
            width: Window width
        """
        self.view_state_manager.handle_window_changed(center, width)
    
    def _on_mouse_mode_changed(self, mode: str) -> None:
        """
        Handle mouse mode change from toolbar.
        
        Args:
            mode: Mouse mode
        """
        self.mouse_mode_handler.handle_mouse_mode_changed(mode)
    
    def _set_mouse_mode(self, mode: str) -> None:
        """
        Set mouse mode programmatically (e.g., from keyboard shortcuts).
        
        Args:
            mode: Mouse mode
        """
        self.mouse_mode_handler.set_mouse_mode(mode)
    
    def _set_roi_mode(self, mode: Optional[str]) -> None:
        """
        Set ROI drawing mode (legacy method for backward compatibility).
        
        Args:
            mode: "rectangle", "ellipse", or None
        """
        self.mouse_mode_handler.set_roi_mode(mode)
    
    def _on_roi_drawing_started(self, pos: QPointF) -> None:
        """
        Handle ROI drawing start.
        
        Args:
            pos: Starting position
        """
        self.roi_coordinator.handle_roi_drawing_started(pos)
    
    def _on_roi_drawing_updated(self, pos: QPointF) -> None:
        """
        Handle ROI drawing update.
        
        Args:
            pos: Current position
        """
        self.roi_coordinator.handle_roi_drawing_updated(pos)
    
    def _on_roi_drawing_finished(self) -> None:
        """Handle ROI drawing finish."""
        self.roi_coordinator.handle_roi_drawing_finished()
    
    def _on_roi_clicked(self, item) -> None:
        """
        Handle ROI click.
        
        Args:
            item: QGraphicsItem that was clicked
        """
        self.roi_coordinator.handle_roi_clicked(item)
    
    def _on_image_clicked_no_roi(self) -> None:
        """Handle image click when not on an ROI - deselect current ROI."""
        self.roi_coordinator.handle_image_clicked_no_roi()
    
    def _on_measurement_started(self, pos: QPointF) -> None:
        """
        Handle measurement start.
        
        Args:
            pos: Starting position
        """
        self.measurement_coordinator.handle_measurement_started(pos)
    
    def _on_measurement_updated(self, pos: QPointF) -> None:
        """
        Handle measurement update.
        
        Args:
            pos: Current position
        """
        self.measurement_coordinator.handle_measurement_updated(pos)
    
    def _on_measurement_finished(self) -> None:
        """Handle measurement finish."""
        self.measurement_coordinator.handle_measurement_finished()
    
    def _on_measurement_delete_requested(self, measurement_item) -> None:
        """
        Handle measurement deletion request from context menu.
        
        Args:
            measurement_item: MeasurementItem to delete
        """
        self.measurement_coordinator.handle_measurement_delete_requested(measurement_item)
    
    def _on_clear_measurements_requested(self) -> None:
        """
        Handle clear measurements request from toolbar or context menu.
        """
        self.measurement_coordinator.handle_clear_measurements()
    
    def _on_toggle_overlay_requested(self) -> None:
        """Handle toggle overlay request from context menu."""
        self.overlay_coordinator.handle_toggle_overlay()
    
    def _on_roi_selected(self, roi) -> None:
        """
        Handle ROI selection from list.
        
        Args:
            roi: Selected ROI item
        """
        self.roi_coordinator.handle_roi_selected(roi)
    
    def _on_roi_delete_requested(self, item) -> None:
        """
        Handle ROI deletion request from context menu.
        
        Args:
            item: QGraphicsItem to delete
        """
        self.roi_coordinator.handle_roi_delete_requested(item)
    
    def _on_roi_deleted(self, roi) -> None:
        """
        Handle ROI deletion.
        
        Args:
            roi: Deleted ROI item
        """
        self.roi_coordinator.handle_roi_deleted(roi)
    
    def _delete_all_rois_current_slice(self) -> None:
        """
        Delete all ROIs on the current slice.
        """
        self.roi_coordinator.delete_all_rois_current_slice()
    
    def _on_scroll_wheel_mode_changed(self, mode: str) -> None:
        """
        Handle scroll wheel mode change.
        
        Args:
            mode: "slice" or "zoom"
        """
        self.mouse_mode_handler.handle_scroll_wheel_mode_changed(mode)
    
    def _on_context_menu_mouse_mode_changed(self, mode: str) -> None:
        """
        Handle mouse mode change from context menu.
        
        Args:
            mode: Mouse mode string
        """
        self.mouse_mode_handler.handle_context_menu_mouse_mode_changed(mode)
    
    def _on_context_menu_scroll_wheel_mode_changed(self, mode: str) -> None:
        """
        Handle scroll wheel mode change from context menu.
        
        Args:
            mode: "slice" or "zoom"
        """
        self.mouse_mode_handler.handle_context_menu_scroll_wheel_mode_changed(mode)
    
    def _on_rescale_toggle_changed(self, checked: bool) -> None:
        """
        Handle rescale toggle change from toolbar or context menu.
        
        Args:
            checked: True to use rescaled values, False to use raw values
        """
        self.view_state_manager.handle_rescale_toggle(checked)
        # Update ROI statistics if ROI is selected and belongs to current slice
        selected_roi = self.roi_manager.get_selected_roi()
        if selected_roi is not None and self.current_dataset is not None:
            study_uid = getattr(self.current_dataset, 'StudyInstanceUID', '')
            series_uid = getattr(self.current_dataset, 'SeriesInstanceUID', '')
            # Use current slice index as instance identifier (array position)
            instance_identifier = self.current_slice_index
            current_slice_rois = self.roi_manager.get_rois_for_slice(study_uid, series_uid, instance_identifier)
            if selected_roi in current_slice_rois:
                self.roi_coordinator.update_roi_statistics(selected_roi)
            else:
                self.roi_statistics_panel.clear_statistics()
        else:
            self.roi_statistics_panel.clear_statistics()
    
    def _on_zoom_changed(self, zoom_level: float) -> None:
        """
        Handle zoom level change.
        
        Args:
            zoom_level: Current zoom level
        """
        self.view_state_manager.handle_zoom_changed(zoom_level)
        # Update status bar widget with zoom and preset info
        self._update_zoom_preset_status_bar()
    
    def _on_transform_changed(self) -> None:
        """
        Handle view transform change (zoom/pan).
        """
        self.view_state_manager.handle_transform_changed()
    
    def _on_viewport_resizing(self) -> None:
        """
        Handle viewport resize start (when splitter starts moving).
        """
        self.view_state_manager.handle_viewport_resizing()
    
    def _on_viewport_resized(self) -> None:
        """
        Handle viewport resize (when splitter moves).
        """
        self.view_state_manager.handle_viewport_resized()
    
    def _on_pixel_info_changed(self, pixel_value_str: str, x: int, y: int, z: int) -> None:
        """
        Handle pixel info changed signal from image viewer.
        
        Args:
            pixel_value_str: Formatted pixel value string
            x: X coordinate
            y: Y coordinate
            z: Z coordinate (slice index)
        """
        if pixel_value_str:
            info_text = f"Pixel: {pixel_value_str}  (x: {x}, y: {y}, z: {z})"
        else:
            info_text = f"(x: {x}, y: {y}, z: {z})" if (x > 0 or y > 0 or z > 0) else ""
        
        if hasattr(self.main_window, 'pixel_info_label'):
            self.main_window.pixel_info_label.setText(info_text)
    
    def _on_arrow_key_pressed(self, direction: int) -> None:
        """
        Handle arrow key press from image viewer.
        
        Args:
            direction: 1 for up (next slice), -1 for down (previous slice)
        """
        self.slice_display_manager.handle_arrow_key_pressed(direction)
    
    def _on_right_mouse_press_for_drag(self) -> None:
        """
        Handle right mouse press for drag - provide window/level values to image viewer.
        """
        self.view_state_manager.handle_right_mouse_press_for_drag()
    
    def _on_window_level_drag_changed(self, center_delta: float, width_delta: float) -> None:
        """
        Handle window/level drag adjustment from image viewer.
        
        Args:
            center_delta: Change in window center
            width_delta: Change in window width
        """
        self.view_state_manager.handle_window_level_drag(center_delta, width_delta)
    
    def _on_window_level_preset_selected(self, preset_index: int) -> None:
        """
        Handle window/level preset selection from context menu.
        
        Args:
            preset_index: Index of the selected preset
        """
        # print(f"[DEBUG-WL-PRESETS] Main: Preset selected: index={preset_index}")
        if self.view_state_manager and self.view_state_manager.window_level_presets:
            # print(f"[DEBUG-WL-PRESETS] Main: Found {len(self.view_state_manager.window_level_presets)} preset(s) in view_state_manager")
            if 0 <= preset_index < len(self.view_state_manager.window_level_presets):
                wc, ww, is_rescaled, preset_name = self.view_state_manager.window_level_presets[preset_index]
                # print(f"[DEBUG-WL-PRESETS] Main: Selected preset {preset_index}: center={wc}, width={ww}, is_rescaled={is_rescaled}, name={preset_name}")
                
                # Get current rescale state
                use_rescaled_values = self.view_state_manager.use_rescaled_values
                rescale_slope = self.view_state_manager.rescale_slope
                rescale_intercept = self.view_state_manager.rescale_intercept
                
                # Convert if needed based on current rescale state
                if is_rescaled and not use_rescaled_values:
                    if (rescale_slope is not None and rescale_intercept is not None and rescale_slope != 0.0):
                        orig_wc, orig_ww = wc, ww
                        wc, ww = self.dicom_processor.convert_window_level_rescaled_to_raw(
                            wc, ww, rescale_slope, rescale_intercept
                        )
                        # print(f"[DEBUG-WL-PRESETS] Main: Converted rescaled->raw: ({orig_wc}, {orig_ww}) -> ({wc}, {ww})")
                elif not is_rescaled and use_rescaled_values:
                    if (rescale_slope is not None and rescale_intercept is not None):
                        orig_wc, orig_ww = wc, ww
                        wc, ww = self.dicom_processor.convert_window_level_raw_to_rescaled(
                            wc, ww, rescale_slope, rescale_intercept
                        )
                        # print(f"[DEBUG-WL-PRESETS] Main: Converted raw->rescaled: ({orig_wc}, {orig_ww}) -> ({wc}, {ww})")
                
                # Update preset index
                self.view_state_manager.current_preset_index = preset_index
                # print(f"[DEBUG-WL-PRESETS] Main: Updated current_preset_index to {preset_index}")
                
                # Set window/level
                self.window_level_controls.set_window_level(wc, ww, block_signals=False)
                
                # Update status bar widget
                current_zoom = self.image_viewer.current_zoom
                preset_display_name = preset_name if preset_name else "Default"
                self.main_window.update_zoom_preset_status(current_zoom, preset_display_name)
                
                # Reset user-modified flag since we're using a preset
                self.view_state_manager.window_level_user_modified = False
    
    def _update_zoom_preset_status_bar(self) -> None:
        """
        Update the zoom and preset status bar widget.
        Gets current zoom and preset info from view_state_manager.
        """
        current_zoom = self.image_viewer.current_zoom
        preset_name = None
        
        # Check if presets exist and user hasn't manually modified window/level
        if (self.view_state_manager.window_level_presets and 
            not self.view_state_manager.window_level_user_modified):
            # Get preset name from current preset index
            preset_index = self.view_state_manager.current_preset_index
            if 0 <= preset_index < len(self.view_state_manager.window_level_presets):
                _, _, _, name = self.view_state_manager.window_level_presets[preset_index]
                preset_name = name if name else "Default"
        
        self.main_window.update_zoom_preset_status(current_zoom, preset_name)
    
    def _on_overlay_font_size_changed(self, font_size: int) -> None:
        """
        Handle overlay font size change from toolbar.
        
        Args:
            font_size: New font size in points
        """
        self.overlay_coordinator.handle_overlay_font_size_changed(font_size)
    
    def _on_overlay_font_color_changed(self, r: int, g: int, b: int) -> None:
        """
        Handle overlay font color change from toolbar.
        
        Args:
            r: Red component (0-255)
            g: Green component (0-255)
            b: Blue component (0-255)
        """
        self.overlay_coordinator.handle_overlay_font_color_changed(r, g, b)
    
    def _on_scene_selection_changed(self) -> None:
        """Handle scene selection change (e.g., when ROI is moved)."""
        self.roi_coordinator.handle_scene_selection_changed()
    
    def _update_roi_statistics(self, roi) -> None:
        """
        Update statistics panel for a ROI.
        
        Args:
            roi: ROI item
        """
        self.roi_coordinator.update_roi_statistics(roi)
    
    def _on_slice_changed(self, slice_index: int) -> None:
        """
        Handle slice index change.
        
        Args:
            slice_index: New slice index
        """
        # print(f"[ROI DEBUG] _on_slice_changed called with slice_index={slice_index}")
        # print(f"[ROI DEBUG] BEFORE update: self.current_slice_index={self.current_slice_index}")
        # Update current slice index FIRST before any operations that might use it
        self.current_slice_index = slice_index
        # Update current dataset reference
        if self.current_studies and self.current_series_uid:
            datasets = self.current_studies[self.current_study_uid][self.current_series_uid]
            if 0 <= slice_index < len(datasets):
                self.current_dataset = datasets[slice_index]
        # print(f"[ROI DEBUG] AFTER update: self.current_slice_index={self.current_slice_index}")
        # Now handle the slice change - at this point self.current_slice_index is correct
        self.slice_display_manager.handle_slice_changed(slice_index)
        
        # Update frame slider position
        total_slices = self.slice_navigator.total_slices
        if total_slices > 0:
            self.cine_controls_widget.update_frame_position(slice_index, total_slices)
    
    def _on_manual_slice_navigation(self, slice_index: int) -> None:
        """
        Handle manual slice navigation (pause cine if playing).
        
        Args:
            slice_index: New slice index
        """
        # Pause cine playback if user manually navigates during playback
        # Check if this navigation is from cine player using the flag
        if self.cine_player.is_playback_active() and not self.cine_player.is_cine_advancing():
            # This is manual navigation, pause playback
            self.cine_player.pause_playback()
    
    def _update_cine_player_context(self) -> None:
        """Update cine player context and enable/disable controls based on series capability."""
        # Update cine player series context
        self.cine_player.set_series_context(
            self.current_studies,
            self.current_study_uid,
            self.current_series_uid
        )
        
        # Check if current series is cine-capable
        is_cine_capable = self.cine_player.is_cine_capable(
            self.current_studies,
            self.current_study_uid,
            self.current_series_uid
        )
        
        # Enable/disable cine controls
        self.cine_controls_widget.set_controls_enabled(is_cine_capable)
        # Also enable/disable cine controls in context menu
        self.image_viewer.set_cine_controls_enabled(is_cine_capable)
        
        # Update frame slider with current frame and total frames
        if is_cine_capable:
            total_slices = self.slice_navigator.total_slices
            current_slice = self.current_slice_index
            self.cine_controls_widget.update_frame_position(current_slice, total_slices)
        else:
            # Reset slider when not cine-capable
            self.cine_controls_widget.update_frame_position(0, 0)
        
        # If not cine-capable, stop any active playback
        if not is_cine_capable and self.cine_player.is_playback_active():
            self.cine_player.stop_playback()
    
    def _on_cine_frame_advance(self, frame_index: int) -> None:
        """
        Handle frame advancement request from cine player.
        
        Args:
            frame_index: Frame index to advance to
        """
        # Use slice navigator's advance_to_frame with loop support
        loop_enabled = self.cine_player.loop_enabled
        self.slice_navigator.advance_to_frame(frame_index, loop=loop_enabled)
        # Reset the cine advancing flag after frame advance
        self.cine_player.reset_cine_advancing_flag()
    
    def _on_cine_playback_state_changed(self, is_playing: bool) -> None:
        """
        Handle cine playback state change.
        
        Args:
            is_playing: True if playing, False if paused/stopped
        """
        self.cine_controls_widget.update_playback_state(is_playing)
        # Update FPS display
        fps = self.cine_player.get_effective_frame_rate()
        self.cine_controls_widget.update_fps_display(fps)
    
    def _on_cine_play(self) -> None:
        """Handle cine play request."""
        if self.current_dataset is not None:
            # Try to extract frame rate from current dataset
            frame_rate = self.cine_player.get_frame_rate_from_dicom(self.current_dataset)
            self.cine_player.start_playback(frame_rate=frame_rate, dataset=self.current_dataset)
            # Update FPS display
            fps = self.cine_player.get_effective_frame_rate()
            self.cine_controls_widget.update_fps_display(fps)
    
    def _on_cine_pause(self) -> None:
        """Handle cine pause request."""
        self.cine_player.pause_playback()
    
    def _on_cine_stop(self) -> None:
        """Handle cine stop request."""
        self.cine_player.stop_playback()
    
    def _on_cine_speed_changed(self, speed_multiplier: float) -> None:
        """
        Handle cine speed change.
        
        Args:
            speed_multiplier: Speed multiplier
        """
        self.cine_player.set_speed(speed_multiplier)
        # Update FPS display
        fps = self.cine_player.get_effective_frame_rate()
        self.cine_controls_widget.update_fps_display(fps)
    
    def _on_cine_loop_toggled(self, enabled: bool) -> None:
        """
        Handle cine loop toggle.
        
        Args:
            enabled: True to enable looping, False to disable
        """
        self.cine_player.set_loop(enabled)
        # Update UI to reflect loop state
        self.cine_controls_widget.set_loop(enabled)
        # Save loop state to config so it persists between sessions
        self.config_manager.set_cine_default_loop(enabled)
    
    def _get_cine_loop_state(self) -> bool:
        """
        Get current cine loop state for context menu.
        
        Returns:
            True if loop is enabled, False otherwise
        """
        return self.cine_player.loop_enabled
    
    def _on_frame_slider_changed(self, frame_index: int) -> None:
        """
        Handle frame slider value change (user manually dragged slider).
        
        Args:
            frame_index: Frame index to navigate to (0-based)
        """
        # Pause playback if currently playing (user is manually navigating)
        if self.cine_player.is_playback_active():
            self.cine_player.pause_playback()
        
        # Navigate to the selected frame
        total_slices = self.slice_navigator.total_slices
        if 0 <= frame_index < total_slices:
            self.slice_navigator.set_current_slice(frame_index)
    
    def _hide_measurement_labels(self, hide: bool) -> None:
        """
        Hide or show measurement labels.
        
        Args:
            hide: True to hide labels, False to show them
        """
        self.measurement_coordinator.hide_measurement_labels(hide)
    
    def _hide_roi_labels(self, hide: bool) -> None:
        """
        Hide or show ROI labels.
        
        Args:
            hide: True to hide labels, False to show them
        """
        self.overlay_coordinator.hide_roi_labels(hide)
    
    def _hide_measurement_graphics(self, hide: bool) -> None:
        """
        Hide or show measurement graphics (lines and handles).
        
        Args:
            hide: True to hide graphics, False to show them
        """
        self.measurement_coordinator.hide_measurement_graphics(hide)
    
    def _hide_roi_graphics(self, hide: bool) -> None:
        """
        Hide or show ROI graphics (shapes).
        
        Args:
            hide: True to hide graphics, False to show them
        """
        self.overlay_coordinator.hide_roi_graphics(hide)
    
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
        if isinstance(event, QKeyEvent):
            return self.keyboard_event_handler.handle_key_event(event)
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


def exception_hook(exctype, value, tb):
    """Global exception handler to catch unhandled exceptions."""
    import traceback
    error_msg = ''.join(traceback.format_exception(exctype, value, tb))
    print(f"Unhandled exception:\n{error_msg}")
    
    # Try to show error dialog if QApplication exists
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
        if QApplication.instance():
            QMessageBox.critical(
                None, 
                "Fatal Error", 
                f"An unexpected error occurred:\n\n{exctype.__name__}: {value}\n\nThe application may be unstable."
            )
    except:
        pass  # If Qt is not available, just print


def main():
    """Main entry point."""
    # Install global exception hook
    sys.excepthook = exception_hook
    
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


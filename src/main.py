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
import time
import inspect
import warnings
from pathlib import Path

# Add src directory to path
src_dir = Path(__file__).parent
sys.path.insert(0, str(src_dir))

from PySide6.QtWidgets import QApplication, QMessageBox, QStyleFactory, QFileDialog
from PySide6.QtCore import Qt, QPointF, QObject, QTimer, QRectF, QSize
from PySide6.QtGui import QKeyEvent
from typing import Optional, Dict, List, Tuple
import pydicom
from pydicom.dataset import Dataset

from gui.main_window import MainWindow
from gui.dialogs.file_dialog import FileDialog
from gui.dialogs.settings_dialog import SettingsDialog
from gui.dialogs.tag_viewer_dialog import TagViewerDialog
from gui.dialogs.overlay_config_dialog import OverlayConfigDialog
from gui.dialogs.annotation_options_dialog import AnnotationOptionsDialog
from gui.image_viewer import ImageViewer
from gui.multi_window_layout import MultiWindowLayout
from gui.sub_window_container import SubWindowContainer
from gui.metadata_panel import MetadataPanel
from gui.window_level_controls import WindowLevelControls
from gui.roi_statistics_panel import ROIStatisticsPanel
from gui.roi_list_panel import ROIListPanel
from utils.undo_redo import UndoRedoManager
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
from utils.dicom_utils import get_composite_series_key
from tools.roi_manager import ROIManager
from tools.measurement_tool import MeasurementTool
from tools.crosshair_manager import CrosshairManager
from tools.annotation_manager import AnnotationManager
from tools.histogram_widget import HistogramWidget
from gui.overlay_manager import OverlayManager
from utils.annotation_clipboard import AnnotationClipboard

# Import handler classes
from core.view_state_manager import ViewStateManager
from core.file_operations_handler import FileOperationsHandler
from core.slice_display_manager import SliceDisplayManager
from gui.roi_coordinator import ROICoordinator
from gui.measurement_coordinator import MeasurementCoordinator
from gui.crosshair_coordinator import CrosshairCoordinator
from gui.overlay_coordinator import OverlayCoordinator
from gui.dialog_coordinator import DialogCoordinator
from gui.mouse_mode_handler import MouseModeHandler
from gui.keyboard_event_handler import KeyboardEventHandler

# Import fusion components
from core.fusion_handler import FusionHandler
from core.fusion_processor import FusionProcessor
from gui.fusion_controls_widget import FusionControlsWidget
from gui.fusion_coordinator import FusionCoordinator


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
        self.undo_redo_manager = UndoRedoManager(max_history=100)
        self.annotation_clipboard = AnnotationClipboard()
        
        # Privacy view state
        self.privacy_view_enabled: bool = self.config_manager.get_privacy_view()
        
        # Track which studies have already shown fusion notification
        # Set of study UIDs that have been notified about compatible fusion series
        self._fusion_notified_studies: set = set()
        
        # Create main window
        self.main_window = MainWindow(self.config_manager)
        
        # Install event filter on main window for key events
        self.main_window.installEventFilter(self)
        
        # Create components
        self.file_dialog = FileDialog(self.config_manager)
        
        # Create multi-window layout instead of single image viewer
        self.multi_window_layout = MultiWindowLayout(config_manager=self.config_manager)
        
        # Get initial layout from config
        initial_layout = self.config_manager.get_multi_window_layout()
        self.multi_window_layout.set_layout(initial_layout)
        # Update menu checkmarks to reflect the actual layout (defaults to "1x1" if no config exists)
        self.main_window.set_layout_mode(initial_layout)
        
        # For backward compatibility, keep image_viewer reference pointing to first subwindow's viewer
        # This will be updated when subwindows are created
        self.image_viewer: Optional[ImageViewer] = None
        
        # Per-subwindow managers (will be created dynamically)
        # Structure: {subwindow_index: {manager_name: manager_instance}}
        self.subwindow_managers: Dict[int, Dict] = {}
        
        # Currently focused subwindow index
        self.focused_subwindow_index: int = 0
        
        # Set image viewer reference in main window for theme updates (will be updated)
        self.main_window.image_viewer = None  # Will be set after subwindows are created
        # Apply theme again to set background color
        self.main_window._apply_theme()
        self.metadata_panel = MetadataPanel(config_manager=self.config_manager,
                                            undo_redo_manager=self.undo_redo_manager)
        self.metadata_panel.set_history_manager(self.tag_edit_history)
        self.metadata_panel.ui_refresh_callback = self._refresh_tag_ui
        # Set undo/redo callbacks
        self.metadata_panel.set_undo_redo_callbacks(
            lambda: self._undo_tag_edit(),
            lambda: self._redo_tag_edit(),
            lambda: self.tag_edit_history.can_undo(self.current_dataset) if self.current_dataset and self.tag_edit_history else False,
            lambda: self.tag_edit_history.can_redo(self.current_dataset) if self.current_dataset and self.tag_edit_history else False
        )
        # Initialize privacy mode
        self.metadata_panel.set_privacy_mode(self.privacy_view_enabled)
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
        # Flag to prevent concurrent series navigation operations
        self._series_navigation_in_progress = False
        self.roi_list_panel.set_roi_manager(self.roi_manager)
        self.series_navigator = SeriesNavigator(self.dicom_processor)
        self.cine_controls_widget = CineControlsWidget()
        self.intensity_projection_controls_widget = IntensityProjectionControlsWidget()
        
        # Initialize fusion components
        # Note: FusionHandler is now created per-subwindow, not shared
        self.fusion_processor = FusionProcessor()
        self.fusion_controls_widget = FusionControlsWidget(config_manager=self.config_manager)
        
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
        # Initialize privacy mode
        self.overlay_manager.set_privacy_mode(self.privacy_view_enabled)
        
        # Set scroll wheel mode (will be applied to subwindows after creation)
        scroll_mode = self.config_manager.get_scroll_wheel_mode()
        self.slice_navigator.set_scroll_wheel_mode(scroll_mode)
        
        # Set up UI layout
        self._setup_ui()
        
        # Initialize subwindow data structure (needed by _initialize_subwindow_managers)
        # Structure: {subwindow_index: {current_dataset, current_slice_index, current_series_uid, current_study_uid}}
        self.subwindow_data: Dict[int, Dict] = {}
        
        # Initialize per-subwindow managers for all subwindows
        self._initialize_subwindow_managers()
        
        # Initialize privacy view state on all image viewers
        subwindows = self.multi_window_layout.get_all_subwindows()
        for subwindow in subwindows:
            if subwindow and subwindow.image_viewer:
                subwindow.image_viewer.set_privacy_view_state(self.privacy_view_enabled)
        
        # Ensure focused subwindow has managers and update references
        # This must happen before _initialize_handlers() which needs these references
        # print(f"DEBUG: Setting up focused subwindow references")
        # print(f"DEBUG: subwindow_managers keys: {list(self.subwindow_managers.keys())}")
        
        focused_subwindow = self.multi_window_layout.get_focused_subwindow()
        # print(f"DEBUG: Focused subwindow: {focused_subwindow}")
        
        if focused_subwindow:
            subwindows = self.multi_window_layout.get_all_subwindows()
            # print(f"DEBUG: Focused subwindow in subwindows list: {focused_subwindow in subwindows}")
            if focused_subwindow in subwindows:
                focused_idx = subwindows.index(focused_subwindow)
                # print(f"DEBUG: Focused subwindow index: {focused_idx}")
                # print(f"DEBUG: Index in managers: {focused_idx in self.subwindow_managers}")
                if focused_idx in self.subwindow_managers:
                    # Update references immediately so _initialize_handlers() can use them
                    # print(f"DEBUG: Calling _update_focused_subwindow_references()")
                    self._update_focused_subwindow_references()
        
        # If still no managers set, ensure at least the first subwindow's managers are used
        if not hasattr(self, 'roi_coordinator') or self.roi_coordinator is None:
            # print(f"DEBUG: roi_coordinator not set, using fallback")
            subwindows = self.multi_window_layout.get_all_subwindows()
            # print(f"DEBUG: Fallback - subwindows count: {len(subwindows) if subwindows else 0}")
            # print(f"DEBUG: Fallback - has index 0: {0 in self.subwindow_managers if self.subwindow_managers else False}")
            if subwindows and 0 in self.subwindow_managers:
                # Use first subwindow's managers as fallback
                # print(f"DEBUG: Using first subwindow's managers as fallback")
                managers = self.subwindow_managers[0]
                self.view_state_manager = managers['view_state_manager']
                self.slice_display_manager = managers['slice_display_manager']
                self.roi_coordinator = managers['roi_coordinator']
                self.measurement_coordinator = managers['measurement_coordinator']
                self.text_annotation_coordinator = managers.get('text_annotation_coordinator')
                self.arrow_annotation_coordinator = managers.get('arrow_annotation_coordinator')
                self.crosshair_coordinator = managers.get('crosshair_coordinator')
                self.overlay_coordinator = managers['overlay_coordinator']
                self.roi_manager = managers['roi_manager']
                self.measurement_tool = managers['measurement_tool']
                self.text_annotation_tool = managers.get('text_annotation_tool')
                self.arrow_annotation_tool = managers.get('arrow_annotation_tool')
                self.crosshair_manager = managers.get('crosshair_manager')
                self.overlay_manager = managers['overlay_manager']
                if subwindows[0]:
                    self.image_viewer = subwindows[0].image_viewer
                    self.main_window.image_viewer = self.image_viewer
                # print(f"DEBUG: Fallback managers set successfully")
            else:
                # print(f"DEBUG: Fallback failed - no subwindows or no managers at index 0")
                pass
        
        # print(f"DEBUG: Final check - has roi_coordinator: {hasattr(self, 'roi_coordinator')}")
        if hasattr(self, 'roi_coordinator'):
            # print(f"DEBUG: roi_coordinator is None: {self.roi_coordinator is None}")
            pass
        
        # Legacy current data (for backward compatibility, points to focused subwindow)
        self.current_datasets: list = []
        self.current_studies: dict = {}
        self.current_slice_index = 0
        self.current_series_uid = ""
        self.current_study_uid = ""
        self.current_dataset: Optional[Dataset] = None
        
        # Initialize handler classes (will use focused subwindow's managers)
        self._initialize_handlers()
        
        # Connect signals
        self._connect_signals()
        
        # Initialize pan mode on all subwindows
        for subwindow in self.multi_window_layout.get_all_subwindows():
            if subwindow:
                subwindow.image_viewer.set_mouse_mode("pan")
    
    def _initialize_subwindow_managers(self) -> None:
        """Initialize managers for each subwindow."""
        subwindows = self.multi_window_layout.get_all_subwindows()
        
        # Debug output
        # print(f"DEBUG: _initialize_subwindow_managers called")
        # print(f"DEBUG: Subwindows count from get_all_subwindows(): {len(subwindows)}")
        # print(f"DEBUG: Current layout mode: {self.multi_window_layout.get_layout_mode()}")
        
        # Ensure we have at least one subwindow - force creation if needed
        if not subwindows:
            # print("DEBUG: No subwindows found, forcing creation of 1x1 layout")
            # Force creation of at least one subwindow
            self.multi_window_layout.set_layout("1x1")
            subwindows = self.multi_window_layout.get_all_subwindows()
            # print(f"DEBUG: After forcing layout, subwindows count: {len(subwindows)}")
            if not subwindows:
                raise RuntimeError("Failed to create subwindows. Cannot initialize managers.")
        
        # print(f"DEBUG: Creating managers for {len(subwindows)} subwindows")
        
        for idx, subwindow in enumerate(subwindows):
            if subwindow is None:
                # print(f"DEBUG: Skipping None subwindow at index {idx}")
                continue
            
            # print(f"DEBUG: Creating managers for subwindow {idx}")
            
            image_viewer = subwindow.image_viewer
            
            # Set scroll wheel mode
            scroll_mode = self.config_manager.get_scroll_wheel_mode()
            image_viewer.set_scroll_wheel_mode(scroll_mode)
            
            # Create managers for this subwindow
            managers = {}
            
            # ROI Manager
            managers['roi_manager'] = ROIManager(config_manager=self.config_manager)
            
            # Measurement Tool
            managers['measurement_tool'] = MeasurementTool(config_manager=self.config_manager)
            
            # Text Annotation Tool
            from tools.text_annotation_tool import TextAnnotationTool
            managers['text_annotation_tool'] = TextAnnotationTool(config_manager=self.config_manager)
            
            # Arrow Annotation Tool
            from tools.arrow_annotation_tool import ArrowAnnotationTool
            managers['arrow_annotation_tool'] = ArrowAnnotationTool(config_manager=self.config_manager)
            
            # Crosshair Manager
            managers['crosshair_manager'] = CrosshairManager(config_manager=self.config_manager)
            managers['crosshair_manager'].set_privacy_mode(self.privacy_view_enabled)
            
            # Overlay Manager (shared config, but per-window items)
            font_size = self.config_manager.get_overlay_font_size()
            font_color = self.config_manager.get_overlay_font_color()
            managers['overlay_manager'] = OverlayManager(
                font_size=font_size,
                font_color=font_color,
                config_manager=self.config_manager
            )
            # Initialize privacy mode
            managers['overlay_manager'].set_privacy_mode(self.privacy_view_enabled)
            
            # View State Manager
            managers['view_state_manager'] = ViewStateManager(
                self.dicom_processor,
                image_viewer,
                self.window_level_controls,  # Will be updated per subwindow later
                self.main_window,
                managers['overlay_manager'],
                overlay_coordinator=None,  # Will be set later
                roi_coordinator=None,  # Will be set later
                display_rois_for_slice=None  # Will be set later
            )
            
            # Slice Display Manager
            managers['slice_display_manager'] = SliceDisplayManager(
                self.dicom_processor,
                image_viewer,
                self.metadata_panel,  # Shared metadata panel
                self.slice_navigator,  # Shared slice navigator
                self.window_level_controls,  # Will be coordinated per subwindow
                managers['roi_manager'],
                managers['measurement_tool'],
                overlay_manager=managers['overlay_manager'],
                view_state_manager=managers['view_state_manager'],
                text_annotation_tool=managers.get('text_annotation_tool'),
                arrow_annotation_tool=managers.get('arrow_annotation_tool'),
                update_tag_viewer_callback=self._update_tag_viewer,
                display_rois_callback=None,
                display_measurements_callback=None,
                roi_list_panel=self.roi_list_panel,  # Shared, will be updated per focus
                roi_statistics_panel=self.roi_statistics_panel,  # Shared, will be updated per focus
                update_roi_statistics_overlays_callback=None,
                annotation_manager=self.annotation_manager,
                dicom_organizer=self.dicom_organizer
            )
            
            # ROI Coordinator
            # Crosshair Coordinator (created before ROI coordinator so it can be passed)
            managers['crosshair_coordinator'] = CrosshairCoordinator(
                managers['crosshair_manager'],
                image_viewer,
                get_current_dataset=lambda idx=idx: self._get_subwindow_dataset(idx),
                get_current_slice_index=lambda idx=idx: self._get_subwindow_slice_index(idx),
                undo_redo_manager=self.undo_redo_manager,
                update_undo_redo_state_callback=self._update_undo_redo_state,
                get_use_rescaled_values=lambda idx=idx: (managers['view_state_manager'].use_rescaled_values if managers['view_state_manager'] else False)
            )
            
            managers['roi_coordinator'] = ROICoordinator(
                managers['roi_manager'],
                self.roi_list_panel,  # Shared, will be updated per focus
                self.roi_statistics_panel,  # Shared, will be updated per focus
                image_viewer,
                self.dicom_processor,
                self.window_level_controls,  # Will be coordinated per subwindow
                self.main_window,
                get_current_dataset=lambda idx=idx: self._get_subwindow_dataset(idx),
                get_current_slice_index=lambda idx=idx: self._get_subwindow_slice_index(idx),
                get_rescale_params=self._get_rescale_params,
                set_mouse_mode_callback=self._set_mouse_mode_via_handler,
                get_projection_enabled=lambda idx=idx: (self._get_subwindow_slice_display_manager(idx).projection_enabled if self._get_subwindow_slice_display_manager(idx) else False),
                get_projection_type=lambda idx=idx: (self._get_subwindow_slice_display_manager(idx).projection_type if self._get_subwindow_slice_display_manager(idx) else "aip"),
                get_projection_slice_count=lambda idx=idx: (self._get_subwindow_slice_display_manager(idx).projection_slice_count if self._get_subwindow_slice_display_manager(idx) else 4),
                get_current_studies=lambda: self.current_studies,
                undo_redo_manager=self.undo_redo_manager,
                update_undo_redo_state_callback=self._update_undo_redo_state,
                crosshair_coordinator=managers['crosshair_coordinator']
            )
            
            # Measurement Coordinator
            managers['measurement_coordinator'] = MeasurementCoordinator(
                managers['measurement_tool'],
                image_viewer,
                get_current_dataset=lambda idx=idx: self._get_subwindow_dataset(idx),
                get_current_slice_index=lambda idx=idx: self._get_subwindow_slice_index(idx),
                undo_redo_manager=self.undo_redo_manager,
                update_undo_redo_state_callback=self._update_undo_redo_state
            )
            
            # Text Annotation Coordinator
            from gui.text_annotation_coordinator import TextAnnotationCoordinator
            managers['text_annotation_coordinator'] = TextAnnotationCoordinator(
                managers['text_annotation_tool'],
                image_viewer,
                get_current_dataset=lambda idx=idx: self._get_subwindow_dataset(idx),
                get_current_slice_index=lambda idx=idx: self._get_subwindow_slice_index(idx),
                undo_redo_manager=self.undo_redo_manager,
                update_undo_redo_state_callback=self._update_undo_redo_state
            )
            
            # Arrow Annotation Coordinator
            from gui.arrow_annotation_coordinator import ArrowAnnotationCoordinator
            managers['arrow_annotation_coordinator'] = ArrowAnnotationCoordinator(
                managers['arrow_annotation_tool'],
                image_viewer,
                get_current_dataset=lambda idx=idx: self._get_subwindow_dataset(idx),
                get_current_slice_index=lambda idx=idx: self._get_subwindow_slice_index(idx),
                undo_redo_manager=self.undo_redo_manager,
                update_undo_redo_state_callback=self._update_undo_redo_state
            )
            
            # Overlay Coordinator
            managers['overlay_coordinator'] = OverlayCoordinator(
                managers['overlay_manager'],
                image_viewer,
                get_current_dataset=lambda idx=idx: self._get_subwindow_dataset(idx),
                get_current_studies=lambda: self.current_studies,
                get_current_study_uid=lambda idx=idx: self._get_subwindow_study_uid(idx),
                get_current_series_uid=lambda idx=idx: self._get_subwindow_series_uid(idx),
                get_current_slice_index=lambda idx=idx: self._get_subwindow_slice_index(idx),
                hide_measurement_labels=managers['measurement_coordinator'].hide_measurement_labels,
                hide_measurement_graphics=managers['measurement_coordinator'].hide_measurement_graphics,
                hide_roi_graphics=managers['roi_coordinator'].hide_roi_graphics if hasattr(managers['roi_coordinator'], 'hide_roi_graphics') else None,
                hide_roi_statistics_overlays=managers['roi_coordinator'].hide_roi_statistics_overlays
            )
            
            # Fusion Handler (per-subwindow)
            managers['fusion_handler'] = FusionHandler()
            
            # Fusion Coordinator
            managers['fusion_coordinator'] = FusionCoordinator(
                managers['fusion_handler'],
                self.fusion_processor,
                self.fusion_controls_widget,
                get_current_studies=lambda: self.current_studies,
                get_current_study_uid=lambda: self.current_study_uid,
                get_current_series_uid=lambda: self.current_series_uid,
                get_current_slice_index=lambda: self.current_slice_index,
                request_display_update=lambda idx=idx: self._redisplay_subwindow_slice(idx, preserve_view=True),
                # Add callbacks for notification tracking
                check_notification_shown=lambda uid: self.has_shown_fusion_notification(uid),
                mark_notification_shown=lambda uid: self.mark_fusion_notification_shown(uid)
            )
            
            # Update slice display manager with fusion coordinator
            managers['slice_display_manager'].fusion_coordinator = managers['fusion_coordinator']
            
            # Update view state manager callbacks
            managers['view_state_manager'].overlay_coordinator = managers['overlay_coordinator'].handle_overlay_config_applied
            managers['view_state_manager'].roi_coordinator = lambda dataset: managers['roi_coordinator'].update_roi_statistics(
                managers['roi_manager'].get_selected_roi()
            ) if managers['roi_manager'].get_selected_roi() else None
            managers['view_state_manager'].display_rois_for_slice = lambda preserve_view=False: self._display_rois_for_subwindow(idx, preserve_view)
            managers['view_state_manager'].set_redisplay_slice_callback(lambda preserve_view=False: self._redisplay_subwindow_slice(idx, preserve_view))
            managers['view_state_manager'].set_series_navigator(self.series_navigator)
            
            # Update slice display manager callbacks
            managers['slice_display_manager'].update_roi_statistics_overlays_callback = managers['roi_coordinator'].update_roi_statistics_overlays
            
            # Connect inversion callback
            def on_inversion_state_changed(inverted: bool, idx=idx) -> None:
                if managers['view_state_manager'].current_series_identifier:
                    managers['view_state_manager'].set_series_inversion_state(
                        managers['view_state_manager'].current_series_identifier,
                        inverted
                    )
            image_viewer.inversion_state_changed_callback = on_inversion_state_changed
            
            # Store managers
            self.subwindow_managers[idx] = managers
            # print(f"DEBUG: Stored managers for subwindow {idx}")
            
            # Initialize subwindow data
            self.subwindow_data[idx] = {
                'current_dataset': None,
                'current_slice_index': 0,
                'current_series_uid': '',
                'current_study_uid': '',
                'current_datasets': []
            }
        
        # print(f"DEBUG: _initialize_subwindow_managers complete. Total managers created: {len(self.subwindow_managers)}")
        
        # Connect transform/zoom signals for all subwindows to their own ViewStateManager
        # This ensures overlays update correctly when panning/zooming in any subwindow
        self._connect_all_subwindow_transform_signals()
        
        # Note: Context menu signals will be connected after mouse_mode_handler is created
        # See _connect_all_subwindow_context_menu_signals() called from _initialize_handlers()
    
    def _create_managers_for_subwindow(self, idx: int, subwindow: SubWindowContainer) -> None:
        """Create managers for a specific subwindow."""
        if subwindow is None:
            return
        
        # print(f"DEBUG: Creating managers for subwindow {idx}")
        
        image_viewer = subwindow.image_viewer
        
        # Set scroll wheel mode
        scroll_mode = self.config_manager.get_scroll_wheel_mode()
        image_viewer.set_scroll_wheel_mode(scroll_mode)
        
        # Create managers for this subwindow
        managers = {}
        
        # ROI Manager
        managers['roi_manager'] = ROIManager(config_manager=self.config_manager)
        
        # Measurement Tool
        managers['measurement_tool'] = MeasurementTool(config_manager=self.config_manager)
        
        # Text Annotation Tool
        from tools.text_annotation_tool import TextAnnotationTool
        managers['text_annotation_tool'] = TextAnnotationTool(config_manager=self.config_manager)
        
        # Arrow Annotation Tool
        from tools.arrow_annotation_tool import ArrowAnnotationTool
        managers['arrow_annotation_tool'] = ArrowAnnotationTool(config_manager=self.config_manager)
        
        # Overlay Manager (shared config, but per-window items)
        font_size = self.config_manager.get_overlay_font_size()
        font_color = self.config_manager.get_overlay_font_color()
        managers['overlay_manager'] = OverlayManager(
            font_size=font_size,
            font_color=font_color,
            config_manager=self.config_manager
        )
        # Initialize privacy mode
        managers['overlay_manager'].set_privacy_mode(self.privacy_view_enabled)
        
        # View State Manager
        managers['view_state_manager'] = ViewStateManager(
            self.dicom_processor,
            image_viewer,
            self.window_level_controls,
            self.main_window,
            managers['overlay_manager'],
            overlay_coordinator=None,
            roi_coordinator=None,
            display_rois_for_slice=None
        )
        
        # Slice Display Manager
        managers['slice_display_manager'] = SliceDisplayManager(
            self.dicom_processor,
            image_viewer,
            self.metadata_panel,
            self.slice_navigator,
            self.window_level_controls,
            managers['roi_manager'],
            managers['measurement_tool'],
            overlay_manager=managers['overlay_manager'],
            view_state_manager=managers['view_state_manager'],
            text_annotation_tool=managers.get('text_annotation_tool'),
            arrow_annotation_tool=managers.get('arrow_annotation_tool'),
            update_tag_viewer_callback=self._update_tag_viewer,
            display_rois_callback=None,
            display_measurements_callback=None,
            roi_list_panel=self.roi_list_panel,
            roi_statistics_panel=self.roi_statistics_panel,
            update_roi_statistics_overlays_callback=None,
            annotation_manager=self.annotation_manager,
            dicom_organizer=self.dicom_organizer
        )
        
        # ROI Coordinator
        managers['roi_coordinator'] = ROICoordinator(
            managers['roi_manager'],
            self.roi_list_panel,
            self.roi_statistics_panel,
            image_viewer,
            self.dicom_processor,
            self.window_level_controls,
            self.main_window,
            get_current_dataset=lambda idx=idx: self._get_subwindow_dataset(idx),
            get_current_slice_index=lambda idx=idx: self._get_subwindow_slice_index(idx),
                get_rescale_params=self._get_rescale_params,
                set_mouse_mode_callback=self._set_mouse_mode_via_handler,
                get_projection_enabled=lambda idx=idx: (self._get_subwindow_slice_display_manager(idx).projection_enabled if self._get_subwindow_slice_display_manager(idx) else False),
                get_projection_type=lambda idx=idx: (self._get_subwindow_slice_display_manager(idx).projection_type if self._get_subwindow_slice_display_manager(idx) else "aip"),
                get_projection_slice_count=lambda idx=idx: (self._get_subwindow_slice_display_manager(idx).projection_slice_count if self._get_subwindow_slice_display_manager(idx) else 4),
                get_current_studies=lambda: self.current_studies,
                undo_redo_manager=self.undo_redo_manager,
                crosshair_coordinator=managers.get('crosshair_coordinator')  # May not exist in this code path
        )
        
        # Measurement Coordinator
        managers['measurement_coordinator'] = MeasurementCoordinator(
            managers['measurement_tool'],
            image_viewer,
            get_current_dataset=lambda idx=idx: self._get_subwindow_dataset(idx),
            get_current_slice_index=lambda idx=idx: self._get_subwindow_slice_index(idx),
            undo_redo_manager=self.undo_redo_manager,
            update_undo_redo_state_callback=self._update_undo_redo_state
        )
        
        # Text Annotation Coordinator
        from gui.text_annotation_coordinator import TextAnnotationCoordinator
        managers['text_annotation_coordinator'] = TextAnnotationCoordinator(
            managers['text_annotation_tool'],
            image_viewer,
            get_current_dataset=lambda idx=idx: self._get_subwindow_dataset(idx),
            get_current_slice_index=lambda idx=idx: self._get_subwindow_slice_index(idx),
            undo_redo_manager=self.undo_redo_manager,
            update_undo_redo_state_callback=self._update_undo_redo_state
        )
        
        # Arrow Annotation Coordinator
        from gui.arrow_annotation_coordinator import ArrowAnnotationCoordinator
        managers['arrow_annotation_coordinator'] = ArrowAnnotationCoordinator(
            managers['arrow_annotation_tool'],
            image_viewer,
            get_current_dataset=lambda idx=idx: self._get_subwindow_dataset(idx),
            get_current_slice_index=lambda idx=idx: self._get_subwindow_slice_index(idx),
            undo_redo_manager=self.undo_redo_manager,
            update_undo_redo_state_callback=self._update_undo_redo_state
        )
        
        # Overlay Coordinator
        managers['overlay_coordinator'] = OverlayCoordinator(
            managers['overlay_manager'],
            image_viewer,
            get_current_dataset=lambda idx=idx: self._get_subwindow_dataset(idx),
            get_current_studies=lambda: self.current_studies,
            get_current_study_uid=lambda idx=idx: self._get_subwindow_study_uid(idx),
            get_current_series_uid=lambda idx=idx: self._get_subwindow_series_uid(idx),
            get_current_slice_index=lambda idx=idx: self._get_subwindow_slice_index(idx),
            hide_measurement_labels=managers['measurement_coordinator'].hide_measurement_labels,
            hide_measurement_graphics=managers['measurement_coordinator'].hide_measurement_graphics,
            hide_roi_graphics=managers['roi_coordinator'].hide_roi_graphics if hasattr(managers['roi_coordinator'], 'hide_roi_graphics') else None,
            hide_roi_statistics_overlays=managers['roi_coordinator'].hide_roi_statistics_overlays
        )
        
        # Fusion Handler (per-subwindow)
        managers['fusion_handler'] = FusionHandler()
        
        # Fusion Coordinator
        managers['fusion_coordinator'] = FusionCoordinator(
            managers['fusion_handler'],
            self.fusion_processor,
            self.fusion_controls_widget,
            get_current_studies=lambda: self.current_studies,
            get_current_study_uid=lambda: self.current_study_uid,
            get_current_series_uid=lambda: self.current_series_uid,
            get_current_slice_index=lambda: self.current_slice_index,
            request_display_update=lambda idx=idx: self._redisplay_subwindow_slice(idx, preserve_view=True),
            # Add callbacks for notification tracking
            check_notification_shown=lambda uid: self.has_shown_fusion_notification(uid),
            mark_notification_shown=lambda uid: self.mark_fusion_notification_shown(uid)
        )
        
        # Update slice display manager with fusion coordinator
        managers['slice_display_manager'].fusion_coordinator = managers['fusion_coordinator']
        
        # Update view state manager callbacks
        managers['view_state_manager'].overlay_coordinator = managers['overlay_coordinator'].handle_overlay_config_applied
        managers['view_state_manager'].roi_coordinator = lambda dataset: managers['roi_coordinator'].update_roi_statistics(
            managers['roi_manager'].get_selected_roi()
        ) if managers['roi_manager'].get_selected_roi() else None
        managers['view_state_manager'].display_rois_for_slice = lambda preserve_view=False: self._display_rois_for_subwindow(idx, preserve_view)
        managers['view_state_manager'].set_redisplay_slice_callback(lambda preserve_view=False: self._redisplay_subwindow_slice(idx, preserve_view))
        managers['view_state_manager'].set_series_navigator(self.series_navigator)
        
        # Update slice display manager callbacks
        managers['slice_display_manager'].update_roi_statistics_overlays_callback = managers['roi_coordinator'].update_roi_statistics_overlays
        
        # Connect inversion callback
        def on_inversion_state_changed(inverted: bool, idx=idx) -> None:
            if managers['view_state_manager'].current_series_identifier:
                managers['view_state_manager'].set_series_inversion_state(
                    managers['view_state_manager'].current_series_identifier,
                    inverted
                )
        image_viewer.inversion_state_changed_callback = on_inversion_state_changed
        
        # Set file path callback for "Show file" context menu
        image_viewer.get_file_path_callback = lambda idx=idx: self._get_current_slice_file_path(idx)
        
        # Store managers
        self.subwindow_managers[idx] = managers
        # print(f"DEBUG: Stored managers for subwindow {idx}")
        
        # Initialize subwindow data if not exists
        if idx not in self.subwindow_data:
            self.subwindow_data[idx] = {
                'current_dataset': None,
                'current_slice_index': 0,
                'current_series_uid': '',
                'current_study_uid': '',
                'current_datasets': []
            }
        
        # Set pan mode
        image_viewer.set_mouse_mode("pan")
    
    def _get_subwindow_dataset(self, idx: int) -> Optional[Dataset]:
        """Get current dataset for a subwindow."""
        if idx in self.subwindow_data:
            return self.subwindow_data[idx].get('current_dataset')
        return None
    
    def _get_subwindow_slice_index(self, idx: int) -> int:
        """Get current slice index for a subwindow."""
        if idx in self.subwindow_data:
            return self.subwindow_data[idx].get('current_slice_index', 0)
        return 0
    
    def _get_subwindow_slice_display_manager(self, idx: int):
        """Get slice display manager for a subwindow."""
        if idx in self.subwindow_managers:
            return self.subwindow_managers[idx].get('slice_display_manager')
        return None
    
    def _get_subwindow_study_uid(self, idx: int) -> str:
        """Get current study UID for a subwindow."""
        if idx in self.subwindow_data:
            return self.subwindow_data[idx].get('current_study_uid', '')
        return ''
    
    def _get_subwindow_series_uid(self, idx: int) -> str:
        """Get current series UID for a subwindow."""
        if idx in self.subwindow_data:
            return self.subwindow_data[idx].get('current_series_uid', '')
        return ''
    
    def _update_focused_subwindow_references(self) -> None:
        """Update legacy references to point to focused subwindow's managers and data."""
        focused_subwindow = self.multi_window_layout.get_focused_subwindow()
        if not focused_subwindow:
            return
        
        subwindows = self.multi_window_layout.get_all_subwindows()
        if focused_subwindow not in subwindows:
            return
        
        focused_idx = subwindows.index(focused_subwindow)
        self.focused_subwindow_index = focused_idx
        
        # Update manager references
        if focused_idx in self.subwindow_managers:
            managers = self.subwindow_managers[focused_idx]
            self.view_state_manager = managers['view_state_manager']
            self.slice_display_manager = managers['slice_display_manager']
            self.roi_coordinator = managers['roi_coordinator']
            self.measurement_coordinator = managers['measurement_coordinator']
            self.text_annotation_coordinator = managers.get('text_annotation_coordinator')
            self.arrow_annotation_coordinator = managers.get('arrow_annotation_coordinator')
            self.crosshair_coordinator = managers.get('crosshair_coordinator')
            self.fusion_coordinator = managers.get('fusion_coordinator')
            self.overlay_coordinator = managers['overlay_coordinator']
            self.roi_manager = managers['roi_manager']
            self.measurement_tool = managers['measurement_tool']
            self.text_annotation_tool = managers.get('text_annotation_tool')
            self.arrow_annotation_tool = managers.get('arrow_annotation_tool')
            self.crosshair_manager = managers.get('crosshair_manager')
            self.overlay_manager = managers['overlay_manager']
        
        # Store previous image_viewer to disconnect signal
        previous_image_viewer = self.image_viewer if hasattr(self, 'image_viewer') else None
        
        # Update image viewer reference
        self.image_viewer = focused_subwindow.image_viewer
        self.main_window.image_viewer = self.image_viewer
        
        # Disconnect old pixel_info_changed signal if it exists
        if previous_image_viewer and previous_image_viewer != self.image_viewer:
            try:
                previous_image_viewer.pixel_info_changed.disconnect(self._on_pixel_info_changed)
            except (TypeError, RuntimeError):
                # Signal may not be connected or already disconnected, ignore
                pass
        
        # Connect pixel_info_changed signal for new image_viewer
        if self.image_viewer:
            self.image_viewer.pixel_info_changed.connect(self._on_pixel_info_changed)
            # Update pixel info callbacks
            self.image_viewer.set_pixel_info_callbacks(
                get_dataset=lambda: self.current_dataset,
                get_slice_index=lambda: self.current_slice_index,
                get_use_rescaled=lambda: self.view_state_manager.use_rescaled_values if self.view_state_manager else False
            )
        
        # Update current data references (point to focused subwindow's data)
        if focused_idx in self.subwindow_data:
            data = self.subwindow_data[focused_idx]
            self.current_dataset = data.get('current_dataset')
            self.current_slice_index = data.get('current_slice_index', 0)
            self.current_series_uid = data.get('current_series_uid', '')
            self.current_study_uid = data.get('current_study_uid', '')
            self.current_datasets = data.get('current_datasets', [])
        
            # Sync shared slice navigator with focused subwindow's slice index
            # This ensures navigation starts from the correct position
            if self.current_datasets:
                total_slices = len(self.current_datasets)
                self.slice_navigator.set_total_slices(total_slices)
                # Use focused subwindow's slice index directly from data, not legacy reference
                focused_slice_index = data.get('current_slice_index', 0)
                if 0 <= focused_slice_index < total_slices:
                    # Temporarily block signals to prevent recursive updates
                    self.slice_navigator.blockSignals(True)
                    self.slice_navigator.current_slice_index = focused_slice_index
                    self.slice_navigator.blockSignals(False)
        
        # FIX: Update unit immediately when focus changes (before _update_right_panel_for_focused_subwindow)
        # This ensures unit is available even if display_slice hasn't been called yet
        if self.current_dataset and self.window_level_controls:
            from core.dicom_processor import DICOMProcessor
            rescale_slope, rescale_intercept, rescale_type = DICOMProcessor.get_rescale_parameters(self.current_dataset)
            # Infer rescale_type if None (e.g., for CT images)
            inferred_type = DICOMProcessor.infer_rescale_type(
                self.current_dataset, rescale_slope, rescale_intercept, rescale_type
            )
            if inferred_type:
                # print(f"[WL UNIT DEBUG] _update_focused_subwindow_references: Setting unit immediately from dataset: {inferred_type}")
                self.window_level_controls.set_unit(inferred_type)
            else:
                # Clear unit if cannot be inferred
                self.window_level_controls.set_unit(None)
                # print(f"[WL UNIT DEBUG] _update_focused_subwindow_references: Clearing unit (rescale_type=None, cannot infer)")
        
        # Update right panel controls to show focused subwindow's state
        self._update_right_panel_for_focused_subwindow()
        
        # Update left panel controls to show focused subwindow's state
        self._update_left_panel_for_focused_subwindow()
        
        # Update keyboard event handler to use focused subwindow's image_viewer
        if hasattr(self, 'keyboard_event_handler') and self.image_viewer:
            self.keyboard_event_handler.image_viewer = self.image_viewer
        
        # Update mouse mode handler reference and apply current mode
        if hasattr(self, 'mouse_mode_handler') and self.image_viewer:
            self.mouse_mode_handler.image_viewer = self.image_viewer
            # Apply current mouse mode from toolbar to newly focused subwindow
            current_mode = self.main_window.get_current_mouse_mode()
            if current_mode:
                self.image_viewer.set_mouse_mode(current_mode)
        
        # Set keyboard focus to focused subwindow's ImageViewer
        if self.image_viewer:
            self.image_viewer.setFocus()
    
    def has_shown_fusion_notification(self, study_uid: str) -> bool:
        """
        Check if fusion notification has already been shown for a study.
        
        Args:
            study_uid: Study UID to check
            
        Returns:
            True if notification was already shown, False otherwise
        """
        return study_uid in self._fusion_notified_studies
    
    def mark_fusion_notification_shown(self, study_uid: str) -> None:
        """
        Mark that fusion notification has been shown for a study.
        
        Args:
            study_uid: Study UID to mark as notified
        """
        if study_uid:
            self._fusion_notified_studies.add(study_uid)
    
    def _update_right_panel_for_focused_subwindow(self) -> None:
        """Update right panel controls to reflect focused subwindow's state."""
        # DEBUG: Log when _update_right_panel_for_focused_subwindow is called
        # print(f"[WL UNIT DEBUG] _update_right_panel_for_focused_subwindow called")
        # print(f"[WL UNIT DEBUG]   view_state_manager: {self.view_state_manager}")
        # if self.view_state_manager:
        #     print(f"[WL UNIT DEBUG]   use_rescaled_values: {self.view_state_manager.use_rescaled_values}")
        #     print(f"[WL UNIT DEBUG]   rescale_type: {self.view_state_manager.rescale_type}")
        # print(f"[WL UNIT DEBUG]   current_dataset: {self.current_dataset is not None}")
        # print(f"[DEBUG-WL] _update_right_panel_for_focused_subwindow called")
        if self.image_viewer is None:
            # print(f"[DEBUG-WL]   ERROR: image_viewer is None")
            return
        
        # Update zoom display
        self.zoom_display_widget.update_zoom(self.image_viewer.current_zoom)
        
        # Update window/level controls with focused subwindow's current values
        if self.view_state_manager:
            # Get unit from ViewStateManager's rescale_type if available
            unit = None
            if self.view_state_manager.use_rescaled_values:
                unit = self.view_state_manager.rescale_type
            
            # If unit not available from ViewStateManager, try to get from current dataset
            if not unit and self.current_dataset:
                from core.dicom_processor import DICOMProcessor
                rescale_slope, rescale_intercept, rescale_type = DICOMProcessor.get_rescale_parameters(self.current_dataset)
                # Infer rescale_type if None (e.g., for CT images)
                unit = DICOMProcessor.infer_rescale_type(
                    self.current_dataset, rescale_slope, rescale_intercept, rescale_type
                )
                # if unit:
                #     print(f"[WL UNIT DEBUG] _update_right_panel_for_focused_subwindow: Got unit from dataset fallback: {unit}")
                # else:
                #     print(f"[WL UNIT DEBUG] _update_right_panel_for_focused_subwindow: Cannot infer unit from dataset")
            
            # DEBUG: Log unit value before setting
            # print(f"[WL UNIT DEBUG] _update_right_panel_for_focused_subwindow: Setting unit to: {unit}")
            # print(f"[WL UNIT DEBUG]   view_state_manager.rescale_type: {self.view_state_manager.rescale_type}")
            # print(f"[WL UNIT DEBUG]   view_state_manager.use_rescaled_values: {self.view_state_manager.use_rescaled_values}")
            
            if (self.view_state_manager.current_window_center is not None and 
                self.view_state_manager.current_window_width is not None):
                # Update controls with unit (unit may be None, which will clear the display)
                self.window_level_controls.set_window_level(
                    self.view_state_manager.current_window_center,
                    self.view_state_manager.current_window_width,
                    block_signals=True,
                    unit=unit
                )
                # print(f"[WL UNIT DEBUG] _update_right_panel_for_focused_subwindow: Called set_window_level with unit={unit}")
            else:
                # Even if window/level values are None, update the unit
                self.window_level_controls.set_unit(unit)  # unit may be None
                # if unit:
                #     print(f"[WL UNIT DEBUG] _update_right_panel_for_focused_subwindow: Called set_unit({unit})")
                # else:
                #     print(f"[WL UNIT DEBUG] _update_right_panel_for_focused_subwindow: Called set_unit(None) to clear units")
        else:
            # print(f"[DEBUG-WL]   ERROR: view_state_manager is None")
            pass
        
        # Update intensity projection controls widget with focused subwindow's projection state
        if self.slice_display_manager:
            # Update enabled state (this method blocks signals on the checkbox internally)
            self.intensity_projection_controls_widget.set_enabled(
                self.slice_display_manager.projection_enabled,
                keep_signals_blocked=False
            )
            
            # Update projection type (this method blocks signals on the combo box internally)
            self.intensity_projection_controls_widget.set_projection_type(
                self.slice_display_manager.projection_type
            )
            
            # Update slice count (this method blocks signals on the combo box internally)
            self.intensity_projection_controls_widget.set_slice_count(
                self.slice_display_manager.projection_slice_count
            )
        
        # Update fusion controls with focused subwindow's series
        # print(f"[RIGHT PANEL DEBUG] Checking fusion controls update")
        # print(f"[RIGHT PANEL DEBUG] hasattr current_studies: {hasattr(self, 'current_studies')}")
        # if hasattr(self, 'current_studies'):
        #     print(f"[RIGHT PANEL DEBUG] current_studies is not None: {self.current_studies is not None}")
        #     if self.current_studies:
        #         print(f"[RIGHT PANEL DEBUG] current_studies count: {len(self.current_studies)}")
        if hasattr(self, 'current_studies') and self.current_studies:
            focused_subwindow = self.multi_window_layout.get_focused_subwindow()
            # print(f"[RIGHT PANEL DEBUG] focused_subwindow: {focused_subwindow is not None}")
            if focused_subwindow:
                subwindows = self.multi_window_layout.get_all_subwindows()
                focused_idx = subwindows.index(focused_subwindow) if focused_subwindow in subwindows else -1
                # print(f"[RIGHT PANEL DEBUG] focused_idx: {focused_idx}")
                # print(f"[RIGHT PANEL DEBUG] focused_idx in subwindow_managers: {focused_idx in self.subwindow_managers}")
                if focused_idx >= 0 and focused_idx in self.subwindow_managers:
                    fusion_coordinator = self.subwindow_managers[focused_idx].get('fusion_coordinator')
                    # print(f"[RIGHT PANEL DEBUG] fusion_coordinator: {fusion_coordinator is not None}")
                    if fusion_coordinator:
                        # print(f"[RIGHT PANEL DEBUG] Calling update_fusion_controls_series_list()")
                        fusion_coordinator.update_fusion_controls_series_list()
        # else:
        #     print(f"[RIGHT PANEL DEBUG] Skipping - no current_studies")
        
        # Update ROI list (will be updated when slice is displayed)
        # Update ROI statistics (will be updated when ROI is selected)
    
    def _update_left_panel_for_focused_subwindow(self) -> None:
        """Update left panel controls (metadata, cine) to reflect focused subwindow's state."""
        if self.current_dataset is None:
            return
        
        # Update metadata panel with focused subwindow's dataset
        self.metadata_panel.set_dataset(self.current_dataset)
        
        # Update cine player context for focused subwindow
        self._update_cine_player_context()
    
    def _display_rois_for_subwindow(self, idx: int, preserve_view: bool = False) -> None:
        """Display ROIs for a specific subwindow."""
        if idx not in self.subwindow_managers:
            return
        managers = self.subwindow_managers[idx]
        # This will be implemented to display ROIs for the subwindow's current slice
        # For now, placeholder
        pass
    
    def _redisplay_subwindow_slice(self, idx: int, preserve_view: bool = False) -> None:
        """Redisplay slice for a specific subwindow."""
        # print(f"[DEBUG-WL] _redisplay_subwindow_slice called: idx={idx}, preserve_view={preserve_view}")
        if idx not in self.subwindow_managers:
            # print(f"[DEBUG-WL]   ERROR: idx {idx} not in subwindow_managers")
            return
        
        managers = self.subwindow_managers[idx]
        view_state_manager = managers.get('view_state_manager')
        slice_display_manager = managers['slice_display_manager']
        
        # print(f"[DEBUG-WL]   ViewStateManager stored values: center={view_state_manager.current_window_center if view_state_manager else 'None'}, width={view_state_manager.current_window_width if view_state_manager else 'None'}")
        
        # Get current data for this subwindow
        if idx not in self.subwindow_data:
            # print(f"[DEBUG-WL]   ERROR: idx {idx} not in subwindow_data")
            return
        
        data = self.subwindow_data[idx]
        dataset = data.get('current_dataset')
        study_uid = data.get('current_study_uid', '')
        series_uid = data.get('current_series_uid', '')
        slice_index = data.get('current_slice_index', 0)
        
        if dataset and study_uid and series_uid and self.current_studies:
            # print(f"[DEBUG-WL]   Calling display_slice with dataset, study={study_uid[:20] if len(study_uid) > 20 else study_uid}..., series={series_uid[:20] if len(series_uid) > 20 else series_uid}...")
            # Redisplay the slice with current window/level
            slice_display_manager.display_slice(
                dataset,
                self.current_studies,
                study_uid,
                series_uid,
                slice_index,
                preserve_view_override=preserve_view
            )
        else:
            # print(f"[DEBUG-WL]   ERROR: Missing data - dataset={dataset is not None}, study_uid={bool(study_uid)}, series_uid={bool(series_uid)}, current_studies={bool(self.current_studies)}")
            pass
    
    def _initialize_handlers(self) -> None:
        """Initialize all handler classes."""
        # Note: Per-subwindow managers are created in _initialize_subwindow_managers
        # References to focused subwindow's managers should already be set in __init__
        # before this method is called. If not, we'll use the first subwindow's managers.
        
        # Ensure managers are set (should already be set in __init__, but double-check)
        if not hasattr(self, 'roi_coordinator') or self.roi_coordinator is None:
            # Fallback: use first subwindow's managers
            subwindows = self.multi_window_layout.get_all_subwindows()
            if subwindows and 0 in self.subwindow_managers:
                managers = self.subwindow_managers[0]
                self.view_state_manager = managers['view_state_manager']
                self.slice_display_manager = managers['slice_display_manager']
                self.roi_coordinator = managers['roi_coordinator']
                self.measurement_coordinator = managers['measurement_coordinator']
                self.text_annotation_coordinator = managers.get('text_annotation_coordinator')
                self.arrow_annotation_coordinator = managers.get('arrow_annotation_coordinator')
                self.crosshair_coordinator = managers.get('crosshair_coordinator')
                self.overlay_coordinator = managers['overlay_coordinator']
                self.roi_manager = managers['roi_manager']
                self.measurement_tool = managers['measurement_tool']
                self.text_annotation_tool = managers.get('text_annotation_tool')
                self.arrow_annotation_tool = managers.get('arrow_annotation_tool')
                self.crosshair_manager = managers.get('crosshair_manager')
                self.overlay_manager = managers['overlay_manager']
                if subwindows[0]:
                    self.image_viewer = subwindows[0].image_viewer
                    self.main_window.image_viewer = self.image_viewer
            else:
                raise RuntimeError("No subwindow managers available. Cannot initialize handlers.")
        
        # Initialize FileOperationsHandler (shared, not per-subwindow)
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
        
        # Initialize DialogCoordinator
        self.dialog_coordinator = DialogCoordinator(
            self.config_manager,
            self.main_window,
            get_current_studies=lambda: self.current_studies,
            settings_applied_callback=self._on_settings_applied,
            overlay_config_applied_callback=self._on_overlay_config_applied,
            tag_edit_history=self.tag_edit_history,
            get_current_dataset=lambda: self.current_dataset,
            get_current_slice_index=lambda: self.current_slice_index,
            get_window_center=lambda: self.view_state_manager.current_window_center if self.view_state_manager else None,
            get_window_width=lambda: self.view_state_manager.current_window_width if self.view_state_manager else None,
            get_use_rescaled=lambda: self.view_state_manager.use_rescaled_values if self.view_state_manager else False,
            get_rescale_params=lambda: self.dicom_processor.get_rescale_parameters(self.current_dataset) if self.current_dataset else (None, None, None),
            undo_redo_manager=self.undo_redo_manager,
            ui_refresh_callback=self._refresh_tag_ui
        )
        # Set annotation options callback
        self.dialog_coordinator.annotation_options_applied_callback = self._on_annotation_options_applied
        # Set tag edited callback
        self.dialog_coordinator.tag_edited_callback = self._on_tag_edited
        # Set undo/redo callbacks for tag viewer dialog
        self.dialog_coordinator.undo_redo_callbacks = (
            lambda: self._on_undo_requested(),
            lambda: self._on_redo_requested(),
            lambda: self.undo_redo_manager.can_undo() if self.undo_redo_manager else False,
            lambda: self.undo_redo_manager.can_redo() if self.undo_redo_manager else False
        )
        
        # Initialize MouseModeHandler
        self.mouse_mode_handler = MouseModeHandler(
            self.image_viewer,
            self.main_window,
            self.slice_navigator,
            self.config_manager
        )
        
        # Connect context menu signals for all subwindows (now that mouse_mode_handler exists)
        self._connect_all_subwindow_context_menu_signals()
        
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
        # Ensure all required managers exist before initializing
        if not all([hasattr(self, attr) and getattr(self, attr) is not None 
                   for attr in ['roi_manager', 'measurement_tool', 'overlay_manager', 
                               'image_viewer', 'roi_coordinator', 'measurement_coordinator', 
                               'overlay_coordinator', 'view_state_manager']]):
            raise RuntimeError("Required managers not initialized. Cannot create KeyboardEventHandler.")
        
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
            invert_image_callback=self.image_viewer.invert_image,
            open_histogram_callback=self.dialog_coordinator.open_histogram,
            reset_all_views_callback=self._on_reset_all_views,
            toggle_privacy_view_callback=lambda enabled: self._on_privacy_view_toggled(enabled),
            get_privacy_view_state_callback=lambda: self.privacy_view_enabled,
            delete_text_annotation_callback=None,  # Will be set when coordinators are available
            delete_arrow_annotation_callback=None,  # Will be set when coordinators are available
            change_layout_callback=self.main_window.set_layout_mode
        )
    
    def _clear_data(self) -> None:
        """Clear all ROIs, measurements, and related data for all subwindows."""
        # Clear data for ALL subwindows, not just focused one
        subwindows = self.multi_window_layout.get_all_subwindows()
        for idx, subwindow in enumerate(subwindows):
            if subwindow and subwindow.image_viewer and subwindow.image_viewer.scene:
                # Get the managers for this subwindow
                if idx in self.subwindow_managers:
                    managers = self.subwindow_managers[idx]
                    roi_manager = managers.get('roi_manager')
                    measurement_tool = managers.get('measurement_tool')
                    text_annotation_tool = managers.get('text_annotation_tool')
                    arrow_annotation_tool = managers.get('arrow_annotation_tool')
                    if roi_manager:
                        roi_manager.clear_all_rois(subwindow.image_viewer.scene)
                    if measurement_tool:
                        measurement_tool.clear_measurements(subwindow.image_viewer.scene)
                    if text_annotation_tool:
                        text_annotation_tool.clear_annotations(subwindow.image_viewer.scene)
                    if arrow_annotation_tool:
                        arrow_annotation_tool.clear_arrows(subwindow.image_viewer.scene)
        
        # Update shared panels (these show focused subwindow's data)
        self.roi_list_panel.update_roi_list("", "", 0)  # Clear list
        self.roi_statistics_panel.clear_statistics()
    
    def _close_files(self) -> None:
        """Close currently open files/folder and clear all data."""
        # Clear all ROIs, measurements, and related data for all subwindows
        self._clear_data()
        
        # Clear image viewers for ALL subwindows
        subwindows = self.multi_window_layout.get_all_subwindows()
        for subwindow in subwindows:
            if subwindow and subwindow.image_viewer:
                # Clear scene
                subwindow.image_viewer.scene.clear()
                subwindow.image_viewer.image_item = None
                # Force viewport update to ensure cleared scene is visible
                subwindow.image_viewer.viewport().update()
        
        # Clear overlay items for all subwindows (including viewport corner overlays)
        for idx in self.subwindow_managers:
            managers = self.subwindow_managers[idx]
            overlay_manager = managers.get('overlay_manager')
            if overlay_manager:
                # Get the scene from the corresponding subwindow to properly clear overlays
                subwindows = self.multi_window_layout.get_all_subwindows()
                if idx < len(subwindows) and subwindows[idx] and subwindows[idx].image_viewer:
                    scene = subwindows[idx].image_viewer.scene
                    overlay_manager.clear_overlay_items(scene)
                else:
                    # Fallback: just clear the items list if scene not available
                    overlay_manager.overlay_items.clear()
        
        # Reset fusion for all subwindows (disable fusion, clear status, clear caches)
        # This is called when opening new files to ensure fusion is disabled
        self._reset_fusion_for_all_subwindows()
        
        # Clear metadata panel (shared)
        self.metadata_panel.set_dataset(None)
        
        # Reset view state for all subwindows
        for idx in self.subwindow_managers:
            managers = self.subwindow_managers[idx]
            view_state_manager = managers.get('view_state_manager')
            slice_display_manager = managers.get('slice_display_manager')
            if view_state_manager:
                view_state_manager.reset_window_level_state()
                view_state_manager.reset_series_tracking()
            if slice_display_manager:
                slice_display_manager.reset_projection_state()
        
        # Update shared widget state
        self.intensity_projection_controls_widget.set_enabled(False)
        self.intensity_projection_controls_widget.set_projection_type("aip")
        self.intensity_projection_controls_widget.set_slice_count(4)
        
        # Reset fusion for all subwindows (disable fusion, clear status, clear caches)
        self._reset_fusion_for_all_subwindows()
        
        # Clear all subwindow data structures
        self.subwindow_data.clear()
        
        # Clear cached pixel arrays from datasets to free memory (before clearing studies dict)
        if self.current_studies:
            for study_uid, series_dict in self.current_studies.items():
                for series_uid, datasets in series_dict.items():
                    for dataset in datasets:
                        # Remove cached pixel arrays if they exist
                        if hasattr(dataset, '_cached_pixel_array'):
                            delattr(dataset, '_cached_pixel_array')
        
        # Clear current dataset references (legacy, points to focused subwindow)
        self.current_dataset = None
        self.current_studies = {}
        self.current_study_uid = ""
        self.current_series_uid = ""
        self.current_slice_index = 0
        
        # Reset slice navigator (shared)
        self.slice_navigator.set_total_slices(0)
        self.slice_navigator.set_current_slice(0)
        
        # Clear series navigator (shared)
        self.series_navigator.update_series_list({}, "", "")
        
        # Clear tag edit history
        if self.tag_edit_history:
            self.tag_edit_history.clear_history()
        
        # Reset undo/redo state
        self._update_undo_redo_state()
        
        # Stop cine player if active (prevents timer leaks)
        if hasattr(self, 'cine_player') and self.cine_player:
            self.cine_player.stop_playback()
        
        # Clear tag viewer filter
        if self.dialog_coordinator:
            self.dialog_coordinator.clear_tag_viewer_filter()
        
        # Update status
        self.main_window.update_status("Ready")
    
    def _reset_fusion_for_all_subwindows(self) -> None:
        """
        Disable fusion and clear status for all subwindows.
        
        This is called when files are closed or when new files are opened
        to ensure fusion is disabled and status messages are cleared.
        """
        # Disable fusion in all handlers and clear caches
        for idx in self.subwindow_managers:
            managers = self.subwindow_managers[idx]
            fusion_handler = managers.get('fusion_handler')
            if fusion_handler:
                # Disable fusion in handler (prevents re-enabling on file load)
                fusion_handler.fusion_enabled = False
                # Clear all fusion caches
                fusion_handler._slice_location_cache.clear()
                fusion_handler._resampling_decision_cache = None
                fusion_handler._resampling_decision_cache_key = None
                fusion_handler.clear_alignment_cache()  # Clears all alignment cache entries
                # Clear 3D resampling volume cache (this is the big one!)
                if hasattr(fusion_handler, 'image_resampler') and fusion_handler.image_resampler:
                    fusion_handler.image_resampler.clear_cache()  # Clears all cached volumes
        
        # Disable fusion in UI widget and clear status messages
        self.fusion_controls_widget.set_fusion_enabled(False)
        self.fusion_controls_widget.clear_status()
    
    def _handle_load_first_slice(self, studies: dict) -> None:
        """
        Handle loading first slice after file operations.
        
        Clears edited tags for the previous dataset before loading new one.
        """
        # print(f"[LOAD DEBUG] ============================================")
        # print(f"[LOAD DEBUG] _handle_load_first_slice called with {len(studies)} study/studies")
        # print(f"[LOAD DEBUG] ============================================")
        
        # Disable fusion and clear status for all subwindows when opening new files
        self._reset_fusion_for_all_subwindows()
        
        # Clear edited tags for previous dataset if it exists
        if self.current_dataset is not None and self.tag_edit_history:
            self.tag_edit_history.clear_edited_tags(self.current_dataset)
        # Clear all subwindows before loading new files
        # This ensures old images don't persist in non-focused subwindows
        subwindows = self.multi_window_layout.get_all_subwindows()
        for subwindow in subwindows:
            if subwindow and subwindow.image_viewer:
                # Clear scene to remove old images
                subwindow.image_viewer.scene.clear()
                subwindow.image_viewer.image_item = None
                # Force viewport update
                subwindow.image_viewer.viewport().update()
        
        # Clear overlay items for all subwindows (including viewport corner overlays)
        for idx in self.subwindow_managers:
            managers = self.subwindow_managers[idx]
            overlay_manager = managers.get('overlay_manager')
            if overlay_manager:
                # Get the scene from the corresponding subwindow to properly clear overlays
                subwindows = self.multi_window_layout.get_all_subwindows()
                if idx < len(subwindows) and subwindows[idx] and subwindows[idx].image_viewer:
                    scene = subwindows[idx].image_viewer.scene
                    overlay_manager.clear_overlay_items(scene)
                else:
                    # Fallback: just clear the items list if scene not available
                    overlay_manager.overlay_items.clear()
        
        # Reset projection state when new files are opened
        self.slice_display_manager.reset_projection_state()
        # Update widget to match reset state
        self.intensity_projection_controls_widget.set_enabled(False)
        self.intensity_projection_controls_widget.set_projection_type("aip")
        self.intensity_projection_controls_widget.set_slice_count(4)
        
        # Clear tag viewer filter when opening new files
        if self.dialog_coordinator:
            self.dialog_coordinator.clear_tag_viewer_filter()
        
        first_slice_info = self.file_operations_handler.load_first_slice(studies)
        if first_slice_info:
            self.current_studies = studies
            self.current_study_uid = first_slice_info['study_uid']
            self.current_series_uid = first_slice_info['series_uid']
            self.current_slice_index = first_slice_info['slice_index']
            
            # Update fusion controls with new studies
            # print(f"[MAIN DEBUG] Checking fusion controls update after loading files")
            focused_subwindow = self.multi_window_layout.get_focused_subwindow()
            # print(f"[MAIN DEBUG] focused_subwindow: {focused_subwindow is not None}")
            if focused_subwindow:
                subwindows = self.multi_window_layout.get_all_subwindows()
                focused_idx = subwindows.index(focused_subwindow) if focused_subwindow in subwindows else -1
                # print(f"[MAIN DEBUG] focused_idx: {focused_idx}")
                # print(f"[MAIN DEBUG] focused_idx in subwindow_managers: {focused_idx in self.subwindow_managers}")
                if focused_idx >= 0 and focused_idx in self.subwindow_managers:
                    fusion_coordinator = self.subwindow_managers[focused_idx].get('fusion_coordinator')
                    # print(f"[MAIN DEBUG] fusion_coordinator: {fusion_coordinator is not None}")
                    if fusion_coordinator:
                        # print(f"[MAIN DEBUG] Calling update_fusion_controls_series_list()")
                        fusion_coordinator.update_fusion_controls_series_list()
                # else:
                #     print(f"[MAIN DEBUG] No valid subwindow manager for fusion")
            
            # Clear stale subwindow data that references series not in current_studies
            # This prevents navigation failures when subwindows have outdated series references
            stale_count = 0
            for idx in list(self.subwindow_data.keys()):
                data = self.subwindow_data[idx]
                study_uid = data.get('current_study_uid', '')
                series_uid = data.get('current_series_uid', '')
                if study_uid and series_uid:
                    # Check if this series still exists in the loaded studies
                    if (study_uid not in self.current_studies or 
                        series_uid not in self.current_studies.get(study_uid, {})):
                        # Stale data - clear it
                        print(f"[DEBUG] Clearing stale subwindow data for subwindow {idx}: "
                              f"study={study_uid[:20] if study_uid else 'None'}..., "
                              f"series={series_uid[:20] if series_uid else 'None'}...")
                        self.subwindow_data[idx] = {
                            'current_dataset': None,
                            'current_slice_index': 0,
                            'current_series_uid': '',
                            'current_study_uid': '',
                            'current_datasets': []
                        }
                        stale_count += 1
            if stale_count > 0:
                print(f"[DEBUG] Cleared stale data from {stale_count} subwindow(s)")
            
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
            
            # Always load first series to subwindow 0 and make it focused
            subwindow_0 = self.multi_window_layout.get_subwindow(0)
            if subwindow_0:
                self.multi_window_layout.set_focused_subwindow(subwindow_0)
                self.focused_subwindow_index = 0
            
            # Get subwindow 0's managers for loading the first series
            if 0 not in self.subwindow_managers:
                # Ensure managers exist for subwindow 0
                self._ensure_all_subwindows_have_managers()
            
            managers_0 = self.subwindow_managers[0]
            slice_display_manager_0 = managers_0.get('slice_display_manager')
            view_state_manager_0 = managers_0.get('view_state_manager')
            
            # Reset view state for subwindow 0
            if view_state_manager_0:
                view_state_manager_0.reset_window_level_state()
                view_state_manager_0.reset_series_tracking()
            
            # Set up slice navigator
            self.slice_navigator.set_total_slices(first_slice_info['total_slices'])
            self.slice_navigator.set_current_slice(0)
            
            # Display slice in subwindow 0
            if slice_display_manager_0:
                slice_display_manager_0.display_slice(
                    first_slice_info['dataset'],
                    self.current_studies,
                    self.current_study_uid,
                    self.current_series_uid,
                    self.current_slice_index
                )
            
            # Update current dataset reference
            self.current_dataset = first_slice_info['dataset']
            
            # Initialize subwindow_data[0] with loaded data for the first subwindow
            # This ensures the first subwindow can navigate and respond to controls
            focused_idx = 0
            if focused_idx not in self.subwindow_data:
                self.subwindow_data[focused_idx] = {}
            
            # Extract actual composite series key from the dataset that was displayed
            # This ensures subwindow_data always reflects what's actually shown
            displayed_dataset = first_slice_info['dataset']
            extracted_series_uid = get_composite_series_key(displayed_dataset)
            extracted_study_uid = getattr(displayed_dataset, 'StudyInstanceUID', '')
            
            # Get stored values for comparison
            stored_series_uid = self.current_series_uid
            stored_study_uid = self.current_study_uid
            
            # Log the sync with FULL UIDs (not truncated) to diagnose mismatches
            if extracted_series_uid != stored_series_uid:
                print(f"[DEBUG] Syncing subwindow_data after initial load: MISMATCH detected!")
                print(f"[DEBUG]   Extracted series_uid from dataset: {extracted_series_uid}")
                print(f"[DEBUG]   Stored series_uid: {stored_series_uid}")
                print(f"[DEBUG]   Series UID match: False - updating stored value to match dataset")
            else:
                print(f"[DEBUG] Syncing subwindow_data after initial load: series_uid matches")
                print(f"[DEBUG]   Series UID: {extracted_series_uid}")
            
            if extracted_study_uid != stored_study_uid:
                print(f"[DEBUG]   Extracted study_uid from dataset: {extracted_study_uid}")
                print(f"[DEBUG]   Stored study_uid: {stored_study_uid}")
                print(f"[DEBUG]   Study UID match: False - updating stored value to match dataset")
            
            # Update subwindow_data and legacy references with extracted UIDs from dataset
            # This ensures navigation always starts from the correct series that's actually displayed
            self.subwindow_data[focused_idx]['current_dataset'] = displayed_dataset
            self.subwindow_data[focused_idx]['current_slice_index'] = self.current_slice_index
            self.subwindow_data[focused_idx]['current_series_uid'] = extracted_series_uid
            self.subwindow_data[focused_idx]['current_study_uid'] = extracted_study_uid
            
            # Update legacy references to match
            self.current_series_uid = extracted_series_uid
            self.current_study_uid = extracted_study_uid
            
            # Get all datasets for the actual series (using extracted UID)
            if extracted_study_uid in studies and extracted_series_uid in studies[extracted_study_uid]:
                series_datasets = studies[extracted_study_uid][extracted_series_uid]
                self.subwindow_data[focused_idx]['current_datasets'] = series_datasets
            else:
                # Fallback to stored values if extracted UIDs don't exist in studies
                print(f"[DEBUG] WARNING: Extracted UIDs not found in studies, using stored values")
                series_datasets = studies[self.current_study_uid][self.current_series_uid]
                self.subwindow_data[focused_idx]['current_datasets'] = series_datasets
            
            # Ensure subwindow 0's slice_display_manager context is initialized with loaded data
            # This is critical for navigation and window/level controls to work
            # Use extracted UIDs to ensure context matches what's actually displayed
            if slice_display_manager_0:
                slice_display_manager_0.set_current_data_context(
                    self.current_studies,
                    extracted_study_uid,  # Use extracted UID, not stored
                    extracted_series_uid,  # Use extracted UID, not stored
                    self.current_slice_index
                )
            
            # Ensure view_state_manager has the current dataset for window/level controls
            if view_state_manager_0:
                view_state_manager_0.current_dataset = first_slice_info['dataset']
                # The window/level will be set when display_slice is called above
                # We just need to ensure the dataset is set so handle_window_changed can work
            
            # Update references to point to subwindow 0's managers
            self.view_state_manager = view_state_manager_0
            self.slice_display_manager = slice_display_manager_0
            if 0 in self.subwindow_managers:
                managers_0 = self.subwindow_managers[0]
                self.roi_coordinator = managers_0.get('roi_coordinator')
            
            # Ensure window/level controls are connected to subwindow 0's view_state_manager
            # Reconnect signals to ensure they point to the correct manager
            self._disconnect_focused_subwindow_signals()
            self._connect_focused_subwindow_signals()
            
            # Clear metadata panel filter when loading new files
            self.metadata_panel.clear_filter()
            
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
    
    def _on_tag_edited(self, tag_str: str, new_value) -> None:
        """
        Handle tag edit from either panel - refresh both panels.
        
        Args:
            tag_str: Tag string that was edited
            new_value: New tag value
        """
        # Refresh metadata panel
        search_text = self.metadata_panel.search_edit.text()
        self.metadata_panel._cached_tags = None
        # Clear parser cache so it re-reads from updated dataset
        if self.metadata_panel.parser is not None:
            self.metadata_panel.parser._tag_cache.clear()
        self.metadata_panel._populate_tags(search_text)
        
        # Refresh tag viewer dialog if open
        if self.dialog_coordinator.tag_viewer_dialog:
            search_text = self.dialog_coordinator.tag_viewer_dialog.search_edit.text()
            self.dialog_coordinator.tag_viewer_dialog._cached_tags = None
            # Clear parser cache so it re-reads from updated dataset
            if self.dialog_coordinator.tag_viewer_dialog.parser is not None:
                self.dialog_coordinator.tag_viewer_dialog.parser._tag_cache.clear()
            self.dialog_coordinator.tag_viewer_dialog._populate_tags(search_text)
        
        # Update undo/redo state
        self._update_undo_redo_state()
    
    def _undo_tag_edit(self) -> None:
        """Handle undo tag edit request."""
        if self.current_dataset is not None and self.tag_edit_history:
            success = self.tag_edit_history.undo(self.current_dataset)
            if success:
                # Refresh metadata panel and tag viewer
                # Clear parser caches so they re-read from updated dataset
                if self.metadata_panel.parser is not None:
                    self.metadata_panel.parser._tag_cache.clear()
                self.metadata_panel._populate_tags()
                if self.dialog_coordinator.tag_viewer_dialog:
                    search_text = self.dialog_coordinator.tag_viewer_dialog.search_edit.text()
                    if self.dialog_coordinator.tag_viewer_dialog.parser is not None:
                        self.dialog_coordinator.tag_viewer_dialog.parser._tag_cache.clear()
                    self.dialog_coordinator.tag_viewer_dialog._populate_tags(search_text)
                # Update undo/redo state
                self._update_undo_redo_state()
    
    def _redo_tag_edit(self) -> None:
        """Handle redo tag edit request."""
        if self.current_dataset is not None and self.tag_edit_history:
            success = self.tag_edit_history.redo(self.current_dataset)
            if success:
                # Refresh metadata panel and tag viewer
                # Clear parser caches so they re-read from updated dataset
                if self.metadata_panel.parser is not None:
                    self.metadata_panel.parser._tag_cache.clear()
                self.metadata_panel._populate_tags()
                if self.dialog_coordinator.tag_viewer_dialog:
                    search_text = self.dialog_coordinator.tag_viewer_dialog.search_edit.text()
                    if self.dialog_coordinator.tag_viewer_dialog.parser is not None:
                        self.dialog_coordinator.tag_viewer_dialog.parser._tag_cache.clear()
                    self.dialog_coordinator.tag_viewer_dialog._populate_tags(search_text)
                # Update undo/redo state
                self._update_undo_redo_state()
    
    def _update_undo_redo_state(self) -> None:
        """Update undo/redo menu item states."""
        # Use unified undo/redo manager for all operations
        can_undo = self.undo_redo_manager.can_undo() if self.undo_redo_manager else False
        can_redo = self.undo_redo_manager.can_redo() if self.undo_redo_manager else False
        
        self.main_window.update_undo_redo_state(can_undo, can_redo)
    
    def _refresh_tag_ui(self) -> None:
        """Refresh both metadata panel and tag viewer dialog after tag changes."""
        # Refresh metadata panel
        if self.metadata_panel and self.metadata_panel.dataset:
            search_text = self.metadata_panel.search_edit.text()
            self.metadata_panel._cached_tags = None
            # Clear parser cache so it re-reads from updated dataset
            if self.metadata_panel.parser is not None:
                self.metadata_panel.parser._tag_cache.clear()
            self.metadata_panel._populate_tags(search_text)
        
        # Refresh tag viewer dialog if open
        if self.dialog_coordinator.tag_viewer_dialog:
            search_text = self.dialog_coordinator.tag_viewer_dialog.search_edit.text()
            self.dialog_coordinator.tag_viewer_dialog._cached_tags = None
            # Clear parser cache so it re-reads from updated dataset
            if self.dialog_coordinator.tag_viewer_dialog.parser is not None:
                self.dialog_coordinator.tag_viewer_dialog.parser._tag_cache.clear()
            self.dialog_coordinator.tag_viewer_dialog._populate_tags(search_text)
    
    def _on_undo_requested(self) -> None:
        """Handle undo request (unified for all operations)."""
        if self.undo_redo_manager and self.undo_redo_manager.can_undo():
            success = self.undo_redo_manager.undo()
            if success:
                # Update UI after undo
                self._update_undo_redo_state()
                # Refresh ROI list and statistics
                self._update_roi_list()
                # Update crosshair visibility if needed
                if hasattr(self, 'crosshair_coordinator') and self.crosshair_coordinator:
                    self.crosshair_coordinator.update_crosshairs_for_slice()
                # Tag UI refresh is handled by the TagEditCommand callback
    
    def _on_redo_requested(self) -> None:
        """Handle redo request (unified for all operations)."""
        if self.undo_redo_manager and self.undo_redo_manager.can_redo():
            success = self.undo_redo_manager.redo()
            if success:
                # Update UI after redo
                self._update_undo_redo_state()
                # Refresh ROI list and statistics
                self._update_roi_list()
                # Update crosshair visibility if needed
                if hasattr(self, 'crosshair_coordinator') and self.crosshair_coordinator:
                    self.crosshair_coordinator.update_crosshairs_for_slice()
                # Tag UI refresh is handled by the TagEditCommand callback
    
    def _update_roi_list(self) -> None:
        """Update ROI list panel."""
        if self.current_dataset is not None:
            study_uid = getattr(self.current_dataset, 'StudyInstanceUID', '')
            series_uid = get_composite_series_key(self.current_dataset)
            # Use current slice index as instance identifier (array position)
            instance_identifier = self.current_slice_index
            self.roi_list_panel.update_roi_list(study_uid, series_uid, instance_identifier)
    
    def _setup_ui(self) -> None:
        """Set up the user interface layout."""
        # Add multi-window layout to center panel
        center_layout = self.main_window.center_panel.layout()
        if center_layout is None:
            from PySide6.QtWidgets import QVBoxLayout
            center_layout = QVBoxLayout(self.main_window.center_panel)
        center_layout.addWidget(self.multi_window_layout)
        
        # Add cine controls widget and metadata panel to left panel
        left_layout = self.main_window.left_panel.layout()
        if left_layout is None:
            from PySide6.QtWidgets import QVBoxLayout
            left_layout = QVBoxLayout(self.main_window.left_panel)
        # Add cine controls widget first (above metadata panel) with stretch 0
        left_layout.addWidget(self.cine_controls_widget, 0)
        # Add metadata panel below cine controls with stretch 1 to make it ~1.5x its current height
        left_layout.addWidget(self.metadata_panel, 1)
        
        # Add controls to right panel with tabbed interface
        right_layout = self.main_window.right_panel.layout()
        if right_layout is None:
            from PySide6.QtWidgets import QVBoxLayout
            right_layout = QVBoxLayout(self.main_window.right_panel)
        
        # Create tab widget
        from PySide6.QtWidgets import QTabWidget, QWidget
        tab_widget = QTabWidget()
        tab_widget.setObjectName("right_panel_tabs")
        
        # Tab 1: Window/Zoom/ROI
        tab1_widget = QWidget()
        tab1_layout = QVBoxLayout(tab1_widget)
        tab1_layout.setContentsMargins(0, 0, 0, 0)
        tab1_layout.setSpacing(0)
        tab1_layout.addWidget(self.window_level_controls)
        tab1_layout.addWidget(self.zoom_display_widget)
        tab1_layout.addStretch()  # Push ROI sections to bottom
        tab1_layout.addWidget(self.roi_list_panel)
        tab1_layout.addWidget(self.roi_statistics_panel)
        tab_widget.addTab(tab1_widget, "Window/Zoom/ROI")
        
        # Tab 2: Combine/Fuse
        tab2_widget = QWidget()
        tab2_layout = QVBoxLayout(tab2_widget)
        tab2_layout.setContentsMargins(0, 0, 0, 0)
        tab2_layout.setSpacing(0)
        tab2_layout.addWidget(self.intensity_projection_controls_widget)
        tab2_layout.addWidget(self.fusion_controls_widget)
        tab2_layout.addStretch()
        tab_widget.addTab(tab2_widget, "Combine/Fuse")
        
        right_layout.addWidget(tab_widget)
        
        # Add series navigator to main window
        self.main_window.set_series_navigator(self.series_navigator)
    
    def _connect_signals(self) -> None:
        """Connect signals between components."""
        # Multi-window layout signals
        self.multi_window_layout.focused_subwindow_changed.connect(self._on_focused_subwindow_changed)
        self.multi_window_layout.layout_changed.connect(self._on_layout_changed)
        
        # Main window layout signal
        self.main_window.layout_changed.connect(self._on_main_window_layout_changed)
        
        # File operations
        self.main_window.open_file_requested.connect(self._open_files)
        self.main_window.open_folder_requested.connect(self._open_folder)
        self.main_window.open_recent_file_requested.connect(self._open_recent_file)
        self.main_window.open_files_from_paths_requested.connect(self._open_files_from_paths)
        # Files dropped will be connected per subwindow
        self.main_window.close_requested.connect(self._close_files)
        
        # Settings (shared, not per-subwindow)
        self.main_window.settings_requested.connect(self._open_settings)
        self.main_window.overlay_settings_requested.connect(self._open_overlay_settings)
        
        # Tag viewer (shared)
        self.main_window.tag_viewer_requested.connect(self._open_tag_viewer)
        
        # Overlay configuration (shared)
        self.main_window.overlay_config_requested.connect(self._open_overlay_config)
        
        # Annotation options (shared)
        self.main_window.annotation_options_requested.connect(self._open_annotation_options)
        
        # Quick Start Guide (shared)
        self.main_window.quick_start_guide_requested.connect(self._open_quick_start_guide)
        
        # Fusion Technical Documentation (shared)
        self.main_window.fusion_technical_doc_requested.connect(self._open_fusion_technical_doc)
        
        # Tag Export (shared)
        self.main_window.tag_export_requested.connect(self._open_tag_export)
        
        # Histogram (shared)
        self.main_window.histogram_requested.connect(self.dialog_coordinator.open_histogram)
        
        # Export (shared)
        self.main_window.export_requested.connect(self._open_export)
        
        # Undo/Redo tag edits (shared)
        # Undo/redo signals (for both tag edits and annotations)
        self.main_window.undo_tag_edit_requested.connect(self._on_undo_requested)
        self.main_window.redo_tag_edit_requested.connect(self._on_redo_requested)
        
        # Annotation copy/paste (shared)
        self.main_window.copy_annotation_requested.connect(self._copy_annotations)
        self.main_window.paste_annotation_requested.connect(self._paste_annotations)
        
        # Privacy view toggle (shared)
        self.main_window.privacy_view_toggled.connect(self._on_privacy_view_toggled)
        
        # Theme change (shared) - update fusion status text colors
        self.main_window.theme_changed.connect(self.fusion_controls_widget.update_status_text_colors)
        
        # About this File (shared)
        self.main_window.about_this_file_requested.connect(self._open_about_this_file)
        
        # Customizations export/import (shared)
        self.main_window.export_customizations_requested.connect(self._on_export_customizations)
        self.main_window.import_customizations_requested.connect(self._on_import_customizations)

        # Tag export presets export/import (shared)
        self.main_window.export_tag_presets_requested.connect(self._on_export_tag_presets)
        self.main_window.import_tag_presets_requested.connect(self._on_import_tag_presets)
        
        # Connect signals for all subwindows
        self._connect_subwindow_signals()
        
        # Connect signals for focused subwindow (initial)
        self._connect_focused_subwindow_signals()
    
    def _on_focused_subwindow_changed(self, subwindow: SubWindowContainer) -> None:
        """Handle focused subwindow change."""
        subwindows = self.multi_window_layout.get_all_subwindows()
        focused_idx = subwindows.index(subwindow) if subwindow in subwindows else -1
        # print(f"[DEBUG-OVERLAY] ===== FOCUS CHANGED to subwindow {focused_idx} =====")
        # Disconnect signals from previous focused subwindow
        self._disconnect_focused_subwindow_signals()
        
        # Update references
        self._update_focused_subwindow_references()
        
        # Log which managers we're now using
        if focused_idx >= 0 and focused_idx in self.subwindow_managers:
            managers = self.subwindow_managers[focused_idx]
            roi_manager = managers.get('roi_manager')
            roi_coordinator = managers.get('roi_coordinator')
            # print(f"[DEBUG-OVERLAY] Focus changed: Using roi_manager={id(roi_manager)}, "
            #       f"roi_coordinator={id(roi_coordinator)}, scene={id(self.image_viewer.scene) if self.image_viewer else None}")
        
        # Connect signals for new focused subwindow
        self._connect_focused_subwindow_signals()
        
        # Update keyboard event handler's reset_view_callback to use focused subwindow's view_state_manager
        if self.keyboard_event_handler and self.view_state_manager:
            self.keyboard_event_handler.reset_view_callback = self.view_state_manager.reset_view
        
        # Update ROI list panel's ROI manager to use focused subwindow's ROI manager
        if self.roi_list_panel and self.roi_manager:
            self.roi_list_panel.set_roi_manager(self.roi_manager)
            # Update ROI list for current slice of focused subwindow
        
        # Update series navigator highlighting to reflect focused subwindow's series
        if focused_idx >= 0 and focused_idx in self.subwindow_data:
            data = self.subwindow_data[focused_idx]
            focused_series_uid = data.get('current_series_uid', '')
            focused_study_uid = data.get('current_study_uid', '')
            if focused_series_uid and focused_study_uid and self.series_navigator:
                self.series_navigator.set_current_series(focused_series_uid, focused_study_uid)
            if self.current_dataset is not None:
                study_uid = getattr(self.current_dataset, 'StudyInstanceUID', '')
                series_uid = get_composite_series_key(self.current_dataset)
                # Use current_slice_index as instance identifier (same as display_rois_for_slice)
                instance_identifier = self.current_slice_index
                self.roi_list_panel.update_roi_list(study_uid, series_uid, instance_identifier)
        
        # Clear selected ROI if it doesn't belong to the new manager
        if self.roi_manager:
            selected_roi = self.roi_manager.get_selected_roi()
            if selected_roi:
                # Verify the selected ROI belongs to this manager
                roi_belongs = False
                for roi_list in self.roi_manager.rois.values():
                    if selected_roi in roi_list:
                        roi_belongs = True
                        break
                
                # print(f"[DEBUG-OVERLAY] Focus changed: Selected ROI is {id(selected_roi)}")
                # print(f"[DEBUG-OVERLAY]   Selected ROI belongs to manager: {roi_belongs}")
                
                if not roi_belongs:
                    # Clear the selection - it belongs to a different manager
                    # print(f"[DEBUG-OVERLAY] Clearing selected ROI {id(selected_roi)} - doesn't belong to manager {id(self.roi_manager)}")
                    self.roi_manager.select_roi(None)
            else:
                # print(f"[DEBUG-OVERLAY] Focus changed: No ROI selected")
                pass
        
        # Update right panel
        self._update_right_panel_for_focused_subwindow()
        
        # Update series navigator highlighting
        self._update_series_navigator_highlighting()
        
        # Update About This File dialog if open
        self._update_about_this_file_dialog()
    
    def _update_series_navigator_highlighting(self) -> None:
        """Update series navigator highlighting based on focused subwindow's series."""
        # Get focused subwindow's series and study UID for highlighting
        focused_idx = self.focused_subwindow_index
        if focused_idx in self.subwindow_data:
            data = self.subwindow_data[focused_idx]
            focused_series_uid = data.get('current_series_uid', '')
            focused_study_uid = data.get('current_study_uid', '')
            if focused_series_uid and focused_study_uid:
                self.series_navigator.set_current_series(focused_series_uid, focused_study_uid)
            elif focused_series_uid:
                self.series_navigator.set_current_series(focused_series_uid)
    
    def _on_layout_changed(self, layout_mode: str) -> None:
        """Handle layout mode change from multi-window layout."""
        # Save to config
        self.config_manager.set_multi_window_layout(layout_mode)
        
        # Update main window menu state
        self.main_window.set_layout_mode(layout_mode)
        
        # Capture scene centers for all subwindows BEFORE layout change
        # This uses the same mechanism as series navigator show/hide
        # It preserves the viewport center so we can restore it after layout change
        subwindows = self.multi_window_layout.get_all_subwindows()
        for idx, subwindow in enumerate(subwindows):
            if subwindow and idx in self.subwindow_managers:
                managers = self.subwindow_managers[idx]
                if 'view_state_manager' in managers:
                    managers['view_state_manager'].handle_viewport_resizing()
        
        # Reinitialize subwindow managers if needed (when subwindows are added/removed)
        # For now, subwindows are created on demand, so we may need to create managers for new ones
        self._ensure_all_subwindows_have_managers()
        
        # Reconnect signals for any newly created subwindows
        self._connect_subwindow_signals()
        
        # After layout change completes, trigger viewport_resized for all subwindows
        # This will fit images to view and restore centers using the same logic as series navigator
        from PySide6.QtCore import QTimer
        def trigger_viewport_resized():
            """Trigger viewport_resized for all subwindows after layout change."""
            subwindows = self.multi_window_layout.get_all_subwindows()
            for idx, subwindow in enumerate(subwindows):
                if subwindow and idx in self.subwindow_managers:
                    managers = self.subwindow_managers[idx]
                    if 'view_state_manager' in managers:
                        managers['view_state_manager'].handle_viewport_resized()
        
        # Use QTimer to defer until after layout processing completes
        # Increase delay to ensure viewport geometry is fully updated
        QTimer.singleShot(100, trigger_viewport_resized)
    
    def _on_main_window_layout_changed(self, layout_mode: str) -> None:
        """Handle layout mode change from main window menu."""
        self.multi_window_layout.set_layout(layout_mode)
    
    def _capture_subwindow_view_states(self) -> Dict[int, Dict]:
        """
        Capture view state for all existing subwindows before layout change.
        
        Returns:
            Dictionary mapping subwindow index to view state dict:
            {index: {'viewport_rect': QRectF, 'zoom': float, 'scene_center': QPointF, 'old_size': QSize}}
        """
        view_states = {}
        subwindows = self.multi_window_layout.get_all_subwindows()
        
        for idx, subwindow in enumerate(subwindows):
            if subwindow is None:
                continue
            
            image_viewer = subwindow.image_viewer
            if image_viewer is None:
                continue
            
            # Only capture if image is displayed
            if image_viewer.image_item is None:
                continue
            
            # Get viewport rect in scene coordinates
            viewport_rect = image_viewer.viewport().rect()
            top_left = image_viewer.mapToScene(viewport_rect.topLeft())
            bottom_right = image_viewer.mapToScene(viewport_rect.bottomRight())
            viewport_rect_scene = QRectF(top_left, bottom_right)
            
            # Get current zoom
            zoom = image_viewer.current_zoom
            
            # Get scene center (viewport center in scene coordinates)
            viewport_center = QPointF(viewport_rect.width() / 2.0, viewport_rect.height() / 2.0)
            scene_center = image_viewer.mapToScene(viewport_center.toPoint())
            
            # Get old subwindow size
            old_size = subwindow.size()
            
            view_states[idx] = {
                'viewport_rect': viewport_rect_scene,
                'zoom': zoom,
                'scene_center': scene_center,
                'old_size': old_size
            }
        
        return view_states
    
    def _restore_subwindow_views(self, view_states: Dict[int, Dict]) -> None:
        """
        Restore subwindow views after layout change.
        
        For layout changes, we want to fit images to the new viewport size
        rather than preserving the exact visible area, so images scale appropriately.
        
        Args:
            view_states: Dictionary of captured view states from _capture_subwindow_view_states()
        """
        print(f"[DEBUG-LAYOUT] _restore_subwindow_views called with {len(view_states)} view states")
        subwindows = self.multi_window_layout.get_all_subwindows()
        print(f"[DEBUG-LAYOUT] Found {len(subwindows)} subwindows")
        
        for idx, view_state in view_states.items():
            try:
                # Check if this subwindow still exists
                if idx >= len(subwindows) or subwindows[idx] is None:
                    print(f"[DEBUG-LAYOUT] Subwindow {idx} doesn't exist or is None")
                    continue
                
                subwindow = subwindows[idx]
                image_viewer = subwindow.image_viewer
                if image_viewer is None:
                    print(f"[DEBUG-LAYOUT] Subwindow {idx} has no image_viewer")
                    continue
                
                # Check if image is still displayed
                if image_viewer.image_item is None:
                    print(f"[DEBUG-LAYOUT] Subwindow {idx} has no image_item")
                    continue
                
                print(f"[DEBUG-LAYOUT] Subwindow {idx}: image_item exists, scheduling fit_to_view")
                
                # For layout changes, fit the image to the new viewport size
                # This ensures images scale appropriately when switching between 1x1, 1x2, 2x1, 2x2 layouts
                # Use QTimer to ensure viewport size is updated before fitting
                from PySide6.QtCore import QTimer
                def fit_image_to_viewport():
                    """Fit image to viewport after layout change."""
                    print(f"[DEBUG-LAYOUT] fit_image_to_viewport callback called for subwindow {idx}")
                    if image_viewer.image_item is not None:
                        # Verify viewport has actually resized before fitting
                        viewport = image_viewer.viewport()
                        if viewport:
                            viewport_width = viewport.width()
                            viewport_height = viewport.height()
                            print(f"[DEBUG-LAYOUT] Subwindow {idx}: viewport size = {viewport_width}x{viewport_height}")
                            if viewport_width > 0 and viewport_height > 0:
                                print(f"[DEBUG-LAYOUT] Subwindow {idx}: Calling fit_to_view(center_image=True)")
                                # Fit to view with centering for better UX
                                image_viewer.fit_to_view(center_image=True)
                            else:
                                print(f"[DEBUG-LAYOUT] Subwindow {idx}: Viewport size invalid, skipping fit_to_view")
                        else:
                            print(f"[DEBUG-LAYOUT] Subwindow {idx}: No viewport found")
                    else:
                        print(f"[DEBUG-LAYOUT] Subwindow {idx}: image_item is None in callback")
                
                # Increase delay to ensure viewport geometry is fully updated
                # and overlay widget resize has completed
                QTimer.singleShot(100, fit_image_to_viewport)
                
            except Exception as e:
                # Handle any errors gracefully - don't break layout change
                print(f"[DEBUG-LAYOUT] Error restoring view for subwindow {idx}: {e}")
                import traceback
                traceback.print_exc()
                continue
    
    def _ensure_all_subwindows_have_managers(self) -> None:
        """Ensure all visible subwindows have managers initialized."""
        subwindows = self.multi_window_layout.get_all_subwindows()
        for idx, subwindow in enumerate(subwindows):
            if subwindow and idx not in self.subwindow_managers:
                # Create managers for this subwindow
                # Use the same logic as _initialize_subwindow_managers but only for this subwindow
                self._create_managers_for_subwindow(idx, subwindow)
        
        # Connect transform/zoom signals for any newly created subwindows
        self._connect_all_subwindow_transform_signals()
    
    def _connect_subwindow_signals(self) -> None:
        """Connect signals that apply to all subwindows."""
        subwindows = self.multi_window_layout.get_all_subwindows()
        for idx, subwindow in enumerate(subwindows):
            if subwindow:
                image_viewer = subwindow.image_viewer
                # Connect files dropped for all subwindows
                image_viewer.files_dropped.connect(self._open_files_from_paths)
                
                # Connect layout change requested from context menu
                image_viewer.layout_change_requested.connect(self._on_layout_change_requested)
                
                # Connect privacy view toggle from context menu
                image_viewer.privacy_view_toggled.connect(self._on_privacy_view_toggled)
                image_viewer.about_this_file_requested.connect(self._open_about_this_file)
                image_viewer.histogram_requested.connect(self.dialog_coordinator.open_histogram)
                
                # Set file path callback for "Show file" context menu
                image_viewer.get_file_path_callback = lambda idx=idx: self._get_current_slice_file_path(idx)
                
                # Connect assign series request
                subwindow.assign_series_requested.connect(self._on_assign_series_requested)
        
        # Connect transform/zoom signals for all subwindows to their own ViewStateManager
        # This ensures overlays update correctly when panning/zooming in any subwindow
        self._connect_all_subwindow_transform_signals()
    
    def _connect_all_subwindow_transform_signals(self) -> None:
        """Connect transform_changed and zoom_changed signals for all subwindows to their own ViewStateManager."""
        subwindows = self.multi_window_layout.get_all_subwindows()
        
        for idx, subwindow in enumerate(subwindows):
            if subwindow and idx in self.subwindow_managers:
                image_viewer = subwindow.image_viewer
                managers = self.subwindow_managers[idx]
                view_state_manager = managers.get('view_state_manager')
                
                if view_state_manager:
                    # Disconnect any existing ViewStateManager connections first to avoid duplicates
                    # Note: For focused subwindow, _connect_focused_subwindow_signals() will also connect
                    # additional handlers (like zoom_display_widget), but we want the ViewStateManager
                    # connection for all subwindows to ensure overlays update correctly
                    with warnings.catch_warnings():
                        warnings.filterwarnings('ignore', category=RuntimeWarning, message='.*Failed to disconnect.*')
                        try:
                            image_viewer.transform_changed.disconnect(view_state_manager.handle_transform_changed)
                        except (TypeError, RuntimeError):
                            pass
                        try:
                            image_viewer.zoom_changed.disconnect(view_state_manager.handle_zoom_changed)
                        except (TypeError, RuntimeError):
                            pass
                    
                    # Connect to this subwindow's ViewStateManager
                    image_viewer.transform_changed.connect(view_state_manager.handle_transform_changed)
                    image_viewer.zoom_changed.connect(view_state_manager.handle_zoom_changed)
    
    def _connect_all_subwindow_context_menu_signals(self) -> None:
        """Connect context menu signals for all subwindows."""
        subwindows = self.multi_window_layout.get_all_subwindows()
        for idx, subwindow in enumerate(subwindows):
            if subwindow:
                image_viewer = subwindow.image_viewer
                image_viewer.context_menu_scroll_wheel_mode_changed.connect(
                    self.mouse_mode_handler.handle_context_menu_scroll_wheel_mode_changed
                )
    
    def _on_layout_change_requested(self, layout_mode: str) -> None:
        """Handle layout change request from image viewer context menu."""
        self.multi_window_layout.set_layout(layout_mode)
    
    def _on_assign_series_requested(self, series_uid: str, slice_index: int) -> None:
        """Handle series assignment request from subwindow."""
        # Find which subwindow requested the assignment
        sender = self.sender()
        if isinstance(sender, SubWindowContainer):
            # Assign series/slice to this subwindow
            self._assign_series_to_subwindow(sender, series_uid, slice_index)
    
    def _assign_series_to_subwindow(self, subwindow: SubWindowContainer, series_uid: str, slice_index: int) -> None:
        """Assign a series/slice to a specific subwindow."""
        subwindows = self.multi_window_layout.get_all_subwindows()
        if subwindow not in subwindows:
            return
        
        idx = subwindows.index(subwindow)
        
        # Ensure managers exist for this subwindow
        if idx not in self.subwindow_managers:
            # Need to create managers for this subwindow
            # This can happen if layout changed and new subwindows were created
            self._ensure_all_subwindows_have_managers()
        
        # Find the series in current studies
        if not self.current_studies:
            return
        
        # Find study and series
        target_study_uid = None
        for study_uid, series_dict in self.current_studies.items():
            if series_uid in series_dict:
                target_study_uid = study_uid
                break
        
        if target_study_uid is None:
            return
        
        # Get series datasets
        series_datasets = self.current_studies[target_study_uid][series_uid]
        if not series_datasets:
            return
        
        # Clamp slice index
        slice_index = max(0, min(slice_index, len(series_datasets) - 1))
        
        # Update subwindow data
        if idx not in self.subwindow_data:
            self.subwindow_data[idx] = {}
        
        self.subwindow_data[idx]['current_study_uid'] = target_study_uid
        self.subwindow_data[idx]['current_series_uid'] = series_uid
        self.subwindow_data[idx]['current_slice_index'] = slice_index
        self.subwindow_data[idx]['current_datasets'] = series_datasets
        self.subwindow_data[idx]['current_dataset'] = series_datasets[slice_index] if slice_index < len(series_datasets) else series_datasets[0]
        
        # Update subwindow assignment
        subwindow.set_assigned_series(series_uid, slice_index)
        
        # Display the slice in this subwindow
        if idx in self.subwindow_managers:
            managers = self.subwindow_managers[idx]
            slice_display_manager = managers['slice_display_manager']
            # Only update global window/level controls and metadata panel if this is the focused subwindow
            # For unfocused subwindows, only update internal ViewStateManager values
            is_focused = (subwindow == self.multi_window_layout.get_focused_subwindow())
            slice_display_manager.display_slice(
                self.subwindow_data[idx]['current_dataset'],
                self.current_studies,
                target_study_uid,
                series_uid,
                slice_index,
                update_controls=is_focused,
                update_metadata=is_focused
            )
        
        # Update slice navigator if this is the focused subwindow
        # This ensures navigation works correctly when a series is assigned to the focused subwindow
        if subwindow == self.multi_window_layout.get_focused_subwindow():
            # Update slice navigator for focused subwindow
            self.slice_navigator.set_total_slices(len(series_datasets))
            self.slice_navigator.blockSignals(True)
            self.slice_navigator.current_slice_index = slice_index
            self.slice_navigator.blockSignals(False)
        
        # Update series navigator highlighting only if this is the focused subwindow
        # This ensures highlighting reflects the focused subwindow's series, not unfocused ones
        if subwindow == self.multi_window_layout.get_focused_subwindow():
            self.series_navigator.set_current_series(series_uid, target_study_uid)
        
        # If this subwindow is the focused one, also update legacy references and highlighting
        if subwindow == self.multi_window_layout.get_focused_subwindow():
            self.current_series_uid = series_uid
            self.current_study_uid = target_study_uid
            self.current_slice_index = slice_index
            self.current_dataset = self.subwindow_data[idx]['current_dataset']
            self._update_series_navigator_highlighting()
            # Update right panel to reflect new series (including fusion base series)
            self._update_right_panel_for_focused_subwindow()
    
    def _disconnect_focused_subwindow_signals(self) -> None:
        """Disconnect signals from previously focused subwindow."""
        if self.image_viewer is None:
            return
        
        # Suppress RuntimeWarning about failed signal disconnects
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', category=RuntimeWarning, message='.*Failed to disconnect.*')
            
            # print("[DEBUG] Disconnecting signals from focused subwindow ImageViewer")
            
            try:
                # Annotation options
                self.image_viewer.annotation_options_requested.disconnect()
            except (TypeError, RuntimeError):
                pass  # Signal not connected or object deleted
            
            try:
                # ROI drawing signals
                self.image_viewer.roi_drawing_started.disconnect()
                self.image_viewer.roi_drawing_updated.disconnect()
                self.image_viewer.roi_drawing_finished.disconnect()
            except (TypeError, RuntimeError):
                pass
            
            try:
                # Measurement signals
                self.image_viewer.measurement_started.disconnect()
                self.image_viewer.measurement_updated.disconnect()
                self.image_viewer.measurement_finished.disconnect()
            except (TypeError, RuntimeError):
                pass
            
            try:
                # ROI click signals
                self.image_viewer.roi_clicked.disconnect()
                self.image_viewer.image_clicked_no_roi.disconnect()
            except (TypeError, RuntimeError):
                pass
            
            try:
                # ROI delete signals
                self.image_viewer.roi_delete_requested.disconnect()
                self.image_viewer.measurement_delete_requested.disconnect()
            except (TypeError, RuntimeError):
                pass
            
            try:
                # ROI statistics signals
                self.image_viewer.roi_statistics_overlay_toggle_requested.disconnect()
                self.image_viewer.roi_statistics_selection_changed.disconnect()
            except (TypeError, RuntimeError):
                pass
            
            try:
                # Scene selection changed
                if self.image_viewer.scene is not None:
                    self.image_viewer.scene.selectionChanged.disconnect()
            except (TypeError, RuntimeError, AttributeError):
                pass
            
            try:
                # Scroll wheel for slice navigation
                self.image_viewer.wheel_event_for_slice.disconnect()
            except (TypeError, RuntimeError):
                pass
            
            try:
                # Pixel info
                self.image_viewer.pixel_info_changed.disconnect()
            except (TypeError, RuntimeError):
                pass
            
            try:
                # Window/Level preset selection
                self.image_viewer.window_level_preset_selected.disconnect()
            except (TypeError, RuntimeError):
                pass
            
            try:
                # Intensity projection context menu signals
                self.image_viewer.projection_enabled_changed.disconnect()
                self.image_viewer.projection_type_changed.disconnect()
                self.image_viewer.projection_slice_count_changed.disconnect()
            except (TypeError, RuntimeError):
                pass
            
            try:
                # Context menu changes
                self.image_viewer.context_menu_mouse_mode_changed.disconnect()
                self.image_viewer.context_menu_scroll_wheel_mode_changed.disconnect()
                self.image_viewer.context_menu_rescale_toggle_changed.disconnect()
            except (TypeError, RuntimeError):
                pass
            
            try:
                # Zoom and transform changes
                self.image_viewer.zoom_changed.disconnect()
                self.image_viewer.transform_changed.disconnect()
            except (TypeError, RuntimeError):
                pass
            
            try:
                # Arrow key navigation
                self.image_viewer.arrow_key_pressed.disconnect()
            except (TypeError, RuntimeError):
                pass
            
            try:
                # Right mouse drag for window/level
                self.image_viewer.right_mouse_press_for_drag.disconnect()
                self.image_viewer.window_level_drag_changed.disconnect()
            except (TypeError, RuntimeError):
                pass
            
            try:
                # Series navigation (CRITICAL - this is causing the double navigation)
                self.image_viewer.series_navigation_requested.disconnect()
            except (TypeError, RuntimeError):
                pass
            
            try:
                # ROI list panel signals
                self.roi_list_panel.roi_selected.disconnect()
                self.roi_list_panel.roi_deleted.disconnect()
                self.roi_list_panel.delete_all_requested.disconnect()
            except (TypeError, RuntimeError, AttributeError):
                pass
            
            try:
                # Crosshair signals
                if hasattr(self, 'image_viewer') and self.image_viewer:
                    self.image_viewer.crosshair_clicked.disconnect()
                    self.image_viewer.crosshair_delete_requested.disconnect()
            except (TypeError, RuntimeError, AttributeError):
                pass
            
            try:
                # Slice navigator signals
                self.slice_navigator.slice_changed.disconnect()
            except (TypeError, RuntimeError, AttributeError):
                pass
            
            try:
                # Window/level controls
                self.window_level_controls.window_changed.disconnect()
            except (TypeError, RuntimeError, AttributeError):
                pass
            
            try:
                # Intensity projection controls
                self.intensity_projection_controls_widget.enabled_changed.disconnect()
                self.intensity_projection_controls_widget.projection_type_changed.disconnect()
                self.intensity_projection_controls_widget.slice_count_changed.disconnect()
            except (TypeError, RuntimeError, AttributeError):
                pass
            
            try:
                # Mouse mode and scroll wheel mode changes
                self.main_window.mouse_mode_changed.disconnect()
                self.main_window.scroll_wheel_mode_changed.disconnect()
            except (TypeError, RuntimeError, AttributeError):
                pass
            
            try:
                # Rescale toggle from toolbar
                self.main_window.rescale_toggle_changed.disconnect()
            except (TypeError, RuntimeError, AttributeError):
                pass
            
            try:
                # Series navigation from main window
                self.main_window.series_navigation_requested.disconnect()
            except (TypeError, RuntimeError, AttributeError):
                pass
            
            try:
                # Overlay font size and color changes
                self.main_window.overlay_font_size_changed.disconnect()
                self.main_window.overlay_font_color_changed.disconnect()
            except (TypeError, RuntimeError, AttributeError):
                pass
            
            try:
                # Zoom display widget
                self.zoom_display_widget.zoom_changed.disconnect()
            except (TypeError, RuntimeError, AttributeError):
                pass
        
        # Disconnect fusion signals from previous focused subwindow's coordinator
        try:
            if hasattr(self, '_previous_fusion_coordinator') and self._previous_fusion_coordinator is not None:
                self._previous_fusion_coordinator.disconnect_fusion_controls_signals()
                self._previous_fusion_coordinator = None
        except (TypeError, RuntimeError, AttributeError):
            pass
        
        # print("[DEBUG] Finished disconnecting signals from focused subwindow ImageViewer")
    
    def _connect_focused_subwindow_signals(self) -> None:
        """Connect signals for the currently focused subwindow."""
        # CRITICAL: Disconnect any existing connections first to prevent duplicates
        self._disconnect_focused_subwindow_signals()
        
        if self.image_viewer is None:
            return
        
        # print("[DEBUG] Connecting signals for focused subwindow ImageViewer")
        
        # CRITICAL FIX: Update the redisplay callback to use the current focused subwindow index
        # This ensures window/level changes redisplay the correct subwindow
        if self.view_state_manager:
            focused_idx = self.focused_subwindow_index
            # print(f"[DEBUG-WL] Updating redisplay callback for focused subwindow idx={focused_idx}")
            self.view_state_manager.set_redisplay_slice_callback(
                lambda preserve_view=False: self._redisplay_subwindow_slice(focused_idx, preserve_view)
            )
        
        # Annotation options from image viewer
        self.image_viewer.annotation_options_requested.connect(self._open_annotation_options)
        
        # ROI drawing signals
        self.image_viewer.roi_drawing_started.connect(self.roi_coordinator.handle_roi_drawing_started)
        self.image_viewer.roi_drawing_updated.connect(self.roi_coordinator.handle_roi_drawing_updated)
        self.image_viewer.roi_drawing_finished.connect(self.roi_coordinator.handle_roi_drawing_finished)
        
        # Measurement signals
        self.image_viewer.measurement_started.connect(self.measurement_coordinator.handle_measurement_started)
        self.image_viewer.measurement_updated.connect(self.measurement_coordinator.handle_measurement_updated)
        self.image_viewer.measurement_finished.connect(self.measurement_coordinator.handle_measurement_finished)
        
        # Text annotation signals
        if hasattr(self, 'text_annotation_coordinator') and self.text_annotation_coordinator is not None:
            self.image_viewer.text_annotation_started.connect(self.text_annotation_coordinator.handle_text_annotation_started)
            self.image_viewer.text_annotation_finished.connect(self.text_annotation_coordinator.handle_text_annotation_finished)
        
        # Arrow annotation signals
        if hasattr(self, 'arrow_annotation_coordinator') and self.arrow_annotation_coordinator is not None:
            self.image_viewer.arrow_annotation_started.connect(self.arrow_annotation_coordinator.handle_arrow_annotation_started)
            self.image_viewer.arrow_annotation_updated.connect(self.arrow_annotation_coordinator.handle_arrow_annotation_updated)
            self.image_viewer.arrow_annotation_finished.connect(self.arrow_annotation_coordinator.handle_arrow_annotation_finished)
        
        # Crosshair signals
        if hasattr(self, 'crosshair_coordinator') and self.crosshair_coordinator is not None:
            self.image_viewer.crosshair_clicked.connect(self.crosshair_coordinator.handle_crosshair_clicked)
        
        # ROI click signal
        self.image_viewer.roi_clicked.connect(self.roi_coordinator.handle_roi_clicked)
        self.image_viewer.image_clicked_no_roi.connect(self.roi_coordinator.handle_image_clicked_no_roi)
        
        # ROI delete signal (from right-click context menu)
        self.image_viewer.roi_delete_requested.connect(self.roi_coordinator.handle_roi_delete_requested)
        self.image_viewer.measurement_delete_requested.connect(self.measurement_coordinator.handle_measurement_delete_requested)
        if hasattr(self, 'text_annotation_coordinator') and self.text_annotation_coordinator is not None:
            self.image_viewer.text_annotation_delete_requested.connect(self.text_annotation_coordinator.handle_text_annotation_delete_requested)
        if hasattr(self, 'arrow_annotation_coordinator') and self.arrow_annotation_coordinator is not None:
            self.image_viewer.arrow_annotation_delete_requested.connect(self.arrow_annotation_coordinator.handle_arrow_annotation_delete_requested)
        if hasattr(self, 'crosshair_coordinator') and self.crosshair_coordinator is not None:
            self.image_viewer.crosshair_delete_requested.connect(self.crosshair_coordinator.handle_crosshair_delete_requested)
        
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
        
        # Set callback for available series (for context menu)
        def get_available_series() -> list:
            """Get list of available series for context menu."""
            if not self.current_studies:
                return []
            series_list = []
            for study_uid, series_dict in self.current_studies.items():
                for series_uid, datasets in series_dict.items():
                    if datasets:
                        first_dataset = datasets[0]
                        series_num = getattr(first_dataset, 'SeriesNumber', '')
                        series_desc = getattr(first_dataset, 'SeriesDescription', 'Unknown Series')
                        modality = getattr(first_dataset, 'Modality', '')
                        series_name = f"Series {series_num}: {series_desc} ({modality})"
                        series_list.append((series_uid, series_name))
            return series_list
        self.image_viewer.get_available_series_callback = get_available_series
        
        # Right mouse drag for window/level adjustment
        self.image_viewer.right_mouse_press_for_drag.connect(self.view_state_manager.handle_right_mouse_press_for_drag)
        self.image_viewer.window_level_drag_changed.connect(self.view_state_manager.handle_window_level_drag)
        
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
        
        # Update keyboard event handler callbacks to use focused subwindow
        if self.keyboard_event_handler:
            self.keyboard_event_handler.delete_all_rois_callback = self.roi_coordinator.delete_all_rois_current_slice
            self.keyboard_event_handler.invert_image_callback = self.image_viewer.invert_image
            if hasattr(self, 'text_annotation_coordinator') and self.text_annotation_coordinator:
                self.keyboard_event_handler.delete_text_annotation_callback = self.text_annotation_coordinator.handle_text_annotation_delete_requested
            if hasattr(self, 'arrow_annotation_coordinator') and self.arrow_annotation_coordinator:
                self.keyboard_event_handler.delete_arrow_annotation_callback = self.arrow_annotation_coordinator.handle_arrow_annotation_delete_requested
        
        # Window/level
        self.window_level_controls.window_changed.connect(self.view_state_manager.handle_window_changed)
        
        # Update histogram dialog when window/level changes
        def update_histogram_if_visible():
            if (hasattr(self, 'dialog_coordinator') and 
                self.dialog_coordinator.histogram_dialog and 
                self.dialog_coordinator.histogram_dialog.isVisible()):
                self.dialog_coordinator.histogram_dialog.update_histogram()
        self.window_level_controls.window_changed.connect(update_histogram_if_visible)
        
        # Window/Level preset selection
        self.image_viewer.window_level_preset_selected.connect(self._on_window_level_preset_selected)
        
        # Intensity projection controls
        self.intensity_projection_controls_widget.enabled_changed.connect(self._on_projection_enabled_changed)
        self.intensity_projection_controls_widget.projection_type_changed.connect(self._on_projection_type_changed)
        self.intensity_projection_controls_widget.slice_count_changed.connect(self._on_projection_slice_count_changed)
        
        # Fusion controls - connect to focused subwindow's coordinator
        if self.fusion_coordinator is not None:
            self.fusion_coordinator.connect_fusion_controls_signals()
            # Sync UI from focused subwindow's fusion handler state
            self.fusion_coordinator.sync_ui_from_handler_state()
            # Store reference for disconnection on next focus change
            self._previous_fusion_coordinator = self.fusion_coordinator
        
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
        # Connect to _on_scroll_wheel_mode_changed() which updates all subwindows
        self.main_window.scroll_wheel_mode_changed.connect(self._on_scroll_wheel_mode_changed)
        
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
        self.series_navigator.series_navigation_requested.connect(
            self._on_series_navigation_requested,
            Qt.ConnectionType.UniqueConnection
        )
        
        # Overlay font size and color changes (will be handled by _on_overlay_font_size_changed and _on_overlay_font_color_changed)
        self.main_window.overlay_font_size_changed.connect(self._on_overlay_font_size_changed)
        self.main_window.overlay_font_color_changed.connect(self._on_overlay_font_color_changed)
        
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
        self.main_window.reset_all_views_requested.connect(self._on_reset_all_views)
        self.image_viewer.reset_all_views_requested.connect(self._on_reset_all_views)
        
        # Clear measurements signals
        self.main_window.clear_measurements_requested.connect(self.measurement_coordinator.handle_clear_measurements)
        self.image_viewer.clear_measurements_requested.connect(self.measurement_coordinator.handle_clear_measurements)
        
        # Histogram signals
        self.image_viewer.histogram_requested.connect(self.dialog_coordinator.open_histogram)
        
        # Toggle overlay signal
        self.image_viewer.toggle_overlay_requested.connect(self.overlay_coordinator.handle_toggle_overlay)
        
        # Viewport resize (when splitter moves)
        self.main_window.viewport_resizing.connect(self.view_state_manager.handle_viewport_resizing)
        self.main_window.viewport_resized.connect(self.view_state_manager.handle_viewport_resized)
        
        # Update histogram dialog when focused subwindow changes
        self.multi_window_layout.focused_subwindow_changed.connect(
            self._update_histogram_dialog_if_visible
        )
        
        # Update histogram dialog when slice changes
        self.slice_navigator.slice_changed.connect(
            self._update_histogram_dialog_if_visible
        )
        
        # Series navigator signals
        self.series_navigator.series_selected.connect(self._on_series_navigator_selected)
        self.series_navigator.show_file_requested.connect(self._on_show_file_from_series)
        self.series_navigator.about_this_file_requested.connect(self._on_about_this_file_from_series)
        self.image_viewer.toggle_series_navigator_requested.connect(self.main_window.toggle_series_navigator)
        
        # Tag edit signals
        self.metadata_panel.tag_edited.connect(self._on_tag_edited)
        
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
        self.cine_controls_widget.loop_start_set.connect(self._on_cine_loop_start_set)
        self.cine_controls_widget.loop_end_set.connect(self._on_cine_loop_end_set)
        self.cine_controls_widget.loop_bounds_cleared.connect(self._on_cine_loop_bounds_cleared)
        
        # Cine control signals from context menu
        self.image_viewer.cine_play_requested.connect(self._on_cine_play)
        self.image_viewer.cine_pause_requested.connect(self._on_cine_pause)
        self.image_viewer.cine_stop_requested.connect(self._on_cine_stop)
        self.image_viewer.cine_loop_toggled.connect(self._on_cine_loop_toggled)
        
        # Set callback to get cine loop state for context menu
        self.image_viewer.get_cine_loop_state_callback = self._get_cine_loop_state
        
        # Connect assign series signal from image viewer context menu
        self.image_viewer.assign_series_requested.connect(self._on_assign_series_from_context_menu)
    
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
        Handle series navigation request from image viewer (focused subwindow only).
        
        Args:
            direction: -1 for left/previous series, 1 for right/next series
        """
        timestamp = time.time()
        # Try to determine signal source by checking call stack
        frame = inspect.currentframe()
        caller_frame = frame.f_back if frame else None
        caller_name = caller_frame.f_code.co_name if caller_frame else "unknown"
        caller_file = caller_frame.f_code.co_filename.split('/')[-1] if caller_frame else "unknown"
        print(f"[DEBUG-NAV] [{timestamp:.6f}] _on_series_navigation_requested: direction={direction}, caller={caller_name} in {caller_file}, lock={self._series_navigation_in_progress}")
        
        # Prevent concurrent navigation operations
        if self._series_navigation_in_progress:
            print(f"[DEBUG-NAV] [{timestamp:.6f}] Series navigation: Navigation already in progress, ignoring request")
            return
        
        # Set navigation lock
        self._series_navigation_in_progress = True
        print(f"[DEBUG-NAV] [{timestamp:.6f}] Series navigation: Lock acquired")
        
        try:
            # Get focused subwindow's data
            focused_idx = self.focused_subwindow_index
            if focused_idx not in self.subwindow_data:
                print(f"[DEBUG] Series navigation: subwindow {focused_idx} not in subwindow_data")
                return
            
            data = self.subwindow_data[focused_idx]
            focused_study_uid = data.get('current_study_uid', '')
            focused_series_uid = data.get('current_series_uid', '')
            focused_slice_index = data.get('current_slice_index', 0)
            
            # CRITICAL FIX: Extract actual composite series key from currently displayed dataset
            # This ensures we navigate from what's actually shown, not what's stored
            displayed_dataset = data.get('current_dataset')
            if displayed_dataset:
                extracted_series_uid = get_composite_series_key(displayed_dataset)
                extracted_study_uid = getattr(displayed_dataset, 'StudyInstanceUID', '')
                
                if extracted_series_uid and extracted_series_uid != focused_series_uid:
                    print(f"[DEBUG] Series navigation: MISMATCH at start! Stored={focused_series_uid}, Extracted={extracted_series_uid}")
                    print(f"[DEBUG]   Full stored UID: {focused_series_uid}")
                    print(f"[DEBUG]   Full extracted UID: {extracted_series_uid}")
                    print(f"[DEBUG]   Using extracted UID for navigation")
                    # Use the extracted UID - this is what's actually displayed
                    focused_series_uid = extracted_series_uid
                    focused_study_uid = extracted_study_uid
                    # Update subwindow_data immediately to fix the mismatch
                    data['current_series_uid'] = extracted_series_uid
                    data['current_study_uid'] = extracted_study_uid
            elif not focused_series_uid:
                # No series loaded - load first series (right arrow) or last series (left arrow)
                print(f"[DEBUG] Series navigation: No series loaded, attempting to load {'first' if direction > 0 else 'last'} series")
                
                # Need to get study_uid from somewhere - try to get it from current_studies
                if not self.current_studies:
                    print(f"[DEBUG] Series navigation: No studies loaded, cannot navigate")
                    return
                
                # Use the first study (or could use focused_study_uid if available)
                if not focused_study_uid:
                    # Get first study
                    focused_study_uid = list(self.current_studies.keys())[0]
                    data['current_study_uid'] = focused_study_uid
                
                study_series = self.current_studies.get(focused_study_uid, {})
                if not study_series:
                    print(f"[DEBUG] Series navigation: Study has no series, cannot navigate")
                    return
                
                # Build sorted list of series
                series_list = []
                for series_uid, datasets in study_series.items():
                    if datasets:
                        first_dataset = datasets[0]
                        series_number = getattr(first_dataset, 'SeriesNumber', None)
                        try:
                            series_num = int(series_number) if series_number is not None else 0
                        except (ValueError, TypeError):
                            series_num = 0
                        series_list.append((series_num, series_uid, datasets))
                
                series_list.sort(key=lambda x: x[0])
                
                if not series_list:
                    print(f"[DEBUG] Series navigation: No valid series in study, cannot navigate")
                    return
                
                # Load first series for right arrow, last series for left arrow
                if direction > 0:
                    # Right arrow: load first series
                    _, target_series_uid, target_datasets = series_list[0]
                    print(f"[DEBUG] Series navigation: Loading first series {target_series_uid[:20]}...")
                else:
                    # Left arrow: load last series
                    _, target_series_uid, target_datasets = series_list[-1]
                    print(f"[DEBUG] Series navigation: Loading last series {target_series_uid[:20]}...")
                
                # Update subwindow_data
                data['current_series_uid'] = target_series_uid
                data['current_study_uid'] = focused_study_uid
                data['current_dataset'] = target_datasets[0]
                data['current_slice_index'] = 0
                
                # Update legacy references
                self.current_series_uid = target_series_uid
                self.current_slice_index = 0
                self.current_dataset = target_datasets[0]
                self.current_study_uid = focused_study_uid
                
                # Set context
                self.slice_display_manager.set_current_data_context(
                    self.current_studies,
                    focused_study_uid,
                    target_series_uid,
                    0
                )
                
                # Display the series
                self.slice_display_manager.display_slice(
                    target_datasets[0],
                    self.current_studies,
                    focused_study_uid,
                    target_series_uid,
                    0
                )
                
                # Extract actual composite series key from the dataset that was displayed
                extracted_series_uid = get_composite_series_key(target_datasets[0])
                extracted_study_uid = getattr(target_datasets[0], 'StudyInstanceUID', '')
                
                # Sync subwindow_data with actual displayed data
                self.subwindow_data[focused_idx]['current_series_uid'] = extracted_series_uid
                self.subwindow_data[focused_idx]['current_study_uid'] = extracted_study_uid
                self.subwindow_data[focused_idx]['current_dataset'] = target_datasets[0]
                self.subwindow_data[focused_idx]['current_slice_index'] = 0
                
                # Update legacy references to match
                self.current_series_uid = extracted_series_uid
                self.current_study_uid = extracted_study_uid
                self.current_slice_index = 0
                self.current_dataset = target_datasets[0]
                
                # Update slice display manager context with extracted UIDs
                self.slice_display_manager.set_current_data_context(
                    self.current_studies,
                    extracted_study_uid,
                    extracted_series_uid,
                    0
                )
                
                # Update undo/redo state when dataset changes
                self._update_undo_redo_state()
                
                # Update slice navigator
                if self.current_studies and self.current_study_uid and self.current_series_uid:
                    datasets = self.current_studies[self.current_study_uid][self.current_series_uid]
                    self.slice_navigator.set_total_slices(len(datasets))
                    self.slice_navigator.set_current_slice(0)
                
                # Update series navigator highlighting using focused subwindow's data
                focused_idx = self.focused_subwindow_index
                if focused_idx in self.subwindow_data:
                    data = self.subwindow_data[focused_idx]
                    focused_series_uid = data.get('current_series_uid', '')
                    focused_study_uid = data.get('current_study_uid', '')
                    if focused_series_uid and focused_study_uid:
                        self.series_navigator.set_current_series(focused_series_uid, focused_study_uid)
                
                # Update cine player context
                self._update_cine_player_context()
                
                return  # Early return since we've handled the navigation
        
            print(f"[DEBUG] Series navigation: subwindow {focused_idx}, study={focused_study_uid[:20] if focused_study_uid else 'None'}..., "
                  f"series={focused_series_uid[:20] if focused_series_uid else 'None'}..., direction={direction}")
            
            # Ensure we have valid study UID and that the study exists in current_studies
            if not focused_study_uid or focused_study_uid not in self.current_studies:
                print(f"[DEBUG] Series navigation: Invalid study UID or study not in current_studies")
                return
            
            # Validate that the series_uid exists in the study (critical fix for skipping)
            study_series = self.current_studies[focused_study_uid]
            if focused_series_uid and focused_series_uid not in study_series:
                # Series doesn't exist - might be stale data
                # Use first series in study as fallback
                print(f"[DEBUG] Series navigation: Series {focused_series_uid[:20] if focused_series_uid else 'None'}... not found in study. "
                      f"Available series: {list(study_series.keys())[:3]}... (showing first 3)")
                if study_series:
                    # Get first series (sorted by SeriesNumber if available)
                    series_list = []
                    for series_uid, datasets in study_series.items():
                        if datasets:
                            first_dataset = datasets[0]
                            series_number = getattr(first_dataset, 'SeriesNumber', None)
                            try:
                                series_num = int(series_number) if series_number is not None else 0
                            except (ValueError, TypeError):
                                series_num = 0
                            series_list.append((series_num, series_uid, datasets))
                    series_list.sort(key=lambda x: x[0])
                    
                    if series_list:
                        _, first_series_uid, first_datasets = series_list[0]
                        focused_series_uid = first_series_uid
                        # Update subwindow_data with correct series
                        self.subwindow_data[focused_idx]['current_series_uid'] = first_series_uid
                        self.subwindow_data[focused_idx]['current_dataset'] = first_datasets[0]
                        self.subwindow_data[focused_idx]['current_slice_index'] = 0
                        focused_slice_index = 0
                        print(f"[DEBUG] Series navigation: Using fallback series {first_series_uid[:20]}...")
                    else:
                        print(f"[DEBUG] Series navigation: No valid series in study, cannot navigate")
                        return
                else:
                    print(f"[DEBUG] Series navigation: Study has no series, cannot navigate")
                    return
            
            # Set context to match focused subwindow's data BEFORE navigation
            # This is critical - the slice_display_manager needs the correct context
            self.slice_display_manager.set_current_data_context(
            self.current_studies,
            focused_study_uid,
                focused_series_uid,
                focused_slice_index
            )
            
            # Verify context was set correctly (debug check)
            # Ensure the slice_display_manager's internal state matches what we set
            if (self.slice_display_manager.current_study_uid != focused_study_uid or 
                self.slice_display_manager.current_series_uid != focused_series_uid):
                print(f"[DEBUG] Series navigation: Context mismatch detected. "
                      f"Expected study={focused_study_uid[:20]}..., series={focused_series_uid[:20]}..., "
                      f"Got study={self.slice_display_manager.current_study_uid[:20] if self.slice_display_manager.current_study_uid else 'None'}..., "
                      f"series={self.slice_display_manager.current_series_uid[:20] if self.slice_display_manager.current_series_uid else 'None'}...")
                # Context didn't update correctly, force it again
                self.slice_display_manager.set_current_data_context(
                    self.current_studies,
                    focused_study_uid,
                    focused_series_uid,
                    focused_slice_index
                )
            
            # Build flat list of all series from all studies in navigator order
            flat_series_list = self._build_flat_series_list(self.current_studies)
            
            if not flat_series_list:
                print(f"[DEBUG] Series navigation: No series found in any study")
                return
            
            # Find current series in flat list by matching both study_uid and series_uid
            current_index = None
            for idx, (_, study_uid, series_uid, _) in enumerate(flat_series_list):
                if study_uid == focused_study_uid and series_uid == focused_series_uid:
                    current_index = idx
                    break
            
            if current_index is None:
                print(f"[DEBUG] Series navigation: Current series not found in flat list. "
                      f"Looking for study={focused_study_uid[:20] if focused_study_uid else 'None'}..., "
                      f"series={focused_series_uid[:20] if focused_series_uid else 'None'}...")
                return
            
            # Calculate new index
            new_index = current_index + direction
            
            # Check if new index is valid
            if new_index < 0 or new_index >= len(flat_series_list):
                print(f"[DEBUG] Series navigation: New index {new_index} out of range [0, {len(flat_series_list)}). "
                      f"Already at {'first' if new_index < 0 else 'last'} series.")
                return
            
            # Get target series from flat list
            _, target_study_uid, target_series_uid, target_first_dataset = flat_series_list[new_index]
            
            # Get full datasets list for the target series
            if target_study_uid not in self.current_studies:
                print(f"[DEBUG] Series navigation: Target study {target_study_uid[:20]}... not found in current_studies")
                return
            
            if target_series_uid not in self.current_studies[target_study_uid]:
                print(f"[DEBUG] Series navigation: Target series {target_series_uid[:20]}... not found in study")
                return
            
            target_datasets = self.current_studies[target_study_uid][target_series_uid]
            if not target_datasets:
                print(f"[DEBUG] Series navigation: Target series has no datasets")
                return
            
            # Set new series information
            new_series_uid = target_series_uid
            slice_index = 0  # Always start at first slice when navigating to new series
            dataset = target_datasets[0]
            
            print(f"[DEBUG] Series navigation: Successfully navigating from index {current_index} to {new_index}, "
                  f"new_series_uid={new_series_uid[:20]}..., new_study_uid={target_study_uid[:20]}...")
            
            if new_series_uid is not None and dataset is not None:
                # Update focused subwindow's data
                self.subwindow_data[focused_idx]['current_series_uid'] = new_series_uid
                self.subwindow_data[focused_idx]['current_study_uid'] = target_study_uid
                self.subwindow_data[focused_idx]['current_slice_index'] = slice_index
                self.subwindow_data[focused_idx]['current_dataset'] = dataset
                
                # Update legacy references (point to focused subwindow)
                self.current_series_uid = new_series_uid
                self.current_slice_index = slice_index
                self.current_dataset = dataset
                self.current_study_uid = target_study_uid  # Use target study UID
                
                # Reset projection state when switching series
                self.slice_display_manager.reset_projection_state()
                # Update widget to match reset state
                self.intensity_projection_controls_widget.set_enabled(False)
                self.intensity_projection_controls_widget.set_projection_type("aip")
                self.intensity_projection_controls_widget.set_slice_count(4)
                
                # Display slice
                self.slice_display_manager.display_slice(
                    dataset,
                    self.current_studies,
                    target_study_uid,  # Use target study UID from navigation
                    new_series_uid,
                    slice_index
                )
                
                # Extract actual composite series key from the dataset that was displayed
                # This ensures subwindow_data always reflects what's actually shown
                extracted_series_uid = get_composite_series_key(dataset)
                extracted_study_uid = getattr(dataset, 'StudyInstanceUID', '')
                
                # Get stored values for comparison
                stored_series_uid = new_series_uid
                stored_study_uid = target_study_uid
                
                # Log the sync with FULL UIDs (not truncated) to diagnose mismatches
                if extracted_series_uid != stored_series_uid:
                    print(f"[DEBUG] Syncing subwindow_data after navigation: MISMATCH detected!")
                    print(f"[DEBUG]   Extracted series_uid from dataset: {extracted_series_uid}")
                    print(f"[DEBUG]   Stored series_uid (from navigation): {stored_series_uid}")
                    print(f"[DEBUG]   Series UID match: False - updating stored value to match dataset")
                else:
                    print(f"[DEBUG] Syncing subwindow_data after navigation: series_uid matches")
                    print(f"[DEBUG]   Series UID: {extracted_series_uid}")
                
                if extracted_study_uid != stored_study_uid:
                    print(f"[DEBUG]   Extracted study_uid from dataset: {extracted_study_uid}")
                    print(f"[DEBUG]   Stored study_uid: {stored_study_uid}")
                    print(f"[DEBUG]   Study UID match: False - updating stored value to match dataset")
                
                # Update subwindow_data with extracted UIDs from dataset
                # This ensures navigation always starts from the correct series that's actually displayed
                self.subwindow_data[focused_idx]['current_series_uid'] = extracted_series_uid
                self.subwindow_data[focused_idx]['current_study_uid'] = extracted_study_uid
                self.subwindow_data[focused_idx]['current_dataset'] = dataset
                self.subwindow_data[focused_idx]['current_slice_index'] = slice_index
                
                # Update legacy references to match
                self.current_series_uid = extracted_series_uid
                self.current_study_uid = extracted_study_uid
                self.current_slice_index = slice_index
                self.current_dataset = dataset
                
                # Update slice display manager context with extracted UIDs (after sync)
                # This ensures the manager's context matches what's actually displayed
                self.slice_display_manager.set_current_data_context(
                    self.current_studies,
                    extracted_study_uid,  # Use extracted UID
                    extracted_series_uid,  # Use extracted UID
                    slice_index
                )
                
                # Update undo/redo state when dataset changes
                self._update_undo_redo_state()
                
                # Update slice navigator (shared, shows focused subwindow's slice)
                if self.current_studies and self.current_study_uid and self.current_series_uid:
                    datasets = self.current_studies[self.current_study_uid][self.current_series_uid]
                    self.slice_navigator.set_total_slices(len(datasets))
                    self.slice_navigator.set_current_slice(slice_index)
                
                # Update series navigator highlighting using focused subwindow's data
                # Get focused subwindow's series and study UID for highlighting
                if focused_idx in self.subwindow_data:
                    data = self.subwindow_data[focused_idx]
                    focused_series_uid = data.get('current_series_uid', '')
                    focused_study_uid = data.get('current_study_uid', '')
                    if focused_series_uid and focused_study_uid:
                        self.series_navigator.set_current_series(focused_series_uid, focused_study_uid)
                
                # Update right panel to reflect new series (including fusion base series)
                self._update_right_panel_for_focused_subwindow()
                
                # Update cine player context and check if series is cine-capable
                self._update_cine_player_context()
        finally:
            # Always clear navigation lock, even if an error occurred
            timestamp = time.time()
            print(f"[DEBUG-NAV] [{timestamp:.6f}] Series navigation: Lock released")
            self._series_navigation_in_progress = False
    
    def _build_flat_series_list(self, studies: Dict) -> List[Tuple[int, str, str, Dataset]]:
        """
        Build flat list of all series from all studies in navigator display order.
        
        This method creates a flat list that matches the order in which series appear
        in the series navigator. Studies are iterated in dict order, and series within
        each study are sorted by SeriesNumber (ascending).
        
        Args:
            studies: Dictionary of studies {study_uid: {series_uid: [datasets]}}
            
        Returns:
            List of tuples: [(series_num, study_uid, series_uid, first_dataset), ...]
        """
        flat_list = []
        for study_uid, study_series in studies.items():
            # Build series list for this study
            series_list = []
            for series_uid, datasets in study_series.items():
                if datasets:
                    first_dataset = datasets[0]
                    series_number = getattr(first_dataset, 'SeriesNumber', None)
                    try:
                        series_num = int(series_number) if series_number is not None else 0
                    except (ValueError, TypeError):
                        series_num = 0
                    series_list.append((series_num, study_uid, series_uid, first_dataset))
            # Sort by SeriesNumber (ascending)
            series_list.sort(key=lambda x: x[0])
            # Add to flat list
            flat_list.extend(series_list)
        return flat_list
    
    def _on_series_navigator_selected(self, series_uid: str) -> None:
        """
        Handle series selection from series navigator (assigns to focused subwindow).
        
        Args:
            series_uid: Selected series UID
        """
        if not self.current_studies:
            return
        
        # Find study containing this series
        target_study_uid = None
        for study_uid, series_dict in self.current_studies.items():
            if series_uid in series_dict:
                target_study_uid = study_uid
                break
        
        if target_study_uid is None:
            return
        
        study_series = self.current_studies[target_study_uid]
        if series_uid not in study_series:
            return
        
        datasets = study_series[series_uid]
        if not datasets:
            return
        
        # Assign to focused subwindow
        focused_subwindow = self.multi_window_layout.get_focused_subwindow()
        if focused_subwindow:
            # Assign first slice of selected series to focused subwindow
            # _assign_series_to_subwindow will handle the display
            self._assign_series_to_subwindow(focused_subwindow, series_uid, 0)
    
    def _on_assign_series_from_context_menu(self, series_uid: str) -> None:
        """
        Handle series assignment request from context menu (assigns to focused subwindow).
        
        Args:
            series_uid: Selected series UID
        """
        # Same logic as _on_series_navigator_selected
        self._on_series_navigator_selected(series_uid)
    
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
            
            # Update ROI statistics panel after slice is displayed
            # This ensures statistics are recalculated when projection state changes
            self._display_rois_for_slice(dataset)
            
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
        # print(f"[DEBUG-ROI-STATS] _display_rois_for_slice: roi_manager={id(self.roi_manager)}, "
        #       f"roi_coordinator={id(self.roi_coordinator)}, scene={id(self.image_viewer.scene) if self.image_viewer.scene else None}, "
        #       f"projection_enabled={self.slice_display_manager.projection_enabled if hasattr(self, 'slice_display_manager') else 'unknown'}")
        self.slice_display_manager.display_rois_for_slice(dataset)
        # Check if there's a selected ROI for this slice and restore UI state
        study_uid = getattr(dataset, 'StudyInstanceUID', '')
        series_uid = get_composite_series_key(dataset)
        # Use current slice index as instance identifier (array position)
        instance_identifier = self.current_slice_index
        rois = self.roi_manager.get_rois_for_slice(study_uid, series_uid, instance_identifier)
        selected_roi = self.roi_manager.get_selected_roi()
        # print(f"[DEBUG-ROI-STATS] _display_rois_for_slice: Found {len(rois)} ROIs for slice, selected_roi={id(selected_roi) if selected_roi else None}")
        if selected_roi is not None:
            selected_in_slice = selected_roi in rois
            # print(f"[DEBUG-ROI-STATS] _display_rois_for_slice: Selected ROI in current slice: {selected_in_slice}")
            if selected_in_slice:
                self.roi_list_panel.select_roi_in_list(selected_roi)
                # print(f"[DEBUG-ROI-STATS] _display_rois_for_slice: Calling update_roi_statistics for selected ROI")
                self.roi_coordinator.update_roi_statistics(selected_roi)
            else:
                # print(f"[DEBUG-ROI-STATS] _display_rois_for_slice: Selected ROI not in current slice, clearing statistics")
                self.roi_statistics_panel.clear_statistics()
        else:
            # print(f"[DEBUG-ROI-STATS] _display_rois_for_slice: No selected ROI, clearing statistics")
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
        print(f"[DEBUG-PROJECTION] _on_projection_enabled_changed: enabled={enabled}, "
              f"_resetting_projection_state={self._resetting_projection_state}")
        
        # Check current states BEFORE updating manager
        current_widget_state = self.intensity_projection_controls_widget.get_enabled()
        current_manager_state = self.slice_display_manager.projection_enabled
        checkbox_visual_state = self.intensity_projection_controls_widget.enable_checkbox.isChecked()
        print(f"[DEBUG-PROJECTION] _on_projection_enabled_changed: Current widget state={current_widget_state}, "
              f"checkbox visual state={checkbox_visual_state}, manager state={current_manager_state}, signal enabled={enabled}")
        
        # If we're resetting and signal doesn't match manager state, sync widget to manager (ignore signal)
        if self._resetting_projection_state and current_manager_state != enabled:
            print(f"[DEBUG-PROJECTION] _on_projection_enabled_changed: Reset in progress: ignoring signal ({enabled}), "
                  f"syncing widget to manager ({current_manager_state})")
            self.intensity_projection_controls_widget.set_enabled(current_manager_state)
        else:
            # Normal case: update manager state to match the signal (user's intent)
            print(f"[DEBUG-PROJECTION] _on_projection_enabled_changed: Updating manager state to match signal ({enabled})")
            self.slice_display_manager.set_projection_enabled(enabled)
            
            # Verify the update took effect
            updated_state = self.slice_display_manager.projection_enabled
            print(f"[DEBUG-PROJECTION] _on_projection_enabled_changed: Manager state after update: {updated_state}, "
                  f"manager object ID: {id(self.slice_display_manager)}")
            
            # Verify ROI coordinator is using the same manager
            if hasattr(self, 'roi_coordinator') and self.roi_coordinator is not None:
                if self.roi_coordinator.get_projection_enabled is not None:
                    try:
                        # Check what the callback returns
                        callback_result = self.roi_coordinator.get_projection_enabled()
                        print(f"[DEBUG-PROJECTION] _on_projection_enabled_changed: ROI coordinator callback returns: {callback_result}")
                        
                        # Try to inspect the closure to see what manager it references
                        if hasattr(self.roi_coordinator.get_projection_enabled, '__closure__') and self.roi_coordinator.get_projection_enabled.__closure__:
                            # The closure should contain the managers dict
                            closure_vars = [cell.cell_contents for cell in self.roi_coordinator.get_projection_enabled.__closure__]
                            print(f"[DEBUG-PROJECTION] _on_projection_enabled_changed: ROI coordinator callback closure vars: {[type(v).__name__ for v in closure_vars]}")
                            
                            # Check if the manager in the closure is the same as self.slice_display_manager
                            for var in closure_vars:
                                if isinstance(var, dict) and 'slice_display_manager' in var:
                                    manager_from_closure = var['slice_display_manager']
                                    print(f"[DEBUG-PROJECTION] _on_projection_enabled_changed: Manager from closure ID: {id(manager_from_closure)}, "
                                          f"self.slice_display_manager ID: {id(self.slice_display_manager)}, "
                                          f"same object: {manager_from_closure is self.slice_display_manager}, "
                                          f"closure manager projection_enabled: {manager_from_closure.projection_enabled}, "
                                          f"self.slice_display_manager projection_enabled: {self.slice_display_manager.projection_enabled}")
                                    if manager_from_closure is not self.slice_display_manager:
                                        print(f"[DEBUG-PROJECTION] _on_projection_enabled_changed: WARNING - Manager objects are different! "
                                              f"This could cause synchronization issues.")
                                    break
                    except Exception as e:
                        print(f"[DEBUG-PROJECTION] _on_projection_enabled_changed: Error checking ROI coordinator callback: {e}")
                        import traceback
                        traceback.print_exc()
            
            # Widget state should already match signal, but verify and sync if needed
            if current_widget_state != enabled:
                print(f"[DEBUG-PROJECTION] _on_projection_enabled_changed: Widget state ({current_widget_state}) != signal ({enabled}), syncing widget")
                self.intensity_projection_controls_widget.set_enabled(enabled)
            else:
                # print(f"[DEBUG-PROJECTION] _on_projection_enabled_changed: Widget state ({current_widget_state}) matches signal ({enabled}), no widget update needed")
                pass
        
        # Redisplay current slice with new projection state
        if self.current_dataset is not None:
            # print(f"[DEBUG-PROJECTION] _on_projection_enabled_changed: Redisplaying slice, current_dataset exists, "
            #       f"selected_roi={id(self.roi_manager.get_selected_roi()) if self.roi_manager.get_selected_roi() else None}, "
            #       f"projection_enabled={self.slice_display_manager.projection_enabled}")
            
            # Verify ROI coordinator callback sees the updated state before redisplaying
            if hasattr(self, 'roi_coordinator') and self.roi_coordinator is not None:
                if self.roi_coordinator.get_projection_enabled is not None:
                    callback_state = self.roi_coordinator.get_projection_enabled()
                    # print(f"[DEBUG-PROJECTION] _on_projection_enabled_changed: ROI coordinator callback state before redisplay: {callback_state}, "
                    #       f"manager state: {self.slice_display_manager.projection_enabled}")
                    if callback_state != self.slice_display_manager.projection_enabled:
                        print(f"[DEBUG-PROJECTION] _on_projection_enabled_changed: WARNING - Callback state mismatch! "
                              f"Callback={callback_state}, Manager={self.slice_display_manager.projection_enabled}")
            
            self._display_slice(self.current_dataset)
            
            # After redisplay, ensure statistics are updated if there's a selected ROI
            # The _display_rois_for_slice should handle this, but we'll verify
            selected_roi = self.roi_manager.get_selected_roi()
            if selected_roi is not None:
                print(f"[DEBUG-PROJECTION] _on_projection_enabled_changed: Selected ROI exists, statistics should be updated by _display_rois_for_slice")
        else:
            print(f"[DEBUG-PROJECTION] _on_projection_enabled_changed: current_dataset is None, cannot redisplay")
    
    def _on_projection_type_changed(self, projection_type: str) -> None:
        """
        Handle projection type change.
        
        Args:
            projection_type: "aip", "mip", or "minip"
        """
        # print(f"[DEBUG-PROJECTION] _on_projection_type_changed: projection_type={projection_type}, "
        #       f"projection_enabled={self.slice_display_manager.projection_enabled}")
        self.slice_display_manager.set_projection_type(projection_type)
        # Update widget state
        self.intensity_projection_controls_widget.set_projection_type(projection_type)
        # Redisplay current slice with new projection type
        if self.current_dataset is not None and self.slice_display_manager.projection_enabled:
            # print(f"[DEBUG-PROJECTION] _on_projection_type_changed: Redisplaying slice")
            self._display_slice(self.current_dataset)
    
    def _on_projection_slice_count_changed(self, count: int) -> None:
        """
        Handle projection slice count change.
        
        Args:
            count: Number of slices to combine (2, 3, 4, 6, or 8)
        """
        print(f"[DEBUG-PROJECTION] _on_projection_slice_count_changed: count={count}, "
              f"projection_enabled={self.slice_display_manager.projection_enabled}")
        self.slice_display_manager.set_projection_slice_count(count)
        # Update widget state
        self.intensity_projection_controls_widget.set_slice_count(count)
        # Redisplay current slice with new slice count
        if self.current_dataset is not None and self.slice_display_manager.projection_enabled:
            print(f"[DEBUG-PROJECTION] _on_projection_slice_count_changed: Redisplaying slice")
            self._display_slice(self.current_dataset)
    
    def _open_settings(self) -> None:
        """Handle settings dialog request."""
        self.dialog_coordinator.open_settings()
    
    def _open_overlay_settings(self) -> None:
        """Handle Overlay Settings dialog request."""
        self.dialog_coordinator.open_overlay_settings()
    
    def _open_about_this_file(self) -> None:
        """Handle About This File dialog request."""
        # Get current dataset and file path from focused subwindow
        focused_idx = self.focused_subwindow_index
        current_dataset = None
        file_path = None
        
        if focused_idx in self.subwindow_data:
            current_dataset = self.subwindow_data[focused_idx].get('current_dataset')
            if current_dataset:
                file_path = self._get_file_path_for_dataset(
                    current_dataset,
                    self.subwindow_data[focused_idx].get('current_study_uid', ''),
                    self.subwindow_data[focused_idx].get('current_series_uid', ''),
                    self.subwindow_data[focused_idx].get('current_slice_index', 0)
                )
        
        self.dialog_coordinator.open_about_this_file(current_dataset, file_path)
    
    def _get_file_path_for_dataset(self, dataset, study_uid: str, series_uid: str, slice_index: int) -> Optional[str]:
        """
        Get file path for a dataset.
        
        Args:
            dataset: DICOM dataset
            study_uid: Study Instance UID
            series_uid: Series UID (composite key)
            slice_index: Slice index
            
        Returns:
            File path if found, None otherwise
        """
        if not dataset or not study_uid or not series_uid:
            return None
        
        # First, check if dataset has filename attribute (pydicom sometimes stores this)
        if hasattr(dataset, 'filename') and dataset.filename:
            return dataset.filename
        
        # Try to get instance number from dataset
        instance_num = None
        if hasattr(dataset, 'InstanceNumber'):
            try:
                instance_num = int(getattr(dataset, 'InstanceNumber'))
            except (ValueError, TypeError):
                pass
        
        # If we have instance_num, try that first
        if instance_num is not None:
            key = (study_uid, series_uid, instance_num)
            if key in self.dicom_organizer.file_paths:
                return self.dicom_organizer.file_paths[key]
        
        # Try with slice_index as instance_num
        key = (study_uid, series_uid, slice_index)
        if key in self.dicom_organizer.file_paths:
            return self.dicom_organizer.file_paths[key]
        
        # If still not found, try to find by iterating through file_paths
        # This handles cases where instance_num calculation doesn't match
        for (s_uid, ser_uid, inst_num), path in self.dicom_organizer.file_paths.items():
            if s_uid == study_uid and ser_uid == series_uid:
                # Check if this might be the right file by comparing dataset
                # We'll use the first match for this series, or try to match by instance
                if instance_num is not None and inst_num == instance_num:
                    return path
                # If no instance match, return first file in series (better than nothing)
                if instance_num is None:
                    return path
        
        return None
    
    def _on_show_file_from_series(self, study_uid: str, series_uid: str) -> None:
        """
        Handle "Show file" request from series navigator thumbnail.
        
        Opens file explorer and selects the first slice file of the specified series.
        
        Args:
            study_uid: Study Instance UID
            series_uid: Series UID (composite key)
        """
        from utils.file_explorer import reveal_file_in_explorer
        
        # Check if we have the studies data
        if not self.current_studies or study_uid not in self.current_studies:
            return
        
        study_series = self.current_studies[study_uid]
        if series_uid not in study_series or not study_series[series_uid]:
            return
        
        # Get first dataset from the series
        first_dataset = study_series[series_uid][0]
        
        # Get file path for first slice (slice_index=0)
        file_path = self._get_file_path_for_dataset(first_dataset, study_uid, series_uid, 0)
        
        if file_path and os.path.exists(file_path):
            reveal_file_in_explorer(file_path)
    
    def _on_about_this_file_from_series(self, study_uid: str, series_uid: str) -> None:
        """
        Handle "About This File" request from series navigator thumbnail.
        
        Opens About This File dialog with the first slice of the specified series.
        
        Args:
            study_uid: Study Instance UID
            series_uid: Series UID (composite key)
        """
        # Check if we have the studies data
        if not self.current_studies or study_uid not in self.current_studies:
            return
        
        study_series = self.current_studies[study_uid]
        if series_uid not in study_series or not study_series[series_uid]:
            return
        
        # Get first dataset from the series
        first_dataset = study_series[series_uid][0]
        
        # Get file path for first slice (slice_index=0)
        file_path = self._get_file_path_for_dataset(first_dataset, study_uid, series_uid, 0)
        
        # Open About This File dialog
        self.dialog_coordinator.open_about_this_file(first_dataset, file_path)
    
    def _get_current_slice_file_path(self, subwindow_idx: Optional[int] = None) -> Optional[str]:
        """
        Get file path for the currently displayed slice in a subwindow.
        
        Args:
            subwindow_idx: Subwindow index (None to use focused subwindow)
            
        Returns:
            File path if found, None otherwise
        """
        # Use focused subwindow if index not provided
        if subwindow_idx is None:
            subwindow_idx = self.focused_subwindow_index
        
        # Get current slice information from subwindow
        dataset = self._get_subwindow_dataset(subwindow_idx)
        study_uid = self._get_subwindow_study_uid(subwindow_idx)
        series_uid = self._get_subwindow_series_uid(subwindow_idx)
        slice_index = self._get_subwindow_slice_index(subwindow_idx)
        
        if not dataset or not study_uid or not series_uid:
            return None
        
        # Get file path using existing method
        return self._get_file_path_for_dataset(dataset, study_uid, series_uid, slice_index)
    
    def _update_about_this_file_dialog(self) -> None:
        """Update About This File dialog with current dataset and file path."""
        focused_idx = self.focused_subwindow_index
        current_dataset = None
        file_path = None
        
        if focused_idx in self.subwindow_data:
            current_dataset = self.subwindow_data[focused_idx].get('current_dataset')
            if current_dataset:
                file_path = self._get_file_path_for_dataset(
                    current_dataset,
                    self.subwindow_data[focused_idx].get('current_study_uid', ''),
                    self.subwindow_data[focused_idx].get('current_series_uid', ''),
                    self.subwindow_data[focused_idx].get('current_slice_index', 0)
                )
        
        self.dialog_coordinator.update_about_this_file(current_dataset, file_path)
    
    def _on_privacy_view_toggled(self, enabled: bool) -> None:
        """
        Handle privacy view toggle.
        
        Propagates privacy mode state to all components that display tags.
        
        Args:
            enabled: True if privacy view is enabled, False otherwise
        """
        # Update state
        self.privacy_view_enabled = enabled
        
        # Propagate to metadata panel
        if hasattr(self, 'metadata_panel') and self.metadata_panel:
            self.metadata_panel.set_privacy_mode(enabled)
        
        # Propagate to overlay manager (shared)
        if hasattr(self, 'overlay_manager') and self.overlay_manager:
            self.overlay_manager.set_privacy_mode(enabled)
        
        # Propagate to all subwindow overlay managers
        for subwindow_idx, managers in self.subwindow_managers.items():
            if 'overlay_manager' in managers and managers['overlay_manager']:
                managers['overlay_manager'].set_privacy_mode(enabled)
            if 'crosshair_manager' in managers and managers['crosshair_manager']:
                managers['crosshair_manager'].set_privacy_mode(enabled)
        
        # Update privacy view state on all image viewers (for context menu synchronization)
        subwindows = self.multi_window_layout.get_all_subwindows()
        for subwindow in subwindows:
            if subwindow and subwindow.image_viewer:
                subwindow.image_viewer.set_privacy_view_state(enabled)
        
        # Refresh overlays if datasets are loaded
        if self.current_dataset is not None:
            # Trigger overlay refresh for focused subwindow
            focused_subwindow = self.multi_window_layout.get_focused_subwindow()
            if focused_subwindow and focused_subwindow.image_viewer:
                # Get current dataset from focused subwindow
                focused_idx = self.multi_window_layout.get_all_subwindows().index(focused_subwindow)
                if focused_idx in self.subwindow_data:
                    current_dataset = self.subwindow_data[focused_idx].get('current_dataset')
                    if current_dataset:
                        # Refresh overlay by re-displaying the current slice
                        if focused_idx in self.subwindow_managers:
                            slice_display_manager = self.subwindow_managers[focused_idx].get('slice_display_manager')
                            if slice_display_manager and hasattr(slice_display_manager, 'current_dataset'):
                                # Re-display current slice to refresh overlays with privacy mode
                                if (slice_display_manager.current_dataset is not None and 
                                    hasattr(slice_display_manager, 'current_studies') and
                                    hasattr(slice_display_manager, 'current_study_uid') and
                                    hasattr(slice_display_manager, 'current_series_uid') and
                                    hasattr(slice_display_manager, 'current_slice_index')):
                                    try:
                                        slice_display_manager.display_slice(
                                            slice_display_manager.current_dataset,
                                            slice_display_manager.current_studies,
                                            slice_display_manager.current_study_uid,
                                            slice_display_manager.current_series_uid,
                                            slice_display_manager.current_slice_index,
                                            update_metadata=False  # Don't update metadata panel (already updated above)
                                        )
                                    except Exception:
                                        # If display_slice fails, just refresh overlays directly
                                        overlay_manager = self.subwindow_managers[focused_idx].get('overlay_manager')
                                        if overlay_manager and slice_display_manager.current_dataset:
                                            from core.dicom_parser import DICOMParser
                                            parser = DICOMParser(slice_display_manager.current_dataset)
                                            overlay_manager.create_overlay_items(
                                                focused_subwindow.image_viewer.scene,
                                                parser
                                            )
    
    def _open_tag_viewer(self) -> None:
        """Handle tag viewer dialog request."""
        self.dialog_coordinator.open_tag_viewer(self.current_dataset, privacy_mode=self.privacy_view_enabled)
    
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
    
    def _open_fusion_technical_doc(self) -> None:
        """Handle Fusion Technical Documentation dialog request."""
        self.dialog_coordinator.open_fusion_technical_doc()
    
    def _open_tag_export(self) -> None:
        """Handle Tag Export dialog request."""
        self.dialog_coordinator.open_tag_export()
    
    def _open_export(self) -> None:
        """Handle Export dialog request."""
        # Get current window/level values if available
        window_center, window_width = self.window_level_controls.get_window_level()
        # Get current rescale state to match viewer behavior
        use_rescaled_values = self.view_state_manager.use_rescaled_values
        # Get current projection state from slice display manager
        projection_enabled = self.slice_display_manager.projection_enabled
        projection_type = self.slice_display_manager.projection_type
        projection_slice_count = self.slice_display_manager.projection_slice_count
        # Get initial fit zoom for font scaling
        initial_fit_zoom = self.view_state_manager.get_initial_fit_zoom()
        self.dialog_coordinator.open_export(
            current_window_center=window_center,
            current_window_width=window_width,
            current_zoom=self.image_viewer.current_zoom,
            initial_fit_zoom=initial_fit_zoom,
            use_rescaled_values=use_rescaled_values,
            roi_manager=self.roi_manager,
            overlay_manager=self.overlay_manager,
            measurement_tool=self.measurement_tool,
            projection_enabled=projection_enabled,
            projection_type=projection_type,
            projection_slice_count=projection_slice_count
        )
    
    def _on_export_customizations(self) -> None:
        """Handle Export Customizations request."""
        # Get last export path or use current directory
        last_export_path = self.config_manager.get_last_export_path()
        if not last_export_path or not os.path.exists(last_export_path):
            last_export_path = os.getcwd()
        
        # If last path is a file, use its directory
        if os.path.isfile(last_export_path):
            last_export_path = os.path.dirname(last_export_path)
        
        # Default filename
        default_filename = os.path.join(last_export_path, "dicom_viewer_customizations.json")
        
        # Show file save dialog
        file_path, _ = QFileDialog.getSaveFileName(
            self.main_window,
            "Export Customizations",
            default_filename,
            "JSON Files (*.json);;All Files (*)"
        )
        
        if not file_path:
            return
        
        # Ensure .json extension
        if not file_path.endswith('.json'):
            file_path += '.json'
        
        # Export customizations
        if self.config_manager.export_customizations(file_path):
            # Update last export path
            self.config_manager.set_last_export_path(os.path.dirname(file_path))
            QMessageBox.information(
                self.main_window,
                "Export Successful",
                f"Customizations exported successfully to:\n{file_path}"
            )
        else:
            QMessageBox.warning(
                self.main_window,
                "Export Failed",
                f"Failed to export customizations to:\n{file_path}\n\nPlease check file permissions and try again."
            )
    
    def _on_import_customizations(self) -> None:
        """Handle Import Customizations request."""
        # Get last path or use current directory
        last_path = self.config_manager.get_last_path()
        if not last_path or not os.path.exists(last_path):
            last_path = os.getcwd()
        
        # If last path is a file, use its directory
        if os.path.isfile(last_path):
            last_path = os.path.dirname(last_path)
        
        # Show file open dialog
        file_path, _ = QFileDialog.getOpenFileName(
            self.main_window,
            "Import Customizations",
            last_path,
            "JSON Files (*.json);;All Files (*)"
        )
        
        if not file_path:
            return
        
        # Import customizations
        if self.config_manager.import_customizations(file_path):
            # Apply imported settings
            # Update overlay manager with new settings
            font_size = self.config_manager.get_overlay_font_size()
            font_color = self.config_manager.get_overlay_font_color()
            self.overlay_manager.set_font_size(font_size)
            self.overlay_manager.set_font_color(*font_color)
            
            # Recreate overlay
            self.overlay_coordinator.handle_overlay_config_applied()
            
            # Update annotation styles
            self._on_annotation_options_applied()
            
            # Apply theme
            theme = self.config_manager.get_theme()
            self.main_window._set_theme(theme)
            
            # Update metadata panel column widths
            widths = self.config_manager.get_metadata_panel_column_widths()
            if len(widths) == 4:
                self.metadata_panel.tree_widget.setColumnWidth(0, widths[0])
                self.metadata_panel.tree_widget.setColumnWidth(1, widths[1])
                self.metadata_panel.tree_widget.setColumnWidth(2, widths[2])
                self.metadata_panel.tree_widget.setColumnWidth(3, widths[3])
            
            QMessageBox.information(
                self.main_window,
                "Import Successful",
                "Customizations imported successfully.\n\nAll settings have been applied."
            )
        else:
            QMessageBox.warning(
                self.main_window,
                "Import Failed",
                f"Failed to import customizations from:\n{file_path}\n\nPlease check that the file is a valid customization file and try again."
            )

    def _on_export_tag_presets(self) -> None:
        """Handle Export Tag Presets request."""
        # Get current presets
        presets = self.config_manager.get_tag_export_presets()
        if not presets:
            QMessageBox.information(
                self.main_window,
                "No Tag Presets",
                "There are no tag export presets to export."
            )
            return

        # Get last export path or use current directory
        last_export_path = self.config_manager.get_last_export_path()
        if not last_export_path or not os.path.exists(last_export_path):
            last_export_path = os.getcwd()

        # If last path is a file, use its directory
        if os.path.isfile(last_export_path):
            last_export_path = os.path.dirname(last_export_path)

        # Default filename
        default_filename = os.path.join(last_export_path, "tag_export_presets.json")

        # Show file save dialog
        file_path, _ = QFileDialog.getSaveFileName(
            self.main_window,
            "Export Tag Presets",
            default_filename,
            "JSON Files (*.json);;All Files (*)"
        )

        if not file_path:
            return

        # Ensure .json extension
        if not file_path.endswith(".json"):
            file_path += ".json"

        # Export presets
        if self.config_manager.export_tag_export_presets(file_path):
            # Update last export path
            self.config_manager.set_last_export_path(os.path.dirname(file_path))
            QMessageBox.information(
                self.main_window,
                "Export Successful",
                f"Tag export presets exported successfully to:\n{file_path}"
            )
        else:
            QMessageBox.warning(
                self.main_window,
                "Export Failed",
                f"Failed to export tag export presets to:\n{file_path}\n\nPlease check file permissions and try again."
            )

    def _on_import_tag_presets(self) -> None:
        """Handle Import Tag Presets request."""
        # Get last path or use current directory
        last_path = self.config_manager.get_last_path()
        if not last_path or not os.path.exists(last_path):
            last_path = os.getcwd()

        # If last path is a file, use its directory
        if os.path.isfile(last_path):
            last_path = os.path.dirname(last_path)

        # Show file open dialog
        file_path, _ = QFileDialog.getOpenFileName(
            self.main_window,
            "Import Tag Presets",
            last_path,
            "JSON Files (*.json);;All Files (*)"
        )

        if not file_path:
            return

        result = self.config_manager.import_tag_export_presets(file_path)
        if result is None:
            QMessageBox.critical(
                self.main_window,
                "Import Failed",
                "Failed to import tag export presets.\n\n"
                "Please verify that the file is a valid DICOM Viewer V3 tag presets file."
            )
            return

        imported = result.get("imported", 0)
        skipped = result.get("skipped_conflicts", 0)

        if imported == 0 and skipped == 0:
            QMessageBox.information(
                self.main_window,
                "No Presets Imported",
                "The selected file did not contain any tag export presets."
            )
        else:
            details_lines = [f"Presets imported: {imported}"]
            if skipped > 0:
                details_lines.append(
                    f"Presets skipped (already exist and were not overwritten): {skipped}"
                )
            details = "\n".join(details_lines)
            QMessageBox.information(
                self.main_window,
                "Import Complete",
                f"Tag export presets import completed.\n\n{details}"
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
        
        # Update styles for all existing ROIs and measurements
        self.roi_manager.update_all_roi_styles(self.config_manager)
        self.measurement_tool.update_all_measurement_styles(self.config_manager)
        
        # Update styles for text and arrow annotations
        if hasattr(self, 'text_annotation_tool') and self.text_annotation_tool:
            self.text_annotation_tool.update_all_annotation_styles(self.config_manager)
        if hasattr(self, 'arrow_annotation_tool') and self.arrow_annotation_tool:
            self.arrow_annotation_tool.update_all_arrow_styles(self.config_manager)
        
        # Also update for all subwindows
        subwindows = self.multi_window_layout.get_all_subwindows()
        for idx, subwindow in enumerate(subwindows):
            if idx in self.subwindow_managers:
                managers = self.subwindow_managers[idx]
                text_tool = managers.get('text_annotation_tool')
                arrow_tool = managers.get('arrow_annotation_tool')
                if text_tool:
                    text_tool.update_all_annotation_styles(self.config_manager)
                if arrow_tool:
                    arrow_tool.update_all_arrow_styles(self.config_manager)
        
        # Update ROI statistics overlays (this will also refresh with new font settings)
        if self.current_dataset is not None:
            self.roi_coordinator.update_roi_statistics_overlays()
        
        # Ensure ROIs and measurements are displayed for current slice
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
        Delete all ROIs and crosshairs on the current slice.
        """
        self.roi_coordinator.delete_all_rois_current_slice()
        # Also delete all crosshairs
        if hasattr(self, 'crosshair_coordinator') and self.crosshair_coordinator:
            self.crosshair_coordinator.handle_clear_crosshairs()
    
    def _on_scroll_wheel_mode_changed(self, mode: str) -> None:
        """
        Handle scroll wheel mode change.
        
        Args:
            mode: "slice" or "zoom"
        """
        self.mouse_mode_handler.handle_scroll_wheel_mode_changed(mode)
        # Also update all subwindows to make scroll wheel mode global
        subwindows = self.multi_window_layout.get_all_subwindows()
        for subwindow in subwindows:
            if subwindow:
                subwindow.image_viewer.set_scroll_wheel_mode(mode)
    
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
            series_uid = get_composite_series_key(self.current_dataset)
            # Use current slice index as instance identifier (array position)
            instance_identifier = self.current_slice_index
            current_slice_rois = self.roi_manager.get_rois_for_slice(study_uid, series_uid, instance_identifier)
            if selected_roi in current_slice_rois:
                self.roi_coordinator.update_roi_statistics(selected_roi)
            else:
                self.roi_statistics_panel.clear_statistics()
        else:
            self.roi_statistics_panel.clear_statistics()
        
        # Update histogram dialog if open
        if hasattr(self, 'dialog_coordinator') and self.dialog_coordinator.histogram_dialog:
            if self.dialog_coordinator.histogram_dialog.isVisible():
                self.dialog_coordinator.histogram_dialog.update_histogram()
    
    def _update_histogram_dialog_if_visible(self) -> None:
        """Update histogram dialog if it's visible."""
        if (hasattr(self, 'dialog_coordinator') and 
            self.dialog_coordinator.histogram_dialog and 
            self.dialog_coordinator.histogram_dialog.isVisible()):
            self.dialog_coordinator.histogram_dialog.update_histogram()
    
    def _on_reset_all_views(self) -> None:
        """
        Reset view for all subwindows in the layout.
        Applies Reset View to each subwindow's view state manager.
        """
        # Iterate through all subwindows
        for idx in self.subwindow_managers:
            managers = self.subwindow_managers[idx]
            view_state_manager = managers.get('view_state_manager')
            slice_display_manager = managers.get('slice_display_manager')
            
            if view_state_manager and view_state_manager.current_dataset is not None:
                # Reset view for this subwindow
                view_state_manager.reset_view(skip_redisplay=True)
                
                # Get the dataset for this subwindow
                if idx in self.subwindow_data:
                    data = self.subwindow_data[idx]
                    dataset = data.get('current_dataset')
                    if dataset is not None:
                        # Redisplay the slice to apply the reset
                        slice_display_manager.display_slice(
                            dataset,
                            data.get('current_studies', {}),
                            data.get('current_study_uid', ''),
                            data.get('current_series_uid', ''),
                            data.get('current_slice_index', 0),
                            preserve_view_override=False
                        )
    
    def _on_zoom_changed(self, zoom_level: float) -> None:
        """
        Handle zoom level change.
        
        Args:
            zoom_level: Current zoom level
        """
        self.view_state_manager.handle_zoom_changed(zoom_level)
        # Update measurement text offsets to maintain constant viewport pixel distance
        self.measurement_tool.update_all_measurement_text_offsets()
        # Update status bar widget with zoom and preset info
        self._update_zoom_preset_status_bar()
    
    def _on_transform_changed(self) -> None:
        """
        Handle view transform change (zoom/pan).
        """
        self.view_state_manager.handle_transform_changed()
        # Update measurement text offsets to maintain constant viewport pixel distance
        self.measurement_tool.update_all_measurement_text_offsets()
    
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
        Handle overlay font size change from toolbar - update ALL subwindows.
        
        Args:
            font_size: New font size in points
        """
        # Update all subwindows' overlay managers
        subwindows = self.multi_window_layout.get_all_subwindows()
        for idx, subwindow in enumerate(subwindows):
            if subwindow and idx in self.subwindow_managers:
                managers = self.subwindow_managers[idx]
                overlay_manager = managers.get('overlay_manager')
                overlay_coordinator = managers.get('overlay_coordinator')
                
                if overlay_manager:
                    overlay_manager.set_font_size(font_size)
                    
                    # Recreate overlay for this subwindow if it has data
                    if overlay_coordinator:
                        overlay_coordinator.handle_overlay_font_size_changed(font_size)
    
    def _on_overlay_font_color_changed(self, r: int, g: int, b: int) -> None:
        """
        Handle overlay font color change from toolbar - update ALL subwindows.
        
        Args:
            r: Red component (0-255)
            g: Green component (0-255)
            b: Blue component (0-255)
        """
        # Update all subwindows' overlay managers
        subwindows = self.multi_window_layout.get_all_subwindows()
        for idx, subwindow in enumerate(subwindows):
            if subwindow and idx in self.subwindow_managers:
                managers = self.subwindow_managers[idx]
                overlay_manager = managers.get('overlay_manager')
                overlay_coordinator = managers.get('overlay_coordinator')
                
                if overlay_manager:
                    overlay_manager.set_font_color(r, g, b)
                    
                    # Recreate overlay for this subwindow if it has data
                    if overlay_coordinator:
                        overlay_coordinator.handle_overlay_font_color_changed(r, g, b)
    
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
        Handle slice change from slice navigator (affects focused subwindow only).
        
        Args:
            slice_index: New slice index
        """
        # Check if this slice change was from a cine advance before processing
        was_cine_advancing = self.cine_player.is_cine_advancing()
        
        # Update focused subwindow's slice
        focused_idx = self.focused_subwindow_index
        if focused_idx in self.subwindow_data and focused_idx in self.subwindow_managers:
            data = self.subwindow_data[focused_idx]
            managers = self.subwindow_managers[focused_idx]
            
            # Get current series
            series_uid = data.get('current_series_uid', '')
            study_uid = data.get('current_study_uid', '')
            
            if not series_uid or not study_uid:
                return
            
            # Get series datasets
            if study_uid not in self.current_studies or series_uid not in self.current_studies[study_uid]:
                return
            
            series_datasets = self.current_studies[study_uid][series_uid]
            if not series_datasets or slice_index < 0 or slice_index >= len(series_datasets):
                return
            
            # Update subwindow data
            data['current_slice_index'] = slice_index
            data['current_dataset'] = series_datasets[slice_index]
            
            # Note: Legacy references (self.current_slice_index, self.current_dataset) are NOT updated here
            # They are maintained in _update_focused_subwindow_references() to avoid contamination
            # when switching between subwindows
            
            # Display slice using focused subwindow's slice display manager
            slice_display_manager = managers['slice_display_manager']
            slice_display_manager.display_slice(
                series_datasets[slice_index],
                self.current_studies,
                study_uid,
                series_uid,
                slice_index
            )
            
            # Update About This File dialog if open
            self._update_about_this_file_dialog()
            
            # Update crosshairs for new slice
            if 'crosshair_coordinator' in managers and managers['crosshair_coordinator']:
                managers['crosshair_coordinator'].update_crosshairs_for_slice()
            
            # Update frame slider position
            total_slices = len(series_datasets)
            if total_slices > 0:
                self.cine_controls_widget.update_frame_position(slice_index, total_slices)
        
        # Reset cine advancing flag after all slice change processing is complete
        if was_cine_advancing:
            QTimer.singleShot(0, self.cine_player.reset_cine_advancing_flag)
    
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
        
        # Pass datasets to cine player for slice-aware navigation
        if (self.current_studies and self.current_study_uid and self.current_series_uid and
            self.current_study_uid in self.current_studies and
            self.current_series_uid in self.current_studies[self.current_study_uid]):
            datasets = self.current_studies[self.current_study_uid][self.current_series_uid]
            self.cine_player.set_datasets(datasets)
            # Clear loop bounds in widget when series changes
            self.cine_controls_widget.set_loop_bounds(None, None)
        
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
        # Flag will be reset in _on_slice_changed() after processing completes
    
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
    
    def _on_cine_loop_start_set(self, frame_index: int) -> None:
        """
        Handle loop start frame set from cine controls.
        
        Args:
            frame_index: Frame index to set as loop start
        """
        # Get current loop end (if any)
        loop_end = self.cine_player.loop_end_frame
        self.cine_player.set_loop_bounds(frame_index, loop_end)
        # Update widget to reflect bounds
        self.cine_controls_widget.set_loop_bounds(frame_index, loop_end)
    
    def _on_cine_loop_end_set(self, frame_index: int) -> None:
        """
        Handle loop end frame set from cine controls.
        
        Args:
            frame_index: Frame index to set as loop end
        """
        # Get current loop start (if any)
        loop_start = self.cine_player.loop_start_frame
        self.cine_player.set_loop_bounds(loop_start, frame_index)
        # Update widget to reflect bounds
        self.cine_controls_widget.set_loop_bounds(loop_start, frame_index)
    
    def _on_cine_loop_bounds_cleared(self) -> None:
        """Handle loop bounds cleared from cine controls."""
        self.cine_player.clear_loop_bounds()
        # Update widget to reflect cleared bounds
        self.cine_controls_widget.set_loop_bounds(None, None)
    
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
    
    def _get_focused_subwindow(self) -> Optional[SubWindowContainer]:
        """
        Get the currently focused subwindow.
        
        Returns:
            SubWindowContainer or None if no subwindow is focused
        """
        return self.multi_window_layout.get_focused_subwindow()
    
    def _get_selected_rois(self, subwindow: SubWindowContainer) -> list:
        """
        Get selected ROI items from the scene.
        
        Args:
            subwindow: SubWindowContainer to get ROIs from
            
        Returns:
            List of selected ROIItem objects
        """
        selected_rois = []
        if subwindow and subwindow.image_viewer and subwindow.image_viewer.scene:
            try:
                selected_items = subwindow.image_viewer.scene.selectedItems()
                from tools.roi_manager import ROIItem
                
                # Get ROI manager for this subwindow
                subwindows = self.multi_window_layout.get_all_subwindows()
                if subwindow in subwindows:
                    idx = subwindows.index(subwindow)
                    if idx in self.subwindow_managers:
                        roi_manager = self.subwindow_managers[idx]['roi_manager']
                        # Check each selected item to see if it's an ROI graphics item
                        for item in selected_items:
                            # Check all ROIs to find matching graphics items
                            key = (roi_manager.current_study_uid, 
                                   roi_manager.current_series_uid, 
                                   roi_manager.current_instance_identifier)
                            if key in roi_manager.rois:
                                for roi in roi_manager.rois[key]:
                                    if roi.item == item:
                                        selected_rois.append(roi)
                                        break
            except RuntimeError:
                # Scene may have been deleted
                pass
        return selected_rois
    
    def _get_selected_measurements(self, subwindow: SubWindowContainer) -> list:
        """
        Get selected measurement items from the scene.
        
        Args:
            subwindow: SubWindowContainer to get measurements from
            
        Returns:
            List of selected MeasurementItem objects
        """
        selected_measurements = []
        if subwindow and subwindow.image_viewer and subwindow.image_viewer.scene:
            try:
                selected_items = subwindow.image_viewer.scene.selectedItems()
                from tools.measurement_tool import MeasurementItem
                
                for item in selected_items:
                    if isinstance(item, MeasurementItem):
                        selected_measurements.append(item)
            except RuntimeError:
                # Scene may have been deleted
                pass
        return selected_measurements
    
    def _get_selected_crosshairs(self, subwindow: SubWindowContainer) -> list:
        """
        Get selected crosshair items from the scene.
        
        Args:
            subwindow: SubWindowContainer to get crosshairs from
            
        Returns:
            List of selected CrosshairItem objects
        """
        selected_crosshairs = []
        if subwindow and subwindow.image_viewer and subwindow.image_viewer.scene:
            try:
                selected_items = subwindow.image_viewer.scene.selectedItems()
                from tools.crosshair_manager import CrosshairItem
                
                for item in selected_items:
                    if isinstance(item, CrosshairItem):
                        selected_crosshairs.append(item)
            except RuntimeError:
                # Scene may have been deleted
                pass
        return selected_crosshairs
    
    def _get_selected_text_annotations(self, subwindow: SubWindowContainer) -> list:
        """
        Get selected text annotation items from the scene.
        
        Args:
            subwindow: SubWindowContainer to get text annotations from
            
        Returns:
            List of selected TextAnnotationItem objects
        """
        selected_text_annotations = []
        if subwindow and subwindow.image_viewer and subwindow.image_viewer.scene:
            try:
                selected_items = subwindow.image_viewer.scene.selectedItems()
                from tools.text_annotation_tool import TextAnnotationItem
                
                for item in selected_items:
                    if isinstance(item, TextAnnotationItem):
                        selected_text_annotations.append(item)
            except RuntimeError:
                # Scene may have been deleted
                pass
        return selected_text_annotations
    
    def _get_selected_arrow_annotations(self, subwindow: SubWindowContainer) -> list:
        """
        Get selected arrow annotation items from the scene.
        
        Args:
            subwindow: SubWindowContainer to get arrow annotations from
            
        Returns:
            List of selected ArrowAnnotationItem objects
        """
        selected_arrow_annotations = []
        if subwindow and subwindow.image_viewer and subwindow.image_viewer.scene:
            try:
                selected_items = subwindow.image_viewer.scene.selectedItems()
                from tools.arrow_annotation_tool import ArrowAnnotationItem
                
                for item in selected_items:
                    if isinstance(item, ArrowAnnotationItem):
                        selected_arrow_annotations.append(item)
            except RuntimeError:
                # Scene may have been deleted
                pass
        return selected_arrow_annotations
    
    def _copy_annotations(self) -> None:
        """
        Copy selected annotations (ROIs, measurements, crosshairs, text annotations, arrow annotations) to clipboard.
        
        Only copies selected annotations. If nothing is selected, shows a status message.
        """
        # Get focused subwindow
        subwindow = self._get_focused_subwindow()
        if not subwindow:
            return
        
        # Collect selected annotations
        selected_rois = self._get_selected_rois(subwindow)
        selected_measurements = self._get_selected_measurements(subwindow)
        selected_crosshairs = self._get_selected_crosshairs(subwindow)
        selected_text_annotations = self._get_selected_text_annotations(subwindow)
        selected_arrow_annotations = self._get_selected_arrow_annotations(subwindow)
        
        # If nothing selected, show message and return
        total_count = (len(selected_rois) + len(selected_measurements) + len(selected_crosshairs) +
                      len(selected_text_annotations) + len(selected_arrow_annotations))
        if total_count == 0:
            self.main_window.update_status("No annotations selected")
            return
        
        # Get source slice information from the subwindow's managers
        subwindows = self.multi_window_layout.get_all_subwindows()
        if subwindow in subwindows:
            idx = subwindows.index(subwindow)
            if idx in self.subwindow_managers:
                roi_manager = self.subwindow_managers[idx]['roi_manager']
                
                # Copy to clipboard with source slice info
                self.annotation_clipboard.copy_annotations(
                    selected_rois,
                    selected_measurements,
                    selected_crosshairs,
                    roi_manager.current_study_uid,
                    roi_manager.current_series_uid,
                    roi_manager.current_instance_identifier,
                    text_annotations=selected_text_annotations,
                    arrow_annotations=selected_arrow_annotations
                )
                
                # Update status
                self.main_window.update_status(f"Copied {total_count} annotation(s)")
    
    def _paste_annotations(self) -> None:
        """
        Paste annotations from clipboard to current slice.
        
        Applies smart offset: 10px offset if pasting to same slice, otherwise no offset.
        """
        # Check if clipboard has data
        if not self.annotation_clipboard.has_data():
            return
        
        data = self.annotation_clipboard.paste_annotations()
        if not data or data.get('type') != 'dicom_viewer_annotations':
            return
        
        # Get focused subwindow
        subwindow = self._get_focused_subwindow()
        if not subwindow:
            return
        
        # Get managers for this subwindow
        subwindows = self.multi_window_layout.get_all_subwindows()
        if subwindow not in subwindows:
            return
        
        idx = subwindows.index(subwindow)
        if idx not in self.subwindow_managers:
            return
        
        managers = self.subwindow_managers[idx]
        roi_manager = managers['roi_manager']
        measurement_tool = managers['measurement_tool']
        crosshair_manager = managers['crosshair_manager']
        text_annotation_tool = managers.get('text_annotation_tool')
        arrow_annotation_tool = managers.get('arrow_annotation_tool')
        
        # Determine offset based on whether pasting to same slice
        current_key = (roi_manager.current_study_uid,
                      roi_manager.current_series_uid,
                      roi_manager.current_instance_identifier)
        source_key = self.annotation_clipboard.get_source_slice_key()
        
        # Smart offset: apply offset only if pasting to same slice
        offset = QPointF(10, 10) if current_key == source_key else QPointF(0, 0)
        
        # Track newly created items for selection
        newly_created = []
        
        # Paste ROIs
        for roi_data in data.get('rois', []):
            new_roi = self._paste_roi(subwindow, managers, roi_data, offset)
            if new_roi:
                newly_created.append(new_roi.item)
        
        # Paste measurements
        for meas_data in data.get('measurements', []):
            new_measurement = self._paste_measurement(subwindow, managers, meas_data, offset)
            if new_measurement:
                newly_created.append(new_measurement)
        
        # Paste crosshairs
        for cross_data in data.get('crosshairs', []):
            new_crosshair = self._paste_crosshair(subwindow, managers, cross_data, offset)
            if new_crosshair:
                newly_created.append(new_crosshair)
        
        # Paste text annotations
        if text_annotation_tool:
            for text_data in data.get('text_annotations', []):
                new_text = self._paste_text_annotation(subwindow, managers, text_data, offset)
                if new_text:
                    newly_created.append(new_text)
        
        # Paste arrow annotations
        if arrow_annotation_tool:
            for arrow_data in data.get('arrow_annotations', []):
                new_arrow = self._paste_arrow_annotation(subwindow, managers, arrow_data, offset)
                if new_arrow:
                    newly_created.append(new_arrow)
        
        # Clear current selection
        if subwindow.image_viewer and subwindow.image_viewer.scene:
            subwindow.image_viewer.scene.clearSelection()
        
        # Select newly pasted items
        for item in newly_created:
            try:
                item.setSelected(True)
            except RuntimeError:
                # Item may have been deleted
                pass
        
        # Update displays
        if hasattr(subwindow, 'update_roi_list'):
            subwindow.update_roi_list()
        if subwindow.image_viewer and subwindow.image_viewer.scene:
            subwindow.image_viewer.scene.update()
        
        # Update status
        total_count = (len(data.get('rois', [])) + len(data.get('measurements', [])) + 
                      len(data.get('crosshairs', [])) + len(data.get('text_annotations', [])) + 
                      len(data.get('arrow_annotations', [])))
        self.main_window.update_status(f"Pasted {total_count} annotation(s)")
    
    def _paste_roi(self, subwindow: SubWindowContainer, managers: Dict, roi_data: Dict, offset: QPointF):
        """
        Recreate an ROI from clipboard data.
        
        Args:
            subwindow: SubWindowContainer to paste into
            managers: Dictionary of managers for this subwindow
            roi_data: Serialized ROI data
            offset: QPointF offset to apply
            
        Returns:
            Created ROIItem or None
        """
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QPen, QColor
        from tools.roi_manager import ROIItem, ROIGraphicsEllipseItem, ROIGraphicsRectItem
        from utils.undo_redo import ROICommand
        
        if not subwindow.image_viewer or not subwindow.image_viewer.scene:
            return None
        
        roi_coordinator = managers['roi_coordinator']
        roi_manager = managers['roi_manager']
        
        # Extract data
        shape_type = roi_data['shape_type']
        rect_data = roi_data['rect']
        pos_data = roi_data['position']
        pen_width = roi_data['pen_width']
        pen_color = roi_data['pen_color']
        
        # Apply offset to position
        new_pos = QPointF(pos_data['x'] + offset.x(), pos_data['y'] + offset.y())
        
        # Create rect
        rect = QRectF(rect_data['x'], rect_data['y'], rect_data['width'], rect_data['height'])
        
        # Create graphics item using custom classes that detect movement
        pen = QPen(QColor(*pen_color), pen_width)
        pen.setCosmetic(True)
        
        if shape_type == "ellipse":
            item = ROIGraphicsEllipseItem(rect)
        else:
            item = ROIGraphicsRectItem(rect)
        
        item.setPen(pen)
        item.setPos(new_pos)
        
        # Get default visible statistics if available
        default_stats = None
        if 'visible_statistics' in roi_data:
            default_stats = set(roi_data['visible_statistics'])
        
        # Create ROIItem
        roi_item = ROIItem(shape_type, item, pen_width=pen_width, pen_color=pen_color,
                          default_visible_statistics=default_stats)
        
        # Make selectable and movable
        item.setFlag(item.GraphicsItemFlag.ItemIsSelectable, True)
        item.setFlag(item.GraphicsItemFlag.ItemIsMovable, True)
        
        # Add to scene
        subwindow.image_viewer.scene.addItem(item)
        
        # Add to ROI manager and undo/redo system
        key = (roi_manager.current_study_uid,
               roi_manager.current_series_uid,
               roi_manager.current_instance_identifier)
        
        if key not in roi_manager.rois:
            roi_manager.rois[key] = []
        roi_manager.rois[key].append(roi_item)
        
        # Set up movement callback for ROI (needed for statistics overlay updates)
        roi_item.on_moved_callback = lambda r=roi_item: roi_coordinator._on_roi_moved(r)
        
        # Create undo command
        command = ROICommand(
            roi_manager,
            "add",
            roi_item,
            subwindow.image_viewer.scene,
            roi_manager.current_study_uid,
            roi_manager.current_series_uid,
            roi_manager.current_instance_identifier,
            update_statistics_callback=roi_coordinator.update_roi_statistics_overlays
        )
        self.undo_redo_manager.execute_command(command)
        
        # Create statistics overlays for the pasted ROI
        roi_coordinator.update_roi_statistics_overlays()
        
        return roi_item
    
    def _paste_measurement(self, subwindow: SubWindowContainer, managers: Dict, meas_data: Dict, offset: QPointF):
        """
        Recreate a measurement from clipboard data.
        
        Args:
            subwindow: SubWindowContainer to paste into
            managers: Dictionary of managers for this subwindow
            meas_data: Serialized measurement data
            offset: QPointF offset to apply
            
        Returns:
            Created MeasurementItem or None
        """
        from PySide6.QtWidgets import QGraphicsLineItem
        from PySide6.QtGui import QPen, QColor, QFont
        from tools.measurement_tool import MeasurementItem, DraggableMeasurementText
        from utils.undo_redo import MeasurementCommand
        
        if not subwindow.image_viewer or not subwindow.image_viewer.scene:
            return None
        
        measurement_coordinator = managers['measurement_coordinator']
        measurement_tool = managers['measurement_tool']
        
        # Extract data and apply offset
        start = QPointF(meas_data['start_point']['x'] + offset.x(),
                       meas_data['start_point']['y'] + offset.y())
        end = QPointF(meas_data['end_point']['x'] + offset.x(),
                     meas_data['end_point']['y'] + offset.y())
        pixel_spacing = meas_data['pixel_spacing']
        
        # Get settings from config
        if self.config_manager:
            line_thickness = self.config_manager.get_measurement_line_thickness()
            line_color = self.config_manager.get_measurement_line_color()
            font_size = self.config_manager.get_measurement_font_size()
            font_color = self.config_manager.get_measurement_font_color()
        else:
            line_thickness = 2
            line_color = (0, 255, 0)
            font_size = 14
            font_color = (255, 255, 0)
        
        # Create line item
        line_pen = QPen(QColor(*line_color), line_thickness)
        line_pen.setCosmetic(True)
        line_item = QGraphicsLineItem(start.x(), start.y(), end.x(), end.y())
        line_item.setPen(line_pen)
        
        # Create text item with proper callback signature (takes QPointF, not x, y)
        text_item = DraggableMeasurementText(None, lambda offset: None)
        text_item.setDefaultTextColor(QColor(*font_color))
        font = QFont("Arial", font_size)
        font.setBold(True)
        text_item.setFont(font)
        text_item.setFlag(text_item.GraphicsItemFlag.ItemIgnoresTransformations, True)
        text_item.setFlag(text_item.GraphicsItemFlag.ItemIsMovable, True)
        text_item.setFlag(text_item.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        text_item.setFlag(text_item.GraphicsItemFlag.ItemIsSelectable, True)
        
        # Create measurement item
        measurement = MeasurementItem(start, end, line_item, text_item, pixel_spacing=pixel_spacing)
        text_item.measurement = measurement
        
        # Add to scene
        subwindow.image_viewer.scene.addItem(measurement)
        measurement.setZValue(150)
        text_item.setZValue(151)
        subwindow.image_viewer.scene.addItem(text_item)
        
        # Update distance
        measurement.update_distance()
        
        # Add to measurement tool
        key = (measurement_tool.current_study_uid,
               measurement_tool.current_series_uid,
               measurement_tool.current_instance_identifier)
        
        if key not in measurement_tool.measurements:
            measurement_tool.measurements[key] = []
        measurement_tool.measurements[key].append(measurement)
        
        # Create undo command
        command = MeasurementCommand(
            measurement_tool,
            "add",
            measurement,
            subwindow.image_viewer.scene,
            measurement_tool.current_study_uid,
            measurement_tool.current_series_uid,
            measurement_tool.current_instance_identifier
        )
        self.undo_redo_manager.execute_command(command)
        
        return measurement
    
    def _paste_crosshair(self, subwindow: SubWindowContainer, managers: Dict, cross_data: Dict, offset: QPointF):
        """
        Recreate a crosshair from clipboard data.
        
        Args:
            subwindow: SubWindowContainer to paste into
            managers: Dictionary of managers for this subwindow
            cross_data: Serialized crosshair data
            offset: QPointF offset to apply
            
        Returns:
            Created CrosshairItem or None
        """
        from tools.crosshair_manager import CrosshairItem
        from utils.undo_redo import CrosshairCommand
        
        if not subwindow.image_viewer or not subwindow.image_viewer.scene:
            return None
        
        crosshair_coordinator = managers['crosshair_coordinator']
        crosshair_manager = managers['crosshair_manager']
        
        # Extract data and apply offset
        pos = QPointF(cross_data['position']['x'] + offset.x(),
                     cross_data['position']['y'] + offset.y())
        pixel_value_str = cross_data['pixel_value_str']
        x_coord = cross_data['x_coord']
        y_coord = cross_data['y_coord']
        z_coord = cross_data['z_coord']
        text_offset_viewport = cross_data.get('text_offset_viewport', (5.0, 5.0))
        
        # Create crosshair item
        crosshair = CrosshairItem(
            pos,
            pixel_value_str,
            x_coord,
            y_coord,
            z_coord,
            self.config_manager,
            crosshair_manager.privacy_mode
        )
        
        # Restore text offset
        crosshair.text_offset_viewport = text_offset_viewport
        
        # Add to scene
        subwindow.image_viewer.scene.addItem(crosshair)
        if crosshair.text_item:
            subwindow.image_viewer.scene.addItem(crosshair.text_item)
            # Update text position
            if subwindow.image_viewer:
                crosshair.update_text_position(subwindow.image_viewer)
        
        # Add to crosshair manager
        key = (crosshair_manager.current_study_uid,
               crosshair_manager.current_series_uid,
               crosshair_manager.current_instance_identifier)
        
        if key not in crosshair_manager.crosshairs:
            crosshair_manager.crosshairs[key] = []
        crosshair_manager.crosshairs[key].append(crosshair)
        
        # Create undo command
        command = CrosshairCommand(
            crosshair_manager,
            "add",
            crosshair,
            subwindow.image_viewer.scene,
            crosshair_manager.current_study_uid,
            crosshair_manager.current_series_uid,
            crosshair_manager.current_instance_identifier
        )
        self.undo_redo_manager.execute_command(command)
        
        return crosshair
    
    def _paste_text_annotation(self, subwindow: SubWindowContainer, managers: Dict, text_data: Dict, offset: QPointF):
        """
        Recreate a text annotation from clipboard data.
        
        Args:
            subwindow: SubWindowContainer to paste into
            managers: Dictionary of managers for this subwindow
            text_data: Serialized text annotation data
            offset: QPointF offset to apply
            
        Returns:
            Created TextAnnotationItem or None
        """
        from tools.text_annotation_tool import TextAnnotationItem
        from utils.undo_redo import TextAnnotationCommand
        from PySide6.QtGui import QColor, QFont
        
        if not subwindow.image_viewer or not subwindow.image_viewer.scene:
            return None
        
        text_annotation_tool = managers.get('text_annotation_tool')
        if not text_annotation_tool:
            return None
        
        # Extract data and apply offset
        text = text_data.get('text', '')
        pos = QPointF(text_data['position']['x'] + offset.x(),
                     text_data['position']['y'] + offset.y())
        font_size = text_data.get('font_size', 12)
        color_data = text_data.get('color', {'r': 255, 'g': 255, 'b': 0})
        color = QColor(color_data['r'], color_data['g'], color_data['b'])
        
        # Create text annotation item
        text_item = TextAnnotationItem(text, self.config_manager, on_editing_finished=None)
        text_item.setPos(pos)
        text_item.setDefaultTextColor(color)
        font = QFont("Arial", font_size)
        font.setBold(True)
        text_item.setFont(font)
        
        # Add to scene
        subwindow.image_viewer.scene.addItem(text_item)
        text_item.setZValue(160)
        
        # Add to text annotation tool
        key = (text_annotation_tool.current_study_uid,
               text_annotation_tool.current_series_uid,
               text_annotation_tool.current_instance_identifier)
        
        if key not in text_annotation_tool.annotations:
            text_annotation_tool.annotations[key] = []
        text_annotation_tool.annotations[key].append(text_item)
        
        # Create undo command
        command = TextAnnotationCommand(
            text_annotation_tool,
            "add",
            text_item,
            subwindow.image_viewer.scene,
            text_annotation_tool.current_study_uid,
            text_annotation_tool.current_series_uid,
            text_annotation_tool.current_instance_identifier
        )
        self.undo_redo_manager.execute_command(command)
        
        return text_item
    
    def _paste_arrow_annotation(self, subwindow: SubWindowContainer, managers: Dict, arrow_data: Dict, offset: QPointF):
        """
        Recreate an arrow annotation from clipboard data.
        
        Args:
            subwindow: SubWindowContainer to paste into
            managers: Dictionary of managers for this subwindow
            arrow_data: Serialized arrow annotation data
            offset: QPointF offset to apply
            
        Returns:
            Created ArrowAnnotationItem or None
        """
        from tools.arrow_annotation_tool import ArrowAnnotationItem
        from utils.undo_redo import ArrowAnnotationCommand
        from PySide6.QtGui import QColor, QPen
        from PySide6.QtCore import QLineF, QPointF
        from PySide6.QtWidgets import QGraphicsLineItem
        
        if not subwindow.image_viewer or not subwindow.image_viewer.scene:
            return None
        
        arrow_annotation_tool = managers.get('arrow_annotation_tool')
        if not arrow_annotation_tool:
            return None
        
        # Extract data and apply offset
        start = QPointF(arrow_data['start_point']['x'] + offset.x(),
                       arrow_data['start_point']['y'] + offset.y())
        end = QPointF(arrow_data['end_point']['x'] + offset.x(),
                     arrow_data['end_point']['y'] + offset.y())
        color_data = arrow_data.get('color', {'r': 255, 'g': 255, 'b': 0})
        color = QColor(color_data['r'], color_data['g'], color_data['b'])
        
        # Get arrow size (line thickness) from config; arrowhead drawn larger for balance
        arrow_size = self.config_manager.get_arrow_annotation_size() if self.config_manager else 6
        from tools.arrow_annotation_tool import ARROWHEAD_SIZE_MULTIPLIER, ArrowHeadItem
        arrowhead_size = arrow_size * ARROWHEAD_SIZE_MULTIPLIER
        
        # Create line item - full length to tip (arrowhead is viewport-sized and sits on top)
        relative_end = end - start
        line = QLineF(QPointF(0, 0), relative_end)
        line_item = QGraphicsLineItem(line)
        pen = QPen(color, arrow_size)
        pen.setCosmetic(True)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        line_item.setPen(pen)
        line_item.setZValue(160)
        
        # Create arrowhead (viewport-relative via ItemIgnoresTransformations)
        arrowhead = ArrowHeadItem(QPointF(0, 0), relative_end, color, arrowhead_size)
        
        # Create arrow group
        arrow_item = ArrowAnnotationItem(start, end, line_item, arrowhead, color)
        
        # Set group position to start so line and arrowhead are positioned correctly
        arrow_item.setPos(start)
        
        # Add to scene
        subwindow.image_viewer.scene.addItem(arrow_item)
        
        # Add to arrow annotation tool
        key = (arrow_annotation_tool.current_study_uid,
               arrow_annotation_tool.current_series_uid,
               arrow_annotation_tool.current_instance_identifier)
        
        if key not in arrow_annotation_tool.arrows:
            arrow_annotation_tool.arrows[key] = []
        arrow_annotation_tool.arrows[key].append(arrow_item)
        
        # Set up move callback for undo/redo tracking
        arrow_coordinator = managers.get('arrow_annotation_coordinator')
        if arrow_coordinator and hasattr(arrow_coordinator, '_on_arrow_moved'):
            arrow_item.on_moved_callback = arrow_coordinator._on_arrow_moved
        
        # Create undo command
        command = ArrowAnnotationCommand(
            arrow_annotation_tool,
            "add",
            arrow_item,
            subwindow.image_viewer.scene,
            arrow_annotation_tool.current_study_uid,
            arrow_annotation_tool.current_series_uid,
            arrow_annotation_tool.current_instance_identifier
        )
        self.undo_redo_manager.execute_command(command)
        
        return arrow_item
    
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
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication
        if isinstance(event, QKeyEvent):
            # Don't intercept standard shortcuts - let menu system handle them
            if event.key() == Qt.Key.Key_Z:
                if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
                    # Cmd+Z or Ctrl+Z - let menu handle it
                    return False
            
            # For layout shortcuts (1, 2, 3, 4), check if focused widget is allowed
            if event.key() in (Qt.Key.Key_1, Qt.Key.Key_2, Qt.Key.Key_3, Qt.Key.Key_4):
                # Check if focused widget is navigator, left panel, right panel, or image viewer (or their children)
                focused_widget = QApplication.focusWidget()
                if focused_widget is not None:
                    if not self._is_widget_allowed_for_layout_shortcuts(focused_widget):
                        # Focused widget is not allowed, don't process layout shortcuts
                        return False
            
            return self.keyboard_event_handler.handle_key_event(event)
        return super().eventFilter(obj, event)
    
    def _is_widget_allowed_for_layout_shortcuts(self, widget) -> bool:
        """
        Check if a widget is allowed to trigger layout shortcuts.
        
        Allowed widgets:
        - Series navigator or its children
        - Left panel or its children
        - Right panel or its children
        - Image viewer or its children
        
        Args:
            widget: Widget to check
            
        Returns:
            True if widget is allowed, False otherwise
        """
        if widget is None:
            return False
        
        # Traverse up the parent chain to find allowed widgets
        current = widget
        max_depth = 10  # Safety limit
        depth = 0
        
        while current is not None and depth < max_depth:
            # Check if current widget is the series navigator
            if current == self.series_navigator:
                return True
            
            # Check if current widget is the left panel
            if hasattr(self.main_window, 'left_panel') and current == self.main_window.left_panel:
                return True
            
            # Check if current widget is the right panel
            if hasattr(self.main_window, 'right_panel') and current == self.main_window.right_panel:
                return True
            
            # Check if current widget is an image viewer
            from gui.image_viewer import ImageViewer
            if isinstance(current, ImageViewer):
                return True
            
            # Check if current widget is a child of left/right panel by checking object name
            if hasattr(current, 'objectName'):
                obj_name = current.objectName()
                if obj_name == "left_panel" or obj_name == "right_panel":
                    return True
            
            # Move up the parent chain
            current = current.parentWidget()
            depth += 1
        
        return False
    
    def run(self) -> int:
        """
        Run the application.
        
        Returns:
            Exit code
        """
        # Show disclaimer dialog before showing main window
        from gui.dialogs.disclaimer_dialog import DisclaimerDialog
        if not DisclaimerDialog.show_disclaimer(self.config_manager, self.main_window, force_show=False):
            # User cancelled, exit application
            return 0
        
        # Show window maximized (full-screen)
        self.main_window.showMaximized()
        
        # Set keyboard focus after window is shown
        # Use QTimer to ensure window is fully visible before setting focus
        from PySide6.QtCore import QTimer
        QTimer.singleShot(100, self._set_initial_keyboard_focus)
        
        return self.app.exec()
    
    def _set_initial_keyboard_focus(self) -> None:
        """Set keyboard focus to the focused subwindow after window is shown."""
        if self.image_viewer:
            self.image_viewer.setFocus()


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


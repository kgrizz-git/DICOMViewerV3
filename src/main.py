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
import json
import traceback
from datetime import datetime, timezone
from pathlib import Path

# Add src directory to path
src_dir = Path(__file__).parent
sys.path.insert(0, str(src_dir))

from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QMessageBox,
    QProgressDialog,
    QStyleFactory,
)
from PySide6.QtCore import Qt, QPoint, QPointF, QObject, QTimer, QRectF, QSize, Signal
from PySide6.QtGui import QCursor
from typing import Any, Callable, Optional, Dict, List, Tuple, cast, Set
import pydicom
from pydicom.dataset import Dataset

from core import dialog_action_handlers
from gui.main_window import MainWindow
from gui.main_window_layout_helper import setup_main_window_content
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
from gui.window_slot_map_widget import WindowSlotMapPopupDialog, WindowSlotMapWidget
from core.dicom_loader import DICOMLoader
from core.dicom_organizer import DICOMOrganizer
from core.dicom_parser import DICOMParser
from core.dicom_processor import DICOMProcessor
from core.tag_edit_history import TagEditHistoryManager
from utils.config_manager import ConfigManager
from utils.dicom_utils import get_composite_series_key
from tools.roi_manager import ROIItem
from tools.annotation_manager import AnnotationManager
from tools.histogram_widget import HistogramWidget
from gui.overlay_manager import OverlayManager
from utils.annotation_clipboard import AnnotationClipboard
from utils.bundled_fonts import register_fonts_with_qt

from metadata.metadata_controller import MetadataController
from roi.roi_measurement_controller import ROIMeasurementController

# Import handler classes
from core.file_operations_handler import FileOperationsHandler
from core.annotation_paste_handler import AnnotationPasteHandler
from core.file_series_loading_coordinator import FileSeriesLoadingCoordinator
from core.subwindow_lifecycle_controller import SubwindowLifecycleController
from core.mpr_controller import MprController, apply_mpr_stack_combine
from core.customization_handlers import CustomizationHandlers
from core.privacy_controller import PrivacyController
from core.projection_app_facade import ProjectionAppFacade
from core.qa_app_facade import QAAppFacade
from core.export_app_facade import ExportAppFacade
from core.subwindow_image_viewer_sync import (
    apply_initial_image_viewer_display_state,
    set_direction_labels_all,
    set_direction_labels_color_all,
    set_scale_markers_all,
    set_scale_markers_color_all,
    set_slice_slider_all,
    set_smooth_when_zoomed_all,
)
from core.subwindow_manager_factory import build_managers_for_subwindow
from core.cine_app_facade import CineAppFacade
from core.main_app_key_event_filter import dispatch_app_key_event, is_widget_allowed_for_layout_shortcuts
from core.window_level_preset_handler import apply_window_level_preset
from gui.dialog_coordinator import DialogCoordinator
from gui.mouse_mode_handler import MouseModeHandler
from gui.keyboard_event_handler import KeyboardEventHandler
from gui.dialogs.tag_export_union_worker import TagExportUnionWorker
from gui.dialogs.disclaimer_dialog import DisclaimerDialog

# Import fusion components
from core.fusion_processor import FusionProcessor
from gui.fusion_controls_widget import FusionControlsWidget
from core.app_signal_wiring import wire_all_signals
from qa.analysis_types import (
    MRIBatchResult,
    MRICompareRequest,
    QARequest,
    QAResult,
)
from qa.worker import QAAnalysisWorker, QABatchWorker

# Import slice sync components
from core.slice_sync_coordinator import SliceSyncCoordinator
from core.slice_location_line_coordinator import SliceLocationLineCoordinator

# Studies structure: study UID → composite series key → ordered instance datasets.
StudiesNestedDict = Dict[str, Dict[str, List[Dataset]]]


class DICOMViewerApp(QObject):
    """
    Main application class for DICOM Viewer.
    
    Coordinates all components and handles application logic.
    """

    #: Emitted when background tag-export union finishes (generation, merged dict).
    tag_export_union_ready = Signal(int, object)

    app: QApplication

    # Set in __init__ (real objects in _initialize_handlers); placeholders use cast(object, None)
    # so the checker accepts definite assignment before coordinator construction runs.
    _file_series_coordinator: FileSeriesLoadingCoordinator
    file_operations_handler: FileOperationsHandler
    dialog_coordinator: DialogCoordinator
    _privacy_controller: PrivacyController
    _customization_handlers: CustomizationHandlers
    mouse_mode_handler: MouseModeHandler
    cine_player: CinePlayer
    cine_app_facade: CineAppFacade
    keyboard_event_handler: KeyboardEventHandler

    # Lazily created UI / background workers (Optional avoids Pyright
    # reportUninitializedInstanceVariable on first use).
    _window_slot_map_dialog: Optional[WindowSlotMapPopupDialog] = None
    _window_slot_map_widget_popup: Optional[WindowSlotMapWidget] = None
    _qa_worker: Optional[QAAnalysisWorker] = None
    _qa_batch_worker: Optional[QABatchWorker] = None
    _mri_compare_result_dialog: Optional[QDialog] = None
    _histogram_wl_update_timer: Optional[QTimer] = None
    _histogram_update_timer: Optional[QTimer] = None

    def __init__(self):
        """
        Initialize the DICOM Viewer application.

        Initialization order is significant and must be preserved:

        1. _init_core_managers()
           QApplication + all data managers (config, DICOM, history, undo/redo).
           No widgets are created yet; Qt must exist first.

        2. _init_main_window_and_layout()
           MainWindow, FileDialog, and MultiWindowLayout.
           Requires Step 1: widgets need config_manager and QApplication.

        3. _init_controllers_and_tools()
           MetadataController and ROIMeasurementController.
           Requires Step 2: theme must be applied before metadata panel is shown.

        4. _init_view_widgets()
           Remaining shared view widgets (navigators, fusion, overlays, etc.).
           Requires Step 1 for config; Step 3 for privacy flag propagation.

        5. _post_init_subwindows_and_handlers()
           UI assembly, per-subwindow manager creation, handler init, signal
           wiring, and final interaction setup.
           Must be last: all managers, widgets, and controllers must be ready.
        """
        # Initialize QObject first (must be the very first statement)
        super().__init__()

        # Typed placeholders; real instances are assigned in _initialize_handlers()
        # (invoked from __init__ via _post_init_subwindows_and_handlers).
        self._file_series_coordinator = cast(
            FileSeriesLoadingCoordinator, cast(object, None)
        )
        self.file_operations_handler = cast(FileOperationsHandler, cast(object, None))
        self.dialog_coordinator = cast(DialogCoordinator, cast(object, None))
        self._privacy_controller = cast(PrivacyController, cast(object, None))
        self._customization_handlers = cast(CustomizationHandlers, cast(object, None))
        self.mouse_mode_handler = cast(MouseModeHandler, cast(object, None))
        self.cine_player = cast(CinePlayer, cast(object, None))
        self.cine_app_facade = cast(CineAppFacade, cast(object, None))
        self.keyboard_event_handler = cast(KeyboardEventHandler, cast(object, None))

        # Step 1 – Core application and data managers
        self._init_core_managers()

        # Step 2 – Main window, file dialog, and layout skeleton
        self._init_main_window_and_layout()

        # Step 3 – Feature controllers (MetadataController, ROIMeasurementController)
        self._init_controllers_and_tools()

        # Step 4 – Remaining shared view widgets
        self._init_view_widgets()

        # Step 5 – Subwindow lifecycle, handlers, signals, and post-init interaction
        self._post_init_subwindows_and_handlers()

    def _init_core_managers(self) -> None:
        """
        Create the Qt application, all data managers, and application-wide state.
        
        This is the very first initialization step. No widgets may be created
        before QApplication exists.
        """
        # Qt application (must precede any widget creation). Reuse an existing
        # QApplication instance when running under tests or embedded contexts.
        existing_app = QApplication.instance()
        if existing_app is None:
            self.app = QApplication(sys.argv)
        else:
            # Reuse existing app (tests / embedded); instance() is typed as QCoreApplication.
            self.app = cast(QApplication, existing_app)
        self.app.setApplicationName("DICOM Viewer V3")
        self.app.setStyle(QStyleFactory.create("Fusion"))

        # Register bundled TrueType fonts with Qt so they can be used by name
        register_fonts_with_qt()

        # DICOM data managers
        self.config_manager = ConfigManager()
        self.dicom_loader = DICOMLoader()
        self.dicom_organizer = DICOMOrganizer()
        self.dicom_processor = DICOMProcessor()

        # Tag-edit history and general undo/redo stack
        self.tag_edit_history = TagEditHistoryManager(max_history=50)
        self.undo_redo_manager = UndoRedoManager(max_history=100)
        self.annotation_clipboard = AnnotationClipboard()

        # Application-wide flags read from persisted config
        self.privacy_view_enabled: bool = self.config_manager.get_privacy_view()
        # Studies that have already shown the fusion compatibility notification
        self._fusion_notified_studies: Set[str] = set()

    def _init_main_window_and_layout(self) -> None:
        """
        Create the main window, file dialog, and multi-window layout.

        Must follow _init_core_managers so that config_manager and the Qt
        application are available.  The main window theme is applied here so
        that subsequent widget creation happens against the correct palette.
        """
        # Main window
        self.main_window = MainWindow(self.config_manager)
        self.main_window.installEventFilter(self)

        # File open dialog (shared across the application)
        self.file_dialog = FileDialog(self.config_manager)

        # Multi-window image layout
        self.multi_window_layout = MultiWindowLayout(config_manager=self.config_manager)
        initial_layout = self.config_manager.get_multi_window_layout()
        self.multi_window_layout.set_layout(initial_layout)
        self.main_window.set_layout_mode(initial_layout)

        # Legacy backward-compatibility reference – updated once subwindows exist
        self.image_viewer: Optional[ImageViewer] = None

        # Per-subwindow manager registry: {subwindow_index: {manager_name: instance}}
        self.subwindow_managers: Dict[int, Dict[str, Any]] = {}

        # Index of the subwindow that currently has input focus
        self.focused_subwindow_index: int = 0

        # Ensure the main window's image_viewer ref is clear until subwindows are ready,
        # then apply the theme so the background colour is correct.
        self.main_window.image_viewer = None
        self.main_window._apply_theme()

    def _init_view_widgets(self) -> None:
        """
        Create remaining shared view-layer widgets.

        Must follow _init_core_managers (config access) and
        _init_controllers_and_tools (privacy flag already confirmed).
        """
        self.window_level_controls = WindowLevelControls()
        self.zoom_display_widget = ZoomDisplayWidget()
        self.slice_navigator = SliceNavigator()

        # Operation guard flags
        self._resetting_projection_state = False
        self._series_navigation_in_progress = False

        # Navigation and playback widgets
        self.series_navigator = SeriesNavigator(self.dicom_processor)
        self.series_navigator.set_multiframe_info_map(self.dicom_organizer.series_multiframe_info)
        self.series_navigator.set_show_instances_separately(
            self.config_manager.get_show_instances_separately()
        )
        self.cine_controls_widget = CineControlsWidget()
        self.intensity_projection_controls_widget = IntensityProjectionControlsWidget()

        # Fusion components (FusionHandler itself is created per-subwindow)
        self.fusion_processor = FusionProcessor()
        self.fusion_controls_widget = FusionControlsWidget(config_manager=self.config_manager)

        # Shared overlay manager (each subwindow also has its own copy)
        font_size = self.config_manager.get_overlay_font_size()
        font_color = self.config_manager.get_overlay_font_color()
        font_family = self.config_manager.get_overlay_font_family()
        font_variant = self.config_manager.get_overlay_font_variant()
        self.overlay_manager = OverlayManager(
            font_size=font_size,
            font_color=font_color,
            font_family=font_family,
            font_variant=font_variant,
            config_manager=self.config_manager,
        )
        # Overlay always starts with everything visible; privacy mode is applied immediately.
        self.overlay_manager.set_privacy_mode(self.privacy_view_enabled)

        # Scroll-wheel mode is propagated to individual image viewers after creation.
        scroll_mode = self.config_manager.get_scroll_wheel_mode()
        self.slice_navigator.set_scroll_wheel_mode(scroll_mode)

    def _post_init_subwindows_and_handlers(self) -> None:
        """
        Assemble the UI, create per-subwindow managers, wire handlers and signals.

        This step must run last: it assumes all managers, widgets, and controllers
        have been fully created by the earlier _init_* methods.
        """
        # Assemble the Qt UI layout (panels, splitters, menus, toolbars)
        self._setup_ui()

        # Per-subwindow data: {index: {current_dataset, current_slice_index, ...}}
        self.subwindow_data: Dict[int, Dict[str, Any]] = {}

        # Subwindow lifecycle controller must precede _initialize_subwindow_managers
        # because that method calls _connect_all_subwindow_transform_signals().
        self._subwindow_lifecycle_controller = SubwindowLifecycleController(self)

        # Create per-subwindow managers for every current subwindow slot
        self._initialize_subwindow_managers()

        # Slice sync coordinator: holds no Qt objects; safe to create here.
        self._slice_sync_coordinator = SliceSyncCoordinator(self)
        self._slice_sync_coordinator.set_enabled(
            self.config_manager.get_slice_sync_enabled()
        )
        self._slice_sync_coordinator.set_groups(
            self.config_manager.get_slice_sync_groups()
        )

        # Slice location line coordinator: shows intersection of other views' slice planes.
        self._slice_location_line_coordinator = SliceLocationLineCoordinator(self)

        # MPR controller: manages MPR views across all subwindows.
        self._mpr_controller = MprController(self)

        self._annotation_paste_handler = AnnotationPasteHandler(self)

        # Propagate initial privacy, slice sync, smoothing, and scale/direction UI to all viewers
        apply_initial_image_viewer_display_state(self)

        # Resolve which subwindow currently has focus and set up its manager references.
        # Must happen before _initialize_handlers() which consumes these references.
        focused_subwindow = self.multi_window_layout.get_focused_subwindow()
        if focused_subwindow:
            subwindows = self.multi_window_layout.get_all_subwindows()
            if focused_subwindow in subwindows:
                focused_idx = subwindows.index(focused_subwindow)
                if focused_idx in self.subwindow_managers:
                    self._update_focused_subwindow_references()

        # Fallback: if the focused-subwindow path failed to set managers, use index 0.
        if not hasattr(self, 'roi_coordinator') or self.roi_coordinator is None:
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

        # Legacy current-data fields for backward compatibility with handlers
        # that predate the multi-window architecture.
        self.current_datasets: List[Dataset] = []
        self.current_studies: StudiesNestedDict = {}
        self.current_slice_index = 0
        self.current_series_uid = ""
        self.current_study_uid = ""
        self.current_dataset: Optional[Dataset] = None

        self._tag_export_union_generation = 0
        self._tag_export_union_merged: Optional[Dict[str, Any]] = None
        self._tag_export_union_worker: Optional[Any] = None

        # Initialize handler objects (depends on all manager references above)
        self._initialize_handlers()

        # Feature façades (logic only; signal targets remain on DICOMViewerApp)
        self._projection_app_facade = ProjectionAppFacade(self)
        self._qa_app_facade = QAAppFacade(self)
        self._export_app_facade = ExportAppFacade(self)

        # Wire Qt signals to slots
        self._connect_signals()

        # Set default mouse mode to pan on every image viewer
        for subwindow in self.multi_window_layout.get_all_subwindows():
            if subwindow:
                subwindow.image_viewer.set_mouse_mode("pan")

    def _init_controllers_and_tools(self) -> None:
        """
        Initialize high-level feature controllers and expose their shared components.

        Step 3 of the DICOMViewerApp initialization sequence. Creates:
        - MetadataController: owns MetadataPanel, TagEditHistoryManager,
          undo/redo wiring, and metadata privacy mode.
        - ROIMeasurementController: owns ROIManager, MeasurementTool,
          AnnotationManager, ROIStatisticsPanel, and ROIListPanel.

        Backward-compatibility aliases (e.g. self.metadata_panel, self.roi_manager)
        are set here so that the rest of the application can continue to access
        these objects directly without knowing about the controller layer.
        """
        # Initialize metadata controller (owns metadata_panel and history wiring)
        self.metadata_controller = MetadataController(
            config_manager=self.config_manager,
            tag_edit_history=self.tag_edit_history,
            undo_redo_manager=self.undo_redo_manager,
            ui_refresh_callback=self._refresh_tag_ui,
            initial_privacy_mode=self.privacy_view_enabled,
        )
        self.metadata_panel = self.metadata_controller.metadata_panel

        # Initialize ROI / measurement controller
        self.roi_measurement_controller = ROIMeasurementController(
            config_manager=self.config_manager
        )
        self.roi_manager = self.roi_measurement_controller.roi_manager
        self.measurement_tool = self.roi_measurement_controller.measurement_tool
        self.annotation_manager = self.roi_measurement_controller.annotation_manager
        self.roi_statistics_panel = (
            self.roi_measurement_controller.roi_statistics_panel
        )
        self.roi_list_panel = self.roi_measurement_controller.roi_list_panel

    def _build_managers_for_subwindow(self, idx: int, subwindow: SubWindowContainer) -> Dict[str, Any]:
        """
        Build the full set of per-subwindow managers for the given subwindow.
        Delegates to ``core.subwindow_manager_factory.build_managers_for_subwindow``.
        """
        return build_managers_for_subwindow(self, idx, subwindow)

    def _initialize_subwindow_managers(self) -> None:
        """Initialize managers for each subwindow."""
        subwindows = self.multi_window_layout.get_all_subwindows()
        if not subwindows:
            self.multi_window_layout.set_layout("1x1")
            subwindows = self.multi_window_layout.get_all_subwindows()
            if not subwindows:
                raise RuntimeError("Failed to create subwindows. Cannot initialize managers.")
        for idx, subwindow in enumerate(subwindows):
            if subwindow is None:
                continue
            subwindow.image_viewer.set_subwindow_index(idx)
            managers = self._build_managers_for_subwindow(idx, subwindow)
            self.subwindow_managers[idx] = managers
            self.subwindow_data[idx] = {
                'current_dataset': None,
                'current_slice_index': 0,
                'current_series_uid': '',
                'current_study_uid': '',
                'current_datasets': []
            }
        self._connect_all_subwindow_transform_signals()

    def _create_managers_for_subwindow(self, idx: int, subwindow: SubWindowContainer) -> None:
        """Create managers for a specific subwindow (e.g. when layout adds a new pane)."""
        if subwindow is None:
            return
        managers = self._build_managers_for_subwindow(idx, subwindow)
        image_viewer = subwindow.image_viewer
        image_viewer.set_subwindow_index(idx)
        image_viewer.set_slice_sync_enabled_state(self.config_manager.get_slice_sync_enabled())
        image_viewer.set_smooth_when_zoomed_state(self.config_manager.get_smooth_image_when_zoomed())
        image_viewer.set_scale_markers_state(self.config_manager.get_show_scale_markers())
        image_viewer.set_direction_labels_state(self.config_manager.get_show_direction_labels())
        image_viewer.set_scale_markers_color_state(self.config_manager.get_scale_markers_color())
        image_viewer.set_direction_labels_color_state(self.config_manager.get_direction_labels_color())
        image_viewer.set_direction_label_size_state(self.config_manager.get_direction_label_size())
        image_viewer.set_scale_markers_tick_intervals_state(
            self.config_manager.get_scale_markers_major_tick_interval_mm(),
            self.config_manager.get_scale_markers_minor_tick_interval_mm(),
        )
        image_viewer.get_file_path_callback = lambda i=idx: self._get_current_slice_file_path(i)
        self.subwindow_managers[idx] = managers
        if idx not in self.subwindow_data:
            self.subwindow_data[idx] = {
                'current_dataset': None,
                'current_slice_index': 0,
                'current_series_uid': '',
                'current_study_uid': '',
                'current_datasets': []
            }
        image_viewer.set_mouse_mode("pan")

    def _get_subwindow_dataset(self, idx: int) -> Optional[Dataset]:
        """Get current dataset for a subwindow. Delegates to subwindow lifecycle controller."""
        return self._subwindow_lifecycle_controller.get_subwindow_dataset(idx)

    def _get_subwindow_slice_index(self, idx: int) -> int:
        """Get current slice index for a subwindow. Delegates to subwindow lifecycle controller."""
        return self._subwindow_lifecycle_controller.get_subwindow_slice_index(idx)

    def _get_subwindow_slice_display_manager(self, idx: int):
        """Get slice display manager for a subwindow. Delegates to subwindow lifecycle controller."""
        return self._subwindow_lifecycle_controller.get_subwindow_slice_display_manager(idx)

    def _get_subwindow_mpr_pixel_array(self, idx: int, slice_index: Optional[int] = None):
        """Return an MPR pixel array for subwindow *idx* (if any)."""
        try:
            data = self.subwindow_data.get(idx, {})
            if not data.get("is_mpr"):
                return None
            result = data.get("mpr_result")
            if result is None:
                return None
            if slice_index is None:
                slice_index = data.get("mpr_slice_index", 0)
            if slice_index is None:
                return None
            slice_index = int(slice_index)
            if slice_index < 0 or slice_index >= getattr(result, "n_slices", 0):
                return None
            raw = apply_mpr_stack_combine(
                result.slices,
                slice_index,
                enabled=bool(data.get("mpr_combine_enabled", False)),
                mode=str(data.get("mpr_combine_mode", "aip") or "aip"),
                n_planes=int(data.get("mpr_combine_slice_count", 4) or 4),
            )
            managers = self.subwindow_managers.get(idx, {})
            view_state_manager = managers.get("view_state_manager")
            use_rescaled = bool(
                getattr(view_state_manager, "use_rescaled_values", True)
            )
            if use_rescaled:
                return result.apply_rescale(raw)
            return raw
        except Exception:
            return None

    def _get_subwindow_mpr_thumbnail_pixel_array(self, idx: int):
        """Return a representative MPR thumbnail slice, preferring the stack midpoint."""
        data = self.subwindow_data.get(idx, {})
        result = data.get("mpr_result")
        if result is None:
            return None
        n_slices = int(getattr(result, "n_slices", 0) or 0)
        if n_slices <= 0:
            return None
        middle_index = n_slices // 2
        return self._get_subwindow_mpr_pixel_array(idx, middle_index)

    def _update_mpr_navigator_thumbnail(self, idx: int) -> None:
        """
        Show or refresh the MPR thumbnail in the series navigator for subwindow *idx*.

        Called automatically when ``MprController.mpr_activated`` is emitted.
        The thumbnail is built from the currently-displayed MPR slice pixel
        array with the active W/L values so it matches what is on screen.

        Args:
            idx: Zero-based subwindow index hosting the MPR view.
        """
        if not hasattr(self, "series_navigator"):
            return
        self.series_navigator.clear_mpr_thumbnail(-1)
        data = self.subwindow_data.get(idx, {})
        if not data.get("is_mpr") or data.get("mpr_result") is None:
            self.series_navigator.clear_mpr_thumbnail(idx)
            return

        pixel_array = self._get_subwindow_mpr_thumbnail_pixel_array(idx)
        if pixel_array is None:
            return

        wc: Optional[float] = None
        ww: Optional[float] = None
        wl_controls = getattr(self, "window_level_controls", None)
        if wl_controls is not None:
            try:
                wc_val = float(wl_controls.window_center)
                ww_val = float(wl_controls.window_width)
                if ww_val > 0:
                    wc, ww = wc_val, ww_val
            except (AttributeError, TypeError, ValueError):
                pass

        self.series_navigator.set_mpr_thumbnail(
            idx,
            pixel_array,
            str(data.get("current_study_uid", "") or ""),
            str(data.get("current_series_uid", "") or ""),
            wc,
            ww,
        )

    def _clear_mpr_navigator_thumbnail(self, idx: int) -> None:
        """
        Remove the MPR thumbnail from the series navigator for subwindow *idx*.

        Called automatically when ``MprController.mpr_cleared`` is emitted.

        Args:
            idx: Zero-based subwindow index whose MPR was cleared.
        """
        if hasattr(self, "series_navigator"):
            self.series_navigator.clear_mpr_thumbnail(idx)

    def _update_floating_mpr_navigator_thumbnail(self) -> None:
        """
        Show or refresh detached MPR under navigator key -1 (internal id only).

        Layout matches attached MPR: same study/series keys place the thumbnail
        immediately after the source series row.
        """
        if not hasattr(self, "series_navigator"):
            return
        if not self._mpr_controller.has_detached_mpr():
            self.series_navigator.clear_mpr_thumbnail(-1)
            return
        focused = getattr(self, "focused_subwindow_index", 0)
        vsm = self.subwindow_managers.get(focused, {}).get("view_state_manager")
        use_rescaled = bool(getattr(vsm, "use_rescaled_values", True))
        pixel_array = self._mpr_controller.get_detached_mpr_thumbnail_pixels(
            use_rescaled
        )
        if pixel_array is None:
            return
        payload = getattr(self._mpr_controller, "_detached_mpr_payload", None)
        study_uid = ""
        series_uid = ""
        if isinstance(payload, dict):
            study_uid = str(payload.get("current_study_uid", "") or "")
            series_uid = str(payload.get("current_series_uid", "") or "")
        wc: Optional[float] = None
        ww: Optional[float] = None
        wl_controls = getattr(self, "window_level_controls", None)
        if wl_controls is not None:
            try:
                wc_val = float(wl_controls.window_center)
                ww_val = float(wl_controls.window_width)
                if ww_val > 0:
                    wc, ww = wc_val, ww_val
            except (AttributeError, TypeError, ValueError):
                pass
        self.series_navigator.set_mpr_thumbnail(
            -1,
            pixel_array,
            study_uid,
            series_uid,
            wc,
            ww,
        )

    def _on_mpr_detached(self, former_idx: int) -> None:
        """MPR was detached from a pane; refresh navigator thumbnails."""
        self._clear_mpr_navigator_thumbnail(former_idx)
        self._update_floating_mpr_navigator_thumbnail()

    def _on_mpr_thumbnail_clicked(self, subwindow_index: int) -> None:
        """
        Focus the subwindow that hosts the MPR view when its thumbnail is clicked.

        Args:
            subwindow_index: Zero-based index of the MPR subwindow, or -1 if detached.
        """
        if subwindow_index < 0:
            return
        try:
            subwindow = self.multi_window_layout.get_subwindow(subwindow_index)
            if subwindow is not None and not subwindow.is_focused:
                subwindow.set_focused(True)
        except Exception as exc:
            print(f"[DICOMViewerApp] _on_mpr_thumbnail_clicked: {exc}")

    def _on_mpr_assign_requested(
        self, source_subwindow_index: int, target_subwindow_index: int
    ) -> None:
        """
        Handle MPR thumbnail drop onto a subwindow: relocate active MPR or
        attach a detached session (source index -1).
        """
        if source_subwindow_index < 0:
            self._mpr_controller.attach_floating_mpr(target_subwindow_index)
            return
        self._mpr_controller.relocate_mpr_subwindow(
            source_subwindow_index, target_subwindow_index
        )

    def _on_mpr_clear_from_navigator_thumbnail(self, subwindow_index: int) -> None:
        """Clear MPR from the navigator context menu (attached or detached)."""
        if subwindow_index < 0:
            self._mpr_controller.clear_detached_mpr()
            if hasattr(self, "series_navigator"):
                self.series_navigator.clear_mpr_thumbnail(-1)
            return
        if self._mpr_controller.is_mpr(subwindow_index):
            self._mpr_controller.clear_mpr(subwindow_index)

    def _sync_intensity_projection_widget_from_mpr_data(self, data: Dict[str, Any]) -> None:
        """Push ``mpr_combine_*`` from *data* to the right-pane Combine Slices widget."""
        self._projection_app_facade.sync_intensity_projection_widget_from_mpr_data(data)

    def _get_subwindow_mpr_output_pixel_spacing(self, idx: int):
        """Return the (row, col) pixel spacing mm for the MPR output grid for subwindow *idx*."""
        try:
            data = self.subwindow_data.get(idx, {})
            if not data.get("is_mpr"):
                return None
            result = data.get("mpr_result")
            if result is None:
                return None
            return getattr(result, "output_spacing_mm", None)
        except Exception:
            return None

    def _sync_navigation_slider_for_subwindow(self, idx: int) -> None:
        """
        Align one pane's edge-reveal slice slider with its current content.

        Hides the overlay and resets internal range to 1/1 when the pane has no
        navigable stack (empty, single-slice native series, or invalid UIDs).
        For MPR, uses ``mpr_result.n_slices`` and ``mpr_slice_index``. For native
        2-D, uses ``current_studies[study][series]`` length and ``current_slice_index``.
        """
        if idx < 0:
            return
        subwindow = self.multi_window_layout.get_subwindow(idx)
        if subwindow is None or subwindow.image_viewer is None:
            return
        viewer = subwindow.image_viewer
        data = self.subwindow_data.get(idx, {})

        if hasattr(self, "_mpr_controller") and self._mpr_controller.is_mpr(idx):
            result = data.get("mpr_result")
            n_slices = int(getattr(result, "n_slices", 0) or 0) if result is not None else 0
            if n_slices > 1:
                si = int(data.get("mpr_slice_index", 0))
                viewer.set_navigation_slider_state(
                    enabled=True,
                    minimum=1,
                    maximum=n_slices,
                    value=si + 1,
                    mode_label="Slice",
                )
            else:
                viewer.set_navigation_slider_state(
                    enabled=False, minimum=1, maximum=1, value=1
                )
            return

        study_uid = data.get("current_study_uid", "")
        series_uid = data.get("current_series_uid", "")
        if not series_uid or not study_uid:
            viewer.set_navigation_slider_state(
                enabled=False, minimum=1, maximum=1, value=1
            )
            return

        datasets = self.current_studies.get(study_uid, {}).get(series_uid, [])
        total = len(datasets)
        current_idx = int(data.get("current_slice_index", 0))
        if total > 1:
            viewer.set_navigation_slider_state(
                enabled=True,
                minimum=1,
                maximum=total,
                value=current_idx + 1,
                mode_label="Slice",
            )
        else:
            viewer.set_navigation_slider_state(
                enabled=False, minimum=1, maximum=1, value=1
            )

    def _get_subwindow_study_uid(self, idx: int) -> str:
        """Get current study UID for a subwindow. Delegates to subwindow lifecycle controller."""
        return self._subwindow_lifecycle_controller.get_subwindow_study_uid(idx)

    def _get_subwindow_series_uid(self, idx: int) -> str:
        """Get current series UID for a subwindow. Delegates to subwindow lifecycle controller."""
        return self._subwindow_lifecycle_controller.get_subwindow_series_uid(idx)

    def get_focused_subwindow_index(self) -> int:
        """Return the currently focused subwindow index (0-3). Delegates to subwindow lifecycle controller."""
        return self._subwindow_lifecycle_controller.get_focused_subwindow_index()

    def get_histogram_callbacks_for_subwindow(self, idx: int) -> Dict[str, Any]:
        """Return callbacks for the histogram dialog for subwindow idx. Delegates to subwindow lifecycle controller."""
        return self._subwindow_lifecycle_controller.get_histogram_callbacks_for_subwindow(idx)
    
    def _update_focused_subwindow_references(self) -> None:
        """Update legacy references to point to focused subwindow's managers and data. Delegates to subwindow lifecycle controller."""
        self._subwindow_lifecycle_controller.update_focused_subwindow_references()
        # Keep ROI measurement controller in sync with the active subwindow's managers.
        if hasattr(self, 'roi_measurement_controller') and self.roi_measurement_controller:
            self.roi_measurement_controller.update_focused_managers(
                getattr(self, 'roi_manager', None),
                getattr(self, 'measurement_tool', None),
            )

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
        """Update right panel controls to reflect focused subwindow's state. Delegates to subwindow lifecycle controller."""
        self._subwindow_lifecycle_controller.update_right_panel_for_focused_subwindow()

    def _update_left_panel_for_focused_subwindow(self) -> None:
        """Update left panel controls (metadata, cine) to reflect focused subwindow's state. Delegates to subwindow lifecycle controller."""
        self._subwindow_lifecycle_controller.update_left_panel_for_focused_subwindow()

    def _display_rois_for_subwindow(self, idx: int, preserve_view: bool = False) -> None:
        """Display ROIs for a specific subwindow. Delegates to subwindow lifecycle controller."""
        self._subwindow_lifecycle_controller.display_rois_for_subwindow(idx, preserve_view)
    
    def _redisplay_subwindow_slice(self, idx: int, preserve_view: bool = False) -> None:
        """Redisplay slice for a specific subwindow. Delegates to subwindow lifecycle controller."""
        self._subwindow_lifecycle_controller.redisplay_subwindow_slice(idx, preserve_view)
        self._slice_location_line_coordinator.refresh_all()
    
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

        if self.image_viewer is None:
            raise RuntimeError(
                "image_viewer must be set before initializing handlers that require a focused viewer."
            )
        focused_image_viewer = self.image_viewer

        # Initialize file/series loading coordinator (owns load-first-slice and open entry points)
        self._file_series_coordinator = FileSeriesLoadingCoordinator(self)
        # Initialize FileOperationsHandler (shared, not per-subwindow)
        self.file_operations_handler = FileOperationsHandler(
            self.dicom_loader,
            self.dicom_organizer,
            self.file_dialog,
            self.config_manager,
            self.main_window,
            clear_data_callback=self._clear_data,
            load_first_slice_callback=self._file_series_coordinator.handle_additive_load,
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
            get_histogram_callbacks_for_subwindow=self.get_histogram_callbacks_for_subwindow,
            get_focused_subwindow_index=self.get_focused_subwindow_index,
            undo_redo_manager=self.undo_redo_manager,
            ui_refresh_callback=self._refresh_tag_ui,
            tag_export_union_host=self,
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
        
        # Privacy controller (propagates privacy mode and refreshes overlays)
        self._privacy_controller = PrivacyController(
            config_manager=self.config_manager,
            metadata_controller=self.metadata_controller,
            overlay_manager=self.overlay_manager,
            dialog_coordinator=self.dialog_coordinator,
            get_subwindow_managers=lambda: self.subwindow_managers,
            get_all_subwindows=self.multi_window_layout.get_all_subwindows,
            get_focused_subwindow_index=self.get_focused_subwindow_index,
            get_subwindow_data=lambda: self.subwindow_data,
        )
        
        # Customization and tag-preset export/import (callbacks run after import; need app state)
        self._customization_handlers = CustomizationHandlers(
            self.config_manager,
            self.main_window,
            after_import_customizations=self._apply_imported_customizations,
        )
        
        # Initialize MouseModeHandler
        self.mouse_mode_handler = MouseModeHandler(
            focused_image_viewer,
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

        self.cine_app_facade = CineAppFacade(self)
        
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
            focused_image_viewer,
            set_mouse_mode=self.mouse_mode_handler.set_mouse_mode,
            delete_all_rois_callback=self.roi_coordinator.delete_all_rois_current_slice,
            clear_measurements_callback=self.measurement_coordinator.handle_clear_measurements,
            toggle_overlay_callback=self.overlay_coordinator.handle_toggle_overlay,
            get_selected_roi=lambda: self.roi_manager.get_selected_roi(),
            delete_roi_callback=self._keyboard_delete_roi,
            delete_measurement_callback=self.measurement_coordinator.handle_measurement_delete_requested,
            update_roi_list_callback=self._update_roi_list,
            clear_roi_statistics_callback=self.roi_statistics_panel.clear_statistics,
            reset_view_callback=self.view_state_manager.reset_view,
            toggle_series_navigator_callback=self.main_window.toggle_series_navigator,
            invert_image_callback=focused_image_viewer.invert_image,
            open_histogram_callback=self.dialog_coordinator.open_histogram,
            reset_all_views_callback=self._on_reset_all_views,
            toggle_privacy_view_callback=lambda enabled: self._on_privacy_view_toggled(enabled),
            get_privacy_view_state_callback=lambda: self.privacy_view_enabled,
            delete_text_annotation_callback=None,  # Will be set when coordinators are available
            delete_arrow_annotation_callback=None,  # Will be set when coordinators are available
            change_layout_callback=self.main_window.set_layout_mode,
            is_focus_ok_for_reset_view=lambda: is_widget_allowed_for_layout_shortcuts(
                self, QApplication.focusWidget()
            ),
            open_quick_window_level_callback=self._open_quick_window_level,
        )

    def _keyboard_delete_roi(self, roi: object) -> None:
        """Delete ROI invoked from keyboard; supports wrapper objects with .item or bare ROIItem."""
        item = getattr(roi, "item", None)
        if item is not None:
            self.roi_coordinator.handle_roi_delete_requested(item)
            return
        if roi is not None and self.image_viewer is not None:
            self.roi_manager.delete_roi(cast(ROIItem, roi), self.image_viewer.scene)

    def _flatten_studies_for_tag_export_union(self, studies: StudiesNestedDict) -> List[Dataset]:
        """Stable study → series → instance order for tag-export union."""
        out: List[Dataset] = []
        for _, series_dict in studies.items():
            for _, datasets in series_dict.items():
                out.extend(datasets)
        return out

    def get_tag_export_union_snapshot(self) -> Tuple[int, Optional[Dict[str, Any]]]:
        """Current load generation and merged tag map, if background union has finished."""
        return (self._tag_export_union_generation, self._tag_export_union_merged)

    def _schedule_tag_export_union_rebuild(self) -> None:
        """Rebuild in-memory tag union off the GUI thread (no disk cache)."""
        prev = self._tag_export_union_worker
        if prev is not None and prev.isRunning():
            prev.requestInterruption()
        self._tag_export_union_generation += 1
        gen = self._tag_export_union_generation
        self._tag_export_union_merged = None
        if not self.current_studies:
            self.tag_export_union_ready.emit(gen, {})
            return
        datasets = self._flatten_studies_for_tag_export_union(self.current_studies)
        worker = TagExportUnionWorker(
            gen,
            datasets,
            include_private=True,
            supplement_standard_tags=True,
        )
        worker.finished_ok.connect(self._on_tag_export_union_worker_finished)
        worker.failed.connect(self._on_tag_export_union_worker_failed)
        self._tag_export_union_worker = worker
        worker.start()

    def _on_tag_export_union_worker_finished(self, gen: int, merged: object) -> None:
        if gen != self._tag_export_union_generation:
            return
        self._tag_export_union_merged = cast(Dict[str, Any], merged)
        self.tag_export_union_ready.emit(gen, self._tag_export_union_merged)

    def _on_tag_export_union_worker_failed(self, gen: int, _message: str) -> None:
        if gen != self._tag_export_union_generation:
            return
        self._tag_export_union_merged = None
        self.tag_export_union_ready.emit(gen, {})

    def _clear_data(self) -> None:
        """Clear all ROIs, measurements, and related data for all subwindows."""
        # Clear slice_display_manager state for all subwindows so no stale cached state
        # is used when opening new folder/files (e.g. by refresh_overlays on privacy toggle).
        for idx in self.subwindow_managers:
            managers = self.subwindow_managers[idx]
            slice_display_manager = managers.get("slice_display_manager")
            if slice_display_manager and hasattr(slice_display_manager, "clear_display_state"):
                slice_display_manager.clear_display_state()
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
        # Clear MPR from any subwindow before clearing overlays and data.
        # This removes the MPR banner and restores or clears the view.
        if hasattr(self, "_mpr_controller"):
            for idx in list(self.subwindow_data.keys()):
                if self.subwindow_data.get(idx, {}).get("is_mpr"):
                    self._mpr_controller.clear_mpr(idx)

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
        
        # Reset view state and clear display state for all subwindows
        for idx in self.subwindow_managers:
            managers = self.subwindow_managers[idx]
            view_state_manager = managers.get('view_state_manager')
            slice_display_manager = managers.get('slice_display_manager')
            if view_state_manager:
                view_state_manager.reset_window_level_state()
                view_state_manager.reset_series_tracking()
            if slice_display_manager and hasattr(slice_display_manager, "clear_display_state"):
                slice_display_manager.clear_display_state()
        
        # Update shared widget state
        self.intensity_projection_controls_widget.set_enabled(False)
        self.intensity_projection_controls_widget.set_projection_type("aip")
        self.intensity_projection_controls_widget.set_slice_count(4)
        
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

        # Reset organizer state (loaded_file_paths, series_source_dirs, disambiguation_counters, etc.)
        self.dicom_organizer.clear()
        # Clear all PS/KO from annotation manager (studies gone)
        self.annotation_manager.clear_all_ps_ko()

        # Clear current dataset references (legacy, points to focused subwindow)
        self.current_dataset = None
        self.current_studies = {}
        self.current_study_uid = ""
        self.current_series_uid = ""
        self.current_slice_index = 0

        self._schedule_tag_export_union_rebuild()
        
        # Dissolve slice sync groups (no linked groups when no files loaded)
        self.config_manager.set_slice_sync_groups([])
        self._slice_sync_coordinator.set_groups([])
        self._slice_sync_coordinator.invalidate_cache()
        self._slice_location_line_coordinator.refresh_all()

        # Reset slice navigator (shared)
        self.slice_navigator.set_total_slices(0)
        self.slice_navigator.set_current_slice(0)
        
        # Clear series navigator (shared) and dot indicators
        self.series_navigator.update_series_list({}, "", "")
        self._refresh_series_navigator_state()
        self.series_navigator.set_subwindow_assignments({})
        
        # Clear tag edit history
        if hasattr(self, 'metadata_controller') and self.metadata_controller:
            self.metadata_controller.clear_tag_history()
        
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

        # Reassign views A–D to default windows 1–4 (slot order [0,1,2,3])
        self.multi_window_layout.reset_slot_to_view_default()
        self._refresh_window_slot_map_widgets()

    def _on_app_about_to_quit(self) -> None:
        """Reset view–slot mapping and dissolve slice sync groups when the application is exiting."""
        self.multi_window_layout.reset_slot_to_view_default()
        self.config_manager.set_slice_sync_groups([])
        self._slice_sync_coordinator.set_groups([])
        self._slice_sync_coordinator.invalidate_cache()

    # -------------------------------------------------------------------------
    # Per-series / per-study close helpers (used by navigator right-click menu)
    # -------------------------------------------------------------------------

    def _get_subwindow_assignments(self) -> Dict[int, Tuple[str, str, int]]:
        """
        Build a mapping of grid **slot** index → (study_uid, series_key, slice_index) for each
        slot that has a loaded series.

        Slot indices (0–3) match the colored window dots in SeriesNavigator and the 2×2 grid
        positions. ``multi_window_layout.get_slot_to_view()[s]`` is the **view** index shown
        in slot ``s``; dataset state for that view lives in ``subwindow_data[view_idx]``.
        After **Swap Windows**, slot→view changes while ``subwindow_data`` stays keyed by view,
        so assignments must be derived from ``slot_to_view`` (not raw ``subwindow_data`` keys).

        Returns:
            Dict mapping slot index (0–3) to
            (current_study_uid, current_series_uid, current_slice_index).
        """
        slot_to_view = self.multi_window_layout.get_slot_to_view()
        assignments: Dict[int, Tuple[str, str, int]] = {}
        for slot_idx, view_idx in enumerate(slot_to_view):
            if slot_idx >= 4:
                break
            if not isinstance(view_idx, int) or view_idx < 0 or view_idx > 3:
                continue
            data = self.subwindow_data.get(view_idx, {})
            if data.get("current_dataset") is None:
                continue
            assignments[slot_idx] = (
                data["current_study_uid"],
                data["current_series_uid"],
                data.get("current_slice_index", 0),
            )
        return assignments

    def _reset_fusion_handler_for_subwindow(self, idx: int) -> None:
        """
        Disable fusion and clear caches for one subwindow's FusionHandler only.

        Does not change the shared fusion controls widget (that remains for
        ``_reset_fusion_for_all_subwindows`` on full close/open).

        Args:
            idx: Zero-based subwindow index (0–3).
        """
        if idx not in self.subwindow_managers:
            return
        managers = self.subwindow_managers[idx]
        fusion_handler = managers.get("fusion_handler")
        if not fusion_handler:
            return
        fusion_handler.fusion_enabled = False
        fusion_handler._slice_location_cache.clear()
        fusion_handler._resampling_decision_cache = None
        fusion_handler._resampling_decision_cache_key = None
        fusion_handler.clear_alignment_cache()
        if hasattr(fusion_handler, "image_resampler") and fusion_handler.image_resampler:
            fusion_handler.image_resampler.clear_cache()

    def _clear_subwindow(self, idx: int) -> None:
        """
        Clear scene, overlays, ROIs, measurements, and annotations for a single
        subwindow by index.  Resets subwindow_data[idx] to the empty template.

        Does NOT touch focused-subwindow app-level attributes (current_dataset, etc.)
        — callers are responsible for those when the closed subwindow was focused.

        Args:
            idx: Zero-based subwindow index (0–3).
        """
        self._reset_fusion_handler_for_subwindow(idx)

        subwindow = self.multi_window_layout.get_subwindow(idx)
        if subwindow and subwindow.image_viewer:
            scene = subwindow.image_viewer.scene

            # Clear ROIs, measurements, and annotations BEFORE scene.clear().
            # scene.clear() destroys all C++ graphics objects; the managers must
            # remove their items first while those objects are still alive.
            if idx in self.subwindow_managers:
                managers = self.subwindow_managers[idx]

                roi_manager = managers.get('roi_manager')
                measurement_tool = managers.get('measurement_tool')
                text_annotation_tool = managers.get('text_annotation_tool')
                arrow_annotation_tool = managers.get('arrow_annotation_tool')
                if roi_manager:
                    roi_manager.clear_all_rois(scene)
                if measurement_tool:
                    measurement_tool.clear_measurements(scene)
                if text_annotation_tool:
                    text_annotation_tool.clear_annotations(scene)
                if arrow_annotation_tool:
                    arrow_annotation_tool.clear_arrows(scene)

                overlay_manager = managers.get('overlay_manager')
                if overlay_manager:
                    overlay_manager.clear_overlay_items(scene)

                # Clear slice display state
                slice_display_manager = managers.get('slice_display_manager')
                if slice_display_manager and hasattr(slice_display_manager, 'clear_display_state'):
                    slice_display_manager.clear_display_state()

            # Now safe to call scene.clear() — all managed items have been removed
            scene.clear()
            subwindow.image_viewer.image_item = None
            subwindow.image_viewer.viewport().update()

        # Reset subwindow_data to the empty template
        self.subwindow_data[idx] = {
            'current_dataset': None,
            'current_slice_index': 0,
            'current_series_uid': '',
            'current_study_uid': '',
            'current_datasets': [],
        }
        # Hide edge-reveal slider and reset to slice 1 / single-step range
        self._sync_navigation_slider_for_subwindow(idx)
        self._refresh_window_slot_map_widgets()

    def _reset_focused_subwindow_state_after_close(self) -> None:
        """
        Update the focused-subwindow app-level attributes after its content was
        cleared by _close_series or _close_study.

        Resets current_dataset/study/series/slice, clears the slice navigator,
        metadata panel, cine player, and re-wires focused-subwindow signals.
        """
        self.current_dataset = None
        self.current_study_uid = ''
        self.current_series_uid = ''
        self.current_slice_index = 0
        self.current_datasets = []

        self.slice_navigator.set_total_slices(0)
        self.slice_navigator.set_current_slice(0)

        self.metadata_panel.set_dataset(None)

        self.cine_app_facade.update_cine_player_context()

        self._disconnect_focused_subwindow_signals()
        self._connect_focused_subwindow_signals()

        # Update shared ROI panels (focused subwindow now empty)
        self.roi_list_panel.update_roi_list('', '', 0)
        self.roi_statistics_panel.clear_statistics()

    def _on_clear_subwindow_content_requested(self, idx: int) -> None:
        """
        Clear one image pane from the context menu; loaded studies/series are unchanged.

        Args:
            idx: Subwindow index (0–3) for the viewer that requested the action.
        """
        data = self.subwindow_data.get(idx, {})
        if data.get("current_dataset") is None and not data.get("is_mpr"):
            return
        if idx == self.focused_subwindow_index and getattr(self, "cine_player", None):
            self.cine_player.stop_playback()
        # Clear Window: detach MPR (keeps session for reassignment) instead of
        # full teardown + blanking the pane.
        if hasattr(self, "_mpr_controller") and data.get("is_mpr"):
            self._mpr_controller.detach_mpr_from_subwindow(idx)
            if idx == self.focused_subwindow_index:
                self._update_focused_subwindow_references()
            self.series_navigator.set_subwindow_assignments(
                self._get_subwindow_assignments()
            )
            return
        self._clear_subwindow(idx)
        if idx == self.focused_subwindow_index:
            self._reset_focused_subwindow_state_after_close()
        self.series_navigator.set_subwindow_assignments(self._get_subwindow_assignments())

    def _close_series(self, study_uid: str, series_key: str) -> None:
        """
        Close a single series: free pixel caches, remove it from the organizer,
        clear any subwindows that were showing it, and refresh the navigator.

        Focus stays on the now-empty subwindow if the closed series was focused.

        Args:
            study_uid:  StudyInstanceUID of the series to close.
            series_key: Composite series key (SeriesInstanceUID + SeriesNumber).
        """
        # Guard: series must exist
        series_datasets = self.current_studies.get(study_uid, {}).get(series_key, [])
        if not series_datasets:
            return

        # 1. Identify affected subwindows
        affected_indices = [
            idx for idx, data in self.subwindow_data.items()
            if data.get('current_study_uid') == study_uid
            and data.get('current_series_uid') == series_key
        ]

        # 2. Free pixel caches for datasets in this series
        for ds in series_datasets:
            if hasattr(ds, '_cached_pixel_array'):
                delattr(ds, '_cached_pixel_array')

        # 3. Remove from organizer; remove PS/KO if the study becomes empty
        self.dicom_organizer.remove_series(study_uid, series_key)
        if study_uid not in self.dicom_organizer.studies:
            self.annotation_manager.remove_study_annotations(study_uid)

        # 4. Sync current_studies
        self.current_studies = self.dicom_organizer.studies

        self._schedule_tag_export_union_rebuild()

        # 5. Clear each affected subwindow
        for idx in affected_indices:
            self._clear_subwindow(idx)

        # 6. Handle focused subwindow
        if self.focused_subwindow_index in affected_indices:
            self._reset_focused_subwindow_state_after_close()

        # 7. Update series navigator and dot indicators
        self.series_navigator.update_series_list(
            self.current_studies,
            self.current_study_uid,
            self.current_series_uid,
        )
        self._refresh_series_navigator_state()
        self.series_navigator.set_subwindow_assignments(self._get_subwindow_assignments())

        # 8. Invalidate slice-sync geometry cache for the closed series.
        self._slice_sync_coordinator.invalidate_cache(study_uid, series_key)

    def _close_study(self, study_uid: str) -> None:
        """
        Close an entire study: free pixel caches for all its series, remove it
        from the organizer, clear all affected subwindows, and refresh the
        navigator in one pass (no per-series navigator refreshes).

        Focus stays on the now-empty subwindow if any focused series was closed.

        Args:
            study_uid: StudyInstanceUID of the study to close.
        """
        study_series = self.current_studies.get(study_uid, {})
        if not study_series:
            return

        # 1. Collect all affected subwindow indices (across all series in this study)
        affected_indices = [
            idx for idx, data in self.subwindow_data.items()
            if data.get('current_study_uid') == study_uid
        ]

        # 2. Free pixel caches for all datasets in all series of this study
        for datasets in study_series.values():
            for ds in datasets:
                if hasattr(ds, '_cached_pixel_array'):
                    delattr(ds, '_cached_pixel_array')

        # 3. Remove study from organizer and annotation manager
        self.dicom_organizer.remove_study(study_uid)
        self.annotation_manager.remove_study_annotations(study_uid)

        # 4. Sync current_studies
        self.current_studies = self.dicom_organizer.studies

        self._schedule_tag_export_union_rebuild()

        # 5. Clear all affected subwindows
        for idx in affected_indices:
            self._clear_subwindow(idx)

        # 6. Handle focused subwindow
        if self.focused_subwindow_index in affected_indices:
            self._reset_focused_subwindow_state_after_close()

        # 7. Update series navigator and dot indicators (single pass — no intermediate refreshes)
        self.series_navigator.update_series_list(
            self.current_studies,
            self.current_study_uid,
            self.current_series_uid,
        )
        self._refresh_series_navigator_state()
        self.series_navigator.set_subwindow_assignments(self._get_subwindow_assignments())

        # 8. Invalidate all cached geometry for this study.
        self._slice_sync_coordinator.invalidate_cache(study_uid)

    def _reset_fusion_for_all_subwindows(self) -> None:
        """
        Disable fusion and clear status for all subwindows.

        This is called when files are closed or when new files are opened
        to ensure fusion is disabled and status messages are cleared.
        """
        for idx in self.subwindow_managers:
            self._reset_fusion_handler_for_subwindow(idx)

        # Disable fusion in UI widget and clear status messages
        self.fusion_controls_widget.set_fusion_enabled(False)
        self.fusion_controls_widget.clear_status()
    
    def _handle_load_first_slice(self, studies: StudiesNestedDict) -> None:
        """
        Handle loading first slice after file operations.

        Delegates to the file/series loading coordinator. Clears edited tags
        for the previous dataset and updates display/state via the coordinator.
        """
        self._file_series_coordinator.handle_load_first_slice(studies)

    def _get_rescale_params(self) -> tuple[Optional[float], Optional[float], Optional[str], bool]:
        """Get rescale parameters for ROI operations (focused subwindow's view state)."""
        return (
            self.view_state_manager.rescale_slope,
            self.view_state_manager.rescale_intercept,
            self.view_state_manager.rescale_type,
            self.view_state_manager.use_rescaled_values
        )

    def _get_subwindow_rescale_params(
        self, idx: int
    ) -> tuple[Optional[float], Optional[float], Optional[str], bool]:
        """
        Rescale parameters for the given subwindow (ROI / statistics must match
        that pane's ``ViewStateManager``, not the legacy focused-window alias).
        """
        managers = self.subwindow_managers.get(idx, {})
        vsm = managers.get("view_state_manager")
        if vsm is None:
            return None, None, None, True
        return (
            getattr(vsm, "rescale_slope", None),
            getattr(vsm, "rescale_intercept", None),
            getattr(vsm, "rescale_type", None),
            bool(getattr(vsm, "use_rescaled_values", True)),
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
        # Refresh metadata panel via controller
        search_text = self.metadata_panel.search_edit.text()
        self.metadata_controller.refresh_panel_tags(search_text)
        
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
        success = self.metadata_controller.undo_tag_edit(self.current_dataset)
        if success:
            # Refresh metadata panel via controller
            self.metadata_controller.refresh_panel_tags()
            # Refresh tag viewer dialog if open
            if self.dialog_coordinator.tag_viewer_dialog:
                search_text = self.dialog_coordinator.tag_viewer_dialog.search_edit.text()
                if self.dialog_coordinator.tag_viewer_dialog.parser is not None:
                    self.dialog_coordinator.tag_viewer_dialog.parser._tag_cache.clear()
                self.dialog_coordinator.tag_viewer_dialog._populate_tags(search_text)
            # Update undo/redo state
            self._update_undo_redo_state()
    
    def _redo_tag_edit(self) -> None:
        """Handle redo tag edit request."""
        success = self.metadata_controller.redo_tag_edit(self.current_dataset)
        if success:
            # Refresh metadata panel via controller
            self.metadata_controller.refresh_panel_tags()
            # Refresh tag viewer dialog if open
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
        """Assemble main-window panel layout. Implemented in gui.main_window_layout_helper."""
        setup_main_window_content(
            self.main_window,
            self.multi_window_layout,
            self.cine_controls_widget,
            self.metadata_panel,
            self.window_level_controls,
            self.zoom_display_widget,
            self.roi_list_panel,
            self.roi_statistics_panel,
            self.intensity_projection_controls_widget,
            self.fusion_controls_widget,
            self.series_navigator,
            get_slot_to_view=self.multi_window_layout.get_slot_to_view,
            get_layout_mode=self.multi_window_layout.get_layout_mode,
            get_focused_view_index=self.get_focused_subwindow_index,
            get_thumbnail_for_view=self._get_thumbnail_for_view,
        )

    def _connect_signals(self) -> None:
        """Connect all application-level Qt signals. Implemented in core.app_signal_wiring."""
        wire_all_signals(self)

    def _on_focused_subwindow_changed(self, subwindow: SubWindowContainer) -> None:
        """Handle focused subwindow change. Delegates to subwindow lifecycle controller."""
        self._subwindow_lifecycle_controller.on_focused_subwindow_changed(subwindow)
        # When "Show Only For Focused Window" is on, refresh slice location lines so they track focus.
        if self.config_manager.get_slice_location_lines_focused_only():
            self._slice_location_line_coordinator.refresh_all()
        # Refresh window-slot thumbnail(s) so focus outline updates.
        self._refresh_window_slot_map_widgets()
    
    def _update_series_navigator_highlighting(self) -> None:
        """Update series navigator highlighting based on focused subwindow's series."""
        # Get focused subwindow's series and study UID for highlighting
        focused_idx = self.focused_subwindow_index
        if focused_idx in self.subwindow_data:
            data = self.subwindow_data[focused_idx]
            focused_series_uid = data.get('current_series_uid', '')
            focused_study_uid = data.get('current_study_uid', '')
            focused_slice_index = data.get('current_slice_index', 0)
            if focused_series_uid and focused_study_uid:
                self.series_navigator.set_current_position(
                    focused_series_uid,
                    focused_study_uid,
                    focused_slice_index,
                )
            elif focused_series_uid:
                self.series_navigator.set_current_position(
                    focused_series_uid,
                    slice_index=focused_slice_index,
                )
            else:
                self.series_navigator.set_current_position('', '', 0)
        self._refresh_series_navigator_state()

    def _refresh_series_navigator_state(self) -> None:
        """Push organizer-backed multiframe state and action enablement into the navigator UI."""
        self.series_navigator.set_multiframe_info_map(self.dicom_organizer.series_multiframe_info)
        show_instances_separately = self.config_manager.get_show_instances_separately()
        self.series_navigator.set_show_instances_separately(show_instances_separately)
        self.main_window.set_show_instances_separately_checked(show_instances_separately)

        multiframe_info = None
        if self.current_study_uid and self.current_series_uid:
            multiframe_info = self.dicom_organizer.get_series_multiframe_info(
                self.current_study_uid,
                self.current_series_uid,
            )

        can_expand_instances = bool(
            multiframe_info is not None
            and multiframe_info.max_frame_count > 1
            and multiframe_info.instance_count > 1
        )
        self.main_window.set_show_instances_separately_enabled(
            can_expand_instances or show_instances_separately
        )
    
    def _on_layout_changed(self, layout_mode: str) -> None:
        """Handle layout mode change from multi-window layout. Delegates to subwindow lifecycle controller."""
        self._subwindow_lifecycle_controller.on_layout_changed(layout_mode)
        QTimer.singleShot(0, self._slice_location_line_coordinator.refresh_all)
        self._refresh_window_slot_map_widgets()
    
    def _on_main_window_layout_changed(self, layout_mode: str) -> None:
        """Handle layout mode change from main window menu. Delegates to subwindow lifecycle controller."""
        self._subwindow_lifecycle_controller.on_main_window_layout_changed(layout_mode)
        QTimer.singleShot(0, self._slice_location_line_coordinator.refresh_all)
    
    def _capture_subwindow_view_states(self) -> Dict[int, Dict[str, Any]]:
        """Capture view state for all subwindows before layout change. Delegates to subwindow lifecycle controller."""
        return self._subwindow_lifecycle_controller.capture_subwindow_view_states()
    
    def _restore_subwindow_views(self, view_states: Dict[int, Dict[str, Any]]) -> None:
        """Restore subwindow views after layout change. Delegates to subwindow lifecycle controller."""
        self._subwindow_lifecycle_controller.restore_subwindow_views(view_states)
    
    def _ensure_all_subwindows_have_managers(self) -> None:
        """Ensure all visible subwindows have managers. Delegates to subwindow lifecycle controller."""
        self._subwindow_lifecycle_controller.ensure_all_subwindows_have_managers()
    
    def _connect_all_subwindow_transform_signals(self) -> None:
        """Connect transform/zoom signals for all subwindows. Delegates to subwindow lifecycle controller."""
        self._subwindow_lifecycle_controller.connect_all_subwindow_transform_signals()
    
    def _connect_all_subwindow_context_menu_signals(self) -> None:
        """Connect context menu signals for all subwindows. Delegates to subwindow lifecycle controller."""
        self._subwindow_lifecycle_controller.connect_all_subwindow_context_menu_signals()
    
    def _on_layout_change_requested(self, layout_mode: str) -> None:
        """Handle layout change request from image viewer context menu. Delegates to subwindow lifecycle controller."""
        self._subwindow_lifecycle_controller.on_layout_change_requested(layout_mode)
    
    def _on_expand_to_1x1_requested(self) -> None:
        """Handle double-click: expand to 1x1 or, if already in 1x1, revert to last used layout (or 2x2)."""
        sender = self.sender()
        if not isinstance(sender, SubWindowContainer):
            return
        if self.multi_window_layout.get_layout_mode() == "1x1":
            # Already in 1x1: revert to last layout before 1x1 (or 2x2)
            self.multi_window_layout.set_layout(self.multi_window_layout.get_revert_layout())
        else:
            self.multi_window_layout.set_focused_subwindow(sender)
            self.multi_window_layout.set_layout("1x1")
    
    def _on_swap_view_requested(self, other_index: int) -> None:
        """Handle Swap with View X from context menu: swap slot positions in all layouts; focus stays unchanged."""
        sender = self.sender()
        if not isinstance(sender, ImageViewer) or sender.subwindow_index is None:
            return
        if other_index < 0 or other_index >= 4 or other_index == sender.subwindow_index:
            return
        self.multi_window_layout.swap_views(sender.subwindow_index, other_index)
        # Resize images in visible panes so any view that was last in a smaller
        # layout (e.g. 2x2) fits the current window.
        self._subwindow_lifecycle_controller.schedule_viewport_resized()
        if self.multi_window_layout.get_layout_mode() != "2x2":
            self.main_window.update_status("Slot order updated; switch to 2x2 to see positions.")
        # Navigator dots are keyed by grid slot; slot_to_view changed, so refresh assignments.
        self.series_navigator.set_subwindow_assignments(self._get_subwindow_assignments())
        self._refresh_window_slot_map_widgets()

    def _refresh_window_slot_map_widgets(self) -> None:
        """Refresh the embedded and popup window-slot map widgets, if present."""
        widget = getattr(self.main_window, "window_slot_map_widget", None)
        if widget is not None:
            try:
                widget.refresh()
            except Exception:
                pass
        popup_widget = getattr(self, "_window_slot_map_widget_popup", None)
        if popup_widget is not None:
            try:
                popup_widget.refresh()
            except Exception:
                pass

    def _on_window_slot_map_popup_requested(self) -> None:
        """Show or hide a small popup with the window-slot map near the cursor (toggle)."""
        base_widget = getattr(self.main_window, "window_slot_map_widget", None)
        if base_widget is None:
            return

        # If dialog already exists and is visible, treat this as a toggle and close it.
        if hasattr(self, "_window_slot_map_dialog") and self._window_slot_map_dialog is not None:
            dlg = self._window_slot_map_dialog
            if dlg.isVisible():
                dlg.close()
                return

        # Lazily create draggable popup dialog
        if not hasattr(self, "_window_slot_map_dialog") or self._window_slot_map_dialog is None:

            def on_position_changed(x: int, y: int) -> None:
                try:
                    self.config_manager.set_layout_map_popup_position(x, y)
                except Exception:
                    pass

            dlg = WindowSlotMapPopupDialog(
                self.main_window,
                boundary_widget=self.main_window,
                on_position_changed=on_position_changed,
            )
            self._window_slot_map_dialog = dlg
        else:
            dlg = self._window_slot_map_dialog

        widget = dlg.get_map_widget()
        if widget is None:
            return
        self._window_slot_map_widget_popup = widget

        # Configure callbacks to mirror the main thumbnail (including thumbnails)
        try:
            widget.set_callbacks(
                get_slot_to_view=self.multi_window_layout.get_slot_to_view,
                get_layout_mode=self.multi_window_layout.get_layout_mode,
                get_focused_view_index=self.get_focused_subwindow_index,
                get_thumbnail_for_view=self._get_thumbnail_for_view,
            )
        except Exception:
            pass

        widget.refresh()

        # Restore saved position if valid and within main window; otherwise place near cursor
        saved = self.config_manager.get_layout_map_popup_position()
        boundary = self.main_window.frameGeometry()
        if saved is not None:
            x, y = saved
            # Clamp so popup stays within main window
            w, h = dlg.width(), dlg.height()
            x = max(boundary.left(), min(x, boundary.right() - w))
            y = max(boundary.top(), min(y, boundary.bottom() - h))
            dlg.move(x, y)
        else:
            global_pos = QCursor.pos()
            dlg.move(global_pos + QPoint(16, 16))

        dlg.show()
        dlg.raise_()
    
    def _on_assign_series_requested(
        self, series_uid: str, slice_index: int, study_uid: str = ""
    ) -> None:
        """Handle series assignment request from subwindow; sender() identifies which subwindow."""
        sender = self.sender()
        if isinstance(sender, SubWindowContainer):
            target_study = study_uid if study_uid else None
            self._subwindow_lifecycle_controller.assign_series_to_subwindow(
                sender, series_uid, slice_index, target_study_uid=target_study
            )
    
    def _assign_series_to_subwindow(self, subwindow: SubWindowContainer, series_uid: str, slice_index: int) -> None:
        """Assign a series/slice to a specific subwindow. Delegates to subwindow lifecycle controller."""
        self._subwindow_lifecycle_controller.assign_series_to_subwindow(subwindow, series_uid, slice_index)
    
    def _disconnect_focused_subwindow_signals(self) -> None:
        """Disconnect signals from previously focused subwindow. Delegates to subwindow lifecycle controller."""
        self._subwindow_lifecycle_controller.disconnect_focused_subwindow_signals()

    def _connect_focused_subwindow_signals(self) -> None:
        """Connect signals for the currently focused subwindow. Delegates to subwindow lifecycle controller."""
        self._subwindow_lifecycle_controller.connect_focused_subwindow_signals()

    def _open_files(self) -> None:
        """Handle open files request. Delegates to file/series loading coordinator."""
        self._file_series_coordinator.open_files()

    def _open_folder(self) -> None:
        """Handle open folder request. Delegates to file/series loading coordinator."""
        self._file_series_coordinator.open_folder()

    def _open_recent_file(self, file_path: str) -> None:
        """
        Handle open recent file/folder request. Delegates to file/series loading coordinator.

        Args:
            file_path: Path to file or folder to open
        """
        self._file_series_coordinator.open_recent_file(file_path)

    def _open_files_from_paths(self, paths: list[str]) -> None:
        """
        Handle open files/folders from drag-and-drop. Delegates to file/series loading coordinator.

        Args:
            paths: List of file or folder paths to open
        """
        self._file_series_coordinator.open_files_from_paths(paths)
    
    def _on_series_navigation_requested(self, direction: int) -> None:
        """
        Handle series navigation request from image viewer (focused subwindow only).
        Delegates to file/series loading coordinator.
        """
        self._file_series_coordinator.on_series_navigation_requested(direction)

    def _build_flat_series_list(self, studies: StudiesNestedDict) -> List[Tuple[int, str, str, Dataset]]:
        """Build flat list of all series from all studies in navigator display order. Delegates to coordinator."""
        return self._file_series_coordinator.build_flat_series_list(studies)

    def _on_series_navigator_selected(self, series_uid: str) -> None:
        """Handle series selection from series navigator (assigns to focused subwindow). Delegates to coordinator."""
        self._file_series_coordinator.on_series_navigator_selected(series_uid)

    def _on_series_navigator_instance_selected(self, study_uid: str, series_uid: str, slice_index: int) -> None:
        """Handle per-instance thumbnail selection from series navigator. Delegates to coordinator."""
        self._file_series_coordinator.on_series_navigator_instance_selected(study_uid, series_uid, slice_index)

    def _on_assign_series_from_context_menu(self, series_uid: str) -> None:
        """Handle series assignment request from context menu. Delegates to coordinator."""
        self._file_series_coordinator.on_assign_series_from_context_menu(series_uid)
    
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

            # Keep series and instance-thumbnail state in sync with the focused slice.
            self._update_series_navigator_highlighting()
            self.series_navigator.set_subwindow_assignments(self._get_subwindow_assignments())
            
            # Store initial view state if this is the first image
            if self.view_state_manager.initial_zoom is None:
                # Wait a bit for view to settle, then store initial state
                QTimer.singleShot(100, self.view_state_manager.store_initial_view_state)
        except MemoryError as e:
            error_msg = f"Memory error displaying slice: {str(e)}"
            self.main_window.update_status(error_msg)
            # Show error dialog for memory errors
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
            print(f"Error displaying slice: {error_msg}")
            traceback.print_exc()
    
    def _redisplay_current_slice(self, preserve_view: bool = True) -> None:
        """
        Redisplay the current slice via SliceDisplayManager with optional preserve_view override.
        
        Args:
            preserve_view: True to preserve zoom/pan, False to refit
        """
        focused_idx = self.focused_subwindow_index
        if (
            hasattr(self, "_mpr_controller")
            and self._mpr_controller.is_mpr(focused_idx)
        ):
            data = self.subwindow_data.get(focused_idx, {})
            self._mpr_controller.display_mpr_slice(
                focused_idx, data.get("mpr_slice_index", 0)
            )
            return
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

        Slot for Qt signals; implementation lives in ``ProjectionAppFacade``.
        """
        self._projection_app_facade.on_projection_enabled_changed(enabled)

    def _on_projection_type_changed(self, projection_type: str) -> None:
        """Handle projection type change. Delegates to ``ProjectionAppFacade``."""
        self._projection_app_facade.on_projection_type_changed(projection_type)

    def _on_projection_slice_count_changed(self, count: int) -> None:
        """Handle projection slice count change. Delegates to ``ProjectionAppFacade``."""
        self._projection_app_facade.on_projection_slice_count_changed(count)
    
    def _open_settings(self) -> None:
        """Handle settings dialog request."""
        self.dialog_coordinator.open_settings()
    
    def _open_overlay_settings(self) -> None:
        """Handle Overlay Settings dialog request."""
        self.dialog_coordinator.open_overlay_settings()
    
    def _open_about_this_file(self) -> None:
        """Handle About This File dialog request."""
        dialog_action_handlers.open_about_this_file(self)
    
    def _get_file_path_for_dataset(self, dataset, study_uid: str, series_uid: str, slice_index: int) -> Optional[str]:
        """Get file path for a dataset. Delegates to file/series loading coordinator."""
        return self._file_series_coordinator.get_file_path_for_dataset(dataset, study_uid, series_uid, slice_index)

    def _on_show_file_from_series(self, study_uid: str, series_uid: str) -> None:
        """Handle 'Show file' request from series navigator thumbnail. Delegates to coordinator."""
        self._file_series_coordinator.on_show_file_from_series(study_uid, series_uid)

    def _on_about_this_file_from_series(self, study_uid: str, series_uid: str) -> None:
        """Handle 'About This File' request from series navigator thumbnail. Delegates to coordinator."""
        self._file_series_coordinator.on_about_this_file_from_series(study_uid, series_uid)

    def _get_current_slice_file_path(self, subwindow_idx: Optional[int] = None) -> Optional[str]:
        """Get file path for the currently displayed slice in a subwindow. Delegates to coordinator."""
        return self._file_series_coordinator.get_current_slice_file_path(subwindow_idx)

    def _update_about_this_file_dialog(self) -> None:
        """Update About This File dialog with current dataset and file path. Delegates to coordinator."""
        self._file_series_coordinator.update_about_this_file_dialog()

    def _on_privacy_view_toggled(self, enabled: bool) -> None:
        """
        Handle privacy view toggle.
        
        Propagates privacy mode state to all components that display tags
        via the privacy controller.
        
        Args:
            enabled: True if privacy view is enabled, False otherwise
        """
        self.privacy_view_enabled = enabled
        self._privacy_controller.apply_privacy(enabled)

    def _on_slice_sync_toggled(self, enabled: bool) -> None:
        """
        Handle the View → Slice Sync → Enable Slice Sync toggle.

        Persists the new state and pushes it to the coordinator.

        Args:
            enabled: True to enable anatomic slice sync, False to disable.
        """
        self.config_manager.set_slice_sync_enabled(enabled)
        self._slice_sync_coordinator.set_enabled(enabled)
        subwindows = self.multi_window_layout.get_all_subwindows()
        for subwindow in subwindows:
            if subwindow and subwindow.image_viewer:
                subwindow.image_viewer.set_slice_sync_enabled_state(enabled)

    def _open_slice_sync_dialog(self) -> None:
        """Open the Manage Sync Groups dialog."""
        dialog_action_handlers.open_slice_sync_dialog(self)

    def _on_slice_sync_groups_changed(self, groups) -> None:
        """
        Receive updated group assignments from the Slice Sync dialog.

        Persists to config, updates the coordinator, and invalidates the
        geometry cache so stale stacks aren't reused.

        Args:
            groups: List[List[int]] — new group assignments.
        """
        self.config_manager.set_slice_sync_groups(groups)
        self._slice_sync_coordinator.set_groups(groups)
        self._slice_sync_coordinator.invalidate_cache()
        self._slice_location_line_coordinator.refresh_all()

    def _on_slice_location_lines_toggled(self, visible: bool) -> None:
        """
        Handle View → Show Slice Location Lines → Enable/Disable toggle.

        Persists the setting and refreshes all subwindows.

        Args:
            visible: True to show slice location lines, False to hide.
        """
        self.config_manager.set_slice_location_lines_visible(visible)
        self._slice_location_line_coordinator.refresh_all()
        self.main_window.set_slice_location_lines_checked(visible)

    def _on_slice_location_lines_same_group_only_toggled(self, same_group_only: bool) -> None:
        """
        Handle View → Show Slice Location Lines → Only Show For Same Group toggle.

        Persists the setting and refreshes all subwindows.

        Args:
            same_group_only: True to show lines only from same linked group, False for all views.
        """
        self.config_manager.set_slice_location_lines_same_group_only(same_group_only)
        self._slice_location_line_coordinator.refresh_all()
        self.main_window.set_slice_location_lines_same_group_only_checked(same_group_only)

    def _on_slice_location_lines_focused_only_toggled(self, focused_only: bool) -> None:
        """
        Handle View → Show Slice Location Lines → Show Only For Focused Window toggle.

        Persists the setting and refreshes all subwindows.

        Args:
            focused_only: True to show only the focused subwindow's line, False for all views.
        """
        self.config_manager.set_slice_location_lines_focused_only(focused_only)
        self._slice_location_line_coordinator.refresh_all()
        self.main_window.set_slice_location_lines_focused_only_checked(focused_only)

    def _on_slice_location_lines_mode_toggled(self, mode: str) -> None:
        """
        Handle View → Show Slice Location Lines → Show Slab Boundaries toggle.

        Persists the new mode ("middle" or "begin_end") and refreshes all
        subwindows so the change is immediately visible.

        Args:
            mode: "middle" for a single centre-plane line, or "begin_end" for
                  two boundary lines at ±(SliceThickness/2).
        """
        self.config_manager.set_slice_location_line_mode(mode)
        self._slice_location_line_coordinator.refresh_all()
        self.main_window.set_slice_location_lines_slab_bounds_checked(mode)

    def _on_smooth_when_zoomed_toggled(self, enabled: bool) -> None:
        """
        Handle smooth-when-zoomed toggle from View menu or image viewer context menu.
        Persists setting and pushes state to all image viewers; syncs View menu check state.

        Args:
            enabled: True if smooth when zoomed is enabled, False otherwise
        """
        self.config_manager.set_smooth_image_when_zoomed(enabled)
        set_smooth_when_zoomed_all(self, enabled)
        self.main_window.set_smooth_when_zoomed_checked(enabled)

    # ------------------------------------------------------------------
    # Orientation handlers (View menu → focused viewer)
    # ------------------------------------------------------------------

    def _on_orientation_flip_h(self) -> None:
        """Toggle horizontal flip on the currently focused image viewer."""
        if self.image_viewer is not None:
            self.image_viewer.flip_h()

    def _on_orientation_flip_v(self) -> None:
        """Toggle vertical flip on the currently focused image viewer."""
        if self.image_viewer is not None:
            self.image_viewer.flip_v()

    def _on_orientation_rotate_cw(self) -> None:
        """Rotate the currently focused image viewer 90° clockwise."""
        if self.image_viewer is not None:
            self.image_viewer.rotate_cw()

    def _on_orientation_rotate_ccw(self) -> None:
        """Rotate the currently focused image viewer 90° counter-clockwise."""
        if self.image_viewer is not None:
            self.image_viewer.rotate_ccw()

    def _on_orientation_rotate_180(self) -> None:
        """Rotate the currently focused image viewer 180°."""
        if self.image_viewer is not None:
            self.image_viewer.rotate_180()

    def _on_orientation_reset(self) -> None:
        """Reset orientation of the currently focused image viewer to default."""
        if self.image_viewer is not None:
            self.image_viewer.reset_orientation()

    def _on_scale_markers_toggled(self, enabled: bool) -> None:
        """
        Handle scale markers toggle from View menu or image viewer context menu.

        Args:
            enabled: True to show scale markers, False to hide
        """
        self.config_manager.set_show_scale_markers(enabled)
        set_scale_markers_all(self, enabled)
        self.main_window.set_scale_markers_checked(enabled)

    def _on_direction_labels_toggled(self, enabled: bool) -> None:
        """
        Handle direction labels toggle from View menu or image viewer context menu.

        Args:
            enabled: True to show direction labels, False to hide
        """
        self.config_manager.set_show_direction_labels(enabled)
        set_direction_labels_all(self, enabled)
        self.main_window.set_direction_labels_checked(enabled)

    def _on_slice_slider_toggled(self, enabled: bool) -> None:
        """
        Handle the in-view slice/frame slider toggle from the View menu.

        Persists the setting and propagates the enabled state to every
        ImageViewer in the layout.

        Args:
            enabled: True to allow the slider to appear on hover, False to hide it.
        """
        self.config_manager.set_show_slice_slider(enabled)
        set_slice_slider_all(self, enabled)
        self.main_window.set_slice_slider_checked(enabled)

    def _on_scale_markers_color_changed(self, r: int, g: int, b: int) -> None:
        """Handle scale markers color change from the View menu."""
        self.config_manager.set_scale_markers_color(r, g, b)
        set_scale_markers_color_all(self, (r, g, b))

    def _on_direction_labels_color_changed(self, r: int, g: int, b: int) -> None:
        """Handle direction labels color change from the View menu."""
        self.config_manager.set_direction_labels_color(r, g, b)
        set_direction_labels_color_all(self, (r, g, b))

    def _on_show_instances_separately_toggled(self, enabled: bool) -> None:
        """Handle the View → Show Instances Separately toggle."""
        self.config_manager.set_show_instances_separately(enabled)
        self.series_navigator.set_show_instances_separately(enabled)
        self.series_navigator.update_series_list(
            self.current_studies,
            self.current_study_uid,
            self.current_series_uid,
        )
        self._refresh_series_navigator_state()
        self.series_navigator.set_subwindow_assignments(self._get_subwindow_assignments())

    def _refresh_overlays_after_privacy_change(self) -> None:
        """Refresh overlays after privacy view change for all subwindows that have loaded data. Delegates to privacy controller."""
        self._privacy_controller.refresh_overlays()

    def _open_tag_viewer(self) -> None:
        """Handle tag viewer dialog request."""
        self.dialog_coordinator.open_tag_viewer(self.current_dataset, privacy_mode=self.privacy_view_enabled)
    
    def _open_overlay_config(self) -> None:
        """Handle overlay configuration dialog request."""
        dialog_action_handlers.open_overlay_config(self)
    
    def _open_annotation_options(self) -> None:
        """Handle annotation options dialog request."""
        self.dialog_coordinator.open_annotation_options()

    def _open_quick_window_level(self) -> None:
        """Open Quick Window/Level dialog for the focused subwindow."""
        dialog_action_handlers.open_quick_window_level(self)
    
    def _open_quick_start_guide(self) -> None:
        """Handle Quick Start Guide dialog request."""
        self.dialog_coordinator.open_quick_start_guide()

    def _open_user_documentation_in_browser(self) -> None:
        """Open the user guide hub (Markdown on GitHub) in the system browser."""
        self.dialog_coordinator.open_user_documentation_in_browser()

    def _open_fusion_technical_doc(self) -> None:
        """Handle Fusion Technical Documentation dialog request."""
        self.dialog_coordinator.open_fusion_technical_doc()
    
    def _open_tag_export(self) -> None:
        """Handle Tag Export dialog request."""
        self.dialog_coordinator.open_tag_export()

    def _open_export_roi_statistics(self) -> None:
        """Handle Export ROI Statistics request (from menu or image viewer context menu)."""
        self._export_app_facade.open_export_roi_statistics()

    def _open_export(self) -> None:
        """Handle Export dialog request. Resolution options are in the dialog."""
        self._export_app_facade.open_export()

    def _open_export_screenshots(self) -> None:
        """Handle Export Screenshots dialog request. One file per selected subwindow."""
        self._export_app_facade.open_export_screenshots()

    def _resolve_focused_series_ordered_paths(
        self,
    ) -> tuple[str, str, str, list[str], List[Dataset]]:
        """
        Resolve focused-subwindow series identity and ordered source file paths.

        Returns:
            Tuple of (study_uid, series_uid, modality, ordered_file_paths, datasets).
        """
        return self._export_app_facade.resolve_focused_series_ordered_paths()

    def _prompt_save_path(
        self,
        title: str,
        default_name: str,
        filter_text: str,
        *,
        remember_pylinac_output_dir: bool = False,
    ) -> str:
        """Open a Save dialog that appears on top initially and return selected path."""
        return self._export_app_facade.prompt_save_path(
            title,
            default_name,
            filter_text,
            remember_pylinac_output_dir=remember_pylinac_output_dir,
        )

    def _qa_build_preflight_warnings(
        self,
        expected_modality: str,
        use_focused: bool,
        folder_path: Optional[str],
        datasets: List[Dataset],
        modality: str,
    ) -> List[str]:
        """Collect Stage 1c preflight warnings. Delegates to ``QAAppFacade``."""
        return self._qa_app_facade.build_preflight_warnings(
            expected_modality, use_focused, folder_path, datasets, modality
        )

    def _qa_user_confirms_preflight(self, warnings: List[str]) -> bool:
        """If warnings exist, show them and return True only if the user continues."""
        return self._qa_app_facade.user_confirms_preflight(warnings)

    def _show_qa_result_dialog(self, title: str, result: QAResult) -> None:
        """Show a compact final status dialog for Stage 1 QA runs."""
        self._qa_app_facade.show_qa_result_dialog(title, result)

    def _export_qa_json(
        self,
        result: QAResult,
        default_stem: str,
        inputs: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Offer JSON export for a finished Stage 1 QA run."""
        self._qa_app_facade.export_qa_json(result, default_stem, inputs)

    def _qa_offer_extent_retry(
        self,
        request: QARequest,
        json_inputs: Optional[Dict[str, Any]],
        *,
        progress_title: str,
        progress_label: str,
        result_dialog_title: str,
        json_default_stem: str,
    ) -> None:
        """After a strict scan-extent failure, offer a relaxed retry (one tier)."""
        self._qa_app_facade.offer_extent_retry(
            request,
            json_inputs,
            progress_title=progress_title,
            progress_label=progress_label,
            result_dialog_title=result_dialog_title,
            json_default_stem=json_default_stem,
        )

    def _start_qa_worker(
        self,
        request: QARequest,
        *,
        progress_title: str,
        progress_label: str,
        result_dialog_title: str,
        json_default_stem: str,
        json_inputs: Optional[Dict[str, Any]] = None,
        allow_extent_retry: bool = True,
    ) -> None:
        """Show progress, run QA in a background thread, then summary + JSON export."""
        self._qa_app_facade.start_qa_worker(
            request,
            progress_title=progress_title,
            progress_label=progress_label,
            result_dialog_title=result_dialog_title,
            json_default_stem=json_default_stem,
            json_inputs=json_inputs,
            allow_extent_retry=allow_extent_retry,
        )

    def _open_acr_ct_phantom_analysis(self) -> None:
        """Open the Stage 1 ACR CT (pylinac) analysis flow (menu / signal slot)."""
        self._qa_app_facade.open_acr_ct_phantom_analysis()

    def _open_acr_mri_phantom_analysis(self) -> None:
        """Open the Stage 1 ACR MRI Large (pylinac) analysis flow (menu / signal slot)."""
        self._qa_app_facade.open_acr_mri_phantom_analysis()

    def _start_mri_batch_worker(
        self,
        base_request: QARequest,
        compare_request: MRICompareRequest,
        *,
        json_inputs: Optional[Dict[str, Any]],
    ) -> None:
        """Launch compare-mode MRI batch analysis. Delegates to ``QAAppFacade``."""
        self._qa_app_facade.start_mri_batch_worker(
            base_request, compare_request, json_inputs=json_inputs
        )

    def _note_mri_compare_dialog_closed(self, *_args: Any) -> None:
        """Clear compare-results dialog reference after WA_DeleteOnClose."""
        self._qa_app_facade.note_mri_compare_dialog_closed(*_args)

    def _open_path_in_system_viewer(self, path: str) -> None:
        """Open a file path with the OS default application (PDF viewer, etc.)."""
        self._qa_app_facade.open_path_in_system_viewer(path)

    def _show_mri_compare_result_dialog(
        self,
        batch: MRIBatchResult,
        *,
        json_inputs: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Show ACR MRI compare results. Delegates to ``QAAppFacade``."""
        self._qa_app_facade.show_mri_compare_result_dialog(batch, json_inputs=json_inputs)

    def _export_mri_compare_json(
        self,
        batch: MRIBatchResult,
        inputs: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Offer JSON export for a finished compare-mode MRI batch. Delegates to ``QAAppFacade``."""
        self._qa_app_facade.export_mri_compare_json(batch, inputs)

    def _apply_imported_customizations(self) -> None:
        """Apply imported customization settings: overlay font, overlay refresh, annotations, theme, metadata columns."""
        font_size = self.config_manager.get_overlay_font_size()
        font_color = self.config_manager.get_overlay_font_color()
        font_family = self.config_manager.get_overlay_font_family()
        font_variant = self.config_manager.get_overlay_font_variant()
        scale_markers_color = self.config_manager.get_scale_markers_color()
        direction_labels_color = self.config_manager.get_direction_labels_color()
        direction_label_size = self.config_manager.get_direction_label_size()
        major_tick_interval_mm = self.config_manager.get_scale_markers_major_tick_interval_mm()
        minor_tick_interval_mm = self.config_manager.get_scale_markers_minor_tick_interval_mm()
        self.overlay_manager.set_font_size(font_size)
        self.overlay_manager.set_font_color(*font_color)
        self.overlay_manager.set_font_family(font_family)
        self.overlay_manager.set_font_variant(font_variant)
        subwindows = self.multi_window_layout.get_all_subwindows()
        for idx, subwindow in enumerate(subwindows):
            if subwindow and subwindow.image_viewer:
                subwindow.image_viewer.set_scale_markers_color_state(scale_markers_color)
                subwindow.image_viewer.set_direction_labels_color_state(direction_labels_color)
                subwindow.image_viewer.set_direction_label_size_state(direction_label_size)
                subwindow.image_viewer.set_scale_markers_tick_intervals_state(
                    major_tick_interval_mm,
                    minor_tick_interval_mm,
                )
            if subwindow and idx in self.subwindow_managers:
                om = self.subwindow_managers[idx].get("overlay_manager")
                if om:
                    om.set_font_size(font_size)
                    om.set_font_color(*font_color)
                    om.set_font_family(font_family)
                    om.set_font_variant(font_variant)
        self._refresh_overlay_all_subwindows()
        self._on_annotation_options_applied()
        theme = self.config_manager.get_theme()
        self.main_window._set_theme(theme)
        widths = self.config_manager.get_metadata_panel_column_widths()
        if len(widths) == 4:
            self.metadata_panel.tree_widget.setColumnWidth(0, widths[0])
            self.metadata_panel.tree_widget.setColumnWidth(1, widths[1])
            self.metadata_panel.tree_widget.setColumnWidth(2, widths[2])
            self.metadata_panel.tree_widget.setColumnWidth(3, widths[3])

    def _on_export_customizations(self) -> None:
        """Handle Export Customizations request."""
        self._customization_handlers.export_customizations()

    def _on_import_customizations(self) -> None:
        """Handle Import Customizations request."""
        self._customization_handlers.import_customizations()

    def _on_export_tag_presets(self) -> None:
        """Handle Export Tag Presets request."""
        self._customization_handlers.export_tag_presets()

    def _on_import_tag_presets(self) -> None:
        """Handle Import Tag Presets request."""
        self._customization_handlers.import_tag_presets()

    def _on_overlay_config_applied(self) -> None:
        """Handle overlay configuration being applied."""
        self._refresh_overlay_all_subwindows()

    def _refresh_overlay_all_subwindows(self) -> None:
        """Recreate corner overlays in every subwindow that has overlay coordinators (keeps multi-pane views in sync)."""
        subwindows = self.multi_window_layout.get_all_subwindows()
        for idx, subwindow in enumerate(subwindows):
            if subwindow and idx in self.subwindow_managers:
                oc = self.subwindow_managers[idx].get("overlay_coordinator")
                if oc:
                    oc.handle_overlay_config_applied()
    
    def _on_annotation_options_applied(self) -> None:
        """Handle annotation options applied - refresh all annotations."""
        default_stats_list = self.config_manager.get_roi_default_visible_statistics()
        default_stats_set = set(default_stats_list)

        subwindows = self.multi_window_layout.get_all_subwindows()
        for idx, subwindow in enumerate(subwindows):
            if idx not in self.subwindow_managers:
                continue
            managers = self.subwindow_managers[idx]
            roi_mgr = managers.get("roi_manager")
            if roi_mgr:
                for _key, roi_list in roi_mgr.rois.items():
                    for roi in roi_list:
                        roi.visible_statistics = default_stats_set.copy()
                roi_mgr.update_all_roi_styles(self.config_manager)
            meas_tool = managers.get("measurement_tool")
            if meas_tool:
                meas_tool.update_all_measurement_styles(self.config_manager)
            text_tool = managers.get("text_annotation_tool")
            if text_tool:
                text_tool.update_all_annotation_styles(self.config_manager)
            arrow_tool = managers.get("arrow_annotation_tool")
            if arrow_tool:
                arrow_tool.update_all_arrow_styles(self.config_manager)
            data = self.subwindow_data.get(idx, {})
            current_ds = data.get("current_dataset")
            sdm = managers.get("slice_display_manager")
            if sdm and current_ds is not None:
                # display_rois_for_slice refreshes ROI stats overlays via slice_display_manager callback
                sdm.display_rois_for_slice(current_ds)
                sdm.display_measurements_for_slice(current_ds)
    
    def _on_settings_applied(self) -> None:
        """Handle settings being applied."""
        font_size = self.config_manager.get_overlay_font_size()
        font_color = self.config_manager.get_overlay_font_color()
        font_family = self.config_manager.get_overlay_font_family()
        font_variant = self.config_manager.get_overlay_font_variant()
        direction_label_size = self.config_manager.get_direction_label_size()
        major_tick_interval_mm = self.config_manager.get_scale_markers_major_tick_interval_mm()
        minor_tick_interval_mm = self.config_manager.get_scale_markers_minor_tick_interval_mm()

        # Update the focused subwindow's overlay manager
        self.overlay_manager.set_font_size(font_size)
        self.overlay_manager.set_font_color(*font_color)
        self.overlay_manager.set_font_family(font_family)
        self.overlay_manager.set_font_variant(font_variant)

        # Also propagate to all per-subwindow overlay managers so that
        # switching subwindows reflects the new font immediately.
        show_scale_markers = self.config_manager.get_show_scale_markers()
        show_direction_labels = self.config_manager.get_show_direction_labels()
        subwindows = self.multi_window_layout.get_all_subwindows()
        for idx, subwindow in enumerate(subwindows):
            if subwindow and idx in self.subwindow_managers:
                om = self.subwindow_managers[idx].get('overlay_manager')
                if om:
                    om.set_font_size(font_size)
                    om.set_font_color(*font_color)
                    om.set_font_family(font_family)
                    om.set_font_variant(font_variant)
                subwindow.image_viewer.set_scale_markers_state(show_scale_markers)
                subwindow.image_viewer.set_direction_labels_state(show_direction_labels)
                subwindow.image_viewer.set_scale_markers_color_state(
                    self.config_manager.get_scale_markers_color()
                )
                subwindow.image_viewer.set_direction_labels_color_state(
                    self.config_manager.get_direction_labels_color()
                )
                subwindow.image_viewer.set_direction_label_size_state(direction_label_size)
                subwindow.image_viewer.set_scale_markers_tick_intervals_state(
                    major_tick_interval_mm,
                    minor_tick_interval_mm,
                )

        self._refresh_overlay_all_subwindows()
        # Slice position line mode may have changed via the Overlay Settings dialog.
        self._slice_location_line_coordinator.refresh_all()
    
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
        
        # Update histogram for focused subwindow if its histogram dialog is open
        if hasattr(self, 'dialog_coordinator'):
            self.dialog_coordinator.update_histogram_for_subwindow(self.focused_subwindow_index)
    
    def _restart_single_shot_timer(
        self,
        attr_name: str,
        interval_ms: int,
        on_timeout: Callable[..., None],
    ) -> None:
        """Create (once), stop, and restart a single-shot QTimer with the given interval and slot."""
        timer = getattr(self, attr_name, None)
        if timer is None:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.setInterval(interval_ms)
            timer.timeout.connect(on_timeout)
            setattr(self, attr_name, timer)
        timer.stop()
        timer.start()

    def _schedule_histogram_wl_only(self) -> None:
        """Schedule a light W/L-only histogram update (no pixel refetch) so W/L sliders stay responsive."""
        if not hasattr(self, "dialog_coordinator"):
            return
        self._restart_single_shot_timer(
            "_histogram_wl_update_timer",
            100,
            self._do_update_histogram_wl_only,
        )

    def _do_update_histogram_wl_only(self) -> None:
        """Update only the W/L overlay in the histogram (called after W/L throttle delay)."""
        if hasattr(self, "dialog_coordinator"):
            self.dialog_coordinator.update_histogram_window_level_only_for_subwindow(
                self.focused_subwindow_index
            )

    def _update_histogram_for_focused_subwindow(self) -> None:
        """Schedule a throttled full histogram update (pixel refetch) for slice/series changes."""
        if not hasattr(self, "dialog_coordinator"):
            return
        self._restart_single_shot_timer(
            "_histogram_update_timer",
            300,
            self._do_update_histogram_for_focused_subwindow,
        )

    def _do_update_histogram_for_focused_subwindow(self) -> None:
        """Update the histogram dialog for the currently focused subwindow (called after throttle delay)."""
        if hasattr(self, "dialog_coordinator"):
            self.dialog_coordinator.update_histogram_for_subwindow(self.focused_subwindow_index)
    
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
                    dataset = self._get_subwindow_dataset(idx)
                    if dataset is None:
                        dataset = data.get("current_dataset")
                    if dataset is not None and slice_display_manager is not None:
                        # Redisplay the slice to apply the reset
                        slice_display_manager.display_slice(
                            dataset,
                            self.current_studies,
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
        """Handle window/level preset selection from context menu (logic in ``window_level_preset_handler``)."""
        apply_window_level_preset(self, preset_index)
    
    def _update_zoom_preset_status_bar(self) -> None:
        """
        Update the zoom and preset status bar widget.
        Gets current zoom and preset info from view_state_manager.
        """
        current_zoom = self.image_viewer.current_zoom if self.image_viewer is not None else 1.0
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

        # MPR subwindow: route slice change to MPR controller.
        focused_idx = self.focused_subwindow_index
        if (
            hasattr(self, "_mpr_controller")
            and self._mpr_controller.is_mpr(focused_idx)
        ):
            self._mpr_controller.display_mpr_slice(focused_idx, slice_index)
            result = self.subwindow_data.get(focused_idx, {}).get("mpr_result")
            if result is not None:
                self.cine_controls_widget.update_frame_position(slice_index, result.n_slices)
                # Update edge-reveal slider for MPR view
                if self.image_viewer is not None:
                    self.image_viewer.set_navigation_slider_state(
                        enabled=True,
                        minimum=1,
                        maximum=result.n_slices,
                        value=slice_index + 1,
                        mode_label="Slice",
                        reveal=True,
                    )
            self._slice_sync_coordinator.on_slice_changed(focused_idx)
            self._slice_location_line_coordinator.refresh_all()
            if was_cine_advancing:
                QTimer.singleShot(0, self.cine_player.reset_cine_advancing_flag)
            return

        # Update focused subwindow's slice
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
            
            # Update subwindow data (keep current_datasets identical to the study
            # list used for display so HUD/metadata cannot use a divergent list).
            data['current_slice_index'] = slice_index
            data['current_datasets'] = series_datasets
            data['current_dataset'] = series_datasets[slice_index]
            
            # Keep app-level legacy references in sync with focused subwindow's current slice
            # (focus change updates them in update_focused_subwindow_references)
            self.current_slice_index = slice_index
            self.current_dataset = series_datasets[slice_index]
            
            # Display slice using focused subwindow's slice display manager
            slice_display_manager = managers['slice_display_manager']
            slice_display_manager.display_slice(
                series_datasets[slice_index],
                self.current_studies,
                study_uid,
                series_uid,
                slice_index
            )

            # Move focused navigator highlight/dots when scrolling crosses instance boundaries.
            self._update_series_navigator_highlighting()
            self.series_navigator.set_subwindow_assignments(self._get_subwindow_assignments())
            
            # Update About This File dialog if open
            self._update_about_this_file_dialog()
            
            # Update crosshairs for new slice
            if 'crosshair_coordinator' in managers and managers['crosshair_coordinator']:
                managers['crosshair_coordinator'].update_crosshairs_for_slice()
            
            # Update frame slider position
            total_slices = len(series_datasets)
            if total_slices > 0:
                self.cine_controls_widget.update_frame_position(slice_index, total_slices)

            # Update edge-reveal slice/frame slider overlay on the focused viewer
            if self.image_viewer is not None and total_slices > 0:
                self.image_viewer.set_navigation_slider_state(
                    enabled=True,
                    minimum=1,
                    maximum=total_slices,
                    value=slice_index + 1,
                    mode_label="Slice",
                    reveal=True,
                )
        
        # Reset cine advancing flag after all slice change processing is complete
        if was_cine_advancing:
            QTimer.singleShot(0, self.cine_player.reset_cine_advancing_flag)

        # Notify slice sync coordinator (no-op if sync is disabled or no groups).
        self._slice_sync_coordinator.on_slice_changed(self.focused_subwindow_index)
        self._slice_location_line_coordinator.refresh_all()

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
        """Get the currently focused subwindow. Delegates to subwindow lifecycle controller."""
        return self._subwindow_lifecycle_controller.get_focused_subwindow()

    def _get_thumbnail_for_view(self, view_index: int):
        """
        Return a small pixmap of the current image displayed in the given view (0–3),
        for use in the window-slot map thumbnail. Returns None if the view has no image.
        """
        subwindows = self.multi_window_layout.get_all_subwindows()
        if view_index < 0 or view_index >= len(subwindows):
            return None
        sub = subwindows[view_index]
        if not sub or not sub.image_viewer:
            return None
        view = sub.image_viewer
        vp = view.viewport()
        if vp is None or vp.width() <= 0 or vp.height() <= 0:
            return None
        pix = vp.grab(vp.rect())
        if pix.isNull():
            return None
        cell = 40
        return pix.scaled(
            cell, cell,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    def eventFilter(self, obj, event) -> bool:
        """Filter key events: layout shortcut focus gating and ``KeyboardEventHandler`` (see ``main_app_key_event_filter``)."""
        dispatched = dispatch_app_key_event(self, event)
        if dispatched is not None:
            return dispatched
        return super().eventFilter(obj, event)
    
    def run(self) -> int:
        """
        Run the application.
        
        Returns:
            Exit code
        """
        # Show disclaimer dialog before showing main window
        if not DisclaimerDialog.show_disclaimer(self.config_manager, self.main_window, force_show=False):
            # User cancelled, exit application
            return 0
        
        # Show window maximized (full-screen) and bring it to the foreground.
        # activateWindow() + raise_() ensure the window appears on top of other
        # open applications regardless of how the process was launched.
        self.main_window.showMaximized()
        self.main_window.activateWindow()
        self.main_window.raise_()
        
        # Set keyboard focus after window is shown
        # Use QTimer to ensure window is fully visible before setting focus
        QTimer.singleShot(100, self._set_initial_keyboard_focus)
        
        return self.app.exec()
    
    def _set_initial_keyboard_focus(self) -> None:
        """Set keyboard focus to the focused subwindow after window is shown."""
        if self.image_viewer:
            self.image_viewer.setFocus()


def exception_hook(exctype, value, tb):
    """Global exception handler to catch unhandled exceptions."""
    error_msg = ''.join(traceback.format_exception(exctype, value, tb))
    print(f"Unhandled exception:\n{error_msg}")
    
    # Try to show error dialog if QApplication exists
    try:
        if QApplication.instance():
            QMessageBox.critical(
                None, 
                "Fatal Error", 
                f"An unexpected error occurred:\n\n{exctype.__name__}: {value}\n\nThe application may be unstable."
            )
    except Exception:
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
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())


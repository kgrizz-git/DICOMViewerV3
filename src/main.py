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

import time as _time

_PERF_STARTUP_T0 = _time.perf_counter()

import logging
import sys
import traceback
from pathlib import Path

# Add src directory to path
src_dir = Path(__file__).parent
sys.path.insert(0, str(src_dir))

from collections.abc import Callable
from typing import Any, cast

from pydicom.dataset import Dataset
from PySide6.QtCore import QObject, QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QMessageBox,
    QStyleFactory,
)

from core.actions import customization_actions
from core.dicom_loader import DICOMLoader
from core.dicom_organizer import DICOMOrganizer
from core.dicom_processor import DICOMProcessor
from core.tag_edit_history import TagEditHistoryManager
from gui.actions import dialog_actions, view_actions
from gui.cine_controls_widget import CineControlsWidget
from gui.cine_player import CinePlayer
from gui.dialogs.file_dialog import FileDialog
from gui.image_viewer import ImageViewer
from gui.intensity_projection_controls_widget import IntensityProjectionControlsWidget
from gui.main_window import MainWindow
from gui.main_window_layout_helper import setup_main_window_content
from gui.multi_window_layout import MultiWindowLayout
from gui.overlay_manager import OverlayManager
from gui.series_navigator import SeriesNavigator
from gui.slice_navigator import SliceNavigator
from gui.sub_window_container import SubWindowContainer
from gui.window_level_controls import WindowLevelControls
from gui.window_slot_map_widget import WindowSlotMapPopupDialog, WindowSlotMapWidget
from gui.zoom_display_widget import ZoomDisplayWidget
from metadata.metadata_controller import MetadataController
from roi.roi_measurement_controller import ROIMeasurementController
from tools.roi_manager import ROIItem
from utils.annotation_clipboard import AnnotationClipboard
from utils.bundled_fonts import register_fonts_with_qt
from utils.config_manager import ConfigManager
from utils.debug_flags import PERF_LOG
from utils.log_sanitizer import sanitized_format_exc
from utils.slice_sync_group_palette import (
    slice_sync_group_rgb,
    view_index_to_group_index,
)
from utils.undo_redo import UndoRedoManager

_logger = logging.getLogger(__name__)

if PERF_LOG:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

# Import handler classes
from core.cine_app_facade import CineAppFacade
from core.customization_handlers import CustomizationHandlers
from core.mpr_navigator_thumbnail import (
    clear_mpr_navigator_thumbnail as mpr_thumb_clear_navigator,
)
from core.mpr_navigator_thumbnail import (
    get_subwindow_mpr_pixel_array as mpr_thumb_get_subwindow_pixel_array,
)
from core.mpr_navigator_thumbnail import (
    get_subwindow_mpr_thumbnail_pixel_array as mpr_thumb_get_subwindow_thumbnail_pixel_array,
)
from core.mpr_navigator_thumbnail import (
    on_mpr_detached as mpr_thumb_on_mpr_detached,
)
from core.mpr_navigator_thumbnail import (
    update_floating_mpr_navigator_thumbnail as mpr_thumb_update_floating_navigator,
)
from core.mpr_navigator_thumbnail import (
    update_mpr_navigator_thumbnail as mpr_thumb_update_navigator,
)
from core.navigation_slider_state import navigation_slider_mode_label_for_dataset
from core.overlay_settings_handlers import (
    apply_imported_customizations,
    cycle_overlay_detail_mode,
    on_annotation_options_applied,
    on_overlay_config_applied,
    on_overlay_font_color_changed,
    on_overlay_font_size_changed,
    on_settings_applied,
    refresh_overlay_all_subwindows,
    sync_all_overlay_managers_from_config,
)
from core.privacy_controller import PrivacyController
from core.projection_app_facade import ProjectionAppFacade
from core.session_reset_controller import (
    clear_data as session_reset_clear_data,
)
from core.session_reset_controller import (
    close_all_files as session_reset_close_all_files,
)
from core.session_reset_controller import (
    finalize_for_application_quit as session_reset_finalize_for_application_quit,
)
from core.slice_display_handlers import (
    display_measurements_for_slice,
    display_rois_for_slice,
    display_slice,
    on_slice_changed,
    redisplay_current_slice,
    update_roi_list,
)

# Import slice sync components
from core.slice_sync_coordinator import SliceSyncCoordinator
from core.study_index import LocalStudyIndexService
from core.study_navigation_handlers import (
    clear_subwindow,
    clear_subwindow_content,
    close_series,
    close_study,
    get_subwindow_assignments,
    refresh_series_navigator_state,
    reset_focused_subwindow_state_after_close,
    update_3d_view_action_state,
    update_series_navigator_highlighting,
)
from core.subwindow_lifecycle_controller import SubwindowLifecycleController
from core.view_state_handlers import (
    on_pixel_info_changed,
    on_rescale_toggle_changed,
    on_reset_all_views,
    on_transform_changed,
    on_viewport_resized,
    on_viewport_resizing,
    on_zoom_changed,
    update_zoom_preset_status_bar,
)
from core.window_level_preset_handler import apply_window_level_preset
from gui.annotation_paste_handler import AnnotationPasteHandler
from gui.app_handler_bootstrap import (
    initialize_handlers as bootstrap_initialize_handlers,
)
from gui.app_signal_wiring import wire_all_signals
from gui.dialog_coordinator import DialogCoordinator
from gui.dialogs.disclaimer_dialog import DisclaimerDialog
from gui.export_app_facade import ExportAppFacade
from gui.file_operations_handler import FileOperationsHandler
from gui.file_series_loading_coordinator import (
    FileSeriesLoadingCoordinator,
    show_cancelled_index_skip_toast,
)

# Import fusion components (FusionProcessor lazy-imported at point of use)
from gui.fusion_controls_widget import FusionControlsWidget
from gui.keyboard_event_handler import KeyboardEventHandler
from gui.layout_window_slot_controller import (
    capture_subwindow_view_states as layout_capture_subwindow_view_states,
)
from gui.layout_window_slot_controller import (
    connect_all_subwindow_context_menu_signals as layout_connect_all_subwindow_context_menu_signals,
)
from gui.layout_window_slot_controller import (
    connect_all_subwindow_transform_signals as layout_connect_all_subwindow_transform_signals,
)
from gui.layout_window_slot_controller import (
    ensure_all_subwindows_have_managers as layout_ensure_all_subwindows_have_managers,
)
from gui.layout_window_slot_controller import (
    on_expand_to_1x1_requested as layout_on_expand_to_1x1_requested,
)
from gui.layout_window_slot_controller import (
    on_layout_change_requested as layout_on_layout_change_requested,
)
from gui.layout_window_slot_controller import (
    on_layout_changed as layout_on_layout_changed,
)
from gui.layout_window_slot_controller import (
    on_main_window_layout_changed as layout_on_main_window_layout_changed,
)
from gui.layout_window_slot_controller import (
    on_swap_view_requested as layout_on_swap_view_requested,
)
from gui.layout_window_slot_controller import (
    on_window_slot_map_cell_clicked as layout_on_window_slot_map_cell_clicked,
)
from gui.layout_window_slot_controller import (
    on_window_slot_map_popup_requested as layout_on_window_slot_map_popup_requested,
)
from gui.layout_window_slot_controller import (
    refresh_window_slot_map_widgets as layout_refresh_window_slot_map_widgets,
)
from gui.layout_window_slot_controller import (
    restore_subwindow_views as layout_restore_subwindow_views,
)
from gui.main_app_key_event_filter import (
    dispatch_app_key_event,
)
from gui.mouse_mode_handler import MouseModeHandler
from gui.mpr_controller import MprController
from gui.qa_app_facade import QAAppFacade
from gui.slice_location_line_coordinator import SliceLocationLineCoordinator
from gui.subwindow_image_viewer_sync import (
    apply_initial_image_viewer_display_state,
    apply_theme_viewer_background_all,
)
from gui.subwindow_manager_factory import build_managers_for_subwindow
from gui.tag_export_union_host import TagExportUnionHost
from qa.analysis_types import (
    MRIBatchResult,
    MRICompareRequest,
    QARequest,
    QAResult,
)
from qa.worker import QAAnalysisWorker, QABatchWorker

_PERF_IMPORTS_DONE = _time.perf_counter()

# Studies structure: study UID → composite series key → ordered instance datasets.
StudiesNestedDict = dict[str, dict[str, list[Dataset]]]


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
    _window_slot_map_dialog: WindowSlotMapPopupDialog | None = None
    _window_slot_map_widget_popup: WindowSlotMapWidget | None = None
    _qa_worker: QAAnalysisWorker | None = None
    _qa_batch_worker: QABatchWorker | None = None
    _mri_compare_result_dialog: QDialog | None = None
    _histogram_wl_update_timer: QTimer | None = None
    _histogram_update_timer: QTimer | None = None
    study_index_service: LocalStudyIndexService
    tag_export_union_host: TagExportUnionHost

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
        self.study_index_service = cast(LocalStudyIndexService, cast(object, None))

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

        # LRU study cache (limits loaded studies in memory)
        from core.study_cache import StudyCache
        self.study_cache = StudyCache(max_studies=5)

        # Tag-edit history and general undo/redo stack
        self.tag_edit_history = TagEditHistoryManager(max_history=50)
        self.undo_redo_manager = UndoRedoManager(max_history=100)
        self.annotation_clipboard = AnnotationClipboard()

        # Application-wide flags read from persisted config
        self.privacy_view_enabled: bool = self.config_manager.get_privacy_view()
        # Studies that have already shown the fusion compatibility notification
        self._fusion_notified_studies: set[str] = set()

    def _init_main_window_and_layout(self) -> None:
        """
        Create the main window, file dialog, and multi-window layout.

        Must follow _init_core_managers so that config_manager and the Qt
        application are available.  The main window theme is applied here so
        that subsequent widget creation happens against the correct palette.
        """
        # Main window
        self.main_window = MainWindow(self.config_manager)
        self.main_window._app_ref = self  # for closing 3D dialogs on quit
        self.main_window.installEventFilter(self)

        # File open dialog (shared across the application)
        self.file_dialog = FileDialog(self.config_manager)

        # Multi-window image layout
        self.multi_window_layout = MultiWindowLayout(config_manager=self.config_manager)
        initial_layout = self.config_manager.get_multi_window_layout()
        self.multi_window_layout.set_layout(initial_layout)
        self.main_window.set_layout_mode(initial_layout)

        # Legacy backward-compatibility reference – updated once subwindows exist
        self.image_viewer: ImageViewer | None = None

        # Per-subwindow manager registry: {subwindow_index: {manager_name: instance}}
        self.subwindow_managers: dict[int, dict[str, Any]] = {}

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
        self.series_navigator.set_privacy_mode(self.privacy_view_enabled)
        self.series_navigator.set_show_slice_frame_count_badge(
            self.config_manager.get_navigator_show_slice_frame_count()
        )
        self.cine_controls_widget = CineControlsWidget()
        self.intensity_projection_controls_widget = IntensityProjectionControlsWidget()

        # Fusion components (FusionHandler itself is created per-subwindow)
        # Lazy import: defers heavy matplotlib/fusion import chain until first use
        from core.fusion_processor import FusionProcessor
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
        self.subwindow_data: dict[int, dict[str, Any]] = {}

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

        # 3D volume render facade: manages 3D rendering dialog lifecycle.
        from gui.volume_render_facade import VolumeRenderFacade
        self._volume_render_facade = VolumeRenderFacade(self)

        self._annotation_paste_handler = AnnotationPasteHandler(self)

        # Propagate initial privacy, slice sync, smoothing, and scale/direction UI to all viewers
        apply_initial_image_viewer_display_state(self)
        # Theme letterbox color: _apply_theme ran before subwindows existed; refresh every pane.
        apply_theme_viewer_background_all(self)
        self._refresh_slice_sync_group_indicators()

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
        self.current_datasets: list[Dataset] = []
        self.current_studies: StudiesNestedDict = {}
        self.current_slice_index = 0
        self.current_series_uid = ""
        self.current_study_uid = ""
        self.current_dataset: Dataset | None = None

        self.tag_export_union_host = TagExportUnionHost(self)

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

        self._update_3d_view_action_state()

        if PERF_LOG:
            _logger.info("[PERF] imports: %.0fms | app_init: %.0fms | total: %.0fms",
                         (_PERF_IMPORTS_DONE - _PERF_STARTUP_T0) * 1000,
                         (_time.perf_counter() - _PERF_IMPORTS_DONE) * 1000,
                         (_time.perf_counter() - _PERF_STARTUP_T0) * 1000)

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

    def _build_managers_for_subwindow(self, idx: int, subwindow: SubWindowContainer) -> dict[str, Any]:
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
        apply_theme_viewer_background_all(self)
        self._refresh_slice_sync_group_indicators()

    def _refresh_slice_sync_group_indicators(self) -> None:
        """
        Update per-pane title-strip colors for slice-sync linked groups.

        Uses **view** indices (0–3) from config, matching ``SliceSyncCoordinator``
        and ``ImageViewer.subwindow_index``. The strip is hidden when sync is off
        or the pane is not in a multi-member group.
        """
        sync_on = self.config_manager.get_slice_sync_enabled()
        groups = list(self.config_manager.get_slice_sync_groups()) if sync_on else []
        strip_h = self.config_manager.get_slice_sync_group_strip_height_px()
        for sub in self.multi_window_layout.get_all_subwindows():
            if sub is None:
                continue
            sub.set_slice_sync_strip_height(strip_h)
            iv = sub.image_viewer
            idx = getattr(iv, "subwindow_index", None) if iv is not None else None
            if idx is None:
                sub.set_slice_sync_group_indicator(None)
                continue
            gi = view_index_to_group_index(groups, int(idx))
            if gi is None:
                sub.set_slice_sync_group_indicator(None)
            else:
                r, g, b = slice_sync_group_rgb(gi)
                sub.set_slice_sync_group_indicator(QColor(r, g, b))

    def _get_subwindow_dataset(self, idx: int) -> Dataset | None:
        """Get current dataset for a subwindow. Delegates to subwindow lifecycle controller."""
        return self._subwindow_lifecycle_controller.get_subwindow_dataset(idx)

    def _get_subwindow_slice_index(self, idx: int) -> int:
        """Get current slice index for a subwindow. Delegates to subwindow lifecycle controller."""
        return self._subwindow_lifecycle_controller.get_subwindow_slice_index(idx)

    def _get_subwindow_slice_display_manager(self, idx: int):
        """Get slice display manager for a subwindow. Delegates to subwindow lifecycle controller."""
        return self._subwindow_lifecycle_controller.get_subwindow_slice_display_manager(idx)

    def _get_subwindow_mpr_pixel_array(self, idx: int, slice_index: int | None = None):
        """Return an MPR pixel array for subwindow *idx* (if any). Body in ``core.mpr_navigator_thumbnail``."""
        return mpr_thumb_get_subwindow_pixel_array(self, idx, slice_index)

    def _get_subwindow_mpr_thumbnail_pixel_array(self, idx: int):
        """Return a representative MPR thumbnail slice, preferring the stack midpoint."""
        return mpr_thumb_get_subwindow_thumbnail_pixel_array(self, idx)

    def _update_mpr_navigator_thumbnail(self, idx: int) -> None:
        """
        Show or refresh the MPR thumbnail in the series navigator for subwindow *idx*.

        Called automatically when ``MprController.mpr_activated`` is emitted.
        The thumbnail is built from the currently-displayed MPR slice pixel
        array with the active W/L values so it matches what is on screen.

        Args:
            idx: Zero-based subwindow index hosting the MPR view.
        """
        mpr_thumb_update_navigator(self, idx)

    def _clear_mpr_navigator_thumbnail(self, idx: int) -> None:
        """
        Remove the MPR thumbnail from the series navigator for subwindow *idx*.

        Called automatically when ``MprController.mpr_cleared`` is emitted.

        Args:
            idx: Zero-based subwindow index whose MPR was cleared.
        """
        mpr_thumb_clear_navigator(self, idx)

    def _update_floating_mpr_navigator_thumbnail(self) -> None:
        """
        Show or refresh detached MPR under navigator key -1 (internal id only).

        Layout matches attached MPR: same study/series keys place the thumbnail
        immediately after the source series row.
        """
        mpr_thumb_update_floating_navigator(self)

    def _on_mpr_detached(self, former_idx: int) -> None:
        """MPR was detached from a pane; refresh navigator thumbnails."""
        mpr_thumb_on_mpr_detached(self, former_idx)

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

    def _sync_intensity_projection_widget_from_mpr_data(self, data: dict[str, Any]) -> None:
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
            current_dataset = data.get("current_dataset")
            if current_dataset is None and 0 <= current_idx < total:
                current_dataset = datasets[current_idx]
            viewer.set_navigation_slider_state(
                enabled=True,
                minimum=1,
                maximum=total,
                value=current_idx + 1,
                mode_label=navigation_slider_mode_label_for_dataset(current_dataset),
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

    def get_histogram_callbacks_for_subwindow(self, idx: int) -> dict[str, Any]:
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
        """Initialize all handler classes. Body in ``core.app_handler_bootstrap``."""
        bootstrap_initialize_handlers(self)

    def _keyboard_delete_roi(self, roi: object) -> None:
        """Delete ROI invoked from keyboard; supports wrapper objects with .item or bare ROIItem."""
        item = getattr(roi, "item", None)
        if item is not None:
            self.roi_coordinator.handle_roi_delete_requested(item)
            return
        if roi is not None and self.image_viewer is not None:
            self.roi_manager.delete_roi(cast(ROIItem, roi), self.image_viewer.scene)

    def get_tag_export_union_snapshot(self) -> tuple[int, dict[str, Any] | None]:
        """Current load generation and merged tag map, if background union has finished."""
        return self.tag_export_union_host.get_snapshot()

    def _drain_tag_export_union_worker(self, timeout_sec: float = 180.0) -> None:
        """
        Stop and join the tag-export union QThread before replacing it.

        Body in ``core.tag_export_union_host.TagExportUnionHost.drain_worker``.
        """
        self.tag_export_union_host.drain_worker(timeout_sec)

    def _schedule_tag_export_union_rebuild(self) -> None:
        """Rebuild in-memory tag union off the GUI thread (no disk cache)."""
        self.tag_export_union_host.schedule_rebuild()

    def _clear_data(self) -> None:
        """Clear all ROIs, measurements, and related data for all subwindows."""
        session_reset_clear_data(self)

    def _close_files(self) -> None:
        """Close currently open files/folder and clear all data."""
        session_reset_close_all_files(self)

    def _on_app_about_to_quit(self) -> None:
        """Reset view–slot mapping and dissolve slice sync groups when the application is exiting."""
        session_reset_finalize_for_application_quit(self)

    # -------------------------------------------------------------------------
    # Per-series / per-study close helpers (used by navigator right-click menu)
    # -------------------------------------------------------------------------

    def _get_subwindow_assignments(self) -> dict[int, tuple[str, str, int]]:
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
        return get_subwindow_assignments(self)

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
        clear_subwindow(self, idx)

    def _reset_focused_subwindow_state_after_close(self) -> None:
        """
        Update the focused-subwindow app-level attributes after its content was
        cleared by _close_series or _close_study.

        Resets current_dataset/study/series/slice, clears the slice navigator,
        metadata panel, cine player, and re-wires focused-subwindow signals.
        """
        reset_focused_subwindow_state_after_close(self)

    def _on_clear_subwindow_content_requested(self, idx: int) -> None:
        """
        Clear one image pane from the context menu; loaded studies/series are unchanged.

        Args:
            idx: Subwindow index (0–3) for the viewer that requested the action.
        """
        clear_subwindow_content(self, idx)

    def _close_series(self, study_uid: str, series_key: str) -> None:
        """
        Close a single series: free pixel caches, remove it from the organizer,
        clear any subwindows that were showing it, and refresh the navigator.

        Focus stays on the now-empty subwindow if the closed series was focused.

        Args:
            study_uid:  StudyInstanceUID of the series to close.
            series_key: Composite series key (SeriesInstanceUID + SeriesNumber).
        """
        close_series(self, study_uid, series_key)

    def _close_study(self, study_uid: str) -> None:
        """
        Close an entire study: free pixel caches for all its series, remove it
        from the organizer, clear all affected subwindows, and refresh the
        navigator in one pass (no per-series navigator refreshes).

        Focus stays on the now-empty subwindow if any focused series was closed.

        Args:
            study_uid: StudyInstanceUID of the study to close.
        """
        close_study(self, study_uid)

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

    def _get_rescale_params(self) -> tuple[float | None, float | None, str | None, bool]:
        """Get rescale parameters for ROI operations (focused subwindow's view state)."""
        return (
            self.view_state_manager.rescale_slope,
            self.view_state_manager.rescale_intercept,
            self.view_state_manager.rescale_type,
            self.view_state_manager.use_rescaled_values
        )

    def _get_subwindow_rescale_params(
        self, idx: int
    ) -> tuple[float | None, float | None, str | None, bool]:
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
        update_roi_list(self)

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
        # Provide a callback so the W/L toolbar dropdown can read the active viewer's presets.
        def _get_active_wl_presets():
            vsm = getattr(self, "view_state_manager", None)
            if vsm is None:
                return []
            return getattr(vsm, "window_level_presets", []) or []
        self.main_window._get_active_wl_presets = _get_active_wl_presets

        def _get_wl_preset_menu_context():
            from gui.wl_preset_menu import (
                WLPresetMenuContext,
                context_from_legacy_presets,
            )

            vsm = getattr(self, "view_state_manager", None)
            if vsm is None:
                return WLPresetMenuContext(preset_objects=[], current_index=0)
            objects = getattr(vsm, "_wl_preset_objects", None)
            if objects:
                return WLPresetMenuContext(
                    preset_objects=list(objects),
                    current_index=vsm.current_preset_index,
                    unit=getattr(vsm, "rescale_type", None),
                    use_rescaled=vsm.use_rescaled_values,
                    rescale_slope=vsm.rescale_slope,
                    rescale_intercept=vsm.rescale_intercept,
                )
            legacy = vsm.window_level_presets or []
            return context_from_legacy_presets(
                legacy,
                current_index=vsm.current_preset_index,
                unit=getattr(vsm, "rescale_type", None),
                use_rescaled=vsm.use_rescaled_values,
                rescale_slope=vsm.rescale_slope,
                rescale_intercept=vsm.rescale_intercept,
            )

        self.main_window._get_wl_preset_menu_context = _get_wl_preset_menu_context
        self.main_window._open_wl_preset_manager = self._open_wl_preset_manager

        from gui.wl_preset_menu import wire_dynamic_wl_preset_menu

        def _on_wl_preset(i):
            return self.main_window._apply_wl_preset_requested.emit(i)
        _manage = self._open_wl_preset_manager
        view_menu = getattr(self.main_window, "wl_presets_view_menu", None)
        if view_menu is not None:
            wire_dynamic_wl_preset_menu(
                view_menu,
                get_context=_get_wl_preset_menu_context,
                get_legacy_presets=_get_active_wl_presets,
                on_select=_on_wl_preset,
                on_manage=_manage,
            )
        self.window_level_controls.attach_wl_presets_menu(
            on_select=_on_wl_preset,
            get_context=_get_wl_preset_menu_context,
            get_legacy_presets=_get_active_wl_presets,
            on_manage=_manage,
            row_layout=getattr(self.main_window, "wl_presets_row_layout", None),
        )

    def _open_wl_preset_manager(self) -> None:
        """Open Manage W/L Presets dialog."""
        dialog_actions.open_wl_preset_manager(self)

    def _on_focused_subwindow_changed(self, subwindow: SubWindowContainer) -> None:
        """Handle focused subwindow change. Delegates to subwindow lifecycle controller."""
        self._subwindow_lifecycle_controller.on_focused_subwindow_changed(subwindow)
        self._update_3d_view_action_state()
        # When "Show Only For Focused Window" is on, refresh slice location lines so they track focus.
        if self.config_manager.get_slice_location_lines_focused_only():
            self._slice_location_line_coordinator.refresh_all()
        # Refresh window-slot thumbnail(s) so focus outline updates.
        self._refresh_window_slot_map_widgets()

    def _update_series_navigator_highlighting(self) -> None:
        """Update series navigator highlighting based on focused subwindow's series."""
        update_series_navigator_highlighting(self)

    def _refresh_series_navigator_state(self) -> None:
        """Push organizer-backed multiframe state and action enablement into the navigator UI."""
        refresh_series_navigator_state(self)

    def _update_3d_view_action_state(self) -> None:
        """Enable toolbar/menu 3D actions when the focused series can volume-render."""
        update_3d_view_action_state(self)

    def _on_layout_changed(self, layout_mode: str) -> None:
        """Handle layout mode change from multi-window layout. Body in ``core.layout_window_slot_controller``."""
        layout_on_layout_changed(self, layout_mode)

    def _on_main_window_layout_changed(self, layout_mode: str) -> None:
        """Handle layout mode change from main window menu. Body in ``core.layout_window_slot_controller``."""
        layout_on_main_window_layout_changed(self, layout_mode)

    def _capture_subwindow_view_states(self) -> dict[int, dict[str, Any]]:
        """Capture view state for all subwindows before layout change."""
        return layout_capture_subwindow_view_states(self)

    def _restore_subwindow_views(self, view_states: dict[int, dict[str, Any]]) -> None:
        """Restore subwindow views after layout change."""
        layout_restore_subwindow_views(self, view_states)

    def _ensure_all_subwindows_have_managers(self) -> None:
        """Ensure all visible subwindows have managers."""
        layout_ensure_all_subwindows_have_managers(self)

    def _connect_all_subwindow_transform_signals(self) -> None:
        """Connect transform/zoom signals for all subwindows."""
        layout_connect_all_subwindow_transform_signals(self)

    def _connect_all_subwindow_context_menu_signals(self) -> None:
        """Connect context menu signals for all subwindows."""
        layout_connect_all_subwindow_context_menu_signals(self)

    def _on_layout_change_requested(self, layout_mode: str) -> None:
        """Handle layout change request from image viewer context menu."""
        layout_on_layout_change_requested(self, layout_mode)

    def _on_expand_to_1x1_requested(self) -> None:
        """Handle double-click: expand to 1x1 or, if already in 1x1, revert to last used layout (or 2x2)."""
        layout_on_expand_to_1x1_requested(self)

    def _on_swap_view_requested(self, other_index: int) -> None:
        """Handle Swap with View X from context menu: swap slot positions in all layouts; focus stays unchanged."""
        layout_on_swap_view_requested(self, other_index)

    def _refresh_window_slot_map_widgets(self) -> None:
        """Refresh the embedded and popup window-slot map widgets, if present."""
        layout_refresh_window_slot_map_widgets(self)

    def _on_window_slot_map_cell_clicked(self, slot: int) -> None:
        """Focus the subwindow in grid slot *slot* (0–3); 1×2 / 2×1 re-arrange via layout."""
        layout_on_window_slot_map_cell_clicked(self, slot)

    def _on_window_slot_map_popup_requested(self) -> None:
        """Show or hide a small popup with the window-slot map near the cursor (toggle)."""
        layout_on_window_slot_map_popup_requested(self)

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
        """Handle open files request. Delegates to ``dialog_actions.open_files``."""
        dialog_actions.open_files(self)

    def _open_folder(self) -> None:
        """Handle open folder request. Delegates to ``dialog_actions.open_folder``."""
        dialog_actions.open_folder(self)

    def _open_recent_file(self, file_path: str) -> None:
        """Handle open recent file/folder request. Delegates to ``dialog_actions.open_recent_file``."""
        dialog_actions.open_recent_file(self, file_path)

    def _open_files_from_paths(self, paths: list[str]) -> None:
        """Handle open files/folders from drag-and-drop. Delegates to ``dialog_actions.open_files_from_paths``."""
        dialog_actions.open_files_from_paths(self, paths)

    def _on_series_navigation_requested(self, direction: int) -> None:
        """
        Handle series navigation request from image viewer (focused subwindow only).
        Delegates to file/series loading coordinator.
        """
        self._file_series_coordinator.on_series_navigation_requested(direction)

    def _build_flat_series_list(self, studies: StudiesNestedDict) -> list[tuple[int, str, str, Dataset]]:
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

    def _display_slice(self, dataset, preserve_view_override: bool | None = None) -> None:
        """Display a DICOM slice."""
        display_slice(self, dataset, preserve_view_override=preserve_view_override)

    def _redisplay_current_slice(self, preserve_view: bool = True) -> None:
        """Redisplay the current slice via SliceDisplayManager with optional preserve_view override."""
        redisplay_current_slice(self, preserve_view)

    def _display_rois_for_slice(self, dataset) -> None:
        """Display ROIs for a slice."""
        display_rois_for_slice(self, dataset)

    def _display_measurements_for_slice(self, dataset) -> None:
        """Display measurements for a slice."""
        display_measurements_for_slice(self, dataset)

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
        """Handle settings dialog request. Delegates to ``dialog_actions.open_settings``."""
        dialog_actions.open_settings(self)

    def _on_study_index_after_load(
        self,
        datasets,
        _studies,
        merge_result,
        source_dir,
        merge_paths,
        *,
        was_cancelled: bool = False,
    ) -> None:
        """Record opened files in the local study index when enabled in settings."""
        if was_cancelled:
            show_cancelled_index_skip_toast(self)
        self.study_index_service.schedule_index_after_load(
            datasets,
            merge_paths,
            source_dir,
            merge_result,
            was_cancelled=was_cancelled,
        )

    def _open_study_index_search(self) -> None:
        """Open the local study index browser (File menu and Tools menu)."""
        dialog_actions.open_study_index_search(self)

    def _open_overlay_settings(self) -> None:
        """Handle Overlay Settings dialog request. Delegates to ``dialog_actions.open_overlay_settings``."""
        dialog_actions.open_overlay_settings(self)

    def _open_about_this_file(self) -> None:
        """Handle About This File dialog request."""
        dialog_actions.open_about_this_file(self)

    def _get_file_path_for_dataset(self, dataset, study_uid: str, series_uid: str, slice_index: int) -> str | None:
        """Get file path for a dataset. Delegates to file/series loading coordinator."""
        return self._file_series_coordinator.get_file_path_for_dataset(dataset, study_uid, series_uid, slice_index)

    def _on_show_file_from_series(self, study_uid: str, series_uid: str) -> None:
        """Handle 'Show file' request from series navigator thumbnail. Delegates to coordinator."""
        self._file_series_coordinator.on_show_file_from_series(study_uid, series_uid)

    def _on_about_this_file_from_series(self, study_uid: str, series_uid: str) -> None:
        """Handle 'About This File' request from series navigator thumbnail. Delegates to coordinator."""
        self._file_series_coordinator.on_about_this_file_from_series(study_uid, series_uid)

    def _get_current_slice_file_path(self, subwindow_idx: int | None = None) -> str | None:
        """Get file path for the currently displayed slice in a subwindow. Delegates to coordinator."""
        return self._file_series_coordinator.get_current_slice_file_path(subwindow_idx)

    def _update_about_this_file_dialog(self) -> None:
        """Update About This File dialog with current dataset and file path. Delegates to coordinator."""
        self._file_series_coordinator.update_about_this_file_dialog()

    def _on_privacy_view_toggled(self, enabled: bool) -> None:
        """Handle privacy view toggle. Delegates to ``view_actions.on_privacy_view_toggled``."""
        view_actions.on_privacy_view_toggled(self, enabled)

    def _on_slice_sync_toggled(self, enabled: bool) -> None:
        """Handle View → Slice Sync → Enable Slice Sync toggle. Delegates to ``view_actions``."""
        view_actions.on_slice_sync_toggled(self, enabled)

    def _open_slice_sync_dialog(self) -> None:
        """Open the Manage Sync Groups dialog."""
        dialog_actions.open_slice_sync_dialog(self)

    def _on_slice_sync_groups_changed(self, groups) -> None:
        """Receive updated group assignments from the Slice Sync dialog. Delegates to ``view_actions``."""
        view_actions.on_slice_sync_groups_changed(self, groups)

    def _on_slice_location_lines_toggled(self, visible: bool) -> None:
        """Handle View → Show Slice Location Lines → Enable/Disable toggle. Delegates to ``view_actions``."""
        view_actions.on_slice_location_lines_toggled(self, visible)

    def _on_slice_location_lines_same_group_only_toggled(self, same_group_only: bool) -> None:
        """Handle slice location lines same-group-only toggle. Delegates to ``view_actions``."""
        view_actions.on_slice_location_lines_same_group_only_toggled(self, same_group_only)

    def _on_slice_location_lines_focused_only_toggled(self, focused_only: bool) -> None:
        """Handle slice location lines focused-only toggle. Delegates to ``view_actions``."""
        view_actions.on_slice_location_lines_focused_only_toggled(self, focused_only)

    def _on_slice_location_lines_mode_toggled(self, mode: str) -> None:
        """Handle View → Show Slice Location Lines → slab mode toggle. Delegates to ``view_actions``."""
        view_actions.on_slice_location_lines_mode_toggled(self, mode)

    def _on_smooth_when_zoomed_toggled(self, enabled: bool) -> None:
        """Handle smooth-when-zoomed toggle. Delegates to ``view_actions``."""
        view_actions.on_smooth_when_zoomed_toggled(self, enabled)

    # ------------------------------------------------------------------
    # Orientation handlers (View menu → focused viewer)
    # ------------------------------------------------------------------

    def _on_orientation_flip_h(self) -> None:
        """Toggle horizontal flip on the currently focused image viewer."""
        view_actions.on_orientation_flip_h(self)

    def _on_orientation_flip_v(self) -> None:
        """Toggle vertical flip on the currently focused image viewer."""
        view_actions.on_orientation_flip_v(self)

    def _on_orientation_rotate_cw(self) -> None:
        """Rotate the currently focused image viewer 90° clockwise."""
        view_actions.on_orientation_rotate_cw(self)

    def _on_orientation_rotate_ccw(self) -> None:
        """Rotate the currently focused image viewer 90° counter-clockwise."""
        view_actions.on_orientation_rotate_ccw(self)

    def _on_orientation_rotate_180(self) -> None:
        """Rotate the currently focused image viewer 180°."""
        view_actions.on_orientation_rotate_180(self)

    def _on_orientation_reset(self) -> None:
        """Reset orientation of the currently focused image viewer to default."""
        view_actions.on_orientation_reset(self)

    def _on_scale_markers_toggled(self, enabled: bool) -> None:
        """Handle scale markers toggle. Delegates to ``view_actions``."""
        view_actions.on_scale_markers_toggled(self, enabled)

    def _on_direction_labels_toggled(self, enabled: bool) -> None:
        """Handle direction labels toggle. Delegates to ``view_actions``."""
        view_actions.on_direction_labels_toggled(self, enabled)

    def _on_slice_slider_toggled(self, enabled: bool) -> None:
        """Handle the in-view slice/frame slider toggle. Delegates to ``view_actions``."""
        view_actions.on_slice_slider_toggled(self, enabled)

    def _on_slice_slider_placement_changed(self, placement: str) -> None:
        """Handle the in-view slice/frame slider placement. Delegates to ``view_actions``."""
        view_actions.on_slice_slider_placement_changed(self, placement)

    def _on_slice_slider_direction_changed(self, direction: str) -> None:
        """Handle the in-view slice/frame slider direction. Delegates to ``view_actions``."""
        view_actions.on_slice_slider_direction_changed(self, direction)

    def _on_scale_markers_color_changed(self, r: int, g: int, b: int) -> None:
        """Handle scale markers color change from the View menu."""
        view_actions.on_scale_markers_color_changed(self, r, g, b)

    def _on_direction_labels_color_changed(self, r: int, g: int, b: int) -> None:
        """Handle direction labels color change from the View menu."""
        view_actions.on_direction_labels_color_changed(self, r, g, b)

    def _on_show_instances_separately_toggled(self, enabled: bool) -> None:
        """Handle the View → Show Instances Separately toggle."""
        view_actions.on_show_instances_separately_toggled(self, enabled)

    def _refresh_overlays_after_privacy_change(self) -> None:
        """Refresh overlays after privacy view change for all subwindows that have loaded data. Delegates to privacy controller."""
        self._privacy_controller.refresh_overlays()

    def _open_tag_viewer(self) -> None:
        """Handle tag viewer dialog request."""
        dialog_actions.open_tag_viewer(self)

    def _open_overlay_config(self) -> None:
        """Handle overlay configuration dialog request."""
        dialog_actions.open_overlay_config(self)

    def _open_annotation_options(self) -> None:
        """Handle annotation options dialog request."""
        dialog_actions.open_annotation_options(self)

    def _open_quick_window_level(self) -> None:
        """Open Quick Window/Level dialog for the focused subwindow."""
        dialog_actions.open_quick_window_level(self)

    def _open_quick_start_guide(self) -> None:
        """Handle Quick Start Guide dialog request."""
        dialog_actions.open_quick_start_guide(self)

    def _on_keyboard_shortcuts_requested(self) -> None:
        """Handle Keyboard Shortcuts dialog request (Help menu / F1)."""
        from gui.dialogs.keyboard_shortcuts_dialog import KeyboardShortcutsDialog
        dlg = KeyboardShortcutsDialog(self.main_window)
        dlg.exec()

    def _open_user_documentation_in_browser(self) -> None:
        """Open the user guide hub (Markdown on GitHub) in the system browser."""
        dialog_actions.open_user_documentation_in_browser(self)

    def _open_fusion_technical_doc(self) -> None:
        """Handle Fusion Technical Documentation dialog request."""
        dialog_actions.open_fusion_technical_doc(self)

    def _open_tag_export(self) -> None:
        """Handle Tag Export dialog request."""
        dialog_actions.open_tag_export(self)

    def _open_export_roi_statistics(self) -> None:
        """Handle Export ROI Statistics request (from menu or image viewer context menu)."""
        self._export_app_facade.open_export_roi_statistics()

    def _open_export(self) -> None:
        """Handle Export dialog request. Resolution options are in the dialog."""
        self._export_app_facade.open_export()

    def _open_deep_anonymizer_export(self) -> None:
        """Handle File → Export with Deep Anonymization… request."""
        self._export_app_facade.open_deep_anonymizer_export()

    def _open_export_screenshots(self) -> None:
        """Handle Export Screenshots dialog request. One file per selected subwindow."""
        self._export_app_facade.open_export_screenshots()

    def _on_save_mpr_as_dicom(self) -> None:
        """File → Save MPR as DICOM… — requires focused subwindow in MPR mode."""
        self._mpr_controller.prompt_save_mpr_as_dicom()

    def _open_structured_report_browser(self, subwindow_idx: int | None = None) -> None:
        """
        Tools → Structured Report… — open the SR document browser for the focused pane's
        current dataset when it is a Structured Report (SR storage class or Modality SR).
        """
        dialog_actions.open_structured_report_browser(self, subwindow_idx)

    def _on_export_cine_video(self) -> None:
        """
        File → Export Cine As… — GIF / AVI / MP4 / MPG for the focused 2D multi-frame pane.

        Delegates to ``dialog_actions.open_export_cine_video`` (same PIL render path and
        threaded encode as before).
        """
        dialog_actions.open_export_cine_video(self)

    def _resolve_focused_series_ordered_paths(
        self,
    ) -> tuple[str, str, str, list[str], list[Dataset]]:
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
        folder_path: str | None,
        datasets: list[Dataset],
        modality: str,
    ) -> list[str]:
        """Collect Stage 1c preflight warnings. Delegates to ``QAAppFacade``."""
        return self._qa_app_facade.build_preflight_warnings(
            expected_modality, use_focused, folder_path, datasets, modality
        )

    def _qa_user_confirms_preflight(self, warnings: list[str]) -> bool:
        """If warnings exist, show them and return True only if the user continues."""
        return self._qa_app_facade.user_confirms_preflight(warnings)

    def _show_qa_result_dialog(self, title: str, result: QAResult) -> None:
        """Show a compact final status dialog for Stage 1 QA runs."""
        self._qa_app_facade.show_qa_result_dialog(title, result)

    def _export_qa_json(
        self,
        result: QAResult,
        default_stem: str,
        inputs: dict[str, Any] | None = None,
    ) -> None:
        """Offer JSON export for a finished Stage 1 QA run."""
        self._qa_app_facade.export_qa_json(result, default_stem, inputs)

    def _qa_offer_extent_retry(
        self,
        request: QARequest,
        json_inputs: dict[str, Any] | None,
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
        json_inputs: dict[str, Any] | None = None,
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
        dialog_actions.open_acr_ct_phantom_analysis(self)

    def _open_acr_mri_phantom_analysis(self) -> None:
        """Open the Stage 1 ACR MRI Large (pylinac) analysis flow (menu / signal slot)."""
        dialog_actions.open_acr_mri_phantom_analysis(self)

    def _open_nuclear_qc_analysis(self) -> None:
        """Open the nuclear-medicine QC (pylinac.nuclear) flow (menu / signal slot)."""
        dialog_actions.open_nuclear_qc_analysis(self)

    def _start_mri_batch_worker(
        self,
        base_request: QARequest,
        compare_request: MRICompareRequest,
        *,
        json_inputs: dict[str, Any] | None,
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
        dialog_actions.open_path_in_system_viewer(self, path)

    def _show_mri_compare_result_dialog(
        self,
        batch: MRIBatchResult,
        *,
        json_inputs: dict[str, Any] | None = None,
    ) -> None:
        """Show ACR MRI compare results. Delegates to ``QAAppFacade``."""
        self._qa_app_facade.show_mri_compare_result_dialog(batch, json_inputs=json_inputs)

    def _export_mri_compare_json(
        self,
        batch: MRIBatchResult,
        inputs: dict[str, Any] | None = None,
    ) -> None:
        """Offer JSON export for a finished compare-mode MRI batch. Delegates to ``QAAppFacade``."""
        self._qa_app_facade.export_mri_compare_json(batch, inputs)

    def _apply_imported_customizations(self) -> None:
        """Apply imported customization settings: overlay font, overlay refresh, annotations, theme, metadata columns."""
        apply_imported_customizations(self)

    def _on_export_customizations(self) -> None:
        """Handle Export Customizations request."""
        customization_actions.on_export_customizations(self)

    def _on_import_customizations(self) -> None:
        """Handle Import Customizations request."""
        customization_actions.on_import_customizations(self)

    def _on_export_tag_presets(self) -> None:
        """Handle Export Tag Presets request."""
        customization_actions.on_export_tag_presets(self)

    def _on_import_tag_presets(self) -> None:
        """Handle Import Tag Presets request."""
        customization_actions.on_import_tag_presets(self)

    def _sync_all_overlay_managers_from_config(self) -> None:
        """Apply persisted overlay mode and visibility state to every pane's OverlayManager."""
        sync_all_overlay_managers_from_config(self)

    def _cycle_overlay_detail_mode(self) -> None:
        """Cycle corner overlay detail across all panes: minimal -> detailed -> hidden -> minimal."""
        cycle_overlay_detail_mode(self)

    def _on_overlay_config_applied(self) -> None:
        """Handle overlay configuration being applied."""
        on_overlay_config_applied(self)

    def _refresh_overlay_all_subwindows(self) -> None:
        """Recreate corner overlays in every subwindow that has overlay coordinators."""
        refresh_overlay_all_subwindows(self)

    def _on_annotation_options_applied(self) -> None:
        """Handle annotation options applied - refresh all annotations."""
        on_annotation_options_applied(self)

    def _on_settings_applied(self) -> None:
        """Handle settings being applied."""
        on_settings_applied(self)

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

    def _set_roi_mode(self, mode: str | None) -> None:
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
        """Handle rescale toggle change from toolbar or context menu."""
        on_rescale_toggle_changed(self, checked)

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
        """Reset view for all subwindows in the layout."""
        on_reset_all_views(self)

    def _on_zoom_changed(self, zoom_level: float) -> None:
        """Handle zoom level change."""
        on_zoom_changed(self, zoom_level)

    def _on_transform_changed(self) -> None:
        """Handle view transform change (zoom/pan)."""
        on_transform_changed(self)

    def _on_viewport_resizing(self) -> None:
        """Handle viewport resize start (when splitter starts moving)."""
        on_viewport_resizing(self)

    def _on_viewport_resized(self) -> None:
        """Handle viewport resize (when splitter moves)."""
        on_viewport_resized(self)

    def _on_pixel_info_changed(self, pixel_value_str: str, x: int, y: int, z: int) -> None:
        """Handle pixel info changed signal from image viewer."""
        on_pixel_info_changed(self, pixel_value_str, x, y, z)

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
        """Update the zoom and preset status bar widget."""
        update_zoom_preset_status_bar(self)

    def _on_overlay_font_size_changed(self, font_size: int) -> None:
        """Handle overlay font size change from toolbar - update ALL subwindows."""
        on_overlay_font_size_changed(self, font_size)

    def _on_overlay_font_color_changed(self, r: int, g: int, b: int) -> None:
        """Handle overlay font color change from toolbar - update ALL subwindows."""
        on_overlay_font_color_changed(self, r, g, b)

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
        """Handle slice change from slice navigator (affects focused subwindow only)."""
        on_slice_changed(self, slice_index)

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

    def _get_focused_subwindow(self) -> SubWindowContainer | None:
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
        QTimer.singleShot(800, self._warn_if_privacy_off)

        return self.app.exec()

    def _set_initial_keyboard_focus(self) -> None:
        """Set keyboard focus to the focused subwindow after window is shown."""
        if self.image_viewer:
            self.image_viewer.setFocus()

    def _warn_if_privacy_off(self) -> None:
        """Show a warning toast on startup when privacy mode is disabled."""
        if not self.config_manager.get_privacy_view():
            self.main_window.show_toast_message(
                "Privacy mode is OFF — patient identifiers are visible",
                timeout_ms=7000,
                severity="warning",
            )


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
        _logger.debug("%s", sanitized_format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())

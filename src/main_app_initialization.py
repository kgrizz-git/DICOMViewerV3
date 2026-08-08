"""
DICOMViewerApp initialization mixin module.

Owns ``_init_*``, ``_setup_*``, ``_connect_*``, and ``_initialize_*`` orchestration
methods for ``DICOMViewerApp`` (see MAIN_PY_REFACTOR_PLAN Appendix A).
Methods extracted from ``main.py`` in Phase 3.
"""

from __future__ import annotations

# pyright: reportAttributeAccessIssue=false, reportArgumentType=false, reportUninitializedInstanceVariable=false
import sys
from typing import Any, cast

from pydicom.dataset import Dataset
from PySide6.QtWidgets import QApplication, QStyleFactory

from core.dicom_loader import DICOMLoader
from core.dicom_organizer import DICOMOrganizer
from core.dicom_processor import DICOMProcessor
from core.projection_app_facade import ProjectionAppFacade
from core.slice_sync_coordinator import SliceSyncCoordinator
from core.subwindow_lifecycle_controller import SubwindowLifecycleController
from core.tag_edit_history import TagEditHistoryManager
from gui.annotation_paste_handler import AnnotationPasteHandler
from gui.app_handler_bootstrap import (
    initialize_handlers as bootstrap_initialize_handlers,
)
from gui.app_signal_wiring import wire_all_signals
from gui.cine_controls_widget import CineControlsWidget
from gui.dialogs.file_dialog import FileDialog
from gui.export_app_facade import ExportAppFacade
from gui.fusion_controls_widget import FusionControlsWidget
from gui.image_viewer import ImageViewer
from gui.intensity_projection_controls_widget import IntensityProjectionControlsWidget
from gui.layout_window_slot_controller import (
    connect_all_subwindow_context_menu_signals as layout_connect_all_subwindow_context_menu_signals,
)
from gui.layout_window_slot_controller import (
    connect_all_subwindow_transform_signals as layout_connect_all_subwindow_transform_signals,
)
from gui.main_window import MainWindow
from gui.main_window_layout_helper import (
    MainWindowPanels,
    WindowSlotMapCallbacks,
    setup_main_window_content,
)
from gui.mpr_controller import MprController
from gui.multi_window_layout import MultiWindowLayout
from gui.overlay_manager import OverlayManager
from gui.qa_app_facade import QAAppFacade
from gui.series_navigator import SeriesNavigator
from gui.slice_location_line_coordinator import SliceLocationLineCoordinator
from gui.slice_navigator import SliceNavigator
from gui.subwindow_image_viewer_sync import (
    apply_initial_image_viewer_display_state,
    apply_theme_viewer_background_all,
)
from gui.tag_export_union_host import StudiesNestedDict, TagExportUnionHost
from gui.window_level_controls import WindowLevelControls
from gui.zoom_display_widget import ZoomDisplayWidget
from metadata.metadata_controller import MetadataController
from roi.roi_measurement_controller import ROIMeasurementController
from utils.annotation_clipboard import AnnotationClipboard
from utils.bundled_fonts import register_fonts_with_qt
from utils.config_manager import ConfigManager
from utils.debug_log import configure_debug_logging
from utils.undo_redo import UndoRedoManager


class InitializationMixin:
    """
    Mixin: core managers, main window/layout, view widgets, controllers/tools,
    handlers, UI setup, and signal connection orchestration for ``DICOMViewerApp``.
    """

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
        configure_debug_logging(
            self.config_manager.get_diagnostics_enabled(),
            path=self.config_manager.get_diagnostics_log_path(),
        )
        self.dicom_loader = DICOMLoader()
        self.dicom_organizer = DICOMOrganizer()
        self.dicom_processor = DICOMProcessor()

        # LRU study cache: memory budget (fraction of system RAM) is the
        # primary limit; max_studies is a high-water safety net only.
        from core.study_cache import StudyCache
        self.study_cache = StudyCache(
            max_studies=self.config_manager.get_study_load_max_studies_cap(),
            memory_fraction=self.config_manager.get_study_load_memory_fraction(),
            memory_floor_mb=1024.0,
        )

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

        # Startup timing constants live on ``main``; emit via app helper to avoid
        # a bare ``_PERF_STARTUP_T0`` NameError and a runtime ``import main`` cycle.
        self._log_startup_perf()

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

    def _initialize_handlers(self) -> None:
        """Initialize all handler classes. Body in ``gui.app_handler_bootstrap``."""
        bootstrap_initialize_handlers(self)

    def _setup_ui(self) -> None:
        """Assemble main-window panel layout. Implemented in gui.main_window_layout_helper."""
        setup_main_window_content(
            self.main_window,
            MainWindowPanels(
                multi_window_layout=self.multi_window_layout,
                cine_controls_widget=self.cine_controls_widget,
                metadata_panel=self.metadata_panel,
                window_level_controls=self.window_level_controls,
                zoom_display_widget=self.zoom_display_widget,
                roi_list_panel=self.roi_list_panel,
                roi_statistics_panel=self.roi_statistics_panel,
                intensity_projection_controls_widget=self.intensity_projection_controls_widget,
                fusion_controls_widget=self.fusion_controls_widget,
                series_navigator=self.series_navigator,
            ),
            slot_map=WindowSlotMapCallbacks(
                get_slot_to_view=self.multi_window_layout.get_slot_to_view,
                get_layout_mode=self.multi_window_layout.get_layout_mode,
                get_focused_view_index=self.get_focused_subwindow_index,
                get_thumbnail_for_view=self._get_thumbnail_for_view,
            ),
        )

    def _connect_signals(self) -> None:
        """Connect all application-level Qt signals. Implemented in gui.app_signal_wiring."""
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

    def _connect_all_subwindow_transform_signals(self) -> None:
        """Connect transform/zoom signals for all subwindows."""
        layout_connect_all_subwindow_transform_signals(self)

    def _connect_all_subwindow_context_menu_signals(self) -> None:
        """Connect context menu signals for all subwindows."""
        layout_connect_all_subwindow_context_menu_signals(self)

    def _connect_focused_subwindow_signals(self) -> None:
        """Connect signals for the currently focused subwindow. Delegates to subwindow lifecycle controller."""
        self._subwindow_lifecycle_controller.connect_focused_subwindow_signals()


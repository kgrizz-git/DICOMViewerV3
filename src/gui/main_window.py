"""
Main Application Window

This module implements the main application window with menu bar, toolbar,
and layout for the DICOM viewer application.

Inputs:
    - User interactions (menu selections, toolbar clicks)
    - Application configuration
    
Outputs:
    - Main application interface
    - Window layout and widgets
    
Requirements:
    - PySide6 for GUI components
    - ConfigManager for settings
"""
# Toolbar / ``QAction`` fields use ``Optional[…] = None`` for pre-builder state; they are
# always populated during ``MainWindow.__init__`` before interactive use.
# pyright: reportOptionalMemberAccess=false

from PySide6.QtWidgets import (QMainWindow, QMenuBar, QStatusBar,
                                QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
                                QMessageBox, QLabel, QSizePolicy, QColorDialog,
                                QApplication, QDialog, QTextBrowser, QPushButton, QDialogButtonBox, QMenu,
                                QScrollArea, QFrame, QGraphicsOpacityEffect, QToolButton, QToolBar,
                                QComboBox)
from PySide6.QtCore import Qt, Signal, QEvent, QBuffer, QByteArray, QIODevice, QDir, QTimer, QPropertyAnimation
from PySide6.QtGui import QAction, QIcon, QKeySequence, QColor, QDragEnterEvent, QDropEvent, QPixmap
from typing import Any, Dict, List, Literal, Optional, TYPE_CHECKING, cast

if TYPE_CHECKING:
    from gui.image_viewer import ImageViewer
from pathlib import Path
from datetime import datetime
import sys
import os
import urllib.parse
import re

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.config_manager import ConfigManager
from version import __version__ as APP_VERSION
from utils.debug_flags import DEBUG_LAYOUT
from gui.dialogs.edit_recent_list_dialog import EditRecentListDialog
from gui.main_window_menu_builder import build_menu_bar
from gui.main_window_toolbar_builder import build_main_toolbar
from gui.window_slot_map_widget import WindowSlotMapWidget


def _get_resource_path(relative_path: str) -> str:
    """
    Get absolute path to a resource file, works for both development and PyInstaller bundle.
    
    Args:
        relative_path: Relative path from project root (e.g., "resources/images/file.png")
        
    Returns:
        Absolute file path with forward slashes for Qt stylesheet url() function.
        Qt stylesheets work best with absolute paths using forward slashes on all platforms.
    """
    if getattr(sys, 'frozen', False):
        # Running in a PyInstaller bundle
        base_path = Path(cast(str, getattr(sys, "_MEIPASS")))
    else:
        # Running in development mode
        # main_window.py is in src/gui/, so go up to project root
        base_path = Path(__file__).parent.parent.parent
    
    resource_path = base_path / relative_path
    absolute_path = resource_path.resolve()
    
    # Convert to string with forward slashes (Qt stylesheets work with forward slashes on all platforms)
    # Use absolute path directly - Qt's url() function handles absolute paths correctly
    path_str = str(absolute_path).replace('\\', '/')
    
    return path_str


class MainWindow(QMainWindow):
    """
    Main application window for the DICOM viewer.
    
    Provides:
    - Menu bar with file operations, view options, tools
    - Toolbar with common actions
    - Status bar for information display
    - Central widget area for image display and panels
    """
    
    # Signals
    open_file_requested = Signal()
    open_folder_requested = Signal()
    open_recent_file_requested = Signal(str)  # Emitted when a recent file/folder is selected (path)
    close_requested = Signal()  # Emitted when close is requested
    export_requested = Signal()
    export_screenshots_requested = Signal()  # Emitted when Export Screenshots is requested
    save_mpr_dicom_requested = Signal()  # File → Save MPR as DICOM… (focused MPR pane)
    export_cine_video_requested = Signal()  # File → Export cine as… (focused multi-frame 2D pane)
    settings_requested = Signal()
    overlay_settings_requested = Signal()  # Emitted when overlay settings dialog is requested
    tag_viewer_requested = Signal()
    overlay_config_requested = Signal()
    annotation_options_requested = Signal()  # Emitted when annotation options dialog is requested
    mouse_mode_changed = Signal(str)  # Emitted when mouse mode changes ("roi_ellipse", "roi_rectangle", "measure", "zoom", "pan", "auto_window_level")
    scroll_wheel_mode_changed = Signal(str)  # Emitted when scroll wheel mode changes ("slice" or "zoom")
    overlay_font_size_changed = Signal(int)  # Emitted when overlay font size changes
    overlay_font_color_changed = Signal(int, int, int)  # Emitted when overlay font color changes (r, g, b)
    scale_markers_color_changed = Signal(int, int, int)  # Emitted when scale markers color changes (r, g, b)
    direction_labels_color_changed = Signal(int, int, int)  # Emitted when direction labels color changes (r, g, b)
    reset_view_requested = Signal()  # Emitted when reset view is requested
    reset_all_views_requested = Signal()  # Emitted when reset all views is requested
    viewport_resized = Signal()  # Emitted when splitter moves and viewport size changes
    viewport_resizing = Signal()  # Emitted when splitter starts moving (before resize completes)
    series_navigation_requested = Signal(int)  # Emitted when series navigation is requested (-1 for prev, 1 for next)
    rescale_toggle_changed = Signal(bool)  # Emitted when rescale toggle changes (True = use rescaled values)
    clear_measurements_requested = Signal()  # Emitted when clear measurements is requested
    quick_start_guide_requested = Signal()  # Emitted when Quick Start Guide is requested
    user_documentation_requested = Signal()  # Opens user guide hub in default browser (Help → Documentation)
    fusion_technical_doc_requested = Signal()  # Emitted when Fusion Technical Documentation is requested
    tag_export_requested = Signal()  # Emitted when tag export is requested
    theme_changed = Signal(str)  # Emitted when theme changes (theme name)
    series_navigator_visibility_changed = Signal(bool)  # Emitted when series navigator visibility changes
    undo_tag_edit_requested = Signal()  # Emitted when undo tag edit is requested
    redo_tag_edit_requested = Signal()  # Emitted when redo tag edit is requested
    open_files_from_paths_requested = Signal(list)  # Emitted when files/folders are dropped (list of paths)
    layout_changed = Signal(str)  # Emitted when layout mode changes ("1x1", "1x2", "2x1", "2x2")
    privacy_view_toggled = Signal(bool)  # Emitted when privacy view is toggled (True = enabled)
    smooth_when_zoomed_toggled = Signal(bool)  # Emitted when smooth-when-zoomed is toggled (True = enabled)
    scale_markers_toggled = Signal(bool)  # Emitted when scale markers are toggled (True = enabled)
    direction_labels_toggled = Signal(bool)  # Emitted when direction labels are toggled (True = enabled)
    slice_slider_toggled = Signal(bool)  # Emitted when in-view slice/frame slider is toggled (True = enabled)
    show_instances_separately_toggled = Signal(bool)  # Emitted when multi-frame instance expansion is toggled
    slice_sync_toggled = Signal(bool)  # Emitted when slice sync enabled state changes (True = enabled)
    slice_sync_manage_requested = Signal()  # Emitted when "Manage Sync Groups…" is chosen
    slice_location_lines_toggled = Signal(bool)  # Emitted when slice location lines toggle (True = show)
    slice_location_lines_same_group_only_toggled = Signal(bool)  # Emitted when same-group-only toggle changes (True = only same group)
    slice_location_lines_focused_only_toggled = Signal(bool)  # Emitted when focused-only toggle changes (True = only focused window)
    slice_location_lines_mode_toggled = Signal(str)  # Emitted when line mode changes ("middle" or "begin_end")
    about_this_file_requested = Signal()  # Emitted when About this File is requested
    histogram_requested = Signal()  # Emitted when Histogram dialog is requested
    radiation_dose_report_requested = Signal()  # Tools → Radiation dose report (focused pane)
    export_roi_statistics_requested = Signal()  # Emitted when Export ROI Statistics is requested
    export_customizations_requested = Signal()  # Emitted when Export Customizations is requested
    import_customizations_requested = Signal()  # Emitted when Import Customizations is requested
    export_tag_presets_requested = Signal()  # Emitted when Export Tag Presets is requested
    import_tag_presets_requested = Signal()  # Emitted when Import Tag Presets is requested
    copy_annotation_requested = Signal()  # Emitted when copy annotation is requested
    paste_annotation_requested = Signal()  # Emitted when paste annotation is requested
    acr_ct_phantom_requested = Signal()  # Emitted when ACR CT (pylinac) analysis is requested
    acr_mri_phantom_requested = Signal()  # Emitted when ACR MRI Large (pylinac) analysis is requested
    create_mpr_view_requested = Signal()  # Tools → Create MPR view (focused subwindow)
    study_index_search_requested = Signal()  # File / Tools → local encrypted study index browser

    # Orientation (flip / rotate) signals — emitted by View menu; connected to focused viewer handlers
    orientation_flip_h_requested = Signal()       # Flip horizontally
    orientation_flip_v_requested = Signal()       # Flip vertically
    orientation_rotate_cw_requested = Signal()    # Rotate 90° clockwise
    orientation_rotate_ccw_requested = Signal()   # Rotate 90° counter-clockwise
    orientation_rotate_180_requested = Signal()   # Rotate 180°
    orientation_reset_requested = Signal()        # Reset to default orientation

    # Filled by build_menu_bar in _create_menu_bar (Optional until menu is built).
    recent_menu: Optional[QMenu] = None
    light_theme_action: Optional[QAction] = None
    dark_theme_action: Optional[QAction] = None
    privacy_view_action: Optional[QAction] = None
    smooth_when_zoomed_action: Optional[QAction] = None
    scale_markers_action: Optional[QAction] = None
    direction_labels_action: Optional[QAction] = None
    slice_slider_action: Optional[QAction] = None
    show_instances_separately_action: Optional[QAction] = None
    show_left_pane_action: Optional[QAction] = None
    show_right_pane_action: Optional[QAction] = None
    show_series_navigator_action: Optional[QAction] = None
    show_navigator_slice_frame_count_action: Optional[QAction] = None
    fullscreen_action: Optional[QAction] = None
    show_window_slot_map_action: Optional[QAction] = None
    slice_sync_action: Optional[QAction] = None
    slice_location_lines_enable_action: Optional[QAction] = None
    slice_location_lines_same_group_only_action: Optional[QAction] = None
    slice_location_lines_focused_only_action: Optional[QAction] = None
    slice_location_lines_show_slab_bounds_action: Optional[QAction] = None
    copy_annotation_action: Optional[QAction] = None
    paste_annotation_action: Optional[QAction] = None
    undo_tag_edit_action: Optional[QAction] = None
    redo_tag_edit_action: Optional[QAction] = None
    layout_1x1_action: Optional[QAction] = None
    layout_1x2_action: Optional[QAction] = None
    layout_2x1_action: Optional[QAction] = None
    layout_2x2_action: Optional[QAction] = None

    # Populated by ``build_main_toolbar`` (Optional until toolbar is built).
    main_toolbar: Optional[QToolBar] = None
    privacy_mode_action: Optional[QAction] = None
    scroll_wheel_mode_combo: Optional[QComboBox] = None
    mouse_mode_ellipse_roi_action: Optional[QAction] = None
    mouse_mode_rectangle_roi_action: Optional[QAction] = None
    mouse_mode_measure_action: Optional[QAction] = None
    mouse_mode_measure_angle_action: Optional[QAction] = None
    mouse_mode_text_annotation_action: Optional[QAction] = None
    mouse_mode_arrow_annotation_action: Optional[QAction] = None
    mouse_mode_crosshair_action: Optional[QAction] = None
    mouse_mode_zoom_action: Optional[QAction] = None
    mouse_mode_magnifier_action: Optional[QAction] = None
    mouse_mode_pan_action: Optional[QAction] = None
    mouse_mode_select_action: Optional[QAction] = None
    mouse_mode_auto_window_level_action: Optional[QAction] = None
    use_rescaled_values_action: Optional[QAction] = None
    series_navigator_action: Optional[QAction] = None
    prev_series_action: Optional[QAction] = None
    next_series_action: Optional[QAction] = None

    # Populated when series navigator bar is assembled (may stay None until then).
    window_slot_map_widget: Optional[WindowSlotMapWidget] = None
    series_navigator_container: Optional[QWidget] = None

    # Toast overlay (ephemeral QLabel + effects; cleared after fade).
    _toast_label: Optional[QLabel] = None
    _toast_effect: Optional[QGraphicsOpacityEffect] = None
    _toast_timer: Optional[QTimer] = None
    _toast_animation: Optional[QPropertyAnimation] = None

    # Note: Cine control signals moved to CineControlsWidget
    # Keeping these signals for backward compatibility but they're not used anymore
    
    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """
        Initialize the main window.
        
        Args:
            config_manager: Optional ConfigManager instance
        """
        super().__init__()
        
        self.config_manager = config_manager or ConfigManager()
        
        # Reference to image viewer (set by main.py after creation)
        self.image_viewer: Optional['ImageViewer'] = None

        # View → Fullscreen: in-memory snapshot only (never write fullscreen layout to config defaults)
        self._fullscreen_snapshot: Optional[Dict[str, Any]] = None
        self._fullscreen_transitioning = False
        
        # Window properties
        self.setWindowTitle("DICOM Viewer V3")
        # Set minimum height for laptop screens
        self.setMinimumHeight(600)
        self.setGeometry(100, 100, 
                        self.config_manager.get("window_width", 1200),
                        self.config_manager.get("window_height", 800))
        
        # Reset View action (shared by menu and toolbar to avoid ambiguous shortcuts)
        self.reset_view_action = QAction("&Reset View", self)
        self.reset_view_action.setToolTip("Reset zoom, pan, window/level to initial (V, Shift+V)")
        self.reset_view_action.setShortcuts([QKeySequence("V"), QKeySequence("Shift+V")])
        self.reset_view_action.triggered.connect(self.reset_view_requested.emit)
        
        # Create UI components
        self._create_menu_bar()
        self._create_toolbar()
        self._create_status_bar()
        self._create_central_widget()
        
        # Enable drag-and-drop on main window
        self.setAcceptDrops(True)
        
        # Apply theme
        self._apply_theme()
    
    def _create_menu_bar(self) -> None:
        """Create the application menu bar via the menu bar builder."""
        build_menu_bar(self)

    def _create_toolbar(self) -> None:
        """Create the application toolbar via the toolbar builder."""
        build_main_toolbar(self)

    def _create_status_bar(self) -> None:
        """Create the status bar."""
        # Create three permanent widgets with equal stretch factors (1:1:1) for fixed 1/3 widths
        # Left widget: File/study information
        self.file_study_label = QLabel("Ready")
        self.file_study_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.statusBar().addPermanentWidget(self.file_study_label, stretch=1)
        
        # Center widget: Zoom and window/level preset info
        self.zoom_preset_label = QLabel("")
        self.zoom_preset_label.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
        self.statusBar().addPermanentWidget(self.zoom_preset_label, stretch=1)
        
        # Right widget: Pixel values and coordinates
        self.pixel_info_label = QLabel("")
        self.pixel_info_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.statusBar().addPermanentWidget(self.pixel_info_label, stretch=1)

    def show_toast_message(
        self,
        message: str,
        timeout_ms: int = 5000,
        *,
        position: Literal["bottom-center", "center"] = "bottom-center",
        bg_alpha: float = 0.75,
    ) -> None:
        """
        Show a temporary toast/banner message over the main window.
        Auto-dismisses after timeout_ms, then fades out over 300 ms.

        Args:
            message: Text to display.
            timeout_ms: Time in milliseconds before starting fade-out (default 5000).
            position: ``bottom-center`` (default) or ``center`` of the main window
                client area (widget coordinates).
            bg_alpha: Background opacity for the toast panel, clamped to [0.0, 1.0].
        """
        if self._toast_timer is not None and self._toast_timer.isActive():
            self._toast_timer.stop()
        if self._toast_label is not None:
            self._toast_label.deleteLater()
        alpha = max(0.0, min(1.0, float(bg_alpha)))
        label = QLabel(message, self)
        label.setStyleSheet(
            f"background-color: rgba(0, 0, 0, {alpha}); color: white; padding: 10px 16px; "
            "border-radius: 6px; font-size: 14px;"
        )
        label.setWordWrap(True)
        label.setMinimumWidth(240)
        label.setMaximumWidth(480)
        label.adjustSize()
        effect = QGraphicsOpacityEffect(label)
        label.setGraphicsEffect(effect)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        x = (self.width() - label.width()) // 2
        if position == "center":
            y = (self.height() - label.height()) // 2
        else:
            y = self.height() - 100
        label.setGeometry(max(0, x), max(0, y), label.width(), label.height())
        label.show()
        label.raise_()
        self._toast_label = label
        self._toast_effect = effect

        def start_fade():
            self._toast_timer = None  # single-shot fired; allow new toasts to schedule again
            anim = QPropertyAnimation(effect, b"opacity")
            anim.setDuration(300)
            anim.setStartValue(1.0)
            anim.setEndValue(0.0)
            anim.finished.connect(lambda: (label.deleteLater(), setattr(self, "_toast_label", None)))
            anim.start()
            self._toast_animation = anim

        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(start_fade)
        self._toast_timer.start(timeout_ms)
    
    def _create_central_widget(self) -> None:
        """Create the central widget area."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Splitter for resizable panels
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(self.splitter)
        
        # Left panel (for metadata, series list, etc.) - Make scrollable
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        left_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        self.left_panel = QWidget()
        self.left_panel.setObjectName("left_panel")
        left_scroll.setWidget(self.left_panel)
        left_scroll.setMaximumWidth(600)
        left_scroll.setMinimumWidth(200)
        self.splitter.addWidget(left_scroll)
        
        # Center panel (for image viewer)
        self.center_panel = QWidget()
        self.center_panel.setObjectName("center_panel")
        self.splitter.addWidget(self.center_panel)
        
        # Right panel (for tools, histogram, etc.) - Make scrollable
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        right_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        self.right_panel = QWidget()
        self.right_panel.setObjectName("right_panel")
        right_scroll.setWidget(self.right_panel)
        right_scroll.setMaximumWidth(600)
        right_scroll.setMinimumWidth(200)
        self.splitter.addWidget(right_scroll)
        
        # Set splitter proportions - use saved positions or defaults
        default_left_width = 250
        default_right_width = 250
        saved_sizes = self.config_manager.get("splitter_sizes", None)
        if saved_sizes and isinstance(saved_sizes, list) and len(saved_sizes) == 3:
            self.splitter.setSizes(saved_sizes)
        else:
            # Calculate center width based on window size (default 1200px wide)
            window_width = self.config_manager.get("window_width", 1200)
            center_width = window_width - default_left_width - default_right_width
            self.splitter.setSizes([default_left_width, center_width, default_right_width])
        
        # Connect to splitter moved signal to update overlay positions when panels are resized
        # Also save splitter positions when moved
        self.splitter.splitterMoved.connect(self._on_splitter_moved)
        
        # Sync View menu pane toggle check state from actual sizes (e.g. restored saved layout with a pane hidden)
        if self.show_left_pane_action is not None:
            self.show_left_pane_action.setChecked(self.splitter.sizes()[0] > 0)
        if self.show_right_pane_action is not None:
            self.show_right_pane_action.setChecked(self.splitter.sizes()[2] > 0)
        
        # Series navigator (initially hidden, will be set by main.py)
        self.series_navigator = None  # Will be set by set_series_navigator method
        self.series_navigator_visible = False
    
    def _apply_theme(self) -> None:
        """Apply the current theme using pure stylesheet approach.

        Uses simplified, palette-like color scheme; stylesheet and viewer color
        are provided by gui.main_window_theme.
        """
        from gui.main_window_theme import get_theme_stylesheet, get_theme_viewer_background_color

        theme = self.config_manager.get_theme()

        # Set up resource search path for images using QDir.addSearchPath
        if getattr(sys, 'frozen', False):
            base_path = Path(cast(str, getattr(sys, "_MEIPASS")))
        else:
            base_path = Path(__file__).parent.parent.parent

        resources_dir = str((base_path / "resources" / "images").resolve())
        QDir.addSearchPath('images', resources_dir)

        white_checkmark_path = "images:checkbox_checkmark_white.png"
        black_checkmark_path = "images:checkbox_checkmark_black.png"

        stylesheet = get_theme_stylesheet(theme, white_checkmark_path, black_checkmark_path)

        if self.image_viewer is not None:
            self.image_viewer.set_background_color(get_theme_viewer_background_color(theme))

        app_instance = QApplication.instance()
        if isinstance(app_instance, QApplication):
            app_instance.setStyleSheet(stylesheet)
        QApplication.processEvents()

    def _set_theme(self, theme: str) -> None:
        """
        Set the application theme.

        Ensures theme actions are mutually exclusive and saves preference.

        Args:
            theme: Theme name ("light" or "dark")
        """
        # Update action states to ensure exclusivity
        if self.light_theme_action is not None and self.dark_theme_action is not None:
            if theme == "light":
                self.light_theme_action.setChecked(True)
                self.dark_theme_action.setChecked(False)
            else:  # dark
                self.light_theme_action.setChecked(False)
                self.dark_theme_action.setChecked(True)

        # Save to config and apply
        self.config_manager.set_theme(theme)
        self._apply_theme()
        # Emit signal to notify other components
        self.theme_changed.emit(theme)

    def _on_privacy_view_toggled(self, checked: bool) -> None:
        """
        Handle privacy view toggle.
        
        Args:
            checked: True if privacy view is enabled, False otherwise
        """
        # Save to config
        self.config_manager.set_privacy_view(checked)
        # Emit signal to notify other components
        self.privacy_view_toggled.emit(checked)
        # Update toolbar button appearance
        self._update_privacy_mode_button()
    
    def _on_privacy_mode_button_clicked(self) -> None:
        """Handle privacy mode button click - toggle privacy mode."""
        # Get current state from config
        current_state = self.config_manager.get_privacy_view()
        # Toggle it
        new_state = not current_state
        # Update via the existing handler
        self._on_privacy_view_toggled(new_state)

    def _on_smooth_when_zoomed_toggled(self, checked: bool) -> None:
        """
        Handle smooth-when-zoomed toggle from View menu or context menu.

        Args:
            checked: True if smooth when zoomed is enabled, False otherwise
        """
        self.config_manager.set_smooth_image_when_zoomed(checked)
        self.smooth_when_zoomed_toggled.emit(checked)

    def _on_scale_markers_toggled(self, checked: bool) -> None:
        """
        Handle scale markers toggle from View menu or context menu.

        Args:
            checked: True if scale markers are enabled, False otherwise
        """
        self.config_manager.set_show_scale_markers(checked)
        self.scale_markers_toggled.emit(checked)

    def _on_direction_labels_toggled(self, checked: bool) -> None:
        """
        Handle direction labels toggle from View menu or context menu.

        Args:
            checked: True if direction labels are enabled, False otherwise
        """
        self.config_manager.set_show_direction_labels(checked)
        self.direction_labels_toggled.emit(checked)

    def set_smooth_when_zoomed_checked(self, checked: bool) -> None:
        """Sync the View menu Image Smoothing action check state without emitting triggered."""
        if self.smooth_when_zoomed_action is None:
            return
        self.smooth_when_zoomed_action.blockSignals(True)
        self.smooth_when_zoomed_action.setChecked(checked)
        self.smooth_when_zoomed_action.blockSignals(False)

    def set_scale_markers_checked(self, checked: bool) -> None:
        """Sync the View menu Show Scale Markers action check state without emitting triggered."""
        if self.scale_markers_action is None:
            return
        self.scale_markers_action.blockSignals(True)
        self.scale_markers_action.setChecked(checked)
        self.scale_markers_action.blockSignals(False)

    def set_direction_labels_checked(self, checked: bool) -> None:
        """Sync the View menu Show Direction Labels action check state without emitting triggered."""
        if self.direction_labels_action is None:
            return
        self.direction_labels_action.blockSignals(True)
        self.direction_labels_action.setChecked(checked)
        self.direction_labels_action.blockSignals(False)

    def set_slice_slider_checked(self, checked: bool) -> None:
        """Sync the View menu Show In-View Slice/Frame Slider action check state without emitting triggered."""
        if self.slice_slider_action is None:
            return
        self.slice_slider_action.blockSignals(True)
        self.slice_slider_action.setChecked(checked)
        self.slice_slider_action.blockSignals(False)

    def _on_show_instances_separately_toggled(self, checked: bool) -> None:
        """Handle the View menu toggle for multi-frame instance expansion."""
        self.config_manager.set_show_instances_separately(checked)
        self.show_instances_separately_toggled.emit(checked)

    def set_show_instances_separately_checked(self, checked: bool) -> None:
        """Sync the View menu Show Instances Separately action check state without emitting triggered."""
        if self.show_instances_separately_action is None:
            return
        self.show_instances_separately_action.blockSignals(True)
        self.show_instances_separately_action.setChecked(checked)
        self.show_instances_separately_action.blockSignals(False)

    def set_show_instances_separately_enabled(self, enabled: bool) -> None:
        """Enable or disable the View menu Show Instances Separately action."""
        if self.show_instances_separately_action is None:
            return
        self.show_instances_separately_action.setEnabled(enabled)

    def set_slice_location_lines_checked(self, checked: bool) -> None:
        """Sync the View menu Show Slice Location Lines → Enable/Disable action check state without emitting triggered."""
        if self.slice_location_lines_enable_action is None:
            return
        self.slice_location_lines_enable_action.blockSignals(True)
        self.slice_location_lines_enable_action.setChecked(checked)
        self.slice_location_lines_enable_action.blockSignals(False)

    def set_slice_location_lines_same_group_only_checked(self, checked: bool) -> None:
        """Sync the View menu Show Slice Location Lines → Only Show For Same Group action check state without emitting triggered."""
        if self.slice_location_lines_same_group_only_action is None:
            return
        self.slice_location_lines_same_group_only_action.blockSignals(True)
        self.slice_location_lines_same_group_only_action.setChecked(checked)
        self.slice_location_lines_same_group_only_action.blockSignals(False)

    def set_slice_location_lines_focused_only_checked(self, checked: bool) -> None:
        """Sync the View menu Show Slice Location Lines → Show Only For Focused Window action check state without emitting triggered."""
        if self.slice_location_lines_focused_only_action is None:
            return
        self.slice_location_lines_focused_only_action.blockSignals(True)
        self.slice_location_lines_focused_only_action.setChecked(checked)
        self.slice_location_lines_focused_only_action.blockSignals(False)

    def set_slice_location_lines_slab_bounds_checked(self, mode: str) -> None:
        """Sync the View menu slab-bounds action check state without emitting triggered.

        Args:
            mode: "middle" or "begin_end".  Action is checked when mode == "begin_end".
        """
        if self.slice_location_lines_show_slab_bounds_action is None:
            return
        self.slice_location_lines_show_slab_bounds_action.blockSignals(True)
        self.slice_location_lines_show_slab_bounds_action.setChecked(mode == "begin_end")
        self.slice_location_lines_show_slab_bounds_action.blockSignals(False)

    def _update_privacy_mode_button(self) -> None:
        """Update privacy mode button text and appearance based on current state."""
        if not hasattr(self, 'privacy_mode_action'):
            return
        
        privacy_enabled = self.config_manager.get_privacy_view()
        
        if privacy_enabled:
            # Privacy is ON - button should say "Privacy is ON" and not be highlighted
            self.privacy_mode_action.setText("Privacy is ON")
            self.privacy_mode_action.setChecked(False)
            # Remove red highlighting
            if hasattr(self, 'main_toolbar'):
                for tool_button in self.main_toolbar.findChildren(QToolButton):
                    if tool_button.defaultAction() == self.privacy_mode_action:
                        tool_button.setStyleSheet("")
                        break
        else:
            # Privacy is OFF - button should say "Privacy is OFF" and be highlighted in red
            self.privacy_mode_action.setText("Privacy is OFF")
            self.privacy_mode_action.setChecked(True)
            # Apply red background highlighting
            if hasattr(self, 'main_toolbar'):
                for tool_button in self.main_toolbar.findChildren(QToolButton):
                    if tool_button.defaultAction() == self.privacy_mode_action:
                        tool_button.setStyleSheet("background-color: #ff0000; font-weight: bold;")
                        break
    
    def _show_disclaimer(self) -> None:
        """Show the disclaimer dialog."""
        from gui.dialogs.disclaimer_dialog import DisclaimerDialog
        DisclaimerDialog.show_disclaimer(self.config_manager, self, force_show=True)
    
    def _on_about_disclaimer_clicked(self, url) -> None:
        """
        Handle disclaimer link click in About dialog.
        
        Args:
            url: QUrl of the clicked link
        """
        if url.scheme() == "disclaimer":
            self._show_disclaimer()
    
    def _show_about(self) -> None:
        """Show the about dialog with scrollable content."""
        dialog = QDialog(self)
        dialog.setWindowTitle("About DICOM Viewer V3")
        dialog.setMinimumSize(500, 400)
        dialog.resize(600, 500)
        
        # Apply theme-based styling to dialog
        theme = self.config_manager.get_theme()
        if theme == "dark":
            # Set dark grey background for dark theme (matches left panel)
            dialog.setStyleSheet("QDialog { background-color: #2b2b2b; }")
        else:
            # Light theme - use white
            dialog.setStyleSheet("QDialog { background-color: #ffffff; }")
        
        layout = QVBoxLayout(dialog)
        
        # Create scrollable text area - use QTextBrowser for anchor link support
        text_edit = QTextBrowser()
        text_edit.setOpenExternalLinks(False)  # Don't open external links in browser
        text_edit.setReadOnly(True)
        # Set QTextBrowser background to match metadata panel in dark theme
        if theme == "dark":
            text_edit.setStyleSheet("QTextBrowser { background-color: #1e1e1e; }")
        
        # Load icon and convert to base64 for HTML embedding
        icon_html = ""
        icon_path = Path(__file__).parent.parent.parent / 'resources' / 'icons' / 'dvv6ldvv6ldvv6ld_edit-removebg-preview.png'
        if icon_path.exists():
            pixmap = QPixmap(str(icon_path))
            # Scale icon to reasonable size (96x96 pixels for inline display)
            scaled_pixmap = pixmap.scaled(96, 96, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            # Convert to base64 for HTML embedding
            buffer = QBuffer()
            buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            scaled_pixmap.save(buffer, "PNG")
            icon_data = bytes(buffer.data().toBase64().data()).decode("ascii")
            icon_html = f'<img src="data:image/png;base64,{icon_data}" style="vertical-align: middle; margin-right: 10px;" />'
        
        # Create HTML content with theme-based link styling
        if theme == "dark":
            link_color = "#4a9eff"  # Light blue for dark theme
        else:
            link_color = "#2980b9"  # Darker blue for light theme
        
        html_content = f"""<html>
<head>
    <style>
        a {{ color: {link_color}; }}
    </style>
</head>
<body>
    <h2>{icon_html}Medical Physics DICOM Viewer</h2>
    <p><b>Version {APP_VERSION}</b></p>
    <p><b>Made by Kevin Grizzard</b><br>
    Available at <a href='https://github.com/kgrizz-git/DICOMViewerV3'>https://github.com/kgrizz-git/DICOMViewerV3</a></p>
    <hr>
    <p>A cross-platform DICOM viewer application.</p>
    <h3>Features:</h3>
    <h4>File Management:</h4>
    <ul>
    <li>Open DICOM files and folders</li>
    <li>Recursive folder search</li>
    <li>Multiple file selection</li>
    <li>Recent files support</li>
    </ul>
    <h4>Image Display:</h4>
    <ul>
    <li>Zoom and pan functionality</li>
    <li>Window width and level adjustment</li>
    <li>Window/Level presets: Multiple presets from DICOM tags with context menu switching</li>
    <li>Slice navigation (arrow keys, mouse wheel)</li>
    <li>Series navigation with thumbnail navigator</li>
    <li>Dark and light themes</li>
    <li>Reset view to fit viewport</li>
    <li>Intensity projections: Combine slices (AIP, MIP, MinIP)</li>
    <li>Image inversion (I key)</li>
    <li>Cine Playback: Automatic frame-by-frame playback for multi-frame DICOM series with a play/pause toggle, stop, adjustable speed, and loop option</li>
    <li>Image Fusion: Overlay functional imaging (PET/SPECT) on anatomical imaging (CT/MR) with automatic spatial alignment, adjustable opacity/threshold/colormap, and 2D/3D resampling modes</li>
    </ul>
    <h4>Analysis Tools:</h4>
    <ul>
    <li>Draw elliptical and rectangular ROIs</li>
    <li>ROI statistics (mean, std dev, min, max, area)</li>
    <li>Distance measurements (pixels, mm, cm)</li>
    <li>Text annotations: Add and edit text labels on images</li>
    <li>Arrow annotations: Add arrows to point to features</li>
    <li>Histogram display: View pixel value distribution with window/level overlay (Cmd+Shift+H / Ctrl+Shift+H)</li>
    <li>Undo/redo functionality</li>
    </ul>
    <h4>Metadata and Overlays:</h4>
    <ul>
    <li>Customizable DICOM metadata overlays</li>
    <li>Toggle overlay visibility (3 states)</li>
    <li>View and edit all DICOM tags</li>
    <li>Tag filtering/search functionality</li>
    <li>Expand/collapse tag groups in metadata panel</li>
    <li>Reorder columns in metadata panel</li>
    <li>Privacy View: Toggle to mask patient-related tags in display (View menu, context menu, or Cmd+P/Ctrl+P)</li>
    <li>Anonymization on Export: Option to anonymize patient information when exporting to DICOM</li>
    <li>Export selected tags to Excel/CSV</li>
    <li>Annotations support: Presentation States, Key Objects, embedded overlays</li>
    </ul>
    <h4>Data Management:</h4>
    <ul>
    <li>Clear ROIs from slice or dataset</li>
    <li>Clear measurements</li>
    <li>ROI list panel with selection</li>
    </ul>
    <h4>Export:</h4>
    <ul>
    <li>Export images as PNG, JPEG, or DICOM</li>
    <li>Hierarchical selection (studies, series, slices)</li>
    <li>Include overlays, ROIs, and measurements</li>
    <li>Export at displayed resolution option</li>
    <li>Export selected DICOM tags to Excel/CSV</li>
    <li>Export/Import Customizations: Save and share overlay config, annotation options, metadata panel settings, and theme as JSON files</li>
    </ul>
    <hr>
    <p><a href="disclaimer://show">View Disclaimer</a></p>
</body>
</html>"""
        
        text_edit.setHtml(html_content)
        # Handle disclaimer link click
        text_edit.anchorClicked.connect(self._on_about_disclaimer_clicked)
        layout.addWidget(text_edit)
        
        # Add OK button
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(dialog.accept)
        layout.addWidget(button_box)
        
        dialog.exec()
    
    def _on_mouse_mode_changed(self, mode: str) -> None:
        """
        Handle mouse mode change to ensure exclusivity.
        
        Args:
            mode: Mouse mode ("select", "roi_ellipse", "roi_rectangle", "measure", "zoom", "magnifier", "pan", "auto_window_level")
        """
        # Uncheck all actions first
        all_actions = [
            self.mouse_mode_select_action,
            self.mouse_mode_ellipse_roi_action,
            self.mouse_mode_rectangle_roi_action,
            self.mouse_mode_measure_action,
            self.mouse_mode_measure_angle_action,
            self.mouse_mode_text_annotation_action,
            self.mouse_mode_arrow_annotation_action,
            self.mouse_mode_crosshair_action,
            self.mouse_mode_zoom_action,
            self.mouse_mode_magnifier_action,
            self.mouse_mode_pan_action,
            self.mouse_mode_auto_window_level_action
        ]
        
        # Block signals when updating toolbar buttons to prevent recursive loops
        # This prevents setChecked() from triggering the action's triggered signal
        for action in all_actions:
            action.blockSignals(True)
        
        # Uncheck all actions
        for action in all_actions:
            action.setChecked(False)
        
        # Check the action corresponding to the selected mode
        if mode == "select":
            self.mouse_mode_select_action.setChecked(True)
        elif mode == "roi_ellipse":
            self.mouse_mode_ellipse_roi_action.setChecked(True)
        elif mode == "roi_rectangle":
            self.mouse_mode_rectangle_roi_action.setChecked(True)
        elif mode == "measure":
            self.mouse_mode_measure_action.setChecked(True)
        elif mode == "measure_angle":
            self.mouse_mode_measure_angle_action.setChecked(True)
        elif mode == "text_annotation":
            self.mouse_mode_text_annotation_action.setChecked(True)
        elif mode == "arrow_annotation":
            self.mouse_mode_arrow_annotation_action.setChecked(True)
        elif mode == "crosshair":
            self.mouse_mode_crosshair_action.setChecked(True)
        elif mode == "zoom":
            self.mouse_mode_zoom_action.setChecked(True)
        elif mode == "magnifier":
            self.mouse_mode_magnifier_action.setChecked(True)
        elif mode == "pan":
            self.mouse_mode_pan_action.setChecked(True)
        elif mode == "auto_window_level":
            self.mouse_mode_auto_window_level_action.setChecked(True)
        
        # Unblock signals after updating toolbar buttons
        for action in all_actions:
            action.blockSignals(False)
        
        # Emit signal AFTER updating toolbar buttons to actually change the mode
        self.mouse_mode_changed.emit(mode)
    
    def get_current_mouse_mode(self) -> str:
        """
        Get the current mouse mode from toolbar.
        
        Returns:
            Current mouse mode string ("select", "roi_ellipse", "roi_rectangle", "measure", "text_annotation", "arrow_annotation", "zoom", "pan", "auto_window_level")
        """
        if self.mouse_mode_select_action.isChecked():
            return "select"
        elif self.mouse_mode_ellipse_roi_action.isChecked():
            return "roi_ellipse"
        elif self.mouse_mode_rectangle_roi_action.isChecked():
            return "roi_rectangle"
        elif self.mouse_mode_measure_action.isChecked():
            return "measure"
        elif self.mouse_mode_measure_angle_action.isChecked():
            return "measure_angle"
        elif self.mouse_mode_text_annotation_action.isChecked():
            return "text_annotation"
        elif self.mouse_mode_arrow_annotation_action.isChecked():
            return "arrow_annotation"
        elif self.mouse_mode_crosshair_action.isChecked():
            return "crosshair"
        elif self.mouse_mode_zoom_action.isChecked():
            return "zoom"
        elif self.mouse_mode_magnifier_action.isChecked():
            return "magnifier"
        elif self.mouse_mode_auto_window_level_action.isChecked():
            return "auto_window_level"
        else:  # pan is default
            return "pan"
    
    def set_mouse_mode_checked(self, mode: str) -> None:
        """
        Update toolbar buttons to reflect the current mouse mode without emitting signals.
        
        This method is used when the mouse mode is changed programmatically (e.g., via keyboard shortcut)
        and we only need to update the toolbar UI without triggering signal emissions.
        
        Args:
            mode: Mouse mode ("select", "roi_ellipse", "roi_rectangle", "measure", "zoom", "magnifier", "pan", "auto_window_level")
        """
        # All mouse mode actions
        all_actions = [
            self.mouse_mode_select_action,
            self.mouse_mode_ellipse_roi_action,
            self.mouse_mode_rectangle_roi_action,
            self.mouse_mode_measure_action,
            self.mouse_mode_measure_angle_action,
            self.mouse_mode_text_annotation_action,
            self.mouse_mode_arrow_annotation_action,
            self.mouse_mode_crosshair_action,
            self.mouse_mode_zoom_action,
            self.mouse_mode_magnifier_action,
            self.mouse_mode_pan_action,
            self.mouse_mode_auto_window_level_action
        ]
        
        # Block signals when updating toolbar buttons
        for action in all_actions:
            action.blockSignals(True)
        
        # Uncheck all actions
        for action in all_actions:
            action.setChecked(False)
        
        # Check the action corresponding to the selected mode
        if mode == "select":
            self.mouse_mode_select_action.setChecked(True)
        elif mode == "roi_ellipse":
            self.mouse_mode_ellipse_roi_action.setChecked(True)
        elif mode == "roi_rectangle":
            self.mouse_mode_rectangle_roi_action.setChecked(True)
        elif mode == "measure":
            self.mouse_mode_measure_action.setChecked(True)
        elif mode == "measure_angle":
            self.mouse_mode_measure_angle_action.setChecked(True)
        elif mode == "text_annotation":
            self.mouse_mode_text_annotation_action.setChecked(True)
        elif mode == "arrow_annotation":
            self.mouse_mode_arrow_annotation_action.setChecked(True)
        elif mode == "crosshair":
            self.mouse_mode_crosshair_action.setChecked(True)
        elif mode == "zoom":
            self.mouse_mode_zoom_action.setChecked(True)
        elif mode == "magnifier":
            self.mouse_mode_magnifier_action.setChecked(True)
        elif mode == "pan":
            self.mouse_mode_pan_action.setChecked(True)
        elif mode == "auto_window_level":
            self.mouse_mode_auto_window_level_action.setChecked(True)
        
        # Unblock signals after updating toolbar buttons
        for action in all_actions:
            action.blockSignals(False)
    
    def _on_scroll_wheel_mode_combo_changed(self, text: str) -> None:
        """
        Handle scroll wheel mode combo box change.
        
        Args:
            text: Selected text ("Slice" or "Zoom")
        """
        mode = "slice" if text == "Slice" else "zoom"
        self.scroll_wheel_mode_changed.emit(mode)
    
    def _on_font_size_decrease(self) -> None:
        """Handle font size decrease button click."""
        current_size = self.config_manager.get_overlay_font_size()
        new_size = max(1, current_size - 1)  # Minimum is 1pt
        if new_size != current_size:
            self.config_manager.set_overlay_font_size(new_size)
            self.overlay_font_size_changed.emit(new_size)
    
    def _on_font_size_increase(self) -> None:
        """Handle font size increase button click."""
        current_size = self.config_manager.get_overlay_font_size()
        new_size = min(24, current_size + 1)  # Maximum is 24pt
        if new_size != current_size:
            self.config_manager.set_overlay_font_size(new_size)
            self.overlay_font_size_changed.emit(new_size)
    
    def _on_font_color_picker(self) -> None:
        """Handle font color picker button click."""
        # Get current color from config
        current_color = self.config_manager.get_overlay_font_color()
        qcolor = QColor(current_color[0], current_color[1], current_color[2])
        
        # Open color dialog
        color = QColorDialog.getColor(qcolor, self, "Select Overlay Font Color")
        
        if color.isValid():
            # Save to config and emit signal
            self.config_manager.set_overlay_font_color(color.red(), color.green(), color.blue())
            self.overlay_font_color_changed.emit(color.red(), color.green(), color.blue())

    def _on_scale_markers_color_picker(self) -> None:
        """Handle scale markers color picker menu action."""
        current_color = self.config_manager.get_scale_markers_color()
        qcolor = QColor(current_color[0], current_color[1], current_color[2])
        color = QColorDialog.getColor(qcolor, self, "Select Scale Markers Color")
        if color.isValid():
            self.config_manager.set_scale_markers_color(color.red(), color.green(), color.blue())
            self.scale_markers_color_changed.emit(color.red(), color.green(), color.blue())

    def _on_direction_labels_color_picker(self) -> None:
        """Handle direction labels color picker menu action."""
        current_color = self.config_manager.get_direction_labels_color()
        qcolor = QColor(current_color[0], current_color[1], current_color[2])
        color = QColorDialog.getColor(qcolor, self, "Select Direction Labels Color")
        if color.isValid():
            self.config_manager.set_direction_labels_color(color.red(), color.green(), color.blue())
            self.direction_labels_color_changed.emit(color.red(), color.green(), color.blue())
    
    def _on_rescale_toggle_changed(self) -> None:
        """Handle rescale toggle button click."""
        # Determine new state based on current text
        # If text is "Use Raw Pixel Values", we're currently using rescaled, so toggle to raw (False)
        # If text is "Use Rescaled Values", we're currently using raw, so toggle to rescaled (True)
        current_text = self.use_rescaled_values_action.text()
        new_state = (current_text == "Use Rescaled Values")  # True if switching to rescaled, False if switching to raw
        # Emit signal with new state
        self.rescale_toggle_changed.emit(new_state)
    
    def set_rescale_toggle_state(self, checked: bool) -> None:
        """
        Set the rescale toggle button text based on current state.
        
        Args:
            checked: True if using rescaled values, False if using raw values
        """
        self.use_rescaled_values_action.blockSignals(True)
        # Update button text based on current state
        # When checked=True (using rescaled), show "Use Raw Pixel Values"
        # When checked=False (using raw), show "Use Rescaled Values"
        if checked:
            self.use_rescaled_values_action.setText("Use Raw Pixel Values")
        else:
            self.use_rescaled_values_action.setText("Use Rescaled Values")
        self.use_rescaled_values_action.blockSignals(False)
    
    def _on_prev_series(self) -> None:
        """Handle previous series button click."""
        self.series_navigation_requested.emit(-1)
    
    def _on_next_series(self) -> None:
        """Handle next series button click."""
        self.series_navigation_requested.emit(1)
    
    def _update_recent_menu(self) -> None:
        """Update the Recent Files submenu with current recent files."""
        if self.recent_menu is None:
            return
        # Clear existing actions
        self.recent_menu.clear()
        
        # Get recent files from config
        recent_files = self.config_manager.get_recent_files()
        
        if not recent_files:
            # Show "No recent files" if empty
            no_recent_action = QAction("No recent files", self)
            no_recent_action.setEnabled(False)
            self.recent_menu.addAction(no_recent_action)
        else:
            # Add action for each recent file using regular QAction for native appearance
            for file_path in recent_files:
                # Create display name (truncate if too long)
                display_name = os.path.basename(file_path)
                
                # Handle edge case where basename returns empty string
                # (e.g., root directory, trailing slashes, etc.)
                if not display_name:
                    # Use the full path as fallback (truncated if needed)
                    display_name = file_path
                    if len(display_name) > 50:
                        display_name = display_name[:47] + "..."
                    
                    # If path is root directory or still empty, use default label
                    if not display_name or display_name in (os.path.sep, "/"):
                        display_name = "Folder" if os.path.isdir(file_path) else "File"
                else:
                    # Normal basename case - truncate if too long
                    if len(display_name) > 50:
                        display_name = display_name[:47] + "..."
                
                # Create regular QAction with just the display name (no prefixes)
                recent_action = QAction(display_name, self)
                # Store file path in action data for event filter
                recent_action.setData(file_path)
                # Connect triggered signal to open the file
                recent_action.triggered.connect(
                    lambda checked, path=file_path: self.open_recent_file_requested.emit(path)
                )
                self.recent_menu.addAction(recent_action)
    
    def eventFilter(self, obj, event) -> bool:
        """
        Event filter for handling context menu events on recent menu items.
        
        Args:
            obj: Object that received the event
            event: Event
            
        Returns:
            True if event was handled, False otherwise
        """
        from PySide6.QtGui import QContextMenuEvent
        
        # Only handle events for the recent menu
        if self.recent_menu is None or obj != self.recent_menu:
            return super().eventFilter(obj, event)
        
        # Check if it's a context menu event (right-click)
        if event.type() == QEvent.Type.ContextMenu:
            context_event = QContextMenuEvent(event)
            # Get the action at the mouse position
            action = self.recent_menu.actionAt(self.recent_menu.mapFromGlobal(context_event.globalPos()))
            
            # Only show context menu if it's a recent file action (has data)
            if action is not None and action.data():
                file_path = action.data()
                recent_files = self.config_manager.get_recent_files()
                file_idx = recent_files.index(file_path) if file_path in recent_files else -1

                # Create context menu
                context_menu = QMenu(self)

                move_up_action = QAction("Move Up", self)
                move_up_action.setEnabled(file_idx > 0)
                move_up_action.triggered.connect(
                    lambda checked=False, fp=file_path: self._move_recent_file(fp, direction="up")
                )
                context_menu.addAction(move_up_action)

                move_down_action = QAction("Move Down", self)
                move_down_action.setEnabled(0 <= file_idx < len(recent_files) - 1)
                move_down_action.triggered.connect(
                    lambda checked=False, fp=file_path: self._move_recent_file(fp, direction="down")
                )
                context_menu.addAction(move_down_action)

                context_menu.addSeparator()

                remove_action = QAction("Remove", self)
                remove_action.triggered.connect(
                    lambda checked=False, fp=file_path: self._remove_recent_file(fp)
                )
                context_menu.addAction(remove_action)

                # Show context menu at the cursor position
                context_menu.exec(context_event.globalPos())
                return True
        
        return super().eventFilter(obj, event)
    
    def _remove_recent_file(self, file_path: str) -> None:
        """
        Remove a file from recent files list.
        
        Args:
            file_path: Path to file or folder to remove
        """
        self.config_manager.remove_recent_file(file_path)
        self._update_recent_menu()

    def _move_recent_file(self, file_path: str, direction: str) -> None:
        """
        Move a recent file one position up or down in the recent files list.

        Args:
            file_path: Path of the recent file entry to move
            direction: "up" to move toward the top, "down" to move toward the bottom
        """
        if direction == "up":
            self.config_manager.move_recent_file_up(file_path)
        else:
            self.config_manager.move_recent_file_down(file_path)
        self._update_recent_menu()

    def update_recent_menu(self) -> None:
        """
        Public method to update recent menu (called from outside).
        """
        self._update_recent_menu()
    
    def _open_edit_recent_list_dialog(self) -> None:
        """
        Open the Edit Recent List dialog.
        """
        dialog = EditRecentListDialog(self.config_manager, self)
        dialog.exec()
        # Update the recent menu after dialog closes (in case items were removed)
        self._update_recent_menu()
    
    def _on_splitter_moved(self, pos: int, index: int) -> None:
        """
        Handle splitter movement.
        
        When the splitter moves, the viewport size changes, so we need to
        update overlay positions to keep them anchored to viewport edges.
        Also save the splitter positions for persistence.
        
        Args:
            pos: New position of the splitter handle
            index: Index of the splitter handle that moved
        """
        # Emit signal to capture scene center before viewport resizes
        # This allows preserving the centered view during resize
        self.viewport_resizing.emit()
        
        # Save splitter positions (skip while true fullscreen — chrome is forced narrow; do not persist that)
        sizes = self.splitter.sizes()
        if not self.isFullScreen():
            self.config_manager.set("splitter_sizes", sizes)
            self.config_manager.save_config()
        
        # Sync View menu pane toggle check state when user drags splitter to 0 or expands
        if self.show_left_pane_action is not None:
            self.show_left_pane_action.setChecked(sizes[0] > 0)
        if self.show_right_pane_action is not None:
            self.show_right_pane_action.setChecked(sizes[2] > 0)
        
        # Emit signal to notify that viewport size changed
        # Use QTimer to batch rapid splitter movements
        from PySide6.QtCore import QTimer
        QTimer.singleShot(10, lambda: self.viewport_resized.emit())
    
    def _toggle_left_pane(self) -> None:
        """
        Toggle left pane visibility: hide (width 0) if visible, show at default 250px if hidden.
        Saves splitter_sizes and syncs View menu check state.
        """
        from PySide6.QtCore import QTimer
        sizes = self.splitter.sizes()
        left, center, right = sizes[0], sizes[1], sizes[2]
        if left > 0:
            self.splitter.setSizes([0, center + left, right])
        else:
            self.splitter.setSizes([250, max(0, center - 250), right])
        new_sizes = self.splitter.sizes()
        self.config_manager.set("splitter_sizes", new_sizes)
        self.config_manager.save_config()
        self.viewport_resizing.emit()
        QTimer.singleShot(10, lambda: self.viewport_resized.emit())
        if self.show_left_pane_action is not None:
            self.show_left_pane_action.setChecked(new_sizes[0] > 0)
    
    def _toggle_right_pane(self) -> None:
        """
        Toggle right pane visibility: hide (width 0) if visible, show at default 250px if hidden.
        Saves splitter_sizes and syncs View menu check state.
        """
        from PySide6.QtCore import QTimer
        sizes = self.splitter.sizes()
        left, center, right = sizes[0], sizes[1], sizes[2]
        if right > 0:
            self.splitter.setSizes([left, center + right, 0])
        else:
            self.splitter.setSizes([left, max(0, center - 250), 250])
        new_sizes = self.splitter.sizes()
        self.config_manager.set("splitter_sizes", new_sizes)
        self.config_manager.save_config()
        self.viewport_resizing.emit()
        QTimer.singleShot(10, lambda: self.viewport_resized.emit())
        if self.show_right_pane_action is not None:
            self.show_right_pane_action.setChecked(new_sizes[2] > 0)
    
    def update_status(self, message: str) -> None:
        """
        Update the status bar message.
        
        Args:
            message: Status message to display
        """
        self.file_study_label.setText(message)
    
    def update_zoom_preset_status(self, zoom: float, preset_name: Optional[str] = None) -> None:
        """
        Update the zoom and window/level preset status in the center of the status bar.
        
        Args:
            zoom: Current zoom level
            preset_name: Name of the window/level preset, or None if using auto-calculated values
        """
        if preset_name is not None:
            status_text = f"Zoom = {zoom:.1f}, Window/Level Preset = {preset_name}"
        else:
            status_text = f"Zoom = {zoom:.1f}, Window/Level Preset = Auto-Calculated"
        self.zoom_preset_label.setText(status_text)
    
    def update_undo_redo_state(self, can_undo: bool, can_redo: bool) -> None:
        """
        Update the enabled state of undo/redo menu items.
        
        Args:
            can_undo: True if undo is possible
            can_redo: True if redo is possible
        """
        if self.undo_tag_edit_action is not None:
            self.undo_tag_edit_action.setEnabled(can_undo)
        if self.redo_tag_edit_action is not None:
            self.redo_tag_edit_action.setEnabled(can_redo)
    
    def set_series_navigator(self, navigator_widget: QWidget) -> None:
        """
        Set the series navigator widget.
        
        Args:
            navigator_widget: SeriesNavigator widget instance
        """
        self.series_navigator = navigator_widget
        # Get the main layout from central widget
        central_widget = self.centralWidget()
        if central_widget:
            main_layout = central_widget.layout()
            if main_layout:
                # Create a container bar so we can place the navigator on the left
                # and the window-slot thumbnail on the right.
                container = QWidget(central_widget)
                container.setObjectName("series_navigator_bar")
                bar_layout = QHBoxLayout(container)
                bar_layout.setContentsMargins(0, 0, 0, 0)
                bar_layout.setSpacing(4)

                # Keep the bar compact in height so it doesn't dominate 1x1/1x2 layouts.
                container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

                # Navigator on the left (stretch to take remaining space)
                navigator_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                bar_layout.addWidget(navigator_widget, 1)

                # Window slot map thumbnail on the right
                self.window_slot_map_widget = WindowSlotMapWidget(container)
                self.window_slot_map_widget.setObjectName("window_slot_map_widget")
                bar_layout.addWidget(self.window_slot_map_widget, 0)

                # Add bar to bottom of main layout
                main_layout.addWidget(container)

                # Initially hide whole bar
                container.setVisible(False)
                self.series_navigator_container = container
                self.series_navigator_visible = False
    
    def toggle_navigator_slice_frame_count_badge(self, checked: bool) -> None:
        """Persist and apply navigator slice/frame count badges on series thumbnails."""
        self.config_manager.set_navigator_show_slice_frame_count(bool(checked))
        nav = self.series_navigator
        if nav is not None and hasattr(nav, "set_show_slice_frame_count_badge"):
            nav.set_show_slice_frame_count_badge(bool(checked))

    def toggle_series_navigator(self) -> None:
        """Toggle series navigator visibility."""
        if self.series_navigator is None:
            return
        
        # Emit viewport_resizing before change to preserve centering
        self.viewport_resizing.emit()
        
        # Toggle visibility of the container bar (navigator + thumbnail)
        self.series_navigator_visible = not self.series_navigator_visible
        container = getattr(self, "series_navigator_container", None)
        if container is not None:
            container.setVisible(self.series_navigator_visible)
        else:
            # Fallback for safety: toggle navigator alone if container missing
            self.series_navigator.setVisible(self.series_navigator_visible)

        # Sync View menu check state
        if self.show_series_navigator_action is not None:
            self.show_series_navigator_action.setChecked(self.series_navigator_visible)
        self.series_navigator_visibility_changed.emit(self.series_navigator_visible)

    def _take_fullscreen_snapshot(self) -> Dict[str, Any]:
        """Capture splitter sizes, navigator bar, and toolbar visibility before entering fullscreen."""
        container = getattr(self, "series_navigator_container", None)
        bar_visible = bool(container.isVisible()) if container is not None else False
        toolbar_vis = self.main_toolbar.isVisible() if hasattr(self, "main_toolbar") else True
        return {
            "splitter_sizes": list(self.splitter.sizes()),
            "series_navigator_bar_visible": bar_visible,
            "toolbar_visible": toolbar_vis,
            "was_maximized": self.isMaximized(),
        }

    def _apply_fullscreen_chrome_hidden(self) -> None:
        """Collapse side panes, hide bottom navigator bar and main toolbar (no config persist)."""
        sizes = self.splitter.sizes()
        total = max(sizes[0] + sizes[1] + sizes[2], 1)
        self.viewport_resizing.emit()
        self.splitter.setSizes([0, total, 0])
        if self.show_left_pane_action is not None:
            self.show_left_pane_action.setChecked(False)
        if self.show_right_pane_action is not None:
            self.show_right_pane_action.setChecked(False)
        container = getattr(self, "series_navigator_container", None)
        if container is not None:
            container.setVisible(False)
        if hasattr(self, "main_toolbar"):
            self.main_toolbar.hide()
        QTimer.singleShot(10, lambda: self.viewport_resized.emit())

    def _restore_fullscreen_chrome(self, snap: Dict[str, Any]) -> None:
        """Restore splitter, navigator bar, toolbar, and View menu checks from *snap*."""
        self.viewport_resizing.emit()
        restored: List[int] = list(snap["splitter_sizes"])
        if len(restored) == 3:
            self.splitter.setSizes(restored)
            if self.show_left_pane_action is not None:
                self.show_left_pane_action.setChecked(restored[0] > 0)
            if self.show_right_pane_action is not None:
                self.show_right_pane_action.setChecked(restored[2] > 0)
        bar_vis = bool(snap.get("series_navigator_bar_visible", False))
        self.series_navigator_visible = bar_vis
        container = getattr(self, "series_navigator_container", None)
        if container is not None:
            container.setVisible(bar_vis)
        if self.show_series_navigator_action is not None:
            self.show_series_navigator_action.setChecked(bar_vis)
        tb_vis = bool(snap.get("toolbar_visible", True))
        if hasattr(self, "main_toolbar"):
            self.main_toolbar.setVisible(tb_vis)
        QTimer.singleShot(10, lambda: self.viewport_resized.emit())

    def set_fullscreen(self, enable: bool) -> None:
        """
        Enter or leave application fullscreen.

        Entering hides left/right panes, the series navigator bar, and the main toolbar
        using a snapshot so leaving restores prior layout without persisting fullscreen
        as user defaults.
        """
        if enable:
            if self.isFullScreen():
                if self.fullscreen_action is not None:
                    self.fullscreen_action.setChecked(True)
                return
            self._fullscreen_transitioning = True
            try:
                self._fullscreen_snapshot = self._take_fullscreen_snapshot()
                self._apply_fullscreen_chrome_hidden()
                self.showFullScreen()
                if self.fullscreen_action is not None:
                    self.fullscreen_action.setChecked(True)
            finally:
                self._fullscreen_transitioning = False
            return

        # --- exit ---
        self._fullscreen_transitioning = True
        try:
            snap = self._fullscreen_snapshot
            self._fullscreen_snapshot = None
            self.showNormal()
            if snap is not None and snap.get("was_maximized"):
                self.showMaximized()
            if snap is not None:
                self._restore_fullscreen_chrome(snap)
            if self.fullscreen_action is not None:
                self.fullscreen_action.setChecked(False)
        finally:
            self._fullscreen_transitioning = False

    def changeEvent(self, event: QEvent) -> None:
        """If the user leaves fullscreen via the OS, restore chrome from the snapshot."""
        super().changeEvent(event)
        if event.type() != QEvent.Type.WindowStateChange:
            return
        if self._fullscreen_transitioning:
            return
        if not self.isFullScreen() and self._fullscreen_snapshot is not None:
            self._fullscreen_transitioning = True
            try:
                snap = self._fullscreen_snapshot
                self._fullscreen_snapshot = None
                if snap is not None:
                    self._restore_fullscreen_chrome(snap)
                if self.fullscreen_action is not None:
                    self.fullscreen_action.setChecked(False)
            finally:
                self._fullscreen_transitioning = False

    def set_window_slot_map_visible(self, visible: bool) -> None:
        """
        Show or hide the window-slot thumbnail widget (when series navigator is visible).
        """
        widget = getattr(self, "window_slot_map_widget", None)
        if widget is not None:
            widget.setVisible(visible)

    def set_window_slot_map_callbacks(
        self,
        get_slot_to_view,
        get_layout_mode,
        get_focused_view_index,
        get_thumbnail_for_view=None,
    ) -> None:
        """
        Configure callbacks for the window-slot thumbnail widget so it can
        query current slot_to_view, layout mode, focused view index, and
        per-view image thumbnails.
        """
        widget = getattr(self, "window_slot_map_widget", None)
        if widget is not None:
            widget.set_callbacks(
                get_slot_to_view=get_slot_to_view,
                get_layout_mode=get_layout_mode,
                get_focused_view_index=get_focused_view_index,
                get_thumbnail_for_view=get_thumbnail_for_view,
            )

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """
        Handle drag enter event - accept files and folders.
        
        Args:
            event: QDragEnterEvent
        """
        if event.mimeData().hasUrls():
            # Check if any of the URLs are files or directories
            urls = event.mimeData().urls()
            for url in urls:
                path = url.toLocalFile()
                if path and os.path.exists(path):
                    # Accept if at least one valid file/folder exists
                    event.acceptProposedAction()
                    return
        
        event.ignore()
    
    def dropEvent(self, event: QDropEvent) -> None:
        """
        Handle drop event - load files or folders.
        
        Args:
            event: QDropEvent
        """
        if not event.mimeData().hasUrls():
            event.ignore()
            return
        
        urls = event.mimeData().urls()
        if not urls:
            event.ignore()
            return
        
        # Extract file paths
        paths = []
        folders = []
        
        for url in urls:
            path = url.toLocalFile()
            if not path:
                continue
            
            if os.path.isfile(path):
                paths.append(path)
            elif os.path.isdir(path):
                folders.append(path)
        
        # Process folders first (if any), otherwise process files
        if folders:
            # Use the first folder (prioritize folders over files)
            # Emit signal with folder path
            self.open_files_from_paths_requested.emit([folders[0]])
        elif paths:
            # Process all files together
            self.open_files_from_paths_requested.emit(paths)
        
        event.acceptProposedAction()
    
    def _on_layout_changed(self, layout_mode: str) -> None:
        """
        Handle layout mode change from menu.
        
        Args:
            layout_mode: Layout mode ("1x1", "1x2", "2x1", "2x2")
        """
        if DEBUG_LAYOUT:
            import traceback
            stack = traceback.extract_stack()[-5:-1]
            callers = " <- ".join([f"{f.name}:{f.lineno}" for f in stack])
            ts = datetime.now().strftime("%H:%M:%S.%f")
            print(f"[DEBUG-LAYOUT] [{ts}] main_window._on_layout_changed: mode={layout_mode!r} callers={callers}")
        # Update menu checkmarks
        if self.layout_1x1_action is not None:
            self.layout_1x1_action.setChecked(layout_mode == "1x1")
        if self.layout_1x2_action is not None:
            self.layout_1x2_action.setChecked(layout_mode == "1x2")
        if self.layout_2x1_action is not None:
            self.layout_2x1_action.setChecked(layout_mode == "2x1")
        if self.layout_2x2_action is not None:
            self.layout_2x2_action.setChecked(layout_mode == "2x2")
        
        # Emit signal
        self.layout_changed.emit(layout_mode)
    
    def set_layout_mode(self, layout_mode: str) -> None:
        """
        Set the layout mode (called from outside to update menu state).
        
        Args:
            layout_mode: Layout mode ("1x1", "1x2", "2x1", "2x2")
        """
        self._on_layout_changed(layout_mode)
    
    def closeEvent(self, event) -> None:
        """
        Handle window close event.
        
        Args:
            event: Close event
        """
        # Avoid persisting fullscreen geometry / forced splitter; restore chrome first
        if self.isFullScreen():
            snap = self._fullscreen_snapshot
            self._fullscreen_snapshot = None
            self.showNormal()
            if snap is not None:
                self._restore_fullscreen_chrome(snap)
                if snap.get("was_maximized"):
                    self.showMaximized()
            if self.fullscreen_action is not None:
                self.fullscreen_action.setChecked(False)
        elif self._fullscreen_snapshot is not None:
            snap = self._fullscreen_snapshot
            self._fullscreen_snapshot = None
            self._restore_fullscreen_chrome(snap)

        # Save window geometry
        geometry = self.geometry()
        self.config_manager.set("window_width", geometry.width())
        self.config_manager.set("window_height", geometry.height())
        self.config_manager.save_config()
        
        event.accept()


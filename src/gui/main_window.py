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

from PySide6.QtWidgets import (QMainWindow, QMenuBar, QToolBar, QStatusBar,
                                QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
                                QMessageBox, QComboBox, QLabel, QSizePolicy, QColorDialog,
                                QApplication, QDialog, QTextBrowser, QPushButton, QDialogButtonBox, QMenu)
from PySide6.QtCore import Qt, Signal, QEvent
from PySide6.QtGui import QAction, QIcon, QKeySequence, QColor, QDragEnterEvent, QDropEvent
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from gui.image_viewer import ImageViewer
from pathlib import Path
import sys
import os
import urllib.parse
import re

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.config_manager import ConfigManager
from gui.dialogs.edit_recent_list_dialog import EditRecentListDialog


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
    settings_requested = Signal()
    overlay_settings_requested = Signal()  # Emitted when overlay settings dialog is requested
    tag_viewer_requested = Signal()
    overlay_config_requested = Signal()
    annotation_options_requested = Signal()  # Emitted when annotation options dialog is requested
    mouse_mode_changed = Signal(str)  # Emitted when mouse mode changes ("roi_ellipse", "roi_rectangle", "measure", "zoom", "pan", "auto_window_level")
    scroll_wheel_mode_changed = Signal(str)  # Emitted when scroll wheel mode changes ("slice" or "zoom")
    overlay_font_size_changed = Signal(int)  # Emitted when overlay font size changes
    overlay_font_color_changed = Signal(int, int, int)  # Emitted when overlay font color changes (r, g, b)
    reset_view_requested = Signal()  # Emitted when reset view is requested
    viewport_resized = Signal()  # Emitted when splitter moves and viewport size changes
    viewport_resizing = Signal()  # Emitted when splitter starts moving (before resize completes)
    series_navigation_requested = Signal(int)  # Emitted when series navigation is requested (-1 for prev, 1 for next)
    rescale_toggle_changed = Signal(bool)  # Emitted when rescale toggle changes (True = use rescaled values)
    clear_measurements_requested = Signal()  # Emitted when clear measurements is requested
    quick_start_guide_requested = Signal()  # Emitted when Quick Start Guide is requested
    tag_export_requested = Signal()  # Emitted when tag export is requested
    series_navigator_visibility_changed = Signal(bool)  # Emitted when series navigator visibility changes
    undo_tag_edit_requested = Signal()  # Emitted when undo tag edit is requested
    redo_tag_edit_requested = Signal()  # Emitted when redo tag edit is requested
    open_files_from_paths_requested = Signal(list)  # Emitted when files/folders are dropped (list of paths)
    layout_changed = Signal(str)  # Emitted when layout mode changes ("1x1", "1x2", "2x1", "2x2")
    privacy_view_toggled = Signal(bool)  # Emitted when privacy view is toggled (True = enabled)
    about_this_file_requested = Signal()  # Emitted when About this File is requested
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
        
        # Window properties
        self.setWindowTitle("DICOM Viewer V3")
        self.setGeometry(100, 100, 
                        self.config_manager.get("window_width", 1200),
                        self.config_manager.get("window_height", 800))
        
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
        """Create the application menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        # Open File action
        open_file_action = QAction("&Open File(s)...", self)
        open_file_action.setShortcut(QKeySequence.Open)
        open_file_action.triggered.connect(self.open_file_requested.emit)
        file_menu.addAction(open_file_action)
        
        # Open Folder action
        open_folder_action = QAction("Open &Folder...", self)
        open_folder_action.setShortcut(QKeySequence("Ctrl+Shift+O"))
        open_folder_action.triggered.connect(self.open_folder_requested.emit)
        file_menu.addAction(open_folder_action)
        
        file_menu.addSeparator()
        
        # Recent Files submenu
        self.recent_menu = file_menu.addMenu("&Recent")
        # Install event filter for context menu support
        self.recent_menu.installEventFilter(self)
        self._update_recent_menu()
        
        # Edit Recent List action
        edit_recent_list_action = QAction("Edit Recent List...", self)
        edit_recent_list_action.triggered.connect(self._open_edit_recent_list_dialog)
        file_menu.addAction(edit_recent_list_action)
        
        file_menu.addSeparator()
        
        # Export action
        export_action = QAction("&Export...", self)
        export_action.setShortcut(QKeySequence("Ctrl+E"))
        export_action.triggered.connect(self.export_requested.emit)
        file_menu.addAction(export_action)
        
        file_menu.addSeparator()
        
        # Close action
        close_action = QAction("&Close", self)
        close_action.setShortcut(QKeySequence("Ctrl+W"))
        close_action.triggered.connect(self.close_requested.emit)
        file_menu.addAction(close_action)
        
        file_menu.addSeparator()
        
        # Exit action
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Edit menu
        edit_menu = menubar.addMenu("&Edit")
        
        # Undo/Redo actions for tag edits
        self.undo_tag_edit_action = QAction("&Undo Tag Edit", self)
        self.undo_tag_edit_action.setShortcut(QKeySequence.Undo)
        self.undo_tag_edit_action.setEnabled(False)
        self.undo_tag_edit_action.triggered.connect(self.undo_tag_edit_requested.emit)
        edit_menu.addAction(self.undo_tag_edit_action)
        
        self.redo_tag_edit_action = QAction("&Redo Tag Edit", self)
        self.redo_tag_edit_action.setShortcut(QKeySequence.Redo)
        self.redo_tag_edit_action.setEnabled(False)
        self.redo_tag_edit_action.triggered.connect(self.redo_tag_edit_requested.emit)
        edit_menu.addAction(self.redo_tag_edit_action)
        
        # View menu
        view_menu = menubar.addMenu("&View")
        
        # Theme actions (exclusive)
        theme_menu = view_menu.addMenu("&Theme")
        self.light_theme_action = QAction("&Light", self)
        self.light_theme_action.setCheckable(True)
        self.light_theme_action.setChecked(self.config_manager.get_theme() == "light")
        self.light_theme_action.triggered.connect(lambda: self._set_theme("light"))
        theme_menu.addAction(self.light_theme_action)
        
        self.dark_theme_action = QAction("&Dark", self)
        self.dark_theme_action.setCheckable(True)
        self.dark_theme_action.setChecked(self.config_manager.get_theme() == "dark")
        self.dark_theme_action.triggered.connect(lambda: self._set_theme("dark"))
        theme_menu.addAction(self.dark_theme_action)
        
        view_menu.addSeparator()
        
        # Privacy View action
        self.privacy_view_action = QAction("&Privacy View", self)
        self.privacy_view_action.setCheckable(True)
        self.privacy_view_action.setChecked(self.config_manager.get_privacy_view())
        self.privacy_view_action.setShortcut(QKeySequence("Ctrl+P"))  # Works on all platforms (Cmd+P on Mac, Ctrl+P on Windows/Linux)
        self.privacy_view_action.triggered.connect(self._on_privacy_view_toggled)
        view_menu.addAction(self.privacy_view_action)
        
        view_menu.addSeparator()
        
        # Settings action
        settings_action = QAction("&Settings...", self)
        settings_action.triggered.connect(self.settings_requested.emit)
        view_menu.addAction(settings_action)
        
        # Overlay Configuration action
        overlay_config_action = QAction("Overlay &Configuration...", self)
        overlay_config_action.setShortcut(QKeySequence("Ctrl+O"))
        overlay_config_action.triggered.connect(self.overlay_config_requested.emit)
        view_menu.addAction(overlay_config_action)
        
        # Overlay Settings action
        overlay_settings_action = QAction("Overlay &Settings...", self)
        overlay_settings_action.triggered.connect(self.overlay_settings_requested.emit)
        view_menu.addAction(overlay_settings_action)
        
        # Annotation Options action
        annotation_options_action = QAction("Annotation &Options...", self)
        annotation_options_action.triggered.connect(self.annotation_options_requested.emit)
        view_menu.addAction(annotation_options_action)
        
        view_menu.addSeparator()
        
        # Layout submenu
        layout_menu = view_menu.addMenu("&Layout")
        self.layout_1x1_action = QAction("&1x1", self)
        self.layout_1x1_action.setCheckable(True)
        self.layout_1x1_action.setChecked(True)  # Default
        self.layout_1x1_action.triggered.connect(lambda: self._on_layout_changed("1x1"))
        layout_menu.addAction(self.layout_1x1_action)
        
        self.layout_1x2_action = QAction("&1x2", self)
        self.layout_1x2_action.setCheckable(True)
        self.layout_1x2_action.triggered.connect(lambda: self._on_layout_changed("1x2"))
        layout_menu.addAction(self.layout_1x2_action)
        
        self.layout_2x1_action = QAction("&2x1", self)
        self.layout_2x1_action.setCheckable(True)
        self.layout_2x1_action.triggered.connect(lambda: self._on_layout_changed("2x1"))
        layout_menu.addAction(self.layout_2x1_action)
        
        self.layout_2x2_action = QAction("&2x2", self)
        self.layout_2x2_action.setCheckable(True)
        self.layout_2x2_action.triggered.connect(lambda: self._on_layout_changed("2x2"))
        layout_menu.addAction(self.layout_2x2_action)
        
        # Tools menu
        tools_menu = menubar.addMenu("&Tools")
        
        # Tag Viewer/Editor action
        tag_viewer_action = QAction("View/Edit DICOM &Tags...", self)
        tag_viewer_action.setShortcut(QKeySequence("Ctrl+T"))
        tag_viewer_action.triggered.connect(self.tag_viewer_requested.emit)
        tools_menu.addAction(tag_viewer_action)
        
        # Tag Export action
        tag_export_action = QAction("Export DICOM &Tags...", self)
        tag_export_action.setShortcut(QKeySequence("Shift+Ctrl+T"))
        tag_export_action.triggered.connect(self.tag_export_requested.emit)
        tools_menu.addAction(tag_export_action)
        
        # About this File action
        about_this_file_action = QAction("About this File...", self)
        about_this_file_action.setMenuRole(QAction.MenuRole.NoRole)  # Prevent macOS from moving to app menu
        about_this_file_action.setShortcut(QKeySequence("Ctrl+A"))
        about_this_file_action.triggered.connect(self.about_this_file_requested.emit)
        tools_menu.addAction(about_this_file_action)
        
        # Help menu
        help_menu = menubar.addMenu("&Help")
        
        quick_start_action = QAction("&Quick Start Guide", self)
        quick_start_action.triggered.connect(self.quick_start_guide_requested.emit)
        help_menu.addAction(quick_start_action)
        
        disclaimer_action = QAction("&Disclaimer", self)
        disclaimer_action.triggered.connect(self._show_disclaimer)
        help_menu.addAction(disclaimer_action)
        
        help_menu.addSeparator()
        
        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
    
    def _create_toolbar(self) -> None:
        """Create the application toolbar."""
        toolbar = QToolBar("Main Toolbar", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        
        # Mouse interaction mode buttons (exclusive)
        self.mouse_mode_ellipse_roi_action = QAction("Ellipse ROI", self)
        self.mouse_mode_ellipse_roi_action.setCheckable(True)
        self.mouse_mode_ellipse_roi_action.triggered.connect(
            lambda: self._on_mouse_mode_changed("roi_ellipse")
        )
        toolbar.addAction(self.mouse_mode_ellipse_roi_action)
        
        self.mouse_mode_rectangle_roi_action = QAction("Rectangle ROI", self)
        self.mouse_mode_rectangle_roi_action.setCheckable(True)
        self.mouse_mode_rectangle_roi_action.triggered.connect(
            lambda: self._on_mouse_mode_changed("roi_rectangle")
        )
        toolbar.addAction(self.mouse_mode_rectangle_roi_action)
        
        self.mouse_mode_measure_action = QAction("Measure", self)
        self.mouse_mode_measure_action.setCheckable(True)
        self.mouse_mode_measure_action.triggered.connect(
            lambda: self._on_mouse_mode_changed("measure")
        )
        toolbar.addAction(self.mouse_mode_measure_action)
        
        self.mouse_mode_zoom_action = QAction("Zoom", self)
        self.mouse_mode_zoom_action.setCheckable(True)
        self.mouse_mode_zoom_action.triggered.connect(
            lambda: self._on_mouse_mode_changed("zoom")
        )
        toolbar.addAction(self.mouse_mode_zoom_action)
        
        self.mouse_mode_pan_action = QAction("Pan", self)
        self.mouse_mode_pan_action.setCheckable(True)
        self.mouse_mode_pan_action.setChecked(True)  # Default mode
        self.mouse_mode_pan_action.triggered.connect(
            lambda: self._on_mouse_mode_changed("pan")
        )
        toolbar.addAction(self.mouse_mode_pan_action)
        
        self.mouse_mode_select_action = QAction("Select", self)
        self.mouse_mode_select_action.setCheckable(True)
        self.mouse_mode_select_action.triggered.connect(
            lambda: self._on_mouse_mode_changed("select")
        )
        toolbar.addAction(self.mouse_mode_select_action)
        
        # Window/Level ROI tool
        self.mouse_mode_auto_window_level_action = QAction("Window/Level ROI", self)
        self.mouse_mode_auto_window_level_action.setCheckable(True)
        self.mouse_mode_auto_window_level_action.triggered.connect(
            lambda: self._on_mouse_mode_changed("auto_window_level")
        )
        toolbar.addAction(self.mouse_mode_auto_window_level_action)
        
        toolbar.addSeparator()
        
        # Privacy Mode button
        self.privacy_mode_action = QAction("Privacy is OFF", self)
        self.privacy_mode_action.setCheckable(True)
        # Initialize from config - when privacy is OFF, button should be highlighted (checked)
        privacy_enabled = self.config_manager.get_privacy_view()
        self.privacy_mode_action.setChecked(not privacy_enabled)  # Checked when privacy is OFF
        self.privacy_mode_action.triggered.connect(self._on_privacy_mode_button_clicked)
        toolbar.addAction(self.privacy_mode_action)
        # Store toolbar reference for styling
        self.main_toolbar = toolbar
        # Update button appearance
        self._update_privacy_mode_button()
        
        toolbar.addSeparator()
        
        # Reset View button
        reset_view_action = QAction("Reset View", self)
        reset_view_action.setToolTip("Reset zoom, pan, window center and level to initial values")
        reset_view_action.triggered.connect(self.reset_view_requested.emit)
        toolbar.addAction(reset_view_action)
        
        toolbar.addSeparator()
        
        # Series Navigator toggle button
        self.series_navigator_action = QAction("Show Series Navigator", self)
        self.series_navigator_action.setToolTip("Show/hide series navigator bar at bottom")
        self.series_navigator_action.triggered.connect(self.toggle_series_navigator)
        toolbar.addAction(self.series_navigator_action)
        
        toolbar.addSeparator()
        
        # Series navigation buttons
        self.prev_series_action = QAction("Prev Series", self)
        self.prev_series_action.setToolTip("Navigate to previous series (left arrow key)")
        self.prev_series_action.triggered.connect(self._on_prev_series)
        toolbar.addAction(self.prev_series_action)
        
        self.next_series_action = QAction("Next Series", self)
        self.next_series_action.setToolTip("Navigate to next series (right arrow key)")
        self.next_series_action.triggered.connect(self._on_next_series)
        toolbar.addAction(self.next_series_action)
        
        toolbar.addSeparator()
        
        # Overlay font size controls
        toolbar.addWidget(QLabel("Font Size:"))
        
        # Font size decrease button
        font_size_decrease_action = QAction("−", self)
        font_size_decrease_action.setToolTip("Decrease overlay font size")
        font_size_decrease_action.triggered.connect(self._on_font_size_decrease)
        toolbar.addAction(font_size_decrease_action)
        
        # Font size increase button
        font_size_increase_action = QAction("+", self)
        font_size_increase_action.setToolTip("Increase overlay font size")
        font_size_increase_action.triggered.connect(self._on_font_size_increase)
        toolbar.addAction(font_size_increase_action)
        
        toolbar.addSeparator()
        
        # Font color picker button
        font_color_action = QAction("Font Color", self)
        font_color_action.setToolTip("Change overlay font color")
        font_color_action.triggered.connect(self._on_font_color_picker)
        toolbar.addAction(font_color_action)
        
        toolbar.addSeparator()
        
        # Use Rescaled Values toggle button (non-checkable, text alternates)
        self.use_rescaled_values_action = QAction("Use Rescaled Values", self)
        self.use_rescaled_values_action.setCheckable(False)  # Not checkable, text shows current state
        self.use_rescaled_values_action.setToolTip("Toggle between rescaled and raw pixel values")
        self.use_rescaled_values_action.triggered.connect(self._on_rescale_toggle_changed)
        toolbar.addAction(self.use_rescaled_values_action)
        
        # Add stretch to push scroll wheel mode toggle to the right
        toolbar.addSeparator()
        
        # Create spacer widget that expands
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)
        
        toolbar.addWidget(QLabel("Scroll Wheel:"))
        
        # Scroll wheel mode toggle (right-aligned)
        self.scroll_wheel_mode_combo = QComboBox()
        self.scroll_wheel_mode_combo.setObjectName("scroll_wheel_mode_combo")
        self.scroll_wheel_mode_combo.addItems(["Slice", "Zoom"])
        # Set current mode from config
        current_mode = self.config_manager.get_scroll_wheel_mode() if self.config_manager else "slice"
        if current_mode == "zoom":
            self.scroll_wheel_mode_combo.setCurrentIndex(1)
        else:
            self.scroll_wheel_mode_combo.setCurrentIndex(0)
        self.scroll_wheel_mode_combo.currentTextChanged.connect(self._on_scroll_wheel_mode_combo_changed)
        toolbar.addWidget(self.scroll_wheel_mode_combo)
    
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
    
    def _create_central_widget(self) -> None:
        """Create the central widget area."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Splitter for resizable panels
        self.splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(self.splitter)
        
        # Left panel (for metadata, series list, etc.)
        self.left_panel = QWidget()
        self.left_panel.setObjectName("left_panel")
        self.left_panel.setMaximumWidth(400)
        self.left_panel.setMinimumWidth(200)
        self.splitter.addWidget(self.left_panel)
        
        # Center panel (for image viewer)
        self.center_panel = QWidget()
        self.center_panel.setObjectName("center_panel")
        self.splitter.addWidget(self.center_panel)
        
        # Right panel (for tools, histogram, etc.)
        self.right_panel = QWidget()
        self.right_panel.setObjectName("right_panel")
        self.right_panel.setMaximumWidth(400)
        self.right_panel.setMinimumWidth(200)
        self.splitter.addWidget(self.right_panel)
        
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
        
        # Series navigator (initially hidden, will be set by main.py)
        self.series_navigator = None  # Will be set by set_series_navigator method
        self.series_navigator_visible = False
    
    def _apply_theme(self) -> None:
        """Apply the current theme using pure stylesheet approach.
        
        Uses simplified, palette-like color scheme with consistent colors
        across similar widgets to avoid QPalette/QStyleSheet conflicts.
        """
        theme = self.config_manager.get_theme()
        
        # Get path to checkmark images
        # main_window.py is in src/gui/, so go up to project root, then to resources/images
        project_root = Path(__file__).parent.parent.parent
        images_dir = project_root / "resources" / "images"
        
        # Get raw absolute paths before URL encoding
        white_checkmark_raw = (images_dir / "checkbox_checkmark_white.png").absolute()
        black_checkmark_raw = (images_dir / "checkbox_checkmark_black.png").absolute()
        
        # Debug: Print raw paths
        # print(f"[CHECKMARK DEBUG] White checkmark raw path: {white_checkmark_raw}")
        # print(f"[CHECKMARK DEBUG] Black checkmark raw path: {black_checkmark_raw}")
        
        # Check if files exist
        white_exists = white_checkmark_raw.exists()
        black_exists = black_checkmark_raw.exists()
        # print(f"[CHECKMARK DEBUG] White checkmark exists: {white_exists}")
        # print(f"[CHECKMARK DEBUG] Black checkmark exists: {black_exists}")
        
        # if white_exists:
        #     print(f"[CHECKMARK DEBUG] White checkmark file size: {white_checkmark_raw.stat().st_size} bytes")
        # if black_exists:
        #     print(f"[CHECKMARK DEBUG] Black checkmark file size: {black_checkmark_raw.stat().st_size} bytes")
        
        # Try relative paths from application working directory
        # Use simple relative path without URL encoding
        white_checkmark_path = "resources/images/checkbox_checkmark_white.png"
        black_checkmark_path = "resources/images/checkbox_checkmark_black.png"
        
        # Debug: Print paths
        # print(f"[CHECKMARK DEBUG] White checkmark path (relative): {white_checkmark_path}")
        # print(f"[CHECKMARK DEBUG] Black checkmark path (relative): {black_checkmark_path}")
        
        # Debug: Print final URL format that will be in stylesheet
        # white_url = f"url('{white_checkmark_path}')"
        # black_url = f"url('{black_checkmark_path}')"
        # print(f"[CHECKMARK DEBUG] White checkmark final URL: {white_url}")
        # print(f"[CHECKMARK DEBUG] Black checkmark final URL: {black_url}")
        
        if theme == "dark":
            # Dark theme - simplified palette-like colors
            stylesheet = """
                /* Main window and panels - all same background */
                QMainWindow, QWidget {{
                    background-color: #2b2b2b;
                    color: #ffffff;
                }}
                
                /* Menu bar */
                QMenuBar {{
                    background-color: #2b2b2b;
                    color: #ffffff;
                    border-bottom: 1px solid #555555;
                }}
                
                QMenuBar::item {{
                    background-color: transparent;
                    padding: 4px 12px;
                }}
                
                QMenuBar::item:selected {{
                    background-color: #3a3a3a;
                }}
                
                QMenuBar::item:pressed {{
                    background-color: #4285da;
                }}
                
                /* Menus */
                QMenu {{
                    background-color: #2b2b2b;
                    color: #ffffff;
                    border: 1px solid #555555;
                }}
                
                QMenu::item {{
                    padding: 5px 25px 5px 25px;
                }}
                
                QMenu::item:selected {{
                    background-color: #4285da;
                }}
                
                QMenu::separator {{
                    height: 1px;
                    background-color: #555555;
                    margin: 5px 0px;
                }}
                
                /* Commented out to allow native checkmark rendering
                QMenu::indicator {{
                    width: 16px;
                    height: 16px;
                    border: none;
                }}
                
                QMenu::indicator:checked {{
                    border: none;
                }}
                */
                
                /* Toolbar */
                QToolBar {{
                    background-color: #3a3a3a;
                    border: 1px solid #555555;
                    spacing: 3px;
                    padding: 3px;
                }}
                
                QToolBar::separator {{
                    background-color: #555555;
                    width: 1px;
                    margin: 2px;
                }}
                
                /* Toolbar widgets (spacer) - transparent to match toolbar */
                QToolBar QWidget {{
                    background-color: transparent;
                }}
                
                /* Toolbar combobox - override transparent background */
                QToolBar QComboBox {{
                    background-color: #1b1b1b;
                    color: #ffffff;
                    border: 1px solid #555555;
                    padding: 3px 10px;
                    border-radius: 3px;
                }}
                
                QToolBar QComboBox:hover {{
                    border: 1px solid #6a6a6a;
                }}
                
                /* Toolbar buttons */
                QToolButton {{
                    background-color: #3a3a3a;
                    color: #ffffff;
                    border: none;
                    padding: 0px 2px;
                }}
                
                QToolButton:hover {{
                    background-color: #454545;
                }}
                
                QToolButton:pressed {{
                    background-color: #4285da;
                }}
                
                QToolButton:checked {{
                    background-color: #4285da;
                }}
                
                QToolButton:disabled {{
                    background-color: #2b2b2b;
                    color: #7f7f7f;
                }}
                
                /* Buttons */
                QPushButton {{
                    background-color: #3a3a3a;
                    color: #ffffff;
                    border: 1px solid #555555;
                    padding: 3px 8px;
                    border-radius: 3px;
                }}
                
                QPushButton:hover {{
                    background-color: #454545;
                }}
                
                QPushButton:pressed {{
                    background-color: #4285da;
                }}
                
                QPushButton:disabled {{
                    background-color: #2b2b2b;
                    color: #7f7f7f;
                    border: 1px solid #3a3a3a;
                }}
                
                QPushButton:checked {{
                    background-color: #4285da;
                }}
                
                QPushButton[objectName="cine_loop_button"]:checked {{
                    background-color: #4285da;
                    border: 2px solid #5a9de5;
                }}
                
                /* Text inputs, lists, tables */
                QTreeWidget, QTableWidget, QListWidget, QTextEdit, QPlainTextEdit {{
                    background-color: #1e1e1e;
                    color: #ffffff;
                    border: 1px solid #555555;
                    selection-background-color: #4285da;
                    selection-color: #ffffff;
                }}
                
                QTreeWidget::item:hover, QTableWidget::item:hover, QListWidget::item:hover {{
                    background-color: #3a3a3a;
                }}
                
                QTreeWidget::item:selected, QTableWidget::item:selected, QListWidget::item:selected {{
                    background-color: #4285da;
                }}
                
                /* Headers */
                QHeaderView::section {{
                    background-color: #3a3a3a;
                    color: #ffffff;
                    border: 1px solid #555555;
                    padding: 4px;
                }}
                
                /* Line edits, spin boxes */
                QLineEdit, QSpinBox, QDoubleSpinBox {{
                    background-color: #1e1e1e;
                    color: #ffffff;
                    border: 1px solid #555555;
                    padding: 3px;
                    border-radius: 3px;
                }}
                
                QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
                    border: 1px solid #4285da;
                }}
                
                QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{
                    background-color: #2b2b2b;
                    color: #7f7f7f;
                }}
                
                /* Scrollbars */
                QScrollBar:vertical {{
                    background-color: #2b2b2b;
                    width: 12px;
                    border: none;
                }}
                
                QScrollBar::handle:vertical {{
                    background-color: #555555;
                    min-height: 20px;
                    border-radius: 6px;
                }}
                
                QScrollBar::handle:vertical:hover {{
                    background-color: #6a6a6a;
                }}
                
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                    height: 0px;
                }}
                
                QScrollBar:horizontal {{
                    background-color: #2b2b2b;
                    height: 12px;
                    border: none;
                }}
                
                QScrollBar::handle:horizontal {{
                    background-color: #555555;
                    min-width: 20px;
                    border-radius: 6px;
                }}
                
                QScrollBar::handle:horizontal:hover {{
                    background-color: #6a6a6a;
                }}
                
                QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                    width: 0px;
                }}
                
                /* Checkboxes */
                QCheckBox {{
                    color: #ffffff;
                    spacing: 5px;
                }}
                
                QCheckBox:disabled {{
                    color: #7f7f7f;
                }}
                
                /* Commented out to allow native checkmark rendering
                QCheckBox::indicator {{
                    width: 16px;
                    height: 16px;
                    border: 1px solid #555555;
                    border-radius: 3px;
                }}
                
                QCheckBox::indicator:hover {{
                    border: 1px solid #6a6a6a;
                }}
                
                QCheckBox::indicator:checked {{
                    border: 1px solid #555555;
                }}
                */
                
                /* Metadata panel checkbox with border and custom checkmark */
                QWidget[objectName="metadata_panel"] QCheckBox::indicator {{
                    width: 16px;
                    height: 16px;
                    border: 2px solid #6a6a6a;
                    border-radius: 3px;
                    background-color: #1e1e1e;
                }}
                
                QWidget[objectName="metadata_panel"] QCheckBox::indicator:checked {{
                    border: 2px solid #6a6a6a;
                    background-color: #1e1e1e;
                    image: url('{white_checkmark_path}');
                }}
                
                /* Labels */
                QLabel {{
                    background-color: transparent;
                    color: #ffffff;
                }}
                
                QLabel:disabled {{
                    color: #7f7f7f;
                }}
                
                /* Status bar */
                QStatusBar {{
                    background-color: #2b2b2b;
                    color: #ffffff;
                    border-top: 1px solid #555555;
                }}
                
                /* Splitter handles */
                QSplitter::handle {{
                    background-color: #555555;
                }}
                
                QSplitter::handle:horizontal {{
                    width: 2px;
                }}
                
                QSplitter::handle:vertical {{
                    height: 2px;
                }}
                
                /* Combo boxes */
                QComboBox {{
                    background-color: #1b1b1b;
                    color: #ffffff;
                    border: 1px solid #555555;
                    padding: 3px 10px;
                    border-radius: 3px;
                }}
                
                QComboBox:hover {{
                    border: 1px solid #6a6a6a;
                }}
                
                /* QComboBox::drop-down - COMMENTED OUT to preserve native arrow */
                /*
                QComboBox::drop-down {{
                    subcontrol-origin: padding;
                    subcontrol-position: top right;
                    width: 20px;
                    border-left-width: 1px;
                    border-left-color: #555555;
                    border-left-style: solid;
                    border-top-right-radius: 3px;
                    border-bottom-right-radius: 3px;
                }}
                */
                
                /* Combo box item view */
                /* Styles the dropdown list that opens when you click the combobox arrow */
                QComboBox QAbstractItemView {{
                    background-color: #1b1b1b;
                    color: #ffffff;
                    selection-background-color: #4285da;
                    border: 1px solid #555555;
                }}
                
                /* Tooltips */
                QToolTip {{
                    background-color: #3a3a3a;
                    color: #ffffff;
                    border: 1px solid #555555;
                    padding: 3px;
                }}
                
                /* Series Navigator */
                QWidget[objectName="series_navigator"] {{
                    background-color: #1b1b1b;
                }}
                
                QScrollArea[objectName="series_navigator_scroll_area"] {{
                    background-color: #1b1b1b;
                }}
                
                QWidget[objectName="series_navigator_container"] {{
                    background-color: #1b1b1b;
                }}
            """.format(white_checkmark_path=white_checkmark_path, black_checkmark_path=black_checkmark_path)
            
            # Update image viewer background color for dark theme
            if self.image_viewer is not None:
                from PySide6.QtGui import QColor
                self.image_viewer.set_background_color(QColor(27, 27, 27))  # #1b1b1b
        else:
            # Light theme - simplified palette-like colors
            stylesheet = """
                /* Main window and panels - all same background */
                QMainWindow, QWidget {{
                    background-color: #f0f0f0;
                    color: #000000;
                }}
                
                /* Menu bar */
                QMenuBar {{
                    background-color: #f0f0f0;
                    color: #000000;
                    border-bottom: 1px solid #c0c0c0;
                }}
                
                QMenuBar::item {{
                    background-color: transparent;
                    padding: 4px 12px;
                }}
                
                QMenuBar::item:selected {{
                    background-color: #e0e0e0;
                }}
                
                QMenuBar::item:pressed {{
                    background-color: #4285da;
                    color: #ffffff;
                }}
                
                /* Menus */
                QMenu {{
                    background-color: #f0f0f0;
                    color: #000000;
                    border: 1px solid #c0c0c0;
                }}
                
                QMenu::item {{
                    padding: 5px 25px 5px 25px;
                }}
                
                QMenu::item:selected {{
                    background-color: #4285da;
                    color: #ffffff;
                }}
                
                QMenu::separator {{
                    height: 1px;
                    background-color: #c0c0c0;
                    margin: 5px 0px;
                }}
                
                /* Commented out to allow native checkmark rendering
                QMenu::indicator {{
                    width: 16px;
                    height: 16px;
                    border: none;
                }}
                
                QMenu::indicator:checked {{
                    border: none;
                }}
                */
                
                /* Toolbar */
                QToolBar {{
                    background-color: #e0e0e0;
                    border: 1px solid #c0c0c0;
                    spacing: 3px;
                    padding: 3px;
                }}
                
                QToolBar::separator {{
                    background-color: #c0c0c0;
                    width: 1px;
                    margin: 2px;
                }}
                
                /* Toolbar widgets (spacer) - transparent to match toolbar */
                QToolBar QWidget {{
                    background-color: transparent;
                }}
                
                /* Toolbar combobox - override transparent background */
                QToolBar QComboBox {{
                    background-color: #ffffff;
                    color: #000000;
                    border: 1px solid #c0c0c0;
                    padding: 3px 10px;
                    border-radius: 3px;
                }}
                
                QToolBar QComboBox:hover {{
                    border: 1px solid #a0a0a0;
                }}
                
                /* Toolbar buttons */
                QToolButton {{
                    background-color: #e0e0e0;
                    color: #000000;
                    border: none;
                    padding: 0px 2px;
                }}
                
                QToolButton:hover {{
                    background-color: #d0d0d0;
                }}
                
                QToolButton:pressed {{
                    background-color: #4285da;
                    color: #ffffff;
                }}
                
                QToolButton:checked {{
                    background-color: #4285da;
                    color: #ffffff;
                }}
                
                QToolButton:disabled {{
                    background-color: #f0f0f0;
                    color: #a0a0a0;
                }}
                
                /* Buttons */
                QPushButton {{
                    background-color: #e0e0e0;
                    color: #000000;
                    border: 1px solid #c0c0c0;
                    padding: 3px 8px;
                    border-radius: 3px;
                }}
                
                QPushButton:hover {{
                    background-color: #d0d0d0;
                }}
                
                QPushButton:pressed {{
                    background-color: #4285da;
                    color: #ffffff;
                }}
                
                QPushButton:disabled {{
                    background-color: #f0f0f0;
                    color: #a0a0a0;
                    border: 1px solid #d0d0d0;
                }}
                
                QPushButton:checked {{
                    background-color: #4285da;
                    color: #ffffff;
                }}
                
                QPushButton[objectName="cine_loop_button"]:checked {{
                    background-color: #4285da;
                    color: #ffffff;
                    border: 2px solid #1a5da5;
                }}
                
                /* Text inputs, lists, tables */
                QTreeWidget, QTableWidget, QListWidget, QTextEdit, QPlainTextEdit {{
                    background-color: #ffffff;
                    color: #000000;
                    border: 1px solid #c0c0c0;
                    selection-background-color: #4285da;
                    selection-color: #ffffff;
                }}
                
                QTreeWidget::item:hover, QTableWidget::item:hover, QListWidget::item:hover {{
                    background-color: #e8e8e8;
                }}
                
                QTreeWidget::item:selected, QTableWidget::item:selected, QListWidget::item:selected {{
                    background-color: #4285da;
                }}
                
                /* Headers */
                QHeaderView::section {{
                    background-color: #e0e0e0;
                    color: #000000;
                    border: 1px solid #c0c0c0;
                    padding: 4px;
                }}
                
                /* Line edits, spin boxes */
                QLineEdit, QSpinBox, QDoubleSpinBox {{
                    background-color: #ffffff;
                    color: #000000;
                    border: 1px solid #c0c0c0;
                    padding: 3px;
                    border-radius: 3px;
                }}
                
                QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
                    border: 1px solid #4285da;
                }}
                
                QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{
                    background-color: #f0f0f0;
                    color: #a0a0a0;
                }}
                
                /* Scrollbars */
                QScrollBar:vertical {{
                    background-color: #f0f0f0;
                    width: 12px;
                    border: none;
                }}
                
                QScrollBar::handle:vertical {{
                    background-color: #c0c0c0;
                    min-height: 20px;
                    border-radius: 6px;
                }}
                
                QScrollBar::handle:vertical:hover {{
                    background-color: #a0a0a0;
                }}
                
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                    height: 0px;
                }}
                
                QScrollBar:horizontal {{
                    background-color: #f0f0f0;
                    height: 12px;
                    border: none;
                }}
                
                QScrollBar::handle:horizontal {{
                    background-color: #c0c0c0;
                    min-width: 20px;
                    border-radius: 6px;
                }}
                
                QScrollBar::handle:horizontal:hover {{
                    background-color: #a0a0a0;
                }}
                
                QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                    width: 0px;
                }}
                
                /* Checkboxes */
                QCheckBox {{
                    color: #000000;
                    spacing: 5px;
                }}
                
                QCheckBox:disabled {{
                    color: #a0a0a0;
                }}
                
                /* Commented out to allow native checkmark rendering
                QCheckBox::indicator {{
                    width: 16px;
                    height: 16px;
                    border: 1px solid #c0c0c0;
                    border-radius: 3px;
                }}
                
                QCheckBox::indicator:hover {{
                    border: 1px solid #a0a0a0;
                }}
                
                QCheckBox::indicator:checked {{
                    border: 1px solid #c0c0c0;
                }}
                */
                
                /* Metadata panel checkbox with border and custom checkmark */
                QWidget[objectName="metadata_panel"] QCheckBox::indicator {{
                    width: 16px;
                    height: 16px;
                    border: 2px solid #808080;
                    border-radius: 3px;
                    background-color: #ffffff;
                }}
                
                QWidget[objectName="metadata_panel"] QCheckBox::indicator:checked {{
                    border: 2px solid #808080;
                    background-color: #ffffff;
                    image: url('{black_checkmark_path}');
                }}
                
                /* Labels */
                QLabel {{
                    background-color: transparent;
                    color: #000000;
                }}
                
                QLabel:disabled {{
                    color: #a0a0a0;
                }}
                
                /* Status bar */
                QStatusBar {{
                    background-color: #f0f0f0;
                    color: #000000;
                    border-top: 1px solid #c0c0c0;
                }}
                
                /* Splitter handles */
                QSplitter::handle {{
                    background-color: #c0c0c0;
                }}
                
                QSplitter::handle:horizontal {{
                    width: 2px;
                }}
                
                QSplitter::handle:vertical {{
                    height: 2px;
                }}
                
                /* Combo boxes */
                QComboBox {{
                    background-color: #ffffff;
                    color: #000000;
                    border: 1px solid #c0c0c0;
                    padding: 3px 10px;
                    border-radius: 3px;
                }}
                
                QComboBox:hover {{
                    border: 1px solid #a0a0a0;
                }}
                
                /* QComboBox::drop-down - COMMENTED OUT to preserve native arrow */
                /*
                QComboBox::drop-down {{
                    subcontrol-origin: padding;
                    subcontrol-position: top right;
                    width: 20px;
                    border-left-width: 1px;
                    border-left-color: #c0c0c0;
                    border-left-style: solid;
                    border-top-right-radius: 3px;
                    border-bottom-right-radius: 3px;
                }}
                */
                
                QComboBox QAbstractItemView {{
                    background-color: #f0f0f0;
                    color: #000000;
                    selection-background-color: #4285da;
                    selection-color: #ffffff;
                    border: 1px solid #c0c0c0;
                }}
                
                /* Tooltips */
                QToolTip {{
                    background-color: #ffffdc;
                    color: #000000;
                    border: 1px solid #c0c0c0;
                    padding: 3px;
                }}
                
                /* Series Navigator */
                QWidget[objectName="series_navigator"] {{
                    background-color: #d0d0d0;
                }}
                
                QScrollArea[objectName="series_navigator_scroll_area"] {{
                    background-color: #d0d0d0;
                }}
                
                QWidget[objectName="series_navigator_container"] {{
                    background-color: #d0d0d0;
                }}
            """.format(white_checkmark_path=white_checkmark_path, black_checkmark_path=black_checkmark_path)
            
            # Update image viewer background color for light theme
            if self.image_viewer is not None:
                from PySide6.QtGui import QColor
                self.image_viewer.set_background_color(QColor(64, 64, 64))  # #404040
        
        # Debug: Extract and print the image URL lines from the stylesheet
        # image_url_pattern = r"image:\s*url\([^)]+\)"
        # image_urls = re.findall(image_url_pattern, stylesheet)
        # print(f"[CHECKMARK DEBUG] Found {len(image_urls)} image URL(s) in stylesheet:")
        # for i, url in enumerate(image_urls, 1):
        #     print(f"[CHECKMARK DEBUG]   {i}. {url}")
        
        # Debug: Check if the specific checkbox indicator lines are present
        # if 'QWidget[objectName="metadata_panel"] QCheckBox::indicator:checked' in stylesheet:
        #     # Extract the relevant section
        #     checkbox_section = re.search(
        #         r'QWidget\[objectName="metadata_panel"\] QCheckBox::indicator:checked \{[^}]*image:[^}]*\}',
        #         stylesheet,
        #         re.DOTALL
        #     )
        #     if checkbox_section:
        #         print(f"[CHECKMARK DEBUG] Checkbox indicator:checked section found:")
        #         print(f"[CHECKMARK DEBUG]   {checkbox_section.group(0)[:200]}...")
        #     else:
        #         print(f"[CHECKMARK DEBUG] WARNING: Checkbox indicator:checked section not found in stylesheet!")
        # else:
        #     print(f"[CHECKMARK DEBUG] WARNING: Checkbox selector not found in stylesheet!")
        
        # Apply stylesheet to QApplication (no palette conflicts)
        QApplication.instance().setStyleSheet(stylesheet)
        
        # Simple refresh - just process events once
        QApplication.processEvents()
    
    def _set_theme(self, theme: str) -> None:
        """
        Set the application theme.
        
        Ensures theme actions are mutually exclusive and saves preference.
        
        Args:
            theme: Theme name ("light" or "dark")
        """
        # Update action states to ensure exclusivity
        if theme == "light":
            self.light_theme_action.setChecked(True)
            self.dark_theme_action.setChecked(False)
        else:  # dark
            self.light_theme_action.setChecked(False)
            self.dark_theme_action.setChecked(True)
        
        # Save to config and apply
        self.config_manager.set_theme(theme)
        self._apply_theme()
    
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
                widgets = self.main_toolbar.findChildren(QWidget)
                for widget in widgets:
                    if hasattr(widget, 'defaultAction') and widget.defaultAction() == self.privacy_mode_action:
                        widget.setStyleSheet("")
                        break
        else:
            # Privacy is OFF - button should say "Privacy is OFF" and be highlighted in red
            self.privacy_mode_action.setText("Privacy is OFF")
            self.privacy_mode_action.setChecked(True)
            # Apply red background highlighting
            if hasattr(self, 'main_toolbar'):
                widgets = self.main_toolbar.findChildren(QWidget)
                for widget in widgets:
                    if hasattr(widget, 'defaultAction') and widget.defaultAction() == self.privacy_mode_action:
                        widget.setStyleSheet("background-color: #ff0000; font-weight: bold;")
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
    <h2>DICOM Viewer V3</h2>
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
    <li>Cine Playback: Automatic frame-by-frame playback for multi-frame DICOM series with play/pause/stop controls, adjustable speed, and loop option</li>
    </ul>
    <h4>Analysis Tools:</h4>
    <ul>
    <li>Draw elliptical and rectangular ROIs</li>
    <li>ROI statistics (mean, std dev, min, max, area)</li>
    <li>Distance measurements (pixels, mm, cm)</li>
    <li>Histogram display: View pixel value distribution with window/level overlay (H key)</li>
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
    </ul>
    <h4>Planned Features (Not yet implemented):</h4>
    <ul>
    <li>RT STRUCT overlays</li>
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
            mode: Mouse mode ("select", "roi_ellipse", "roi_rectangle", "measure", "zoom", "pan", "auto_window_level")
        """
        # Uncheck all actions first
        all_actions = [
            self.mouse_mode_select_action,
            self.mouse_mode_ellipse_roi_action,
            self.mouse_mode_rectangle_roi_action,
            self.mouse_mode_measure_action,
            self.mouse_mode_zoom_action,
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
        elif mode == "zoom":
            self.mouse_mode_zoom_action.setChecked(True)
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
            Current mouse mode string ("select", "roi_ellipse", "roi_rectangle", "measure", "zoom", "pan", "auto_window_level")
        """
        if self.mouse_mode_select_action.isChecked():
            return "select"
        elif self.mouse_mode_ellipse_roi_action.isChecked():
            return "roi_ellipse"
        elif self.mouse_mode_rectangle_roi_action.isChecked():
            return "roi_rectangle"
        elif self.mouse_mode_measure_action.isChecked():
            return "measure"
        elif self.mouse_mode_zoom_action.isChecked():
            return "zoom"
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
            mode: Mouse mode ("select", "roi_ellipse", "roi_rectangle", "measure", "zoom", "pan", "auto_window_level")
        """
        # All mouse mode actions
        all_actions = [
            self.mouse_mode_select_action,
            self.mouse_mode_ellipse_roi_action,
            self.mouse_mode_rectangle_roi_action,
            self.mouse_mode_measure_action,
            self.mouse_mode_zoom_action,
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
        elif mode == "zoom":
            self.mouse_mode_zoom_action.setChecked(True)
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
                display_name = os.path.basename(file_path) if os.path.isfile(file_path) else os.path.basename(file_path)
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
        if obj != self.recent_menu:
            return super().eventFilter(obj, event)
        
        # Check if it's a context menu event (right-click)
        if event.type() == QEvent.Type.ContextMenu:
            context_event = QContextMenuEvent(event)
            # Get the action at the mouse position
            action = self.recent_menu.actionAt(self.recent_menu.mapFromGlobal(context_event.globalPos()))
            
            # Only show context menu if it's a recent file action (has data)
            if action is not None and action.data():
                file_path = action.data()
                # Create context menu
                context_menu = QMenu(self)
                remove_action = QAction("Remove", self)
                remove_action.triggered.connect(
                    lambda: self._remove_recent_file(file_path)
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
        
        # Save splitter positions
        sizes = self.splitter.sizes()
        self.config_manager.set("splitter_sizes", sizes)
        self.config_manager.save_config()
        
        # Emit signal to notify that viewport size changed
        # Use QTimer to batch rapid splitter movements
        from PySide6.QtCore import QTimer
        QTimer.singleShot(10, lambda: self.viewport_resized.emit())
    
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
        self.undo_tag_edit_action.setEnabled(can_undo)
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
                # Add navigator to bottom of layout
                main_layout.addWidget(navigator_widget)
                # Initially hide it
                navigator_widget.setVisible(False)
                self.series_navigator_visible = False
    
    def toggle_series_navigator(self) -> None:
        """Toggle series navigator visibility."""
        if self.series_navigator is None:
            return
        
        # Emit viewport_resizing before change to preserve centering
        self.viewport_resizing.emit()
        
        # Toggle visibility
        self.series_navigator_visible = not self.series_navigator_visible
        self.series_navigator.setVisible(self.series_navigator_visible)
        
        # Update toolbar button text
        if hasattr(self, 'series_navigator_action'):
            if self.series_navigator_visible:
                self.series_navigator_action.setText("Hide Series Navigator")
            else:
                self.series_navigator_action.setText("Show Series Navigator")
        
        # Emit signal
        self.series_navigator_visibility_changed.emit(self.series_navigator_visible)
        
        # Emit viewport_resized after change to restore centering
        from PySide6.QtCore import QTimer
        QTimer.singleShot(10, lambda: self.viewport_resized.emit())
    
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
        # Update menu checkmarks
        self.layout_1x1_action.setChecked(layout_mode == "1x1")
        self.layout_1x2_action.setChecked(layout_mode == "1x2")
        self.layout_2x1_action.setChecked(layout_mode == "2x1")
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
        # Save window geometry
        geometry = self.geometry()
        self.config_manager.set("window_width", geometry.width())
        self.config_manager.set("window_height", geometry.height())
        self.config_manager.save_config()
        
        event.accept()


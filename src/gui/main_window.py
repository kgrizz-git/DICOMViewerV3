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
                                QApplication, QDialog, QTextBrowser, QPushButton, QDialogButtonBox, QMenu,
                                QScrollArea, QFrame)
from PySide6.QtCore import Qt, Signal, QEvent, QBuffer, QByteArray, QIODevice, QDir
from PySide6.QtGui import QAction, QIcon, QKeySequence, QColor, QDragEnterEvent, QDropEvent, QPixmap
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
from gui.main_window_menu_builder import build_menu_bar


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
        base_path = Path(sys._MEIPASS)
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
    reset_all_views_requested = Signal()  # Emitted when reset all views is requested
    viewport_resized = Signal()  # Emitted when splitter moves and viewport size changes
    viewport_resizing = Signal()  # Emitted when splitter starts moving (before resize completes)
    series_navigation_requested = Signal(int)  # Emitted when series navigation is requested (-1 for prev, 1 for next)
    rescale_toggle_changed = Signal(bool)  # Emitted when rescale toggle changes (True = use rescaled values)
    clear_measurements_requested = Signal()  # Emitted when clear measurements is requested
    quick_start_guide_requested = Signal()  # Emitted when Quick Start Guide is requested
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
    about_this_file_requested = Signal()  # Emitted when About this File is requested
    histogram_requested = Signal()  # Emitted when Histogram dialog is requested
    export_roi_statistics_requested = Signal()  # Emitted when Export ROI Statistics is requested
    export_customizations_requested = Signal()  # Emitted when Export Customizations is requested
    import_customizations_requested = Signal()  # Emitted when Import Customizations is requested
    export_tag_presets_requested = Signal()  # Emitted when Export Tag Presets is requested
    import_tag_presets_requested = Signal()  # Emitted when Import Tag Presets is requested
    copy_annotation_requested = Signal()  # Emitted when copy annotation is requested
    paste_annotation_requested = Signal()  # Emitted when paste annotation is requested
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
        
        # Text Annotation tool
        self.mouse_mode_text_annotation_action = QAction("Text", self)
        self.mouse_mode_text_annotation_action.setCheckable(True)
        self.mouse_mode_text_annotation_action.setShortcut(QKeySequence("T"))
        self.mouse_mode_text_annotation_action.triggered.connect(
            lambda: self._on_mouse_mode_changed("text_annotation")
        )
        toolbar.addAction(self.mouse_mode_text_annotation_action)
        
        # Arrow Annotation tool
        self.mouse_mode_arrow_annotation_action = QAction("Arrow", self)
        self.mouse_mode_arrow_annotation_action.setCheckable(True)
        self.mouse_mode_arrow_annotation_action.setShortcut(QKeySequence("A"))
        self.mouse_mode_arrow_annotation_action.triggered.connect(
            lambda: self._on_mouse_mode_changed("arrow_annotation")
        )
        toolbar.addAction(self.mouse_mode_arrow_annotation_action)
        
        self.mouse_mode_crosshair_action = QAction("Crosshair", self)
        self.mouse_mode_crosshair_action.setCheckable(True)
        self.mouse_mode_crosshair_action.triggered.connect(
            lambda: self._on_mouse_mode_changed("crosshair")
        )
        toolbar.addAction(self.mouse_mode_crosshair_action)
        
        self.mouse_mode_zoom_action = QAction("Zoom", self)
        self.mouse_mode_zoom_action.setCheckable(True)
        self.mouse_mode_zoom_action.triggered.connect(
            lambda: self._on_mouse_mode_changed("zoom")
        )
        toolbar.addAction(self.mouse_mode_zoom_action)
        
        self.mouse_mode_magnifier_action = QAction("Magnifier", self)
        self.mouse_mode_magnifier_action.setCheckable(True)
        self.mouse_mode_magnifier_action.triggered.connect(
            lambda: self._on_mouse_mode_changed("magnifier")
        )
        toolbar.addAction(self.mouse_mode_magnifier_action)
        
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
        
        # Reset View button (shared action with View menu; V or Shift+V for focused subwindow)
        toolbar.addAction(self.reset_view_action)
        
        # Reset All Views button
        reset_all_views_action = QAction("Reset All Views", self)
        reset_all_views_action.setToolTip("Reset zoom, pan, window center and level for all subwindows")
        reset_all_views_action.setShortcut(QKeySequence("Shift+A"))
        reset_all_views_action.triggered.connect(self.reset_all_views_requested.emit)
        toolbar.addAction(reset_all_views_action)
        
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
        
        # Left panel (for metadata, series list, etc.) - Make scrollable
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        left_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        self.left_panel = QWidget()
        self.left_panel.setObjectName("left_panel")
        left_scroll.setWidget(self.left_panel)
        left_scroll.setMaximumWidth(400)
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
        right_scroll.setMaximumWidth(400)
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
            base_path = Path(sys._MEIPASS)
        else:
            base_path = Path(__file__).parent.parent.parent

        resources_dir = str((base_path / "resources" / "images").resolve())
        QDir.addSearchPath('images', resources_dir)

        white_checkmark_path = "images:checkbox_checkmark_white.png"
        black_checkmark_path = "images:checkbox_checkmark_black.png"

        stylesheet = get_theme_stylesheet(theme, white_checkmark_path, black_checkmark_path)

        if self.image_viewer is not None:
            self.image_viewer.set_background_color(get_theme_viewer_background_color(theme))

        QApplication.instance().setStyleSheet(stylesheet)
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

    def set_smooth_when_zoomed_checked(self, checked: bool) -> None:
        """Sync the View menu Image Smoothing action check state without emitting triggered."""
        if not hasattr(self, 'smooth_when_zoomed_action') or self.smooth_when_zoomed_action is None:
            return
        self.smooth_when_zoomed_action.blockSignals(True)
        self.smooth_when_zoomed_action.setChecked(checked)
        self.smooth_when_zoomed_action.blockSignals(False)

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
            icon_data = buffer.data().toBase64().data().decode()
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


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
                                QMessageBox, QComboBox, QLabel, QSizePolicy, QColorDialog)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QIcon, QKeySequence, QColor
from typing import Optional
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.config_manager import ConfigManager


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
    export_requested = Signal()
    settings_requested = Signal()
    tag_viewer_requested = Signal()
    overlay_config_requested = Signal()
    mouse_mode_changed = Signal(str)  # Emitted when mouse mode changes ("roi_ellipse", "roi_rectangle", "measure", "zoom", "pan", "auto_window_level")
    scroll_wheel_mode_changed = Signal(str)  # Emitted when scroll wheel mode changes ("slice" or "zoom")
    overlay_font_size_changed = Signal(int)  # Emitted when overlay font size changes
    overlay_font_color_changed = Signal(int, int, int)  # Emitted when overlay font color changes (r, g, b)
    reset_view_requested = Signal()  # Emitted when reset view is requested
    viewport_resized = Signal()  # Emitted when splitter moves and viewport size changes
    
    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """
        Initialize the main window.
        
        Args:
            config_manager: Optional ConfigManager instance
        """
        super().__init__()
        
        self.config_manager = config_manager or ConfigManager()
        
        # Window properties
        self.setWindowTitle("DICOM Viewer V2")
        self.setGeometry(100, 100, 
                        self.config_manager.get("window_width", 1200),
                        self.config_manager.get("window_height", 800))
        
        # Create UI components
        self._create_menu_bar()
        self._create_toolbar()
        self._create_status_bar()
        self._create_central_widget()
        
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
        self._update_recent_menu()
        
        file_menu.addSeparator()
        
        # Export action
        export_action = QAction("&Export...", self)
        export_action.setShortcut(QKeySequence("Ctrl+E"))
        export_action.triggered.connect(self.export_requested.emit)
        file_menu.addAction(export_action)
        
        file_menu.addSeparator()
        
        # Exit action
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
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
        
        # Tools menu
        tools_menu = menubar.addMenu("&Tools")
        
        # Settings action
        settings_action = QAction("&Settings...", self)
        settings_action.setShortcut(QKeySequence.Preferences)
        settings_action.triggered.connect(self.settings_requested.emit)
        tools_menu.addAction(settings_action)
        
        tools_menu.addSeparator()
        
        # Tag Viewer action
        tag_viewer_action = QAction("DICOM Tag &Viewer...", self)
        tag_viewer_action.setShortcut(QKeySequence("Ctrl+T"))
        tag_viewer_action.triggered.connect(self.tag_viewer_requested.emit)
        tools_menu.addAction(tag_viewer_action)
        
        # Overlay Configuration action
        overlay_config_action = QAction("Overlay &Configuration...", self)
        overlay_config_action.setShortcut(QKeySequence("Ctrl+O"))
        overlay_config_action.triggered.connect(self.overlay_config_requested.emit)
        tools_menu.addAction(overlay_config_action)
        
        # Help menu
        help_menu = menubar.addMenu("&Help")
        
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
        
        # Auto Window/Level ROI tool
        self.mouse_mode_auto_window_level_action = QAction("Auto Window/Level", self)
        self.mouse_mode_auto_window_level_action.setCheckable(True)
        self.mouse_mode_auto_window_level_action.triggered.connect(
            lambda: self._on_mouse_mode_changed("auto_window_level")
        )
        toolbar.addAction(self.mouse_mode_auto_window_level_action)
        
        toolbar.addSeparator()
        
        # Reset View button
        reset_view_action = QAction("Reset View", self)
        reset_view_action.setToolTip("Reset zoom, pan, window center and level to initial values")
        reset_view_action.triggered.connect(self.reset_view_requested.emit)
        toolbar.addAction(reset_view_action)
        
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
        
        # Add stretch to push scroll wheel mode toggle to the right
        toolbar.addSeparator()
        
        # Create spacer widget that expands
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)
        
        toolbar.addWidget(QLabel("Scroll Wheel:"))
        
        # Scroll wheel mode toggle (right-aligned)
        self.scroll_wheel_mode_combo = QComboBox()
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
        self.statusBar().showMessage("Ready")
    
    def _create_central_widget(self) -> None:
        """Create the central widget area."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Splitter for resizable panels
        self.splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(self.splitter)
        
        # Left panel (for metadata, series list, etc.)
        self.left_panel = QWidget()
        self.left_panel.setMaximumWidth(300)
        self.left_panel.setMinimumWidth(200)
        self.splitter.addWidget(self.left_panel)
        
        # Center panel (for image viewer)
        self.center_panel = QWidget()
        self.splitter.addWidget(self.center_panel)
        
        # Right panel (for tools, histogram, etc.)
        self.right_panel = QWidget()
        self.right_panel.setMaximumWidth(300)
        self.right_panel.setMinimumWidth(200)
        self.splitter.addWidget(self.right_panel)
        
        # Set splitter proportions
        self.splitter.setSizes([200, 800, 200])
        
        # Connect to splitter moved signal to update overlay positions when panels are resized
        self.splitter.splitterMoved.connect(self._on_splitter_moved)
    
    def _apply_theme(self) -> None:
        """Apply the current theme to the window."""
        theme = self.config_manager.get_theme()
        
        if theme == "dark":
            # Dark theme - apply light colors (stylesheets are reversed)
            self.setStyleSheet("")
        else:
            # Light theme (default) - apply dark colors (stylesheets are reversed)
            self.setStyleSheet("""
                QMainWindow {
                    background-color: #2b2b2b;
                    color: #ffffff;
                }
                QMenuBar {
                    background-color: #3c3c3c;
                    color: #ffffff;
                }
                QMenuBar::item:selected {
                    background-color: #505050;
                }
                QToolBar {
                    background-color: #3c3c3c;
                    color: #ffffff;
                }
                QStatusBar {
                    background-color: #3c3c3c;
                    color: #ffffff;
                }
            """)
    
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
    
    def _show_about(self) -> None:
        """Show the about dialog."""
        QMessageBox.about(self, "About DICOM Viewer V2",
                         "DICOM Viewer V2\n\n"
                         "A cross-platform DICOM viewer application.\n\n"
                         "Features:\n"
                         "- View DICOM images with zoom and pan\n"
                         "- Draw ROIs and measure distances\n"
                         "- Customizable metadata overlays\n"
                         "- Export to multiple formats")
    
    def _on_mouse_mode_changed(self, mode: str) -> None:
        """
        Handle mouse mode change to ensure exclusivity.
        
        Args:
            mode: Mouse mode ("roi_ellipse", "roi_rectangle", "measure", "zoom", "pan", "auto_window_level")
        """
        # Uncheck all other actions
        all_actions = [
            self.mouse_mode_ellipse_roi_action,
            self.mouse_mode_rectangle_roi_action,
            self.mouse_mode_measure_action,
            self.mouse_mode_zoom_action,
            self.mouse_mode_pan_action,
            self.mouse_mode_auto_window_level_action
        ]
        
        for action in all_actions:
            if action != self.mouse_mode_ellipse_roi_action and mode == "roi_ellipse":
                action.setChecked(False)
            elif action != self.mouse_mode_rectangle_roi_action and mode == "roi_rectangle":
                action.setChecked(False)
            elif action != self.mouse_mode_measure_action and mode == "measure":
                action.setChecked(False)
            elif action != self.mouse_mode_zoom_action and mode == "zoom":
                action.setChecked(False)
            elif action != self.mouse_mode_pan_action and mode == "pan":
                action.setChecked(False)
            elif action != self.mouse_mode_auto_window_level_action and mode == "auto_window_level":
                action.setChecked(False)
        
        # Emit signal
        self.mouse_mode_changed.emit(mode)
    
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
            # Add action for each recent file
            for i, file_path in enumerate(recent_files):
                # Create display name (truncate if too long)
                display_name = os.path.basename(file_path) if os.path.isfile(file_path) else os.path.basename(file_path)
                if len(display_name) > 50:
                    display_name = display_name[:47] + "..."
                
                # Add number prefix for keyboard shortcuts (1-9, 0)
                number = (i + 1) % 10
                if number == 0:
                    number = 10
                action_text = f"&{number} {display_name}"
                
                recent_action = QAction(action_text, self)
                recent_action.setData(file_path)  # Store full path in action data
                recent_action.triggered.connect(
                    lambda checked, path=file_path: self.open_recent_file_requested.emit(path)
                )
                self.recent_menu.addAction(recent_action)
    
    def update_recent_menu(self) -> None:
        """
        Public method to update recent menu (called from outside).
        """
        self._update_recent_menu()
    
    def _on_splitter_moved(self, pos: int, index: int) -> None:
        """
        Handle splitter movement.
        
        When the splitter moves, the viewport size changes, so we need to
        update overlay positions to keep them anchored to viewport edges.
        
        Args:
            pos: New position of the splitter handle
            index: Index of the splitter handle that moved
        """
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
        self.statusBar().showMessage(message)
    
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


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
                                QMessageBox, QButtonGroup)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QIcon, QKeySequence
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
    export_requested = Signal()
    settings_requested = Signal()
    tag_viewer_requested = Signal()
    
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
        
        # Theme actions
        theme_menu = view_menu.addMenu("&Theme")
        light_theme_action = QAction("&Light", self)
        light_theme_action.setCheckable(True)
        light_theme_action.setChecked(self.config_manager.get_theme() == "light")
        light_theme_action.triggered.connect(lambda: self._set_theme("light"))
        theme_menu.addAction(light_theme_action)
        
        dark_theme_action = QAction("&Dark", self)
        dark_theme_action.setCheckable(True)
        dark_theme_action.setChecked(self.config_manager.get_theme() == "dark")
        dark_theme_action.triggered.connect(lambda: self._set_theme("dark"))
        theme_menu.addAction(dark_theme_action)
        
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
        
        # Open file action
        open_file_action = QAction("Open File", self)
        open_file_action.triggered.connect(self.open_file_requested.emit)
        toolbar.addAction(open_file_action)
        
        toolbar.addSeparator()
        
        # ROI tools
        self.roi_rectangle_action = QAction("Rectangle ROI", self)
        self.roi_rectangle_action.setCheckable(True)
        toolbar.addAction(self.roi_rectangle_action)
        
        self.roi_ellipse_action = QAction("Ellipse ROI", self)
        self.roi_ellipse_action.setCheckable(True)
        toolbar.addAction(self.roi_ellipse_action)
        
        self.roi_none_action = QAction("None", self)
        self.roi_none_action.setCheckable(True)
        self.roi_none_action.setChecked(True)
        toolbar.addAction(self.roi_none_action)
        
        # Create button group for ROI tools
        self.roi_button_group = QButtonGroup()
        self.roi_button_group.addButton(self.roi_rectangle_action, 0)
        self.roi_button_group.addButton(self.roi_ellipse_action, 1)
        self.roi_button_group.addButton(self.roi_none_action, 2)
    
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
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # Left panel (for metadata, series list, etc.)
        self.left_panel = QWidget()
        self.left_panel.setMaximumWidth(300)
        self.left_panel.setMinimumWidth(200)
        splitter.addWidget(self.left_panel)
        
        # Center panel (for image viewer)
        self.center_panel = QWidget()
        splitter.addWidget(self.center_panel)
        
        # Right panel (for tools, histogram, etc.)
        self.right_panel = QWidget()
        self.right_panel.setMaximumWidth(300)
        self.right_panel.setMinimumWidth(200)
        splitter.addWidget(self.right_panel)
        
        # Set splitter proportions
        splitter.setSizes([200, 800, 200])
    
    def _apply_theme(self) -> None:
        """Apply the current theme to the window."""
        theme = self.config_manager.get_theme()
        
        if theme == "dark":
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
        else:
            # Light theme (default)
            self.setStyleSheet("")
    
    def _set_theme(self, theme: str) -> None:
        """
        Set the application theme.
        
        Args:
            theme: Theme name ("light" or "dark")
        """
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


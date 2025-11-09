"""
Mouse Mode Handler

This module handles mouse mode and scroll wheel mode changes.

Inputs:
    - Mouse mode change requests
    - Scroll wheel mode change requests
    
Outputs:
    - Updated mouse modes
    - Updated scroll wheel modes
    
Requirements:
    - ImageViewer for mouse mode
    - MainWindow for toolbar updates
    - SliceNavigator for scroll wheel mode
    - ConfigManager for configuration
"""

from typing import Optional
from gui.image_viewer import ImageViewer
from gui.main_window import MainWindow
from gui.slice_navigator import SliceNavigator
from utils.config_manager import ConfigManager


class MouseModeHandler:
    """
    Handles mouse mode and scroll wheel mode changes.
    
    Responsibilities:
    - Handle mouse mode changes
    - Handle scroll wheel mode changes
    - Update UI to reflect mode changes
    """
    
    def __init__(
        self,
        image_viewer: ImageViewer,
        main_window: MainWindow,
        slice_navigator: SliceNavigator,
        config_manager: ConfigManager
    ):
        """
        Initialize the mouse mode handler.
        
        Args:
            image_viewer: Image viewer widget
            main_window: Main window for toolbar updates
            slice_navigator: Slice navigator widget
            config_manager: Configuration manager
        """
        self.image_viewer = image_viewer
        self.main_window = main_window
        self.slice_navigator = slice_navigator
        self.config_manager = config_manager
    
    def handle_mouse_mode_changed(self, mode: str) -> None:
        """
        Handle mouse mode change from toolbar.
        
        Args:
            mode: Mouse mode ("select", "roi_ellipse", "roi_rectangle", "measure", "zoom", "pan", "auto_window_level")
        """
        self.image_viewer.set_mouse_mode(mode)
    
    def set_mouse_mode(self, mode: str) -> None:
        """
        Set mouse mode programmatically (e.g., from keyboard shortcuts).
        
        Updates both the image viewer and the toolbar UI to ensure consistent state.
        This method is used for programmatic mode changes (like keyboard shortcuts)
        where we need to update both the viewer and toolbar without triggering signals.
        
        Args:
            mode: Mouse mode ("select", "roi_ellipse", "roi_rectangle", "measure", "zoom", "pan", "auto_window_level")
        """
        # Update image viewer mouse mode
        self.image_viewer.set_mouse_mode(mode)
        # Update toolbar button states without emitting signals
        self.main_window.set_mouse_mode_checked(mode)
    
    def set_roi_mode(self, mode: Optional[str]) -> None:
        """
        Set ROI drawing mode (legacy method for backward compatibility).
        
        Args:
            mode: "rectangle", "ellipse", or None
        """
        self.image_viewer.set_roi_drawing_mode(mode)
    
    def handle_context_menu_mouse_mode_changed(self, mode: str) -> None:
        """
        Handle mouse mode change from context menu.
        Updates toolbar to reflect the change.
        
        Args:
            mode: Mouse mode string
        """
        # Call main_window's _on_mouse_mode_changed() directly to update toolbar buttons
        # This method will update toolbar button states and then emit the signal
        # which will trigger the normal flow (setting mouse mode in image_viewer)
        self.main_window._on_mouse_mode_changed(mode)
    
    def handle_scroll_wheel_mode_changed(self, mode: str) -> None:
        """
        Handle scroll wheel mode change.
        
        Args:
            mode: "slice" or "zoom"
        """
        self.config_manager.set_scroll_wheel_mode(mode)
        self.image_viewer.set_scroll_wheel_mode(mode)
        self.slice_navigator.set_scroll_wheel_mode(mode)
    
    def handle_context_menu_scroll_wheel_mode_changed(self, mode: str) -> None:
        """
        Handle scroll wheel mode change from context menu.
        Updates toolbar combo box to reflect the change.
        
        Args:
            mode: "slice" or "zoom"
        """
        # Update toolbar combo box
        if mode == "slice":
            self.main_window.scroll_wheel_mode_combo.setCurrentText("Slice")
        else:  # zoom
            self.main_window.scroll_wheel_mode_combo.setCurrentText("Zoom")
        
        # Emit the main_window signal to trigger normal flow
        self.main_window.scroll_wheel_mode_changed.emit(mode)


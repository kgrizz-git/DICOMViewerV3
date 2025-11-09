"""
Keyboard Event Handler

This module handles all keyboard shortcuts and events.

Inputs:
    - Keyboard events
    
Outputs:
    - Actions triggered by keyboard shortcuts
    
Requirements:
    - PySide6 for Qt events
    - Various coordinators and managers for actions
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from typing import Optional, Callable
from tools.roi_manager import ROIManager
from tools.measurement_tool import MeasurementTool
from gui.slice_navigator import SliceNavigator
from gui.overlay_manager import OverlayManager
from gui.image_viewer import ImageViewer


class KeyboardEventHandler:
    """
    Handles keyboard shortcuts and events.
    
    Responsibilities:
    - Handle Delete/Backspace (delete ROI/measurement)
    - Handle Arrow keys (slice navigation)
    - Handle Spacebar (toggle overlay)
    - Handle mode switching keys (P, Z, M, S, W, R, E, C, D, V)
    """
    
    def __init__(
        self,
        roi_manager: ROIManager,
        measurement_tool: MeasurementTool,
        slice_navigator: SliceNavigator,
        overlay_manager: OverlayManager,
        image_viewer: ImageViewer,
        set_mouse_mode: Callable[[str], None],
        delete_all_rois_callback: Callable[[], None],
        clear_measurements_callback: Callable[[], None],
        toggle_overlay_callback: Callable[[], None],
        get_selected_roi: Callable[[], Optional[object]],
        delete_roi_callback: Callable[[object], None],
        delete_measurement_callback: Callable[[object], None],
        update_roi_list_callback: Optional[Callable[[], None]] = None,
        clear_roi_statistics_callback: Optional[Callable[[], None]] = None,
        reset_view_callback: Optional[Callable[[], None]] = None
    ):
        """
        Initialize the keyboard event handler.
        
        Args:
            roi_manager: ROI manager
            measurement_tool: Measurement tool
            slice_navigator: Slice navigator
            overlay_manager: Overlay manager
            image_viewer: Image viewer
            set_mouse_mode: Callback to set mouse mode
            delete_all_rois_callback: Callback to delete all ROIs
            clear_measurements_callback: Callback to clear measurements
            toggle_overlay_callback: Callback to toggle overlay
            get_selected_roi: Callback to get selected ROI
            delete_roi_callback: Callback to delete ROI
            delete_measurement_callback: Callback to delete measurement
            update_roi_list_callback: Optional callback to update ROI list
            clear_roi_statistics_callback: Optional callback to clear ROI statistics
            reset_view_callback: Optional callback to reset view
        """
        self.roi_manager = roi_manager
        self.measurement_tool = measurement_tool
        self.slice_navigator = slice_navigator
        self.overlay_manager = overlay_manager
        self.image_viewer = image_viewer
        self.set_mouse_mode = set_mouse_mode
        self.delete_all_rois_callback = delete_all_rois_callback
        self.clear_measurements_callback = clear_measurements_callback
        self.toggle_overlay_callback = toggle_overlay_callback
        self.get_selected_roi = get_selected_roi
        self.delete_roi_callback = delete_roi_callback
        self.delete_measurement_callback = delete_measurement_callback
        self.update_roi_list_callback = update_roi_list_callback
        self.clear_roi_statistics_callback = clear_roi_statistics_callback
        self.reset_view_callback = reset_view_callback
    
    def handle_key_event(self, event: QKeyEvent) -> bool:
        """
        Handle key event.
        
        Args:
            event: Key event
            
        Returns:
            True if event was handled, False otherwise
        """
        if event.type() != QKeyEvent.Type.KeyPress:
            return False
        
        # Delete key to delete selected ROI or measurement
        if event.key() == Qt.Key.Key_Delete or event.key() == Qt.Key.Key_Backspace:
            # Check for selected ROI first (priority)
            selected_roi = self.get_selected_roi()
            if selected_roi:
                self.delete_roi_callback(selected_roi)
                if self.update_roi_list_callback:
                    self.update_roi_list_callback()
                if self.clear_roi_statistics_callback:
                    self.clear_roi_statistics_callback()
                return True
            
            # Check for selected measurement
            if self.image_viewer.scene is not None:
                try:
                    selected_items = self.image_viewer.scene.selectedItems()
                    from tools.measurement_tool import MeasurementItem
                    for item in selected_items:
                        if isinstance(item, MeasurementItem):
                            self.delete_measurement_callback(item)
                            return True
                except RuntimeError:
                    # Scene may have been deleted, ignore
                    pass
        
        # Arrow keys for slice navigation
        elif event.key() == Qt.Key.Key_Up:
            # Up arrow: next slice
            self.slice_navigator.next_slice()
            return True
        elif event.key() == Qt.Key.Key_Down:
            # Down arrow: previous slice
            self.slice_navigator.previous_slice()
            return True
        
        # Spacebar to toggle overlay visibility
        elif event.key() == Qt.Key.Key_Space:
            self.toggle_overlay_callback()
            return True
        
        # P key for Pan mode
        elif event.key() == Qt.Key.Key_P:
            self.set_mouse_mode("pan")
            return True
        
        # Z key for Zoom mode
        elif event.key() == Qt.Key.Key_Z:
            self.set_mouse_mode("zoom")
            return True
        
        # M key for Measure mode
        elif event.key() == Qt.Key.Key_M:
            self.set_mouse_mode("measure")
            return True
        
        # S key for Select mode
        elif event.key() == Qt.Key.Key_S:
            self.set_mouse_mode("select")
            return True
        
        # W key for Window/Level ROI mode
        elif event.key() == Qt.Key.Key_W:
            self.set_mouse_mode("auto_window_level")
            return True
        
        # R key for Rectangle ROI mode
        elif event.key() == Qt.Key.Key_R:
            self.set_mouse_mode("roi_rectangle")
            return True
        
        # E key for Ellipse ROI mode
        elif event.key() == Qt.Key.Key_E:
            self.set_mouse_mode("roi_ellipse")
            return True
        
        # C key for Clear measurements
        elif event.key() == Qt.Key.Key_C:
            self.clear_measurements_callback()
            return True
        
        # D key for Delete All ROIs on current slice
        elif event.key() == Qt.Key.Key_D:
            self.delete_all_rois_callback()
            return True
        
        # V key for Reset View
        elif event.key() == Qt.Key.Key_V:
            if self.reset_view_callback:
                self.reset_view_callback()
            return True
        
        return False


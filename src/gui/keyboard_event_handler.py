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
    - Handle mode switching keys (P, Z, M, S, W, R, E, C, D, V, N)
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
        reset_view_callback: Optional[Callable[[], None]] = None,
        toggle_series_navigator_callback: Optional[Callable[[], None]] = None,
        invert_image_callback: Optional[Callable[[], None]] = None,
        open_histogram_callback: Optional[Callable[[], None]] = None,
        reset_all_views_callback: Optional[Callable[[], None]] = None,
        toggle_privacy_view_callback: Optional[Callable[[bool], None]] = None,
        get_privacy_view_state_callback: Optional[Callable[[], bool]] = None,
        delete_text_annotation_callback: Optional[Callable[[object], None]] = None,
        delete_arrow_annotation_callback: Optional[Callable[[object], None]] = None,
        change_layout_callback: Optional[Callable[[str], None]] = None
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
            toggle_series_navigator_callback: Optional callback to toggle series navigator
            invert_image_callback: Optional callback to invert image
            open_histogram_callback: Optional callback to open histogram dialog
            reset_all_views_callback: Optional callback to reset all views
            toggle_privacy_view_callback: Optional callback to toggle privacy view (takes enabled bool)
            get_privacy_view_state_callback: Optional callback to get current privacy view state (returns bool)
            change_layout_callback: Optional callback to change layout mode (takes layout_mode string: "1x1", "1x2", "2x1", or "2x2")
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
        self.toggle_series_navigator_callback = toggle_series_navigator_callback
        self.invert_image_callback = invert_image_callback
        self.open_histogram_callback = open_histogram_callback
        self.reset_all_views_callback = reset_all_views_callback
        self.toggle_privacy_view_callback = toggle_privacy_view_callback
        self.get_privacy_view_state_callback = get_privacy_view_state_callback
        self.delete_text_annotation_callback = delete_text_annotation_callback
        self.delete_arrow_annotation_callback = delete_arrow_annotation_callback
        self.change_layout_callback = change_layout_callback
    
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
            
            # Check for selected measurement, text annotation, or arrow annotation
            if self.image_viewer.scene is not None:
                try:
                    selected_items = self.image_viewer.scene.selectedItems()
                    from tools.measurement_tool import MeasurementItem
                    from tools.text_annotation_tool import TextAnnotationItem
                    from tools.arrow_annotation_tool import ArrowAnnotationItem
                    for item in selected_items:
                        if isinstance(item, MeasurementItem):
                            self.delete_measurement_callback(item)
                            return True
                        elif isinstance(item, TextAnnotationItem):
                            # Delete text annotation if callback is available
                            if hasattr(self, 'delete_text_annotation_callback') and self.delete_text_annotation_callback:
                                self.delete_text_annotation_callback(item)
                                return True
                        elif isinstance(item, ArrowAnnotationItem):
                            # Delete arrow annotation if callback is available
                            if hasattr(self, 'delete_arrow_annotation_callback') and self.delete_arrow_annotation_callback:
                                self.delete_arrow_annotation_callback(item)
                                return True
                except RuntimeError:
                    # Scene may have been deleted, ignore
                    pass
        
        # Arrow keys for slice navigation
        elif event.key() == Qt.Key.Key_Up or event.key() == Qt.Key.Key_Down:
            # Check if any text annotation is being edited - if so, don't process arrow keys for navigation
            from tools.text_annotation_tool import is_any_text_annotation_editing
            if self.image_viewer.scene is not None and is_any_text_annotation_editing(self.image_viewer.scene):
                # Let the text editor handle arrow keys for cursor movement
                return False
            
            if event.key() == Qt.Key.Key_Up:
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
            # Don't intercept if Cmd/Ctrl is pressed (for standard shortcuts)
            if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
                return False  # Let Qt handle Cmd+P / Ctrl+P
            self.set_mouse_mode("pan")
            return True
        
        # Z key for Zoom mode
        elif event.key() == Qt.Key.Key_Z:
            # Don't intercept if Cmd/Ctrl is pressed (for standard shortcuts)
            if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
                return False  # Let Qt handle Cmd+Z / Ctrl+Z
            self.set_mouse_mode("zoom")
            return True
        
        # G key for Magnifier mode
        elif event.key() == Qt.Key.Key_G:
            self.set_mouse_mode("magnifier")
            return True
        
        # M key for Measure mode
        elif event.key() == Qt.Key.Key_M:
            # Don't intercept if Cmd/Ctrl is pressed (for standard shortcuts)
            if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
                return False  # Let Qt handle Cmd+M / Ctrl+M
            self.set_mouse_mode("measure")
            return True
        
        # S key for Select mode
        elif event.key() == Qt.Key.Key_S:
            # Don't intercept if Cmd/Ctrl is pressed (for standard shortcuts)
            if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
                return False  # Let Qt handle Cmd+S / Ctrl+S
            self.set_mouse_mode("select")
            return True
        
        # W key for Window/Level ROI mode
        elif event.key() == Qt.Key.Key_W:
            # Don't intercept if Cmd/Ctrl is pressed (for standard shortcuts)
            if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
                return False  # Let Qt handle Cmd+W / Ctrl+W
            self.set_mouse_mode("auto_window_level")
            return True
        
        # R key for Rectangle ROI mode
        elif event.key() == Qt.Key.Key_R:
            # Don't intercept if Cmd/Ctrl is pressed (for standard shortcuts)
            if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
                return False  # Let Qt handle Cmd+R / Ctrl+R
            self.set_mouse_mode("roi_rectangle")
            return True
        
        # E key for Ellipse ROI mode
        elif event.key() == Qt.Key.Key_E:
            # Don't intercept if Cmd/Ctrl is pressed (for standard shortcuts)
            if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
                return False  # Let Qt handle Cmd+E / Ctrl+E
            self.set_mouse_mode("roi_ellipse")
            return True
        
        # H key for Crosshair mode
        elif event.key() == Qt.Key.Key_H:
            # Don't intercept if Cmd/Ctrl is pressed (for standard shortcuts)
            if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
                return False  # Let Qt handle Cmd+H / Ctrl+H
            self.set_mouse_mode("crosshair")
            return True
        
        # C key for Clear measurements
        elif event.key() == Qt.Key.Key_C:
            # Don't intercept if Cmd/Ctrl is pressed (for standard shortcuts)
            if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
                return False  # Let Qt handle Cmd+C / Ctrl+C
            self.clear_measurements_callback()
            return True
        
        # D key for Delete All ROIs on current slice
        elif event.key() == Qt.Key.Key_D:
            # Don't intercept if Cmd/Ctrl is pressed (for standard shortcuts)
            if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
                return False  # Let Qt handle Cmd+D / Ctrl+D
            self.delete_all_rois_callback()
            return True
        
        # V key - available (Shift+V for Reset View)
        elif event.key() == Qt.Key.Key_V:
            # Check for Shift modifier for Reset View
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                # Shift+V: Reset View
                if self.reset_view_callback:
                    self.reset_view_callback()
                return True
            # Don't intercept if Cmd/Ctrl is pressed (for standard shortcuts like Ctrl+V)
            if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
                return False  # Let Qt handle Cmd+V / Ctrl+V
            # Single V key is available (not used)
            return False
        
        # N key for Toggle Series Navigator
        elif event.key() == Qt.Key.Key_N:
            # Don't intercept if Cmd/Ctrl is pressed (for standard shortcuts)
            if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
                return False  # Let Qt handle Cmd+N / Ctrl+N
            if self.toggle_series_navigator_callback:
                self.toggle_series_navigator_callback()
            return True
        
        # I key for Invert Image
        elif event.key() == Qt.Key.Key_I:
            if self.invert_image_callback:
                self.invert_image_callback()
            return True
        
        # Cmd+Shift+H / Ctrl+Shift+H for Histogram
        elif event.key() == Qt.Key.Key_H:
            # Only handle if Cmd/Ctrl+Shift modifiers are pressed
            if (event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier) and
                event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                if self.open_histogram_callback:
                    self.open_histogram_callback()
                return True
            # Regular H key (no modifiers) is for crosshair mode - don't handle here
        
        # Ctrl+P (Cmd+P on Mac) for Privacy View toggle
        elif event.key() == Qt.Key.Key_P and (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            if self.toggle_privacy_view_callback and self.get_privacy_view_state_callback:
                # Get current state and toggle it
                current_state = self.get_privacy_view_state_callback()
                self.toggle_privacy_view_callback(not current_state)
            return True
        
        # A key for Arrow Annotation mode (Shift+A for Reset All Views)
        elif event.key() == Qt.Key.Key_A:
            # Check for Shift modifier for Reset All Views
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                # Shift+A: Reset All Views
                if self.reset_all_views_callback:
                    self.reset_all_views_callback()
                return True
            # Don't intercept if Cmd/Ctrl is pressed (for standard shortcuts like Ctrl+A)
            if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
                return False  # Let Qt handle Cmd+A / Ctrl+A
            # Single A key: Arrow Annotation mode
            self.set_mouse_mode("arrow_annotation")
            return True
        
        # T key for Text Annotation mode
        elif event.key() == Qt.Key.Key_T:
            # Don't intercept if Cmd/Ctrl is pressed (for standard shortcuts like Ctrl+T)
            if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
                return False  # Let Qt handle Cmd+T / Ctrl+T
            self.set_mouse_mode("text_annotation")
            return True
        
        # Layout shortcuts: 1, 2, 3, 4 for 1x1, 1x2, 2x1, 2x2 layouts
        elif event.key() in (Qt.Key.Key_1, Qt.Key.Key_2, Qt.Key.Key_3, Qt.Key.Key_4):
            # Check if any text annotation is being edited - if so, don't process layout shortcuts
            from tools.text_annotation_tool import is_any_text_annotation_editing
            if self.image_viewer.scene is not None and is_any_text_annotation_editing(self.image_viewer.scene):
                # Let the text editor handle the keys
                return False
            
            # Don't intercept if Cmd/Ctrl is pressed (for standard shortcuts)
            if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
                return False  # Let Qt handle Cmd+1-4 / Ctrl+1-4
            
            if self.change_layout_callback:
                if event.key() == Qt.Key.Key_1:
                    self.change_layout_callback("1x1")
                elif event.key() == Qt.Key.Key_2:
                    self.change_layout_callback("1x2")
                elif event.key() == Qt.Key.Key_3:
                    self.change_layout_callback("2x1")
                elif event.key() == Qt.Key.Key_4:
                    self.change_layout_callback("2x2")
            return True
        
        return False


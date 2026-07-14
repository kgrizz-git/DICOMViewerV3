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

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent

from gui.image_viewer import ImageViewer
from gui.overlay_manager import OverlayManager
from gui.slice_navigator import SliceNavigator
from tools.angle_measurement_items import AngleMeasurementItem
from tools.arrow_annotation_tool import ArrowAnnotationItem
from tools.measurement_tool import MeasurementItem, MeasurementTool
from tools.roi_manager import ROIManager
from tools.text_annotation_tool import (
    TextAnnotationItem,
    is_any_text_annotation_editing,
)

CTRL_CMD = Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier


def _has_ctrl_cmd(event: QKeyEvent) -> bool:
    """True when Ctrl (or Cmd on macOS) is held."""
    return bool(event.modifiers() & CTRL_CMD)


def _has_shift(event: QKeyEvent) -> bool:
    """True when Shift is held."""
    return bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)


# Keyed by int, not Qt.Key, because QKeyEvent.key() returns a plain int.
# Keys that map straight onto a mouse mode and share the Ctrl/Cmd passthrough.
_MOUSE_MODE_KEYS: dict[int, str] = {
    Qt.Key.Key_P: "pan",
    Qt.Key.Key_Z: "zoom",
    Qt.Key.Key_S: "select",
    Qt.Key.Key_W: "auto_window_level",
    Qt.Key.Key_R: "roi_rectangle",
    Qt.Key.Key_E: "roi_ellipse",
    Qt.Key.Key_H: "crosshair",
    Qt.Key.Key_T: "text_annotation",
}

# Key -> handler method name. Shift variants live inside their key's handler.
_KEY_HANDLERS: dict[int, str] = {
    **dict.fromkeys(_MOUSE_MODE_KEYS, "_key_mouse_mode"),
    Qt.Key.Key_G: "_key_magnifier",
    Qt.Key.Key_M: "_key_measure",
    Qt.Key.Key_C: "_key_clear_measurements",
    Qt.Key.Key_D: "_key_delete_all_rois",
    Qt.Key.Key_V: "_key_reset_view",
    Qt.Key.Key_Q: "_key_quick_window_level",
    Qt.Key.Key_N: "_key_series_navigator",
    Qt.Key.Key_I: "_key_invert",
    Qt.Key.Key_A: "_key_arrow_annotation",
    Qt.Key.Key_Space: "_key_space",
    Qt.Key.Key_1: "_key_layout",
    Qt.Key.Key_2: "_key_layout",
    Qt.Key.Key_3: "_key_layout",
    Qt.Key.Key_4: "_key_layout",
}


class KeyboardEventHandler:
    """
    Handles keyboard shortcuts and events.
    
    Responsibilities:
    - Handle Delete/Backspace (delete ROI/measurement)
    - Handle Arrow keys (slice navigation)
    - Handle Spacebar (cycle overlay detail minimal / detailed / hidden)
    - Handle Shift+Space (legacy overlay visibility cycle on focused view)
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
        get_selected_roi: Callable[[], object | None],
        delete_roi_callback: Callable[[object], None],
        delete_measurement_callback: Callable[[object], None],
        cycle_overlay_detail_callback: Callable[[], None] | None = None,
        toggle_overlay_visibility_legacy_callback: Callable[[], None] | None = None,
        update_roi_list_callback: Callable[[], None] | None = None,
        clear_roi_statistics_callback: Callable[[], None] | None = None,
        reset_view_callback: Callable[[], None] | None = None,
        toggle_series_navigator_callback: Callable[[], None] | None = None,
        invert_image_callback: Callable[[], None] | None = None,
        reset_all_views_callback: Callable[[], None] | None = None,
        delete_text_annotation_callback: Callable[[object], None] | None = None,
        delete_arrow_annotation_callback: Callable[[object], None] | None = None,
        change_layout_callback: Callable[[str], None] | None = None,
        cycle_three_pane_layout_callback: Callable[[], object] | None = None,
        toggle_two_pane_layout_callback: Callable[[], object] | None = None,
        is_focus_ok_for_reset_view: Callable[[], bool] | None = None,
        open_quick_window_level_callback: Callable[[], None] | None = None,
        cancel_angle_draw_callback: Callable[[], None] | None = None,
        exit_roi_geometry_edit_callback: Callable[[], bool] | None = None,
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
            toggle_overlay_callback: Fallback when cycle callbacks are omitted
            cycle_overlay_detail_callback: Space cycles minimal / detailed / hidden (all panes)
            toggle_overlay_visibility_legacy_callback: Shift+Space legacy visibility cycle (focused pane)
            get_selected_roi: Callback to get selected ROI
            delete_roi_callback: Callback to delete ROI
            delete_measurement_callback: Callback to delete measurement
            update_roi_list_callback: Optional callback to update ROI list
            clear_roi_statistics_callback: Optional callback to clear ROI statistics
            reset_view_callback: Optional callback to reset view
            toggle_series_navigator_callback: Optional callback to toggle series navigator
            invert_image_callback: Optional callback to invert image
            reset_all_views_callback: Optional callback to reset all views
            change_layout_callback: Optional callback for keys 1 and 4 (layout_mode: "1x1" or "2x2")
            cycle_three_pane_layout_callback: Optional callback for key 3 (cycle 3-pane modes)
            toggle_two_pane_layout_callback: Optional callback for key 2 (toggle 1x2 / 2x1)
            is_focus_ok_for_reset_view: Optional callback returning True if focus is in a widget where V should trigger Reset View (e.g. image viewer, navigator)
            open_quick_window_level_callback: Optional callback to open Quick Window/Level dialog for the focused subwindow (shortcut Q)
            cancel_angle_draw_callback: Optional callback to cancel in-progress angle placement (Esc in measure_angle mode)
            exit_roi_geometry_edit_callback: Optional callback to leave ROI resize-handle mode (Esc); return True if handled
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
        self.cycle_overlay_detail_callback = cycle_overlay_detail_callback
        self.toggle_overlay_visibility_legacy_callback = toggle_overlay_visibility_legacy_callback
        self.get_selected_roi = get_selected_roi
        self.delete_roi_callback = delete_roi_callback
        self.delete_measurement_callback = delete_measurement_callback
        self.update_roi_list_callback = update_roi_list_callback
        self.clear_roi_statistics_callback = clear_roi_statistics_callback
        self.reset_view_callback = reset_view_callback
        self.toggle_series_navigator_callback = toggle_series_navigator_callback
        self.invert_image_callback = invert_image_callback
        self.reset_all_views_callback = reset_all_views_callback
        self.delete_text_annotation_callback = delete_text_annotation_callback
        self.delete_arrow_annotation_callback = delete_arrow_annotation_callback
        self.change_layout_callback = change_layout_callback
        self.cycle_three_pane_layout_callback = cycle_three_pane_layout_callback
        self.toggle_two_pane_layout_callback = toggle_two_pane_layout_callback
        self.is_focus_ok_for_reset_view = is_focus_ok_for_reset_view
        self.open_quick_window_level_callback = open_quick_window_level_callback
        self.cancel_angle_draw_callback = cancel_angle_draw_callback
        self.exit_roi_geometry_edit_callback = exit_roi_geometry_edit_callback

    # --- non-uniform handlers (checked before the key table) ----------------

    def _handle_escape(self, event: QKeyEvent) -> bool:
        """Escape: cancel in-progress angle placement, else leave ROI geometry edit."""
        if event.key() != Qt.Key.Key_Escape:
            return False
        if getattr(self.image_viewer, "mouse_mode", "") == "measure_angle":
            if self.cancel_angle_draw_callback:
                self.cancel_angle_draw_callback()
            return True
        exit_roi_edit = self.exit_roi_geometry_edit_callback
        return bool(exit_roi_edit is not None and exit_roi_edit())

    def _handle_delete(self, event: QKeyEvent) -> bool:
        """Delete/Backspace: remove the selected ROI, else the selected scene item."""
        if event.key() not in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            return False

        # A selected ROI takes priority over scene selection.
        selected_roi = self.get_selected_roi()
        if selected_roi:
            self.delete_roi_callback(selected_roi)
            if self.update_roi_list_callback:
                self.update_roi_list_callback()
            if self.clear_roi_statistics_callback:
                self.clear_roi_statistics_callback()
            return True

        if self.image_viewer.scene is None:
            return False
        try:
            for item in self.image_viewer.scene.selectedItems():
                if isinstance(item, (MeasurementItem, AngleMeasurementItem)):
                    self.delete_measurement_callback(item)
                    return True
                if isinstance(item, TextAnnotationItem):
                    if self.delete_text_annotation_callback:
                        self.delete_text_annotation_callback(item)
                        return True
                elif isinstance(item, ArrowAnnotationItem):
                    if self.delete_arrow_annotation_callback:
                        self.delete_arrow_annotation_callback(item)
                        return True
        except RuntimeError:
            # Scene may have been deleted, ignore
            pass
        return False

    def _handle_arrow_navigation(self, event: QKeyEvent) -> bool:
        """Up/Down: slice navigation, unless a text annotation is being edited."""
        key = event.key()
        if key not in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            return False
        if self._is_editing_text():
            # Let the text editor handle arrow keys for cursor movement
            return False

        if key == Qt.Key.Key_Up:
            self.slice_navigator.next_slice()
        else:
            self.slice_navigator.previous_slice()
        return True

    def _is_editing_text(self) -> bool:
        """True while a text annotation in the scene has an active editor."""
        scene = self.image_viewer.scene
        return scene is not None and is_any_text_annotation_editing(scene)

    # --- per-key handlers ---------------------------------------------------

    def _key_mouse_mode(self, event: QKeyEvent) -> bool:
        """Uniform mouse-mode keys: set the mode unless Ctrl/Cmd is held."""
        if _has_ctrl_cmd(event):
            return False  # Let Qt handle the standard Cmd/Ctrl shortcut
        self.set_mouse_mode(_MOUSE_MODE_KEYS[event.key()])
        return True

    def _key_magnifier(self, event: QKeyEvent) -> bool:
        """G: magnifier. Intentionally has no Ctrl/Cmd passthrough."""
        self.set_mouse_mode("magnifier")
        return True

    def _key_measure(self, event: QKeyEvent) -> bool:
        """M: distance measure; Shift+M: angle measure."""
        if _has_ctrl_cmd(event):
            return False
        self.set_mouse_mode("measure_angle" if _has_shift(event) else "measure")
        return True

    def _key_clear_measurements(self, event: QKeyEvent) -> bool:
        """C: clear measurements."""
        if _has_ctrl_cmd(event):
            return False
        self.clear_measurements_callback()
        return True

    def _key_delete_all_rois(self, event: QKeyEvent) -> bool:
        """D: delete all ROIs on the current slice."""
        if _has_ctrl_cmd(event):
            return False
        self.delete_all_rois_callback()
        return True

    def _key_reset_view(self, event: QKeyEvent) -> bool:
        """Shift+V: always reset view. Plain V: reset only when focus allows it."""
        if _has_shift(event):
            if self.reset_view_callback:
                self.reset_view_callback()
            return True
        if _has_ctrl_cmd(event):
            return False
        # Plain V must still type "V" into a text annotation, hence the focus check.
        if (
            self.reset_view_callback
            and self.is_focus_ok_for_reset_view
            and self.is_focus_ok_for_reset_view()
        ):
            self.reset_view_callback()
            return True
        return False

    def _key_quick_window_level(self, event: QKeyEvent) -> bool:
        """Q: open the Quick Window/Level dialog for the focused subwindow."""
        if _has_ctrl_cmd(event):
            return False
        if (
            self.open_quick_window_level_callback
            and self.is_focus_ok_for_reset_view
            and self.is_focus_ok_for_reset_view()
        ):
            self.open_quick_window_level_callback()
            return True
        return False

    def _key_series_navigator(self, event: QKeyEvent) -> bool:
        """N: toggle the series navigator."""
        if _has_ctrl_cmd(event):
            return False
        if self.toggle_series_navigator_callback:
            self.toggle_series_navigator_callback()
        return True

    def _key_invert(self, event: QKeyEvent) -> bool:
        """I: invert image. Intentionally has no Ctrl/Cmd passthrough."""
        if self.invert_image_callback:
            self.invert_image_callback()
        return True

    def _key_arrow_annotation(self, event: QKeyEvent) -> bool:
        """A: arrow annotation mode; Shift+A: reset all views."""
        if _has_shift(event):
            if self.reset_all_views_callback:
                self.reset_all_views_callback()
            return True
        if _has_ctrl_cmd(event):
            return False
        self.set_mouse_mode("arrow_annotation")
        return True

    def _key_space(self, event: QKeyEvent) -> bool:
        """Space: cycle overlay detail across panes; Shift+Space: legacy focused cycle."""
        if _has_shift(event):
            legacy = self.toggle_overlay_visibility_legacy_callback
            if legacy is not None:
                legacy()
            else:
                self.toggle_overlay_callback()
        else:
            cycle = self.cycle_overlay_detail_callback
            if cycle is not None:
                cycle()
            else:
                self.toggle_overlay_callback()
        return True

    def _key_layout(self, event: QKeyEvent) -> bool:
        """1 = 1x1; 2 = toggle 1x2/2x1; 3 = cycle 3-pane; 4 = 2x2."""
        if self._is_editing_text():
            # Let the text editor receive the digit
            return False
        if _has_ctrl_cmd(event):
            return False

        key = event.key()
        if key == Qt.Key.Key_1 and self.change_layout_callback:
            self.change_layout_callback("1x1")
        elif key == Qt.Key.Key_2 and self.toggle_two_pane_layout_callback:
            self.toggle_two_pane_layout_callback()
        elif key == Qt.Key.Key_3 and self.cycle_three_pane_layout_callback:
            self.cycle_three_pane_layout_callback()
        elif key == Qt.Key.Key_4 and self.change_layout_callback:
            self.change_layout_callback("2x2")
        return True

    def handle_key_event(self, event: QKeyEvent) -> bool:
        """
        Handle key event.

        Ctrl/Cmd combos are passed through (return False) for most keys so Qt can
        route them to the menu QActions -- notably Ctrl+P (Privacy View) and
        Ctrl/Cmd+Shift+H (Histogram), which this handler deliberately does not own.

        Args:
            event: Key event

        Returns:
            True if event was handled, False otherwise
        """
        if event.type() != QKeyEvent.Type.KeyPress:
            return False

        if self._handle_escape(event):
            return True
        if self._handle_delete(event):
            return True
        if self._handle_arrow_navigation(event):
            return True

        handler_name = _KEY_HANDLERS.get(event.key())
        if handler_name is None:
            return False
        handler: Callable[[QKeyEvent], bool] = getattr(self, handler_name)
        return handler(event)

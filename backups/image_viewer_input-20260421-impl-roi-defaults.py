"""
Image viewer — input routing: gestures, wheel, mouse, keys, drag/drop (Phase 3 split).

Mixin listed before `ImageViewerViewMixin` on `ImageViewer` so Qt event overrides resolve first.
"""
# Pyright: methods run only on ``ImageViewer`` (combined Qt type); mixin bases cannot
# express cross-mixin ``self`` without a duplicate protocol surface.
# pyright: reportAttributeAccessIssue=false, reportUninitializedInstanceVariable=false
from __future__ import annotations

from PySide6.QtWidgets import QGraphicsView, QWidget, QApplication, QMenu
from PySide6.QtCore import Qt, QPointF, QTimer, QEvent
from PySide6.QtGui import (
    QWheelEvent,
    QKeyEvent,
    QMouseEvent,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QNativeGestureEvent,
)
import os
import time
from typing import Optional

from utils.debug_flags import DEBUG_NAV, DEBUG_MAGNIFIER


class ImageViewerInputMixin:
    """event(), wheel, cursor/mouse modes, mouse press/move/release, keys, DnD."""

    def event(self, event: QEvent) -> bool:
        """
        Handle native gesture events (e.g. trackpad pinch-to-zoom).
        Pinch zoom is independent of scroll wheel mode: pinch always zooms the image
        without affecting slice navigation or other wheel behavior.
        """
        if event.type() == QEvent.Type.NativeGesture and isinstance(event, QNativeGestureEvent):
            if event.gestureType() == Qt.NativeGestureType.ZoomNativeGesture:
                self._apply_pinch_zoom(event.value())
                event.accept()
                return True
        return super().event(event)

    def _apply_pinch_zoom(self, value: float) -> None:
        """
        Apply incremental zoom from a native pinch gesture.
        value is the scale delta: new_scale = current_scale * (1 + value).
        Called only when an image is displayed; no-op otherwise.
        """
        if self.image_item is None:
            return
        # Qt: item.scale = item.scale * (1 + event.value()); value is typically small
        new_zoom = self.current_zoom * (1.0 + value)
        new_zoom = max(self.min_zoom, min(self.max_zoom, new_zoom))
        center_scene = self.mapToScene(self.viewport().rect().center())
        self.current_zoom = new_zoom
        self._apply_view_transform()  # type: ignore[attr-defined]
        self.centerOn(center_scene)
        self._check_transform_changed()
        self._restart_smooth_idle_timer()

    def wheelEvent(self, event: QWheelEvent) -> None:
        """
        Handle mouse wheel events for zooming or slice navigation.
        Ctrl+wheel is always treated as zoom (e.g. Windows trackpad pinch sent as Ctrl+wheel).
        """
        # Ctrl+wheel: always zoom (common for trackpad pinch on Windows)
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.angleDelta().y() > 0:
                self.zoom_in()
            elif event.angleDelta().y() < 0:
                self.zoom_out()
            event.accept()
            return
        # Use scroll wheel mode to determine behavior
        if self.scroll_wheel_mode == "zoom":
            # Perform zoom - AnchorViewCenter is set in __init__ and ensures zooming is centered on viewport center
            if event.angleDelta().y() > 0:
                self.zoom_in()
            else:
                self.zoom_out()
        else:
            # Slice navigation mode - emit signal for slice navigator
            self.wheel_event_for_slice.emit(event.angleDelta().y())
        
        event.accept()
    
    def _sync_cursor_to_parent_chain(self) -> None:
        """Mirror the active tool cursor onto the subwindow container and layout QWidget parents."""
        parent = self.parent()
        if not isinstance(parent, QWidget):
            return
        parent.setCursor(self.cursor())
        layout_parent = parent.parent()
        if isinstance(layout_parent, QWidget):
            layout_parent.setCursor(self.cursor())
            layout_grandparent = layout_parent.parent()
            if isinstance(layout_grandparent, QWidget):
                layout_grandparent.setCursor(self.cursor())

    def set_mouse_mode(self, mode: str) -> None:
        """
        Set mouse interaction mode.
        
        Args:
            mode: "select", "roi_ellipse", "roi_rectangle", "measure", "measure_angle", "zoom", "pan", or "auto_window_level"
        """
        prev_mode = self.mouse_mode
        if getattr(self, "_mpr_mode_override", False):
            # In MPR mode we intentionally restrict which tools can be
            # activated to avoid half-implemented interaction types.
            # ROI/measure/WL-ROI must remain enabled for the MPR feature work.
            allowed_modes = {
                "pan",
                "zoom",
                "magnifier",
                "select",
                "roi_ellipse",
                "roi_rectangle",
                "measure",
                "measure_angle",
                "auto_window_level",
                "text_annotation",
                "arrow_annotation",
            }
            if mode not in allowed_modes:
                mode = "pan"

        self.mouse_mode = mode
        
        # Update ROI drawing mode based on mouse mode
        if mode == "select":
            # Select mode - allow clicking on ROIs and measurements to select them
            self.roi_drawing_mode = None
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.setCursor(Qt.CursorShape.ArrowCursor)
        elif mode == "roi_ellipse":
            self.roi_drawing_mode = "ellipse"
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.setCursor(Qt.CursorShape.CrossCursor)
        elif mode == "roi_rectangle":
            self.roi_drawing_mode = "rectangle"
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.setCursor(Qt.CursorShape.CrossCursor)
        elif mode == "auto_window_level":
            # Auto window/level mode - use rectangle ROI drawing
            self.roi_drawing_mode = "rectangle"
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.setCursor(Qt.CursorShape.CrossCursor)
        elif mode == "measure":
            self.roi_drawing_mode = None
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            # Cursor set by _apply_cursor_for_mouse_mode() below
            # Reset measurement state when switching to measure mode
            self.measuring = False
            self.measurement_start_pos = None
        elif mode == "measure_angle":
            self.roi_drawing_mode = None
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.measuring = False
            self.measurement_start_pos = None
        elif mode == "zoom":
            self.roi_drawing_mode = None
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            # Store zoom start position for click-to-zoom
            self.zoom_start_pos: Optional[QPointF] = None
        elif mode == "magnifier":
            self.roi_drawing_mode = None
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            # Use cross cursor for magnifier mode
            self.setCursor(Qt.CursorShape.CrossCursor)
            # Reset magnifier state when switching to magnifier mode
            if self.magnifier_widget is not None:
                self.magnifier_widget.hide()
            self.magnifier_active = False
        elif mode == "crosshair":
            self.roi_drawing_mode = None
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.setCursor(Qt.CursorShape.CrossCursor)
        elif mode == "text_annotation":
            self.roi_drawing_mode = None
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.setCursor(Qt.CursorShape.IBeamCursor)  # Text cursor for text annotation
            # Reset text annotation state when switching to text annotation mode
            self.text_annotating = False
            self.text_annotation_start_pos = None
        elif mode == "arrow_annotation":
            self.roi_drawing_mode = None
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.setCursor(Qt.CursorShape.CrossCursor)  # Cross cursor for arrow annotation
            # Reset arrow annotation state when switching to arrow annotation mode
            self.arrow_annotating = False
            self.arrow_annotation_start_pos = None
        else:  # pan
            self.roi_drawing_mode = None
            # Use ScrollHandDrag for panning - this works even when image fits viewport
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            # Ensure scrollbars are enabled for ScrollHandDrag to work
            self.horizontalScrollBar().setEnabled(True)
            self.verticalScrollBar().setEnabled(True)

        # Keep SubWindowContainer cursor in sync so hit-test on container border shows tool cursor.
        # Also set cursor on the layout parent chain (layout_widget, MultiWindowLayout) so in 1x1
        # any background region shows the tool cursor and doesn't flicker to arrow.
        self._apply_cursor_for_mouse_mode()
        self._sync_cursor_to_parent_chain()

        if prev_mode == "measure_angle" and mode != "measure_angle":
            self.angle_draw_cancel_requested.emit()

    def _apply_cursor_for_mouse_mode(self) -> None:
        """Set cursor to the one appropriate for the current mouse_mode (used by set_mouse_mode and restore_cursor_for_current_mode)."""
        mode = self.mouse_mode
        if mode == "select":
            self.setCursor(Qt.CursorShape.ArrowCursor)
        elif mode in ("roi_ellipse", "roi_rectangle", "measure", "measure_angle", "magnifier", "crosshair", "arrow_annotation") or mode == "auto_window_level":
            self.setCursor(Qt.CursorShape.CrossCursor)
        elif mode == "zoom":
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        elif mode == "text_annotation":
            self.setCursor(Qt.CursorShape.IBeamCursor)
        else:  # pan
            self.setCursor(Qt.CursorShape.OpenHandCursor)

    def restore_cursor_for_current_mode(self) -> None:
        """Restore the cursor to match the current mouse mode (e.g. after hiding it during measurement draw or handle drag)."""
        self._apply_cursor_for_mouse_mode()
        self._sync_cursor_to_parent_chain()

    def set_roi_drawing_mode(self, mode: Optional[str]) -> None:
        """
        Set ROI drawing mode (legacy method for backward compatibility).
        
        Args:
            mode: "rectangle", "ellipse", or None to disable
        """
        self.roi_drawing_mode = mode
        if mode:
            self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
    
    def mousePressEvent(self, event: QMouseEvent) -> None:
        """
        Handle mouse press events for panning or ROI drawing.
        
        Args:
            event: Mouse event
        """
        # Hybrid focus: parent is typically `SubWindowContainer`, but avoid importing it here
        # to prevent a Pyright import-cycle with `gui.sub_window_container`.
        parent = self.parent()
        if (
            parent is not None
            and hasattr(parent, "is_focused")
            and hasattr(parent, "set_focused")
            and hasattr(parent, "focus_changed")
        ):
            if not bool(getattr(parent, "is_focused")):
                if event.button() == Qt.MouseButton.LeftButton:
                    event.accept()
                    getattr(parent, "set_focused")(True)
                    getattr(parent, "focus_changed").emit(True)
                    return
        
        if event.button() == Qt.MouseButton.LeftButton:
            # Handle select mode - allow default Qt selection behavior
            if self.mouse_mode == "select":
                # Check what item is at the click position
                scene_pos = self.mapToScene(event.position().toPoint())
                item = self.scene.itemAt(scene_pos, self.transform())
                
                # Check if clicking on empty space (image item or None)
                from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsEllipseItem
                from tools.measurement_tool import MeasurementItem, MeasurementHandle, DraggableMeasurementText
                from tools.angle_measurement_items import AngleMeasurementItem, AngleVertexHandle, DraggableAngleMeasurementText
                
                is_empty_space = (item is None or item == self.image_item)
                
                # Check if item is an ROI - use ROI manager callback for accurate detection
                is_roi_item = False
                if item is not None and hasattr(self, 'get_roi_from_item_callback') and self.get_roi_from_item_callback:
                    roi = self.get_roi_from_item_callback(item)
                    if roi is not None:
                        is_roi_item = True
                
                # Fallback: check by type if callback not available
                if not is_roi_item:
                    is_roi_item = isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem)) and item != self.image_item
                
                is_measurement_item = isinstance(item, (MeasurementItem, AngleMeasurementItem))
                is_handle = isinstance(item, (MeasurementHandle, AngleVertexHandle))
                is_measurement_text = isinstance(item, (DraggableMeasurementText, DraggableAngleMeasurementText))
                
                # Check for text and arrow annotation items
                from tools.text_annotation_tool import TextAnnotationItem
                from tools.arrow_annotation_tool import ArrowAnnotationItem
                is_text_annotation_item = isinstance(item, TextAnnotationItem)
                is_arrow_annotation_item = isinstance(item, ArrowAnnotationItem)
                
                # Check if item is a child of a measurement (line or text)
                is_measurement_child = False
                if item is not None:
                    parent = item.parentItem()
                    while parent is not None:
                        if isinstance(parent, (MeasurementItem, AngleMeasurementItem)):
                            is_measurement_child = True
                            break
                        parent = parent.parentItem()
                if is_empty_space and not (is_roi_item or is_measurement_item or is_handle or is_measurement_text or is_measurement_child or is_text_annotation_item or is_arrow_annotation_item):
                    # Clicking on empty space - deselect everything
                    # print(f"[DEBUG-DESELECT] Empty space click detected in Select mode")
                    # print(f"[DEBUG-DESELECT]   is_empty_space: {is_empty_space}, is_roi_item: {is_roi_item}, is_measurement_item: {is_measurement_item}")
                    
                    if self.scene is not None:
                        # First, explicitly deselect all measurements, text annotations, arrow annotations, and their text labels
                        from tools.text_annotation_tool import TextAnnotationItem
                        from tools.arrow_annotation_tool import ArrowAnnotationItem
                        for scene_item in self.scene.items():
                            if isinstance(scene_item, (MeasurementItem, AngleMeasurementItem, DraggableMeasurementText, DraggableAngleMeasurementText, TextAnnotationItem, ArrowAnnotationItem)):
                                scene_item.setSelected(False)
                        
                        # Clear scene selection (this will visually deselect ROIs)
                        selected_before = [item for item in self.scene.selectedItems()]
                        # print(f"[DEBUG-DESELECT]   Selected items in scene before clear: {len(selected_before)}")
                        # for item in selected_before:
                        #     print(f"[DEBUG-DESELECT]     Item: {type(item).__name__}, isSelected: {item.isSelected()}")
                        self.scene.clearSelection()
                        selected_after = [item for item in self.scene.selectedItems()]
                        # print(f"[DEBUG-DESELECT]   Selected items in scene after clear: {len(selected_after)}")
                    
                    # Emit signal to clear ROI selection - this is critical for proper ROI deselection
                    # This must happen BEFORE calling super() to prevent Qt's default behavior from interfering
                    # print(f"[DEBUG-DESELECT]   Emitting image_clicked_no_roi signal")
                    self.image_clicked_no_roi.emit()
                    
                    # Accept the event to prevent further processing
                    event.accept()
                    return
                
                # Let Qt handle selection of ROIs and measurements
                super().mousePressEvent(event)
                return
            
            # If ScrollHandDrag is active (pan mode), let Qt handle it unless clicking on ROI
            if self.dragMode() == QGraphicsView.DragMode.ScrollHandDrag:
                # Check if clicking on ROI item first
                scene_pos = self.mapToScene(event.position().toPoint())
                item = self.scene.itemAt(scene_pos, self.transform())
                
                from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsEllipseItem
                # Check if item is an ROI item (but not the image item)
                is_roi_item = (item is not None and 
                              item != self.image_item and
                              isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem)))
                
                if is_roi_item:
                    # Clicking on ROI - disable ScrollHandDrag temporarily
                    self.setDragMode(QGraphicsView.DragMode.NoDrag)
                    self.roi_clicked.emit(item)
                    return
                else:
                    # Not clicking on ROI (clicking on image item, empty space, or other items) - deselect measurements and emit signal for deselection
                    from tools.measurement_tool import MeasurementItem, DraggableMeasurementText
                    from tools.angle_measurement_items import AngleMeasurementItem, DraggableAngleMeasurementText
                    from tools.text_annotation_tool import TextAnnotationItem
                    from tools.arrow_annotation_tool import ArrowAnnotationItem
                    if self.scene is not None:
                        # Deselect all measurements, text annotations, arrow annotations, and their text labels
                        for scene_item in self.scene.items():
                            if isinstance(scene_item, (MeasurementItem, AngleMeasurementItem, DraggableMeasurementText, DraggableAngleMeasurementText, TextAnnotationItem, ArrowAnnotationItem)):
                                scene_item.setSelected(False)
                        # Also clear scene selection to ensure everything is deselected
                        self.scene.clearSelection()
                    # Emit before calling super() to ensure signal is processed
                    self.image_clicked_no_roi.emit()
                    # This is critical: we must let Qt handle the event for ScrollHandDrag to work
                    super().mousePressEvent(event)
                    return
            
            # For other modes, handle normally
            # First check if clicking on existing ROI item
            scene_pos = self.mapToScene(event.position().toPoint())
            item = self.scene.itemAt(scene_pos, self.transform())
            
            # Check if it's a ROI item (QGraphicsRectItem or QGraphicsEllipseItem) but not the image item
            from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsEllipseItem
            from tools.measurement_tool import MeasurementItem, MeasurementHandle, DraggableMeasurementText
            from tools.angle_measurement_items import AngleMeasurementItem, AngleVertexHandle, DraggableAngleMeasurementText
            
            is_roi_item = (item is not None and 
                          item != self.image_item and
                          isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem)))
            
            # Check if clicking on measurement-related items
            is_measurement_item = isinstance(item, (MeasurementItem, AngleMeasurementItem))
            is_handle = isinstance(item, (MeasurementHandle, AngleVertexHandle))
            is_measurement_text = isinstance(item, (DraggableMeasurementText, DraggableAngleMeasurementText))
            
            # Check for text and arrow annotation items
            from tools.text_annotation_tool import TextAnnotationItem
            from tools.arrow_annotation_tool import ArrowAnnotationItem
            is_text_annotation_item = isinstance(item, TextAnnotationItem)
            is_arrow_annotation_item = isinstance(item, ArrowAnnotationItem)
            
            # Check if item is a child of a measurement
            is_measurement_child = False
            if item is not None:
                parent = item.parentItem()
                while parent is not None:
                    if isinstance(parent, (MeasurementItem, AngleMeasurementItem)):
                        is_measurement_child = True
                        break
                    parent = parent.parentItem()
            
            if is_roi_item:
                # Clicking on existing ROI - emit signal for ROI click
                self.roi_clicked.emit(item)
            elif is_measurement_item or is_handle or is_measurement_text or is_measurement_child:
                # Clicking on measurement, handle, text, or measurement child - let Qt handle it
                # Don't deselect here - allow normal selection behavior
                pass
            elif is_text_annotation_item or is_arrow_annotation_item:
                # Clicking on text or arrow annotation - let Qt handle it for selection
                # Don't start new annotation if clicking on existing one
                pass
            elif item is None or item == self.image_item:
                # Clicking on empty space or image item - deselect measurements and emit deselection signal
                # This ensures measurements are deselected even after handle dragging
                from tools.text_annotation_tool import TextAnnotationItem
                from tools.arrow_annotation_tool import ArrowAnnotationItem
                if self.scene is not None:
                    # Deselect all measurements, text annotations, arrow annotations, and their text labels
                    for scene_item in self.scene.items():
                        if isinstance(scene_item, (MeasurementItem, AngleMeasurementItem, DraggableMeasurementText, DraggableAngleMeasurementText, TextAnnotationItem, ArrowAnnotationItem)):
                            scene_item.setSelected(False)
                    # Also clear scene selection to ensure everything is deselected
                    self.scene.clearSelection()
                self.image_clicked_no_roi.emit()
                # Continue with mode-specific handling
                if self.mouse_mode == "zoom":
                    # Zoom mode - start zoom operation
                    # Use viewport position for zoom tracking (more accurate for vertical movement)
                    self.zoom_start_pos = event.position()
                    self.zoom_start_zoom = self.current_zoom
                    self.zoom_mouse_moved = False  # Track if mouse actually moved
                elif self.mouse_mode == "measure":
                    # Measurement mode - start or finish measurement
                    if not self.measuring:
                        # Start new measurement (first end placed); hide cursor while drawing line
                        self.measuring = True
                        self.measurement_start_pos = scene_pos
                        self.setCursor(Qt.CursorShape.BlankCursor)
                        self.measurement_started.emit(scene_pos)
                    else:
                        # Finish current measurement
                        self.measuring = False
                        self.measurement_start_pos = None
                        self.measurement_finished.emit()
                elif self.mouse_mode == "measure_angle":
                    self.angle_measurement_clicked.emit(scene_pos)
                elif self.mouse_mode == "magnifier":
                    # Magnifier mode - activate magnifier
                    if not self.magnifier_active:
                        # Create magnifier widget if it doesn't exist
                        if self.magnifier_widget is None:
                            from gui.magnifier_widget import MagnifierWidget
                            self.magnifier_widget = MagnifierWidget()
                        
                        self.magnifier_active = True
                        # Hide cursor when magnifier is active
                        self.setCursor(Qt.CursorShape.BlankCursor)
                        # Extract and show magnified region
                        # Get current zoom from authoritative scalar (not from matrix m11,
                        # which would be incorrect when rotation is active)
                        current_zoom = self.current_zoom
                        # Magnifier zoom is 2.0x the current view zoom
                        magnifier_zoom = 2.0 * current_zoom
                        # Extract region size calculation for 2.0x zoom
                        # To achieve true 2.0x zoom: we want final pixmap to be 200px (widget size)
                        # After scaling by magnifier_zoom, we need: region_size * magnifier_zoom = 200
                        # So: region_size = 200 / magnifier_zoom = 200 / (2.0 * current_zoom)
                        # This ensures the extracted region, when scaled, fills the 200px widget at 2.0x zoom
                        adjusted_region_size = 200.0 / (2.0 * current_zoom) if current_zoom > 0 else 200.0 / 2.0
                        if DEBUG_MAGNIFIER:
                            print(f"[DEBUG-MAGNIFIER] Press: current_zoom={current_zoom:.3f}, magnifier_zoom={magnifier_zoom:.3f}, adjusted_region_size={adjusted_region_size:.3f}")
                        magnified_pixmap = self._render_scene_region(
                            scene_pos.x(), scene_pos.y(), adjusted_region_size, magnifier_zoom
                        )
                        if magnified_pixmap is not None and DEBUG_MAGNIFIER:
                            print(f"[DEBUG-MAGNIFIER] Press: extracted_region_size=({int(adjusted_region_size):d}x{int(adjusted_region_size):d}), scaled_pixmap_size=({magnified_pixmap.width()}x{magnified_pixmap.height()})")
                        if magnified_pixmap is not None:
                            self.magnifier_widget.update_magnified_region(magnified_pixmap)
                            # Position magnifier centered on cursor
                            global_pos = self.mapToGlobal(event.position().toPoint())
                            self.magnifier_widget.show_at_position(global_pos)
                elif self.mouse_mode == "crosshair":
                    # Crosshair mode - get pixel value and coordinates, emit signal
                    if self.get_current_dataset_callback:
                        dataset = self.get_current_dataset_callback()
                        if dataset is not None:
                            # Convert scene position to image coordinates
                            x = int(scene_pos.x())
                            y = int(scene_pos.y())
                            z = 0
                            if self.get_current_slice_index_callback:
                                z = self.get_current_slice_index_callback()
                            
                            # Get pixel value
                            use_rescaled = False
                            if self.get_use_rescaled_values_callback:
                                use_rescaled = self.get_use_rescaled_values_callback()
                            
                            pixel_value_str = self._get_pixel_value_at_coords(dataset, x, y, z, use_rescaled)
                            
                            # Emit signal with crosshair information
                            self.crosshair_clicked.emit(scene_pos, pixel_value_str, x, y, z)
                elif self.mouse_mode == "text_annotation":
                    # Text annotation mode - start text annotation (if not clicking on existing annotation)
                    if not is_text_annotation_item:
                        # Finish any current annotation first (if editing)
                        if self.text_annotating:
                            # Cancel current annotation if it exists
                            self.text_annotation_finished.emit()
                        # Start new annotation
                        self.text_annotating = True
                        self.text_annotation_start_pos = scene_pos
                        self.text_annotation_started.emit(scene_pos)
                    else:
                        # Clicking on existing text annotation - let it handle the event (for selection/editing)
                        pass
                elif self.mouse_mode == "arrow_annotation":
                    # Arrow annotation mode - start arrow annotation (if not clicking on existing annotation)
                    if not is_arrow_annotation_item:
                        # Cancel any current arrow first
                        if self.arrow_annotating:
                            self.arrow_annotation_finished.emit()
                        # Start new arrow
                        self.arrow_annotating = True
                        self.arrow_annotation_start_pos = scene_pos
                        self.arrow_annotation_started.emit(scene_pos)
                elif self.roi_drawing_mode:
                    # Start ROI drawing
                    self.roi_drawing_start = scene_pos
                    self.roi_drawing_started.emit(scene_pos)
            elif self.mouse_mode == "zoom":
                # Zoom mode - start zoom operation (clicking on overlay or other items)
                # Use viewport position for zoom tracking (more accurate for vertical movement)
                self.zoom_start_pos = event.position()
                self.zoom_start_zoom = self.current_zoom
                self.zoom_mouse_moved = False  # Track if mouse actually moved
                # Deselect measurements when clicking away
                from tools.measurement_tool import MeasurementItem, DraggableMeasurementText
                from tools.angle_measurement_items import AngleMeasurementItem, DraggableAngleMeasurementText
                if self.scene is not None:
                    for scene_item in self.scene.items():
                        if isinstance(scene_item, (MeasurementItem, AngleMeasurementItem, DraggableMeasurementText, DraggableAngleMeasurementText)):
                            scene_item.setSelected(False)
                    self.scene.clearSelection()
                # Emit signal for clicking on image (not ROI) to allow deselection
                self.image_clicked_no_roi.emit()
            elif self.mouse_mode == "measure":
                # Measurement mode - start or finish measurement
                if not self.measuring:
                    # Start new measurement
                    self.measuring = True
                    self.measurement_start_pos = scene_pos
                    self.measurement_started.emit(scene_pos)
                else:
                    # Finish current measurement
                    self.measuring = False
                    self.measurement_start_pos = None
                    self.measurement_finished.emit()
            elif self.mouse_mode == "measure_angle":
                self.angle_measurement_clicked.emit(scene_pos)
            elif self.roi_drawing_mode:
                # Start ROI drawing only if not clicking on existing ROI
                self.roi_drawing_start = scene_pos
                self.roi_drawing_started.emit(scene_pos)
            else:
                # Clicking on other items (overlay, etc.) but not on ROI or measurement - deselect measurements and allow deselection
                # This ensures measurements are deselected when clicking on overlays or other items after dragging handles
                from tools.measurement_tool import MeasurementItem, DraggableMeasurementText
                from tools.angle_measurement_items import AngleMeasurementItem, DraggableAngleMeasurementText
                from tools.text_annotation_tool import TextAnnotationItem
                from tools.arrow_annotation_tool import ArrowAnnotationItem
                if self.scene is not None:
                    # Deselect all measurements, text annotations, arrow annotations, and their text labels
                    for scene_item in self.scene.items():
                        if isinstance(scene_item, (MeasurementItem, AngleMeasurementItem, DraggableMeasurementText, DraggableAngleMeasurementText, TextAnnotationItem, ArrowAnnotationItem)):
                            scene_item.setSelected(False)
                    # Also clear scene selection to ensure everything is deselected
                    self.scene.clearSelection()
        elif event.button() == Qt.MouseButton.RightButton:
            from gui.image_viewer_context_menu import handle_mouse_press_right_button
            if handle_mouse_press_right_button(self, event):
                return

        super().mousePressEvent(event)

    def _toggle_statistic(self, roi, stat_name: str, checked: bool) -> None:
        from gui.image_viewer_context_menu import toggle_roi_statistic
        toggle_roi_statistic(self, roi, stat_name, checked)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """
        Handle mouse move events for panning, ROI drawing, or zooming.
        
        Args:
            event: Mouse event
        """
        # Track cursor position and pixel values for status bar display
        # This should happen in all mouse modes, regardless of tool selection
        self._update_pixel_info(event)

        # Update edge-reveal slice/frame slider overlay proximity
        if getattr(self, "_slice_slider_enabled", False) and getattr(self, "_slider_overlay", None) is not None:
            self._update_slider_visibility_from_mouse(event.position().toPoint())
        
        # Check for right mouse drag FIRST, before any mode-specific checks
        # This allows window/level adjustment to work in all modes (Select, Pan, etc.)
        if event.buttons() & Qt.MouseButton.RightButton and self.right_mouse_drag_start_pos is not None:
            # Right mouse drag for window/level adjustment
            # Only if we have initial window/level values and context menu wasn't shown
            if (self.right_mouse_drag_start_center is not None and 
                self.right_mouse_drag_start_width is not None and
                not self.right_mouse_context_menu_shown):
                
                current_pos = event.position()
                start_pos = self.right_mouse_drag_start_pos
                
                # Calculate deltas (in viewport pixels)
                delta_x = current_pos.x() - start_pos.x()  # Horizontal: positive = right (wider), negative = left (narrower)
                delta_y = start_pos.y() - current_pos.y()  # Vertical: positive = up (higher center), negative = down (lower center)
                
                # Convert to window/level units using sensitivity
                center_delta = delta_y * self.window_center_sensitivity
                width_delta = delta_x * self.window_width_sensitivity
                
                # Emit signal with deltas
                self.window_level_drag_changed.emit(center_delta, width_delta)
                return  # Return early to prevent other mode handling
        
        # In select mode, allow default Qt behavior (selection dragging, etc.)
        if self.mouse_mode == "select":
            super().mouseMoveEvent(event)
            return
        
        if (
            self.mouse_mode == "zoom"
            and self.zoom_start_pos is not None
            and self.zoom_start_zoom is not None
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            # Zoom mode - adjust zoom based on vertical drag distance
            # Ensure ScrollHandDrag is disabled for zoom mode
            if self.dragMode() == QGraphicsView.DragMode.ScrollHandDrag:
                self.setDragMode(QGraphicsView.DragMode.NoDrag)
            
            current_pos = event.position()
            start_pos = self.zoom_start_pos
            base_zoom = self.zoom_start_zoom
            
            # Calculate vertical distance moved (in viewport coordinates)
            delta_y = current_pos.y() - start_pos.y()
            
            # Only zoom if mouse moved significantly (threshold: 2 pixels)
            # This prevents zoom on just a click
            if abs(delta_y) > 2.0:
                self.zoom_mouse_moved = True
                
                # Convert to zoom factor (negative delta = zoom in, positive = zoom out)
                zoom_delta = -delta_y / 350.0  # Reduced sensitivity (was 300.0)
                new_zoom = base_zoom * (1.0 + zoom_delta)
                
                # Clamp zoom
                new_zoom = max(self.min_zoom, min(self.max_zoom, new_zoom))
                
                # Apply zoom via _apply_view_transform to keep flip/rotation consistent
                center_scene = self.mapToScene(self.viewport().rect().center())
                self.current_zoom = new_zoom
                self._apply_view_transform()  # type: ignore[attr-defined]
                self.centerOn(center_scene)
                self._check_transform_changed()
        elif self.mouse_mode == "measure" and self.measuring and self.measurement_start_pos is not None:
            # Measurement mode - update measurement while dragging; keep cursor hidden
            if self.cursor().shape() != Qt.CursorShape.BlankCursor:
                self.setCursor(Qt.CursorShape.BlankCursor)
            if self.dragMode() == QGraphicsView.DragMode.ScrollHandDrag:
                self.setDragMode(QGraphicsView.DragMode.NoDrag)
            
            if event.buttons() & Qt.MouseButton.LeftButton:
                scene_pos = self.mapToScene(event.position().toPoint())
                self.measurement_updated.emit(scene_pos)
        elif self.mouse_mode == "measure_angle":
            scene_pos = self.mapToScene(event.position().toPoint())
            self.angle_measurement_preview.emit(scene_pos)
        elif self.mouse_mode == "arrow_annotation" and self.arrow_annotating and self.arrow_annotation_start_pos is not None:
            # Arrow annotation mode - update arrow while dragging
            if self.dragMode() == QGraphicsView.DragMode.ScrollHandDrag:
                self.setDragMode(QGraphicsView.DragMode.NoDrag)
            
            if event.buttons() & Qt.MouseButton.LeftButton:
                scene_pos = self.mapToScene(event.position().toPoint())
                self.arrow_annotation_updated.emit(scene_pos)
        elif self.roi_drawing_mode and self.roi_drawing_start is not None:
            # ROI drawing mode - ensure ScrollHandDrag is disabled
            if self.dragMode() == QGraphicsView.DragMode.ScrollHandDrag:
                self.setDragMode(QGraphicsView.DragMode.NoDrag)
            
            if event.buttons() & Qt.MouseButton.LeftButton:
                scene_pos = self.mapToScene(event.position().toPoint())
                self.roi_drawing_updated.emit(scene_pos)
        elif self.mouse_mode == "magnifier" and self.magnifier_active:
            # Magnifier mode - update magnifier position and content
            if event.buttons() & Qt.MouseButton.LeftButton:
                # Ensure cursor stays hidden
                if self.cursor().shape() != Qt.CursorShape.BlankCursor:
                    self.setCursor(Qt.CursorShape.BlankCursor)
                scene_pos = self.mapToScene(event.position().toPoint())
                # Extract and update magnified region
                # Get current zoom from authoritative scalar (not from matrix m11,
                # which would be incorrect when rotation is active)
                current_zoom = self.current_zoom
                # Magnifier zoom is 2.0x the current view zoom
                magnifier_zoom = 2.0 * current_zoom
                # Extract region size calculation for 2.0x zoom
                # To achieve true 2.0x zoom: we want final pixmap to be 200px (widget size)
                # After scaling by magnifier_zoom, we need: region_size * magnifier_zoom = 200
                # So: region_size = 200 / magnifier_zoom = 200 / (2.0 * current_zoom)
                # This ensures the extracted region, when scaled, fills the 200px widget at 2.0x zoom
                adjusted_region_size = 200.0 / (2.0 * current_zoom) if current_zoom > 0 else 200.0 / 2.0
                magnified_pixmap = self._render_scene_region(
                    scene_pos.x(), scene_pos.y(), adjusted_region_size, magnifier_zoom
                )
                if magnified_pixmap is not None and DEBUG_MAGNIFIER:
                    print(f"[DEBUG-MAGNIFIER] Move: current_zoom={current_zoom:.3f}, magnifier_zoom={magnifier_zoom:.3f}, adjusted_region_size={adjusted_region_size:.3f}, scaled_pixmap_size=({magnified_pixmap.width()}x{magnified_pixmap.height()})")
                if magnified_pixmap is not None and self.magnifier_widget is not None:
                    self.magnifier_widget.update_magnified_region(magnified_pixmap)
                    # Update magnifier position (centered on cursor)
                    global_pos = self.mapToGlobal(event.position().toPoint())
                    self.magnifier_widget.show_at_position(global_pos)
        elif self.mouse_mode == "pan":
            # Pan mode - ensure ScrollHandDrag is enabled (it may have been disabled by other operations)
            if self.dragMode() != QGraphicsView.DragMode.ScrollHandDrag:
                self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        # Pan mode is handled automatically by ScrollHandDrag, no manual code needed
        # But we need to emit transform_changed signal when panning occurs
        # This is handled by connecting to scrollbar valueChanged signals
        
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """
        Handle mouse release events.
        
        Args:
            event: Mouse event
        """
        # In select mode, allow default Qt behavior for left button
        if self.mouse_mode == "select":
            # Only use default behavior for left button
            if event.button() == Qt.MouseButton.LeftButton:
                super().mouseReleaseEvent(event)
                return
            # Fall through for right button to allow context menu
        
        if event.button() == Qt.MouseButton.LeftButton:
            if self.mouse_mode == "zoom" and self.zoom_start_pos is not None:
                # Finish zoom operation - clear state regardless of whether mouse moved
                # (zoom only happens in mouseMoveEvent if mouse actually moved)
                self.zoom_start_pos = None
                self.zoom_start_zoom = None
                self.zoom_mouse_moved = False
                # Restore ScrollHandDrag if we're in pan mode
                if self.mouse_mode == "pan":
                    self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            elif self.mouse_mode == "measure" and self.measuring:
                # Finish measurement (if not already finished by second click); restore cursor
                self.measuring = False
                self.measurement_start_pos = None
                self.setCursor(Qt.CursorShape.CrossCursor)
                self.measurement_finished.emit()
            elif self.mouse_mode == "text_annotation" and self.text_annotating:
                # Text annotation finishing is handled by the text item's editing callback
                # Don't emit signal here - it will be emitted when editing finishes
                # Just clear the state
                # Note: The text item will call its callback when editing finishes
                pass
            elif self.mouse_mode == "arrow_annotation" and self.arrow_annotating:
                # Finish arrow annotation
                self.arrow_annotating = False
                self.arrow_annotation_start_pos = None
                self.arrow_annotation_finished.emit()
            elif self.roi_drawing_mode and self.roi_drawing_start is not None:
                # Finish ROI drawing
                self.roi_drawing_finished.emit()
                self.roi_drawing_start = None
                # Restore ScrollHandDrag if we're in pan mode
                if self.mouse_mode == "pan":
                    self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            elif self.mouse_mode == "magnifier" and self.magnifier_active:
                # Finish magnifier - hide widget and restore cursor
                self.magnifier_active = False
                if self.magnifier_widget is not None:
                    self.magnifier_widget.hide()
                # Restore cursor visibility (cross cursor for magnifier mode)
                self.setCursor(Qt.CursorShape.CrossCursor)
            # Pan mode is handled automatically by ScrollHandDrag, no cleanup needed
        elif event.button() == Qt.MouseButton.RightButton:
            # Right mouse release - check if we were dragging or should show context menu
            if (self.right_mouse_drag_start_pos is not None and 
                not self.right_mouse_context_menu_shown):
                
                # Check if mouse moved significantly (drag threshold: 5 pixels)
                current_pos = event.position()
                start_pos = self.right_mouse_drag_start_pos
                drag_distance = ((current_pos.x() - start_pos.x()) ** 2 + 
                               (current_pos.y() - start_pos.y()) ** 2) ** 0.5
                
                if drag_distance < 5.0:
                    # Mouse didn't move much - show context menu
                    from gui.image_viewer_context_menu import (
                        show_image_background_context_menu_on_right_release,
                    )
                    show_image_background_context_menu_on_right_release(self, event)

            
            # Reset right mouse drag tracking
            self.right_mouse_drag_start_pos = None
            self.right_mouse_drag_start_center = None
            self.right_mouse_drag_start_width = None
            self.right_mouse_context_menu_shown = False
        
        super().mouseReleaseEvent(event)
    def _on_show_file_requested(self) -> None:
        """
        Handle "Show file" request from context menu.
        
        Opens file explorer and selects the currently displayed slice file.
        """
        from utils.file_explorer import reveal_file_in_explorer
        
        if self.get_file_path_callback:
            file_path = self.get_file_path_callback()
            if file_path and os.path.exists(file_path):
                reveal_file_in_explorer(file_path)
    
    def viewportEvent(self, event: QEvent) -> bool:
        """
        Override viewportEvent to catch mouse move events even when ScrollHandDrag is active.
        This ensures pixel info updates work consistently in all modes, including pan mode.
        
        Args:
            event: Viewport event
            
        Returns:
            True if event was handled, False otherwise
        """
        # Handle mouse move events to update pixel info even when ScrollHandDrag is active
        if event.type() == QEvent.Type.MouseMove and isinstance(event, QMouseEvent):
            # Update pixel info for all mouse move events, regardless of drag mode
            self._update_pixel_info(event)
        
        # Let Qt handle the event normally (for ScrollHandDrag, etc.)
        return super().viewportEvent(event)
    
    def keyPressEvent(self, event: QKeyEvent) -> None:
        """
        Handle key press events for arrow key navigation.
        
        Args:
            event: Key event
        """
        # Check if any text annotation is being edited - if so, don't process arrow keys for navigation
        from tools.text_annotation_tool import is_any_text_annotation_editing
        if is_any_text_annotation_editing(self.scene):
            # Let the text editor handle arrow keys for cursor movement
            super().keyPressEvent(event)
            return
        
        if event.key() == Qt.Key.Key_Up:
            # Up arrow: next slice
            self.arrow_key_pressed.emit(1)
            event.accept()
        elif event.key() == Qt.Key.Key_Down:
            # Down arrow: previous slice
            self.arrow_key_pressed.emit(-1)
            event.accept()
        elif event.key() == Qt.Key.Key_Left:
            # Left arrow: previous series
            if DEBUG_NAV:
                timestamp = time.time()
                focused_widget = QApplication.focusWidget()
                focus_info = f"focused={focused_widget.objectName() if focused_widget else 'None'}"
                print(f"[DEBUG-NAV] [{timestamp:.6f}] ImageViewer.keyPressEvent: LEFT arrow, {focus_info}")
            focused_widget = QApplication.focusWidget()
            # Only handle if series navigator doesn't have focus
            if focused_widget:
                # Check if focused widget is the series navigator or one of its children
                widget = focused_widget
                while widget:
                    if widget.objectName() == "series_navigator" or widget.objectName() == "series_navigator_scroll_area" or widget.objectName() == "series_navigator_container":
                        # Series navigator has focus, let it handle the event
                        if DEBUG_NAV:
                            timestamp = time.time()
                            print(f"[DEBUG-NAV] [{timestamp:.6f}] ImageViewer: Series navigator has focus, skipping emit")
                        return
                    widget = widget.parent()
            if DEBUG_NAV:
                timestamp = time.time()
                print(f"[DEBUG-NAV] [{timestamp:.6f}] ImageViewer: Emitting series_navigation_requested(-1)")
            self.series_navigation_requested.emit(-1)
            event.accept()
        elif event.key() == Qt.Key.Key_Right:
            # Right arrow: next series
            if DEBUG_NAV:
                timestamp = time.time()
                focused_widget = QApplication.focusWidget()
                focus_info = f"focused={focused_widget.objectName() if focused_widget else 'None'}"
                print(f"[DEBUG-NAV] [{timestamp:.6f}] ImageViewer.keyPressEvent: RIGHT arrow, {focus_info}")
            focused_widget = QApplication.focusWidget()
            # Only handle if series navigator doesn't have focus
            if focused_widget:
                # Check if focused widget is the series navigator or one of its children
                widget = focused_widget
                while widget:
                    if widget.objectName() == "series_navigator" or widget.objectName() == "series_navigator_scroll_area" or widget.objectName() == "series_navigator_container":
                        # Series navigator has focus, let it handle the event
                        if DEBUG_NAV:
                            timestamp = time.time()
                            print(f"[DEBUG-NAV] [{timestamp:.6f}] ImageViewer: Series navigator has focus, skipping emit")
                        return
                    widget = widget.parent()
            if DEBUG_NAV:
                timestamp = time.time()
                print(f"[DEBUG-NAV] [{timestamp:.6f}] ImageViewer: Emitting series_navigation_requested(1)")
            self.series_navigation_requested.emit(1)
            event.accept()
        else:
            super().keyPressEvent(event)
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
    
    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        """
        Handle drag move event - accept files and folders.
        
        Args:
            event: QDragMoveEvent
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
        Handle drop event - emit signal with dropped file/folder paths.
        
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
        
        for url in urls:
            path = url.toLocalFile()
            if not path:
                continue
            
            if os.path.isfile(path) or os.path.isdir(path):
                paths.append(path)
        
        # Emit signal with paths if any valid paths found
        if paths:
            self.files_dropped.emit(paths)
        
        event.acceptProposedAction()

    # ------------------------------------------------------------------ #
    # Edge-reveal slider — hover / leave helpers
    # ------------------------------------------------------------------ #

    def _update_slider_visibility_from_mouse(self, pos) -> None:
        """
        Show or schedule-hide the slice/frame slider overlay based on
        how close the mouse pointer is to the right edge of the viewport.

        Args:
            pos: QPoint in viewport coordinates (from event.position().toPoint()).
        """
        ACTIVATION_ZONE_PX = 28
        overlay = self._slider_overlay  # type: ignore[attr-defined]

        # If slider has only one slice it is intentionally hidden
        if overlay.maximum() <= 1:
            return

        vp_width = self.viewport().width()
        dist_from_right = vp_width - pos.x()

        # Check if pointer is currently over the overlay widget itself
        if overlay.is_interacting():
            overlay.keep_visible()
            return

        if overlay.isVisible() and overlay.geometry().contains(pos):
            overlay.keep_visible()
            return

        if dist_from_right <= ACTIVATION_ZONE_PX:
            overlay.reveal()
        elif overlay.isVisible():
            overlay.schedule_hide()

    def leaveEvent(self, event) -> None:  # noqa: N802
        """
        Schedule the slice/frame slider overlay to hide when the mouse
        leaves the viewport entirely.
        """
        super().leaveEvent(event)
        overlay = getattr(self, "_slider_overlay", None)
        if (
            overlay is not None
            and overlay.isVisible()
            and not overlay.is_interacting()
        ):
            overlay.schedule_hide()

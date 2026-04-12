"""
Sub-Window Container

This module implements a container widget that wraps an ImageViewer
for use in multi-window layouts. Manages focus state, border highlighting,
and drag-and-drop support for series assignment.

Inputs:
    - ImageViewer instance
    - Focus state changes
    - Drag-and-drop events from series navigator
    
Outputs:
    - Focused subwindow with highlighted border
    - Series/slice assignment signals
    - Drag-and-drop acceptance
    
Requirements:
    - PySide6 for GUI components
    - ImageViewer for image display
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QFrame, QSizePolicy
from PySide6.QtCore import Qt, Signal, QMimeData
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent, QColor, QPainter, QPen
from typing import Optional

from gui.image_viewer import ImageViewer
from gui.style_constants import FOCUS_BORDER_COLOR
from gui.mpr_thumbnail_widget import MPR_ASSIGN_MIME


def _parse_series_drop_mime(text: str) -> tuple[str, int, str]:
    """
    Parse navigator / thumbnail drag text into (series_uid, slice_index, study_uid).

    Formats:
    - dv3_assign\\t<study_uid>\\t<series_uid>\\t<slice_index> — per-instance thumbnail drag
    - series_uid:<uid> — whole series, first slice; study resolved at drop
    - series_uid:<uid>:<n> — slice index n (composite UIDs use dots/underscores, not extra colons)
    """
    study_uid = ""
    if text.startswith("dv3_assign\t"):
        parts = text.split("\t")
        if len(parts) >= 4:
            try:
                return parts[2], int(parts[3]), parts[1]
            except ValueError:
                return "", 0, ""
        return "", 0, ""
    if text.startswith("series_uid:"):
        rest = text[len("series_uid:") :]
        if not rest:
            return "", 0, ""
        if ":" in rest:
            uid_part, slice_part = rest.rsplit(":", 1)
            try:
                return uid_part, int(slice_part), study_uid
            except ValueError:
                return rest, 0, study_uid
        return rest, 0, study_uid
    return "", 0, ""


class SubWindowContainer(QFrame):
    """
    Container widget wrapping an ImageViewer for multi-window layouts.
    
    Features:
    - Focus management with highlighted border
    - Series/slice assignment tracking
    - Drag-and-drop support from series navigator
    - Click-to-focus functionality
    """
    
    # Signals
    focus_changed = Signal(bool)  # Emitted when focus state changes (True = focused)
    # series_uid, slice_index in flattened series list; study_uid "" = resolve from series (legacy drops)
    assign_series_requested = Signal(str, int, str)
    context_menu_requested = Signal()  # Emitted when context menu is requested
    expand_to_1x1_requested = Signal()  # Emitted when user double-clicks on image/background to expand this pane to 1x1
    # Emitted when an MPR thumbnail is dragged onto this container; payload is the *source* subwindow index.
    mpr_focus_requested = Signal(int)
    
    def __init__(self, image_viewer: ImageViewer, parent=None):
        """
        Initialize the subwindow container.
        
        Args:
            image_viewer: ImageViewer instance to wrap
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.image_viewer = image_viewer
        self.is_focused = False
        
        # Track assigned series and slice
        self.assigned_series_uid: Optional[str] = None
        self.assigned_slice_index: int = 0
        
        # Border highlighting
        self.focus_border_width = 3
        self.normal_border_width = 1
        self.focus_border_color = FOCUS_BORDER_COLOR  # Shared blue highlight
        self.normal_border_color = QColor(128, 128, 128)  # Gray
        
        # Set size policy to expand
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # Set up layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.image_viewer)
        
        # Enable drag-and-drop
        self.setAcceptDrops(True)
        
        # Set initial border style
        self._update_border_style()
        
        # Install event filter on image viewer to capture clicks
        self.image_viewer.installEventFilter(self)
    
    def set_focused(self, focused: bool) -> None:
        """
        Set the focus state of this subwindow.
        
        Args:
            focused: True if this subwindow should be focused
        """
        if self.is_focused != focused:
            # print(f"[DEBUG-FOCUS] SubWindowContainer.set_focused: Changing focus from {self.is_focused} to {focused}")
            self.is_focused = focused
            self._update_border_style()
            self.focus_changed.emit(focused)
            # print(f"[DEBUG-FOCUS] SubWindowContainer.set_focused: Focus state updated and signal emitted")
        else:
            # print(f"[DEBUG-FOCUS] SubWindowContainer.set_focused: Focus already {focused}, no change needed")
            pass
    
    def _update_border_style(self) -> None:
        """Update the border style based on focus state."""
        if self.is_focused:
            border_width = self.focus_border_width
            border_color = self.focus_border_color
        else:
            border_width = self.normal_border_width
            border_color = self.normal_border_color
        
        # Use stylesheet for border
        # Build the stylesheet string with proper escaping
        stylesheet = (
            "SubWindowContainer {\n"
            f"    border: {border_width}px solid rgb({border_color.red()}, {border_color.green()}, {border_color.blue()});\n"
            "}"
        )
        self.setStyleSheet(stylesheet)
        self.update()
    
    def _is_double_click_on_background_or_image(self, event) -> bool:
        """
        Return True if the double-click event is on the image or background
        (no interactive scene item under cursor: not on text annotation, ROI, measurement, arrow, crosshair).
        Used to decide whether to expand to 1x1 or let the scene handle the event.
        """
        try:
            view = self.image_viewer
            if view.scene is None:
                return True
            scene_pos = view.mapToScene(event.position().toPoint())
            item = view.scene.itemAt(scene_pos, view.transform())
            if item is None:
                return True
            if item is view.image_item:
                return True
            # Interactive items: ROI, measurement, text annotation, arrow, crosshair (or their children)
            from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsEllipseItem
            try:
                from tools.measurement_tool import MeasurementItem, DraggableMeasurementText
            except ImportError:
                MeasurementItem = type(None)
                DraggableMeasurementText = type(None)
            try:
                from tools.text_annotation_tool import TextAnnotationItem
            except ImportError:
                TextAnnotationItem = type(None)
            try:
                from tools.arrow_annotation_tool import ArrowAnnotationItem
            except ImportError:
                ArrowAnnotationItem = type(None)
            try:
                from tools.crosshair_manager import CrosshairItem
            except ImportError:
                CrosshairItem = type(None)
            if isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem)) and item is not view.image_item:
                return False
            if isinstance(item, (MeasurementItem, DraggableMeasurementText, TextAnnotationItem, ArrowAnnotationItem)):
                return False
            if CrosshairItem is not type(None) and isinstance(item, CrosshairItem):
                return False
            # Check parent chain for measurement/text/arrow (e.g. handle or child of annotation)
            parent = item.parentItem()
            while parent is not None:
                if isinstance(parent, (MeasurementItem, DraggableMeasurementText, TextAnnotationItem, ArrowAnnotationItem)):
                    return False
                if CrosshairItem is not type(None) and isinstance(parent, CrosshairItem):
                    return False
                parent = parent.parentItem()
            return True
        except Exception:
            return True
    
    def paintEvent(self, event) -> None:
        """
        Paint the border highlight.
        
        Args:
            event: Paint event
        """
        super().paintEvent(event)
        
        # Draw additional border highlight if focused
        if self.is_focused:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            pen = QPen(self.focus_border_color, self.focus_border_width)
            painter.setPen(pen)
            rect = self.rect().adjusted(
                self.focus_border_width // 2,
                self.focus_border_width // 2,
                -self.focus_border_width // 2,
                -self.focus_border_width // 2
            )
            painter.drawRect(rect)
    
    def eventFilter(self, obj, event) -> bool:
        """
        Event filter to capture mouse clicks for focus management and
        double-click to expand to 1x1 (when click is on image/background, not on interactive items).
        
        Args:
            obj: Object that received the event
            event: Event
            
        Returns:
            True if event was handled, False otherwise
        """
        from PySide6.QtCore import QEvent
        
        if obj == self.image_viewer:
            if event.type() == QEvent.Type.MouseButtonDblClick:
                # Double-click: expand to 1x1 only when click is on image or background (no interactive item)
                if self._is_double_click_on_background_or_image(event):
                    self.set_focused(True)
                    self.expand_to_1x1_requested.emit()
                    return True
                # Otherwise let the view/scene handle it (e.g. text annotation inline edit)
                return False
            if event.type() == QEvent.Type.MouseButtonPress:
                # print(f"[DEBUG-FOCUS] SubWindowContainer.eventFilter: MouseButtonPress intercepted on image_viewer, is_focused={self.is_focused}")
                # Click on image viewer - set focus to this container
                if not self.is_focused:
                    # print(f"[DEBUG-FOCUS] SubWindowContainer.eventFilter: Container not focused, requesting focus change")
                    # CRITICAL: Accept the event to prevent ImageViewer from processing it
                    # This prevents panning from starting before focus is set
                    event.accept()
                    # print(f"[DEBUG-FOCUS] SubWindowContainer.eventFilter: Event accepted, setting focus and emitting signal")
                    # Request focus change (will be handled by parent layout)
                    self.set_focused(True)
                    # Emit signal to notify parent
                    self.focus_changed.emit(True)
                    # print(f"[DEBUG-FOCUS] SubWindowContainer.eventFilter: Focus set and signal emitted, returning True")
                    # Return True to indicate we handled the event
                    return True
                else:
                    # print(f"[DEBUG-FOCUS] SubWindowContainer.eventFilter: Container already focused, allowing event to pass through")
                    pass
        
        return super().eventFilter(obj, event)
    
    def mousePressEvent(self, event) -> None:
        """
        Handle mouse press events to set focus.
        
        Args:
            event: Mouse event
        """
        if event.button() == Qt.MouseButton.LeftButton:
            # print(f"[DEBUG-FOCUS] SubWindowContainer.mousePressEvent: LeftButton click received, is_focused={self.is_focused}")
            if not self.is_focused:
                # print(f"[DEBUG-FOCUS] SubWindowContainer.mousePressEvent: Container not focused, setting focus")
                # Accept the event to prevent propagation to ImageViewer
                event.accept()
                # Set focus to this container
                self.set_focused(True)
                # Emit signal to notify parent
                self.focus_changed.emit(True)
                # print(f"[DEBUG-FOCUS] SubWindowContainer.mousePressEvent: Focus set and signal emitted, returning early")
                # Don't call super() to prevent ImageViewer from processing the event
                # This prevents panning from starting
                return
        
        # For right button or already focused, allow normal processing
        if event.button() == Qt.MouseButton.RightButton:
            # Emit context menu request signal
            self.context_menu_requested.emit()
        
        super().mousePressEvent(event)
    
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """
        Handle drag enter event - accept series UID drops and MPR thumbnail drops.
        
        Args:
            event: Drag enter event
        """
        mime = event.mimeData()
        if mime.hasFormat(MPR_ASSIGN_MIME):
            event.acceptProposedAction()
            return
        if mime.hasText():
            text = mime.text()
            if text.startswith("series_uid:") or text.startswith("dv3_assign\t"):
                event.acceptProposedAction()
                return
        event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        """
        Handle drag move event - accept series UID drops and MPR thumbnail drops.
        
        Args:
            event: Drag move event
        """
        mime = event.mimeData()
        if mime.hasFormat(MPR_ASSIGN_MIME):
            event.acceptProposedAction()
            return
        if mime.hasText():
            text = mime.text()
            if text.startswith("series_uid:") or text.startswith("dv3_assign\t"):
                event.acceptProposedAction()
                return
        event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        """
        Handle drop event - assign series to this subwindow, or focus an MPR
        subwindow when an MPR thumbnail is dropped here.
        
        Args:
            event: Drop event
        """
        mime = event.mimeData()

        # MPR thumbnail drop: focus the source MPR subwindow.
        if mime.hasFormat(MPR_ASSIGN_MIME):
            try:
                source_idx = int(mime.data(MPR_ASSIGN_MIME).data().decode("ascii"))
                self.mpr_focus_requested.emit(source_idx)
                event.acceptProposedAction()
            except Exception:
                event.ignore()
            return

        if not mime.hasText():
            event.ignore()
            return

        text = mime.text()
        series_uid, slice_index, study_uid = _parse_series_drop_mime(text)
        if not series_uid:
            event.ignore()
            return

        self.assign_series_requested.emit(series_uid, slice_index, study_uid)
        event.acceptProposedAction()
    
    def set_assigned_series(self, series_uid: Optional[str], slice_index: int = 0) -> None:
        """
        Set the assigned series and slice for this subwindow.
        
        Args:
            series_uid: Series UID to assign (None to clear)
            slice_index: Slice index to assign
        """
        self.assigned_series_uid = series_uid
        self.assigned_slice_index = slice_index
    
    def get_assigned_series(self) -> tuple[Optional[str], int]:
        """
        Get the assigned series and slice for this subwindow.
        
        Returns:
            Tuple of (series_uid, slice_index)
        """
        return (self.assigned_series_uid, self.assigned_slice_index)


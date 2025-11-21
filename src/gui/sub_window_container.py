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
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QColor, QPainter, QPen
from typing import Optional

from gui.image_viewer import ImageViewer


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
    assign_series_requested = Signal(str, int)  # Emitted when series/slice assignment requested (series_uid, slice_index)
    context_menu_requested = Signal()  # Emitted when context menu is requested
    
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
        self.focus_border_color = QColor(0, 170, 255)  # Blue highlight
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
            print(f"[DEBUG-FOCUS] SubWindowContainer.set_focused: Changing focus from {self.is_focused} to {focused}")
            self.is_focused = focused
            self._update_border_style()
            self.focus_changed.emit(focused)
            print(f"[DEBUG-FOCUS] SubWindowContainer.set_focused: Focus state updated and signal emitted")
        else:
            print(f"[DEBUG-FOCUS] SubWindowContainer.set_focused: Focus already {focused}, no change needed")
    
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
        Event filter to capture mouse clicks for focus management.
        
        Args:
            obj: Object that received the event
            event: Event
            
        Returns:
            True if event was handled, False otherwise
        """
        from PySide6.QtCore import QEvent
        
        if obj == self.image_viewer:
            if event.type() == QEvent.Type.MouseButtonPress:
                print(f"[DEBUG-FOCUS] SubWindowContainer.eventFilter: MouseButtonPress intercepted on image_viewer, is_focused={self.is_focused}")
                # Click on image viewer - set focus to this container
                if not self.is_focused:
                    print(f"[DEBUG-FOCUS] SubWindowContainer.eventFilter: Container not focused, requesting focus change")
                    # CRITICAL: Accept the event to prevent ImageViewer from processing it
                    # This prevents panning from starting before focus is set
                    event.accept()
                    print(f"[DEBUG-FOCUS] SubWindowContainer.eventFilter: Event accepted, setting focus and emitting signal")
                    # Request focus change (will be handled by parent layout)
                    self.set_focused(True)
                    # Emit signal to notify parent
                    self.focus_changed.emit(True)
                    print(f"[DEBUG-FOCUS] SubWindowContainer.eventFilter: Focus set and signal emitted, returning True")
                    # Return True to indicate we handled the event
                    return True
                else:
                    print(f"[DEBUG-FOCUS] SubWindowContainer.eventFilter: Container already focused, allowing event to pass through")
        
        return super().eventFilter(obj, event)
    
    def mousePressEvent(self, event) -> None:
        """
        Handle mouse press events to set focus.
        
        Args:
            event: Mouse event
        """
        if event.button() == Qt.MouseButton.LeftButton:
            print(f"[DEBUG-FOCUS] SubWindowContainer.mousePressEvent: LeftButton click received, is_focused={self.is_focused}")
            if not self.is_focused:
                print(f"[DEBUG-FOCUS] SubWindowContainer.mousePressEvent: Container not focused, setting focus")
                # Accept the event to prevent propagation to ImageViewer
                event.accept()
                # Set focus to this container
                self.set_focused(True)
                # Emit signal to notify parent
                self.focus_changed.emit(True)
                print(f"[DEBUG-FOCUS] SubWindowContainer.mousePressEvent: Focus set and signal emitted, returning early")
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
        Handle drag enter event - accept series UID drops.
        
        Args:
            event: Drag enter event
        """
        # Check if mime data contains series UID
        if event.mimeData().hasText():
            text = event.mimeData().text()
            # Check if it's a series UID (starts with "series_uid:")
            if text.startswith("series_uid:"):
                event.acceptProposedAction()
                return
        
        event.ignore()
    
    def dragMoveEvent(self, event: QDragEnterEvent) -> None:
        """
        Handle drag move event - accept series UID drops.
        
        Args:
            event: Drag move event (uses same type as drag enter)
        """
        # Check if mime data contains series UID
        if event.mimeData().hasText():
            text = event.mimeData().text()
            if text.startswith("series_uid:"):
                event.acceptProposedAction()
                return
        
        event.ignore()
    
    def dropEvent(self, event: QDropEvent) -> None:
        """
        Handle drop event - assign series to this subwindow.
        
        Args:
            event: Drop event
        """
        if not event.mimeData().hasText():
            event.ignore()
            return
        
        text = event.mimeData().text()
        if not text.startswith("series_uid:"):
            event.ignore()
            return
        
        # Extract series UID and optional slice index
        # Format: "series_uid:UID:slice_index" or "series_uid:UID"
        parts = text.split(":")
        if len(parts) < 2:
            event.ignore()
            return
        
        series_uid = parts[1]
        slice_index = 0  # Default to first slice
        
        # Check if slice index is provided
        if len(parts) >= 3:
            try:
                slice_index = int(parts[2])
            except ValueError:
                slice_index = 0
        
        # Emit signal to assign series/slice
        self.assign_series_requested.emit(series_uid, slice_index)
        
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


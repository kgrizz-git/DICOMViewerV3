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
    - Optional thin top color strip when slice sync groups apply (view indices)
    - Series/slice assignment signals
    - Drag-and-drop acceptance
    
Requirements:
    - PySide6 for GUI components
    - ImageViewer for image display
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFrame, QSizePolicy
from PySide6.QtCore import Qt, Signal, QMimeData, QByteArray
from PySide6.QtGui import (
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QColor,
    QMouseEvent,
    QPainter,
    QPen,
    QPalette,
)
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


class _SliceSyncGroupBar(QWidget):
    """
    Full-width horizontal strip filled with the slice-sync group color.
    Height is set by ``SubWindowContainer.set_slice_sync_strip_height`` (config-driven).
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._fill: Optional[QColor] = None
        self.setFixedHeight(5)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_fill_color(self, color: Optional[QColor]) -> None:
        self._fill = color
        self.update()

    def paintEvent(self, _event) -> None:
        if self._fill is None:
            return
        painter = QPainter(self)
        painter.fillRect(self.rect(), self._fill)
        win = self.palette().color(QPalette.ColorRole.Window)
        edge = QColor(40, 40, 40) if win.lightness() > 140 else QColor(90, 90, 90)
        painter.setPen(QPen(edge, 1))
        painter.drawLine(0, self.height() - 1, self.width(), self.height() - 1)


class _PaneTitleBarFrame(QFrame):
    """
    Thin top strip holding the sync-group color bar; forwards DnD and mouse to the parent pane.
    """

    def __init__(self, container: "SubWindowContainer", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._container = container
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFixedHeight(5)
        self.setAcceptDrops(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        self._bar = _SliceSyncGroupBar(self)
        row.addWidget(self._bar, 1)

    @property
    def sync_bar(self) -> _SliceSyncGroupBar:
        return self._bar

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if self._container._mime_accepts_series_or_mpr(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if self._container._mime_accepts_series_or_mpr(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        SubWindowContainer.dropEvent(self._container, event)

    def mousePressEvent(self, event) -> None:
        SubWindowContainer.mousePressEvent(self._container, event)


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
    # Emitted when an MPR thumbnail is dragged onto this container:
    # (source_subwindow_index, target_subwindow_index). Source -1 = detached MPR.
    mpr_assign_requested = Signal(int, int)
    
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
        # When True, paint the unfocused (gray) border even if this pane is focused — used
        # during screenshot export so captures match a neutral multi-pane look.
        self._suppress_focus_border_for_export: bool = False

        # Set size policy to expand
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # Set up layout: optional top strip (slice-sync group color) + image viewer
        self._pane_title_bar = _PaneTitleBarFrame(self, parent=self)
        self._sync_group_bar = self._pane_title_bar.sync_bar
        self._pane_title_bar.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._pane_title_bar)
        layout.addWidget(self.image_viewer)
        
        # Enable drag-and-drop
        self.setAcceptDrops(True)
        
        # Set initial border style
        self._update_border_style()
        
        # Install on both QGraphicsView and its viewport. Mouse presses are usually
        # delivered to the viewport, so listening to both ensures consistent focus behavior.
        self.image_viewer.installEventFilter(self)
        self.image_viewer.viewport().installEventFilter(self)

    def set_slice_sync_strip_height(self, height_px: int) -> None:
        """
        Set the fixed height (px) of the slice-sync group color strip and its title bar row.

        Must match config ``slice_sync_group_strip_height_px`` (typically 2–16). Called whenever
        overlay settings change or indicators refresh so all panes stay consistent.
        """
        h = max(2, min(16, int(height_px)))
        self._pane_title_bar.setFixedHeight(h)
        self._sync_group_bar.setFixedHeight(h)

    def set_slice_sync_group_indicator(self, color: Optional[QColor]) -> None:
        """
        Show or hide the slice-sync group color on the pane title strip.

        When ``color`` is None, the strip is hidden (sync off, singleton, or pane
        not in any group). Groups use **view** indices (0–3), not grid slots.
        """
        if color is None:
            self._sync_group_bar.set_fill_color(None)
            self._sync_group_bar.setToolTip("")
            self._pane_title_bar.hide()
        else:
            self._sync_group_bar.set_fill_color(color)
            self._sync_group_bar.setToolTip(
                "Anatomic slice sync: this pane is in a linked group. "
                "Same bar color means the same group."
            )
            self._pane_title_bar.show()

    def _mime_accepts_series_or_mpr(self, mime: QMimeData) -> bool:
        if mime.hasFormat(MPR_ASSIGN_MIME):
            return True
        if mime.hasText():
            text = mime.text()
            if text.startswith("series_uid:") or text.startswith("dv3_assign\t"):
                return True
        return False

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

    def set_suppress_focus_border_for_export(self, suppress: bool) -> None:
        """Hide the blue focus border temporarily (e.g. while grabbing screenshots)."""
        suppress = bool(suppress)
        if self._suppress_focus_border_for_export == suppress:
            return
        self._suppress_focus_border_for_export = suppress
        self._update_border_style()

    def _update_border_style(self) -> None:
        """Update the border style based on focus state."""
        if self.is_focused and not self._suppress_focus_border_for_export:
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
                from tools.angle_measurement_items import AngleMeasurementItem, DraggableAngleMeasurementText, AngleVertexHandle
            except ImportError:
                MeasurementItem = type(None)
                DraggableMeasurementText = type(None)
                AngleMeasurementItem = type(None)
                DraggableAngleMeasurementText = type(None)
                AngleVertexHandle = type(None)
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
            if isinstance(item, (MeasurementItem, AngleMeasurementItem, DraggableMeasurementText, DraggableAngleMeasurementText, AngleVertexHandle, TextAnnotationItem, ArrowAnnotationItem)):
                return False
            if CrosshairItem is not type(None) and isinstance(item, CrosshairItem):
                return False
            # Check parent chain for measurement/text/arrow (e.g. handle or child of annotation)
            parent = item.parentItem()
            while parent is not None:
                if isinstance(parent, (MeasurementItem, AngleMeasurementItem, DraggableMeasurementText, DraggableAngleMeasurementText, TextAnnotationItem, ArrowAnnotationItem)):
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

        # Draw additional border highlight if focused (unless suppressed for export grab)
        if self.is_focused and not self._suppress_focus_border_for_export:
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

        # During teardown, ``image_viewer`` may be cleared before the filter is uninstalled.
        image_viewer = getattr(self, "image_viewer", None)
        if image_viewer is None:
            return super().eventFilter(obj, event)

        if obj == image_viewer or obj == image_viewer.viewport():
            if event.type() == QEvent.Type.MouseButtonDblClick:
                # Double-click: expand to 1x1 only when click is on image or background (no interactive item)
                if self._is_double_click_on_background_or_image(event):
                    self.set_focused(True)
                    self.expand_to_1x1_requested.emit()
                    return True
                # Otherwise let the view/scene handle it (e.g. text annotation inline edit)
                return False
            if event.type() == QEvent.Type.MouseButtonPress:
                # Unfocused pane: left-click only is swallowed so pan/ROI tools do not run
                # before focus moves here. Right/middle/etc. focus this pane but must still
                # reach ImageViewer (W/L drag, context menus) on the same gesture.
                if not self.is_focused and isinstance(event, QMouseEvent):
                    if event.button() == Qt.MouseButton.LeftButton:
                        event.accept()
                        self.set_focused(True)
                        self.focus_changed.emit(True)
                        return True
                    # Non-left: focus once (set_focused emits); do not accept so the viewer still gets the press.
                    self.set_focused(True)
                    return False
        
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
            if not self.is_focused:
                self.set_focused(True)
            self.context_menu_requested.emit()
        
        super().mousePressEvent(event)
    
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """
        Handle drag enter event - accept series UID drops and MPR thumbnail drops.
        
        Args:
            event: Drag enter event
        """
        if self._mime_accepts_series_or_mpr(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        """
        Handle drag move event - accept series UID drops and MPR thumbnail drops.
        
        Args:
            event: Drag move event
        """
        if self._mime_accepts_series_or_mpr(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        """
        Handle drop event - assign series to this subwindow, or focus an MPR
        subwindow when an MPR thumbnail is dropped here.
        
        Args:
            event: Drop event
        """
        mime = event.mimeData()

        # MPR thumbnail drop: relocate or attach floating MPR to this pane.
        if mime.hasFormat(MPR_ASSIGN_MIME):
            try:
                ba = mime.data(MPR_ASSIGN_MIME)
                if isinstance(ba, QByteArray):
                    inner = ba.data()
                    raw_bytes = inner.tobytes() if isinstance(inner, memoryview) else inner
                else:
                    raw_bytes = ba
                source_idx = int(raw_bytes.decode("ascii"))
                target_idx = getattr(self.image_viewer, "subwindow_index", None)
                if target_idx is None:
                    event.ignore()
                    return
                self.mpr_assign_requested.emit(source_idx, int(target_idx))
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


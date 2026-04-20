"""
Multi-Window Layout Manager

This module manages the layout of multiple subwindows (1x1, 1x2, 2x1, 2x2)
for displaying different series/slices simultaneously.

Inputs:
    - Layout mode selection (1x1, 1x2, 2x1, 2x2)
    - Focus change requests
    - Series/slice assignment requests
    
Outputs:
    - Layout of subwindows
    - Focused subwindow tracking
    - Focus change signals
    
Requirements:
    - PySide6 for GUI components
    - SubWindowContainer for subwindow management
"""

from PySide6.QtWidgets import QWidget, QGridLayout, QVBoxLayout, QHBoxLayout, QSizePolicy
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from typing import Optional, List, Literal, Tuple
from datetime import datetime

from gui.sub_window_container import SubWindowContainer
from gui.image_viewer import ImageViewer
from utils.debug_flags import DEBUG_LAYOUT, DEBUG_RESIZE


LayoutMode = Literal["1x1", "1x2", "2x1", "2x2"]


class MultiWindowLayout(QWidget):
    """
    Manages multi-window layout with support for 1x1, 1x2, 2x1, and 2x2 layouts.
    
    Features:
    - Dynamic layout switching
    - Focus management
    - Subwindow creation and management
    """
    
    # Signals
    focused_subwindow_changed = Signal(SubWindowContainer)  # Emitted when focused subwindow changes
    layout_changed = Signal(str)  # Emitted when layout mode changes (layout_mode)
    
    def __init__(self, parent=None, config_manager=None):
        """
        Initialize the multi-window layout.
        
        Args:
            parent: Parent widget
            config_manager: Optional ConfigManager instance
        """
        super().__init__(parent)
        
        self.config_manager = config_manager
        
        # Current layout mode
        self.current_layout: LayoutMode = "1x1"
        
        # Subwindow containers (maximum 4 for 2x2 layout)
        self.subwindows: List[SubWindowContainer] = []
        
        # Currently focused subwindow
        self.focused_subwindow: Optional[SubWindowContainer] = None
        
        # Slot-to-view mapping for 2x2: slot_to_view[s] = view index in slot s (default [0,1,2,3])
        # Restore from config if available and valid
        self.slot_to_view = self._load_slot_to_view()
        
        # Layout widget
        self.layout_widget: Optional[QWidget] = None
        self.layout_manager: Optional[QGridLayout] = None
        
        # Last layout before switching to 1x1 (for double-click-in-1x1 revert)
        self._last_layout_before_1x1: Optional[LayoutMode] = None
        
        # Create initial layout
        self._create_layout()
        
        # Create all 4 subwindows up front so 1x2/2x1 can use (focused+1)%4 and 2x2 has all four.
        # Only the number needed for the current layout are shown; the rest are hidden.
        while len(self.subwindows) < 4:
            self._create_subwindow()
        
        # Set initial layout mode (will show only the first subwindow in 1x1)
        self.set_layout("1x1")
    
    def _load_slot_to_view(self) -> List[int]:
        """
        Load slot-to-view order from config if available and valid.
        Returns a list of 4 ints in [0,3] representing a permutation of [0,1,2,3].
        
        Returns:
            List of length 4: slot_to_view[s] = view index in slot s
        """
        default = [0, 1, 2, 3]
        if self.config_manager is None or not hasattr(
            self.config_manager, "get_view_slot_order"
        ):
            return default.copy()
        try:
            order = self.config_manager.get_view_slot_order()
            if not isinstance(order, list) or len(order) != 4:
                return default.copy()
            if set(order) != {0, 1, 2, 3}:
                return default.copy()
            return list(order)
        except Exception:
            return default.copy()
    
    def _create_layout(self) -> None:
        """Create the layout structure."""
        # Set size policy to expand
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # Main layout for this widget
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Container widget for subwindows (will use grid layout)
        self.layout_widget = QWidget(self)
        self.layout_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.layout_manager = QGridLayout(self.layout_widget)
        self.layout_manager.setContentsMargins(0, 0, 0, 0)
        self.layout_manager.setSpacing(0)
        
        main_layout.addWidget(self.layout_widget, 1)  # Add with stretch factor 1
    
    def set_layout(self, layout_mode: LayoutMode) -> None:
        """
        Set the layout mode.
        
        Args:
            layout_mode: Layout mode ("1x1", "1x2", "2x1", or "2x2")
        """
        if layout_mode not in ["1x1", "1x2", "2x1", "2x2"]:
            return
        
        # Store previous layout so we only emit layout_changed when the mode actually changed.
        # This prevents the feedback loop: set_layout -> emit -> set_layout_mode -> emit ->
        # deferred set_layout again (for 1x1 we never early-return, so we used to always re-emit).
        previous_layout = getattr(self, 'current_layout', None)
        
        if DEBUG_LAYOUT:
            import traceback
            focused_idx = self._get_focused_view_index()
            current = getattr(self, 'current_layout', None)
            stack = traceback.extract_stack()[-6:-1]
            callers = " <- ".join([f"{f.name}:{f.lineno}" for f in stack])
            ts = datetime.now().strftime("%H:%M:%S.%f")
            if DEBUG_LAYOUT:
                print(f"[DEBUG-LAYOUT] [{ts}] set_layout: mode={layout_mode!r} current_layout={current!r} focused_view_index={focused_idx} callers={callers}")
        
        num_subwindows = self._get_num_subwindows(layout_mode)
        
        # Only skip if layout matches AND we have enough subwindows AND layout is not 1x1.
        # For 1x1 we never skip so that each set_layout("1x1") re-runs _arrange_subwindows
        # and shows the current focused view.
        if (self.current_layout == layout_mode and
                layout_mode != "1x1" and
                len(self.subwindows) >= num_subwindows):
            return  # No change needed
        
        # When switching to 1x1, remember previous layout for double-click revert
        if layout_mode == "1x1" and self.current_layout != "1x1":
            self._last_layout_before_1x1 = self.current_layout
        
        self.current_layout = layout_mode
        
        # Create subwindows if needed
        while len(self.subwindows) < num_subwindows:
            self._create_subwindow()
        
        # Remove excess subwindows (hide them, don't delete)
        for i in range(num_subwindows, len(self.subwindows)):
            self.subwindows[i].hide()
        
        # Show needed subwindows and arrange them
        self._arrange_subwindows(layout_mode)
        
        # Set focus to first visible slot if no focus or focused container not visible
        if self.focused_subwindow is None or not self.focused_subwindow.isVisible():
            first_container = self._get_first_visible_container(layout_mode)
            if first_container is not None:
                self.set_focused_subwindow(first_container)
        
        # Emit only when layout mode actually changed to prevent feedback loop.
        if previous_layout != layout_mode:
            self.layout_changed.emit(layout_mode)
    
    def _get_num_subwindows(self, layout_mode: LayoutMode) -> int:
        """
        Get the number of subwindows needed for a layout mode.
        
        Args:
            layout_mode: Layout mode
            
        Returns:
            Number of subwindows needed
        """
        if layout_mode == "1x1":
            return 1
        elif layout_mode == "1x2":
            return 2
        elif layout_mode == "2x1":
            return 2
        elif layout_mode == "2x2":
            return 4
        return 1
    
    def _get_focused_view_index(self) -> int:
        """
        Return the index of the currently focused subwindow in self.subwindows.
        If focused subwindow is not in the list or None, return 0.
        
        Returns:
            Index in [0, 3] for use with subwindows and slot_to_view.
        """
        if self.focused_subwindow is not None and self.focused_subwindow in self.subwindows:
            return self.subwindows.index(self.focused_subwindow)
        return 0
    
    def _get_focused_slot(self) -> int:
        """
        Return the slot (0-3) that contains the currently focused view.
        Slot 0=top-left, 1=top-right, 2=bottom-left, 3=bottom-right.
        Used for slot-based 1x2/2x1: 1x2 shows the row containing focus, 2x1 shows the column.
        
        Returns:
            Slot index s such that slot_to_view[s] == focused view index; 0 if not found.
        """
        focused_idx = self._get_focused_view_index()
        for s in range(4):
            if s < len(self.slot_to_view) and self.slot_to_view[s] == focused_idx:
                return s
        return 0
    
    def get_slot_to_view(self) -> List[int]:
        """
        Return current slot-to-view mapping (copy). Used by Swap menu to resolve
        "Window 1-4" to view index. Window k = slot k-1; view in that slot = slot_to_view[k-1].
        
        Returns:
            List of 4 ints: slot_to_view[s] = view index in slot s.
        """
        return list(self.slot_to_view)
    
    def _get_first_visible_container(self, layout_mode: LayoutMode) -> Optional[SubWindowContainer]:
        """
        Return the container that is in the first visible slot for the given layout.
        Used to set focus when no focus or focused container is not visible.
        
        Args:
            layout_mode: Current layout mode
            
        Returns:
            SubWindowContainer for first slot, or None if none.
        """
        if not self.subwindows:
            return None
        if layout_mode == "1x1":
            idx = self._get_focused_view_index()
            if idx < len(self.subwindows):
                return self.subwindows[idx]
            return self.subwindows[0]
        if layout_mode == "1x2":
            focused_slot = self._get_focused_slot()
            row = focused_slot // 2
            idx = self.slot_to_view[row * 2] if row * 2 < len(self.slot_to_view) else 0
            if idx < len(self.subwindows):
                return self.subwindows[idx]
            return self.subwindows[0] if self.subwindows else None
        if layout_mode == "2x1":
            focused_slot = self._get_focused_slot()
            col = focused_slot % 2
            idx = self.slot_to_view[col] if col < len(self.slot_to_view) else 0
            if idx < len(self.subwindows):
                return self.subwindows[idx]
            return self.subwindows[0] if self.subwindows else None
        if layout_mode == "2x2":
            if len(self.subwindows) >= 4:
                return self.subwindows[self.slot_to_view[0]]
            return self.subwindows[0] if self.subwindows else None
        return self.subwindows[0] if self.subwindows else None
    
    def _create_subwindow(self) -> SubWindowContainer:
        """
        Create a new subwindow container.
        
        Returns:
            Created SubWindowContainer
        """
        # Create ImageViewer for this subwindow
        image_viewer = ImageViewer(config_manager=self.config_manager)
        
        # Create SubWindowContainer
        container = SubWindowContainer(image_viewer, self)
        
        # Connect signals
        container.focus_changed.connect(self._on_subwindow_focus_changed)
        container.assign_series_requested.connect(self._on_assign_series_requested)
        container.context_menu_requested.connect(self._on_context_menu_requested)
        
        # Add to list
        self.subwindows.append(container)
        
        return container
    
    def _arrange_subwindows(self, layout_mode: LayoutMode) -> None:
        """
        Arrange subwindows in the grid layout based on layout mode.
        
        Args:
            layout_mode: Layout mode
        """
        grid = self.layout_manager
        host = self.layout_widget
        if grid is None or host is None:
            return
        # Clear layout
        while grid.count():
            item = grid.takeAt(0)
            if item is None:
                continue
            child = item.widget()
            if child is not None:
                child.hide()
        
        # Determine expected grid dimensions based on layout mode
        expected_rows = 1
        expected_cols = 1
        if layout_mode == "1x2":
            expected_rows = 1
            expected_cols = 2
        elif layout_mode == "2x1":
            expected_rows = 2
            expected_cols = 1
        elif layout_mode == "2x2":
            expected_rows = 2
            expected_cols = 2
        
        # Arrange based on layout mode (focus-based for 1x1, 1x2, 2x1; slot_to_view for 2x2)
        if layout_mode == "1x1":
            # Single window: show only the focused view's container
            if len(self.subwindows) >= 1:
                idx = self._get_focused_view_index()
                container = self.subwindows[idx]
                container.show()
                grid.addWidget(container, 0, 0, 1, 1)
        elif layout_mode == "1x2":
            # Two windows side by side: row in 2x2 containing focused slot (slot-based)
            if len(self.subwindows) >= 2:
                focused_slot = self._get_focused_slot()
                row = focused_slot // 2
                v0 = self.slot_to_view[row * 2]
                v1 = self.slot_to_view[row * 2 + 1]
                self.subwindows[v0].show()
                self.subwindows[v1].show()
                grid.addWidget(self.subwindows[v0], 0, 0, 1, 1)
                grid.addWidget(self.subwindows[v1], 0, 1, 1, 1)
        elif layout_mode == "2x1":
            # Two windows stacked: column in 2x2 containing focused slot (slot-based)
            if len(self.subwindows) >= 2:
                focused_slot = self._get_focused_slot()
                col = focused_slot % 2
                v0 = self.slot_to_view[col]
                v1 = self.slot_to_view[col + 2]
                self.subwindows[v0].show()
                self.subwindows[v1].show()
                grid.addWidget(self.subwindows[v0], 0, 0, 1, 1)
                grid.addWidget(self.subwindows[v1], 1, 0, 1, 1)
        elif layout_mode == "2x2":
            # Four windows in grid: order by slot_to_view (slot s -> row s//2, col s%2)
            if len(self.subwindows) >= 4:
                for s in range(4):
                    view_idx = self.slot_to_view[s]
                    self.subwindows[view_idx].show()
                    row, col = s // 2, s % 2
                    grid.addWidget(self.subwindows[view_idx], row, col, 1, 1)
        
        # Explicitly manage grid layout dimensions
        # Set stretch factors only for rows/columns that should exist
        current_rows = grid.rowCount()
        current_cols = grid.columnCount()
        
        # Set stretch factors for expected rows and columns
        for i in range(expected_rows):
            grid.setRowStretch(i, 1)
        # Remove stretch from any extra rows
        for i in range(expected_rows, current_rows):
            grid.setRowStretch(i, 0)
        
        for i in range(expected_cols):
            grid.setColumnStretch(i, 1)
        # Remove stretch from any extra columns
        for i in range(expected_cols, current_cols):
            grid.setColumnStretch(i, 0)
        
        # Ensure all visible subwindows have expanding size policy
        for subwindow in self.subwindows:
            if subwindow and subwindow.isVisible():
                subwindow.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                # Clear any size constraints that might prevent expansion
                subwindow.setMinimumSize(0, 0)
                subwindow.setMaximumSize(16777215, 16777215)  # QWIDGETSIZE_MAX
        
        # Force layout activation to recalculate geometry
        grid.activate()
        
        # Force layout to recalculate geometry using QTimer to delay update
        # This ensures Qt has processed all layout changes before forcing recalculation
        # Fix: Use proper function instead of tuple lambda
        from PySide6.QtCore import QTimer
        import os
        def force_layout_update():
            """Force layout geometry update after delay."""
            host.updateGeometry()
            self.updateGeometry()
            # Force repaint
            host.update()
            self.update()
        
        QTimer.singleShot(10, force_layout_update)
        
        # Optional: debug resize when switching from 2x2 to 1x2/2x1 (Phase 5.6). Set env DICOM_DEBUG_LAYOUT_RESIZE=1 to enable.
        if os.environ.get("DICOM_DEBUG_LAYOUT_RESIZE"):
            def _debug_resize():
                visible = [i for i, w in enumerate(self.subwindows) if w and w.isVisible()]
                for i in visible:
                    w = self.subwindows[i]
                    w.updateGeometry()
                    w.update()
                host.updateGeometry()
                self.updateGeometry()
                # Log sizes for investigation
                if DEBUG_RESIZE:
                    sizes = [(i, self.subwindows[i].size().width(), self.subwindows[i].size().height()) for i in visible]
                    print(f"[DEBUG-RESIZE] layout={layout_mode} visible_indices={visible} sizes={sizes}")
            QTimer.singleShot(50, _debug_resize)
    
    def _on_subwindow_focus_changed(self, focused: bool) -> None:
        """
        Handle subwindow focus change.
        
        Args:
            focused: True if subwindow gained focus
        """
        # print(f"[DEBUG-FOCUS] MultiWindowLayout._on_subwindow_focus_changed: Signal received, focused={focused}")
        if not focused:
            # print(f"[DEBUG-FOCUS] MultiWindowLayout._on_subwindow_focus_changed: Focus loss, ignoring")
            return  # Only handle focus gain
        
        # Find which subwindow emitted the signal
        sender = self.sender()
        # print(f"[DEBUG-FOCUS] MultiWindowLayout._on_subwindow_focus_changed: Sender={sender}, is SubWindowContainer={isinstance(sender, SubWindowContainer)}")
        if isinstance(sender, SubWindowContainer):
            # print(f"[DEBUG-FOCUS] MultiWindowLayout._on_subwindow_focus_changed: Calling set_focused_subwindow")
            self.set_focused_subwindow(sender)
    
    def set_focused_subwindow(self, subwindow: SubWindowContainer) -> None:
        """
        Set the focused subwindow.
        
        Args:
            subwindow: SubWindowContainer to focus
        """
        # print(f"[DEBUG-FOCUS] MultiWindowLayout.set_focused_subwindow: Called, current focused={self.focused_subwindow}, new={subwindow}")
        if subwindow == self.focused_subwindow:
            # print(f"[DEBUG-FOCUS] MultiWindowLayout.set_focused_subwindow: Already focused, returning")
            return  # Already focused
        
        # Unfocus current subwindow
        if self.focused_subwindow is not None:
            # print(f"[DEBUG-FOCUS] MultiWindowLayout.set_focused_subwindow: Unfocusing previous subwindow")
            self.focused_subwindow.set_focused(False)
        
        # Focus new subwindow
        self.focused_subwindow = subwindow
        if self.focused_subwindow is not None:
            # print(f"[DEBUG-FOCUS] MultiWindowLayout.set_focused_subwindow: Focusing new subwindow")
            self.focused_subwindow.set_focused(True)
        
        # Emit signal
        # print(f"[DEBUG-FOCUS] MultiWindowLayout.set_focused_subwindow: Emitting focused_subwindow_changed signal")
        self.focused_subwindow_changed.emit(self.focused_subwindow)
        # 1×1: single visible pane follows focused view — re-arrange so the window map
        # can switch which pane is shown. 1×2 / 2×1: row/column follows focused slot.
        if self.current_layout in ("1x1", "1x2", "2x1"):
            self._arrange_subwindows(self.current_layout)

    def get_focused_subwindow(self) -> Optional[SubWindowContainer]:
        """
        Get the currently focused subwindow.
        
        Returns:
            Focused SubWindowContainer or None
        """
        return self.focused_subwindow
    
    def get_subwindow(self, index: int) -> Optional[SubWindowContainer]:
        """
        Get a subwindow by index.
        
        Args:
            index: Subwindow index (0-based)
            
        Returns:
            SubWindowContainer or None if index is invalid
        """
        if 0 <= index < len(self.subwindows):
            return self.subwindows[index]
        return None
    
    def get_all_subwindows(self) -> List[SubWindowContainer]:
        """
        Get all subwindows.
        
        Returns:
            List of all SubWindowContainer instances
        """
        return self.subwindows.copy()

    def get_screenshot_grid_cells(self) -> List[Tuple[int, int, int]]:
        """
        Describe the on-screen image grid for composite screenshot export.

        Returns:
            List of (row, col, view_index) for each visible layout cell, in reading
            order (left-to-right, top-to-bottom). ``view_index`` indexes
            ``get_all_subwindows()`` (0..3). Layout matches ``_arrange_subwindows``.
        """
        mode = self.current_layout
        stv = self.slot_to_view
        if mode == "1x1":
            idx = self._get_focused_view_index()
            return [(0, 0, idx)]
        if mode == "1x2":
            focused_slot = self._get_focused_slot()
            row = focused_slot // 2
            v0 = stv[row * 2]
            v1 = stv[row * 2 + 1]
            return [(0, 0, v0), (0, 1, v1)]
        if mode == "2x1":
            focused_slot = self._get_focused_slot()
            col = focused_slot % 2
            v0 = stv[col]
            v1 = stv[col + 2]
            return [(0, 0, v0), (1, 0, v1)]
        if mode == "2x2":
            out: List[Tuple[int, int, int]] = []
            for s in range(4):
                r, c = s // 2, s % 2
                out.append((r, c, stv[s]))
            return out
        idx = self._get_focused_view_index()
        return [(0, 0, idx)]

    def grab_layout_grid_pixmap(self) -> Optional[QPixmap]:
        """
        Capture the visible multi-pane grid exactly as arranged on screen.

        This grabs ``layout_widget`` (the internal QGridLayout host with zero margins
        and spacing), so exported composites match the app layout without gutters
        caused by assembling per-viewport grabs with mismatched logical vs device sizes.

        Returns:
            Non-null pixmap on success, or None if there is nothing to grab.
        """
        host = self.layout_widget
        if host is None or not host.isVisible():
            return None
        host.update()
        pix = host.grab()
        if pix.isNull() or pix.width() < 1 or pix.height() < 1:
            return None
        return pix

    def _on_assign_series_requested(self, series_uid: str, slice_index: int, study_uid: str = "") -> None:
        """
        Handle series assignment request from a subwindow.
        
        Args:
            series_uid: Series UID to assign
            slice_index: Slice index to assign
            study_uid: Study UID when known from drag payload (may be empty)
        """
        # This will be handled by the main application
        # Emit a signal that main.py can connect to
        sender = self.sender()
        if isinstance(sender, SubWindowContainer):
            # Store assignment in subwindow
            sender.set_assigned_series(series_uid, slice_index)
    
    def _on_context_menu_requested(self) -> None:
        """Handle context menu request from a subwindow."""
        # This will be handled by the main application
        pass
    
    def get_layout_mode(self) -> LayoutMode:
        """
        Get the current layout mode.
        
        Returns:
            Current layout mode
        """
        return self.current_layout

    def get_revert_layout(self) -> LayoutMode:
        """
        Get the layout to revert to when user double-clicks in 1x1 (expand-to-1x1 toggle).
        Returns the last layout that was active before switching to 1x1, or "2x2" if none.
        """
        if self._last_layout_before_1x1 in ("1x2", "2x1", "2x2"):
            return self._last_layout_before_1x1
        return "2x2"

    def swap_views(self, view_index_a: int, view_index_b: int) -> None:
        """
        Swap the slot positions of two views (updates slot_to_view).
        Effective in all layouts:
        - 2x2: all four positions update.
        - 1x2 / 2x1: slot order is updated and visible panes are re-arranged.
        - 1x1: slot order is updated for when the user switches layouts; visible
          content stays bound to the focused view.
        
        View data (slice, ROIs, etc.) stays with the same logical view index.
        After swapping slot_to_view, focus is re-applied to the **same window
        (grid slot)** that was focused before the swap, so ROI list/statistics,
        slice navigator, metadata, and cine controls follow the content now
        occupying that window.
        
        Args:
            view_index_a: View index (0-3)
            view_index_b: View index (0-3), must differ from view_index_a
        """
        if view_index_a < 0 or view_index_a >= 4 or view_index_b < 0 or view_index_b >= 4:
            return
        if view_index_a == view_index_b:
            return

        # Remember which slot (window) is currently focused so we can keep
        # focus on that window after the swap and have panels follow the
        # swapped-in view.
        focused_slot = None
        if self.focused_subwindow is not None and self.focused_subwindow in self.subwindows:
            focused_view_idx = self.subwindows.index(self.focused_subwindow)
            for s in range(4):
                if s < len(self.slot_to_view) and self.slot_to_view[s] == focused_view_idx:
                    focused_slot = s
                    break

        # Find slots that currently show these views
        s_a = s_b = None
        for s in range(4):
            if self.slot_to_view[s] == view_index_a:
                s_a = s
            if self.slot_to_view[s] == view_index_b:
                s_b = s
        if s_a is None or s_b is None:
            return
        self.slot_to_view[s_a], self.slot_to_view[s_b] = (
            self.slot_to_view[s_b],
            self.slot_to_view[s_a],
        )
        if self.config_manager is not None and hasattr(
            self.config_manager, "set_view_slot_order"
        ):
            try:
                self.config_manager.set_view_slot_order(self.slot_to_view)
            except Exception:
                pass

        # Re-apply focus to the same window (slot) that was focused before the
        # swap so that _arrange_subwindows (which uses focused view/slot in 1x2
        # and 2x1) keeps showing the row/column containing that window, and all
        # panels follow the swapped-in view in that window.
        if focused_slot is not None:
            new_view_index = self.slot_to_view[focused_slot] if focused_slot < len(self.slot_to_view) else None
            if new_view_index is not None and 0 <= new_view_index < len(self.subwindows):
                self.set_focused_subwindow(self.subwindows[new_view_index])

        # Re-arrange visible panes so layout reflects new slot order (including 1x1
        # so the single visible pane is the swapped-in view for the focused window).
        if self.current_layout == "2x2":
            self._arrange_subwindows("2x2")
        elif self.current_layout == "1x2":
            self._arrange_subwindows("1x2")
        elif self.current_layout == "2x1":
            self._arrange_subwindows("2x1")
        elif self.current_layout == "1x1":
            self._arrange_subwindows("1x1")

    def reset_slot_to_view_default(self) -> None:
        """
        Reset slot-to-view mapping to default: views A–D (0–3) in windows 1–4 (slots 0–3).
        Persist to config and re-arrange if currently in 2x2.
        Call when all files are closed or when the application is about to exit.
        """
        self.slot_to_view = [0, 1, 2, 3]
        if self.config_manager is not None and hasattr(
            self.config_manager, "set_view_slot_order"
        ):
            try:
                self.config_manager.set_view_slot_order(self.slot_to_view)
            except Exception:
                pass
        if self.current_layout == "2x2":
            self._arrange_subwindows("2x2")

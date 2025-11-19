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
from typing import Optional, List, Literal

from gui.sub_window_container import SubWindowContainer
from gui.image_viewer import ImageViewer


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
        
        # Layout widget
        self.layout_widget: Optional[QWidget] = None
        self.layout_manager: Optional[QGridLayout] = None
        
        # Create initial layout
        self._create_layout()
        
        # Set initial layout mode
        self.set_layout("1x1")
    
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
        
        # Only skip if layout matches AND subwindows already exist
        # This ensures subwindows are created on first launch even if layout is already "1x1"
        if self.current_layout == layout_mode and len(self.subwindows) > 0:
            return  # No change needed
        
        self.current_layout = layout_mode
        
        # Determine number of subwindows needed
        num_subwindows = self._get_num_subwindows(layout_mode)
        
        # Create subwindows if needed
        while len(self.subwindows) < num_subwindows:
            self._create_subwindow()
        
        # Remove excess subwindows (hide them, don't delete)
        for i in range(num_subwindows, len(self.subwindows)):
            self.subwindows[i].hide()
        
        # Show needed subwindows and arrange them
        self._arrange_subwindows(layout_mode)
        
        # Set focus to first subwindow if no focus
        if self.focused_subwindow is None or not self.focused_subwindow.isVisible():
            if self.subwindows:
                self.set_focused_subwindow(self.subwindows[0])
        
        # Emit signal
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
        # Clear layout
        while self.layout_manager.count():
            item = self.layout_manager.takeAt(0)
            if item.widget():
                item.widget().hide()
        
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
        
        # Arrange based on layout mode
        if layout_mode == "1x1":
            # Single window: row 0, col 0, spans 1x1
            if len(self.subwindows) >= 1:
                self.subwindows[0].show()
                self.layout_manager.addWidget(self.subwindows[0], 0, 0, 1, 1)
        elif layout_mode == "1x2":
            # Two windows side by side: row 0, cols 0 and 1
            if len(self.subwindows) >= 2:
                self.subwindows[0].show()
                self.subwindows[1].show()
                self.layout_manager.addWidget(self.subwindows[0], 0, 0, 1, 1)
                self.layout_manager.addWidget(self.subwindows[1], 0, 1, 1, 1)
        elif layout_mode == "2x1":
            # Two windows stacked: rows 0 and 1, col 0
            if len(self.subwindows) >= 2:
                self.subwindows[0].show()
                self.subwindows[1].show()
                self.layout_manager.addWidget(self.subwindows[0], 0, 0, 1, 1)
                self.layout_manager.addWidget(self.subwindows[1], 1, 0, 1, 1)
        elif layout_mode == "2x2":
            # Four windows in grid: rows 0-1, cols 0-1
            if len(self.subwindows) >= 4:
                for i in range(4):
                    self.subwindows[i].show()
                self.layout_manager.addWidget(self.subwindows[0], 0, 0, 1, 1)
                self.layout_manager.addWidget(self.subwindows[1], 0, 1, 1, 1)
                self.layout_manager.addWidget(self.subwindows[2], 1, 0, 1, 1)
                self.layout_manager.addWidget(self.subwindows[3], 1, 1, 1, 1)
        
        # Explicitly manage grid layout dimensions
        # Set stretch factors only for rows/columns that should exist
        current_rows = self.layout_manager.rowCount()
        current_cols = self.layout_manager.columnCount()
        
        # Set stretch factors for expected rows and columns
        for i in range(expected_rows):
            self.layout_manager.setRowStretch(i, 1)
        # Remove stretch from any extra rows
        for i in range(expected_rows, current_rows):
            self.layout_manager.setRowStretch(i, 0)
        
        for i in range(expected_cols):
            self.layout_manager.setColumnStretch(i, 1)
        # Remove stretch from any extra columns
        for i in range(expected_cols, current_cols):
            self.layout_manager.setColumnStretch(i, 0)
        
        # Ensure all visible subwindows have expanding size policy
        for subwindow in self.subwindows:
            if subwindow and subwindow.isVisible():
                subwindow.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                # Clear any size constraints that might prevent expansion
                subwindow.setMinimumSize(0, 0)
                subwindow.setMaximumSize(16777215, 16777215)  # QWIDGETSIZE_MAX
        
        # Force layout activation to recalculate geometry
        self.layout_manager.activate()
        
        # Force layout to recalculate geometry using QTimer to delay update
        # This ensures Qt has processed all layout changes before forcing recalculation
        # Fix: Use proper function instead of tuple lambda
        from PySide6.QtCore import QTimer
        def force_layout_update():
            """Force layout geometry update after delay."""
            self.layout_widget.updateGeometry()
            self.updateGeometry()
            # Force repaint
            self.layout_widget.update()
            self.update()
        
        QTimer.singleShot(10, force_layout_update)
    
    def _on_subwindow_focus_changed(self, focused: bool) -> None:
        """
        Handle subwindow focus change.
        
        Args:
            focused: True if subwindow gained focus
        """
        if not focused:
            return  # Only handle focus gain
        
        # Find which subwindow emitted the signal
        sender = self.sender()
        if isinstance(sender, SubWindowContainer):
            self.set_focused_subwindow(sender)
    
    def set_focused_subwindow(self, subwindow: SubWindowContainer) -> None:
        """
        Set the focused subwindow.
        
        Args:
            subwindow: SubWindowContainer to focus
        """
        if subwindow == self.focused_subwindow:
            return  # Already focused
        
        # Unfocus current subwindow
        if self.focused_subwindow is not None:
            self.focused_subwindow.set_focused(False)
        
        # Focus new subwindow
        self.focused_subwindow = subwindow
        if self.focused_subwindow is not None:
            self.focused_subwindow.set_focused(True)
        
        # Emit signal
        self.focused_subwindow_changed.emit(self.focused_subwindow)
    
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
    
    def _on_assign_series_requested(self, series_uid: str, slice_index: int) -> None:
        """
        Handle series assignment request from a subwindow.
        
        Args:
            series_uid: Series UID to assign
            slice_index: Slice index to assign
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


"""
Slice Navigator

This module handles slice navigation with arrow keys and mouse wheel,
with scroll wheel mode toggle between zooming and slice navigation.

Inputs:
    - Keyboard arrow key events
    - Mouse wheel events
    - Scroll wheel mode setting
    
Outputs:
    - Current slice index changes
    - Navigation signals
    
Requirements:
    - PySide6 for event handling
"""


from PySide6.QtCore import QObject, Qt, Signal


class SliceNavigator(QObject):
    """
    Handles slice navigation functionality.
    
    Features:
    - Navigate slices with arrow keys
    - Navigate slices with mouse wheel (when in slice mode)
    - Toggle between zoom and slice navigation modes
    """

    # Signals
    slice_changed = Signal(int)  # Emitted when slice index changes

    def __init__(self):
        """Initialize the slice navigator."""
        super().__init__()
        self.current_slice_index = 0
        self.total_slices = 0
        self.scroll_wheel_mode = "slice"  # "slice" or "zoom"

    def set_total_slices(self, total: int) -> None:
        """
        Set the total number of slices.
        
        Args:
            total: Total number of slices
        """
        self.total_slices = max(0, total)
        # Ensure current index is valid
        if self.current_slice_index >= self.total_slices:
            self.current_slice_index = max(0, self.total_slices - 1)

    def set_scroll_wheel_mode(self, mode: str) -> None:
        """
        Set scroll wheel mode.
        
        Args:
            mode: "slice" or "zoom"
        """
        if mode in ["slice", "zoom"]:
            self.scroll_wheel_mode = mode

    def get_current_slice(self) -> int:
        """
        Get current slice index.
        
        Returns:
            Current slice index
        """
        return self.current_slice_index

    def set_current_slice(self, index: int) -> None:
        """
        Set current slice index.
        
        Args:
            index: Slice index to set
        """
        if 0 <= index < self.total_slices:
            if self.current_slice_index != index:
                self.current_slice_index = index
                self.slice_changed.emit(self.current_slice_index)

    def next_slice(self) -> None:
        """Navigate to next slice."""
        self.set_current_slice(self.current_slice_index + 1)

    def previous_slice(self) -> None:
        """Navigate to previous slice."""
        self.set_current_slice(self.current_slice_index - 1)

    def first_slice(self) -> None:
        """Navigate to first slice."""
        self.set_current_slice(0)

    def last_slice(self) -> None:
        """Navigate to last slice."""
        self.set_current_slice(self.total_slices - 1)

    def handle_key_event(self, key: int) -> bool:
        """
        Handle keyboard event for navigation.
        
        Args:
            key: Key code
            
        Returns:
            True if event was handled, False otherwise
        """
        if key in (Qt.Key.Key_Up, Qt.Key.Key_Right, Qt.Key.Key_PageDown):
            self.next_slice()
            return True
        elif key in (Qt.Key.Key_Down, Qt.Key.Key_Left, Qt.Key.Key_PageUp):
            self.previous_slice()
            return True
        elif key == Qt.Key.Key_Home:
            self.first_slice()
            return True
        elif key == Qt.Key.Key_End:
            self.last_slice()
            return True

        return False

    def handle_wheel_event(self, delta: int) -> bool:
        """
        Handle mouse wheel event for navigation (if in slice mode).
        
        Args:
            delta: Wheel delta (positive = scroll up, negative = scroll down)
            
        Returns:
            True if event was handled, False otherwise
        """
        if self.scroll_wheel_mode != "slice" or delta == 0:
            return False

        if delta > 0:
            self.previous_slice()
        else:
            self.next_slice()

        return True

    def advance_to_frame(self, index: int, loop: bool = False) -> None:
        """
        Advance to a specific frame index, with optional loop support.
        
        Args:
            index: Frame index to advance to
            loop: If True and index is out of bounds, wrap around. If False, clamp to valid range.
        """
        if self.total_slices == 0:
            return

        if loop:
            # Wrap around if out of bounds
            if index < 0:
                index = self.total_slices - 1
            elif index >= self.total_slices:
                index = 0
        else:
            # Clamp to valid range
            index = max(0, min(index, self.total_slices - 1))

        if self.current_slice_index != index:
            self.current_slice_index = index
            self.slice_changed.emit(self.current_slice_index)


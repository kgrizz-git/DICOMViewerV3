"""
Magnifier Widget

This module provides a floating magnifier widget that displays a magnified
region of the image following the cursor.

Inputs:
    - Image region to display
    - Position updates
    
Outputs:
    - Floating magnified view
    
Requirements:
    - PySide6 for widget components
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QPixmap, QPainter, QColor, QPen
from typing import Optional

try:
    from utils.debug_flags import DEBUG_MAGNIFIER as _debug_magnifier_imported
except ImportError:
    _debug_magnifier_imported = False

_debug_magnifier_enabled: bool = bool(_debug_magnifier_imported)


class MagnifierWidget(QWidget):
    """
    Floating widget that displays a magnified region of the image.
    
    Features:
    - Fixed size display area
    - Border and shadow for visibility
    - Updates position and content based on cursor
    """
    
    def __init__(self, parent=None):
        """
        Initialize the magnifier widget.
        
        Args:
            parent: Parent widget (optional, None for floating window)
        """
        super().__init__(parent)
        
        # Set widget properties for floating window
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        
        # Fixed size for magnifier
        self.magnifier_size = 200
        self.setFixedSize(self.magnifier_size, self.magnifier_size)
        
        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)
        
        # Label to display magnified image
        self.image_label = QLabel(self)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("""
            QLabel {
                background-color: white;
                border: 2px solid #333;
                border-radius: 2px;
            }
        """)
        layout.addWidget(self.image_label)
        
        # Set widget style
        self.setStyleSheet("""
            QWidget {
                background-color: rgba(0, 0, 0, 0);
            }
        """)
        
        # Initially hidden
        self.hide()
    
    def update_magnified_region(self, pixmap: QPixmap) -> None:
        """
        Update the displayed magnified region.
        
        Args:
            pixmap: QPixmap containing the magnified image region
        """
        if pixmap.isNull():
            self.image_label.clear()
            return
        
        if _debug_magnifier_enabled:
            print(f"[DEBUG-MAGNIFIER] update_magnified_region: input_pixmap_size=({pixmap.width()}x{pixmap.height()}), widget_size={self.magnifier_size}")
        
        # Scale pixmap to fit label while maintaining aspect ratio
        target_size = self.magnifier_size - 4  # Account for border
        scaled_pixmap = pixmap.scaled(
            target_size,
            target_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        
        # Keep this debug lightweight: only log input size above, not every derived metric.
        
        self.image_label.setPixmap(scaled_pixmap)
    
    def show_at_position(self, global_pos: QPoint) -> None:
        """
        Show the magnifier widget centered on the specified global position.
        
        The widget is positioned centered on the cursor.
        
        Args:
            global_pos: Global screen position (QPoint)
        """
        # Center the magnifier on the requested global position
        x = global_pos.x() - self.magnifier_size // 2
        y = global_pos.y() - self.magnifier_size // 2
        
        # Ensure widget stays on screen – use the screen that contains the target point
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        screen_obj = (
            app.screenAt(global_pos)
            if isinstance(app, QApplication)
            else None
        )
        primary = QApplication.primaryScreen()
        screen = (
            screen_obj.geometry()
            if screen_obj is not None
            else (primary.geometry() if primary is not None else self.screen().geometry())
        )
        
        # Adjust if would go off left edge
        if x < screen.left():
            x = screen.left()
        
        # Adjust if would go off right edge
        if x + self.magnifier_size > screen.right():
            x = screen.right() - self.magnifier_size
        
        # Adjust if would go off top edge
        if y < screen.top():
            y = screen.top()
        
        # Adjust if would go off bottom edge
        if y + self.magnifier_size > screen.bottom():
            y = screen.bottom() - self.magnifier_size
        
        if _debug_magnifier_enabled:
            print(
                "[DEBUG-MAGNIFIER] MagnifierWidget.show_at_position: "
                f"requested_global=({global_pos.x()},{global_pos.y()}), "
                f"screen=({screen.left()},{screen.top()})-({screen.right()},{screen.bottom()}), "
                f"final_pos=({x},{y}), size={self.magnifier_size}"
            )

        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()


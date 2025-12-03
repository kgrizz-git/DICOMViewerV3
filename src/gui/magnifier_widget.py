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
        
        print(f"[DEBUG-MAGNIFIER] update_magnified_region: input_pixmap_size=({pixmap.width()}x{pixmap.height()}), widget_size={self.magnifier_size}")
        
        # Scale pixmap to fit label while maintaining aspect ratio
        target_size = self.magnifier_size - 4  # Account for border
        scaled_pixmap = pixmap.scaled(
            target_size,
            target_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        
        print(f"[DEBUG-MAGNIFIER] update_magnified_region: final_display_size=({scaled_pixmap.width()}x{scaled_pixmap.height()}), effective_zoom={target_size / pixmap.width():.3f}x")
        
        self.image_label.setPixmap(scaled_pixmap)
    
    def show_at_position(self, global_pos: QPoint) -> None:
        """
        Show the magnifier widget centered on the specified global position.
        
        The widget is positioned centered on the cursor.
        
        Args:
            global_pos: Global screen position (QPoint)
        """
        # Center the magnifier on the cursor
        x = global_pos.x() - self.magnifier_size // 2
        y = global_pos.y() - self.magnifier_size // 2
        
        # Ensure widget stays on screen
        from PySide6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().geometry()
        
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
        
        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()


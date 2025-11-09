"""
Series Navigator Widget

This module provides a horizontal series navigator bar that displays thumbnails
of the first slice of each series with series numbers overlaid.

Inputs:
    - Studies dictionary with series data
    - Current study and series UIDs
    - DICOMProcessor for thumbnail generation
    
Outputs:
    - Visual series navigator with clickable thumbnails
    - Series selection signal
    
Requirements:
    - PySide6 for GUI components
    - PIL/Pillow for image handling
    - DICOMProcessor for image conversion
"""

from PySide6.QtWidgets import (QWidget, QHBoxLayout, QScrollArea, QVBoxLayout,
                                QLabel, QFrame)
from PySide6.QtCore import Qt, Signal, QSize, QPoint
from PySide6.QtGui import QPixmap, QImage, QPainter, QFont, QColor
from typing import Optional, Dict
from pydicom.dataset import Dataset
from core.dicom_processor import DICOMProcessor
from PIL import Image


class SeriesThumbnail(QFrame):
    """
    Individual thumbnail widget for a series.
    
    Displays first slice image with series number overlaid.
    """
    
    clicked = Signal(str)  # Emitted with series_uid when clicked
    
    def __init__(self, series_uid: str, series_number: int, thumbnail_image: Optional[Image.Image], parent=None):
        """
        Initialize series thumbnail.
        
        Args:
            series_uid: Series instance UID
            series_number: Series number to display
            thumbnail_image: PIL Image for thumbnail (or None)
            parent: Parent widget
        """
        super().__init__(parent)
        self.series_uid = series_uid
        self.series_number = series_number
        self.thumbnail_image = thumbnail_image
        self.is_current = False
        
        # Set fixed size for thumbnails
        self.setFixedSize(120, 120)
        self.setFrameStyle(QFrame.Shape.Box)
        self.setLineWidth(2)
        self.setStyleSheet("QFrame { border: 2px solid gray; }")
        
        # Enable mouse tracking for hover effects
        self.setMouseTracking(True)
        
    def set_current(self, is_current: bool) -> None:
        """
        Set whether this is the current series.
        
        Args:
            is_current: True if this is the current series
        """
        self.is_current = is_current
        if is_current:
            self.setStyleSheet("QFrame { border: 3px solid #00aaff; background-color: rgba(0, 170, 255, 0.1); }")
        else:
            self.setStyleSheet("QFrame { border: 2px solid gray; }")
        self.update()
    
    def mousePressEvent(self, event) -> None:
        """Handle mouse click to select series."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.series_uid)
        super().mousePressEvent(event)
    
    def paintEvent(self, event) -> None:
        """Paint thumbnail image with series number overlay."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw thumbnail image if available
        if self.thumbnail_image is not None:
            # Convert PIL Image to QPixmap
            if self.thumbnail_image.mode == 'L':
                qimage = QImage(self.thumbnail_image.tobytes(), 
                              self.thumbnail_image.width, self.thumbnail_image.height,
                              QImage.Format.Format_Grayscale8)
            elif self.thumbnail_image.mode == 'RGB':
                qimage = QImage(self.thumbnail_image.tobytes(), 
                              self.thumbnail_image.width, self.thumbnail_image.height,
                              QImage.Format.Format_RGB888)
            else:
                # Convert to RGB
                rgb_image = self.thumbnail_image.convert('RGB')
                qimage = QImage(rgb_image.tobytes(), 
                              rgb_image.width, rgb_image.height,
                              QImage.Format.Format_RGB888)
            
            pixmap = QPixmap.fromImage(qimage)
            # Scale to fit thumbnail size (maintain aspect ratio)
            scaled_pixmap = pixmap.scaled(self.width() - 4, self.height() - 4,
                                         Qt.AspectRatioMode.KeepAspectRatio,
                                         Qt.TransformationMode.SmoothTransformation)
            # Center the image
            x = (self.width() - scaled_pixmap.width()) // 2
            y = (self.height() - scaled_pixmap.height()) // 2
            painter.drawPixmap(x, y, scaled_pixmap)
        else:
            # Draw placeholder if no image
            painter.fillRect(self.rect(), QColor(128, 128, 128))
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No Image")
        
        # Draw series number overlay (top-left corner)
        painter.setPen(QColor(255, 255, 0))  # Yellow text
        painter.setBrush(QColor(0, 0, 0, 180))  # Semi-transparent black background
        font = QFont()
        font.setBold(True)
        font.setPointSize(12)
        painter.setFont(font)
        
        series_text = f"S{self.series_number}"
        text_rect = painter.fontMetrics().boundingRect(series_text)
        padding = 4
        bg_rect = text_rect.adjusted(-padding, -padding, padding, padding)
        # Position in top-left corner with padding
        top_left = self.rect().topLeft()
        bg_rect.moveTopLeft(QPoint(int(top_left.x()) + padding, int(top_left.y()) + padding))
        
        # Draw background rectangle
        painter.drawRect(bg_rect)
        # Draw text
        painter.drawText(bg_rect, Qt.AlignmentFlag.AlignCenter, series_text)


class SeriesNavigator(QWidget):
    """
    Horizontal series navigator bar with thumbnails.
    
    Displays thumbnails of the first slice of each series with series numbers
    overlaid. Clicking a thumbnail navigates to that series.
    """
    
    series_selected = Signal(str)  # Emitted with series_uid when thumbnail is clicked
    
    def __init__(self, dicom_processor: DICOMProcessor, parent=None):
        """
        Initialize series navigator.
        
        Args:
            dicom_processor: DICOMProcessor instance for thumbnail generation
            parent: Parent widget
        """
        super().__init__(parent)
        self.dicom_processor = dicom_processor
        self.current_study_uid = ""
        self.current_series_uid = ""
        self.thumbnails: Dict[str, SeriesThumbnail] = {}
        
        # Thumbnail cache: (study_uid, series_uid) -> PIL Image
        self.thumbnail_cache: Dict[tuple, Image.Image] = {}
        
        self._create_ui()
    
    def _create_ui(self) -> None:
        """Create the UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create scroll area for horizontal scrolling
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        
        # Container widget for thumbnails
        self.thumbnail_container = QWidget()
        self.thumbnail_layout = QHBoxLayout(self.thumbnail_container)
        self.thumbnail_layout.setContentsMargins(5, 5, 5, 5)
        self.thumbnail_layout.setSpacing(5)
        self.thumbnail_layout.addStretch()  # Add stretch at end
        
        scroll_area.setWidget(self.thumbnail_container)
        layout.addWidget(scroll_area)
        
        # Set fixed height for navigator
        self.setFixedHeight(140)
    
    def update_series_list(self, studies: Dict, current_study_uid: str, current_series_uid: str) -> None:
        """
        Update the series list with thumbnails.
        
        Args:
            studies: Dictionary of studies {study_uid: {series_uid: [datasets]}}
            current_study_uid: Current study UID
            current_series_uid: Current series UID
        """
        self.current_study_uid = current_study_uid
        self.current_series_uid = current_series_uid
        
        # Clear existing thumbnails
        for thumbnail in self.thumbnails.values():
            self.thumbnail_layout.removeWidget(thumbnail)
            thumbnail.deleteLater()
        self.thumbnails.clear()
        
        if not studies or current_study_uid not in studies:
            return
        
        # Get series for current study
        study_series = studies[current_study_uid]
        
        # Build list of (series_number, series_uid, first_dataset)
        series_list = []
        for series_uid, datasets in study_series.items():
            if datasets:
                first_dataset = datasets[0]
                series_number = getattr(first_dataset, 'SeriesNumber', None)
                try:
                    series_num = int(series_number) if series_number is not None else 0
                except (ValueError, TypeError):
                    series_num = 0
                series_list.append((series_num, series_uid, first_dataset))
        
        # Sort by series number
        series_list.sort(key=lambda x: x[0])
        
        # Create thumbnails
        for series_num, series_uid, first_dataset in series_list:
            # Check cache first
            cache_key = (current_study_uid, series_uid)
            if cache_key in self.thumbnail_cache:
                thumbnail_image = self.thumbnail_cache[cache_key]
            else:
                # Generate thumbnail
                thumbnail_image = self._generate_thumbnail(first_dataset)
                if thumbnail_image:
                    self.thumbnail_cache[cache_key] = thumbnail_image
            
            # Create thumbnail widget
            thumbnail = SeriesThumbnail(series_uid, series_num, thumbnail_image, self)
            thumbnail.clicked.connect(self.series_selected.emit)
            thumbnail.set_current(series_uid == current_series_uid)
            
            self.thumbnails[series_uid] = thumbnail
            # Insert before the stretch
            self.thumbnail_layout.insertWidget(self.thumbnail_layout.count() - 1, thumbnail)
    
    def _generate_thumbnail(self, dataset: Dataset) -> Optional[Image.Image]:
        """
        Generate thumbnail image from first slice of series.
        
        Args:
            dataset: DICOM dataset (first slice of series)
            
        Returns:
            PIL Image thumbnail (resized) or None if generation fails
        """
        try:
            # Convert dataset to image
            image = self.dicom_processor.dataset_to_image(dataset, apply_rescale=False)
            if image is None:
                return None
            
            # Resize to thumbnail size (maintain aspect ratio)
            thumbnail_size = 100  # Target size for thumbnail
            image.thumbnail((thumbnail_size, thumbnail_size), Image.Resampling.LANCZOS)
            
            return image
        except Exception as e:
            print(f"Error generating thumbnail: {e}")
            return None
    
    def set_current_series(self, series_uid: str) -> None:
        """
        Update current series highlighting.
        
        Args:
            series_uid: Series UID to highlight
        """
        self.current_series_uid = series_uid
        for uid, thumbnail in self.thumbnails.items():
            thumbnail.set_current(uid == series_uid)
    
    def clear(self) -> None:
        """Clear all thumbnails."""
        for thumbnail in self.thumbnails.values():
            self.thumbnail_layout.removeWidget(thumbnail)
            thumbnail.deleteLater()
        self.thumbnails.clear()
        self.thumbnail_cache.clear()


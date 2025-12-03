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
from PySide6.QtCore import Qt, Signal, QSize, QPoint, QMimeData, QTimer
from PySide6.QtGui import QPixmap, QImage, QPainter, QFont, QColor, QDrag, QMouseEvent, QKeyEvent
from typing import Optional, Dict
from pydicom.dataset import Dataset
from core.dicom_processor import DICOMProcessor
from PIL import Image
import numpy as np
import time


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
        
        # Set fixed size for thumbnails (85% of 80x80 to fit smaller navigator height)
        self.setFixedSize(68, 68)
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
    
    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse click to start drag operation."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Store press position for drag detection
            self.drag_start_position = event.pos()
            # Single-click loading disabled - series can be loaded via context menu, drag-and-drop, or arrow keys
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse move to start drag operation."""
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        
        if not hasattr(self, 'drag_start_position'):
            return
        
        # Check if mouse has moved enough to start drag
        if (event.pos() - self.drag_start_position).manhattanLength() < 10:
            return  # Not enough movement
        
        # Create drag object
        drag = QDrag(self)
        mime_data = QMimeData()
        
        # Set mime data with series UID
        # Format: "series_uid:UID" (slice_index will default to 0 in drop handler)
        mime_data.setText(f"series_uid:{self.series_uid}")
        drag.setMimeData(mime_data)
        
        # Create drag pixmap (thumbnail of this series)
        if self.thumbnail_image is not None:
            # Create a small pixmap from thumbnail
            pixmap = QPixmap.fromImage(self._thumbnail_to_qimage(self.thumbnail_image))
            # Scale to reasonable drag size
            drag_pixmap = pixmap.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            drag.setPixmap(drag_pixmap)
            drag.setHotSpot(QPoint(32, 32))
        
        # Execute drag
        drag.exec(Qt.DropAction.CopyAction)
    
    def _thumbnail_to_qimage(self, pil_image) -> QImage:
        """Convert PIL Image to QImage for drag pixmap."""
        import numpy as np
        try:
            img_array = np.array(pil_image)
            if not img_array.flags['C_CONTIGUOUS']:
                img_array = np.ascontiguousarray(img_array)
            
            if pil_image.mode == 'L':
                height, width = img_array.shape
                return QImage(img_array.data, width, height, width, QImage.Format.Format_Grayscale8)
            elif pil_image.mode == 'RGB':
                height, width, channels = img_array.shape
                return QImage(img_array.data, width, height, width * 3, QImage.Format.Format_RGB888)
            else:
                rgb_image = pil_image.convert('RGB')
                img_array = np.array(rgb_image)
                if not img_array.flags['C_CONTIGUOUS']:
                    img_array = np.ascontiguousarray(img_array)
                height, width, channels = img_array.shape
                return QImage(img_array.data, width, height, width * 3, QImage.Format.Format_RGB888)
        except Exception:
            # Fallback: create empty QImage
            return QImage(64, 64, QImage.Format.Format_RGB888)
    
    def paintEvent(self, event) -> None:
        """Paint thumbnail image with series number overlay."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw thumbnail image if available
        if self.thumbnail_image is not None:
            try:
                # Validate image dimensions
                if self.thumbnail_image.width <= 0 or self.thumbnail_image.height <= 0:
                    raise ValueError("Invalid image dimensions")
                
                # Convert PIL Image to QPixmap via numpy array (more reliable than tobytes)
                # Convert PIL Image to numpy array first
                img_array = np.array(self.thumbnail_image)
                
                # Ensure array is contiguous and in correct format
                if not img_array.flags['C_CONTIGUOUS']:
                    img_array = np.ascontiguousarray(img_array)
                
                # Convert to QImage based on image mode
                if self.thumbnail_image.mode == 'L':
                    # Grayscale: shape is (height, width)
                    height, width = img_array.shape
                    qimage = QImage(img_array.data, width, height, 
                                  width, QImage.Format.Format_Grayscale8)
                elif self.thumbnail_image.mode == 'RGB':
                    # RGB: shape is (height, width, 3)
                    height, width, channels = img_array.shape
                    qimage = QImage(img_array.data, width, height, 
                                  width * 3, QImage.Format.Format_RGB888)
                else:
                    # Convert to RGB first
                    rgb_image = self.thumbnail_image.convert('RGB')
                    img_array = np.array(rgb_image)
                    if not img_array.flags['C_CONTIGUOUS']:
                        img_array = np.ascontiguousarray(img_array)
                    height, width, channels = img_array.shape
                    qimage = QImage(img_array.data, width, height, 
                                  width * 3, QImage.Format.Format_RGB888)
                
                # Validate QImage was created successfully
                if qimage.isNull():
                    raise ValueError("Failed to create QImage")
                
                pixmap = QPixmap.fromImage(qimage)
                if pixmap.isNull():
                    raise ValueError("Failed to create QPixmap")
                
                # Scale to fit thumbnail size (maintain aspect ratio)
                scaled_pixmap = pixmap.scaled(self.width() - 4, self.height() - 4,
                                             Qt.AspectRatioMode.KeepAspectRatio,
                                             Qt.TransformationMode.SmoothTransformation)
                # Center the image
                x = (self.width() - scaled_pixmap.width()) // 2
                y = (self.height() - scaled_pixmap.height()) // 2
                painter.drawPixmap(x, y, scaled_pixmap)
            except Exception as e:
                # Draw placeholder if image conversion fails
                print(f"Error painting thumbnail: {e}")
                painter.fillRect(self.rect(), QColor(128, 128, 128))
                painter.setPen(QColor(255, 255, 255))
                painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Error")
        else:
            # Draw placeholder if no image
            # Check if this might be a compression error by checking if thumbnail is compression error marker
            if (self.thumbnail_image is not None and 
                hasattr(self.thumbnail_image, 'size') and 
                self.thumbnail_image.size == (57, 57)):
                # Might be compression error thumbnail - use different color
                painter.fillRect(self.rect(), QColor(200, 150, 150))  # Light red
                painter.setPen(QColor(255, 255, 255))
                painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "COMP")
            else:
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
    series_navigation_requested = Signal(int)  # Emitted when arrow keys are pressed (-1 for prev, 1 for next)
    
    def __init__(self, dicom_processor: DICOMProcessor, parent=None):
        """
        Initialize series navigator.
        
        Args:
            dicom_processor: DICOMProcessor instance for thumbnail generation
            parent: Parent widget
        """
        super().__init__(parent)
        self.setObjectName("series_navigator")
        self.dicom_processor = dicom_processor
        self.current_study_uid = ""
        self.current_series_uid = ""
        self.thumbnails: Dict[str, SeriesThumbnail] = {}
        
        # Thumbnail cache: (study_uid, series_uid) -> PIL Image
        self.thumbnail_cache: Dict[tuple, Image.Image] = {}
        
        # Enable keyboard focus so we can receive key events
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        
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
        scroll_area.setObjectName("series_navigator_scroll_area")
        
        # Container widget for thumbnails
        self.thumbnail_container = QWidget()
        self.thumbnail_container.setObjectName("series_navigator_container")
        self.thumbnail_layout = QHBoxLayout(self.thumbnail_container)
        self.thumbnail_layout.setContentsMargins(5, 5, 5, 5)
        self.thumbnail_layout.setSpacing(5)
        self.thumbnail_layout.addStretch()  # Add stretch at end
        
        scroll_area.setWidget(self.thumbnail_container)
        layout.addWidget(scroll_area)
        
        # Set fixed height for navigator (85% of 93px)
        self.setFixedHeight(79)
    
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
            # Check if this is a compressed file that can't be decoded
            if hasattr(dataset, 'file_meta') and hasattr(dataset.file_meta, 'TransferSyntaxUID'):
                transfer_syntax = str(dataset.file_meta.TransferSyntaxUID)
                # Check for JPEG compression transfer syntaxes that require pylibjpeg
                jpeg_transfer_syntaxes = [
                    '1.2.840.10008.1.2.4.50',  # JPEG Baseline (Process 1)
                    '1.2.840.10008.1.2.4.51',  # JPEG Extended (Process 2 & 4)
                    '1.2.840.10008.1.2.4.57',  # JPEG Lossless, Non-Hierarchical (Process 14)
                    '1.2.840.10008.1.2.4.70',  # JPEG Lossless, Non-Hierarchical (Process 14 [Selection Value 1])
                    '1.2.840.10008.1.2.4.80',  # JPEG-LS Lossless Image Compression
                    '1.2.840.10008.1.2.4.81',  # JPEG-LS Lossy (Near-Lossless) Image Compression
                    '1.2.840.10008.1.2.4.90',  # JPEG 2000 Image Compression (Lossless Only)
                    '1.2.840.10008.1.2.4.91',  # JPEG 2000 Image Compression
                ]
                if transfer_syntax in jpeg_transfer_syntaxes:
                    # Try to check if pixel array can be accessed (this will fail if pylibjpeg not installed)
                    try:
                        # Just check if we can access pixel_array property (don't actually load it)
                        _ = dataset.pixel_array
                    except Exception as e:
                        error_msg = str(e)
                        if ("pylibjpeg" in error_msg.lower() or 
                            "missing required dependencies" in error_msg.lower() or
                            "unable to convert" in error_msg.lower()):
                            # This is a compressed file that can't be decoded
                            # Return a special marker image that will show compression error
                            return self._create_compression_error_thumbnail()
            
            # Convert dataset to image
            image = self.dicom_processor.dataset_to_image(dataset, apply_rescale=False)
            if image is None:
                return None
            
            # Resize to thumbnail size (maintain aspect ratio)
            thumbnail_size = 57  # Target size for thumbnail (85% of 67px to fit smaller navigator height)
            image.thumbnail((thumbnail_size, thumbnail_size), Image.Resampling.LANCZOS)
            
            return image
        except Exception as e:
            error_msg = str(e)
            # Check if this is a compression error
            if ("pylibjpeg" in error_msg.lower() or 
                "missing required dependencies" in error_msg.lower() or
                "unable to convert" in error_msg.lower()):
                return self._create_compression_error_thumbnail()
            print(f"Error generating thumbnail: {e}")
            return None
    
    def _create_compression_error_thumbnail(self) -> Image.Image:
        """
        Create a thumbnail placeholder indicating compression error.
        
        Returns:
            PIL Image with compression error indicator
        """
        from PIL import ImageDraw, ImageFont
        # Create a small image with error indicator
        size = 57
        img = Image.new('RGB', (size, size), color=(200, 150, 150))  # Light red background
        draw = ImageDraw.Draw(img)
        
        # Try to use a font, fallback to default if not available
        try:
            font = ImageFont.truetype("arial.ttf", 8)
        except:
            font = ImageFont.load_default()
        
        # Draw "COMP" text to indicate compression error
        text = "COMP"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (size - text_width) // 2
        y = (size - text_height) // 2
        draw.text((x, y), text, fill=(255, 255, 255), font=font)
        
        return img
    
    def set_current_series(self, series_uid: str) -> None:
        """
        Update current series highlighting.
        
        Args:
            series_uid: Series UID to highlight
        """
        self.current_series_uid = series_uid
        for uid, thumbnail in self.thumbnails.items():
            thumbnail.set_current(uid == series_uid)
    
    def regenerate_series_thumbnail(self, study_uid: str, series_uid: str, 
                                    dataset: Dataset, window_center: float, 
                                    window_width: float, apply_rescale: bool) -> None:
        """
        Regenerate thumbnail for a specific series with explicit window/level values.
        
        This is used to update thumbnails when window/level values are corrected
        after initial generation.
        
        Args:
            study_uid: Study instance UID
            series_uid: Series instance UID
            dataset: DICOM dataset (first slice of series)
            window_center: Window center value
            window_width: Window width value
            apply_rescale: Whether to apply rescale to the thumbnail
        """
        # Invalidate cached thumbnail for this series
        cache_key = (study_uid, series_uid)
        if cache_key in self.thumbnail_cache:
            del self.thumbnail_cache[cache_key]
        
        # Generate new thumbnail with explicit window/level
        try:
            # Convert dataset to image with explicit window/level
            image = self.dicom_processor.dataset_to_image(
                dataset, 
                window_center=window_center,
                window_width=window_width,
                apply_rescale=apply_rescale
            )
            if image is None:
                return
            
            # Resize to thumbnail size (maintain aspect ratio)
            thumbnail_size = 57  # Target size for thumbnail
            image.thumbnail((thumbnail_size, thumbnail_size), Image.Resampling.LANCZOS)
            
            # Cache the new thumbnail
            self.thumbnail_cache[cache_key] = image
            
            # Update the thumbnail widget if it exists
            if series_uid in self.thumbnails:
                thumbnail_widget = self.thumbnails[series_uid]
                thumbnail_widget.thumbnail_image = image
                thumbnail_widget.update()  # Trigger repaint
                # print(f"[DEBUG-WL] Regenerated series navigator thumbnail for series {series_uid[:20]}...")
        except Exception as e:
            print(f"Error regenerating thumbnail: {e}")
    
    def clear(self) -> None:
        """Clear all thumbnails."""
        for thumbnail in self.thumbnails.values():
            self.thumbnail_layout.removeWidget(thumbnail)
            thumbnail.deleteLater()
        self.thumbnails.clear()
        self.thumbnail_cache.clear()
    
    def keyPressEvent(self, event: QKeyEvent) -> None:
        """
        Handle key press events for series navigation.
        
        Args:
            event: Key event
        """
        # Ignore key repeat events to prevent rapid navigation
        if event.isAutoRepeat():
            event.accept()
            return
        
        if event.key() == Qt.Key.Key_Left:
            # Left arrow: previous series
            timestamp = time.time()
            print(f"[DEBUG-NAV] [{timestamp:.6f}] SeriesNavigator.keyPressEvent: LEFT arrow pressed, hasFocus={self.hasFocus()}")
            print(f"[DEBUG-NAV] [{timestamp:.6f}] SeriesNavigator: Emitting series_navigation_requested(-1)")
            self.series_navigation_requested.emit(-1)
            event.accept()
        elif event.key() == Qt.Key.Key_Right:
            # Right arrow: next series
            timestamp = time.time()
            print(f"[DEBUG-NAV] [{timestamp:.6f}] SeriesNavigator.keyPressEvent: RIGHT arrow pressed, hasFocus={self.hasFocus()}")
            print(f"[DEBUG-NAV] [{timestamp:.6f}] SeriesNavigator: Emitting series_navigation_requested(1)")
            self.series_navigation_requested.emit(1)
            event.accept()
        else:
            super().keyPressEvent(event)
    
    
    def mousePressEvent(self, event: QMouseEvent) -> None:
        """
        Handle mouse press to set focus so keyboard events work.
        
        Args:
            event: Mouse event
        """
        # Set focus when clicked so keyboard events are received
        self.setFocus()
        super().mousePressEvent(event)


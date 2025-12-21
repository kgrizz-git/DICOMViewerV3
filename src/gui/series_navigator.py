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
                                QLabel, QFrame, QStyleOption)
from PySide6.QtCore import Qt, Signal, QSize, QPoint, QMimeData, QTimer
from PySide6.QtGui import QPixmap, QImage, QPainter, QFont, QColor, QDrag, QMouseEvent, QKeyEvent, QPalette
from typing import Optional, Dict, List
from pydicom.dataset import Dataset
from core.dicom_processor import DICOMProcessor
from PIL import Image
import numpy as np
import time


class StudyDivider(QFrame):
    """
    Visual separator widget between studies in the series navigator.
    
    Displays a thin vertical line to separate series from different studies.
    Spans both the label row and thumbnail row.
    """
    
    def __init__(self, parent=None):
        """
        Initialize study divider.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        # Set fixed width, height will span both rows (label + thumbnail)
        # Height: label row (18px) + thumbnail row (68px) + border (2px) + margins = 95px
        # Narrower divider: 2px instead of 3px, lighter color: #666666 instead of #888888
        self.setFixedSize(2, 95)
        self.setStyleSheet("QFrame { background-color: #666666; border: none; }")


class StudyLabel(QFrame):
    """
    Study label widget displaying study description or UID.
    
    Shows StudyDescription if available, otherwise displays truncated StudyInstanceUID.
    Thin row above thumbnails, left-aligned, spans full width of study's thumbnails.
    """
    
    def __init__(self, study_label_text: str, parent=None):
        """
        Initialize study label.
        
        Args:
            study_label_text: Text to display (study description or UID)
            parent: Parent widget
        """
        super().__init__(parent)
        # Set fixed height for thin row, width will be set dynamically
        self.setFixedHeight(18)
        self.setMinimumWidth(68)  # Minimum width of one thumbnail
        # No frame style - we don't want any borders
        self.setFrameStyle(QFrame.Shape.NoFrame)
        # Background color is set via global stylesheet in main_window.py for theme awareness
        # Dark theme: #2a2a2a, Light theme: #e0e0e0
        # No borders
        self.setStyleSheet(
            "QFrame { "
            "border: none; "
            "border-radius: 0px; "
            "}"
        )
        
        # Create label for text
        self.label = QLabel(study_label_text, self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.label.setWordWrap(False)
        # Text color will adapt to theme via parent stylesheet
        self.label.setStyleSheet(
            "QLabel { "
            "background-color: transparent; "
            "font-weight: bold; "
            "font-size: 9pt; "
            "padding: 2px 5px; "
            "}"
        )
        
        # Layout for label
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.label)
    
    def set_text(self, text: str) -> None:
        """
        Update the label text.
        
        Args:
            text: New text to display
        """
        self.label.setText(text)
    
    def set_width(self, width: int) -> None:
        """
        Set the width of the label to span thumbnails.
        
        Args:
            width: Width in pixels
        """
        self.setFixedWidth(width)


class SeriesThumbnail(QFrame):
    """
    Individual thumbnail widget for a series.
    
    Displays first slice image with series number overlaid.
    """
    
    clicked = Signal(str)  # Emitted with series_uid when clicked
    show_file_requested = Signal(str, str)  # Emitted with (study_uid, series_uid) when "Show file" is requested
    about_this_file_requested = Signal(str, str)  # Emitted with (study_uid, series_uid) when "About This File" is requested
    
    def __init__(self, series_uid: str, series_number: int, thumbnail_image: Optional[Image.Image], study_uid: str = "", parent=None):
        """
        Initialize series thumbnail.
        
        Args:
            series_uid: Series instance UID
            series_number: Series number to display
            thumbnail_image: PIL Image for thumbnail (or None)
            study_uid: Study Instance UID (required for file path lookup)
            parent: Parent widget
        """
        super().__init__(parent)
        self.series_uid = series_uid
        self.series_number = series_number
        self.thumbnail_image = thumbnail_image
        self.study_uid = study_uid
        self.is_current = False
        
        # Set fixed size for thumbnails (85% of 80x80 to fit smaller navigator height)
        self.setFixedSize(68, 68)
        self.setFrameStyle(QFrame.Shape.Box)
        self.setLineWidth(1)
        # Darker border: #444444 instead of #555555
        self.setStyleSheet("QFrame { border: 1px solid #444444; }")
        
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
            self.setStyleSheet("QFrame { border: 2px solid #00aaff; background-color: rgba(0, 170, 255, 0.1); }")
        else:
            # Darker border: #444444 instead of #555555
            self.setStyleSheet("QFrame { border: 1px solid #444444; }")
        self.update()
    
    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press and start possible drag operation."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Store press position for drag detection and reset drag flag
            self.drag_start_position = event.pos()
            self._drag_started = False
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
        
        # We are starting a drag, so later mouseRelease should not count as a click.
        self._drag_started = True

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

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Emit clicked only if this was not part of a drag."""
        if event.button() == Qt.MouseButton.LeftButton:
            if not getattr(self, "_drag_started", False):
                self.clicked.emit(self.series_uid)
        super().mouseReleaseEvent(event)
    
    def contextMenuEvent(self, event) -> None:
        """
        Handle right-click context menu event.
        
        Args:
            event: Context menu event
        """
        from PySide6.QtWidgets import QMenu
        
        # Only show context menu if we have study_uid (required for file path lookup)
        if not self.study_uid:
            return
        
        context_menu = QMenu(self)
        
        # Add "About This File" action
        about_this_file_action = context_menu.addAction("About This File...")
        about_this_file_action.triggered.connect(
            lambda: self.about_this_file_requested.emit(self.study_uid, self.series_uid)
        )
        
        # Add "Show File in File Explorer" action
        show_file_action = context_menu.addAction("Show File in File Explorer")
        show_file_action.triggered.connect(
            lambda: self.show_file_requested.emit(self.study_uid, self.series_uid)
        )
        
        # Show context menu at cursor position
        context_menu.exec(event.globalPos())
    
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
    show_file_requested = Signal(str, str)  # Emitted with (study_uid, series_uid) when "Show file" is requested
    about_this_file_requested = Signal(str, str)  # Emitted with (study_uid, series_uid) when "About This File" is requested
    
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
        
        # Store study labels and dividers for cleanup
        self.study_labels: List[StudyLabel] = []
        self.study_dividers: List[StudyDivider] = []
        
        # Thumbnail cache: (study_uid, series_uid) -> PIL Image
        self.thumbnail_cache: Dict[tuple, Image.Image] = {}
        
        # Enable keyboard focus so we can receive key events
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        
        self._create_ui()
    
    def _create_ui(self) -> None:
        """Create the UI layout with two-row structure (label row + thumbnail row)."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create scroll area for horizontal scrolling
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setObjectName("series_navigator_scroll_area")
        
        # Main container widget for study sections
        self.main_container = QWidget()
        self.main_container.setObjectName("series_navigator_container")
        self.main_layout = QHBoxLayout(self.main_container)
        # Reduce margins to ensure thumbnails aren't cut off
        # Top margin for spacing, left/right for padding, bottom minimal to prevent clipping
        self.main_layout.setContentsMargins(5, 5, 5, 1)
        self.main_layout.setSpacing(0)  # No spacing, dividers provide separation
        self.main_layout.addStretch()  # Add stretch at end
        
        scroll_area.setWidget(self.main_container)
        layout.addWidget(scroll_area)
        
        # Set fixed height for navigator: 
        # Top margin (5px) + label row (18px) + thumbnail row (68px) + border (2px) + bottom margin (1px) = 94px
        # Round up to 95px for safety
        self.setFixedHeight(95)
    
    def _get_study_label(self, dataset: Dataset) -> str:
        """
        Extract study label from dataset.
        
        Returns StudyDescription if available, otherwise returns truncated StudyInstanceUID.
        
        Args:
            dataset: DICOM dataset to extract study information from
            
        Returns:
            Study label string (description or truncated UID)
        """
        # Try to get StudyDescription first
        study_desc = getattr(dataset, 'StudyDescription', None)
        if study_desc and str(study_desc).strip():
            # Truncate if too long (max 30 chars)
            desc_str = str(study_desc).strip()
            if len(desc_str) > 30:
                return desc_str[:27] + "..."
            return desc_str
        
        # Fallback to StudyInstanceUID (truncated)
        study_uid = getattr(dataset, 'StudyInstanceUID', None)
        if study_uid:
            uid_str = str(study_uid)
            if len(uid_str) > 30:
                return uid_str[:27] + "..."
            return uid_str
        
        # Final fallback
        return "Unknown Study"
    
    def update_series_list(self, studies: Dict, current_study_uid: str, current_series_uid: str) -> None:
        """
        Update the series list with thumbnails from all studies.
        
        Displays all series from all studies in a two-row layout:
        - Top row: Study labels spanning full width of their thumbnails
        - Bottom row: Series thumbnails
        - Vertical dividers span both rows to separate studies.
        
        Args:
            studies: Dictionary of studies {study_uid: {series_uid: [datasets]}}
            current_study_uid: Current study UID
            current_series_uid: Current series UID
        """
        self.current_study_uid = current_study_uid
        self.current_series_uid = current_series_uid
        
        # Clear existing widgets from main layout
        # Get all widgets from main layout and remove them
        while self.main_layout.count() > 1:  # Keep the stretch at the end
            item = self.main_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Clear tracking lists
        self.thumbnails.clear()
        self.study_labels.clear()
        self.study_dividers.clear()
        
        if not studies:
            return
        
        # Iterate through all studies and create study sections
        first_study = True
        for study_uid, study_series in studies.items():
            # Skip studies with no series
            if not study_series:
                continue
            
            # Add divider before study (except for first study)
            if not first_study:
                divider = StudyDivider(self.main_container)
                self.study_dividers.append(divider)
                self.main_layout.insertWidget(self.main_layout.count() - 1, divider)
            
            # Get study label from first dataset of first series
            study_label_text = "Unknown Study"
            first_dataset = None
            
            # Find first series with datasets
            for series_uid, datasets in study_series.items():
                if datasets:
                    first_dataset = datasets[0]
                    break
            
            if first_dataset:
                study_label_text = self._get_study_label(first_dataset)
            
            # Build list of (series_number, series_uid, first_dataset) for this study
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
            
            # Calculate width for this study section
            # Width = (number of thumbnails × 68px) + (spacing between thumbnails × (num - 1))
            num_thumbnails = len(series_list)
            thumbnail_width = 68
            thumbnail_spacing = 5
            if num_thumbnails > 0:
                section_width = (num_thumbnails * thumbnail_width) + ((num_thumbnails - 1) * thumbnail_spacing)
            else:
                section_width = thumbnail_width  # Minimum width
            
            # Create study section container
            # The global stylesheet has: QWidget[objectName="series_navigator_container"] > QWidget
            # This should apply to child widgets, but we need WA_StyledBackground for it to work
            study_section = QWidget(self.main_container)
            # Enable styled background so the global stylesheet rule applies
            study_section.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            # Don't set local stylesheet - let the global one handle it
            # The global stylesheet rule should match: QWidget[objectName="series_navigator_container"] > QWidget
            
            section_layout = QVBoxLayout(study_section)
            section_layout.setContentsMargins(0, 0, 0, 0)
            section_layout.setSpacing(0)
            
            # Add study label at top (spans full width of section)
            study_label = StudyLabel(study_label_text, study_section)
            study_label.set_width(section_width)
            self.study_labels.append(study_label)
            section_layout.addWidget(study_label)
            
            # Create thumbnails container
            # The global stylesheet should apply here too via the child selector
            thumbnails_container = QWidget(study_section)
            # Enable styled background so the global stylesheet rule applies
            thumbnails_container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            # Don't set local stylesheet - let the global one handle it
            thumbnails_layout = QHBoxLayout(thumbnails_container)
            thumbnails_layout.setContentsMargins(0, 0, 0, 0)
            thumbnails_layout.setSpacing(thumbnail_spacing)
            
            # Create thumbnails for this study
            for series_num, series_uid, first_dataset in series_list:
                # Check cache first
                cache_key = (study_uid, series_uid)
                if cache_key in self.thumbnail_cache:
                    thumbnail_image = self.thumbnail_cache[cache_key]
                else:
                    # Generate thumbnail
                    thumbnail_image = self._generate_thumbnail(first_dataset)
                    if thumbnail_image:
                        self.thumbnail_cache[cache_key] = thumbnail_image
                
                # Create thumbnail widget
                thumbnail = SeriesThumbnail(series_uid, series_num, thumbnail_image, study_uid, thumbnails_container)
                thumbnail.clicked.connect(self.series_selected.emit)
                # Connect show_file_requested signal to SeriesNavigator signal
                thumbnail.show_file_requested.connect(self.show_file_requested.emit)
                # Connect about_this_file_requested signal to SeriesNavigator signal
                thumbnail.about_this_file_requested.connect(self.about_this_file_requested.emit)
                # Highlight if this is the current series AND current study
                is_current = (series_uid == current_series_uid and study_uid == current_study_uid)
                thumbnail.set_current(is_current)
                
                # Store thumbnail with composite key (study_uid, series_uid) for lookup
                composite_key = f"{study_uid}:{series_uid}"
                self.thumbnails[composite_key] = thumbnail
                thumbnails_layout.addWidget(thumbnail)
            
            # Add thumbnails container to section
            section_layout.addWidget(thumbnails_container)
            
            # Add study section to main layout
            self.main_layout.insertWidget(self.main_layout.count() - 1, study_section)
            
            first_study = False
    
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
    
    def set_current_series(self, series_uid: str, study_uid: Optional[str] = None) -> None:
        """
        Update current series highlighting.
        
        Args:
            series_uid: Series UID to highlight
            study_uid: Optional study UID. If provided, only highlights if both match.
                      If None, uses current_study_uid.
        """
        self.current_series_uid = series_uid
        if study_uid is not None:
            self.current_study_uid = study_uid
        
        # Update highlighting for all thumbnails
        for composite_key, thumbnail in self.thumbnails.items():
            # Composite key format: "study_uid:series_uid"
            if ":" in composite_key:
                stored_study_uid, stored_series_uid = composite_key.split(":", 1)
                is_current = (stored_series_uid == series_uid and 
                            stored_study_uid == self.current_study_uid)
            else:
                # Fallback for old format (shouldn't happen with new code)
                is_current = (composite_key == series_uid)
            thumbnail.set_current(is_current)
    
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
            
            # Update the thumbnail widget if it exists (use composite key)
            composite_key = f"{study_uid}:{series_uid}"
            if composite_key in self.thumbnails:
                thumbnail_widget = self.thumbnails[composite_key]
                thumbnail_widget.thumbnail_image = image
                thumbnail_widget.update()  # Trigger repaint
                # print(f"[DEBUG-WL] Regenerated series navigator thumbnail for series {series_uid[:20]}...")
        except Exception as e:
            print(f"Error regenerating thumbnail: {e}")
    
    def clear(self) -> None:
        """Clear all thumbnails, labels, dividers, and study sections."""
        # Clear all widgets from main layout (except stretch)
        while self.main_layout.count() > 1:  # Keep the stretch at the end
            item = self.main_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Clear tracking lists
        self.thumbnails.clear()
        self.study_labels.clear()
        self.study_dividers.clear()
        
        # Clear cache
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
        
        # Check if any text annotation is being edited - if so, don't process arrow keys for navigation
        if event.key() == Qt.Key.Key_Left or event.key() == Qt.Key.Key_Right:
            # Check if the focused widget is a TextAnnotationItem or if any text annotation is being edited
            from PySide6.QtWidgets import QApplication
            from tools.text_annotation_tool import TextAnnotationItem, is_any_text_annotation_editing
            
            focused_widget = QApplication.focusWidget()
            # Check if focused widget is a TextAnnotationItem that's being edited
            if isinstance(focused_widget, TextAnnotationItem) and getattr(focused_widget, '_editing', False):
                # Let the text editor handle arrow keys for cursor movement
                super().keyPressEvent(event)
                return
            
            # Also check the scene if we can find it
            scene = None
            parent = self.parent()
            while parent:
                if hasattr(parent, 'scene'):
                    scene = parent.scene
                    break
                elif hasattr(parent, 'image_viewer') and hasattr(parent.image_viewer, 'scene'):
                    scene = parent.image_viewer.scene
                    break
                parent = parent.parent()
            
            if scene is not None and is_any_text_annotation_editing(scene):
                # Let the text editor handle arrow keys for cursor movement
                super().keyPressEvent(event)
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


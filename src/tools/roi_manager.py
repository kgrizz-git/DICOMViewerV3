"""
ROI Manager

This module handles drawing and management of Regions of Interest (ROIs)
including elliptical and rectangular shapes, with statistics calculation.

Inputs:
    - User mouse interactions for drawing
    - ROI shape type (ellipse, rectangle)
    - Pixel array data for statistics
    
Outputs:
    - ROI graphics items
    - ROI statistics (mean, std dev, etc.)
    
Requirements:
    - PySide6 for graphics items
    - numpy for statistics calculations
"""

from PySide6.QtWidgets import QGraphicsEllipseItem, QGraphicsRectItem, QGraphicsItem
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPen, QColor
from typing import List, Optional, Tuple, Dict
import numpy as np
from PIL import Image


class ROIItem:
    """
    Base class for ROI items.
    """
    
    def __init__(self, shape_type: str, item: QGraphicsEllipseItem | QGraphicsRectItem):
        """
        Initialize ROI item.
        
        Args:
            shape_type: "ellipse" or "rectangle"
            item: Graphics item
        """
        self.shape_type = shape_type
        self.item = item
        self.id = id(self)
        
        # Set pen style - thinner line (1px)
        pen = QPen(QColor(255, 0, 0), 1)  # Red, 1px width
        pen.setStyle(Qt.PenStyle.DashLine)
        self.item.setPen(pen)
        self.item.setBrush(Qt.BrushStyle.NoBrush)
        
        # Make item selectable and movable
        self.item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        
        # Store callback for when ROI is moved
        self.on_moved_callback = None
    
    def get_bounds(self) -> QRectF:
        """
        Get bounding rectangle of ROI.
        
        Returns:
            Bounding rectangle
        """
        return self.item.rect()
    
    def get_mask(self, width: int, height: int) -> np.ndarray:
        """
        Get binary mask for ROI.
        
        Args:
            width: Image width
            height: Image height
            
        Returns:
            Binary mask array
        """
        mask = np.zeros((height, width), dtype=bool)
        bounds = self.get_bounds()
        
        if self.shape_type == "rectangle":
            x1 = int(max(0, bounds.left()))
            y1 = int(max(0, bounds.top()))
            x2 = int(min(width, bounds.right()))
            y2 = int(min(height, bounds.bottom()))
            mask[y1:y2, x1:x2] = True
        elif self.shape_type == "ellipse":
            # Create ellipse mask
            center_x = bounds.center().x()
            center_y = bounds.center().y()
            radius_x = bounds.width() / 2.0
            radius_y = bounds.height() / 2.0
            
            y, x = np.ogrid[:height, :width]
            ellipse_mask = ((x - center_x) / radius_x) ** 2 + ((y - center_y) / radius_y) ** 2 <= 1
            mask = ellipse_mask
        
        return mask


class ROIManager:
    """
    Manages ROIs on images.
    
    Features:
    - Draw elliptical and rectangular ROIs
    - Calculate statistics within ROIs
    - Clear ROIs from slice or dataset
    """
    
    def __init__(self):
        """Initialize the ROI manager."""
        # Key format: (StudyInstanceUID, SeriesInstanceUID, instance_identifier)
        # instance_identifier can be InstanceNumber from DICOM or slice_index as fallback
        self.rois: Dict[Tuple[str, str, int], List[ROIItem]] = {}
        self.current_study_uid = ""
        self.current_series_uid = ""
        self.current_instance_identifier = 0
        self.drawing = False
        self.drawing_start_pos: Optional[QPointF] = None
        self.current_roi_item: Optional[ROIItem] = None
        self.current_shape_type = "rectangle"  # "rectangle" or "ellipse"
        self.selected_roi: Optional[ROIItem] = None  # Currently selected ROI
    
    def set_current_slice(self, study_uid: str, series_uid: str, instance_identifier: int) -> None:
        """
        Set the current slice using composite key.
        
        Args:
            study_uid: StudyInstanceUID
            series_uid: SeriesInstanceUID
            instance_identifier: InstanceNumber from DICOM or slice_index as fallback
        """
        self.current_study_uid = study_uid
        self.current_series_uid = series_uid
        self.current_instance_identifier = instance_identifier
        key = (study_uid, series_uid, instance_identifier)
        if key not in self.rois:
            self.rois[key] = []
    
    def start_drawing(self, pos: QPointF, shape_type: str = "rectangle") -> None:
        """
        Start drawing a new ROI.
        
        Args:
            pos: Starting position
            shape_type: "rectangle" or "ellipse"
        """
        self.drawing = True
        self.drawing_start_pos = pos
        self.current_shape_type = shape_type
        self.current_roi_item = None
    
    def update_drawing(self, pos: QPointF, scene) -> None:
        """
        Update ROI while drawing.
        
        Args:
            pos: Current mouse position
            scene: QGraphicsScene to add items to
        """
        if not self.drawing or self.drawing_start_pos is None:
            return
        
        # Calculate bounds
        x1 = min(self.drawing_start_pos.x(), pos.x())
        y1 = min(self.drawing_start_pos.y(), pos.y())
        x2 = max(self.drawing_start_pos.x(), pos.x())
        y2 = max(self.drawing_start_pos.y(), pos.y())
        
        rect = QRectF(x1, y1, x2 - x1, y2 - y1)
        
        # Remove old item if exists
        if self.current_roi_item is not None:
            # Only remove if item actually belongs to this scene
            if self.current_roi_item.item.scene() == scene:
                scene.removeItem(self.current_roi_item.item)
        
        # Create new item
        if self.current_shape_type == "rectangle":
            item = QGraphicsRectItem(rect)
        else:  # ellipse
            item = QGraphicsEllipseItem(rect)
        
        self.current_roi_item = ROIItem(self.current_shape_type, item)
        # Don't make drawing ROI selectable/movable yet (will be enabled when finished)
        self.current_roi_item.item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.current_roi_item.item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        scene.addItem(item)
    
    def finish_drawing(self) -> Optional[ROIItem]:
        """
        Finish drawing ROI.
        
        Returns:
            Created ROI item or None
        """
        if not self.drawing or self.current_roi_item is None:
            self.drawing = False
            return None
        
        # Add to current slice using composite key
        key = (self.current_study_uid, self.current_series_uid, self.current_instance_identifier)
        if key not in self.rois:
            self.rois[key] = []
        
        self.rois[key].append(self.current_roi_item)
        
        # Enable selectable/movable now that drawing is finished
        self.current_roi_item.item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.current_roi_item.item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        
        # Select the newly created ROI
        self.select_roi(self.current_roi_item)
        
        self.drawing = False
        self.drawing_start_pos = None
        roi = self.current_roi_item
        self.current_roi_item = None
        
        return roi
    
    def select_roi(self, roi: Optional[ROIItem]) -> None:
        """
        Select a ROI.
        
        Args:
            roi: ROI item to select, or None to deselect
        """
        # Deselect previous ROI
        if self.selected_roi is not None:
            self.selected_roi.item.setSelected(False)
        
        # Select new ROI
        self.selected_roi = roi
        if roi is not None:
            roi.item.setSelected(True)
    
    def get_selected_roi(self) -> Optional[ROIItem]:
        """
        Get currently selected ROI.
        
        Returns:
            Selected ROI item or None
        """
        return self.selected_roi
    
    def find_roi_by_item(self, item) -> Optional[ROIItem]:
        """
        Find ROI item by graphics item.
        
        Args:
            item: QGraphicsItem
            
        Returns:
            ROIItem or None
        """
        for roi_list in self.rois.values():
            for roi in roi_list:
                if roi.item == item:
                    return roi
        return None
    
    def delete_roi(self, roi: ROIItem, scene) -> bool:
        """
        Delete a ROI.
        
        Args:
            roi: ROI item to delete
            scene: QGraphicsScene to remove item from
            
        Returns:
            True if deleted, False otherwise
        """
        # Find and remove from rois dict
        for roi_list in self.rois.values():
            if roi in roi_list:
                roi_list.remove(roi)
                # Only remove if item actually belongs to this scene
                if roi.item.scene() == scene:
                    scene.removeItem(roi.item)
                
                # Deselect if this was the selected ROI
                if self.selected_roi == roi:
                    self.selected_roi = None
                
                return True
        return False
    
    def get_rois_for_slice(self, study_uid: str, series_uid: str, instance_identifier: int) -> List[ROIItem]:
        """
        Get all ROIs for a slice using composite key.
        
        Args:
            study_uid: StudyInstanceUID
            series_uid: SeriesInstanceUID
            instance_identifier: InstanceNumber from DICOM or slice_index as fallback
            
        Returns:
            List of ROI items
        """
        key = (study_uid, series_uid, instance_identifier)
        return self.rois.get(key, [])
    
    def clear_slice_rois(self, study_uid: str, series_uid: str, instance_identifier: int, scene) -> None:
        """
        Clear all ROIs from a slice using composite key.
        
        Args:
            study_uid: StudyInstanceUID
            series_uid: SeriesInstanceUID
            instance_identifier: InstanceNumber from DICOM or slice_index as fallback
            scene: QGraphicsScene to remove items from
        """
        key = (study_uid, series_uid, instance_identifier)
        if key in self.rois:
            for roi in self.rois[key]:
                # Remove item from scene if it exists
                if roi.item and scene:
                    scene.removeItem(roi.item)
            del self.rois[key]
    
    def clear_all_rois(self, scene) -> None:
        """
        Clear all ROIs from all slices.
        
        Args:
            scene: QGraphicsScene to remove items from
        """
        for slice_index, roi_list in self.rois.items():
            for roi in roi_list:
                # Only remove if item actually belongs to this scene
                if roi.item.scene() == scene:
                    scene.removeItem(roi.item)
        self.rois.clear()
    
    def calculate_statistics(self, roi: ROIItem, pixel_array: np.ndarray, 
                            rescale_slope: Optional[float] = None,
                            rescale_intercept: Optional[float] = None,
                            pixel_spacing: Optional[Tuple[float, float]] = None) -> Dict[str, float]:
        """
        Calculate statistics for an ROI.
        
        Args:
            roi: ROI item
            pixel_array: Image pixel array
            rescale_slope: Optional rescale slope to apply to pixel values
            rescale_intercept: Optional rescale intercept to apply to pixel values
            pixel_spacing: Optional pixel spacing tuple (row_spacing, col_spacing) in mm for area calculation
            
        Returns:
            Dictionary with statistics (mean, std, min, max, count, area_pixels, area_mm2)
        """
        height, width = pixel_array.shape[:2]
        
        # Get ROI bounds in scene coordinates
        bounds = roi.get_bounds()
        
        # Convert scene coordinates to pixel coordinates
        # Note: This assumes 1:1 mapping - may need adjustment based on image scaling
        x1 = int(max(0, bounds.left()))
        y1 = int(max(0, bounds.top()))
        x2 = int(min(width, bounds.right()))
        y2 = int(min(height, bounds.bottom()))
        
        if x2 <= x1 or y2 <= y1:
            return {
                "mean": 0.0,
                "std": 0.0,
                "min": 0.0,
                "max": 0.0,
                "count": 0,
                "area_pixels": 0.0,
                "area_mm2": None
            }
        
        # Get mask for ROI shape
        mask = roi.get_mask(width, height)
        
        # Calculate area in pixels
        area_pixels = float(np.sum(mask))
        
        # Calculate area in mm² if pixel spacing is available
        area_mm2 = None
        if pixel_spacing is not None and len(pixel_spacing) >= 2:
            row_spacing = pixel_spacing[0]  # mm per pixel in row direction
            col_spacing = pixel_spacing[1]  # mm per pixel in column direction
            # Area in mm² = area in pixels * (row_spacing * col_spacing)
            area_mm2 = area_pixels * row_spacing * col_spacing
        
        # Get pixels within ROI
        roi_pixels = pixel_array[mask]
        
        if len(roi_pixels) == 0:
            return {
                "mean": 0.0,
                "std": 0.0,
                "min": 0.0,
                "max": 0.0,
                "count": 0,
                "area_pixels": area_pixels,
                "area_mm2": area_mm2
            }
        
        # Apply rescale if parameters provided
        if rescale_slope is not None and rescale_intercept is not None:
            roi_pixels = roi_pixels.astype(np.float32) * float(rescale_slope) + float(rescale_intercept)
        
        return {
            "mean": float(np.mean(roi_pixels)),
            "std": float(np.std(roi_pixels)),
            "min": float(np.min(roi_pixels)),
            "max": float(np.max(roi_pixels)),
            "count": int(len(roi_pixels)),
            "area_pixels": area_pixels,
            "area_mm2": area_mm2
        }


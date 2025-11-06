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

from PySide6.QtWidgets import QGraphicsEllipseItem, QGraphicsRectItem
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
        
        # Set pen style
        pen = QPen(QColor(255, 0, 0), 2)  # Red, 2px width
        pen.setStyle(Qt.PenStyle.DashLine)
        self.item.setPen(pen)
        self.item.setBrush(Qt.BrushStyle.NoBrush)
    
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
        self.rois: Dict[int, List[ROIItem]] = {}  # slice_index -> list of ROIs
        self.current_slice_index = 0
        self.drawing = False
        self.drawing_start_pos: Optional[QPointF] = None
        self.current_roi_item: Optional[ROIItem] = None
        self.current_shape_type = "rectangle"  # "rectangle" or "ellipse"
    
    def set_current_slice(self, slice_index: int) -> None:
        """
        Set the current slice index.
        
        Args:
            slice_index: Current slice index
        """
        self.current_slice_index = slice_index
        if slice_index not in self.rois:
            self.rois[slice_index] = []
    
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
            scene.removeItem(self.current_roi_item.item)
        
        # Create new item
        if self.current_shape_type == "rectangle":
            item = QGraphicsRectItem(rect)
        else:  # ellipse
            item = QGraphicsEllipseItem(rect)
        
        self.current_roi_item = ROIItem(self.current_shape_type, item)
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
        
        # Add to current slice
        if self.current_slice_index not in self.rois:
            self.rois[self.current_slice_index] = []
        
        self.rois[self.current_slice_index].append(self.current_roi_item)
        
        self.drawing = False
        self.drawing_start_pos = None
        roi = self.current_roi_item
        self.current_roi_item = None
        
        return roi
    
    def get_rois_for_slice(self, slice_index: int) -> List[ROIItem]:
        """
        Get all ROIs for a slice.
        
        Args:
            slice_index: Slice index
            
        Returns:
            List of ROI items
        """
        return self.rois.get(slice_index, [])
    
    def clear_slice_rois(self, slice_index: int, scene) -> None:
        """
        Clear all ROIs from a slice.
        
        Args:
            slice_index: Slice index
            scene: QGraphicsScene to remove items from
        """
        if slice_index in self.rois:
            for roi in self.rois[slice_index]:
                scene.removeItem(roi.item)
            del self.rois[slice_index]
    
    def clear_all_rois(self, scene) -> None:
        """
        Clear all ROIs from all slices.
        
        Args:
            scene: QGraphicsScene to remove items from
        """
        for slice_index, roi_list in self.rois.items():
            for roi in roi_list:
                scene.removeItem(roi.item)
        self.rois.clear()
    
    def calculate_statistics(self, roi: ROIItem, pixel_array: np.ndarray) -> Dict[str, float]:
        """
        Calculate statistics for an ROI.
        
        Args:
            roi: ROI item
            pixel_array: Image pixel array
            
        Returns:
            Dictionary with statistics (mean, std, min, max, etc.)
        """
        height, width = pixel_array.shape[:2]
        mask = roi.get_mask(width, height)
        
        # Get pixels within ROI
        roi_pixels = pixel_array[mask]
        
        if len(roi_pixels) == 0:
            return {
                "mean": 0.0,
                "std": 0.0,
                "min": 0.0,
                "max": 0.0,
                "count": 0
            }
        
        return {
            "mean": float(np.mean(roi_pixels)),
            "std": float(np.std(roi_pixels)),
            "min": float(np.min(roi_pixels)),
            "max": float(np.max(roi_pixels)),
            "count": int(len(roi_pixels))
        }


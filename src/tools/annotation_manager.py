"""
Annotation and RT STRUCT Manager

This module handles display of annotations and RT STRUCT overlays
from DICOM files.

Inputs:
    - DICOM datasets with RT STRUCT data
    - Annotation data
    
Outputs:
    - Overlay graphics items
    - Annotation displays
    
Requirements:
    - PySide6 for graphics
    - pydicom for RT STRUCT parsing
"""

from PySide6.QtWidgets import QGraphicsItem
from PySide6.QtCore import Qt
from PySide6.QtGui import QPen, QColor, QBrush
from typing import List, Optional, Dict
import pydicom
from pydicom.dataset import Dataset


class AnnotationManager:
    """
    Manages annotations and RT STRUCT overlays.
    
    Features:
    - Display RT STRUCT contours
    - Display annotations
    - Overlay on images
    """
    
    def __init__(self):
        """Initialize the annotation manager."""
        self.annotations: List[QGraphicsItem] = []
        self.rt_struct_data: Optional[Dataset] = None
    
    def load_rt_struct(self, dataset: Dataset) -> bool:
        """
        Load RT STRUCT data from DICOM dataset.
        
        Args:
            dataset: pydicom Dataset with RT STRUCT data
            
        Returns:
            True if loaded successfully
        """
        try:
            # Check if this is an RT STRUCT file
            if hasattr(dataset, 'SOPClassUID'):
                # RT Structure Set Storage
                if '1.2.840.10008.5.1.4.1.1.481.3' in str(dataset.SOPClassUID):
                    self.rt_struct_data = dataset
                    return True
        except Exception as e:
            print(f"Error loading RT STRUCT: {e}")
        
        return False
    
    def get_contours(self) -> List[Dict]:
        """
        Extract contours from RT STRUCT data.
        
        Returns:
            List of contour dictionaries
        """
        if self.rt_struct_data is None:
            return []
        
        contours = []
        
        try:
            # RT STRUCT structure
            # StructureSetROISequence contains ROI information
            # ROIContourSequence contains contour data
            
            if hasattr(self.rt_struct_data, 'StructureSetROISequence'):
                roi_sequence = self.rt_struct_data.StructureSetROISequence
                
                if hasattr(self.rt_struct_data, 'ROIContourSequence'):
                    contour_sequence = self.rt_struct_data.ROIContourSequence
                    
                    for roi, contour in zip(roi_sequence, contour_sequence):
                        roi_name = getattr(roi, 'ROIName', 'Unknown')
                        roi_number = getattr(roi, 'ROINumber', 0)
                        
                        # Get contour data
                        if hasattr(contour, 'ContourSequence'):
                            contour_data = []
                            for contour_item in contour.ContourSequence:
                                if hasattr(contour_item, 'ContourData'):
                                    # ContourData is a flat list of x,y,z coordinates
                                    data = contour_item.ContourData
                                    points = []
                                    for i in range(0, len(data), 3):
                                        if i + 2 < len(data):
                                            points.append((data[i], data[i+1], data[i+2]))
                                    contour_data.append({
                                        'points': points,
                                        'roi_name': roi_name,
                                        'roi_number': roi_number
                                    })
                            
                            contours.extend(contour_data)
        except Exception as e:
            print(f"Error extracting contours: {e}")
        
        return contours
    
    def create_overlay_items(self, scene, contours: List[Dict]) -> List[QGraphicsItem]:
        """
        Create graphics items for contours.
        
        Args:
            scene: QGraphicsScene to add items to
            contours: List of contour dictionaries
            
        Returns:
            List of graphics items
        """
        # Clear existing items
        self.clear_annotations(scene)
        
        items = []
        
        # Color map for different ROIs
        colors = [
            QColor(255, 0, 0),    # Red
            QColor(0, 255, 0),    # Green
            QColor(0, 0, 255),    # Blue
            QColor(255, 255, 0),  # Yellow
            QColor(255, 0, 255), # Magenta
            QColor(0, 255, 255), # Cyan
        ]
        
        for idx, contour in enumerate(contours):
            points = contour.get('points', [])
            if len(points) < 3:  # Need at least 3 points for a polygon
                continue
            
            roi_number = contour.get('roi_number', 0)
            color = colors[roi_number % len(colors)]
            
            # Create polygon item (simplified - would need proper QGraphicsPolygonItem)
            # For now, we'll create line items connecting points
            from PySide6.QtWidgets import QGraphicsPolygonItem
            from PySide6.QtCore import QPointF, QPolygonF
            
            polygon_points = [QPointF(p[0], p[1]) for p in points]
            polygon = QPolygonF(polygon_points)
            
            polygon_item = QGraphicsPolygonItem(polygon)
            pen = QPen(color, 2)
            polygon_item.setPen(pen)
            polygon_item.setBrush(QBrush(color, Qt.BrushStyle.NoBrush))
            
            scene.addItem(polygon_item)
            items.append(polygon_item)
            self.annotations.append(polygon_item)
        
        return items
    
    def clear_annotations(self, scene) -> None:
        """
        Clear all annotations from scene.
        
        Args:
            scene: QGraphicsScene to remove items from
        """
        for item in self.annotations:
            scene.removeItem(item)
        self.annotations.clear()


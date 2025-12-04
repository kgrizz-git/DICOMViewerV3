"""
Annotation Clipboard Manager

This module manages copy/paste operations for annotations (ROIs, measurements, crosshairs).

Inputs:
    - Annotation items (ROIs, measurements, crosshairs) to copy
    
Outputs:
    - Serialized annotation data for pasting
    
Requirements:
    - PySide6 for Qt types (QPointF, QRectF)
    - Standard library for JSON serialization
"""

from typing import Optional, Dict, List, Any, Tuple
from PySide6.QtCore import QPointF, QRectF


class AnnotationClipboard:
    """
    Manages clipboard operations for annotations.
    
    Features:
    - Copy selected annotations to internal clipboard
    - Serialize annotation properties
    - Paste annotations from clipboard
    - Track source slice for smart offset logic
    """
    
    def __init__(self):
        """Initialize the annotation clipboard."""
        self.clipboard_data: Optional[Dict[str, Any]] = None
        self.source_slice_key: Optional[Tuple[str, str, int]] = None
    
    def copy_annotations(
        self,
        rois: List,
        measurements: List,
        crosshairs: List,
        source_study_uid: str,
        source_series_uid: str,
        source_instance_identifier: int
    ) -> Dict[str, Any]:
        """
        Copy annotations to clipboard.
        
        Args:
            rois: List of ROIItem objects to copy
            measurements: List of MeasurementItem objects to copy
            crosshairs: List of CrosshairItem objects to copy
            source_study_uid: Study UID of source slice
            source_series_uid: Series UID of source slice
            source_instance_identifier: Instance identifier of source slice
            
        Returns:
            Dictionary containing serialized annotation data
        """
        data = {
            'type': 'dicom_viewer_annotations',
            'version': '1.0',
            'rois': self._serialize_rois(rois),
            'measurements': self._serialize_measurements(measurements),
            'crosshairs': self._serialize_crosshairs(crosshairs)
        }
        
        self.clipboard_data = data
        self.source_slice_key = (source_study_uid, source_series_uid, source_instance_identifier)
        
        return data
    
    def _serialize_rois(self, rois: List) -> List[Dict[str, Any]]:
        """
        Serialize ROI items.
        
        Args:
            rois: List of ROIItem objects
            
        Returns:
            List of dictionaries containing ROI properties
        """
        from PySide6.QtGui import QColor
        
        serialized = []
        for roi in rois:
            rect = roi.item.rect()
            pos = roi.item.pos()
            
            # Extract pen properties from the graphics item's pen
            pen = roi.item.pen()
            pen_width = int(pen.widthF()) if pen.widthF() > 0 else int(pen.width())
            pen_color_obj = pen.color()
            pen_color = (pen_color_obj.red(), pen_color_obj.green(), pen_color_obj.blue())
            
            roi_data = {
                'shape_type': roi.shape_type,
                'rect': {
                    'x': rect.x(),
                    'y': rect.y(),
                    'width': rect.width(),
                    'height': rect.height()
                },
                'position': {
                    'x': pos.x(),
                    'y': pos.y()
                },
                'pen_width': pen_width,
                'pen_color': pen_color,
            }
            
            # Include visible statistics if available
            if hasattr(roi, 'visible_statistics'):
                roi_data['visible_statistics'] = list(roi.visible_statistics)
            
            serialized.append(roi_data)
        
        return serialized
    
    def _serialize_measurements(self, measurements: List) -> List[Dict[str, Any]]:
        """
        Serialize measurement items.
        
        Args:
            measurements: List of MeasurementItem objects
            
        Returns:
            List of dictionaries containing measurement properties
        """
        serialized = []
        for m in measurements:
            meas_data = {
                'start_point': {
                    'x': m.start_point.x(),
                    'y': m.start_point.y()
                },
                'end_point': {
                    'x': m.end_point.x(),
                    'y': m.end_point.y()
                },
                'pixel_spacing': m.pixel_spacing
            }
            serialized.append(meas_data)
        
        return serialized
    
    def _serialize_crosshairs(self, crosshairs: List) -> List[Dict[str, Any]]:
        """
        Serialize crosshair items.
        
        Args:
            crosshairs: List of CrosshairItem objects
            
        Returns:
            List of dictionaries containing crosshair properties
        """
        serialized = []
        for c in crosshairs:
            cross_data = {
                'position': {
                    'x': c.position.x(),
                    'y': c.position.y()
                },
                'pixel_value_str': c.pixel_value_str,
                'x_coord': c.x_coord,
                'y_coord': c.y_coord,
                'z_coord': c.z_coord,
                'text_offset_viewport': c.text_offset_viewport
            }
            serialized.append(cross_data)
        
        return serialized
    
    def paste_annotations(self) -> Optional[Dict[str, Any]]:
        """
        Get clipboard data for pasting.
        
        Returns:
            Dictionary containing annotation data or None if clipboard is empty
        """
        return self.clipboard_data
    
    def get_source_slice_key(self) -> Optional[Tuple[str, str, int]]:
        """
        Get the source slice key (study_uid, series_uid, instance_identifier).
        
        Returns:
            Tuple of (study_uid, series_uid, instance_identifier) or None
        """
        return self.source_slice_key
    
    def has_data(self) -> bool:
        """
        Check if clipboard contains annotation data.
        
        Returns:
            True if clipboard has data, False otherwise
        """
        return self.clipboard_data is not None
    
    def clear(self) -> None:
        """Clear the clipboard."""
        self.clipboard_data = None
        self.source_slice_key = None


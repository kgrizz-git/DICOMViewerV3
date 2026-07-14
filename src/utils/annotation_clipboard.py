"""
Annotation Clipboard Manager

This module manages copy/paste operations for annotations (ROIs, measurements, crosshairs).

Inputs:
    - Annotation items (ROIs, measurements, crosshairs) to copy
    
Outputs:
    - Serialized annotation data for pasting
    
Requirements:
    - PySide6 for some annotation item types (measurements, text, arrows, etc.)
    - Standard library for JSON serialization
    - tools.roi_persistence for ROI clipboard dicts (Phase 5B)
"""

from typing import Any, Literal

from PySide6.QtCore import QPointF

from utils.roi_persistence import serialize_rois_for_clipboard

ClipboardOperation = Literal["copy", "cut"]

# Same-slice paste nudge for Copy only (duplicate visible next to original).
_SAME_SLICE_COPY_OFFSET_PX = 10.0


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
        self.clipboard_data: dict[str, Any] | None = None
        self.source_slice_key: tuple[str, str, int] | None = None
        self._source_operation: ClipboardOperation = "copy"

    def copy_annotations(
        self,
        rois: list[Any],
        measurements: list[Any],
        crosshairs: list[Any],
        source_study_uid: str,
        source_series_uid: str,
        source_instance_identifier: int,
        text_annotations: list[Any] | None = None,
        arrow_annotations: list[Any] | None = None,
        *,
        operation: ClipboardOperation = "copy",
    ) -> dict[str, Any]:
        """
        Copy annotations to clipboard.
        
        Args:
            rois: List of ROIItem objects to copy
            measurements: List of MeasurementItem objects to copy
            crosshairs: List of CrosshairItem objects to copy
            source_study_uid: Study UID of source slice
            source_series_uid: Series UID of source slice
            source_instance_identifier: Instance identifier of source slice
            text_annotations: Optional list of TextAnnotationItem objects to copy
            arrow_annotations: Optional list of ArrowAnnotationItem objects to copy
            operation: ``"copy"`` or ``"cut"`` — controls same-slice paste offset (cut restores position).
            
        Returns:
            Dictionary containing serialized annotation data
        """
        data = {
            'type': 'dicom_viewer_annotations',
            'version': '1.0',
            'rois': serialize_rois_for_clipboard(rois),
            'measurements': self._serialize_measurements(measurements),
            'crosshairs': self._serialize_crosshairs(crosshairs),
            'text_annotations': self._serialize_text_annotations(text_annotations or []),
            'arrow_annotations': self._serialize_arrow_annotations(arrow_annotations or [])
        }

        self.clipboard_data = data
        self.source_slice_key = (source_study_uid, source_series_uid, source_instance_identifier)
        self._source_operation = operation

        return data

    def get_paste_offset(
        self, current_slice_key: tuple[str, str, int]
    ) -> QPointF:
        """
        Scene offset for paste on the focused slice.

        Different slice: no offset (same image coordinates).
        Same slice + copy: small nudge so duplicate does not cover the original.
        Same slice + cut: no offset (restore cut position).
        """
        if self.source_slice_key is None or current_slice_key != self.source_slice_key:
            return QPointF(0.0, 0.0)
        if self._source_operation == "cut":
            return QPointF(0.0, 0.0)
        return QPointF(_SAME_SLICE_COPY_OFFSET_PX, _SAME_SLICE_COPY_OFFSET_PX)

    def _serialize_measurements(self, measurements: list[Any]) -> list[dict[str, Any]]:
        """
        Serialize measurement items.
        
        Args:
            measurements: List of MeasurementItem objects
            
        Returns:
            List of dictionaries containing measurement properties
        """
        serialized = []
        for m in measurements:
            # Duck-type: angle measurements have p1/p2/p3; distance has start_point/end_point
            if hasattr(m, "p3"):
                meas_data = {
                    "measurement_kind": "angle",
                    "p1": {"x": m.p1.x(), "y": m.p1.y()},
                    "p2": {"x": m.p2.x(), "y": m.p2.y()},
                    "p3": {"x": m.p3.x(), "y": m.p3.y()},
                    "text_offset_viewport": {
                        "x": m.text_offset_viewport.x(),
                        "y": m.text_offset_viewport.y(),
                    },
                }
            else:
                meas_data = {
                    "measurement_kind": "distance",
                    "start_point": {
                        "x": m.start_point.x(),
                        "y": m.start_point.y(),
                    },
                    "end_point": {
                        "x": m.end_point.x(),
                        "y": m.end_point.y(),
                    },
                    "pixel_spacing": m.pixel_spacing,
                }
            serialized.append(meas_data)

        return serialized

    def _serialize_crosshairs(self, crosshairs: list[Any]) -> list[dict[str, Any]]:
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

    def _serialize_text_annotations(self, text_annotations: list[Any]) -> list[dict[str, Any]]:
        """
        Serialize text annotation items.
        
        Args:
            text_annotations: List of TextAnnotationItem objects
            
        Returns:
            List of dictionaries containing text annotation properties
        """

        serialized = []
        for text_item in text_annotations:
            pos = text_item.pos()
            text_color_obj = text_item.defaultTextColor()
            font = text_item.font()

            text_data = {
                'text': text_item.toPlainText(),
                'position': {
                    'x': pos.x(),
                    'y': pos.y()
                },
                'font_size': font.pointSize() if font.pointSize() > 0 else font.pixelSize(),
                'color': {
                    'r': text_color_obj.red(),
                    'g': text_color_obj.green(),
                    'b': text_color_obj.blue()
                }
            }
            serialized.append(text_data)

        return serialized

    def _serialize_arrow_annotations(self, arrow_annotations: list[Any]) -> list[dict[str, Any]]:
        """
        Serialize arrow annotation items.
        
        Args:
            arrow_annotations: List of ArrowAnnotationItem objects
            
        Returns:
            List of dictionaries containing arrow annotation properties
        """
        serialized = []
        for arrow_item in arrow_annotations:
            arrow_data = {
                'start_point': {
                    'x': arrow_item.start_point.x(),
                    'y': arrow_item.start_point.y()
                },
                'end_point': {
                    'x': arrow_item.end_point.x(),
                    'y': arrow_item.end_point.y()
                },
                'color': {
                    'r': arrow_item.color.red(),
                    'g': arrow_item.color.green(),
                    'b': arrow_item.color.blue()
                }
            }
            serialized.append(arrow_data)

        return serialized

    def paste_annotations(self) -> dict[str, Any] | None:
        """
        Get clipboard data for pasting.
        
        Returns:
            Dictionary containing annotation data or None if clipboard is empty
        """
        return self.clipboard_data

    def get_source_slice_key(self) -> tuple[str, str, int] | None:
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
        self._source_operation = "copy"


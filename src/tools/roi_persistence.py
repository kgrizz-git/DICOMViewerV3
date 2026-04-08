"""
ROI persistence helpers — clipboard-oriented serialization (Phase 5B).

Produces JSON-compatible ``dict`` payloads matching the schema consumed by
``AnnotationPasteHandler.paste_roi`` and stored in ``AnnotationClipboard``.

Inputs:
    - ``ROIItem`` instances (from ``tools.roi_manager``).

Outputs:
    - Plain ``dict`` / ``list`` structures suitable for merging into clipboard JSON.

Requirements:
    - PySide6 (reads pen, rectangle, and position from the ROI graphics item).
"""

from __future__ import annotations

from typing import Any, Dict, List


def serialize_roi_for_clipboard(roi: Any) -> Dict[str, Any]:
    """
    Build one clipboard ROI dict from *roi* (an ``ROIItem``).

    Keys mirror the historical ``AnnotationClipboard._serialize_rois`` layout.
    """
    rect = roi.item.rect()
    pos = roi.item.pos()

    pen = roi.item.pen()
    pen_width = int(pen.widthF()) if pen.widthF() > 0 else int(pen.width())
    pen_color_obj = pen.color()
    pen_color = (pen_color_obj.red(), pen_color_obj.green(), pen_color_obj.blue())

    roi_data: Dict[str, Any] = {
        "shape_type": roi.shape_type,
        "rect": {
            "x": rect.x(),
            "y": rect.y(),
            "width": rect.width(),
            "height": rect.height(),
        },
        "position": {
            "x": pos.x(),
            "y": pos.y(),
        },
        "pen_width": pen_width,
        "pen_color": pen_color,
    }

    if hasattr(roi, "visible_statistics"):
        roi_data["visible_statistics"] = list(roi.visible_statistics)

    return roi_data


def serialize_rois_for_clipboard(rois: List[Any]) -> List[Dict[str, Any]]:
    """Serialize a list of ``ROIItem`` instances for the annotation clipboard."""
    return [serialize_roi_for_clipboard(roi) for roi in rois]

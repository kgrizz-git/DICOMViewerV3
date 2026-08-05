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
import importlib
import logging
from typing import Any

from pydicom.dataset import Dataset
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsPolygonItem,
    QGraphicsScene,
    QGraphicsTextItem,
)

from core.key_object_handler import KeyObjectHandler
from core.presentation_state_handler import PresentationStateHandler
from tools.annotation_overlay_bitmap import convert_overlay_bitmap_to_graphics
from utils.log_sanitizer import sanitized_format_exc
from utils.privacy.console import print_redacted

_logger = logging.getLogger(__name__)


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
        # Dictionary mapping scenes to their annotation items for multi-subwindow support
        self.annotations: dict[QGraphicsScene, list[QGraphicsItem]] = {}
        self.rt_struct_data: Dataset | None = None

        # Presentation State and Key Object handlers
        self.presentation_state_handler = PresentationStateHandler()
        self.key_object_handler = KeyObjectHandler()

        # Storage for Presentation States and Key Objects
        self.presentation_states: dict[str, list[Dataset]] = {}  # Keyed by StudyInstanceUID
        self.key_objects: dict[str, list[Dataset]] = {}  # Keyed by StudyInstanceUID

    def _add_annotation_to_scene(self, scene: QGraphicsScene, item: QGraphicsItem) -> None:
        """
        Add an annotation item to the scene-specific tracking list.
        
        Args:
            scene: QGraphicsScene the item belongs to
            item: QGraphicsItem to track
        """
        if scene not in self.annotations:
            self.annotations[scene] = []
        self.annotations[scene].append(item)

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
            print_redacted(f"Error loading RT STRUCT: {e}")

        return False

    def get_contours(self) -> list[dict[str, Any]]:
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

                    for roi, contour in zip(roi_sequence, contour_sequence, strict=False):
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
            print_redacted(f"Error extracting contours: {e}")

        return contours

    def create_overlay_items(self, scene, contours: list[dict[str, Any]]) -> list[QGraphicsItem]:
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

        for _idx, contour in enumerate(contours):
            points = contour.get('points', [])
            if len(points) < 3:  # Need at least 3 points for a polygon
                continue

            roi_number = contour.get('roi_number', 0)
            color = colors[roi_number % len(colors)]

            # Create polygon item (simplified - would need proper QGraphicsPolygonItem)
            # For now, we'll create line items connecting points

            polygon_points = [QPointF(p[0], p[1]) for p in points]
            polygon = QPolygonF(polygon_points)

            polygon_item = QGraphicsPolygonItem(polygon)
            pen = QPen(color, 2)
            polygon_item.setPen(pen)
            polygon_item.setBrush(QBrush(color, Qt.BrushStyle.NoBrush))

            scene.addItem(polygon_item)
            items.append(polygon_item)
            self._add_annotation_to_scene(scene, polygon_item)

        return items

    def load_presentation_states(self, presentation_states: dict[str, list[Dataset]]) -> None:
        """
        Store Presentation State files for later matching.
        Merges into existing state (additive) so multiple studies' PS can coexist.
        
        Args:
            presentation_states: Dictionary keyed by StudyInstanceUID containing lists of Presentation State datasets
        """
        self.presentation_states.update(presentation_states)

    def load_key_objects(self, key_objects: dict[str, list[Dataset]]) -> None:
        """
        Store Key Object files for later matching.
        Merges into existing state (additive) so multiple studies' KO can coexist.
        
        Args:
            key_objects: Dictionary keyed by StudyInstanceUID containing lists of Key Object datasets
        """
        self.key_objects.update(key_objects)

    def remove_study_annotations(self, study_uid: str) -> None:
        """
        Remove Presentation State and Key Object data for a single study.
        Used when a study is closed (e.g. right-click Close This Study).
        """
        self.presentation_states.pop(study_uid, None)
        self.key_objects.pop(study_uid, None)

    def clear_all_ps_ko(self) -> None:
        """
        Clear all Presentation State and Key Object data.
        Used by the Close All path.
        """
        self.presentation_states.clear()
        self.key_objects.clear()

    def get_annotations_for_image(self, dataset: Dataset, study_uid: str) -> list[dict[str, Any]]:
        """
        Get annotations for a specific image from Presentation States, Key Objects, and embedded annotations.
        
        Args:
            dataset: pydicom Dataset for the image
            study_uid: Study Instance UID
            
        Returns:
            List of annotation dictionaries
        """
        annotations = []

        try:
            # Get SOP Instance UID for this image
            if not hasattr(dataset, 'SOPInstanceUID'):
                return annotations

            image_uid = str(dataset.SOPInstanceUID)
            series_uid = getattr(dataset, 'SeriesInstanceUID', '')

            # Check for embedded annotations in the image file itself
            embedded_annotations = self._get_embedded_annotations(dataset)
            if embedded_annotations:
                annotations.extend(embedded_annotations)

            # Check Presentation States for this study
            if study_uid in self.presentation_states:
                for _idx, ps_dataset in enumerate(self.presentation_states[study_uid]):
                    parsed_ps = self.presentation_state_handler.parse_presentation_state(ps_dataset)

                    ref_info = parsed_ps['referenced_images']
                    image_uids = ref_info.get('image_uids', [])
                    series_uids = ref_info.get('series_uids', [])

                    # Check if this Presentation State references our image (image-level or series-level)
                    matches = image_uid in image_uids or series_uid in series_uids

                    if matches:
                        # Add annotations from this Presentation State
                        for ann in parsed_ps['annotations']:
                            ann['source'] = 'presentation_state'
                            annotations.append(ann)

            # Check Key Objects for this study
            if study_uid in self.key_objects:
                for _idx, ko_dataset in enumerate(self.key_objects[study_uid]):
                    parsed_ko = self.key_object_handler.parse_key_object(ko_dataset)

                    # Key Objects reference images through ContentSequence
                    # For now, check if image UID is in referenced_images list
                    # Future: could also check for series-level references
                    ref_images = parsed_ko.get('referenced_images', [])
                    if image_uid in ref_images:
                        # Convert Key Object annotations to graphic format
                        for ann in parsed_ko['annotations']:
                            # Convert text annotations to graphic format
                            graphic_ann = {
                                'type': 'TEXT',
                                'text': ann.get('text', ''),
                                'coordinates': [(0, 0)],  # Default position, would need proper positioning
                                'color': (255, 255, 0),  # Default yellow
                                'layer': ann.get('type', ''),
                                'source': 'key_object',
                                'value': ann.get('value'),
                                'units': ann.get('units', 'PIXEL')
                            }
                            annotations.append(graphic_ann)
        except Exception:
            _logger.debug("%s", sanitized_format_exc())

        return annotations

    def create_presentation_state_items(self, scene, annotations: list[dict[str, Any]],
                                       image_width: float, image_height: float) -> list[QGraphicsItem]:
        """
        Create graphics items for Presentation State annotations.
        
        Args:
            scene: QGraphicsScene to add items to
            annotations: List of annotation dictionaries
            image_width: Width of the image (for coordinate scaling)
            image_height: Height of the image (for coordinate scaling)
            
        Returns:
            List of graphics items
        """
        items: list[QGraphicsItem] = []

        try:
            for ann in annotations:
                ann_type = ann.get('type', '')
                coords = ann.get('coordinates', [])
                units = ann.get('units', 'PIXEL')

                # Transform coordinates based on units. OVERLAY annotations render
                # from overlay_data / paths and must not be skipped when coordinates
                # are empty (bitmap / path branches do not need pre-populated coords).
                transformed_coords = self._transform_coordinates(coords, units, image_width, image_height)
                if not transformed_coords and ann_type != 'OVERLAY':
                    continue

                qcolor = self._presentation_state_color(ann.get('color', (255, 255, 0)))
                self._render_presentation_state_annotation(
                    scene,
                    ann_type,
                    ann,
                    transformed_coords,
                    qcolor,
                    image_width,
                    image_height,
                    items,
                )
        except Exception:
            _logger.debug("%s", sanitized_format_exc())

        return items

    @staticmethod
    def _presentation_state_color(color: Any) -> QColor:
        """Return the annotation color, preserving the yellow fallback."""
        if isinstance(color, tuple) and len(color) >= 3:
            return QColor(color[0], color[1], color[2])
        return QColor(255, 255, 0)

    def _render_presentation_state_annotation(
        self,
        scene: QGraphicsScene,
        ann_type: str,
        annotation: dict[str, Any],
        coords: list[tuple[float, float]],
        color: QColor,
        image_width: float,
        image_height: float,
        items: list[QGraphicsItem],
    ) -> None:
        """Dispatch one transformed presentation-state annotation to its renderer."""
        pen = QPen(color, 2)
        if ann_type == 'TEXT':
            self._render_presentation_state_text(scene, annotation, coords, color, image_width, image_height, items)
        elif ann_type == 'POLYLINE':
            self._render_presentation_state_polyline(scene, coords, pen, image_width, image_height, items)
        elif ann_type == 'CIRCLE':
            self._render_presentation_state_circle(scene, coords, pen, image_width, image_height, items)
        elif ann_type == 'ELLIPSE':
            self._render_presentation_state_ellipse(scene, coords, pen, image_width, image_height, items)
        elif ann_type == 'POINT':
            self._render_presentation_state_point(scene, coords, color, pen, image_width, image_height, items)
        elif ann_type == 'OVERLAY':
            self._render_presentation_state_overlay(scene, annotation, coords, color, pen, items)

    def _render_presentation_state_text(
        self,
        scene: QGraphicsScene,
        annotation: dict[str, Any],
        coords: list[tuple[float, float]],
        color: QColor,
        image_width: float,
        image_height: float,
        items: list[QGraphicsItem],
    ) -> None:
        """Render a bounded TEXT annotation."""
        text = annotation.get('text', '')
        if not text or not coords:
            return

        x, y = coords[0][0], coords[0][1]
        if not (0 <= x <= image_width and 0 <= y <= image_height):
            return

        text_item = QGraphicsTextItem(text)
        text_item.setDefaultTextColor(color)
        text_item.setPos(QPointF(x, y))
        self._register_presentation_state_item(scene, text_item, items)

    def _render_presentation_state_polyline(
        self,
        scene: QGraphicsScene,
        coords: list[tuple[float, float]],
        pen: QPen,
        image_width: float,
        image_height: float,
        items: list[QGraphicsItem],
    ) -> None:
        """Render a POLYLINE when its first point is in image bounds."""
        if len(coords) < 2:
            return

        first_x, first_y = coords[0][0], coords[0][1]
        if not (0 <= first_x <= image_width and 0 <= first_y <= image_height):
            return

        path = QPainterPath()
        path.moveTo(QPointF(first_x, first_y))
        for x, y in coords[1:]:
            path.lineTo(QPointF(x, y))

        path_item = QGraphicsPathItem(path)
        path_item.setPen(pen)
        self._register_presentation_state_item(scene, path_item, items)

    def _render_presentation_state_circle(
        self,
        scene: QGraphicsScene,
        coords: list[tuple[float, float]],
        pen: QPen,
        image_width: float,
        image_height: float,
        items: list[QGraphicsItem],
    ) -> None:
        """Render a CIRCLE using its centre and one point on the circumference."""
        if len(coords) < 2:
            return

        center, point_on_circle = coords[:2]
        dx = point_on_circle[0] - center[0]
        dy = point_on_circle[1] - center[1]
        radius = (dx * dx + dy * dy) ** 0.5
        if not (-radius <= center[0] <= image_width + radius
                and -radius <= center[1] <= image_height + radius):
            return

        ellipse_item = QGraphicsEllipseItem(
            center[0] - radius,
            center[1] - radius,
            2 * radius,
            2 * radius,
        )
        ellipse_item.setPen(pen)
        ellipse_item.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        self._register_presentation_state_item(scene, ellipse_item, items)

    def _render_presentation_state_ellipse(
        self,
        scene: QGraphicsScene,
        coords: list[tuple[float, float]],
        pen: QPen,
        image_width: float,
        image_height: float,
        items: list[QGraphicsItem],
    ) -> None:
        """Render an ELLIPSE from the bounding box of at least three points."""
        if len(coords) < 3:
            return

        min_x = min(coord[0] for coord in coords)
        max_x = max(coord[0] for coord in coords)
        min_y = min(coord[1] for coord in coords)
        max_y = max(coord[1] for coord in coords)
        if not (-100 <= min_x <= image_width + 100
                and -100 <= min_y <= image_height + 100):
            return

        ellipse_item = QGraphicsEllipseItem(min_x, min_y, max_x - min_x, max_y - min_y)
        ellipse_item.setPen(pen)
        ellipse_item.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        self._register_presentation_state_item(scene, ellipse_item, items)

    def _render_presentation_state_point(
        self,
        scene: QGraphicsScene,
        coords: list[tuple[float, float]],
        color: QColor,
        pen: QPen,
        image_width: float,
        image_height: float,
        items: list[QGraphicsItem],
    ) -> None:
        """Render a bounded POINT annotation as a filled three-pixel circle."""
        if not coords:
            return

        x, y = coords[0][0], coords[0][1]
        if not (0 <= x <= image_width and 0 <= y <= image_height):
            return

        radius = 3
        ellipse_item = QGraphicsEllipseItem(x - radius, y - radius, 2 * radius, 2 * radius)
        ellipse_item.setPen(pen)
        ellipse_item.setBrush(QBrush(color))
        self._register_presentation_state_item(scene, ellipse_item, items)

    def _render_presentation_state_overlay(
        self,
        scene: QGraphicsScene,
        annotation: dict[str, Any],
        coords: list[tuple[float, float]],
        color: QColor,
        pen: QPen,
        items: list[QGraphicsItem],
    ) -> None:
        """Render an OVERLAY bitmap first, falling back to vector paths."""
        overlay_paths = annotation.get('paths', [])
        bitmap_item = self._create_presentation_state_overlay_bitmap(annotation, color)
        if bitmap_item:
            self._register_presentation_state_item(scene, bitmap_item, items)
            return

        self._render_overlay_paths(overlay_paths, coords, overlay_paths, pen, color, scene, items)

    def _create_presentation_state_overlay_bitmap(
        self,
        annotation: dict[str, Any],
        color: QColor,
    ) -> QGraphicsItem | None:
        """Create an overlay bitmap item when the annotation has valid bitmap metadata."""
        overlay_data = annotation.get('overlay_data')
        overlay_rows = annotation.get('overlay_rows', 0)
        overlay_cols = annotation.get('overlay_cols', 0)
        if overlay_data is None or overlay_rows <= 0 or overlay_cols <= 0:
            return None

        return self._create_overlay_bitmap_item(
            overlay_data,
            overlay_cols,
            overlay_rows,
            annotation.get('overlay_origin_x', 0),
            annotation.get('overlay_origin_y', 0),
            color,
        )

    def _register_presentation_state_item(
        self,
        scene: QGraphicsScene,
        item: QGraphicsItem,
        items: list[QGraphicsItem],
    ) -> None:
        """Style, add, return-track, and scene-track a presentation-state item."""
        item.setZValue(200)
        item.setVisible(True)
        scene.addItem(item)
        items.append(item)
        self._add_annotation_to_scene(scene, item)

    def _transform_coordinates(
        self,
        coords: list[tuple[float, float]],
        units: str,
        image_width: float,
        image_height: float,
    ) -> list[tuple[float, float]]:
        """
        Transform coordinates based on their units.
        
        Args:
            coords: List of coordinate tuples (x, y)
            units: Coordinate units ('PIXEL', 'DISPLAY', 'NORMALIZED')
            image_width: Image width in pixels
            image_height: Image height in pixels
            
        Returns:
            Transformed coordinates in pixel space
        """
        if not coords:
            return []

        transformed = []

        try:
            if units == 'NORMALIZED':
                # Normalized coordinates are in range 0-1, scale to pixel coordinates
                for coord in coords:
                    if len(coord) >= 2:
                        x = float(coord[0]) * image_width
                        y = float(coord[1]) * image_height
                        transformed.append((x, y))
            elif units == 'PIXEL':
                # Pixel coordinates - use as-is
                transformed = [(float(c[0]), float(c[1])) for c in coords if len(c) >= 2]
            elif units == 'DISPLAY':
                # DISPLAY coordinates - for now, treat as pixel coordinates
                # Future enhancement: account for zoom/pan/rotation
                transformed = [(float(c[0]), float(c[1])) for c in coords if len(c) >= 2]
            else:
                # Unknown units - default to pixel
                transformed = [(float(c[0]), float(c[1])) for c in coords if len(c) >= 2]
        except Exception:
            return []

        return transformed

    def _get_embedded_annotations(self, dataset: Dataset) -> list[dict[str, Any]]:
        """
        Extract embedded annotations from an image dataset.
        
        Checks for:
        - OverlayData tags (overlays embedded in image files)
        - GraphicAnnotationSequence (graphic annotations in image files)
        
        Args:
            dataset: pydicom Dataset for the image
            
        Returns:
            List of annotation dictionaries
        """
        annotations = []

        try:
            # Check for GraphicAnnotationSequence in image file
            if hasattr(dataset, 'GraphicAnnotationSequence'):
                graphic_seq = dataset.GraphicAnnotationSequence
                # Use the presentation state handler to parse it
                parsed_annotations = self.presentation_state_handler.parse_graphic_annotations(graphic_seq)
                for ann in parsed_annotations:
                    ann['source'] = 'embedded_graphics'
                    annotations.append(ann)

            # Check for OverlayData tags
            overlay_annotations = self._parse_overlay_data(dataset)
            if overlay_annotations:
                annotations.extend(overlay_annotations)
        except Exception:
            _logger.debug("%s", sanitized_format_exc())

        return annotations

    def _parse_overlay_data(self, dataset: Dataset) -> list[dict[str, Any]]:
        """
        Parse OverlayData tags from DICOM dataset.
        
        Overlays are stored in tags 0x60xx where xx can be 00-1F (overlay groups).
        Each overlay group has:
        - OverlayData (0x60xx, 0x3000): Bitmap data
        - OverlayRows (0x60xx, 0x0010): Number of rows
        - OverlayColumns (0x60xx, 0x0011): Number of columns
        - OverlayOrigin (0x60xx, 0x0050): Origin coordinates [row, column]
        - OverlayType (0x60xx, 0x0040): Type (G=graphic, R=ROI)
        
        Args:
            dataset: pydicom Dataset
            
        Returns:
            List of annotation dictionaries representing overlays
        """
        overlays = []

        try:
            # Check for overlay groups (0x6000-0x601F)
            for overlay_group in range(0x6000, 0x6020):
                overlay_data_tag = (overlay_group, 0x3000)  # OverlayData
                overlay_rows_tag = (overlay_group, 0x0010)  # OverlayRows
                overlay_cols_tag = (overlay_group, 0x0011)  # OverlayColumns
                overlay_origin_tag = (overlay_group, 0x0050)  # OverlayOrigin

                # Check if this overlay group exists
                # OverlayData might be in the dataset directly or in pixel data
                overlay_data = None
                if overlay_data_tag in dataset:
                    overlay_data = dataset[overlay_data_tag]
                else:
                    # Check if overlay is embedded in pixel data
                    # Some DICOM files store overlays in unused bits of pixel data
                    # For now, skip if not found in dedicated tag
                    continue

                overlay_rows = dataset.get(overlay_rows_tag, None)
                overlay_cols = dataset.get(overlay_cols_tag, None)
                overlay_origin = dataset.get(overlay_origin_tag, None)

                if overlay_rows and overlay_cols:
                    def _coerce_to_int(raw_value: Any, default: int = 0) -> int:
                        value = raw_value.value if hasattr(raw_value, "value") else raw_value
                        try:
                            return int(value)
                        except (TypeError, ValueError):
                            return default

                    rows_raw = overlay_rows.value if hasattr(overlay_rows, "value") else overlay_rows
                    cols_raw = overlay_cols.value if hasattr(overlay_cols, "value") else overlay_cols
                    rows_val = _coerce_to_int(rows_raw, default=0)
                    cols_val = _coerce_to_int(cols_raw, default=0)

                    # Parse OverlayOrigin - stored as [row, column] pair (1-based indexing)
                    # Default to [1, 1] per DICOM standard if missing
                    if overlay_origin:
                        origin_value = overlay_origin.value if hasattr(overlay_origin, 'value') else overlay_origin
                        if isinstance(origin_value, (list, tuple)) and len(origin_value) >= 2:
                            origin_row = _coerce_to_int(origin_value[0], default=1)  # Row (y coordinate)
                            origin_col = _coerce_to_int(origin_value[1], default=1)  # Column (x coordinate)
                        else:
                            origin_row = 1
                            origin_col = 1
                    else:
                        origin_row = 1
                        origin_col = 1

                    # Convert DICOM 1-based OverlayOrigin [row, column] into 0-based Qt x/y.
                    origin_x = float(origin_col - 1)  # horizontal pixel from column
                    origin_y = float(origin_row - 1)  # vertical pixel from row


                    # Extract overlay bitmap data
                    overlay_data_value = overlay_data.value if hasattr(overlay_data, 'value') else overlay_data

                    # Convert overlay bitmap to graphics primitives
                    graphics_primitives = self._convert_overlay_bitmap_to_graphics(
                        overlay_data_value, cols_val, rows_val, origin_x, origin_y
                    )

                    overlay_ann = {
                        'type': 'OVERLAY',
                        'coordinates': graphics_primitives.get('coordinates', []),
                        'paths': graphics_primitives.get('paths', []),
                        'text': f'Overlay {overlay_group:04X}',
                        'color': (255, 255, 0),  # Yellow
                        'layer': f'Overlay_{overlay_group:04X}',
                        'source': 'embedded_overlay',
                        'units': 'PIXEL',
                        'overlay_rows': rows_val,
                        'overlay_cols': cols_val,
                        'overlay_origin_x': origin_x,
                        'overlay_origin_y': origin_y,
                        'overlay_data': overlay_data_value
                    }
                    overlays.append(overlay_ann)
        except Exception:
            _logger.debug("%s", sanitized_format_exc())

        return overlays

    def _convert_overlay_bitmap_to_graphics(
        self,
        overlay_data,
        cols: int,
        rows: int,
        origin_x: float,
        origin_y: float,
    ) -> dict[str, Any]:
        """
        Convert overlay bitmap data to graphics primitives.

        Args:
            overlay_data: Overlay bitmap data (byte array, 1 bit per pixel)
            cols: Number of columns in overlay
            rows: Number of rows in overlay
            origin_x: X coordinate of overlay origin
            origin_y: Y coordinate of overlay origin

        Returns:
            Dictionary with 'coordinates' (list of points) and 'paths' (list of paths)
        """
        return convert_overlay_bitmap_to_graphics(
            overlay_data,
            cols,
            rows,
            origin_x,
            origin_y,
            log_debug=lambda msg: _logger.debug("%s", msg),
            import_module=importlib.import_module,
        )

    def _create_overlay_bitmap_item(self, overlay_data, cols: int, rows: int,
                                    origin_x: float, origin_y: float, color: QColor) -> QGraphicsItem | None:
        """
        Create a QGraphicsPixmapItem from overlay bitmap data.
        
        This provides better quality rendering than vector paths for complex overlays.
        
        Args:
            overlay_data: Overlay bitmap data
            cols: Number of columns
            rows: Number of rows
            origin_x: X coordinate of overlay origin
            origin_y: Y coordinate of overlay origin
            color: Color to tint the overlay
            
        Returns:
            QGraphicsPixmapItem or None if creation fails
        """
        try:
            import numpy as np
            from PySide6.QtGui import QImage, QPixmap
            from PySide6.QtWidgets import QGraphicsPixmapItem

            # Convert overlay data to numpy array (same logic as _convert_overlay_bitmap_to_graphics)
            overlay_bytes = None

            if hasattr(overlay_data, 'value'):
                overlay_bytes = overlay_data.value
            elif isinstance(overlay_data, (bytes, bytearray)):
                overlay_bytes = bytes(overlay_data)
            else:
                try:
                    overlay_bytes = bytes(overlay_data)
                except Exception:
                    return None

            if not overlay_bytes:
                return None

            # Convert bytes to bitmap
            num_bits = cols * rows
            num_bytes = (num_bits + 7) // 8

            if len(overlay_bytes) < num_bytes:
                num_bytes = len(overlay_bytes)
                num_bits = num_bytes * 8
                if num_bits > cols * rows:
                    num_bits = cols * rows

            # DICOM overlay data uses LSB-first bit order per DICOM standard Part 5, Chapter 8
            # First bit stored in LSB of first byte, next bits in increasing MSB positions
            # Use bitorder='little' (default) to unpack LSB-to-MSB within each byte
            bit_array = np.unpackbits(np.frombuffer(overlay_bytes[:num_bytes], dtype=np.uint8), bitorder='little')
            if len(bit_array) >= num_bits:
                bitmap = bit_array[:num_bits].reshape((rows, cols))
            else:
                return None

            # Bitmap positions are correct - no flip needed
            # DICOM overlay data: bits packed LSB-first within each byte, bytes stored sequentially
            # Character reversal is fixed by using LSB-first bit order (bitorder='little') per DICOM standard Part 5, Chapter 8
            bitmap_to_use = bitmap.copy()

            # Convert bitmap to QImage
            # Create RGBA image: colored pixels where overlay is set, transparent elsewhere
            height, width = bitmap_to_use.shape
            image = QImage(width, height, QImage.Format.Format_ARGB32)

            # Get color components
            r, g, b = color.red(), color.green(), color.blue()

            for y in range(height):
                for x in range(width):
                    if bitmap_to_use[y, x] > 0:
                        # Set pixel to overlay color (fully opaque)
                        image.setPixel(x, y, (255 << 24) | (r << 16) | (g << 8) | b)
                    else:
                        # Transparent pixel
                        image.setPixel(x, y, 0)

            # Create pixmap from image
            pixmap = QPixmap.fromImage(image)

            # Create graphics item
            pixmap_item = QGraphicsPixmapItem(pixmap)
            pixmap_item.setPos(QPointF(origin_x, origin_y))

            # Enable smooth pixmap transformation to prevent blocky appearance when zoomed
            from PySide6.QtCore import Qt
            pixmap_item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)

            pixmap_item.setZValue(200)
            pixmap_item.setVisible(True)


            return pixmap_item

        except ImportError:
            return None
        except Exception:
            _logger.debug("%s", sanitized_format_exc())
            return None

    def _render_overlay_paths(
        self,
        overlay_paths: list[list[tuple[float, float]]],
        coords: list[tuple[float, float]],
        _paths: list[list[tuple[float, float]]],
        _pen: QPen,
        color: QColor,
        scene,
        items: list[QGraphicsItem],
    ) -> None:
        """
        Render overlay paths with improved visibility and filtering.
        
        Args:
            overlay_paths: List of path coordinate lists
            coords: List of individual coordinates
            paths: Same as overlay_paths (for compatibility)
            pen: Pen to use for drawing
            color: Color for paths
            scene: QGraphicsScene to add items to
            items: List to append created items to
        """
        # Increase pen width for better visibility
        thick_pen = QPen(color, 3)  # 3 pixels wide

        # Filter and render paths
        if overlay_paths:
            # Filter out very small paths (likely noise)
            filtered_paths = []
            for path_coords in overlay_paths:
                if len(path_coords) >= 3:  # Need at least 3 points for a meaningful path
                    # Calculate path bounding box
                    xs = [p[0] for p in path_coords]
                    ys = [p[1] for p in path_coords]
                    width = max(xs) - min(xs)
                    height = max(ys) - min(ys)
                    # Filter out paths smaller than 2x2 pixels
                    if width >= 2 or height >= 2:
                        filtered_paths.append(path_coords)


            for path_coords in filtered_paths:
                if len(path_coords) >= 2:
                    # Create path from coordinates
                    path = QPainterPath()
                    first_point = path_coords[0]
                    path.moveTo(QPointF(first_point[0], first_point[1]))

                    for coord in path_coords[1:]:
                        path.lineTo(QPointF(coord[0], coord[1]))

                    # Optionally close the path if it's a closed shape
                    if len(path_coords) > 2:
                        # Check if first and last points are close
                        first = path_coords[0]
                        last = path_coords[-1]
                        dist = ((first[0] - last[0])**2 + (first[1] - last[1])**2)**0.5
                        if dist < 3.0:  # Close if within 3 pixels
                            path.closeSubpath()

                    path_item = QGraphicsPathItem(path)
                    path_item.setPen(thick_pen)
                    path_item.setBrush(QBrush(Qt.BrushStyle.NoBrush))
                    self._register_presentation_state_item(scene, path_item, items)

        # Render individual points only if no paths
        if coords and len(coords) > 0 and not overlay_paths:
            for coord in coords:
                x, y = coord[0], coord[1]
                # Create slightly larger circles for better visibility
                point_item = QGraphicsEllipseItem(
                    x - 2, y - 2,
                    4, 4
                )
                point_item.setPen(thick_pen)
                point_item.setBrush(QBrush(color))
                self._register_presentation_state_item(scene, point_item, items)

    def clear_annotations(self, scene) -> None:
        """
        Clear all annotations from the specified scene.
        
        Args:
            scene: QGraphicsScene to remove items from
        """
        # Only clear annotations that belong to this specific scene
        if scene in self.annotations:
            items_to_remove = self.annotations[scene]
            for item in items_to_remove:
                # Only remove if item is still in the scene (might have been removed already)
                if item.scene() == scene:
                    scene.removeItem(item)
            # Clear the list for this scene
            self.annotations[scene] = []

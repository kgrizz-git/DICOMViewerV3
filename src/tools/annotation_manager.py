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

from PySide6.QtWidgets import (QGraphicsItem, QGraphicsTextItem, QGraphicsLineItem,
                                QGraphicsEllipseItem, QGraphicsPathItem, QGraphicsPolygonItem)
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QPen, QColor, QBrush, QPainterPath, QPolygonF
from typing import List, Optional, Dict
import pydicom
from pydicom.dataset import Dataset
from core.presentation_state_handler import PresentationStateHandler
from core.key_object_handler import KeyObjectHandler


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
        
        # Presentation State and Key Object handlers
        self.presentation_state_handler = PresentationStateHandler()
        self.key_object_handler = KeyObjectHandler()
        
        # Storage for Presentation States and Key Objects
        self.presentation_states: Dict[str, List[Dataset]] = {}  # Keyed by StudyInstanceUID
        self.key_objects: Dict[str, List[Dataset]] = {}  # Keyed by StudyInstanceUID
    
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
    
    def load_presentation_states(self, presentation_states: Dict[str, List[Dataset]]) -> None:
        """
        Store Presentation State files for later matching.
        
        Args:
            presentation_states: Dictionary keyed by StudyInstanceUID containing lists of Presentation State datasets
        """
        self.presentation_states = presentation_states
    
    def load_key_objects(self, key_objects: Dict[str, List[Dataset]]) -> None:
        """
        Store Key Object files for later matching.
        
        Args:
            key_objects: Dictionary keyed by StudyInstanceUID containing lists of Key Object datasets
        """
        self.key_objects = key_objects
    
    def get_annotations_for_image(self, dataset: Dataset, study_uid: str) -> List[Dict]:
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
                print(f"[ANNOTATIONS] Image has no SOPInstanceUID, skipping annotation lookup")
                return annotations
            
            image_uid = str(dataset.SOPInstanceUID)
            series_uid = getattr(dataset, 'SeriesInstanceUID', '')
            print(f"[ANNOTATIONS] Looking for annotations for image UID: {image_uid[:30]}..., series: {series_uid[:30]}...")
            
            # Check for embedded annotations in the image file itself
            embedded_annotations = self._get_embedded_annotations(dataset)
            if embedded_annotations:
                print(f"[ANNOTATIONS] Found {len(embedded_annotations)} embedded annotation(s) in image file")
                annotations.extend(embedded_annotations)
            
            # Check Presentation States for this study
            if study_uid in self.presentation_states:
                print(f"[ANNOTATIONS] Checking {len(self.presentation_states[study_uid])} Presentation State(s) for study {study_uid[:20]}...")
                for idx, ps_dataset in enumerate(self.presentation_states[study_uid]):
                    parsed_ps = self.presentation_state_handler.parse_presentation_state(ps_dataset)
                    
                    ref_info = parsed_ps['referenced_images']
                    image_uids = ref_info.get('image_uids', [])
                    series_uids = ref_info.get('series_uids', [])
                    
                    # Check if this Presentation State references our image (image-level or series-level)
                    matches = False
                    if image_uid in image_uids:
                        print(f"[ANNOTATIONS] Presentation State {idx} matches image UID (image-level reference)")
                        matches = True
                    elif series_uid in series_uids:
                        print(f"[ANNOTATIONS] Presentation State {idx} matches series UID (series-level reference)")
                        matches = True
                    
                    if matches:
                        print(f"[ANNOTATIONS] Presentation State {idx} matches, adding {len(parsed_ps['annotations'])} annotation(s)")
                        # Add annotations from this Presentation State
                        for ann in parsed_ps['annotations']:
                            ann['source'] = 'presentation_state'
                            annotations.append(ann)
                    else:
                        print(f"[ANNOTATIONS] Presentation State {idx} references {len(image_uids)} image(s) and {len(series_uids)} series, but not this one")
            else:
                print(f"[ANNOTATIONS] No Presentation States found for study {study_uid[:20]}...")
            
            # Check Key Objects for this study
            if study_uid in self.key_objects:
                print(f"[ANNOTATIONS] Checking {len(self.key_objects[study_uid])} Key Object(s) for study {study_uid[:20]}...")
                for idx, ko_dataset in enumerate(self.key_objects[study_uid]):
                    parsed_ko = self.key_object_handler.parse_key_object(ko_dataset)
                    
                    # Key Objects reference images through ContentSequence
                    # For now, check if image UID is in referenced_images list
                    # Future: could also check for series-level references
                    ref_images = parsed_ko.get('referenced_images', [])
                    if image_uid in ref_images:
                        print(f"[ANNOTATIONS] Key Object {idx} matches image UID, adding {len(parsed_ko['annotations'])} annotation(s)")
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
                    else:
                        print(f"[ANNOTATIONS] Key Object {idx} references {len(ref_images)} image(s), but not this one")
            else:
                print(f"[ANNOTATIONS] No Key Objects found for study {study_uid[:20]}...")
        except Exception as e:
            import traceback
            print(f"[ANNOTATIONS] Error getting annotations for image: {e}")
            traceback.print_exc()
        
        return annotations
    
    def create_presentation_state_items(self, scene, annotations: List[Dict], 
                                       image_width: float, image_height: float) -> List[QGraphicsItem]:
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
        items = []
        
        try:
            for ann in annotations:
                ann_type = ann.get('type', '')
                coords = ann.get('coordinates', [])
                color = ann.get('color', (255, 255, 0))
                units = ann.get('units', 'PIXEL')
                
                # Transform coordinates based on units
                transformed_coords = self._transform_coordinates(coords, units, image_width, image_height)
                if not transformed_coords:
                    print(f"[ANNOTATIONS] Skipping annotation with no valid coordinates after transformation")
                    continue
                
                # Convert color tuple to QColor
                if isinstance(color, tuple) and len(color) >= 3:
                    qcolor = QColor(color[0], color[1], color[2])
                else:
                    qcolor = QColor(255, 255, 0)  # Default yellow
                
                pen = QPen(qcolor, 2)
                
                # Use transformed coordinates
                coords = transformed_coords
                
                if ann_type == 'TEXT':
                    # Create text item
                    text = ann.get('text', '')
                    if text and coords:
                        text_item = QGraphicsTextItem(text)
                        text_item.setDefaultTextColor(qcolor)
                        if coords:
                            x, y = coords[0][0], coords[0][1]
                            # Bounds check
                            if 0 <= x <= image_width and 0 <= y <= image_height:
                                text_item.setPos(QPointF(x, y))
                                text_item.setZValue(200)  # Above image
                                text_item.setVisible(True)
                                scene.addItem(text_item)
                                items.append(text_item)
                                self.annotations.append(text_item)
                            else:
                                print(f"[ANNOTATIONS] Text annotation out of bounds: ({x}, {y})")
                
                elif ann_type == 'POLYLINE':
                    # Create polyline (path)
                    if len(coords) >= 2:
                        path = QPainterPath()
                        # Check if first point is in bounds
                        first_x, first_y = coords[0][0], coords[0][1]
                        if 0 <= first_x <= image_width and 0 <= first_y <= image_height:
                            path.moveTo(QPointF(first_x, first_y))
                            for i in range(1, len(coords)):
                                x, y = coords[i][0], coords[i][1]
                                path.lineTo(QPointF(x, y))
                            
                            path_item = QGraphicsPathItem(path)
                            path_item.setPen(pen)
                            path_item.setZValue(200)  # Above image
                            path_item.setVisible(True)
                            scene.addItem(path_item)
                            items.append(path_item)
                            self.annotations.append(path_item)
                        else:
                            print(f"[ANNOTATIONS] Polyline annotation out of bounds: ({first_x}, {first_y})")
                
                elif ann_type == 'CIRCLE':
                    # Create circle
                    if len(coords) >= 2:
                        center = coords[0]
                        point_on_circle = coords[1]
                        
                        # Calculate radius
                        dx = point_on_circle[0] - center[0]
                        dy = point_on_circle[1] - center[1]
                        radius = (dx * dx + dy * dy) ** 0.5
                        
                        # Bounds check (allow some margin for circles extending beyond image)
                        if -radius <= center[0] <= image_width + radius and -radius <= center[1] <= image_height + radius:
                            ellipse_item = QGraphicsEllipseItem(
                                center[0] - radius, center[1] - radius,
                                2 * radius, 2 * radius
                            )
                            ellipse_item.setPen(pen)
                            ellipse_item.setBrush(QBrush(Qt.BrushStyle.NoBrush))
                            ellipse_item.setZValue(200)  # Above image
                            ellipse_item.setVisible(True)
                            scene.addItem(ellipse_item)
                            items.append(ellipse_item)
                            self.annotations.append(ellipse_item)
                        else:
                            print(f"[ANNOTATIONS] Circle annotation out of bounds: center=({center[0]}, {center[1]})")
                
                elif ann_type == 'ELLIPSE':
                    # Create ellipse (simplified - using bounding box)
                    if len(coords) >= 3:
                        # Use first three points to define ellipse
                        # This is simplified - proper ellipse would need more calculation
                        min_x = min(c[0] for c in coords)
                        max_x = max(c[0] for c in coords)
                        min_y = min(c[1] for c in coords)
                        max_y = max(c[1] for c in coords)
                        
                        # Bounds check
                        if -100 <= min_x <= image_width + 100 and -100 <= min_y <= image_height + 100:
                            ellipse_item = QGraphicsEllipseItem(
                                min_x, min_y,
                                max_x - min_x, max_y - min_y
                            )
                            ellipse_item.setPen(pen)
                            ellipse_item.setBrush(QBrush(Qt.BrushStyle.NoBrush))
                            ellipse_item.setZValue(200)  # Above image
                            ellipse_item.setVisible(True)
                            scene.addItem(ellipse_item)
                            items.append(ellipse_item)
                            self.annotations.append(ellipse_item)
                        else:
                            print(f"[ANNOTATIONS] Ellipse annotation out of bounds: ({min_x}, {min_y}) to ({max_x}, {max_y})")
                
                elif ann_type == 'POINT':
                    # Create point (small circle)
                    if coords:
                        point = coords[0]
                        radius = 3  # Small radius for point
                        x, y = point[0], point[1]
                        # Bounds check
                        if 0 <= x <= image_width and 0 <= y <= image_height:
                            ellipse_item = QGraphicsEllipseItem(
                                x - radius, y - radius,
                                2 * radius, 2 * radius
                            )
                            ellipse_item.setPen(pen)
                            ellipse_item.setBrush(QBrush(qcolor))
                            ellipse_item.setZValue(200)  # Above image
                            ellipse_item.setVisible(True)
                            scene.addItem(ellipse_item)
                            items.append(ellipse_item)
                            self.annotations.append(ellipse_item)
                        else:
                            print(f"[ANNOTATIONS] Point annotation out of bounds: ({x}, {y})")
                
                elif ann_type == 'OVERLAY':
                    # Render overlay graphics from bitmap
                    overlay_rows = ann.get('overlay_rows', 0)
                    overlay_cols = ann.get('overlay_cols', 0)
                    overlay_origin_x = ann.get('overlay_origin_x', 0)
                    overlay_origin_y = ann.get('overlay_origin_y', 0)
                    overlay_paths = ann.get('paths', [])
                    overlay_data = ann.get('overlay_data', None)
                    
                    # Try bitmap rendering first for better quality
                    if overlay_data is not None and overlay_rows > 0 and overlay_cols > 0:
                        bitmap_item = self._create_overlay_bitmap_item(
                            overlay_data, overlay_cols, overlay_rows,
                            overlay_origin_x, overlay_origin_y, qcolor
                        )
                        if bitmap_item:
                            print(f"[ANNOTATIONS] Created overlay bitmap item")
                            scene.addItem(bitmap_item)
                            items.append(bitmap_item)
                            self.annotations.append(bitmap_item)
                        else:
                            # Fallback to path rendering if bitmap fails
                            print(f"[ANNOTATIONS] Bitmap rendering failed, falling back to paths")
                            self._render_overlay_paths(
                                overlay_paths, coords, overlay_paths, pen, qcolor, scene, items
                            )
                    else:
                        # Render paths (connected components)
                        self._render_overlay_paths(
                            overlay_paths, coords, overlay_paths, pen, qcolor, scene, items
                        )
                    
                    if overlay_rows > 0 and overlay_cols > 0:
                        print(f"[ANNOTATIONS] Created overlay graphics: {len(overlay_paths)} path(s), size: {overlay_cols}x{overlay_rows}, origin: ({overlay_origin_x}, {overlay_origin_y})")
        except Exception as e:
            import traceback
            print(f"[ANNOTATIONS] Error creating presentation state items: {e}")
            traceback.print_exc()
        
        return items
    
    def _transform_coordinates(self, coords: List[tuple], units: str, 
                               image_width: float, image_height: float) -> List[tuple]:
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
                print(f"[ANNOTATIONS] Unknown coordinate units '{units}', treating as PIXEL")
                transformed = [(float(c[0]), float(c[1])) for c in coords if len(c) >= 2]
        except Exception as e:
            print(f"[ANNOTATIONS] Error transforming coordinates: {e}")
            return []
        
        return transformed
    
    def _get_embedded_annotations(self, dataset: Dataset) -> List[Dict]:
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
                print(f"[ANNOTATIONS] Found GraphicAnnotationSequence in image file")
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
        except Exception as e:
            import traceback
            print(f"[ANNOTATIONS] Error extracting embedded annotations: {e}")
            traceback.print_exc()
        
        return annotations
    
    def _parse_overlay_data(self, dataset: Dataset) -> List[Dict]:
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
                overlay_type_tag = (overlay_group, 0x0040)  # OverlayType
                
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
                overlay_type = dataset.get(overlay_type_tag, 'G')
                
                # Get overlay type value properly
                if hasattr(overlay_type, 'value'):
                    overlay_type_val = str(overlay_type.value)
                elif isinstance(overlay_type, str):
                    overlay_type_val = overlay_type
                else:
                    overlay_type_val = 'G'
                
                if overlay_rows and overlay_cols:
                    rows_val = int(overlay_rows.value) if hasattr(overlay_rows, 'value') else int(overlay_rows)
                    cols_val = int(overlay_cols.value) if hasattr(overlay_cols, 'value') else int(overlay_cols)
                    
                    # Parse OverlayOrigin - stored as [row, column] pair (1-based indexing)
                    # Default to [1, 1] per DICOM standard if missing
                    if overlay_origin:
                        origin_value = overlay_origin.value if hasattr(overlay_origin, 'value') else overlay_origin
                        if isinstance(origin_value, (list, tuple)) and len(origin_value) >= 2:
                            origin_row = int(origin_value[0])  # Row (y coordinate)
                            origin_col = int(origin_value[1])  # Column (x coordinate)
                        else:
                            origin_row = 1
                            origin_col = 1
                    else:
                        origin_row = 1
                        origin_col = 1
                    
                    # Convert to 0-based coordinates (DICOM uses 1-based)
                    # OverlayOrigin is [row, column] = [y, x] in DICOM
                    # DICOM uses 1-based indexing, Qt uses 0-based
                    origin_x = float(origin_col - 1)  # Column = x (horizontal)
                    origin_y = float(origin_row - 1)  # Row = y (vertical)
                    
                    print(f"[ANNOTATIONS] Found overlay group {overlay_group:04X}: {cols_val}x{rows_val}, type={overlay_type_val}")
                    print(f"[ANNOTATIONS] OverlayOrigin (DICOM 1-based): row={origin_row}, col={origin_col}")
                    print(f"[ANNOTATIONS] OverlayOrigin (Qt 0-based): x={origin_x}, y={origin_y}")
                    
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
        except Exception as e:
            import traceback
            print(f"[ANNOTATIONS] Error parsing overlay data: {e}")
            traceback.print_exc()
        
        return overlays
    
    def _convert_overlay_bitmap_to_graphics(self, overlay_data, cols: int, rows: int, 
                                           origin_x: float, origin_y: float) -> Dict:
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
        coordinates = []
        paths = []
        
        try:
            import numpy as np
            
            # Convert overlay data to numpy array
            # pydicom may return overlay data as bytes, bytearray, or pydicom DataElement
            overlay_bytes = None
            
            if hasattr(overlay_data, 'value'):
                # pydicom DataElement
                overlay_bytes = overlay_data.value
            elif isinstance(overlay_data, (bytes, bytearray)):
                overlay_bytes = bytes(overlay_data)
            elif isinstance(overlay_data, pydicom.valuerep.OBvalue):
                overlay_bytes = bytes(overlay_data)
            elif isinstance(overlay_data, pydicom.valuerep.OWvalue):
                overlay_bytes = bytes(overlay_data)
            else:
                # Try to convert to bytes
                try:
                    overlay_bytes = bytes(overlay_data)
                except Exception as e:
                    print(f"[ANNOTATIONS] Could not convert overlay data to bytes: {e}, type: {type(overlay_data)}")
                    return {'coordinates': [], 'paths': []}
            
            if overlay_bytes:
                # Convert bytes to numpy array
                # Overlay data is packed: 1 bit per pixel
                num_bits = cols * rows
                num_bytes = (num_bits + 7) // 8  # Round up to nearest byte
                
                # Ensure we have enough bytes
                if len(overlay_bytes) < num_bytes:
                    print(f"[ANNOTATIONS] Overlay data too short: got {len(overlay_bytes)} bytes, expected at least {num_bytes}")
                    # Try to use what we have
                    num_bytes = len(overlay_bytes)
                    num_bits = num_bytes * 8
                    if num_bits > cols * rows:
                        num_bits = cols * rows
                
                # Convert bytes to bit array
                # DICOM overlay data uses LSB-first bit order per DICOM standard Part 5, Chapter 8
                # First bit stored in LSB of first byte, next bits in increasing MSB positions
                # Use bitorder='little' (default) to unpack LSB-to-MSB within each byte
                bit_array = np.unpackbits(np.frombuffer(overlay_bytes[:num_bytes], dtype=np.uint8), bitorder='little')
                # Reshape to image dimensions (only use the bits we need)
                if len(bit_array) >= num_bits:
                    bitmap = bit_array[:num_bits].reshape((rows, cols))
                else:
                    print(f"[ANNOTATIONS] Bit array too short: got {len(bit_array)} bits, expected {num_bits}")
                    return {'coordinates': [], 'paths': []}
            else:
                # If we didn't get bytes, try other formats
                if isinstance(overlay_data, (list, tuple)):
                    # Already a list/array
                    bitmap = np.array(overlay_data, dtype=np.uint8)
                    if bitmap.size == cols * rows:
                        bitmap = bitmap.reshape((rows, cols))
                    else:
                        print(f"[ANNOTATIONS] Overlay data size mismatch: expected {cols*rows}, got {bitmap.size}")
                        return {'coordinates': [], 'paths': []}
                else:
                    # Try to convert to numpy array
                    try:
                        bitmap = np.array(overlay_data, dtype=np.uint8)
                        if bitmap.size == cols * rows:
                            bitmap = bitmap.reshape((rows, cols))
                        else:
                            print(f"[ANNOTATIONS] Overlay data size mismatch: expected {cols*rows}, got {bitmap.size}")
                            return {'coordinates': [], 'paths': []}
                    except Exception as e:
                        print(f"[ANNOTATIONS] Could not convert overlay data to array: {e}, type: {type(overlay_data)}")
                        return {'coordinates': [], 'paths': []}
            
            # Bitmap positions are correct - no flip needed
            # DICOM overlay data: bits packed LSB-first within each byte, bytes stored sequentially
            # Character reversal is fixed by using LSB-first bit order (bitorder='little') per DICOM standard Part 5, Chapter 8
            
            # Find set pixels (value > 0)
            set_pixels = np.argwhere(bitmap > 0)
            
            if len(set_pixels) == 0:
                print(f"[ANNOTATIONS] No set pixels found in overlay bitmap")
                return {'coordinates': [], 'paths': []}
            
            print(f"[ANNOTATIONS] Found {len(set_pixels)} set pixels in overlay bitmap")
            
            # Convert pixel coordinates to image coordinates
            # Overlay bitmap coordinates: (row, col) where row=y-axis, col=x-axis
            # DICOM: row increases downward (top to bottom), col increases rightward (left to right)
            # Qt: y increases downward, x increases rightward
            # Bitmap positions are correct - no flip needed, character reversal fixed by bit order
            print(f"[ANNOTATIONS] Converting {len(set_pixels)} pixels to image coordinates")
            print(f"[ANNOTATIONS] Origin offset: x={origin_x}, y={origin_y}")
            print(f"[ANNOTATIONS] Bitmap dimensions: cols={cols}, rows={rows}")
            print(f"[ANNOTATIONS] Using LSB-first bit order (bitorder='little') per DICOM standard Part 5, Chapter 8")
            
            # Sample first few pixels for debugging
            sample_pixels = min(5, len(set_pixels))
            for i, pixel in enumerate(set_pixels[:sample_pixels]):
                row, col = pixel[0], pixel[1]
                x = float(col) + origin_x
                y = float(row) + origin_y
                print(f"[ANNOTATIONS] Sample pixel {i}: bitmap(row={row}, col={col}) -> image(x={x:.1f}, y={y:.1f})")
            
            for pixel in set_pixels:
                row, col = pixel[0], pixel[1]
                # Convert to image coordinates: overlay_coord + origin
                x = float(col) + origin_x
                y = float(row) + origin_y
                coordinates.append((x, y))
            
            # Group connected pixels into paths
            # Use contour extraction for smoother paths
            try:
                # Try OpenCV for better contour extraction
                try:
                    import cv2
                    # Find contours (external contours only for now)
                    contours, _ = cv2.findContours(
                        (bitmap > 0).astype(np.uint8) * 255,
                        cv2.RETR_EXTERNAL,
                        cv2.CHAIN_APPROX_SIMPLE
                    )
                    
                    print(f"[ANNOTATIONS] Found {len(contours)} contour(s) using OpenCV")
                    
                    # Convert contours to paths
                    # OpenCV contours return points as (x, y) = (column, row) in bitmap space
                    for idx, contour in enumerate(contours):
                        if len(contour) >= 3:  # Need at least 3 points for a path
                            # Simplify contour (reduce points while preserving shape)
                            epsilon = 0.5  # Simplification factor
                            simplified = cv2.approxPolyDP(contour, epsilon, closed=True)
                            
                            # Convert to image coordinates
                            # OpenCV point format: point[0] = [x, y] = [col, row]
                            # Bitmap positions are correct - no flip needed
                            path_coords = []
                            for point_idx, point in enumerate(simplified):
                                # OpenCV returns (x, y) = (col, row) from bitmap
                                col = point[0][0]  # x coordinate in bitmap = column
                                row = point[0][1]  # y coordinate in bitmap = row
                                x = float(col) + origin_x
                                y = float(row) + origin_y
                                path_coords.append((x, y))
                                
                                # Debug: show first point of first contour
                                if idx == 0 and point_idx == 0:
                                    print(f"[ANNOTATIONS] First contour point: OpenCV(col={col}, row={row}) -> image(x={x:.1f}, y={y:.1f})")
                                    print(f"[ANNOTATIONS] Using LSB-first bit order per DICOM standard Part 5, Chapter 8")
                            
                            if len(path_coords) >= 2:
                                paths.append(path_coords)
                                if idx == 0:
                                    print(f"[ANNOTATIONS] First contour has {len(path_coords)} points")
                except ImportError:
                    # OpenCV not available, use scipy connected components
                    from scipy import ndimage
                    # Label connected components
                    labeled, num_features = ndimage.label(bitmap > 0)
                    
                    print(f"[ANNOTATIONS] Found {num_features} connected component(s) using scipy")
                    
                    # Extract paths for each component
                    for label_id in range(1, num_features + 1):
                        component_pixels = np.argwhere(labeled == label_id)
                        
                        # Filter out very small components (likely noise)
                        if len(component_pixels) < 3:
                            continue
                        
                        # Extract contour using marching squares or simple boundary tracing
                        # For now, use sorted pixels but try to create smoother paths
                        # Sort pixels to create a more coherent path
                        component_pixels = component_pixels[np.lexsort((component_pixels[:, 1], component_pixels[:, 0]))]
                        
                        # Simplify: take every Nth point for large paths
                        if len(component_pixels) > 100:
                            step = max(1, len(component_pixels) // 100)
                            component_pixels = component_pixels[::step]
                        
                        # Convert to image coordinates
                        # Bitmap positions are correct - no flip needed
                        path_coords = []
                        for pixel_idx, pixel in enumerate(component_pixels):
                            row, col = pixel[0], pixel[1]
                            x = float(col) + origin_x
                            y = float(row) + origin_y
                            path_coords.append((x, y))
                            
                            # Debug: show first point of first component
                            if label_id == 1 and pixel_idx == 0:
                                print(f"[ANNOTATIONS] First scipy component point: bitmap(row={row}, col={col}) -> image(x={x:.1f}, y={y:.1f})")
                                print(f"[ANNOTATIONS] Using LSB-first bit order per DICOM standard Part 5, Chapter 8")
                        
                        if len(path_coords) >= 2:
                            paths.append(path_coords)
            except ImportError:
                # Neither OpenCV nor scipy available, skip path extraction
                print(f"[ANNOTATIONS] OpenCV and scipy not available, skipping path extraction")
            except Exception as e:
                import traceback
                print(f"[ANNOTATIONS] Error extracting paths: {e}")
                traceback.print_exc()
        
        except ImportError:
            # numpy not available, use simple approach
            print(f"[ANNOTATIONS] numpy not available, using simple pixel extraction")
            # Fallback: just extract individual pixels
            if isinstance(overlay_data, bytes):
                # Simple byte-by-byte extraction
                byte_idx = 0
                bit_idx = 0
                for row in range(rows):
                    for col in range(cols):
                        if byte_idx < len(overlay_data):
                            byte_val = overlay_data[byte_idx]
                            bit_val = (byte_val >> (7 - bit_idx)) & 1
                            if bit_val:
                                x = float(col) + origin_x
                                y = float(row) + origin_y
                                coordinates.append((x, y))
                            
                            bit_idx += 1
                            if bit_idx >= 8:
                                bit_idx = 0
                                byte_idx += 1
        except Exception as e:
            import traceback
            print(f"[ANNOTATIONS] Error converting overlay bitmap: {e}")
            traceback.print_exc()
        
        return {'coordinates': coordinates, 'paths': paths}
    
    def _create_overlay_bitmap_item(self, overlay_data, cols: int, rows: int,
                                    origin_x: float, origin_y: float, color: QColor) -> Optional[QGraphicsItem]:
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
            from PySide6.QtWidgets import QGraphicsPixmapItem
            from PySide6.QtGui import QImage, QPixmap
            
            # Convert overlay data to numpy array (same logic as _convert_overlay_bitmap_to_graphics)
            overlay_bytes = None
            
            if hasattr(overlay_data, 'value'):
                overlay_bytes = overlay_data.value
            elif isinstance(overlay_data, (bytes, bytearray)):
                overlay_bytes = bytes(overlay_data)
            elif isinstance(overlay_data, pydicom.valuerep.OBvalue):
                overlay_bytes = bytes(overlay_data)
            elif isinstance(overlay_data, pydicom.valuerep.OWvalue):
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
            
            # Debug: Show bitmap info
            print(f"[ANNOTATIONS] Bitmap shape: {bitmap.shape} (rows={rows}, cols={cols})")
            print(f"[ANNOTATIONS] Bitmap origin: ({origin_x}, {origin_y})")
            print(f"[ANNOTATIONS] Using LSB-first bit order (bitorder='little') per DICOM standard Part 5, Chapter 8")
            # Show sample of first few pixels
            if bitmap.size > 0:
                sample_size = min(10, cols)
                print(f"[ANNOTATIONS] First row sample (first {sample_size} pixels): {bitmap[0, :sample_size].tolist()}")
                if rows > 1:
                    print(f"[ANNOTATIONS] Last row sample (first {sample_size} pixels): {bitmap[-1, :sample_size].tolist()}")
            
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
            pixmap_item.setZValue(200)
            pixmap_item.setVisible(True)
            
            print(f"[ANNOTATIONS] Created overlay bitmap: {width}x{height} at ({origin_x}, {origin_y})")
            
            return pixmap_item
            
        except ImportError:
            print(f"[ANNOTATIONS] numpy or Qt not available for bitmap rendering")
            return None
        except Exception as e:
            import traceback
            print(f"[ANNOTATIONS] Error creating overlay bitmap: {e}")
            traceback.print_exc()
            return None
    
    def _render_overlay_paths(self, overlay_paths: List[List[tuple]], coords: List[tuple],
                              paths: List[List[tuple]], pen: QPen, color: QColor,
                              scene, items: List) -> None:
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
            
            print(f"[ANNOTATIONS] Rendering {len(filtered_paths)} filtered overlay path(s) (filtered from {len(overlay_paths)})")
            
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
                    path_item.setZValue(200)
                    path_item.setVisible(True)
                    scene.addItem(path_item)
                    items.append(path_item)
                    self.annotations.append(path_item)
        
        # Render individual points only if no paths
        if coords and len(coords) > 0 and not overlay_paths:
            print(f"[ANNOTATIONS] Rendering {len(coords)} overlay point(s)")
            for coord in coords:
                x, y = coord[0], coord[1]
                # Create slightly larger circles for better visibility
                point_item = QGraphicsEllipseItem(
                    x - 2, y - 2,
                    4, 4
                )
                point_item.setPen(thick_pen)
                point_item.setBrush(QBrush(color))
                point_item.setZValue(200)
                point_item.setVisible(True)
                scene.addItem(point_item)
                items.append(point_item)
                self.annotations.append(point_item)
    
    def clear_annotations(self, scene) -> None:
        """
        Clear all annotations from scene.
        
        Args:
            scene: QGraphicsScene to remove items from
        """
        for item in self.annotations:
            scene.removeItem(item)
        self.annotations.clear()


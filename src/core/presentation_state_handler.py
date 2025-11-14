"""
DICOM Presentation State Handler

This module handles parsing and extracting annotations from DICOM Presentation State files.
Presentation States contain graphic annotations, display settings, and references to images.

Inputs:
    - DICOM Presentation State datasets (Grayscale or Color Softcopy Presentation State Storage)
    
Outputs:
    - Parsed annotations (text, lines, circles, ellipses, points)
    - Display settings (window/level, zoom, pan, rotation)
    - Referenced image UIDs
    
Requirements:
    - pydicom library
    - typing for type hints
"""

from typing import Dict, List, Optional, Any
from pydicom.dataset import Dataset


class PresentationStateHandler:
    """
    Handles parsing of DICOM Presentation State files.
    
    Features:
    - Parse graphic annotations
    - Extract display settings
    - Get referenced images
    """
    
    def __init__(self):
        """Initialize the Presentation State handler."""
        pass
    
    def parse_presentation_state(self, dataset: Dataset) -> Dict[str, Any]:
        """
        Parse a Presentation State dataset and extract all relevant information.
        
        Args:
            dataset: pydicom Dataset with Presentation State data
            
        Returns:
            Dictionary containing:
            - 'annotations': List of annotation dictionaries
            - 'display_settings': Dictionary of display settings
            - 'referenced_images': List of referenced SOP Instance UIDs
        """
        result = {
            'annotations': [],
            'display_settings': {},
            'referenced_images': {'image_uids': [], 'series_uids': []}
        }
        
        # Get referenced images
        result['referenced_images'] = self.get_referenced_images(dataset)
        print(f"[ANNOTATIONS] Parsed Presentation State: {len(result['referenced_images']['image_uids'])} referenced image(s), {len(result['referenced_images']['series_uids'])} referenced series")
        
        # Parse graphic annotations
        if hasattr(dataset, 'GraphicAnnotationSequence'):
            result['annotations'] = self.parse_graphic_annotations(dataset.GraphicAnnotationSequence)
            print(f"[ANNOTATIONS] Parsed {len(result['annotations'])} annotation(s) from Presentation State")
            if result['annotations']:
                types = [ann.get('type', 'UNKNOWN') for ann in result['annotations']]
                print(f"[ANNOTATIONS] Annotation types: {', '.join(set(types))}")
        else:
            print(f"[ANNOTATIONS] No GraphicAnnotationSequence found in Presentation State")
        
        # Parse display settings
        result['display_settings'] = self.parse_display_settings(dataset)
        
        return result
    
    def get_referenced_images(self, dataset: Dataset) -> Dict[str, Any]:
        """
        Extract referenced image SOP Instance UIDs from Presentation State.
        
        Args:
            dataset: pydicom Dataset with Presentation State data
            
        Returns:
            Dictionary with:
            - 'image_uids': List of referenced SOP Instance UIDs (for image-level references)
            - 'series_uids': List of referenced Series Instance UIDs (for series-level references)
        """
        result = {
            'image_uids': [],
            'series_uids': []
        }
        
        try:
            # Check for image-level references
            if hasattr(dataset, 'ReferencedImageSequence'):
                ref_seq = dataset.ReferencedImageSequence
                for ref_item in ref_seq:
                    if hasattr(ref_item, 'ReferencedSOPInstanceUID'):
                        result['image_uids'].append(str(ref_item.ReferencedSOPInstanceUID))
            
            # Check for series-level references
            if hasattr(dataset, 'ReferencedSeriesSequence'):
                ref_seq = dataset.ReferencedSeriesSequence
                for ref_item in ref_seq:
                    if hasattr(ref_item, 'SeriesInstanceUID'):
                        series_uid = str(ref_item.SeriesInstanceUID)
                        if series_uid not in result['series_uids']:
                            result['series_uids'].append(series_uid)
                            print(f"[ANNOTATIONS] Presentation State references series: {series_uid[:30]}...")
        except Exception as e:
            print(f"[ANNOTATIONS] Error extracting referenced images: {e}")
        
        return result
    
    def parse_graphic_annotations(self, graphic_annotation_seq) -> List[Dict[str, Any]]:
        """
        Parse GraphicAnnotationSequence to extract graphic annotations.
        
        Args:
            graphic_annotation_seq: GraphicAnnotationSequence from dataset
            
        Returns:
            List of annotation dictionaries, each containing:
            - 'type': Graphic type (TEXT, POLYLINE, CIRCLE, ELLIPSE, POINT)
            - 'coordinates': List of coordinate tuples
            - 'text': Text content (if type is TEXT)
            - 'color': Color tuple (r, g, b) or grayscale value
            - 'layer': Layer name
            - 'units': Coordinate units ('PIXEL', 'DISPLAY', 'NORMALIZED')
        """
        annotations = []
        
        try:
            for annotation_item in graphic_annotation_seq:
                # Get graphic layer (if present)
                layer_name = ""
                if hasattr(annotation_item, 'GraphicLayer'):
                    layer_name = str(annotation_item.GraphicLayer)
                
                # Get annotation units (coordinate system)
                annotation_units = 'PIXEL'  # Default
                if hasattr(annotation_item, 'GraphicAnnotationUnits'):
                    annotation_units = str(annotation_item.GraphicAnnotationUnits)
                    print(f"[ANNOTATIONS] GraphicAnnotationUnits: {annotation_units}")
                
                # Get graphic objects
                if hasattr(annotation_item, 'GraphicObjectSequence'):
                    graphic_obj_seq = annotation_item.GraphicObjectSequence
                    
                    for graphic_obj in graphic_obj_seq:
                        annotation = {
                            'type': '',
                            'coordinates': [],
                            'text': '',
                            'color': (255, 255, 0),  # Default yellow
                            'layer': layer_name,
                            'units': annotation_units
                        }
                        
                        # Get graphic type
                        if hasattr(graphic_obj, 'GraphicType'):
                            annotation['type'] = str(graphic_obj.GraphicType)
                        
                        # Get graphic data (coordinates)
                        if hasattr(graphic_obj, 'GraphicData'):
                            coords = self._parse_graphic_data(graphic_obj.GraphicData, annotation['type'])
                            annotation['coordinates'] = coords
                        
                        # Get text content if this is a text annotation
                        if annotation['type'] == 'TEXT' and hasattr(annotation_item, 'TextObjectSequence'):
                            text_seq = annotation_item.TextObjectSequence
                            for text_obj in text_seq:
                                if hasattr(text_obj, 'UnformattedTextValue'):
                                    annotation['text'] = str(text_obj.UnformattedTextValue)
                                elif hasattr(text_obj, 'BoundingBoxAnnotationUnits'):
                                    # Text might be in bounding box
                                    if hasattr(text_obj, 'BoundingBoxTopLeftHandCorner'):
                                        annotation['coordinates'] = self._parse_bounding_box(
                                            text_obj.BoundingBoxTopLeftHandCorner,
                                            getattr(text_obj, 'BoundingBoxBottomRightHandCorner', None)
                                        )
                        
                        # Get color from graphic layer (if available)
                        # This would need to be looked up from GraphicLayerSequence
                        # For now, use default color
                        
                        if annotation['type']:  # Only add if we have a type
                            annotations.append(annotation)
        except Exception as e:
            print(f"Error parsing graphic annotations: {e}")
        
        return annotations
    
    def _parse_graphic_data(self, graphic_data: List[float], graphic_type: str) -> List[tuple]:
        """
        Parse GraphicData coordinates based on graphic type.
        
        Args:
            graphic_data: List of coordinate values
            graphic_type: Type of graphic (TEXT, POLYLINE, CIRCLE, ELLIPSE, POINT)
            
        Returns:
            List of coordinate tuples
        """
        coords = []
        
        try:
            if graphic_type == 'POINT':
                # Point: single (x, y) pair
                if len(graphic_data) >= 2:
                    coords.append((float(graphic_data[0]), float(graphic_data[1])))
            elif graphic_type == 'CIRCLE':
                # Circle: center (x, y) and point on circumference (x, y)
                if len(graphic_data) >= 4:
                    coords.append((float(graphic_data[0]), float(graphic_data[1])))  # Center
                    coords.append((float(graphic_data[2]), float(graphic_data[3])))  # Point on circle
            elif graphic_type == 'ELLIPSE':
                # Ellipse: center (x, y) and two points on ellipse
                if len(graphic_data) >= 6:
                    coords.append((float(graphic_data[0]), float(graphic_data[1])))  # Center
                    coords.append((float(graphic_data[2]), float(graphic_data[3])))  # Point 1
                    coords.append((float(graphic_data[4]), float(graphic_data[5])))  # Point 2
            elif graphic_type in ['POLYLINE', 'TEXT']:
                # Polyline/Text: series of (x, y) pairs
                for i in range(0, len(graphic_data), 2):
                    if i + 1 < len(graphic_data):
                        coords.append((float(graphic_data[i]), float(graphic_data[i + 1])))
        except Exception as e:
            print(f"Error parsing graphic data: {e}")
        
        return coords
    
    def _parse_bounding_box(self, top_left, bottom_right) -> List[tuple]:
        """
        Parse bounding box coordinates for text annotations.
        
        Args:
            top_left: Top-left corner coordinates
            bottom_right: Bottom-right corner coordinates
            
        Returns:
            List of coordinate tuples representing bounding box
        """
        coords = []
        
        try:
            if top_left and len(top_left) >= 2:
                coords.append((float(top_left[0]), float(top_left[1])))
            if bottom_right and len(bottom_right) >= 2:
                coords.append((float(bottom_right[0]), float(bottom_right[1])))
        except Exception as e:
            print(f"Error parsing bounding box: {e}")
        
        return coords
    
    def parse_display_settings(self, dataset: Dataset) -> Dict[str, Any]:
        """
        Extract display settings from Presentation State.
        
        Args:
            dataset: pydicom Dataset with Presentation State data
            
        Returns:
            Dictionary containing:
            - 'window_center': Window center value
            - 'window_width': Window width value
            - 'zoom': Zoom factor
            - 'pan': Pan offset (x, y)
            - 'rotation': Rotation angle
        """
        settings = {}
        
        try:
            # Window/Level settings
            if hasattr(dataset, 'WindowCenter'):
                window_center = dataset.WindowCenter
                if isinstance(window_center, (list, tuple)) and len(window_center) > 0:
                    settings['window_center'] = float(window_center[0])
                else:
                    settings['window_center'] = float(window_center)
            
            if hasattr(dataset, 'WindowWidth'):
                window_width = dataset.WindowWidth
                if isinstance(window_width, (list, tuple)) and len(window_width) > 0:
                    settings['window_width'] = float(window_width[0])
                else:
                    settings['window_width'] = float(window_width)
            
            # Displayed area selection (zoom/pan)
            if hasattr(dataset, 'DisplayedAreaSelectionSequence'):
                display_seq = dataset.DisplayedAreaSelectionSequence
                if len(display_seq) > 0:
                    display_item = display_seq[0]
                    
                    # Zoom (from PixelSpacing or PresentationPixelSpacing)
                    if hasattr(display_item, 'PresentationPixelSpacing'):
                        # This indicates zoom level
                        spacing = display_item.PresentationPixelSpacing
                        if spacing and len(spacing) >= 2:
                            settings['pixel_spacing'] = (float(spacing[0]), float(spacing[1]))
                    
                    # Pan (from DisplayedAreaTopLeftHandCorner)
                    if hasattr(display_item, 'DisplayedAreaTopLeftHandCorner'):
                        top_left = display_item.DisplayedAreaTopLeftHandCorner
                        if top_left and len(top_left) >= 2:
                            settings['pan'] = (float(top_left[0]), float(top_left[1]))
            
            # Rotation
            if hasattr(dataset, 'ImageRotation'):
                settings['rotation'] = float(dataset.ImageRotation)
        except Exception as e:
            print(f"Error parsing display settings: {e}")
        
        return settings


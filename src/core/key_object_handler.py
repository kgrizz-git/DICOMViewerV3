"""
DICOM Key Object Selection Document Handler

This module handles parsing and extracting annotations from DICOM Key Object Selection Document files.
Key Objects contain references to selected images and annotations/measurements.

Inputs:
    - DICOM Key Object Selection Document datasets
    
Outputs:
    - Parsed annotations and measurements
    - Referenced image UIDs
    
Requirements:
    - pydicom library
    - typing for type hints
"""

from typing import Dict, List, Optional, Any
from pydicom.dataset import Dataset


class KeyObjectHandler:
    """
    Handles parsing of DICOM Key Object Selection Document files.
    
    Features:
    - Parse ContentSequence for annotations
    - Extract referenced images
    - Extract measurements and text annotations
    """
    
    def __init__(self):
        """Initialize the Key Object handler."""
        pass
    
    def parse_key_object(self, dataset: Dataset) -> Dict[str, Any]:
        """
        Parse a Key Object Selection Document dataset and extract all relevant information.
        
        Args:
            dataset: pydicom Dataset with Key Object data
            
        Returns:
            Dictionary containing:
            - 'annotations': List of annotation/measurement dictionaries
            - 'referenced_images': List of referenced SOP Instance UIDs
        """
        result = {
            'annotations': [],
            'referenced_images': []
        }
        
        # Get referenced images
        result['referenced_images'] = self.get_referenced_images(dataset)
        
        # Parse ContentSequence for annotations
        if hasattr(dataset, 'ContentSequence'):
            result['annotations'] = self.parse_content_sequence(dataset.ContentSequence)
        
        return result
    
    def get_referenced_images(self, dataset: Dataset) -> List[str]:
        """
        Extract referenced image SOP Instance UIDs from Key Object.
        
        Args:
            dataset: pydicom Dataset with Key Object data
            
        Returns:
            List of referenced SOP Instance UIDs
        """
        referenced_uids = []
        
        try:
            # Key Objects reference images through ContentSequence
            if hasattr(dataset, 'ContentSequence'):
                referenced_uids = self._extract_uids_from_content_sequence(dataset.ContentSequence)
        except Exception as e:
            print(f"Error extracting referenced images: {e}")
        
        return referenced_uids
    
    def _extract_uids_from_content_sequence(self, content_seq) -> List[str]:
        """
        Recursively extract referenced SOP Instance UIDs from ContentSequence.
        
        Args:
            content_seq: ContentSequence from dataset
            
        Returns:
            List of referenced SOP Instance UIDs
        """
        uids = []
        
        try:
            for content_item in content_seq:
                # Check for ReferencedSOPSequence
                if hasattr(content_item, 'ReferencedSOPSequence'):
                    ref_seq = content_item.ReferencedSOPSequence
                    for ref_item in ref_seq:
                        if hasattr(ref_item, 'ReferencedSOPInstanceUID'):
                            uid = str(ref_item.ReferencedSOPInstanceUID)
                            if uid not in uids:
                                uids.append(uid)
                
                # Recursively check nested ContentSequence
                if hasattr(content_item, 'ContentSequence'):
                    nested_uids = self._extract_uids_from_content_sequence(content_item.ContentSequence)
                    for uid in nested_uids:
                        if uid not in uids:
                            uids.append(uid)
        except Exception as e:
            print(f"Error extracting UIDs from ContentSequence: {e}")
        
        return uids
    
    def parse_content_sequence(self, content_seq) -> List[Dict[str, Any]]:
        """
        Recursively parse ContentSequence to extract annotations and measurements.
        
        Args:
            content_seq: ContentSequence from dataset
            
        Returns:
            List of content item dictionaries, each containing:
            - 'type': Concept name or value type
            - 'text': Text value
            - 'value': Numeric value (if applicable)
            - 'referenced_images': List of referenced SOP Instance UIDs
        """
        annotations = []
        
        try:
            for content_item in content_seq:
                annotation = {
                    'type': '',
                    'text': '',
                    'value': None,
                    'referenced_images': []
                }
                
                # Get concept name (type of annotation)
                if hasattr(content_item, 'ConceptNameCodeSequence'):
                    concept_seq = content_item.ConceptNameCodeSequence
                    if len(concept_seq) > 0:
                        concept = concept_seq[0]
                        if hasattr(concept, 'CodeMeaning'):
                            annotation['type'] = str(concept.CodeMeaning)
                        elif hasattr(concept, 'CodeValue'):
                            annotation['type'] = str(concept.CodeValue)
                
                # Get text value
                if hasattr(content_item, 'TextValue'):
                    annotation['text'] = str(content_item.TextValue)
                
                # Get numeric value
                if hasattr(content_item, 'MeasuredValueSequence'):
                    measured_seq = content_item.MeasuredValueSequence
                    if len(measured_seq) > 0:
                        measured = measured_seq[0]
                        if hasattr(measured, 'NumericValue'):
                            try:
                                annotation['value'] = float(measured.NumericValue)
                            except (ValueError, TypeError):
                                pass
                        if hasattr(measured, 'MeasurementUnitsCodeSequence'):
                            units_seq = measured.MeasurementUnitsCodeSequence
                            if len(units_seq) > 0:
                                units = units_seq[0]
                                if hasattr(units, 'CodeMeaning'):
                                    annotation['units'] = str(units.CodeMeaning)
                
                # Get referenced images
                if hasattr(content_item, 'ReferencedSOPSequence'):
                    ref_seq = content_item.ReferencedSOPSequence
                    for ref_item in ref_seq:
                        if hasattr(ref_item, 'ReferencedSOPInstanceUID'):
                            annotation['referenced_images'].append(str(ref_item.ReferencedSOPInstanceUID))
                
                # Only add if we have some content
                if annotation['type'] or annotation['text'] or annotation['value'] is not None:
                    annotations.append(annotation)
                
                # Recursively parse nested ContentSequence
                if hasattr(content_item, 'ContentSequence'):
                    nested_annotations = self.parse_content_sequence(content_item.ContentSequence)
                    annotations.extend(nested_annotations)
        except Exception as e:
            print(f"Error parsing ContentSequence: {e}")
        
        return annotations


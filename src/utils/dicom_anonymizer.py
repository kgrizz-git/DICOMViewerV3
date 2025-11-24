"""
DICOM Anonymizer Utility

This module provides functionality for anonymizing DICOM datasets by replacing
or removing patient-related tags.

Inputs:
    - pydicom.Dataset objects
    
Outputs:
    - Anonymized pydicom.Dataset objects
    
Requirements:
    - pydicom library
    - utils.dicom_utils for patient tag identification
"""

from typing import List
import pydicom
from pydicom.dataset import Dataset
from pydicom.tag import Tag

from utils.dicom_utils import is_patient_tag


class DICOMAnonymizer:
    """
    Anonymizes DICOM datasets by replacing or removing patient-related tags.
    
    Features:
    - Replaces text-valued patient tags with "ANONYMIZED"
    - Removes date/time patient tags
    - Removes other non-text patient tags
    - Preserves all other tags and image data
    """
    
    def __init__(self):
        """Initialize the anonymizer."""
        pass
    
    def anonymize_dataset(self, dataset: Dataset) -> Dataset:
        """
        Anonymize a DICOM dataset by replacing or removing patient-related tags.
        
        Creates a copy of the dataset and modifies patient tags:
        - Text-valued tags: replaced with "ANONYMIZED"
        - Date/time tags: removed or set to empty
        - Other tags: removed
        
        Args:
            dataset: pydicom Dataset to anonymize
            
        Returns:
            Anonymized Dataset (copy of original)
        """
        # Create a copy of the dataset
        anonymized = dataset.copy()
        
        # List of tags to remove (will be collected during iteration)
        tags_to_remove = []
        
        # Iterate through all elements in the dataset
        for elem in anonymized:
            tag = elem.tag
            tag_str = str(tag)
            
            # Check if this is a patient-related tag (group 0010)
            if is_patient_tag(tag_str):
                # Get VR (Value Representation) type
                vr = elem.VR if hasattr(elem, 'VR') else ""
                
                # Handle based on VR type
                if self._is_text_vr(vr):
                    # Text-valued tags: replace with "ANONYMIZED"
                    try:
                        anonymized[tag].value = "ANONYMIZED"
                    except Exception:
                        # If we can't modify, remove it
                        tags_to_remove.append(tag)
                elif self._is_date_vr(vr):
                    # Date/time tags: remove
                    tags_to_remove.append(tag)
                else:
                    # Other VR types: remove
                    tags_to_remove.append(tag)
        
        # Remove tags that need to be deleted
        for tag in tags_to_remove:
            try:
                if tag in anonymized:
                    del anonymized[tag]
            except Exception:
                # If deletion fails, try to set to empty
                try:
                    anonymized[tag].value = ""
                except Exception:
                    pass
        
        return anonymized
    
    def _is_text_vr(self, vr: str) -> bool:
        """
        Check if a VR (Value Representation) is a text type.
        
        Args:
            vr: VR string (e.g., "LO", "PN", "SH")
            
        Returns:
            True if VR is a text type, False otherwise
        """
        text_vrs = ["LO", "PN", "SH", "ST", "LT", "UT", "CS", "IS", "DS"]
        return vr in text_vrs
    
    def _is_date_vr(self, vr: str) -> bool:
        """
        Check if a VR (Value Representation) is a date/time type.
        
        Args:
            vr: VR string (e.g., "DA", "TM", "DT")
            
        Returns:
            True if VR is a date/time type, False otherwise
        """
        date_vrs = ["DA", "TM", "DT"]
        return vr in date_vrs


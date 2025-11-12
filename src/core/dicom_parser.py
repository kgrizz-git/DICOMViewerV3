"""
DICOM Metadata Parser

This module extracts and organizes DICOM metadata (tags) from pydicom datasets.
Handles both standard and private tags.

Inputs:
    - pydicom.Dataset objects
    
Outputs:
    - Organized metadata dictionaries
    - Tag value lookups
    - Formatted tag information
    
Requirements:
    - pydicom library
    - typing for type hints
"""

from typing import Dict, Any, Optional, List, Tuple
import pydicom
from pydicom.dataset import Dataset
from pydicom.tag import Tag
import numpy as np


class DICOMParser:
    """
    Parses and organizes DICOM metadata from datasets.
    
    Provides methods to:
    - Extract all tags (standard and private)
    - Get specific tag values
    - Format tag information for display
    - Organize tags by group/element
    """
    
    def __init__(self, dataset: Optional[Dataset] = None):
        """
        Initialize the parser with an optional dataset.
        
        Args:
            dataset: pydicom Dataset to parse
        """
        self.dataset = dataset
        self._tag_cache: Dict[str, Any] = {}
    
    def set_dataset(self, dataset: Dataset) -> None:
        """
        Set the dataset to parse.
        
        Args:
            dataset: pydicom Dataset
        """
        self.dataset = dataset
        self._tag_cache.clear()
    
    def get_all_tags(self, include_private: bool = True) -> Dict[str, Any]:
        """
        Get all tags from the dataset.
        
        Args:
            include_private: If True, include private tags
            
        Returns:
            Dictionary mapping tag strings to values
        """
        if self.dataset is None:
            return {}
        
        tags = {}
        
        for elem in self.dataset:
            tag = elem.tag
            tag_str = str(tag)
            
            # Skip private tags if not requested
            if not include_private and tag.is_private:
                continue
            
            # Get tag value
            try:
                value = elem.value
                # Convert to string if it's a complex type
                if isinstance(value, (list, tuple)):
                    value = [str(v) for v in value]
                elif not isinstance(value, (str, int, float)):
                    value = str(value)
                
                tags[tag_str] = {
                    "tag": tag_str,
                    "keyword": elem.keyword if hasattr(elem, 'keyword') else "",
                    "VR": elem.VR if hasattr(elem, 'VR') else "",
                    "value": value,
                    "is_private": tag.is_private,
                    "name": elem.name if hasattr(elem, 'name') else tag_str,
                }
            except Exception as e:
                # If we can't read the value, store error
                tags[tag_str] = {
                    "tag": tag_str,
                    "keyword": "",
                    "VR": "",
                    "value": f"<Error: {str(e)}>",
                    "is_private": tag.is_private,
                    "name": tag_str,
                }
        
        return tags
    
    def get_tag_value(self, tag: Tuple[int, int], default: Any = None) -> Any:
        """
        Get the value of a specific tag.
        
        Args:
            tag: Tag as (group, element) tuple or Tag object
            default: Default value if tag not found
            
        Returns:
            Tag value or default
        """
        if self.dataset is None:
            return default
        
        try:
            if isinstance(tag, tuple):
                tag_obj = Tag(tag[0], tag[1])
            else:
                tag_obj = tag
            
            if tag_obj in self.dataset:
                return self.dataset[tag_obj].value
            return default
        except Exception:
            return default
    
    def get_tag_by_keyword(self, keyword: str, default: Any = None) -> Any:
        """
        Get tag value by keyword.
        
        Args:
            keyword: DICOM tag keyword (e.g., "PatientName", "StudyDate")
            default: Default value if tag not found
            
        Returns:
            Tag value or default
        """
        if self.dataset is None:
            return default
        
        try:
            if hasattr(self.dataset, keyword):
                return getattr(self.dataset, keyword)
            return default
        except Exception:
            return default
    
    def get_patient_info(self) -> Dict[str, Any]:
        """
        Get patient-related information.
        
        Returns:
            Dictionary with patient information
        """
        return {
            "PatientName": self.get_tag_by_keyword("PatientName", ""),
            "PatientID": self.get_tag_by_keyword("PatientID", ""),
            "PatientBirthDate": self.get_tag_by_keyword("PatientBirthDate", ""),
            "PatientSex": self.get_tag_by_keyword("PatientSex", ""),
            "PatientAge": self.get_tag_by_keyword("PatientAge", ""),
        }
    
    def get_study_info(self) -> Dict[str, Any]:
        """
        Get study-related information.
        
        Returns:
            Dictionary with study information
        """
        return {
            "StudyInstanceUID": self.get_tag_by_keyword("StudyInstanceUID", ""),
            "StudyDate": self.get_tag_by_keyword("StudyDate", ""),
            "StudyTime": self.get_tag_by_keyword("StudyTime", ""),
            "StudyDescription": self.get_tag_by_keyword("StudyDescription", ""),
            "AccessionNumber": self.get_tag_by_keyword("AccessionNumber", ""),
        }
    
    def get_series_info(self) -> Dict[str, Any]:
        """
        Get series-related information.
        
        Returns:
            Dictionary with series information
        """
        return {
            "SeriesInstanceUID": self.get_tag_by_keyword("SeriesInstanceUID", ""),
            "SeriesNumber": self.get_tag_by_keyword("SeriesNumber", ""),
            "SeriesDate": self.get_tag_by_keyword("SeriesDate", ""),
            "SeriesTime": self.get_tag_by_keyword("SeriesTime", ""),
            "SeriesDescription": self.get_tag_by_keyword("SeriesDescription", ""),
            "Modality": self.get_tag_by_keyword("Modality", ""),
        }
    
    def get_image_info(self) -> Dict[str, Any]:
        """
        Get image-related information.
        
        Returns:
            Dictionary with image information
        """
        return {
            "SOPInstanceUID": self.get_tag_by_keyword("SOPInstanceUID", ""),
            "InstanceNumber": self.get_tag_by_keyword("InstanceNumber", ""),
            "ImagePositionPatient": self.get_tag_by_keyword("ImagePositionPatient", ""),
            "ImageOrientationPatient": self.get_tag_by_keyword("ImageOrientationPatient", ""),
            "SliceThickness": self.get_tag_by_keyword("SliceThickness", ""),
            "SliceLocation": self.get_tag_by_keyword("SliceLocation", ""),
            "Rows": self.get_tag_by_keyword("Rows", ""),
            "Columns": self.get_tag_by_keyword("Columns", ""),
            "PixelSpacing": self.get_tag_by_keyword("PixelSpacing", ""),
            "WindowCenter": self.get_tag_by_keyword("WindowCenter", ""),
            "WindowWidth": self.get_tag_by_keyword("WindowWidth", ""),
        }
    
    def update_tag(self, tag: Tuple[int, int], value: Any) -> bool:
        """
        Update a tag value in the dataset.
        
        Args:
            tag: Tag as (group, element) tuple
            value: New value for the tag
            
        Returns:
            True if successful, False otherwise
        """
        if self.dataset is None:
            return False
        
        try:
            if isinstance(tag, tuple):
                tag_obj = Tag(tag[0], tag[1])
            else:
                tag_obj = tag
            
            self.dataset[tag_obj].value = value
            # Clear cache
            self._tag_cache.clear()
            return True
        except Exception:
            return False
    
    def get_private_tags(self) -> Dict[str, Any]:
        """
        Get all private tags.
        
        Returns:
            Dictionary of private tags
        """
        all_tags = self.get_all_tags(include_private=True)
        return {k: v for k, v in all_tags.items() if v.get("is_private", False)}


def get_frame_rate_from_dicom(dataset: Dataset) -> Optional[float]:
    """
    Extract frame rate (FPS) from DICOM dataset.
    
    Checks multiple DICOM tags in priority order:
    1. RecommendedDisplayFrameRate (0008,2144) - Direct FPS value
    2. CineRate (0018,0040) - Cine rate in FPS
    3. FrameTime (0018,1063) - Time per frame in ms, convert to FPS
    4. FrameTimeVector (0018,1065) - Array of frame times, calculate average
    
    Args:
        dataset: pydicom Dataset
        
    Returns:
        Frame rate in FPS (frames per second), or None if no timing information found
    """
    try:
        # 1. Check RecommendedDisplayFrameRate (0008,2144)
        if hasattr(dataset, 'RecommendedDisplayFrameRate'):
            rate = dataset.RecommendedDisplayFrameRate
            if rate:
                try:
                    fps = float(rate)
                    if fps > 0:
                        return fps
                except (ValueError, TypeError):
                    pass
        
        # 2. Check CineRate (0018,0040)
        if hasattr(dataset, 'CineRate'):
            rate = dataset.CineRate
            if rate:
                try:
                    fps = float(rate)
                    if fps > 0:
                        return fps
                except (ValueError, TypeError):
                    pass
        
        # 3. Check FrameTime (0018,1063) - time per frame in milliseconds
        if hasattr(dataset, 'FrameTime'):
            frame_time_ms = dataset.FrameTime
            if frame_time_ms:
                try:
                    frame_time = float(frame_time_ms)
                    if frame_time > 0:
                        # Convert ms to FPS: 1000 ms / frame_time_ms = FPS
                        fps = 1000.0 / frame_time
                        if fps > 0:
                            return fps
                except (ValueError, TypeError):
                    pass
        
        # 4. Check FrameTimeVector (0018,1065) - array of frame times
        if hasattr(dataset, 'FrameTimeVector'):
            frame_times = dataset.FrameTimeVector
            if frame_times and len(frame_times) > 0:
                try:
                    # Convert to numpy array if not already
                    if not isinstance(frame_times, np.ndarray):
                        frame_times = np.array(frame_times)
                    # Calculate average frame time in milliseconds
                    avg_frame_time_ms = np.mean(frame_times)
                    if avg_frame_time_ms > 0:
                        # Convert to FPS
                        fps = 1000.0 / avg_frame_time_ms
                        if fps > 0:
                            return fps
                except (ValueError, TypeError, AttributeError):
                    pass
        
        # No timing information found
        return None
        
    except Exception:
        return None


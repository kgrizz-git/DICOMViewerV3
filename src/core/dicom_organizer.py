"""
DICOM Series and Study Organizer

This module organizes DICOM files into studies and series based on their metadata.
Groups files by StudyInstanceUID and SeriesInstanceUID, and sorts slices by
InstanceNumber or SliceLocation.

Inputs:
    - List of pydicom.Dataset objects
    
Outputs:
    - Organized structure: Studies -> Series -> Slices
    - Sorted slice lists
    
Requirements:
    - pydicom library
    - typing for type hints
"""

from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict
import pydicom
from pydicom.dataset import Dataset


class DICOMOrganizer:
    """
    Organizes DICOM files into studies and series.
    
    Groups files by:
    - StudyInstanceUID (studies)
    - SeriesInstanceUID (series within studies)
    - Sorts slices by InstanceNumber or SliceLocation
    """
    
    def __init__(self):
        """Initialize the organizer."""
        self.studies: Dict[str, Dict[str, List[Dataset]]] = {}
        self.file_paths: Dict[Tuple[str, str, int], str] = {}  # (study_uid, series_uid, instance_num) -> path
    
    def organize(self, datasets: List[Dataset], file_paths: Optional[List[str]] = None) -> Dict[str, Dict[str, List[Dataset]]]:
        """
        Organize datasets into studies and series.
        
        Args:
            datasets: List of pydicom.Dataset objects
            file_paths: Optional list of file paths corresponding to datasets
            
        Returns:
            Dictionary structure: {StudyInstanceUID: {SeriesInstanceUID: [sorted_datasets]}}
        """
        self.studies = {}
        self.file_paths = {}
        
        # Group by StudyInstanceUID and SeriesInstanceUID
        study_dict: Dict[str, Dict[str, List[Tuple[Dataset, Optional[str]]]]] = defaultdict(
            lambda: defaultdict(list)
        )
        
        for idx, dataset in enumerate(datasets):
            # Get study and series UIDs
            study_uid = self._get_tag_value(dataset, "StudyInstanceUID", "")
            series_uid = self._get_tag_value(dataset, "SeriesInstanceUID", "")
            
            if not study_uid or not series_uid:
                # Skip files without proper UIDs
                continue
            
            file_path = file_paths[idx] if file_paths and idx < len(file_paths) else None
            study_dict[study_uid][series_uid].append((dataset, file_path))
        
        # Sort slices within each series and organize
        for study_uid, series_dict in study_dict.items():
            self.studies[study_uid] = {}
            
            for series_uid, slice_list in series_dict.items():
                # Sort slices by InstanceNumber or SliceLocation
                sorted_slices = self._sort_slices(slice_list)
                
                # Store datasets
                self.studies[study_uid][series_uid] = [ds for ds, _ in sorted_slices]
                
                # Store file paths if available
                for idx, (ds, path) in enumerate(sorted_slices):
                    if path:
                        instance_num = self._get_tag_value(ds, "InstanceNumber", idx)
                        self.file_paths[(study_uid, series_uid, instance_num)] = path
        
        return self.studies
    
    def _sort_slices(self, slice_list: List[Tuple[Dataset, Optional[str]]]) -> List[Tuple[Dataset, Optional[str]]]:
        """
        Sort slices by InstanceNumber or SliceLocation.
        
        Args:
            slice_list: List of (dataset, file_path) tuples
            
        Returns:
            Sorted list of (dataset, file_path) tuples
        """
        def get_sort_key(item: Tuple[Dataset, Optional[str]]) -> float:
            """Get sort key for a slice."""
            dataset, _ = item
            
            # Try InstanceNumber first
            instance_num = self._get_tag_value(dataset, "InstanceNumber")
            if instance_num is not None:
                try:
                    return float(instance_num)
                except (ValueError, TypeError):
                    pass
            
            # Try SliceLocation
            slice_loc = self._get_tag_value(dataset, "SliceLocation")
            if slice_loc is not None:
                try:
                    return float(slice_loc)
                except (ValueError, TypeError):
                    pass
            
            # Try ImagePositionPatient (Z coordinate)
            img_pos = self._get_tag_value(dataset, "ImagePositionPatient")
            if img_pos and len(img_pos) >= 3:
                try:
                    return float(img_pos[2])  # Z coordinate
                except (ValueError, TypeError, IndexError):
                    pass
            
            # Fallback: use index
            return float('inf')
        
        return sorted(slice_list, key=get_sort_key)
    
    def _get_tag_value(self, dataset: Dataset, tag_name: str, default: Any = None) -> Any:
        """
        Get tag value from dataset.
        
        Args:
            dataset: pydicom Dataset
            tag_name: Tag keyword
            default: Default value if tag not found
            
        Returns:
            Tag value or default
        """
        try:
            if hasattr(dataset, tag_name):
                return getattr(dataset, tag_name)
            return default
        except Exception:
            return default
    
    def get_studies(self) -> Dict[str, Dict[str, List[Dataset]]]:
        """
        Get organized studies structure.
        
        Returns:
            Dictionary: {StudyInstanceUID: {SeriesInstanceUID: [sorted_datasets]}}
        """
        return self.studies
    
    def get_series_list(self, study_uid: Optional[str] = None) -> List[Tuple[str, str]]:
        """
        Get list of (study_uid, series_uid) pairs.
        
        Args:
            study_uid: Optional study UID to filter by
            
        Returns:
            List of (study_uid, series_uid) tuples
        """
        series_list = []
        
        if study_uid:
            if study_uid in self.studies:
                for series_uid in self.studies[study_uid].keys():
                    series_list.append((study_uid, series_uid))
        else:
            for study_uid, series_dict in self.studies.items():
                for series_uid in series_dict.keys():
                    series_list.append((study_uid, series_uid))
        
        return series_list
    
    def get_slice_count(self, study_uid: str, series_uid: str) -> int:
        """
        Get number of slices in a series.
        
        Args:
            study_uid: Study Instance UID
            series_uid: Series Instance UID
            
        Returns:
            Number of slices
        """
        if study_uid in self.studies and series_uid in self.studies[study_uid]:
            return len(self.studies[study_uid][series_uid])
        return 0
    
    def get_file_path(self, study_uid: str, series_uid: str, instance_number: int) -> Optional[str]:
        """
        Get file path for a specific instance.
        
        Args:
            study_uid: Study Instance UID
            series_uid: Series Instance UID
            instance_number: Instance number
            
        Returns:
            File path or None
        """
        return self.file_paths.get((study_uid, series_uid, instance_number))


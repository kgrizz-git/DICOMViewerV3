"""
DICOM Series and Study Organizer

This module organizes DICOM files into studies and series based on their metadata.
Groups files by StudyInstanceUID and composite series keys (SeriesInstanceUID + SeriesNumber),
and sorts slices by InstanceNumber or SliceLocation.

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
from core.multiframe_handler import is_multiframe, get_frame_count, create_frame_dataset
from utils.dicom_utils import get_composite_series_key


class DICOMOrganizer:
    """
    Organizes DICOM files into studies and series.
    
    Groups files by:
    - StudyInstanceUID (studies)
    - Composite series key (SeriesInstanceUID + SeriesNumber) for series within studies
    - Sorts slices by InstanceNumber or SliceLocation
    
    The composite series key combines SeriesInstanceUID with SeriesNumber to handle
    edge cases where the same SeriesInstanceUID appears with different SeriesNumber
    values, which should be treated as separate series.
    """
    
    def __init__(self):
        """Initialize the organizer."""
        self.studies: Dict[str, Dict[str, List[Dataset]]] = {}
        self.file_paths: Dict[Tuple[str, str, int], str] = {}  # (study_uid, series_uid, instance_num) -> path
        # Storage for Presentation State and Key Object files
        self.presentation_states: Dict[str, List[Dataset]] = {}  # Keyed by StudyInstanceUID
        self.key_objects: Dict[str, List[Dataset]] = {}  # Keyed by StudyInstanceUID
    
    def organize(self, datasets: List[Dataset], file_paths: Optional[List[str]] = None) -> Dict[str, Dict[str, List[Dataset]]]:
        """
        Organize datasets into studies and series.
        
        Args:
            datasets: List of pydicom.Dataset objects
            file_paths: Optional list of file paths corresponding to datasets
            
        Returns:
            Dictionary structure: {StudyInstanceUID: {composite_series_key: [sorted_datasets]}}
            where composite_series_key is "SeriesInstanceUID_SeriesNumber" or "SeriesInstanceUID"
        """
        import time
        organize_start = time.time()
        
        self.studies = {}
        self.file_paths = {}
        self.presentation_states = {}
        self.key_objects = {}
        
        # Group by StudyInstanceUID and SeriesInstanceUID
        study_dict: Dict[str, Dict[str, List[Tuple[Dataset, Optional[str]]]]] = defaultdict(
            lambda: defaultdict(list)
        )
        
        # SOP Class UIDs for Presentation States and Key Objects
        GRAYSCALE_PRESENTATION_STATE_UID = '1.2.840.10008.5.1.4.1.1.11.1'
        COLOR_PRESENTATION_STATE_UID = '1.2.840.10008.5.1.4.1.1.11.2'
        KEY_OBJECT_SELECTION_UID = '1.2.840.10008.5.1.4.1.1.88.59'
        
        # Track SOP Class UIDs encountered
        sop_class_counts = {}
        ps_count = 0
        ko_count = 0
        
        grouping_start = time.time()
        multiframe_count = 0
        total_frames_created = 0
        
        for idx, dataset in enumerate(datasets):
            # Check SOP Class UID to identify file type
            sop_class_uid = self._get_tag_value(dataset, "SOPClassUID", "")
            sop_class_uid_str = str(sop_class_uid)
            
            # Track SOP Class UIDs for debugging
            if sop_class_uid_str:
                sop_class_counts[sop_class_uid_str] = sop_class_counts.get(sop_class_uid_str, 0) + 1
            
            # Handle Presentation State files - use exact match
            if sop_class_uid_str == GRAYSCALE_PRESENTATION_STATE_UID or sop_class_uid_str == COLOR_PRESENTATION_STATE_UID:
                study_uid = self._get_tag_value(dataset, "StudyInstanceUID", "")
                if study_uid:
                    if study_uid not in self.presentation_states:
                        self.presentation_states[study_uid] = []
                    self.presentation_states[study_uid].append(dataset)
                    ps_count += 1
                    # print(f"[ANNOTATIONS] Detected Presentation State file (SOP Class: {sop_class_uid_str[:50]}...)")
                # Skip adding to image series (they're metadata files)
                continue
            
            # Handle Key Object Selection Document files - use exact match
            if sop_class_uid_str == KEY_OBJECT_SELECTION_UID:
                study_uid = self._get_tag_value(dataset, "StudyInstanceUID", "")
                if study_uid:
                    if study_uid not in self.key_objects:
                        self.key_objects[study_uid] = []
                    self.key_objects[study_uid].append(dataset)
                    ko_count += 1
                    # print(f"[ANNOTATIONS] Detected Key Object file (SOP Class: {sop_class_uid_str[:50]}...)")
                # Skip adding to image series (they're metadata files)
                continue
            
            # Check for embedded annotations in image files
            has_overlay = False
            has_graphics = False
            for tag in dataset.keys():
                tag_str = str(tag)
                # Check for OverlayData tags (0x60xx, 0x3000)
                if tag_str.startswith('(0x60') and '0x3000' in tag_str:
                    has_overlay = True
                # Check for GraphicAnnotationSequence
                if 'GraphicAnnotationSequence' in tag_str or hasattr(dataset, 'GraphicAnnotationSequence'):
                    has_graphics = True
            
            if has_overlay or has_graphics:
                study_uid = self._get_tag_value(dataset, "StudyInstanceUID", "")
                series_uid = self._get_tag_value(dataset, "SeriesInstanceUID", "")
                if study_uid and series_uid:
                    # print(f"[ANNOTATIONS] Image file contains embedded annotations (Overlay: {has_overlay}, Graphics: {has_graphics})")
                    # Mark this image as having embedded annotations
                    # We'll process these when displaying the image
                    pass
            
            # Get study UID and composite series key for image files
            study_uid = self._get_tag_value(dataset, "StudyInstanceUID", "")
            series_uid = self._get_tag_value(dataset, "SeriesInstanceUID", "")
            
            if not study_uid or not series_uid:
                # Skip files without proper UIDs
                # print(f"[ANNOTATIONS] Skipping file {idx}: missing StudyInstanceUID or SeriesInstanceUID (SOP Class: {sop_class_uid_str[:50]}...)")
                continue
            
            # Generate composite series key (includes SeriesNumber if available)
            composite_series_key = get_composite_series_key(dataset)
            
            file_path = file_paths[idx] if file_paths and idx < len(file_paths) else None
            
            # Check if this is a multi-frame file
            if is_multiframe(dataset):
                # Split multi-frame file into individual frames
                num_frames = get_frame_count(dataset)
                multiframe_count += 1
                total_frames_created += num_frames
                # print(f"[ORGANIZE] Splitting multi-frame file into {num_frames} frames...")
                
                for frame_index in range(num_frames):
                    # print(f"[ORGANIZE] Creating wrapper for frame {frame_index + 1}/{num_frames}")
                    # Create a frame-specific dataset wrapper
                    frame_dataset = create_frame_dataset(dataset, frame_index)
                    if frame_dataset is not None:
                        # Store frame index in dataset for reference
                        frame_dataset._frame_index = frame_index
                        frame_dataset._original_dataset = dataset
                        # Add frame to the series using composite key
                        study_dict[study_uid][composite_series_key].append((frame_dataset, file_path))
                
                # print(f"[ORGANIZE] Successfully split into {num_frames} frame wrappers")
            else:
                # Single-frame file - add as-is using composite key
                study_dict[study_uid][composite_series_key].append((dataset, file_path))
        
        grouping_time = time.time() - grouping_start
        sorting_start = time.time()
        
        # Sort slices within each series and organize
        for study_uid, series_dict in study_dict.items():
            self.studies[study_uid] = {}
            
            for composite_series_key, slice_list in series_dict.items():
                # Sort slices by InstanceNumber or SliceLocation
                sorted_slices = self._sort_slices(slice_list)
                
                # DEBUG: Log dataset ordering when stored in current_studies
                if sorted_slices and len(sorted_slices) > 0:
                    print(f"[3D RESAMPLE DEBUG] dicom_organizer: Storing datasets in current_studies")
                    print(f"[3D RESAMPLE DEBUG]   Series: {composite_series_key[:30]}...")
                    print(f"[3D RESAMPLE DEBUG]   Total slices: {len(sorted_slices)}")
                    # Log first 3 and last 3 slice locations
                    for i in [0, 1, 2] if len(sorted_slices) > 2 else range(len(sorted_slices)):
                        ds, _ = sorted_slices[i]
                        slice_loc = getattr(ds, 'SliceLocation', None)
                        instance_num = getattr(ds, 'InstanceNumber', None)
                        print(f"[3D RESAMPLE DEBUG]   Sorted slice[{i}]: InstanceNumber={instance_num}, SliceLocation={slice_loc}")
                    if len(sorted_slices) > 3:
                        for i in range(max(3, len(sorted_slices)-3), len(sorted_slices)):
                            ds, _ = sorted_slices[i]
                            slice_loc = getattr(ds, 'SliceLocation', None)
                            instance_num = getattr(ds, 'InstanceNumber', None)
                            print(f"[3D RESAMPLE DEBUG]   Sorted slice[{i}]: InstanceNumber={instance_num}, SliceLocation={slice_loc}")
                
                # Store datasets using composite series key
                self.studies[study_uid][composite_series_key] = [ds for ds, _ in sorted_slices]
                
                # Store file paths if available (using composite series key)
                for idx, (ds, path) in enumerate(sorted_slices):
                    if path:
                        # For multi-frame files, use frame index as part of instance identifier
                        if hasattr(ds, '_frame_index') and hasattr(ds, '_original_dataset'):
                            # This is a frame from a multi-frame file
                            # Use a combination of InstanceNumber and frame index
                            base_instance = self._get_tag_value(ds._original_dataset, "InstanceNumber", 0)
                            frame_index = ds._frame_index
                            # Create a unique instance number: base * 10000 + frame_index
                            # This ensures frames are properly ordered
                            instance_num = int(base_instance) * 10000 + frame_index
                        else:
                            instance_num = self._get_tag_value(ds, "InstanceNumber", idx)
                        self.file_paths[(study_uid, composite_series_key, instance_num)] = path
        
        sorting_time = time.time() - sorting_start
        total_time = time.time() - organize_start
        
        # Debug summary
        total_series = sum(len(series_dict) for series_dict in self.studies.values())
        total_slices = sum(len(slices) for study_dict in self.studies.values() for slices in study_dict.values())
        
        print(f"[ORGANIZE DEBUG] ===== Organize Summary =====")
        print(f"[ORGANIZE DEBUG] Input datasets: {len(datasets)}")
        print(f"[ORGANIZE DEBUG] Multi-frame files: {multiframe_count}")
        print(f"[ORGANIZE DEBUG] Total frames created: {total_frames_created}")
        print(f"[ORGANIZE DEBUG] Output studies: {len(self.studies)}")
        print(f"[ORGANIZE DEBUG] Output series: {total_series}")
        print(f"[ORGANIZE DEBUG] Total slices: {total_slices}")
        print(f"[ORGANIZE DEBUG] Grouping time: {grouping_time:.2f}s")
        print(f"[ORGANIZE DEBUG] Sorting time: {sorting_time:.2f}s")
        print(f"[ORGANIZE DEBUG] Total time: {total_time:.2f}s")
        print(f"[ORGANIZE DEBUG] ===========================")
        
        # Print summary of detected annotation files
        # print(f"[ANNOTATIONS] Organization complete: {ps_count} Presentation State(s), {ko_count} Key Object(s)")
        # if sop_class_counts:
        #     print(f"[ANNOTATIONS] SOP Class UIDs encountered: {len(sop_class_counts)} unique types")
        #     # Print top 10 most common SOP Class UIDs
        #     sorted_sop = sorted(sop_class_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        #     for uid, count in sorted_sop:
        #         print(f"  {uid[:60]}... : {count} file(s)")
        
        return self.studies
    
    def _sort_slices(self, slice_list: List[Tuple[Dataset, Optional[str]]]) -> List[Tuple[Dataset, Optional[str]]]:
        """
        Sort slices by InstanceNumber or SliceLocation.
        For multi-frame files, frames are sorted by frame index within the same instance.
        
        Args:
            slice_list: List of (dataset, file_path) tuples
            
        Returns:
            Sorted list of (dataset, file_path) tuples
        """
        def get_sort_key(item: Tuple[Dataset, Optional[str]]) -> Tuple[float, float]:
            """Get sort key for a slice."""
            dataset, _ = item
            
            # Primary sort key: InstanceNumber or equivalent
            primary_key = float('inf')
            
            # Check if this is a frame from a multi-frame file
            if hasattr(dataset, '_frame_index') and hasattr(dataset, '_original_dataset'):
                # This is a frame from a multi-frame file
                original_ds = dataset._original_dataset
                frame_index = dataset._frame_index
                
                # Get base instance number from original dataset
                instance_num = self._get_tag_value(original_ds, "InstanceNumber")
                if instance_num is not None:
                    try:
                        primary_key = float(instance_num)
                    except (ValueError, TypeError):
                        pass
                
                # Secondary key: frame index (to sort frames within same instance)
                secondary_key = float(frame_index)
                return (primary_key, secondary_key)
            else:
                # Single-frame file
                # Try InstanceNumber first
                instance_num = self._get_tag_value(dataset, "InstanceNumber")
                if instance_num is not None:
                    try:
                        primary_key = float(instance_num)
                    except (ValueError, TypeError):
                        pass
                
                # Try SliceLocation
                if primary_key == float('inf'):
                    slice_loc = self._get_tag_value(dataset, "SliceLocation")
                    if slice_loc is not None:
                        try:
                            primary_key = float(slice_loc)
                        except (ValueError, TypeError):
                            pass
                
                # Try ImagePositionPatient (Z coordinate)
                if primary_key == float('inf'):
                    img_pos = self._get_tag_value(dataset, "ImagePositionPatient")
                    if img_pos and len(img_pos) >= 3:
                        try:
                            primary_key = float(img_pos[2])  # Z coordinate
                        except (ValueError, TypeError, IndexError):
                            pass
                
                # Secondary key: 0 for single-frame files
                secondary_key = 0.0
                return (primary_key, secondary_key)
        
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
            Dictionary: {StudyInstanceUID: {composite_series_key: [sorted_datasets]}}
            where composite_series_key is "SeriesInstanceUID_SeriesNumber" or "SeriesInstanceUID"
        """
        return self.studies
    
    def get_series_list(self, study_uid: Optional[str] = None) -> List[Tuple[str, str]]:
        """
        Get list of (study_uid, composite_series_key) pairs.
        
        Args:
            study_uid: Optional study UID to filter by
            
        Returns:
            List of (study_uid, composite_series_key) tuples
            where composite_series_key is "SeriesInstanceUID_SeriesNumber" or "SeriesInstanceUID"
        """
        series_list = []
        
        if study_uid:
            if study_uid in self.studies:
                for composite_series_key in self.studies[study_uid].keys():
                    series_list.append((study_uid, composite_series_key))
        else:
            for study_uid, series_dict in self.studies.items():
                for composite_series_key in series_dict.keys():
                    series_list.append((study_uid, composite_series_key))
        
        return series_list
    
    def get_slice_count(self, study_uid: str, series_uid: str) -> int:
        """
        Get number of slices in a series.
        
        Args:
            study_uid: Study Instance UID
            series_uid: Composite series key (SeriesInstanceUID_SeriesNumber or SeriesInstanceUID)
            
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
            series_uid: Composite series key (SeriesInstanceUID_SeriesNumber or SeriesInstanceUID)
            instance_number: Instance number
            
        Returns:
            File path or None
        """
        return self.file_paths.get((study_uid, series_uid, instance_number))
    
    def get_presentation_states(self, study_uid: str) -> List[Dataset]:
        """
        Get Presentation State files for a study.
        
        Args:
            study_uid: Study Instance UID
            
        Returns:
            List of Presentation State datasets
        """
        return self.presentation_states.get(study_uid, [])
    
    def get_key_objects(self, study_uid: str) -> List[Dataset]:
        """
        Get Key Object Selection Document files for a study.
        
        Args:
            study_uid: Study Instance UID
            
        Returns:
            List of Key Object datasets
        """
        return self.key_objects.get(study_uid, [])


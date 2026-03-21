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

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple
from collections import defaultdict
import pydicom
from pydicom.dataset import Dataset
from core.multiframe_handler import (
    FrameType,
    classify_frame_type,
    create_frame_dataset,
    get_frame_count,
    get_frame_diffusion_b_value,
    get_frame_trigger_time_ms,
    is_multiframe,
)
from utils.dicom_utils import get_composite_series_key


@dataclass
class MergeResult:
    """
    Result of merging a new batch of DICOM files into the organizer.

    Used for additive loading: new_series and appended_series tell the caller
    what changed so the UI can update only affected subwindows.
    """
    new_series: List[Tuple[str, str]]  # (study_uid, series_key) for brand-new series
    appended_series: List[Tuple[str, str]]  # (study_uid, series_key) where slices were merged in
    skipped_file_count: int  # files whose paths were already in loaded_file_paths
    added_file_count: int  # files actually ingested


@dataclass(frozen=True)
class MultiFrameSeriesInfo:
    """Per-series summary of multi-frame structure."""
    instance_count: int
    max_frame_count: int
    frame_type: FrameType = FrameType.UNKNOWN


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
        self.series_multiframe_info: Dict[Tuple[str, str], MultiFrameSeriesInfo] = {}
        # Storage for Presentation State and Key Object files
        self.presentation_states: Dict[str, List[Dataset]] = {}  # Keyed by StudyInstanceUID
        self.key_objects: Dict[str, List[Dataset]] = {}  # Keyed by StudyInstanceUID
        # Multi-study additive loading: track loaded paths and source dirs per series
        self.loaded_file_paths: Set[str] = set()
        self.series_source_dirs: Dict[Tuple[str, str], str] = {}  # (study_uid, series_key) -> source_dir
        self._disambiguation_counters: Dict[Tuple[str, str], int] = {}  # (study_uid, base_series_key) -> next suffix

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
        self.studies = {}
        self.file_paths = {}
        self.series_multiframe_info = {}
        self.presentation_states = {}
        self.key_objects = {}
        batch_studies, batch_fp, batch_ps, batch_ko = self._organize_files_into_batch(datasets, file_paths)
        self.studies = batch_studies
        self.file_paths = batch_fp
        self.series_multiframe_info = self._build_series_multiframe_info_map(batch_studies)
        self.presentation_states = batch_ps
        self.key_objects = batch_ko
        return self.studies

    def _organize_files_into_batch(
        self,
        datasets: List[Dataset],
        file_paths_input: Optional[List[str]] = None,
    ) -> Tuple[
        Dict[str, Dict[str, List[Dataset]]],
        Dict[Tuple[str, str, int], str],
        Dict[str, List[Dataset]],
        Dict[str, List[Dataset]],
    ]:
        """Organize a batch without modifying instance state. Returns (batch_studies, batch_file_paths, batch_ps, batch_ko)."""
        batch_studies: Dict[str, Dict[str, List[Dataset]]] = {}
        batch_file_paths: Dict[Tuple[str, str, int], str] = {}
        batch_ps: Dict[str, List[Dataset]] = {}
        batch_ko: Dict[str, List[Dataset]] = {}
        study_dict: Dict[str, Dict[str, List[Tuple[Dataset, Optional[str]]]]] = defaultdict(
            lambda: defaultdict(list)
        )
        
        # SOP Class UIDs for Presentation States and Key Objects
        GRAYSCALE_PRESENTATION_STATE_UID = '1.2.840.10008.5.1.4.1.1.11.1'
        COLOR_PRESENTATION_STATE_UID = '1.2.840.10008.5.1.4.1.1.11.2'
        KEY_OBJECT_SELECTION_UID = '1.2.840.10008.5.1.4.1.1.88.59'
        
        for idx, dataset in enumerate(datasets):
            # Check SOP Class UID to identify file type
            sop_class_uid = self._get_tag_value(dataset, "SOPClassUID", "")
            sop_class_uid_str = str(sop_class_uid)
            
            # Handle Presentation State files - use exact match
            if sop_class_uid_str == GRAYSCALE_PRESENTATION_STATE_UID or sop_class_uid_str == COLOR_PRESENTATION_STATE_UID:
                study_uid = self._get_tag_value(dataset, "StudyInstanceUID", "")
                if study_uid:
                    if study_uid not in batch_ps:
                        batch_ps[study_uid] = []
                    batch_ps[study_uid].append(dataset)
                    # print(f"[ANNOTATIONS] Detected Presentation State file (SOP Class: {sop_class_uid_str[:50]}...)")
                # Skip adding to image series (they're metadata files)
                continue
            
            # Handle Key Object Selection Document files - use exact match
            if sop_class_uid_str == KEY_OBJECT_SELECTION_UID:
                study_uid = self._get_tag_value(dataset, "StudyInstanceUID", "")
                if study_uid:
                    if study_uid not in batch_ko:
                        batch_ko[study_uid] = []
                    batch_ko[study_uid].append(dataset)
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
            
            file_path = file_paths_input[idx] if file_paths_input and idx < len(file_paths_input) else None

            if is_multiframe(dataset):
                num_frames = get_frame_count(dataset)
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
        
        for study_uid, series_dict in study_dict.items():
            batch_studies[study_uid] = {}
            for composite_series_key, slice_list in series_dict.items():
                sorted_slices = self._sort_slices(slice_list)
                batch_studies[study_uid][composite_series_key] = [ds for ds, _ in sorted_slices]
                for idx, (ds, path) in enumerate(sorted_slices):
                    if path:
                        if hasattr(ds, '_frame_index') and hasattr(ds, '_original_dataset'):
                            base_instance = self._get_tag_value(ds._original_dataset, "InstanceNumber", 0)
                            frame_index = ds._frame_index
                            instance_num = int(base_instance) * 10000 + frame_index
                        else:
                            instance_num = self._get_tag_value(ds, "InstanceNumber", idx)
                        batch_file_paths[(study_uid, composite_series_key, instance_num)] = path
        return (batch_studies, batch_file_paths, batch_ps, batch_ko)

    def _get_instance_identifier(self, ds: Dataset, idx_fallback: int) -> int:
        """Return the instance number used as part of the file_paths key for this dataset."""
        if hasattr(ds, '_frame_index') and hasattr(ds, '_original_dataset'):
            base_instance = self._get_tag_value(ds._original_dataset, "InstanceNumber", 0)
            return int(base_instance) * 10000 + ds._frame_index
        return self._get_tag_value(ds, "InstanceNumber", idx_fallback)

    def merge_batch(
        self,
        datasets: List[Dataset],
        file_paths_input: Optional[List[str]] = None,
        source_dir: str = "",
    ) -> MergeResult:
        """
        Merge a new batch of DICOM files into existing organizer state.
        Skips files whose path is already in loaded_file_paths.
        Same series from a different source_dir becomes a separate series (disambiguation suffix).
        """
        result = MergeResult(
            new_series=[],
            appended_series=[],
            skipped_file_count=0,
            added_file_count=0,
        )
        if not datasets:
            return result

        # Normalize paths for dedup; build parallel lists of new-only datasets/paths
        def norm(p: str) -> str:
            return os.path.normpath(os.path.abspath(p))

        datasets_new: List[Dataset] = []
        file_paths_new: List[Optional[str]] = []
        for idx, ds in enumerate(datasets):
            path = file_paths_input[idx] if file_paths_input and idx < len(file_paths_input) else None
            if path and norm(path) in self.loaded_file_paths:
                result.skipped_file_count += 1
                continue
            datasets_new.append(ds)
            file_paths_new.append(path)

        if not datasets_new:
            return result

        batch_studies, batch_fp, batch_ps, batch_ko = self._organize_files_into_batch(datasets_new, file_paths_new)

        for study_uid, series_dict in batch_studies.items():
            if study_uid not in self.studies:
                self.studies[study_uid] = {}
            for base_key, new_datasets_list in series_dict.items():
                existing_source = self.series_source_dirs.get((study_uid, base_key))
                if existing_source is None or existing_source == source_dir:
                    effective_key = base_key
                    self.series_source_dirs[(study_uid, base_key)] = source_dir
                    if base_key in self.studies.get(study_uid, {}):
                        # Slice append: merge and re-sort; existing file_paths stay, add only new from batch_fp
                        existing_list = self.studies[study_uid][base_key]
                        existing_tuples = [
                            (ds, self.file_paths.get((study_uid, base_key, self._get_instance_identifier(ds, i)), None))
                            for i, ds in enumerate(existing_list)
                        ]
                        new_tuples = [
                            (ds, batch_fp.get((study_uid, base_key, self._get_instance_identifier(ds, i)), None))
                            for i, ds in enumerate(new_datasets_list)
                        ]
                        combined = existing_tuples + new_tuples
                        sorted_slices = self._sort_slices(combined)
                        self.studies[study_uid][base_key] = [ds for ds, _ in sorted_slices]
                        for k, v in batch_fp.items():
                            if k[0] == study_uid and k[1] == base_key:
                                self.file_paths[k] = v
                        self._update_series_multiframe_info(study_uid, base_key)
                        result.appended_series.append((study_uid, base_key))
                    else:
                        self.studies[study_uid][base_key] = new_datasets_list
                        for k, v in batch_fp.items():
                            if k[0] == study_uid and k[1] == base_key:
                                self.file_paths[k] = v
                        self._update_series_multiframe_info(study_uid, base_key)
                        result.new_series.append((study_uid, base_key))
                else:
                    n = self._disambiguation_counters.get((study_uid, base_key), 2)
                    effective_key = f"{base_key}_v{n}"
                    self._disambiguation_counters[(study_uid, base_key)] = n + 1
                    self.series_source_dirs[(study_uid, effective_key)] = source_dir
                    self.studies[study_uid][effective_key] = new_datasets_list
                    for k, v in batch_fp.items():
                        if k[0] == study_uid and k[1] == base_key:
                            self.file_paths[(study_uid, effective_key, k[2])] = v
                    self._update_series_multiframe_info(study_uid, effective_key)
                    result.new_series.append((study_uid, effective_key))

        self.presentation_states.update(batch_ps)
        self.key_objects.update(batch_ko)

        added_paths = set()
        for idx, path in enumerate(file_paths_new):
            if path:
                added_paths.add(norm(path))
        self.loaded_file_paths.update(added_paths)
        result.added_file_count = len(added_paths)
        return result

    def remove_series(self, study_uid: str, series_key: str) -> None:
        """Remove one series and its file_paths; if study becomes empty, remove the study."""
        if study_uid not in self.studies or series_key not in self.studies[study_uid]:
            return
        paths_to_remove: Set[str] = set()
        keys_to_del = [k for k in self.file_paths if k[0] == study_uid and k[1] == series_key]
        for k in keys_to_del:
            path = self.file_paths.pop(k)
            if path:
                paths_to_remove.add(os.path.normpath(os.path.abspath(path)))
        self.loaded_file_paths -= paths_to_remove
        self.series_source_dirs.pop((study_uid, series_key), None)
        self.series_multiframe_info.pop((study_uid, series_key), None)
        del self.studies[study_uid][series_key]
        if not self.studies[study_uid]:
            self.remove_study(study_uid)

    def remove_study(self, study_uid: str) -> None:
        """Remove a study and all its series, file_paths, PS/KO."""
        if study_uid not in self.studies:
            return
        series_keys = list(self.studies[study_uid].keys())
        paths_to_remove: Set[str] = set()
        keys_to_del = [k for k in self.file_paths if k[0] == study_uid]
        for k in keys_to_del:
            path = self.file_paths.pop(k)
            if path:
                paths_to_remove.add(os.path.normpath(os.path.abspath(path)))
        self.loaded_file_paths -= paths_to_remove
        for sk in series_keys:
            self.series_source_dirs.pop((study_uid, sk), None)
            self.series_multiframe_info.pop((study_uid, sk), None)
        del self.studies[study_uid]
        self.presentation_states.pop(study_uid, None)
        self.key_objects.pop(study_uid, None)
        for key in list(self._disambiguation_counters.keys()):
            if key[0] == study_uid:
                del self._disambiguation_counters[key]

    def clear(self) -> None:
        """Reset all organizer state (studies, file_paths, PS/KO, loaded paths, source dirs)."""
        self.studies = {}
        self.file_paths = {}
        self.series_multiframe_info = {}
        self.presentation_states = {}
        self.key_objects = {}
        self.loaded_file_paths = set()
        self.series_source_dirs = {}
        self._disambiguation_counters = {}

    def _build_series_multiframe_info_map(
        self,
        studies: Dict[str, Dict[str, List[Dataset]]],
    ) -> Dict[Tuple[str, str], MultiFrameSeriesInfo]:
        """Build per-series multiframe metadata for a studies dictionary."""
        info_map: Dict[Tuple[str, str], MultiFrameSeriesInfo] = {}
        for study_uid, series_dict in studies.items():
            for series_key, datasets in series_dict.items():
                info_map[(study_uid, series_key)] = self._compute_series_multiframe_info(datasets)
        return info_map

    def _compute_series_multiframe_info(self, datasets: List[Dataset]) -> MultiFrameSeriesInfo:
        """Compute instance and frame counts for one organized series."""
        if not datasets:
            return MultiFrameSeriesInfo(instance_count=0, max_frame_count=1, frame_type=FrameType.UNKNOWN)

        seen_original_ids: Set[int] = set()
        instance_count = 0
        max_frame_count = 1
        frame_types: Set[FrameType] = set()

        for dataset in datasets:
            original_dataset = getattr(dataset, '_original_dataset', dataset)
            original_id = id(original_dataset)
            if original_id in seen_original_ids:
                continue
            seen_original_ids.add(original_id)
            instance_count += 1
            max_frame_count = max(max_frame_count, get_frame_count(original_dataset))
            frame_types.add(classify_frame_type(original_dataset))

        if len(frame_types) == 1:
            frame_type = next(iter(frame_types))
        else:
            frame_type = FrameType.UNKNOWN

        return MultiFrameSeriesInfo(
            instance_count=instance_count,
            max_frame_count=max_frame_count,
            frame_type=frame_type,
        )

    def _update_series_multiframe_info(self, study_uid: str, series_key: str) -> None:
        """Refresh cached multiframe metadata for one series."""
        datasets = self.studies.get(study_uid, {}).get(series_key, [])
        if not datasets:
            self.series_multiframe_info.pop((study_uid, series_key), None)
            return
        self.series_multiframe_info[(study_uid, series_key)] = self._compute_series_multiframe_info(datasets)

    def get_series_multiframe_info(self, study_uid: str, series_key: str) -> Optional[MultiFrameSeriesInfo]:
        """Return cached multiframe metadata for a series, if available."""
        return self.series_multiframe_info.get((study_uid, series_key))

    def get_multiframe_display_context(
        self,
        study_uid: str,
        series_key: str,
        dataset: Optional[Dataset],
    ) -> Optional[Dict[str, Any]]:
        """Return instance/frame display context for a frame wrapper within a series."""
        if dataset is None:
            return None
        if not hasattr(dataset, '_frame_index') or not hasattr(dataset, '_original_dataset'):
            return None

        series_datasets = self.studies.get(study_uid, {}).get(series_key, [])
        if not series_datasets:
            return None

        original_dataset = dataset._original_dataset
        ordered_instances: List[Dataset] = []
        seen_original_ids: Set[int] = set()
        for series_dataset in series_datasets:
            series_original = getattr(series_dataset, '_original_dataset', series_dataset)
            series_original_id = id(series_original)
            if series_original_id in seen_original_ids:
                continue
            seen_original_ids.add(series_original_id)
            ordered_instances.append(series_original)

        instance_index = None
        for idx, ordered_instance in enumerate(ordered_instances, start=1):
            if ordered_instance is original_dataset:
                instance_index = idx
                break

        total_frames = get_frame_count(original_dataset)
        if instance_index is None or total_frames <= 1:
            return None

        series_info = self.get_series_multiframe_info(study_uid, series_key)
        if series_info is None:
            frame_type = FrameType.UNKNOWN
        else:
            frame_type = series_info.frame_type

        context: Dict[str, Any] = {
            'instance_index': instance_index,
            'total_instances': len(ordered_instances),
            'frame_index': int(dataset._frame_index) + 1,
            'total_frames': total_frames,
            'frame_type': frame_type.value,
        }

        if frame_type == FrameType.CARDIAC:
            trigger_time_ms = get_frame_trigger_time_ms(original_dataset, int(dataset._frame_index))
            if trigger_time_ms is not None:
                context['trigger_time_ms'] = trigger_time_ms
        elif frame_type == FrameType.DIFFUSION:
            diffusion_b_value = get_frame_diffusion_b_value(original_dataset, int(dataset._frame_index))
            if diffusion_b_value is not None:
                context['diffusion_b_value'] = diffusion_b_value

        return context

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


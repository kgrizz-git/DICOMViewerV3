"""
Slice Grouping Utility

This module provides utilities for grouping DICOM datasets by their original slice,
which is necessary for handling multi-slice series where some slices contain multiple frames.

Inputs:
    - List of DICOM datasets (may include frame datasets from multi-frame files)
    
Outputs:
    - Grouped datasets by original slice
    - Slice index mapping for navigation
    
Requirements:
    - pydicom for Dataset type
    - typing for type hints
"""

from typing import Dict, List, Optional
from pydicom.dataset import Dataset


def group_datasets_by_slice(datasets: List[Dataset]) -> Dict[int, List[Dataset]]:
    """
    Group datasets by their original slice.
    
    For multi-frame files, frames are split into individual datasets during organization.
    Each frame dataset has a `_original_dataset` attribute pointing to the original
    multi-frame dataset. This function groups all frame datasets that came from the
    same original dataset.
    
    Args:
        datasets: List of DICOM datasets (may include frame datasets)
        
    Returns:
        Dictionary mapping original dataset ID (via id()) to list of frame datasets.
        Single-frame datasets map to themselves.
    """
    slice_groups: Dict[int, List[Dataset]] = {}
    
    for dataset in datasets:
        # Check if this is a frame from a multi-frame file
        if hasattr(dataset, '_original_dataset') and dataset._original_dataset is not None:
            # This is a frame dataset - group by original dataset
            original_dataset = dataset._original_dataset
            original_id = id(original_dataset)
            if original_id not in slice_groups:
                slice_groups[original_id] = []
            slice_groups[original_id].append(dataset)
        else:
            # Single-frame dataset - map to itself
            dataset_id = id(dataset)
            if dataset_id not in slice_groups:
                slice_groups[dataset_id] = []
            slice_groups[dataset_id].append(dataset)
    
    # Sort frames within each slice group by frame index
    for original_id, frame_datasets in slice_groups.items():
        frame_datasets.sort(key=lambda ds: getattr(ds, '_frame_index', 0))
    
    return slice_groups


def get_slice_index_for_dataset(datasets: List[Dataset], current_index: int) -> int:
    """
    Get which slice group the dataset at the given index belongs to.
    
    Args:
        datasets: List of all datasets in the series
        current_index: Index of the current dataset in the list
        
    Returns:
        Zero-based slice group index (0 = first slice, 1 = second slice, etc.)
    """
    if current_index < 0 or current_index >= len(datasets):
        return 0
    
    slice_groups = group_datasets_by_slice(datasets)
    
    # Create ordered list of original dataset IDs (slice groups)
    # Use the order they appear in the datasets list
    seen_originals = set()
    ordered_slices = []
    
    for dataset in datasets:
        if hasattr(dataset, '_original_dataset') and dataset._original_dataset is not None:
            original = dataset._original_dataset
            original_id = id(original)
        else:
            original = dataset
            original_id = id(original)
        
        if original_id not in seen_originals:
            seen_originals.add(original_id)
            ordered_slices.append(original_id)
    
    # Find which slice group the current dataset belongs to
    current_dataset = datasets[current_index]
    if hasattr(current_dataset, '_original_dataset') and current_dataset._original_dataset is not None:
        target_original = current_dataset._original_dataset
        target_id = id(target_original)
    else:
        target_original = current_dataset
        target_id = id(target_original)
    
    # Find index of target_id in ordered_slices
    try:
        slice_index = ordered_slices.index(target_id)
        return slice_index
    except ValueError:
        return 0


def get_frame_index_in_slice(datasets: List[Dataset], current_index: int) -> int:
    """
    Get the frame index within the current slice for the dataset at the given index.
    
    Args:
        datasets: List of all datasets in the series
        current_index: Index of the current dataset in the list
        
    Returns:
        Zero-based frame index within the slice (0 = first frame in slice)
    """
    if current_index < 0 or current_index >= len(datasets):
        return 0
    
    current_dataset = datasets[current_index]
    
    # If this is a frame dataset, return its frame index
    if hasattr(current_dataset, '_frame_index'):
        return current_dataset._frame_index
    
    # Otherwise, it's a single-frame dataset, so frame index is 0
    return 0


def get_slice_frame_count(datasets: List[Dataset], slice_index: int) -> int:
    """
    Get the number of frames in a specific slice.
    
    Args:
        datasets: List of all datasets in the series
        slice_index: Zero-based slice group index
        
    Returns:
        Number of frames in the specified slice
    """
    slice_groups = group_datasets_by_slice(datasets)
    
    # Create ordered list of original dataset IDs
    seen_originals = set()
    ordered_slices = []
    
    for dataset in datasets:
        if hasattr(dataset, '_original_dataset') and dataset._original_dataset is not None:
            original = dataset._original_dataset
            original_id = id(original)
        else:
            original = dataset
            original_id = id(original)
        
        if original_id not in seen_originals:
            seen_originals.add(original_id)
            ordered_slices.append(original_id)
    
    if slice_index < 0 or slice_index >= len(ordered_slices):
        return 0
    
    original_id = ordered_slices[slice_index]
    if original_id in slice_groups:
        return len(slice_groups[original_id])
    
    return 0


def get_total_slices(datasets: List[Dataset]) -> int:
    """
    Get the total number of slice groups (original slices) in the series.
    
    Args:
        datasets: List of all datasets in the series
        
    Returns:
        Total number of slice groups
    """
    slice_groups = group_datasets_by_slice(datasets)
    return len(slice_groups)


def get_first_frame_index_for_slice(datasets: List[Dataset], slice_index: int) -> int:
    """
    Get the dataset index of the first frame in a specific slice.
    
    Args:
        datasets: List of all datasets in the series
        slice_index: Zero-based slice group index
        
    Returns:
        Index in datasets list of the first frame in the specified slice, or 0 if not found
    """
    slice_groups = group_datasets_by_slice(datasets)
    
    # Create ordered list of original dataset IDs
    seen_originals = set()
    ordered_slices = []
    
    for dataset in datasets:
        if hasattr(dataset, '_original_dataset') and dataset._original_dataset is not None:
            original = dataset._original_dataset
            original_id = id(original)
        else:
            original = dataset
            original_id = id(original)
        
        if original_id not in seen_originals:
            seen_originals.add(original_id)
            ordered_slices.append(original_id)
    
    if slice_index < 0 or slice_index >= len(ordered_slices):
        return 0
    
    original_id = ordered_slices[slice_index]
    if original_id in slice_groups:
        frame_datasets = slice_groups[original_id]
        if frame_datasets:
            # Find the index of the first frame dataset in the original datasets list
            first_frame = frame_datasets[0]
            try:
                return datasets.index(first_frame)
            except ValueError:
                return 0
    
    return 0


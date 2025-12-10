"""
Fusion Handler

This module manages image fusion state and slice matching logic for overlaying
functional imaging (PET/SPECT) on anatomical imaging (CT/MR).

Inputs:
    - DICOM datasets from base and overlay series
    - Fusion configuration (opacity, threshold, colormap)
    
Outputs:
    - Matched slice indices
    - Interpolated overlay arrays
    - Frame of Reference compatibility checks
    
Requirements:
    - pydicom for DICOM tag access
    - numpy for array operations
"""

import time
import numpy as np
from typing import Optional, List, Tuple, Dict
from pydicom.dataset import Dataset
from core.dicom_processor import DICOMProcessor


class FusionHandler:
    """
    Manages fusion state and slice matching between two DICOM series.
    
    Responsibilities:
    - Track base and overlay series selection
    - Check Frame of Reference UID compatibility
    - Match slices by position
    - Interpolate overlay slices when needed
    """
    
    def __init__(self):
        """Initialize fusion handler with default state."""
        self.base_series_uid: Optional[str] = None
        self.overlay_series_uid: Optional[str] = None
        self.fusion_enabled: bool = False
        self.opacity: float = 0.5  # 0.0 to 1.0
        self.threshold: float = 0.2  # 0.0 to 1.0
        self.colormap: str = 'hot'
        
        # Track whether overlay pixels are in rescaled units
        self.overlay_uses_rescaled: bool = False
        self._overlay_rescale_slope: Optional[float] = None
        self._overlay_rescale_intercept: Optional[float] = None
        
        # Cache for slice locations
        self._slice_location_cache: Dict[str, List[Tuple[int, float]]] = {}
        # Cache for spatial alignment per (base, overlay) series pair
        self._alignment_cache: Dict[
            Tuple[str, str],
            Dict[str, Optional[Tuple[float, float]]]
        ] = {}
    
    def set_base_series(self, series_uid: str) -> None:
        """
        Set the base (anatomical) series.
        
        Args:
            series_uid: Series instance UID for base series
        """
        self.base_series_uid = series_uid
    
    def set_overlay_series(self, series_uid: str) -> None:
        """
        Set the overlay (functional) series.
        
        Args:
            series_uid: Series instance UID for overlay series
        """
        self.overlay_series_uid = series_uid
        # Reset rescale state when overlay series changes
        self.overlay_uses_rescaled = False
        self._overlay_rescale_slope = None
        self._overlay_rescale_intercept = None
        # Clear cache when overlay series changes
        self._slice_location_cache.clear()
    
    def get_overlay_rescale_state(self) -> Tuple[bool, Optional[float], Optional[float]]:
        """
        Get the current rescale state for overlay pixels.
        
        Returns:
            Tuple of (is_rescaled, slope, intercept)
            - is_rescaled: True if overlay pixels are in rescaled units
            - slope: Rescale slope if available, None otherwise
            - intercept: Rescale intercept if available, None otherwise
        """
        return (
            self.overlay_uses_rescaled,
            self._overlay_rescale_slope,
            self._overlay_rescale_intercept
        )
    
    def set_alignment(
        self,
        base_series_uid: Optional[str],
        overlay_series_uid: Optional[str],
        scale: Optional[Tuple[float, float]],
        offset: Optional[Tuple[float, float]]
    ) -> None:
        """Store alignment info for a base/overlay pair."""
        if not base_series_uid or not overlay_series_uid:
            return
        self._alignment_cache[(base_series_uid, overlay_series_uid)] = {
            'scale': scale,
            'offset': offset,
            'timestamp': time.time(),
        }
    
    def get_alignment(
        self,
        base_series_uid: Optional[str],
        overlay_series_uid: Optional[str]
    ) -> Optional[Dict[str, Optional[Tuple[float, float]]]]:
        """Retrieve cached alignment for a base/overlay pair."""
        if not base_series_uid or not overlay_series_uid:
            return None
        # Ignore self-pair cache to force recalculation for new overlays
        if base_series_uid == overlay_series_uid:
            return None
        return self._alignment_cache.get((base_series_uid, overlay_series_uid))
    
    def clear_alignment_cache(self, series_uid: Optional[str] = None) -> None:
        """Clear cached alignment data completely or for a specific series."""
        if series_uid is None:
            self._alignment_cache.clear()
            return
        
        keys_to_delete = [
            key for key in self._alignment_cache
            if series_uid in key
        ]
        for key in keys_to_delete:
            del self._alignment_cache[key]
    
    def check_frame_of_reference_match(
        self,
        series1_datasets: List[Dataset],
        series2_datasets: List[Dataset]
    ) -> bool:
        """
        Check if two series share the same Frame of Reference UID.
        
        Args:
            series1_datasets: List of datasets from first series
            series2_datasets: List of datasets from second series
            
        Returns:
            True if both series have the same FrameOfReferenceUID, False otherwise
        """
        if not series1_datasets or not series2_datasets:
            return False
        
        # Get Frame of Reference UID from first slice of each series
        frame_ref_1 = getattr(series1_datasets[0], 'FrameOfReferenceUID', None)
        frame_ref_2 = getattr(series2_datasets[0], 'FrameOfReferenceUID', None)
        
        if frame_ref_1 is None or frame_ref_2 is None:
            return False
        
        return frame_ref_1 == frame_ref_2
    
    def get_slice_location(self, dataset: Dataset) -> Optional[float]:
        """
        Extract slice location from dataset.
        
        Tries SliceLocation tag first, then calculates from ImagePositionPatient.
        
        Args:
            dataset: DICOM dataset
            
        Returns:
            Slice location as float, or None if not available
        """
        # Try SliceLocation tag first (0020,1041)
        slice_location = getattr(dataset, 'SliceLocation', None)
        if slice_location is not None:
            try:
                return float(slice_location)
            except (ValueError, TypeError):
                pass
        
        # Fall back to ImagePositionPatient (0020,0032)
        # Use Z coordinate (third element) as slice location
        image_position = getattr(dataset, 'ImagePositionPatient', None)
        if image_position is not None and len(image_position) >= 3:
            try:
                return float(image_position[2])
            except (ValueError, TypeError, IndexError):
                pass
        
        return None
    
    def _get_sorted_slice_locations(
        self,
        datasets: List[Dataset],
        series_uid: str
    ) -> List[Tuple[int, float]]:
        """
        Get sorted list of (index, location) tuples for a series.
        
        Uses cache to avoid repeated calculations.
        
        Args:
            datasets: List of DICOM datasets
            series_uid: Series UID for caching
            
        Returns:
            List of (original_index, slice_location) tuples sorted by location
        """
        # Check cache
        if series_uid in self._slice_location_cache:
            return self._slice_location_cache[series_uid]
        
        # Build list of (index, location) pairs
        locations = []
        for idx, dataset in enumerate(datasets):
            location = self.get_slice_location(dataset)
            if location is not None:
                locations.append((idx, location))
        
        # Sort by location
        locations.sort(key=lambda x: x[1])
        
        # Cache result
        self._slice_location_cache[series_uid] = locations
        
        return locations
    
    def find_matching_slice(
        self,
        base_slice_idx: int,
        base_datasets: List[Dataset],
        overlay_datasets: List[Dataset]
    ) -> Tuple[Optional[int], Optional[int]]:
        """
        Find matching overlay slice(s) for a base slice.
        
        Returns either an exact match or two adjacent slices for interpolation.
        
        Args:
            base_slice_idx: Index of base slice
            base_datasets: List of base series datasets
            overlay_datasets: List of overlay series datasets
            
        Returns:
            Tuple of (slice_idx_1, slice_idx_2):
            - If exact match: (idx, None)
            - If interpolation needed: (lower_idx, upper_idx)
            - If no match possible: (None, None)
        """
        if base_slice_idx >= len(base_datasets):
            return (None, None)
        
        # Get base slice location
        base_location = self.get_slice_location(base_datasets[base_slice_idx])
        if base_location is None:
            return (None, None)
        
        # Get sorted overlay locations
        overlay_locations = self._get_sorted_slice_locations(
            overlay_datasets,
            self.overlay_series_uid or "overlay"
        )
        
        if not overlay_locations:
            return (None, None)
        
        # Find exact match or bracketing slices
        tolerance = 0.01  # mm tolerance for exact match
        
        for i, (idx, location) in enumerate(overlay_locations):
            if abs(location - base_location) < tolerance:
                # Exact match
                return (idx, None)
            
            if location > base_location:
                # Found first slice above base location
                if i == 0:
                    # Base is below all overlay slices
                    return (None, None)
                else:
                    # Return bracketing slices
                    lower_idx = overlay_locations[i - 1][0]
                    upper_idx = idx
                    return (lower_idx, upper_idx)
        
        # Base location is above all overlay slices
        return (None, None)
    
    def interpolate_overlay_slice(
        self,
        base_slice_idx: int,
        base_datasets: List[Dataset],
        overlay_datasets: List[Dataset]
    ) -> Optional[np.ndarray]:
        """
        Get overlay pixel array for base slice, with interpolation if needed.
        
        Args:
            base_slice_idx: Index of base slice
            base_datasets: List of base series datasets
            overlay_datasets: List of overlay series datasets
            
        Returns:
            Pixel array for overlay, or None if not available
        """
        # Find matching slice(s)
        idx1, idx2 = self.find_matching_slice(
            base_slice_idx, base_datasets, overlay_datasets
        )
        
        if idx1 is None:
            return None
        
        # Extract rescale parameters from overlay dataset
        overlay_ds = overlay_datasets[idx1]
        rescale_slope, rescale_intercept, _ = DICOMProcessor.get_rescale_parameters(overlay_ds)
        
        # Update rescale state tracking
        self.overlay_uses_rescaled = (rescale_slope is not None and rescale_intercept is not None)
        self._overlay_rescale_slope = rescale_slope
        self._overlay_rescale_intercept = rescale_intercept
        
        # Get pixel array from first slice
        try:
            array1 = overlay_datasets[idx1].pixel_array.astype(np.float32)
        except Exception as e:
            print(f"Error getting overlay pixel array: {e}")
            return None
        
        # Apply rescale transformation if parameters exist
        if self.overlay_uses_rescaled and rescale_slope is not None and rescale_intercept is not None:
            array1 = array1 * float(rescale_slope) + float(rescale_intercept)
        
        if idx2 is None:
            # Exact match, no interpolation needed
            return array1
        
        # Interpolation needed
        try:
            array2 = overlay_datasets[idx2].pixel_array.astype(np.float32)
        except Exception as e:
            print(f"Error getting second overlay pixel array: {e}")
            return array1  # Fall back to first slice
        
        # Apply rescale to second array if needed
        if self.overlay_uses_rescaled and rescale_slope is not None and rescale_intercept is not None:
            array2 = array2 * float(rescale_slope) + float(rescale_intercept)
        
        # Check array shapes match
        if array1.shape != array2.shape:
            print(f"Warning: Overlay slice shapes don't match for interpolation: "
                  f"{array1.shape} vs {array2.shape}")
            return array1
        
        # Get locations for interpolation weight
        base_location = self.get_slice_location(base_datasets[base_slice_idx])
        loc1 = self.get_slice_location(overlay_datasets[idx1])
        loc2 = self.get_slice_location(overlay_datasets[idx2])
        
        if base_location is None or loc1 is None or loc2 is None:
            return array1
        
        # Calculate interpolation weight
        # weight = 0 means all from slice1, weight = 1 means all from slice2
        weight = (base_location - loc1) / (loc2 - loc1)
        weight = np.clip(weight, 0.0, 1.0)
        
        # Linear interpolation
        interpolated = array1 * (1.0 - weight) + array2 * weight
        
        return interpolated
    
    def get_pixel_spacing(self, dataset: Dataset) -> Optional[Tuple[float, float]]:
        """
        Extract pixel spacing from dataset.
        
        Args:
            dataset: DICOM dataset
            
        Returns:
            Tuple of (row_spacing, col_spacing) in mm, or None if not available
        """
        pixel_spacing = getattr(dataset, 'PixelSpacing', None)
        if pixel_spacing is not None and len(pixel_spacing) >= 2:
            try:
                row_spacing = float(pixel_spacing[0])
                col_spacing = float(pixel_spacing[1])
                return (row_spacing, col_spacing)
            except (ValueError, TypeError, IndexError):
                pass
        
        return None
    
    def get_image_position_patient(self, dataset: Dataset) -> Optional[Tuple[float, float, float]]:
        """
        Extract image position patient from dataset.
        
        Args:
            dataset: DICOM dataset
            
        Returns:
            Tuple of (x, y, z) in mm, or None if not available
        """
        image_position = getattr(dataset, 'ImagePositionPatient', None)
        if image_position is not None and len(image_position) >= 3:
            try:
                x = float(image_position[0])
                y = float(image_position[1])
                z = float(image_position[2])
                return (x, y, z)
            except (ValueError, TypeError, IndexError):
                pass
        
        return None
    
    def get_series_spatial_info(self, datasets: List[Dataset]) -> Dict:
        """
        Get spatial information for a series.
        
        Args:
            datasets: List of DICOM datasets from a series
            
        Returns:
            Dictionary with spatial information:
            - pixel_spacing: (row_spacing, col_spacing) in mm
            - image_position: (x, y, z) in mm
            - field_of_view: (fov_x, fov_y) in mm (if calculable)
            - matrix_size: (rows, cols) in pixels
        """
        if not datasets:
            return {}
        
        first_ds = datasets[0]
        info = {}
        
        # Get pixel spacing
        pixel_spacing = self.get_pixel_spacing(first_ds)
        if pixel_spacing is not None:
            info['pixel_spacing'] = pixel_spacing
        
        # Get image position
        image_position = self.get_image_position_patient(first_ds)
        if image_position is not None:
            info['image_position'] = image_position
        
        # Get matrix size
        rows = getattr(first_ds, 'Rows', None)
        cols = getattr(first_ds, 'Columns', None)
        if rows is not None and cols is not None:
            info['matrix_size'] = (int(rows), int(cols))
            
            # Calculate field of view if we have both pixel spacing and matrix size
            if pixel_spacing is not None:
                fov_y = rows * pixel_spacing[0]  # row spacing
                fov_x = cols * pixel_spacing[1]  # column spacing
                info['field_of_view'] = (fov_x, fov_y)
        
        return info
    
    def calculate_translation_offset(
        self,
        base_dataset: Dataset,
        overlay_dataset: Dataset,
        base_pixel_spacing: Tuple[float, float],
        overlay_pixel_spacing: Tuple[float, float]
    ) -> Optional[Tuple[float, float]]:
        """
        Calculate translation offset between base and overlay images.
        
        Uses ImagePositionPatient to determine the physical offset between the two
        images, then converts to pixel offset in base image coordinates.
        
        Args:
            base_dataset: DICOM dataset from base series
            overlay_dataset: DICOM dataset from overlay series
            base_pixel_spacing: (row_spacing, col_spacing) for base in mm
            overlay_pixel_spacing: (row_spacing, col_spacing) for overlay in mm
            
        Returns:
            Tuple of (x_offset, y_offset) in pixels (base image coordinates),
            or None if ImagePositionPatient is not available
        """
        # Get image positions
        base_ipp = self.get_image_position_patient(base_dataset)
        overlay_ipp = self.get_image_position_patient(overlay_dataset)
        
        # DEBUG - commented out
        # print(f"\n[OFFSET CALC DEBUG] calculate_translation_offset called")
        # print(f"  base IPP: {base_ipp}")
        # print(f"  overlay IPP: {overlay_ipp}")
        # print(f"  base_pixel_spacing: {base_pixel_spacing}")
        # print(f"  overlay_pixel_spacing: {overlay_pixel_spacing}")
        
        if base_ipp is None or overlay_ipp is None:
            # print(f"  Result: None (IPP missing)")
            return None
        
        # Calculate physical offset in mm
        # ImagePositionPatient is [x, y, z] where:
        # x increases left to right
        # y increases front to back
        # z increases foot to head
        offset_mm_x = overlay_ipp[0] - base_ipp[0]
        offset_mm_y = overlay_ipp[1] - base_ipp[1]
        
        # DEBUG - commented out
        # print(f"  Physical offset (mm): X={offset_mm_x:.2f}, Y={offset_mm_y:.2f}")
        
        # Convert to pixel offset in base image coordinates
        # Note: Pixel spacing is [row_spacing, col_spacing] where:
        # - row_spacing is the spacing between rows (vertical, relates to y)
        # - col_spacing is the spacing between columns (horizontal, relates to x)
        offset_px_x = offset_mm_x / base_pixel_spacing[1]  # column spacing
        offset_px_y = offset_mm_y / base_pixel_spacing[0]  # row spacing
        
        # DEBUG - commented out
        # print(f"  Pixel offset: X={offset_px_x:.2f}, Y={offset_px_y:.2f} pixels")
        
        return (offset_px_x, offset_px_y)
    
    def get_available_series_for_fusion(
        self,
        studies: Dict,
        current_study_uid: str
    ) -> List[Tuple[str, str]]:
        """
        Get list of available series for fusion from current study.
        
        Args:
            studies: Dictionary of studies {study_uid: {series_uid: [datasets]}}
            current_study_uid: Current study UID
            
        Returns:
            List of (series_uid, display_name) tuples
        """
        if not studies or current_study_uid not in studies:
            return []
        
        series_list = []
        study_series = studies[current_study_uid]
        
        for series_uid, datasets in study_series.items():
            if not datasets:
                continue
            
            # Get series information for display name
            first_dataset = datasets[0]
            series_number = getattr(first_dataset, 'SeriesNumber', None)
            series_desc = getattr(first_dataset, 'SeriesDescription', '')
            modality = getattr(first_dataset, 'Modality', '')
            
            # Build display name
            display_parts = []
            if series_number is not None:
                display_parts.append(f"S{series_number}")
            if modality:
                display_parts.append(modality)
            if series_desc:
                display_parts.append(series_desc)
            
            display_name = ' - '.join(display_parts) if display_parts else series_uid[:20]
            
            series_list.append((series_uid, display_name))
        
        # Sort by series number if available
        def get_series_num(item):
            series_uid, _ = item
            datasets = study_series.get(series_uid, [])
            if datasets:
                series_num = getattr(datasets[0], 'SeriesNumber', None)
                try:
                    return int(series_num) if series_num is not None else 999999
                except (ValueError, TypeError):
                    return 999999
            return 999999
        
        series_list.sort(key=get_series_num)
        
        return series_list


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
    - SimpleITK for 3D resampling (Phase 2)
"""

import numpy as np
from typing import Optional, List, Tuple, Dict
from pydicom.dataset import Dataset

from core.image_resampler import ImageResampler
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
        
        # Window/level for overlay (per-subwindow state)
        self.overlay_window: float = 1000.0
        self.overlay_level: float = 500.0
        
        # Phase 2: Resampling mode and settings
        self.resampling_mode: str = 'auto'  # 'auto', 'fast', 'high_accuracy'
        self.interpolation_method: str = 'linear'  # 'linear', 'nearest', 'cubic', 'b-spline'
        
        # Phase 2: Image resampler for 3D volume resampling
        self.image_resampler = ImageResampler()
        
        # Cache for slice locations
        self._slice_location_cache: Dict[str, List[Tuple[int, float]]] = {}
        
        # Cache for resampling decision (to avoid repeated checks)
        self._resampling_decision_cache: Optional[Tuple[bool, str]] = None
        self._resampling_decision_cache_key: Optional[Tuple[str, str]] = None
        
        # Cache for alignment (offset and scaling) per base-overlay pair
        # Key: (base_series_uid, overlay_series_uid), Value: {'scale': (x, y), 'offset': (x, y)}
        self._alignment_cache: Dict[Tuple[str, str], Dict[str, Optional[Tuple[float, float]]]] = {}
    
    def set_base_series(self, series_uid: str) -> None:
        """
        Set the base (anatomical) series.
        
        Args:
            series_uid: Series instance UID for base series
        """
        old_base_uid = self.base_series_uid
        self.base_series_uid = series_uid
        # Clear alignment cache entries involving old base
        if old_base_uid:
            self.clear_alignment_cache(old_base_uid)
    
    def set_overlay_series(self, series_uid: str) -> None:
        """
        Set the overlay (functional) series.
        
        Args:
            series_uid: Series instance UID for overlay series
        """
        old_overlay_uid = self.overlay_series_uid
        self.overlay_series_uid = series_uid
        # Clear cache when overlay series changes
        self._slice_location_cache.clear()
        # Clear resampling decision cache
        self._resampling_decision_cache = None
        self._resampling_decision_cache_key = None
        # Clear alignment cache entries involving old overlay
        if old_overlay_uid:
            self.clear_alignment_cache(old_overlay_uid)
    
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
    
    def _should_use_3d_resampling(
        self,
        base_datasets: List[Dataset],
        overlay_datasets: List[Dataset]
    ) -> Tuple[bool, str]:
        """
        Determine if 3D resampling should be used based on mode and compatibility.
        
        Args:
            base_datasets: List of base series datasets
            overlay_datasets: List of overlay series datasets
            
        Returns:
            Tuple of (use_3d: bool, reason: str)
        """
        # Check cache first
        cache_key = (self.base_series_uid, self.overlay_series_uid)
        if (self._resampling_decision_cache is not None and 
            self._resampling_decision_cache_key == cache_key):
            needs_3d, reason = self._resampling_decision_cache
        else:
            # Check compatibility
            needs_3d, reason = self.image_resampler.needs_resampling(
                overlay_datasets, base_datasets
            )
            # Cache the result
            self._resampling_decision_cache = (needs_3d, reason)
            self._resampling_decision_cache_key = cache_key
        
        # Apply user mode selection
        if self.resampling_mode == 'fast':
            # User forced 2D mode
            return (False, "User selected Fast Mode (2D)")
        elif self.resampling_mode == 'high_accuracy':
            # User forced 3D mode
            return (True, "User selected High Accuracy Mode (3D)")
        else:
            # Auto mode - use compatibility check
            return (needs_3d, reason)
    
    def interpolate_overlay_slice(
        self,
        base_slice_idx: int,
        base_datasets: List[Dataset],
        overlay_datasets: List[Dataset]
    ) -> Optional[np.ndarray]:
        """
        Get overlay pixel array for base slice, with interpolation if needed.
        
        Phase 2: Uses 3D resampling when needed, falls back to 2D interpolation otherwise.
        
        Args:
            base_slice_idx: Index of base slice
            base_datasets: List of base series datasets
            overlay_datasets: List of overlay series datasets
            
        Returns:
            Pixel array for overlay, or None if not available
        """
        # DEBUG: Log dataset ordering when passed to get_resampled_slice
        if base_datasets and len(base_datasets) > 0:
            print(f"[3D RESAMPLE DEBUG] interpolate_overlay_slice: base_datasets order check")
            print(f"[3D RESAMPLE DEBUG]   Total base datasets: {len(base_datasets)}")
            print(f"[3D RESAMPLE DEBUG]   Requested slice_idx: {base_slice_idx}")
            # Log first 3 and last 3 slice locations
            for i in [0, 1, 2] if len(base_datasets) > 2 else range(len(base_datasets)):
                ds = base_datasets[i]
                loc = self.get_slice_location(ds)
                print(f"[3D RESAMPLE DEBUG]   Base dataset[{i}]: SliceLocation={loc}")
            if len(base_datasets) > 3:
                for i in range(max(3, len(base_datasets)-3), len(base_datasets)):
                    ds = base_datasets[i]
                    loc = self.get_slice_location(ds)
                    print(f"[3D RESAMPLE DEBUG]   Base dataset[{i}]: SliceLocation={loc}")
        
        if overlay_datasets and len(overlay_datasets) > 0:
            print(f"[3D RESAMPLE DEBUG] interpolate_overlay_slice: overlay_datasets order check")
            print(f"[3D RESAMPLE DEBUG]   Total overlay datasets: {len(overlay_datasets)}")
            # Log first 3 and last 3 slice locations
            for i in [0, 1, 2] if len(overlay_datasets) > 2 else range(len(overlay_datasets)):
                ds = overlay_datasets[i]
                loc = self.get_slice_location(ds)
                print(f"[3D RESAMPLE DEBUG]   Overlay dataset[{i}]: SliceLocation={loc}")
            if len(overlay_datasets) > 3:
                for i in range(max(3, len(overlay_datasets)-3), len(overlay_datasets)):
                    ds = overlay_datasets[i]
                    loc = self.get_slice_location(ds)
                    print(f"[3D RESAMPLE DEBUG]   Overlay dataset[{i}]: SliceLocation={loc}")
        
        # Phase 2: Check if 3D resampling is needed
        use_3d, reason = self._should_use_3d_resampling(base_datasets, overlay_datasets)
        
        if use_3d:
            # Use 3D resampling
            try:
                resampled_slice = self.image_resampler.get_resampled_slice(
                    overlay_datasets,
                    base_datasets,
                    base_slice_idx,
                    use_cache=True,
                    interpolator=self.interpolation_method,
                    overlay_series_uid=self.overlay_series_uid,
                    reference_series_uid=self.base_series_uid
                )
                if resampled_slice is not None:
                    # Rescale is already applied in image_resampler.get_resampled_slice()
                    return resampled_slice.astype(np.float32)
                else:
                    print(f"Warning: 3D resampling returned None, falling back to 2D")
            except Exception as e:
                print(f"Error in 3D resampling: {e}, falling back to 2D")
                import traceback
                traceback.print_exc()
        
        # Fall back to 2D interpolation (original Phase 1 method)
        # Find matching slice(s)
        idx1, idx2 = self.find_matching_slice(
            base_slice_idx, base_datasets, overlay_datasets
        )
        
        if idx1 is None:
            return None
        
        # Get pixel array from first slice
        try:
            array1 = overlay_datasets[idx1].pixel_array.astype(np.float32)
            # Apply rescale if parameters exist
            rescale_slope, rescale_intercept, _ = DICOMProcessor.get_rescale_parameters(overlay_datasets[idx1])
            if rescale_slope is not None and rescale_intercept is not None:
                array1 = array1.astype(np.float32) * float(rescale_slope) + float(rescale_intercept)
        except Exception as e:
            print(f"Error getting overlay pixel array: {e}")
            return None
        
        if idx2 is None:
            # Exact match, no interpolation needed
            return array1
        
        # Interpolation needed
        try:
            array2 = overlay_datasets[idx2].pixel_array.astype(np.float32)
            # Apply rescale if parameters exist
            rescale_slope, rescale_intercept, _ = DICOMProcessor.get_rescale_parameters(overlay_datasets[idx2])
            if rescale_slope is not None and rescale_intercept is not None:
                array2 = array2.astype(np.float32) * float(rescale_slope) + float(rescale_intercept)
        except Exception as e:
            print(f"Error getting second overlay pixel array: {e}")
            return array1  # Fall back to first slice
        
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
        
        # Note: Rescale already applied to array1 and array2, so interpolated is already rescaled
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
        
        print(f"\n[OFFSET CALC DEBUG] calculate_translation_offset called")
        print(f"  base IPP: {base_ipp}")
        print(f"  overlay IPP: {overlay_ipp}")
        print(f"  base_pixel_spacing: {base_pixel_spacing}")
        print(f"  overlay_pixel_spacing: {overlay_pixel_spacing}")
        
        if base_ipp is None or overlay_ipp is None:
            print(f"  Result: None (IPP missing)")
            return None
        
        # Calculate physical offset in mm
        # ImagePositionPatient is [x, y, z] where:
        # x increases left to right
        # y increases front to back
        # z increases foot to head
        offset_mm_x = overlay_ipp[0] - base_ipp[0]
        offset_mm_y = overlay_ipp[1] - base_ipp[1]
        
        print(f"  Physical offset (mm): X={offset_mm_x:.2f}, Y={offset_mm_y:.2f}")
        
        # Convert to pixel offset in base image coordinates
        # Note: Pixel spacing is [row_spacing, col_spacing] where:
        # - row_spacing is the spacing between rows (vertical, relates to y)
        # - col_spacing is the spacing between columns (horizontal, relates to x)
        offset_px_x = offset_mm_x / base_pixel_spacing[1]  # column spacing
        offset_px_y = offset_mm_y / base_pixel_spacing[0]  # row spacing
        
        print(f"  Pixel offset: X={offset_px_x:.2f}, Y={offset_px_y:.2f} pixels")
        
        return (offset_px_x, offset_px_y)
    
    def set_alignment(
        self,
        base_series_uid: Optional[str],
        overlay_series_uid: Optional[str],
        scale: Optional[Tuple[float, float]],
        offset: Optional[Tuple[float, float]]
    ) -> None:
        """
        Store alignment info (scaling and offset) for a base-overlay pair.
        
        Args:
            base_series_uid: Base series UID
            overlay_series_uid: Overlay series UID
            scale: (scale_x, scale_y) tuple or None
            offset: (offset_x, offset_y) tuple or None
        """
        if not base_series_uid or not overlay_series_uid:
            return
        self._alignment_cache[(base_series_uid, overlay_series_uid)] = {
            'scale': scale,
            'offset': offset,
        }
    
    def get_alignment(
        self,
        base_series_uid: Optional[str],
        overlay_series_uid: Optional[str]
    ) -> Optional[Dict[str, Optional[Tuple[float, float]]]]:
        """
        Retrieve cached alignment (scaling and offset) for a base-overlay pair.
        
        Args:
            base_series_uid: Base series UID
            overlay_series_uid: Overlay series UID
            
        Returns:
            Dictionary with 'scale' and 'offset' keys, or None if not cached
        """
        if not base_series_uid or not overlay_series_uid:
            return None
        # Don't return cache for self-pair (same series as base and overlay)
        if base_series_uid == overlay_series_uid:
            return None
        return self._alignment_cache.get((base_series_uid, overlay_series_uid))
    
    def clear_alignment_cache(self, series_uid: Optional[str] = None) -> None:
        """
        Clear alignment cache.
        
        Args:
            series_uid: If provided, clear only entries involving this series UID.
                       If None, clear entire cache.
        """
        if series_uid is None:
            self._alignment_cache.clear()
            return
        
        # Remove entries where either key component matches
        keys_to_delete = [
            key for key in self._alignment_cache.keys()
            if series_uid in key
        ]
        for key in keys_to_delete:
            del self._alignment_cache[key]
    
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
    
    def get_resampling_status(
        self,
        base_datasets: List[Dataset],
        overlay_datasets: List[Dataset]
    ) -> Tuple[str, str]:
        """
        Get current resampling status for UI display.
        
        Args:
            base_datasets: List of base series datasets
            overlay_datasets: List of overlay series datasets
            
        Returns:
            Tuple of (mode_display: str, reason: str)
            Examples:
            - ("Auto (2D Fast Mode)", "Compatible: same orientation")
            - ("Auto (3D High Accuracy)", "Different orientation detected")
            - ("Fast Mode (2D)", "User selected Fast Mode")
            - ("High Accuracy (3D)", "User selected High Accuracy Mode")
        """
        if not base_datasets or not overlay_datasets:
            return ("Disabled", "No datasets available")
        
        use_3d, reason = self._should_use_3d_resampling(base_datasets, overlay_datasets)
        
        if self.resampling_mode == 'fast':
            return ("Fast Mode (2D)", reason)
        elif self.resampling_mode == 'high_accuracy':
            return ("High Accuracy (3D)", reason)
        else:
            # Auto mode
            if use_3d:
                return ("Auto (3D High Accuracy)", reason)
            else:
                return ("Auto (2D Fast Mode)", reason)


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

import logging

import numpy as np
from typing import Any, Optional, List, Tuple, Dict
from pydicom.dataset import Dataset

from core import fusion_handler_io as fusion_io
from core.image_resampler import ImageResampler
from core.dicom_processor import DICOMProcessor

from utils.debug_flags import DEBUG_OFFSET
from utils.log_sanitizer import sanitized_format_exc

_logger = logging.getLogger(__name__)


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
        self.resampling_mode: str = 'high_accuracy'  # 'fast', 'high_accuracy'
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
        
        # Track actual resampling mode used (True = 3D used, False = 2D fallback, None = not determined yet)
        self._actual_resampling_mode_used: Optional[bool] = None
        # Store failure reason when 3D fails
        self._resampling_failure_reason: Optional[str] = None
    
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
        # Clear actual mode tracking when series changes
        self._actual_resampling_mode_used = None
        self._resampling_failure_reason = None
    
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
        # Clear actual mode tracking when series changes
        self._actual_resampling_mode_used = None
        self._resampling_failure_reason = None
        # Clear alignment cache entries involving old overlay
        if old_overlay_uid:
            self.clear_alignment_cache(old_overlay_uid)
    
    def set_resampling_mode(self, mode: str) -> None:
        """
        Set resampling mode and invalidate actual-mode tracking until next render.
        
        Call this when the user changes the resampling mode (e.g. Fast <-> High Accuracy).
        This clears _actual_resampling_mode_used and _resampling_failure_reason so that
        status logic uses the predicted mode until the next slice is rendered. When the
        coordinator forces Fast after a real 3D failure, it should assign
        resampling_mode = 'fast' directly so actual/failure reason are not cleared.
        
        Args:
            mode: 'fast' or 'high_accuracy'
        """
        self.resampling_mode = mode
        self._actual_resampling_mode_used = None
        self._resampling_failure_reason = None
        self._resampling_decision_cache = None
        self._resampling_decision_cache_key = None
    
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
        return fusion_io.check_frame_of_reference_match(
            series1_datasets, series2_datasets
        )
    
    def get_slice_location(self, dataset: Dataset) -> Optional[float]:
        """
        Extract slice location from dataset.
        
        Tries SliceLocation tag first, then calculates from ImagePositionPatient.
        
        Args:
            dataset: DICOM dataset
            
        Returns:
            Slice location as float, or None if not available
        """
        return fusion_io.read_slice_location(dataset)
    
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
        
        locations = fusion_io.sorted_slice_index_locations(datasets)
        self._slice_location_cache[series_uid] = locations
        return locations
    
    def has_duplicate_locations(
        self,
        datasets: List[Dataset],
        tolerance: float = 0.01
    ) -> Tuple[bool, int]:
        """
        Check if a series has multiple slices at the same location.
        
        Args:
            datasets: List of DICOM datasets
            tolerance: Tolerance in mm for considering locations as duplicates (default: 0.01mm)
            
        Returns:
            Tuple of (has_duplicates: bool, duplicate_count: int)
            duplicate_count is the number of slices that are duplicates (total slices - unique locations)
        """
        if not datasets:
            return (False, 0)
        
        locations = fusion_io.sorted_slice_index_locations(datasets)
        if len(locations) < 2:
            return (False, 0)
        
        # Check for duplicates
        unique_locations = []
        duplicate_count = 0
        
        for idx, location in locations:
            is_duplicate = False
            for seen_loc in unique_locations:
                if abs(location - seen_loc) < tolerance:
                    is_duplicate = True
                    duplicate_count += 1
                    break
            
            if not is_duplicate:
                unique_locations.append(location)
        
        return (duplicate_count > 0, duplicate_count)
    
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
        # Check cache first (only when both series UIDs are known).
        cache_key: Optional[Tuple[str, str]] = None
        if self.base_series_uid is not None and self.overlay_series_uid is not None:
            cache_key = (self.base_series_uid, self.overlay_series_uid)
        if (
            self._resampling_decision_cache is not None
            and self._resampling_decision_cache_key == cache_key
        ):
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
            # Default to high_accuracy for unknown modes
            return (True, "Defaulting to High Accuracy Mode (3D)")
    
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
        # if base_datasets and len(base_datasets) > 0:
        #     print(f"[3D RESAMPLE DEBUG] interpolate_overlay_slice: base_datasets order check")
        #     print(f"[3D RESAMPLE DEBUG]   Total base datasets: {len(base_datasets)}")
        #     print(f"[3D RESAMPLE DEBUG]   Requested slice_idx: {base_slice_idx}")
        #     # Log first 3 and last 3 slice locations
        #     for i in [0, 1, 2] if len(base_datasets) > 2 else range(len(base_datasets)):
        #         ds = base_datasets[i]
        #         loc = self.get_slice_location(ds)
        #         print(f"[3D RESAMPLE DEBUG]   Base dataset[{i}]: SliceLocation={loc}")
        #     if len(base_datasets) > 3:
        #         for i in range(max(3, len(base_datasets)-3), len(base_datasets)):
        #             ds = base_datasets[i]
        #             loc = self.get_slice_location(ds)
        #             print(f"[3D RESAMPLE DEBUG]   Base dataset[{i}]: SliceLocation={loc}")
        # 
        # if overlay_datasets and len(overlay_datasets) > 0:
        #     print(f"[3D RESAMPLE DEBUG] interpolate_overlay_slice: overlay_datasets order check")
        #     print(f"[3D RESAMPLE DEBUG]   Total overlay datasets: {len(overlay_datasets)}")
        #     # Log first 3 and last 3 slice locations
        #     for i in [0, 1, 2] if len(overlay_datasets) > 2 else range(len(overlay_datasets)):
        #         ds = overlay_datasets[i]
        #         loc = self.get_slice_location(ds)
        #         print(f"[3D RESAMPLE DEBUG]   Overlay dataset[{i}]: SliceLocation={loc}")
        #     if len(overlay_datasets) > 3:
        #         for i in range(max(3, len(overlay_datasets)-3), len(overlay_datasets)):
        #             ds = overlay_datasets[i]
        #             loc = self.get_slice_location(ds)
        #             print(f"[3D RESAMPLE DEBUG]   Overlay dataset[{i}]: SliceLocation={loc}")
        
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
                    # 3D resampling succeeded
                    self._actual_resampling_mode_used = True
                    self._resampling_failure_reason = None
                    # Rescale is already applied in image_resampler.get_resampled_slice()
                    return resampled_slice.astype(np.float32)
                else:
                    # 3D resampling returned None, fall back to 2D
                    self._actual_resampling_mode_used = False
                    self._resampling_failure_reason = "3D resampling returned None"
                    print(f"Warning: 3D resampling returned None, falling back to 2D")
            except Exception as e:
                # 3D resampling failed with exception, fall back to 2D
                self._actual_resampling_mode_used = False
                error_msg = str(e)
                # Extract meaningful error message (e.g., zero slice spacing)
                if "Zero-valued spacing" in error_msg or "zero slice spacing" in error_msg.lower():
                    self._resampling_failure_reason = "Zero-valued spacing not supported for 3D mode"
                else:
                    self._resampling_failure_reason = f"3D resampling error: {error_msg[:100]}"
                print(f"Error in 3D resampling: {e}, falling back to 2D")
                _logger.debug("%s", sanitized_format_exc())
        else:
            # 2D mode was selected/predicted, so actual mode is 2D
            self._actual_resampling_mode_used = False
            self._resampling_failure_reason = None
        
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
        
        return fusion_io.linear_blend_rescaled_slices(
            array1, array2, base_location, loc1, loc2
        )
    
    def get_pixel_spacing(self, dataset: Dataset) -> Optional[Tuple[float, float]]:
        """
        Extract pixel spacing from dataset.
        
        Args:
            dataset: DICOM dataset
            
        Returns:
            Tuple of (row_spacing, col_spacing) in mm, or None if not available
        """
        return fusion_io.read_pixel_spacing(dataset)

    def get_pixel_spacing_with_source(
        self, dataset: Dataset
    ) -> Tuple[Optional[Tuple[float, float]], Optional[str]]:
        """
        Extract pixel spacing from dataset along with information about the source.

        Priority:
        1) PixelSpacing / ImagerPixelSpacing (true DICOM spacing)
        2) Heuristic estimates based on ReconstructionDiameter and matrix size

        Returns:
            ((row_spacing, col_spacing) in mm, source_string) or (None, None)
        """
        return fusion_io.read_pixel_spacing_with_source(dataset)
    
    def get_image_position_patient(self, dataset: Dataset) -> Optional[Tuple[float, float, float]]:
        """
        Extract image position patient from dataset.
        
        Args:
            dataset: DICOM dataset
            
        Returns:
            Tuple of (x, y, z) in mm, or None if not available
        """
        return fusion_io.read_image_position_patient(dataset)
    
    def get_series_spatial_info(self, datasets: List[Dataset]) -> Dict[str, Any]:
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
        return fusion_io.series_spatial_info_dict(datasets)
    
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

        if DEBUG_OFFSET:
            print(f"\n[OFFSET CALC DEBUG] calculate_translation_offset called")
            print(f"  base IPP: {base_ipp}")
            print(f"  overlay IPP: {overlay_ipp}")
            print(f"  base_pixel_spacing: {base_pixel_spacing}")
            print(f"  overlay_pixel_spacing: {overlay_pixel_spacing}")

        if base_ipp is None or overlay_ipp is None:
            if DEBUG_OFFSET:
                print(f"  Result: None (IPP missing)")
            return None

        # ImagePositionPatient is [x, y, z] where:
        # x increases left to right
        # y increases front to back
        # z increases foot to head
        if DEBUG_OFFSET:
            offset_mm_x = overlay_ipp[0] - base_ipp[0]
            offset_mm_y = overlay_ipp[1] - base_ipp[1]
            print(f"  Physical offset (mm): X={offset_mm_x:.2f}, Y={offset_mm_y:.2f}")

        offset_px_x, offset_px_y = fusion_io.translation_offset_pixels_from_ipps(
            base_ipp, overlay_ipp, base_pixel_spacing
        )

        if DEBUG_OFFSET:
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
    
    def get_actual_resampling_mode_used(self) -> Optional[bool]:
        """
        Get the actual resampling mode that was used.
        
        Returns:
            True if 3D resampling was actually used, False if 2D fallback was used,
            None if mode hasn't been determined yet (no resampling attempted)
        """
        return self._actual_resampling_mode_used
    
    def get_resampling_failure_reason(self) -> Optional[str]:
        """
        Get the reason why 3D resampling failed (if it did).
        
        Returns:
            Failure reason string, or None if 3D succeeded or wasn't attempted
        """
        return self._resampling_failure_reason
    
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
        studies: Dict[str, Dict[str, List[Dataset]]],
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
            - ("2D Mode (3D Failed)", "3D resampling failed (zero slice spacing), using 2D fallback")
        """
        if not base_datasets or not overlay_datasets:
            return ("Disabled", "No datasets available")
        
        use_3d, reason = self._should_use_3d_resampling(base_datasets, overlay_datasets)
        
        # Check actual mode used - if 3D was attempted but failed, show that
        actual_mode = self._actual_resampling_mode_used
        if actual_mode is False and use_3d:
            # 3D was predicted but failed, show fallback status
            failure_reason = self._resampling_failure_reason or "3D resampling failed"
            if self.resampling_mode == 'fast':
                return ("Fast Mode (2D)", reason)
            else:
                return ("2D Mode (3D Failed)", f"{failure_reason}, using 2D fallback")
        
        if self.resampling_mode == 'fast':
            return ("Fast Mode (2D)", reason)
        elif self.resampling_mode == 'high_accuracy':
            return ("High Accuracy (3D)", reason)
        else:
            # Default to high_accuracy for unknown modes
            return ("High Accuracy (3D)", reason)


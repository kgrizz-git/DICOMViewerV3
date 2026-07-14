"""
Image Resampler

This module provides 3D volume resampling capabilities for image fusion using SimpleITK.
Handles DICOM series with different pixel spacings, orientations, or slice thicknesses.

Inputs:
    - DICOM datasets from base and overlay series
    - Resampling parameters (interpolation method)
    
Outputs:
    - Resampled 3D volumes or 2D slices
    - Compatibility checks for 2D vs 3D resampling
    
Requirements:
    - SimpleITK for 3D image processing
    - numpy for array operations
    - pydicom for DICOM tag access
"""

import logging
import threading
from collections import OrderedDict
from typing import Any, ClassVar

import numpy as np
from pydicom.dataset import Dataset

sitk: Any = None
sitk_available: bool = False
try:
    import SimpleITK as _sitk
    sitk = _sitk
    sitk_available = True
except ImportError:
    pass

from core.dicom_processor import DICOMProcessor
from utils.dicom_utils import (
    get_image_orientation,
    get_image_position,
    get_pixel_spacing,
    get_slice_thickness,
)
from utils.log_sanitizer import sanitized_format_exc

_logger = logging.getLogger(__name__)


class ImageResampler:
    """
    Handles 3D volume resampling for image fusion.
    
    Responsibilities:
    - Convert DICOM series to SimpleITK images with proper spatial metadata
    - Resample volumes to match reference grid
    - Cache resampled volumes for performance
    - Determine when 3D resampling is needed vs 2D resize
    """

    _MAX_CACHE_ENTRIES = 3

    # Interpolation method mapping
    INTERPOLATION_METHODS: ClassVar[dict[str, Any]] = {
        'linear': sitk.sitkLinear if sitk_available else None,
        'nearest': sitk.sitkNearestNeighbor if sitk_available else None,
        'cubic': sitk.sitkBSpline if sitk_available else None,
        'b-spline': sitk.sitkBSpline if sitk_available else None,
    }

    def __init__(self):
        """Initialize image resampler with cache."""
        if not sitk_available:
            print("Warning: SimpleITK not available. 3D resampling will not work.")

        # Cache for resampled volumes: key = (overlay_uid, base_uid), value = sitk.Image
        # OrderedDict for LRU eviction (bounded by _MAX_CACHE_ENTRIES)
        self._cache: OrderedDict[tuple[str, str], Any] = OrderedDict()
        self._cache_lock = threading.Lock()  # For thread-safe caching

        # Numpy array cache: avoids repeated sitk_to_numpy() on every scroll
        # key = same as _cache (overlay_uid, base_uid), value = np.ndarray (z, y, x)
        self._numpy_cache: dict[tuple[str, str], np.ndarray] = {}

        # Sorted reference datasets cache: avoids O(N^2) sort+filter per scroll
        # key = reference_series_uid, value = sorted+filtered dataset list
        self._sorted_ref_cache: dict[str, list[Dataset]] = {}

    def dicom_series_to_sitk(
        self,
        datasets: list[Dataset],
        series_uid: str | None = None
    ) -> Any | None:
        """
        Convert DICOM series to SimpleITK image with proper spatial metadata.
        
        Handles ImagePositionPatient, ImageOrientationPatient, PixelSpacing, SliceThickness.
        Sorts datasets by slice location before stacking.
        
        Args:
            datasets: List of DICOM datasets (may be unsorted)
            series_uid: Optional series UID for debugging
            
        Returns:
            SimpleITK image with proper origin, spacing, and direction, or None if conversion fails
        """
        if not sitk_available:
            return None

        if not datasets:
            return None

        try:
            # DEBUG: Log dataset order before sorting
            # if datasets and len(datasets) > 0:
            #     print(f"[3D RESAMPLE DEBUG] dicom_series_to_sitk: Input datasets order check")
            #     print(f"[3D RESAMPLE DEBUG]   Series UID: {series_uid[:30] if series_uid else 'None'}...")
            #     print(f"[3D RESAMPLE DEBUG]   Total input datasets: {len(datasets)}")
            #     # Log first 3 and last 3 slice locations
            #     for i in [0, 1, 2] if len(datasets) > 2 else range(len(datasets)):
            #         ds = datasets[i]
            #         slice_loc = getattr(ds, 'SliceLocation', None)
            #         if slice_loc is None and hasattr(ds, 'ImagePositionPatient'):
            #             ipp = ds.ImagePositionPatient
            #             slice_loc = float(ipp[2]) if ipp and len(ipp) >= 3 else None
            #         print(f"[3D RESAMPLE DEBUG]   Input dataset[{i}]: SliceLocation={slice_loc}")
            #     if len(datasets) > 3:
            #         for i in range(max(3, len(datasets)-3), len(datasets)):
            #             ds = datasets[i]
            #             slice_loc = getattr(ds, 'SliceLocation', None)
            #             if slice_loc is None and hasattr(ds, 'ImagePositionPatient'):
            #                 ipp = ds.ImagePositionPatient
            #                 slice_loc = float(ipp[2]) if ipp and len(ipp) >= 3 else None
            #             print(f"[3D RESAMPLE DEBUG]   Input dataset[{i}]: SliceLocation={slice_loc}")

            # Sort datasets by slice location
            sorted_datasets = self._sort_datasets_by_location(datasets)
            if not sorted_datasets:
                print(f"Warning: Could not sort datasets for series {series_uid}")
                return None

            # Filter duplicate locations (keep first occurrence of each unique location)
            # This prevents zero-valued spacing errors when multiple slices share the same location
            filtered_datasets = self._filter_duplicate_locations(sorted_datasets)
            if not filtered_datasets:
                print(f"Warning: No valid slices after filtering duplicates for series {series_uid}")
                return None

            # Use filtered datasets for all subsequent processing
            sorted_datasets = filtered_datasets

            # DEBUG: Log dataset order after sorting
            # if sorted_datasets and len(sorted_datasets) > 0:
            #     print(f"[3D RESAMPLE DEBUG] dicom_series_to_sitk: Sorted datasets order check")
            #     print(f"[3D RESAMPLE DEBUG]   Total sorted datasets: {len(sorted_datasets)}")
            #     # Log first 3 and last 3 slice locations
            #     for i in [0, 1, 2] if len(sorted_datasets) > 2 else range(len(sorted_datasets)):
            #         ds = sorted_datasets[i]
            #         slice_loc = getattr(ds, 'SliceLocation', None)
            #         if slice_loc is None and hasattr(ds, 'ImagePositionPatient'):
            #             ipp = ds.ImagePositionPatient
            #             slice_loc = float(ipp[2]) if ipp and len(ipp) >= 3 else None
            #         print(f"[3D RESAMPLE DEBUG]   Sorted dataset[{i}]: SliceLocation={slice_loc}")
            #     if len(sorted_datasets) > 3:
            #         for i in range(max(3, len(sorted_datasets)-3), len(sorted_datasets)):
            #             ds = sorted_datasets[i]
            #             slice_loc = getattr(ds, 'SliceLocation', None)
            #             if slice_loc is None and hasattr(ds, 'ImagePositionPatient'):
            #                 ipp = ds.ImagePositionPatient
            #                 slice_loc = float(ipp[2]) if ipp and len(ipp) >= 3 else None
            #             print(f"[3D RESAMPLE DEBUG]   Sorted dataset[{i}]: SliceLocation={slice_loc}")

            # Extract pixel arrays with per-slice rescale applied.
            # Rescaling before stacking handles series where
            # RescaleSlope/Intercept varies across slices (e.g. some PET).
            pixel_arrays = []
            for ds in sorted_datasets:
                try:
                    array = ds.pixel_array.astype(np.float32)
                    rescale_slope, rescale_intercept, _ = (
                        DICOMProcessor.get_rescale_parameters(ds)
                    )
                    if rescale_slope is not None and rescale_intercept is not None:
                        array = array * float(rescale_slope) + float(rescale_intercept)
                    pixel_arrays.append(array)
                except Exception as e:
                    print(f"Error extracting pixel array: {e}")
                    return None

            if not pixel_arrays:
                return None

            # Stack into 3D volume (z, y, x) - SimpleITK expects this order
            volume = np.stack(pixel_arrays, axis=0)

            # Create SimpleITK image
            sitk_image = sitk.GetImageFromArray(volume)

            # Extract spatial information from first dataset
            ds = sorted_datasets[0]

            # Origin (ImagePositionPatient) - SimpleITK uses (x, y, z)
            ipp_arr = get_image_position(ds)
            if ipp_arr is not None:
                sitk_image.SetOrigin(ipp_arr.tolist())

            # Pixel spacing
            pixel_spacing = [1.0, 1.0]
            ps_tuple = get_pixel_spacing(ds)
            if ps_tuple is not None:
                pixel_spacing = [ps_tuple[0], ps_tuple[1]]  # [row, col]

            # Slice spacing (from consecutive slices or SliceThickness)
            slice_spacing = 1.0
            if len(sorted_datasets) > 1:
                # Calculate from ImagePositionPatient differences
                pos1 = get_image_position(sorted_datasets[0])
                pos2 = get_image_position(sorted_datasets[1])
                if pos1 is not None and pos2 is not None:
                    # Calculate 3D distance
                    distance_3d = np.linalg.norm(pos2 - pos1)

                    # Get slice thickness for comparison
                    get_slice_thickness(sorted_datasets[0])

                    # Calculate slice spacing as component along slice normal
                    orientation = get_image_orientation(sorted_datasets[0])
                    if orientation is not None:
                        row_cosines, col_cosines = orientation
                        slice_normal = np.cross(row_cosines, col_cosines)
                        slice_normal = slice_normal / np.linalg.norm(slice_normal)

                        pos_diff = pos2 - pos1
                        slice_spacing = abs(np.dot(pos_diff, slice_normal))
                    else:
                        slice_spacing = distance_3d
                else:
                    st = get_slice_thickness(ds)
                    if st is not None:
                        slice_spacing = st
            else:
                st = get_slice_thickness(ds)
                if st is not None:
                    slice_spacing = st

            # SimpleITK uses (x, y, z) order for spacing
            # Pixel spacing is [row, col] in DICOM, which maps to [y, x] in SimpleITK
            sitk_image.SetSpacing([pixel_spacing[1], pixel_spacing[0], slice_spacing])

            # Direction cosines (ImageOrientationPatient)
            orientation = get_image_orientation(ds)
            if orientation is not None:
                row_cosines, col_cosines = orientation
                slice_cosines = np.cross(row_cosines, col_cosines)

                # SimpleITK 3x3 direction matrix: each COLUMN is the
                # physical direction of one image axis, flattened in
                # row-major order.  Same convention as mpr_volume.py.
                #   Column 0 (x-axis / cols) -> row_cosines
                #   Column 1 (y-axis / rows) -> col_cosines
                #   Column 2 (z-axis / slices) -> slice_cosines
                direction = [
                    row_cosines[0], col_cosines[0], slice_cosines[0],
                    row_cosines[1], col_cosines[1], slice_cosines[1],
                    row_cosines[2], col_cosines[2], slice_cosines[2],
                ]
                sitk_image.SetDirection(direction)

            return sitk_image

        except Exception as e:
            print(f"Error converting DICOM series to SimpleITK: {e}")
            _logger.debug("%s", sanitized_format_exc())
            return None

    def _get_location(self, ds: Dataset) -> float | None:
        """
        Get slice location from dataset.
        
        Args:
            ds: DICOM dataset
            
        Returns:
            Slice location as float, or None if not available
        """
        # Try SliceLocation first
        if hasattr(ds, 'SliceLocation'):
            try:
                return float(ds.SliceLocation)
            except (ValueError, TypeError):
                pass

        # Fall back to ImagePositionPatient Z coordinate
        if hasattr(ds, 'ImagePositionPatient'):
            ipp = ds.ImagePositionPatient
            if ipp and len(ipp) >= 3:
                try:
                    return float(ipp[2])
                except (ValueError, TypeError, IndexError):
                    pass

        return None

    def _filter_duplicate_locations(
        self,
        sorted_datasets: list[Dataset],
        tolerance: float = 0.01
    ) -> list[Dataset]:
        """
        Filter out duplicate slice locations, keeping only the first occurrence.
        
        Args:
            sorted_datasets: List of datasets already sorted by location
            tolerance: Tolerance in mm for considering locations as duplicates (default: 0.01mm)
            
        Returns:
            Filtered list of datasets with unique locations
        """
        if not sorted_datasets:
            return []

        filtered = []
        seen_locations = []

        for ds in sorted_datasets:
            location = self._get_location(ds)
            if location is None:
                # Skip datasets without valid location
                continue

            # Check if this location is a duplicate (within tolerance)
            is_duplicate = False
            for seen_loc in seen_locations:
                if abs(location - seen_loc) < tolerance:
                    is_duplicate = True
                    break

            if not is_duplicate:
                filtered.append(ds)
                seen_locations.append(location)

        return filtered

    def _sort_datasets_by_location(self, datasets: list[Dataset]) -> list[Dataset]:
        """
        Sort datasets by slice location.
        
        Args:
            datasets: List of DICOM datasets
            
        Returns:
            Sorted list of datasets
        """
        def _sort_key(ds: Dataset) -> float:
            location = self._get_location(ds)
            return float('inf') if location is None else location

        sorted_list = sorted(datasets, key=_sort_key)
        # Filter out datasets without valid location
        return [ds for ds in sorted_list if self._get_location(ds) is not None]

    def sitk_to_numpy(self, sitk_image: Any) -> np.ndarray | None:
        """
        Convert SimpleITK image to numpy array.
        
        Args:
            sitk_image: SimpleITK image
            
        Returns:
            Numpy array (z, y, x) or None if conversion fails
        """
        if not sitk_available or sitk_image is None:
            return None

        try:
            return sitk.GetArrayFromImage(sitk_image)
        except Exception as e:
            print(f"Error converting SimpleITK to numpy: {e}")
            return None

    def resample_to_reference(
        self,
        moving: Any,
        reference: Any,
        interpolator: str = 'linear'
    ) -> Any | None:
        """
        Resample moving image to match reference image's grid.
        
        Uses sitk.Resample() with identity transform (assumes same Frame of Reference).
        
        Args:
            moving: Moving image to resample
            reference: Reference image (target grid)
            interpolator: Interpolation method ('linear', 'nearest', 'cubic', 'b-spline')
            
        Returns:
            Resampled SimpleITK image, or None if resampling fails
        """
        if not sitk_available:
            return None

        if moving is None or reference is None:
            return None

        try:
            # Get interpolation method
            interp_method = self.INTERPOLATION_METHODS.get(interpolator.lower(), sitk.sitkLinear)
            if interp_method is None:
                interp_method = sitk.sitkLinear

            # Create identity transform (assumes same Frame of Reference)
            transform = sitk.Transform(3, sitk.sitkIdentity)

            # Resample
            resampled = sitk.Resample(
                moving,
                reference,
                transform,
                interp_method,
                0.0,  # default pixel value
                moving.GetPixelID()
            )

            return resampled

        except Exception as e:
            print(f"Error resampling image: {e}")
            _logger.debug("%s", sanitized_format_exc())
            return None

    def get_resampled_slice(
        self,
        overlay_datasets: list[Dataset],
        reference_datasets: list[Dataset],
        slice_idx: int,
        use_cache: bool = True,
        interpolator: str = 'linear',
        overlay_series_uid: str | None = None,
        reference_series_uid: str | None = None
    ) -> np.ndarray | None:
        """
        Get resampled slice from overlay volume.
        
        Caches full volume resampling for performance. Extracts the requested slice
        from the cached resampled volume.
        
        Args:
            overlay_datasets: List of overlay series datasets
            reference_datasets: List of reference (base) series datasets
            slice_idx: Slice index in reference series
            use_cache: Whether to use cached resampled volume
            interpolator: Interpolation method
            overlay_series_uid: Overlay series UID for caching
            reference_series_uid: Reference series UID for caching
            
        Returns:
            Resampled 2D numpy array for the requested slice, or None if resampling fails
        """
        if not sitk_available:
            return None

        if slice_idx < 0 or not reference_datasets or slice_idx >= len(reference_datasets):
            return None

        # DEBUG: Log slice index mapping from unsorted to sorted order
        # print(f"[3D RESAMPLE DEBUG] get_resampled_slice: Slice index mapping check")
        # print(f"[3D RESAMPLE DEBUG]   Requested slice_idx (unsorted): {slice_idx}")
        # print(f"[3D RESAMPLE DEBUG]   Total reference_datasets (unsorted): {len(reference_datasets)}")

        # Get the dataset at slice_idx in unsorted reference_datasets
        target_dataset = reference_datasets[slice_idx]
        target_slice_loc = getattr(target_dataset, 'SliceLocation', None)
        if target_slice_loc is None and hasattr(target_dataset, 'ImagePositionPatient'):
            ipp = target_dataset.ImagePositionPatient
            target_slice_loc = float(ipp[2]) if ipp and len(ipp) >= 3 else None
        # print(f"[3D RESAMPLE DEBUG]   Target dataset at unsorted_idx={slice_idx}: SliceLocation={target_slice_loc}")

        # Find its position in sorted datasets (used to create reference_sitk).
        # Cache the sorted+filtered list to avoid O(N^2) re-sort on every scroll (P1.2).
        _ref_cache_key = reference_series_uid or ""
        sorted_reference_datasets = self._sorted_ref_cache.get(_ref_cache_key) if _ref_cache_key else None
        if sorted_reference_datasets is None:
            sorted_reference_datasets = self._sort_datasets_by_location(reference_datasets)
            sorted_reference_datasets = self._filter_duplicate_locations(sorted_reference_datasets)
            if _ref_cache_key:
                self._sorted_ref_cache[_ref_cache_key] = sorted_reference_datasets
        # print(f"[3D RESAMPLE DEBUG]   Total sorted reference_datasets: {len(sorted_reference_datasets)}")

        # Map unsorted index to sorted index
        sorted_slice_idx = slice_idx
        try:
            sorted_slice_idx = sorted_reference_datasets.index(target_dataset)
            # print(f"[3D RESAMPLE DEBUG]   Slice index mapping: unsorted_idx={slice_idx} -> sorted_idx={sorted_slice_idx}")
            if sorted_slice_idx < len(sorted_reference_datasets):
                sorted_ds = sorted_reference_datasets[sorted_slice_idx]
                sorted_slice_loc = getattr(sorted_ds, 'SliceLocation', None)
                if sorted_slice_loc is None and hasattr(sorted_ds, 'ImagePositionPatient'):
                    ipp = sorted_ds.ImagePositionPatient
                    sorted_slice_loc = float(ipp[2]) if ipp and len(ipp) >= 3 else None
                # print(f"[3D RESAMPLE DEBUG]   Sorted dataset at sorted_idx={sorted_slice_idx}: SliceLocation={sorted_slice_loc}")
        except ValueError:
            # Dataset not found in sorted list - may have been filtered as duplicate
            # Find first dataset at the same location (within tolerance)
            target_location = self._get_location(target_dataset)
            if target_location is not None:
                # Search for first dataset with same location
                found = False
                for idx, ds in enumerate(sorted_reference_datasets):
                    ds_location = self._get_location(ds)
                    if ds_location is not None and abs(ds_location - target_location) < 0.01:
                        sorted_slice_idx = idx
                        found = True
                        break
                if not found:
                    # Fall back to original index if location not found
                    sorted_slice_idx = slice_idx
            else:
                # No location available, fall back to original index
                sorted_slice_idx = slice_idx

        # Create cache key
        cache_key = None
        if use_cache and overlay_series_uid and reference_series_uid:
            cache_key = (overlay_series_uid, reference_series_uid)

        # Check cache
        resampled_volume = None
        if cache_key and use_cache:
            with self._cache_lock:
                resampled_volume = self._cache.get(cache_key)
                if resampled_volume is not None:
                    self._cache.move_to_end(cache_key)

        # Resample if not cached
        if resampled_volume is None:
            # Convert to SimpleITK
            overlay_sitk = self.dicom_series_to_sitk(overlay_datasets, overlay_series_uid)
            reference_sitk = self.dicom_series_to_sitk(reference_datasets, reference_series_uid)

            if overlay_sitk is None or reference_sitk is None:
                return None

            # Resample overlay to match reference grid
            resampled_volume = self.resample_to_reference(
                overlay_sitk,
                reference_sitk,
                interpolator
            )

            if resampled_volume is None:
                return None

            # Cache the resampled volume
            if cache_key and use_cache:
                with self._cache_lock:
                    self._cache[cache_key] = resampled_volume
                    # LRU eviction: remove oldest entries when over capacity
                    while len(self._cache) > self._MAX_CACHE_ENTRIES:
                        evicted_key, _ = self._cache.popitem(last=False)
                        self._numpy_cache.pop(evicted_key, None)

        # Extract requested slice — use cached numpy array to avoid
        # re-extracting the full 3D volume on every scroll (P1.1).
        volume_array = None
        if cache_key:
            with self._cache_lock:
                volume_array = self._numpy_cache.get(cache_key)
        if volume_array is None:
            volume_array = self.sitk_to_numpy(resampled_volume)
            if volume_array is None:
                return None
            if cache_key:
                with self._cache_lock:
                    self._numpy_cache[cache_key] = volume_array

        if sorted_slice_idx < volume_array.shape[0]:
            slice_array = volume_array[sorted_slice_idx]
        else:
            return None

        return slice_array if slice_array.dtype == np.float32 else slice_array.astype(np.float32)

    def needs_resampling(
        self,
        overlay_datasets: list[Dataset],
        reference_datasets: list[Dataset]
    ) -> tuple[bool, str]:
        """
        Determine if 3D resampling is needed.
        
        Returns (needs_resampling: bool, reason: str).
        
        Checks:
        - ImageOrientationPatient differences (direction cosine difference ≥0.1)
        - Slice thickness ratio (≥2:1 requires 3D)
        - Pixel spacing differences (handled by 2D if orientations match)
        - Missing spatial metadata (requires 3D for robustness)
        
        Examples:
        - (False, "Compatible: same orientation, similar thickness") -> Use 2D
        - (True, "Different orientation: axial vs sagittal") -> Use 3D
        - (True, "Slice thickness ratio 3:1 (1mm vs 3mm)") -> Use 3D
        
        Args:
            overlay_datasets: List of overlay series datasets
            reference_datasets: List of reference (base) series datasets
            
        Returns:
            Tuple of (needs_3d_resampling: bool, reason: str)
        """
        if not overlay_datasets or not reference_datasets:
            return (True, "Missing datasets")

        overlay_ds = overlay_datasets[0]
        reference_ds = reference_datasets[0]

        # Check ImageOrientationPatient
        overlay_orient = get_image_orientation(overlay_ds)
        reference_orient = get_image_orientation(reference_ds)

        if overlay_orient is None or reference_orient is None:
            # Missing orientation data - use 3D for robustness
            return (True, "Missing ImageOrientationPatient - using 3D resampling for robustness")

        # Check orientation difference
        row_diff = np.linalg.norm(overlay_orient[0] - reference_orient[0])
        col_diff = np.linalg.norm(overlay_orient[1] - reference_orient[1])

        if row_diff >= 0.1 or col_diff >= 0.1:
            return (True, f"Different orientation detected (row_diff={row_diff:.3f}, col_diff={col_diff:.3f})")

        # Check slice thickness ratio
        overlay_thickness = get_slice_thickness(overlay_ds)
        reference_thickness = get_slice_thickness(reference_ds)

        if overlay_thickness is not None and reference_thickness is not None:
            if reference_thickness > 0:
                thickness_ratio = overlay_thickness / reference_thickness
                if thickness_ratio >= 2.0 or thickness_ratio <= 0.5:
                    return (True, f"Slice thickness ratio {thickness_ratio:.2f}:1 ({overlay_thickness:.1f}mm vs {reference_thickness:.1f}mm)")

        # Check if slice spacing is significantly different (calculate from ImagePositionPatient)
        if len(overlay_datasets) > 1 and len(reference_datasets) > 1:
            overlay_spacing = self._calculate_slice_spacing(overlay_datasets)
            reference_spacing = self._calculate_slice_spacing(reference_datasets)

            if overlay_spacing is not None and reference_spacing is not None:
                if reference_spacing > 0:
                    spacing_ratio = overlay_spacing / reference_spacing
                    if spacing_ratio >= 2.0 or spacing_ratio <= 0.5:
                        return (True, f"Slice spacing ratio {spacing_ratio:.2f}:1 ({overlay_spacing:.2f}mm vs {reference_spacing:.2f}mm)")

        # All checks passed - 2D resize should be sufficient
        return (False, "Compatible: same orientation, similar thickness")

    def _calculate_slice_spacing(self, datasets: list[Dataset]) -> float | None:
        """
        Calculate slice spacing from ImagePositionPatient differences.

        Sorts datasets by location first, then projects the inter-slice
        offset along the slice normal (cross product of IOP row/col
        cosines).  Falls back to 3-D Euclidean distance when IOP is
        unavailable.

        Args:
            datasets: List of DICOM datasets (at least 2)

        Returns:
            Median slice spacing in mm, or None if cannot calculate
        """
        if len(datasets) < 2:
            return None

        sorted_ds = self._sort_datasets_by_location(datasets)

        # Compute slice normal from IOP if available
        slice_normal = None
        ds0 = sorted_ds[0]
        if hasattr(ds0, "ImageOrientationPatient"):
            iop = ds0.ImageOrientationPatient
            if iop and len(iop) >= 6:
                row_cos = np.array([float(iop[0]), float(iop[1]), float(iop[2])])
                col_cos = np.array([float(iop[3]), float(iop[4]), float(iop[5])])
                sn = np.cross(row_cos, col_cos)
                norm = np.linalg.norm(sn)
                if norm > 1e-8:
                    slice_normal = sn / norm

        spacings = []
        for i in range(len(sorted_ds) - 1):
            if hasattr(sorted_ds[i], "ImagePositionPatient") and \
               hasattr(sorted_ds[i + 1], "ImagePositionPatient"):
                try:
                    pos1 = np.array([float(x) for x in sorted_ds[i].ImagePositionPatient])
                    pos2 = np.array([float(x) for x in sorted_ds[i + 1].ImagePositionPatient])
                    diff = pos2 - pos1
                    if slice_normal is not None:
                        spacing = abs(float(np.dot(diff, slice_normal)))
                    else:
                        spacing = float(np.linalg.norm(diff))
                    if spacing > 0:
                        spacings.append(spacing)
                except Exception:
                    pass

        if spacings:
            return float(np.median(spacings))

        return None

    def clear_cache(self, series_uid: str | None = None) -> None:
        """
        Clear resampled volume cache.
        
        Args:
            series_uid: If provided, clear only entries involving this series UID.
                       If None, clear entire cache.
        """
        with self._cache_lock:
            if series_uid is None:
                self._cache.clear()
                self._numpy_cache.clear()
                self._sorted_ref_cache.clear()
            else:
                # Remove entries where either key component matches
                keys_to_remove = [
                    key for key in self._cache
                    if series_uid in key
                ]
                for key in keys_to_remove:
                    del self._cache[key]
                    self._numpy_cache.pop(key, None)
                # Clear sorted ref cache for this series
                self._sorted_ref_cache.pop(series_uid, None)

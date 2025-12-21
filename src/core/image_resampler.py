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

import threading
import numpy as np
from typing import Optional, List, Tuple, Dict
from pydicom.dataset import Dataset

try:
    import SimpleITK as sitk
    SIMPLEITK_AVAILABLE = True
except ImportError:
    SIMPLEITK_AVAILABLE = False
    sitk = None

from utils.dicom_utils import get_image_orientation, get_slice_thickness
from core.dicom_processor import DICOMProcessor


class ImageResampler:
    """
    Handles 3D volume resampling for image fusion.
    
    Responsibilities:
    - Convert DICOM series to SimpleITK images with proper spatial metadata
    - Resample volumes to match reference grid
    - Cache resampled volumes for performance
    - Determine when 3D resampling is needed vs 2D resize
    """
    
    # Interpolation method mapping
    INTERPOLATION_METHODS = {
        'linear': sitk.sitkLinear if SIMPLEITK_AVAILABLE else None,
        'nearest': sitk.sitkNearestNeighbor if SIMPLEITK_AVAILABLE else None,
        'cubic': sitk.sitkBSpline if SIMPLEITK_AVAILABLE else None,
        'b-spline': sitk.sitkBSpline if SIMPLEITK_AVAILABLE else None,
    }
    
    def __init__(self):
        """Initialize image resampler with cache."""
        if not SIMPLEITK_AVAILABLE:
            print("Warning: SimpleITK not available. 3D resampling will not work.")
        
        # Cache for resampled volumes: key = (overlay_uid, base_uid), value = sitk.Image
        self._cache: Dict[Tuple[str, str], sitk.Image] = {}
        self._cache_lock = threading.Lock()  # For thread-safe caching
    
    def dicom_series_to_sitk(
        self,
        datasets: List[Dataset],
        series_uid: Optional[str] = None
    ) -> Optional['sitk.Image']:
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
        if not SIMPLEITK_AVAILABLE:
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
            
            # Extract pixel arrays
            pixel_arrays = []
            for ds in sorted_datasets:
                try:
                    array = ds.pixel_array.astype(np.float32)
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
            if hasattr(ds, 'ImagePositionPatient'):
                ipp = ds.ImagePositionPatient
                if ipp and len(ipp) >= 3:
                    origin = [float(ipp[0]), float(ipp[1]), float(ipp[2])]
                    sitk_image.SetOrigin(origin)
            
            # Pixel spacing
            pixel_spacing = [1.0, 1.0]
            if hasattr(ds, 'PixelSpacing'):
                ps = ds.PixelSpacing
                if ps and len(ps) >= 2:
                    pixel_spacing = [float(ps[0]), float(ps[1])]  # [row, col]
            
            # Slice spacing (from consecutive slices or SliceThickness)
            slice_spacing = 1.0
            if len(sorted_datasets) > 1:
                # Calculate from ImagePositionPatient differences
                if hasattr(sorted_datasets[0], 'ImagePositionPatient') and \
                   hasattr(sorted_datasets[1], 'ImagePositionPatient'):
                    pos1 = np.array([float(x) for x in sorted_datasets[0].ImagePositionPatient])
                    pos2 = np.array([float(x) for x in sorted_datasets[1].ImagePositionPatient])
                    
                    # DEBUG: Log slice spacing calculation
                    # print(f"[3D RESAMPLE DEBUG] dicom_series_to_sitk: Slice spacing calculation")
                    # print(f"[3D RESAMPLE DEBUG]   ImagePositionPatient[0]: {pos1}")
                    # print(f"[3D RESAMPLE DEBUG]   ImagePositionPatient[1]: {pos2}")
                    
                    # Calculate 3D distance
                    distance_3d = np.linalg.norm(pos2 - pos1)
                    # print(f"[3D RESAMPLE DEBUG]   3D distance: {distance_3d:.3f}mm")
                    
                    # Get slice thickness for comparison
                    slice_thickness = None
                    if hasattr(sorted_datasets[0], 'SliceThickness'):
                        try:
                            slice_thickness = float(sorted_datasets[0].SliceThickness)
                            # print(f"[3D RESAMPLE DEBUG]   SliceThickness: {slice_thickness:.3f}mm")
                        except (ValueError, TypeError):
                            pass
                    
                    # Calculate slice spacing as component along slice normal
                    if hasattr(sorted_datasets[0], 'ImageOrientationPatient'):
                        iop = sorted_datasets[0].ImageOrientationPatient
                        if iop and len(iop) >= 6:
                            row_cosines = np.array([float(iop[0]), float(iop[1]), float(iop[2])])
                            col_cosines = np.array([float(iop[3]), float(iop[4]), float(iop[5])])
                            slice_normal = np.cross(row_cosines, col_cosines)
                            slice_normal = slice_normal / np.linalg.norm(slice_normal)  # Normalize
                            
                            # Calculate spacing as component along slice normal (increment between centers)
                            pos_diff = pos2 - pos1
                            slice_spacing = abs(np.dot(pos_diff, slice_normal))
                            
                            # print(f"[3D RESAMPLE DEBUG]   Slice normal (from IOP): {slice_normal}")
                            # print(f"[3D RESAMPLE DEBUG]   Spacing along normal: {slice_spacing:.3f}mm")
                            
                            # Debug: Check for overlap
                            if slice_thickness is not None and slice_spacing < slice_thickness:
                                overlap = slice_thickness - slice_spacing
                                # print(f"[3D RESAMPLE DEBUG]   OVERLAP DETECTED: thickness={slice_thickness:.2f}mm, spacing={slice_spacing:.2f}mm, overlap={overlap:.2f}mm")
                            elif slice_thickness is not None:
                                gap = slice_spacing - slice_thickness
                                # print(f"[3D RESAMPLE DEBUG]   Gap between slices: {gap:.2f}mm")
                        else:
                            # Fall back to 3D distance if no orientation
                            slice_spacing = distance_3d
                            # print(f"[3D RESAMPLE DEBUG]   No ImageOrientationPatient, using 3D distance: {slice_spacing:.3f}mm")
                    else:
                        # Fall back to 3D distance if no orientation
                        slice_spacing = distance_3d
                        # print(f"[3D RESAMPLE DEBUG]   No ImageOrientationPatient, using 3D distance: {slice_spacing:.3f}mm")
                elif hasattr(ds, 'SliceThickness'):
                    slice_spacing = float(ds.SliceThickness)
                    # print(f"[3D RESAMPLE DEBUG] dicom_series_to_sitk: Using SliceThickness: {slice_spacing:.3f}mm")
            elif hasattr(ds, 'SliceThickness'):
                slice_spacing = float(ds.SliceThickness)
                # print(f"[3D RESAMPLE DEBUG] dicom_series_to_sitk: Single slice, using SliceThickness: {slice_spacing:.3f}mm")
            
            # SimpleITK uses (x, y, z) order for spacing
            # Pixel spacing is [row, col] in DICOM, which maps to [y, x] in SimpleITK
            sitk_image.SetSpacing([pixel_spacing[1], pixel_spacing[0], slice_spacing])
            
            # Direction cosines (ImageOrientationPatient)
            if hasattr(ds, 'ImageOrientationPatient'):
                iop = ds.ImageOrientationPatient
                if iop and len(iop) >= 6:
                    row_cosines = np.array([float(iop[0]), float(iop[1]), float(iop[2])])
                    col_cosines = np.array([float(iop[3]), float(iop[4]), float(iop[5])])
                    slice_cosines = np.cross(row_cosines, col_cosines)
                    
                    # DEBUG: Log direction matrix calculation
                    # print(f"[3D RESAMPLE DEBUG] dicom_series_to_sitk: Direction matrix calculation")
                    # print(f"[3D RESAMPLE DEBUG]   ImageOrientationPatient: {iop}")
                    # print(f"[3D RESAMPLE DEBUG]   Row cosines: {row_cosines}")
                    # print(f"[3D RESAMPLE DEBUG]   Col cosines: {col_cosines}")
                    # print(f"[3D RESAMPLE DEBUG]   Slice normal (cross product): {slice_cosines}")
                    
                    # FIX: Direction matrix in row-major order for SimpleITK (not column-major)
                    # Format: [Row_x, Row_y, Row_z, Col_x, Col_y, Col_z, Slice_x, Slice_y, Slice_z]
                    direction = [
                        row_cosines[0], row_cosines[1], row_cosines[2],  # Row vector
                        col_cosines[0], col_cosines[1], col_cosines[2],  # Col vector
                        slice_cosines[0], slice_cosines[1], slice_cosines[2]  # Slice normal
                    ]
                    # print(f"[3D RESAMPLE DEBUG]   Direction matrix (row-major, FIXED): {direction}")
                    # print(f"[3D RESAMPLE DEBUG]   Row cosines: {row_cosines}")
                    # print(f"[3D RESAMPLE DEBUG]   Col cosines: {col_cosines}")
                    # print(f"[3D RESAMPLE DEBUG]   Slice normal: {slice_cosines}")
                    sitk_image.SetDirection(direction)
            
            return sitk_image
            
        except Exception as e:
            print(f"Error converting DICOM series to SimpleITK: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _get_location(self, ds: Dataset) -> Optional[float]:
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
        sorted_datasets: List[Dataset],
        tolerance: float = 0.01
    ) -> List[Dataset]:
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
    
    def _sort_datasets_by_location(self, datasets: List[Dataset]) -> List[Dataset]:
        """
        Sort datasets by slice location.
        
        Args:
            datasets: List of DICOM datasets
            
        Returns:
            Sorted list of datasets
        """
        sorted_list = sorted(datasets, key=lambda ds: self._get_location(ds) or float('inf'))
        # Filter out datasets without valid location
        return [ds for ds in sorted_list if self._get_location(ds) is not None]
    
    def sitk_to_numpy(self, sitk_image: 'sitk.Image') -> Optional[np.ndarray]:
        """
        Convert SimpleITK image to numpy array.
        
        Args:
            sitk_image: SimpleITK image
            
        Returns:
            Numpy array (z, y, x) or None if conversion fails
        """
        if not SIMPLEITK_AVAILABLE or sitk_image is None:
            return None
        
        try:
            return sitk.GetArrayFromImage(sitk_image)
        except Exception as e:
            print(f"Error converting SimpleITK to numpy: {e}")
            return None
    
    def resample_to_reference(
        self,
        moving: 'sitk.Image',
        reference: 'sitk.Image',
        interpolator: str = 'linear'
    ) -> Optional['sitk.Image']:
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
        if not SIMPLEITK_AVAILABLE:
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
            import traceback
            traceback.print_exc()
            return None
    
    def get_resampled_slice(
        self,
        overlay_datasets: List[Dataset],
        reference_datasets: List[Dataset],
        slice_idx: int,
        use_cache: bool = True,
        interpolator: str = 'linear',
        overlay_series_uid: Optional[str] = None,
        reference_series_uid: Optional[str] = None
    ) -> Optional[np.ndarray]:
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
        if not SIMPLEITK_AVAILABLE:
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
        
        # Find its position in sorted datasets (used to create reference_sitk)
        # Note: dicom_series_to_sitk() filters duplicates, so we need to filter here too for correct mapping
        sorted_reference_datasets = self._sort_datasets_by_location(reference_datasets)
        sorted_reference_datasets = self._filter_duplicate_locations(sorted_reference_datasets)
        # print(f"[3D RESAMPLE DEBUG]   Total sorted reference_datasets: {len(sorted_reference_datasets)}")
        
        # Map unsorted index to sorted index
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
        
        # Extract requested slice using sorted index (FIX: use sorted_slice_idx instead of slice_idx)
        volume_array = self.sitk_to_numpy(resampled_volume)
        if volume_array is None:
            return None
        
        # DEBUG: Log which slice is extracted from volume
        # print(f"[3D RESAMPLE DEBUG] get_resampled_slice: Extracting slice from resampled volume")
        # print(f"[3D RESAMPLE DEBUG]   Volume shape (z, y, x): {volume_array.shape}")
        # print(f"[3D RESAMPLE DEBUG]   Using sorted_slice_idx: {sorted_slice_idx} (was unsorted_idx: {slice_idx})")
        
        # volume_array is (z, y, x), extract slice at sorted index
        # FIX: Use sorted_slice_idx instead of slice_idx to correctly map from unsorted to sorted order
        if sorted_slice_idx < volume_array.shape[0]:
            slice_array = volume_array[sorted_slice_idx]
            # print(f"[3D RESAMPLE DEBUG]   Successfully extracted slice {sorted_slice_idx} from volume")
        else:
            # print(f"[3D RESAMPLE DEBUG] ERROR: sorted_slice_idx={sorted_slice_idx} >= volume_array.shape[0]={volume_array.shape[0]}")
            return None
        
        # Apply rescale if parameters exist (3D resampling works with raw pixel values)
        if overlay_datasets:
            # DEBUG: Check rescale parameter consistency across slices
            # print(f"[3D RESAMPLE DEBUG] get_resampled_slice: Rescale parameter check")
            # print(f"[3D RESAMPLE DEBUG]   Total overlay_datasets: {len(overlay_datasets)}")
            
            # Check rescale parameters for multiple slices
            rescale_params_list = []
            check_slices = [0]
            if len(overlay_datasets) > 1:
                check_slices.append(1)
            if len(overlay_datasets) > 2:
                check_slices.append(len(overlay_datasets) - 1)
            
            for idx in check_slices:
                ds = overlay_datasets[idx]
                rescale_slope, rescale_intercept, rescale_type = DICOMProcessor.get_rescale_parameters(ds)
                rescale_params_list.append((idx, rescale_slope, rescale_intercept, rescale_type))
                # print(f"[3D RESAMPLE DEBUG]   Slice[{idx}]: slope={rescale_slope}, intercept={rescale_intercept}, type={rescale_type}")
            
            # Check consistency
            if len(rescale_params_list) > 1:
                first_params = rescale_params_list[0][1:4]  # (slope, intercept, type)
                all_consistent = all(params[1:4] == first_params for params in rescale_params_list[1:])
                if not all_consistent:
                    # print(f"[3D RESAMPLE DEBUG]   WARNING: Rescale parameters are NOT consistent across slices!")
                    pass
                else:
                    # print(f"[3D RESAMPLE DEBUG]   Rescale parameters are consistent across slices")
                    pass
            
            # Use first dataset's rescale parameters
            rescale_slope, rescale_intercept, _ = DICOMProcessor.get_rescale_parameters(overlay_datasets[0])
            if rescale_slope is not None and rescale_intercept is not None:
                # print(f"[3D RESAMPLE DEBUG]   Applying rescale: slope={rescale_slope}, intercept={rescale_intercept}")
                slice_array = slice_array.astype(np.float32) * float(rescale_slope) + float(rescale_intercept)
        
        return slice_array
        
        return None
    
    def needs_resampling(
        self,
        overlay_datasets: List[Dataset],
        reference_datasets: List[Dataset]
    ) -> Tuple[bool, str]:
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
    
    def _calculate_slice_spacing(self, datasets: List[Dataset]) -> Optional[float]:
        """
        Calculate slice spacing from ImagePositionPatient differences.
        
        Args:
            datasets: List of DICOM datasets (at least 2)
            
        Returns:
            Average slice spacing in mm, or None if cannot calculate
        """
        if len(datasets) < 2:
            return None
        
        spacings = []
        for i in range(len(datasets) - 1):
            if hasattr(datasets[i], 'ImagePositionPatient') and \
               hasattr(datasets[i+1], 'ImagePositionPatient'):
                try:
                    pos1 = np.array([float(x) for x in datasets[i].ImagePositionPatient])
                    pos2 = np.array([float(x) for x in datasets[i+1].ImagePositionPatient])
                    spacing = np.linalg.norm(pos2 - pos1)
                    if spacing > 0:
                        spacings.append(spacing)
                except Exception:
                    pass
        
        if spacings:
            return np.mean(spacings)
        
        return None
    
    def clear_cache(self, series_uid: Optional[str] = None) -> None:
        """
        Clear resampled volume cache.
        
        Args:
            series_uid: If provided, clear only entries involving this series UID.
                       If None, clear entire cache.
        """
        with self._cache_lock:
            if series_uid is None:
                self._cache.clear()
            else:
                # Remove entries where either key component matches
                keys_to_remove = [
                    key for key in self._cache.keys()
                    if series_uid in key
                ]
                for key in keys_to_remove:
                    del self._cache[key]

# Image Fusion Technical Documentation

## Overview

The DICOM Viewer V3 image fusion feature allows overlaying functional imaging (PET/SPECT) on anatomical imaging (CT/MR) from different series within the same study. This document provides detailed technical information about the fusion algorithms, options, error sources, and accuracy estimates.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Fusion Options and Parameters](#fusion-options-and-parameters)
3. [2D Fusion Algorithm](#2d-fusion-algorithm)
4. [3D Fusion Algorithm](#3d-fusion-algorithm)
5. [Spatial Alignment](#spatial-alignment)
6. [Error Sources and Accuracy Analysis](#error-sources-and-accuracy-analysis)
7. [Performance Considerations](#performance-considerations)

---

## Architecture Overview

The fusion system consists of three main components:

1. **FusionHandler**: Manages fusion state, slice matching, and spatial metadata extraction
2. **FusionProcessor**: Performs image blending, colormap application, and pixel-level operations
3. **ImageResampler**: Handles 3D volume resampling using SimpleITK for complex spatial transformations

### Data Flow

```
User Selection → FusionHandler → Slice Matching → Resampling Decision
                                                      ↓
                                             2D or 3D Resampling
                                                      ↓
                                            FusionProcessor
                                                      ↓
                                            Blended RGB Image
```

---

## Fusion Options and Parameters

### Core Parameters

1. **Opacity (α)**: 0.0 to 1.0 (0-100% in UI)
   - Controls transparency of overlay on base image
   - Formula: `fused = base × (1 - α×mask) + overlay × (α×mask)`
   - Default: 0.5 (50%)

2. **Threshold**: 0.0 to 1.0 (0-100% in UI, normalized space)
   - Minimum overlay value to display
   - Creates binary mask: `mask = (overlay_normalized >= threshold)`
   - Default: 0.2 (20% of normalized range)

3. **Colormap**: Visualization scheme for overlay
   - Available: hot, jet, viridis, plasma, inferno, rainbow, cool, spring
   - Applied to normalized overlay values (0-1 range)
   - Default: 'hot' (red-yellow, good for PET)

4. **Overlay Window/Level**: Independent window width and center for overlay series
   - Normalizes overlay pixel values before colormap application
   - Formula: `normalized = clip((value - (level - window/2)) / window, 0, 1)`
   - Default: Window=1000, Level=500

### Resampling Modes

1. **Fast Mode (2D)**:
   - Uses 2D image resize (PIL bilinear interpolation)
   - Suitable for series with:
     - Same ImageOrientationPatient (orientation difference < 0.1)
     - Similar slice thickness (ratio between 0.5 and 2.0)
     - Same or similar pixel spacing
   - Faster processing, lower memory usage
   - Limited to 2D transformations (scaling, translation)

2. **High Accuracy Mode (3D)**:
   - Uses 3D volume resampling (SimpleITK)
   - Handles:
     - Different orientations (axial vs sagittal vs coronal)
     - Different slice thicknesses (any ratio)
     - Different pixel spacings
     - Complex spatial relationships
   - Slower processing, higher memory usage
   - Full 3D spatial transformation

### Interpolation Methods (3D Mode Only)

1. **Linear** (default):
   - SimpleITK: `sitkLinear`
   - Smooth interpolation, good balance of quality and speed
   - Suitable for most cases

2. **Nearest Neighbor**:
   - SimpleITK: `sitkNearestNeighbor`
   - Fastest, preserves original pixel values
   - May produce blocky artifacts

3. **Cubic/B-Spline**:
   - SimpleITK: `sitkBSpline`
   - Higher quality, smoother results
   - More computationally expensive

---

## 2D Fusion Algorithm

### Algorithm Steps

In 2D mode, the fusion system operates on one slice at a time. For each anatomical “base” slice, it tries to find the most appropriate functional “overlay” slice (or pair of slices) that represents the same physical location in the patient. Once that overlay information has been located and, if needed, interpolated, the system scales and shifts the overlay slice so that it lines up with the base image in pixel space and then blends the two images together.

1. **Slice Matching**:
   - Extract slice location from base slice (SliceLocation or ImagePositionPatient[2])
   - Find matching overlay slice(s):
     - Exact match: tolerance < 0.01 mm
     - Interpolation: two adjacent slices bracketing base location
   - If no match found within series bounds, return None

2. **2D Interpolation (if needed)**:
   - If exact match: use overlay slice directly
   - If interpolation is needed because the base slice lies between two overlay slices:
     - Get the two adjacent overlay slices that bracket the base slice in physical space
     - Calculate a continuous weight: `weight = (base_location - loc1) / (loc2 - loc1)`
     - Perform linear interpolation: `overlay = array1 × (1 - weight) + array2 × weight`, so the overlay values change smoothly as the base position moves between the two overlay slices

3. **Pixel Spacing Scaling**:
   - Calculate scaling factors:
     - `scale_x = overlay_pixel_spacing[col] / base_pixel_spacing[col]`
     - `scale_y = overlay_pixel_spacing[row] / base_pixel_spacing[row]`
   - Resize overlay to match physical dimensions:
     - `new_width = overlay_width × scale_x`
     - `new_height = overlay_height × scale_y`
   - Uses PIL bilinear resampling

4. **Translation Offset**:
   - Calculate from ImagePositionPatient:
     - `offset_mm_x = overlay_IPP[0] - base_IPP[0]`
     - `offset_mm_y = overlay_IPP[1] - base_IPP[1]`
   - Convert to pixels:
     - `offset_px_x = offset_mm_x / base_pixel_spacing[col]`
     - `offset_px_y = offset_mm_y / base_pixel_spacing[row]`
   - Apply translation by placing overlay on base-sized canvas at offset position

5. **Normalization and Blending**:
   - Normalize base and overlay using window/level
   - Apply colormap to overlay
   - Apply threshold mask
   - Alpha blend: `fused = base × (1 - α×mask) + overlay × (α×mask)`

### Error Sources (2D Mode)

1. **Slice Location Extraction**:
   - **Source**: Missing or inaccurate SliceLocation tag
   - **Fallback**: Uses ImagePositionPatient[2] (Z coordinate)
   - **Error**: ±0.01 mm (exact match tolerance)
   - **Impact**: May select wrong slice if location is inaccurate

2. **2D Interpolation**:
   - **Source**: Base slice location between two overlay slices
   - **Method**: Linear interpolation along Z-axis
   - **Error**: Depends on slice spacing
     - For 1 mm slice spacing: interpolation error ≈ 0.5 mm (half slice spacing)
     - For 3 mm slice spacing: interpolation error ≈ 1.5 mm
   - **Impact**: Minor blurring in Z-direction, typically < 1 pixel equivalent

3. **Pixel Spacing Scaling**:
   - **Source**: Different pixel spacings between base and overlay
   - **Method**: Bilinear resampling
   - **Error**: 
     - Resampling introduces sub-pixel interpolation errors
     - Typical error: ±0.5 pixels (half pixel size)
     - For 1 mm pixel spacing: ±0.5 mm
     - For 0.5 mm pixel spacing: ±0.25 mm
   - **Impact**: Slight blurring, especially at edges

4. **Translation Offset**:
   - **Source**: ImagePositionPatient accuracy and pixel spacing conversion
   - **Error**:
     - Rounding to integer pixels: ±0.5 pixels
     - For 1 mm pixel spacing: ±0.5 mm
     - For 0.5 mm pixel spacing: ±0.25 mm
   - **Impact**: Sub-pixel misalignment

5. **Orientation Mismatch** (2D cannot handle):
   - **Source**: Different ImageOrientationPatient
   - **Error**: Can be significant (several pixels to centimeters)
   - **Impact**: Severe misalignment, fusion may be unusable
   - **Mitigation**: System recommends 3D mode when orientation difference ≥ 0.1

### Accuracy Estimates (2D Mode)

- **Best Case** (same orientation, same pixel spacing, exact slice match):
  - Spatial accuracy: ±0.5 pixels (±0.5 mm for 1 mm spacing)
  - Interpolation error: 0 mm (exact match)
  - **Total error**: ±0.5-1.0 mm

- **Typical Case** (same orientation, different pixel spacing, interpolation needed):
  - Spatial accuracy: ±0.5-1.0 pixels
  - Interpolation error: ±0.5-1.5 mm (depending on slice spacing)
  - **Total error**: ±1.0-2.5 mm

- **Worst Case** (orientation mismatch, forced 2D mode):
  - Spatial accuracy: Can be centimeters
  - **Total error**: Unpredictable, may be unusable

---

## 3D Fusion Algorithm

### Algorithm Steps

1. **DICOM Series to SimpleITK Conversion**:
   - Sort datasets by slice location (SliceLocation or ImagePositionPatient[2])
   - Extract pixel arrays and stack into 3D volume (z, y, x)
   - Set spatial metadata:
     - **Origin**: ImagePositionPatient[0,1,2] (x, y, z in mm)
     - **Spacing**: [pixel_spacing[col], pixel_spacing[row], slice_spacing] (x, y, z in mm)
     - **Direction**: 3×3 matrix from ImageOrientationPatient
       - Row cosines: IOP[0:3]
       - Column cosines: IOP[3:6]
       - Slice normal: cross product of row and column cosines

2. **Slice Spacing Calculation**:
   - Primary method: Component along slice normal
     - Calculate slice normal from ImageOrientationPatient
     - Project ImagePositionPatient difference onto slice normal
     - `slice_spacing = |dot(pos_diff, slice_normal)|`
   - Fallback: 3D Euclidean distance between consecutive slices
   - Fallback: SliceThickness tag (if only one slice)

3. **3D Volume Resampling**:
   - Convert overlay series to SimpleITK image
   - Convert base series to SimpleITK image (reference grid)
   - Use SimpleITK `Resample()` with identity transform
   - Assumes same Frame of Reference UID (see “Frame of Reference Assumption” below)
   - Resamples the entire 3D overlay volume so that it shares the same origin, spacing, and direction matrix as the base volume, meaning every overlay voxel is mapped into the base image’s 3D grid

4. **Slice Extraction**:
   - Extract requested slice from resampled volume
   - Map unsorted slice index to sorted index (datasets are sorted by location)
   - Apply rescale slope/intercept if present

5. **Normalization and Blending**:
   - Same as 2D mode (normalize, colormap, threshold, alpha blend)
   - Skip 2D resize and translation (already handled by 3D resampling)

### Error Sources (3D Mode)

1. **Slice Location Sorting**:
   - **Source**: Missing or inaccurate SliceLocation/ImagePositionPatient
   - **Error**: Datasets without valid location are filtered out
   - **Impact**: Missing slices in volume, potential gaps

2. **Slice Spacing Calculation**:
   - **Source**: Inaccurate ImagePositionPatient or ImageOrientationPatient
   - **Method**: Component along slice normal (most accurate)
   - **Error**:
     - If using slice normal: ±0.1-0.5 mm (depends on IOP accuracy)
     - If using 3D distance: Overestimates for oblique slices
       - For 30° oblique: error ≈ distance × (1 - cos(30°)) ≈ 13% overestimate
       - For 45° oblique: error ≈ distance × (1 - cos(45°)) ≈ 29% overestimate
   - **Impact**: Incorrect slice spacing affects volume reconstruction

3. **Direction Matrix Construction**:
   - **Source**: ImageOrientationPatient accuracy
   - **Error**: 
     - IOP cosines should be unit vectors (normalized)
     - Rounding errors: typically < 0.001
     - Non-orthogonal row/col vectors: system normalizes slice normal
   - **Impact**: Minor orientation errors, typically < 0.1° for well-formed DICOM

4. **3D Resampling Interpolation**:
   - **Source**: Interpolation method and grid mismatch
   - **Linear interpolation error**:
     - Sub-voxel accuracy: ±0.5 voxels in each dimension
     - For 1 mm spacing: ±0.5 mm per dimension
     - 3D error: √(0.5² + 0.5² + 0.5²) ≈ ±0.87 mm
   - **Nearest neighbor error**:
     - Up to ±0.5 voxels per dimension
     - **Total error**: ±0.87 mm (same as linear for worst case)
   - **Cubic/B-spline error**:
     - Better accuracy: ±0.3-0.4 voxels
     - **Total error**: ±0.5-0.7 mm

5. **Frame of Reference Assumption**:
   - **Source**: Assumes same Frame of Reference UID for base and overlay series.
   - In DICOM, the `FrameOfReferenceUID` defines a patient‑fixed 3D coordinate system. Two series that share the same `FrameOfReferenceUID` (for example, the CT and PET components of a PET‑CT exam acquired on the same scanner and table position) are expected to be already registered in physical space.
   - The 3D resampling code relies on this and uses an identity (no‑movement) transform when it resamples the overlay volume into the base volume’s grid. This is only correct if both series really do share the same frame of reference and have consistent spatial metadata.
   - **Error**: If the Frame of Reference differs, the identity transform is mathematically incorrect: the two volumes are not actually in the same physical coordinate system, so origin, orientation, and voxel spacing no longer line up. The resampling will still run, but the resulting fused image may place functional uptake in the wrong anatomical location.
   - **Impact**: Misalignment can be substantial—ranging from several millimeters to multiple centimeters—depending on how different the true frames of reference are (for example, different scanners, different sessions, or external registrations that are not captured in the DICOM metadata).
   - **Mitigation and warning behaviour**: The fusion coordinator checks the `FrameOfReferenceUID` from each series. If the UIDs do not match, the fusion status area shows a clear warning that the frames of reference differ. **Fusion is still allowed in this situation** so you can visually inspect the result, but you should treat the alignment as potentially inaccurate and avoid using it for tasks that require precise registration unless you have performed and validated an external registration step.

6. **Rescale Parameter Consistency**:
   - **Source**: Rescale slope/intercept may vary across slices
   - **Error**: System uses first slice's rescale parameters for entire volume
   - **Impact**: If parameters vary, some slices may have incorrect pixel values
   - **Typical**: Most DICOM series have consistent rescale parameters

### Accuracy Estimates (3D Mode)

- **Best Case** (accurate spatial metadata, linear interpolation, same Frame of Reference):
  - Spatial accuracy: ±0.5-0.87 mm (sub-voxel interpolation)
  - Slice spacing error: ±0.1 mm
  - **Total error**: ±0.6-1.0 mm

- **Typical Case** (good spatial metadata, linear interpolation):
  - Spatial accuracy: ±0.87 mm
  - Slice spacing error: ±0.2-0.5 mm
  - **Total error**: ±1.0-1.5 mm

- **Worst Case** (inaccurate metadata, oblique slices, different Frame of Reference):
  - Spatial accuracy: Can be several millimeters to centimeters
  - **Total error**: Unpredictable, may require manual adjustment

---

## Spatial Alignment

### Automatic Alignment

When you enable fusion, the viewer must decide exactly how to place the overlay pixels on top of the base image pixels. This is a spatial alignment or registration problem: the two series may have different pixel spacings, different physical starting positions in the patient, or different slice thicknesses and orientations. The fusion system uses the spatial metadata already present in the DICOM headers to compute how the overlay should be scaled and shifted relative to the base series.

In 2D (fast) mode, that alignment is reduced to scale factors and in‑plane translations that are applied slice‑by‑slice. In 3D (high‑accuracy) mode, the same spatial information is used to build a full 3D resampling grid, so the overlay volume is warped directly into the base volume’s coordinate system before any slice is displayed.

The system automatically calculates spatial alignment using DICOM metadata:

1. **Scaling Factors**:
   - `scale_x = overlay_pixel_spacing[col] / base_pixel_spacing[col]`
   - `scale_y = overlay_pixel_spacing[row] / base_pixel_spacing[row]`
   - Used in 2D mode for resize
   - Handled automatically in 3D mode

2. **Translation Offset**:
   - Calculated from ImagePositionPatient:
     - `offset_mm_x = overlay_IPP[0] - base_IPP[0]`
     - `offset_mm_y = overlay_IPP[1] - base_IPP[1]`
   - Converted to pixels:
     - `offset_px_x = offset_mm_x / base_pixel_spacing[col]`
     - `offset_px_y = offset_mm_y / base_pixel_spacing[row]`
   - Applied in 2D mode
   - Handled automatically in 3D mode through resampling grid

### Manual Adjustment

Even when the DICOM metadata is correct, small residual misalignments can occur because of positioning differences, table movement, or interpolation effects. For that reason, the right‑panel fusion controls expose the calculated translation as editable X and Y offsets so that you can fine‑tune the overlay placement visually.

Users can manually adjust translation offset:
- Range: -500 to +500 pixels in each direction
- Step: 1 pixel
- A “Reset to Calculated” control restores the automatically computed offset
- This manual adjustment is most useful when the automatic alignment is close but not perfect, for example when aligning PET and CT from the same scanner with slightly different breathing or positioning between scans

### Alignment Accuracy

- **Automatic alignment error**:
  - Depends on ImagePositionPatient accuracy
  - Typical DICOM accuracy: ±0.1-0.5 mm
  - For 1 mm pixel spacing: ±0.1-0.5 pixels
  - **Total alignment error**: ±0.1-0.5 mm (best case) to ±1-2 mm (typical)

- **Manual adjustment precision**:
  - Limited to integer pixels
  - For 1 mm pixel spacing: ±0.5 mm precision
  - For 0.5 mm pixel spacing: ±0.25 mm precision

---

## Error Sources and Accuracy Analysis

### Summary of Error Sources

| Error Source | 2D Mode Error | 3D Mode Error | Impact |
|-------------|---------------|---------------|---------|
| Slice location extraction | ±0.01 mm | ±0.01 mm | Low |
| Slice interpolation | ±0.5-1.5 mm | N/A (handled by 3D) | Medium |
| Pixel spacing scaling | ±0.5 pixels | N/A (handled by 3D) | Low-Medium |
| Translation offset | ±0.5 pixels | N/A (handled by 3D) | Low |
| Orientation mismatch | Can be large | ±0.87 mm (interpolation) | High (2D), Low (3D) |
| Slice spacing calculation | N/A | ±0.1-0.5 mm | Low-Medium |
| 3D resampling interpolation | N/A | ±0.5-0.87 mm | Low-Medium |
| Frame of Reference mismatch | Can be large | Can be large | High |
| Rescale parameter inconsistency | Low | Low | Low |

### Overall Accuracy Estimates

**2D Mode**:
- Best case: ±0.5-1.0 mm
- Typical case: ±1.0-2.5 mm
- Worst case (orientation mismatch): Unpredictable, may be unusable

**3D Mode**:
- Best case: ±0.6-1.0 mm
- Typical case: ±1.0-1.5 mm
- Worst case (Frame of Reference mismatch): Unpredictable, may be unusable

### Recommendations

1. **Use 3D mode** when:
   - Series have different orientations
   - Slice thickness ratio > 2:1 or < 0.5:1
   - Maximum accuracy is required

2. **Use 2D mode** when:
   - Series have same orientation
   - Similar slice thicknesses
   - Speed is prioritized

3. **Verify Frame of Reference**:
   - Check status indicator for warnings
   - If Frame of Reference differs, verify alignment manually

4. **Fine-tune alignment**:
   - Use manual translation offset adjustment if automatic alignment is slightly off
   - Adjust in 1-pixel increments for sub-pixel precision

---

## Performance Considerations

### Memory Usage

- **2D Mode**:
  - Processes one slice at a time
  - Memory: ~2-4× single slice size (base + overlay + intermediate arrays)
  - Typical: 10-50 MB per slice

- **3D Mode**:
  - Caches full resampled volume
  - Memory: ~2× volume size (original + resampled)
  - Typical: 100-500 MB for typical CT/PET volumes
  - Cache persists until series changes

### Processing Time

- **2D Mode**:
  - Slice matching: < 1 ms
  - 2D resize: 10-50 ms per slice
  - Blending: 5-20 ms per slice
  - **Total**: 15-70 ms per slice

- **3D Mode**:
  - Volume conversion: 100-500 ms (one-time)
  - 3D resampling: 500-2000 ms (one-time, cached)
  - Slice extraction: < 1 ms (from cached volume)
  - Blending: 5-20 ms per slice
  - **Total**: 600-2500 ms first slice, 5-20 ms subsequent slices

### Optimization Strategies

1. **Caching**: 3D mode caches resampled volumes to avoid repeated resampling
2. **Lazy evaluation**: Resampling only occurs when fusion is enabled
3. **Thread-safe caching**: Uses locks for multi-threaded access
4. **Cache invalidation**: Clears cache when series changes

---

## Conclusion

The image fusion feature provides flexible and accurate spatial alignment between different imaging series. The choice between 2D and 3D modes depends on the spatial relationship between series and the required accuracy. Overall, the system achieves sub-millimeter to low-millimeter accuracy in typical use cases, with 3D mode providing better accuracy for complex spatial relationships.

For detailed usage instructions, see the Quick Start Guide in the application Help menu.

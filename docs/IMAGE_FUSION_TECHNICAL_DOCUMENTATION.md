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

There are two broad classes of error sources in 2D fusion:

- **Algorithm‑intrinsic errors**: limits of interpolation, rounding and resampling, even when the DICOM metadata is perfectly correct.
- **Metadata / input errors**: problems caused by missing or incorrect DICOM tags (e.g., bad `SliceLocation`, `ImagePositionPatient`, or `ImageOrientationPatient`). In these cases the algorithm behaves “correctly” given its inputs, but the inputs themselves are wrong.

#### Algorithm‑intrinsic error sources (assuming correct DICOM metadata)

1. **2D Interpolation**:
   - **Source (algorithmic)**: Base slice location lies between two overlay slices, so the overlay must be interpolated between them along the slice (through‑plane) direction.
   - **Method**: Linear interpolation along the Z‑axis between the two bracketing slices.
   - **Error (native units)**: Typically up to about **±0.5 overlay slices** (±0.5 voxels along Z) in the worst case, because the true signal may not be exactly linear between slices.
   - **Derived physical error**:
     - For 1.0 mm slice spacing: ±0.5 slices ≈ **±0.5 mm**.
     - For 3.0 mm slice spacing: ±0.5 slices ≈ **±1.5 mm**.
   - **Impact**: Minor blurring in the through‑plane direction; in‑plane (x/y) placement of structures remains aligned to the base grid.

2. **Pixel Spacing Scaling**:
   - **Source (algorithmic)**: Different in‑plane pixel spacings between base and overlay require scaling the overlay in x/y to match the base’s physical FOV.
   - **Method**: 2D resize of the overlay image using bilinear interpolation.
   - **Error (native units)**:
     - Resampling introduces sub‑pixel interpolation errors in x and y.
     - Typical local error: about **±0.5 pixels** (half of one output pixel) at edges or high‑contrast boundaries.
   - **Derived physical error**:
     - For 1.0 mm pixel spacing: ±0.5 pixels ≈ **±0.5 mm**.
     - For 0.5 mm pixel spacing: ±0.5 pixels ≈ **±0.25 mm**.
   - **Impact**: Slight softening of edges and fine detail; geometric alignment to the base pixel grid is preserved.

3. **Translation Offset Rounding**:
   - **Source (algorithmic)**: Translation offsets are computed in mm from `ImagePositionPatient` and then converted to pixels; final array indices must be integers.
   - **Method**: Offsets are rounded to the nearest pixel when placing the overlay on a base‑sized canvas.
   - **Error (native units)**:
     - Rounding to integer indices introduces up to **±0.5 pixels** of error in x and y.
   - **Derived physical error**:
     - For 1.0 mm pixel spacing: ±0.5 pixels ≈ **±0.5 mm**.
     - For 0.5 mm pixel spacing: ±0.5 pixels ≈ **±0.25 mm**.
   - **Impact**: Sub‑pixel misalignment; typically not visually obvious, but relevant if you are doing very precise measurements.

#### Metadata / input‑driven error sources

4. **Slice Location Extraction**:
   - **Source (metadata)**: Missing or inaccurate `SliceLocation` or `ImagePositionPatient` tags for either series.
   - **Behaviour**: The algorithm falls back from `SliceLocation` to `ImagePositionPatient[2]`, but if these tags are wrong or inconsistent, the base and overlay slices will be matched using incorrect physical positions.
   - **Error**: There is no fixed bound in pixels or mm; errors can range from fraction‑of‑slice offsets up to many slices (tens or hundreds of voxels) if slice positions are mis‑encoded.
   - **Impact**: The overlay slice chosen for fusion may not correspond to the same anatomical location as the base slice (e.g., fusing the wrong axial level), regardless of how accurate the interpolation algorithm is.

5. **Orientation Mismatch** (2D path cannot handle fully):
   - **Source (metadata)**: Different `ImageOrientationPatient` between base and overlay (e.g., axial vs sagittal, or rotated acquisitions).
   - **Behaviour**: 2D mode assumes that in‑plane axes line up; if orientations differ, no amount of in‑plane scaling/translation will fully correct the mis‑registration.
   - **Error**:
     - In‑plane offsets can be several pixels to tens of pixels, depending on the degree of rotation or tilt.
     - In physical units this can correspond to **several millimetres up to centimetres**, especially in larger FOVs.
   - **Impact**: Potentially severe misalignment (organs or lesions appearing in the wrong place) that cannot be fixed by the 2D algorithm alone.
   - **Mitigation**: The system recommends 3D mode when orientation differences are detected (direction cosine difference ≥ 0.1), and you should treat any 2D fusion in such cases as qualitative at best.

### Accuracy Estimates (2D Mode)

The estimates below assume that the DICOM spatial metadata (`PixelSpacing`, `ImagePositionPatient`, `ImageOrientationPatient`, etc.) is internally consistent and correctly describes how the pixels relate to the patient. Under that assumption, only the algorithm‑intrinsic errors described above contribute to misalignment.

- **Best Case** (same orientation, same pixel spacing, exact slice match; interpolation not needed):
  - Spatial accuracy (native): about **±0.5 pixels** in x/y from scaling and translation rounding, and ≈0 pixels through‑plane.
  - Derived physical accuracy:
    - At 1.0 mm spacing: ≈ **±0.5 mm** in‑plane.
    - At 0.5 mm spacing: ≈ **±0.25 mm** in‑plane.
  - **Total error** (algorithm‑only): on the order of **±0.5–1.0 pixels** (≈±0.5–1.0 mm for 1.0 mm spacing).

- **Typical Case** (same orientation, different pixel spacing, interpolation needed between reasonably spaced slices):
  - Spatial accuracy (native):
    - In‑plane: **±0.5–1.0 pixels** from scaling and rounding.
    - Through‑plane: up to **±0.5 overlay slices** from 2D interpolation.
  - Derived physical accuracy:
    - At 1.0 mm spacing: ≈ **±0.5–1.5 mm** combined in‑ and through‑plane.
    - At 3.0 mm slice spacing: through‑plane component can reach **±1.5 mm** (±0.5 slices).
  - **Total error** (algorithm‑only): typically **±1.0–2.5 mm** depending on slice spacing and contrast structure.

- **Worst Case (algorithm‑only)** (still assuming correct metadata, but using 2D mode where 3D would be better, e.g., very thick slices and sparse sampling):
  - Spatial accuracy (native): several pixels of combined in‑plane and through‑plane interpolation error.
  - Derived physical error: can reach multiple millimetres, especially with thick slices.
  - **Total error** (algorithm‑only): may become large enough that 3D resampling is strongly recommended.

> **Metadata error scenarios** (e.g., wrong `SliceLocation` or `ImageOrientationPatient`) are not bounded by the ranges above. In those cases, pixel‑level misalignments can be arbitrarily large (multiple slices or strong rotations), and the fusion result should be treated as qualitatively wrong regardless of the algorithm’s nominal accuracy.

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
   - Skip 2D resize and translation (already handled by 3D interpolation/resampling on the full volume)

### Error Sources (3D Mode)

As with 2D mode, 3D fusion errors fall into **algorithm‑intrinsic** and **metadata / input‑driven** categories.

#### Algorithm‑intrinsic error sources (assuming correct DICOM metadata)

1. **3D Resampling Interpolation**:
   - **Source (algorithmic)**: Interpolating voxel values when mapping the overlay volume into the base volume’s grid.
   - **Linear interpolation error (native units)**:
     - Sub‑voxel accuracy: typically up to about **±0.5 voxels** in each dimension (x, y, z) near sharp edges.
     - Combined 3D interpolation error magnitude: √(0.5² + 0.5² + 0.5²) ≈ **±0.87 voxels** in the worst case.
   - **Derived physical error** (for isotropic 1.0 mm voxels):
     - ±0.5 voxels per axis ≈ **±0.5 mm** per axis.
     - Combined 3D magnitude ≈ **±0.87 mm**.
   - **Higher‑order interpolation (cubic / B‑spline)**:
     - Typical interpolation error: about **±0.3–0.4 voxels** per axis.
     - Combined 3D magnitude ≈ **±0.5–0.7 voxels** (≈±0.5–0.7 mm for 1.0 mm spacing).
   - **Nearest‑neighbor interpolation**:
     - Can deviate by up to **±0.5 voxels** in each dimension (choosing the nearest existing sample).
     - Similar voxel‑scale error magnitude to linear, but with blockier appearance.
   - **Impact**: Slight blurring or stair‑step artifacts at boundaries; geometry remains correctly positioned on the base grid.

2. **Rescale Parameter Consistency (when metadata is correct but non‑uniform)**:
   - **Source (algorithmic/metadata interaction)**: If rescale slope/intercept vary across slices in a series, but the implementation applies a single set of parameters taken from the first slice.
   - **Behaviour**: All resampled voxels are converted using one global `(slope, intercept)` pair.
   - **Error**: Differences in per‑slice rescale parameters will appear as per‑slice intensity scaling errors, not geometric misalignment:
     - Pixel intensities may be off by a factor proportional to the slope/intercept differences.
   - **Impact**: Quantitative values in the overlay (e.g., SUV) may be slightly wrong from slice to slice, but spatial placement remains determined by the volume resampling grid.

#### Metadata / input‑driven error sources

3. **Slice Location Sorting**:
   - **Source (metadata)**: Missing or inaccurate `SliceLocation` / `ImagePositionPatient` used to order slices into a volume.
   - **Behaviour**: The resampler sorts slices by their reported locations; slices without valid locations may be dropped, and mis‑ordered slices will produce a volume with discontinuities or overlaps.
   - **Error**: Not easily bounded in voxels or mm; errors can range from minor ordering noise up to gross mis‑ordering of slices or missing chunks of the volume.
   - **Impact**: Distorted or incomplete 3D overlay volume, so fused slices may show incorrect anatomy for a given Z index, even if interpolation itself is mathematically correct.

4. **Slice Spacing Calculation**:
   - **Source (metadata)**: Inaccurate `ImagePositionPatient`, `ImageOrientationPatient`, or `SliceThickness`.
   - **Method**: The ideal spacing is computed by projecting position differences onto the slice normal; fallbacks may use 3D Euclidean distance or `SliceThickness` alone.
   - **Error**:
     - With correct metadata, spacing error is typically **±0.1–0.5 mm**.
     - With oblique slices and only 3D distance, spacing can be overestimated:
       - For 30° oblique: spacing error ≈ **13%** of the true spacing.
       - For 45° oblique: spacing error ≈ **29%** of the true spacing.
   - **Impact**: Incorrect spacing distorts the Z‑axis scale of the volume; overlay voxels may appear too close together or too far apart in the through‑plane dimension.

5. **Direction Matrix Construction**:
   - **Source (metadata)**: `ImageOrientationPatient` encodes row/column direction cosines; small rounding or non‑orthogonality can occur.
   - **Behaviour**: The resampler normalizes these vectors and computes a slice normal; tiny numerical differences change the direction matrix.
   - **Error**:
     - For well‑formed DICOM, rounding errors are usually < **0.001** in cosine components.
     - This corresponds to orientation errors typically < **0.1°**.
   - **Impact**: Very small rotations of the resampled volume relative to the true orientation; in practice this is negligible compared to voxel size.

6. **Frame of Reference Assumption**:
   - **Source (metadata)**: Assumes same `FrameOfReferenceUID` for base and overlay series.
   - In DICOM, `FrameOfReferenceUID` defines a patient‑fixed 3D coordinate system. Two series that share the same UID (for example, CT and PET from a hybrid PET‑CT acquisition) are expected to be already registered in physical space.
   - The 3D resampling code uses an identity (no‑movement) transform when it resamples the overlay volume into the base volume’s grid. This is only correct if both series really do share the same frame of reference and have consistent spatial metadata.
   - **Error**: If the Frame of Reference differs, the identity transform is mathematically incorrect: the volumes are not actually in the same coordinate system, so origin, orientation, and voxel spacing no longer correspond. The resampling will still produce an image, but voxels will be mapped to the wrong anatomical locations.
   - **Impact (native units)**: Misalignment can be many voxels in x, y, and z, depending on the underlying registration error between the frames.
   - **Derived physical impact**: Misalignments often range from several millimetres up to centimetres (e.g., entire organs shifted), especially across different scanners or sessions.
   - **Mitigation and warning behaviour**: The fusion coordinator checks the `FrameOfReferenceUID` from each series. If the UIDs do not match, the fusion status area shows a clear warning that the frames of reference differ. **Fusion is still allowed in this situation**, but the result should be treated as potentially inaccurate and not used for precise quantitative work without external registration and validation.

7. **Rescale Parameter Inconsistency (metadata)**:
   - **Source (metadata)**: Rescale slope/intercept tags differ between slices within a series.
   - **Behaviour**: If not handled per‑slice, using one set of parameters for the whole volume will mis‑scale some slices’ intensities.
   - **Error**: Intensity (value) errors, not geometric misalignments; magnitude depends on how different the per‑slice parameters are.
   - **Impact**: Can affect quantitative interpretation of overlay values (e.g., SUV), but geometry remains anchored by the resampling grid and frame of reference.

### Accuracy Estimates (3D Mode)

These estimates assume that spatial DICOM metadata is correct and consistent (including `FrameOfReferenceUID`, `ImageOrientationPatient`, `ImagePositionPatient`, `PixelSpacing`, and `SliceThickness`). Under that assumption, only the interpolation and numerical effects described in the algorithm‑intrinsic section contribute to geometric error.

- **Best Case** (accurate spatial metadata, linear interpolation, same Frame of Reference):
  - Spatial accuracy (native): sub‑voxel in all three dimensions, typically **±0.5–0.87 voxels** in combined 3D magnitude.
  - Derived physical accuracy (for 1.0 mm isotropic voxels): about **±0.6–1.0 mm** total positional error.
  - Slice spacing error (from normal‑based calculation): typically within **±0.1 mm** if metadata is clean.

- **Typical Case** (good spatial metadata, linear interpolation):
  - Spatial accuracy (native): combined interpolation error around **±0.87 voxels**, plus small spacing and orientation uncertainties.
  - Derived physical accuracy: **±1.0–1.5 mm** in most clinical CT/PET settings.
  - Slice spacing error: **±0.2–0.5 mm** depending on acquisition geometry and obliquity.

- **Worst Case (algorithm‑only)** (still assuming correct metadata, but with aggressive resampling between very dissimilar grids and orientations):
  - Spatial accuracy (native): a few voxels of total 3D error in extreme cases.
  - Derived physical error: several millimetres, especially with thick slices or large rotations.
  - **Total error** (algorithm‑only): may become large enough that further refinement (e.g., higher‑order interpolation or dedicated registration) is desirable.

> **Metadata error scenarios** (e.g., wrong `FrameOfReferenceUID`, incorrect slice ordering, or bad `PixelSpacing`) are not captured by the ranges above. In those cases, voxel‑level misalignments can be arbitrarily large, and the fused images should be regarded as qualitatively misleading unless the metadata is corrected or an explicit registration step is applied.

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

The tables below summarize the main error sources across 2D and 3D fusion, grouped by **algorithm‑intrinsic** vs **DICOM metadata/input‑driven** origins.

#### Algorithm‑intrinsic error sources (with correct metadata)

| Error Source | 2D Mode Error (pixels/voxels & mm) | 3D Mode Error (voxels & mm) | Notes |
|-------------|--------------------------------------|------------------------------|-------|
| Slice interpolation | Up to ≈±0.5 overlay slices (±0.5 voxels in Z); ≈±0.5 mm at 1 mm spacing, ≈±1.5 mm at 3 mm spacing | N/A (effect is handled by 3D interpolation/resampling instead of 2D per‑slice interpolation) | Through‑plane interpolation when the base slice lies between overlay slices |
| Pixel spacing scaling | ≈±0.5 pixels in x/y; ≈±0.5 mm at 1 mm pixels, ≈±0.25 mm at 0.5 mm pixels | N/A (3D resampling handles in‑plane scaling in voxel space) | 2D resize of overlay to match base FOV; slight blurring at edges |
| Translation offset (rounding) | ±0.5 pixels in x/y; ≈±0.5 mm at 1 mm pixels, ≈±0.25 mm at 0.5 mm pixels | N/A (3D translation handled in continuous world space by resampler) | Rounding mm offsets to integer pixel indices in 2D mode |
| 3D resampling interpolation | N/A | ≈±0.5–0.87 voxels (linear); ≈±0.3–0.7 voxels (cubic/B‑spline); ≈±0.5–0.9 mm for 1 mm voxels | Unavoidable sub‑voxel error from mapping overlay into base grid |

#### Metadata / input‑driven error sources

| Error Source | 2D Mode Error (pixels/voxels & mm) | 3D Mode Error (voxels & mm) | Notes |
|-------------|--------------------------------------|------------------------------|-------|
| Slice location extraction | Unbounded; can mis‑match slices by many indices (tens of voxels) if tags are wrong | Same: can mis‑order or drop slices when building volume | Incorrect/missing `SliceLocation` / `ImagePositionPatient` affects which slices are fused, not the interpolation math |
| Orientation mismatch | Can be many pixels (or entire FOV) off; several mm–cm in physical space | Reduced to interpolation‑scale error (≈sub‑voxel) if metadata is correct and 3D resampling is used | Different `ImageOrientationPatient`; 2D mode cannot fully correct this, 3D mode relies on accurate direction cosines |
| Slice spacing calculation | N/A | Typically ±0.1–0.5 mm with good metadata; larger % errors (10–30%+) if spacing derived from oblique positions | Depends on `ImagePositionPatient`, `SliceThickness`, and orientation; algorithm follows reported geometry |
| Frame of Reference mismatch | Can be very large (entire organs shifted) when fusing across frames | Same: misregistration can be many voxels; often several mm–cm | Wrong or differing `FrameOfReferenceUID`; algorithm assumes identity transform and cannot correct this automatically |
| Rescale parameter inconsistency | Low (intensity only) | Low (intensity only) | Per‑slice differences in rescale slope/intercept cause value, not geometric, errors if a single global pair is used |

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

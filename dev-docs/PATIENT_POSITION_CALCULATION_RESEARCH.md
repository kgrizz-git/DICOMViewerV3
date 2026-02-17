# Patient Position Calculation Research: ImagePositionPatient Formula

## Overview

This document provides detailed research findings on the correct method for calculating patient position coordinates (in mm) from pixel coordinates in a DICOM image. This research was conducted to address issues with crosshair ROI coordinate calculations where the two in-plane directions appear to be switched.

## Executive Summary

**The Issue:** The in-plane directions (row vs. column) may be getting switched in the patient coordinate calculation.

**Key Finding:** According to the DICOM standard and multiple authoritative sources, the correct formula uses:
- ImageOrientationPatient **first three values** = **row direction** cosines
- ImageOrientationPatient **last three values** = **column direction** cosines
- PixelSpacing **first value** = **row spacing** (vertical/between rows)
- PixelSpacing **second value** = **column spacing** (horizontal/between columns)

**Critical Convention:** 
- **pixel_x** = **column** index (horizontal position in image)
- **pixel_y** = **row** index (vertical position in image)

## DICOM Standard Tags

### 1. ImagePositionPatient (0020,0032)

**Definition:** The (x, y, z) coordinates in millimeters of the **upper left-hand corner** (center of the first pixel at indices [0, 0]) of the image, in the patient-based coordinate system.

**Type:** Three decimal strings representing the x, y, and z coordinates in mm.

**Usage:** This is the origin point for the transformation formula.

### 2. ImageOrientationPatient (0020,0037)

**Definition:** The direction cosines of the first row and first column with respect to the patient coordinate system.

**Type:** Six decimal strings.

**Structure:**
```
[Xr, Yr, Zr, Xc, Yc, Zc]
```

Where:
- **First three values [Xr, Yr, Zr]:** Direction cosines of the **first row** of the image (direction from left to right across the image, as column index increases)
- **Last three values [Xc, Yc, Zc]:** Direction cosines of the **first column** of the image (direction from top to bottom down the image, as row index increases)

**Important:** Both vectors are unit vectors (length = 1) and must be orthogonal (perpendicular) to each other.

**From DICOM Standard:**
> "Image Orientation (Patient) (0020,0037) specifies the direction cosines of the first row and the first column with respect to the patient. These Attributes shall be provided as a pair. Row value for the x, y, and z axes respectively followed by the Column value for the x, y, and z axes respectively."

### 3. PixelSpacing (0028,0030)

**Definition:** Physical distance (in mm) between the centers of adjacent pixels.

**Type:** Two decimal strings.

**Structure:**
```
[Δr, Δc]
```

Where:
- **First value [Δr]:** Spacing between pixel centers in the **row direction** (vertical spacing, distance between adjacent rows)
- **Second value [Δc]:** Spacing between pixel centers in the **column direction** (horizontal spacing, distance between adjacent columns)

**Important:** Row spacing is the vertical distance; column spacing is the horizontal distance.

## Pixel Coordinate Convention

In DICOM and most image processing contexts:

- **Row index (i)** = **pixel_y** = vertical position (0 to Rows-1)
- **Column index (j)** = **pixel_x** = horizontal position (0 to Columns-1)

So when accessing a pixel in an array:
```python
pixel_value = image_array[row, column]  # or image_array[y, x]
```

- **row / y / pixel_y**: increases going DOWN the image (top to bottom)
- **column / x / pixel_x**: increases going RIGHT across the image (left to right)

## The Standard Formula

To convert pixel coordinates (pixel_x, pixel_y) to patient coordinates (X, Y, Z):

### Mathematical Notation

```
P(pixel_x, pixel_y) = IPP + pixel_y × Δr × R + pixel_x × Δc × C
```

Where:
- **P** = Patient position (X, Y, Z) in mm
- **IPP** = ImagePositionPatient (origin at pixel [0,0])
- **pixel_y** = row index (vertical, 0 to Rows-1)
- **pixel_x** = column index (horizontal, 0 to Columns-1)
- **Δr** = PixelSpacing[0] (row spacing, vertical)
- **Δc** = PixelSpacing[1] (column spacing, horizontal)
- **R** = [Xr, Yr, Zr] = row direction vector (first 3 values of IOP)
- **C** = [Xc, Yc, Zc] = column direction vector (last 3 values of IOP)

### Component-wise Formula

```
X = IPP_x + pixel_y × Δr × Xr + pixel_x × Δc × Xc
Y = IPP_y + pixel_y × Δr × Yr + pixel_x × Δc × Yc
Z = IPP_z + pixel_y × Δr × Zr + pixel_x × Δc × Zc
```

### Pseudocode

```python
def pixel_to_patient_coordinates(dataset, pixel_x, pixel_y):
    """
    Convert pixel coordinates to patient space.
    
    Args:
        dataset: DICOM dataset
        pixel_x: Column index (horizontal position, 0 to Columns-1)
        pixel_y: Row index (vertical position, 0 to Rows-1)
    
    Returns:
        Tuple of (X, Y, Z) patient coordinates in mm
    """
    # Get ImagePositionPatient (origin)
    IPP = dataset.ImagePositionPatient  # [IPP_x, IPP_y, IPP_z]
    
    # Get ImageOrientationPatient
    IOP = dataset.ImageOrientationPatient  # [Xr, Yr, Zr, Xc, Yc, Zc]
    row_direction = IOP[0:3]     # First 3: row direction [Xr, Yr, Zr]
    col_direction = IOP[3:6]     # Last 3: column direction [Xc, Yc, Zc]
    
    # Get PixelSpacing
    PS = dataset.PixelSpacing  # [Δr, Δc]
    row_spacing = PS[0]        # First: row spacing (vertical)
    col_spacing = PS[1]        # Second: column spacing (horizontal)
    
    # Calculate patient position
    X = IPP[0] + pixel_y * row_spacing * row_direction[0] + pixel_x * col_spacing * col_direction[0]
    Y = IPP[1] + pixel_y * row_spacing * row_direction[1] + pixel_x * col_spacing * col_direction[1]
    Z = IPP[2] + pixel_y * row_spacing * row_direction[2] + pixel_x * col_spacing * col_direction[2]
    
    return (X, Y, Z)
```

## 3D/Multi-Slice Extension

For 3D volumes with multiple slices, the formula extends to include the slice direction:

```
P(pixel_x, pixel_y, slice_idx) = IPP + pixel_y × Δr × R + pixel_x × Δc × C + slice_idx × Δs × N
```

Where:
- **slice_idx** = slice index (0 to NumberOfSlices-1)
- **Δs** = slice spacing (from SpacingBetweenSlices or SliceThickness)
- **N** = slice normal vector = **R × C** (cross product, perpendicular to image plane)

The slice normal is calculated as:
```
N = R × C  (cross product of row and column direction vectors)
```

This gives the direction perpendicular to the image plane, pointing from one slice to the next.

## Patient Coordinate System (LPS)

DICOM uses the **LPS** coordinate system:
- **L** (Left): +X axis points towards patient's left
- **P** (Posterior): +Y axis points towards patient's back  
- **S** (Superior): +Z axis points towards patient's head

Note: Some systems use **RAS** (Right-Anterior-Superior) which is the opposite sign convention.

## Common Pitfalls and Issues

### 1. Swapping Row and Column Directions

**Problem:** Using column direction with pixel_y (row index) and row direction with pixel_x (column index).

**Incorrect:**
```python
# WRONG!
patient_pos = IPP + pixel_x * row_spacing * row_direction + pixel_y * col_spacing * col_direction
```

**Correct:**
```python
# CORRECT!
patient_pos = IPP + pixel_y * row_spacing * row_direction + pixel_x * col_spacing * col_direction
```

### 2. Confusing pixel_x/pixel_y with row/column

**Remember:**
- **pixel_x = column** (horizontal)
- **pixel_y = row** (vertical)

When someone passes (x, y) coordinates from a mouse click:
- x usually means horizontal position → **column index**
- y usually means vertical position → **row index**

### 3. Swapping PixelSpacing order

**Problem:** Using PixelSpacing[1] (column spacing) with row direction, or vice versa.

**Remember:**
- PixelSpacing[0] = row spacing (vertical) → use with **pixel_y** and **row_direction**
- PixelSpacing[1] = column spacing (horizontal) → use with **pixel_x** and **col_direction**

### 4. Incorrect ImageOrientationPatient indexing

**Problem:** Using indices [0:3] for column direction and [3:6] for row direction.

**Remember:**
- ImageOrientationPatient[0:3] = **row direction** (first three values)
- ImageOrientationPatient[3:6] = **column direction** (last three values)

## Verification Checklist

To verify your implementation is correct:

1. ✓ Row direction uses **first 3** values of ImageOrientationPatient
2. ✓ Column direction uses **last 3** values of ImageOrientationPatient
3. ✓ Row spacing is **PixelSpacing[0]**
4. ✓ Column spacing is **PixelSpacing[1]**
5. ✓ **pixel_y** (row index) is multiplied by **row spacing** and **row direction**
6. ✓ **pixel_x** (column index) is multiplied by **column spacing** and **column direction**
7. ✓ ImagePositionPatient is the origin (added before any offsets)
8. ✓ For 3D: slice normal = cross product of row × column (in that order)

## References

### Primary Sources

1. **DICOM Standard - Part 3, Section C.7.6.2 (Image Plane Module)**
   - URL: https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_C.7.6.2.html
   - Official specification for ImagePositionPatient and ImageOrientationPatient

2. **DICOM Standard Browser (Innolitics)**
   - ImagePositionPatient: https://dicom.innolitics.com/ciods/ct-image/image-plane/00200032
   - ImageOrientationPatient: https://dicom.innolitics.com/ciods/ct-image/image-plane/00200037
   - PixelSpacing: https://dicom.innolitics.com/ciods/ct-image/image-plane/00280030

3. **NiBabel Documentation - DICOM Orientation**
   - URL: https://nipy.org/nibabel/dicom/dicom_orientation.html
   - Comprehensive explanation with examples

4. **DICOM is Easy Blog**
   - Getting Oriented: https://dicomiseasy.blogspot.com/2013/06/getting-oriented-using-image-plane.html
   - Tutorial on understanding image plane orientation

5. **Michele Pierri - Orientation in DICOM**
   - URL: https://www.micheledpierri.com/2025/10/12/dicom-orientation/
   - Clear explanation with diagrams

### Additional Resources

6. **UCL Computer Science - DICOM for MRI Images**
   - URL: http://www.cs.ucl.ac.uk/fileadmin/cmic/Documents/DavidAtkinson/DICOM.pdf
   - Technical reference for MRI-specific DICOM

7. **RedBrickAI - Introduction to DICOM Coordinate Systems**
   - URL: https://www.redbrickai.com/blog/2022-01-15-intro-to-dicom-coordinate-systems
   - Practical guide to coordinate transformations

8. **GitHub Gist - Image Orientation in DICOM**
   - URL: https://gist.github.com/agirault/60a72bdaea4a2126ecd08912137fe641
   - Code examples and explanations

9. **Stack Overflow - DICOM and Image Position Patient**
   - URL: https://stackoverflow.com/questions/30814720/dicom-and-the-image-position-patient
   - Community discussion and solutions

10. **MathWorks - Medical Image Coordinate Systems**
    - URL: https://www.mathworks.com/help/medical-imaging/ug/medical-image-coordinate-systems.html
    - MATLAB perspective on medical imaging coordinates

## Conclusion

The correct formula for calculating patient coordinates from pixel coordinates is:

```
PatientPosition = ImagePositionPatient 
                + (pixel_y × PixelSpacing[0] × ImageOrientationPatient[0:3])
                + (pixel_x × PixelSpacing[1] × ImageOrientationPatient[3:6])
```

The key points to remember:
1. **pixel_y** is the **row** index (vertical) and uses **row direction** (first 3 IOP values) and **row spacing** (PS[0])
2. **pixel_x** is the **column** index (horizontal) and uses **column direction** (last 3 IOP values) and **column spacing** (PS[1])
3. The order matters - mixing these up will cause the in-plane directions to be switched

Any implementation that deviates from this formula will produce incorrect patient coordinates, particularly noticeable when the two in-plane directions are switched (e.g., using column direction with row indices).

---

**Document Created:** 2026-02-17  
**Research Purpose:** Investigating crosshair ROI patient coordinate calculation issues  
**Issue Description:** Two in-plane directions appear to be switched in current implementation

# Crosshair ROI and Patient Coordinates

This document describes how the displayed coordinates are determined when the user draws a crosshair ROI, and how pixel indices are converted to patient coordinates (e.g. for sagittal, coronal, and axial views).

---

## 1. Crosshair displayed coordinates (overview)

When the user clicks in **crosshair mode**, the viewer:

1. Converts the mouse click to **scene coordinates**.
2. Derives **image indices** (x, y, z) from that position.
3. Optionally computes **patient coordinates** (mm) from those indices and the current DICOM dataset.
4. Shows **(x, y, z)** and, when available, **Patient: (px, py, pz) mm** on the crosshair label.

The same (x, y, z) are used for the pixel value lookup and for the optional patient-coordinate line.

---

## 2. Where coordinates are determined (code flow)

### 2.1 Initial click (image viewer)

**File:** `src/gui/image_viewer.py`

On mouse press in crosshair mode:

1. **Scene position**  
   `scene_pos = self.mapToScene(event.position().toPoint())`  
   The click is converted from widget coordinates to **scene coordinates**. The scene is set up so that one scene unit corresponds to one image pixel (image item at origin).

2. **Image indices**  
   - **x** = `int(scene_pos.x())` — column index in the image.  
   - **y** = `int(scene_pos.y())` — row index in the image.  
   - **z** = `get_current_slice_index_callback()` (or 0 if no callback) — slice index.

3. **Pixel value string**  
   `pixel_value_str = self._get_pixel_value_at_coords(dataset, x, y, z, use_rescaled)`  
   So the value shown is for the pixel at (x, y, z) in the current dataset/slice.

4. **Signal**  
   `self.crosshair_clicked.emit(scene_pos, pixel_value_str, x, y, z)`  
   The coordinator receives this and creates the crosshair.

### 2.2 Patient coordinates (coordinator)

**File:** `src/gui/crosshair_coordinator.py`

In `handle_crosshair_clicked`:

- **Patient coordinates** are computed from the **same (x, y, z)** (image column, row, slice):  
  `patient_coords = pixel_to_patient_coordinates(current_dataset, x, y, z)`  
- If present, the label is extended with:  
  `"Patient: (px, py, pz) mm"`  
  So the **displayed** coordinates are:
  - **(x, y, z)** = image indices (column, row, slice).
  - **Patient (px, py, pz) mm** = result of `pixel_to_patient_coordinates(dataset, x, y, z)` when the dataset supports it.

### 2.3 After moving a crosshair

**File:** `src/gui/crosshair_coordinator.py` — `_update_crosshair_pixel_values`

When the user drags a crosshair to a new scene position:

- **x** = `int(new_pos.x())`  
- **y** = `int(new_pos.y())`  
- **z** = `get_current_slice_index()`  

Then the pixel value and patient coordinates are recomputed at (x, y, z) and the crosshair label is updated via `crosshair_item.update_pixel_values(...)`.

### 2.4 What is shown on the crosshair

**File:** `src/tools/crosshair_manager.py` — `CrosshairItem`

- **Privacy mode:** `"({x}, {y}, {z})"`  
- **Normal:** `"Pixel Value: {pixel_value_str}\n({x}, {y}, {z})"`  
  `pixel_value_str` may already include the `"Patient: (px, py, pz) mm"` line added by the coordinator.

---

## 3. `pixel_to_patient_coordinates` — how it works

**File:** `src/utils/dicom_utils.py`  
**Function:** `pixel_to_patient_coordinates(dataset, pixel_x, pixel_y, slice_index=0)`

This function converts **image indices** (column, row, slice) into **patient coordinates in mm**. It does **not** have separate branches for axial, sagittal, or coronal; the mapping is entirely determined by the **DICOM geometry** of the **dataset** passed in.

### 3.1 DICOM tags used

| Tag / concept | Role |
|---------------|------|
| **ImagePositionPatient** | Position of the **top-left pixel (0, 0)** of the image in patient coordinates (mm). |
| **ImageOrientationPatient** | Six direction cosines: first three = **row direction** (patient-space direction in which **image row index** increases), next three = **column direction** (patient-space direction in which **image column index** increases). |
| **Pixel Spacing** | (row_spacing, column_spacing) in mm — from `PixelSpacing` or fallbacks (see `get_pixel_spacing`). |
| **Slice spacing** | From `SpacingBetweenSlices` or `SliceThickness` (or 0 if missing). |

**Parameter convention in code:**

- `pixel_x` = **column** index (image X).  
- `pixel_y` = **row** index (image Y).  
- `slice_index` = slice index (which slice in the stack).

So: **row** in the formula below corresponds to **pixel_y**, and **column** to **pixel_x**.

### 3.2 Slice direction (out-of-plane)

The direction in patient space along which **slice index** increases is **not** stored explicitly in DICOM. It is derived as the **slice normal**:

- **slice_normal** = **row_cosine × col_cosine** (cross product, right-hand rule).  
- So slice_normal is perpendicular to the image plane; moving to the “next” slice moves along this vector (by `slice_spacing` per slice index).

Thus:

- **Image row** → patient direction = **row_cosine** (from ImageOrientationPatient).  
- **Image column** → patient direction = **col_cosine**.  
- **Slice (out-of-plane)** → patient direction = **slice_normal**.

Which of patient ±X, ±Y, ±Z corresponds to row, column, or slice **depends on the dataset’s ImageOrientationPatient** (and thus on whether the series is axial, sagittal, coronal, or oblique).

### 3.3 Formula

```
patient_pos = ImagePositionPatient
            + pixel_y * row_spacing * row_cosine
            + pixel_x * col_spacing * col_cosine
            + slice_index * slice_spacing * slice_normal
```

So:

- **Row (pixel_y)** moves along **row_cosine** by `row_spacing` per unit.  
- **Column (pixel_x)** moves along **col_cosine** by `col_spacing` per unit.  
- **Slice (slice_index)** moves along **slice_normal** by `slice_spacing` per unit.

The result is (X, Y, Z) in **patient mm** (typically LPS or similar, depending on the DICOM convention used in the dataset).

### 3.4 How axial, sagittal, and coronal are “handled”

The function does **not** check for “sagittal” or “coronal” by name. It is **view-agnostic**:

- For **axial** series: ImageOrientationPatient usually has row/col in the patient XY plane (e.g. row = left–right, col = anterior–posterior), so **slice_normal** is along patient Z (superior–inferior).  
- For **sagittal** series: row/col lie in a plane (e.g. Y–Z), and **slice_normal** is along patient X (left–right).  
- For **coronal** series: row/col lie in another plane (e.g. X–Z), and **slice_normal** is along patient Y (anterior–posterior).

In all cases the **same formula** is used. The mapping from (image row, image column, slice) to patient (x, y, z) is fully defined by:

- **ImagePositionPatient** (origin of the image in patient space),  
- **ImageOrientationPatient** (row and column directions),  
- **Pixel Spacing** and slice spacing.

So “how it handles sagittal and coronal” is: it uses whatever orientation the **current dataset** has. If the dataset is a native sagittal or coronal slice, that slice’s ImagePositionPatient and ImageOrientationPatient already encode the correct plane and directions.

### 3.5 Important assumption (reformatted views)

For the displayed patient coordinates to be correct:

- **(pixel_x, pixel_y, slice_index)** must be in the **same convention** as the geometry of the **dataset** passed to `pixel_to_patient_coordinates`.  
- Typically: **dataset** = the slice (or representative frame) currently displayed; **pixel_x** = column, **pixel_y** = row, **slice_index** = index of that slice in the series.

If the viewer shows **reformatted** views (e.g. reslicing an axial stack into sagittal or coronal), then:

- Either the **dataset** (or geometry) passed to `pixel_to_patient_coordinates` must describe that **reformatted** orientation, and (pixel_x, pixel_y, slice_index) must be in the **reformatted** image’s row/column/slice convention,  
- Or the caller must convert from reformatted (display) coordinates to the **native** (e.g. axial) (row, column, slice) before calling this function.

Otherwise, patient coordinates may be wrong for reformatted sagittal/coronal views.

### 3.6 Helper functions used

- **get_image_position(dataset)** — returns ImagePositionPatient as a 3-element array.  
- **get_image_orientation(dataset)** — returns `(row_cosine, col_cosine)` from ImageOrientationPatient.  
- **get_pixel_spacing(dataset)** — returns (row_spacing, col_spacing); uses Pixel Spacing, Imager Pixel Spacing, or FOV-based calculation.  
- **get_slice_thickness(dataset)** — SliceThickness; slice spacing also uses SpacingBetweenSlices when present.

If any required tag is missing, `pixel_to_patient_coordinates` returns `None` and no patient coordinates are shown on the crosshair.

---

## 4. Summary

| What is displayed | How it is determined |
|-------------------|------------------------|
| **(x, y, z)**     | Image column, row, and slice index from scene position: `x = int(scene_pos.x())`, `y = int(scene_pos.y())`, `z = get_current_slice_index()`. |
| **Pixel value**   | Lookup at (x, y, z) in the current dataset via `_get_pixel_value_at_coords`. |
| **Patient (px, py, pz) mm** | `pixel_to_patient_coordinates(current_dataset, x, y, z)` using DICOM ImagePositionPatient, ImageOrientationPatient, Pixel Spacing, and slice spacing. Row/column/slice map to patient axes only through these tags (no explicit sagittal/coronal logic). |

Correctness for sagittal and coronal depends on the **dataset** and **(x, y, z)** representing the **same** image and orientation as the displayed view.

---

## 5. Code Analysis and Verification

### 5.1 Investigation Summary

A thorough code review was conducted to verify the correctness of the patient coordinate calculation implementation, particularly focusing on how pixel indices (row/column) are used in combination with ImageOrientationPatient direction cosines.

### 5.2 DICOM Standard Requirements

According to the DICOM standard (Part 3, Section C.7.6.2 - Image Plane Module):

**ImageOrientationPatient (0020,0037):**
- Contains six values representing direction cosines
- **First three values [0:3]**: Direction cosines for the **row** direction (direction in which the row index increases)
- **Last three values [3:6]**: Direction cosines for the **column** direction (direction in which the column index increases)

**PixelSpacing (0028,0030):**
- Contains two values in mm
- **First value [0]**: Row spacing (distance between centers of adjacent rows, vertical spacing)
- **Second value [1]**: Column spacing (distance between centers of adjacent columns, horizontal spacing)

**Standard Formula:**
```
PatientPosition(i, j) = ImagePositionPatient
                      + i * PixelSpacing[0] * RowDirection
                      + j * PixelSpacing[1] * ColumnDirection
                      + slice_index * slice_spacing * SliceNormal
```
Where:
- `i` = row index (vertical, top to bottom in array)
- `j` = column index (horizontal, left to right in array)
- `RowDirection` = ImageOrientationPatient[0:3]
- `ColumnDirection` = ImageOrientationPatient[3:6]
- `SliceNormal` = RowDirection × ColumnDirection (cross product, right-hand rule)

### 5.3 Code Implementation Review

#### 5.3.1 Coordinate Extraction (`src/gui/image_viewer.py`, lines 1103-1104)

```python
x = int(scene_pos.x())
y = int(scene_pos.y())
```

**Analysis:**
- Qt scene coordinates map directly to image pixel positions (scene is set up with 1:1 correspondence)
- `scene_pos.x()` → horizontal position (left to right) → **column index**
- `scene_pos.y()` → vertical position (top to bottom) → **row index**

**Result:** ✓ CORRECT - x represents column, y represents row

#### 5.3.2 Coordinate Passing (`src/gui/crosshair_coordinator.py`, line 97)

```python
patient_coords = pixel_to_patient_coordinates(current_dataset, x, y, z)
```

**Analysis:**
- `x` (column) is passed as first argument
- `y` (row) is passed as second argument
- Function signature expects `pixel_x`, `pixel_y`, `slice_index`

**Result:** ✓ CORRECT - Arguments are passed in (column, row, slice) order

#### 5.3.3 Direction Cosine Extraction (`src/utils/dicom_utils.py`, lines 295-296)

```python
row_cosine = np.array([float(orient[0]), float(orient[1]), float(orient[2])])
col_cosine = np.array([float(orient[3]), float(orient[4]), float(orient[5])])
```

**Analysis:**
- `row_cosine` extracts ImageOrientationPatient[0:3]
- `col_cosine` extracts ImageOrientationPatient[3:6]
- Matches DICOM standard: first three = row direction, last three = column direction

**Result:** ✓ CORRECT - Direction cosines are extracted properly

#### 5.3.4 Pixel Spacing Extraction (`src/utils/dicom_utils.py`, lines 142-143)

```python
row_spacing = float(pixel_spacing[0])
col_spacing = float(pixel_spacing[1])
```

**Analysis:**
- `row_spacing` = PixelSpacing[0]
- `col_spacing` = PixelSpacing[1]
- Matches DICOM standard: first value = row spacing, second value = column spacing

**Result:** ✓ CORRECT - Pixel spacing is extracted properly

#### 5.3.5 Slice Normal Calculation (`src/utils/dicom_utils.py`, line 361)

```python
slice_normal = np.cross(row_cosine, col_cosine)
```

**Analysis:**
- Uses NumPy cross product: row_cosine × col_cosine
- Follows right-hand rule convention
- Perpendicular to image plane, points in slice progression direction

**Result:** ✓ CORRECT - Slice normal calculation follows DICOM convention

#### 5.3.6 Patient Position Formula (`src/utils/dicom_utils.py`, lines 365-370)

```python
patient_pos = (
    img_pos +
    pixel_y * row_spacing * row_cosine +
    pixel_x * col_spacing * col_cosine +
    slice_index * slice_spacing * slice_normal
)
```

**Analysis:**
Let's trace the formula with actual parameter meanings:
- `pixel_x` = column index (from `x = scene_pos.x()`)
- `pixel_y` = row index (from `y = scene_pos.y()`)

Expanding the formula:
```
patient_pos = img_pos
            + pixel_y * row_spacing * row_cosine
            + pixel_x * col_spacing * col_cosine
            + slice_index * slice_spacing * slice_normal
```

Substituting meanings:
```
patient_pos = img_pos
            + row_index * row_spacing * row_cosine
            + col_index * col_spacing * col_cosine
            + slice_index * slice_spacing * slice_normal
```

This EXACTLY matches the DICOM standard formula where:
- Row index (i) multiplies row spacing and row direction cosines
- Column index (j) multiplies column spacing and column direction cosines

**Result:** ✓ CORRECT - Formula matches DICOM standard

#### 5.3.7 Pixel Value Lookup Verification (`src/gui/image_viewer.py`, line 2329)

To confirm our coordinate interpretation is correct, we verify the pixel value lookup:

```python
pixel_value = float(frame_array[y, x])
```

**Analysis:**
- NumPy array indexing: `array[row, column]`
- Code uses: `frame_array[y, x]`
- Since `y` = row index and `x` = column index, this is correct
- This confirms that our row/column interpretation throughout the chain is consistent

**Result:** ✓ CORRECT - Pixel lookup confirms row/column interpretation

### 5.4 Conclusion

After thorough analysis of the entire coordinate flow from user click through patient coordinate calculation, the implementation is **CORRECT** and follows the DICOM standard precisely:

1. ✓ Scene coordinates are correctly interpreted as (column, row)
2. ✓ ImageOrientationPatient values are correctly extracted as (row_cosine, col_cosine)
3. ✓ PixelSpacing values are correctly extracted as (row_spacing, col_spacing)
4. ✓ The formula correctly applies: row_index × row_spacing × row_cosine + column_index × column_spacing × column_cosine
5. ✓ Slice normal is correctly calculated using cross product
6. ✓ Pixel value lookup confirms the coordinate interpretation is consistent

### 5.5 Potential Sources of Confusion

While the implementation is mathematically correct, there are some aspects that could cause confusion:

1. **Parameter Naming**: The function parameter names `pixel_x` and `pixel_y` might suggest "X-Y coordinates" in a Cartesian sense, but they actually represent (column, row) in the image array sense. The code correctly treats them this way.

2. **Documentation Comments**: The docstrings correctly state:
   - Line 321: `pixel_x: Column index (X in image)`
   - Line 322: `pixel_y: Row index (Y in image)`
   
   This is accurate and matches the implementation.

3. **Coordinate System Terminology**: "X" and "Y" in scene/display coordinates map to "column" and "row" in array indices, which can be confusing when dealing with DICOM's "row direction" and "column direction" cosines. However, the code handles this correctly.

### 5.6 No Issues Found

The crosshair ROI patient position coordinate calculation is implemented correctly according to the DICOM standard. The code properly:
- Interprets scene positions as (column, row) indices
- Extracts DICOM orientation and spacing parameters correctly
- Applies the standard transformation formula
- Handles slice normal calculation properly

If users are experiencing incorrect patient coordinates, the issue is likely elsewhere:
- Incorrect or missing DICOM tags in the dataset
- Display/reformatting issues in multi-planar reconstructions
- Coordinate system interpretation in the viewing software

The `pixel_to_patient_coordinates` function itself is sound.

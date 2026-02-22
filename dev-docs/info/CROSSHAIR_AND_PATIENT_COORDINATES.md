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
| **ImageOrientationPatient** | Six direction cosines: first three = **row direction** (patient-space direction along the image row), next three = **column direction** (patient-space direction along the image column). |
| **Pixel Spacing** | (row_spacing, column_spacing) in mm — from `PixelSpacing` or fallbacks (see `get_pixel_spacing`). |
| **Slice spacing** | From `SpacingBetweenSlices` or `SliceThickness` (or 0 if missing). |

**Parameter convention in code:**

- `pixel_x` = **column** index (image X).  
- `pixel_y` = **row** index (image Y).  
- `slice_index` = slice index (which slice in the stack).

In the formula, **col_cosine** (IOP last three values) is the direction that corresponds to **row index** (pixel_y), and **row_cosine** (IOP first three values) corresponds to **column index** (pixel_x).

### 3.2 Slice direction (out-of-plane)

The direction in patient space along which **slice index** increases is **not** stored explicitly in DICOM. It is derived as the **slice normal**:

- **slice_normal** = **row_cosine × col_cosine** (cross product, right-hand rule).  
- So slice_normal is perpendicular to the image plane; moving to the “next” slice moves along this vector (by `slice_spacing` per slice index).

Thus:

- **Image row (pixel_y)** → patient direction = **col_cosine** (column direction cosines; row number varies along this direction).  
- **Image column (pixel_x)** → patient direction = **row_cosine** (row direction cosines; column number varies along this direction).  
- **Slice (out-of-plane)** → patient direction = **slice_normal**.

Which of patient ±X, ±Y, ±Z corresponds to row, column, or slice **depends on the dataset’s ImageOrientationPatient** (and thus on whether the series is axial, sagittal, coronal, or oblique).

### 3.3 Formula

```
patient_pos = ImagePositionPatient
            + pixel_y * row_spacing * col_cosine
            + pixel_x * col_spacing * row_cosine
            + slice_index * slice_spacing * slice_normal
```

So:

- **Row (pixel_y)** moves along **col_cosine** by `row_spacing` per unit.  
- **Column (pixel_x)** moves along **row_cosine** by `col_spacing` per unit.  
- **Slice (slice_index)** moves along **slice_normal** by `slice_spacing` per unit.

The result is (X, Y, Z) in **patient mm** (typically LPS or similar, depending on the DICOM convention used in the dataset).

**Why this formula:** **col_cosine** is the cosine of the column direction with the patient x, y, z unit vectors; the **column direction** (top-to-bottom in the image) corresponds to **row number** (pixel_y). **row_cosine** is the cosine of the row direction with patient axes; the **row direction** (left-to-right) corresponds to **column number** (pixel_x). Hence row index is applied with col_cosine and column index with row_cosine.

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
| **Patient (px, py, pz) mm** | `pixel_to_patient_coordinates(current_dataset, x, y, z)` using DICOM ImagePositionPatient, ImageOrientationPatient, Pixel Spacing, and slice spacing. In-plane mapping: pixel_y ↔ col_cosine, pixel_x ↔ row_cosine. |

Correctness for sagittal and coronal depends on the **dataset** and **(x, y, z)** representing the **same** image and orientation as the displayed view.

---

## References

- **RedBrick AI (Medium) – DICOM Coordinate Systems: 3D DICOM for Computer Vision Engineers (Pt. 1)**  
  https://medium.com/redbrick-ai/dicom-coordinate-systems-3d-dicom-for-computer-vision-engineers-pt-1-61341d87485f

# Pylinac ACR MRI Large — low-contrast detectability (algorithm & PDF overlays)

**Scope:** Behavior of **`pylinac.acr.ACRMRILarge`** low-contrast detectability for the **ACR MRI Large** phantom, as implemented in **pylinac 3.42.0** (the version pinned in this project’s `requirements.txt`).  
**Sources:** Installed package (`pylinac/acr.py`, `pylinac/core/roi.py`) and pylinac documentation topics [ACR Phantoms](https://pylinac.readthedocs.io/en/latest/acr.html) and [Contrast — Visibility](https://pylinac.readthedocs.io/en/latest/topics/contrast.html#visibility) (RTD “latest” tracks recent releases; confirm against your installed `pylinac.__version__`).

---

## What the test is doing

- **Slices:** Low-contrast detectability uses **phantom slices 8, 9, 10, and 11** (pylinac’s internal module offsets: **70, 80, 90, 100 mm** from the origin slice along the stack — see `MR_LOW_CONTRAST_MODULE_OFFSETS_MM` in `acr.py`).
- **Geometry:** On each slice, **10 spokes** are arranged in a circle. Spoke diameters **decrease clockwise** from **7.0 mm (spoke 1)** to **1.5 mm (spoke 10)**. Each spoke has **three low-contrast disks** at **different radial distances** from the phantom center (nominal distances **12.75, 25.50, 38.25 mm** in 3.42.0).
- **Scoring (per slice):** A spoke counts as **complete** only if **all three** of its disks are considered **visible** under pylinac’s rules. Counting **starts at spoke 1** and **stops at the first incomplete spoke**; spokes after that are **not** counted even if they would pass.
- **Total score:** `MRLowContrastMultiSliceModule.score` is the **sum** of the per-slice scores (each slice contributes **0–10**; four slices ⇒ **0–40** maximum).

This matches the narrative in the **ACR MRI** section of the pylinac ACR documentation (“Low Contrast Detectability” bullet list).

---

## Visibility algorithm (per disk ROI)

Each low-contrast disk is sampled with a **`LowContrastDiskROI`**. Pylinac separates **contrast** from **visibility**:

1. **Contrast** for the disk is computed from **median** signal in the disk ROI vs **median** in a paired **background** ROI (same spoke geometry), using the selected **low-contrast method** (default for MRI analyze: **`Weber`** — see `ACRMRILarge.analyze(..., low_contrast_method=...)`).
2. **Visibility** follows a **Rose-model-style** combination of contrast, ROI area, and noise, as documented under **Visibility** in the Contrast topic:

   - Conceptually: visibility scales contrast by a factor involving **effective area** and **noise** (std dev of the disk ROI used as a practical surrogate for detective quantum efficiency in the docs).
   - Implementation (3.42.0): `LowContrastDiskROI.visibility` calls `pylinac.core.contrast.visibility()` with the contrast algorithm, disk **radius**, and ROI **std**.

3. **Threshold pass:** `passed_visibility` is **`visibility > visibility_threshold`**, where `visibility_threshold` comes from **`low_contrast_visibility_threshold`** on **`analyze()`** (default **0.001** in 3.42.0).

---

## Sanity check on tiny ROIs (plot vs raw threshold)

Small disks can yield **unphysically large** visibility values (low std). For **MRI low-contrast plotting and the same “visible” logic used in scoring**, pylinac applies an extra rule (`MRLowContrastModule.roi_is_visible`):

- Let **max_visibility** = maximum visibility among the **three disks on spoke 1** (largest bubbles).
- Let **sanity_visibility** = **max_visibility × `low_contrast_visibility_sanity_multiplier`** (default multiplier **3**).

A disk is treated as **visible** for scoring/plot coloring only if:

- **`passed_visibility`** is true **and**
- **`visibility < sanity_visibility`**

So a disk can **fail** the combined check even if it barely exceeds the numeric threshold, if visibility is **inflated** beyond the sanity cap (guarding the smallest ROIs).

---

## PDF / figure overlays: what the circle colors mean

MRI analysis figures for each low-contrast slice are produced by the same path as other modules: **`plot_images()`** / **`save_images()`**, which **`publish_pdf()`** embeds as PNG pages. The low-contrast panels call **`MRLowContrastModule.plot_rois()`** (matplotlib) or **`plotly_rois()`** (Plotly) with identical color logic:

| Color | What it marks |
|--------|----------------|
| **Blue** | **Outer low-contrast region** — large disk outlining the detected low-contrast **area** of the phantom on that slice (`low_contrast_region`, ~**40 mm** radius nominal). |
| **Blue** | **Background ROIs** — small circles placed on **background** for each spoke (three per spoke), used as the reference for contrast/visibility. |
| **Green** | **Low-contrast disk ROIs** that count as **visible** under the **combined** rule: passed the visibility threshold **and** under the **sanity_visibility** cap (see above). |
| **Red** | **Low-contrast disk ROIs** that are **not** visible by that combined rule (below threshold **or** failed sanity). |

**Important:** This is **not** a clinical “pass/fail” against ACR accreditation limits by itself; it is pylinac’s **automated visibility model** plus the **phantom-specific** spoke-counting rule. The numeric **Low Contrast Score** in the PDF text summary is **`low_contrast_multi_slice.score`** (sum of per-slice spoke counts).

---

## Parameters you can change (`ACRMRILarge.analyze`)

In **DICOM Viewer V3**, the MRI options dialog now surfaces and persists all three
low-contrast knobs below:

- **`low_contrast_method`**
- **`low_contrast_visibility_threshold`**
- **`low_contrast_visibility_sanity_multiplier`**

These values are stored in app config (`QaPylinacConfigMixin`) and passed on
**each** `analyze()` call (see
[PYLINAC_CUSTOMIZATION_AND_EXTENSIONS.md](PYLINAC_CUSTOMIZATION_AND_EXTENSIONS.md)).

Relevant keyword arguments (3.42.0):

- **`low_contrast_method`** — Contrast equation for visibility input (default **`Weber`**). Other options are described under **Low contrast** in the Contrast topic (`Michelson`, `Ratio`, `Difference`, `RMS`, etc.).
- **`low_contrast_visibility_threshold`** — Threshold on **visibility** for `passed_visibility` (default **0.001**).
- **`low_contrast_visibility_sanity_multiplier`** — Multiplier on spoke-1 max visibility for the **sanity** cap (default **3**).

Fine-tuning of phantom localization (**`x_adjustment`**, **`y_adjustment`**, **`angle_adjustment`**, **`roi_size_factor`**, **`scaling_factor`**) also affects where the circles fall.

---

## References (pylinac 3.42.0–aligned)

- Package: `pylinac.acr` — `ACRMRILarge`, `MRLowContrastModule`, `MRLowContrastMultiSliceModule`, `analyze()`, `publish_pdf()`, `results()`.
- Package: `pylinac.core.roi` — `LowContrastDiskROI` (`visibility`, `passed_visibility`, `as_dict()` for exports).
- Docs: [ACR Phantoms — MRI analysis / Low Contrast Detectability](https://pylinac.readthedocs.io/en/latest/acr.html)  
- Docs: [Contrast — Low contrast methods & Visibility](https://pylinac.readthedocs.io/en/latest/topics/contrast.html)

---

*This note is project documentation only; authoritative physics criteria remain the ACR program materials and site protocols.*

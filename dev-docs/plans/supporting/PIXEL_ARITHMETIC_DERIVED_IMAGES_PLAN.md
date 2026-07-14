# Pixel-wise Image Arithmetic & Derived Images Plan

**Status:** Not started  
**Priority:** P1  
**TO_DO ref:** Features (Near-Term) — "Add pixel-wise image arithmetic for derived images/series"

---

## Goal

Allow users to perform **pixel-wise arithmetic** (subtraction, addition, multiplication, division) between DICOM images to produce derived images or series. Use cases include:

- **Subtraction imaging:** Post-contrast minus pre-contrast (angiography, enhancement maps).
- **Difference maps:** Compare two time points or series.
- **Normalization:** Divide by a reference image.
- **Frame-to-frame operations:** Temporal difference within a series (frame N+1 minus frame N).

Results can be viewed in the app and exported as standard image formats or derived DICOM.

---

## Phase 1 — Core arithmetic engine

### 1a. Arithmetic module

- [ ] Create `src/core/image_arithmetic.py` with:
  ```python
  def compute_image_arithmetic(
      array_a: np.ndarray,
      array_b: np.ndarray,
      operation: str,  # "subtract", "add", "multiply", "divide"
      rescale_a: tuple[float, float] | None = None,  # (slope, intercept)
      rescale_b: tuple[float, float] | None = None,
  ) -> np.ndarray:
  ```
  - Apply rescale to physical values before arithmetic (option).
  - Division: guard against divide-by-zero (output 0 or NaN, configurable).
  - Output dtype: float32 (preserve full range; display pipeline handles W/L).
  - Handle shape mismatch: raise clear error if dimensions differ.

### 1b. Pairing strategies

- [ ] Define pairing modes for series-to-series operations:
  - **By index:** Pair slice N from series A with slice N from series B (simplest).
  - **By `ImagePositionPatient`:** Match closest IPP (for series with different slice counts or spacing).
  - **By `SliceLocation`:** Match on SliceLocation tag.
  - **By temporal phase:** Match on `TemporalPositionIdentifier` or `TriggerTime` (cardiac).
- [ ] Implement `src/core/image_pairing.py`:
  ```python
  def pair_series(
      series_a: list[Dataset],
      series_b: list[Dataset],
      method: str,  # "index", "ipp", "slice_location", "temporal"
  ) -> list[tuple[Dataset, Dataset]]:
  ```
  - Return matched pairs; log/warn for unmatched slices.
  - IPP matching: project onto slice normal, find nearest within tolerance.

### 1c. Within-series frame operations

- [ ] Support "frame-to-next-frame" subtraction/addition within a single series:
  - Pair slice N with slice N+1 (or N-1).
  - Output series has one fewer slice than input.
  - Useful for temporal subtraction in dynamic series.

### 1d. Tests

- [ ] `tests/test_image_arithmetic.py`:
  - Subtract identical images → all zeros.
  - Add image to itself → doubled values.
  - Divide by zero handling.
  - Shape mismatch raises error.
  - Rescale applied correctly before arithmetic.
- [ ] `tests/test_image_pairing.py`:
  - Index pairing with equal-length series.
  - IPP pairing with different slice counts.
  - Unmatched slices logged.

---

## Phase 2 — UI: single-image operations

### 2a. Dialog

- [ ] Create **Tools → Image Arithmetic…** menu entry.
- [ ] `src/gui/dialogs/image_arithmetic_dialog.py`:
  - **Image A:** Current pane's image (default), or pick from any loaded series/slice.
  - **Image B:** Pick from any loaded series/slice (dropdown: study → series → slice).
  - **Operation:** Subtract (A−B), Add (A+B), Multiply (A×B), Divide (A÷B).
  - **Options:** Apply rescale before arithmetic (checkbox, default on for CT/PET).
  - **Preview:** Show result in a preview pane (reuse existing image display logic).
  - **Actions:** "Apply to viewer" (display as temporary derived image), "Export…" (save).

### 2b. Display in viewer

- [ ] Derived images display in the current pane with a "[Derived: A − B]" overlay label.
- [ ] W/L auto-range to the derived image's min/max (since values may be very different from source).
- [ ] Derived image is not added to the study/series tree unless explicitly saved.

---

## Phase 3 — UI: series-to-series operations

### 3a. Series arithmetic dialog

- [ ] Extend the dialog (or add a **Series Arithmetic** tab):
  - **Series A:** Pick from loaded series.
  - **Series B:** Pick from loaded series (same or different study).
  - **Pairing method:** Index / IPP / SliceLocation / Temporal (dropdown).
  - **Operation:** Same as single-image.
  - Progress bar for multi-slice operations.
- [ ] **Within-series mode:** "Frame-to-next-frame" checkbox — operates within Series A only.
- [ ] Result: a derived series displayed in a new pane or added to the navigator as "[Derived]".

### 3b. Derived series management

- [ ] Derived series get a synthetic SeriesInstanceUID and a "[Derived]" prefix in the navigator.
- [ ] Derived series are in-memory only; not saved to disk unless explicitly exported.
- [ ] Clearing data or loading a new folder removes derived series.

---

## Phase 4 — Export

- [ ] **Image export (PNG/JPG):** Reuse existing export pipeline with the derived array.
- [ ] **DICOM export:** Create derived DICOM instances using the pattern from `mpr_dicom_export.py`:
  - SOP Class: Secondary Capture (safest for derived/computed images).
  - Copy patient/study metadata from source.
  - Set `ImageType` to `["DERIVED", "SECONDARY"]`.
  - Set `DerivationDescription` to e.g. "Subtraction: SeriesA - SeriesB".
  - Store float32 → int16 with computed RescaleSlope/Intercept (same approach as MPR export).
  - Optional anonymization.
- [ ] Export as multi-file DICOM series (one file per derived slice).

---

## Phase 5 — Verification

- [ ] Manual QA: Load a CT with pre/post contrast series → subtract → verify enhancement map looks correct.
- [ ] Manual QA: Within-series frame subtraction on a dynamic series → verify temporal differences.
- [ ] Verify W/L auto-range works on derived images (values may be negative for subtraction).
- [ ] Verify DICOM export of derived series loads in an external viewer (e.g. 3D Slicer, Horos).
- [ ] Run existing tests to ensure no regression.

---

## Open questions

1. **Should derived images be saveable to the study index?** Probably not — they are computed, not original data. But the user might want to re-derive them later; consider storing the operation recipe as metadata.
2. **Registration/alignment:** This plan assumes images are spatially aligned. For cross-series subtraction where geometry differs, should we resample first? That's essentially fusion territory — defer to a follow-up or note the limitation.
3. **Color images:** Operations on RGB DICOM (US, pathology) — apply per-channel? Probably convert to grayscale first; defer color arithmetic.
4. **Performance:** For large series (500+ slices), operations should run in a background thread with progress.

---

## Files likely touched

| File | Change |
|------|--------|
| `src/core/image_arithmetic.py` | **New** — arithmetic engine |
| `src/core/image_pairing.py` | **New** — series pairing strategies |
| `src/gui/dialogs/image_arithmetic_dialog.py` | **New** — UI |
| `src/gui/main_window_menu_builder.py` | Tools menu entry |
| `src/core/export_rendering.py` | Hook derived images into export |
| `src/core/mpr_dicom_export.py` | Reuse patterns for derived DICOM |
| `src/gui/overlay_text_builder.py` | "[Derived]" overlay label |
| `tests/test_image_arithmetic.py` | **New** |
| `tests/test_image_pairing.py` | **New** |

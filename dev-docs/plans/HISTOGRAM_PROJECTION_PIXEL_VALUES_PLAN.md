# Histogram + intensity projection pixel values — **HIST_PROJ1**

**Task ID:** **HIST_PROJ1**  
**TO_DO:** `dev-docs/TO_DO.md` **L102** — *When projection is enabled, allow to show projection pixel values on histogram.*  
**Priority:** P2  
**Phasing:** milestone **M4** after **ROI_RGB1** on single-branch default (`plans/orchestration-state.md` user queue).

---

## Goal

When **intensity projection** (AIP / MIP / MinIP) is **enabled** for a **2D stack** subwindow, the **Tools → Histogram** (and per-view histogram) should optionally plot the **same projected pixel values** the viewer uses for display, instead of only the **single-slice** raw/rescaled array from the current `Dataset` instance.

---

## Current behavior (as of plan authoring)

| Component | Role |
|-----------|------|
| **`HistogramDialog`** (`src/gui/dialogs/histogram_dialog.py`) | Builds histogram from **`get_current_dataset()`** + **`get_current_slice_index()`** via **`DICOMProcessor.get_pixel_array`** / **`get_frame_pixel_array`** — **one slice / frame**, then optional rescale. **Does not** consult **`SliceDisplayManager.projection_*`**. |
| **`HistogramWidget`** (`src/tools/histogram_widget.py`) | **`np.histogram`** on **`pixel_array`** (2D or masked ROI) — agnostic to projection source. |
| **Projection state** | **`SliceDisplayManager`**: `projection_enabled`, `projection_type`, `projection_slice_count` (wired via `subwindow_manager_factory`, `projection_app_facade`). |
| **Projection math (reuse)** | **`DICOMProcessor.average_intensity_projection` / `maximum_intensity_projection` / `minimum_intensity_projection`** — already used by **`export_rendering.create_projection_for_export`** and related paths. |

**Gap:** histogram pipeline and **slice display / projection** pipeline are **disjoint**; enabling projection in the UI does not change **`HistogramDialog.update_histogram`**.

---

## Representation of “projection mode” for histogram

- **Source of truth:** per-subwindow **`SliceDisplayManager`** projection flags (same as viewer).
- **Histogram dialog** receives new optional callbacks **or** extends existing **`get_histogram_callbacks_for_subwindow`** (`src/core/subwindow_lifecycle_controller.py`) with:
  - `get_projection_enabled() -> bool`
  - `get_projection_type() -> str`
  - `get_projection_slice_count() -> int`
  - `get_study_series_ids()` (already indirectly present) + access to **series datasets list** for the same ordering as the viewer.

---

## Data path (target architecture)

1. **When projection is off:** keep existing **`HistogramDialog`** behavior (single slice + rescale).
2. **When projection is on and user selects “Projection pixels”** (see UX below):
   - Resolve **slice index** `z` and contiguous range `[z, z + count - 1]` capped by series length (match **`export_rendering`** / viewer rules).
   - Build **2D float** projection array using **shared** helper (prefer **one module** — e.g. factor `projection_pixels_from_series(...)` into `core/slice_display_pixels.py`, `dicom_processor`, or small `core/intensity_projection_pixels.py` — **`coder`** decides to avoid triplication with `export_rendering` and `SliceDisplayManager`).
   - Apply **same rescale** policy as histogram’s **raw vs rescaled** toggle.
   - Pass result to **`HistogramWidget.set_pixel_array`**.
3. **Series-wide global min/max** (`_compute_series_global_frequency_max`): either **skip** expensive all-slices projection scan in v1, or **document** O(slices²) risk — **gate with `ux`/`reviewer`**.

---

## Toggle UX (defer detail to **`ux`**)

- **Checkbox** in **`HistogramDialog`**: e.g. **“Use intensity projection pixels”**, **enabled only when** `get_projection_enabled()` is true; when disabled, revert to single-slice histogram.
- **Optional persistence:** `display_config` key `histogram_match_intensity_projection` (default **on** when projection active — product choice; default **off** is safer for behavior change — **`ux`**).

---

## Tests

- [ ] **Pure numpy / small synthetic series:** 3 slices × 2×2 distinct values → **MIP** at center index → expected histogram peak locations (unit test on helper, no Qt).
- [ ] **Integration (light):** mock callbacks feeding a known projection array into **`HistogramWidget`** (existing patterns if any).
- [ ] **Manual smoke:** enable projection in UI, open histogram, toggle checkbox — counts change vs off.

---

## Files likely touched

`src/gui/dialogs/histogram_dialog.py`, `src/core/subwindow_lifecycle_controller.py` (`get_histogram_callbacks_for_subwindow`), `src/core/slice_display_manager.py` and/or **`dicom_processor` / `slice_display_pixels` / `export_rendering`** for shared projection builder, `src/utils/config/display_config.py` if persisted, **`CHANGELOG.md`**.

---

## Checklist

- [x] **(HIST1-1)** Shared “projection pixels from series” helper + tests  
  `parallel-safe: no`, `stream: Q`, `after: ROI_RGB1` — **done** 2026-04-15 (`compute_intensity_projection_raw_array` in `slice_display_pixels.py`; pure helper test **deferred**)
- [x] **(HIST1-2)** Wire callbacks from **`SubwindowLifecycleController`** into **`HistogramDialog`** — **done** 2026-04-15
- [x] **(HIST1-3)** UI toggle + optional config persistence — **done** 2026-04-15 (`histogram_use_projection_pixels` in `display_config` / `config_manager` defaults)
- [x] **(HIST1-4)** **`CHANGELOG`** + manual smoke notes — **done** 2026-04-15 (**CHANGELOG**); manual smoke: enable projection → open histogram → toggle checkbox

---

## Questions for user / orchestrator

- [ ] Should **global histogram range** across the series precompute **projected** min/max (costly), or stay **per-slice** only when projection mode is on?

# Plan: Bit-Depth / Photometric-Aware W/L Presets and MONOCHROME1 Display

**Date:** 2026-08-15
**Status:** Draft (not started)
**Severity:** High
**Blocks:** TO_DO "Window/Level presets should depend on bit depth and photometric interpretation" (2026-08-11) and the MONOCHROME1 on-screen display bug.
**Investigation basis:** `dev-docs/bug-investigations/CR-DX-WL-PRESETS-BIT-DEPTH.md`

---

## Problem Statement

Two related display-correctness defects for non-HU (projection / secondary-capture) modalities:

1. **W/L presets are not bit-depth aware.** `src/core/wl_builtin_presets.py` hardcodes a
   12-bit raw range (`(2048, 4096)`) and, for CR/DX, embeds HU-style `is_rescaled=True`
   presets (`Chest = -600/1500`, `Bone = 300/1500`). CR/DX rarely carry `RescaleSlope`/
   `RescaleIntercept`, so the viewer runs in raw mode and the preset handler skips the
   HU→raw conversion (rescale is `None`). The HU value `-600` is then used directly as a
   raw window center against unsigned pixels (min 0) → clipped/black image. See
   investigation file for full evidence (lines 19–49 of `wl_builtin_presets.py`, handler
   no-op at `window_level_preset_handler.py:38-52`, `dicom_rescale.py:142-148`).

2. **MONOCHROME1 is not handled on screen.** The live viewer
   (`dicom_processor.dataset_to_image` → `dicom_image_render.render_grayscale_image`) never
   inverts for `MONOCHROME1`. Only the manual "Invert Image" user toggle exists
   (`image_viewer_view.py:450-507`, default `False`). Export *does* invert
   (`export_rendering.py:221-230`), creating an asymmetry where exported images honor
   MONOCHROME1 but the interactive viewer does not.

---

## Goals

- W/L presets for modalities without a standardized rescaled range (CR, DX, MG, NM, RF, XA,
  US, and `ANY` fallback) are expressed in the **dataset's actual stored raw range**, derived
  from `BitsAllocated` / `BitsStored` / `PixelRepresentation` / high-bit.
- Remove or gate the HU-style CR/DX presets so they are only offered when the dataset truly
  rescales to HU (mirroring the existing MR-HU gate).
- The on-screen viewer auto-inverts for `MONOCHROME1`, consistent with export output and PACS.
- Manual "Invert Image" toggle remains, layered on top of the dataset-driven baseline without
  double-inverting.

---

## Non-Goals

- Changing the CT/PT HU preset logic (already correct).
- Changing the rescale conversion math in `dicom_window_level.py` (correct; the data must change).
- Auto-W/L from pixel min/max (separate TO_DO item, `UX_IMPROVEMENTS_BATCH1_PLAN.md` #4).

---

## Design

### 1. Stored full-scale range helper (new)

Add `src/core/dicom_pixel_range.py` (or extend `dicom_rescale.py`):

```python
def get_stored_value_range(dataset) -> tuple[float, float]:
    """Return (stored_min, stored_max) for raw stored pixels.

    Uses BitsAllocated, BitsStored, HighBit, PixelRepresentation.
    Unsigned N-bit: 0 .. 2**bits_stored - 1.
    Signed N-bit:   -(2**(bits_stored-1)) .. 2**(bits_stored-1) - 1.
    Falls back to (0, 2**bits_allocated - 1) / signed when BitsStored missing.
    """
```

Wire into `dicom_processor.py` as a static method (mirror existing `dataset_to_image` shape).

### 2. Rewrite non-HU preset tables

In `src/core/wl_builtin_presets.py`:

- Change signatures so built-in presets can be **generated from the dataset's stored range**
  rather than hardcoded. Introduce a function `get_builtin_presets(modality, dataset=None)`
  (keep backward-compatible `modality`-only overload) that, for CR/DX/MG/NM/RF/XA/US/ANY,
  derives a "Default" / "Wide" preset from the stored range:
  - `Default`: center = midpoint, width = full range (or a percentile-trimmed width).
  - `Wide`: center = midpoint, width = full range (clamped).
- Remove `Chest`/`Bone` `is_rescaled=True` CR/DX entries. If a CR/DX genuinely carries a HU
  rescale, those presets are produced by the **HU gate** (see step 3), not hardcoded.

### 3. HU-gate CR/DX presets (like MR-HU)

In `src/core/wl_preset_catalog.py:build_preset_list`, mirror the existing
`MR_HU_PRESETS` gate (`wl_preset_catalog.py:116-117`):

```python
if modality.upper() in ("CR", "DX") and _has_usable_rescale(rescale_slope, rescale_intercept):
    builtin_tuples = list(builtin_tuples) + get_cr_dx_hu_builtin_presets()
```

Only when the dataset actually rescales (rare for CR/DX) are HU presets offered, and they will
convert correctly because `rescale_slope` is non-`None`.

### 4. MONOCHROME1 auto-inversion on screen

- Pass `photometric_interpretation` into `render_grayscale_image`
  (`dicom_image_render.py:188-219`). When `MONOCHROME1`, invert the windowed array before the
  uint8 cast (`255 - arr`, equivalent to the export step at `export_rendering.py:225`).
- Define `effective_inverted = dataset_is_monochrome1 XOR user_toggled_invert`.
  - The dataset baseline is computed in `dataset_to_image` / `slice_display_manager`.
  - The manual toggle (`image_viewer.image_inverted`) becomes an *additional* user offset.
  - Persist the combined state per series in `ViewStateManager.series_defaults`
    (`view_state_manager.py:1098-1112`) as today, but initialize it from the dataset baseline
    so MONOCHROME1 series open correctly without user action.
- Keep `invert_image` (manual) semantics: toggling flips the current effective polarity.

### 5. Menu labeling

In `wl_preset_catalog.py:storage_space_label` / `format_preset_tooltip`, CR/DX raw presets
should label as "raw" (already the case for `is_rescaled=False`), and never as "HU" unless
the HU gate applied. Confirm no CR/DX raw preset is mislabeled HU.

---

## Files to Change

| File | Change |
|------|--------|
| `src/core/dicom_pixel_range.py` (new) | Stored full-scale range helper |
| `src/core/dicom_processor.py` | Add static method; pass photometric + stored range into render |
| `src/core/dicom_image_render.py` | Invert for MONOCHROME1 in `render_grayscale_image` |
| `src/core/wl_builtin_presets.py` | Bit-depth-aware raw presets; remove hardcoded HU CR/DX; add CR/DX HU gate list |
| `src/core/wl_preset_catalog.py` | CR/DX HU gate (mirror MR-HU); ensure correct labeling |
| `src/core/window_level_preset_handler.py` | No logic change expected (already correct no-op) |
| `src/core/slice_window_level_resolver.py` | Init per-series inversion from dataset baseline (lines 59–103, 248–273) |
| `src/gui/image_viewer.py` / `image_viewer_view.py` | User toggle = offset on top of dataset baseline; avoid double-invert |
| `src/gui/view_state_manager.py` | Persist combined inversion state (lines 1098–1112) |
| Tests (below) | New + updated |

---

## Tests

- `tests/core/test_wl_builtin_presets.py`: assert CR/DX presets are `is_rescaled=False`,
  bit-depth-aware (10/12/14/16-bit, signed vs unsigned), and contain no HU-style values.
- New `tests/core/test_dicom_pixel_range.py`: stored-range math for all bit combos.
- `tests/core/test_slice_window_level_resolver.py`: update fixtures (line 155 HU `Bone` no
  longer a CR preset) and add MONOCHROME1 default-inversion case.
- New `tests/core/test_dicom_image_render_monochrome1.py`: MONOCHROME1 grayscale inversion.
- `tests/test_wl_preset_catalog.py`: CR/DX HU gate only when rescale present.
- `tests/gui/`: MONOCHROME1 + manual-toggle combined state (XOR, no double-invert).

---

## Verification

- `python -m pytest tests/core tests/gui -q`
- `python -m pytest tests/ -q` (full suite)
- `python scripts/check_architecture_boundaries.py`
- `python scripts/agent_smoke_harness.py`
- `python scripts/check_user_docs_links.py`
- Manual: load 10-bit, 12-bit, 14-bit unsigned CR/DX and a MONOCHROME1 series; confirm presets
  render anatomically sensible windows, MONOCHROME1 opens with correct polarity, export output
  matches screen, and the manual Invert toggle flips without double-inverting.

---

## Rollout / Commits

- Single feature branch `fix/wl-presets-bit-depth-monochrome1`.
- Commit 1: stored-range helper + tests.
- Commit 2: bit-depth-aware presets + HU gate.
- Commit 3: MONOCHROME1 on-screen inversion + combined-toggle state.
- Commit 4: docs (link TO_DO, update investigation file status).

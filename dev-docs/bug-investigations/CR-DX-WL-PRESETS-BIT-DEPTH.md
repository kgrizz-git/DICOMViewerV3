# Bug Investigation: CR/DX (and other non-HU) Window/Level Presets Are Not Bit-Depth Aware

**Date:** 2026-08-15T22-58-22
**Investigator:** Kilo
**Repository:** kgrizz-git/DICOMViewerV3
**Severity:** High (visual correctness — presets produce wrong/invalid display for CR, DX, MG, NM, RF, XA, US and any modality without HU rescale)
**Status:** Implemented 2026-08-16. See [completed plan](../plans/completed/WL_PRESETS_BIT_DEPTH_AND_MONOCHROME1_PLAN.md). MONOCHROME1 inversion moved from export (`export_rendering.process_image_by_photometric_interpretation`) to core render (`core.dicom_image_render.render_grayscale_image`).

---

## Executive Summary

The built-in window/level (W/L) presets in `src/core/wl_builtin_presets.py` define
values for projection/secondary-capture modalities (CR, DX, MG, NM, RF, XA, US) that
assume a fixed 12-bit raw stored range (`(2048, 4096)` default) and, for CR/DX
specifically, embed **HU-style rescaled values** (`Chest = -600/1500`, `Bone = 300/1500`)
with `is_rescaled=True`.

Two defects follow from this, exactly as the user suspected:

1. **No bit-depth awareness.** Stored pixel range depends on `BitsAllocated`/`BitsStored`
   (10-, 12-, 14-, 16-bit) and `PixelRepresentation` (signed vs unsigned). The presets
   hardcode one 12-bit range and never read the dataset's actual bit depth, so the raw
   presets are wrong for 10-bit (0–1023), 14-bit, or 16-bit CR/DX, and for signed data.

2. **HU-style `is_rescaled=True` CR/DX presets are applied as raw values.** CR/DX almost
   never carry `RescaleSlope`/`RescaleIntercept` (unlike CT). With no rescale, the viewer
   runs in raw mode and the preset handler **skips the raw↔rescaled conversion**, so a
   HU value like `-600` is used directly as a raw window center — impossible for unsigned
   CR/DX (typical minimum 0). The result is a fully clipped / black image, not a chest view.

The fix direction: modality presets for non-HU modalities must be expressed in the
dataset's **actual stored raw range**, derived from `BitsAllocated`/`BitsStored`/
`PixelRepresentation`/`PhotometricInterpretation`, not a hardcoded 12-bit constant and not
HU values. MONOCHROME1 (inverted) also needs handling.

---

## Evidence and File/Line References

### 1. Built-in preset tables (root of the defect)

**File:** `src/core/wl_builtin_presets.py`

- Lines 45–49 — CR table:
  ```python
  "CR": [
      (-600.0, 1500.0, True, "Chest"),       # is_rescaled=True HU values
      (300.0, 1500.0, True, "Bone"),         # is_rescaled=True HU values
      (2048.0, 4096.0, False, _PRESET_DEFAULT_RAW),  # hardcoded 12-bit raw
  ],
  ```
- Lines 50–54 — DX table: same pattern (`Chest`/`Bone` as `is_rescaled=True`, plus a
  hardcoded `(2048, 4096, False)` raw default).
- Lines 55–57 — MG: `(2048.0, 4096.0, False, "Default")` (hardcoded 12-bit).
- Lines 58–61 — NM: `(500, 1000, True)` + `(128, 256, False)` raw default.
- Lines 62–64 — US: `(128, 256, False, "Default")`.
- Lines 65–70 — RF / XA: `(2048, 4096, False)` raw.
- Lines 71–74 — ANY fallback: `(128, 256, False)` and `(512, 1024, False)` — also assumes a
  fixed small range.
- Lines 33–34 — comment admits the raw MR defaults are "12-bit-style" but applies the same
  hardcoded-range thinking to projection modalities.

Every `2048/4096` tuple encodes the implicit assumption "stored pixels span 0–4095"
(i.e. 12-bit unsigned). That is not true for 10-bit (0–1023), 14-bit, or signed data.

None of these presets consult `BitsAllocated`, `BitsStored`, `PixelRepresentation`, or
`PhotometricInterpretation` — there is no bit-depth input to `get_builtin_presets`
(lines 87–99), which only takes a `modality` string.

### 2. CR/DX typically have NO rescale → viewer runs raw → HU presets not converted

**File:** `src/core/dicom_rescale.py`

- Lines 142–148 — `infer_rescale_type` only infers `"HU"` for `Modality == "CT"` when both
  slope and intercept are present. CR/DX are not special-cased, confirming the viewer does
  not assume HU for them.
- Lines 54–115 — `get_rescale_parameters` returns `(None, None, None)` for CR/DX that omit
  `RescaleSlope`/`RescaleIntercept` (the common case).

**File:** `src/core/slice_window_level_resolver.py`

- Line 50 — `_init_new_series_state`:
  ```python
  use_rescaled = rescale_slope is not None and rescale_intercept is not None
  ```
  For CR/DX without rescale → `use_rescaled_values = False`. Viewer is in **raw** mode.

**File:** `src/core/window_level_preset_handler.py`

- Lines 38–52 — `apply_window_level_preset`:
  ```python
  if is_rescaled and not use_rescaled_values:
      if (
          rescale_slope is not None
          and rescale_intercept is not None
          and rescale_slope != 0.0
      ):
          wc, ww = app.dicom_processor.convert_window_level_rescaled_to_raw(...)
  ```
  Since CR/DX rescale_slope is `None`, the `if` is **false** and the conversion is
  **skipped**. The HU-style `wc=-600, ww=1500` is passed straight through unchanged.

**File:** `src/core/dicom_window_level.py`

- Lines 109–116 — `convert_window_level_rescaled_to_raw` would normally map HU→raw, but it
  is never reached for CR/DX (see above).
- Lines 48–69 — `apply_window_level` applies the window directly against the raw pixel
  array (`arr = pixel_array.astype(np.float64)`) with **no** rescale when slope/intercept
  are `None`. So a raw window center of `-600` with pixel minimum 0 yields `window_min=-1350`,
  `window_max=150` → for typical CR pixels (all ≥ 0) almost everything is above `window_max`
  and clips to white/black, and for MONOCHROME1 the polarity inverts. Either way: not a
  usable chest view.

**Net effect:** selecting "CR → Chest" on a real CR image produces a clipped/invalid image
because `-600` is interpreted as a raw stored value, which is meaningless for unsigned CR.

### 3. The raw default also ignores actual bit depth and signedness

**File:** `src/core/wl_builtin_presets.py` lines 48, 53, 56, 66, 69 — `2048/4096`.

Even the "correct" raw fallback is wrong when:
- `BitsAllocated=16, BitsStored=10` (0–1023) → preset center 2048 is beyond the data range.
- `PixelRepresentation=1` (signed, e.g. some NM/secondary capture) → range is
  `[-32768, 32767]` (or `[-512, 511]` for 10-bit signed), not `0–4095`.

No code path computes the *actual* full-scale range from the dataset. The auto-range
fallbacks elsewhere (e.g. `slice_window_level_resolver._compute_wl_from_series_pixel_range`,
lines 139–170, and `_compute_wl_from_single_slice`, lines 173–211) **do** derive W/L from
the real pixel min/max — but the *presets* bypass that and use the hardcoded constants.

### 4. MONOCHROME1 vs MONOCHROME2 is not considered by presets

**File:** `src/core/dicom_color.py`

- Lines 66–90, 102–120 — `is_color_image` / photometric helpers read
  `PhotometricInterpretation` (`MONOCHROME1` vs `MONOCHROME2`) but only to detect color.
- MONOCHROME1 means stored values are **inverted** (higher stored value = darker). A window
  center expressed for MONOCHROME2 is visually reversed on a MONOCHROME1 image. The preset
  system (`wl_builtin_presets.py`, `wl_preset_catalog.py`, `window_level_preset_handler.py`)
  never reads `PhotometricInterpretation`, so a "Bone" preset on a MONOCHROME1 CR would look
  inversely rendered. This is the "monochromatic1 vs 2" concern raised by the user.

### 5. How presets are consumed (confirms the bad values reach rendering)

**File:** `src/core/slice_window_level_resolver.py`

- Lines 59–103 — `_build_presets_and_extract_wl` builds the merged list and (line 87)
  sets `current_preset_index = 0`, so the **first** preset in the merged list becomes the
  default applied W/L. For CR, the first built-in is `Chest (-600, 1500, is_rescaled=True)`
  (DICOM presets are prepended in `wl_preset_catalog.build_preset_list`, lines 102–112, only
  if the dataset carries `WindowCenter`/`WindowWidth`). With no DICOM W/L tags, the built-in
  `Chest` is the default and is applied via the handler at series load — i.e. a CR with no
  embedded W/L opens clipped.

**File:** `src/core/wl_preset_catalog.py`

- Lines 79–138 — `build_preset_list` merges DICOM + builtin + user. Built-in CR/DX presets
  (including the bad HU ones) flow straight into `ViewStateManager.window_level_presets`
  (via `presets_to_legacy`, line 46–48) with their `is_rescaled` flag intact.
- Lines 153–163 — `storage_space_label` will label `is_rescaled=True` CR presets as "HU"
  (or the dataset rescale type) in the menu, which is misleading because CR isn't in HU.

### 6. Tests encode the current (defective) assumption

**File:** `tests/core/test_wl_builtin_presets.py`

- Lines 16–25 — assert all CT presets `is_rescaled=True` and all MR presets `is_rescaled=False`.
- There is **no** test asserting CR/DX presets are raw-range-correct or bit-depth-aware;
  the CR/DX entries are only validated for tuple shape (lines 64–72), not correctness.

**File:** `tests/core/test_slice_window_level_resolver.py` line 155 — test fixture uses
`(300.0, 1500.0, True, "Bone")` as a CT-style preset, reinforcing the HU assumption.

---

## Reproduction (conceptual)

1. Load a CR or DX image where `BitsAllocated=16, BitsStored=10..14`, `PixelRepresentation=0`
   (unsigned), and **no** `RescaleSlope`/`RescaleIntercept` (typical for projection radiographs).
2. Open the context menu → Window/Level Presets → "Chest" (or note it is auto-applied as the
   default since it is `current_preset_index=0`).
3. Observe: image is fully clipped (e.g. all white/black) because window center `-600` is
   applied against raw pixels whose minimum is 0.
4. Observe "Bone" → window center `300`, width `1500` is a *CT-HU* bone window, also wrong for
   the raw stored range (e.g. 0–1023 for 10-bit), so it crushes most soft tissue.

---

## Root Cause (one sentence)

`wl_builtin_presets.py` hardcodes modality W/L presets using a single 12-bit raw range and
CT-HU values for CR/DX, with no dependency on the dataset's actual `BitsAllocated`/
`BitsStored`/`PixelRepresentation`/`PhotometricInterpretation` or on whether a rescale to HU
actually exists — and the preset handler safely no-ops the HU→raw conversion when rescale is
absent, leaving the HU numbers applied directly as raw stored values.

---

## Recommended Fix Direction (not yet implemented)

1. **Compute the actual stored full-scale range per dataset** from
   `BitsAllocated`, `BitsStored`, `PixelRepresentation`, and high-bit (see
   `src/core/dicom_loader_file.py:172` for existing `BitsAllocated` access). Provide a helper
   returning `(stored_min, stored_max)` for raw mode and the rescaled range when slope/
   intercept exist.
2. **Express non-HU modality presets in raw stored units**, derived from that range (e.g. a
   "Default" CR preset of `(mid, full_range)`), instead of hardcoded `2048/4096`.
3. **Remove the HU-style `Chest`/`Bone` `is_rescaled=True` entries from CR/DX** (or only offer
   them when the dataset genuinely carries a HU rescale, mirroring the existing MR-HU gate at
   `wl_preset_catalog.py:116-117` / `wl_builtin_presets.py:77-82`).
4. **Account for MONOCHROME1** when assembling/auto-applying presets so inverted displays don't
   look reversed (store-flag or invert the default window).
5. **Update tests** (`tests/core/test_wl_builtin_presets.py`,
   `tests/core/test_slice_window_level_resolver.py`) to assert bit-depth-aware, raw-correct
   CR/DX defaults.

---

## Files to Touch for the Fix

- `src/core/wl_builtin_presets.py` (preset values + add bit-depth/photometric inputs)
- `src/core/wl_preset_catalog.py` (pass dataset bit depth / photometric into preset build)
- `src/core/dicom_rescale.py` or a new `dicom_pixel_range.py` helper (stored full-scale range)
- `src/core/window_level_preset_handler.py` (already correct; conversion correctly no-ops when
  no rescale — the data, not the handler, must change)
- `src/core/slice_window_level_resolver.py` (default-preset selection, lines 59–103)
- `tests/core/test_wl_builtin_presets.py`, `tests/core/test_slice_window_level_resolver.py`

---

## Addendum: Is MONOCHROME1 vs MONOCHROME2 handled elsewhere (in display)?

No. MONOCHROME1 inversion is handled only for **image export**, NOT for the live on-screen
viewer. This is a **separate, larger display-correctness bug** (independent of the preset
bug above), and it compounds the CR/DX problem: a MONOCHROME1 CR would render with reversed
brightness in the viewer, and a manually "Invert Image" toggle would be needed by the user
to match PACS.

### Evidence

**On-screen render path does NOT invert for MONOCHROME1.**

- `src/core/dicom_processor.py:171-233` — `dataset_to_image` is the on-screen conversion entry
  point (called from `src/gui/slice_display_manager.py:536`). It reads photometric
  interpretation only for PALETTE/YBR/RGB color handling (`dicom_processor.py:206-229`). For
  grayscale it calls `render_grayscale_image` (line 231) with **no** MONOCHROME1 branch.
- `src/core/dicom_image_render.py:188-219` — `render_grayscale_image` applies window/level
  (`apply_window_level`) or normalizes, then `Image.fromarray(..., mode='L')`. No inversion
  for MONOCHROME1 anywhere.
- `src/core/dicom_color.py:90` — `is_color_image` recognizes `MONOCHROME1`/`MONOCHROME2` only
  to classify them as **grayscale** (not color); it does not signal inversion.

**On-screen inversion is purely a manual user toggle, never auto-derived from the dataset.**

- `src/gui/image_viewer.py:180` — `self.image_inverted = False` default.
- `src/gui/image_viewer_view.py:450-507` — `set_image` only inverts when `apply_inversion` is
  set; when no stored series state exists it explicitly resets to `False`
  (`image_viewer_view.py:477`). The stored inversion state (`ViewStateManager.series_defaults
  ['image_inverted']`, `view_state_manager.py:1098-1112`) is only ever written by the user's
  "Invert Image" action (`image_viewer_context_menu.py:665-668`, `keyboard_event_handler.py
  :70,328-331`). Nothing reads `PhotometricInterpretation == 'MONOCHROME1'` to set it.
- `src/gui/slice_window_level_resolver.py:271,469` — only persists the *current*
  `mgr.image_viewer.image_inverted` into series defaults; does not initialize inversion from
  the dataset.

**Export DOES handle MONOCHROME1 correctly (proves the viewer is missing it).**

- `src/gui/export_rendering.py:187-235` — `process_image_by_photometric_interpretation`
  inverts for MONOCHROME1 via `img_array = 255 - img_array` (lines 221-230).
- `src/gui/export_manager.py:590` — references "MONOCHROME1 inversion" in export.

So there is an asymmetry: exported images honor MONOCHROME1, but the interactive viewer does
not. A MONOCHROME1 study (e.g. many dental/cephalometric and some CR/MG acquisitions) appears
reversed on screen relative to every PACS and relative to the app's own export output.

### Recommended fix direction (display bug, separate from presets)

Auto-derive inversion from `PhotometricInterpretation` in the on-screen path:
- In `dataset_to_image` / `render_grayscale_image`, pass `photometric_interpretation` and
  invert when `MONOCHROME1` (equivalently `255 - windowed_array`, i.e. invert **before** the
  uint8 cast or via the existing `_apply_inversion` PIL step). Keep the manual user toggle as
  an additional "user invert" layered on top of the dataset-driven baseline, and persist the
  combined state per series as today.
- Be careful that the manual toggle and the dataset baseline don't double-invert; the cleanest
  model is: `effective_inverted = dataset_is_monochrome1 XOR user_toggled_invert`.

---

## Verification Steps After Fix

- `python -m pytest tests/core -q` (and `tests/test_wl_preset_catalog.py`,
  `tests/test_window_level_preset_handler.py`)
- Manual: load 10-bit, 12-bit, 14-bit unsigned CR/DX and a MONOCHROME1 series; confirm presets
  render anatomically sensible windows and the auto-applied default is within the data range.
- `python scripts/check_architecture_boundaries.py` and `python scripts/agent_smoke_harness.py`.

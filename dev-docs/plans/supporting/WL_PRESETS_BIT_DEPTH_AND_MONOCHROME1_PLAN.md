# Plan: Bit-Depth / Photometric-Aware W/L Presets and MONOCHROME1 Display

**Date:** 2026-08-15 · **Status:** Ready to implement · **Severity:** High
**Branch:** `fix/wl-presets-bit-depth-monochrome1`
**Investigation basis:** `dev-docs/bug-investigations/CR-DX-WL-PRESETS-BIT-DEPTH.md`
**TO_DO items:** "Window/Level presets should depend on bit depth and photometric interpretation" (2026-08-11); "MONOCHROME1 not handled in on-screen viewer" (2026-08-15); MPR/projection MONOCHROME1 follow-up (this plan §Follow-up).

---

## TL;DR (read this first)

Two unrelated display bugs for non-HU modalities (CR, DX, MG, NM, RF, XA, US, and `ANY`):

1. **Presets are not bit-depth aware.** Presets hardcode a 12-bit range and CR/DX embeds HU values
   (`Chest -600/1500`, `Bone 300/1500`) that the handler never converts (no rescale on CR/DX) →
   clipped/black image. Fix: derive presets from the dataset's real stored range; gate HU presets
   behind a real rescale.
2. **MONOCHROME1 not inverted on screen.** Export inverts MONOCHROME1; the live viewer does not.
   Fix: invert in the core render layer, keep the manual toggle as a user-only offset (XOR), and
   stop export/cine from double-inverting.

This plan is split into **Workstream 1 (presets)** and **Workstream 2 (MONOCHROME1)**, each with its
own phases, tests, and DoD. Implement them in order; Workstream 2's export change MUST ship in the
same commit as its render change (see Invariant #3).

---

## Invariants — do not violate (the easy ways to break this)

1. **Core inverts the dataset baseline; the view layer persists ONLY the user toggle.** The persisted
   `image_inverted` is the *user* half, never the combined effective polarity. (Prevents double-inversion.)
2. **Invert on the finalized `uint8` array** (`arr = arr.astype(uint8); arr = 255 - arr`), matching
   `export_rendering.py:221-230` exactly. Both `apply_window_level` and `normalize_to_uint8` already
   return `uint8`, so this is byte-identical to export.
3. **Export/cine must NOT re-invert MONOCHROME1 once core owns it** — remove the MONOCHROME1 branch in
   `process_image_by_photometric_interpretation` (keep YBR/RGB/PALETTE) in the **same commit** as the
   render change, or exports/cine regress to wrong polarity.
4. **No new pixel scans on the hot path.** The stored-range helper reads only tags (`BitsAllocated`/
   `BitsStored`/`HighBit`/`PixelRepresentation`).
5. **No `is_rescaled=True` preset without a real rescale.** CT/PT use rescale (correct); CR/DX/NM only
   get rescaled presets when `_has_usable_rescale` is true.

---

## Scope

**In scope:** single-slice on-screen viewer; built-in preset generation for CR/DX/MG/NM/RF/XA/US/ANY;
export still + cine polarity for MONOCHROME1.

**Out of scope (explicit follow-up, TO_DO linked):** MPR panes (`mpr_view_math.array_to_pil`) and
on-screen projection panes (`slice_display_pixels.create_slice_projection_pil_image`) — they bypass
`render_grayscale_image`, so the core-routed inversion does not reach them. CT/PT presets (already
correct). MR raw presets (hardcoded but `is_rescaled=False`; not broken the same way — follow-up).
Auto-W/L from pixel min/max (separate TO_DO, `UX_IMPROVEMENTS_BATCH1_PLAN.md` #4). The rescale math in
`dicom_window_level.py` (correct; the *data* must change, not the math).

---

## Workstream 1 — Bit-depth-aware W/L presets

### W1.1 Stored full-scale range helper (new file `src/core/dicom_pixel_range.py`)

```python
def get_stored_value_range(dataset) -> tuple[float, float]:
    """(stored_min, stored_max) for raw stored pixels. Tag-only (no pixel scan).

    Rules:
    - BitsStored authoritative; HighBit used ONLY for validation (warn if != BitsStored-1).
    - PixelRepresentation == 1 => signed, else unsigned.
    - Unsigned N-bit: 0 .. 2**bits_stored - 1.
    - Signed   N-bit: -(2**(bits_stored-1)) .. 2**(bits_stored-1) - 1.
    - Missing/zero/invalid BitsStored -> fall back to BitsAllocated (clamped >=1).
    - BitsStored > BitsAllocated (malformed) -> clamp BitsStored = BitsAllocated.
    - Guarantee stored_max > stored_min (never 0-width): if equal, stored_max += 1.
    """
```

Expose as a `DICOMProcessor` static method (mirror `dataset_to_image`).

### W1.2 Rewrite non-HU preset tables (`src/core/wl_builtin_presets.py`)

- Add `get_builtin_presets(modality, dataset=None)` (keep the `modality`-only overload for callers).
  For CR/DX/MG/NM/RF/XA/US/ANY, generate from `get_stored_value_range`:
  - `Default`: center = midpoint, width = **full stored range**.
  - `Wide`: center = midpoint, width = full range **extended 25% each side** (so it straddles the
    data; never equal to `Default`'s (center, width)).
- Remove CR/DX `Chest`/`Bone` `is_rescaled=True` entries.
- NM (`wl_builtin_presets.py:59` `(500,1000,True,"Default")`): if `_has_usable_rescale` → gate a
  generic **"rescaled Default"** (`is_rescaled=True`); else replace with the bit-depth-aware raw
  `Default` (`is_rescaled=False`). NM's raw `(128,256,False)` fallback stays but is also derived from
  the stored range.

### W1.3 HU-gate CR/DX (`src/core/wl_preset_catalog.py:build_preset_list`)

Mirror the existing `MR_HU_PRESETS` gate (`wl_preset_catalog.py:116-117`):

```python
if modality.upper() in ("CR", "DX") and _has_usable_rescale(rescale_slope, rescale_intercept):
    builtin_tuples = list(builtin_tuples) + get_cr_dx_hu_builtin_presets()
```

HU presets only appear when a real rescale exists, so they convert correctly (`rescale_slope` non-`None`).

### W1.4 Menu labeling (`src/core/wl_preset_catalog.py:storage_space_label` / `format_preset_tooltip`)

Raw non-HU presets label as "raw" (already true for `is_rescaled=False`); never label "HU" unless the
HU gate applied.

---

## Workstream 2 — MONOCHROME1 on-screen inversion

### W2.1 Invert in core render (`src/core/dicom_image_render.py:render_grayscale_image`)

Pass `photometric_interpretation`; when `MONOCHROME1`, after WL/normalize and the `uint8` cast, do
`arr = 255 - arr` (Invariant #2). Core must NOT read persisted `image_inverted`.

### W2.2 XOR ownership (Invariant #1)

```
effective_inverted = dataset_is_monochrome1 XOR user_toggled_invert
```
- Core layer owns the **dataset baseline** (inverts iff `MONOCHROME1`).
- View layer (`image_viewer_view._apply_inversion` / `set_image`) owns ONLY the **user toggle** half.
  `image_viewer.image_inverted` and `ViewStateManager.series_defaults['image_inverted']`
  (`view_state_manager.py:1081-1112`) persist the *user* half (default `False`).

### W2.3 Stop export/cine double-inversion (SAME COMMIT as W2.1 — Invariant #3)

- `src/gui/export_rendering.py`: drop the MONOCHROME1 branch in
  `process_image_by_photometric_interpretation` (keep YBR/RGB/PALETTE).
- `src/gui/export_manager.py:593` and `src/gui/cine_video_export.py:235`: no longer re-invert
  MONOCHROME1 (the guard `if not is_projection_image` stays; single-slice paths now rely on core).

### W2.4 Persisted-state migration (`src/gui/view_state_manager.py`)

Add a `schema_version` key to `series_defaults` (absence = pre-scheme). Rule:
- **MONOCHROME2:** honor stored user half as-is (incl. pre-scheme `True`).
- **MONOCHROME1:** discard pre-scheme stored value, start user half `False` (baseline auto-inverts).
  Rationale: pre-upgrade a user could only "fix" MONOCHROME1 by pressing Invert (`True`); restoring
  that under the new XOR would yield effective **un-inverted** (wrong).
- Post-scheme: restore user half normally for both PI values.

### W2.5 UX details

- Context-menu check (`image_viewer_context_menu.py:667`) reflects the **user offset**; add a
  status-bar/tooltip note that a MONOCHROME1 image is shown inverted by modality.
- `invert_image` still toggles the user half; effective polarity is the XOR.

---

## Files to Change

| File | Workstream | Change |
|------|-----------|--------|
| `src/core/dicom_pixel_range.py` (new) | W1 | Stored full-scale range helper (W1.1) |
| `src/core/dicom_processor.py` | W1 | Static method wrapping the helper |
| `src/core/wl_builtin_presets.py` | W1 | Bit-depth-aware presets; remove CR/DX HU; NM resolved (W1.2) |
| `src/core/wl_preset_catalog.py` | W1 | CR/DX HU gate; labeling (W1.3, W1.4) |
| `src/core/window_level_preset_handler.py` | — | No change (correct no-op) |
| `src/core/dicom_image_render.py` | W2 | MONOCHROME1 invert in `render_grayscale_image` (W2.1) |
| `src/gui/image_viewer.py` / `image_viewer_view.py` | W2 | User toggle = offset; no double-invert (W2.2) |
| `src/gui/view_state_manager.py` | W2 | Persist user half; `schema_version` key (W2.4) |
| `src/gui/export_rendering.py` | W2 | Drop MONOCHROME1 branch (keep YBR/RGB/PALETTE) (W2.3) |
| `src/gui/export_manager.py` | W2 | No re-invert MONOCHROME1 (W2.3) |
| `src/gui/cine_video_export.py` | W2 | No re-invert MONOCHROME1 (W2.3) |
| `src/core/slice_window_level_resolver.py` | W2 | Init per-series inversion from dataset baseline |

---

## Implementation Task List (check off as done)

**Workstream 1**
- [ ] W1.1 `get_stored_value_range` + `DICOMProcessor` static method
- [ ] W1.2 `get_builtin_presets(modality, dataset=None)`; `Default`/`Wide` from stored range; remove CR/DX `Chest`/`Bone`; NM resolved
- [ ] W1.3 CR/DX HU gate in `build_preset_list`
- [ ] W1.4 labeling correct (raw vs HU)

**Workstream 2** (W2.1 + W2.3 in ONE commit)
- [ ] W2.1 MONOCHROME1 invert in `render_grayscale_image` (cast-then-invert)
- [ ] W2.3 remove MONOCHROME1 branch in `export_rendering` + stop re-invert in `export_manager`/`cine_video_export`
- [ ] W2.2 view layer persists user half only; `set_image` applies only user offset
- [ ] W2.4 `schema_version` migration (MONOCHROME1 discards pre-scheme stored value)
- [ ] W2.5 context-menu reflects user half + status-bar note

**Tests** (see matrix below)
- [ ] `test_dicom_pixel_range` (W1.1)
- [ ] `test_wl_builtin_presets` + `test_wl_preset_catalog` (W1.2/W1.3)
- [ ] `test_dicom_image_render_monochrome1` (W2.1, signed + unsigned)
- [ ] GUI XOR / no-double-invert + migration (W2.2/W2.4)
- [ ] `test_export_monochrome1` still + cine polarity == screen (W2.3)
- [ ] duplicate-preset guard (`Wide` ≠ `Default`)
- [ ] `test_slice_window_level_resolver` (`current_preset_index=0` CR/DX in range; MONOCHROME1 default)

---

## Test Matrix (acceptance-linked)

| Area | Test | Asserts |
|------|------|---------|
| W1 helper | `tests/core/test_dicom_pixel_range.py` | 10/12/14/16-bit signed/unsigned + malformed tags (BitsStored=0, HighBit missing, BitsStored>BitsAllocated) → clamped, non-zero-width |
| W1 presets | `tests/core/test_wl_builtin_presets.py` | CR/DX `is_rescaled=False`, bit-depth-aware, no HU-style values; NM resolved |
| W1 gate | `tests/test_wl_preset_catalog.py` | CR/DX HU presets only when rescale present; no `is_rescaled=True` without rescale |
| W1 default | `tests/core/test_slice_window_level_resolver.py` | `current_preset_index=0` CR/DX preset `is_rescaled=False` & within stored range; MONOCHROME1 default-inversion case |
| W1 dup | generated-menu guard | no two presets share identical `(center, width)` (`Wide` ≠ `Default`) |
| W2 render | `tests/core/test_dicom_image_render_monochrome1.py` | unsigned + signed MONOCHROME1; output == `255 - export_render(MONOCHROME2)` (byte-identical to export) |
| W2 xor | `tests/gui/` | MONOCHROME1 + user `False` inverted once (core only); restored `image_inverted` is user half, not combined |
| W2 export | `tests/gui/test_export_monochrome1.py` | MONOCHROME1 still + cine frame polarity == on-screen slice (guards double-invert) |
| W2 migrate | `tests/gui/` | MONOCHROME1 pre-scheme `True` → user half `False`; MONOCHROME2 `True` kept |

**Explicitly NOT covered (follow-up):** MPR/projection-pane MONOCHROME1 (paths bypass core render).

---

## Verification (run all before merge)

```
python -m pytest tests/core tests/gui -q
python -m pytest tests/ -q
python scripts/check_architecture_boundaries.py
python scripts/agent_smoke_harness.py
python scripts/check_user_docs_links.py
```
Manual: load 10/12/14-bit unsigned CR/DX and a MONOCHROME1 series; confirm presets render sensible
windows, MONOCHROME1 opens correct polarity, export (still + cine) matches screen, signed
MONOCHROME1 renders correctly, and the manual Invert toggle flips without double-inverting.

### Definition of Done

- All targeted + full-suite tests green; `check_architecture_boundaries`, `agent_smoke_harness`,
  `check_user_docs_links` pass; debug flags `False` (`src/utils/debug_flags.py`).
- MONOCHROME1 polarity consistent across slice, still export, cine export (MPR/projection declared
  non-goal). No double-inversion (core baseline + user-half-only persistence + export branch removed).
- No duplicate preset (center, width). Migration tested. CHANGELOG/version bump if warranted;
  TO_DO updated (incl. MPR/projection follow-up); migration documented.

---

## Risk / Rollback

- **Highest:** export/cine double-inversion if W2.3 lags W2.1 → ship together; regression test asserts
  screen == export/cine uint8 for MONOCHROME1.
- **Behavior change:** removing CR/DX `Chest`/`Bone` changes the default applied W/L for existing CR/DX
  (intended) — note in release notes.
- **MPR/projection:** known asymmetry, explicit follow-up (TO_DO linked) — not accidental.
- **Rollback:** each workstream is its own commit on the branch; revert a commit if a gate fails.
  Migration is forward-only (baseline re-derived per load, safe to leave).

---

## Follow-up (out of scope, TO_DO linked)

MPR pane (`mpr_view_math.array_to_pil`) and on-screen projection pane
(`slice_display_pixels.create_slice_projection_pil_image`) MONOCHROME1 inversion: extend those paths
(and the export-projection path) so polarity matches the corrected slice view.

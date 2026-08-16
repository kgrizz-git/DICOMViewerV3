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

    Resolution rules (robust to malformed/missing tags):
    - `BitsStored` is AUTHORITATIVE for the value width; `HighBit` is used ONLY for
      validation (warn if HighBit != BitsStored-1), never as the range source.
    - `PixelRepresentation` 1 => signed, else unsigned.
    - Unsigned N-bit: 0 .. 2**bits_stored - 1.
    - Signed   N-bit: -(2**(bits_stored-1)) .. 2**(bits_stored-1) - 1.
    - Missing/zero/invalid BitsStored: fall back to BitsAllocated (clamped to >=1).
    - If BitsStored > BitsAllocated (malformed): clamp BitsStored = BitsAllocated.
    - Guarantee stored_max > stored_min (never a 0-width range): if equal, max += 1.
    """
```

Wire into `dicom_processor.py` as a static method (mirror existing `dataset_to_image` shape).
The helper reads **only tags** (no pixel scan) so it is safe on the hot path.

### 2. Rewrite non-HU preset tables

In `src/core/wl_builtin_presets.py`:

- Change signatures so built-in presets can be **generated from the dataset's stored range**
  rather than hardcoded. Introduce a function `get_builtin_presets(modality, dataset=None)`
  (keep backward-compatible `modality`-only overload) that, for CR/DX/MG/NM/RF/XA/US/ANY,
  derives a "Default" / "Wide" preset from the stored range returned by `get_stored_value_range`
  (§1):
  - `Default`: center = midpoint, width = **full stored range** (tag-derived, deterministic).
  - `Wide`: center = midpoint, width = full stored range **extended by 25% on each side** (so it
    straddles and exceeds the data range — visibly distinct from `Default`, which is exactly the
    full range). Never duplicate `Default`'s (center, width). A DoD test asserts no two generated
    menu presets share identical (center, width).
  - **No percentile-trimmed width in this change.** Trimming needs pixel data / a per-series
    scan, which contradicts the tag-only helper and duplicates
    `_compute_wl_from_series_pixel_range`. Percentile/auto-W/L belongs with the separate auto-W/L
    TO_DO item (`UX_IMPROVEMENTS_BATCH1_PLAN.md` #4), not this preset fix.
- Remove `Chest`/`Bone` `is_rescaled=True` CR/DX entries. If a CR/DX genuinely carries a HU
  rescale, those presets are produced by the **HU gate** (see §3), not hardcoded.
- **MR scope (was silent — now explicit):** MR raw defaults (`wl_builtin_presets.py:33-40`) are
  also hardcoded numbers with no bit-depth basis. Bringing them into the tag-derived model is
  **out of scope for this change** (MR is already `is_rescaled=False` and not broken in the same
  way as CR/DX); track as a follow-up. CT/PT remain untouched (correct HU logic). This scoping is
  deliberate, not implied.

### 3. HU-gate CR/DX presets (like MR-HU)

In `src/core/wl_preset_catalog.py:build_preset_list`, mirror the existing
`MR_HU_PRESETS` gate (`wl_preset_catalog.py:116-117`):

```python
if modality.upper() in ("CR", "DX") and _has_usable_rescale(rescale_slope, rescale_intercept):
    builtin_tuples = list(builtin_tuples) + get_cr_dx_hu_builtin_presets()
```

Only when the dataset actually rescales (rare for CR/DX) are HU presets offered, and they will
convert correctly because `rescale_slope` is non-`None`.

### 3b. Resolve NM preset (same latent bug as CR/DX)

`wl_builtin_presets.py:59` has `(500.0, 1000.0, True, "Default")` — an `is_rescaled=True` entry
with no unit and no gate. NM *can* carry an SUV-like rescale, so treat it exactly like CR/DX:

- Gate NM on `_has_usable_rescale` **only** (consistent with MR/CR/DX — do NOT introduce a
  separate "RescaleType meaningful" predicate; no preset code reads `RescaleType` today and
  `_has_usable_rescale` already encodes the usable condition). When gated, name the preset
  generically **"rescaled Default"** (NM may be counts, not SUV — do not assume SUV in the label).
- If there is **no** rescale, replace it with a bit-depth-aware raw "Default" derived from
  `get_stored_value_range` (see §1/§2), `is_rescaled=False`.
- The raw `(128.0, 256.0, False)` NM fallback already matches the tag-derived range for small
  stored ranges; keep it but also let it be derived from the stored range so it is correct for
  other bit depths.

### 4. MONOCHROME1 auto-inversion on screen (layer ownership is the critical part)

**Inversion order (matches export exactly):** in `render_grayscale_image`
(`dicom_image_render.py:188-219`), apply window/level / normalization **first**, cast to `uint8`,
**then** invert with `255 - arr` — identical to `export_rendering.py:221-230`. Both
`apply_window_level` (`dicom_window_level.py:67`) and `normalize_to_uint8` already return a
finalized `uint8` array, so `255 - arr` pre- vs post-cast is numerically identical; the mandate
is to invert on the **finalized uint8 array** so the on-screen result is byte-for-byte the same
operation as export (and so a future reviewer does not "optimize" the cast order and drift from
export). Goal #4 requires "export output matches screen", so cast-then-invert is mandatory.

**XOR ownership — the single most important rule (prevents double-inversion):**

```
effective_inverted = dataset_is_monochrome1 XOR user_toggled_invert
```

- **Core render layer** (`render_grayscale_image`) owns the **dataset baseline** half: it inverts
  iff `PhotometricInterpretation == MONOCHROME1`. It must NOT read or trust any persisted
  `image_inverted`.
- **View / user layer** (`image_viewer_view._apply_inversion`, `set_image`) owns ONLY the
  **user toggle** half. The persisted `image_inverted` in `ViewStateManager.series_defaults`
  (`view_state_manager.py:1098-1112`) and `image_viewer.image_inverted` MUST represent the
  *user* offset (default `False`), **never the combined effective polarity**.
- Therefore `set_image` must never re-invert an image that core has already inverted: it applies
  `_apply_inversion` only when the *user* toggle is set, on top of the core-rendered baseline. A
  MONOCHROME1 series with user toggle `False` is inverted once (in core) and not again in view.

**Persisted-state migration for already-stored series:** `series_defaults` has **no schema/version
key today** (`view_state_manager.py:1081-1112`), so the migration must add a small
`schema_version` key written for every series when inversion state is persisted; treat absence as
"pre-scheme". Rule:
  - For **MONOCHROME2** series: honor the stored user half (`image_inverted`) as-is, including a
    pre-scheme `True` (a user who deliberately inverted a normal series keeps that choice).
  - For **MONOCHROME1** series: discard any pre-scheme stored value and start the user half at
    `False` (the dataset baseline now auto-inverts). Rationale: pre-upgrade, a user could only
    "fix" a MONOCHROME1 series by pressing Invert (`image_inverted=True`); restoring that `True`
    as the user half under the new XOR would yield effective **un-inverted** (wrong). So the
    MONOCHROME1 case is the one that must NOT trust pre-scheme state.
  - For post-scheme state (key present), restore the user half normally for both PI values.
  Store the dataset baseline separately (or derive it fresh each load) so it always wins for
  MONOCHROME1.

- **Export / cine paths must NOT double-invert (same release as render change).** Today
  `export_manager.py:593` and `cine_video_export.py:235` call `dataset_to_image(...)` then
  `process_image_by_photometric_interpretation(image, dataset)`, which performs the MONOCHROME1
  `255 - arr` inversion (`export_rendering.py:221-230`). Once Phase C makes `render_grayscale_image`
  invert MONOCHROME1, these paths would invert **twice** → wrong-polarity stills and cine MP4s.
  Therefore, in the **same commit** as the render change: `process_image_by_photometric_interpretation`
  must drop its MONOCHROME1 branch (keep YBR/RGB/PALETTE branches), OR the two export call sites
  must skip photometric processing for MONOCHROME1. Add `export_rendering.py`, `export_manager.py`,
  `cine_video_export.py` to the Files-to-Change table. Add an export-path regression test asserting
  a MONOCHROME1 still image and a cine frame have the **same polarity** as the on-screen slice.

- **MPR and on-screen projection panes do NOT route through core render — explicit scope.**
  Verified: MPR panes render via `mpr_view_math.array_to_pil` (`mpr_view_math.py:87-94`), which
  does its own WL→uint8 with no photometric handling; on-screen projections use
  `slice_display_pixels.create_slice_projection_pil_image` (`slice_display_manager.py` ~line 359),
  which also applies WL/normalize itself and never consults `PhotometricInterpretation`. The
  earlier claim that "core-routed inversion is inherited" by MPR/projection is **false** — no such
  path exists, so the test described in OQ7 cannot be written and would silently test nothing.
  **Decision (this change):** Phase C fixes the **single-slice on-screen viewer** only. MPR and
  projection-pane MONOCHROME1 inversion are declared an **explicit follow-up** (add a TO_DO entry
  linking here; extend `mpr_view_math.array_to_pil` and `slice_display_pixels` projection path,
  plus the export-projection path, when picked up). This leaves a known, visible asymmetry rather
  than an accidental wrong-polarity MPR pane. Note projection *exports* already skip MONOCHROME1
  (`export_manager.py:593` / `cine_video_export.py:235` guard on `not is_projection_image`), so the
  post-change polarities are: on-screen slice correct, MPR/projection panes follow-up, single-slice
  still/cine export correct (once G1 fix lands), projection export unchanged (already uninverted).

- **Menu check-state semantics (UX decision).** `image_viewer_context_menu.py:667` sets
  `invert_action.setChecked(viewer.image_inverted)`. With user-half-only semantics, a MONOCHROME1
  series displays inverted while the menu shows "Invert Image: unchecked". Decision: the checkbox
  reflects the **user offset** (`image_inverted`), minimal change and consistent with persistence;
  add a status-bar/tooltip affordance so users understand a MONOCHROME1 image is shown inverted by
  modality. (Effective-polarity display is the alternative but requires plumbing the dataset PI into
  the menu; defer unless users report confusion.)

- Keep `invert_image` (manual) semantics: toggling flips the *user* half; effective polarity is
  the XOR, so a user invert on a MONOCHROME2 (or a deliberate un-invert on a MONOCHROME1) is
  preserved and never cancelled by re-derivation.

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
| `src/gui/view_state_manager.py` | Persist **user** inversion half only; add `schema_version` key (lines 1081–1112) |
| `src/gui/export_rendering.py` | Remove MONOCHROME1 branch from `process_image_by_photometric_interpretation` (keep YBR/RGB/PALETTE) |
| `src/gui/export_manager.py` | Drop double-invert (MONOCHROME1 no longer inverted here; line 593) |
| `src/gui/cine_video_export.py` | Drop double-invert (line 235) |
| Tests (below) | New + updated |

---

## Tests (acceptance-linked)

Concrete assertions (each Goal maps to at least one):

- `tests/core/test_wl_builtin_presets.py`: assert CR/DX presets are `is_rescaled=False`,
  bit-depth-aware (10/12/14/16-bit, signed vs unsigned), and contain **no** HU-style
  `is_rescaled=True` values. NM resolved per §3b.
- `tests/core/test_dicom_pixel_range.py`: stored-range math for all bit combos **plus malformed
  inputs** (BitsStored=0, HighBit missing, BitsStored>BitsAllocated) → clamped, non-zero-width.
- `tests/core/test_slice_window_level_resolver.py`: update fixture (line 155 HU `Bone` no longer
  a CR preset); assert `current_preset_index=0` CR/DX preset is `is_rescaled=False` and within
  the stored range (this *is* the default-display change — assert it explicitly, see B4); add a
  MONOCHROME1 default-inversion case.
- `tests/core/test_dicom_image_render_monochrome1.py`: MONOCHROME1 grayscale inversion for
  **unsigned and signed** data; assert output == `255 - export_render(MONOCHROME2_array)` (i.e.
  cast-then-invert matches `export_rendering.py:221-230` exactly).
- `tests/test_wl_preset_catalog.py`: CR/DX HU gate adds presets **only** when rescale present;
  no `is_rescaled=True` CR/DX preset without a real rescale.
- `tests/gui/`: MONOCHROME1 + manual-toggle **combined state (XOR, no double-invert)** — assert a
  MONOCHROME1 series with user toggle `False` is inverted once (core only) and that a
  persisted `image_inverted` restored from storage is the *user* half, never the combined value.
- `tests/gui/test_export_monochrome1.py` (or extend export tests): a MONOCHROME1 still image and
  a cine frame have the **same polarity** as the on-screen slice (G1 regression — guards against
  export/cine double-inversion after core render owns inversion).
- **Duplicate-preset guard:** generated CR/DX/ANY menu presets contain no two entries with
  identical `(center, width)` (covers `Wide` ≠ `Default`, §2).
- **Migration test:** a MONOCHROME1 series with a pre-scheme stored `image_inverted=True` opens
  user half = `False` (effective inverted via baseline); a MONOCHROME2 series with stored `True`
  keeps it.
- **Explicitly NOT covered (follow-up, see TO_DO):** MPR pane (`mpr_view_math.array_to_pil`) and
  on-screen projection pane (`slice_display_pixels`) MONOCHROME1 inversion — no test can assert
  "inherited" because those paths bypass `render_grayscale_image`.

---

## Verification

- `python -m pytest tests/core tests/gui -q`
- `python -m pytest tests/ -q` (full suite)
- `python scripts/check_architecture_boundaries.py`
- `python scripts/agent_smoke_harness.py`
- `python scripts/check_user_docs_links.py`
- Manual: load 10-bit, 12-bit, 14-bit unsigned CR/DX and a MONOCHROME1 series; confirm presets
  render anatomically sensible windows, MONOCHROME1 opens with correct polarity, export output
  matches screen, and the manual Invert toggle flips without double-inverting. Also confirm a
  signed MONOCHROME1 secondary-capture renders correctly.

---

## Phases (with exit criteria)

- **Phase A — range helper + tests.** Exit: `test_dicom_pixel_range` green; verified for
  10/12/14/16-bit, signed/unsigned, missing/malformed tags.
- **Phase B — preset tables + HU gate + NM + MR scope.** Exit: `test_wl_builtin_presets` +
  `test_wl_preset_catalog` green; NM `(500,1000,True)` resolved; no CR/DX `is_rescaled=True`
  without a real rescale; MR explicitly scoped out (follow-up).
- **Phase C — MONOCHROME1 render + combined-toggle + migration + export de-dup (MPR/projection follow-up).** Exit:
  `test_dicom_image_render_monochrome1` + GUI XOR/double-invert tests green; export/cine
  double-invert removed in the **same** commit as the render change; migration **implemented and
  covered by a test** (pre-scheme stored state verified); manual MONOCHROME1 == export check passes.

### Definition of Done (before merge)

- All targeted tests green; full suite green; `check_architecture_boundaries` passes;
  `agent_smoke_harness` passes; `check_user_docs_links` passes.
- Manual MONOCHROME1 polarity == export (still + cine); debug flags False (`src/utils/debug_flags.py`).
- CHANGELOG/version patch bump if warranted; TO_DO link updated (incl. MPR/projection follow-up); migration behavior documented.
- No double-inversion: review confirms core inverts dataset baseline and view persists only the
  user toggle; export/cine paths no longer re-invert MONOCHROME1 (YBR/RGB/PALETTE branches kept).
- No duplicate preset names/values in generated menu (`Wide` ≠ `Default`).
- MONOCHROME1 polarity consistent across slice, still export, cine export — OR declared non-goal
  (MPR/projection panes are the explicit declared non-goal for this change).

---

## Risk / rollback

- **Highest risk:** double-inversion via export/cine paths. Once core render owns MONOCHROME1
  inversion, `export_rendering.process_image_by_photometric_interpretation` (called from
  `export_manager.py:593` and `cine_video_export.py:235`) would invert a second time unless
  updated **in the same commit/release** as the render change. Mitigated by removing the
  MONOCHROME1 branch there (YBR/RGB/PALETTE kept) and a regression test asserting screen uint8 ==
  export/cine uint8 for the same MONOCHROME1 dataset.
- **Secondary risk:** MPR/projection panes bypass core render and are left as an explicit
  follow-up (known asymmetry, not accidental). Tracked via a new TO_DO entry linking here.
- **Behavior change:** removing CR/DX `Chest`/`Bone` changes the default applied W/L for existing
  CR/DX (B4) — intended, but call out in release notes.
- **Rollback:** each phase is its own commit on `fix/wl-presets-bit-depth-monochrome1`; revert the
  phase commit if a gate fails. Persisted-state migration is forward-only (safe to leave; baseline
  re-derived per load).

---

## Rollout / Commits

- Single feature branch `fix/wl-presets-bit-depth-monochrome1`.
- Commit 1: stored-range helper + tests (Phase A).
- Commit 2: bit-depth-aware presets + HU gate + NM + MR scope (Phase B).
- Commit 3: MONOCHROME1 on-screen inversion + combined-toggle state + migration (Phase C).
- Commit 4: docs (link TO_DO, update investigation file status).

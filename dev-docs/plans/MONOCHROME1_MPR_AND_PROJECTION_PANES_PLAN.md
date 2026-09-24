# Plan: MONOCHROME1 Polarity for MPR and Projection Panes

**Date:** 2026-09-24 · **Status:** Planned · **Priority:** P2
**Branch:** `plan/monochrome1-mpr-projection-panes`
**TO_DO item:** "[P2] MONOCHROME1 for MPR and on-screen projection panes (follow-up to the on-screen viewer fix)" (`dev-docs/TO_DO.md:118`)
**Predecessor:** [`WL_PRESETS_BIT_DEPTH_AND_MONOCHROME1_PLAN.md`](completed/WL_PRESETS_BIT_DEPTH_AND_MONOCHROME1_PLAN.md) §Follow-up (shipped 2026-08-16)

---

## TL;DR

The 2026-08-16 fix put MONOCHROME1 baseline inversion inside `render_grayscale_image`
(`src/core/dicom_image_render.py:226-228`) and removed it from export
(`export_rendering.process_image_by_photometric_interpretation`). Three pixel paths never
route through `render_grayscale_image`, so they still show MONOCHROME1 at the wrong polarity:

| Path | Builder | Site |
|------|---------|------|
| MPR panes | `mpr_view_math.array_to_pil` | `src/core/mpr_view_math.py:82-99` |
| On-screen projection panes (AIP/MIP/MinIP) | `slice_display_pixels.create_slice_projection_pil_image` | `src/core/slice_display_pixels.py:19-113` |
| Export + cine projection frames | `export_rendering.create_projection_for_export` | `src/gui/export_rendering.py:289-396` |

The export/cine projection path is now **doubly** wrong: it never inverted MONOCHROME1 itself,
and `export_manager.py:589` / `cine_video_export.py:235` deliberately skip
`process_image_by_photometric_interpretation` for projections (`if not is_projection_image`).

Fix: one shared core helper that inverts the finalized `uint8` array when the source series is
MONOCHROME1, called from all three builders, with the photometric interpretation threaded in
from the source datasets. Manual Invert stays a user-only XOR offset applied later in
`image_viewer_view` — unchanged and not touched by this plan.

---

## Invariants — do not violate

1. **Core owns the dataset baseline; the view layer owns only the user toggle.** Carried over
   from the predecessor plan's Invariant #1. None of the new code may read `image_inverted` or
   `series_defaults`. `image_viewer_view.set_image(..., apply_inversion=...)` already applies
   the user half on top of whatever PIL image it is handed, so MPR/projection panes get the XOR
   for free once the baseline is correct.
2. **Invert a copy, never the caller's array.** The same float array handed to `array_to_pil`
   flows onward to `_display_mpr_post_display_sync` (`mpr_controller.py:1006`). `array_to_pil`
   already copies at `mapped.astype(np.uint8)`; the helper must preserve that, so this is a
   "do not regress it" constraint rather than a redesign.
3. **Invert on the finalized `uint8` array** (`arr = arr.astype(np.uint8); arr = 255 - arr`),
   byte-identical to `render_grayscale_image`. Never invert the float array, and never invert
   before window/level.
4. **Invert display pixels only — never analysis pixels.**
   `slice_display_pixels.compute_intensity_projection_raw_array` (histogram / ROI source,
   `src/core/slice_display_pixels.py:117-153`) must stay raw and uninverted; so must
   `MprResult.slices`, the MPR measurement/probe arrays, and
   `mpr_controller._display_mpr_post_display_sync`'s `array` argument. Inverting those would
   corrupt HU readouts and ROI statistics.
5. **The projection operator keeps operating on stored values.** AIP/MIP/MinIP run before the
   polarity flip, exactly as window/level does. See "Decision: MIP semantics" below.
6. **Screen == export.** Any change to the on-screen projection polarity ships in the same
   commit as the matching `create_projection_for_export` change, or exports diverge from the
   viewer (predecessor Invariant #3, same reasoning).
7. **No new pixel scans and no new per-frame dataset parsing on the hot path.** The PI lookup is
   a tag read on one dataset, resolved once per render call (and cached on `MprResult` for MPR).

---

## Scope

**In scope:** MPR pane display, MPR thumbnail preview, on-screen AIP/MIP/MinIP projection panes,
export-still projection, cine projection frames, and the shared PI helper consolidation.

**Out of scope:** the manual Invert toggle and its persistence (already correct); the 3D volume
renderer (separate ownership, no MONOCHROME1 handling today — record as a new TO_DO if a
MONOCHROME1 volume study surfaces); the `(MI)` status-bar marker for
MPR/projection panes (see "Deferred" below); the DICOM-projection export path
(`create_projection_dataset`, which writes stored pixels and must keep the source
`PhotometricInterpretation` untouched).

---

## Phase 0 — Consolidate the photometric-interpretation helper

`PhotometricInterpretation` is parsed with near-identical list/tuple/strip/upper logic in at
least four places today:

- `src/core/dicom_image_render.py:217-228` (render baseline)
- `src/core/view_state_handlers.py:123-136` (`_is_dataset_monochrome1`, status bar)
- `src/core/view_state_inversion.py:18-22` (legacy-state migration)
- `src/gui/export_rendering.py:207-218` (export dispatch)

Adding three more copies is the wrong move. Create `src/core/photometric_polarity.py`:

```python
def normalize_photometric_interpretation(value: Any) -> str:
    """Upper-cased PI string; '' when absent. Accepts str, list/tuple (first element), None."""

def is_monochrome1(value: Any) -> bool:
    """True iff the normalized PI is exactly 'MONOCHROME1'."""

def dataset_photometric_interpretation(dataset: Any) -> str:
    """Normalized PI read from a pydicom Dataset (''-safe; no exceptions)."""

def apply_monochrome1_polarity(array: np.ndarray, photometric_interpretation: Any) -> np.ndarray:
    """Return ``255 - array.astype(uint8)`` for MONOCHROME1, else the array unchanged."""
```

Then refactor `render_grayscale_image` and `view_state_handlers._is_dataset_monochrome1` to
delegate (behavior-preserving; their existing tests are the regression net).
`view_state_inversion` and `export_rendering` may also delegate their parsing, but do not change
their *decisions* in this plan.

Architecture note: `src/core/` must not import `src/gui/` — this module is pure numpy + typing,
so `scripts/check_architecture_boundaries.py` stays green.

---

## Phase 1 — MPR panes

### 1.1 Carry the PI on `MprResult`

Add `photometric_interpretation: str = ""` to `MprResult`
(`src/core/mpr_builder.py:97-106`), populated exactly like the existing rescale params: a new
`MprBuilderWorker._get_photometric_interpretation()` mirroring `_get_rescale_params`
(`src/core/mpr_builder.py:455-475`), reading `self._volume.source_datasets[0]` via
`dataset_photometric_interpretation`. Default `""` keeps every existing construction site and
test compiling.

Mixed-PI series are pathological; first-dataset-wins matches the rescale precedent. Document
that in the field docstring.

**The disk cache must carry the PI too — this is a correctness bug, not a nicety.**
`mpr_controller.py:1349` reconstructs an `MprResult` from cached meta and passes only
`output_spacing_mm`, `output_thickness_mm`, `interpolation`, `rescale_slope`,
`rescale_intercept`, `combine_mode`, and `slab_thickness_mm`. A new field left out there defaults
to `""`, so a cache hit would render the *uninverted* image while a fresh build renders the
inverted one — same series, polarity depending on cache state, which is the worst possible
failure mode because it is intermittent. Persist `photometric_interpretation` in the cache meta
(`src/core/mpr_cache.py:125` save / `:294` load) and read it back at `mpr_controller.py:1349`, in
the same commit as §1.1. It is re-derivable at save time from
`result.source_volume.source_datasets`, so old entries can also simply be invalidated — pick one
and say which. Test: a cache-hit render and a cold-build render of the same MONOCHROME1 series
produce identical pixels.

### 1.2 Extend `array_to_pil`

```python
def array_to_pil(
    array: np.ndarray,
    window_center: float,
    window_width: float,
    *,
    photometric_interpretation: str | None = None,
) -> Image.Image | None:
```

Apply `apply_monochrome1_polarity` after `uint8_arr = mapped.astype(np.uint8)` and before
`Image.fromarray`. Keyword-only with a `None` default, so the 16 existing positional calls in
`tests/core/test_mpr_view_math.py` keep passing unchanged and the MONOCHROME2 path is
bit-identical.

### 1.3 Thread it through the controller

- `mpr_controller._array_to_pil` (`src/gui/mpr_controller.py:1904-1921`): add the same
  keyword-only parameter and forward it.
- `display_mpr_slice` (`src/gui/mpr_controller.py:956`, `_array_to_pil` call at `:992`): pass
  `photometric_interpretation=result.photometric_interpretation`.
- Audit for other `_array_to_pil` / MPR render entry points before editing
  (`rg "_array_to_pil|display_mpr_slice" src`) — `tests/gui/test_mpr_controller_sonar_slice.py:163`
  patches `_array_to_pil`, so any new keyword must not break that patch (it uses
  `patch.object(..., return_value=...)`, which tolerates added kwargs).

### 1.4 MPR thumbnail preview

`mpr_thumbnail_widget.update_preview` (`src/gui/mpr_thumbnail_widget.py:120-188`) does its own
inline windowing and `Image.fromarray(uint8_arr, mode="L")`. Add an optional
`photometric_interpretation: str | None = None` parameter and apply the same helper on
`uint8_arr`. A thumbnail whose polarity disagrees with the pane it previews is exactly the bug
this plan exists to remove.

**"Pass it from the caller" is five links, not one.** Editing only `update_preview` leaves
thumbnails broken, because nothing upstream carries the PI:

```
core/mpr_navigator_thumbnail.update_mpr_navigator_thumbnail          (:82, call at :125)
core/mpr_navigator_thumbnail.update_floating_mpr_navigator_thumbnail (:149, call at :194)
  -> gui/series_navigator.set_mpr_thumbnail                          (:160)
     -> stored in the _mpr_thumbnail_specs dict                      (:191-198)  <- no PI key today
        -> gui/series_navigator._append_mpr_thumbnails_for_series    (:643)
           -> mpr_widget.update_preview(...)                         (:661-665)  <- forwards 3 args
```

All five need the PI threaded: both navigator-thumbnail entry points, `set_mpr_thumbnail`'s
signature, a new `"photometric_interpretation"` key in the spec dict, and the `update_preview`
call. Existing spec-dict tests (`tests/gui/test_series_navigator_coverage_followup.py:171`) stay
green under a `None` default, but add a test that the PI actually propagates end to end and a
direct unit test that `update_preview` inverts its `uint8` array for MONOCHROME1.

---

## Phase 2 — On-screen projection panes

### 2.1 `create_slice_projection_pil_image`

The function already derives `series_datasets` as a local
(`src/core/slice_display_pixels.py:47`), so no new caller argument is strictly required.
Prefer the explicit parameter anyway — the callers know the canonical dataset, and an explicit
argument keeps the function testable without a full studies dict:

```python
    ...,
    rescale_intercept: float | None,
    *,
    photometric_interpretation: str | None = None,
) -> Image.Image | None:
```

When `photometric_interpretation` is `None`, fall back to
`dataset_photometric_interpretation(series_datasets[0])` — the **series-first** dataset, not
`projection_slices[0]` (the slab start). MPR uses `source_datasets[0]`; using the same rule in
both places keeps one answer per series instead of a slab-dependent one. Apply
`apply_monochrome1_polarity` to `processed_array` **after** the window/level or normalize
branch and after the `np.clip(...).astype(np.uint8)` cast — note the windowed branch relies on
`dicom_processor.apply_window_level` already returning `uint8`; assert that in the test rather
than assuming it, and cast defensively in the helper (Invariant #3 does this already).

Guard the color branches: only invert when the array is 2-D grayscale. A 3-channel projection
array cannot be MONOCHROME1, but the shape check prevents a silent RGB inversion if a malformed
series claims otherwise.

### 2.2 Caller

`slice_display_manager._create_projection_image` (`src/gui/slice_display_manager.py:328-372`)
already takes `_dataset` (currently unused, prefixed). Use it: pass
`photometric_interpretation=dataset_photometric_interpretation(_dataset)` and rename the
parameter to `dataset`. Check for other callers first (`rg "create_slice_projection_pil_image" src`
— currently only this one).

### 2.3 Leave the raw path alone

`compute_intensity_projection_raw_array` gains nothing and must change nothing (Invariant #4).
Add a test pinning that it stays uninverted for a MONOCHROME1 series, so a future well-meaning
edit does not "fix" it.

---

## Phase 3 — Export and cine projection (same commit as Phase 2)

`export_rendering.create_projection_for_export` (`src/gui/export_rendering.py:289-396`) builds
its PIL image inline at lines 382-390. Apply `apply_monochrome1_polarity` to `processed_array`
before `Image.fromarray`, using `dataset_photometric_interpretation(dataset)` — the function
already takes the current `dataset` for metadata and rescale.

Apply the same 2-D-grayscale shape guard as §2.1. The export function has the identical
2-D / 3-channel / fallback branch structure at `export_rendering.py:382-390`, so the guard
belongs in both or the two paths drift.

Do **not** re-enable `process_image_by_photometric_interpretation` for projections. The
`if not is_projection_image:` guards at `export_manager.py:589` and `cine_video_export.py:235`
stay as they are; that helper no longer inverts MONOCHROME1 at all (predecessor W2.3), and the
guard still correctly protects the YBR/RGB branches from running on an already-grayscale
projection. Cine inherits the fix for free — it calls the same helper
(`cine_video_export.py:203`).

`create_projection_dataset` (`src/gui/export_rendering.py:398+`) is untouched: it writes stored
pixel values into a DICOM object that keeps the source `PhotometricInterpretation`, so inverting
there would corrupt the file.

---

## Decision: MIP semantics under MONOCHROME1

**What PhotometricInterpretation does and does not say** (see References; this framing governs
the whole plan, not just this section). MONOCHROME1 is purely a *display* directive: "the minimum
sample value is intended to be displayed as white after any VOI gray scale transformations have
been performed" (PS3.3 C.7.6.3.1.2). Its counterpart MONOCHROME2 displays the minimum as black.
Neither changes how pixel values are or should be stored, and neither implies the pixel data was
or should be inverted on disk. The equivalent statement in the presentation chain is Presentation
LUT Shape (2050,0020): `IDENTITY` for MONOCHROME2, `INVERSE` for MONOCHROME1. So the only
unconditional consequence is:

> Under MONOCHROME1, the **highest stored value displays darkest**, and the lowest displays
> brightest. That is the entire content of the tag.

**You cannot infer tissue polarity from PhotometricInterpretation.** Whether bone is a high or a
low stored value is declared by a *different*, independent pair of attributes — Pixel Intensity
Relationship (0028,1040) and Pixel Intensity Relationship Sign (0028,1041) — and PS3.3 C.8.11.3
says of them explicitly: "They do not define a transformation intended to be applied to the pixel
data for presentation." The standard's own worked example uses `LIN` with sign `-1`, where
*higher* pixel values mean less beam intensity, i.e. bone and contrast are the **high** values.
A MONOCHROME1 image with that sign therefore displays bone dark; with sign `+1` it displays bone
bright. Both are legal, and this plan must not assume either.

Consequently, for the projection operators the only defensible statement is the display-domain
one: projecting on stored values and inverting at render means a "MIP" returns the stored maximum,
which under MONOCHROME1 is displayed as the **darkest** pixel in the slab — the opposite of what
a user expects from "maximum intensity" — and MinIP displays brightest. Which *tissue* that
corresponds to depends on (0028,1041) and is not knowable from the polarity tag alone.

**AIP is unaffected and must not be "fixed" later.** The mean commutes with `255 - x`, so
`255 - mean(x) == mean(255 - x)` exactly. Only MIP and MinIP are order-sensitive.

**Recommendation for this plan: keep the operator on stored values (Invariant #5).** Reasons:

- It preserves the slice/projection/export contract the predecessor plan established: one
  window/level pipeline, one polarity flip at the end. Swapping the operator would make the
  projection's raw histogram path (Invariant #4) disagree with what the pane shows.
- MONOCHROME1 is predominantly seen in projection radiography (the DX Image Module permits only
  MONOCHROME1 or MONOCHROME2, and CR/DX/MG/RF/XA are where it is encountered in practice), where
  slab projections are rare. CT and MR permit it but conventionally store MONOCHROME2. The
  polarity bug is the real, reachable defect; the operator question is a design choice on a
  near-empty intersection.
- Swapping silently would change the meaning of an existing exported image with no version marker.

If the user wants brightness-domain semantics instead, the clean form is to swap `mip`↔`minip`
selection for MONOCHROME1 series at the *controller* level (so the label the user picked matches
the displayed result) and label it in the overlay. **Add that as a separate TO_DO item**, do not
fold it into this fix. That TO_DO must record two constraints: the swap has to apply at **both**
the on-screen and the export-projection operator selection or export diverges from screen
(Invariant #6), and brightness-domain semantics will inherently disagree with the raw-histogram
path (Invariant #4), which is a deliberate trade the user has to accept.

---

## Tests

New files (mirroring `tests/core/test_dicom_image_render_monochrome1.py`):

- `tests/core/test_photometric_polarity.py` — helper unit tests: `str`/list/tuple/`None`/empty/
  lowercase `"monochrome1"`/`MONOCHROME2`/`RGB` inputs; `apply_monochrome1_polarity` is
  `255 - arr` on uint8, identity for non-MONOCHROME1, and handles a non-uint8 input by casting.
- `tests/core/test_mpr_view_math_monochrome1.py` — `array_to_pil` with and without the kwarg;
  assert MONOCHROME2 output is unchanged from the current expected bytes, and MONOCHROME1 output
  equals `255 - <MONOCHROME2 output>` pixel for pixel.
- `tests/core/test_slice_display_pixels_monochrome1.py` — AIP/MIP/MinIP × (windowed, normalized)
  × (MONOCHROME1, MONOCHROME2); plus the Invariant #4 pin on
  `compute_intensity_projection_raw_array`.
- `tests/gui/test_export_projection_monochrome1.py` — `create_projection_for_export` polarity,
  the 2-D-only shape guard (a 3-channel array is never inverted), and the end-to-end contract:
  **on-screen projection pixels == exported projection pixels** for the same slab, W/L, and PI.
  That equality assertion is the one that catches a future half-applied change — but it must
  compare the *builder* outputs, or pin the manual Invert toggle to `False`. Export deliberately
  ignores the user toggle (`export_manager.py:586-590` never applies it), so an equality test
  written against a viewer with Invert on fails by design and would be "fixed" wrongly.

Extend existing files:

- `tests/core/test_mpr_builder*.py` — `MprResult.photometric_interpretation` is populated from
  the first source dataset and defaults to `""` when there are none.
- MPR cache round-trip — a cache-hit render and a cold-build render of the same MONOCHROME1
  series produce identical pixels (the §1.1 intermittent-polarity bug).
- MPR thumbnail chain — the PI propagates from `update_mpr_navigator_thumbnail` /
  `update_floating_mpr_navigator_thumbnail` through `_mpr_thumbnail_specs` to `update_preview`,
  plus a direct unit test that `update_preview` inverts for MONOCHROME1.
- `tests/gui/test_mpr_controller_sonar_slice.py` — the controller forwards the PI from the
  result into `_array_to_pil`.
- `tests/core/test_slice_display_pixels.py` — existing positional calls stay green (proves the
  kwarg is genuinely optional).

Qt-touching tests use the session `qapp` fixture; no test constructs a `QCoreApplication`
(`dev-docs/info/TESTING_GUIDANCE.md`). Iterate single tests with `-n 0`.

---

## Verification

```
source .venv/bin/activate
python -m pytest tests/ -v                          # ~10 min timeout
python scripts/check_architecture_boundaries.py
python scripts/check_repo_harness.py
python scripts/agent_smoke_harness.py
python scripts/git_hook_privacy_checks.py --staged
```

Manual smoke (needs a MONOCHROME1 multi-slice series — a MONOCHROME1 CT/MR is rare, so a
synthesized fixture built by flipping `PhotometricInterpretation` on an existing test series is
acceptable and must live under `tmp/`, never staged):

1. Open the series; confirm the single-slice pane polarity (the shipped, correct baseline).
2. Enable projection (AIP, then MIP, then MinIP); confirm each pane matches the slice polarity.
3. Export a still with projection on; confirm the PNG matches the screen.
4. Export a short cine with projection on; confirm frames match.
5. Open MPR; confirm all three planes and the MPR thumbnails match the slice polarity.
6. Toggle manual Invert in each mode; confirm it flips relative to the baseline (XOR), and that
   the context-menu checkbox reflects the user half only. Note that the MPR pane's toggle is
   per-viewer local and is never seeded from `series_defaults`, unlike the main pane — so its
   persistence behaviour differs by design and is not a regression.
7. Open the histogram with "Use intensity projection pixels"; confirm the distribution is
   unchanged by this work (raw path, Invariant #4).

---

## Definition of done

- All three builders apply the baseline inversion through the one shared helper; no new copy of
  the PI parsing logic exists.
- On-screen MPR, MPR thumbnail, on-screen projection, exported projection still, and cine
  projection frames all agree with the single-slice viewer for a MONOCHROME1 series.
- Manual Invert remains a pure user XOR in every mode; persistence is untouched.
- Raw/analysis arrays are provably uninverted (test-pinned).
- Full suite, architecture boundaries, harness, and agent smoke are green.

---

## References

Checked 2026-09-24 against the current edition of the DICOM standard. These back the polarity
claims above; re-read them before changing any inversion behavior.

- **PS3.3 C.7.6.3.1.2, Photometric Interpretation (0028,0004)** — MONOCHROME1 / MONOCHROME2
  definitions ("minimum sample value is intended to be displayed as white / black after any VOI
  gray scale transformations"). The definitions are about display only; the standard states no
  storage or encoding difference between the two.
  <https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_c.7.6.3.html>
- **Presentation LUT Shape (2050,0020)** — `IDENTITY` "shall be used if Photometric
  Interpretation is MONOCHROME2"; `INVERSE` "shall be used if Photometric Interpretation is
  MONOCHROME1". Confirms MONOCHROME1 is an inverted presentation transform, not inverted data.
  <https://dicom.innolitics.com/ciods/digital-x-ray-image/dx-image/20500020>
- **PS3.3 C.8.11.3, DX Image Module** — Photometric Interpretation restricted to MONOCHROME1 or
  MONOCHROME2; Pixel Intensity Relationship (0028,1040) / Sign (0028,1041) "describe how the
  stored pixel values ... are related to the X-Ray beam intensity" and "do not define a
  transformation intended to be applied to the pixel data for presentation"; worked example with
  `LIN` / sign `-1` where higher values are bone and contrast.
  <https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_C.8.11.3.html>
- **Pixel Intensity Relationship Sign (0028,1041)** — enumerated values: `+1` lower pixel values
  correspond to less X-ray beam intensity; `-1` higher pixel values correspond to less intensity.
  <https://dicom.innolitics.com/ciods/digital-x-ray-image/dx-image/00281041>
- **PS3.3 C.11.2, VOI LUT Module** — Window Center / Width "shall be used only for Images with
  Photometric Interpretation values of MONOCHROME1 and MONOCHROME2", and specify a conversion
  from stored values after the Modality LUT. Together with C.7.6.3.1.2's "after any VOI gray
  scale transformations", this pins the pipeline order this plan implements: modality rescale →
  window/level on stored values → polarity inversion last, on the finalized 8-bit array.
  <https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_C.11.2.html>
- **Corroborating implementation practice** — the widely cited position that a renderer should
  apply an inverting LUT at display rather than invert stored pixel values.
  <https://github.com/scifio/scifio/issues/311>

---

## Closeout (same PR, per AGENTS.md)

- Remove the MONOCHROME1 MPR/projection item from `dev-docs/TO_DO.md:118`.
- Add the new "MIP/MinIP operator semantics under MONOCHROME1" TO_DO item (see Decision above).
- Add a `CHANGELOG.md` entry (user-visible display fix) and bump `src/version.py` per
  [`SEMANTIC_VERSIONING_GUIDE.md`](../info/SEMANTIC_VERSIONING_GUIDE.md) — patch-level.
- Append the manual smoke steps above to **Manual Smoke Checks** in `TO_DO.md` if they are not
  all completed in-PR.
- Move this plan to `dev-docs/plans/completed/` and update the predecessor plan's §Follow-up
  (`WL_PRESETS_BIT_DEPTH_AND_MONOCHROME1_PLAN.md:322-326`, confirmed present) to point at it.

---

## Deferred

- **`(MI)` marker for MPR/projection panes.** The status-bar modality-inverted marker
  (`format_status_bar_wl`) is driven by `current_dataset` and reaches the single-slice pane
  only. Extending it to MPR/projection panes is a status-plumbing change, not a pixel change;
  track separately.
- **3D volume renderer.** Does not apply MONOCHROME1 today; out of scope here.
- **Fusion blending is not untouched, even though no fusion code changes.** `_maybe_apply_fusion`
  (`slice_display_manager.py:579-607`) blends `np.array(base_image)` (`fusion_coordinator.py:809`)
  where the base is the slice/projection PIL this plan corrects, while the overlay half is
  windowed from stored values with no polarity concept. After this fix the base carries inverted
  polarity into an unexamined blend, and the composite is what the user XOR then applies to.
  Deferring is defensible — fusion of a MONOCHROME1 base is vanishingly rare — but the behaviour
  change is real and must not be discovered by a user. Smoke it if a fusion-capable MONOCHROME1
  pair exists; otherwise raise a TO_DO.

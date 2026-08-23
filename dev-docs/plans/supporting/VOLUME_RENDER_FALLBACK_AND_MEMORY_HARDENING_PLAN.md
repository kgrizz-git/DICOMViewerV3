# Plan: Fix the blank-frame GPU-fallback false positive and the volume build memory amplification

**Date:** 2026-08-22
**Status:** Supporting — both defects confirmed by measurement, implementation not started
**Priority:** P1 (Task A — silent quality degradation), P2 (Task B — memory)
**Area:** 3D Volume Rendering — renderer correctness and build-path memory
**Branch suggestion:** `fix/volume-render-fallback-and-memory`
**Related:** [`3D_VIEWER_MACOS_NATIVE_RENDERING_PLAN.md`](../3D_VIEWER_MACOS_NATIVE_RENDERING_PLAN.md),
[`3D_VOLUME_RENDERING_PLAN.md`](../3D_VOLUME_RENDERING_PLAN.md),
[`3D_VIEWER_FIRST_PAINT_RESPONSIVENESS_PLAN.md`](../3D_VIEWER_FIRST_PAINT_RESPONSIVENESS_PLAN.md)

> Both defects were found while diagnosing the native-macOS 3D freeze. **Neither causes
> that freeze** — they are independent, real, and reproducible. Task A and Task B are
> independent of each other and of the macOS plan; they can land in any order.

---

## Task A — `check_gpu_fallback()` misdiagnoses legitimately blank frames

### Problem

[`src/core/volume_renderer.py:924`](../../../src/core/volume_renderer.py) infers "the GPU
silently failed" from a single signal: the first rendered frame is entirely black. That
inference is invalid whenever the transfer function legitimately maps every voxel in the
volume to zero opacity.

The default CT preset is **CT Bone**, which makes everything below roughly 200 HU fully
transparent. A CT QC phantom is water and acrylic — roughly 0–120 HU, **no bone**. Its
first frame is *correctly* black.

**Confirmed by repro** on a synthetic water phantom (no bone, HU range −1000…120):

```text
preset: CT Bone
first Fast render 0.25s   (GetLastUsedRenderMode() == 2, i.e. GPU — the GPU worked fine)
check_gpu_fallback -> True
requested render mode now: 1   (CPU ray cast)
```

### Consequences

- The mapper is switched to CPU ray casting for the rest of the session.
- `_gpu_fallback_done` latches `True`, so the decision is never revisited.
- `run_first_preview()` sets `_auto_refine_suppressed = True`, pinning detail at **Fast**.
- The user is shown "3D preview shown at Fast detail… choose a detail level manually",
  blaming their hardware for what is actually a transfer-function outcome.

Any bone-free CT (QC phantoms, water phantoms, pure soft-tissue crops) hits this.

### Fix

Do not treat "black frame" as sufficient evidence. Establish whether a non-blank frame was
even *expected* before concluding failure.

- [ ] **Step 1:** Add a pure helper — `frame_expected_nonblank(opacity_tf, occupancy) -> bool`.
      **Evaluate opacity against values the volume actually contains, not the scalar range
      alone:** a range endpoint pair says nothing about which values are populated, so a
      transfer function that is opaque only in a band with *no voxels* would be wrongly
      judged visible. Drive it from a **full-coverage histogram**, not a strided sample.
      **This helper must fail safe toward "visible".** A strided sample can miss sparse
      opaque content — a handful of high-HU fiducials, seeds, or clips occupy very few
      voxels — and a false `EXPECTED_BLANK` is the worse error: it suppresses a *genuine*
      CPU fallback and leaves the user on a silently broken GPU path with a black
      viewport. A full histogram over the volume has no such blind spot; if any
      approximation is used instead, it must round toward "expected visible". Return
      `False` only when the maximum mapped opacity across *all* occupied values is ~0.
      The signal must also correspond to what `check_gpu_fallback()` measures — RGB output
      — so colour/lighting that renders black must not be mistaken for a GPU failure. Put
      it in `src/core/volume_render_quality.py` (VTK-free, unit-testable) or a sibling pure
      module. Computing the histogram on the background build thread avoids a GUI-thread
      cost; note the volume can be large.
- [ ] **Step 2:** Return a **three-way outcome** from `check_gpu_fallback()`, not a bool:
      `FELL_BACK` / `GPU_OK_VISIBLE` / `EXPECTED_BLANK`. A bare `False` collapses "the GPU
      rendered fine" and "nothing was supposed to be visible", which are different states
      and need different UI and refinement rules. On `EXPECTED_BLANK`, do not switch to CPU
      — the render is correct and there is nothing to fall back from.
- [ ] **Step 3:** Do **not** latch `_gpu_fallback_done` on `EXPECTED_BLANK`, so a later
      preset change can still probe once for a genuine GPU failure.
- [ ] **Step 4:** Drive `run_first_preview()` from the outcome: suppress auto-refine only
      on `FELL_BACK`. **Keep the existing elapsed-time suppression** for a slow but visible
      preview — that gate is independent of blankness and must not be lost. On
      `EXPECTED_BLANK` a fast preview should refine normally.
- [ ] **Step 5:** Consider a distinct, honest user message for the
      expected-blank case (e.g. "Nothing is visible with this preset — try CT Soft Tissue")
      instead of the hardware-performance warning. Keep it non-modal, reusing
      `set_render_feedback()`.
- [ ] **Step 6:** Tests, with fixtures chosen so the two black-frame causes are actually
      distinguishable:
      - all-transparent transfer function (bone-free phantom + CT Bone) → **no** fallback,
        detail not pinned, `EXPECTED_BLANK`;
      - a preset that *should* produce visible output but renders black (simulated GPU
        failure) → fallback still fires. Note the previous wording asked one
        all-transparent fixture to prove both, which it cannot;
      - **sparse opaque content** (a volume that is empty except for a few high-HU
        voxels, as with fiducials or clips) → judged *visible*, so a genuine GPU failure
        on that volume still triggers fallback. This is the case a strided sample would
        get wrong;
      - existing Parallels blank-frame behaviour preserved;
      - slow-but-visible preview still suppresses auto-refine via the elapsed-time gate.

### Success criteria

- A bone-free CT phantom under CT Bone stays on the GPU path and keeps its Auto detail.
- Real GPU failures on Parallels / virtual GPUs still fall back to CPU ray casting.
- No user-facing message blames hardware for a transfer-function outcome.

---

## Task B — ~8× memory amplification in the volume build path

### Problem

Measured on a synthetic 800-slice CT (512×512×800), instrumented with `ru_maxrss`:

```text
int16 source MB: 419   peak RSS 1032 MB
after prepare_volume_data: peak RSS 3274 MB
after attach_volume:       peak RSS 3276 MB
```

**419 MB of pixel data → 3.3 GB peak RSS**, on top of the pydicom datasets the viewer
already holds. Four full-size buffers stack up:

| Source | Buffer |
|---|---|
| `sitk.GetArrayFromImage(sitk_image)` | int16 copy (419 MB) |
| `np.ascontiguousarray(arr, dtype=np.float32)` | float32 copy (838 MB) |
| `_calibrate_volume_array()` → `calibrated = arr.copy()` | float32 copy (838 MB) |
| `numpy_to_vtk(..., deep=True)` | float32 copy (838 MB) |

Plus the `sitk_image` itself, retained by `MprVolume` for the dialog's lifetime, and
`source_datasets`. Display smoothing (`vtkImageGaussianSmooth`,
[`src/core/volume_renderer.py:796`](../../../src/core/volume_renderer.py)) allocates yet
another full float32 volume at runtime when sigma > 0.

There is no cap and no downsampling — `dev-docs/TO_DO.md:217` confirms the downsampling
toggle was never implemented; only a cosmetic ">512 MB" warning exists in the Advanced
render-status readout.

> **Note:** `self._vtk_image_original = vtk_image` at
> [`src/core/volume_renderer.py:485`](../../../src/core/volume_renderer.py) aliases the same
> object, but this was checked and is **harmless** — the smoother emits a *new* output and
> the original is never mutated in place. Do not "fix" it.

### Fix

- [ ] **Step 1:** Eliminate the `_calibrate_volume_array()` copy. The array it receives was
      just created by `ascontiguousarray(..., dtype=np.float32)` and is uniquely owned, so
      per-slice rescale can be applied **in place**. Guard this with an explicit ownership
      contract: `prepare_volume_data()` must document that it hands over a fresh, owned
      array, and `_calibrate_volume_array()` must assert `arr.flags.owndata` before
      mutating. **Validate in two passes:** the current code can bail part-way because it
      copies first, but in-place mutation cannot be undone — so collect and check every
      slice's slope/intercept, the zero-slope condition, and the unit set in a read-only
      pass, and only mutate once all inputs are known good. Preserve the existing
      early-return semantics exactly (mixed units, non-finite slope/intercept, zero slope →
      fall back to raw, **unmutated**).
- [ ] **Step 2:** Drop the `numpy_to_vtk(deep=True)` copy in favour of `deep=False`,
      retaining a strong reference to the backing numpy array for the lifetime of the
      `vtkImageData`. **This is the riskiest step** — a dangling reference is a
      use-after-free, not a wrong picture. Store the array on the renderer alongside
      `_vtk_image`, clear both together in `cleanup()`, and add a test that renders after
      dropping every other reference to `VolumeData`.
- [ ] **Step 3:** Release the int16 intermediate and the `sitk_image` as soon as the
      float32 array exists, where `MprVolume`'s other consumers permit it. Audit
      `MprVolume.sitk_image` users before changing retention.
- [ ] **Step 4:** Add a real memory guard: estimate the peak requirement up front (reuse
      `estimate_volume_megabytes()`), and above a threshold either downsample by an integer
      factor or refuse with an actionable message. This closes the `TO_DO.md:217` P2 item.
      **Decide before allocating.** The estimate must be computed from the *source*
      dimensions and the factor chosen **before** `prepare_volume_data()` materialises the
      full-size float32 array or anything is handed to VTK — deciding afterwards means the
      peak has already been paid and the guard cannot prevent the very thrash it exists to
      stop. Downsampling should therefore be applied during, not after, the array build.
      **Count every live buffer** in the estimate, including the retained `vtkImageData`
      and the *additional* full-size float32 volume `vtkImageGaussianSmooth` allocates
      whenever display smoothing sigma > 0
      ([`src/core/volume_renderer.py:796`](../../../src/core/volume_renderer.py)) — a
      volume that fits without smoothing can still exhaust memory with it on.
      Downsampling must be applied **before** the VTK attach, and the Advanced status
      readout must state the volume was downsampled — never silently. **Update the derived
      geometry with it:** integer decimation changes `spacing` (and, depending on the
      sampling convention, `origin`), so `VolumeData.spacing`/`origin`/`direction` must be
      recomputed and volume bounds plus crop-box placement re-derived. Shrinking only the
      voxel array would silently rescale the anatomy and break measurements in physical
      coordinates.
- [ ] **Step 5:** Re-measure with the same `ru_maxrss` harness and record before/after in
      this plan. Target: **at most one full-size float32 buffer live at peak** (~838 MB for
      the fixture), which is what the "under ~1.5 GB peak RSS" success criterion below
      implies once the int16 source and interpreter overhead are counted. The earlier
      "≤ 2 buffers" wording was inconsistent with that number. **Measure both** display
      smoothing off and sigma > 0, since the latter is the true worst case.
- [ ] **Step 6:** Tests — in-place calibration correctness vs. the current copy-based
      result (bit-identical on a fixture); `deep=False` lifetime safety; downsample
      threshold policy as a pure unit test; existing rescale fall-back paths unchanged.

### Success criteria

- Peak RSS for the 800-slice fixture drops from ~3.3 GB to under ~1.5 GB.
- Calibrated voxel values are bit-identical to today's output.
- Oversized volumes downsample or refuse with a clear message rather than swap-thrashing.
- No use-after-free under `deep=False` (test renders with all other references dropped).

---

## Global constraints

- Activate the project `.venv` before tests. Full suite: `python -m pytest tests/ -v` (~10 min).
- PHI: synthetic fixtures only; no series paths or patient identifiers in tests or logs.
- Back up modified production files under `tmp/*.bak-*`; delete after a verified commit.
- SemVer: **patch** for Task A; **patch** for Task B unless the downsampling guard becomes
  a user-visible toggle, in which case **minor**.
- Task B Step 2 must not land without Step 6's lifetime test passing.

---

## File map

| File | Role |
|------|------|
| `src/core/volume_renderer.py` | `check_gpu_fallback()`, `prepare_volume_data()`, `attach_volume()`, `_calibrate_volume_array()`, `cleanup()` |
| `src/core/volume_render_quality.py` | New `frame_expected_nonblank()` policy helper; downsample threshold policy |
| `src/gui/volume/first_paint.py` | Stop suppressing auto-refine when no real fallback occurred |
| `src/gui/volume_viewer_widget.py` | Status/feedback copy for the expected-blank case; downsample notice |
| `tests/core/test_volume_render_quality.py` | Policy unit tests |
| `tests/test_volume_renderer_controls.py` | Fallback behavior tests |
| `tests/core/test_volume_memory.py` | **New.** Calibration equivalence + `deep=False` lifetime |
| `CHANGELOG.md`, `dev-docs/MAINTENANCE_LOG.md`, `dev-docs/TO_DO.md` | Standard bookkeeping (close `TO_DO.md:217`) |

---

## Verification gate

- [ ] Bone-free CT phantom + CT Bone preset: GPU path retained, Auto detail retained,
      no hardware-blaming message.
- [ ] Windows under Parallels: genuine blank-frame GPU failure still falls back to CPU.
- [ ] 800-slice fixture: before/after peak RSS recorded here.
- [ ] Full pytest suite green.

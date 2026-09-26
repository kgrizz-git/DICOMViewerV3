# Look-Up Tables (LUTs) & Colormaps Plan

**Status:** Not started  
**Priority:** P1  
**Last updated:** 2026-09-25  
**TO_DO ref:** [`TO_DO.md` Next up](../../TO_DO.md#next-up) — "**More and custom look-up tables (LUTs & colormaps)**" (paraphrased; see the **Next up** entry for the authoritative wording)

---

## Goal

Extend the display pipeline beyond the current **linear** window/level ramp to support **non-linear look-up tables** (sigmoid, logarithmic, exponential, gamma) and **color look-up tables / colormaps** (hot, cool, rainbow, bone, etc.) for grayscale DICOM images. Also provide an interactive custom curve editor with draggable breakpoints, freehand drawing, and straight-line or smooth interpolation; display the active/loaded LUT with its curve or colormap preview; and show the **active window/level ramp, the LUT, and their composed result** together as a transfer-function display, since the LUT is a separate processing step applied *after* window/level (`final(x) = LUT(WL(x))`).

### Current state

- `src/core/dicom_window_level.py` → `apply_window_level()` uses a linear clamp+normalize to uint8.
- All direct `apply_window_level()` call sites (must each be reconciled in Phase 2):
  - `src/core/dicom_processor.py:132`
  - `src/core/dicom_image_render.py:204`
  - `src/core/slice_display_pixels.py:110` (AIP/MIP/MinIP projections — **not** via `SliceDisplayManager`)
  - `src/gui/export_rendering.py:357` (export rasterization — **not** via `SliceDisplayManager`)
- `src/core/slice_display_lut.py` is **not** a LUT system — it is W/L rescale-alignment (`apply_window_level_rescale_conversion`). It is reused, not replaced, by this plan; the new engine must not shadow its name/purpose.
- Fusion applies colormaps through `FusionProcessor.apply_colormap()`
  (`src/core/fusion_processor.py:100-124`), which is **matplotlib-only** and
  memoizes into a module-level `_COLORMAP_CACHE` (`fusion_processor.py:28`,
  `:113-121`); `fusion_handler.py:78` holds only the colormap *name* string.
  There is **no** `cv2.applyColorMap` call anywhere in `src/` (and no `cv2`
  import at all), so do not look for an OpenCV colormap path.
- No general-purpose LUT system for single-series grayscale display.
- Histogram widget (`src/gui/dialogs/histogram_dialog.py`, drawing in `src/tools/histogram_widget.py`) does not show the transfer function.

---

## Phase 1 — LUT engine

### 1a. LUT module

- [ ] Create `src/core/lut_engine.py`:
  ```python
  LutType = Literal["grayscale_ramp", "colormap"]
  Interpolation = Literal["linear", "monotone_cubic", "catmull_rom"]

  @dataclass(frozen=True)
  class LookUpTable:
      name: str
      lut_type: LutType = "grayscale_ramp"
      source: Literal["built_in", "dicom", "file", "custom"] = "built_in"
      transfer_fn: Callable[[float], np.ndarray] | None = None
      colormap: np.ndarray | None = None          # (256, 3) uint8 for color LUTs
      control_points: tuple[tuple[float, float], ...] | None = None
      interpolation: Interpolation = "linear"
      gamma: float | None = None                  # 0.1–5.0, used when transfer_fn is gamma
      sigmoid_k: float | None = None              # steepness, used when transfer_fn is sigmoid
      exp_k: float | None = None                   # 0.1–5.0, used when transfer_fn is exponential

      def __post_init__(self) -> None:
          """Validate/normalize: sort control points by x, reject duplicate x,
          clamp y to [0, 1], require x strictly increasing in [0, 1], require
          gamma in [0.1, 5.0], require colormap shape (256, 3) uint8 when set."""

  def apply_lut(
      pixel_array: np.ndarray,
      window_center: float,
      window_width: float,
      rescale_slope: float | None = None,
      rescale_intercept: float | None = None,
      *,
      lut: LookUpTable | None = None,
  ) -> np.ndarray:
      """Apply W/L then LUT. Returns uint8 (grayscale) or (H,W,3) uint8 (color).

      ``lut=None`` (or a linear LUT) is a passthrough that reproduces today's
      linear clamp+normalize byte-for-byte.
      """
  ```

`lut` is optional from Phase 1 so the engine is testable on its own, before
Phase 2 threads it through the display path; `apply_window_level()` gains the
same optional parameter in Phase 2a.

Custom curves are first-class data, not a raster-only editor state: keep ordered
control points plus an interpolation mode in the LUT model, then sample them to
a 256-entry LUT for the fast display path. The editor, histogram overlay, and
persistence format should all share this representation.

**Interpolation choices.** `linear` and `monotone_cubic` (Fritsch–Carlson) both
pass through every control point. Smooth mode uses `catmull_rom`, not Bezier:
a plain parametric cubic Bézier does **not** interpolate its control points and
can double back in x (making the result not a function `y = f(x)`), so it would
break the user expectation that a dragged breakpoint lies on the curve.
Monotone cubic and Catmull–Rom results are clamped to the endpoint range
(`catmull_rom` may overshoot and is clamped, not left unbounded).

**Parameter binding.** `transfer_fn` is never a bare closure built in a widget;
parameterized built-ins (gamma, sigmoid, exponential) read their parameters from the
`LookUpTable` fields (`gamma`, `sigmoid_k`, `exp_k`) at sample time, so the toolbar
slider mutates a `LookUpTable` and the display path needs no extra plumbing.

### 1b. Built-in grayscale transfer functions

- [ ] **Linear** (current behavior, default).
- [ ] **Sigmoid:** `1 / (1 + exp(-k * (x - center)))` on normalized `x` in [0, 1],
  `center = 0.5` — adjustable steepness `k` (bound to `LookUpTable.sigmoid_k`).
- [ ] **Logarithmic:** `log(1 + x)` normalized.
- [ ] **Exponential:** `exp(k * x)` normalized, with `k` bound to a new
  `LookUpTable.exp_k` field (default 1.0, range 0.1–5.0) — like `gamma` and
  `sigmoid_k`, a transfer-function parameter needs a model field to be
  adjustable from the UI.
- [ ] **Gamma:** `x^gamma` — adjustable gamma (0.1–5.0, bound to
  `LookUpTable.gamma`).
- [ ] **Inverse:** `1 - x` on normalized input. (Written normalized, **not** `255 - x`:
  the engine samples at 256 points on [0, 1] and scales to [0, 255], so a
  `255 - x` formula here would double-scale and produce the wrong range.)
- [ ] Each function maps the [0, 255] post-W/L range to [0, 255]. Every formula
  above is written on **normalized [0, 1] input**; `transfer_fn` is only ever
  called with normalized values, and `lut_engine` owns the single scale to
  [0, 255]. Do not mix byte-range and normalized forms in the same function.

### 1c. Built-in colormaps

- [ ] Leverage matplotlib colormaps (already a dependency):
  - Hot, Cool, Jet, Rainbow, Bone, Gray, Viridis, Magma, Inferno, Plasma, Turbo.
  - Generate `(256, 3)` uint8 arrays at init time using the **current** API —
    `matplotlib.colormaps.get_cmap(name)` (as `src/core/fusion_processor.py:117`
    already does). Do **not** use `matplotlib.cm.get_cmap` / `plt.cm.get_cmap`;
    they were removed in matplotlib 3.9 and the pin is `>=3.11.1`:
    `(matplotlib.colormaps.get_cmap(name)(np.linspace(0, 1, 256))[:, :3] * 255).astype(np.uint8)`.
- [ ] Store as `LookUpTable` instances in a registry (`src/core/lut_catalog.py`).
- [ ] Share the colormap cache/lookup already present in `src/core/fusion_processor.py`
  rather than adding a second matplotlib colormap cache and a second import path.
- [ ] Built-in colormaps stay as pre-sampled `(256, 3)` arrays for performance;
  the control-point representation is the **editable** form for user-defined
  curves (Phase 3b) and the **persisted** form once Phase 4a lands — sampling
  converts between the two.
- [ ] Allow user-defined colormaps from a `.csv` or `.json` file (future — Phase 4).

### 1d. Tests

- [ ] `tests/core/test_lut_engine.py`:
  - Linear LUT matches current `apply_window_level` output.
  - `apply_lut(..., lut=None)` is byte-identical to today (Phase 1 covers
    `apply_lut`; the matching `apply_window_level(..., lut=None)` assertion
    belongs to Phase 2a, once that parameter exists).
  - Sigmoid with high steepness approximates a step function.
  - Gamma=1.0 matches linear.
  - Inverse flips values.
  - Color LUT output is (H,W,3).
  - Edge cases: all-zero image, single-value image.
- [ ] `tests/core/test_lut_curve.py`:
  - Piecewise-linear control points sample exactly between breakpoints.
  - Every interpolation mode passes through each control point; monotone-cubic
    and Catmull–Rom output stays within the endpoint range after clamping.
  - Clamping, duplicate-point rejection, and 256-entry sampling are deterministic.
  - Freehand simplification is deterministic: Ramer–Douglas–Peucker with
    `epsilon = 0.02` in normalized [0, 1] **output-value** space, endpoints
    always pinned to (0, 0) and (1, 1), and a fixed point set simplifying to the
    same points.
  - **Epsilon units guard:** a freehand stroke is a function of *output* value
    (y), so RDP runs on points normalized to [0, 1] in both axes. `epsilon` must
    be a small fraction of that unit range — the geometric bound for any
    point-to-segment distance inside the unit square is `sqrt(2) ≈ 1.414`, so any
    `epsilon >= 1.414` is **degenerate**: no point can ever exceed tolerance,
    every stroke collapses to its two pinned endpoints, and freehand becomes a
    no-op that still passes a naive determinism test. `0.02` (2% of the output
    range) is the starting value; keep it well below 1.414 and add a test that
    asserts a drawn S-curve survives simplification with more than two control
    points, so a degenerate epsilon cannot pass silently again.

---

## Phase 2 — Display pipeline integration

### 2a. Wire LUT into slice display

- [ ] Add `current_lut: LookUpTable` alongside the existing W/L fields in the
  per-series state dict on `ViewStateManager`
  (`src/gui/view_state_manager.py:112` — `series_defaults`, keyed by series
  identifier: "window_center, window_width, zoom, … image_inverted"), and to
  `_user_wl_cache`-style per-series LUT restore.
  `src/core/view_state_handlers.py` is **event glue** (`on_rescale_toggle_changed`,
  `on_reset_all_views`, `update_zoom_wl_status_from_view_state`), not a state
  store — extend it only where a LUT change must fan out to status text/reset.
- [ ] Per-**pane** state (MPR subwindows) is separate: it lives in
  `app.subwindow_data` / `app.subwindow_managers` (see
  `src/core/mpr_navigator_thumbnail.py:57-61`), so "one LUT per pane" is stored
  there, not on the per-series dict. See 2b.
- [ ] **Signature contract:** `apply_window_level()` gains an optional
  `lut: LookUpTable | None = None` parameter **after** the existing
  `rescale_slope` / `rescale_intercept` parameters, and it is **keyword-only**
  (declared after `*`). Today the two five-argument callers pass positionally —
  `src/core/dicom_image_render.py:204-206` and the `DICOMProcessor` wrapper at
  `src/core/dicom_processor.py:127-134`, both
  `apply_window_level(pixel_array, window_center, window_width, rescale_slope,
  rescale_intercept)` — so inserting `lut` in 4th position would silently bind
  a `LookUpTable` to `rescale_slope` at those sites. (The other two call sites,
  `slice_display_pixels.py:110-111` and `export_rendering.py:357-361`, pass
  only three positional arguments and would keep working either way.)
  Keyword-only keeps every existing positional call source- and
  behavior-compatible:
  ```python
  def apply_window_level(
      pixel_array: np.ndarray,
      window_center: float,
      window_width: float,
      rescale_slope: float | None = None,
      rescale_intercept: float | None = None,
      *,
      lut: LookUpTable | None = None,
  ) -> np.ndarray:
  ```
  When `lut` is `None` (or a linear LUT), the output is byte-identical to the
  current linear clamp+normalize. `apply_window_level` then delegates to
  `lut_engine.apply_lut()`.
- [ ] Replace direct calls to `apply_window_level()` with `apply_lut()` in the
  display path (`src/gui/slice_display_manager.py` → `src/core/dicom_processor.py`),
  passing the active LUT from per-pane state.
- [ ] Update the remaining direct callers to pass the active LUT from their own
  state source: `src/core/dicom_image_render.py:204` and
  `src/core/slice_display_pixels.py:110` (projections) — see 2b.
- [ ] When LUT is "Linear" (default), behavior is identical to today.
- [ ] **Unresolved W/L (no windowing) branch — the LUT must still apply.**
  Three display/export paths have a no-windowing fallback, and all three must
  converge on the same post-normalize step: **normalize (or window) to uint8
  first, then apply the LUT** to the normalized 0–255 array. W/L can be
  unresolved because `resolve_window_level_and_rescale()`
  (`src/core/dicom_window_level.py:244`) returns `None` for window center/width
  when the dataset carries no window metadata and none is supplied; in every
  case the parameter is typed `float | None`, so the branch is reachable.
  - `render_grayscale_image()` — windowed at
    `src/core/dicom_image_render.py:204`, **falls back to
    `normalize_to_uint8()` at `:209`**.
  - `create_slice_projection_pil_image()` — windowed at
    `src/core/slice_display_pixels.py:110`, **falls back to an inline
    min/max normalize at `:113-123`**.
  - The export rasterization path (`src/gui/export_rendering.py`, whose
    signature types `window_center`/`window_width` as `float | None` at
    `:287-288`) — windowed at `:357-361`, **falls back to a third inline
    min/max normalize at `:362-368`**. This path duplicates the normalization
    logic rather than calling the shared helper, so it will not pick up a fix
    applied to the other two.

  Routing only the `apply_window_level` path through the LUT engine would
  silently ignore the active LUT for datasets with no window metadata, and
  would produce a LUT-less export for exactly the datasets where it is most
  visible. Specify and test this explicitly; do not let the LUT be reachable
  only via the windowing path. Where practical, de-duplicate the three inline
  normalize blocks into one helper so future fixes apply to all three.
- [ ] **MONOCHROME1 ordering with color LUTs.** Current display polarity is
  applied by `apply_monochrome1_polarity()` (`src/core/photometric_polarity.py:73`)
  **after** W/L and **after** normalization: at `dicom_image_render.py:218` for
  the slice path and `slice_display_pixels.py:123` for projections. That helper
  inverts only 2-D grayscale (`255 - array`, and it returns the array unchanged
  when `array.ndim != 2` — a color array can never be MONOCHROME1). Therefore:
  - **Polarity is applied before the LUT**, to the 2-D grayscale intermediate.
    A grayscale LUT then consumes the correctly-polarized 0–255 array.
  - A color LUT expands to `(H, W, 3)` **after** polarity, so
    `apply_monochrome1_polarity` sees a 2-D array and inverts as today; the
    existing `ndim != 2` guard means a color result is never double-inverted.
  - State this order in the code and the docstrings: `W/L or normalize → uint8
    → MONOCHROME1 polarity → LUT (grayscale or RGB expansion)`.
- [ ] **Where RGB expansion happens.** Both functions already build the PIL image
  from a 2-D array with `Image.fromarray(..., mode='L')`
  (`dicom_image_render.py:222-224`) and from a 3-channel array with
  `mode="RGB"` (`slice_display_pixels.py:129-131`); the MPR/QImage paths convert
  with `QImage.Format_Grayscale8`. A color LUT returns `(H, W, 3)` uint8 and
  must reach those existing RGB branches; the 2-D analysis arrays that
  polarity/photometric-interpretation invariants depend on stay grayscale, so
  expansion is only at the image-construction boundary. Single-slice analysis
  arrays (polarity/photometric-interpretation invariants) stay grayscale — the
  RGB expansion happens at the QImage conversion boundary only.

### 2b. MPR and projection displays

- [ ] Apply the active LUT to MPR panes and AIP/MIP/MinIP projections too.
- [ ] Projections: thread `lut: LookUpTable | None` through
  `src/core/slice_display_pixels.py` → `create_slice_projection_pil_image` and
  pass it at the `apply_window_level` call site (`slice_display_pixels.py:110`).
  Source: `src/core/dicom_projections.py` / `src/core/projection_app_facade.py`
  / `src/gui/intensity_projection_controls_widget.py`.
- [ ] MPR: `src/core/mpr_builder.py` stays **LUT-free**. `MprResult.slices` are raw
  stored-value float32 "consumed only at display time"
  (`mpr_builder.py:101-104`), and `mpr_cache.save(result: MprResult)`
  (`mpr_cache.py:291`) persists exactly what the builder produced — applying the
  LUT at reslice time would bake it into cached arrays, force a cache
  invalidation on every LUT change, and push display work into the builder
  worker thread. Apply the LUT only at the **display/consumption** points,
  alongside the rescale step that already lives there:
  - `get_subwindow_mpr_pixel_array` (`src/core/mpr_navigator_thumbnail.py:32`),
    which already calls `result.apply_rescale(raw)` at `:62-63`;
  - `MprThumbnailWidget`'s internal render (`src/gui/mpr_thumbnail_widget.py:189`,
    `QPixmap.fromImage`);
  - the MPR pane's QImage conversion path.
- [ ] The active LUT for an MPR pane is read from that pane's subwindow state
  (`app.subwindow_data` / `app.subwindow_managers`), falling back to the
  per-series `ViewStateManager` LUT when the pane has no explicit override.
- [ ] 3D volume rendering has its own transfer function system — LUTs here are for 2D display only.

### 2c. Export with LUT

- [ ] PNG/JPG export applies the active LUT (user sees what they exported):
  pass the active LUT at `src/gui/export_rendering.py:357`.
- [ ] DICOM export: store the raw pixel data (no LUT baked in); optionally write a VOI LUT Sequence for non-linear functions, or note in export dialog that LUT is display-only
  (`src/core/mpr_dicom_export.py` for MPR DICOM export).

---

## Phase 3 — UI

### 3a. LUT selector

- [ ] Add a **LUT** dropdown to the toolbar (or to the right-pane controls area):
  - Grouped: **Grayscale** (Linear, Sigmoid, Log, Exp, Gamma, Inverse) | **Color** (Hot, Cool, Jet, …).
  - Icon swatches showing a mini gradient preview for each LUT.
- [ ] Also accessible from **View → Look-Up Table** submenu and from the image context menu.
- [ ] Active LUT is persisted per-pane (so different panes can have different LUTs).
- [ ] The dropdown entry for "Custom…" is present but **disabled/grayed out** until
  the Phase 3b curve editor lands (see sequencing note below) — Phase 3 is
  completable on its own.
- [ ] Display the active/loaded LUT name, source (built-in, file, or custom), and curve/colormap preview; loading a LUT immediately selects it and updates the histogram overlay. (Loading a **saved** LUT depends on Phase 4a persistence; until that ships there is nothing to load from disk, so this bullet covers in-session selection only.)
- [ ] Gamma LUT: show a slider for the gamma parameter (default 1.0) bound to
  `LookUpTable.gamma`, so changing it re-samples and re-renders.

> **Sequencing:** the interactive curve editor is **Phase 3b**, not Phase 4 —
> the selector and the editor ship together so "Custom…" is never a dead entry.
> Phase 4 is reduced to the genuinely deferred items below.

### 3b. Interactive custom curve / colormap editor

- [ ] **New** `src/gui/dialogs/lut_curve_editor_dialog.py`: edit grayscale transfer curves and color colormaps. Add, delete, and drag breakpoints on a graph; draw freehand; switch between straight-line piecewise interpolation and smooth curves (monotone cubic or Catmull–Rom); clamp or snap endpoints to the valid range; preview the result; undo/redo edits. Freehand input simplifies into editable control points (Ramer–Douglas–Peucker, `epsilon = 0.02` in normalized [0, 1] output space, endpoints pinned to (0,0)/(1,1)) rather than becoming a raster-only map. A loaded LUT remains visible in the selector with its name/source and is reopenable here.
- [ ] Gamma / sigmoid parameter controls live in this dialog as well as the toolbar.
- [ ] Live preview uses the same `apply_lut` path as the viewport (no separate preview renderer).

### 3c. Transfer-function display: W/L ramp, LUT, and the composed result

**The pipeline is a composition, not a convolution.** The LUT is a *separate
processing step applied after* window/level, so the mapping a viewer sees is

```
final(x) = LUT(WL(x))          # composition: LUT ∘ W/L
```

where `WL(x)` is today's linear clamp+normalize from the current window
center/width, and `LUT(·)` is the 256-entry table from the active `LookUpTable`.
There is no spatial kernel and no convolution anywhere in this path — the two
stages are independent 1-D functions of intensity, composed by function
application. Every display surface should make that composition visible rather
than showing the LUT alone, because a user who changes W/L under a steep LUT
needs to see which part of the curve moved.

- [ ] Draw all three curves together, painted once in `HistogramWidget`'s paint
  path (`src/tools/histogram_widget.py`) so every host — including
  `src/gui/dialogs/histogram_dialog.py` — inherits them, rather than
  duplicating the overlay per dialog:
  1. **W/L ramp alone** — the plain `WL(x)` diagonal clipped to the current
     window, i.e. the "simple window/level" reference. Neutral gray, dashed.
  2. **LUT alone** — the active LUT's own transfer function over a unit
     (0–255 → 0–255) input range. Saturated, solid. Color LUTs draw a colored
     gradient bar along the x-axis instead of a line.
  3. **Composed result** — `LUT(WL(x))` over the histogram's real x-range:
     the curve the viewport actually applies. Bold, topmost, and the one that
     updates on W/L drags.
  - X-axis = pixel/stored value (or HU if rescaled), Y-axis = output intensity
    (0–255). Linear LUT ⇒ the composed curve coincides with the W/L ramp;
    show a single line rather than two overlapping ones.
  - A legend labels the three curves, and the active LUT name/source appears
    alongside it so the overlay is self-describing.
- [ ] Update the overlay when W/L or LUT changes (W/L drag re-samples the
  composed curve; LUT or gamma change re-samples the LUT and composed curves).
- [ ] The editor (3b) shows the same three-curve arrangement: the edited curve
  is the **LUT (post-W/L)** curve, with the composed result drawn behind it as
  a live preview against the current W/L, so editing stays in LUT space while
  the preview remains in display space.
- [ ] Allow interactive W/L adjustment by dragging the composed curve's
  endpoints (stretch goal).
- [ ] The same three-curve widget is reused for the toolbar dropdown swatches
  and the LUT name/source readout (3a) so there is one implementation.

### 3d. Keyboard shortcut

- [ ] `L` to cycle through LUTs? Or just rely on the toolbar dropdown.
- [ ] Check for conflicts with existing shortcuts.

---

## Phase 4 — Advanced (future)

- [ ] **DICOM Modality LUT Sequence:** Parse `ModalityLUTSequence` (0028,3000) and `VOILUTSequence` (0028,3010) from datasets that embed non-linear LUTs — use them as an additional "From DICOM" option.
- [ ] **Per-series default LUT:** E.g., always use "Hot" for PET, "Bone" for CT.

### 4a. Persistence schema

- [ ] Custom LUTs persist as `custom_luts.json` in the app data directory, via
  `ConfigManager` (`src/utils/config_manager.py`), not ad-hoc files.
- [ ] `LookUpTable` gains `to_dict()` / `from_dict()`. Schema:
  ```json
  {
    "schema_version": 1,
    "luts": [
      {
        "name": "My chest curve",
        "lut_type": "grayscale_ramp",
        "source": "custom",
        "interpolation": "catmull_rom",
        "gamma": null,
        "sigmoid_k": null,
        "exp_k": null,
        "control_points": [[0.0, 0.0], [0.25, 0.18], [0.5, 0.55], [1.0, 1.0]]
      }
    ]
  }
  ```
- [ ] Unknown/missing `interpolation` falls back to `linear`; a LUT that fails
  validation is skipped with a warning rather than aborting app data load.
- [ ] `tests/core/test_lut_persistence.py` (Phase 4a): `to_dict()` /
  `from_dict()` round-trip preserves control points, interpolation, and
  parameters; an unknown `interpolation` falls back to `linear`; an invalid LUT
  is skipped with a warning rather than aborting the load.

---

## Test plan (all phases)

- [ ] **Unit — engine** (`tests/core/test_lut_engine.py`): linear LUT byte-identical
  to `apply_window_level`; `lut=None` unchanged behavior; sigmoid steepness → step;
  `gamma=1.0` == linear; inverse flips; color LUT `(H, W, 3)`; all-zero and
  single-value images.
- [ ] **Unit — curve model** (`tests/core/test_lut_curve.py`): piecewise-linear
  sampling exact between breakpoints; every interpolation mode passes through
  each control point; monotone-cubic and Catmull–Rom stay in the endpoint range
  after clamping; clamping / duplicate-point rejection / 256-entry sampling
  deterministic; RDP simplification (`epsilon = 0.02`, endpoints pinned) is
  deterministic and idempotent.
- [ ] **Unit — composition** (new, `tests/core/test_lut_transfer.py`): the
  composed curve satisfies `composed(x) == LUT(WL(x))` for both a linear and a
  non-linear LUT; a linear LUT's composed curve equals the W/L ramp exactly;
  `composed` is monotonically non-decreasing for a monotone LUT; composition is
  order-sensitive (asserting it is LUT-after-W/L, never W/L-after-LUT).
- [ ] **Regression — display path**: existing slice-display, MPR, projection, and
  export tests stay green with a Linear LUT selected
  (`tests/core/test_mpr_photometric_interpretation.py`,
  `tests/gui/test_mpr_controller_monochrome1.py`, and the projection/export
  image tests) — the polarity and `Format_Grayscale8` invariants are unchanged
  by a default Linear LUT. Add MONOCHROME1 coverage for **both**
  `render_grayscale_image()` and `create_slice_projection_pil_image()` under a
  color LUT, asserting polarity is applied before LUT expansion and the result is
  never double-inverted (`(H, W, 3)` output, not `(H, W)`).
- [ ] **Regression — no-windowing branch**: a dataset with no window metadata
  (so `resolve_window_level_and_rescale()` returns `None` center/width) still
  applies the active LUT after the normalize fallback — for **all three** paths
  (`render_grayscale_image`, `create_slice_projection_pil_image`, and the
  `export_rendering.py` rasterization path) — and the pixel-invariance test
  asserts a non-linear LUT changes the output there too, not only on the
  windowed path. Include the export case, so "user sees what they exported"
  holds for un-windowed datasets too.
- [ ] **Qt/GUI** (`tests/gui/test_lut_curve_editor.py`): breakpoint add/delete/drag;
  freehand draw → simplified control points; interpolation switch; undo/redo;
  gamma slider re-samples; a LUT loaded into the selector keeps its name/source
  and reopens in the editor; the three-curve overlay renders W/L, LUT, and
  composed result and collapses to one line for a Linear LUT. Save/load
  round-trip is covered in Phase 4a (`tests/core/test_lut_persistence.py`).
- [ ] Follow [`dev-docs/info/TESTING_GUIDANCE.md`](../../info/TESTING_GUIDANCE.md)
  tiers; never construct a `QCoreApplication` in a test — use the session `qapp`
  fixture.

---

## Documentation and docstrings

- [ ] **Contract docstrings** on the new/changed public functions —
  `apply_lut()`, `LookUpTable.__post_init__`/`to_dict`/`from_dict`, the
  interpolation and RDP helpers, and `apply_window_level(..., lut=None)` —
  stating the composition order (`LUT ∘ W/L`, applied after window/level, not a
  convolution), the `lut=None` equivalence guarantee, output dtype/shape for
  grayscale vs color, and the accepted parameter ranges (`gamma` 0.1–5.0,
  `sigmoid_k`, `exp_k`).
- [ ] Update the docstring on every signature this plan changes
  (`apply_window_level`, the projection-image builder, `export_rendering`'s
  rasterization entry point, the MPR reslice/thumbnail entry points) so callers
  reading only docstrings know a LUT is applied and where it comes from.
- [ ] **`src/core/photometric_polarity.py` module docstring goes stale and must be
  updated.** `photometric_polarity.py:16-18` currently states the pipeline is
  "modality rescale, then window/level on stored values, then polarity inversion
  **last, on the finalized 8-bit array**" (per PS3.3 C.11.2 and C.7.6.3.1.2's
  "after any VOI gray scale transformations"), and `export_rendering.py:370`
  carries a matching "Polarity last, on the finalized uint8 array" comment.
  With a LUT applied **after** polarity (2a), polarity is no longer last, so
  both must be rewritten to state the new order and to note that the DICOM
  standard's "after any VOI gray scale transformations" is satisfied because
  the LUT is a viewer-side display transform, not a DICOM VOI transformation.
  Do not silently leave a comment that now contradicts the code.
- [ ] **User docs** (`user-docs/`): document the LUT selector, the three-curve
  transfer-function display, the editor, keyboard shortcut, and the explicit
  statement that PNG/JPG export bakes the LUT while DICOM export does not.
  Follow [`dev-docs/plans/DOCUMENTATION_WORKFLOW_AND_FRESHNESS_PLAN.md`](../../DOCUMENTATION_WORKFLOW_AND_FRESHNESS_PLAN.md)
  and run `python scripts/check_user_docs_links.py`.
- [ ] **Dev docs**: refresh
  [`dev-docs/info/PYLINAC_INTEGRATION_OVERVIEW.md`](../../info/PYLINAC_INTEGRATION_OVERVIEW.md)
  only if a DICOM LUT source lands; add a CHANGELOG entry for the user-visible
  feature; keep `dev-docs/TO_DO.md` and the plan status in sync in the same PR.
- [ ] **Manual smoke** steps for the AGENTS.md smoke harness
  (`dev-docs/orchestration/AGENT_SMOKE.md`): select Linear (no visible change),
  select a color LUT (RGB output, correct orientation), open the editor, draw
  freehand, save/reload, and confirm export matches the viewport.

---

## Open questions

1. **Interaction with fusion:** Fusion already uses colormaps for the overlay series. Should the base image LUT apply independently? Probably yes — the fusion overlay has its own color pipeline.
2. **Performance:** Applying a 256-entry LUT to a large image is a vectorized `np.take` — should be fast. Color LUTs require 1→3 channel expansion; measure impact on large images.
3. **DICOM VOI LUT Sequence:** Some DICOM datasets embed non-linear LUTs. Should we automatically use them if present? Recommend: offer as a choice ("From DICOM" in the dropdown).
4. **Overlay text:** Should the overlay show which LUT is active? E.g., "LUT: Sigmoid" or "LUT: Hot". Recommend yes, small text in corner.
5. **Custom curve editing:** Should freehand drawing create a dense point set or simplify into a small set of editable control points? Recommend editable control points, optional freehand sampling, monotone-cubic smoothing, and undo/redo; keep endpoints clamped to the valid range.

---

## Files likely touched

| File | Change |
|------|--------|
| `src/core/lut_engine.py` | **New** — LUT application logic + `LookUpTable` model/validation |
| `src/core/lut_curve.py` | **New** — control-point storage, interpolation, RDP simplification, and 256-entry sampling |
| `src/core/lut_catalog.py` | **New** — built-in LUT registry (shares `fusion_processor` colormap lookup) |
| `src/core/dicom_window_level.py` | Refactor: `apply_window_level(..., lut=None)` delegates to `lut_engine` |
| `src/core/dicom_processor.py` | Pass LUT through processing |
| `src/core/dicom_image_render.py` | Pass active LUT at the direct `apply_window_level` call |
| `src/core/slice_display_pixels.py` | Pass active LUT into AIP/MIP/MinIP projection rendering |
| `src/core/mpr_builder.py` | **Stays LUT-free** — cached `MprResult` slices remain raw stored values |
| `src/core/mpr_navigator_thumbnail.py` | Apply active LUT at display, next to the existing rescale step |
| `src/gui/mpr_thumbnail_widget.py` | Apply active LUT in the thumbnail's internal render |
| `src/gui/slice_display_manager.py` | Use active LUT in display path |
| `src/gui/view_state_manager.py` | Store active LUT per series in `series_defaults` |
| `src/core/view_state_handlers.py` | Event glue only — fan LUT changes out to status text/reset |
| `src/core/view_state_inversion.py` | Respect LUT when inverting |
| `src/gui/main_window_toolbar_builder.py` | LUT dropdown |
| `src/gui/main_window_menu_builder.py` | View → Look-Up Table submenu |
| `src/gui/image_viewer_context_menu.py` | LUT submenu |
| `src/tools/histogram_widget.py` | Three-curve transfer-function overlay: W/L ramp, LUT, composed result |
| `src/gui/dialogs/histogram_dialog.py` | Host the overlay; no duplicate painting |
| `src/gui/widgets/lut_transfer_function_widget.py` | **New** — reusable W/L + LUT + composed curve canvas (histogram overlay, dropdown swatches, editor preview) |
| `src/gui/dialogs/lut_curve_editor_dialog.py` | **New** — interactive custom curve/colormap editor |
| `src/gui/overlay_text_builder.py` | Active LUT label |
| `src/core/photometric_polarity.py` | Update the stale "polarity last" module docstring for the new order |
| `src/gui/export_rendering.py` | Apply LUT on PNG/JPG export (both the windowed and normalize-fallback branches) |
| `src/core/mpr_dicom_export.py` | Keep DICOM export display-only (no baked LUT) |
| `src/utils/config_manager.py` | Persist `custom_luts.json` |
| `tests/core/test_lut_engine.py` | **New** |
| `tests/core/test_lut_curve.py` | **New** — control-point interpolation and sampling |
| `tests/core/test_lut_transfer.py` | **New** — `composed(x) == LUT(WL(x))` composition tests |
| `tests/gui/test_lut_curve_editor.py` | **New** — breakpoint editing, freehand, and loaded-LUT display (Phase 3b) |
| `tests/gui/test_lut_transfer_overlay.py` | **New** — three-curve overlay rendering and Linear collapse |
| `tests/core/test_lut_persistence.py` | **New** — `to_dict`/`from_dict` round-trip and fallback (Phase 4a) |
| `user-docs/` (display + LUT pages) | User documentation for the selector, editor, and overlay |

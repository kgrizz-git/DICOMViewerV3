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

  @dataclass(frozen=True)   # see "Immutability" below before changing this
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
      exp_k: float = 1.0                     # 0.1–5.0, used when transfer_fn is exponential

      def __post_init__(self) -> None:
          """Validate/normalize: sort control points by x, reject duplicate x,
          clamp y to [0, 1], require x strictly increasing in [0, 1], require
          gamma in [0.1, 5.0] when set, sigmoid_k > 0 when set, and
          exp_k in [0.1, 5.0] (defaulting to 1.0) when transfer_fn is
          exponential; require colormap shape (256, 3) uint8 when set."""

**Parameter defaults.** `exp_k` is a plain `float` defaulting to `1.0` (not
`None`), because exponential is always usable and `exp(1.0 * x)` is a
well-defined curve — there is no "unset" state to represent. `gamma` and
`sigmoid_k` stay `float | None`, because `None` is meaningful there: it means
"this parameter does not apply to the selected transfer function".
`__post_init__` validates `exp_k` against `[0.1, 5.0]`, so `lut_engine` can never
sample exponential with an out-of-range or absent value.

  def apply_lut_to_uint8(
      display_array: np.ndarray,   # (H, W) uint8, already windowed/normalized
                                   # and already MONOCHROME1-corrected
      lut: LookUpTable | None = None,
  ) -> np.ndarray:
      """Apply the LUT to an already-displayed uint8 array.

      Returns uint8 (H, W) for a grayscale ramp, or uint8 (H, W, 3) for a
      colormap. ``lut=None`` returns *display_array* unchanged (same object).
      This is the operation every display/export path calls, after
      windowing/normalization and after polarity.
      """

  def apply_lut(
      pixel_array: np.ndarray,
      window_center: float,
      window_width: float,
      rescale_slope: float | None = None,
      rescale_intercept: float | None = None,
      *,
      lut: LookUpTable | None = None,
  ) -> np.ndarray:
      """Convenience: W/L (or normalize), then LUT. Raw-pixel entry point."""
  ```

**Two entry points, because the pipeline has two stages.** Phase 2 requires the
LUT to be applied *after* normalization **and** after MONOCHROME1 polarity, and
that on paths which may have no window/level at all. A single raw-pixel
`apply_lut(pixel_array, wc, ww, ...)` cannot serve that position: calling it at
the post-polarity stage would window the bytes a second time, and calling it
earlier would invert the polarity order. So:

- `apply_lut_to_uint8()` is the **post-normalize, post-polarity** operation, and
  it is the **only** thing the display paths call, exactly once each. Each calls
  it *after* `apply_monochrome1_polarity()`, never before. There are **five**
  such paths — see the canonical inventory below, which every phase and the test
  plan reference rather than restating counts.

> ### Canonical display-path inventory
>
> This table is the single source of truth. Do not restate "four", "three", or
> "fifth" anywhere else; cite the row. Five paths each re-implement
> window/level → polarity → image construction, and each must gain exactly one
> `apply_lut_to_uint8()` call after polarity.
>
> | # | Path | Entry point | No-windowing fallback? | Polarity at |
> |---|------|-------------|------------------------|-------------|
> | 1 | Single-slice pane | `render_grayscale_image`, `src/core/dicom_image_render.py:189` | **Yes** — `normalize_to_uint8()` at `:209` | `:218` |
> | 2 | Projection (AIP/MIP/MinIP) | `create_slice_projection_pil_image`, `src/core/slice_display_pixels.py:38` | **Yes** — inline min/max normalize at `:113-123` | `:123` |
> | 3 | PNG/JPG export | export rasterization, `src/gui/export_rendering.py` | **Yes** — inline min/max normalize at `:362-368` | `:370` |
> | 4 | MPR pane | `array_to_pil`, `src/core/mpr_view_math.py:90` | **No** — takes a non-optional float window, so the branch is unreachable | inside `array_to_pil` |
> | 5 | MPR navigator thumbnail | `MprThumbnailWidget` render, `src/gui/mpr_thumbnail_widget.py:148-161` | **Yes** — inline min/max normalize at `:148-157`, and only windows when `window_width > 0` | `:159-161` |
>
> Rows 1, 2, 3, and 5 have a reachable no-windowing branch; row 4 does not.
> Rows 1, 2, 3, 4, and 5 all need the LUT call. Row 5 is the easiest to miss
> because it is a thumbnail rather than a pane — if it is skipped, the navigator
> keeps a linear appearance while its pane uses the active LUT.
- `apply_lut()` is a **test/one-shot convenience wrapper** over a raw pixel
  array. It performs window/level (or normalize when no W/L) and then calls
  `apply_lut_to_uint8()`. It does **not** apply polarity — it has no
  `photometric_interpretation` parameter and no polarity stage, so it must not
  be used on the display path.

**`apply_window_level()` stays window/level only — it must NOT take a `lut`.**
It is called at `dicom_image_render.py:204`, *before* the polarity call at
`:218`, so a `lut` parameter there would apply the LUT before polarity and
silently invert the required order. Drop the `lut` parameter from
`apply_window_level` entirely; the display paths call `apply_lut_to_uint8()`
after polarity instead. (If a `lut` keyword is kept on it for compatibility, it
must be documented as test-only and must never be passed from a display path.)

Keep the two operations as separate named functions rather than one function
with an `already_normalized` flag, so the call sites make the stage explicit.

`lut` is optional from Phase 1 so the engine is testable on its own, before
Phase 2 threads it through the display path.

Custom curves are first-class data, not a raster-only editor state: keep ordered
control points plus an interpolation mode in the LUT model, then sample them to
a 256-entry LUT for the fast display path. The editor, histogram overlay, and
persistence format should all share this representation.

**Interpolation choices.** `linear`, `monotone_cubic` (Fritsch–Carlson), and
`catmull_rom` all pass through every control point. Smooth mode uses
`catmull_rom`, not Bézier: a plain parametric cubic Bézier does **not**
interpolate its control points and can double back in x, so it would break the
user expectation that a dragged breakpoint lies on the curve. Verified: a cubic
Bézier through `(0,0), (0.2,1), (0.8,1), (1,0)` evaluates to `[0.5, 0.75]` at
`t = 0.5`, matching neither interior point.

**All three modes must be univariate splines in `x`** — evaluated as
`y = f(x)` per interval, never as a parametric curve through the `(x, y)` pairs.
A *parametric* `(x, y)` Catmull–Rom still hits the knots but is not a function:
on `(0,0), (0.05,0.2), (0.1,0.8), (1,1)` the sampled `x` decreased on **27**
sampled steps. The Bézier objection above applies equally to it.

**Clamping: only Catmull–Rom needs it, and only to `[0, 1]`.** Do **not** clamp
to the first/last `y` span:
- Fritsch–Carlson's guarantee is "no new extrema" — it stays inside the
  control-point y-range. On `(0, 0.2), (0.5, 0.9), (1, 0.3)` it spans
  `[0.2, 0.9]` and legitimately goes outside the first/last span `[0.2, 0.3]`.
  Clamping to `[0.2, 0.3]` would flatten the interior peak and pull the curve
  off the control points.
- Catmull–Rom may overshoot. On the spike `(0,0), (0.25,0), (0.5,1), (0.75,0),
  (1,0)` it reaches about **−0.074**, and on the non-monotone set above about
  `0.9005`. Clamping its samples to `[0, 1]` is correct: control-point `y` is
  already constrained to [0, 1] by `__post_init__`, so no control point moves,
  and the uint8 output stays valid.

The earlier "clamped to the endpoint range" wording was wrong for exactly this
reason — endpoint-range clamping and "passes through every control point" are
mutually exclusive on a non-monotone curve.

**Parameter binding.** `transfer_fn` is never a bare closure built in a widget;
parameterized built-ins (gamma, sigmoid, exponential) read their parameters from the
`LookUpTable` fields (`gamma`, `sigmoid_k`, `exp_k`) at sample time, so the
display path needs no extra plumbing.

**Immutability — `LookUpTable` is frozen, so nothing mutates one.** A slider
does **not** assign to a live LUT: it builds a replacement with
`dataclasses.replace(lut, gamma=new_value)`. Two consequences to honor:

- Do **not** write "the slider mutates a `LookUpTable`" anywhere. On a frozen
  dataclass that raises `FrozenInstanceError` at runtime.
- `__post_init__` normalizes `control_points` (sorts by x, rejects duplicate x,
  clamps y). A frozen dataclass forbids plain assignment, so that normalization
  must go through `object.__setattr__` inside `__post_init__` — state that
  explicitly in the method's docstring, or a reviewer will "fix" it into an
  `AttributeError`.

Frozen is the right choice here: LUTs are shared across panes and the MPR cache,
so a LUT that could be mutated in place would let one pane's gamma change another
pane's rendering without a state round-trip. Prefer
`@dataclass(frozen=True)`; if v1 genuinely needs in-place parameter updates, drop
`frozen` **and** say so here, because the immutability assumption is load-bearing
for the shared-LUT design.

### 1b. Built-in grayscale transfer functions

- [ ] **Linear** (current behavior, default).
- [ ] **Sigmoid:** `1 / (1 + exp(-k * (x - center)))` on normalized `x` in [0, 1],
  `center = 0.5` — adjustable steepness `k` (bound to `LookUpTable.sigmoid_k`).
- [ ] **Logarithmic:** `log(1 + x) / log(2)` on [0, 1]. The explicit divisor is
  required: raw `log(1 + x)` ends at `log(2) ≈ 0.693`, not 1. (Divide-by-max
  happens to be the same divisor here, because the minimum is already 0.)
- [ ] **Exponential:** `(exp(k * x) - 1) / (exp(k) - 1)` on [0, 1], with `k`
  bound to a new `LookUpTable.exp_k` field (default 1.0, range 0.1–5.0) — like
  `gamma` and `sigmoid_k`, a transfer-function parameter needs a model field to
  be adjustable from the UI. **The affine form is required, not
  `exp(k*x)/exp(k)`:** dividing by the maximum pins only `x = 1` and leaves
  `x = 0` at `exp(-k)` (0.905 at k=0.1, 0.368 at k=1, 0.0067 at k=5), so the
  curve would never reach black.
- [ ] **Gamma:** `x^gamma` — adjustable gamma (0.1–5.0, bound to
  `LookUpTable.gamma`).
- [ ] **Inverse:** `1 - x` on normalized input. (Written normalized, **not** `255 - x`:
  the engine samples at 256 points on [0, 1] and scales to [0, 255], so a
  `255 - x` formula here would double-scale and produce the wrong range.)
- [ ] **Sigmoid is the one exception to full-range coverage** — see below.
- [ ] **The `[0, 1] → [0, 255]` scale uses round-to-nearest, never truncation.**
  `(1 - i/255) * 255` carries float error of about ±2.84e-14, so
  `.astype(np.uint8)` (which truncates) misses **50 of 256** codes by one level
  (byte 43 → 211 instead of 212, byte 59 → 195 instead of 196), while
  `np.rint` misses **zero**. Identity `(i/255) * 255` truncates exactly, so a
  `gamma = 1.0` equality test cannot catch this — the inverse LUT is the test
  that exposes it. Use `np.rint(values * 255).astype(np.uint8)` (or
  `np.clip(np.rint(...), 0, 255)`) in `lut_engine`, and add a regression test
  asserting the inverse LUT is exactly `lut[i] == 255 - i` for all 256 codes.
  Note this is distinct from MONOCHROME1 polarity, which legitimately does
  `255 - array` on an already-uint8 array at a later stage.
- [ ] Every formula above is written on **normalized [0, 1] input**; `transfer_fn`
  is only ever called with normalized values, and `lut_engine` owns the single
  scale to [0, 255]. Do not mix byte-range and normalized forms in one function.
- [ ] **Sigmoid does not map [0, 1] onto [0, 1] and must not claim to.** With
  `center = 0.5`, `y(0.5) = 0.5` for every `k`, but the endpoints are
  `0.378 / 0.622` at `k = 1` and `0.076 / 0.924` at `k = 5` — a sigmoid never
  reaches pure black or pure white. **Use the endpoint renormalization**
  `(s(x) - s(0)) / (s(1) - s(0))`, which pins both ends to 0 and 1 and keeps
  `y(0.5) = 0.5`; the raw logistic is *not* an acceptable alternative, because
  the two are different LUTs and leaving the choice open would let an
  implementation ship either one. Note `sigmoid_k` is only
  constrained `> 0`, **not** `[0.1, 5.0]` like `gamma`/`exp_k` — keep the three
  ranges stated consistently wherever they appear. No overflow cap is needed:
  `k = 2000` returns finite `[0.0, 0.5, 1.0]` in both float32 and float64.

### 1c. Built-in colormaps

- [ ] Leverage matplotlib colormaps (already a dependency):
  - `hot`, `cool`, `jet`, `rainbow`, `bone`, `gray`, `viridis`, `magma`,
    `inferno`, `plasma`, `turbo` — **lowercase registry keys only.** Every
    title-case form raises `ValueError` in the installed matplotlib 3.11.1
    (`get_cmap("Hot")` and `get_cmap("Gray")` both fail). Use `gray`, **not**
    `Gray` and not `Greys` — `Greys` is a different map.
  - Generate `(256, 3)` uint8 arrays at init time using the **current** API —
    `matplotlib.colormaps.get_cmap(name)` (as `src/core/fusion_processor.py:117`
    already does). `matplotlib.cm.get_cmap` is **absent** in the installed
    3.11.1 (`hasattr(matplotlib.cm, "get_cmap")` is `False`) and the pin is
    `>=3.11.1`:
    `(matplotlib.colormaps.get_cmap(name)(np.linspace(0, 1, 256))[:, :3] * 255).astype(np.uint8)`.
    Verified: yields shape `(256, 3)` uint8, and truncation matches
    `cmap(..., bytes=True)` exactly (max abs difference 0) — so the
    `* 255).astype(np.uint8)` idiom is fine *for colormaps*, unlike the
    inverse transfer function in 1b.
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
  - `apply_lut(..., lut=None)` and `apply_lut_to_uint8(arr, None)` are
    byte-identical to today.
  - Sigmoid with high steepness approximates a step function, **and with the
    endpoint renormalization of 1b returns exactly 0 and 1 at the endpoints**
    (`lut[0] == 0`, `lut[255] == 255`) at every `k`, with `y(0.5) == 0.5`.
  - Gamma=1.0 matches linear.
  - **Inverse is exactly `lut[i] == 255 - i` for all 256 codes.** This is the
    test that catches a truncating scale — a `gamma = 1.0` test cannot, because
    identity truncates exactly (0 mismatches either way).
  - Log and exponential both return exactly 0 and 1 at the endpoints
    (`lut[0] == 0`, `lut[255] == 255`); a divide-by-max exponential fails this.
  - Color LUT output is (H,W,3).
  - Edge cases: all-zero image, single-value image.
- [ ] `tests/core/test_lut_curve.py`:
  - Piecewise-linear control points sample exactly between breakpoints.
  - Every interpolation mode passes through each control point, evaluated as a
    **univariate** spline in `x` (not parametric).
  - Fritsch–Carlson introduces **no new extrema** — its output stays within the
    control-point y-range — and needs no clamp. Assert that on a non-monotone
    set such as `(0, 0.2), (0.5, 0.9), (1, 0.3)`, where staying inside the
    first/last span `[0.2, 0.3]` would be *wrong*.
  - Catmull–Rom **may** overshoot (about −0.074 on the spike
    `(0,0), (0.25,0), (0.5,1), (0.75,0), (1,0)`) and is clamped to `[0, 1]`;
    assert no output leaves [0, 1] and that every control point is still hit.
  - Clamping, duplicate-point rejection, and 256-entry sampling are deterministic.
  - Freehand simplification is deterministic: Ramer–Douglas–Peucker with
    `epsilon = 0.02` in normalized [0, 1] **output-value** space, endpoints
    always pinned to (0, 0) and (1, 1), and a fixed point set simplifying to the
    same points.
  - **Epsilon units guard:** a freehand stroke is a function of *output* value
    (y), so RDP runs on points normalized to [0, 1] in both axes. `epsilon` must
    be a small fraction of that unit range. The relevant bound is **not** the
    `sqrt(2) ≈ 1.414` diagonal: RDP's first chord is the segment between the
    pinned endpoints `(0,0)` and `(1,1)`, i.e. the diagonal, and the maximum
    perpendicular distance to it is `|x - y| / sqrt(2)`, peaking at
    **`1/sqrt(2) ≈ 0.707`** at the opposite corners. So `epsilon >= 0.707` is
    already degenerate (an 81-point S-curve collapses to 2 points at 0.707, 1.0,
    1.414, and 2.0 alike) — stating the looser `sqrt(2)` bound would miss it.
    `epsilon` must stay well below `0.707`, or every stroke collapses to its two
    pinned endpoints and freehand becomes a no-op that still passes a naive
    determinism test.
    `0.02` is the starting value. Measured behavior: an 81-point S-curve (max
    perpendicular `0.104`) keeps **6** points at `0.02` and 4 at `0.05`; a `+0.03`
    vertical bump (perpendicular `0.021`) survives, while a `+0.02` bump
    (`0.014`) and a 1.5% sine (`0.011`) are dropped — i.e. it discards wiggles
    under roughly 7 gray levels, which is a reasonable freehand tolerance. Note
    the perpendicular is measured against the diagonal, so the *vertical* motion
    needed to survive is about `0.02 * sqrt(2) ≈ 0.028`, not 2%. RDP is
    idempotent (re-running on its own output is a no-op). Add a test asserting a
    drawn S-curve survives with more than two control points, so a degenerate
    epsilon cannot pass silently again.

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
- [ ] **`apply_window_level()` keeps its existing signature and gains NO `lut`
  parameter.** It is called at `dicom_image_render.py:204`, *before* the polarity
  call at `:218`, so a `lut` here would apply the LUT before polarity and invert
  the required order. The LUT is applied afterwards by calling
  `apply_lut_to_uint8()` directly. This also sidesteps the positional-argument
  hazard entirely: the two five-argument callers (`dicom_image_render.py:204-206`
  and the `DICOMProcessor` wrapper at `dicom_processor.py:127-134`) pass
  `rescale_slope` / `rescale_intercept` **positionally**, so any new parameter
  inserted in 4th position would silently bind a `LookUpTable` to
  `rescale_slope` at those sites. (The other two call sites,
  `slice_display_pixels.py:110-111` and `export_rendering.py:357-361`, pass only
  three positional arguments.) The signature stays unchanged:
  ```python
  def apply_window_level(
      pixel_array: np.ndarray,
      window_center: float,
      window_width: float,
      rescale_slope: float | None = None,
      rescale_intercept: float | None = None,
  ) -> np.ndarray:
  ```
- [ ] Keep the `apply_window_level()` call as-is in the display path
  (`src/gui/slice_display_manager.py` → `src/core/dicom_processor.py`), and call
  `apply_lut_to_uint8(active_lut)` on its result **after** polarity, with the
  active LUT taken from per-pane state.
- [ ] Update the remaining direct callers so each **threads the active LUT from
  their own state source into the image builder** and calls
  `apply_lut_to_uint8()` there, **after** polarity — not by passing a LUT to
  `apply_window_level()`: `src/core/dicom_image_render.py:204` and
  `src/core/slice_display_pixels.py:110` (projections) — see 2b.
- [ ] When LUT is "Linear" (default), behavior is identical to today.
- [ ] **Unresolved W/L (no windowing) branch — the LUT must still apply.**
  **Four** of the five inventory rows have a reachable no-windowing fallback
  (rows 1, 2, 3, and 5; row 4 does not), and all four must converge on the same
  post-normalize step: **normalize (or window) to uint8 first, then polarity,
  then the LUT** on the resulting 0–255 array. W/L can be
  unresolved because `resolve_window_level_and_rescale()`
  (`src/core/dicom_window_level.py:244`) returns `None` for window center/width
  when the dataset carries no window metadata and none is supplied; in every
  case the parameter is typed `float | None` (or the guard checks for it), so
  the branch is reachable.
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
    applied to the others.
  - `MprThumbnailWidget`'s render (`src/gui/mpr_thumbnail_widget.py:148-157`) —
    windowed only when `window_center`/`window_width` are set **and**
    `window_width > 0`, **falls back to a fourth inline min/max normalize
    otherwise**, then applies polarity at `:159-161`. Easy to miss because the
    widget is a thumbnail rather than a pane. Consequence if skipped: the MPR
    thumbnail keeps a linear appearance while its pane uses the active LUT, so
    the navigator no longer previews what the pane shows.
  - (`mpr_view_math.array_to_pil`, `src/core/mpr_view_math.py:90`, is a fifth
    window/level path but takes a non-optional float window, so it has **no**
    no-windowing branch — it is counted in the four-way display-path list, not
    here.)

  Routing only the `apply_window_level` path through the LUT engine would
  silently ignore the active LUT for datasets with no window metadata, and
  would produce a LUT-less export for exactly the datasets where it is most
  visible. Specify and test this explicitly; do not let the LUT be reachable
  only via the windowing path. Where practical, de-duplicate the four inline
  normalize blocks into one helper so future fixes apply to all of them.
- [ ] **The user "invert" flag is a second `255 - array`, and it must move.**
  `src/core/view_state_inversion.py` only *reports* the flag (it returns a bool
  from the per-series `image_inverted` default); the pixels are actually
  inverted in `src/gui/image_viewer_view.py:403-415`, which does `255 - array`
  for mode `'L'` and for `'RGB'` (and converts to RGB first for any other mode)
  on the **finished PIL image** produced by the render path at `:441`/`:485`.
  Once the LUT is inside that render, this invert runs *after* it, which is
  wrong: inverting a non-linear curve flips an already-shaped transfer function
  rather than inverting the display mapping, and on a **color LUT** it negates
  every channel independently (turning `hot` into a negative-looking map).
  Therefore: apply the user-invert flag to the **2-D grayscale array at the
  same stage as MONOCHROME1 polarity — before `apply_lut_to_uint8()`** — and
  remove the post-render inversion from `image_viewer_view`. The two inversions
  compose (`255 - (255 - u) == u`) when both are active, so a dataset that is
  both MONOCHROME1 and user-inverted is simply un-inverted; keep that behavior
  explicit and tested. `view_state_inversion.py` itself needs no change beyond
  being named as the flag's source of truth.
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
  - **Keep an explicit stage boundary before `apply_lut_to_uint8()`.** The
    ordering above must be structural, not a convention that a later edit can
    quietly reorder: the polarity call
    (`apply_monochrome1_polarity(processed_array, photometric_interpretation)`)
    must remain a distinct, completed step *before* the LUT is applied, at all
    four display/export sites. Do not fold polarity into the LUT engine, do not
    apply it to the LUT's RGB output, and do not reorder it to run last. If it
    helps, name the two phases explicitly (e.g. a `_to_display_uint8` /
    `_apply_active_lut` step pair) so the boundary is visible at each call site
    and greppable in review. A non-linear grayscale LUT is the case that breaks first: applying
    polarity after it would invert an already-shaped curve, and for a color LUT
    it would silently no-op on the `ndim != 2` guard.
- [ ] **Where RGB expansion happens.** Both projection functions already build the
  PIL image from a 2-D array with `Image.fromarray(..., mode='L')`
  (`dicom_image_render.py:222-224`) and from a 3-channel array with
  `mode="RGB"` (`slice_display_pixels.py:129-131`). The QImage side is **not**
  uniformly grayscale-only, so audit each consumer rather than assuming:
  `src/gui/image_viewer_view.py:531-544` already branches on the PIL image mode
  and emits `Format_Grayscale8` for `'L'` and `Format_RGB888` for `'RGB'`, while
  `src/gui/mpr_thumbnail_widget.py:180-186` hardcodes
  `QImage.Format.Format_RGB888` with a `3 * _THUMBNAIL_SIZE` stride.
  A color LUT returns `(H, W, 3)` uint8 and must reach the existing RGB
  branches; the 2-D analysis arrays that polarity/photometric-interpretation
  invariants depend on stay grayscale, so expansion happens only at the
  image-construction boundary.
- [ ] **Always pass an explicit `bytesPerLine`, and keep it equal to the actual
  buffer layout.** Verified behavior for `QImage` in this repo's PySide6:
  - When **QImage allocates** the buffer (`QImage(w, h, Format_RGB888`), it
    rounds `bytesPerLine` **up** to a 4-byte multiple — a width of 63 yields
    192, not 189.
  - When the **caller supplies** the buffer and an explicit `bytesPerLine`, QImage
    honors that value verbatim and reads rows correctly even when it is not
    4-byte aligned (a width-5 RGB888 image with a 15-byte stride reads back
    correctly).
  So a `width * 3` stride is *not* inherently broken, and padding is a
  defensive choice rather than a Qt correctness requirement. The real invariant
  to protect is **consistency**: the `bytesPerLine` passed must match the stride
  the source buffer was actually packed with, and the backing `bytes` must stay
  alive for the `QImage`'s lifetime (the existing `self._img_bytes_ref` /
  `self._display_bytes_ref` pattern already does this — preserve it on every new
  path). A mismatch is what produces skewed rows, and it can creep in if a
  consumer later `copy()`s, converts, or concatenates the image and assumes
  QImage's own 4-byte-rounded stride. **`copy()` repacks to a 4-byte-rounded
  stride**: `img.copy()` on a stride-15 image reports `bytesPerLine` 16, so
  reads after a `copy()`/`convertToFormat`/concatenate must use the **new**
  image's `bytesPerLine()`. On a width-5 image with row 1 `(11, 22, 33)`,
  reading the copy at 16 returns `[11, 22, 33]` and at 15 returns
  `[0, 11, 22]`. `QPixmap.fromImage()` also converts RGB888 to RGB32, so a
  pixmap round-trip changes format and stride again. Pick one convention per
  call site, pass it explicitly, and keep the two in sync. Grayscale 8-bit paths keep
  `width * 1` and `Format_Grayscale8` unchanged.

### 2b. MPR and projection displays

- [ ] Apply the active LUT to MPR panes and AIP/MIP/MinIP projections too.
- [ ] Projections: thread `lut: LookUpTable | None` through
  `src/core/slice_display_pixels.py` → `create_slice_projection_pil_image` and
  call `apply_lut_to_uint8()` on its result **after** the
  `apply_monochrome1_polarity` call (`slice_display_pixels.py:123`). Do **not**
  pass a LUT to `apply_window_level()` at `slice_display_pixels.py:110` — that
  function no longer takes one, and applying it there would invert the curve
  before polarity. Source: `src/core/dicom_projections.py` /
  `src/core/projection_app_facade.py`
  / `src/gui/intensity_projection_controls_widget.py`.
- [ ] MPR: `src/core/mpr_builder.py` stays **LUT-free**. `MprResult.slices` are raw
  stored-value float32 "consumed only at display time"
  (`mpr_builder.py:101-104`), and `mpr_cache.save(result: MprResult)`
  (`mpr_cache.py:291`) persists exactly what the builder produced — applying the
  LUT at reslice time would bake it into cached arrays, force a cache
  invalidation on every LUT change, and push display work into the builder
  worker thread.
- [ ] **Split measurement space from display space in the MPR accessor — this is
  the highest-risk item in the plan.** `get_subwindow_mpr_pixel_array()`
  (`src/core/mpr_navigator_thumbnail.py:32`) has *two* consumers with opposite
  requirements:
  - **Measurement:** `subwindow_manager_factory.py:164` passes it as
    `get_mpr_pixel_array` into the ROI coordinator, and
    `roi_coordinator._get_pixel_array_for_statistics()` (`src/gui/roi_coordinator.py:260`)
    returns it for ROI statistics. It must stay in **raw/rescaled measurement
    space** (rescale applied, no windowing, no polarity, no LUT).
  - **Display:** the same function feeds the navigator thumbnail
    (`mpr_navigator_thumbnail.py:111`), which is a display consumer.

  Applying a display LUT inside this shared getter would silently replace
  measurement values with 8-bit display values, so ROI statistics on MPR panes
  would report windowed, polarity-inverted, LUT-shaped numbers — a
  clinically-significant correctness bug with no error message. Therefore:
  - Keep the measurement accessor in measurement space (renaming it or adding a
    `get_subwindow_mpr_measurement_array()` is fine — **do not** add display
    transforms to the accessor ROI statistics uses).
  - Add a separate **display-space** accessor, or apply the transform at the
    image-construction sites, where W/L + polarity + LUT are applied in that
    order.
- [ ] **All five inventory paths need the LUT, not just the panes.** The W/L →
  polarity → image sequence is re-implemented once per row of the canonical
  inventory in 1a. Row 4 (`array_to_pil`, `src/core/mpr_view_math.py:90`)
  re-implements linear W/L inline ("`out = clip((val - (wc - ww/2)) / ww * 255,
  0, 255)`") and calls `apply_monochrome1_polarity` itself so "MPR panes agree
  with the single-slice viewer"; row 5 is the thumbnail and is the easiest to
  miss. Every row must route through the same normalize/window → polarity → LUT
  order, and the duplicated inline logic should ideally be collapsed onto shared
  helpers so a future fix cannot reach only some of them.
- [ ] The active LUT for an MPR pane is read from that pane's subwindow state
  (`app.subwindow_data` / `app.subwindow_managers`), falling back to the
  per-series `ViewStateManager` LUT when the pane has no explicit override.
- [ ] 3D volume rendering has its own transfer function system — LUTs here are for 2D display only.

### 2c. Export with LUT

- [ ] PNG/JPG export applies the active LUT (user sees what they exported):
  thread the active LUT into the export rasterization builder and call
  `apply_lut_to_uint8()` **after** its `apply_monochrome1_polarity` call
  (`export_rendering.py:370`), on both the windowed branch (`:357-361`) and the
  normalize fallback (`:362-368`). Do **not** pass a LUT to
  `apply_window_level()` at `:357`.
- [ ] DICOM export: store the raw pixel data (no LUT baked in); optionally write a VOI LUT Sequence for non-linear functions, or note in export dialog that LUT is display-only
  (`src/core/mpr_dicom_export.py` for MPR DICOM export).

---

## Phase 3 — UI

### 3a. LUT selector

- [ ] Add a **LUT** dropdown to the toolbar (or to the right-pane controls area):
  - Grouped: **Grayscale** (Linear, Sigmoid, Log, Exp, Gamma, Inverse) | **Color** (Hot, Cool, Jet, …).
  - Icon swatches showing a mini gradient preview for each LUT.
- [ ] Also accessible from **View → Look-Up Table** submenu and from the image context menu.
- [ ] Active LUT is persisted per-pane (so different panes can have different
  LUTs). Because `LookUpTable` is frozen, persisting means storing the LUT (or
  its `custom_luts.json` key) in the pane's state and handing out replacements —
  never mutating a LUT that another pane or the MPR cache may still hold.
- [ ] The dropdown entry for "Custom…" is present but **disabled/grayed out** until
  the Phase 3b curve editor lands (see sequencing note below) — Phase 3 is
  completable on its own.
- [ ] Display the active/loaded LUT name, source (built-in, file, or custom), and curve/colormap preview; loading a LUT immediately selects it and updates the histogram overlay. (Loading a **saved** LUT depends on Phase 4a persistence; until that ships there is nothing to load from disk, so this bullet covers in-session selection only.)
- [ ] Gamma LUT: show a slider for the gamma parameter (default 1.0) bound to
  `LookUpTable.gamma`, so changing it re-samples and re-renders.

> **Sequencing:** the interactive curve editor is **Phase 3b**, not Phase 4 —
> the selector and the editor ship together so "Custom…" is never a dead entry.
> Phase 4 is reduced to the genuinely deferred items below.

### 3b. Interactive custom curve editor (grayscale curves first)

- [ ] **New** `src/gui/dialogs/lut_curve_editor_dialog.py`: edit **grayscale transfer curves**. Add, delete, and drag breakpoints on a graph; draw freehand; switch between straight-line piecewise interpolation and smooth curves (monotone cubic or Catmull–Rom); clamp or snap endpoints to the valid range; preview the result; undo/redo edits. Freehand input simplifies into editable control points (Ramer–Douglas–Peucker, `epsilon = 0.02` in normalized [0, 1] output space, endpoints pinned to (0,0)/(1,1)) rather than becoming a raster-only map. A loaded LUT remains visible in the selector with its name/source and is reopenable here.
- [ ] Gamma / sigmoid / exponential parameter controls live in this dialog as well as
  the toolbar, bound to `LookUpTable.gamma` / `sigmoid_k` / `exp_k`.
- [ ] Live preview goes through the same `apply_lut_to_uint8()` call the viewport uses,
  on the already-windowed **and polarity-corrected** array — not `apply_lut()` —
  so the preview cannot diverge from the pane. No separate preview renderer.
- [ ] **Editing *color* colormaps is explicitly out of scope for v1 and is deferred
  to Phase 4b.** The current `control_points` model is a list of `(x, y)` scalar
  pairs, which describes a grayscale intensity ramp only — it cannot represent
  an RGB color stop, and the persistence schema stores no color data either.
  Promising "edit grayscale transfer curves and color colormaps" in 3b while
  specifying only a scalar control-point model would ship a selector entry that
  cannot do what it claims. So: v1's editor edits grayscale curves, and
  built-in color LUTs remain read-only pre-sampled `(256, 3)` arrays (selectable
  and previewable, just not editable).

### 3c. Transfer-function display: W/L ramp, LUT, and the composed result

**The pipeline is a composition, not a convolution.** The LUT is a *separate
processing step applied after* window/level, so the mapping a viewer sees is

```
final(x) = LUT(P(WL(x)))       # composition: LUT ∘ P ∘ W/L
```

where `P` is **MONOCHROME1 polarity** — the identity for MONOCHROME2 and
`255 - u` for MONOCHROME1. `WL(x)` is today's linear clamp+normalize from the
current window
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
  3. **Composed result** — `LUT(P(WL(x)))` over the histogram's real x-range:
     the curve the viewport actually applies. Bold, topmost, and the one that
     updates on W/L drags. **This must be polarity-aware**, or the overlay
     misrepresents MONOCHROME1 images: for those the composed curve is
     `LUT(255 - WL(x))`, which is a *different* curve from the MONOCHROME2
     `LUT(WL(x))` for the same W/L and LUT. Read the dataset's
     `photometric_interpretation` and apply `P` when sampling the composed
     trace; do not draw the MONOCHROME2 formula for a MONOCHROME1 series.
  - X-axis = pixel/stored value (or HU if rescaled), Y-axis = output intensity
    (0–255). Linear LUT **and MONOCHROME2** ⇒ the composed curve coincides with
    the W/L ramp, so draw a single line rather than two overlapping ones. For
    MONOCHROME1 the ramp and composed curve legitimately differ even with a
    Linear LUT (the composed one is the inverted ramp), so draw both and let the
    polarity do the explaining.
  - A legend labels the three curves, and the active LUT name/source appears
    alongside it so the overlay is self-describing.
- [ ] Update the overlay when W/L or LUT changes (W/L drag re-samples the
  composed curve; LUT or gamma change re-samples the LUT and composed curves).
- [ ] The editor (3b) shows the same three-curve arrangement: the edited curve
  is the **LUT (post-polarity)** curve, with the polarity-aware composed result
  drawn behind it as a live preview against the current W/L, so editing stays in
  LUT space while the preview remains in display space. The preview must go
  through the same `apply_lut_to_uint8()` call the viewport uses — **not**
  `apply_lut()` — so it cannot diverge from what the pane shows.
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
        "exp_k": 1.0,
        "control_points": [[0.0, 0.0], [0.25, 0.18], [0.5, 0.55], [1.0, 1.0]]
      }
    ]
  }
  ```
- [ ] The 256 samples are at **`x = i / 255` for `i = 0..255`**
  (`linspace(0, 1, 256)`, which matches `i/255` to ~1e-16). A control point at
  `x = 0.25` is therefore **not** itself a table abscissa (`63/255 ≈ 0.24706`,
  `64/255 ≈ 0.25098`): the piecewise-linear *function* passes through it exactly,
  but the nearest stored sample can differ **arbitrarily** in `y` when the curve
  is steep there — e.g. control points `(0,0), (0.25,1), (0.26,0), (1,0)` give a
  nearest abscissa of `64/255` whose interpolated `y ≈ 0.902`, a difference of
  ~0.098, far beyond the `0.5/255 ≈ 0.00196` half-step in *x*. Tests must
  evaluate the interpolant at `i/255`, not assert that a control point's `y`
  appears verbatim in the table.
- [ ] Unknown/missing `interpolation` falls back to `linear`; a missing or null
  `exp_k` maps to the `1.0` default; a LUT that fails validation is skipped with
  a warning rather than aborting app data load.
- [ ] `tests/core/test_lut_persistence.py` (Phase 4a): `to_dict()` /
  `from_dict()` round-trip preserves control points, interpolation, and
  parameters; an unknown `interpolation` falls back to `linear`; an invalid LUT
  is skipped with a warning rather than aborting the load.

### 4b. Editable color colormaps (deferred)

- [ ] **Color stop model:** add an RGB(A) color-stop representation to
  `LookUpTable` — e.g. `color_stops: tuple[tuple[float, tuple[int, int, int]], ...]`
  keyed on input position, plus a `color_interpolation` mode (`linear` in RGB
  space, or a perceptual space). Sample to the same `(256, 3)` uint8 array the
  fast path already consumes, so `apply_lut_to_uint8()` needs no special case.
- [ ] **Editor support:** a color-gradient editing surface (add/move/delete
  stops, pick RGB, smooth vs stepped between stops) in the same dialog, kept
  clearly separate from the grayscale curve surface rather than overloading
  `(x, y)` breakpoints.
- [ ] **Persistence:** extend the `custom_luts.json` schema with a
  `"color_stops"` array and bump `schema_version`; `from_dict()` must accept the
  v1 grayscale-only shape unchanged.

---

## Test plan (all phases)

- [ ] **Unit — engine** (`tests/core/test_lut_engine.py`): linear LUT byte-identical
  to `apply_window_level`; `lut=None` unchanged behavior; sigmoid steepness → step;
  `gamma=1.0` == linear; inverse flips; color LUT `(H, W, 3)`; all-zero and
  single-value images.
- [ ] **Unit — curve model** (`tests/core/test_lut_curve.py`): piecewise-linear
  sampling exact between breakpoints; every interpolation mode passes through
  each control point as a **univariate** spline in `x`; Fritsch–Carlson
  introduces **no new extrema** (stays within the control-point y-range) and
  needs no clamp; Catmull–Rom **may** overshoot and is clamped to `[0, 1]` only
  — do **not** assert "stays in the endpoint range", which is wrong for
  non-monotone control points and contradicts the Phase 1 rule; clamping /
  duplicate-point rejection / 256-entry sampling deterministic; RDP
  simplification (`epsilon = 0.02`, endpoints pinned) is deterministic and
  idempotent.
- [ ] **Unit — composition** (new, `tests/core/test_lut_transfer.py`): the
  composed curve satisfies `composed(x) == LUT(P(WL(x)))` — with `P` the
  MONOCHROME1 inversion or the identity — for both a linear and a non-linear
  LUT, and a linear LUT's composed curve equals the polarity-corrected ramp
  exactly (the plain ramp for MONOCHROME2, the inverted ramp for MONOCHROME1);
  `composed` is monotonically **non-decreasing only for an increasing LUT** —
  the Inverse LUT is monotone *non-increasing*, so assert the direction from the
  LUT's own monotonicity rather than assuming "monotone" means "increasing";
  composition is order-sensitive (asserting it is LUT-after-W/L, never
  W/L-after-LUT).
- [ ] **Regression — display path**: existing slice-display, MPR, projection, and
  export tests stay green with a Linear LUT selected
  (`tests/core/test_mpr_photometric_interpretation.py`,
  `tests/gui/test_mpr_controller_monochrome1.py`, and the projection/export
  image tests) — the polarity and `Format_Grayscale8` invariants are unchanged
  by a default Linear LUT. Add MONOCHROME1 coverage for **both**
  `render_grayscale_image()` and `create_slice_projection_pil_image()` under a
  color LUT, asserting polarity is applied before LUT expansion and the result is
  never double-inverted (`(H, W, 3)` output, not `(H, W)`).
- [ ] **Regression — QImage stride consistency**: render a color LUT at image widths
  that are *not* multiples of 4 (e.g. 63, 65, 101) through every QImage consumer
  and assert (a) the pixels round-trip to the expected `(H, W, 3)` array with no
  row skew, and (b) the `bytesPerLine` actually passed equals the stride the
  source buffer was packed with. Do **not** assert that the stride is
  4-byte-padded — QImage honors an explicit unaligned stride correctly, so
  padding is an implementation choice, not an invariant. Use odd widths so a
  hardcoded or mismatched stride cannot hide.
- [ ] **Regression — measurement space is never display-transformed**: assert that
  the array returned for MPR ROI statistics equals the rescaled stored values
  exactly — no windowing, no polarity inversion, no LUT — and that selecting a
  color LUT does not change a single reported ROI statistic. This guards the
  shared-accessor split in 2b, whose failure mode is silent.
- [ ] **Regression — LUT reaches every inventory path**: each of the five rows
  in the 1a inventory produces output changed by a non-linear LUT, on both its
  windowed and (where reachable) its normalize-fallback branch. Assert
  row-by-row so a path cannot be silently skipped.
- [ ] **Regression — no-windowing branch**: a dataset with no window metadata
  (so `resolve_window_level_and_rescale()` returns `None` center/width) still
  applies the active LUT after the normalize fallback, for **all four rows that
  have the branch** — row 1 `render_grayscale_image`, row 2
  `create_slice_projection_pil_image`, row 3 the `export_rendering.py`
  rasterization path, and **row 5 `MprThumbnailWidget`**. The pixel-invariance
  test asserts a non-linear LUT changes the output there too, not only on the
  windowed path. Row 5 is the one most likely to be forgotten — without it the
  navigator stops previewing its pane. Row 3 matters because "user sees what
  they exported" must hold for un-windowed datasets too.
- [ ] **Qt/GUI** (`tests/gui/test_lut_curve_editor.py`): breakpoint add/delete/drag;
  freehand draw → simplified control points; interpolation switch; undo/redo;
  gamma slider re-samples; a LUT loaded into the selector keeps its name/source
  and reopens in the editor; the three-curve overlay renders W/L, LUT, and
  composed result; for a Linear LUT the W/L ramp and the composed result are
  drawn as **one** line, while the LUT-alone trace stays on its own 0–255 axis
  (a Linear LUT is the identity there, which is *not* the W/L ramp — on stored
  values `[0, 400, 500, 600, 1000]` with center 500 / width 200 the ramp is
  `[0, 0, 127.5, 255, 255]` as floats before the cast — `apply_window_level`
  ends in `astype(np.uint8)`, so the stored value is **127**). Save/load
  round-trip is covered in Phase 4a (`tests/core/test_lut_persistence.py`).
- [ ] Follow [`dev-docs/info/TESTING_GUIDANCE.md`](../../info/TESTING_GUIDANCE.md)
  tiers; never construct a `QCoreApplication` in a test — use the session `qapp`
  fixture.

---

## Documentation and docstrings

- [ ] **Contract docstrings** on the new/changed public functions —
  `apply_lut()`, `LookUpTable.__post_init__`/`to_dict`/`from_dict`, the
  interpolation and RDP helpers, and `apply_lut_to_uint8()` —
  stating the composition order (`LUT ∘ P ∘ W/L`, where `P` is MONOCHROME1
  polarity, applied after window/level, not a convolution), the `lut=None`
  equivalence guarantee, output dtype/shape for grayscale vs color, the
  round-to-nearest `[0, 1] -> [0, 255]` scale, and the accepted parameter
  ranges — **`gamma` in [0.1, 5.0] (`None` when not the gamma curve),
  `sigmoid_k > 0` (`None` when not the sigmoid curve), `exp_k` in [0.1, 5.0]
  defaulting to 1.0**. Keep these three ranges identical to the dataclass
  comments, `__post_init__`, and the JSON schema.
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
| `src/core/dicom_window_level.py` | **Signature unchanged** (no `lut`); the LUT is applied after polarity via `apply_lut_to_uint8` |
| `src/core/dicom_processor.py` | Pass LUT through processing |
| `src/core/dicom_image_render.py` | Pass active LUT at the direct `apply_window_level` call |
| `src/core/slice_display_pixels.py` | Pass active LUT into AIP/MIP/MinIP projection rendering |
| `src/core/mpr_builder.py` | **Stays LUT-free** — cached `MprResult` slices remain raw stored values |
| `src/core/mpr_navigator_thumbnail.py` | Getter stays in measurement space; apply the active LUT only in the thumbnail/display builder |
| `src/gui/mpr_thumbnail_widget.py` | Apply active LUT in the thumbnail's internal render; pass a bytesPerLine matching the buffer |
| `src/gui/image_viewer_view.py` | Pass a bytesPerLine matching the buffer for color-LUT output |
| `src/gui/slice_display_manager.py` | Use active LUT in display path |
| `src/gui/view_state_manager.py` | Store active LUT per series in `series_defaults` |
| `src/core/view_state_handlers.py` | Event glue only — fan LUT changes out to status text/reset |
| `src/core/view_state_inversion.py` | Unchanged — it only reports the invert *flag*; the pixels are inverted in `image_viewer_view` |
| `src/gui/image_viewer_view.py` | Move user-invert to the 2-D grayscale stage, before `apply_lut_to_uint8`; add the color branch for a color LUT |
| `src/gui/main_window_toolbar_builder.py` | LUT dropdown |
| `src/gui/main_window_menu_builder.py` | View → Look-Up Table submenu |
| `src/gui/image_viewer_context_menu.py` | LUT submenu |
| `src/tools/histogram_widget.py` | Three-curve transfer-function overlay: W/L ramp, LUT, composed result |
| `src/gui/dialogs/histogram_dialog.py` | Host the overlay; no duplicate painting |
| `src/gui/widgets/lut_transfer_function_widget.py` | **New** — reusable W/L + LUT + composed curve canvas (histogram overlay, dropdown swatches, editor preview) |
| `src/gui/dialogs/lut_curve_editor_dialog.py` | **New** — interactive custom curve editor (grayscale curves) |
| `src/core/mpr_view_math.py` | Route `array_to_pil` through the shared W/L → polarity → LUT order |
| `src/gui/overlay_text_builder.py` | Active LUT label |
| `src/core/photometric_polarity.py` | Update the stale "polarity last" module docstring for the new order |
| `src/gui/export_rendering.py` | Apply LUT on PNG/JPG export (both the windowed and normalize-fallback branches) |
| `src/core/mpr_dicom_export.py` | Keep DICOM export display-only (no baked LUT) |
| `src/utils/config_manager.py` | Persist `custom_luts.json` |
| `tests/core/test_lut_engine.py` | **New** |
| `tests/core/test_lut_curve.py` | **New** — control-point interpolation and sampling |
| `tests/core/test_lut_transfer.py` | **New** — `composed(x) == LUT(WL(x))` composition tests |
| `tests/gui/test_lut_curve_editor.py` | **New** — breakpoint editing, freehand, and loaded-LUT display (Phase 3b) |
| `tests/core/test_mpr_roi_measurement_space.py` | **New** — MPR ROI statistics stay in measurement space (no W/L, polarity, or LUT) |
| `tests/gui/test_lut_transfer_overlay.py` | **New** — three-curve overlay rendering and Linear collapse |
| `tests/core/test_lut_persistence.py` | **New** — `to_dict`/`from_dict` round-trip and fallback (Phase 4a) |
| `user-docs/` (display + LUT pages) | User documentation for the selector, editor, and overlay |

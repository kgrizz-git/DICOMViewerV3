# Look-Up Tables (LUTs) & Colormaps Plan

**Status:** Not started  
**Priority:** P1  
**TO_DO ref:** [`TO_DO.md` Next up](../../TO_DO.md#next-up) — "Add more and custom look-up tables (LUTs & colormaps) beyond linear W/L, including an interactive custom curve editor, with an active-LUT overlay on histograms."

---

## Goal

Extend the display pipeline beyond the current **linear** window/level ramp to support **non-linear look-up tables** (sigmoid, logarithmic, exponential, gamma) and **color look-up tables / colormaps** (hot, cool, rainbow, bone, etc.) for grayscale DICOM images. Also provide an interactive custom curve editor with draggable breakpoints, freehand drawing, and straight-line or smooth interpolation; display the active/loaded LUT with its curve or colormap preview; and overlay the active LUT curve on the histogram widget.

### Current state

- `src/core/dicom_window_level.py` → `apply_window_level()` uses a linear clamp+normalize to uint8.
- All direct `apply_window_level()` call sites (must each be reconciled in Phase 2):
  - `src/core/dicom_processor.py:132`
  - `src/core/dicom_image_render.py:204`
  - `src/core/slice_display_pixels.py:110` (AIP/MIP/MinIP projections — **not** via `SliceDisplayManager`)
  - `src/gui/export_rendering.py:357` (export rasterization — **not** via `SliceDisplayManager`)
- `src/core/slice_display_lut.py` is **not** a LUT system — it is W/L rescale-alignment (`apply_window_level_rescale_conversion`). It is reused, not replaced, by this plan; the new engine must not shadow its name/purpose.
- Fusion uses colormaps via `src/core/fusion_processor.py` / `fusion_handler.py` (`cv2.applyColorMap`, and `matplotlib.colormaps.get_cmap(...)` for overlay blending at `fusion_processor.py:117-120`).
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

      def __post_init__(self) -> None:
          """Validate/normalize: sort control points by x, reject duplicate x,
          clamp y to [0, 1], require x strictly increasing in [0, 1], require
          gamma in [0.1, 5.0], require colormap shape (256, 3) uint8 when set."""

  def apply_lut(
      pixel_array: np.ndarray,
      window_center: float,
      window_width: float,
      lut: LookUpTable,
      rescale_slope: float | None = None,
      rescale_intercept: float | None = None,
  ) -> np.ndarray:
      """Apply W/L then LUT. Returns uint8 (grayscale) or (H,W,3) uint8 (color)."""
  ```

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
parameterized built-ins (gamma, sigmoid) read their parameters from the
`LookUpTable` fields (`gamma`, `sigmoid_k`) at sample time, so the toolbar
slider mutates a `LookUpTable` and the display path needs no extra plumbing.

### 1b. Built-in grayscale transfer functions

- [ ] **Linear** (current behavior, default).
- [ ] **Sigmoid:** `1 / (1 + exp(-k * (x - center)))` — adjustable steepness `k`.
- [ ] **Logarithmic:** `log(1 + x)` normalized.
- [ ] **Exponential:** `exp(k * x)` normalized.
- [ ] **Gamma:** `x^gamma` — adjustable gamma (0.1–5.0).
- [ ] **Inverse:** `255 - x` (simple invert after W/L).
- [ ] Each function maps the [0, 255] post-W/L range to [0, 255].

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
  the control-point representation is the editable/persisted form for
  user-defined curves (Phase 4), and sampling converts between the two.
- [ ] Allow user-defined colormaps from a `.csv` or `.json` file (future — Phase 4).

### 1d. Tests

- [ ] `tests/core/test_lut_engine.py`:
  - Linear LUT matches current `apply_window_level` output.
  - `apply_lut(..., lut=None)` / `apply_window_level(..., lut=None)` is byte-identical to today.
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
    `epsilon = 2.0` in normalized [0, 1] input space, endpoints always pinned to
    (0, 0) and (1, 1), and a fixed point set simplifying to the same points.

---

## Phase 2 — Display pipeline integration

### 2a. Wire LUT into slice display

- [ ] Add `current_lut: LookUpTable` to the per-pane view state
  (`src/gui/view_state_manager.py`, with `src/core/view_state_handlers.py` for
  the per-series/per-pane getters used by the display path).
- [ ] **Signature contract:** `apply_window_level()` gains an optional
  `lut: LookUpTable | None = None` parameter. When `None` (or a linear LUT), the
  output is byte-identical to the current linear clamp+normalize. `apply_window_level`
  then delegates to `lut_engine.apply_lut()`. Because the parameter is optional
  and defaults to `None`, existing callers stay source- and behavior-compatible.
- [ ] Replace direct calls to `apply_window_level()` with `apply_lut()` in the
  display path (`src/gui/slice_display_manager.py` → `src/core/dicom_processor.py`),
  passing the active LUT from per-pane state.
- [ ] Update the remaining direct callers to pass the active LUT from their own
  state source: `src/core/dicom_image_render.py:204` and
  `src/core/slice_display_pixels.py:110` (projections) — see 2b.
- [ ] When LUT is "Linear" (default), behavior is identical to today.
- [ ] When LUT produces RGB (colormap), the display path must handle `(H, W, 3)`
  → `QImage.Format_RGB888` instead of `Format_Grayscale8`. Single-slice analysis
  arrays (polarity/photometric-interpretation invariants) stay grayscale — the
  RGB expansion happens at the QImage conversion boundary only.

### 2b. MPR and projection displays

- [ ] Apply the active LUT to MPR panes and AIP/MIP/MinIP projections too.
- [ ] Projections: thread `lut: LookUpTable | None` through
  `src/core/slice_display_pixels.py` → `create_slice_projection_pil_image` and
  pass it at the `apply_window_level` call site (`slice_display_pixels.py:110`).
  Source: `src/core/dicom_projections.py` / `src/core/projection_app_facade.py`
  / `src/gui/intensity_projection_controls_widget.py`.
- [ ] MPR: thread `current_lut` from `ViewStateManager` through the subwindow
  manager into `src/core/mpr_builder.py` (reslice) and
  `src/core/mpr_navigator_thumbnail.py` / `src/gui/mpr_thumbnail_widget.py`
  (navigator thumbnail). Both call `apply_lut` with the active LUT.
- [ ] MPR cache (`src/core/mpr_cache.py`) stores volume/slice data, not rendered
  pixels — do **not** bake the LUT into cached arrays; apply it per render so
  changing the LUT does not require a cache invalidation.
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
- [ ] Display the active/loaded LUT name, source (built-in, file, or custom), and curve/colormap preview; loading a saved LUT immediately selects it and updates the histogram overlay.
- [ ] Gamma LUT: show a slider for the gamma parameter (default 1.0) bound to
  `LookUpTable.gamma`, so changing it re-samples and re-renders.

> **Sequencing:** the interactive curve editor is **Phase 3b**, not Phase 4 —
> the selector and the editor ship together so "Custom…" is never a dead entry.
> Phase 4 is reduced to the genuinely deferred items below.

### 3b. Interactive custom curve / colormap editor

- [ ] **New** `src/gui/dialogs/lut_curve_editor_dialog.py`: edit grayscale transfer curves and color colormaps. Add, delete, and drag breakpoints on a graph; draw freehand; switch between straight-line piecewise interpolation and smooth curves (monotone cubic or Catmull–Rom); clamp or snap endpoints to the valid range; preview the result; undo/redo edits. Freehand input simplifies into editable control points (Ramer–Douglas–Peucker, `epsilon = 2.0` in normalized space, endpoints pinned to (0,0)/(1,1)) rather than becoming a raster-only map. A loaded LUT remains visible in the selector with its name/source and is reopenable here.
- [ ] Gamma / sigmoid parameter controls live in this dialog as well as the toolbar.
- [ ] Live preview uses the same `apply_lut` path as the viewport (no separate preview renderer).

### 3c. Histogram LUT overlay

- [ ] Draw the active LUT transfer curve as an overlay, painted in
  `HistogramWidget`'s paint path (`src/tools/histogram_widget.py`) so every host
  — including `src/gui/dialogs/histogram_dialog.py` — inherits it, rather than
  duplicating the overlay per dialog:
  - X-axis = pixel value (or HU if rescaled).
  - Y-axis = output intensity (0–255).
  - Linear: straight diagonal line.
  - Sigmoid: S-curve.
  - Color LUT: draw a colored gradient bar along the x-axis showing the colormap.
- [ ] Update the overlay when W/L or LUT changes.
- [ ] Allow interactive W/L adjustment by dragging the curve endpoints (stretch goal).

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
        "control_points": [[0.0, 0.0], [0.25, 0.18], [0.5, 0.55], [1.0, 1.0]]
      }
    ]
  }
  ```
- [ ] Unknown/missing `interpolation` falls back to `linear`; a LUT that fails
  validation is skipped with a warning rather than aborting app data load.

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
| `src/core/mpr_builder.py` | Apply active LUT to MPR reslice panes |
| `src/core/mpr_navigator_thumbnail.py` | Apply active LUT to the navigator thumbnail |
| `src/gui/mpr_thumbnail_widget.py` | Apply active LUT to the thumbnail widget |
| `src/gui/slice_display_manager.py` | Use active LUT in display path |
| `src/gui/view_state_manager.py` | Store active LUT per pane |
| `src/core/view_state_handlers.py` | Expose active LUT to the display/projection/MPR paths |
| `src/core/view_state_inversion.py` | Respect LUT when inverting |
| `src/gui/main_window_toolbar_builder.py` | LUT dropdown |
| `src/gui/main_window_menu_builder.py` | View → Look-Up Table submenu |
| `src/gui/image_viewer_context_menu.py` | LUT submenu |
| `src/tools/histogram_widget.py` | LUT curve overlay (painted once, inherited by the dialog) |
| `src/gui/dialogs/histogram_dialog.py` | Host the overlay; no duplicate painting |
| `src/gui/dialogs/lut_curve_editor_dialog.py` | **New** — interactive custom curve/colormap editor |
| `src/gui/overlay_text_builder.py` | Active LUT label |
| `src/gui/export_rendering.py` | Apply LUT on PNG/JPG export |
| `src/core/mpr_dicom_export.py` | Keep DICOM export display-only (no baked LUT) |
| `src/utils/config_manager.py` | Persist `custom_luts.json` |
| `tests/core/test_lut_engine.py` | **New** |
| `tests/core/test_lut_curve.py` | **New** — control-point interpolation and sampling |
| `tests/gui/test_lut_curve_editor.py` | **New** — breakpoint editing, freehand, loaded-LUT display, and persistence |

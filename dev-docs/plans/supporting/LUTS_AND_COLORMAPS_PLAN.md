# Look-Up Tables (LUTs) & Colormaps Plan

**Status:** Not started  
**Priority:** P1  
**TO_DO ref:** [`TO_DO.md` Next up](../../TO_DO.md#next-up) — "Add more and custom look-up tables (LUTs & colormaps) beyond linear W/L, including an interactive custom curve editor, with an active-LUT overlay on histograms."

---

## Goal

Extend the display pipeline beyond the current **linear** window/level ramp to support **non-linear look-up tables** (sigmoid, logarithmic, exponential, gamma) and **color look-up tables / colormaps** (hot, cool, rainbow, bone, etc.) for grayscale DICOM images. Also provide an interactive custom curve editor with draggable breakpoints, freehand drawing, and straight-line or smooth interpolation; display the active/loaded LUT with its curve or colormap preview; and overlay the active LUT curve on the histogram widget.

### Current state

- `dicom_window_level.py` → `apply_window_level()` uses a linear clamp+normalize to uint8.
- Fusion uses colormaps via `fusion_processor.py` / `fusion_handler.py` (`cv2.applyColorMap` or matplotlib colormaps for overlay blending).
- No general-purpose LUT system for single-series grayscale display.
- Histogram widget (`histogram_dialog.py` / `histogram_widget.py`) does not show the transfer function.

---

## Phase 1 — LUT engine

### 1a. LUT module

- [ ] Create `src/core/lut_engine.py`:
  ```python
  class LookUpTable:
      name: str
      lut_type: str  # "grayscale_ramp", "colormap"
      transfer_fn: Callable | None  # for non-linear grayscale
      colormap: np.ndarray | None   # (256, 3) uint8 for color LUTs
      control_points: tuple[tuple[float, float], ...] | None
      interpolation: str  # "linear", "monotone_cubic", or "bezier"

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
  - Generate `(256, 3)` uint8 arrays at init time: `(plt.cm.get_cmap(name)(np.linspace(0, 1, 256))[:, :3] * 255).astype(np.uint8)`.
- [ ] Store as `LookUpTable` instances in a registry (`src/core/lut_catalog.py`).
- [ ] Allow user-defined colormaps from a `.csv` or `.json` file (future — Phase 4).
- [ ] Keep custom grayscale curves in the same control-point representation as color maps so an editable curve can be sampled and applied through the same fast LUT path.

### 1d. Tests

- [ ] `tests/test_lut_engine.py`:
  - Linear LUT matches current `apply_window_level` output.
  - Sigmoid with high steepness approximates a step function.
  - Gamma=1.0 matches linear.
  - Inverse flips values.
  - Color LUT output is (H,W,3).
  - Edge cases: all-zero image, single-value image.
- [ ] `tests/core/test_lut_curve.py`:
  - Piecewise-linear control points sample exactly between breakpoints.
  - Monotone-cubic and Bezier interpolation stay within the endpoint range.
  - Clamping, duplicate-point rejection, and 256-entry sampling are deterministic.
  - Freehand samples simplify to a stable, editable control-point set.

---

## Phase 2 — Display pipeline integration

### 2a. Wire LUT into slice display

- [ ] Add `current_lut: LookUpTable` to the per-pane view state (or to `ViewStateManager` / `SliceDisplayManager`).
- [ ] Replace direct calls to `apply_window_level()` with `apply_lut()` in the display path (`slice_display_manager.py` → `dicom_processor.py`).
- [ ] When LUT is "Linear" (default), behavior is identical to today.
- [ ] When LUT produces RGB (colormap), the display path must handle `(H, W, 3)` → `QImage.Format_RGB888` instead of `Format_Grayscale8`.

### 2b. MPR and projection displays

- [ ] Apply the active LUT to MPR panes and AIP/MIP/MinIP projections too.
- [ ] 3D volume rendering has its own transfer function system — LUTs here are for 2D display only.

### 2c. Export with LUT

- [ ] PNG/JPG export applies the active LUT (user sees what they exported).
- [ ] DICOM export: store the raw pixel data (no LUT baked in); optionally write a VOI LUT Sequence for non-linear functions, or note in export dialog that LUT is display-only.

---

## Phase 3 — UI

### 3a. LUT selector

- [ ] Add a **LUT** dropdown to the toolbar (or to the right-pane controls area):
  - Grouped: **Grayscale** (Linear, Sigmoid, Log, Exp, Gamma, Inverse) | **Color** (Hot, Cool, Jet, …).
  - Icon swatches showing a mini gradient preview for each LUT.
- [ ] Also accessible from **View → Look-Up Table** submenu and from the image context menu.
- [ ] Active LUT is persisted per-pane (so different panes can have different LUTs).
- [ ] Selecting a custom LUT opens the Phase 4 curve/colormap editor.
- [ ] Display the active/loaded LUT name, source (built-in, file, or custom), and curve/colormap preview; loading a saved LUT immediately selects it and updates the histogram overlay.
- [ ] Gamma LUT: show a slider for the gamma parameter (default 1.0).

### 3b. Histogram LUT overlay

- [ ] In the histogram dialog/widget, draw the active LUT transfer curve as an overlay:
  - X-axis = pixel value (or HU if rescaled).
  - Y-axis = output intensity (0–255).
  - Linear: straight diagonal line.
  - Sigmoid: S-curve.
  - Color LUT: draw a colored gradient bar along the x-axis showing the colormap.
- [ ] Update the overlay when W/L or LUT changes.
- [ ] Allow interactive W/L adjustment by dragging the curve endpoints (stretch goal).

### 3c. Keyboard shortcut

- [ ] `L` to cycle through LUTs? Or just rely on the toolbar dropdown.
- [ ] Check for conflicts with existing shortcuts.

---

## Phase 4 — Advanced (future)

- [ ] **Interactive custom LUT/curve editor:** edit grayscale transfer curves and color colormaps. Add, delete, and drag breakpoints on a graph; draw freehand; switch between straight-line piecewise interpolation and smooth curves (monotone cubic or Bezier); clamp or snap endpoints to the valid range; preview the result; undo/redo edits; and save/load the control points as JSON. Freehand input should simplify into editable control points rather than becoming a raster-only map. A loaded LUT must remain visible in the selector with its name/source and be reopenable in the editor.
- [ ] **DICOM Modality LUT Sequence:** Parse `ModalityLUTSequence` (0028,3000) and `VOILUTSequence` (0028,3010) from datasets that embed non-linear LUTs — use them as an additional "From DICOM" option.
- [ ] **Per-series default LUT:** E.g., always use "Hot" for PET, "Bone" for CT.

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
| `src/core/lut_engine.py` | **New** — LUT application logic |
| `src/core/lut_curve.py` | **New** — control-point storage, interpolation, and 256-entry sampling |
| `src/core/lut_catalog.py` | **New** — built-in LUT registry |
| `src/core/dicom_window_level.py` | Refactor: `apply_window_level` delegates to `lut_engine` |
| `src/core/slice_display_manager.py` | Use active LUT in display path |
| `src/core/dicom_processor.py` | Pass LUT through processing |
| `src/core/view_state_manager.py` | Store active LUT per pane |
| `src/gui/main_window_toolbar_builder.py` | LUT dropdown |
| `src/gui/main_window_menu_builder.py` | View → Look-Up Table submenu |
| `src/gui/image_viewer_context_menu.py` | LUT submenu |
| `src/gui/dialogs/histogram_dialog.py` | LUT curve overlay |
| `src/gui/dialogs/lut_curve_editor_dialog.py` | **New** — interactive custom curve/colormap editor |
| `src/gui/overlay_text_builder.py` | Active LUT label |
| `src/core/export_rendering.py` | Apply LUT on export |
| `tests/test_lut_engine.py` | **New** |
| `tests/core/test_lut_curve.py` | **New** — control-point interpolation and sampling |
| `tests/gui/test_lut_curve_editor.py` | **New** — breakpoint editing, freehand, loaded-LUT display, and persistence |

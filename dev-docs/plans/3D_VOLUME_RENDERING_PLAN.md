# 3D Volume Rendering with Adjustable Opacity – Implementation Plan

**Created:** 2026-05-22
**Tracks:** [`dev-docs/TO_DO.md`](../TO_DO.md) line 131 — `[P1] Allow 3D visualization of DICOM datasets with adjustable opacity`
**Follow-on (P2):** line 132 — `[P2] Eventually allow coloring of different structures, e.g. based on HU/pixel value`

---

## Goals

- [ ] Render a 3D volume from any loaded CT/MR series using GPU-accelerated volume rendering (VTK)
- [ ] Provide a global opacity slider that controls overall volume transparency
- [ ] Embed the 3D view in a dedicated dialog/window (not replacing the existing 2D subwindow system)
- [ ] Allow basic 3D interaction: rotate, pan, zoom via mouse
- [ ] Provide preset transfer functions (opacity ramps) for common modalities (CT soft tissue, CT bone, MR brain)
- [ ] Support adjustable window/level mapped to the transfer function range
- [ ] (P2, deferred) Allow HU-range-based coloring of different structures with per-structure opacity

---

## Non-Goals (for this plan)

- No surface rendering / isosurface extraction (marching cubes) — volume rendering only for now
- No segmentation or contouring tools in the 3D view
- No 3D ROI measurement or annotation
- No 3D printing / STL export
- No real-time fusion overlay in 3D (e.g., PET-CT volume fusion) — future work
- No replacement of the 2D subwindow layout; 3D is a separate modality window

---

## Current State

### What exists
- **SimpleITK volume construction** is fully implemented in [`src/core/mpr_volume.py`](../../src/core/mpr_volume.py). `MprVolume.from_datasets(List[Dataset])` builds a `sitk.Image` with correct origin, spacing, and direction cosines from any sorted DICOM series. This is the same pipeline used by MPR.
- **No 3D rendering** of any kind exists — no VTK, no OpenGL, no GPU-based rendering in the codebase.
- **No VTK dependency** in `requirements.txt`.

### What we build on
- `MprVolume.from_datasets()` already validates geometry, handles variable slice spacing, and produces a ready-to-render `sitk.Image`. The 3D renderer reuses this directly — no new volume assembly code needed.
- The right-panel widget pattern (`FusionControlsWidget`, `IntensityProjectionControlsWidget`) provides a proven template for adding a 3D controls panel.
- The `MprController` lifecycle (dialog → build in background thread → display result → cleanup) is the model for how 3D rendering should be triggered and managed.

---

## Technology Choice: VTK

**Decision:** Use VTK (`vtk` Python package) with `QVTKRenderWindowInteractor` embedded in a PySide6 `QWidget`.

**Rationale:**
- VTK is the industry standard for medical image 3D visualization — mature, GPU-accelerated, well-documented.
- `vtkSmartVolumeMapper` auto-selects the best GPU/CPU rendering path available.
- `QVTKRenderWindowInteractor` provides a drop-in Qt widget for embedding VTK render windows.
- SimpleITK → VTK conversion is a single call: `sitk.GetArrayFromImage()` → `vtkImageData`, or use `vtkImageImport` directly.
- VTK handles all interaction (trackball rotate, pan, zoom) out of the box via `vtkInteractorStyleTrackballCamera`.

**New dependency:** `vtk>=9.3.0` (BSD license, pre-built wheels on PyPI for Windows/macOS/Linux, Python 3.10–3.12).

**Decision placeholder:** If VTK wheels prove too large or cause PySide6 conflicts on some platforms, a fallback plan is CPU-based ray-casting via NumPy displayed in a standard `QGraphicsView`. This would be Phase 5 (not in initial scope).

---

## Files to Be Created / Touched

### New files
- [x] `src/core/volume_renderer.py` — VTK volume rendering pipeline (no Qt imports)
- [x] `src/gui/volume_viewer_widget.py` — `QWidget` wrapping `QVTKRenderWindowInteractor` + controls
- [x] `src/gui/dialogs/volume_render_dialog.py` — Dialog housing the 3D viewer widget
- [x] `src/core/volume_render_facade.py` — facade for launching 3D from the app coordinator

### Modified files
- [x] `requirements.txt` — add `vtk>=9.3.0`
- [x] `src/gui/main_window.py` — add `create_3d_view_requested` signal
- [x] `src/gui/main_window_toolbar_builder.py` — add "3D View" toolbar button
- [x] `src/gui/main_window_menu_builder.py` — add "3D Volume Render" menu item under Tools
- [x] `src/core/app_signal_wiring.py` — wire 3D action signal
- [x] `src/main.py` — instantiate `VolumeRenderFacade`
- [ ] `CHANGELOG.md` — document new feature
- [ ] `dev-docs/TO_DO.md` — mark item complete with plan link

---

## Phase 0: Dependency and Widget Foundation

### 0.1 Add VTK dependency
- [x] Add `vtk>=9.3.0` to `requirements.txt` with a comment explaining its purpose
- [x] Verify `pip install vtk` works in the project venv (Windows, Python 3.11/3.12)
- [x] Verify no PySide6 conflicts: `QVTKRenderWindowInteractor` must coexist with PySide6 (VTK 9.3+ supports PySide6 natively via `vtkmodules.qt.QVTKRenderWindowInteractor`)

### 0.2 Lazy import guard
- [x] Follow the existing `SimpleITK` lazy-import pattern from `mpr_volume.py`:
  ```python
  vtk_mod: Any = None
  vtk_available: bool = False
  try:
      import vtkmodules.all as _vtk
      vtk_mod = _vtk
      vtk_available = True
  except ImportError:
      pass
  ```
- [x] Surface a user-friendly error dialog if VTK is not installed when the user clicks "3D View"

---

## Phase 1: Core Volume Rendering Pipeline (`src/core/volume_renderer.py`)

### 1.1 Volume data conversion
- [x] Accept a `sitk.Image` (from `MprVolume`) and convert to `vtkImageData`:
  - Use `sitk.GetArrayFromImage()` to get the NumPy array
  - Use `vtkImageImport` or `numpy_support.numpy_to_vtk()` to create `vtkImageData`
  - Preserve origin, spacing, and direction from the SimpleITK image
- [x] Handle both int16 (CT Hounsfield) and uint16/float32 (MR) scalar types

### 1.2 Transfer function presets
- [x] Define a `TransferFunctionPreset` dataclass:
  ```python
  @dataclass
  class TransferFunctionPreset:
      name: str
      scalar_opacity: List[Tuple[float, float]]  # (scalar_value, opacity) control points
      color: List[Tuple[float, float, float, float]]  # (scalar_value, r, g, b) control points
      gradient_opacity: Optional[List[Tuple[float, float]]]  # optional gradient-based opacity
  ```
- [x] Implement presets:
  - [x] **CT Bone:** high opacity at HU > 200, ramp from 200–400, white/cream color
  - [x] **CT Soft Tissue:** opacity ramp HU -100 to 300, flesh tones
  - [x] **CT Lung/Air:** include air pockets (HU < -500) as transparent, lung tissue semi-transparent
  - [x] **MR Default:** linear ramp across the intensity range, grayscale
  - [ ] **Custom:** user-editable (deferred to P2 for full editor; initially just W/L-mapped linear ramp)
  - [x] **MR T2 Brain:** T2-weighted ramp, CSF bright, grayscale-blue tones
  - [x] **MR Angiography:** TOF MRA ramp, bright vessels with red-to-cream colour

### 1.3 Rendering setup
- [x] Create `VolumeRenderer` class with methods:
  - `set_volume(sitk_image: sitk.Image)` — converts and sets the volume data
  - `set_preset(preset: TransferFunctionPreset)` — applies transfer function
  - `set_global_opacity(opacity: float)` — scales all opacity values by a 0.0–1.0 multiplier
  - `set_window_level(window: float, center: float)` — shifts the transfer function scalar range
  - `get_vtk_renderer() -> vtkRenderer` — returns configured renderer for embedding
- [x] Use `vtkSmartVolumeMapper` for automatic GPU/CPU path selection
- [x] Use `vtkVolumeProperty` with the transfer function applied via `SetScalarOpacity()` and `SetColor()`
- [x] Enable shading: `SetShade(True)`, ambient/diffuse/specular lighting for depth cues
- [x] Set interpolation to `SetInterpolationTypeToLinear()` for smooth rendering

---

## Phase 2: Qt Widget and Dialog (`src/gui/`)

### 2.1 Volume viewer widget (`src/gui/volume_viewer_widget.py`)
- [x] Create `VolumeViewerWidget(QWidget)` containing:
  - A `QVTKRenderWindowInteractor` (the 3D viewport)
  - A control panel (right side or bottom) with:
    - [x] **Preset dropdown** (`QComboBox`): CT Bone / CT Soft Tissue / CT Lung / MR Default / + more; auto-selects MR Default for MR modality
    - [x] **Global opacity slider** (`QSlider`): 0–100%, default 100%
    - [x] **Threshold slider** (`QSlider`): ±500 HU/intensity, shifts opacity onset; resets when preset changes
    - [x] **Window/Level controls**: two `QSpinBox` or `QDoubleSpinBox` for W/L, mirroring the existing 2D W/L pattern
    - [ ] **Background color toggle**: black (default) / dark gray / white
    - [x] **Reset camera button**: returns to canonical anterior view with Superior up
  - VTK interactor style: `vtkInteractorStyleTrackballCamera` (left-drag = rotate, right-drag = zoom, middle-drag = pan, scroll = zoom)
- [x] Connect slider/combo signals to `VolumeRenderer` methods
- [x] Handle widget cleanup: call `Finalize()` on the VTK interactor when the widget is destroyed to prevent crashes

### 2.2 Volume render dialog (`src/gui/dialogs/volume_render_dialog.py`)
- [x] Create `VolumeRenderDialog(QDialog)` as a non-modal, resizable dialog
- [x] Title: "3D Volume Render — {series description}"
- [x] Size: default 800x600, remember last size via `QSettings`
- [x] Contains a `VolumeViewerWidget` as its central content
- [x] Accept a `List[pydicom.Dataset]` (the series to render) — builds `MprVolume` internally using the existing `MprVolume.from_datasets()` path
- [x] Show a progress indicator during volume construction (reuse `MprVolume` which can be slow for large series)
- [x] Allow multiple 3D dialogs open simultaneously (one per series)

---

## Phase 3: App Integration (Menu, Toolbar, Wiring)

### 3.1 Toolbar and menu entry
- [x] Add a "3D View" `QAction` with a suitable icon to the toolbar (`main_window_toolbar_builder.py`)
  - Icon: use an existing 3D/cube icon from resources, or add one
  - Tooltip: "Open 3D Volume Render of current series"
- [x] Add "3D Volume Render..." under the **Tools** menu (`main_window_menu_builder.py`)
- [x] Action is enabled only when a valid single-frame multi-slice series is loaded in the focused subwindow (disable for single-frame, structured reports, etc.)

### 3.2 Launch facade
- [x] Create `src/core/volume_render_facade.py` (following the `cine_app_facade.py` pattern):
  - `launch_3d_view(app, subwindow_index)`:
    1. Get the current series datasets from `app.subwindow_data[subwindow_index]`
    2. Validate: at least 3 slices, has pixel data, has geometry (ImagePositionPatient, etc.)
    3. Show error dialog if validation fails
    4. Create and show `VolumeRenderDialog` with the datasets
  - Track open dialogs to prevent duplicate renders of the same series

### 3.3 Signal wiring
- [x] Wire the "3D View" action in `app_signal_wiring.py` to `volume_render_facade.launch_3d_view()`

---

## Phase 4: Background Volume Construction

### 4.1 Threaded volume build
- [x] Build the `MprVolume` (and VTK conversion) in a `QThread` worker to avoid freezing the UI for large series
- [x] Show a `QProgressDialog` or inline progress bar in the `VolumeRenderDialog` during loading
- [x] Follow the `MprBuilderWorker` pattern: emit `finished(result)` / `error(message)` signals
- [x] Cancel support: if the user closes the dialog before loading completes, cancel the worker

### 4.2 Memory management
- [ ] For large volumes (e.g., 512x512x500 float32 = ~500 MB), warn the user if estimated memory exceeds a threshold (e.g., 1 GB)
- [x] On dialog close, explicitly release VTK objects and the volume data to free GPU/CPU memory
- [ ] Consider downsampling option for very large datasets (e.g., 2x downsample toggle)

---

## Phase 5 (P2 / Future): HU-Based Structure Coloring

This phase implements the P2 follow-on item: "Eventually allow coloring of different structures, e.g. based on HU/pixel value."

### 5.1 Multi-segment transfer function editor
- [ ] Add a transfer function editor widget (mini color/opacity curve editor) allowing users to:
  - Define multiple HU ranges with distinct colors and opacities
  - Example: bone (white, HU > 300), soft tissue (flesh, HU -100 to 200), air (transparent, HU < -500)
- [ ] Persist custom transfer functions to `QSettings`

### 5.2 Predefined anatomical presets
- [ ] CT Abdomen (liver, kidneys, bone differentiated by HU)
- [ ] CT Chest (lung air, soft tissue, bone)
- [ ] CT Head (brain, bone, air)
- [ ] Allow user to save/name custom presets

---

## Risks

1. **VTK + PySide6 compatibility:** VTK 9.3+ officially supports PySide6, but edge cases (especially on Windows with specific GPU drivers) may cause rendering artifacts or crashes. Mitigation: test on multiple machines; the `vtkSmartVolumeMapper` gracefully falls back to CPU rendering if GPU is unavailable.
2. **Package size:** VTK wheels are ~100–150 MB. This increases download/install time. Mitigation: document in requirements; consider making VTK an optional dependency with a graceful "install VTK for 3D" message.
3. **Memory consumption:** Volume rendering of large CT series (500+ slices at 512x512) requires significant RAM and VRAM. Mitigation: implement the memory warning (Phase 4.2) and optional downsampling.
4. **Rendering performance on integrated GPUs:** Laptops with Intel integrated graphics may have slow volume rendering. Mitigation: `vtkSmartVolumeMapper` auto-selects CPU path; add a "quality" toggle (low/medium/high) controlling sample distance.
5. **Thread safety:** VTK rendering must happen on the main thread; only data preparation (volume construction) can be threaded. Mitigation: follow the MPR pattern — build volume in worker thread, set up VTK pipeline on main thread after worker completes.

---

## Completion Criteria

- [ ] User can click "3D View" in toolbar/menu and see a GPU-rendered 3D volume of the current series
- [ ] Global opacity slider smoothly adjusts volume transparency in real-time
- [ ] At least 3 transfer function presets work correctly (CT Bone, CT Soft Tissue, MR Default)
- [ ] 3D interaction (rotate, pan, zoom) works smoothly
- [ ] Window/level controls shift the transfer function range
- [ ] Background volume construction with progress indication (no UI freeze)
- [ ] Memory cleanup on dialog close (no leaked VTK objects)
- [x] Action is disabled when no valid series is loaded
- [ ] Multiple 3D windows can be open simultaneously
- [ ] Works on Windows 11 with both dedicated and integrated GPUs
- [ ] `CHANGELOG.md` updated
- [ ] `dev-docs/TO_DO.md` line 131 marked complete with link to this plan

---

## Completion Protocol

Mark each `[ ]` item `[x]` only when fully verified. If blocked, add a short note under the item (do not rename the goal).

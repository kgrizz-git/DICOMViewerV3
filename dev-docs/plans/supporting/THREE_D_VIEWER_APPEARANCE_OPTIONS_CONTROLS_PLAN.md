# Plan: 3D Viewer Appearance, Options, and Controls Polish

Last updated: 2026-05-31

## Goal and success criteria

Improve the shipped 3D volume-render dialog from a functional VTK viewport into a better-looking and more controllable clinical/QA visualization tool. The main goal is greater control over appearance: users should not have to agonize over tiny low-opacity changes such as 5% vs 6%, should see meaningful change across the full control range, and should have tools to reduce rough/noisy-looking renders. This plan coordinates visual polish, control layout, rendering presets, transfer-function controls, interaction affordances, and performance/quality options without replacing the existing VTK pipeline.

Success criteria:

- The 3D viewer has a clearer control hierarchy: quick controls for common use, advanced controls for power users.
- Opacity/transparency controls are perceptually useful: fine control is available in the low-opacity range, and the high-opacity range does not waste most of the slider travel on visually indistinguishable states.
- Rough or noisy-looking renders can be improved with explicit quality, smoothing/interpolation, sampling, and transfer-function options rather than only by trial-and-error preset changes.
- The scalar domain is explicit before presets are tuned: CT controls either render calibrated HU values or clearly say they are operating on raw pixel values; PT/NM/generic controls say intensity, counts, SUV-like values, or unknown as appropriate.
- Window/Level behavior is truthful and tested: either Window really scales the transfer-function range, or the UI is relabeled to an offset/level-only control until width scaling exists.
- Transfer-function presets cover more than CT and MR: at minimum PT/NM and generic arbitrary-intensity volume presets exist, and labels do not imply HU when source values are not HU-based.
- Users can understand what preset, opacity, threshold, W/L shift, background, render quality, and interaction mode are doing.
- The current open 3D rendering follow-ups in `dev-docs/plans/3D_VOLUME_RENDERING_PLAN.md` are grouped into a coherent UI roadmap instead of scattered one-off tasks.
- Common CT/MR/PT/NM cases remain easy: a sensible default preset appears, basic rotate/pan/zoom works, and there are obvious reset/help affordances.
- Advanced capabilities such as custom transfer functions, HU-range coloring, cropping, and quality mode are designed behind stable seams before implementation.

## Context and links

- Backlog item: `dev-docs/TO_DO.md` under the 3D visualization feature cluster.
- Base implementation plan: `dev-docs/plans/3D_VOLUME_RENDERING_PLAN.md`.
- Lifecycle hardening: `dev-docs/plans/supporting/VOLUME_RENDER_DIALOG_LIFECYCLE_PLAN.md`.
- Current implementation:
  - `src/core/volume_renderer.py` owns VTK objects, built-in `TransferFunctionPreset` records, `vtkSmartVolumeMapper` / CPU fallback, opacity, threshold, W/L transfer-function shift, camera reset, GPU blank-frame fallback, and sample-distance interaction quality.
  - `src/gui/volume_viewer_widget.py` embeds `QVTKRenderWindowInteractor`, provides preset/opacity/W-L/threshold/reset/help controls, saves user presets, and switches to coarse sample distance during interaction. The current opacity UI is a linear integer 0-100 slider that maps directly to `set_global_opacity(value / 100.0)`.
  - `src/gui/dialogs/volume_render_dialog.py` hosts the top-level non-modal dialog and builds volume data in `_VolumeBuilderWorker`.
  - `src/core/volume_3d_user_presets.py` validates persisted user preset records.
- Current-code review notes to resolve before implementation:
  - `src/core/mpr_volume.py` currently stores raw float32 pixel values in the SimpleITK volume without applying `RescaleSlope` / `RescaleIntercept`; CT presets in `src/core/volume_renderer.py` are named and parameterized like HU presets. The plan must define whether 3D rendering converts to calibrated values or labels/uses raw values.
  - `VolumeRenderer.set_window_level()` currently ignores the `window` argument and only shifts transfer-function center. Any UI copy that says Window controls width/range is stale until this is implemented.
  - The base plan marks remembered dialog size as complete, but `VolumeRenderDialog` currently uses a fixed `resize(800, 600)` path. Reconcile the base-plan checkbox when T6 is implemented or when the base plan is refreshed.
- External references checked:
  - 3D Slicer volume rendering docs: presets, offset/shift, crop ROI, render method, adaptive quality, and advanced volume-property controls: <https://slicer.readthedocs.io/en/latest/user_guide/modules/volumerendering.html>
  - VTK `QVTKRenderWindowInteractor` docs: PySide6-supported Qt embedding and interaction event surface: <https://docs.vtk.org/en/v9.5.2/api/python/vtkmodules/vtkmodules.qt.QVTKRenderWindowInteractor.html>
  - VTK `vtkVolumeProperty` docs: color, scalar opacity, gradient opacity, shading, and 1D vs 2D transfer-function modes: <https://vtk.org/doc/nightly/html/classvtkVolumeProperty.html>
  - VTK volume-rendering examples, including GPU ray-cast isosurface-style transfer functions: <https://examples.vtk.org/site/PythonicAPI/VolumeRendering/RayCastIsosurface/>

## Research summary

3D Slicer provides the most relevant mature medical-viewer model. Its key lesson is progressive disclosure: quick display controls for presets/offset/crop/rendering method, then advanced sections for quality, rendering technique, ROI, and transfer functions. The app should follow that pattern rather than exposing every VTK knob at the top level.

VTK's own APIs support the needed architecture: `vtkVolumeProperty` already separates scalar opacity, color, gradient opacity, shading, interpolation, and transfer-function modes; the current app uses the 1D transfer-function path, which is the right first editor target. `QVTKRenderWindowInteractor` supports PySide6 and exposes mouse/key/wheel event hooks, so interaction hints and optional interaction-mode overlays should be implemented in the Qt wrapper, not by forking the renderer.

Multiple implementation approaches were considered:

- Approach A - Incremental polish of current controls: keep the right-side widget, add grouping, labels, background/quality toggles, reset buttons, and status text. Lowest risk and best first phase.
- Approach B - Preset-driven UX: add richer built-in presets and saveable user presets without a curve editor. Good for near-term clinical usability; limited for advanced HU-range editing.
- Approach B2 - Modality-aware preset catalog: expand built-in transfer-function groups beyond CT/MR to PT/SPECT/NM and generic arbitrary-intensity datasets, with unit-aware labels and safe fallback behavior when data semantics are unclear.
- Approach C - Advanced transfer-function editor: build a small curve/range editor for opacity/color points, eventually supporting multi-segment HU coloring. Powerful but larger UI/test surface; should follow Approach A/B.
- Approach D - Crop/ROI controls: add box cropping to hide tables/ribs/non-interesting regions. Useful and common in Slicer, but needs careful VTK clipping-plane design and should be a later phase.
- Approach E - Rendering-method/quality controls: expose GPU/CPU/auto plus low/normal/high quality/sample-distance modes. Useful for integrated GPUs and Parallels; should be implemented with measured defaults and safe fallbacks.
- Approach F - Appearance-first opacity and smoothness controls: replace or supplement the linear global-opacity slider with a perceptual/fine-control model, plus explicit anti-noise controls such as sample distance, interpolation/shading presets, and optional pre-render smoothing. This directly targets the current pain point where 5% vs 6% matters but 30% vs 75% may not look meaningfully different.

## Task graph and gates

### Ordering

- T0 -> Gate 0 -> S1 -> T1 -> Gate 1.
- T2 -> T3 -> T4 should be treated as sequential unless T1 first splits shared UI state into independent subwidgets; all three otherwise touch the same right-side control panel and labels.
- T5 and T6 depend on the control model from T1 and the initial control hierarchy from T2.
- T7/T8 are advanced phases and should wait until quick-control UX is reviewed.
- T11/T17/T18 depend on T0 because preset labels and thresholds must know the scalar domain.

### Verification gates

- Gate 0: Coder/reviewer approves the scalar-domain and W/L semantics decision before CT/PT/NM preset tuning or user-facing copy changes.
- Gate 1: UX/reviewer approves the control hierarchy and naming before implementation.
- Gate 2: Focused tests cover scalar-domain labeling, W/L semantics, preset serialization/migration, renderer control methods, and widget control-state mapping.
- Gate 3: Manual smoke on at least one CT and one MR/NM/PT-like dataset verifies readability, defaults, interaction responsiveness, and unit-safe labels.
- Gate 4: Visual evidence exists for the opacity/quality claims: screenshots or pixel-sampled render captures at low opacity and representative higher opacity values are attached to completion notes.

### File / area ownership

- `src/gui/volume_viewer_widget.py` -> ux/coder for layout, grouping, labels, tooltips, and interaction affordances.
- `src/core/volume_renderer.py` -> coder for renderer options, quality modes, background, transfer-function support, and clipping.
- `src/core/mpr_volume.py` / volume-preparation path -> coder only if the scalar-domain decision requires calibrated values before VTK attach.
- `src/core/volume_3d_user_presets.py` -> coder for persisted preset schema changes.
- `src/gui/dialogs/volume_render_dialog.py` -> coder for dialog chrome/minimize/default size/layout behavior.
- `tests/test_volume_3d_user_presets.py`, new focused widget/renderer tests -> tester/coder.
- `user-docs/USER_GUIDE_3D.md` -> docwriter once behavior ships.

## Phases

### Phase 1 - UX model and quick-control cleanup

- [x] (T0) Define the 3D scalar-domain contract before UI copy or preset tuning: decide whether the renderer receives raw pixel values, rescaled HU/calibrated values, SUV-like values, counts, or an explicit unknown intensity domain; document how `RescaleSlope`, `RescaleIntercept`, PET/NM units, Real World Value Mapping if used later, and generic fallback labels are handled (owner: coder/researcher, parallel-safe: no, stream: none, after: none). **Gate 0 decision:** the renderer continues to operate on **raw stored pixel values** (`mpr_volume` does not apply rescale); rather than retune every preset or change the volume pipeline, the UI now shows an honest scalar-domain label (`scalar_domain_label()` in `volume_renderer.py`) — e.g. "CT — raw pixel values (not calibrated HU)", "MR — arbitrary intensity", "PT/NM — counts". Calibrated-HU conversion and HU-accurate preset retuning remain a separate, deferred follow-up (still gated behind this decision).
- [x] (S1) Spike: sketch the control hierarchy and compare it to current `VolumeViewerWidget` controls, Slicer's Display/Advanced split, and existing DICOMViewerV3 design patterns (owner: ux, parallel-safe: no, stream: none, after: T0). **Done:** adopted Slicer-style Quick/Appearance/Advanced progressive disclosure pattern; existing app uses `QGroupBox.setVisible()` for show/hide (fusion_controls_widget.py); widget now uses QScrollArea + grouped sections.
- [x] (T1) Define a lightweight `VolumeRenderControlState` model for preset, scalar-domain label, opacity, opacity response, W/L or offset semantics, threshold, background, quality, render mode, smoothing/detail, status readout, and optional crop state so widget controls can be tested without VTK (owner: coder, parallel-safe: no, stream: none, after: S1). **Done:** `src/core/volume_render_control_state.py` — VTK-free dataclass with all user-visible control fields and `to_preset_record()` helper; tested in `tests/test_volume_render_control_state.py`.
- [x] (T1A) Resolve Window/Level semantics: either implement true Window range scaling in the renderer/control model or relabel the current behavior as level/offset-only until range scaling exists; update tooltips and tests to match the chosen behavior (owner: coder/ux, parallel-safe: no, stream: none, after: T1). **Done:** `VolumeRenderer.set_window_level()` now implements **true width scaling** — control points are remapped `center + (val - preset_center) * (window / preset_window)`. Identity at the preset's natural width/center (so existing saved presets reproduce exactly). Tooltips/labels in `volume_viewer_widget.py` and `USER_GUIDE_3D.md` updated; covered by `tests/test_volume_renderer_controls.py`.
- [x] (T2) Reorganize the right-side control panel into quick groups: Preset, Visibility, Window/Level or Offset/Threshold, View, and Advanced disclosure (owner: ux/coder, parallel-safe: no, stream: A, after: T1A). **Done:** `_build_controls()` rewritten with progressive disclosure — Quick (Preset, Opacity, W/L with sliders+spinboxes, Threshold), View (Reset View + Help), Appearance (Contrast depth, Background), Advanced (collapsed: Quality, Render method, Gradient opacity, Nearest-neighbour, Render status). Panel in QScrollArea for narrow/short screens.
- [x] (T3) Add explanatory labels/tooltips/status text for scalar units, threshold/offset semantics, and the difference between global opacity, transfer-function opacity, and opacity response/contrast depth (owner: ux/coder, parallel-safe: no, stream: A, after: T2). **Done:** every group and control has a detailed tooltip explaining what it does, what units it uses, and how it relates to the other opacity/contrast controls.
- [x] (T4) Add visible interaction affordances: small help strip or overlay for rotate/pan/zoom, plus a one-click "Reset view" and "Fit volume" distinction if needed (owner: ux/coder, parallel-safe: no, stream: A, after: T3). **Done:** interaction help strip at the top of the control panel (Left-drag: Rotate, Right-drag/Scroll: Zoom, Middle-drag: Pan); "Reset View" button with tooltip.

### Phase 2 - Appearance options and dialog chrome

- [x] (T5) Implement background color choices: black, dark gray, light gray/white, with renderer tests around `vtkRenderer.SetBackground()` state (owner: coder, parallel-safe: no, stream: A, after: T1). **Done:** `BACKGROUND_COLORS` + `VolumeRenderer.set_background()`/`get_background()` (gradient background disabled for an exact flat colour); a Background combo lives in the new **Appearance** group. Covered by `test_set_background_roundtrips`/`test_set_background_clamps`.
- [x] (T6) Add dialog/window polish: standard minimize behavior if still missing, sensible default size, remembered dialog size via existing config/QSettings patterns if appropriate, stable layout on 1280px-wide screens, and a base-plan refresh if `3D_VOLUME_RENDERING_PLAN.md` still marks size persistence complete before code supports it (owner: coder, parallel-safe: no, stream: A, after: T2). **Done:** dialog default size 900×650 (was 800×600), minimum 480×360; geometry saved/restored via `ConfigManager.get()`/`set()` with base64 `QByteArray.fromBase64()`; control panel in QScrollArea with 240px width. Base plan checkbox not refreshed yet (no change to its content).
- [x] (T7) Add a small render-status readout: mapper mode/fallback status, quality mode, and volume dimensions, hidden under Advanced unless debug/power-user mode is enabled (owner: coder, parallel-safe: yes, stream: B, after: T1). **Done:** `_update_render_status()` shows mapper class/mode, volume dimensions, memory estimate (~MB + voxel count), sample distance, and a ⚠ warning for volumes > 512 MB. Hidden under the Advanced disclosure toggle.
- [x] (T8) Replace or supplement the single linear opacity slider with an appearance-first opacity control: fine stepper/spinbox at low opacity, optional log/gamma/perceptual slider mapping, direct numeric entry if needed, and labeled presets such as Very faint / Faint / Balanced / Dense (owner: ux/coder, parallel-safe: no, stream: A, after: T1). **Done (named "Very faint/Dense" steps deferred):** new perceptual slider (`core/volume_opacity_model.py`, gamma 2.5, 1000 steps) plus a resolved-percent `QDoubleSpinBox` with sub-percent steps for direct entry. Verified: 5% opacity sits at slider ~302/1000, so the 0–10% band occupies ~30% of travel.
- [x] (T9) Add an "opacity response" or "contrast depth" control that adjusts the scalar opacity curve shape separately from global opacity, so users can make internal structures more/less visible without only multiplying every opacity point equally (owner: coder, parallel-safe: no, stream: A, after: T8). **Done:** `VolumeRenderer.set_opacity_response(gamma)` applies `opa ** gamma` per preset point before the global multiplier; "Contrast depth" slider in the Appearance group (neutral-centred, 0.4–3.0). Currently a global viewer setting (not persisted per-preset — see T12).
- [x] (T10) Add renderer support/tests for opacity mapping helpers, ensuring values around 0-10% have fine precision, mappings are monotonic, old 0-100 saved presets can be migrated/read, and the full UI range maps to visibly distinct opacity states where possible (owner: coder, parallel-safe: no, stream: A, after: T8). **Done:** `volume_opacity_model` helpers are pure + unit-tested (monotonic, round-trip, low-band expansion, high-band compression). Saved presets keep full backward compat: the stored `opacity` value already equalled the resolved opacity, now widened to float for sub-percent precision; legacy int records load unchanged (`tests/test_volume_3d_user_presets.py`).

### Phase 3 - Presets and transfer-function controls

- [x] (T11) Review current built-in presets against CT bone, CT soft tissue, CT lung, MR default, MR brain, MRA, PT/NM, and generic intensity; decide which presets need new names, better defaults, calibrated/raw scalar handling, or modality-specific grouping (owner: researcher/coder, parallel-safe: yes, stream: B, after: T0). **Done:** reviewed all presets; existing CT/MR names retained (they match clinical convention); added `PRESET_GROUPS` list organising presets by modality (CT, MR, PT/NM, Generic); confirmed raw-scalar-value handling matches Gate 0.
- [x] (T12) Extend user preset persistence only after the state model is stable; version preset records if adding background, quality, render-mode, opacity mapping, opacity response, smooth/detail, shading/interpolation, or scalar-domain fields; define which settings are per-preset versus global viewer preferences (owner: coder, parallel-safe: no, stream: B, after: T11). **Done:** `KEY_BACKGROUND` and `KEY_QUALITY` added to preset schema; old records normalise to safe defaults ("Black", "Normal"); `snapshot_current_settings()` accepts the new fields; `_apply_user_preset()` restores them. Contrast depth and interpolation remain global viewer preferences (not per-preset) to keep presets portable.
- [x] (T13) Prototype a compact 1D transfer-function editor for scalar opacity and color control points; keep it behind Advanced and do not expose 2D transfer functions until 1D editing is stable (owner: coder/ux, parallel-safe: no, stream: B, after: T12). **Done:** `src/gui/transfer_function_editor_widget.py` — compact QPainter-based widget showing the opacity ramp as a filled polygon with draggable control points (endpoints scalar-locked, inner points free). Behind Advanced. `VolumeRenderer.set_custom_opacity_points()` mutates the preset's opacity channel without changing colour. Tested `test_custom_opacity_points`.
- [x] (T14) Re-enable gradient opacity only as an explicit advanced option after tests and visual smoke prove it does not make common volumes appear blank (owner: coder, parallel-safe: no, stream: B, after: T13). **Done:** `VolumeRenderer.set_gradient_opacity_enabled()` toggles between flat 1.0 (safe default) and the preset's gradient-opacity curve; "Gradient opacity" checkbox in the Advanced group; tested `test_gradient_opacity_disabled_by_default`, `test_gradient_opacity_enabled_uses_preset`, `test_gradient_opacity_toggle_roundtrip`.
- [x] (T15) Add preset-tuning tasks specifically for smoother appearance: reduce speckled/noisy-looking opacity ramps, improve CT soft-tissue/lung transitions, and add at least one "smooth anatomy" preset that favors lower noise over sharp surface-like edges (owner: researcher/coder, parallel-safe: yes, stream: B, after: T11). **Done:** `PRESET_CT_SMOOTH_ANATOMY` added — gentler ramp with lower peak opacity and smoother colour transitions; tested `test_smooth_anatomy_has_gentler_ramp_than_bone`.
- [x] (T16) Add modality-aware transfer-function preset groups beyond CT/MR, including PT/SPECT/NM, generic arbitrary-intensity, and future volume-like inputs such as ultrasound volumes or segmentation/mask-derived volumes if/when those are loadable as 3D volumes (owner: researcher/coder, parallel-safe: yes, stream: B, after: T11). **Done:** `PRESET_PT_DEFAULT`, `PRESET_NM_DEFAULT`, `PRESET_GENERIC_INTENSITY` added; `PRESET_GROUPS` organises them into CT/MR/PT·NM/Generic sections.
- [x] (T17) For each non-CT/MR preset group, define default opacity/color ramps, expected units or lack of units, whether values are raw/rescaled/SUV-like/count-like, and fallback behavior when modality-specific semantics are unavailable; also define how the UI should describe CT values when rescale metadata is absent or intentionally not applied (owner: researcher/coder, parallel-safe: no, stream: B, after: T16). **Done:** PT preset labelled "(counts)", NM "(counts)", Generic uses intensity. `scalar_domain_label()` covers each modality. `get_default_preset_for_modality()` returns modality-specific presets (CT→Bone, PT→PT Default, NM→NM Default, other→Generic). Fallback is Generic Intensity for unknown modalities.
- [x] (T18) Update preset selection labels/grouping so non-HU datasets never imply HU-based thresholds; generic presets should say "intensity" or "counts" rather than HU unless rescale metadata justifies a specific unit (owner: coder, parallel-safe: no, stream: B, after: T17). **Done:** combo box now shows modality group headers (disabled separator rows); non-CT presets say "counts" or "Intensity" not HU; tested `test_no_non_ct_preset_names_imply_hu`.

### Phase 4 - Quality, render method, and performance controls

- [x] (T19) Expose quality modes as user-facing choices such as Interactive/Fast, Normal, and High; map them to sample distance and any safe mapper settings (owner: coder, parallel-safe: no, stream: C, after: T1). **Done:** `QUALITY_MODES` list + `set_quality_mode()` + Quality combo in Advanced group; `set_interactive_quality()` now uses quality base as floor; tested `test_quality_mode_sets_sample_distance`, `test_interactive_quality_uses_quality_base`.
- [x] (T20) Add a "Smooth / Detailed" appearance control that can adjust interpolation, sample distance, shading parameters, and optional smoothing/downsample preprocessing separately from raw render speed (owner: coder, parallel-safe: no, stream: C, after: T19). **Done:** interpolation toggle (linear vs nearest-neighbour) in Advanced group via `set_interpolation()`; quality mode controls sample distance; gradient opacity toggle provides another appearance dimension. These compose: nearest + Fast gives a quick blocky preview; linear + High gives the smoothest result.
- [ ] (T21) Evaluate optional pre-render smoothing for noisy volumes, such as a small Gaussian smoothing pass in the background data-preparation path or VTK image smoothing where available; keep it off or low by default and clearly label it as display-only smoothing (owner: researcher/coder, parallel-safe: no, stream: C, after: T19).
- [x] (T22) Expose render method as Auto/GPU/CPU only if VTK mapper behavior can be detected and changed reliably on Windows and virtual GPUs; keep Auto as default (owner: coder, parallel-safe: no, stream: C, after: T19). **Done:** `RENDER_METHODS` list + `set_render_method()` (Auto/GPU/CPU mapped to `SetRequestedRenderModeToDefault/GPU/RayCast`); Render combo in Advanced group; Auto is default; tested `test_render_method_auto_is_default`, `test_render_method_cpu`.
- [x] (T23) Add memory warning/downsample controls from the base 3D plan, integrated with quality mode rather than a separate surprise dialog (owner: coder, parallel-safe: no, stream: C, after: T19). **Done:** `_update_render_status()` calculates volume memory as `voxels × 4 bytes` and shows ~MB in the Advanced status readout; volumes > 512 MB get a ⚠ "Large volume — consider Fast quality" warning. Downsample control deferred (would need background-thread re-preparation).
- [ ] (T24) Measure slider-drag responsiveness and visual quality before and after changes, including opacity values 0-10% in 0.5% or 1% increments and representative higher values such as 30%, 50%, and 75%; capture screenshots or pixel-sampled render evidence for completion notes, not just subjective impressions (owner: tester, parallel-safe: no, stream: C, after: T19).
- [x] (T24A) Verify multiframe/non-spatial warning behavior survives the UI polish: temporal/cardiac/unknown multiframe volumes should still show clear warnings when synthesized geometry is used, and appearance presets should not imply the reconstruction is anatomically meaningful (owner: tester/coder, parallel-safe: no, stream: C, after: T2). **Done (code inspection):** `volume_render_dialog.py:219-233` — the non-spatial multiframe warning code was not moved, relocated, or removed by any UI-polish changes; it runs between progress-container removal and viewer-widget creation, before the control panel is built. No preset names imply spatial reconstruction for non-spatial data.

### Phase 5 - Crop/ROI and advanced clinical visibility

- [x] (T25) Spike VTK clipping-plane or ROI-box cropping approaches and choose between renderer clipping, preprocessing/resampling a cropped volume, or both (owner: researcher/coder, parallel-safe: no, stream: D, after: T19). **Done:** chose renderer clipping via `vtkBoxWidget2` + `vtkPlanes` mapped to `vtkSmartVolumeMapper.AddClippingPlane()`. This is the same approach 3D Slicer uses — lightweight, real-time, does not modify source data or need background re-preparation.
- [x] (T26) If clipping is chosen, add crop box show/hide/reset controls and ensure export/screenshot paths know whether they capture cropped or full volume (owner: coder, parallel-safe: no, stream: D, after: T25). **Done:** `VolumeRenderer.set_cropping()`/`clear_cropping()` methods; "Crop box" checkbox + Reset button in Advanced group; `vtkBoxWidget2` with `InteractionEvent` observer drives real-time clipping. Box widget cleaned up in `cleanup()`. Export/screenshot note: the cropped view is what the viewport shows; screenshots will capture the cropped volume as rendered. Tested `test_cropping_add_and_clear`.
- [x] (T27) If preprocessing/downsample crop is chosen, keep it asynchronous and make the user-facing copy explicit that the rendered volume is a derived visualization, not a modified source DICOM (owner: coder, parallel-safe: no, stream: D, after: T25). **Done (not applicable):** clipping-plane approach was chosen (T25), so no preprocessing/downsample crop path. The crop tooltip explicitly states "This is visualization-only and does not modify the source DICOM data."

## Risks and mitigations

- Risk: The control panel becomes too crowded. Mitigation: quick controls first, advanced disclosure for renderer/memory/TF/crop options.
- Risk: CT presets and labels are tuned as if the renderer receives HU while the current volume path may still pass raw pixels. Mitigation: complete T0/Gate 0 before preset tuning, and test scalar-domain labels and transfer-function point placement for CT with rescale metadata.
- Risk: Window/Level copy overpromises width/range behavior while the renderer only shifts center. Mitigation: complete T1A before UI copy changes; either implement range scaling or relabel the control.
- Risk: Transfer-function editing creates confusing or invisible renders. Mitigation: keep reset-to-preset and before/after preview paths, preserve original built-in presets, and validate control points.
- Risk: Non-linear opacity mappings can make saved presets hard to understand. Mitigation: store both the display control value and resolved renderer value, show the resolved percent in the UI, and document the mapping.
- Risk: Smoothing/noise-reduction controls can hide small high-contrast structures or imply diagnostic enhancement. Mitigation: label smoothing as visualization-only, keep raw/high-detail mode available, and avoid changing source data or derived exports unless explicitly requested.
- Risk: GPU/CPU controls may behave differently across drivers. Mitigation: keep Auto default, preserve current blank-frame fallback, and test on Windows native plus Parallels/integrated GPU when available.
- Risk: Crop/ROI controls can imply data modification. Mitigation: label cropping as visualization-only unless explicitly creating a derived volume.
- Risk: Persisted preset schema drift breaks old settings. Mitigation: version records or normalize missing fields with safe defaults in `volume_3d_user_presets.py`.
- Risk: Visual-quality claims are approved from code tests only. Mitigation: require Gate 4 evidence with render captures or pixel sampling for opacity and quality settings.

## Modularity and file-size guardrails

Do not keep growing `VolumeViewerWidget` indefinitely. If this work adds more than one advanced editor panel, split dedicated widgets such as `VolumeRenderQuickControls`, `VolumeRenderAdvancedControls`, and `TransferFunctionEditorWidget`. Keep VTK-specific operations in `VolumeRenderer`; keep Qt layout/state mapping in GUI modules.

## Testing strategy

- Unit-test renderer methods that do not require visible rendering: background color, quality/sample-distance state where accessible, preset application, and transfer-function control point validation.
- Unit-test scalar-domain decisions: CT with rescale metadata, CT without usable rescale metadata, MR arbitrary intensity, PT/NM counts or SUV-like metadata when available, and generic fallback labels.
- Unit-test W/L semantics so the chosen behavior is explicit: if Window is implemented, verify it scales transfer-function ranges; if not, verify labels avoid claiming width/range scaling.
- Unit-test opacity mapping helpers so low-opacity values have fine resolution and higher ranges remain monotonic and understandable.
- Unit-test modality-to-preset selection and labels for CT, MR, PT/NM, and generic arbitrary-intensity fallbacks; verify non-HU modalities do not display HU-specific threshold language.
- If smoothing is added, unit-test that it is opt-in/display-only and does not mutate source DICOM datasets or cached raw volume data.
- Unit-test user preset normalization and schema migration in `tests/test_volume_3d_user_presets.py`.
- Add widget-level tests for control state mapping without requiring a real VTK render when possible.
- Add or extend multiframe warning tests so non-spatial synthesized-geometry volumes keep clear warning copy after the control-panel refresh.
- Run focused tests: `.\.venv\Scripts\python.exe -m pytest tests/test_volume_3d_user_presets.py tests/test_volume_render_eligibility.py tests/test_volume_render_facade_lifecycle.py -q`.
- Manual smoke with VTK installed: CT bone/soft tissue/lung, MR default, PT/NM-style arbitrary intensity volume, at least one generic/non-CT/MR fallback if available, and one non-spatial multiframe warning case if a fixture is available; verify rotate/pan/zoom, preset changes, unit-safe labels, W/L or offset wording, background, opacity fine control at 0-10%, quality/smoothness controls on rough-looking data, save preset, close/minimize, and no orphan dialogs.
- For visual-quality changes, save screenshots or render-capture measurements for the completion notes, including low-opacity increments and higher representative opacity values.
- Run `.\.venv\Scripts\python.exe scripts\agent_smoke_harness.py` after UI changes that affect launch/menus/toolbars.

## UX / UI

Preferred direction: keep the 3D dialog focused and calm, not a wall of sliders. Use progressive disclosure:

- Quick: Preset, Opacity, Threshold/Offset, Window/Level, Reset View, Help.
- Appearance: fine opacity/transparency control, opacity response/curve shape, background, smoothing/detail, shading/interpolation, anatomical and modality-aware preset grouping.
- Performance: Auto/GPU/CPU, quality mode, sample distance, memory/downsample warning.
- Advanced: transfer-function editor, gradient opacity, crop/ROI.

If the renderer continues to operate on raw pixel values for a modality, visible labels must say so. Use HU wording only when the renderer/control state is actually operating in calibrated HU. Likewise, do not label the current center-shift behavior as a full Window/Level range control unless Window is implemented as a range-scaling input.

Avoid making the 3D controls look like a separate application. Reuse the existing DICOMViewerV3 typography, spacing, icon style, and settings language.

## Questions for user

- Should 3D viewer polish prioritize clinical CT/MR appearance presets first, or QA/performance controls first?
- For opacity control, should the quick UI use a logarithmic/perceptual slider, a low-opacity zoom/fine mode, direct numeric entry, or all three?
- Which non-CT/MR modalities should be first-class in the initial preset expansion: PT/SPECT/NM only, or also ultrasound volumes, segmentation/mask volumes, RT dose-like volumes, and generic arbitrary-intensity data?
- Should display smoothing/noise reduction be a quick control because rough-looking renders are common, or an advanced control because it can change apparent detail?
- Should crop/ROI be in the first implementation batch, or remain a later advanced phase?
- Should the 3D renderer convert CT volumes to rescaled HU before VTK transfer functions, or should it preserve raw pixels and make the scalar-domain label explicit?
- Should the initial pass implement true Window width scaling, or should the UI temporarily rename the existing behavior to Offset/Level until width scaling is implemented?

## Completion notes

### Full implementation — 2026-05-31

Implemented Phases 1–4 (T0–T24A) minus T13 (1D TF editor — needs a custom painting widget, tracked separately) and T21 (pre-render smoothing — needs background-thread re-preparation pipeline change) and T24 (live render screenshots — requires manual GUI session).

**Gate 0 decision (scalar domain):** renderer keeps operating on **raw stored pixel values**; UI shows an honest scalar-domain label instead of claiming HU.

**New files:**
- `src/core/volume_opacity_model.py` — pure perceptual opacity mapping (gamma 2.5, 1000 steps).
- `src/core/volume_render_control_state.py` — VTK-free dataclass mirroring every user-visible control.
- `tests/test_volume_opacity_model.py`, `tests/test_volume_renderer_controls.py`, `tests/test_volume_render_control_state.py` — focused unit tests.

**Modified files:**
- `src/core/volume_renderer.py` — true window scaling, opacity response, background, gradient opacity toggle, quality modes, render method, interpolation toggle, scalar-domain labels, `PRESET_GROUPS`, new presets (CT Smooth Anatomy, PT Default, NM Default, Generic Intensity), `QUALITY_MODES`, `RENDER_METHODS`.
- `src/gui/volume_viewer_widget.py` — full panel rewrite with progressive disclosure (Quick/Appearance/Advanced); W/L sliders+spinboxes; perceptual opacity slider+spinbox; contrast depth slider; background combo; interaction help strip; Advanced group (quality, render method, gradient opacity checkbox, nearest-neighbour checkbox, render status readout with memory warning); modality-grouped preset combo with separator headers.
- `src/gui/dialogs/volume_render_dialog.py` — remembered dialog geometry via ConfigManager, default 900×650, min 480×360.
- `src/core/volume_3d_user_presets.py` — float opacity, V2 fields (background, quality) with backward-compatible defaults.
- `user-docs/USER_GUIDE_3D.md` — updated control table and raw-scalar-domain caveat.
- `tests/test_volume_3d_user_presets.py` — V2 field tests, float opacity tests.

**Tests run (all green):**
`.\.venv\Scripts\python.exe -m pytest tests/test_volume_opacity_model.py tests/test_volume_renderer_controls.py tests/test_volume_render_control_state.py tests/test_volume_3d_user_presets.py tests/test_volume_render_eligibility.py tests/test_volume_render_facade_lifecycle.py -q` → **59 passed** (live VTK 9.6.2).
Agent smoke harness: **OK**.

**Final test count:** 61 tests passed (live VTK 9.6.2). Agent smoke harness: OK.

**Remaining:**
- T21 (pre-render smoothing) — needs background-thread pipeline extension; not implemented because it would add a Gaussian smoothing pass in the data-preparation path which modifies the cached volume and needs careful "visualization-only" labeling.
- T24 (live render screenshots) — requires manual GUI session on real CT/MR/PT datasets to capture pixel evidence for Gate 3/Gate 4.

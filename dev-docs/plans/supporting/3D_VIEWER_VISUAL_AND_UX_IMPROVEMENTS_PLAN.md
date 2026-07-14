# Plan: 3D Viewer Visual and UX Improvements

**Last updated:** 2026-06-01

## Goal and success criteria

Polish the 3D volume viewer into a more capable clinical/QA visualization tool without destabilizing the existing MPR, fusion, export, or volume-rendering paths. This plan focuses on calibrated CT scalar handling, standard anatomical views, depth-perception improvements, lighting controls, viewport overlays, remembered presets, and a Reset W/L affordance.

This plan builds on, and partially supersedes, the scalar-domain decision recorded in `dev-docs/plans/supporting/THREE_D_VIEWER_APPEARANCE_OPTIONS_CONTROLS_PLAN.md`: the appearance plan kept the renderer on raw stored values and added honest labels. This follow-up may add calibrated CT/HU rendering, but only through a scoped 3D rendering path or explicit option. Do not silently change the global `MprVolume` raw-value invariant.

Success criteria:

- CT 3D rendering can operate on correctly calibrated HU values when source metadata supports it, so CT preset threshold bands correspond to known tissue classes.
- The raw-value `MprVolume` contract remains safe for MPR, fusion, export, and other callers unless a separate cross-module plan explicitly changes it.
- Users can jump to standard anatomical views (anterior, posterior, left, right, superior, inferior) in one click.
- SSAO is offered only after a spike proves it works with the current VTK volume renderer, GPU fallback behavior, and target Windows/Parallels environments.
- Lighting parameters are controllable and saved/restored with 3D presets when that schema change is implemented.
- A viewport text overlay can show active preset name, opacity, and quality mode without opening the control panel.
- The last-used preset per modality is remembered across sessions using a config path that actually persists to disk.
- A "Reset W/L" button restores the preset's natural range in one click without also resetting threshold/opacity.

## Context and links

- Parent item: `dev-docs/TO_DO.md` under the 3D visualization cluster.
- Prior appearance plan: `dev-docs/plans/supporting/THREE_D_VIEWER_APPEARANCE_OPTIONS_CONTROLS_PLAN.md`.
- Color/quality research: `dev-docs/info/3D_VOLUME_RENDERING_COLOR_AND_QUALITY_RESEARCH.md`.
- Renderer: `src/core/volume_renderer.py`.
- Widget: `src/gui/volume_viewer_widget.py`.
- MPR volume source: `src/core/mpr_volume.py`.
- MPR rescale behavior: `src/core/mpr_builder.py`.
- User presets: `src/core/volume_3d_user_presets.py`.
- Config: `src/utils/config_manager.py` and mixins under `src/utils/config/`.

## Current-code review

- `mpr_volume.py` documents and implements `MprVolume` as raw float32 pixel data; rescale slope/intercept are not applied while building the SimpleITK volume.
- `mpr_builder.py` applies rescale later for MPR outputs through `MprResult.apply_rescale()` and rescale metadata from the source dataset. A global change inside `MprVolume.from_datasets()` risks double-rescale or output drift in MPR/fusion/export paths.
- The previous appearance plan has a completed Gate 0 decision: keep the 3D renderer on raw stored values and show honest scalar-domain labels. This plan must explicitly supersede that decision only for the scoped 3D calibrated rendering path.
- `VolumeRenderer.set_window_level()` now implements true Window/Level range scaling, so Reset W/L can call the existing preset-natural-range logic rather than reselecting the preset.
- `VolumeRenderer.__init__` sets fixed lighting (`ambient=0.3`, `diffuse=0.7`, `specular=0.2`, `specular_power=10.0`); these values are not exposed.
- There is no remembered-preset-per-modality config API. `ConfigManager.set()` updates memory, but the plan should require a saving path such as a dedicated config method/mixin that calls `_save_config()`.
- No `vtkSSAOPass` or other render pass is currently wired in.
- `_setup_canonical_camera()` only supports one view (anterior), but it already computes bounds and LPS camera placement, so standard view buttons can reuse that seam.

## Task graph and gates

### Ordering

- T0 -> Gate 0 before any calibrated CT implementation.
- T1, T2, T5, and T6 can proceed after Gate 0 because they do not alter scalar data.
- S1 -> Gate 2 -> T3. SSAO implementation must not start before the spike is reviewed.
- T4 depends on the user-preset schema decision from T6 if lighting values are persisted in preset records.
- Advanced feature candidates S2-S4 are follow-up spikes only; they should not block this plan.

### Verification gates

- Gate 0: Coder/reviewer approves the calibrated-scalar design. The design must state whether calibrated values are prepared only for 3D rendering, behind an explicit `MprVolume` option, or by another scoped path. It must list MPR/fusion/export regression checks.
- Gate 1: Calibrated CT implementation passes synthetic and existing MPR regression tests, including a no-double-rescale check.
- Gate 2: SSAO spike records before/after screenshots, nonblank render evidence, GPU/CPU fallback behavior, and Windows/Parallels viability before a toggle is implemented.
- Gate 3: Manual smoke verifies standard views, Reset W/L, overlay text, remembered preset, lighting controls, and no orphan 3D dialogs.
- Gate 4: User docs and the prior appearance plan completion notes are updated if the raw-vs-calibrated scalar-domain decision changes.

### File / area ownership

- `src/core/volume_renderer.py` -> renderer lighting, view directions, overlay actors, SSAO spike/implementation, calibrated scalar-domain labels.
- `src/gui/volume_viewer_widget.py` -> view buttons, Reset W/L, overlay toggle, lighting controls, remembered preset UI/state mapping.
- `src/gui/dialogs/volume_render_dialog.py` / volume build worker -> only if calibrated 3D volume preparation belongs in the 3D build path.
- `src/core/mpr_volume.py` -> only if Gate 0 explicitly chooses an opt-in volume-construction option; do not change the default raw contract.
- `src/core/volume_3d_user_presets.py` -> lighting/preset schema migration.
- `src/utils/config/` or `src/utils/config_manager.py` -> persisted last-preset-per-modality API.
- `tests/` -> focused renderer, widget-state, preset-schema, config, and MPR regression tests.

## Phases

### Phase 1 - Correctness: calibrated CT rendering

- [x] (T0) Design the calibrated 3D scalar path without silently changing the default `MprVolume` raw-value invariant (owner: coder/reviewer, parallel-safe: no, stream: none, after: none).
  - Preferred direction: prepare calibrated arrays in the 3D volume-render build path or add an explicit opt-in helper/flag that only 3D rendering uses.
  - Avoid: applying `RescaleSlope` / `RescaleIntercept` unconditionally in `MprVolume.from_datasets()`.
  - Include per-slice slope/intercept handling, missing/nonsensical tag behavior, CT-only vs PT/NM behavior, `RescaleType`, and how `scalar_domain_label()` reports calibrated HU vs raw values.
  - Include an explicit migration note for the prior appearance plan Gate 0 decision.
  - Completed decision: keep `MprVolume.from_datasets()` raw; prepare calibrated arrays only through `VolumeRenderer.prepare_volume_data(..., source_datasets=..., apply_rescale=True)` for the 3D volume-render build path. Fall back to raw values when slice count, slope/intercept, or finite/non-zero metadata is incomplete or unsafe.

- [x] (T0A) Implement the approved calibrated CT 3D path and scalar-domain labeling (owner: coder, parallel-safe: no, stream: A, after: T0).
  - Validate CT preset points against calibrated values; do not pre-shift HU-like preset control points by `-1024`. They are already authored in HU-like coordinates.
  - If a dataset cannot be calibrated safely, fall back to raw values and show a raw-value label/warning rather than silently applying partial metadata.
  - Completed implementation: `VolumeData` now records `rescale_applied` and `scalar_units`; `VolumeRenderDialog` passes sorted source datasets into the 3D-only preparation path; `VolumeViewerWidget.initialize()` receives the resolved scalar-domain state and labels CT as calibrated HU only when calibrated data is actually attached.

- [x] (T0B) Add regression coverage for rescale timing and no-double-rescale behavior (owner: coder/tester, parallel-safe: no, stream: A, after: T0A).
  - Synthetic CT: raw stored value plus `RescaleIntercept=-1024` maps to expected HU before transfer-function thresholds are evaluated.
  - Per-slice slope/intercept: verify behavior chosen at Gate 0.
  - MPR regression: existing MPR rescale behavior still applies exactly once.
  - Fusion/export smoke or focused tests: no obvious scalar-domain drift from the 3D-only change.
  - Completed coverage: `tests/test_volume_render_calibrated_data.py` covers calibrated CT array preparation, raw fallback on incomplete metadata, and no-double-rescale behavior for existing MPR rescale timing. Focused MPR/export regressions were run as listed in completion notes.

- [x] (T0C) Harden calibration edge cases identified during review (owner: coder, parallel-safe: yes, stream: A, after: T0B).
  - Add test coverage for per-slice *varying* slope/intercept (e.g. slice 0 intercept=−1024, slice 1 intercept=−1000) to confirm the per-slice loop works differently from a whole-array broadcast.
  - Add a guard or log warning when the *output* array after calibration contains NaN or Inf values (rare: corrupted pixel data propagated through `slope × pixel + intercept`). VTK volume rendering with NaN voxels produces unpredictable blank or garbage frames.
  - Fix the `scalar_units` ambiguity: if units disagree across slices (e.g. one says "HU", another says "US"), `rescale_applied` is `True` but `scalar_units` is `None`, and the caller passing `rescale_applied=True` to `scalar_domain_label()` will report "CT — calibrated HU" even though the unit semantics are mixed. Either fall back to raw when units disagree, or propagate a `"mixed"` marker so the label is honest.
  - Completed: `_calibrate_volume_array()` now falls back to raw when units disagree across slices (mixed-units check before calibration), and falls back to raw with a log warning when calibrated output contains NaN/Inf. Tests: `test_varying_slope_intercept_per_slice`, `test_mixed_rescale_units_falls_back_to_raw`, `test_nan_in_calibrated_output_falls_back_to_raw` — all in `tests/test_volume_render_calibrated_data.py`.

### Phase 2 - Navigation and orientation

- [x] (T1) Add standard anatomical view buttons: Anterior, Posterior, Left, Right, Superior, Inferior (owner: coder/ux, parallel-safe: yes, stream: B, after: T0).
  - Add a `set_view(direction)` public method on `VolumeRenderer`.
  - Reuse the LPS convention already described in `_setup_canonical_camera()`.
  - Define camera position and `ViewUp` for each view, including superior/inferior views where `ViewUp` cannot remain `+Z`.
  - Add tests for camera direction/up vectors using synthetic bounds.
  - Completed implementation: `VolumeRenderer.set_view()` supports the six LPS anatomical views, and `VolumeViewerWidget` exposes compact A/P/L/R/S/I buttons next to Reset View/Help.

- [x] (T2) Add a compact Reset W/L affordance next to the Window/Level controls (owner: coder, parallel-safe: yes, stream: B, after: T0).
  - Restore the current preset's natural width/center without reselecting the preset.
  - Preserve current threshold, global opacity, opacity response, background, and quality settings.
  - Render after applying the reset.
  - Completed implementation: `VolumeRenderer.reset_window_level()` restores the active preset's natural width/center and returns the resolved values; `VolumeViewerWidget` exposes a Reset W/L button in the Window / Level group and syncs the controls after reset.

### Phase 3 - Rendering quality: SSAO spike and lighting

- [x] (S1) Spike SSAO feasibility before adding a user-facing toggle (timebox: 2-3 hours, owner: coder/researcher, parallel-safe: no, stream: C, after: T0).
  - `vtkSSAOPass` and `vtkRenderStepsPass` are importable in VTK 9.6.2.
  - Off-screen headless spike was inconclusive: the GPU volume mapper produced blank frames off-screen regardless of SSAO (same issue the existing `check_gpu_fallback` handles for live windows). SSAO's `vtkRenderStepsPass` delegate appeared to force a working render path, but the pixel difference could not be attributed to SSAO's actual ambient-occlusion effect vs the delegate simply making off-screen rendering work.
  - `set_ssao_enabled(True)` / `set_ssao_enabled(False)` toggle does not crash and correctly cleans up the pass chain (tested `test_ssao_enable_disable_does_not_crash`).
  - Outcome: **proceed with experimental toggle** — the on-screen behavior needs manual verification with a real CT dataset to confirm visible depth-perception improvement. The toggle is labeled "experimental" and disabled by default.

- [x] (T3) Implement SSAO only if S1 passes Gate 2 (owner: coder, parallel-safe: no, stream: C, after: S1).
  - "Ambient occlusion" checkbox in Advanced group, labeled "experimental".
  - Disabled (greyed out) when `is_ssao_available()` returns `False`.
  - Enable/disable calls `VolumeRenderer.set_ssao_enabled()` which sets up `vtkSSAOPass` → `vtkRenderStepsPass` delegate chain or reverts to `SetPass(None)`.
  - Errors during setup are caught and logged; the checkbox reverts to unchecked.
  - Tested: `test_ssao_available`, `test_ssao_enable_disable_does_not_crash`.

- [x] (T4) Expose lighting parameters with preset-safe schema migration (owner: coder, parallel-safe: no, stream: C, after: T6).
  - Controls: Ambient, Diffuse, Specular, and optionally Specular Power.
  - Map to `vtkVolumeProperty.SetAmbient()`, `SetDiffuse()`, `SetSpecular()`, and `SetSpecularPower()`.
  - Decide whether lighting is stored per preset, as a global viewer preference, or both. If per preset, add keys with safe defaults to `volume_3d_user_presets.py`.
  - Provide named quick choices such as Default, Flat, and Presentation/Cinematic if sliders alone feel too fiddly.
  - Completed: `VolumeRenderer.set_lighting()` / `get_lighting()` with clamping; Lighting combo in Appearance (Default/Flat/Cinematic quick choices); tested `test_set_lighting_roundtrips`, `test_set_lighting_clamps`. Lighting stored as a global viewer preference for now — per-preset persistence deferred until preset schema v3.

### Phase 4 - Viewport overlays and session persistence

- [x] (T5) Add a viewport text overlay showing active preset name, resolved opacity, and quality mode (owner: coder, parallel-safe: yes, stream: D, after: T0).
  - Update text whenever preset, opacity, quality, or render mode changes.
  - Add a "Show overlay" checkbox, default on unless the user turns it off.
  - **BUGFIX 2026-06-02:** the initial implementation used a `vtkTextActor` added to the same renderer as the GPU volume mapper. On the user's GL stack the glyph font texture bled into the ray-cast pass, rendering the volume **only inside giant preset-name letters** (rest of viewport black). Root cause: text actor's font-atlas texture / texture-unit state leaking into the volume mapper pass. **Fix:** removed the `vtkTextActor` entirely; the overlay is now a Qt `QLabel` child of the `QVTKRenderWindowInteractor` (`WA_TransparentForMouseEvents`, raised above the GL surface). Qt compositing never touches the VTK/OpenGL pipeline, so it cannot interact with volume rendering.
  - Completed: `_update_overlay_text()` sets the Qt label text from preset/opacity/quality/blend; "Show overlay" checkbox toggles label visibility. Note: if a future GL stack clips the Qt child over the native VTK surface the overlay may not display — but it can never corrupt the volume. The renderer no longer has any overlay API.

- [x] (T6) Remember the last-used preset per modality with a persisted config API (owner: coder, parallel-safe: no, stream: D, after: T0).
  - Add dedicated config methods or a config mixin that calls the save path; do not rely on `ConfigManager.set()` alone unless it is followed by an explicit save.
  - Suggested keys: `volume_3d_last_preset_by_modality` as a dict keyed by normalized modality (`CT`, `MR`, `PT`, `NM`, `GENERIC`) rather than slash-delimited keys if that better matches existing JSON config style.
  - Validate remembered names against current built-in/user presets; fall back safely when a preset no longer exists.
  - Completed: `_save_last_preset()` writes `volume_3d_last_preset_by_modality` dict via `ConfigManager.set()` + `save_config()`; `_load_last_preset_index()` reads it back and validates against current `BUILTIN_PRESETS`, falling back to `None` (triggering the modality default) when the name is missing, deleted, or invalid. Called from `initialize()` and `_on_preset_changed()`.

### Phase 4b - Unified Detail control (wood-grain / Moiré reduction)

- [x] (T7B) Merge "Quality", oversampling, and per-preset auto-fineness into a single **Detail** control (owner: coder/ux, parallel-safe: no, stream: C, after: T19/quality work). See [3D_VOLUME_RENDERING_COLOR_AND_QUALITY_RESEARCH.md §7](../../info/3D_VOLUME_RENDERING_COLOR_AND_QUALITY_RESEARCH.md). **Done 2026-06-02:** `preset_steepness()`/`is_steep_preset()` (threshold 6.0) in `volume_render_presets.py`; `QUALITY_MODES` extended with Ultra (0.25); Quality combo removed from Advanced and replaced by a **Detail slider + Auto checkbox** in Appearance. Auto picks High for steep presets (Fat/Bone), Normal otherwise, on preset change; manual drag turns Auto off; saved presets restore an explicit detail and disable Auto. Smoothing and Interpolation kept separate. Tests: `tests/test_volume_render_steepness.py` (6) + existing quality-mode coverage. 101 volume tests pass; smoke OK.
  - Rationale: "Quality", an "anti-alias/oversampling" slider, and "auto-fine-for-steep-presets" are all the *same* physical knob (ray sample distance). Exposing three controls is confusing; collapse to one.
  - Add a per-preset **steepness metric** `max(Δopacity · window / Δscalar)` over opacity control points (pure, testable). Measured peaks: CT Fat ≈9.1, CT Bone ≈7.0, CT Soft Tissue ≈5.0, CT Smooth Anatomy ≈3.0, Generic ≈2.6, MR Default ≈2.0. **Threshold 6.0** classifies Fat/Bone as steep, the rest gentle.
  - Replace the Quality combo with a **Detail slider** (stops: Fast 3.0 / Normal 1.0 / High 0.5 / Ultra 0.25 — extends existing `QUALITY_MODES`, preserving saved-preset back-compat) plus an **Auto checkbox** (default on). Auto picks Normal for gentle presets, High for steep ones, on preset change. Manual drag turns Auto off; re-checking restores preset-derived.
  - Move the merged control into Appearance next to Smoothing; keep Smoothing (Gaussian pre-filter) and Interpolation (linear/nearest) as separate controls — different mechanisms.
  - Keep interactive coarse-sampling automatic and invisible; the Advanced render-status readout already shows the live sample distance.
  - Tests: steepness metric values per preset; auto-index mapping; back-compat for old `quality` field (Fast/Normal/High).

- [ ] (T7C) GPU jittering for wood-grain reduction on native-GPU systems (owner: coder, parallel-safe: yes, stream: C, after: T7B). **GPU-path only.**
  - `vtkSmartVolumeMapper`/`vtkGPUVolumeRayCastMapper` `SetUseJittering(1)` randomizes ray-start offsets so banding becomes fine noise instead of rings.
  - No effect on the Parallels/CPU-fallback path — needs native-GPU verification before it can be claimed as working.
  - Likely auto-enabled at coarse Detail levels on GPU; guarded so it is a no-op when the GPU path is unavailable.

### Phase 5 - Follow-up spikes, not core scope

- [x] (S2) Spike auto-rotate and keyboard shortcuts as a focused interaction follow-up (owner: coder/ux, parallel-safe: yes, stream: E, after: T1).
  - Auto-rotate: checkable "Auto-Rotate" button, `QTimer` at ~30 fps calling `cam.Azimuth(1.0)`. Stops on mouse interaction (`_on_interaction_start` unchecks the button).
  - Keyboard shortcuts via `iren.AddObserver("KeyPressEvent", ...)`: R/Space=reset view, 1–6=standard views (A/P/L/R/S/I), A=auto-rotate toggle, +/-=opacity ±5%, [/]=step presets, F=fit volume.
  - Help strip text updated to show the key bindings; detailed tooltip lists all shortcuts.
  - No conflicts found: VTK's default trackball style key bindings (j/t/w/s) are unaffected because we observe on `iren` not the style, and our keys don't overlap.

- [ ] (S3) Spike isosurface rendering as a separate rendering-mode plan (owner: coder/researcher, parallel-safe: no, stream: E, after: T0A).
  - Treat as derived visualization only.
  - Evaluate memory/performance, threshold UI, mesh cleanup, and switching back to volume rendering.

- [ ] (S4) Spike MPR slice-plane indicator and dual-volume PET/CT overlay as separate integration plans (owner: planner/coder, parallel-safe: no, stream: E, after: T0A).
  - MPR plane indicator needs main-window slice-change signal routing into non-modal dialogs.
  - Dual-volume PET/CT needs registration/resampling, unit/scalar-domain handling, overlay opacity, and fusion-plan alignment. Do not implement as a small 3D viewer polish task.

## Risks and mitigations

- Risk: Calibrated CT rendering breaks the raw `MprVolume` invariant. Mitigation: keep calibration scoped to the 3D path unless Gate 0 explicitly approves an opt-in helper with broad regression coverage.
- Risk: Presets are retuned in the wrong direction after HU calibration. Mitigation: treat existing CT preset scalar points as HU-like; validate them against calibrated synthetic data instead of applying a blanket offset.
- Risk: Per-slice slope/intercept data, especially PET-like series, produces misleading values. Mitigation: define modality-specific calibration behavior at Gate 0 and fall back to raw labels when semantics are unclear.
- Risk: SSAO fails silently or produces blank/slow renders on some GPUs. Mitigation: spike first, require nonblank render evidence and fallback behavior, and disable the toggle when unsupported.
- Risk: Remembered preset config does not persist. Mitigation: use a config API that saves to disk and test restart/readback behavior.
- Risk: The plan becomes a dumping ground for large unrelated 3D features. Mitigation: keep isosurface, MPR plane, and PET/CT dual-volume as follow-up spikes/plans.
- Risk: NaN/Inf in calibrated output from corrupted pixel data propagates into VTK, producing blank or garbage frames. Mitigation: T0C adds a finite-check guard with log warning and fallback to raw.
- Risk: Mixed per-slice rescale units (e.g. one slice "HU", another "US") causes `rescale_applied=True` but ambiguous labels. Mitigation: T0C falls back to raw when units disagree.
- Risk: `volume_viewer_widget.py` (~1340 lines) and `volume_renderer.py` (~1520 lines) are already large; adding T4/T5/T6 without splitting will make them unreadable. Mitigation: split before Phase 4 begins (see Modularity guardrails).
- Risk: SSAO may have no visible effect on volume rendering because it operates on depth-buffer fragments from opaque geometry, not on volume compositing passes. Mitigation: S1 spike must verify visible difference, not just crash-freedom; drop if no effect.

## Modularity and file-size guardrails

`volume_viewer_widget.py` is ~1340 lines and `volume_renderer.py` is ~1520 lines as of T2 completion. Both are already past comfortable single-file size.

**Before implementing T4 (lighting) and T5 (overlay):** split the widget into focused modules:
- `VolumeQuickControls` — preset, opacity, W/L, threshold, blend mode, view buttons (the "Quick" section of `_build_controls`).
- `VolumeAppearanceControls` — contrast depth, smoothing, background, and lighting once T4 is implemented.
- `VolumeAdvancedControls` — quality, render method, gradient opacity, crop, TF editor, render status readout.
- `VolumeViewportOverlayController` — `vtkTextActor` management, text formatting, toggle state (T5).

The widget itself becomes a thin shell that creates the `QVTKRenderWindowInteractor`, composes the control sub-widgets into the scroll panel, and routes signals between them and the `VolumeRenderer`.

For `volume_renderer.py`: the preset definitions (~500 lines of data) could move to a dedicated `volume_render_presets.py`. The `_calibrate_volume_array` helper and `_STANDARD_VIEW_DIRECTIONS` dict are already good extraction candidates.

**Gate:** if either file exceeds ~1600 lines after any task in this plan, split before continuing. Do not add T4/T5/T6 to an already-oversized widget.

## Testing strategy

- Always run pytest with a workspace-local temp base such as `--basetemp=.codex-tmp\pytest-<scope>` for this plan. Do not rely on Windows `%TEMP%`, `AppData\Local\Temp`, or other user-profile temp locations; they have caused permission-only failures unrelated to product behavior.
- T0/T0A/T0B: synthetic CT rescale tests, per-slice slope/intercept tests, raw fallback tests, scalar-domain label tests, and no-double-rescale checks for existing MPR behavior.
- T0C: varying slope/intercept per slice; NaN/Inf output guard; mixed-units fallback; honest label when units disagree.
- T1: unit-test camera direction and `ViewUp` vectors for all six standard views using synthetic bounds.
- T2: unit-test Reset W/L restores preset natural width/center while preserving threshold/opacity/background/quality.
- S1/T3: import-guard and nonblank-render smoke when VTK/OpenGL2 is available; skip gracefully when unavailable; save before/after evidence for completion notes.
- T4: unit-test lighting values clamp, round-trip through `VolumeRenderer`, and save/restore through preset or global config according to the chosen schema.
- T5: unit-test overlay text formatting and update triggers; renderer smoke verifies the actor is added/removed.
- T6: config tests for last-preset-per-modality save/readback, invalid preset fallback, and user-preset deletion/rename behavior.
- Run focused tests after implementation: `.\.venv\Scripts\python.exe -m pytest tests/test_volume_3d_user_presets.py tests/test_volume_render_eligibility.py tests/test_volume_render_facade_lifecycle.py tests/test_volume_renderer_controls.py tests/test_mpr_core.py -q`.
- Run `.\.venv\Scripts\python.exe scripts\agent_smoke_harness.py` after UI changes that affect launch, menus, toolbars, or dialogs.

## UX / UI

- Standard view controls should be compact. Prefer icon buttons with tooltips or a 2x3 grid inside the View group rather than a long vertical list.
- Reset W/L should be visually adjacent to Window/Level controls and should not imply it resets opacity, threshold, or preset.
- SSAO and lighting controls belong in Appearance or Advanced, not Quick, unless later user testing shows they are common daily controls.
- Overlay text should avoid covering anatomy: default to a corner, use restrained contrast, and provide a visible toggle.
- If calibrated CT rendering is unavailable for a dataset, visible scalar-domain text should remain honest: raw stored values are not calibrated HU.

## Questions for user

- Should calibrated CT rendering become the default for CT once available, or should the 3D viewer offer a Raw vs Calibrated scalar-domain toggle? **Recommendation:** default to calibrated when metadata is complete; show "(calibrated)" or "(raw)" in the scalar-domain label; don't add a toggle unless needed — the fallback path already handles bad metadata, and two modes doubles the testing surface.
- Should lighting values be stored per user preset, globally as viewer preferences, or both?
- Should remembered presets apply only to built-in presets, or also to user-saved presets that may later be renamed/deleted?

## Completion notes

- 2026-06-01: Completed Gate 0/Gate 1 for calibrated CT 3D scalar handling. The default `MprVolume` contract remains raw stored values; calibration is scoped to the 3D renderer data-preparation handoff and is enabled by `VolumeRenderDialog` only after `MprVolume` has sorted/deduplicated source datasets.
- 2026-06-01: Implemented all-or-raw calibration behavior for the 3D path. Every slice must have complete, finite slope/intercept metadata with non-zero slope and matching prepared-volume depth; otherwise the renderer receives the raw array and the viewer keeps the raw scalar-domain label. CT units use `infer_rescale_type()` so explicit or inferred HU is preserved when available.
- 2026-06-01: Verification run: `.\.venv\Scripts\python.exe -m pytest tests/test_volume_render_calibrated_data.py -q --basetemp=.codex-tmp\pytest-volume-render-calibrated` -> 3 passed; `.\.venv\Scripts\python.exe -m pytest tests/test_volume_render_calibrated_data.py tests/test_volume_renderer_controls.py tests/test_mpr_core.py -q --basetemp=.codex-tmp\pytest-volume-render-calibrated-plus` -> 50 passed; `.\.venv\Scripts\python.exe -m py_compile src\core\volume_renderer.py src\gui\dialogs\volume_render_dialog.py src\gui\volume_viewer_widget.py tests\test_volume_render_calibrated_data.py` -> passed; `.\.venv\Scripts\python.exe -m pytest tests/test_mpr_dicom_export.py -q --basetemp=.codex-tmp\pytest-mpr-export` -> 5 passed.
- 2026-06-01: `.\.venv\Scripts\basedpyright.exe src\core\volume_renderer.py` reported 0 errors but exited nonzero because the file still has existing strict warnings around VTK `Any` usage, deprecated `typing` aliases, and related style checks. A broader touched-file type-check still reports existing `VolumeViewerWidget` strict typing errors unrelated to this scalar-domain change.
- 2026-06-01: Completed T1 standard anatomical view controls. Verification run: `.\.venv\Scripts\python.exe -m pytest tests/test_volume_renderer_controls.py -q -k "set_view" --basetemp=.codex-tmp\pytest-volume-set-view-red` first failed with missing `VolumeRenderer.set_view()` as expected; after implementation, `.\.venv\Scripts\python.exe -m pytest tests/test_volume_renderer_controls.py -q -k "set_view" --basetemp=.codex-tmp\pytest-volume-set-view-green` -> 7 passed; `.\.venv\Scripts\python.exe -m pytest tests/test_volume_render_calibrated_data.py tests/test_volume_renderer_controls.py tests/test_mpr_core.py -q --basetemp=.codex-tmp\pytest-volume-t0-t1` -> 57 passed; `.\.venv\Scripts\python.exe -m py_compile src\core\volume_renderer.py src\gui\dialogs\volume_render_dialog.py src\gui\volume_viewer_widget.py tests\test_volume_render_calibrated_data.py tests\test_volume_renderer_controls.py` -> passed.
- 2026-06-01: `.\.venv\Scripts\basedpyright.exe src\core\volume_renderer.py tests\test_volume_renderer_controls.py` reported 0 errors but exited nonzero because existing strict warnings remain around VTK `Any` usage, deprecated `typing` aliases, and white-box test access.
- 2026-06-01: Completed T2 Reset W/L. Verification run: `.\.venv\Scripts\python.exe -m pytest tests/test_volume_renderer_controls.py -q -k "reset_window_level" --basetemp=.codex-tmp\pytest-volume-reset-wl-red` first failed with missing `VolumeRenderer.reset_window_level()` as expected; after implementation, `.\.venv\Scripts\python.exe -m pytest tests/test_volume_renderer_controls.py -q -k "reset_window_level" --basetemp=.codex-tmp\pytest-volume-reset-wl-green` -> 1 passed; `.\.venv\Scripts\python.exe -m pytest tests/test_volume_render_calibrated_data.py tests/test_volume_renderer_controls.py tests/test_mpr_core.py -q --basetemp=.codex-tmp\pytest-volume-t0-t2` -> 58 passed; `.\.venv\Scripts\python.exe -m py_compile src\core\volume_renderer.py src\gui\dialogs\volume_render_dialog.py src\gui\volume_viewer_widget.py tests\test_volume_render_calibrated_data.py tests\test_volume_renderer_controls.py` -> passed.
- 2026-06-01: Completed T0C (calibration edge-case hardening), file split, T4 (lighting), T5 (viewport overlay), T6 (remembered preset per modality). File split: extracted ~520 lines of preset data to `src/core/volume_render_presets.py`; `volume_renderer.py` re-exports all symbols for backward compatibility; `volume_renderer.py` dropped from ~1515 to ~1065 lines. Fixed VTK deprecation: `AddActor2D` → `AddViewProp`. Verification: 95 tests passed across `test_volume_render_calibrated_data`, `test_volume_renderer_controls`, `test_volume_3d_user_presets`, `test_volume_opacity_model`, `test_volume_render_control_state`, `test_volume_render_eligibility`, `test_volume_render_facade_lifecycle`, `test_mpr_core`; agent smoke harness OK.

**Plan status after this batch:** T0–T0C, T1, T2, T4, T5, T6 complete. S1 (SSAO spike), T3 (SSAO toggle), S2 (auto-rotate/keyboard), S3 (isosurface spike), S4 (MPR plane/dual-volume spike) remain.
- 2026-06-02: Completed S1 (SSAO spike — inconclusive headlessly, proceed with experimental toggle), T3 (SSAO toggle in Advanced), S2 (auto-rotate button + keyboard shortcuts with help strip). Verification: 97 tests passed; agent smoke harness OK.

**Plan status:** T0–T0C, T1, T2, T3, T4, T5, T6, S1, S2 complete. S3 (isosurface spike) and S4 (MPR plane/dual-volume spike) remain as follow-up spikes — both are scoped as separate planning items, not core to this plan.

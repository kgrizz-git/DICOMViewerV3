# Plan: Fix 3D viewer corner-overlay text ghosting

**Last updated:** 2026-06-04  
**Status:** Supporting — Qt sibling overlay shipped 2026-06-04 (layer-1 VTK failed manual gate)  
**Area:** 3D Volume Rendering — viewport overlay

---

## Goal and success criteria

The corner overlay in the 3D Volume Render window (preset name, opacity, detail,
blend mode) prints stale text on top of new text, producing overlapping,
double-printed lines. Changing presets or adjusting opacity makes it worse
(more ghosted lines accumulate). Replace the overlay-text mechanism so the text
is always crisp and single, **without** reintroducing the earlier
volume-masking ("image only renders where the preset name overlaps it") bug.

**Success criteria:**

- Overlay text is sharp, single, and non-overlapping at all times.
- Cycling presets and changing opacity / detail / blend mode never accumulates
  ghosted glyphs; the overlay reflects exactly the current state.
- The full volume renders everywhere in the viewport — **never** masked to the
  text region — on **both** the GPU (`vtkSmartVolumeMapper`) and forced-CPU
  (`vtkFixedPointVolumeRayCastMapper`) paths.
- `Show overlay` checkbox still toggles the overlay on/off.
- Verified on the actual Parallels-on-Mac / CPU-fallback environment, where the
  GPU silently falls back to CPU ray casting.

---

## Context and links

- Viewport widget: [`src/gui/volume_viewer_widget.py`](../../../src/gui/volume_viewer_widget.py)
- Renderer/mapper: [`src/core/volume_renderer.py`](../../../src/core/volume_renderer.py)
- Tests referencing the overlay:
  [`tests/test_volume_renderer_controls.py`](../../../tests/test_volume_renderer_controls.py),
  [`tests/test_volume_render_control_state.py`](../../../tests/test_volume_render_control_state.py)
- Related: [`3D_VIEWER_VISUAL_AND_UX_IMPROVEMENTS_PLAN.md`](3D_VIEWER_VISUAL_AND_UX_IMPROVEMENTS_PLAN.md),
  [`3D_VOLUME_RENDERING_PLAN.md`](../3D_VOLUME_RENDERING_PLAN.md)

---

## Root cause

The overlay is a Qt `QLabel` parented to the native VTK window:

- [`volume_viewer_widget.py:161`](../../../src/gui/volume_viewer_widget.py) —
  `self._overlay_label = QLabel(self._interactor)`, transparent background
  ([:162-165](../../../src/gui/volume_viewer_widget.py)), parented to
  `self._interactor`, a `QVTKRenderWindowInteractor`
  ([:147](../../../src/gui/volume_viewer_widget.py)) — i.e. a native
  OpenGL-backed window.
- [`_update_overlay_text`](../../../src/gui/volume_viewer_widget.py) rebuilds the
  full string correctly each call, then `setText` → `adjustSize` → `raise_`
  ([:1356-1358](../../../src/gui/volume_viewer_widget.py)). The **content** is
  right; the **pixels** are stale.

A Qt widget with a **transparent background**, layered over a **native OpenGL
surface**, does not get its previously painted region erased between repaints —
those pixels are owned by the OpenGL window, which only repaints on a VTK
`Render()`. So when the preset-name string length changes, or extra lines
(`Opacity …`, `Detail: …`) are added/removed and `adjustSize()` grows/shrinks
the label, the vacated areas are never cleared. Old glyphs persist and new text
paints on top → the observed overlap. The user's GL stack (Parallels, CPU
fallback) is exactly the kind where alien-widget-over-native-GL compositing is
undefined.

---

## The earlier bug this fix MUST NOT reproduce

A previous experiment used a `vtkTextActor` for the overlay and caused the
volume to render **only where it overlapped the preset-name text** (e.g.
"Default" acted as a mask). It was abandoned for the QLabel and never committed.

**Mechanism (per project record):** the text actor was added to the **same
`vtkRenderer` as the volume mapper**, and — quoting the
[`TO_DO.md`](../../TO_DO.md) changelog entry — *"vtkTextActor glyph texture bled
into the GPU volume pass → volume rendered only inside giant preset-name
letters."* The code comment at
[`volume_viewer_widget.py:155-160`](../../../src/gui/volume_viewer_widget.py)
agrees: *"adding a text actor to the same renderer as the GPU volume mapper
caused the glyph font texture to bleed into the ray-cast pass on some GL
stacks."* So the documented cause is **glyph-texture / shared-pass bleed**, not a
depth-buffer interaction. The exact GL-level cause is not pinned down ("on some
GL stacks"), but the precise mechanism does not change the fix.

**Why the chosen fix is structurally immune:** the overlay text is rendered in a
**separate `vtkRenderer` on a separate render-window layer**. VTK renders each
layer in its own independent pass and composites the finished color images. The
volume mapper never shares a renderer, framebuffer pass, or texture state with
the text. The common factor in every reported failure — text and volume in the
**same renderer/pass** — is removed by construction, regardless of whether the
underlying cause was texture, depth, or framebuffer state. The volume's renderer
(layer 0) is left completely untouched.

---

## Current state (verified)

- Mapper: `vtkSmartVolumeMapper` (GPU), CPU fallback to
  `vtkFixedPointVolumeRayCastMapper`
  ([`volume_renderer.py:307-310`](../../../src/core/volume_renderer.py)).
- The render window currently uses a **single layer** (no `SetNumberOfLayers` /
  `SetLayer` anywhere). The widget owns `self._vtk_render_window` and adds the
  volume renderer via `AddRenderer(self._renderer.get_renderer())`
  ([:148-149](../../../src/gui/volume_viewer_widget.py)).
- Render is driven through `self._vtk_render_window.Render()`
  ([`_render`, :1614-1617](../../../src/gui/volume_viewer_widget.py)).

---

## Approach (2026-06-03 attempt): VTK overlay-layer `vtkCornerAnnotation` — **FAILED manual gate**

Implemented layer-1 `vtkCornerAnnotation` on Parallels/software GL. **Manual verification failed:** volume rendered only inside preset-name glyph shapes (same mask bug as `vtkTextActor`). Separate renderer/layer is **not** sufficient on this stack — likely OpenGL texture/state leakage into `vtkSmartVolumeMapper`.

## Approach (chosen 2026-06-04): Qt sibling overlay on `viewport_container`

All changes stay in the GUI layer (`volume_viewer_widget.py`). **Do not modify
`volume_renderer.py`**. No VTK text actors in the render window.

- `QWidget` `_viewport_container` holds `QVTKRenderWindowInteractor` + `QLabel` overlay (sibling, not child of QVTK).
- Opaque dark chip stylesheet (no transparent background).
- On text shrink: `_render_timer.start()` + `_viewport_container.update()`.

---

## Approach (superseded): VTK overlay-layer `vtkCornerAnnotation`

All changes stay in the GUI layer (`volume_viewer_widget.py`). **Do not modify
`volume_renderer.py`'s renderer** — the volume renderer remains layer 0.

### Phase 1 — Overlay renderer + annotation

- [x] In [`_setup_ui`](../../../src/gui/volume_viewer_widget.py), after
  `AddRenderer(self._renderer.get_renderer())`:
  - [x] `self._vtk_render_window.SetNumberOfLayers(2)`
  - [x] **Explicitly** pin the volume renderer to layer 0:
    `self._renderer.get_renderer().SetLayer(0)` (default is 0, but set it so the
    pairing with the overlay's layer 1 is unambiguous and review-proof).
  - [x] Create `self._overlay_renderer = vtk_mod.vtkRenderer()`,
    `self._overlay_renderer.SetLayer(1)`,
    `self._overlay_renderer.InteractiveOff()`. (Layers > 0 do not erase the
    color buffer, so the volume shows through; no background config needed.)
  - [x] **Share the volume renderer's active camera** with the overlay renderer:
    `self._overlay_renderer.SetActiveCamera(self._renderer.get_renderer().GetActiveCamera())`.
    For a 2D-only `vtkCornerAnnotation` this is not strictly required (the
    annotation is screen-anchored and camera-independent), but sharing the
    camera (a) avoids VTK building a separate camera whose clipping-range resets
    could perturb layer compositing, and (b) future-proofs the overlay layer if
    a 3D prop (e.g. an orientation axis) is ever added. `InteractiveOff()`
    already prevents the interactor from grabbing this renderer.
  - [x] `self._vtk_render_window.AddRenderer(self._overlay_renderer)`
- [x] Create `self._corner_annotation = vtk_mod.vtkCornerAnnotation()`:
  - [x] Style `GetTextProperty()` to match current look — light grey
    (`SetColor`), monospace font (`SetFontFamilyToCourier` or
    `SetFontFile`), modest font size, left/top justification.
  - [x] Set a sensible `SetMaximumFontSize` / `SetLinearFontScaleFactor` so text
    stays small and corner-anchored, like the current label.
  - [x] `self._overlay_renderer.AddViewProp(self._corner_annotation)`.

### Phase 2 — Drive the annotation from state

- [x] Rewrite [`_update_overlay_text`](../../../src/gui/volume_viewer_widget.py)
  (def near line 1329, body ≈ lines 1333–1358 — verify exact range at edit time):
  keep the existing string-building logic; replace the
  `QLabel.setText/adjustSize/raise_` tail with
  `self._corner_annotation.SetText(2, text)` (slot 2 = upper-left), then
  `self._render_timer.start()` to repaint via the same 80 ms debounce every
  other control uses ([:1213+](../../../src/gui/volume_viewer_widget.py)). Do
  **not** call `Render()` directly here — match the surrounding control idiom.
  - [x] Confirm `vtkCornerAnnotation` renders the multi-line string
    (`"\n".join(...)`) correctly in slot 2 — it accepts embedded `\n`; verify on
    the software-GL path during testing.
  - [x] Guard against the annotation not existing yet (called from
    `initialize()` before VTK init): keep an existence check like today's
    `hasattr` guard, retargeted to `_corner_annotation`.
- [x] **First paint:** `initialize()` calls `_update_overlay_text()` before VTK
  init, so the annotation object must already exist by then, **or** add an
  explicit `_update_overlay_text()` (and a render) at the end of
  [`_deferred_vtk_init`](../../../src/gui/volume_viewer_widget.py) so the overlay
  is present on first open, not just after the first control change. Today the
  QLabel paints immediately; preserve that behavior. — **Done:** `_update_overlay_text()` + `_render_timer.start()` called at end of `_deferred_vtk_init`.
- [x] `_on_overlay_toggled`
  ([:1324-1327](../../../src/gui/volume_viewer_widget.py)) → toggle
  `self._corner_annotation.SetVisibility(...)` (or add/remove the view prop)
  **and request a render** (`self._render_timer.start()`). Note: the old QLabel
  toggle did *not* render because Qt repaints the label itself; the VTK
  annotation only updates on the next `Render()`, so this render call is new and
  required.

### Phase 3 — Remove the QLabel path

- [x] Delete the `QLabel` overlay creation
  ([:161-170](../../../src/gui/volume_viewer_widget.py)) and the `QLabel` import
  if now unused. — **Note:** `QLabel` import retained; it is used extensively in
  the control panel for layout labels (Opacity %, Window:, Level:, etc.). Only
  `_overlay_label` and its `QLabel(self._interactor)` creation were removed.
- [x] Remove all `_overlay_label` references and `hasattr(self,
  "_overlay_label")` guards; replace guards with `_corner_annotation` existence
  checks where ordering matters.

### Phase 4 — Lifecycle

- [x] Ensure the overlay renderer + annotation are created only when the render
  window exists (same path as today's `_setup_ui`).
- [x] In teardown ([`:1633` `Finalize()`](../../../src/gui/volume_viewer_widget.py)
  and the `self._interactor = None` cleanup at
  [:1634](../../../src/gui/volume_viewer_widget.py)), drop references to the
  overlay renderer and annotation so VTK objects release cleanly. — **Done:** `cleanup()` removes the corner annotation view prop and the overlay renderer from the render window before nulling both references.

### Phase 5 — Tests

**Correction to the original plan:** there are currently **no** tests for the
overlay and **no** test instantiates `VolumeViewerWidget`. Verified:
`grep` for `overlay` / `_overlay_label` / `VolumeViewerWidget` across
[`test_volume_renderer_controls.py`](../../../tests/test_volume_renderer_controls.py)
and [`test_volume_render_control_state.py`](../../../tests/test_volume_render_control_state.py)
returns nothing — those exercise `VolumeRenderer` and control-state objects, not
the widget. So this is **new** test coverage, not an update.

Testing a `QVTKRenderWindowInteractor`-hosted widget headlessly is heavy
(needs a Qt app + offscreen GL). To keep coverage cheap and meaningful:

- [x] **Extract the overlay string builder into a pure function/staticmethod**
  (e.g. `_build_overlay_text(preset_name, opacity_pct, quality, blend) -> str`)
  with no Qt/VTK dependencies, and have `_update_overlay_text` call it. This is
  the testability win the reviewer flagged and keeps the ~1646-line widget from
  growing untestable logic.
- [x] Add `tests/test_volume_overlay_text.py` unit-testing that builder:
  preset-only; opacity < 100 adds `Opacity …`; non-`Normal` detail adds
  `Detail: …`; non-`Composite` blend adds the blend line; empty/`-1` logical
  index yields no preset line. (Covers exactly the regression the user hit:
  extra lines appearing/clearing correctly.) — **Done:** 12 tests, all pass. Uses `ast.get_source_segment` to extract the pure function without triggering Qt/VTK imports.
- [x] **Layer-separation regression guard.** If an offscreen VTK render-window
  fixture is feasible in CI, assert `volume_renderer.GetLayer() == 0`,
  `overlay_renderer.GetLayer() == 1`, and that the `vtkCornerAnnotation` is a
  view prop of the overlay renderer and **not** of the volume renderer (the
  direct guard against reviving the mask bug). If an offscreen GL context is not
  reliable in CI (Parallels/software GL), mark this as a **manual** check in the
  verification gate instead of a CI test, and document why. — **Manual check:** offscreen GL is not reliable in this environment; this is a verification gate item (see below).
- [x] Confirm the existing volume-render test modules still pass unchanged (no
  edits expected there now that the premise is corrected). — **Done:** `test_volume_renderer_controls.py` (52 tests) + `test_volume_render_control_state.py` (3 tests) = 55 passed.

---

## Task graph and sequencing

```
Phase 1 (overlay renderer + annotation)
   └─> Phase 2 (drive from state, first paint, toggle render)
          └─> Phase 3 (remove QLabel) ──> Phase 4 (lifecycle)
   └─> Phase 5a (extract pure string builder)  [can start in parallel with P1]
          └─> Phase 5b (unit tests on builder)
          └─> Phase 5c (layer-separation guard — CI if offscreen GL works, else manual)
All phases ─> Verification gate (manual, on Parallels/CPU-fallback) ─> hygiene
```

- **Owner:** single implementer (widget-scoped bugfix; no cross-module
  coordination needed).
- **Parallelism:** Phase 5a (extract builder) is independent of the VTK wiring
  and can land first to de-risk the rest.

## Risks and mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Layered rendering misbehaves on software/virtual GL (Parallels) — e.g. overlay layer clears the volume or doesn't composite | Medium | Verification gate item 3 explicitly tests volume-not-masked on GPU **and** forced-CPU paths; Plan B (QLabel fix) is the documented fallback |
| `vtkCornerAnnotation` font/scale looks different from the old QLabel | Low | Match color/size via `GetTextProperty`; font is a visual nicety, not correctness (see Open questions) |
| First-paint regression (overlay missing on open) because annotation is created after `initialize()` calls `_update_overlay_text()` | Medium | Phase 2 first-paint step: ensure annotation exists before `initialize()` or re-call in `_deferred_vtk_init`; gate item 5 checks it |
| Camera/clipping interaction between layers | Low | Share active camera + `InteractiveOff()` (Phase 1); gate item 6 checks rotate/zoom |
| Offscreen VTK unavailable in CI, so layer-separation can't be asserted automatically | Medium | Fall back to a manual gate check (Phase 5c) rather than blocking; pure string-builder tests still run in CI |

## Verification gate (must pass before merge)

Run on the real Parallels-on-Mac / CPU-fallback environment:

1. [ ] Overlay text is sharp, single, non-overlapping at the upper-left corner.
2. [ ] Cycle several presets and change opacity / detail / blend mode — confirm
   **no** ghost glyphs accumulate; overlay matches current state exactly.
3. [ ] **Critical:** confirm the full volume renders across the whole viewport,
   **not** masked to the text region — test both GPU and forced-CPU render
   methods via the Render-method control.
4. [ ] `Show overlay` unchecked hides the text; rechecked restores it.
5. [ ] First-open: overlay is present immediately when the 3D window opens, not
   only after the first control change.
6. [ ] Resize the window and rotate/zoom the volume — overlay stays anchored
   top-left, stays crisp, and the volume is never clipped/masked by the overlay
   layer.
7. [ ] **Optional / nice-to-have:** check overlay legibility at HiDPI scaling,
   and with the experimental **SSAO** toggle on (SSAO touches the render passes;
   confirm the overlay layer still composites cleanly).
8. [ ] `pytest tests/test_volume_overlay_text.py` and the existing volume-render
   test modules pass.
9. [ ] Repo harness / pre-commit checks pass.
10. [ ] Run the 3D portion of the manual smoke checklist in
    [`AGENT_SMOKE.md`](../../orchestration/AGENT_SMOKE.md) (or via the
    `agent-smoke-harness` skill) after the change.

---

## Fallback (Plan B) — only if the layer approach shows any artifact on the stack

Keep the `QLabel` but fix *its* ghosting rather than the text source:

- Opaque (or solid semi-opaque) rounded background so each repaint fills its own
  rect and overwrites old glyphs within the label.
- Fixed maximum width; allow height to grow but force a full
  `self._vtk_render_window.Render()` after every text change so the GL window
  repaints pixels the label vacated when it shrinks.

This is a mitigation (fights native-window layering) rather than a true fix, so
it is the fallback, not the default.

---

## Open questions

- `vtkCornerAnnotation` font: confirm a monospace family renders consistently on
  the software-GL path; if `SetFontFamilyToCourier` looks off, fall back to Arial
  at the same size (visual nicety, not correctness).
- Whether to render immediately or via the existing 80 ms `_render_timer` debounce
  on overlay text changes — pick whichever matches the perceived snappiness of
  the other controls without extra full renders.

---

## Project hygiene (on completion)

- [x] Add a `[ ]` item under the **3D viewer** group in
  [`dev-docs/TO_DO.md`](../../TO_DO.md) for this overlay-ghosting fix, linking
  this plan; mark `[x]` with a dated note when shipped (mirror the style of the
  prior 3D overlay entry, which records the original glyph-texture bleed fix). — **Done 2026-06-03:** updated the existing viewport overlay `[x]` entry with a ghosting-fix dated note.
- [x] Add a `CHANGELOG.md` entry (semantic versioning: **patch** — bugfix, no
  API/behavior change beyond the overlay rendering mechanism). — **Done 2026-06-03.**
- [ ] Cross-link from [`3D_VIEWER_VISUAL_AND_UX_IMPROVEMENTS_PLAN.md`](3D_VIEWER_VISUAL_AND_UX_IMPROVEMENTS_PLAN.md)
  if it tracks overlay work.

## Notes on modularity

This is a widget-scoped bugfix; keeping the change inside the ~1646-line
[`volume_viewer_widget.py`](../../../src/gui/volume_viewer_widget.py) is
acceptable. The only extraction worth doing is the pure overlay **string
builder** (Phase 5a) — it buys real unit-test coverage for the exact logic that
regressed. No broader refactor of the widget is in scope here.

---

## Completion notes (2026-06-04)

- **Layer-1 VTK:** Failed verification gate #2 (letter-shaped volume mask on MR T1 Brain preset).
- **Qt sibling:** Shipped in `volume_viewer_widget.py`; `tests/test_volume_overlay_text.py` + `test_viewport_overlay_uses_qt_sibling_not_vtk_text`.
- **Manual gate (Parallels/CPU):** User to confirm items 1–6 in verification gate after merge.

# Plan: Make the 3D viewer work on native macOS (offscreen render surface)

**Date:** 2026-08-22
**Status:** Active — Phases 0–3 complete and verified 2026-08-22; Phase 4 (platform strategy) and the manual gate remain
**Priority:** P0 (3D viewer hard-freezes the application on native macOS; force quit required)
**Branch suggestion:** `fix/3d-macos-native-offscreen-render`
**Related:** [`3D_VOLUME_RENDERING_PLAN.md`](3D_VOLUME_RENDERING_PLAN.md),
[`3D_VIEWER_FIRST_PAINT_RESPONSIVENESS_PLAN.md`](3D_VIEWER_FIRST_PAINT_RESPONSIVENESS_PLAN.md),
[`VOLUME_RENDER_DIALOG_LIFECYCLE_PLAN.md`](supporting/VOLUME_RENDER_DIALOG_LIFECYCLE_PLAN.md),
[`3D_VIEWER_OVERLAY_GHOSTING_FIX_PLAN.md`](supporting/3D_VIEWER_OVERLAY_GHOSTING_FIX_PLAN.md),
[`VOLUME_RENDER_FALLBACK_AND_MEMORY_HARDENING_PLAN.md`](supporting/VOLUME_RENDER_FALLBACK_AND_MEMORY_HARDENING_PLAN.md)

> **For agentic workers:** Execute task-by-task and tick the checkboxes. Activate `.venv`
> before pytest; allow ~10 minutes for the full suite. **Phase 0 is a decision gate — do
> not start Phase 1 until Phase 0 is signed off.**

---

## Goal and success criteria

Opening **3D View** on native macOS must render the volume and keep the Qt event loop
responsive, without regressing the known-good Windows / Parallels path.

**Success criteria:**

- Opening 3D View on native macOS renders a visible volume and never blocks the GUI
  thread for more than the existing first-paint budget.
- Rotate / pan / zoom / preset / opacity / W-L / detail / blend-mode / crop / standard
  views / auto-rotate all work on native macOS.
- No regression on Windows and Windows-under-Parallels (the historical test environment).
- Closing the dialog releases VTK resources with no "QThread destroyed while running"
  aborts and no leaked timers.

---

## Problem evidence (2026-08-22)

Reproduced with the real `VolumeRenderDialog` on a real CT QC phantom series
(25 slices, 512×512, `1.2.840.10008.1.2.1` uncompressed, 13 MB on disk).
The GUI thread stalls permanently; the application must be force-quit.

Native stack from `sample(1)` — 61% of all samples in a single frame:

```
QWidgetPrivate::paintOnScreen → paintEvent → vtkRenderWindowInteractor::Render()
  → vtkCocoaRenderWindow::Render() → vtkOpenGLGPUVolumeRayCastMapper::GPURender()
    → glFinish_Exec → GLDShareGroupRec::waitUsage (AppleMetalOpenGLRenderer)
      → _pthread_cond_wait          ← parked indefinitely
```

Key measurements:

| Observation | Value |
|---|---|
| Volume build (`MprVolume.from_datasets` + `prepare_volume_data`) | **0.01 s** |
| Same volume rendered **offscreen** (Fast / Normal / High) | **0.20 s / 0.01 s / 0.00 s** |
| Same volume rendered **on-screen** | **hangs forever** |
| Smallest volume that still hangs | **64×64×8 (32 KB)** |

It is a *single* `paintEvent` that never returns — not a repaint loop. Because
`_on_build_finished` never returns to the event loop, the dialog keeps painting its stale
"Building 3D volume…" text, which is why the freeze *looks* like a stuck build.

### Ruled out

| Hypothesis | Evidence |
|---|---|
| Volume size / memory pressure | Series is 13 MB; a 32 KB volume hangs identically |
| Detail level / first-paint quality policy | Hangs at Fast **and** High |
| PySide6 6.11.2 (installed 2026-08-18) | Hangs on 6.11.1 too |
| VTK 9.6.2 (installed 2026-07-09) | Hangs on 9.5.2 too |
| GDCM decoder switch (`32083b1`) | Series is uncompressed (no decoder runs); a synthetic raw-`PixelData` volume hangs identically; that commit touches no `volume_*` file |
| The phantom data itself | Identical data renders offscreen in 0.20 s |

### Root cause

VTK's `vtkCocoaRenderWindow` issues a blocking `glFinish` from inside a CoreAnimation
transaction commit (`-[_NSOpenGLViewBackingLayer display]`). Under macOS 26's
OpenGL-over-Metal shim (`AppleMetalOpenGLRenderer`) that call never returns for a volume
render. Offscreen rendering does not go through the CALayer path and is unaffected.

### Why this was never caught

The 3D viewer was developed and verified on **Windows under Parallels**, where VTK gets a
software / virtual GL stack and takes the CPU ray-cast path. The codebase records this
throughout — [`src/core/volume_renderer.py:332`](../../src/core/volume_renderer.py),
[`src/core/volume_renderer.py:931`](../../src/core/volume_renderer.py),
[`src/gui/volume_viewer_widget.py:179`](../../src/gui/volume_viewer_widget.py),
`dev-docs/TO_DO.md:102`, and the "Verified on the actual Parallels-on-Mac /
CPU-fallback environment" note in the overlay-ghosting plan. Several plans still list
native-GPU verification as outstanding. **Native macOS 3D was never verified**; this is
not a regression from any recent commit.

Note the irony worth preserving in review: `check_gpu_fallback()` exists specifically to
rescue Parallels' blank frames, but on native macOS it never executes — the *first*
`Render()` never returns.

---

## Hard constraints

- **VTK's Python wheels ship only `vtkmodules.qt.QVTKRenderWindowInteractor`.**
  `QVTKOpenGLNativeWidget` (the modern `QOpenGLWidget`-based host, and the natural
  upstream fix) is **C++-only** and unavailable without building VTK from source with Qt
  Python bindings. Confirmed by inspecting the installed wheel.
- VTK objects are main-thread-affine. Offscreen rendering does **not** move `Render()` to a
  background thread; it only changes the *surface*.
- Do not import `gui` → `main`.

---

## Non-goals

- Building VTK from source, or vendoring `QVTKOpenGLNativeWidget`.
- Moving `Render()` off the GUI thread.
- Changing transfer-function aesthetics or preset definitions.
- Fixing the blank-frame false positive and the build-path memory amplification — those
  are tracked in
  [`VOLUME_RENDER_FALLBACK_AND_MEMORY_HARDENING_PLAN.md`](supporting/VOLUME_RENDER_FALLBACK_AND_MEMORY_HARDENING_PLAN.md).

---

## Global constraints

- Activate the project `.venv` before tests. Full suite: `python -m pytest tests/ -v` (~10 min).
- Gate new diagnostics behind `DEBUG_VOLUME_3D` in `src/utils/debug_flags.py`.
- PHI: no series paths or patient identifiers in logs, tests, or this plan. Use synthetic
  fixtures and fixture dimensions only.
- Back up modified production files under `tmp/*.bak-*` before edits; delete after a
  verified commit (project refactor rule).
- SemVer: **minor** (new rendering surface; user-visible behavior change on macOS).

---

## File map

| File | Role |
|------|------|
| `src/gui/volume/render_surface.py` | **New.** Offscreen render surface + QImage blit widget |
| `src/gui/volume/interactor_bridge.py` | **New.** Qt events → `vtkGenericRenderWindowInteractor` |
| `src/gui/volume_viewer_widget.py` | Swap `QVTKRenderWindowInteractor` for the new surface; re-wire observers |
| `src/gui/volume/first_paint.py` | Preview/refine timers now drive the surface, not the interactor |
| `src/core/volume_renderer.py` | Render-window ownership; `check_gpu_fallback` call site |
| `src/gui/dialogs/volume_render_dialog.py` | Unchanged if the widget API is preserved |
| `tests/gui/test_volume_render_surface.py` | **New.** Offscreen surface + blit unit tests |
| `tests/gui/test_volume_interactor_bridge.py` | **New.** Event-forwarding and coordinate tests |
| `tests/gui/test_volume_viewer_widget.py` | Update for the new surface |
| `user-docs/USER_GUIDE_3D.md` | Note platform support if behavior differs |
| `CHANGELOG.md`, `dev-docs/MAINTENANCE_LOG.md`, `dev-docs/TO_DO.md` | Standard bookkeeping |

---

## Phase 0 — Spike and decision gate

Prove the offscreen surface is viable *before* committing to the port.

- [x] **Step 1:** Standalone script: offscreen `vtkRenderWindow` + `SetOffScreenRendering(1)`
      → `Render()` → `GetRGBACharPixelData()` → numpy → `QImage` → `QLabel` in a live Qt
      window. Confirm a visible, correct volume image and a responsive event loop.
- [x] **Step 2:** Confirm Retina correctness — render at `devicePixelRatio`, set
      `QImage.setDevicePixelRatio()`, verify no blur and no half-size viewport.
- [x] **Step 3:** Confirm the vertical flip (VTK origin is bottom-left, `QImage` is
      top-left) and the RGBA byte order on ARM64.
- [x] **Step 4:** Measure blit cost per frame at 884×560 and at full-screen on Retina.
      Budget: < 5 ms per frame for the readback + `QImage` construction.
- [x] **Step 5:** Drag-loop feasibility — synthesize 60 camera updates and confirm sustained
      interactive frame rate with `set_interactive_quality(low=True)`.
- [x] **Decision gate:** all five green → proceed. Any red → record the failure here and
      escalate (options: ship 3D as Windows/Parallels-only on macOS with an explicit
      unsupported notice, or revisit building VTK with `QVTKOpenGLNativeWidget`).

### Phase 0 results — 2026-08-22: **PASSED, proceed to Phase 1**

Spike scripts: `tmp/spike/phase0_offscreen.py`, `tmp/spike/phase0_flip_dpr.py`
(scratch only — not committed as production code).

| Gate | Result |
|---|---|
| Step 1 — visible image + responsive loop | **PASS.** First offscreen render 0.140 s; event loop stayed responsive through **103 live re-renders** at 10 Hz with zero stalls. Rendered image visually verified as a correct phantom cylinder. |
| Step 2 — Retina / DPR | **PASS.** At `dpr=2.0`, rendering 800×600 px yields a 400×300 logical image; blit 1.54 ms. *(This display reports `dpr=1.0`, so 2× was simulated — re-verify on a real Retina panel at the manual gate.)* |
| Step 3 — flip + byte order | **PASS.** A superior-only bright marker lands at row 78/300 (top quarter), confirming `buf[::-1]` is correct. Colors correct — no BGR swap on ARM64. |
| Step 4 — blit cost | **PASS, 17× under budget.** 884×560: median **0.29 ms**, max 0.47 ms (budget 5.00 ms). |
| Step 5 — drag loop | **PASS.** 60 camera updates + readbacks in 0.16 s → **385 fps** at coarse quality. |

**Critical finding — discard the alpha channel.** The offscreen buffer's background alpha
is **0**: 118 817 of 120 000 pixels are fully transparent. Blitting via
`QImage.Format_RGBA8888` therefore produces a near-invisible overlay. **Phase 1 must use
`Format_RGB888` with the alpha channel sliced off** (`flipped[:, :, :3]`). Verified
correct, with the renderer background color showing properly, once alpha is dropped.

**Buffer lifetime:** `QImage` does not copy its backing buffer. Every `QImage` built over a
numpy array must be `.copy()`-ed (or the array kept alive for the widget's lifetime)
before the numpy buffer goes out of scope. Phase 1 Step 5 must test this.

**Already-tested options (do not redo):**

| Option | Result |
|---|---|
| `vtkGenericOpenGLRenderWindow` passed to `QVTKRenderWindowInteractor` | **Segfault** (exit 139). It needs a `QOpenGLWidget` host to supply the GL context, which this widget does not provide. Rejected as a drop-in. |
| Forcing `SetRequestedRenderModeToRayCast()` (CPU) on-screen | Still hangs — the deadlock is in the window/CALayer path, not the mapper |
| Downgrading PySide6 / VTK | Still hangs (see evidence table) |

---

## Phase 1 — Offscreen render surface

**Produces:** `src/gui/volume/render_surface.py`

- [x] **Step 1:** `VolumeRenderSurface(QWidget)` owning an offscreen `vtkRenderWindow`.
      Public API mirrors what the viewer widget uses today: `render()`, `render_window`,
      `resize`, `cleanup()`.
- [x] **Step 2:** `render()` = `rw.Render()` → readback → `QImage` → `update()`.
      `paintEvent` draws the **cached** `QImage` only — it must never call `rw.Render()`.
      This is the invariant that fixes the freeze; assert it in a test.
- [x] **Step 3:** Debounce resize: on `resizeEvent`, update the offscreen window size
      (× `devicePixelRatio`) and re-render through the existing owned timer, not inline.
- [x] **Step 4:** `cleanup()` releases the render window and drops the cached `QImage`.
- [x] **Step 5:** Unit tests: paintEvent-does-not-render invariant, DPR sizing, flip
      correctness, cleanup idempotence.

---

## Phase 2 — Camera interaction

**Produces:** `src/gui/volume/interactor_bridge.py`

> **Design superseded 2026-08-22.** The original plan hand-rolled camera math. A spike
> (`tmp/spike/phase2_generic_interactor.py`) showed that a
> **`vtkGenericRenderWindowInteractor` binds cleanly to the offscreen render window**, so
> the existing `vtkInteractorStyleTrackballCamera` can be kept verbatim. This is
> strictly better: identical interaction feel to the Windows build (no tuning),
> `StartInteractionEvent` / `EndInteractionEvent` keep firing so
> `apply_interaction_detail()` needs no change, and — decisively — the **crop box widget
> keeps working**. `vtkBoxWidget2.SetInteractor()` requires a real interactor
> (`src/gui/volume_viewer_widget.py:1469`); hand-rolled camera math would have silently
> broken 3D cropping.

Spike results:

| Check | Result |
|---|---|
| Generic interactor binds to offscreen window (`rw.GetInteractor() is iren`) | **PASS** |
| Trackball style moves the camera from synthetic drag events | **PASS** |
| Render-window `EndEvent` fires per render (the blit hook) | **PASS** (11/11) |
| `vtkBoxWidget2` crop widget attaches and renders | **PASS** |
| Event loop stays responsive with the interactor attached | **PASS** |

- [x] **Step 1:** `VolumeRenderSurface` owns a `vtkGenericRenderWindowInteractor` bound to
      its offscreen window, with `vtkInteractorStyleTrackballCamera` as the style.
- [x] **Step 2:** Blit on the render window's `EndEvent` observer, so renders triggered by
      the *interactor* (not just explicit `render()` calls) also refresh the widget.
      Guard against re-entrancy and against firing after `cleanup()`.
- [x] **Step 3:** Forward Qt events → interactor: press / move / release for left, middle
      and right buttons, plus wheel. **Coordinates must be converted** — Qt is top-left
      origin in logical units, VTK is bottom-left origin in device pixels
      (`y_vtk = height_px - y_qt * dpr`).
- [x] **Step 4:** Forward modifier state (Ctrl / Shift) so the trackball style's
      pan / spin / dolly modifiers behave as they do on Windows.
- [x] **Step 5:** Forward `keyPressEvent`, preserving the shortcuts currently bound via
      `iren.AddObserver("KeyPressEvent", ...)`.
- [x] **Step 6:** Unit tests: coordinate conversion (pure function), synthetic drag moves
      the camera, `EndEvent` triggers exactly one blit, no events delivered after cleanup.

---

## Phase 3 — Port the viewer widget

- [x] **Step 1:** Replace the `QVTKRenderWindowInteractor` construction
      (`src/gui/volume_viewer_widget.py:170`) with `VolumeRenderSurface`.
- [x] **Step 2:** Rewrite `_deferred_vtk_init` — no `Initialize()`, no interactor-style
      observers. Keep the deferred-first-paint structure and `schedule_first_preview()`.
- [x] **Step 3:** Repoint `_render()`, `_auto_rotate_step()`, and the first-paint helpers
      at the surface.
- [ ] **Step 4:** *(Automated coverage only so far — needs the manual gate.)* Verify feature parity item by item: presets, opacity, W/L,
      contrast-depth, detail slider, blend mode, cropping, standard views, auto-rotate,
      overlay text, background color, screenshot export.
- [ ] **Step 5:** *(Not yet visually confirmed — needs the manual gate.)* Confirm the Qt sibling overlay from the overlay-ghosting plan still
      composites correctly (it should get *simpler* — the volume is now a plain QImage
      underneath, eliminating the GL texture-bleed class of bug entirely).
- [x] **Step 6:** `cleanup()` path — timers stopped before teardown, no double-free.

---

### Phase 3 results — 2026-08-22

- The original freeze repro (real `VolumeRenderDialog`, real CT QC phantom) now runs to
  **`clean exit, rc= 0`**. Previously it deadlocked the GUI thread indefinitely.
- Open/close the dialog **5×**: no crash, no stall, peak RSS flat (561 → 567 MB).
- Full suite: **6312 passed, 15 skipped, 0 failures**.

**Critical finding — never call `vtkRenderWindow.Finalize()`.** The first working port
still segfaulted (exit 139) at application teardown. Bisected to `Finalize()` in
`VolumeRenderSurface.cleanup()`: it destroys the offscreen GL context, and VTK's
destructor frees it again when the last reference drops. Removing renderers first does
**not** help. Dropping the references is sufficient — VTK releases the context in its
destructor. Locked by `test_cleanup_does_not_finalize_render_window`.

Incidental confirmation of the supporting plan's Task A: the dialog's first paint on this
phantom under the default **CT Bone** preset shows only the dense QA inserts floating in
black, because the water/acrylic body is fully transparent at that preset.

---

## Phase 4 — Platform strategy

- [ ] **Step 1:** Ship the offscreen surface on **all** platforms (recommended) rather
      than branching by OS. Rationale: one code path, and it retires the Parallels-specific
      blank-frame and GL-bleed workarounds. Two rendering paths would double the manual
      verification matrix permanently.
- [ ] **Step 2:** Add a temporary escape hatch (`DICOMVIEWER_3D_LEGACY_INTERACTOR=1`) to
      restore the old widget for one release, in case Windows/Parallels regresses in the
      field.
- [ ] **Step 3:** After one clean release, delete the legacy path and the now-dead
      Parallels workarounds. Track as a follow-up TO_DO item; do **not** delete in this plan.

---

## Verification gate (manual — required before archiving)

- [ ] Native macOS (this machine, macOS 26.5.2, ARM64): open 3D on the CT QC phantom —
      volume visible, UI responsive, all controls functional, clean close.
- [ ] Native macOS: a large series (≥ 300 slices) — first paint within budget, interaction
      usable.
- [ ] Windows native: full 3D smoke per `dev-docs/TO_DO.md:102`.
- [ ] Windows under Parallels: full 3D smoke — **no regression** vs. current behavior.
- [ ] Open / close the dialog 5× consecutively — no leak, no abort, no orphaned timers.
- [ ] Record results (platform, GPU, dims, timings) here. **No PHI.**

---

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Offscreen context creation fails on some GPU/driver | Low | Verified working here (0.20 s); Phase 0 Step 1 gates it |
| Per-frame readback too slow for smooth interaction | Medium | Phase 0 Step 4/5 measure it; coarse quality during drag; blit is ~2 MB/frame at 884×560 |
| Hand-rolled camera feels different from trackball | Medium | Tune constants against the Windows build side-by-side; Phase 2 unit tests lock behavior |
| Windows/Parallels regression | Medium | Phase 4 escape hatch + explicit manual gate on both |
| Retina / DPR bugs (blurry or half-size viewport) | Medium | Phase 0 Step 2 gates it explicitly |

---

## Rollback

The change is contained to the viewer widget's render surface. Reverting the branch
restores `QVTKRenderWindowInteractor`. During the escape-hatch release, users can set
`DICOMVIEWER_3D_LEGACY_INTERACTOR=1` without a rebuild.

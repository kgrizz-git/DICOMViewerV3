# 3D Viewer First-Paint Responsiveness Plan

**Date:** 2026-08-10
**Status:** Active — implementation and automated verification complete; manual large-volume/hardware timing remains
**Last updated:** 2026-08-10
**Priority:** P1 (user-visible hang on open / first interaction)
**Branch suggestion:** `fix/3d-first-paint-responsiveness` (or continue from current WIP)
**Related:** [`3D_VOLUME_RENDERING_PLAN.md`](3D_VOLUME_RENDERING_PLAN.md), [`THREE_D_VIEWER_APPEARANCE_OPTIONS_CONTROLS_PLAN.md`](../supporting/THREE_D_VIEWER_APPEARANCE_OPTIONS_CONTROLS_PLAN.md), [`VOLUME_RENDER_DIALOG_LIFECYCLE_PLAN.md`](../supporting/VOLUME_RENDER_DIALOG_LIFECYCLE_PLAN.md)

> **For agentic workers:** Prefer `superpowers:subagent-driven-development` or execute task-by-task. Use checkboxes below. Activate `.venv` before pytest; allow ~10 minutes for full suite.

**Goal:** Keep the Qt UI responsive when opening a 3D volume render (especially large CT / PET-CT series with steep presets like CT Bone), while preserving final image quality when the device can render it within a responsiveness budget.

**Architecture:** Volume **build** already runs on a background `QThread`. Remaining freezes are **synchronous VTK `Render()` on the GUI thread** during `_deferred_vtk_init` (first paint) and optional GPU→CPU fallback (second full render). Fix by (1) a Fast preview, (2) capping Auto Detail by volume size, (3) running blank-frame GPU fallback at Fast, (4) refining automatically only when the preview stays within a measured GUI-thread render budget, (5) busy cursor + status copy, and (6) ensuring interaction coarsening and cleanup stay reliable.

> **Important constraint:** A queued timer does not make a VTK `Render()` cancellable or non-blocking. It only gives Qt a chance to paint and process input *before* the next render begins. A slow automatic refinement must therefore be skipped, not merely delayed; manual High/Ultra remains an explicit user choice.

**Tech stack:** PySide6, VTK (`vtkSmartVolumeMapper` / ray cast), existing `VolumeRenderer` + `VolumeViewerWidget` + `VolumeRenderDialog`.

## Problem evidence (2026-08-10)

Observed hang opening **3D View** on a **PET-CT SERIES - CT** study:

- Dialog had already left “Building 3D volume…” (controls visible).
- OCR / screenshot: preset **CT Bone**, **Detail: High**, Composite.
- CT Bone is a **steep** preset → Auto Detail selects **High** (`sample distance = 0.5`).
- First paint path: `_deferred_vtk_init` → `Render()` → `check_gpu_fallback()` (may read back pixels and **Render() again on CPU** at High).

That combination can block the event loop for tens of seconds to minutes on integrated GPU / Parallels / CPU fallback — feels like a hang even when work is progressing.

## Non-goals

- Dual-volume PET/CT 3D overlay (separate spike).
- Moving VTK `Render()` itself off the GUI thread (VTK objects are main-thread-affine; progressive quality is the practical fix).
- Changing transfer-function aesthetics of CT Bone / other presets.
- Full memory downsampling toggle (already a separate TO_DO / plan §4.2 item); this plan may **reuse** the existing memory estimate for Detail caps only.

## Global constraints

- Activate project `.venv` before tests (`source .venv/bin/activate` / Windows equivalent).
- Full suite: `python -m pytest tests/ -v` (~10 min timeout).
- Gate new diagnostic prints behind `DEBUG_VOLUME_3D` (default `False`) in `src/utils/debug_flags.py`.
- Do not import `gui` → `main`. Keep VTK create/manipulate on the GUI thread.
- Preserve public control semantics: user can still manually choose High/Ultra; caps apply to **Auto** and **first-paint / fallback** paths.
- PHI: no series paths / patient identifiers in logs or tests; use fixtures / synthetic dims.
- Backup modified production files under `tmp/*.bak-*` before edits; delete after verified commit (project refactor rule).
- SemVer: patch (responsiveness / robustness; no intentional feature surface change beyond status text).

## File map

| File | Role |
|------|------|
| `src/core/volume_renderer.py` | Quality modes, interactive sample distance, GPU fallback; add size-aware helpers / Fast-path fallback render |
| `src/gui/volume_viewer_widget.py` | Auto Detail, `_deferred_vtk_init`, `_render`, interaction observers, status UI |
| `src/gui/dialogs/volume_render_dialog.py` | Optional: status label during first paint if not owned by viewer |
| `src/core/volume_render_presets.py` | Steepness helpers already exist; do not change scores unless tests require |
| `tests/test_volume_renderer_controls.py` | Unit tests for quality / interactive / fallback |
| `tests/gui/test_volume_viewer_widget.py` | Widget init / deferred init / auto detail |
| `user-docs/USER_GUIDE_3D.md` | Brief note on Auto Detail + progressive refine |
| `CHANGELOG.md` | Fixed / Changed under Unreleased |
| `dev-docs/MAINTENANCE_LOG.md` | Short maintenance entry |
| `dev-docs/TO_DO.md` | Link this plan under 3D visualization |

## Recommended constants (tune with measurements; lock in Task 0)

| Name | Suggested starting value | Purpose |
|------|--------------------------|---------|
| `FIRST_PAINT_QUALITY` | `"Fast"` (sample distance 3.0) | Initial `Render()` after VTK init |
| `FALLBACK_PROBE_QUALITY` | `"Fast"` | Quality used for blank-frame probe + CPU re-render |
| `LARGE_VOLUME_BYTES` | `64 * 1024 * 1024` | Soft threshold for Auto Detail cap; renderer input is float32, so one byte threshold avoids redundant voxel/MB rules |
| `AUTO_DETAIL_CAP_LARGE` | `"Normal"` (index 1) | Max Auto Detail when large |
| `AUTO_DETAIL_CAP_HUGE` | `"Fast"` (index 0) | Optional second tier if `MB > 512` (align with existing status warning) |
| `REFINE_IDLE_MS` | `50`–`100` | Owned, cancellable single-shot `QTimer` before refining to target Detail |
| `AUTO_REFINE_BUDGET_MS` | `200` | Maximum Fast-preview + fallback time that permits automatic refinement |
| Interactive coarsening | Keep `max(quality * 2, 2.0)`; optionally more aggressive while `_first_paint_pending` | Already in `set_interactive_quality` |

---

## Task 0: Capture baseline measurements (manual / instrumented)

**Files:**
- Modify (temporary): use `DEBUG_VOLUME_3D` or a short-lived timer log around `_deferred_vtk_init` / `_render` / `check_gpu_fallback`
- Document results in this plan under “Baseline notes” (below) or `tmp/` (do not commit PHI)

- [ ] **Step 1:** On the hanging PET-CT (or similar large CT), open 3D View with `DEBUG_VOLUME_3D=True` and note wall times for: build finished → first `Render` → GPU fallback (if any) → UI responsive again; record mapper mode (GPU vs CPU) and volume dims/MB from Advanced status.
- [ ] **Step 2:** Repeat with Detail forced to Fast vs High (Auto off) to confirm High is the dominant cost.
- [ ] **Step 3:** Write 3–6 bullet “Baseline notes” into this plan (no patient identifiers).
- [ ] **Step 4:** Commit plan-only notes update if measured on a branch; otherwise keep notes local until Task 1.

**Baseline notes:** _(fill during Task 0)_

-

## Implementation notes (2026-08-10)

- Implemented a VTK-free byte-size/elapsed-time policy: 64 MiB Auto cap to
  Normal, 512 MiB Auto cap to Fast, and automatic refinement only when the
  Fast preview (including any fallback work) completes within 200 ms.
- Preview/fallback/refinement use owned `QTimer` instances and cleanup stops
  them before VTK teardown. Fast preview state is separate from the selected
  target detail, so manual changes cannot be silently overwritten.
- A GPU blank-frame fallback CPU render stays at Fast and suppresses automatic
  refinement. Manual High/Ultra is still available by explicit user action.
- Focused policy/widget/renderer tests, harness checks, architecture and link
  checks, and the full pytest suite passed. The manual timing/hardware matrix
  below remains required before archiving this plan.

---

## Task 1: Volume-size helpers + Auto Detail cap

**Files:**
- Modify: `src/core/volume_renderer.py` (or small new `src/core/volume_render_quality.py` if `volume_renderer.py` is too large — prefer helper module if adding >40 lines of pure logic)
- Modify: `src/gui/volume_viewer_widget.py` (`_apply_auto_detail`)
- Test: `tests/test_volume_renderer_controls.py` and/or new `tests/core/test_volume_render_quality.py`

**Interfaces:**
- Produces: `estimate_volume_megabytes(dims: tuple[int,int,int], bytes_per_voxel: int = 4) -> float`
- Produces: `auto_detail_cap_index(*, voxels: int, megabytes: float) -> int`
  Returns max allowed QUALITY_MODES index for Auto (0=Fast … 3=Ultra).
- Consumes: existing `QUALITY_MODES`, mapper input dims when available

- [x] **Step 1:** Write failing tests for caps (small volume → no cap beyond steepness High; large input bytes → Normal max; huge input bytes → Fast max).
- [ ] **Step 2:** Run tests — expect FAIL.
- [x] **Step 3:** Implement pure helpers based on `VolumeData.array.nbytes` (or the VTK float32 input size) + wire `_apply_auto_detail` to
  `target = min(steepness_target, auto_detail_cap_index(...))`.
- [ ] **Step 4:** When dims unavailable (pre-attach), keep current steepness-only behavior.
- [x] **Step 5:** Run focused tests — PASS.
- [ ] **Step 6:** Commit: `Cap Auto Detail for large 3D volumes.`

---

## Task 2: Progressive first paint + idle refinement

**Files:**
- Modify: `src/gui/volume_viewer_widget.py` (`_deferred_vtk_init`, new helpers)
- Modify: `src/core/volume_renderer.py` if a `render_at_quality(name)` helper helps
- Test: `tests/gui/test_volume_viewer_widget.py` (mock renderer: assert first quality Fast, then refine timer schedules target)

**Interfaces:**
- Produces: `_first_paint_complete: bool`, `_target_detail_index: int`, `_refine_timer: QTimer`, `_schedule_detail_refine()`
- Behavior:
  1. After interactor `Initialize()`, set mapper sample distance to **FIRST_PAINT_QUALITY** without permanently changing the Detail slider’s *target*.
  2. `Render()` once (cheap).
  3. Run GPU fallback at probe quality (Task 3).
  4. Start the owned `QTimer` only when preview + fallback elapsed time is within `AUTO_REFINE_BUDGET_MS` and no GPU→CPU fallback occurred; its timeout applies **capped** Auto/manual Detail and `Render()` again.
  5. If the preview is slow or fallback occurred, retain Fast preview detail, show that higher detail may be slow, and do not automatically re-render at the target.
  6. If dialog closed / `cleanup()` before refine, stop timer and skip. Manual detail/preset changes invalidate a pending timer.

- [x] **Step 1:** Add focused widget/state-machine tests for Fast preview, responsive refinement, CPU fallback suppression, and timer cancellation.
- [ ] **Step 2:** Run — FAIL.
- [x] **Step 3:** Implement progressive path with separate *target* versus temporarily-applied sample distance; keep Detail slider/caption reflecting target and show honest preview/refining state.
- [ ] **Step 4:** Ensure manual Detail changes during refine cancel pending refine and use the user’s choice.
- [x] **Step 5:** Run focused tests — PASS.
- [ ] **Step 6:** Commit: `Progressive first paint for 3D volume viewer.`

---

## Task 3: GPU fallback at Fast, then decide whether to refine

**Files:**
- Modify: `src/core/volume_renderer.py` (`check_gpu_fallback`)
- Test: `tests/test_volume_renderer_controls.py` (or extend existing fallback tests if present)

**Interfaces:**
- Change: `check_gpu_fallback(render_window, *, probe_quality: str = "Fast") -> bool`
- Behavior: the widget renders its Fast preview first, then reads that frame. If CPU fallback is needed, temporarily use Fast for the CPU re-`Render()`; do not mutate caller-owned target quality. CPU fallback disables automatic refinement for this open.
- Do **not** leave the mapper permanently at High during a blank-frame CPU re-render.

- [x] **Step 1:** Add renderer/state tests for preserving target detail through temporary Fast quality and fallback suppression.
- [x] **Step 2:** Implement.
- [ ] **Step 3:** Wire `_deferred_vtk_init` to use Fast preview before fallback; implement Tasks 2 and 3 as one render-state-machine change.
- [x] **Step 4:** Tests PASS; included in final responsiveness commit.

---

## Task 4: Busy cursor + “Rendering…” status

**Files:**
- Modify: `src/gui/volume_viewer_widget.py` and/or `volume_render_dialog.py`
- Test: light GUI test or mock that `QApplication.setOverrideCursor` / status label text is set around first paint (optional if flaky — prefer status label assert)

**Behavior:**
- Before first/fallback/refine `Render()`, set `Qt.CursorShape.WaitCursor` (override) and a visible non-modal status string (“Rendering 3D preview…” / “Refining detail…”), then yield one event-loop turn before the first render so the feedback can paint.
- Restore cursor in `finally` even if VTK raises.
- Prefer reusing Advanced status or a non-modal banner in the viewer chrome so users know the app is alive.

- [x] **Step 1:** Implement cursor + status around the progressive paint / refine path.
- [ ] **Step 2:** Manual smoke: open large CT — cursor/status visible before first paint; Close works while a refinement is queued. Do not claim it can interrupt an already-running VTK render.
- [ ] **Step 3:** Commit: `Show busy feedback during 3D first paint and refine.`

---

## Task 5: Harden interaction coarsening during first paint

**Files:**
- Modify: `src/core/volume_renderer.py` (`set_interactive_quality`) and/or widget observers
- Test: `tests/test_volume_renderer_controls.py`

**Behavior:**
- While `_first_paint_complete` is False, interactive mode uses at least Fast (or more aggressive than `max(2×quality, 2.0)` if quality is already High).
- Confirm `EndInteractionEvent` is still wired on the **interactor style** (existing fix) so coarse mode does not stick.
- Optional: skip refine `Render` while a drag is active; reschedule refine on interaction end.

- [x] **Step 1:** Cover suppressed Fast preview behavior in focused state tests.
- [x] **Step 2:** Implement + include in final responsiveness commit.

---

## Task 6: Close/cancel safety

**Files:**
- Modify: `src/gui/volume_viewer_widget.py` (`cleanup`, `closeEvent` path via dialog)
- Modify: `src/gui/dialogs/volume_render_dialog.py` if needed

**Behavior:**
- Stop the owned pending-refine `QTimer` on cleanup/close; do not use uncancellable `QTimer.singleShot`.
- Make cleanup idempotent, stop render timers, and reset initialized state before VTK teardown.
- Do not call `Render()` after VTK teardown.
- Existing `_release_worker().wait()` stays; do not add unbounded waits.

- [x] **Step 1:** Test queued-refinement cancellation; manual close while queued remains in final QA.
- [x] **Step 2:** Include cancellation in final responsiveness commit.

---

## Task 7: Docs + backlog wiring

**Files:**
- Modify: `user-docs/USER_GUIDE_3D.md` (Auto Detail, progressive refine, large-volume cap)
- Modify: `CHANGELOG.md` Unreleased Fixed/Changed (patch)
- Modify: `dev-docs/MAINTENANCE_LOG.md`
- Modify: `dev-docs/TO_DO.md` (link this plan; mark related responsiveness bullet)
- Modify: this plan status → Completed when done; move to `dev-docs/plans/completed/`

- [x] **Step 1:** Doc updates + link checker if `user-docs/` changed: `python scripts/check_user_docs_links.py`
- [x] **Step 2:** Include docs in final responsiveness commit.
- [ ] **Step 3:** Archive plan when all tasks checked.

---

## Task 8: Verification gate

- [x] Focused: `python -m pytest tests/test_volume_renderer_controls.py tests/gui/test_volume_viewer_widget.py tests/gui/test_volume_first_paint.py tests/core/test_volume_render_quality.py -v`
- [x] Architecture: `python scripts/check_architecture_boundaries.py`
- [x] Smoke: `python scripts/agent_smoke_harness.py --write-report`
- [x] Full suite: `python -m pytest tests/ -v` (~10 min)
- [ ] Manual (required for this plan):
  - [ ] Large CT / PET-CT: open 3D — UI remains responsive within ~1–2 s of dialog controls appearing; preview then refines
  - [ ] Steep preset Auto on small phantom: still allowed to refine to High
  - [ ] Force CPU (Advanced → Render: CPU) + High: progressive path still shows Fast first
  - [ ] Drag rotate during refine: stays responsive; ends at target Detail
- [ ] Close while refine is queued: clean shutdown and no later render
  - [ ] Parallels / integrated GPU if available: GPU fallback no longer freezes for minutes at High

---

## Implementation order

0 → 1 → (2 + 3) → 4 → 5 → 6 → 7 → 8

Tasks 4–6 can partially overlap after 2–3 land, but do not ship progressive paint without fallback Fast (Task 3) or close cancel (Task 6).

## Risk notes

| Risk | Mitigation |
|------|------------|
| Automatic High refinement still blocks on slow devices | Measure preview/fallback duration; skip automatic refinement when over budget or CPU fallback was used; leave manual High/Ultra available |
| Double-render increases total GPU work | Acceptable only when preview time is within the responsiveness budget |
| Auto cap surprises power users | Caps only Auto; manual High/Ultra unchanged; status can say “Auto capped for large volume” |
| Caption flicker Fast→High | Short “refining” state or keep slider on target while mapper is temporarily Fast |
| Tests without real VTK | Keep using existing mock renderer patterns in `tests/gui/test_volume_viewer_widget.py` |

## Success criteria

- Opening 3D on the previously hanging PET-CT produces a Fast preview without a prolonged initial beach-ball; slow/CPU paths do not schedule an automatic fine render.
- Final refined image quality for small volumes with steep presets remains High when Auto is on (unless user overrides).
- Focused + full automated tests green; manual checklist above completed.

# Image Smoothing When Magnified – Implementation Plan

This document is a multi-phase implementation plan for optional image smoothing when the user zooms or pans, following the recommendations in [IMAGE_SMOOTHING_WHEN_MAGNIFIED_RESEARCH.md](../info/IMAGE_SMOOTHING_WHEN_MAGNIFIED_RESEARCH.md).

**References:**
- Research and recommendations: `dev-docs/info/IMAGE_SMOOTHING_WHEN_MAGNIFIED_RESEARCH.md`
- Current display: `src/gui/image_viewer.py` (QGraphicsView, QGraphicsPixmapItem, SmoothPixmapTransform)
- Config pattern: `src/utils/config_manager.py` (e.g. `get_privacy_view` / `set_privacy_view`)
- View menu / context menu pattern: `src/gui/main_window_menu_builder.py`, `src/main.py` (`_on_privacy_view_toggled`), image viewer context menu
- Magnifier scaling: `ImageViewer._extract_image_region()` in `image_viewer.py` (QPixmap.scaled with SmoothTransformation)

---

## 1. Overview of Changes

| Area | Current behavior | Target behavior |
|------|------------------|-----------------|
| **View / item transform** | View always has `SmoothPixmapTransform`; main image item has no `setTransformationMode()` (default). | When smoothing is **on**: use `SmoothPixmapTransform` + `SmoothTransformation` on image item when **idle**; use **fast** (no hint + `FastTransformation`) during zoom/pan. When smoothing is **off**: always fast. |
| **User setting** | None. | Boolean "Smooth when zoomed" (or "Image smoothing") persisted in config; default **off** (conservative "no enhancement"). |
| **UI** | None. | Checkable action in **image viewer context menu** and in **View** menu; state synced and persisted. |
| **Magnifier** | Always uses `SmoothTransformation` in `region.scaled()`. | Use same user setting: **FastTransformation** when smoothing off, **SmoothTransformation** when on. |
| **Export** | Export uses its own resize path. | No change; export quality remains independent of display smoothing (per research). |

---

## 2. Scope and Out-of-Scope

**In scope**
- Config key and get/set for "smooth image when zoomed".
- ImageViewer: apply view render hint and image item transformation mode from setting; two-tier behavior (fast while interacting, smooth when idle) via idle timer.
- Context menu (image viewer): checkable "Smooth when zoomed" that toggles setting and persists config.
- View menu: same option (shared or synced action) for discoverability.
- Main window and main.py: wire menu/context toggle, push state to all subwindows (each ImageViewer).
- Magnifier: use same setting when choosing Fast vs Smooth in `_extract_image_region` (or equivalent scaling).
- Apply setting when new image is set and when subwindow is created (read from config).

**Out of scope**
- Tying export resize quality to this setting (export keeps current behavior).
- PIL/numpy-based pre-rendering or tile-based scaling (current design is single pixmap + view transform).
- GPU-specific interpolation paths.

---

## 3. Principles

- **Backups:** Per project rules, back up any code file before modifying it (e.g. in `backups/`).
- **No artificial test changes:** Do not alter tests solely to make them pass; fix behavior or document gaps.
- **Consistency:** All image subwindows use the same global setting; context menu and View menu reflect and update the same state.
- **Default:** Research recommends default **off** for "no enhancement"; document the choice.

---

## 4. Phase Overviews

### Phase 1: Config and core smoothing state in ImageViewer

**Goal:** Add a persisted setting and make ImageViewer apply view hint + image item transformation mode from that setting. No two-tier (idle) behavior yet—when smoothing is on, always use smooth; when off, always use fast.

**Scope:**
- Config: add key `smooth_image_when_zoomed` (default `False`), `get_smooth_image_when_zoomed()`, `set_smooth_image_when_zoomed()`.
- ImageViewer: add `_smooth_when_zoomed: bool`; add `_apply_smoothing_mode()` that sets/clears `SmoothPixmapTransform` and calls `image_item.setTransformationMode(SmoothTransformation | FastTransformation)`; call it when image is set and when setting changes. Set transformation mode on the image item when it is created (in `set_image`/display path).
- Main: at startup and when creating subwindows, pass initial value from config to each ImageViewer (e.g. `set_smooth_when_zoomed_state(config_manager.get_smooth_image_when_zoomed())`).

**Success criteria:** Config get/set works; toggling the state programmatically (e.g. from a temporary button or test) updates view and item; new images and new subwindows show correct mode. No menu/context UI yet.

**Estimated effort:** Small.

---

### Phase 2: Two-tier behavior (idle timer)

**Goal:** When smoothing is enabled, use **fast** transformation during zoom/pan/scroll and **smooth** when the user has been idle for a short period (e.g. 250–400 ms).

**Scope:**
- ImageViewer: add a restartable single-shot QTimer instance (e.g. 300 ms). "Interacting" state or equivalent.
- On transform change (zoom), scrollbar value change (pan), wheel, or other relevant interaction: restart timer, and if smoothing enabled apply **fast** mode immediately.
- On timer fire: if smoothing enabled apply **smooth** mode; if smoothing disabled keep fast.
- Ensure initial state after load is correct (idle → smooth if enabled).

**Success criteria:** With smoothing on, zooming or panning shows fast (blocky) scaling; after stopping for ~300 ms, view switches to smooth. With smoothing off, always fast. No regressions when no image is loaded.

**Estimated effort:** Small.

---

### Phase 3: User control – context menu and View menu

**Goal:** User can toggle "Smooth when zoomed" from the image viewer context menu and from the View menu; state persists and is applied to all subwindows.

**Scope:**
- MainWindow: add checkable action `smooth_when_zoomed_action` (or `image_smoothing_action`), signal `smooth_when_zoomed_toggled = Signal(bool)`, and handler `_on_smooth_when_zoomed_toggled(checked)` that calls `config_manager.set_smooth_image_when_zoomed(checked)` and emits the signal. Sync menu check state with config when opening menu or on load (same pattern as Privacy View).
- Main: connect to `smooth_when_zoomed_toggled`; in handler, call `set_smooth_when_zoomed_state(checked)` on every subwindow's image_viewer. On subwindow creation, pass initial state from config.
- Menu builder: add "Smooth when zoomed" (or "Image smoothing") to View menu (e.g. after Privacy View), checkable, connected to main window's handler; initial checked state from config.
- ImageViewer context menu: add checkable "Smooth when zoomed"; emit a class-level `Signal(bool)` with the new state; main connects to it and handles it the same as the View menu toggle.

**Success criteria:** Toggling from View menu or from any subwindow's context menu updates all viewers and persists; restarting the app restores the setting; menu and context menu check state stay in sync with actual behavior.

**Estimated effort:** Small–medium.

---

### Phase 4: Magnifier consistency

**Goal:** Magnifier uses the same "smooth when zoomed" setting when scaling the extracted region (Fast vs Smooth transformation).

**Scope:**
- In `ImageViewer._extract_image_region()` (and any other place that scales a pixmap for the magnifier): when calling `QPixmap.scaled(..., Qt.TransformationMode...)`, use `SmoothTransformation` if `_smooth_when_zoomed` is True, else `FastTransformation`.
- Ensure magnifier gets updates when the user toggles the setting (magnifier reads current viewer state when it draws; no extra wiring if it uses the same `_smooth_when_zoomed` flag).

**Success criteria:** With smoothing off, magnifier region is scaled with fast transformation; with smoothing on, with smooth transformation. No new bugs in magnifier display.

**Estimated effort:** Small.

---

### Phase 5: Tests and documentation

**Goal:** Basic test coverage and doc updates; research doc cross-reference.

**Scope:**
- Add tests (e.g. in existing test layout): config default and get/set; ImageViewer applies correct mode when state is set (and when image is set); optional: idle timer switches to smooth after delay when smoothing on. Do not change tests artificially to pass.
- Update AGENTS.md or README if there is a "View options" or "Display options" section to mention "Smooth when zoomed" (View menu / context menu).
- In `dev-docs/info/IMAGE_SMOOTHING_WHEN_MAGNIFIED_RESEARCH.md`, add a short "Implementation" subsection linking to this plan and stating that the recommended approach has been implemented (after Phase 5 is complete).

**Success criteria:** New tests pass; docs reflect the feature; research doc points to plan/implementation.

**Estimated effort:** Small.

---

## 5. Phase 1 – Detailed Checklist

Use this checklist when implementing Phase 1. Mark items only after they are fully done and verified.

### 5.1 Config: add "smooth image when zoomed"

- [ ] **Backup:** Copy `src/utils/config_manager.py` to `backups/config_manager_pre_smooth_zoomed.py` (or equivalent).
- [ ] **Default config:** In `default_config` dict, add `"smooth_image_when_zoomed": False` with a short comment (e.g. "User option to smooth image when zoomed; off by default for no-enhancement").
- [ ] **Getters/setters:** Add `get_smooth_image_when_zoomed(self) -> bool` and `set_smooth_image_when_zoomed(self, enabled: bool) -> None` following the same pattern as `get_privacy_view` / `set_privacy_view` (read/write config key, call `save_config()` in setter). Add brief docstrings.
- [ ] **Lint:** Run linter on `config_manager.py`; fix any issues.

### 5.2 ImageViewer: state and apply logic

- [ ] **Backup:** Copy `src/gui/image_viewer.py` to `backups/image_viewer_pre_smooth_zoomed.py` (or equivalent).
- [ ] **State:** Add instance attribute `_smooth_when_zoomed: bool = False` in `__init__`.
- [ ] **Apply method:** Add private method `_apply_smoothing_mode(self) -> None` that: (1) if `image_item` is not None, calls `image_item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)` when `_smooth_when_zoomed` else `Qt.TransformationMode.FastTransformation`; (2) sets `self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)` when `_smooth_when_zoomed`, or clears it with `self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)` when not. Ensure the Antialiasing hint is unaffected (set/clear only `SmoothPixmapTransform`).
- [ ] **Call apply when image is set:** In the code path that creates and sets `self.image_item` (e.g. wherever the `QGraphicsPixmapItem` is created and added to the scene), call `_apply_smoothing_mode()` after adding the item so every new image immediately gets the current mode.
- [ ] **Public setter:** Add `set_smooth_when_zoomed_state(self, enabled: bool) -> None` that sets `_smooth_when_zoomed = enabled` and calls `_apply_smoothing_mode()`. Document that this is used by main to sync the global setting to this viewer.
- [ ] **Initial state:** The attribute starts as `False` on construction. The config value is pushed to all viewers via the startup loop and `_create_managers_for_subwindow` additions in §5.3 — no further wiring is needed here. Verify that calling `set_smooth_when_zoomed_state(True/False)` correctly updates `_smooth_when_zoomed` and invokes `_apply_smoothing_mode()`.
- [ ] **Lint:** Run linter on `image_viewer.py`; fix any issues.

### 5.3 Main: pass initial config to viewers

- [ ] **Existing subwindows at startup:** In the same block as the privacy view loop in `main.py` (after `_initialize_subwindow_managers()`, ~lines 235–239), add a loop over `multi_window_layout.get_all_subwindows()` that calls `subwindow.image_viewer.set_smooth_when_zoomed_state(self.config_manager.get_smooth_image_when_zoomed())` for each subwindow (with null checks). This applies the saved config to all viewers at startup.
- [ ] **On subwindow creation:** In `_create_managers_for_subwindow()`, after `image_viewer.set_scroll_wheel_mode(scroll_mode)`, add `image_viewer.set_smooth_when_zoomed_state(self.config_manager.get_smooth_image_when_zoomed())` so new subwindows (e.g. when switching to 2×2 layout) get the current config.
- [ ] **Smoke test:** Run app; load an image; programmatically set smoothing on/off (e.g. via a temporary debug path or button) and confirm view and item switch between smooth and fast. Confirm new subwindow gets correct initial state in a multi-view layout.
- [ ] **Revert any temporary test UI** used for verification before committing Phase 1.

---

## 6. Phase 2 – Detailed Checklist

Use this checklist when implementing Phase 2. Mark items only after they are fully done and verified.

### 6.1 Idle timer and "interacting" state

- [ ] **Backup:** If not already backed up, ensure `src/gui/image_viewer.py` has a backup before further edits.
- [ ] **Timer:** In `__init__`, create a `QTimer` instance: `self._smooth_idle_timer = QTimer(self)`, then `self._smooth_idle_timer.setSingleShot(True)`, and connect `self._smooth_idle_timer.timeout` to a method that calls `_apply_smoothing_mode()`. Use a *restartable instance*, not `QTimer.singleShot()` — the static form creates a new timer on every call and cannot be cancelled or restarted. To restart on each interaction, call `self._smooth_idle_timer.start(300)` — calling `start()` on an already-running single-shot timer cancels and restarts the 300 ms countdown.
- [ ] **Interacting:** When the user triggers a transform change (zoom in/out, fit, reset view) or scrollbar change (pan), or wheel event that changes view: call `self._smooth_idle_timer.start(300)` to restart the countdown, and if `_smooth_when_zoomed` is True, immediately apply **fast** mode. If smoothing is disabled, no action is needed (always fast).
- [ ] **Wire events:** Hook into the same code paths that already trigger `_check_transform_changed()` or scrollbar updates so that each also calls `_smooth_idle_timer.start(300)` and applies fast mode when smoothing is on. Ensure **all** zoom/pan entry points are covered: wheel zoom, zoom buttons/shortcuts, fit-to-view, reset view, scrollbar pan, and pan-by-drag (if it changes transform or scrollbars).
- [ ] **Timer fire:** On timer fire, `_apply_smoothing_mode()` is called (connected above). This applies smooth when `_smooth_when_zoomed` is True, else fast — reverting to the user's preference after the idle delay.
- [ ] **Edge cases:** When there is no image (`image_item` is None), `_apply_smoothing_mode()` should no-op or only update the view hint; avoid errors. When smoothing is turned off while the timer is armed, the next timer fire is a no-op (will apply fast). Optionally call `self._smooth_idle_timer.stop()` when smoothing is turned off to avoid the unnecessary callback.
- [ ] **Lint:** Run linter on `image_viewer.py`; fix any issues.

### 6.2 Verification

- [ ] **Manual test:** Enable smoothing; zoom in/out or pan; confirm image briefly uses fast (blocky) then after ~300 ms switches to smooth. Disable smoothing; confirm always blocky. Multiple subwindows all behave correctly.
- [ ] **No regression:** With smoothing off, behavior unchanged from Phase 1 (always fast). With no image loaded, no crashes or warnings.

---

## 7. Phase 3 – Detailed Checklist

Use this checklist when implementing Phase 3. Mark items only after they are fully done and verified.

### 7.1 MainWindow: action, signal, handler

- [ ] **Backup:** Copy `src/gui/main_window.py` to `backups/main_window_pre_smooth_zoomed.py` (or equivalent) if not already backed up.
- [ ] **Signal:** Add `smooth_when_zoomed_toggled = Signal(bool)` at class level in MainWindow, alongside the existing signals (e.g. `privacy_view_toggled`).
- [ ] **Action:** Add checkable QAction (e.g. `smooth_when_zoomed_action`), label "Smooth when zoomed" (or "Image smoothing"). Set initial checked state from `config_manager.get_smooth_image_when_zoomed()` where the action is created (e.g. in menu builder).
- [ ] **Handler:** Add `_on_smooth_when_zoomed_toggled(self, checked: bool)` that calls `self.config_manager.set_smooth_image_when_zoomed(checked)` and emits `self.smooth_when_zoomed_toggled.emit(checked)`. Connect the action's `triggered` signal to this handler. Note: when the toggle arrives via the context menu path (see §7.3), main's handler also calls `config_manager.set_smooth_image_when_zoomed` — that double-save is intentional and harmless (same value, idempotent).
- [ ] **Sync menu state:** Provide a method (e.g. `set_smooth_when_zoomed_checked(self, checked: bool)`) that sets the action's checked state using `blockSignals(True/False)` around `setChecked()` so the action's `triggered` is not re-emitted. Main calls this to sync the View menu when the toggle originates from a context menu.
- [ ] **Lint:** Run linter on `main_window.py`; fix any issues.

### 7.2 Menu builder: View menu

- [ ] **Backup:** Copy `src/gui/main_window_menu_builder.py` to `backups/main_window_menu_builder_pre_smooth_zoomed.py` (or equivalent).
- [ ] **Add action:** In the View menu section, after the Privacy View action (and its separator), add the "Smooth when zoomed" action (stored as `main_window.smooth_when_zoomed_action`), checkable, initial checked state from `main_window.config_manager.get_smooth_image_when_zoomed()`. Connect `triggered` to `main_window._on_smooth_when_zoomed_toggled`.
- [ ] **Lint:** Run linter on menu builder; fix any issues.

### 7.3 Main: connect signal and push to all viewers

- [ ] **Backup:** Copy `src/main.py` to `backups/main_py_pre_smooth_zoomed.py` (or equivalent) if not already backed up.
- [ ] **ImageViewer signal:** In `image_viewer.py`, add `smooth_when_zoomed_toggled = Signal(bool)` at class level (alongside `privacy_view_toggled = Signal(bool)`). In the context menu, add a checkable "Smooth when zoomed" action placed after the Privacy View item; set its checked state to `self._smooth_when_zoomed`. On `triggered`, emit `self.smooth_when_zoomed_toggled.emit(checked)` with the new boolean state.
- [ ] **Connect in lifecycle controller:** In `SubwindowLifecycleController.connect_subwindow_signals()`, add `image_viewer.smooth_when_zoomed_toggled.connect(app._on_smooth_when_zoomed_toggled)` directly alongside `image_viewer.privacy_view_toggled.connect(app._on_privacy_view_toggled)`.
- [ ] **Connect MainWindow signal:** In main, connect `main_window.smooth_when_zoomed_toggled` to the same handler `app._on_smooth_when_zoomed_toggled`.
- [ ] **Handler:** Add `_on_smooth_when_zoomed_toggled(self, enabled: bool)` in main. Always call `self.config_manager.set_smooth_image_when_zoomed(enabled)` (this is the only place config is set when the toggle comes from a context menu; when it comes from the View menu, MainWindow already saved it, so this is an idempotent double-save — harmless). Then loop over all subwindows and call `subwindow.image_viewer.set_smooth_when_zoomed_state(enabled)`. Finally call `self.main_window.set_smooth_when_zoomed_checked(enabled)` to keep the View menu check mark in sync.
- [ ] **Lint:** Run linter on `main.py` and `image_viewer.py`; fix any issues.

### 7.4 Subwindow creation and initial state

- [ ] **Confirm:** Phase 1 already passes initial config to each new image_viewer in `_create_managers_for_subwindow()`. Confirm the call is present; add it here if it was deferred.
- [ ] **Smoke test:** Toggle from View menu: all views update, config persists after restart. Toggle from context menu (right-click on image): same. Both menus show correct check state. New subwindow gets current setting.

---

## 8. Phase 4 – Detailed Checklist

Use this checklist when implementing Phase 4. Mark items only after they are fully done and verified.

### 8.1 Magnifier: use smoothing setting when scaling

- [ ] **Backup:** If making further edits to `image_viewer.py`, ensure backup exists.
- [ ] **Locate scaling:** In `_extract_image_region()` (or the method that produces the scaled pixmap for the magnifier), find the call to `region.scaled(..., Qt.TransformationMode.SmoothTransformation)`.
- [ ] **Use setting:** Replace with a transformation mode chosen from `_smooth_when_zoomed`: `Qt.TransformationMode.SmoothTransformation` if True, else `Qt.TransformationMode.FastTransformation`.
- [ ] **Lint:** Run linter; fix any issues.
- [ ] **Manual test:** With smoothing off, open magnifier and zoom; confirm magnifier region is not smoothed (blocky). With smoothing on, confirm it is smoothed. Toggle while magnifier is open and confirm the next magnifier refresh uses the new mode.

---

## 9. Phase 5 – Detailed Checklist

Use this checklist when implementing Phase 5. Mark items only after they are fully done and verified.

### 9.1 Tests

- [ ] **Config:** Add or extend tests in `tests/` (e.g. `test_config_manager.py` or a new file) for: default value of `smooth_image_when_zoomed` is `False`; get/set round-trip; value persists to disk and reloads correctly.
- [ ] **ImageViewer:** If feasible with existing test fixtures, add a test that creates an ImageViewer, sets an image, calls `set_smooth_when_zoomed_state(True)` then `set_smooth_when_zoomed_state(False)` and verifies `image_item.transformationMode()` and the view's render hints change accordingly via Qt API. Skip if the test requires a heavy GUI fixture that is not practical; document in plan as skipped.
- [ ] **Idle timer:** Optional: test that after triggering a transform event and advancing time by more than the idle delay (e.g. using `QTest.qWait` or mocking the timer), smoothing mode is applied. Document if skipped.
- [ ] **Run tests:** Execute full test suite (`python tests/run_tests.py` or `python -m pytest tests/ -v`). Do not change tests artificially to pass; fix implementation or document known gaps.

### 9.2 Documentation

- [ ] **AGENTS.md / README:** Add a line noting that "Smooth when zoomed" (image smoothing) is a user-configurable option in the View menu and image viewer context menu; default is off; persisted in config.
- [ ] **Research doc:** In `dev-docs/info/IMAGE_SMOOTHING_WHEN_MAGNIFIED_RESEARCH.md`, add a short **Implementation** subsection at the end stating the recommended approach has been implemented per this plan (`dev-docs/plans/IMAGE_SMOOTHING_IMPLEMENTATION_PLAN.md`), covering config, two-tier idle behavior, context menu and View menu, magnifier, and tests.
- [ ] **Export/import customizations (optional):** If desired, include `smooth_image_when_zoomed` in `config_manager.export_customizations()` / `import_customizations()` so it is saved and restored with other view preferences. Document here if skipped.

---

## 10. Future considerations (out of scope for this plan)

- **Overlay/annotation items:** Only the main image item and view render hint are changed by this plan. Overlay/annotation pixmap items (e.g. in `annotation_manager`) independently use `SmoothTransformation`. When the main image uses fast transformation, overlays may appear slightly different under zoom. Matching overlay transformation to the user's smoothing setting can be a follow-up if visual consistency is desired.
- **Timer cancellation:** When smoothing is turned off while the idle timer is armed, the timer fire is a no-op, so stopping it is optional but avoids an unnecessary callback.

---

## 11. File Touch Summary

| File | Changes (summary) |
|------|-------------------|
| `src/utils/config_manager.py` | Add default key, `get_smooth_image_when_zoomed()`, `set_smooth_image_when_zoomed()`. |
| `src/gui/image_viewer.py` | Class-level `smooth_when_zoomed_toggled = Signal(bool)`; instance attr `_smooth_when_zoomed`; `_apply_smoothing_mode()`; `set_smooth_when_zoomed_state()`; call apply when image set; Phase 2: restartable idle QTimer, fast mode during interaction; Phase 3: context menu "Smooth when zoomed" action + emit signal; Phase 4: magnifier scaling mode from setting. |
| `src/gui/main_window.py` | Class-level `smooth_when_zoomed_toggled = Signal(bool)`; `smooth_when_zoomed_action`; `_on_smooth_when_zoomed_toggled()`; `set_smooth_when_zoomed_checked()`. |
| `src/gui/main_window_menu_builder.py` | Add "Smooth when zoomed" after Privacy View in View menu; connect to main window handler. |
| `src/main.py` | Connect `main_window.smooth_when_zoomed_toggled`; handler sets config, pushes state to all image_viewers, syncs menu; startup loop and `_create_managers_for_subwindow` pass initial state. |
| `src/core/subwindow_lifecycle_controller.py` | In `connect_subwindow_signals()`, add `image_viewer.smooth_when_zoomed_toggled.connect(app._on_smooth_when_zoomed_toggled)` alongside `privacy_view_toggled`. |
| `dev-docs/info/IMAGE_SMOOTHING_WHEN_MAGNIFIED_RESEARCH.md` | Add Implementation subsection linking to this plan. |
| `AGENTS.md` / `README.md` | Mention "Smooth when zoomed" as a user-configurable View option. |
| Test files in `tests/` | Add config and optionally ImageViewer/mode tests per Phase 5. |

---

## 12. Status

- **Phase 1:** Not started
- **Phase 2:** Not started
- **Phase 3:** Not started
- **Phase 4:** Not started
- **Phase 5:** Not started

Update this section as phases are completed.

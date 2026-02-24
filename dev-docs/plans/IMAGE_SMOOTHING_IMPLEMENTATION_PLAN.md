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
| **User setting** | None. | Boolean “Smooth when zoomed” (or “Image smoothing”) persisted in config; default **off** (conservative “no enhancement”). |
| **UI** | None. | Checkable action in **image viewer context menu** and in **View** menu; state synced and persisted. |
| **Magnifier** | Always uses `SmoothTransformation` in `region.scaled()`. | Use same user setting: **FastTransformation** when smoothing off, **SmoothTransformation** when on. |
| **Export** | Export uses its own resize path. | No change; export quality remains independent of display smoothing (per research). |

---

## 2. Scope and Out-of-Scope

**In scope**
- Config key and get/set for “smooth image when zoomed”.
- ImageViewer: apply view render hint and image item transformation mode from setting; two-tier behavior (fast while interacting, smooth when idle) via idle timer.
- Context menu (image viewer): checkable “Smooth when zoomed” that toggles setting and persists config.
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
- **Default:** Research recommends default **off** for “no enhancement”; document the choice.

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
- ImageViewer: add a single-shot or restarting QTimer (e.g. 300 ms). “Interacting” state or equivalent.
- On transform change (zoom), scrollbar value change (pan), wheel, or other relevant interaction: mark interacting, restart timer, and if smoothing enabled apply **fast** mode.
- On timer fire: if smoothing enabled apply **smooth** mode; if smoothing disabled keep fast. Clear interacting.
- Ensure initial state after load is correct (idle → smooth if enabled).

**Success criteria:** With smoothing on, zooming or panning shows fast (blocky) scaling; after stopping for ~300 ms, view switches to smooth. With smoothing off, always fast. No regressions when no image is loaded.

**Estimated effort:** Small.

---

### Phase 3: User control – context menu and View menu

**Goal:** User can toggle “Smooth when zoomed” from the image viewer context menu and from the View menu; state persists and is applied to all subwindows.

**Scope:**
- MainWindow: add checkable action `smooth_when_zoomed_action` (or `image_smoothing_action`), signal `smooth_when_zoomed_toggled = Signal(bool)`, and handler `_on_smooth_when_zoomed_toggled(checked)` that calls `config_manager.set_smooth_image_when_zoomed(checked)` and emits the signal. Sync menu check state with config when opening menu or on load (same pattern as Privacy View).
- Main: connect to `smooth_when_zoomed_toggled`; in handler, call `set_smooth_when_zoomed_state(checked)` on every subwindow’s image_viewer. On subwindow creation, pass initial state from config.
- Menu builder: add “Smooth when zoomed” (or “Image smoothing”) to View menu (e.g. after Privacy View), checkable, connected to main window’s handler; initial checked state from config.
- ImageViewer context menu: add checkable “Smooth when zoomed”; when triggered, either call a main-provided callback (like privacy) or emit a signal that main handles to toggle config and push to all viewers. Prefer same pattern as Privacy View: context menu emits signal → main toggles config and pushes to all.

**Success criteria:** Toggling from View menu or from any subwindow’s context menu updates all viewers and persists; restarting the app restores the setting; menu and context menu check state stay in sync with actual behavior.

**Estimated effort:** Small–medium.

---

### Phase 4: Magnifier consistency

**Goal:** Magnifier uses the same “smooth when zoomed” setting when scaling the extracted region (Fast vs Smooth transformation).

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
- Update AGENTS.md or README if there is a “View options” or “Display options” section to mention “Smooth when zoomed” (View menu / context menu).
- In `dev-docs/info/IMAGE_SMOOTHING_WHEN_MAGNIFIED_RESEARCH.md`, add a short “Implementation” subsection linking to this plan and stating that the recommended approach has been implemented (after Phase 5 is complete).

**Success criteria:** New tests pass; docs reflect the feature; research doc points to plan/implementation.

**Estimated effort:** Small.

---

## 5. Phase 1 – Detailed Checklist

Use this checklist when implementing Phase 1. Mark items only after they are fully done and verified.

### 5.1 Config: add “smooth image when zoomed”

- [ ] **Backup:** Copy `src/utils/config_manager.py` to `backups/config_manager_pre_smooth_zoomed.py` (or equivalent).
- [ ] **Default config:** In `default_config` dict, add `"smooth_image_when_zoomed": False` with a short comment (e.g. “User option to smooth image when zoomed; off by default for no-enhancement”).
- [ ] **Getters/setters:** Add `get_smooth_image_when_zoomed(self) -> bool` and `set_smooth_image_when_zoomed(self, enabled: bool) -> None` following the same pattern as `get_privacy_view` / `set_privacy_view` (read/write config key, call `save_config()` in setter). Add brief docstrings.
- [ ] **Lint:** Run linter on `config_manager.py`; fix any issues.

### 5.2 ImageViewer: state and apply logic

- [ ] **Backup:** Copy `src/gui/image_viewer.py` to `backups/image_viewer_pre_smooth_zoomed.py` (or equivalent).
- [ ] **State:** Add instance attribute `_smooth_when_zoomed: bool = False` (or read initial from a callback if preferred; for Phase 1, can be set only by caller).
- [ ] **Apply method:** Add private method `_apply_smoothing_mode(self) -> None` that: (1) if `image_item` is not None, calls `image_item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)` when `_smooth_when_zoomed` else `Qt.TransformationMode.FastTransformation`; (2) if `_smooth_when_zoomed`, sets `self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)` on the view, otherwise clears it (`setRenderHint(..., False)` or remove the hint). Ensure Antialiasing hint is unchanged (keep as is).
- [ ] **Call apply when image is set:** In the code path that creates and sets `self.image_item` (e.g. in `set_image` or wherever the pixmap is assigned), after adding the item to the scene, call `_apply_smoothing_mode()` so new images get the current mode.
- [ ] **Public setter:** Add `set_smooth_when_zoomed_state(self, enabled: bool) -> None` that sets `_smooth_when_zoomed = enabled` and calls `_apply_smoothing_mode()`. Document that this is used by main to sync the global setting to this viewer.
- [ ] **Initial state:** Ensure that when the viewer is created, it starts with a consistent state (e.g. False until main calls `set_smooth_when_zoomed_state` with config value). If subwindows are created after main has config, main will pass initial value in Phase 3; for Phase 1, manual or test call to `set_smooth_when_zoomed_state(True/False)` should update display.
- [ ] **Lint:** Run linter on `image_viewer.py`; fix any issues.

### 5.3 Main: pass initial config to viewers

- [ ] **On subwindow creation:** Wherever a new ImageViewer is created and added to a subwindow, after creation call `image_viewer.set_smooth_when_zoomed_state(self.config_manager.get_smooth_image_when_zoomed())` so new subwindows get the current config.
- [ ] **Existing subwindows at startup:** After layout is built and subwindows exist, ensure each existing image_viewer receives the initial state (e.g. loop and call `set_smooth_when_zoomed_state(config_manager.get_smooth_image_when_zoomed())`). Match how privacy view is applied to existing viewers at startup.
- [ ] **Smoke test:** Run app; load an image; programmatically set smoothing on/off (e.g. via a temporary debug path or by adding a temporary button) and confirm view and item switch between smooth and fast. Confirm new subwindow gets correct initial state if you have multi-view layout.
- [ ] **Revert any temporary test UI** used for verification before committing Phase 1.

---

## 6. Phase 2 – Detailed Checklist

Use this checklist when implementing Phase 2. Mark items only after they are fully done and verified.

### 6.1 Idle timer and “interacting” state

- [ ] **Backup:** If not already backed up, ensure `src/gui/image_viewer.py` has a backup before further edits.
- [ ] **Timer:** Add a QTimer (e.g. `_smooth_idle_timer`) single-shot or with 300 ms interval. When it fires, call a method that applies “idle” smoothing mode (smooth if `_smooth_when_zoomed`, else keep fast).
- [ ] **Interacting:** When the user triggers a transform change (zoom in/out, fit, reset view) or scrollbar change (pan), or wheel event that changes view: restart the timer and immediately apply **fast** mode if `_smooth_when_zoomed` is True (so during interaction we use fast). If smoothing is disabled, keep fast and do not need to change behavior.
- [ ] **Wire events:** Connect or hook into the same code paths that already trigger `_check_transform_changed()` or scrollbar updates so that each of those also restarts the idle timer and applies fast mode when smoothing is on. Ensure zoom (wheel or buttons), pan (scrollbars or drag), and “fit to view” / “reset view” all trigger this.
- [ ] **Timer fire:** On timer fire, call `_apply_smoothing_mode()` (which already applies smooth when `_smooth_when_zoomed` is True, else fast). So after idle delay, we revert to the “user preference” mode.
- [ ] **Edge cases:** When there is no image (`image_item` is None), `_apply_smoothing_mode()` should no-op or only update view hint; avoid errors. When smoothing is turned off while timer is armed, next timer fire should still apply fast (no-op).
- [ ] **Lint:** Run linter on `image_viewer.py`; fix any issues.

### 6.2 Verification

- [ ] **Manual test:** Enable smoothing; zoom in/out or pan; confirm image briefly uses fast (blocky) then after ~300 ms switches to smooth. Disable smoothing; confirm always blocky. Multiple subwindows all behave correctly.
- [ ] **No regression:** With smoothing off, behavior unchanged from Phase 1 (always fast). With no image loaded, no crashes or warnings.

---

## 7. Phase 3 – Detailed Checklist

Use this checklist when implementing Phase 3. Mark items only after they are fully done and verified.

### 7.1 MainWindow: action, signal, handler

- [ ] **Backup:** Copy `src/gui/main_window.py` to `backups/main_window_pre_smooth_zoomed.py` (or equivalent) if not already backed up.
- [ ] **Signal:** Add `smooth_when_zoomed_toggled = Signal(bool)` to MainWindow (or the class that holds the View menu actions).
- [ ] **Action:** Add checkable QAction (e.g. `smooth_when_zoomed_action`), label “Smooth when zoomed” (or “Image smoothing”). Set initial checked state from `config_manager.get_smooth_image_when_zoomed()` where the action is created (e.g. in menu builder).
- [ ] **Handler:** Add `_on_smooth_when_zoomed_toggled(self, checked: bool)` that calls `self.config_manager.set_smooth_image_when_zoomed(checked)` and emits `smooth_when_zoomed_toggled.emit(checked)`. Connect the action’s `triggered` to this handler (passing the action’s checked state). Ensure menu check state is updated when the user toggles from context menu (main will call a method to sync—see below).
- [ ] **Sync menu state:** Provide a method (e.g. `set_smooth_when_zoomed_checked(self, checked: bool)`) that sets the action’s checked state without triggering the handler, so main can sync the View menu when the toggle originates from the context menu. Call it from main’s handler when pushing state to viewers.
- [ ] **Lint:** Run linter on `main_window.py`; fix any issues.

### 7.2 Menu builder: View menu

- [ ] **Backup:** Copy `src/gui/main_window_menu_builder.py` to `backups/main_window_menu_builder_pre_smooth_zoomed.py` (or equivalent).
- [ ] **Add action:** In the View menu section, add the “Smooth when zoomed” action (create on main_window, e.g. `main_window.smooth_when_zoomed_action`), checkable, initial checked from `main_window.config_manager.get_smooth_image_when_zoomed()`, and add it to the view menu (e.g. after Privacy View, with separator if desired). Connect `triggered` to `main_window._on_smooth_when_zoomed_toggled` (pass checked state—ensure the handler receives the new value).
- [ ] **Lint:** Run linter on menu builder; fix any issues.

### 7.3 Main: connect signal and push to all viewers

- [ ] **Backup:** Copy `src/main.py` to `backups/main_py_pre_smooth_zoomed.py` (or equivalent) if not already backed up.
- [ ] **Connect:** Connect `main_window.smooth_when_zoomed_toggled` to a new handler in main (e.g. `_on_smooth_when_zoomed_toggled(self, enabled: bool)`).
- [ ] **Handler:** In the handler, loop over all subwindows and call `subwindow.image_viewer.set_smooth_when_zoomed_state(enabled)`. Also call `main_window.set_smooth_when_zoomed_checked(enabled)` so the View menu check state stays in sync when the toggle came from the context menu.
- [ ] **Context menu from viewer:** In ImageViewer context menu, add a checkable “Smooth when zoomed” action. When triggered, it should notify main (same pattern as Privacy View): either emit a signal that main connects to, or call a callback provided to the viewer (e.g. when building the viewer, main passes `toggle_smooth_when_zoomed_callback` and `get_smooth_when_zoomed_state_callback`). Main’s callback should toggle config, emit or call the same path as the View menu (set config, then push to all viewers and update main window action check state). Prefer reusing the same “toggle” logic: get current state, flip it, set config, push to all viewers, update menu.
- [ ] **ImageViewer context menu:** Add the “Smooth when zoomed” menu item; checked state = current `_smooth_when_zoomed`. On trigger, call the callback that main provided (e.g. `toggle_smooth_when_zoomed_callback()`) so main toggles and pushes; no need for viewer to know config. Alternatively, viewer can emit `smooth_when_zoomed_toggled.emit(not self._smooth_when_zoomed)` and main connects to that and treats it as “toggle” (main then reads new state from config after setting it). Choose one pattern and document.
- [ ] **Lint:** Run linter on `main.py` and `image_viewer.py`; fix any issues.

### 7.4 Subwindow creation and initial state

- [ ] **Confirm:** Phase 1 already passes initial config to each new image_viewer when subwindows are created. Confirm that when a new subwindow is created, it receives `set_smooth_when_zoomed_state(config_manager.get_smooth_image_when_zoomed())`. If not already done in Phase 1, add it here.
- [ ] **Smoke test:** Toggle from View menu: all views update, config persists after restart. Toggle from context menu (right-click on image): same. Both menus show correct check state. New subwindow gets current setting.

---

## 8. Phase 4 – Detailed Checklist

Use this checklist when implementing Phase 4. Mark items only after they are fully done and verified.

### 8.1 Magnifier: use smoothing setting when scaling

- [ ] **Backup:** If making further edits to `image_viewer.py`, ensure backup exists.
- [ ] **Locate scaling:** In `_extract_image_region()` (or the method that produces the scaled pixmap for the magnifier), find the call to `region.scaled(..., Qt.TransformationMode.SmoothTransformation)` (or equivalent).
- [ ] **Use setting:** Replace with a transformation mode chosen from `_smooth_when_zoomed`: if True use `Qt.TransformationMode.SmoothTransformation`, else `Qt.TransformationMode.FastTransformation`.
- [ ] **Lint:** Run linter; fix any issues.
- [ ] **Manual test:** With smoothing off, open magnifier and zoom; confirm magnifier region is not smoothed. With smoothing on, confirm it is smoothed. Toggle while magnifier is open and confirm next refresh uses new mode (or document that magnifier updates on next move/refresh).

---

## 9. Phase 5 – Detailed Checklist

Use this checklist when implementing Phase 5. Mark items only after they are fully done and verified.

### 9.1 Tests

- [ ] **Config:** Add or extend tests for config: default value of `smooth_image_when_zoomed` is False; get/set round-trip and persist (if test infrastructure allows).
- [ ] **ImageViewer:** If feasible, add a test that creates an ImageViewer (or uses existing test fixture), sets an image, calls `set_smooth_when_zoomed_state(True)` then `set_smooth_when_zoomed_state(False)` and verifies the image item’s transformation mode and/or view render hint (via Qt API) change accordingly. Skip if requires heavy GUI fixture; document in plan.
- [ ] **Idle timer:** Optional: test that after triggering a transform and advancing time by more than the idle delay, smoothing mode is applied (e.g. mock timer or use QTest). Document if skipped.
- [ ] **Run tests:** Execute full test suite; do not change tests artificially to pass; fix implementation or document known gaps.

### 9.2 Documentation

- [ ] **AGENTS.md / README:** If there is a “View options” or “Display options” section, add a line that “Smooth when zoomed” (or “Image smoothing”) can be toggled from the View menu or the image viewer context menu and is persisted in config; default is off.
- [ ] **Research doc:** In `dev-docs/info/IMAGE_SMOOTHING_WHEN_MAGNIFIED_RESEARCH.md`, add a short **Implementation** subsection (e.g. at the end) stating that the recommended approach has been implemented per the plan in `dev-docs/plans/IMAGE_SMOOTHING_IMPLEMENTATION_PLAN.md`, with Phases 1–5 (config, two-tier idle behavior, context and View menu, magnifier, tests and docs).

---

## 10. File Touch Summary

| File | Changes (summary) |
|------|-------------------|
| `src/utils/config_manager.py` | Add default key, `get_smooth_image_when_zoomed()`, `set_smooth_image_when_zoomed()`. |
| `src/gui/image_viewer.py` | Add `_smooth_when_zoomed`, `_apply_smoothing_mode()`, `set_smooth_when_zoomed_state()`; call apply when image set; Phase 2: idle timer and fast-during-interaction; Phase 3: context menu action and callback/signal; Phase 4: magnifier scaling mode from setting. |
| `src/gui/main_window.py` | Add `smooth_when_zoomed_toggled` signal, `smooth_when_zoomed_action`, `_on_smooth_when_zoomed_toggled`, `set_smooth_when_zoomed_checked()`. |
| `src/gui/main_window_menu_builder.py` | Add “Smooth when zoomed” to View menu, connect to main window handler. |
| `src/main.py` | Connect `smooth_when_zoomed_toggled`; handler pushes state to all image_viewers and syncs menu; pass toggle/get callbacks to ImageViewer for context menu; pass initial state on subwindow creation (if not in Phase 1). |
| `dev-docs/info/IMAGE_SMOOTHING_WHEN_MAGNIFIED_RESEARCH.md` | Add Implementation subsection linking to this plan. |
| `AGENTS.md` / `README.md` | Mention “Smooth when zoomed” in View/display options if applicable. |
| Test files | Add config and optionally ImageViewer/mode tests per Phase 5. |

---

## 11. Status

- **Phase 1:** Not started  
- **Phase 2:** Not started  
- **Phase 3:** Not started  
- **Phase 4:** Not started  
- **Phase 5:** Not started  

Update this section as phases are completed.

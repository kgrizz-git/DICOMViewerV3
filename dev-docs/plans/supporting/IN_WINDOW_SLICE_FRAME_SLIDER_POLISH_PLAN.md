# Plan: In-Window Slice/Frame Slider Polish

Last updated: 2026-05-31

## Goal and success criteria

Refine the already-implemented in-window slice/frame navigation slider so it is easier to grab, less visually intrusive, and configurable enough to avoid conflicts with overlays and user navigation preferences.

Success criteria:

- The slider handle is easier to acquire than the current small 14 px handle and uses a cursor that clearly communicates slider dragging rather than image panning.
- The default horizontal slider no longer spans the full viewport width; it uses about the central 50% of the viewport so it fits between overlay corner text.
- Users can choose slider placement on bottom, top, left, or right.
- Users can choose direction/inversion so slice/frame 1 can be at the left/bottom/top/right side according to preference.
- Direction/inversion has one explicit owner for mapping visual slider values to app navigation indices, so wheel/keyboard/cine movement and slider dragging cannot double-invert.
- True multi-frame instances use frame labeling and frame range data where applicable; ordinary multi-slice series keep slice labeling.
- Wheel, keyboard, cine, navigator thumbnail selection, MPR, and programmatic navigation keep the overlay state synchronized.
- The implementation updates the shipped `EdgeRevealSliderOverlay` path rather than resurrecting the older unimplemented plan text in `VIEWER_UX_FEATURES_PLAN.md`.

## Context and links

- Backlog items: `dev-docs/TO_DO.md` UX / Workflow in-window slider bar handle, shorter central-width bar, and placement/direction options.
- **Corner overlay position labels (stack vs InstanceNumber):** [`OVERLAY_SLICE_FRAME_POSITION_LABEL_PLAN.md`](OVERLAY_SLICE_FRAME_POSITION_LABEL_PLAN.md) — slice/frame position text belongs in the corner overlay rather than inside the slider control.
- Older background plan: `dev-docs/plans/supporting/VIEWER_UX_FEATURES_PLAN.md#6-subwindow-slice--frame-slider-bars`. That plan is stale for this work because the core edge-reveal slider has already shipped.
- Current implementation:
  - `src/gui/edge_reveal_slider_overlay.py` owns the `EdgeRevealSliderOverlay` widget, current horizontal `QSlider`, opacity/fade behavior, cursor, orientation, and stylesheet.
  - `src/gui/image_viewer.py` creates `_slider_overlay`, exposes `set_slice_slider_enabled()`, `set_navigation_slider_state()`, routes slider changes through `slider_navigate_callback`, and positions the overlay with `_reposition_slider_overlay()`.
  - `src/gui/image_viewer_input.py` reveals/hides the overlay using a hard-coded bottom activation band of 40 px.
  - `src/gui/image_viewer_view.py` repositions viewport-anchored overlays during resize and scroll.
  - `src/utils/config/display_config.py` persists the global `show_slice_slider` toggle.
  - `src/utils/config_manager.py` defines default config keys that new placement/direction settings must join.
  - `src/gui/main_window_menu_builder.py` currently exposes the feature as `Show In-Window Frame Slider`, even though the overlay may represent slices or frames.
  - `src/core/subwindow_image_viewer_sync.py`, `src/core/slice_display_handlers.py`, `src/core/study_navigation_handlers.py`, `src/core/subwindow_lifecycle_controller.py`, `src/core/mpr_controller.py`, and `src/main.py::_sync_navigation_slider_for_subwindow()` feed state into the overlay.
  - Current callers pass slice mode by default; frame-specific state must be added intentionally rather than assumed, but the slider itself should not render position text.

## Task graph and gates

### Ordering

- T1 -> T2 -> T3.
- T4 and T5 follow T3 and must be settled before implementation work that touches index mapping or labels.
- T6 and T7 both touch `src/gui/edge_reveal_slider_overlay.py`; implement them together or sequence them, then run T8.
- T9 -> T10 -> T11 for geometry.
- T12 -> T13 -> T14 -> T15 for persisted preferences and placement-aware overlay behavior; T16 -> T17 for user controls and live propagation.
- T17 and T18 follow the mapping/config decisions and should land before final verification.

### Verification gates

- Gate 1: UX/reviewer approves default handle size, central-width ratio, placement names, and direction labels before implementation.
- Gate 2: Reviewer approves the single inversion/index-mapping owner and the slice-vs-frame state-source rule before navigation code changes.
- Gate 3: Unit/widget tests cover geometry and configuration mapping for bottom/top/left/right placements.
- Gate 4: Tests cover slider-to-navigation conversion in both directions and confirm no double inversion.
- Gate 5: Manual smoke confirms the slider remains easy to reveal/use without blocking pan, W/L drag, context menu, or overlay text.

### File / area ownership

- `src/gui/edge_reveal_slider_overlay.py` -> coder/ux for handle styling, cursor, orientation, label layout, and hit target.
- `src/gui/image_viewer.py` -> coder for placement-aware positioning, viewer-facing API, and the app boundary where 1-based slider values become 0-based navigation indices.
- `src/gui/image_viewer_input.py` -> coder for placement-aware activation zones.
- `src/utils/config/display_config.py` and `src/utils/config_manager.py` -> coder for persisted placement/direction preferences, defaults, validation, and fallback.
- `src/core/subwindow_image_viewer_sync.py`, `src/core/actions/view_actions.py`, and `src/main.py::_sync_navigation_slider_for_subwindow()` -> coder for initial application, live propagation, and slice/frame state source.
- `src/gui/main_window_menu_builder.py`, settings dialog/config UI if needed -> coder/ux for user controls and existing toggle-label cleanup.
- `tests/` focused slider overlay/config/navigation tests -> tester/coder.

## Phases

### Phase 1 - Specify default geometry and interaction

- [x] (T1) Audit current overlay dimensions, stylesheet, activation zone, and conflicts with corner overlay text in 1x1, 1x2, 2x1, and 2x2 layouts (owner: ux/tester, parallel-safe: no, stream: none, after: none).
- [x] (T2) Decide default values: handle visual size, handle hit target, central-width ratio (target about 50%), minimum usable width, overlay height, activation-zone thickness, and hide delay (owner: ux, parallel-safe: no, stream: none, after: T1).
- [x] (T3) Define user-facing labels for placement and direction, avoiding ambiguous terms such as "normal" when orientation changes (owner: ux/coder, parallel-safe: no, stream: none, after: T2).
- [x] (T4) Define the slice-vs-frame state rule: which datasets/subwindow states produce `Slice` labels, which produce `Frame` labels, and which total/current index fields feed the overlay (owner: coder/ux, parallel-safe: no, stream: none, after: T3).
- [x] (T5) Define one inversion/index-mapping owner and helper contract, including whether Qt `invertedAppearance`/`invertedControls` are visual-only or whether app-facing values are remapped before `slider_navigate_callback` (owner: coder/reviewer, parallel-safe: no, stream: none, after: T3).

### Phase 2 - Larger handle and clearer cursor

- [x] (T6) Increase the slider handle visual size and/or hit target in `EdgeRevealSliderOverlay` while preserving a clean unobtrusive track (owner: coder, parallel-safe: no, stream: A, after: T2).
- [x] (T7) Set an explicit cursor over the slider/handle, such as horizontal/vertical resize or pointing hand depending on Qt behavior, so hovering the control no longer feels like image pan mode (owner: coder, parallel-safe: no, stream: A, after: T6).
- [x] (T8) Add focused tests or inspection helpers proving the overlay creates the expected cursor/style state without relying on full app startup (owner: tester/coder, parallel-safe: no, stream: A, after: T6/T7).

### Phase 3 - Shorter central slider bar

- [x] (T9) Change `_reposition_slider_overlay()` so the default bottom placement computes a centered overlay width around 50% of viewport width, with sensible min/max clamping for small panes (owner: coder, parallel-safe: no, stream: B, after: T2).
- [x] (T10) Decide whether the translucent background should shrink with the slider or whether only the active track shrinks inside a full-width transparent overlay; prefer not blocking image interactions outside the visible central control (owner: ux/coder, parallel-safe: no, stream: B, after: T9).
- [x] (T11) Add geometry tests for representative viewport widths and heights, including small panes where the label may need to hide or the ratio may need to clamp; cover vertical left/right placements with central-height clamping (owner: tester/coder, parallel-safe: no, stream: B, after: T9).

### Phase 4 - Placement and direction preferences

- [x] (T12) Add configuration keys for slider placement (`bottom`, `top`, `left`, `right`) and direction/inversion in both `display_config.py` accessors and `ConfigManager.default_config`, with defaults matching current behavior except for the new shorter central width (owner: coder, parallel-safe: no, stream: C, after: T2).
- [x] (T13) Validate persisted placement/direction values and fall back to defaults for unknown or stale config strings without crashing startup (owner: coder, parallel-safe: no, stream: C, after: T12).
- [x] (T14) Extend `EdgeRevealSliderOverlay` to support horizontal and vertical orientations, label placement, and inverted appearance/controls for each edge according to the T5 mapping contract (owner: coder, parallel-safe: no, stream: C, after: T5/T12/T13).
- [x] (T15) Make activation-zone logic in `image_viewer_input.py` placement-aware rather than bottom-edge-only (owner: coder, parallel-safe: no, stream: C, after: T14).
- [x] (T16) Add UI for choosing placement and direction, either in View menu sub-actions or the Settings dialog if the menu would become too crowded; also rename the existing toggle from frame-only wording to slice/frame wording (owner: ux/coder, parallel-safe: no, stream: C, after: T3/T5/T12).
- [x] (T17) Propagate placement/direction changes to all subwindow viewers without requiring reload, including initial application in `apply_initial_image_viewer_display_state()` and live menu/settings changes through view actions (owner: coder, parallel-safe: no, stream: C, after: T14/T15/T16).
- [x] (T18) Wire frame-specific overlay state for true multi-frame instances per T4, while preserving slice behavior for native multi-slice series and MPR stacks (owner: coder, parallel-safe: no, stream: C, after: T4/T17).

### Phase 3b - Overlay-aware geometry (follow-up)

- [ ] (T23) Reduce default central width/height ratio and/or inset slider geometry using estimated safe margins for corner metadata overlays and direction/scale-marker labels so the track rarely overlaps readable UI (owner: coder/ux, parallel-safe: no, stream: B, after: T9).
- [ ] (T24) Add geometry tests for representative overlay-on layouts (bottom bar vs lower-left/right corner text and direction labels) (owner: tester/coder, parallel-safe: no, stream: B, after: T23).

### Phase 5 - Verification and documentation

- [x] (T19) Add tests for config defaults, invalid-value fallback, persistence, placement mapping, direction inversion, and slider-to-navigation index conversion (owner: tester/coder, parallel-safe: no, stream: none, after: T17).
- [x] (T20) Add tests for frame-vs-slice state/ranges, including true multi-frame instances, ordinary multi-slice series, and MPR stacks; ensure the slider bar itself does not duplicate overlay position text (owner: tester/coder, parallel-safe: no, stream: none, after: T18).
- [ ] (T21) Manually smoke wheel navigation, arrow navigation, cine playback, navigator thumbnail clicks, MPR panes, multi-frame frame labels, pan drag, W/L drag, and right-click context menus with each placement and direction option (owner: tester, parallel-safe: no, stream: none, after: T19/T20).
- [x] (T22) Update user-facing docs or help text if placement/direction settings are exposed beyond the View menu toggle (owner: docwriter, parallel-safe: yes, stream: D, after: T16).

## Risks and mitigations

- Risk: A larger handle becomes visually distracting. Mitigation: separate visual size from hit target where possible and keep fade/opacity subtle.
- Risk: A shorter central overlay may be hard to reveal if activation depends only on visible geometry. Mitigation: keep the activation zone edge-based but keep pointer event capture limited to the visible overlay.
- Risk: Vertical placements can conflict with right-click context menu or side overlay text. Mitigation: test all four layouts and allow users to choose a different edge.
- Risk: Direction settings can confuse 1-based UI labels and 0-based internal indices. Mitigation: keep `slider_value_changed` 1-based at the overlay boundary and test conversion in both directions.
- Risk: Inversion is applied in both Qt control settings and app index conversion. Mitigation: document one mapping owner in T5, centralize conversion, and test slider drag plus programmatic updates.
- Risk: Stale config values from prior experimental builds break startup or hide the slider. Mitigation: validate placement/direction getters and fall back to safe defaults.
- Risk: The existing feature is named as a frame slider but often controls slices. Mitigation: rename labels and tests to `slice/frame` unless a true multi-frame state is active.
- Risk: View menu clutter grows. Mitigation: use a submenu or Settings panel if placement/direction options are more than a simple toggle.

## Modularity and file-size guardrails

Keep the overlay widget responsible for its own orientation, label layout, style, and cursor. Keep viewport placement math in `ImageViewer` or a small helper. Avoid spreading edge-specific geometry calculations across input, view, and app-level controllers.

Keep direction/index conversion centralized at the overlay boundary. The overlay may know how to display an inverted control, but app navigation callbacks should receive the same 0-based logical slice/frame index regardless of edge placement or visual direction.

## Testing strategy

- Unit/widget tests for `EdgeRevealSliderOverlay` orientation, cursor/style hooks, signal behavior, and label updates.
- Geometry tests for centered 50% width, vertical central-height placement, and top/bottom/left/right placement with small and normal viewport sizes.
- Config tests in the display config suite for placement and direction defaults, invalid-value fallback, and persistence.
- Focused navigation tests that verify direction inversion maps UI values to the expected 0-based slice/frame index and that programmatic state updates render the expected visual handle position.
- Focused state-source tests for `Slice` vs `Frame` state/ranges, especially true multi-frame instances versus ordinary multi-slice series, while keeping the slider control text-free.
- Manual smoke across 1x1, 1x2, 2x1, and 2x2 layouts with overlays visible and hidden.

## UX / UI

Default should remain low-clutter: bottom edge, centered shorter control, larger easy-grab handle, and a cursor that makes it feel like a control rather than image panning. Placement/direction choices should be discoverable but not prominent enough to distract casual users.

## Questions for user

- Should the default shorter bar be exactly 50% of viewport width, or should it be "about 50%" with min/max clamps based on pane size?
- Should placement/direction live in the View menu, Settings dialog, or both?
- For direction labels, should the UI describe physical edge placement (`first at left`, `first at right`, etc.) or navigation intent (`increasing toward right`, `increasing toward left`, etc.)?

## Completion notes

- 2026-05-31 implementation:
  - Defaults/settings: `slice_slider_placement="bottom"`, `slice_slider_direction="first_at_start"`; valid placements are `bottom`, `top`, `left`, `right`; valid directions are `first_at_start` and `first_at_end`.
  - Geometry: top/bottom overlays are centered at about 50% of viewport width, clamped by an 8 px edge margin and a 180 px preferred minimum when space allows; left/right overlays are centered at about 50% of viewport height. The visible overlay geometry shrinks to the central control, so it does not capture pointer events across the full viewport.
  - Interaction: handle visual size is 22 px; horizontal overlays use `SizeHorCursor`, vertical overlays use `SizeVerCursor`; reveal zones are placement-aware with the existing 40 px edge band.
  - Mapping: inversion is handled by Qt slider appearance/controls; app navigation callbacks still receive the same 0-based logical index through `slider_value_to_logical_index()`.
  - Labels: no slice/frame position text is shown inside the slider bar; corner overlays own that text. Split multi-frame wrappers still use `Frame` state internally, while ordinary series and MPR stacks use `Slice`.
  - UI/docs: View menu controls are grouped under `View -> In-Window Slice/Frame Slider`; placement and direction live inside that submenu. `user-docs/CONFIGURATION.md` documents the controls.
  - Tests/checks run: focused slider/config/navigation tests, nearby GUI/menu construction tests, user-doc link checker, `py_compile`, and touched-file `basedpyright --level error`.
  - Manual smoke: T21 remains pending for hands-on verification across every placement/direction with real image navigation workflows.
- 2026-06-03 backlog sync: placement/direction (Phase 4) and central-width bar (Phase 3) marked done in `dev-docs/TO_DO.md`. User follow-up: bar may need to be narrower still, or geometry should avoid corner overlays and direction/scale-marker labels — tracked as Phase 3b (T23/T24).

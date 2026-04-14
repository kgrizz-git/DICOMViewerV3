# Window Layout and Navigation Polish Plan

Last updated: 2026-03-22
Owner: DICOM Viewer V3
Status: Draft implementation plan

## Goals

Implement these UX/navigation improvements:

1. Allow further subdivision of each subwindow into up to 4 tiles.
2. Add a View Fullscreen command and shortcut that enters app fullscreen and hides panes/toolbar.
3. Provide slice position line display options (middle only vs begin/end).
4. When Show Instances Separately is enabled, allow left/right keys to move across instances.

## Constraints and Existing Architecture Notes

- Respect current controller boundaries in src/main.py, src/core/, src/gui/, src/metadata/, and src/roi/.
- Keep signal wiring centralized in DICOMViewerApp._connect_signals family.
- Reuse existing config persistence patterns via src/utils/config_manager.py and mixins in src/utils/config/.
- Preserve Privacy Mode behavior while updating overlays and keyboard navigation.

## 1. Subwindow Further Subdivision (Up to 4 Tiles)

### Scope

- Add optional local tiling within each existing viewport slot (1x1, 1x2, 2x1, 2x2 layouts remain top-level).
- Support per-subwindow tile counts of 1, 2, or 4.

### Proposed Design

- Introduce a lightweight tile container widget inside each subwindow content area.
- Keep a single active tile per subwindow for tool focus and keyboard operations.
- Route viewer interactions to active tile while keeping the existing manager ownership model.

### Data/State

- Persist per-subwindow tile mode and active tile index in config.
- Defaults: tile mode = 1, active tile = 0.

### Implementation Steps

1. Add tile container abstraction in src/gui/ and integrate into subwindow creation path.
2. Update focus tracking so active subwindow and active tile are both known.
3. Add context-menu commands: Split 1/2/4, focus tile, reset tiles.
4. Ensure ROI/measurement/annotation tools target active tile image viewer only.
5. Add serialization/deserialization for tile state in config.

### Validation

- Switch tile modes repeatedly in all top-level layouts.
- Verify tool operations, drag/drop, and focus behavior remain stable.
- Confirm no regression for swap behavior in 2x2 top-level layout.

## 2. View Fullscreen Command and Shortcut

### Scope

- Add View menu item and shortcut to enter/exit fullscreen.
- In fullscreen, hide left pane, right pane, bottom navigator, and toolbar.

### Proposed UX

- Menu entry: View Fullscreen (checkable).
- Shortcuts: **F11** and **Ctrl+F** (Qt shows **⌘F** on macOS); **Escape** exits fullscreen when focus is not in a text/spin control. Bare **F** is not used (would conflict with typing in fields).
- Restore prior visibility/sizes when leaving fullscreen.

### Data/State

- Track pre-fullscreen UI state (splitter sizes, pane visibility, navigator, toolbar visibility).
- Fullscreen state does not overwrite user defaults unless explicitly changed outside fullscreen mode.

### Implementation Steps

1. Add action in View menu and bind shortcut.
2. Add app-level fullscreen state machine and restore snapshot.
3. Reuse existing pane/navigator show/hide methods where possible.
4. Ensure privacy toggle, dialogs, and focus handling work in fullscreen.

### Validation

- Enter/exit via menu, shortcut, and Escape.
- Confirm state restoration after layout change, file load, and tool usage.

## 3. Slice Position Line Display Options (Middle vs Begin/End)

### Scope

- Provide overlay option for slice position line mode:
  - Middle of slice.
  - Begin and end slice boundaries.

### Proposed Design

- Extend overlay configuration model with an enum-like mode field.
- Update line rendering logic to compute one or two lines based on mode.

### Data/State

- Add config key with default = middle.
- Expose setting in overlay configuration UI and optional context-menu quick toggle.

### Implementation Steps

1. Add config option and migration-safe default.
2. Add UI controls in overlay config dialog.
3. Adjust rendering path for position line overlay.
4. Ensure MPR and non-MPR views behave consistently where applicable.

### Validation

- Verify geometry in axial/coronal/sagittal and non-isotropic spacing cases.
- Confirm mode persists across restart.

## 4. Left/Right Keys for Instance Switching (Show Instances Separately)

### Scope

- When Show Instances Separately is enabled, map left/right arrow keys to previous/next instance.
- Maintain existing behavior when mode is disabled.

### Proposed Design

- Add keyboard routing branch in focused-view navigation handler.
- Delegate to instance-aware navigation in organizer/navigator layer.

### Implementation Steps

1. Detect active mode flag from existing instance-separate configuration.
2. Implement bounded instance index movement for left/right.
3. Keep up/down or scroll behavior unchanged unless separately configured.
4. Update on-screen indicators so users can see current instance/frame context.

### Validation

- Multi-frame and single-frame datasets.
- Boundary behavior at first/last instance.
- No conflicts with text/metadata editing controls.

## Cross-Cutting Test Plan

1. Manual smoke tests in one session across all four features, including restart persistence checks.
2. Add targeted regression tests where hooks already exist (config defaults, keyboard navigation routing).
3. Run existing test suite and focused viewer/navigation tests.

## Risk and Mitigation

- Risk: Increased complexity in focus routing with tiles.
  - Mitigation: Single active tile model and explicit focus update hooks.
- Risk: Fullscreen can desync visibility state.
  - Mitigation: Snapshot-and-restore model with guarded transitions.

# UX Assessment Remediation & Design System Plan

**Created:** 2026-05-03  
**Updated:** 2026-05-17  
**Source:** [ux-summary.md](../../dev-docs/ux-assessments/ux-summary.md) · [ux-assessment-overall-2026-04-30.md](../../dev-docs/ux-assessments/ux-assessment-overall-2026-04-30.md)  
**Design reference:** [DESIGN.md](../../DESIGN.md)  
**TO_DO section:** UX / Workflow

This plan addresses all P0, P1, and selected P2 findings from the 2026-04-30 UX assessment, and defines the steps to produce `DESIGN.md` as the canonical design specification for the project.

**Execution order:** Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5. Icon work (Phase 3–4) is intentionally deferred until cleanup and structural UX improvements are done, so the toolbar is in its final shape before icons are sourced and matched.

---

## Phase 1 — Design Foundation

Goal: produce `DESIGN.md` at the repo root with a living specification for color tokens, typography, spacing, iconography, and interaction patterns. All fixes in later phases must conform to it.  
**Status: largely done** — `DESIGN.md` exists; remaining items below fill in gaps.

### A1 — Audit and apply color tokens [x]

*Done 2026-05-15.*
- Read both QSS files; reconciled all literal color values with `DESIGN.md §2`.
- Added `QSlider` rules to both themes (accent-blue fill, pill handle) — eliminates purple OS-native slider.
- Added `QGroupBox` rules to both themes (see D9).
- Fixed `#ffffdc` yellow tooltip → dark tooltip `#3a3a3a` / `#ffffff` in `light.qss`.
- Templatized accent color: all `#4285da` occurrences replaced with `{accent}` / `{accent_light}` / `{accent_dark}` placeholders (see A5).
- Updated `DESIGN.md §2` goal palette: stripped audit noise, set sleeker dark theme targets, documented accent preset system.

### A2 — Apply typography spec [x]

*Closed 2026-05-17 — already correct.*
- Overlay, annotation, and measurement font defaults are all `"IBM Plex Sans"` in their respective config mixins.
- All bundled fonts (IBM Plex Sans, Noto Sans, Open Sans, Raleway, DejaVu Sans) are registered with Qt at startup via `register_fonts_with_qt()` in `utils/bundled_fonts.py`.
- Dialog UI widgets correctly use the platform system font (Segoe UI / SF Pro); no enforcement needed or desired.

### A5 — Accent colour system [x]

*Done 2026-05-17.*
- Created `src/gui/accent_presets.py` with 4 presets: Steel Blue (default), Violet, Navy, Garnet.
- Both QSS files are fully templatized with `{accent}`, `{accent_light}`, `{accent_dark}` placeholders.
- `get_theme_stylesheet()` in `main_window_theme.py` resolves the preset at load time.
- `ConfigManager` persists the selected preset id as `"accent"` (default `"steel-blue"`).
- Settings dialog (`settings_dialog.py`) exposes a combo box with a live colour swatch.
- `_on_settings_applied` in `main.py` calls `_apply_theme()` so changes are live on OK.
- Documented in `DESIGN.md §2.4`.

### A6 — Theme palette refinement + hairline splitter [x]

*Done 2026-05-17.*
- Dark theme fully rewritten to modern deep palette (`#1e1e1e` window / `#252525` panels / `#141414` inputs / `#111111` navigator / `#363636` borders / `#e0e0e0` text / `#5a5a5a` disabled).
- Gradient hairline splitter applied to both themes (1 px visual via `qlineargradient` stops 0.399–0.601; full fill on hover; 5 px hit zone preserved).
- Focus border wired to accent preset via `get_focus_border_color()` in `style_constants.py` (merged from `claude/naughty-leakey-8408fc`).

**Goal:** make the dark theme feel more modern (deeper backgrounds, slimmer borders, softer text) and align the splitter visual in both themes so it reads as a 1 px separator at rest but expands to 5 px on hover.

#### Part 1 — Dark theme palette (`dark.qss`)

Current code values diverge from the goal. Update all literal values to match `DESIGN.md §2.1`:

| Token | Goal | Current code |
|---|---|---|
| `--bg-window` | `#1e1e1e` | `#2b2b2b` |
| `--bg-panel` | `#252525` | `#3a3a3a` |
| `--bg-surface` | `#141414` | `#1e1e1e` |
| `--bg-surface-nav` | `#111111` | `#1b1b1b` |
| `--bg-surface-raised` | `#2e2e2e` | `#454545` |
| `--border` | `#363636` | `#555555` |
| `--fg-primary` | `#e0e0e0` | `#ffffff` |
| `--fg-disabled` | `#5a5a5a` | `#7f7f7f` |

Verify sufficient contrast at each surface boundary after the change: bg-window/bg-panel step, bg-surface/border, fg-primary/bg-window.

#### Part 2 — Hairline splitter (both themes)

Visual borders in the UI are 1 px. The splitter *hit zone* must stay at 5 px to be draggable, but the visual indicator should match the 1 px convention at rest. Apply to `dark.qss` **and** `light.qss`:

```css
/* Dark theme example — same pattern for light, substituting --border colour */
QSplitter::handle:horizontal {
    width: 5px;
    background-color: transparent;
    border-left: 1px solid #363636;
}
QSplitter::handle:horizontal:hover {
    background-color: #363636;
    border-left: none;
}
QSplitter::handle:vertical {
    height: 5px;
    background-color: transparent;
    border-top: 1px solid #363636;
}
QSplitter::handle:vertical:hover {
    background-color: #363636;
    border-top: none;
}
```

For `light.qss`, substitute `#363636` → `#c0c0c0` (the light `--border` value).

The light theme's background/border/text values already match the goal — only the splitter visual treatment needs changing there, not the palette.

### A3 — Spacing/sizing tokens review [x]

*Done 2026-05-17.*
- Reviewed all `DESIGN.md §5` values against code.
- Corrected ROI resize handle spec: 8 × 8 px (`HANDLE_HALF = 4.0`), not 10 × 10.
- Noted gap: handle colour is currently hardcoded cyan; goal is `--accent` (tracked in §5 note).
- All other spacing values confirmed reasonable.

### A4 — Link DESIGN.md from README and CLAUDE.md [x]

*Done 2026-05-17.*
- Added DESIGN.md as first bullet under "Developers and contributors" in `README.md`.
- No `CLAUDE.md` exists in this repo (AGENTS.md serves that role; DESIGN.md reference added to README is sufficient).

---

## Phase 2 — UX Cleanup & Structural Improvements (no icon work)

All of these can be done with text buttons. Doing this first means the toolbar is in its final shape before any icon sourcing begins.

### B-series: P0 Bugs

#### B2 — Fix toolbar overflow (two rows) [x]

*Done 2026-05-17.*
- **Font Color** removed from toolbar — already fully accessible via View → Overlay Settings (font color picker at line 161 of `overlay_settings_dialog.py`). No migration needed.
- **Use Rescaled Values** moved from toolbar `QAction` to a `QCheckBox` at the top of the Window/Zoom/ROI right-panel tab (`main_window_layout_helper.py`). Checkbox `toggled` signal connects directly to `main_window.rescale_toggle_changed`; `set_rescale_toggle_state()` updated to sync checkbox state. Old `_on_rescale_toggle_changed` on MainWindow removed.
- Toolbar now ends after Font Size +/− controls; Scroll Wheel combo remains right-aligned.
- Recheck toolbar width at 1280 px after Phase 5 icon additions (G5).

#### B3 — Fix shortcut conflicts [x]

*Done 2026-05-17.*
- Overlay Tags Config: `Ctrl+O` → `Ctrl+Shift+L` (`main_window_menu_builder.py`).
- "About this File…" renamed to "DICOM File Info…" and rebound to `Ctrl+I` in menu, dialog window title, viewport context menu, and series navigator context menu.
- `DESIGN.md §6` conflict note removed; shortcut table reflects final bindings.

#### B4 — Widen splitter handles [x]

*Done 2026-05-15.*  Splitter handles widened to 5 px in both `dark.qss` and `light.qss`; hover colour added (`#6a6a6a` dark / `#a0a0a0` light).  
*Deferred:* grip-dot visual (2 × 3 dots via `paintEvent` or SVG) — cosmetic; can be added without changing handle hit-zone size.

#### B5 — Fix "overlay mode_modality" raw identifier [x]

*Closed 2026-05-17 — already fixed.* The `QGroupBox` title in `overlay_config_dialog.py` reads `"Overlay mode & modality"` — the underscore raw-identifier leak noted in the April assessment is gone.

#### B7 — Fix Settings dialog theme rendering [x]

*Done 2026-05-17.*
- Settings dialog verified clean: no inline `setStyleSheet`, inherits app-level QSS from `QApplication.instance()` automatically.
- Found and fixed adjacent issue in the About dialog (`_show_about_dialog` in `main_window.py`): removed stale hardcoded `#2b2b2b` / `#ffffff` `QDialog` background overrides and the `QTextBrowser` dark-theme inline style — all now inherited from QSS. HTML link colour (`theme`-based) retained as it is not covered by QSS.

#### B8 — Unify app name [ ]

- Decide canonical name; apply to title bar, About dialog, `pyproject.toml`, installer, icon tooltip.
- Document the chosen name in `DESIGN.md § 1`.

### C-series: P1 Ergonomic / Discoverability

#### C1 — Label copy/paste/undo scope [x]

*Done 2026-05-17.* Copy → "Copy Annotation", Paste → "Paste Annotation". Undo/Redo left as plain "Undo"/"Redo" — the undo stack is unified across ROI, measurements, annotations, and tag edits, so a scope qualifier would be misleading.

#### C2 — View menu reorganization [x]

*Done (previous session).* Five sections with separators: (1) View Layout, (2) Overlays, (3) Linked Navigation, (4) Privacy, (5) Appearance. "Show/Hide" prefix retained on pane toggle labels — checkmark alone is ambiguous when the pane is already hidden and the item is unchecked; the prefix makes the action direction clear.

#### C3 — Remove Study Index Search duplication [x]

*Done 2026-05-17.* Removed "Study Index Search…" from Tools menu; canonical entry "Open Study Index…" remains in File menu.

#### C4 — Reduce right-click context menu depth [x]

*Done 2026-05-17.*
- All 13 tool modes grouped into "Tools ▶" submenu with separators between navigation/ROI/measure/annotation groups.
- Annotation/ROI actions (Annotation Options, Delete all ROIs, Clear Measurements, Export ROI Statistics) grouped into "Annotations ▶" submenu.
- "Cycle overlay detail / legacy toggle" → "Toggle Overlay Detail (Space)".
- "Configure Overlay Tags…" → "Overlay Tags Configuration…" (aligned with View menu label).
- Layout labels updated to × glyph ("1×1" etc.); Privacy View shortcut corrected to Ctrl+P.
- Invert Image unconditionally present (was only shown when presets existed).

#### C5 — Series navigator: show series descriptions [x]

*Done 2026-05-17.* In `series_navigator.py`, the `SeriesThumbnail(...)` call at the main-series creation point now computes a `display_label` from `first_dataset.SeriesDescription` (truncated to 16 chars with `…` if longer), falling back to `{Modality} S{series_num}`, then bare `S{series_num}`. Passed as `display_label=` keyword; `paintEvent` in `series_navigator_view.py` already uses it.

#### C6 — Fix font consistency in Annotation Options dialog [–]

*Won't do — dialog widgets correctly inherit the platform system font (Segoe UI / SF Pro). Annotation and overlay fonts are user-configurable separately. No enforcement needed.*

#### C7 — Fix "Default (Space)" overlay tag label [x]

*Done 2026-05-15.* `overlay_config_dialog.py`: `"Default (Space):"` → `"Default (Spacebar):"`.

#### C8 — Add keyboard shortcuts to toolbar tooltips [x]

*Done 2026-05-17.* Added `setToolTip` with shortcut hint to: Angle (Shift+M), Text Annotation (T), Arrow Annotation (A), Reset All Views (Shift+A). Reset View already had it. Tooltip-less actions (no bound key) left unchanged.

#### C9 — Privacy label clarity [x]

*Won't do — text too long for a toolbar button. Current "Privacy is OFF" / "Privacy is ON" labels retained.*

#### C10 — Status bar empty-state guidance [x]

*Done 2026-05-15.* `main_window.py` and `session_reset_controller.py`: `"Ready"` → `"Open a DICOM file or folder to begin"`.

#### C11 — Tool-mode cursor feedback [x]

*Already implemented.* `image_viewer_input.py` `set_mouse_mode()` and `_apply_cursor_for_mouse_mode()` set the correct Qt cursor for every mode: `CrossCursor` (ROI/measurement), `OpenHandCursor` (pan), `PointingHandCursor` (zoom), `IBeamCursor` (text annotation), `ArrowCursor` (select/default). No code change needed.

#### C12 — Histogram / chart axis label size [x]

*Done 2026-05-19.* `histogram_widget.py` `_FONT_TIERS`: label_pt bumped to 11 at medium (≥500 px) and large (≥700 px) tiers. Title remains 11/12 pt; tick labels 9/10 pt. Applied via the existing `update_font_sizes_for_size()` call at end of `_update_histogram()`.

#### C13 — SR Dose table column truncation [x]

*Done 2026-05-19.*
- `radiation_dose_report_dialog.py`: Field column fixed width 220 px; vertical header hidden; "Parse hit node cap" → "Parser node cap reached".
- `structured_report_browser_dialog.py`: Same Field column and label fix; `_populate_event_table()` now calls `resizeColumnsToContents()` after filling rows so dose-event columns auto-fit their content.

#### C14 — Conditional Delete ROI visibility [x]

*Done 2026-05-19.* `roi_list_panel.py`: buttons stored as `self.delete_button` / `self.delete_all_button`, both start disabled. `_update_button_states()` helper enables Delete Selected only when `currentItem() is not None`, Delete All only when `count() > 0`. Called from `update_roi_list()`, `_on_list_selection_changed()`, and the deselect path in `select_roi_in_list()`.

#### C15 — MPR crosshair / reference lines [x]

When an MPR pane is paired with source panes, draw the MPR cut-plane intersection line onto each source pane.

**Research completed 2026-05-19.** The feature may be substantially pre-implemented — see findings below before writing any code.

##### Findings

The existing slice-location-line pipeline (`SliceLocationLineCoordinator` → `get_slice_location_line_segments` in `core/slice_location_line_helper.py` → `SliceLocationLineManager`) already has MPR-specific branches in the helper and coordinator. `MprController.display_mpr_slice` already fires `QTimer.singleShot(0, line_coord.refresh_all)` after every slice change. `SliceSyncCoordinator.get_current_plane(idx)` already returns the correct `SlicePlane` for the current MPR slice index via `data["mpr_result"].slice_stack`.

##### Implementation phases

**Phase 1 — Verify end-to-end (do first, before writing code)**
- Enable View → Slice Location Lines. Open a native series in pane 0, create an MPR in pane 1. Scroll the MPR. Confirm a line appears on the native pane.
- If it works: skip to Phase 4.
- If not: diagnose in `get_slice_location_line_segments`; likely cause is `_slice_sync_coordinator` being `None` (verify always initialized in `main.py` regardless of sync-enabled flag) or `slice_location_lines_visible` config default being `False`.

**Phase 2 — Fix pipeline gap (only if Phase 1 fails)**
- `src/main.py`: confirm `_slice_sync_coordinator` and `_slice_location_line_coordinator` are unconditionally initialized at startup.
- `src/core/config_manager.py`: if `get_slice_location_lines_visible()` defaults to `False`, either change default or add `get_mpr_reference_lines_visible()` with default `True`.

**Phase 3 — MPR-to-MPR crosshairs**
- Two MPR panes (e.g. axial + sagittal) should show each other's cut line. Expected to work already via the same pipeline; verify.

**Phase 4 — Polish**
- Config: share `slice_location_lines_visible` key with native slice location lines (decided 2026-05-19).
- Visual style: MPR reference lines use a dashed pen to distinguish from native solid lines (decided 2026-05-19).
- If dashed: add MPR-specific `line_id` prefix (`"mpr_ref:<source_idx>"`) in `slice_location_line_helper.py` and teach `SliceLocationLineManager` to use `Qt.PenStyle.DashLine` for that prefix.

##### Files to touch
| File | Change |
|---|---|
| `core/mpr_controller.py` | None expected |
| `core/slice_location_line_helper.py` | Possibly add `mpr_ref:` line_id prefix |
| `gui/slice_location_line_manager.py` | Possibly add dash-pen path for `mpr_ref:` ids |
| `core/config_manager.py` | Possibly add independent toggle |
| `main.py` | Verify coordinator initialization order |

##### Complexity: Low–Medium (3–8 hours total; mostly verification)
##### Key risk: Feature may already work — Phase 1 first.

### D-series: P2 Polish (do alongside related work)

#### D1 — Clean up informal labels in ACR / pylinac dialogs [x]

*Done 2026-05-15.*  
**Kept "(pylinac)" in labels** — attribution to pylinac is intentional.  
**Kept "Sanity multiplier"** — it is pylinac's own parameter name (`low_contrast_visibility_sanity_multiplier`).  
**Renamed "Vanilla pylinac" → "Stock pylinac mode"** across:
- `acr_ct_qa_dialog.py`, `acr_mri_qa_dialog.py` checkboxes
- `mri_compare_result_dialog.py` column header
- `qa_app_facade.py` log strings
- `pylinac_runner.py` comment strings

#### D5 — Lime green overlay color default [ ]

*Won't do — lime green (255, 255, 0) is intentionally kept as the default. It provides superior contrast on dark greyscale radiology images compared to white, which can blend into bright image regions.*

#### D6 — "Combine/Fuse" tab rename [x]

*Done 2026-05-17.* `main_window_layout_helper.py`: tab label changed to `"Slab / Fuse"`.

#### D7 — Layout shortcut registration [x]

*Done 2026-05-17.* Layout action labels changed from `"&1x1  (1)"` style to `"&1×1"` (proper ×); shortcut hint moved to `setToolTip()`. Actual key routing (1–4) kept in existing keyboard event filter in `keyboard_event_handler.py`, which correctly gates shortcuts when a text field has focus.

#### D8 — Help menu label cleanup [x]

*Done 2026-05-17.* `"&Documentation (browser)..."` → `"&Documentation..."`. `"Fusion &Technical Documentation"` removed from Help menu; replaced with a flat `"Fusion Documentation…"` button at the bottom of the Slab/Fuse tab in `main_window_layout_helper.py`.

#### D2 — Group automated QA tools in Tools menu [x]

*Done 2026-05-18.* `main_window_menu_builder.py`: the two ACR actions previously added flat to Tools menu are now nested under an **Automated QA ▶** submenu with `setToolTipsVisible(True)` and individual tooltips. Name kept generic so future non-ACR QA tools slot in without a rename.

#### D3 — Toast notification severity icons [x]

*Done 2026-05-19.* `main_window.py` `show_toast_message()`: added `severity` kwarg (`"info"` / `"warning"` / `"error"` / `"success"`). Each severity maps to a border color (`#4285da` / `#d68910` / `#c0392b` / `#27ae60`) and a Unicode icon prefix (ℹ / ⚠ / ✕ / ✓). Toast CSS uses `border-left: 4px solid {color}` and `border-radius: 0 6px 6px 0` (flat left, rounded right). All existing callers default to `"info"`.

#### D4 — Drag-and-drop target indicator [x]

*Done 2026-05-19.* `image_viewer_input.py`: `dragEnterEvent` sets `self._drag_active = True` and invalidates the viewport; `dragLeaveEvent` and `dropEvent` clear it. `drawForeground` override paints a dashed 3px accent-colored border (4px inset from viewport edges) using `painter.resetTransform()` to stay in viewport coordinates regardless of zoom/pan. `_drag_active = False` initialized in `image_viewer.py`.

#### D9 — QGroupBox theming [x]

*Done 2026-05-15.* Added `QGroupBox` and `QGroupBox::title` rules to both `dark.qss` and `light.qss`. Dark: `#555555` border / `#aaaaaa` title. Light: `#c0c0c0` border / `#606060` title. 4 px border-radius both themes.

---

## Phase 3 — Toolbar Button Definition

Before sourcing any icons, decide exactly which buttons belong on the toolbar. Icons are expensive to source and match well — do this once against the final list.

### E1 — Finalize toolbar button set [x]

*Done 2026-05-20.*
- Open → split QToolButton (click = Open File, dropdown = Open File / Open Folder).
- All 12 mouse-mode tools kept (Arrow, Text, Crosshair, Magnifier, Select, etc.) — removable later via planned customisable-toolbar feature.
- Added Export, MPR, Study Index buttons (all newly connected to existing signals).
- Removed Font Size +/−, Scroll Wheel combo — commented out in builder, preserved for customisable-toolbar.
- Font Color and Use Rescaled Values already moved off toolbar (B2).
- Final set: Open (split), 12 mouse-mode tools, Privacy, Reset View, Reset All, Overlay Toggle, Cine Play/Pause, MPR, Export, Study Index, Series Navigator, Prev/Next Series.

---

## Phase 4 — Icon Research & Selection

### F1 — Evaluate icon collections [x]

*Done 2026-05-20. Tabler Icons (MIT, outline style) selected as primary set. Material Symbols, Phosphor, IBM Carbon samples retained in `resources/icons/samples/` for future user-selectable icon set feature (F5).*

All collections below are free for commercial use (Apache 2.0 or MIT). Each has a distinct visual style; offering users 2–3 style choices is a goal.

#### Collection A — Material Symbols (Google)
- **License:** Apache 2.0
- **Count:** 2,500+ icons
- **Styles:** Outlined, Rounded, Sharp (each available as filled or not; weight and grade are variable)
- **Source:** https://fonts.google.com/icons · https://github.com/google/material-design-icons
- **Download:** Individual SVGs available per icon; or the full repo (large). The `material-symbols` npm package has well-organized per-icon SVG exports.
- **Strengths:** Enormous set, well-maintained, excellent coverage of tool/measurement/view concepts, variable stroke weight is useful for light vs dark themes.
- **Best style for MPDV:** Outlined (weight 300–400) for dark theme; Outlined (weight 400) for light theme.

#### Collection B — Phosphor Icons
- **License:** MIT
- **Count:** 6,000+ icons
- **Styles:** Thin, Light, Regular, Bold, Fill, Duotone
- **Source:** https://phosphoricons.com · https://github.com/phosphor-icons/core
- **Download:** Full SVG set available as a zip from GitHub releases or per-icon via the website.
- **Strengths:** Largest freely available set by count. Very strong measurement, geometry, and science icons. "Regular" style is clean and professional. Duotone looks polished on dark UIs but may be complex to implement (two-layer SVG).
- **Best style for MPDV:** Regular or Light for the main icon set.

#### Collection C — Tabler Icons
- **License:** MIT
- **Count:** 5,500+ icons
- **Styles:** Outline and Filled
- **Source:** https://tabler.io/icons · https://github.com/tabler/tabler-icons
- **Download:** Full SVG zip available from GitHub releases.
- **Strengths:** Very clean, consistent stroke width, sharp and technical-feeling. Good for a professional tool. Consistent 24×24 viewbox.
- **Best style for MPDV:** Outline (the filled set is a bonus for active states).

#### Collection D — IBM Carbon Icons (bonus / supplementary)
- **License:** Apache 2.0
- **Count:** 1,000+ icons
- **Source:** https://carbondesignsystem.com/elements/icons/library · https://github.com/carbon-design-system/carbon/tree/main/packages/icons
- **Strengths:** Specifically designed for data-dense enterprise UIs; strong data, medical, and tools coverage. Lower total count but high semantic relevance. Good fallback for any gaps in A/B/C.

### F2 — Create candidate folder structure [x]

*Done 2026-05-20. `resources/icons/toolbar/` created with 28 named SVGs (one per toolbar button). Ruler alternatives in `resources/icons/samples/tabler/` for comparison.*

Create `resources/icons/candidates/` with one subfolder per toolbar button. Naming must match the final button list from E1.

Proposed structure (adjust to match E1 decisions):

```
resources/icons/candidates/
  open/
  export/
  privacy-on/
  privacy-off/
  pan/
  window-level/
  zoom/
  reset-view/
  measure-distance/
  measure-angle/
  roi-ellipse/
  roi-rectangle/
  text-annotation/
  overlay-toggle/
  mpr/
  cine-play/
  study-index/
  screenshot/
```

Each subfolder gets candidates from at least 2 collections. Use a naming convention like `material-outlined-<icon-name>.svg`, `phosphor-regular-<icon-name>.svg`, `tabler-<icon-name>.svg` so the source is clear at a glance.

For buttons with an active/toggled state (Privacy ON/OFF, Overlay on/off, Cine play/stop), include both variants.

### F3 — Download and populate candidates [x]

*Done 2026-05-20. All 28 toolbar icons downloaded from Tabler outline set. Ruler variant selected: `ruler-measure` (user-confirmed over ruler-2, line, dimensions, separator alternatives).*

For each button, find 2–3 candidate icons per collection and drop the SVGs into the subfolder. Don't over-curate at this stage — 2–3 options per button per collection is fine. The review step (F4) makes the final call.

Useful search terms per button:

| Button | Search terms |
|---|---|
| Open | folder_open, folder, open_in_new |
| Export | save, download, export |
| Privacy ON | visibility_off, hide, eye_slash |
| Privacy OFF | visibility, eye |
| Pan | pan_tool, hand, move |
| Window / Level | contrast, brightness, tune, exposure |
| Zoom | zoom_in, magnify, search_plus |
| Reset View | fit_screen, fullscreen_exit, aspect_ratio, center_focus |
| Measure Distance | straighten, ruler, horizontal_rule |
| Measure Angle | architecture, angle, triangle |
| Ellipse ROI | radio_button_unchecked, circle, ellipse |
| Rectangle ROI | crop_square, rectangle, square |
| Text Annotation | text_fields, title, edit_note |
| Overlay Toggle | layers, overlay, stack |
| MPR | view_in_ar, view_comfy, grid_view, 3d_rotation |
| Cine Play | play_circle, play_arrow, slideshow |
| Study Index | table_view, list, database |
| Screenshot | photo_camera, camera, screenshot |

### F4 — Review candidates and select [x]

*Done 2026-05-20. All icon assignments confirmed (Tabler outline). See `resources/icons/toolbar/` for final names. Privacy: eye / eye-off. Cine: player-play / player-pause. Measure: ruler-measure.*

For each button, pick:
- A **primary icon** (used in the default icon set)
- An **alternate icon** from a different collection style (used in the alternate icon set, if offering choice to users — see F5)

Document selections in `DESIGN.md § 4.2`, replacing the placeholder entries.

Consider laying out a simple HTML or markdown grid with embedded SVG previews to compare candidates side by side. This is much faster than opening each file individually.

### F5 — Decide on user-selectable icon sets [ ]

**Goal:** offer users 2 icon style choices from Settings (e.g. "Outlined" and "Filled", or "Material" and "Phosphor").

Implementation approach:
- Store icons in `resources/icons/<set-name>/` (e.g. `resources/icons/outlined/`, `resources/icons/filled/`)
- On startup, load the set from user preferences; reload on setting change (may require restart or can hot-swap via `QIcon` re-fetch)
- Settings key: `icon_set` (string, default `"outlined"`)
- Expose in Settings dialog as a combobox: "Icon style: Outlined | Filled"

This is optional — if the candidate review in F4 finds one style that clearly wins, offering choice adds complexity for little gain. Decide after F4.

---

## Phase 5 — Icon Implementation

### G1 — Set up icon resource system [x]

*Done 2026-05-20. Direct file paths from `resources/icons/toolbar/`. `_icon(name, color)` in `main_window_toolbar_builder.py` loads SVG bytes, replaces `currentColor` with theme-appropriate hex, renders via `QSvgRenderer` to 48×48 px at DPR 2.0 for HiDPI sharpness.*

- Choose delivery mechanism: bundled SVGs loaded at runtime via `QIcon(QPixmap(":/icons/..."))` from a `.qrc` file, or direct file path from `resources/icons/`.
- `.qrc` + `pyrcc6` (or `pyside6-rcc`) compiles icons into the binary — simpler distribution but requires a rebuild step when icons change.
- Direct file path from `resources/` is easier to iterate and hot-swap; fine for now since the app is not yet widely distributed.
- Recommendation: direct file paths for now; migrate to `.qrc` before first packaged release.

### G2 — Apply icons to toolbar actions [x]

*Done 2026-05-20. All 27 toolbar actions/buttons have Tabler SVG icons. Toolbar uses `ToolButtonIconOnly`. Theme-aware: icons rendered in `#e0e0e0` (dark) or `#2c2c2c` (light). `refresh_toolbar_icon_theme(color)` closure stored on `main_window`; called from `_apply_theme()` on every theme switch.*

- After G1 and F4, for each toolbar button replace text-only with `QAction.setIcon(QIcon(...))`.
- Use `setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)` or `ToolButtonTextBesideIcon` (keep text for accessibility until icon recognition is established).
- Set a full text tooltip: `setToolTip("<action name>  (<shortcut>)")`.

### G3 — Apply icons to non-toolbar uses [x]

*Done 2026-05-20.*
- **Menu icons**: `Open File(s)…`, `Open Folder…`, `Export…` in File menu; `Undo`, `Redo` in Edit menu — all wired via `_mi()` helper in `main_window_menu_builder.py`. New Tabler icons `arrow-back-up.svg` and `arrow-forward-up.svg` added for Undo/Redo.
- **Privacy**: menu item now uses the shared `privacy_action` (same object as toolbar button); icon managed by `_update_privacy_action()`.
- **Privacy action refactor**: `MainWindow.__init__` now creates a single `privacy_action` (`checked=True` = privacy ON) connected to `_on_privacy_toggled(checked)`. Menu and toolbar both reference this action — no more state drift between them. `_update_privacy_action()` replaces the old `_update_privacy_mode_button()` (backward-compat alias kept). `view_actions.on_privacy_view_toggled` syncs the shared action check state to handle the context-menu toggle path.
- **Menu icon theme refresh**: `_menu_icon_registry` on `main_window` is populated by menu builder; toolbar builder's `_refresh_icons` closure iterates it on theme change.
- Toast severity icons (info/warning/error/success) already done via Unicode prefix in `show_toast_message` (D3 path). Dialog buttons intentionally left icon-free.

### G4 — Active / toggled state icons [x]

*Done 2026-05-20.*
- **Privacy**: `_update_privacy_action()` swaps icon between `privacy-off.svg` (eye) and `privacy-on.svg` (eye-off) on every state change. Toolbar button background turns red (`#c0392b`) when privacy is OFF (data exposed). Tooltip also updates to state description.
- **Cine**: `on_cine_playback_state_changed()` in `CineAppFacade` swaps icon between `cine-play.svg` and `cine-pause.svg` and updates tooltip. Uses `pause_playback()` (not stop).
- **Overlay**: cycles 3 states (detailed / minimal / hidden) — not a binary toggle, no icon swap needed.
- Theme refresh (`_refresh_icons`) re-renders all toggled-state icons in the new colour then re-applies the active state via `_update_privacy_action()`.

### G5 — Verify toolbar fits single row [ ]

After icons are applied, confirm toolbar fits in one row at 1280 px width. Adjust button set or icon size if needed (recheck from E1 decisions).

---

## Verification Gates

1. **A1–A4 done** before any Phase 2 work begins.
2. **Phase 2 complete** before Phase 3 begins — toolbar button set must be stable before icons are sourced.
3. **E1 finalized** (toolbar button list) before F2 folder structure is created.
4. **F4 complete** (icon selections documented in DESIGN.md) before G2 begins.
5. All P0 items (B2–B8, G2) resolved and tested in both dark and light themes.
6. Toolbar fits single row at 1280 px (screenshot evidence).
7. No duplicate shortcut bindings in `DESIGN.md § 6`.
8. SR Dose table renders without truncation at default dialog width (screenshot evidence).
9. QSS lint pass: no remaining literal color values outside the token definitions.

---

## File References (key implementation files)

Locate these via `grep` or the codebase directly:

- Main QSS theme files — `resources/themes/dark.qss` / `resources/themes/light.qss`
- Accent colour presets — `src/gui/accent_presets.py`
- Theme loader — `src/gui/main_window_theme.py` (`get_theme_stylesheet`)
- Toolbar builder — search for `QToolBar` or `addAction` near `toolbar`
- Menu builder — `main_window_menu_builder.py`
- Context menu — search for `QMenu` + `exec_` in viewer widgets
- Series navigator — search for `SeriesNavigator` or `navigator`
- Toast — search for `toast` or `notification`
- Splitter — search for `QSplitter`
- Overlay settings — search for `OverlaySettings` or `overlay_settings`
- ACR dialogs — `src/gui/dialogs/acr_ct_qa_dialog.py`, `src/gui/dialogs/acr_mri_qa_dialog.py`
- Icon resources (once created) — `resources/icons/`

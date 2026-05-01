# UX Assessment — Overall Presentation & Experience
**Date:** 2026-04-30 (updated with screenshots + menu deep-dive 2026-05-01)  
**Scope:** Overall structural pass + full menu bar deep-dive. Right-click context menus reserved for follow-up.  
**Method:** Static code analysis (QSS stylesheets, main window layout, toolbar/menu/panel layout builders, existing UX planning docs) + visual review of 8 live screenshots.  
**Screenshots:** `resources/screenshots-ignored/Screenshot 2026-05-01 00*.png`  
**Follow-up passes planned:** (1) Right-click context menu deep-dive, (2) DESIGN.md — design system alignment, token system, icon adoption plan.

---

## 1. Application Architecture Overview

DICOMViewerV3 is a **PySide6 (Qt 6) desktop application** for medical DICOM image viewing. The main window follows a classic three-panel layout common in professional imaging software:

```
┌─────────────────────────────────────────────────────────────┐
│  Menu Bar  (File / Edit / View / Tools / Help)              │
├─────────────────────────────────────────────────────────────┤
│  Toolbar  (text-only buttons — ~18 actions + controls)      │
├──────────────┬──────────────────────────┬───────────────────┤
│  Left Panel  │    Center Panel          │  Right Panel      │
│  (Cine +     │    (Multi-window image   │  (Tabbed:         │
│   Metadata)  │     viewer — 1×1 to 2×2) │   W/L/ROI,        │
│              │                          │   Combine/Fuse)   │
├──────────────┴──────────────────────────┴───────────────────┤
│  Series Navigator bar (toggleable, bottom)                  │
├─────────────────────────────────────────────────────────────┤
│  Status Bar  (file info | zoom/preset | pixel coords)       │
└─────────────────────────────────────────────────────────────┘
```

All three side panels are separated by a `QSplitter` and are individually scrollable. Widths are persisted across sessions via `ConfigManager`. The layout is drag-and-drop capable for file loading and supports multi-window grid arrangements (1×1, 1×2, 2×1, 2×2).

---

## 2. Visual Design

### 2.1 Theming

The app ships two hand-crafted QSS themes. Both are functional and internally consistent, sharing the same structural rules with different palettes.

| Token              | Dark                   | Light                  |
|--------------------|------------------------|------------------------|
| Window background  | `#2b2b2b`              | `#f0f0f0`              |
| Panel background   | `#1e1e1e` / `#1b1b1b`  | `#ffffff` / `#d0d0d0`  |
| Toolbar background | `#3a3a3a`              | `#e0e0e0`              |
| Primary text       | `#ffffff`              | `#000000`              |
| Muted text         | `#7f7f7f`              | `#a0a0a0`              |
| Accent / active    | `#4285da`              | `#4285da`              |
| Border             | `#555555`              | `#c0c0c0`              |

**Strengths:**
- The dark theme is well-calibrated for clinical use — dark surrounds reduce eye fatigue during long reading sessions and are standard in radiology software (OsiriX, Horos, Weasis).
- The accent color (`#4285da`, a Google-blue adjacent hue) is applied consistently for pressed, checked, selected, and focus states across all widget types.
- The series navigator uses a slightly darker background (`#1b1b1b` dark / `#d0d0d0` light) to visually separate it from the main panels — a good differentiation strategy.

**Weaknesses / opportunities:**
- **No semantic color roles.** There is no error color, warning color, or success color defined in the theme. Toast messages are always white-on-black regardless of severity. A proper color role system (like M3's error/warning/tertiary containers) would allow the app to communicate state visually.
- **Single accent color.** Everything interactive uses the same `#4285da`. There is no way to distinguish primary actions from secondary ones, or to indicate a destructive action (e.g., "Delete ROI") vs. a neutral one.
- **Hardcoded pixel values throughout.** The QSS uses raw hex codes rather than CSS variables. If you ever want to ship a third theme or a high-contrast accessibility theme, every value has to be updated manually. Qt 6.6+ supports color tokens in stylesheets to some degree, but a token abstraction at the Python level (substituted at theme load time) would be the pragmatic choice.
- **Light tooltip** (`#ffffdc` in light theme) is a legacy Windows yellow. It looks dated and inconsistent with the otherwise clean palette.
- **`QGroupBox` not explicitly themed.** Group boxes will fall back to the OS default, which may look inconsistent on non-Windows platforms. *[Needs screenshot to verify.]*

### 2.2 Typography

The app ships and loads three font families:
- **IBM Plex Sans** — primary (multiple weights)
- **DejaVu Sans** — fallback
- **Liberation Sans** — secondary fallback

IBM Plex Sans is an excellent choice: it is open-source, designed for technical/data-dense UIs (originally for IBM's brand but widely adopted), highly legible at small sizes, and has strong Latin and numerals. It aligns well with the app's professional medical context.

**Weaknesses / opportunities:**
- **No explicit type scale defined.** The QSS doesn't define font sizes for structural roles (heading, body, label, caption). Individual widgets use whatever Qt defaults, except the toast which hardcodes `font-size: 14px`. This results in an inconsistent hierarchy — some labels may be 9pt, some 11pt, depending on the OS default. A small defined type scale (e.g., 11px body, 12px label, 14px subheading, 18px heading) would unify the UI.
- **Font loading not verified in QSS.** The QSS files don't set `font-family` globally — the font loading must happen via `QFontDatabase` in Python code. Worth verifying that IBM Plex Sans is actually active at runtime and not silently falling back to the OS default. *[Needs verification.]*

### 2.3 Iconography

**This is the most significant visual design gap.** The toolbar contains ~18 actions, all rendered as **text-only `QToolButton`s** — no icons whatsoever. This is atypical for professional desktop software and creates several problems:

- The toolbar is very wide (potentially overflowing on smaller screens).
- Tool identity relies entirely on reading text labels, which is slower than icon recognition.
- The app has no visual vocabulary — there is no iconographic language that carries through to menus, tooltips, or documentation.
- Clinical workflow requires rapid tool switching; text labels are not scannable at speed.

The only images in `resources/` are the application icon (PNG/ICO/ICNS, a custom logo) and checkbox checkmarks (two PNGs). There are no toolbar or menu icons.

**The application icon** itself (`dvv6ldvv6ldvv6ld_edit-removebg-preview.png`) has a non-descriptive, AI-generated-looking filename. It should be renamed to something clear (e.g., `app_icon.png`) and its visual quality should be assessed for sharpness at small sizes (16×16, 32×32 taskbar use). *[Needs screenshot/visual review.]*

---

## 3. Layout & Structural UX

### 3.1 Three-Panel Splitter Layout

The left–center–right three-panel layout is a standard and appropriate choice for this category of software. The constraints are well-chosen:
- Minimum panel width: `200px` — prevents accidental collapse to nothing
- Maximum panel width: `600px` — prevents the side panels from crowding the image
- Panel widths persisted via config — good, users customize their workspace once

**Weaknesses:**
- **2px splitter handles.** The `QSplitter::handle` is `width: 2px / height: 2px`. This is extremely thin and hard to grab precisely, especially on high-DPI displays where it may render as 1 logical pixel. Industry standard is 4–6px, often with a visual drag indicator (dots or lines). *[Needs testing on HiDPI.]*
- **No visual affordance for the splitter.** There are no grip dots, chevrons, or hover highlight on the splitter handles. A user unfamiliar with Qt splitters may not realize the panels are resizable.
- **No "collapse panel" button.** Panels can be collapsed via View menu actions, but there is no inline collapse arrow on the panel border itself — a common affordance in IDEs (VS Code, JetBrains) and imaging software.

### 3.2 Center Panel — Multi-Window Layout

The center panel supports grid arrangements (1×1, 1×2, 2×1, 2×2), a slice/frame slider overlay, and a `WindowSlotMapWidget` (80×80px mini-map of the current layout). This is a well-designed multi-window system.

**Positive notes:**
- Drag-and-drop file loading is supported.
- The window slot map is a clever navigator for quickly understanding which pane is active.
- Toast notifications with fade animations provide non-intrusive feedback.
- The slice slider toggles in/out to avoid cluttering the image area.

**Weaknesses:**
- The `WindowSlotMapWidget` is (per the UX plan `UX_IMPROVEMENTS_BATCH1_PLAN.md`) not yet clickable to switch focus — this is a planned improvement but a notable missing affordance.
- In 1×1 mode with multi-window switching, the layout control is menu-only; a floating or edge-pinned layout switcher (like the one in Horos or RadiAnt) would be more ergonomic.

### 3.3 Left Panel — Metadata + Cine Controls

The left panel stacks cine controls at the top and the metadata/DICOM tag panel below. This vertical ordering is reasonable — cine is a transient control (you enable playback, then stop) while metadata is consulted for longer periods.

**Weaknesses:**
- Left and right panels are always visible at a fixed width by default (250px each). On smaller screens (1366×768 laptop), this leaves only 666px for the image viewport — which may be too narrow for some DICOM series. The series navigator further reduces vertical space. A "compact mode" or automatic panel collapsing on small screens would help.
- The metadata panel's tab label ("metadata") is not surfaced in the UX documents reviewed; it is unclear whether there are sub-tabs within the left panel. *[Needs screenshot.]*

### 3.4 Right Panel — Tabbed Controls

The right panel uses two tabs: **"Window/Zoom/ROI"** and **"Combine/Fuse"**.

**Weaknesses:**
- Tab label "Window/Zoom/ROI" is three concepts in one and is quite long. Consider "Adjust" (Window/Level + Zoom) and "Overlay" or "Regions" (ROI tools), each as separate tabs, if the panel ever expands.
- "Combine/Fuse" is technically accurate but not immediately intuitive to a clinical user unfamiliar with the features. Consider "Fusion" or "MPR/Fusion" as a clearer label.
- The tab widget (`right_panel_tabs`) has no icon in the tab headers — adding small icons would help disambiguate the tabs visually, especially when the panel is narrow.

### 3.5 Series Navigator

The series navigator is a collapsible bar at the bottom of the window, containing thumbnail series and the `WindowSlotMapWidget`. It is toggled from the toolbar and persists its visibility state.

**Positive notes:**
- The slightly different background (`#1b1b1b` dark) correctly signals that this is a different functional area.
- Study sections and thumbnails are visually grouped — a good hierarchical structure.

**Weaknesses / unknowns:**
- Thumbnail dimensions and visual quality cannot be assessed without live screenshots. *[Needs screenshot.]*
- It is unclear from code review whether thumbnails show series description, instance count, and modality labels. *[Needs screenshot.]*

---

## 4. Toolbar Assessment

### 4.1 Current Toolbar Contents (in order)

| Group | Actions |
|---|---|
| Mouse modes | Ellipse ROI, Rectangle ROI, Measure, Angle, Text, Arrow, Crosshair, Zoom, Magnifier, Pan, Select, Window/Level ROI |
| Separator | — |
| Privacy | Privacy is OFF/ON |
| Separator | — |
| View | Reset View, Reset All Views |
| Separator | — |
| Navigator | Show Series Navigator |
| Separator | — |
| Series nav | Prev Series, Next Series |
| Separator | — |
| Overlay font | Font Size: [label], −, + |
| Separator | — |
| Overlay | Font Color |
| Separator | — |
| Display | Use Rescaled Values |
| Spacer | (expanding) |
| Scroll wheel | Scroll Wheel: [label], [Slice/Zoom combobox] |

**12 mouse-mode tools + 7 utility actions + 3 controls = 22 interactive elements** in a single toolbar row. This is exceptionally dense.

### 4.2 Issues

1. **No icons.** All 22 elements are text only. This is the single highest-priority visual improvement. Every professional Qt imaging application (Horos, OsiriX, 3D Slicer, Weasis) uses icons for toolbar tools.

2. **"Privacy is OFF" / "Privacy is ON" toggle labeling is confusing.** A toggle button that says "Privacy is OFF" when privacy is off (and presumably changes to "Privacy is ON" when on) uses the label to describe current state, not the action. This is a classic toggle anti-pattern. Better: icon with "Privacy" label, checked = enabled, unchecked = disabled — or separate on/off labels like a lock icon.

3. **"Use Rescaled Values" is non-checkable.** The action alternates text but is not checkable, meaning there is no visual indicator of the current state other than reading the text. This is confusing. It should be a checkable `QAction` with clear checked/unchecked visual differentiation (or a labeled toggle button like "Raw | Rescaled").

4. **Font Size controls (−, +, "Font Size:" label) are very small targets.** The `−` and `+` actions are single-character buttons with no minimum size set. On high-DPI or with system scaling, these may be nearly impossible to click.

5. **Scroll wheel combobox** at the right end is the only dropdown in the toolbar, making it visually inconsistent with everything else. A pair of small toggle buttons ("Slice" / "Zoom") would be more consistent.

6. **The toolbar is not movable** (`setMovable(False)`) — which is appropriate given its complexity, but means the user has no flexibility.

7. **No keyboard shortcut visible in toolbar tooltips.** Only a few actions set `setStatusTip` or `setToolTip` that mention shortcut keys. Most tool buttons have no tooltip set at all — the user must discover shortcuts from the menu or documentation.

### 4.3 Toolbar Recommendations (Priority Order)

| Priority | Recommendation |
|---|---|
| P0 | Add icons to all 12 mouse-mode tool buttons (see Icon Resources section below) |
| P0 | Fix Privacy toggle labeling (icon + descriptive state) |
| P1 | Make "Use Rescaled Values" a proper checkable action with visual state |
| P1 | Add tooltips with keyboard shortcuts to every toolbar action |
| P1 | Group mouse-mode tools visually (e.g., draw tools / navigation tools / view tools) |
| P2 | Replace Font Color / Font Size controls with a single compact settings button |
| P2 | Implement toolbar section customization (already planned in UX_IMPROVEMENTS_BATCH1_PLAN.md) |
| P3 | Consider splitting the toolbar into two rows or a side panel for very high tool counts |

---

## 5. Status Bar

The status bar is split into three equal-width sections:
- **Left:** File/study information ("Ready" on launch)
- **Center:** Zoom level and window/level preset
- **Right:** Pixel values and cursor coordinates

This is a sensible information architecture. Three sections match the spatial awareness needs of a DICOM viewer (what am I looking at? how am I viewing it? what am I pointing at?).

**Weaknesses:**
- Equal stretch (1:1:1) may not be ideal — pixel coordinate strings can be long (e.g., `HU: -254  (512, 384)`) while the center section may often be short. Consider (1:2:2) or left-right compressed / center-expanded proportions.
- No iconographic differentiation between the three sections. A small icon prefix (file icon, zoom icon, cursor icon) would make the sections scannable at a glance.
- "Ready" on launch is generic. A more welcoming initial state ("Drop a DICOM file or folder to open" or "File → Open to get started") would improve onboarding.

---

## 6. Interaction Design

### 6.1 Mouse Interaction Model

The app uses an explicit **tool mode** paradigm (Pan is default; click a toolbar button to activate Ellipse ROI, Measure, etc.). This is standard for medical imaging software. Right-click opens a context menu (or, if dragged, adjusts window/level). Scroll wheel changes slice or zoom depending on the mode combo.

**Strengths:** Explicit modes are appropriate for clinical workflows — accidentally drawing an ROI is worse than needing to click a tool button.

**Weaknesses:**
- Right-click drag for window/level is discoverable only if the user reads documentation or right-click context menus carefully. The UX plan notes this as a discoverability issue.
- No visual cursor change when entering different modes. A crosshair cursor in Zoom mode, a pencil in draw modes, etc., would make the active mode self-evident.

### 6.2 Drag and Drop

Files and folders can be dropped onto the main window. This is a great power-user feature that reduces friction for quick file opening.

**Weakness:** There is no visual drop target indicator (a highlight zone, a dashed border, or a prompt label). When the window is occupied by an image, the user has no visible confirmation that dropping is possible. *[Needs screenshot to verify.]*

### 6.3 Keyboard Shortcuts

Several shortcuts are set: `V`/`Shift+V` (reset view), `Shift+A` (reset all views), `T` (text annotation), `A` (arrow annotation), `Shift+M` (angle measure), spacebar (toggle overlay). This is a modest but reasonable set.

**Weakness:** The shortcut set is sparse and not consistently surfaced. `T` for text conflicts with some systems' screen reader shortcuts. A keyboard shortcut reference card or a configurable shortcuts dialog would be a significant UX improvement for power users.

### 6.4 Toast Notifications

Toast messages appear with a semi-transparent dark background, centered-bottom, with a fade-out animation (300ms). This is well-implemented — unobtrusive, readable, and auto-dismissing.

**Weakness:** All toasts use the same visual style regardless of severity (informational vs. warning vs. error). There is no icon in the toast. Consider adding an icon prefix and a color-coded left border (blue = info, yellow = warning, red = error) to match the planned semantic color system.

---

## 7. Accessibility

No dedicated accessibility work is visible in the codebase or planning documents.

**Known gaps:**
- No `setAccessibleName` or `setAccessibleDescription` calls found (would need a thorough grep to confirm). These are required for screen readers (Windows Narrator, NVDA).
- No high-contrast theme. The existing dark theme is reasonably high-contrast, but an explicit WCAG AA/AAA compliant theme with verified contrast ratios does not exist.
- No keyboard-only navigation audit. Can all controls be reached without a mouse? Qt tab order is automatic but should be verified, especially for the multi-panel splitter layout.
- Minimum touch target sizes are not enforced. The `−` and `+` font-size buttons are likely below 24×24px. WCAG 2.5.5 recommends 44×44px; M3 recommends 48dp.
- The 2px splitter handle is inaccessible to users with fine motor impairments.

---

## 8. Design System Comparison (Preview)

A full DESIGN.md comparison will be done in a future pass. This section provides initial directional observations.

### Material Design 3 (M3) — https://m3.material.io/

| M3 Principle | Current State |
|---|---|
| **Color roles** (primary, secondary, tertiary, error, surface, outline) | Only one color role exists (accent `#4285da`). No error/warning/success colors. |
| **Elevation & surface tinting** | No elevation model. All surfaces are flat. M3 uses surface tints at different levels to imply depth. |
| **Icon buttons** (filled, filled tonal, outlined, standard) | No icons. Text-only toolbar. |
| **Typography scale** (Display, Headline, Title, Body, Label) | No defined type scale. IBM Plex Sans is the right font; the scale is missing. |
| **State layers** (hover, pressed, focused, dragged, disabled) | Present for key states but inconsistent (hover on some buttons, not others; focus ring not always themed). |
| **48dp minimum touch targets** | Not enforced. Many toolbar buttons are likely smaller. |
| **Motion** | Toast fade is good. No other transitions/animations visible. |

M3 is a web-native system and adapts imperfectly to Qt desktop. However, its color role system and type scale are valuable abstractions worth borrowing.

### IBM Carbon Design System — https://carbondesignsystem.com/

Carbon is arguably the best reference for this application category — it was designed for technical/data-dense enterprise UIs and includes components specifically for data visualization, dense tables, and tool panels.

| Carbon Principle | Current State |
|---|---|
| **2px grid, 8px base unit** | Layout appears ad-hoc. Spacing values not standardized. |
| **Icon library** (Carbon Icons — 1000+) | Not used. Carbon's icon set includes medical, data, tools categories. |
| **Themes** (White, G10, G90, G100) | Our dark/light roughly maps to G100/White. Carbon's token system is more sophisticated. |
| **Dense component sizes** (sm/md/lg) | No size variants. All controls appear at a single size. |
| **Notification components** (inline, toast, banner) | Toast exists; no inline or banner notifications. |
| **Tabs** (contained, line) | Right panel uses basic Qt tabs; not styled. |

Carbon's icon set (`@carbon/icons`) is free (Apache 2.0) and would solve the toolbar icon problem immediately. It includes: ruler, measurement, magnifier, pan, zoom-in, zoom-out, cursor, color-picker, text, arrows, and more.

### Apple Human Interface Guidelines — https://developer.apple.com/design/

Less directly applicable (macOS-specific), but relevant principles:

| HIG Principle | Current State |
|---|---|
| **SF Symbols** | N/A (not on macOS-exclusive codebase) |
| **Toolbar conventions** | Apple strongly recommends icon+label or icon-only toolbars. Text-only toolbars are not a HIG pattern. |
| **Destructive action confirmation** | Not assessed — delete ROI, close study etc. should be confirmed. |
| **Native controls where possible** | Qt on macOS may not fully use native controls; worth auditing on macOS specifically. |

---

## 9. Icon Resources

For implementing toolbar icons, the following free open-source icon libraries are recommended:

| Library | License | Notes |
|---|---|---|
| **Carbon Icons** (`@carbon/icons`) | Apache 2.0 | 1000+ icons, medical/tools categories, SVG, designed for dense UIs. Best match for this app's context. |
| **Material Symbols** (Google) | Apache 2.0 | 2500+ icons, all weights/fills, SVG. The "outlined" style works well in dark UIs. |
| **Feather Icons** | MIT | 280 minimalist SVG icons. Clean but limited for medical/measurement tools. |
| **Phosphor Icons** | MIT | 1000+ icons, 6 weight styles, excellent SVG. |
| **Lucide** (Feather fork) | ISC | 1400+ icons, active development. |
| **Font Awesome 6 Free** | CC BY 4.0 (icons) | Very large set but mixed visual quality; better for web. |

**Recommendation:** Start with **Carbon Icons** (best semantic coverage for tools, measurement, medical) supplemented by **Material Symbols** for any gaps. Both work as SVG files loadable via `QIcon` / `QPixmap` from file in Qt.

**Qt Icon workflow:** Load SVGs via `QIcon(QPixmap("path/to/icon.svg"))` or bundle them in Qt resources (`.qrc`). For multi-resolution support on HiDPI, SVGs scale perfectly. Alternatively, use `QSvgRenderer` for custom rendering.

---

## 10. Visual Findings from Screenshots

The following observations come from the 8 live screenshots and supersede or confirm earlier code-only analysis.

### 10.1 Empty / Cold-Start State (`002101`)

- **2×2 grid layout visible on launch** — the top-left pane has a blue border indicating focus. The four black panels are clean but stark. There is no empty-state guidance (no "Drop a DICOM file here" message, no drag-target overlay).
- **Toolbar confirmed text-only.** All buttons render as plain text QToolButtons. The density is significant: the full width of the window is consumed by toolbar labels.
- **"Privacy is OFF" renders in bright red/orange** — this is intentional and correct. The red highlight is a deliberate safety signal: when PHI/patient data is visible (privacy OFF), the toolbar draws maximum attention to that state so the user cannot miss it. When privacy mode is active, the button returns to the standard blue styling. This is the right pattern for a compliance-sensitive medical application. The only suggestion is to make the label slightly more explicit: "Privacy OFF — PHI Visible" would remove any ambiguity about what the red state means.
- **"Pan" is highlighted in blue** (the active mode) — the checked-state blue is recognizable and correct.
- **Status bar shows "Ready"** with nothing else — confirms the cold-start empty-state problem.
- **Right panel is fully populated** even with no file loaded: Window Center, Window Width, Zoom spinboxes, sliders, ROI list, ROI Statistics table, "Delete Selected" / "Delete All" buttons. The Delete buttons appearing when there is nothing to delete adds visual noise. Consider disabling or hiding them until ROIs exist.

### 10.2 Loaded State — Dual Pane with CT + Photo (`002253`)

- **The 1×2 split looks crisp.** The blue focus border on the active pane is clear without being intrusive.
- **Overlay text on the CT image is extremely dense.** Each corner of the image has 4–8 lines of small text. This is standard DICOM viewer behaviour, but the font size at normal viewing distance is at the edge of legibility. The overlay competes with the image content more than it should.
- **Left panel DICOM tag table is very compact.** Three columns (Tag, Name, Value) at a small font render a large number of rows in a narrow panel. Usable, but demanding on the eyes — a slightly larger row height or the option to expand individual cells would help.
- **"Filter tags…" input at the top of the metadata panel** is excellent — one of the most useful affordances for dense metadata.
- **Series navigator bar is visible at the bottom** — thumbnails are small but identifiable. The navigator uses the correct slightly-darker background to visually separate it.

### 10.3 Tools Menu (`002337`) & File Menu (`002423`)

Covered in depth in the menus follow-up pass. Brief notes:
- The **Tools menu is very long** — visible scroll is required on smaller screens. Sub-menus help but the structure is not obviously grouped by workflow.
- The **File menu** is moderately long with good use of separators. "Recent Files" submenu is present.
- Both menus use the styled `QMenu` correctly: dark background, blue hover highlight, separator lines. This is the most polished part of the UI — the menu styling is clean and professional.

### 10.4 Annotation Options Dialog + Histogram (`002551`)

- **Annotation Options dialog** is well-structured: three sections (ROI, Measurement, Text Annotation) with consistent layout. Color swatches are prominent (cyan, yellow, green defaults visible). The dialog is functional but uses no custom styling beyond the base dark theme — it looks like a generic Qt dialog.
- **Checkboxes use the custom PNG checkmark** (white checkmark on dark field) — these look good and are clearly legible.
- **Histogram dialog** is a floating, detachable panel with a line chart. The dual-line display (red + blue channels or different datasets) is clear. "Log Scale" button is present. The dark background on the chart is appropriate. **The chart's axis labels and tick marks appear very small** — needs font size attention.
- Both dialogs are well-positioned (not covering the full image) and can coexist. The floating/non-modal Histogram is a good interaction choice for a tool users reference while adjusting W/L.

### 10.5 ROIs Drawn + Slice Sync Dialog (`002649`)

- **ROI ellipses render in cyan** with bounding-box resize handles (small square dots at corners and edges). The handles are visible but small — borderline on usability for fine adjustments.
- **ROI label text** (mean, std dev, min, max, area, pixel count) is rendered directly on the image in cyan. This is dense but standard for medical imaging. The font is legible at this size.
- **Distance measurement** (yellow line + endpoints) is clearly rendered with handles visible.
- **The Slice Sync dialog** floats on top of the image. Its layout is clean but the dialog's dark styling blends heavily with the image background — a subtle window frame or shadow would help distinguish it.
- **The Histogram remains open** alongside the Slice Sync dialog — demonstrates the app handles multiple floating dialogs correctly.

### 10.6 View Menu Open (`002803`)

Full analysis reserved for the menus pass. Notable: **the View menu is the longest menu in the application** — it requires scrolling on typical laptop displays. It covers image orientation, overlays, layout, sync, privacy, theme, and display options all in one menu. This breadth suggests the View menu may need restructuring (e.g., splitting "Display" from "Layout" from "Sync").

### 10.7 DICOM Tag Viewer Dialog (`002858`)

- **The tag table uses purple/magenta alternating row tinting.** This is a significant style inconsistency — the entire application uses `#4285da` (blue) as its only accent, but the tag viewer dialog introduces purple/violet row colors that appear nowhere else. This should be unified with the blue accent palette.
- **The dialog is well-structured** otherwise: columns for tag number, description, and value; a search/filter input; tabs visible at the top.
- **The tag data is rendered in a monospaced-feeling layout** — appropriate for hex tag codes. The columns are wide enough to read values without truncation in most cases.
- **Privacy mode is visibly active** in this screenshot (toolbar shows the red "Privacy is ON" button) — PHI in the tag viewer is still shown, which may be intentional (tag viewer is an advanced tool), but worth a privacy audit.

---

## 11. Menu Bar Deep-Dive

Source: `src/gui/main_window_menu_builder.py`. Screenshots: `002337` (Tools), `002423` (File), `002803` (View).

### 11.1 Menu Bar Structure Overview

```
File | Edit | View | Tools | Help
```

Five top-level menus is appropriate for this application scope. The ordering follows platform conventions (File first, Help last). The structure is broadly correct but each individual menu has specific issues detailed below.

---

### 11.2 File Menu

**Full current structure:**
```
Open File(s)...                 Ctrl+O
Open Folder...                  Ctrl+Shift+O
Open Study Index…
─────────────────────────────
Recent ▶
Edit Recent List...
─────────────────────────────
Export...                       Ctrl+E
Export Screenshots...
Export Cine As…
Save MPR as DICOM…
─────────────────────────────
Export Customizations...
Import Customizations...
─────────────────────────────
Export Tag Presets...
Import Tag Presets...
─────────────────────────────
Close All                       Ctrl+W
─────────────────────────────
Exit                            Ctrl+Q
```

**Findings:**

| # | Issue | Severity |
|---|---|---|
| F1 | **"Open Study Index…" duplicated in Tools** — same `study_index_search_requested` signal fires from both File and Tools menus. Users won't know which is canonical. | P1 |
| F2 | **"Edit Recent List..."** sits outside the Recent submenu, making it harder to discover. It logically belongs as the last item inside the Recent flyout, or as "Clear / Edit Recent…" at the bottom of Recent. | P2 |
| F3 | **Customizations and Tag Presets are two separate groups** (two pairs of Export/Import) when they could be consolidated into one "Settings Backup" submenu: Export Customizations, Import Customizations, Export Tag Presets, Import Tag Presets. Reduces File menu length by 2 visible items. | P2 |
| F4 | **"Close All" only** — there is no "Close" for a single focused pane. This is not blocking but may surprise users who expect granular close. | P3 |
| F5 | **"Save MPR as DICOM…"** is a save operation mixed into an export group. It is always enabled regardless of whether an MPR view exists, inviting confusion. Should be disabled when no MPR pane is focused. | P2 |

**What's working well:**
- Opening trilogy (File / Folder / Study Index) is well-organized and covers the three access paths.
- Export group (Export..., Export Screenshots, Export Cine) is logically grouped.
- Close/Exit at the bottom with a separator is correct platform convention.

**Proposed restructured File menu:**
```
Open File(s)...                 Ctrl+O
Open Folder...                  Ctrl+Shift+O
Open Study Index…
─────────────────────────────
Recent ▶
  [recent files list]
  ─────────────────
  Edit Recent List...
─────────────────────────────
Export Image...                 Ctrl+E
Export Screenshots...
Export Cine As…
Save MPR as DICOM…              (disabled when no MPR active)
─────────────────────────────
Settings Backup ▶
  Export Customizations...
  Import Customizations...
  ─────────────────
  Export Tag Presets...
  Import Tag Presets...
─────────────────────────────
Close All                       Ctrl+W
─────────────────────────────
Exit                            Ctrl+Q
```

---

### 11.3 Edit Menu

**Full current structure:**
```
Copy                            Ctrl+C
Paste                           Ctrl+V
─────────────────────────────
Undo                            Ctrl+Z
Redo                            Ctrl+Y / Shift+Ctrl+Z
─────────────────────────────
Settings...
```

**Findings:**

| # | Issue | Severity |
|---|---|---|
| E1 | **"Copy" and "Paste" are annotation-only** but are labelled generically. Users pressing Ctrl+C may expect to copy the image or a DICOM value, not an annotation. Labels should be "Copy Annotation" and "Paste Annotation". | P1 |
| E2 | **"Undo" and "Redo" are tag-edit-only** (`undo_tag_edit_action`), not general undo. A user who draws an ROI and presses Ctrl+Z will be confused when nothing undoes. Should be labelled "Undo Tag Edit" / "Redo Tag Edit", or Undo should be generalized to cover all edit operations over time. | P1 |
| E3 | **"Settings…" in Edit** — correct on Windows/Linux (where it mirrors "Preferences" placement conventions), but on macOS Qt should map it to the application menu via `QAction.MenuRole`. Worth verifying this is handled correctly on macOS builds. | P2 |

**What's working well:**
- The menu is appropriately short.
- Standard shortcuts (Ctrl+C, Ctrl+V, Ctrl+Z, Ctrl+Y) are wired to matching standard keys.

---

### 11.4 View Menu

**Full current structure:**
```
Theme ▶
  Light [checkable]
  Dark  [checkable]
─────────────────────────────
Reset View                      V / Shift+V
─────────────────────────────
Orientation ▶
  Flip Horizontal               Alt+H
  Flip Vertical                 Alt+V
  ─────────────────
  Rotate 90° CW                 Alt+R
  Rotate 90° CCW                Shift+Alt+R
  Rotate 180°
  ─────────────────
  Reset Orientation             Shift+Alt+O
Privacy View                    Ctrl+P  [checkable]
Image Smoothing                         [checkable]
Show Scale Markers                      [checkable]
Show Direction Labels                   [checkable]
Scale Markers Color...
Direction Labels Color...
Show In-View Slice/Frame Slider         [checkable]
Show Instances Separately               [checkable, disabled]
─────────────────────────────
Fullscreen                      F11 / Ctrl+F  [checkable]
Show/Hide Left Pane                     [checkable]
Show/Hide Right Pane                    [checkable]
Show/Hide Series Navigator              [checkable]
Show Slice/Frame Count on Navigator Thumbnails  [checkable]
─────────────────────────────
Show Window Assignment Thumbnail        [checkable]
Overlay Tags Configuration...  Ctrl+O   ← ⚠ CONFLICT
Overlay Settings...
Annotation Options...
─────────────────────────────
Layout ▶
  1x1  (1)  [checkable]
  1x2  (2)  [checkable]
  2x1  (3)  [checkable]
  2x2  (4)  [checkable]
─────────────────────────────
Slice Sync ▶
  Enable Slice Sync             [checkable]
  Manage Sync Groups...
Show Slice Location Lines ▶
  Enable/Disable                [checkable]
  Only Show For Same Group      [checkable]
  Show Only For Focused Window  [checkable]
  ─────────────────
  Show Slab Boundaries Instead of Centre  [checkable]
```

**Findings:**

| # | Issue | Severity |
|---|---|---|
| V1 | **Ctrl+O shortcut conflict** — `Open File(s)...` (File menu, `StandardKey.Open`) and `Overlay Tags Configuration...` (View menu, `"Ctrl+O"`) both resolve to Ctrl+O. Qt will likely silently prefer one; the other will be unreachable by keyboard. This is a **bug**. | P0 |
| V2 | **View menu has 25+ items and is the longest menu in the app.** It mixes theme, navigation, image display options, overlay config, window management, layout, and synchronisation — 7 conceptual categories. M3, Carbon, and Apple HIG all recommend splitting menus that exceed ~12 items. | P1 |
| V3 | **Privacy View mixed in with display options** (between Orientation submenu and Image Smoothing) with no separator. Privacy is compliance-critical and deserves its own visual group or could move to a dedicated position near the top. | P1 |
| V4 | **"Show/Hide Left Pane" / "Show/Hide Right Pane"** — the label "Show/Hide" is redundant when the item has a checkmark indicator. Better: "Left Panel" and "Right Panel" (the checkmark state communicates show/hide). | P2 |
| V5 | **"Show Instances Separately" is permanently disabled** but still visible. Grayed-out items with no tooltip or status tip explaining *why* they are disabled create confusion. Either hide it until the feature is activatable, or add a status tip ("Available when a multi-frame series is loaded"). | P2 |
| V6 | **Layout keyboard shortcuts documented in label text** — "1x1  (1)", "1x2  (2)" puts the shortcut hint inside the label string rather than using `setShortcut()`. This means the shortcut doesn't appear right-aligned in standard shortcut position, and the actual key (1, 2, 3, 4) may not be wired. | P2 |
| V7 | **"Scale Markers Color..." and "Direction Labels Color..."** appear inline in the main menu rather than as submenu items of their respective toggles. This adds 2 items to an already long menu. Consider grouping each toggle + its color picker under a flyout, or placing both color pickers in Overlay Settings. | P3 |
| V8 | **"Show Window Assignment Thumbnail", "Overlay Tags Configuration...", "Overlay Settings...", "Annotation Options..."** are grouped together but represent three different concerns (layout widget, overlay data config, overlay appearance, annotation appearance). The grouping is incidental rather than intentional. | P2 |
| V9 | **Slice Sync and Show Slice Location Lines** are multi-pane synchronization features. They fit in View but their placement at the very bottom (below Layout) makes them easy to miss. Advanced sync features might be better surfaced through a dedicated "Sync" or "Multi-Window" menu item. | P3 |

**Proposed View menu restructuring:**

The View menu could be split into focused sub-sections using a cleaner grouping. Below is a suggested restructure that removes nothing but reorders and adds targeted submenus:

```
Theme ▶  (Light, Dark)
─────────────────────────────
Fullscreen                      F11 / Ctrl+F
Layout ▶  (1×1, 1×2, 2×1, 2×2 — with proper setShortcut calls)
─────────────────────────────
Left Panel               [checkable]
Right Panel              [checkable]
Series Navigator         [checkable]
  Show Slice/Frame Count on Thumbnails  [checkable, move inside navigator section]
─────────────────────────────
Reset View                      V / Shift+V
Orientation ▶  (unchanged)
Privacy View                    Ctrl+P  [checkable]
─────────────────────────────
Display Options ▶
  Image Smoothing                [checkable]
  Show Scale Markers             [checkable]
  Scale Markers Color...
  Show Direction Labels          [checkable]
  Direction Labels Color...
  Show In-View Slice/Frame Slider [checkable]
  Show Instances Separately       [checkable]
  Show Window Assignment Thumbnail [checkable]
─────────────────────────────
Overlays ▶
  Overlay Tags Configuration...  (fix shortcut — remove Ctrl+O conflict)
  Overlay Settings...
  Annotation Options...
─────────────────────────────
Synchronisation ▶
  Enable Slice Sync              [checkable]
  Manage Sync Groups...
  ─────────────
  Show Slice Location Lines      [checkable]
  Only Show For Same Group       [checkable]
  Show Only For Focused Window   [checkable]
  Show Slab Boundaries Instead of Centre  [checkable]
```

This reduces the flat item count from 25+ to 10 top-level items by consolidating Display Options, Overlays, and Synchronisation into submenus. Privacy View stays top-level because it is compliance-critical and requires high discoverability.

---

### 11.5 Tools Menu

**Full current structure:**
```
View/Edit DICOM Tags...         Ctrl+T
Export DICOM Tags...            Shift+Ctrl+T
Create MPR View…
Study Index Search…             ← duplicate from File
Structured Report…
About this File...              Ctrl+A  ← ⚠ CONFLICT
─────────────────────────────
Histogram...                    Shift+Ctrl+H
Export ROI Statistics...
─────────────────────────────
ACR CT Phantom (pylinac)...
ACR MRI Phantom (pylinac)...
```

**Findings:**

| # | Issue | Severity |
|---|---|---|
| T1 | **Ctrl+A conflict** — "About this File..." uses Ctrl+A, which is the universal platform shortcut for "Select All". This will break expected text-selection behaviour wherever Ctrl+A might be used. Should be reassigned (e.g. Ctrl+I for "file Info", or no shortcut). | P0 |
| T2 | **"Study Index Search…" duplicated from File menu.** Either pick one canonical location or make the File entry "Open from Study Index…" (an opening workflow) and the Tools entry "Manage Study Index…" (an administration/search workflow) to distinguish the two. | P1 |
| T3 | **"About this File..."** is a metadata information item. On all platforms, "About" items belong in Help. This item is really "DICOM File Info" — renaming it and moving it to Help (or making it a contextual panel) would be more correct. | P1 |
| T4 | **"(pylinac)"** in ACR QA tool names is an implementation detail that doesn't belong in a user-facing label. Users care about "ACR CT Phantom Analysis" and "ACR MRI Phantom Analysis" — not the underlying library. | P2 |
| T5 | **ACR QA tools are specialist/advanced** features that could be grouped under a "Quality Assurance" submenu to avoid clutter for users who never use them. | P3 |
| T6 | **Heterogeneous mix** without clear grouping rationale: tag management, MPR reconstruction, study database, structured reports, histogram, QA — four conceptual categories with only two separators. | P2 |

**Proposed Tools restructuring:**
```
View/Edit DICOM Tags...         Ctrl+T
Export DICOM Tags...            Shift+Ctrl+T
─────────────────────────────
Histogram...                    Shift+Ctrl+H
Export ROI Statistics...
─────────────────────────────
Create MPR View…
Structured Report…
─────────────────────────────
Manage Study Index…             (rename to distinguish from File > Open Study Index)
─────────────────────────────
Quality Assurance ▶
  ACR CT Phantom Analysis...
  ACR MRI Phantom Analysis...
```

Move "About this File..." → Help menu as "DICOM File Info…" (Ctrl+I).

---

### 11.6 Help Menu

**Full current structure:**
```
Quick Start Guide
Documentation (browser)...
Fusion Technical Documentation
Disclaimer
─────────────────────────────
About
```

**Findings:**

| # | Issue | Severity |
|---|---|---|
| H1 | **"Documentation (browser)..."** — the "(browser)" parenthetical is an implementation detail. "User Guide…" or "Documentation…" is cleaner. | P3 |
| H2 | **"Fusion Technical Documentation"** is feature-specific and feels out of place in Help alongside app-level docs. Consider moving it to the fusion workflow context (a button/link within the Fusion controls), or grouping all feature docs under a "Feature Guides ▶" submenu. | P3 |
| H3 | **"Disclaimer"** as a top-level item is intentional and appropriate for a medical application. Keeping it easily accessible satisfies regulatory and liability requirements. No change needed. | ✓ |
| H4 | **"About this File..."** (currently in Tools) belongs here as "DICOM File Info…". | P1 |

**Proposed Help restructuring:**
```
Quick Start Guide
User Guide…
─────────────────────────────
Feature Guides ▶
  Fusion Technical Documentation
  (add others as features grow)
DICOM File Info…               Ctrl+I  (moved from Tools)
─────────────────────────────
Disclaimer
─────────────────────────────
About
```

---

### 11.7 Cross-Cutting Menu Issues

#### Keyboard Shortcut Conflicts (Bugs)

| Shortcut | Assignment 1 | Assignment 2 |
|---|---|---|
| **Ctrl+O** | File → Open File(s)... | View → Overlay Tags Configuration... |
| **Ctrl+A** | Tools → About this File... | Platform standard: Select All |

Both are real bugs. Ctrl+O is particularly bad because it's one of the most commonly used shortcuts in any application. Qt will silently prefer one; the other becomes unreachable by keyboard.

#### Duplicate Commands

| Command | Location 1 | Location 2 | Recommendation |
|---|---|---|---|
| Study Index | File → Open Study Index… | Tools → Study Index Search… | Differentiate: File = "Open from Index" (opening workflow), Tools = "Manage Index" (admin/search) |

#### Design System Alignment

**Material Design 3:**
- Menus should have no more than 5–12 items before considering a split or submenu. The View menu (25+ items) violates this significantly.
- M3 recommends avoiding disabled items without explanation. "Show Instances Separately" is disabled with no tooltip.
- M3 progressive disclosure: advanced settings in submenus, core actions at the top level. The View menu buries Layout below 15 other items.

**IBM Carbon:**
- "Menu items must be actionable." Disabled items without explanation ("Show Instances Separately") violate this.
- Recommends dividers after groups of 6–8 related items maximum. The View menu's middle section (between the two separators) has 12+ items.
- Carbon's navigation pattern places layout/view controls more prominently than overlay configurations.

**Apple Human Interface Guidelines:**
- The File menu should contain only file operations: open, save, close, print, export. "Edit Recent List..." is a management action that HIG would place in Edit or as a submenu option of Recent.
- Edit menu: Undo/Redo should be general application-level operations, not scoped to one feature (tag edits). HIG considers scoped undo confusing.
- Disabled items: "If a command doesn't apply in the current context, remove it from the menu." HIG is more aggressive about hiding disabled items than M3 or Carbon.
- Preferences (Settings): on macOS this must appear in the application menu (⌘,), not in Edit. Qt's `QAction.MenuRole.PreferencesRole` handles this.
- The Help menu structure (Quick Start, Docs, About) is close to HIG-standard. Excellent.

#### Summary Scorecard

| Menu | Item Count | Design System Compliance | Top Issues |
|---|---|---|---|
| **File** | 16 | ⭐⭐⭐ Good | Duplicate Study Index, Edit Recent placement |
| **Edit** | 5 | ⭐⭐⭐ Good | Copy/Paste/Undo scope not communicated |
| **View** | 25+ | ⭐⭐ Needs work | Too long, Ctrl+O conflict, privacy not separated |
| **Tools** | 10 | ⭐⭐ Needs work | Ctrl+A conflict, duplicate Study Index, About misplaced |
| **Help** | 5 | ⭐⭐⭐⭐ Very good | Minor label polish only |

---

## 12. Summary: Key Findings

### Highest Priority (P0 — bugs or affects every user on every session)

| Issue | Source | Impact |
|---|---|---|
| **No toolbar icons** | All 8 screenshots | Slow tool identification, toolbar too wide, unprofessional appearance |
| **Ctrl+O conflict** — Open File and Overlay Tags Config share the same shortcut | `main_window_menu_builder.py` | One shortcut becomes unreachable; keyboard navigation broken |
| **Ctrl+A conflict** — "About this File" shadows platform-standard Select All | `main_window_menu_builder.py` | Breaks expected text-selection in any focused field |
| **2px splitter handles** | 002101 — invisible between panels | Difficult to resize panels precisely |
| **Tag viewer purple row tinting** inconsistent with blue accent | 002858 | Visual incoherence; the only place in the app with this color |

### High Priority (P1 — significant ergonomic or discoverability impact)

| Issue | Source | Impact |
|---|---|---|
| "Copy" / "Paste" / "Undo" / "Redo" scope not labelled | Edit menu | Users expect these to operate on image or ROI, not just annotations/tags |
| "About this File..." belongs in Help, not Tools | Tools menu | Misplaced; Ctrl+A conflict also resolved by moving it |
| Study Index duplicated across File and Tools | Both menus | Users unsure which is canonical |
| View menu has 25+ items across 7 conceptual categories | View menu + 002803 | Requires scrolling; buries Layout and Privacy in a flat list |
| Privacy View not visually separated in View menu | View menu code | Compliance-critical action mixed in with display options |
| Overlay text on images is extremely dense | 002253, 002649 | Competes with image content; legibility at its limit |
| "Delete Selected" / "Delete All" visible with no ROIs | 002101 | Visual noise; invites accidental destructive action |
| "Use Rescaled Values" not visually checkable | Toolbar in all screenshots | Current display state is unclear |
| "Privacy OFF — PHI Visible" wording would be clearer than "Privacy is OFF" | 002101 | Label could be more self-explanatory at a glance |
| No type scale defined | Visible inconsistency across panels | Inconsistent text hierarchy throughout |
| No cursor changes on tool mode switch | All screenshots | No per-mode visual feedback |
| Status bar "Ready" cold-start message | 002101 | Poor onboarding — no empty-state guidance |
| Tooltips lack keyboard shortcuts | Toolbar in all screenshots | Discoverability of shortcuts is poor |
| Histogram / dialog chart axis labels are very small | 002551, 002649 | Legibility issues in chart data |

### Medium Priority (P2 — reduces polish and learnability)

| Issue | Source | Impact |
|---|---|---|
| "Show/Hide Left Pane" / "Show/Hide Right Pane" redundant label | View menu | Checkmark already communicates show/hide |
| "Show Instances Separately" disabled with no explanation | View menu | Confusing grayed-out item; add status tip or hide |
| Layout shortcuts documented in label text rather than `setShortcut()` | View → Layout submenu | Shortcuts not right-aligned, may not be wired properly |
| "(pylinac)" in ACR tool names exposes implementation detail | Tools menu | User-facing labels should describe what, not how |
| ACR QA tools ungrouped alongside everyday utilities | Tools menu | Specialist tools mixed with histogram/tags without visual separation |
| "Fusion Technical Documentation" in Help is feature-specific | Help menu | Should be contextual or in a Feature Guides submenu |
| "Documentation (browser)..." qualifier is redundant | Help menu | "(browser)" is implementation detail |
| Light tooltip color (`#ffffdc`) | QSS | Dated, inconsistent with overall theme |
| `QGroupBox` unthemed | 002551 | Cross-platform inconsistency |
| Splitter handles have no visual affordance | 002101 | Resizing not discoverable |
| Right panel tab labels verbose ("Window/Zoom/ROI") | 002101 | Navigation friction |
| No drop target indicator | 002101 | Drag-and-drop not obviously available |
| Toast has no icon or severity color | No screenshot | All messages appear equally important |
| ROI resize handles are small dots | 002649 | Fine-motor difficulty on small screens |

### Positive Foundations (confirmed visually)

- **Privacy red toolbar button** is an intentional and correct safety pattern for a medical app — maximum visibility when PHI is exposed
- Dark theme is clean, professional, and appropriate for radiology use
- **Menu bar visual styling** (dark background, blue hover, clean separators) is the most polished surface in the UI
- Custom checkbox checkmarks (white PNG on dark) look correct and crisp
- ROI and measurement rendering (cyan ellipses, yellow distance line) is distinctive and clear
- Floating dialogs (Histogram, Slice Sync) coexist gracefully
- "Filter tags…" in the metadata panel is a strong affordance for a dense data list
- Series navigator correctly uses a differentiated background tone
- Blue focus border on active viewport pane is clear without being intrusive
- IBM Plex Sans is an excellent technical font choice
- Multi-window grid system is a strong feature differentiator
- Help menu structure is nearly HIG-standard

---

## 13. Screenshots Still Needed

Capture these for future passes:

1. **Light theme** — cold start and loaded state
2. **Series navigator bar close-up** — thumbnail sizing, study labels, window slot map widget
3. **Right panel "Combine/Fuse" tab** — intensity projection and fusion controls
4. **Right-click context menu on image** — reserved for the context menu deep-dive pass
5. **Settings dialog** — assess dialog styling and completeness
6. **Toolbar close-up** — cropped to show individual button sizes and spacing

---

## 14. Tools Used

**Code analysis:**
- `Glob` — directory and file structure discovery
- `Read` — `dark.qss`, `light.qss`, `main_window.py`, `main_window_toolbar_builder.py`, `main_window_menu_builder.py`, `main_window_layout_helper.py`, `UX_IMPROVEMENTS_BATCH1_PLAN.md`, `VIEWER_UX_FEATURES_PLAN.md`; all 8 screenshots
- `Bash` — process check, directory checks
- `Explore` agent — codebase architecture survey

**Design research referenced:**
- Material Design 3: https://m3.material.io/
- IBM Carbon Design System: https://carbondesignsystem.com/
- Apple HIG: https://developer.apple.com/design/

**Screenshots reviewed:** 8 live screenshots in `resources/screenshots-ignored/` (2026-05-01)

---

*Next pass: Right-click context menu deep-dive*  
*Planned: `DESIGN.md` — design system alignment, token system proposal, icon adoption plan*

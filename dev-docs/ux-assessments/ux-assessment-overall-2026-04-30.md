# UX Assessment — Overall Presentation & Experience
**Date:** 2026-04-30  
**Scope:** High-level structural UX pass. Menus and right-click context menus are reserved for follow-up assessments.  
**Method:** Static code analysis of QSS stylesheets, main window layout, toolbar builder, menu builder, panel layout helper, and existing UX planning documents. Live screenshots needed for verification — see flagged items.  
**Follow-up passes planned:** (1) Top menu bar deep-dive, (2) Right-click context menu deep-dive, (3) DESIGN.md with design-system alignment.

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

## 10. Summary: Key Findings

### Highest Priority (P0 — affects every user on every session)

| Issue | Impact |
|---|---|
| No toolbar icons | Slow tool identification, unscalable toolbar, unprofessional appearance |
| Privacy toggle label anti-pattern | Confusing state communication |
| 2px splitter handles | Difficult to resize panels precisely |

### High Priority (P1 — significant ergonomic impact)

| Issue | Impact |
|---|---|
| No type scale defined | Inconsistent text hierarchy across all panels |
| "Use Rescaled Values" not visually checkable | Unclear display state |
| No cursor changes on tool mode switch | No visual feedback for active tool |
| Status bar "Ready" cold-start message | Poor onboarding / empty-state guidance |
| No semantic color roles | Cannot visually distinguish severity of messages/actions |
| Tooltips lack keyboard shortcuts | Discoverability of shortcuts is poor |

### Medium Priority (P2 — reduces polish and learnability)

| Issue | Impact |
|---|---|
| Light tooltip color (`#ffffdc`) | Inconsistent with overall theme |
| No `QGroupBox` styling in QSS | May look inconsistent cross-platform |
| Splitter handles have no visual affordance | Non-discoverable resizing |
| Right panel tab labels are verbose/unclear | Navigation friction |
| No drop target indicator | Drag-and-drop not obviously available |
| Toast has no icon or severity color | All messages appear equally important |

### Positive Foundations

- Dark theme well-suited for radiology use
- IBM Plex Sans is an excellent font choice
- Accent color `#4285da` applied consistently
- Toast fade animation is polished
- Three-panel layout is industry-appropriate
- Multi-window grid system is a strong differentiator
- Series navigator thumbnail bar is a good information architecture pattern
- Config persistence for panel sizes and preferences
- Drag-and-drop file loading

---

## 11. Screenshots Needed

The following items require live screenshots to complete this assessment. Please run the app and capture:

1. **Empty/cold-start state** — full window with no files loaded (both dark and light theme)
2. **With a DICOM series loaded** — full window showing image in viewport, overlay text, metadata panel, and series navigator
3. **Toolbar close-up** — showing all tool buttons and their current appearance
4. **Series navigator bar** — showing thumbnails and the window slot map widget
5. **Right panel** — both tabs ("Window/Zoom/ROI" and "Combine/Fuse")
6. **A dialog** — e.g., Settings or About, to assess dialog styling
7. **Right-click context menu** — on image (for the context menu pass)
8. **Menu bar open** — e.g., the Tools menu expanded

---

## 12. Tools Used

**Code analysis:**
- `Glob` — directory and file structure discovery
- `Read` — source files: `dark.qss`, `light.qss`, `main_window.py`, `main_window_toolbar_builder.py`, `main_window_layout_helper.py`, `UX_IMPROVEMENTS_BATCH1_PLAN.md`, `VIEWER_UX_FEATURES_PLAN.md`
- `Bash` — process check (is app running?), directory existence check
- `Explore` agent — codebase architecture survey

**Design research referenced:**
- Material Design 3: https://m3.material.io/
- IBM Carbon Design System: https://carbondesignsystem.com/
- Apple HIG: https://developer.apple.com/design/

**Screenshots:** None captured (app was not running). See Section 11 for required screenshots.

---

*Next assessment: Menu bar deep-dive (`ux-assessment-menus-YYYY-MM-DD.md`)*  
*Planned: `DESIGN.md` — design system alignment, token system proposal, icon adoption plan*

# UX Assessment — Overall Presentation & Experience
**Date:** 2026-04-30 (updated with screenshots + menu deep-dive 2026-05-01; second screenshot batch + right-click context menu deep-dive 2026-05-02)  
**Scope:** Overall structural pass + full menu bar deep-dive + right-click context menu deep-dive.  
**Method:** Static code analysis (QSS stylesheets, main window layout, toolbar/menu/panel layout builders, existing UX planning docs) + visual review of 18 live screenshots.  
**Screenshots (batch 1):** `resources/screenshots-ignored/Screenshot 2026-05-01 00*.png`  
**Screenshots (batch 2):** `resources/screenshots-ignored/screenshots-more/Screenshot 2026-05-01 23*.png`  
**Follow-up passes planned:** (1) DESIGN.md — design system alignment, token system, icon adoption plan.

**Quick reference (priority tables + section map):** [ux-summary.md](ux-summary.md)

---

## Contents

1. [Application Architecture Overview](#1-application-architecture-overview)
2. [Visual Design](#2-visual-design)
   - [2.1 Theming](#21-theming) · [2.2 Typography](#22-typography) · [2.3 Iconography](#23-iconography)
3. [Layout & Structural UX](#3-layout--structural-ux)
   - [3.1 Splitter](#31-three-panel-splitter-layout) · [3.2 Center Panel](#32-center-panel--multi-window-layout) · [3.3 Left Panel](#33-left-panel--metadata--cine-controls) · [3.4 Right Panel](#34-right-panel--tabbed-controls) · [3.5 Series Navigator](#35-series-navigator)
4. [Toolbar Assessment](#4-toolbar-assessment)
5. [Status Bar](#5-status-bar)
6. [Interaction Design](#6-interaction-design)
7. [Accessibility](#7-accessibility)
8. [Design System Comparison](#8-design-system-comparison-preview)
9. [Icon Resources](#9-icon-resources)
10. [Visual Findings — Batch 1](#10-visual-findings-from-screenshots)
    - [10.1 Cold Start](#101-empty--cold-start-state-002101) · [10.2 Loaded State](#102-loaded-state--dual-pane-with-ct--photo-002253) · [10.3 Menus](#103-tools-menu-002337--file-menu-002423) · [10.4 Annotation + Histogram](#104-annotation-options-dialog--histogram-002551) · [10.5 ROIs + Slice Sync](#105-rois-drawn--slice-sync-dialog-002649) · [10.6 View Menu](#106-view-menu-open-002803) · [10.7 Tag Viewer](#107-dicom-tag-viewer-dialog-002858)
11. [Menu Bar Deep-Dive](#11-menu-bar-deep-dive)
    - [11.2 File](#112-file-menu) · [11.3 Edit](#113-edit-menu) · [11.4 View](#114-view-menu) · [11.5 Tools](#115-tools-menu) · [11.6 Help](#116-help-menu) · [11.7 Cross-Cutting Issues](#117-cross-cutting-menu-issues)
12. [Visual Findings — Batches 2–5](#12-visual-findings-from-new-screenshots-batches-2-3--4--2026-05-02)
    - [12.1 Light Theme Cold Start](#121-light-theme--cold-start-232107) · [12.2 Tag Viewer + Navigator](#122-dicom-tag-viewer-dialog-and-series-navigator-232501) · [12.3 Series Navigator](#123-series-navigator-close-up-233854) · [12.4 Combine/Fuse + Cine](#124-combinefuse-tab-and-cine-playback-233936-234016) · [12.5 Right-Click Menu](#125-right-click-context-menu-deep-dive-234100) · [12.6 Overlay Settings](#126-overlay-settings-dialog-234825) · [12.7 Annotation Options](#127-annotation-options--font-inconsistency-234902) · [12.8 Toolbar Overflow](#128-toolbar-overflow--two-rows-confirmed-235112) · [12.9 Overlay Tags Config](#129-overlay-tags-configuration-dialog-235159) · [12.10 Settings Dialog](#1210-settings-dialog-001155) · [12.11 Edit Recent List](#1211-edit-recent-list-dialog-001345-001359) · [12.12 Light Theme Loaded](#1212-light-theme--loaded-state-with-ct-image-and-rois-001542) · [12.13 Fullscreen](#1213-fullscreen-mode-001636) · [12.14 ACR MRI Options](#1214-acr-mri-options-dialog-001718) · [12.15 ACR CT Options](#1215-acr-ct-options-dialog-001744) · [12.16 Quick Start Guide](#1216-quick-start-guide-dialog-001806) · [12.17 About Dialog](#1217-about-dialog-001835) · [12.18 Tag Panel + VR Column](#1218-main-window-with-dicom-tags--vr-column-visible-001941) · [12.19 SR Document Tab](#1219-structured-report-dialog--document-tab-004749) · [12.20 SR Dose Events](#1220-structured-report-dialog--dose-events-tab-004848) · [12.21 SR Dose Summary](#1221-structured-report-dialog--dose-summary-tab-004914) · [12.22 MPR Single-Pane](#1222-mpr-view--sagittal-single-pane-012434-mpr) · [12.23 MPR + Axial](#1223-mpr-view--sagittal--axial-side-by-side-012652-mpr2)
13. [Summary: Key Findings](#13-summary-key-findings)
14. [Screenshots Still Needed](#14-screenshots-still-needed)
15. [Tools Used](#15-tools-used)

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

## 12. Visual Findings from New Screenshots (batches 2, 3 & 4 — 2026-05-02)

Screenshots reviewed: `232107`, `232501`, `233854`, `233936`, `234016`, `234100`, `234825`, `234902`, `235112`, `235159`.

### 12.1 Light Theme — Cold Start (`232107`)

- **Light theme confirmed visually.** White window background, gray panels, black text — clean and professional.
- **Slider accent color is purple/violet in the light theme.** Window Center, Window Width, and Zoom sliders in the right panel render in a purple/magenta color — not the blue (`#4285da`) that appears in the dark theme. This is a second undocumented accent color that appears nowhere in the design token table. The light theme has a different slider track color than the dark theme, and this purple also matches the tag viewer alternating row tint noted in 10.7 — confirming these are both light-theme-specific palette choices not covered by the stated token set.
- **"Privacy is ON" button renders in standard blue** — correct, no file loaded so privacy mode is on by default.
- **"Delete Selected" / "Delete All"** confirmed visible with no ROIs — same noise issue as dark theme.
- **Status bar "Ready"** confirmed across both themes.

### 12.2 DICOM Tag Viewer Dialog and Series Navigator (`232501`)

- **Series navigator clearly visible** at the bottom with thumbnails; the selected series has a yellow highlighted border and others are dark. Thumbnail sizes are consistent and identifiable at a glance.
- **Window Slot Map** (mini 2×2 grid, bottom-right) is visible with pane 1 highlighted — correctly tracks the active pane.
- **Status bar fully populated on file load:** left section shows study/file count ("9 studies, 12 series, 51 files loaded from exam (45 non-DICOM skipped)"); center shows Zoom and W/L Preset; right shows pixel coordinates. All three sections working as designed. The "(45 non-DICOM skipped)" detail is useful for technical users but may be confusing for clinical users who don't know what DICOM skipping means.
- **DICOM Tag Viewer dialog** includes a VR (Value Representation) column not present in the inline left-panel tag table — an inconsistency between the two tag views. Users familiar with the dialog will be confused by the absence of the VR column in the panel, and vice versa.
- **"Edit Selected Tag" button** is present at the bottom — confirms in-place tag editing capability, which is a powerful but potentially dangerous feature (modifying DICOM tags). No visible write-protection or confirmation prompt is shown in the dialog view; worth verifying whether a confirmation step exists.

### 12.3 Series Navigator Close-Up (`233854`)

- **Series labels are truncated UIDs**, not human-readable descriptions. Every series except "OB Image" shows a partial UID string (e.g., "1.3.6.1.4.1", "1.2.826.0") as its label. Clinically, users identify series by modality and description — not UID. The navigator should display series description as the primary label and show the UID only on hover or in a details panel.
- **Frame count badges** ("2f", "28f") correctly distinguish multi-frame series. Good affordance.
- **Thumbnail borders** correctly highlight the active series in cyan/blue.
- **Window slot map quadrants** (1–4) are visible; confirming that the map is non-clickable (per UX plan) remains a missing affordance.
- **Status bar left section** shows a very long study description string that likely requires text elision. The full UID-style study name fills the status bar edge-to-edge; series descriptions this long should be truncated with a tooltip showing the full text.

### 12.4 Combine/Fuse Tab and Cine Playback (`233936`, `234016`)

- **Combine/Fuse tab confirmed.** Controls visible: Enable Combine Slices (checkbox), Projection (combobox: Average AP), Slices (spinbox: 4), Enable Fusion (checkbox), Base Series selector, Overlay Series selector, Color Map, Fusion Status, Opacity, Threshold, Resampling Mode (Fast Mode / High Accuracy radio buttons), Interpolation, Overlay Window/Level.
- **"(INFO) Please select overlay series"** status message is clear inline guidance — a good pattern.
- **Resampling Mode** uses radio buttons (Fast Mode / High Accuracy) — appropriate for a binary choice between distinct modes.
- **The tab covers two distinct feature domains** (slab combination ≠ image fusion). As the panel grows, consider separate sub-tabs: "Slab" and "Fusion".
- **Cine playback controls confirmed** (`234016`): Play, Stop, Loop buttons; Speed (1x), FPS (10.0), Frame (1/25). Loop button highlights in blue when active — correct visual state. Speed and FPS are shown on the same row with a Frame counter — readable and compact.
- **"Privacy is OFF" (red)** visible in both screenshots with patient data in overlays — working as intended for loaded data.

### 12.5 Right-Click Context Menu Deep-Dive (`234100`)

The full right-click context menu is now captured. It is the most comprehensive context menu in the application.

**Full reconstructed structure:**

```
Angle (Shift+M)                              ← top items cut off; appear above visible area
Arrow Annotation (A)
Text Annotation (T)
Window/Level ROI (W)
Delete all ROIs (D)
Clear Measurements (C)
Histogram (Ctrl+Shift+H)
Scroll Wheel Mode ▶
────────────────────────────────────────────
Reset View (V, Shift+V)
Reset All Views
Orientation ▶
Cycle overlay detail (Space) / legacy toggle (Shift+Space)
Overlay Configuration
Privacy View (Cmd+P)
✓ Image Smoothing
  Show Scale Markers
✓ Show Direction Labels
  Slice Sync ▶
  Show Slice Location Lines ▶              → [submenu]:
    ✓ Enable/Disable
      Only Show For Same Group
      Only Show For Focused Window
    ✓ Show Slab Boundaries (Begin/End) Instead of Centre
  Show/Hide Left Pane
  Show/Hide Right Pane
  Show/Hide Series Navigator
  Prev Series (—)
  Next Series (—)
  Assign Series to Focused Window
  Layout ▶
  Swap
  Clear This Window
  Create MPR View…
  Annotation Options…
  Export ROI Statistics…
  Quick Window/Level (Q)
  Select (S)
  Zoom (Z)
  Pan (P)
  Magnifier (G)
  Ellipse ROI (E)
  Rectangle ROI (R)
  Crosshair ROI (H)
  Measure (M)
```

**Findings:**

| # | Issue | Severity |
|---|---|---|
| RC1 | **~40-item context menu** — by far the longest context menu in the application. At this length it defeats the purpose of a context menu (fast access to contextual actions) and effectively becomes a second menu bar. On 1080p displays it may require scrolling. | P1 |
| RC2 | **Tool mode shortcuts duplicated at the bottom** (Quick W/L, Select, Zoom, Pan, Magnifier, Ellipse ROI, Rectangle ROI, Crosshair ROI, Measure, Angle, Arrow, Text, W/L ROI) — 13 of the 22 toolbar items appear in the context menu. While useful as a mouse-only shortcut, the duplication inflates the length severely. Consider a "Tools ▶" submenu for these. | P1 |
| RC3 | **"Cycle overlay detail (Space) / legacy toggle (Shift+Space)"** is too long and exposes "legacy toggle" as an implementation term. Better: "Toggle Overlay Detail (Space)". | P2 |
| RC4 | **"Overlay Configuration"** (standalone item, no ellipsis) is ambiguous — it likely opens the Overlay Tags Configuration dialog, in which case it should be "Overlay Tags Configuration…" to match the menu bar label. | P2 |
| RC5 | **"Assign Series to Focused Window"** could be grouped with Prev/Next Series and Swap under a "Series" submenu. | P3 |
| RC6 | **Checkmarks on Image Smoothing and Show Direction Labels** are correctly shown — confirming state-aware context menu behavior. | ✓ |
| RC7 | **"Clear This Window"** is appropriately context-menu-only (pane-level action, not applicable globally) — good use of context menu to expose a pane-scoped action. | ✓ |

**Suggested right-click restructuring:**

```
── View ─────────────────────────────────
Reset View (V)   |  Reset All Views
Orientation ▶
Layout ▶   |   Swap   |   Clear This Window
────────────────────────────────────────────
── Display ──────────────────────────────
Toggle Overlay Detail (Space)
✓ Image Smoothing
✓ Show Direction Labels   |   Show Scale Markers
Privacy View (Cmd+P)
────────────────────────────────────────────
── Series ───────────────────────────────
Prev Series   |   Next Series
Assign Series to Focused Window
Show/Hide Left Pane   |   Right Pane   |   Navigator
────────────────────────────────────────────
── Sync ─────────────────────────────────
Slice Sync ▶
Show Slice Location Lines ▶
────────────────────────────────────────────
── Tools ────────────────────────────────
Pan (P)   |   Zoom (Z)   |   Select (S)   |   Magnifier (G)
Quick Window/Level (Q)   |   W/L ROI (W)
Ellipse ROI (E)   |   Rectangle ROI (R)   |   Crosshair ROI (H)
Measure (M)   |   Angle (Shift+M)
Arrow (A)   |   Text (T)
────────────────────────────────────────────
── Data ─────────────────────────────────
Overlay Tags Configuration…
Annotation Options…
Export ROI Statistics…
Delete all ROIs (D)   |   Clear Measurements (C)
Histogram (Ctrl+Shift+H)
Create MPR View…
```

This reduces the flat item count from ~40 to ~12 top-level items with logical subgrouping using section headers (Qt supports `addSection()` for labeled separators).

### 12.6 Overlay Settings Dialog (`234825`)

- **Well-structured dialog** with three clearly labeled sections (Overlay Settings, Viewer Overlay Elements, Slice Position Lines). The layout is clean and navigable.
- **Liberation Sans** is the currently selected overlay font — not IBM Plex Sans. The app ships IBM Plex Sans as its primary UI font but the overlay system defaults to a different family. Defaulting to IBM Plex Sans would improve visual cohesion.
- **Lime green overlay font color** is a user setting, but the default should be a more clinically neutral color (white, `#ffffff`, or light gray) rather than lime green, which may be confused with color-coded clinical indicators on some modalities.
- **Three color swatches** (lime green, cyan, red) demonstrate that per-element color customization is fully supported — a strong power-user feature.
- **Explanatory footnote text** ("Major ticks are longer; minor ticks are shorter", "Middle: one line at the centre plane...") is present and appropriately concise. Good pattern.
- **Slice sync group strip height (px)** is a very technical parameter that most users will never need. Consider moving it to an "Advanced" section or collapsible area.

### 12.7 Annotation Options — Font Inconsistency (`234902`)

- **Three different bundled font families across one dialog:** IBM Plex Sans (ROI Settings), Open Sans (Measurement Settings), Noto Sans (Text Annotation Settings). Open Sans and Noto Sans do not appear in the documented bundled font resources (`resources/fonts/`). If these fonts are not bundled, Qt will silently fall back to the OS default, potentially looking different on different platforms.
- **The four-quadrant layout** (ROI top-left, Measurement top-right, ROI Statistics Visibility bottom-left, Text/Arrow bottom-right) is logically organized. The two-column structure makes good use of dialog space.
- **Arrow Annotation Settings** (Color + Size only) has no Font field — correct, arrows have no label text. Consistent with feature scope.
- **Minus/Plus buttons** for font size and line thickness are larger here than in the toolbar context — adequate for dialog use.
- **Color swatches are large and easy to target** — good touch target sizing for this class of control.
- **"Show per-channel statistics when image is multi-channel (e.g. RGB)"** — long but clear label. The parenthetical example "(e.g. RGB)" is a helpful hint.

### 12.8 Toolbar Overflow — Two Rows Confirmed (`235112`)

- **CONFIRMED: the toolbar wraps to a second row.** "Font Color" and "Use Rescaled Values" render on a separate row below the main toolbar. This occurs because the combined width of all toolbar buttons exceeds the window width. Two toolbar rows:
  - Consume extra vertical space (the image viewport shrinks by one toolbar height, ~30px).
  - Make the second-row items harder to discover — users may not realize "Font Color" exists if the window is maximized or at a wider size where it fits on one row (the overflow breakpoint is layout-dependent).
- **"Use Rescaled Values"** on the second row is further evidence this should be a checkable action with a clear on/off state rather than a text-only toggle.
- **"Font Color"** on the second row is a low-frequency control (set once, rarely changed) — a strong candidate for moving to Overlay Settings dialog rather than the toolbar.
- **"Privacy is OFF" (red)** is the most visually prominent element — correct priority.

### 12.9 Overlay Tags Configuration Dialog (`235159`)

- **"Overlay mode_modality"** appears as a label/subtitle in the dialog — this is an internal Python identifier (likely a config key name) that has leaked directly into the UI. It should be reformatted as a readable label ("Modality-specific mode" or simply removed — the two dropdowns below (Default and Modality) are self-explanatory).
- **Dual-list transfer widget** (Catalog → Simple / Catalog → Detailed) is a sophisticated and appropriate pattern for this level of configuration. The "→ Detailed" / "← Simple" labeled arrow buttons are clear.
- **Four corner tabs** (Upper Left, Upper Right, Lower Left, Lower Right) map directly to the four overlay corners of the image viewport — intuitive spatial labeling.
- **Catalog shows CamelCase DICOM keyword names** (PatientName, PatientID, etc.) rather than hex codes — the right choice for a configuration interface where users need to recognize attributes by name.
- **"Default (Space)"** label on the first combobox is cryptic — it means "the mode toggled by pressing Space", but a user unfamiliar with the Space shortcut will not understand. Better: "Space Bar Mode" or "Default Toggle Mode (Space)".
- **Instructions text** ("Corner tabs: catalog at left; Simple and Detailed-only lists share one row. → Detailed / ← Simple move selection. Double-click catalog → Simple.") is helpful but dense. Consider a collapsible "?" tooltip or breaking it into a short bulleted help block.
- **"Add to Simple" / "Add to Detailed" buttons** at the bottom of the catalog are redundant with the arrow buttons in the center — two ways to do the same action. Recommend removing the bottom buttons and relying on the center arrow buttons plus a double-click shortcut (already documented in the instructions).

---

*Batch 3 — screenshots `001155`–`001941` (2026-05-02):*

### 12.10 Settings Dialog (`001155`)

- **The Settings dialog interior uses the system (OS) light theme instead of the app's dark QSS.** The content area renders with a white/light-gray background and native-styled controls while the main window behind it is dark `#2b2b2b`. Every other dialog in the app (Tag Viewer, Annotation Options, Overlay Settings, etc.) correctly applies the dark theme. Settings is the only exception — likely because the dialog class isn't receiving the QSS. This is a theme break that makes the dialog visually jarring to open.
- **The dialog is nearly empty as a Settings dialog.** Its only actual setting is "Automatically add files to the study index when opened successfully." The top of the dialog is occupied by three lines of instructional prose redirecting the user to the View menu for overlay preferences, annotation options, and privacy mode. This is the opposite of what a Settings dialog should do — it should centralize preferences, not scatter them and provide directions to find them elsewhere.
- **Encryption security note is good but buried.** The text "The index database is encrypted (SQLCipher). The encryption key is stored in your OS credential manager, not in this JSON config file." is exactly the right information to surface to users, but it is rendered as small secondary text. For a medical app, this security transparency deserves more prominence.
- **"Use default path" button** next to the database path field is a sensible recovery affordance.

### 12.11 Edit Recent List Dialog (`001345`, `001359`)

- **Full file paths are displayed without truncation** in the list. On the user's machine, several paths are long enough to overflow the dialog width horizontally. Truncating from the left (showing `…\DICOMViewerV3\test-data\file.dcm`) would preserve the most useful part (filename and immediate parent) while fitting the column.
- **"Move Up" and "Move Down" buttons** allow reordering the recent files list. This is an unusual feature — most applications order recent files strictly by recency and do not expose manual reordering. If the intent is to let users "pin" frequently used files to the top, a dedicated "Pin" concept would be clearer than an order that can drift from actual recency.
- **"Remove All" and "Remove Selected"** are appropriately paired destructive actions with no confirmation prompt visible — the consequence (clearing recent history) is mild enough that a confirmation is optional, but "Remove All" in particular would benefit from one.
- **Dialog is dark-themed correctly** — consistent with the rest of the application (unlike the Settings dialog).

### 12.12 Light Theme — Loaded State with CT Image and ROIs (`001542`)

*Correction: this screenshot shows the light theme with a study loaded — not the dark theme as previously described. The CT image center is always dark (that is the image content, not the theme), but the surrounding UI chrome is light.*

- **Light theme confirmed in loaded state.** The left tag panel has a white/light-gray background with dark text — matching the light-theme tokens. The right panel sliders are purple/violet, **confirming the undocumented purple accent color from §12.1 persists in the loaded state**, not just cold-start. Two ROIs are visible on the CT phantom.
- **VR column IS present in the inline left-panel tag table** — all four columns (Tag, Name, Value, VR) visible. The earlier finding (§12.2) that VR was absent was incorrect; the panel was simply too narrow in that screenshot. That finding is retracted.
- **Tag group headers** (Group 0002, Group 0008, Group 0010, etc.) with expand/collapse behavior are a clean organizing pattern for dense DICOM data.
- **Two simultaneous ROIs (rectangle + ellipse)** each display six lines of statistics on the image — twelve total floating text lines. This is the practical ceiling: a third ROI would make the image unreadable. Consider a per-ROI text toggle (show/hide label on image, with stats still in the right-panel table) for multi-ROI workflows.
- **ROI type annotation** in the right-panel list — "ROI 1 (ellipse)" and "ROI 2 (rectangle)" — is a good affordance.
- **Cyan ROI annotations remain clearly legible** against the dark CT image background even in the light theme — good contrast choice.

### 12.13 Fullscreen Mode (`001636`)

- **Fullscreen mode hides both side panels and expands the image viewport**, leaving only the toolbar at top and status bar at bottom. The CT phantom with both ROIs fills the full center area cleanly — excellent for focused clinical reading.
- **The window title bar remains visible** in this fullscreen implementation. This is likely the app's internal fullscreen (hiding panels + maximizing the viewport area) rather than OS-level F11 fullscreen which would suppress the title bar entirely. Either behavior is acceptable; the OS-level variant recovers a few more pixels.
- **Corner overlays persist correctly** in fullscreen — they belong to the viewport, not the panels, so their visibility is unaffected.
- **ROI annotations and statistics render correctly** with panels hidden — no layout artifacts or text clipping visible.
- **Toolbar and status bar remain full-width** — consistent with the non-fullscreen layout. This means the user retains access to all toolbar tools in fullscreen, which is the right tradeoff for a clinical tool (mode switching should always be reachable).

### 12.14 ACR MRI Options Dialog (`001718`)

- **Dialog title still contains "(pylinac)"** — as noted in §12.5. The implementation library name should be removed from the user-facing title.
- **"Sanity multiplier"** is a raw internal/algorithmic term. "Maximum allowed contrast ratio" or simply "Contrast limit multiplier" would be more interpretable to a medical physicist who may not know the pylinac source code.
- **Advanced section is well-separated** with a clear "Low-contrast detectability — single run" header and distinct field grouping. The "Reset to pylinac defaults" button is a useful escape hatch.
- **"Compare to up to 3 parameter sets" multi-run feature** is disabled (greyed "Enable next run" button) in this state — it is not explained why it's disabled. A status tip ("Load a study to enable") would reduce confusion.
- **Dark-themed correctly** throughout.

### 12.15 ACR CT Options Dialog (`001744`)

- **"Vanilla pylinac (stock ACRCT)"** is developer jargon. A clinical user sees "vanilla" and either doesn't know what it means or finds it unprofessional in a medical context. Better: "Standard mode (strict slice index rules, matches pylinac CLI)" with a separate parenthetical for the class name if needed at all.
- **Explanatory paragraph is long but the information is necessary** for a medical physicist who needs to understand the difference between viewer integration mode and vanilla pylinac. Consider a collapsed "?" or "Learn more" expander to keep the dialog compact by default and reveal the explanation on demand.
- **Dialog is well-structured** given its complexity: vanilla toggle → HU module section → scan extent section. The `QGroupBox`-style section frames provide clear visual separation.
- **Dark-themed correctly** throughout.

### 12.16 Quick Start Guide Dialog (`001806`)

- **Excellent in-app help implementation.** The Quick Start Guide is a full rich-text viewer with: search field (with Prev/Next match navigation), section navigation (Table of Contents, Prev Section, Next Section), inline links to browser-based documentation, and a proper table of contents with clickable bullet links. For a desktop medical application, this is a strong onboarding asset.
- **Search field placeholder** "Search in guide to enable Prev/Next..." is clear and communicates the interaction model upfront.
- **Links to feature-specific documentation** (MPR, ACR phantom QA, image fusion) are well-organized within the guide — this directly answers the concern raised about "Fusion Technical Documentation" in the Help menu (§11.6 H2). With in-app links, a top-level Help menu entry for it is less necessary.
- **"Close" button** is correctly placed bottom-right. The guide is modal (no interaction with the main window while open), which is acceptable for a Help dialog.
- **Dark-themed correctly** throughout.

### 12.17 About Dialog (`001835`)

- **App has two names: "DICOM Viewer V3" (window title bar) and "Medical Physics DICOM Viewer" / "MPDV" (About dialog and app icon).** The title bar, taskbar tooltip, and window title all say "DICOM Viewer V3" while the About dialog, app icon, and GitHub repo appear to use "Medical Physics DICOM Viewer" / "MPDV". Users, support requests, and documentation cannot agree on what the app is called. One canonical name should be chosen and used everywhere. "MPDV — Medical Physics DICOM Viewer" with "v0.3.0" in the title bar would be clean.
- **App icon quality confirmed:** The brain+heart graphic with "MPDV" text on a dark blue rounded-square background is professional, recognizable, and should render clearly at small sizes (32×32 taskbar). The earlier concern about the icon being low quality (§2.3) is resolved — the icon is good. The concern about the filename was the actual problem.
- **About dialog is well-structured:** icon + name + version + author + GitHub link + horizontal divider + feature bulleted list. The scrollable feature list is a nice touch for a v0.3 app with broad functionality.
- **Dark-themed correctly** throughout.

### 12.18 Main Window with DICOM Tags + VR Column Visible (`001941`)

- **VR column visible in both the left tag panel and confirmed correct.** All four columns (Tag, Name, Value, VR) are visible when the panel is at adequate width. The earlier inconsistency finding is hereby retracted.
- **Full DICOM tag listing** with expanded groups (0002, 0008, 0010, 0018, etc.) and a scrolled view is clear and well-organized. The Group row headers (e.g., "Group {0008}") function as section headers — appropriate.
- **"Select" tool is active** (toolbar highlight) with a rectangle ROI and ellipse ROI drawn — confirming the Select mode's visual state is correctly communicated via the blue highlight.
- **Privacy is OFF** (red) — patient data visible in overlays. Working as designed.

---

*Batch 4 — screenshots `004749`–`004914` from `more2/` (2026-05-02):*

### 12.19 Structured Report Dialog — Document Tab (`004749`)

- **Dialog title is long but accurate:** "Structured Report — X-Ray Radiation Dose SR — Radiation Dose Information." The three-part format (dialog type — SR SOP class — SR concept name) is precise but may exceed the title bar width on smaller screens. Consider truncating to "Structured Report — Radiation Dose Information" with the full name in a subtitle label inside the dialog.
- **Four tabs** (Document, Dose events, Dose summary, Raw tags) cover the SR information from four complementary perspectives — an excellent structure for a complex DICOM object with layered data.
- **Document tab** renders the full SR ContentSequence as an expandable tree: Concept (with DCM code), Relationship, Value type, Value columns. The right sidebar shows selected-item detail. This is the correct approach for a complex nested DICOM SR — a flat table would not represent the hierarchy.
- **"Export document tree JSON..." button** at bottom-left is a strong power-user feature.
- **Alternating row colors** in the Document tree appear to use a blue tint on highlighted rows (selected) and default dark rows — no purple anomaly visible. Dark-themed correctly.
- **The tree depth** (indentation levels visible) is appropriate; CONTAINS relationships are correctly subordinated under their parent nodes.

### 12.20 Structured Report Dialog — Dose Events Tab (`004848`)

- **Row-to-Document-tab highlighting** is an excellent cross-tab affordance: selecting a dose event row highlights the matching CONTAINER in the Document tree. This directly aids debugging and verification workflows.
- **"Hide empty columns" checkbox** (checked by default) is a smart density control — most SR files will have many sparsely populated columns. Well-conceived.
- **Export buttons** — "Export dose events CSV..." and "Export dose events XLSX..." — are appropriately placed at the bottom left, paired clearly with the active tab's data. XLSX support is a strong feature for medical physics reporting workflows.
- **Column header truncation is a significant readability issue.** Several headers appear cut off or corrupted: "tcquisition plan" (likely "Acquisition plan" with leading character(s) clipped), "DateTime starter" (likely "DateTime started"), "radiation event t" (truncated). These truncations suggest the table columns have fixed widths too narrow for their headers. Default column widths should be set to at least accommodate the full header text, with horizontal scroll available for overflow.
- **Row 4 selected and highlighted in blue** — correct visual feedback that links to the Document tab.
- **kVp values visible** (57.5, 55.74, 60.07, 61.82, 72.71, 68.13, 65.13, 64.73, 57.93, 59.8, 60.42, 60.79, 66.96) — meaningful radiation dose data displaying correctly.

### 12.21 Structured Report Dialog — Dose Summary Tab (`004914`)

- **Two-column table** (Field | Value) for the summary is clean and readable.
- **Field column truncation** — several field names are cut off: "Study Instance ...", "Series Instance ...", "Manufacturer ...", "Device Serial ...", "Irradiation even...", "Parse hit node ..." — the Field column is too narrow. Unlike the Dose events tab (where columns can be resized), this appears to be a fixed-width layout. The Field column should be wide enough to show full field names without truncation, or field names should wrap to two lines.
- **CTDIvol (mGy), DLP (mGy·cm), SSDE (mGy) are all empty** — expected for a fluoroscopy X-Ray SR (not CT), but the empty rows add visual noise. A "Hide empty rows" toggle (mirroring the Dose events tab's "Hide empty columns") would improve this.
- **"Parse hit node ... | No"** is raw internal implementation language — "Dose summary parsed: No" or "Dose metrics extracted: No" would be more meaningful to a clinical user who doesn't know what a "parse hit node" is.
- **"Irradiation even... | 0"** — truncated to the point where it reads ambiguously. "Irradiation events" = 0 is meaningful clinical information that deserves to be legible.
- **The "Raw tags" tab** is not captured but its existence is appropriate — raw DICOM tag access within the SR viewer is correct for a medical physics tool.
- **Dark-themed correctly** throughout all three tabs.

---

*Batch 5 — screenshots `012434-mpr.png`, `012652-mpr2.png` from `more2/` (2026-05-02):*

### 12.22 MPR View — Sagittal Single-Pane (`012434-mpr`)

- **MPR is integrated into the main multi-window viewport grid, not a separate dialog or mode.** The sagittal reconstruction replaces the content of a standard viewport slot — the correct UX approach. Users get MPR as a first-class view alongside any other pane type.
- **"MPR - Sagittal" is shown in the corner overlay** (top-center position, alongside orientation markers A/P/S). This clearly identifies the reconstructed plane. The direction labels (Anterior, Posterior, Superior) are correctly oriented for the sagittal plane — the orientation system works correctly across reconstructed planes, not just the source axial.
- **The MPR view participates in cine playback.** Frame counter shows 10/42 — the user is scrolling through sagittal MPR slices via cine. This is the correct behavior; MPR frames are navigable the same way as source slices.
- **Window/Level applies correctly** to the MPR pane — Window Center 40.0, Width 500.0 (soft-tissue windowing) renders the sagittal reconstruction with appropriate contrast.
- **No MPR-specific controls are visible in the right panel** — the standard Window/Zoom/ROI panel is shown. There is no plane-angle control, slab-thickness spinbox, or source-link indicator visible in this state. If such controls exist elsewhere, their location is not surfaced in this view.
- **Privacy is OFF (red)** — patient data visible in overlays, working correctly.

### 12.23 MPR View — Sagittal + Axial Side-by-Side (`012652-mpr2`)

- **MPR coexists with the original axial source view** in a 2-pane layout (axial top, sagittal MPR bottom). This is the primary clinical MPR workflow — the reconstructed plane and the source data visible simultaneously. The implementation handles this correctly.
- **No reference lines (crosshairs) are visible** between the axial pane and the sagittal MPR pane. In clinical MPR workflows, a reference line on the axial view shows the position of the sagittal cut plane, and vice versa. Without this, the user cannot visually correlate which axial position the sagittal slice represents. The "Show Slice Location Lines" feature (seen in the View menu and context menu) may provide this, but it is not active in this screenshot — its discoverability and applicability to MPR cross-pane linking is worth verifying.
- **The active pane (MPR, bottom) has the correct blue focus border** — consistent with other multi-pane layouts.
- **Cine plays within each pane independently** — frame counter shows 20/42 in the cine controls, consistent with navigating MPR slices.
- **The two-pane layout is the natural entry point for MPR work**, and the app supports it correctly via the existing multi-window grid system. No special MPR layout mode is required.

| # | Issue | Severity |
|---|---|---|
| M1 | **No reference/crosshair lines between MPR and source panes** — the intersection of the sagittal cut plane on the axial view (and vice versa) is not shown. This is the primary spatial orientation tool in clinical MPR workflows. | P1 |
| M2 | **No MPR-specific controls visible in the right panel** — plane angle, slab thickness, and source-link controls (if they exist) are not surfaced when an MPR pane is focused. | P2 |
| M3 | **MPR creation is only accessible via "Create MPR View…"** in the right-click context menu and the Tools menu — a new user reading the toolbar would not find it. A toolbar button or a View → Layout-level affordance would improve discoverability. | P2 |

---

## 13. Summary: Key Findings

### Highest Priority (P0 — bugs or affects every user on every session)

| Issue | Source | Impact |
|---|---|---|
| **No toolbar icons** | All screenshots | Slow tool identification, toolbar too wide, unprofessional appearance |
| **Toolbar wraps to two rows** | `235112` | Viewport height loss; second-row items harder to discover |
| **Ctrl+O conflict** — Open File and Overlay Tags Config share the same shortcut | `main_window_menu_builder.py` | One shortcut unreachable; keyboard navigation broken |
| **Ctrl+A conflict** — "About this File" shadows platform-standard Select All | `main_window_menu_builder.py` | Breaks text-selection in any focused field |
| **2px splitter handles** | `232107`, `002101` | Difficult to resize panels precisely; no visual affordance |
| **"Overlay mode_modality" raw identifier in dialog UI** | `235159` | Internal Python variable name exposed directly to users; display bug |
| **Light theme has undocumented purple/violet slider accent** | `232107` | Second undocumented accent color; inconsistent with the blue token used in the dark theme |
| **Settings dialog ignores app QSS — renders with OS light theme** | `001155` | White dialog interior inconsistent with other dialogs; screenshot may have been in light theme mode — needs verification in dark theme |
| **App has two different names** — "DICOM Viewer V3" (title bar) vs "Medical Physics DICOM Viewer / MPDV" (About dialog, icon) | `001835`, title bar | Documentation, support, and users cannot agree on what to call the app |

### High Priority (P1 — significant ergonomic or discoverability impact)

| Issue | Source | Impact |
|---|---|---|
| "Copy" / "Paste" / "Undo" / "Redo" scope not labelled | Edit menu | Applies to annotations, ROIs, and tags; labels give no hint which objects are affected — scope ambiguity reduces discoverability |
| "About this File…" Ctrl+A conflict | Tools menu | Shadows platform Select All; rename to "DICOM File Info…" or add qualifier to remove ambiguity |
| Study Index duplicated across File and Tools | Both menus | Users unsure which is canonical |
| View menu has 25+ items across 7 conceptual categories | View menu + `002803` | Requires scrolling; buries Layout and Privacy |
| Privacy View not visually separated in View menu | View menu code | Compliance-critical action mixed with display options |
| Right-click context menu has ~40 items | `234100` | Defeats purpose of context menu; requires scrolling |
| 13 tool modes listed flat in right-click menu — group into "Tools ▶" submenu | `234100`, toolbar | Having tool modes accessible from both toolbar and context menu is intentional; flat listing at root level is what creates the clutter |
| Overlay text default density | `002253`, `002649` | Size and content are user-configurable (Overlay Settings); default configuration may overwhelm new users — consider lighter out-of-box defaults |
| "Delete Selected" / "Delete All" visible with no ROIs | `232107`, `002101` | Visual noise; invites accidental destructive action |
| "Use Rescaled Values" not visually checkable; overflows to second toolbar row | `235112` | Current display state unclear; discoverable only when window is narrow |
| "Font Color" on second toolbar row | `235112` | Low-frequency control taking prime toolbar real estate; candidate for Overlay Settings |
| Series navigator labels are truncated UIDs not series descriptions | `233854` | Clinical users identify series by description, not UID |
| Three different font families in Annotation Options dialog | `234902` | IBM Plex Sans, Open Sans, Noto Sans in one dialog; Open Sans and Noto Sans may not be bundled |
| ~~VR column present in Tag Viewer dialog but absent from inline tag panel~~ | *Retracted — VR column confirmed present in inline panel (`001941`); was a viewport-width artifact in `232501`* | — |
| "Default (Space)" combobox label in Overlay Tags Configuration is cryptic | `235159` | Space shortcut undocumented and label unintuitive |
| Settings dialog contains only 1 setting; redirects to menus for all others | `001155` | Anti-pattern — Settings should centralize preferences, not give directions elsewhere |
| "Move Up" / "Move Down" in Edit Recent List reorders by user drag rather than recency | `001345`, `001359` | Unusual; intent is unclear without explanation; may confuse users expecting auto-recency ordering |
| **No reference/crosshair lines between MPR and source panes** — sagittal cut position not shown on axial, and vice versa | `012652-mpr2` | Primary spatial orientation tool for clinical MPR workflows is absent |
| SR Dose events tab column headers truncated — "tcquisition plan", "DateTime starter", "radiation event t" | `004848` | Headers clipped by fixed column widths; data is unreadable without context |
| SR Dose summary "Field" column too narrow — truncates every field name | `004914` | "Study Instance ...", "Irradiation even..." lose meaning when cut off |
| SR Dose summary "Parse hit node ... \| No" is raw internal implementation language | `004914` | Should read "Dose summary parsed: No" or similar plain-language equivalent |
| "Privacy OFF — PHI Visible" wording would be clearer than "Privacy is OFF" | `002101`, `233936` | Label could be more explicit at a glance |
| No type scale defined | Visible inconsistency across panels | Inconsistent text hierarchy throughout |
| No cursor changes on tool mode switch | All screenshots | No per-mode visual feedback |
| Status bar "Ready" cold-start message | `232107`, `002101` | Poor onboarding — no empty-state guidance in either theme |
| Tooltips lack keyboard shortcuts | Toolbar across all screenshots | Discoverability of shortcuts is poor |
| Histogram / chart axis labels are very small | `002551`, `002649` | Legibility issues in chart data |

### Medium Priority (P2 — reduces polish and learnability)

| Issue | Source | Impact |
|---|---|---|
| "Show/Hide Left Pane" / "Show/Hide Right Pane" redundant label | View menu | Checkmark already communicates show/hide |
| "Show Instances Separately" disabled with no explanation | View menu | Confusing grayed-out item; add status tip or hide |
| Layout shortcuts in label text rather than `setShortcut()` | View → Layout submenu | Shortcuts not right-aligned, may not be wired |
| "(pylinac)" in ACR tool names and dialog titles exposes implementation detail | Tools menu, `001718`, `001744` | User-facing labels should describe what, not how |
| "Vanilla pylinac" and "Sanity multiplier" in ACR dialogs are developer jargon | `001718`, `001744` | Unintelligible to clinical users; need plain-language replacements |
| ACR QA tools ungrouped alongside everyday utilities | Tools menu | Specialist tools mixed with histogram/tags |
| "Fusion Technical Documentation" in Help is feature-specific | Help menu | Should be contextual or in Feature Guides submenu |
| "Documentation (browser)..." qualifier is redundant | Help menu | "(browser)" is implementation detail |
| Light tooltip color (`#ffffdc`) | QSS | Dated; inconsistent with overall theme |
| `QGroupBox` unthemed | `002551` | Cross-platform inconsistency |
| Splitter handles have no visual affordance | `232107`, `002101` | Resizing not discoverable |
| Right panel tab label "Window/Zoom/ROI" is verbose | `232107`, `002101` | Navigation friction |
| No drop target indicator | `232107`, `002101` | Drag-and-drop availability not visible |
| Toast has no icon or severity color | Code only | All toasts appear equally important |
| ROI resize handles are small dots | `002649` | Fine-motor difficulty on small screens |
| "Cycle overlay detail / legacy toggle" label too long and exposes internals | `234100` | Simpler: "Toggle Overlay Detail (Space)" |
| "Overlay Configuration" in context menu label differs from menu bar label | `234100` | Should be "Overlay Tags Configuration…" for consistency |
| "(45 non-DICOM skipped)" in status bar is jargon for clinical users | `232501` | Technical detail inappropriate for non-expert audience |
| Overlay font defaults to Liberation Sans, not IBM Plex Sans | `234825` | Inconsistency with primary UI font; cohesion opportunity |
| Lime green as default overlay font color | `234825` | Aggressive default; white or light gray would be more clinically neutral |
| "Add to Simple" / "Add to Detailed" buttons redundant with arrow buttons | `235159` | Two ways to do the same action; prefer arrow buttons only |
| Combine/Fuse tab covers two distinct feature domains | `233936`, `234016` | As panel grows, consider "Slab" and "Fusion" sub-tabs |
| "Slice sync group strip height (px)" is too advanced for top-level exposure | `234825` | Move to collapsed "Advanced" section |
| SR Dose summary has no "Hide empty rows" toggle | `004914` | CTDIvol/DLP/SSDE empty rows add noise; mirrors the Dose events "Hide empty columns" pattern |
| SR dialog title is very long and may clip on smaller screens | `004749` | "Structured Report — X-Ray Radiation Dose SR — Radiation Dose Information" — consider shorter display title |
| No MPR-specific controls in right panel when MPR pane is focused | `012434-mpr` | Plane angle, slab thickness, source-link controls (if they exist) not surfaced |
| MPR creation only discoverable via right-click and Tools menu | `012652-mpr2` | Not on toolbar; new users reading the toolbar will not find it |

### Positive Foundations (confirmed visually — batch 1 + batch 2)

- **Privacy red toolbar button** is an intentional and correct safety pattern — maximum visibility when PHI is exposed, both themes
- Dark theme is clean, professional, and appropriate for radiology use
- Light theme is clean and professional; a viable alternative to the dark theme
- **Menu bar visual styling** (dark background, blue hover, clean separators) is the most polished surface in the UI
- Custom checkbox checkmarks (white PNG on dark) look correct and crisp
- ROI and measurement rendering (cyan ellipses, yellow distance line) is distinctive and clear
- Floating dialogs (Histogram, Slice Sync) coexist gracefully without covering critical content
- "Filter tags…" in the metadata panel is a strong affordance for a dense data list
- **Cine playback controls** (Play / Stop / Loop) with active-state highlighting are clean and functional
- **Overlay Tags Configuration** dual-list widget is a sophisticated and correct pattern for overlay customization
- Series navigator correctly uses a differentiated background tone
- Blue focus border on active viewport pane is clear without being intrusive
- IBM Plex Sans is an excellent technical font choice for the primary UI
- Multi-window grid system (1×1 to 2×2) is a strong clinical workflow differentiator
- Help menu structure is nearly HIG-standard
- Frame-count badges on navigator thumbnails ("2f", "28f") are a good at-a-glance differentiator
- Overlay Settings dialog is well-structured with clear section groupings
- Annotation Options dialog layout (four-quadrant) is logical and compact
- "(INFO) Please select overlay series" inline guidance in Fusion panel is the right pattern for progressive disclosure
- **Quick Start Guide** (`001806`) is an excellent in-app help implementation — rich-text viewer with search, Prev/Next match navigation, section navigation, and browser-doc links; one of the strongest in-app help systems for a desktop tool of this scope
- **About dialog** (`001835`) is well-structured: icon + product name + version + author + GitHub link + scrollable feature list
- **App icon (MPDV)** (`001835`) — brain+heart graphic on dark rounded square is professional, clear, and readable at small sizes; earlier filename concern is resolved
- **Hidden-panel mode** (`001636`) — when both side panels are collapsed, the image fills the viewport cleanly with no layout artifacts; a good focused-reading mode
- **Encryption transparency note** in Settings (`001155`) — surfacing "key stored in OS credential manager, not JSON config" is exactly the right security communication for a medical app
- **Tag group expand/collapse structure** in the left panel (`001542`) — Group headers (Group 0002, 0008, etc.) as collapsible sections is the right pattern for dense DICOM data
- **Edit Recent List dialog** (`001345`) — dark-themed correctly; "Remove All" and "Remove Selected" are appropriately scoped actions
- **Structured Report dialog** (`004749`–`004914`) — four-tab structure (Document tree, Dose events, Dose summary, Raw tags) is exactly the right information architecture for a complex DICOM SR; row↔Document-tab cross-linking is an excellent affordance; CSV/XLSX export is a strong medical physics workflow feature; "Hide empty columns" checkbox is a well-conceived density control; dark-themed correctly throughout
- **Fullscreen mode** (`001636`) — image expands to fill the viewport cleanly with toolbar and status bar intact; all tools remain accessible; ROI annotations persist without artifacts
- **MPR integrated into multi-window grid** (`012434-mpr`, `012652-mpr2`) — sagittal reconstruction is a first-class viewport, not a separate dialog; direction labels correctly orient for the reconstructed plane; cine navigation works within MPR panes; MPR + axial side-by-side layout works cleanly
- **Light-theme loaded state** (`001542`) — cyan ROI annotations remain clearly legible against the dark CT image background in the light theme; purple/violet slider accent color confirmed in loaded state as well as cold-start

---

## 14. Screenshots Still Needed

Covered in batches 1–4 (can be removed from backlog):
- ~~Light theme cold-start~~ — covered (`232107`)
- ~~Light theme loaded state~~ — covered (`001542`)
- ~~Series navigator bar close-up~~ — covered (`233854`)
- ~~Right panel Combine/Fuse tab~~ — covered (`233936`, `234016`)
- ~~Right-click context menu~~ — covered (`234100`)
- ~~Toolbar close-up~~ — covered (`235112`)
- ~~Settings dialog~~ — covered (`001155`)
- ~~ACR Phantom QA dialogs~~ — covered (`001718`, `001744`)
- ~~Quick Start Guide~~ — covered (`001806`)
- ~~About dialog~~ — covered (`001835`)
- ~~Structured Report dialog~~ — covered (`004749`, `004848`, `004914`)
- ~~Fullscreen mode~~ — covered (`001636`)

- ~~MPR view~~ — covered (`012434-mpr`, `012652-mpr2`)

All planned screenshot passes complete. No further screenshots outstanding.

---

## 15. Tools Used

**Code analysis:**
- `Glob` — directory and file structure discovery
- `Read` — `dark.qss`, `light.qss`, `main_window.py`, `main_window_toolbar_builder.py`, `main_window_menu_builder.py`, `main_window_layout_helper.py`, `UX_IMPROVEMENTS_BATCH1_PLAN.md`, `VIEWER_UX_FEATURES_PLAN.md`; all 33 screenshots
- `Bash` — process check, directory checks
- `Explore` agent — codebase architecture survey

**Design research referenced:**
- Material Design 3: https://m3.material.io/
- IBM Carbon Design System: https://carbondesignsystem.com/
- Apple HIG: https://developer.apple.com/design/

**Screenshots reviewed:**
- Batch 1: 8 screenshots in `resources/screenshots-ignored/` (2026-05-01)
- Batch 2: 10 screenshots in `resources/screenshots-ignored/screenshots-more/` (2026-05-02)
- Batch 3: 10 screenshots in `resources/screenshots-ignored/screenshots-more/` (2026-05-02)
- Batch 4: 3 SR screenshots in `resources/screenshots-ignored/more2/` (2026-05-02)
- Batch 5: 2 MPR screenshots in `resources/screenshots-ignored/more2/` (2026-05-02)

---

*Next pass: DESIGN.md — design system alignment, token system proposal, icon adoption plan*

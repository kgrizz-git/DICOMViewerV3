# DESIGN.md — MPDV Design Specification

**Project:** Medical Physics DICOM Viewer (MPDV)  
**Last updated:** 2026-05-17  
**Status:** Active — maintained alongside the [UX Assessment Remediation Plan](dev-docs/plans/supporting/UX_ASSESSMENT_REMEDIATION_AND_DESIGN_SYSTEM_PLAN.md)

This document is the single source of truth for visual design, interaction design, and naming conventions across the application. All UI code and QSS changes must be consistent with what is defined here. When this document conflicts with the code, update the code; when the code introduces a new pattern, document it here before the change is merged.

> **Goal spec, not current state.** DESIGN.md describes the design we are *building toward*. The code is the ground truth for what is currently implemented. The [UX remediation plan](dev-docs/plans/supporting/UX_ASSESSMENT_REMEDIATION_AND_DESIGN_SYSTEM_PLAN.md) tracks which goals have been implemented and which remain open. When a design goal is implemented, mark it done in the plan — not here. When design intent changes, update this document (the spec), not the plan.

---

## 0. Design Inspirations

MPDV does not follow any single design system wholesale — it is a Qt desktop application, not a web or mobile app, so direct adoption of web-first systems like M3 is impractical. Instead, specific ideas and philosophies are borrowed from three well-regarded systems. This section records what we take from each and why, so future contributors understand the reasoning behind design decisions rather than treating them as arbitrary.

---

### 0.1 Material Design 3 (Google)
**Reference:** https://m3.material.io/

M3 is Google's current design language, used across Android and Google's web products. It is primarily a mobile/web system, but several of its ideas translate directly to dense desktop UIs.

**What we borrow:**

- **Color roles over literal values.** M3 defines colors by their semantic role — primary, on-primary, surface, on-surface, error, warning — rather than as raw hex codes. This is why `DESIGN.md` uses named tokens (`--accent`, `--danger`, `--bg-surface`, etc.) instead of hardcoding colors in QSS. When a color needs to change (e.g. the accent shifts from blue to teal), one token changes and the whole app updates consistently.
- **Severity-coded feedback.** M3 uses distinct colors and icons for error, warning, and informational states. Our toast notification spec (left-border color + icon per severity) follows this pattern directly.
- **Progressive disclosure.** M3 recommends keeping top-level surfaces simple and revealing complexity on demand — submenus, expandable sections, and dialogs rather than enormous flat lists. This is the principle behind reorganizing the View menu and right-click context menu into grouped sections and submenus.
- **No disabled items without explanation.** M3 advises against showing disabled controls with no indication of why they're disabled. Applied here: "Show Instances Separately" (permanently grayed out with no tooltip) is a violation of this principle and is flagged for a fix.

**What we don't take from M3:**

M3's elevation and surface-tinting model (where surfaces at different "heights" get progressively lighter tints of the primary color) is designed for mobile and doesn't adapt well to multi-panel desktop UIs with many simultaneous surfaces. We use flat surfaces with explicit border tokens instead.

---

### 0.2 IBM Carbon Design System
**Reference:** https://carbondesignsystem.com/

Carbon is the design system behind IBM's enterprise software products — dashboards, data tools, developer consoles. Of the three systems listed here, it is the most relevant to MPDV because it was explicitly designed for **data-dense, technical, professional UIs** — the same category as a medical imaging viewer.

**What we borrow:**

- **Overall philosophy: clarity over decoration.** Carbon is deliberately plain. It uses a neutral gray palette, minimal rounded corners, thin borders, and straightforward typography. This matches how a radiology or medical physics workstation should feel — professional, not flashy. Our dark/light theme palettes are roughly analogous to Carbon's G100 (near-black) and White themes.
- **Dense information layout.** Carbon components are designed to pack meaningful content into limited screen space without feeling cramped. This informs decisions like keeping toolbar icons at 20×20 px, using a compact type scale, and preferring thin separators over large padding between sections.
- **Token-based theming.** Carbon's token system (background, layer, layer-hover, border-strong, text-primary, text-secondary, etc.) directly inspired the color token table in `§2`. The naming philosophy — describe the *role*, not the color — is Carbon's.
- **Icon library.** Carbon Icons (`@carbon/icons`, Apache 2.0) is the best-matched free icon set for this app's domain. It includes ruler, measurement, zoom, pan, magnifier, cursor, data table, medical, and tool-category icons. It is listed as the preferred supplementary source alongside Material Symbols for any gaps in coverage.
- **Menu structure guidance.** Carbon's navigation patterns place layout and view controls prominently, with secondary configuration options in panels or dialogs — not buried at the bottom of a 25-item menu. This is the basis for the View menu reorganization spec in `§8.2`.

**What we don't take from Carbon:**

Carbon's full component library (dropdowns, data tables, modals) is React-based and doesn't map to Qt widgets. We borrow the philosophy and visual language, not the components.

---

### 0.3 Apple Human Interface Guidelines (HIG)
**Reference:** https://developer.apple.com/design/human-interface-guidelines/

Apple's HIG covers macOS, iOS, and cross-platform conventions. Even on Windows and Linux, the HIG is worth reading because it articulates *why* certain UI conventions exist — conventions that users of all platforms have internalized.

**What we borrow:**

- **Menu bar discipline.** HIG defines what belongs in each menu with unusual precision. The File menu is for file operations only (open, save, close, export). The Edit menu is for selection and clipboard operations scoped clearly. The Help menu ends with About. This is why "About this File" is being renamed and moved (it is not a Help item), and why "Edit Recent List" is considered out of place in File.
- **Hide rather than disable.** HIG recommends removing menu items that don't apply in the current context, rather than graying them out. It is more aggressive on this point than M3 or Carbon. Applied here: "Delete Selected" and "Delete All" should only be visible when there are ROIs to delete.
- **Toolbar conventions.** HIG strongly recommends icon-only or icon+label toolbars — text-only toolbars are not a recognized HIG pattern on any platform. This underpins the priority placed on adding toolbar icons (B1 in the remediation plan).
- **Keyboard shortcut hygiene.** HIG documents platform-standard shortcuts that must not be overridden — Cmd/Ctrl+A for Select All, Cmd/Ctrl+C for Copy, etc. The shortcut conflict audit (`§6`) follows this principle.
- **Toolbar tooltips must show shortcuts.** HIG and most platform guidelines agree: hovering a toolbar button should show its name and keyboard shortcut. Currently none of MPDV's toolbar tooltips show shortcuts; this is tracked as fix C8.

**What we don't take from HIG:**

HIG's visual style (rounded corners, translucency, system font, system controls) is macOS-native and should not be mimicked on Windows/Linux. We borrow the interaction and structural rules, not the visual appearance.

---

### 0.4 Summary: What each system contributes

| System | Primary contribution to MPDV |
|---|---|
| Material Design 3 | Color role system (tokens), severity feedback, progressive disclosure |
| IBM Carbon | Dense professional aesthetic, token naming, menu structure, icon library |
| Apple HIG | Menu bar discipline, hide-vs-disable, toolbar icon requirement, shortcut hygiene |

When a design decision is debated in the future, checking what these three systems recommend is a good starting point. Where they agree, follow them. Where they conflict, Carbon is usually the most relevant reference for this application category.

---

## 1. Product Identity

### 1.1 Canonical Name

| Context | Name |
|---|---|
| Window title bar | `MPDV` |
| About dialog | `Medical Physics DICOM Viewer (MPDV)` |
| Short label (icon tooltip, taskbar) | `MPDV` |
| Setup / installer display name | `Medical Physics DICOM Viewer` |
| Python package `name` field | `mpdv` |

> **Rationale:** The assessment identified two competing names ("DICOM Viewer V3" and "Medical Physics DICOM Viewer / MPDV"). A single canonical name reduces confusion and signals a professional product.  
> **Decision pending** — update this section once the name is finalized and strike the draft note.

---

## 2. Color Tokens

> **Goal palette.** These are the target values. The QSS files and the [UX plan](dev-docs/plans/supporting/UX_ASSESSMENT_REMEDIATION_AND_DESIGN_SYSTEM_PLAN.md) track how close the current code is to these goals.

All colors in QSS and Python UI code must reference one of these semantic tokens. Do not add literal hex values outside this table.

### 2.1 Dark Theme (primary)

The goal is a deep, modern dark palette — darker than the current code — with borders that are subtle rather than prominent. Surfaces are layered from nearly-black (inputs) up through panels to slightly lighter (hover), creating depth without heavy borders.

| Token | Goal hex | Usage |
|---|---|---|
| `--bg-window` | `#1e1e1e` | Main window, widget default background |
| `--bg-panel` | `#252525` | Toolbar, panel header background |
| `--bg-surface` | `#141414` | Input fields, list widgets, text areas, tree widgets |
| `--bg-surface-nav` | `#111111` | Series navigator — deepest dark layer |
| `--bg-surface-raised` | `#2e2e2e` | Button/item hover state |
| `--border` | `#363636` | Borders and separators — subtle, not dominant |
| `--border-focus` | `--accent` | Focus ring on inputs — always matches accent |
| `--fg-primary` | `#e0e0e0` | Primary text — off-white to reduce eye strain |
| `--fg-secondary` | `#a0a0a0` | Secondary / muted text, group-box titles |
| `--fg-disabled` | `#5a5a5a` | Disabled text and icons |
| `--accent` | *(from preset — see §2.4)* | Buttons active/pressed, menu selection, focus ring, slider fill |
| `--danger` | `#c0392b` | Privacy ON button background, error states, destructive actions |
| `--warning` | `#d68910` | Warning toasts, caution labels |
| `--success` | `#27ae60` | Success toasts |
| `--tooltip-bg` | `#2a2a2a` | Tooltip background |
| `--tooltip-fg` | `#e0e0e0` | Tooltip text |
| `--scrollbar-handle` | `#3a3a3a` | Scrollbar handle at rest |
| `--scrollbar-handle-hover` | `#4a4a4a` | Scrollbar handle on hover |

### 2.2 Light Theme

The light theme is intentionally conventional — neutral grays, no tinting. The tooltip uses a dark background (same as dark theme) for contrast consistency across themes.

| Token | Goal hex | Usage |
|---|---|---|
| `--bg-window` | `#f0f0f0` | Main window, widget default background |
| `--bg-panel` | `#e0e0e0` | Toolbar, panel header background |
| `--bg-surface` | `#ffffff` | Input fields, list widgets, text areas |
| `--bg-surface-nav` | `#d0d0d0` | Series navigator |
| `--bg-surface-raised` | `#d0d0d0` | Toolbar button/item hover; `#e8e8e8` for list-item hover |
| `--border` | `#c0c0c0` | Borders and separators |
| `--border-focus` | `--accent` | Focus ring on inputs |
| `--fg-primary` | `#000000` | Primary text |
| `--fg-secondary` | `#606060` | Secondary / muted text, group-box titles |
| `--fg-disabled` | `#a0a0a0` | Disabled text |
| `--accent` | *(from preset — same hex as dark theme)* | See §2.4 |
| `--danger` | `#c0392b` | Privacy ON, errors |
| `--warning` | `#d68910` | Warning |
| `--success` | `#27ae60` | Success |
| `--tooltip-bg` | `#3a3a3a` | Tooltip background — dark even in light theme |
| `--tooltip-fg` | `#ffffff` | Tooltip text |
| `--scrollbar-handle` | `#c0c0c0` | Scrollbar handle at rest |
| `--scrollbar-handle-hover` | `#a0a0a0` | Scrollbar handle on hover |

### 2.3 Shared / Theme-invariant

| Property | Value | Notes |
|---|---|---|
| Slider groove height | 4 px | Horizontal and vertical |
| Slider handle diameter | 12 px | Pill-shaped, accent-coloured |
| Splitter — hit zone | 5 px wide/tall | Must stay ≥ 5 px so it can be grabbed reliably |
| Splitter — visual at rest | 1 px centred line, `--border` colour | Hit zone is transparent; only the hairline is drawn |
| Splitter — visual on hover | Full 5 px fill, `--border` colour | Expands to fill hit zone — clear "grab me" signal |
| QGroupBox border | 1 px `--border`, 4 px radius | Title text in `--fg-secondary` |
| Scrollbar track width | 12 px | No arrow buttons |
| Toolbar separator | 1 px `--border` colour | |

**Splitter design rationale:** Visual borders elsewhere in the UI are 1 px. Splitter *hit zones* must be wider than that to be reliably draggable, but the visual indicator does not need to match the hit zone width. At rest the splitter looks like any other 1 px separator; on hover it expands to signal interactivity. This keeps the UI visually consistent — everything that is not interactive stays at 1 px — without sacrificing usability.

### 2.4 Accent Colour Presets

The accent colour is user-selectable via **Settings → Accent colour**. QSS uses three placeholder tokens — `{accent}`, `{accent_light}` (dark-theme hover), `{accent_dark}` (light-theme hover) — substituted at stylesheet-load time by `gui.accent_presets`. The preset ID is persisted in config as `"accent"`.

| ID | Label | `{accent}` | `{accent_light}` | `{accent_dark}` | Notes |
|---|---|---|---|---|---|
| `steel-blue` | Steel Blue | `#4285da` | `#5a9de5` | `#1a5da5` | **Default** |
| `violet` | Violet | `#7c4dff` | `#9e72ff` | `#5530cc` | |
| `navy` | Navy | `#1565c0` | `#2979ff` | `#0d47a1` | Clearly darker blue |
| `garnet` | Garnet | `#a0303f` | `#c94050` | `#6e1f2b` | Dark wine-red; distinct from `--danger #c0392b` |

To add a new preset: add an entry to `ACCENT_PRESETS` in `src/gui/accent_presets.py` and add a row here.

---

## 3. Typography

### 3.1 Font

| Role | Family | Fallback |
|---|---|---|
| UI primary | IBM Plex Sans | system-ui, sans-serif |
| Monospace (DICOM tags, values) | IBM Plex Mono | Consolas, monospace |
| Overlay (on image) | IBM Plex Sans | (no fallback — set programmatically) |

Open Sans and Noto Sans must not appear in the UI. The Annotation Options dialog currently loads them via system font fallback; fix by explicitly constructing `QFont("IBM Plex Sans", ...)` on each widget.

### 3.2 Type Scale

| Name | Size (px) | Size (pt) | Weight | Usage |
|---|---|---|---|---|
| caption | 11 px | ~8 pt | 400 | Axis labels, status bar secondary text |
| body | 13 px | ~10 pt | 400 | Default widget text, list items |
| label-bold | 13 px | ~10 pt | 600 | Dialog section headings, key labels |
| heading | 15 px | ~11 pt | 600 | Dialog titles, panel headings |

### 3.3 Qt Font Sizing Notes

Qt supports two sizing modes and they behave differently across platforms and DPI settings:

- **Point size** (`QFont("IBM Plex Sans", 10)` or `QFont.setPointSize(10)`) — scales automatically with the system DPI. This is Qt's default and the right choice for most UI text. At 96 DPI (standard Windows), 10 pt ≈ 13 px.
- **Pixel size** (`QFont.setPixelSize(13)`) — absolute screen pixels, does not scale with DPI. Use only when you need exact pixel alignment (e.g. overlay text rendered onto a medical image where pixel precision matters).

**Rule:** Use **point sizes** for all standard UI widgets (labels, buttons, menus, dialogs). Use pixel sizes only for the image overlay font. The pt column in §3.2 gives the equivalent values at 96 DPI — use those when constructing `QFont` objects in code.

The app currently sets the application-wide font in one place (search for `setFont` on `QApplication`). Prefer adjusting the app-wide font there rather than setting fonts on individual widgets, which creates maintenance debt. Override only where a specific widget genuinely needs to differ (e.g. monospace for the tag viewer).

---

## 4. Iconography

### 4.1 Library

**Status: TBD** — icon library selection and toolbar button set are being finalized in Phase 3–4 of the [UX remediation plan](dev-docs/plans/supporting/UX_ASSESSMENT_REMEDIATION_AND_DESIGN_SYSTEM_PLAN.md) (steps E1 and F1–F4). Do not hard-code any icon paths or library choices until that process is complete.

**Candidate collections** (all Apache 2.0 or MIT — free for commercial use):

| Collection | License | Count | Style options | Best for |
|---|---|---|---|---|
| Material Symbols (Google) | Apache 2.0 | 2,500+ | Outlined, Rounded, Sharp; variable weight/fill | Broad coverage, universal recognition |
| Phosphor Icons | MIT | 6,000+ | Thin, Light, Regular, Bold, Fill, Duotone | Measurement, science, geometry icons |
| Tabler Icons | MIT | 5,500+ | Outline, Filled | Sharp, technical feel; consistent 24×24 viewbox |
| IBM Carbon Icons | Apache 2.0 | 1,000+ | Single style | Data/medical/tools semantic coverage; supplementary use |

**Goal:** offer users a choice of 2 icon styles from Settings (e.g. Outlined vs. Filled), sourced from the best-matched collection(s) per button. Final decision documented here after Phase 4 review.

**Delivery (interim):** Direct file paths from `resources/icons/<set-name>/` during development. Migrate to compiled `.qrc` before first packaged release.

**Size:** 20 × 20 px rendered; 24 px source SVG with 2 px padding.  
**Color:** `--fg-primary` token at rest; `--accent` for active/checked state.

### 4.2 Toolbar Button Set

**Status: draft — pending E1 finalization.** The button set below is the working proposal. Exact contents, ordering, and which buttons are toolbar vs. menu-only must be confirmed in step E1 before icon sourcing begins.

| # | Button | Status | Notes |
|---|---|---|---|
| 1 | Open | Draft | Consider split button: left = Open File, dropdown = Open Folder / Recent |
| 2 | Export / Save | Draft | |
| — | *(separator)* | | |
| 3 | Privacy Toggle | Draft | Safety-critical; red background when ON |
| — | *(separator)* | | |
| 4 | Pan | Draft | |
| 5 | Window / Level | Draft | |
| 6 | Zoom | Draft | Single tool; scroll/drag to zoom; replaces separate Zoom In + Zoom Out |
| 7 | Reset View | Draft | |
| — | *(separator)* | | |
| 8 | Measure Distance | Draft | |
| 9 | Measure Angle | Draft | |
| 10 | Ellipse ROI | Draft | |
| 11 | Rectangle ROI | Draft | |
| 12 | Text Annotation | Draft | |
| — | *(separator)* | | |
| 13 | Overlay Toggle | Draft | Cycle overlay visibility; equivalent to Spacebar |
| 14 | MPR | Draft | |
| 15 | Cine Play | Draft | |
| — | *(separator)* | | |
| 16 | Study Index | Draft | May move to menu-only — decide in E1 |
| 17 | Screenshot | Draft | May move to menu-only — decide in E1 |

**Removed from toolbar vs. original 22-button set:**
- Open Folder as a separate button — folded into Open split button or File menu only
- Zoom In / Zoom Out as separate buttons — replaced by single Zoom tool
- Free ROI — low frequency; available via context menu and Tools menu
- Sync Slices — available via View menu and right panel
- Font Color — moved to Overlay Settings dialog (plan B2)
- Use Rescaled Values — moved to right panel (plan B2)

### 4.3 Icon Map

**Status: placeholder** — populate after E1 (button set confirmed) and F4 (candidates reviewed). Do not treat these as final.

| Button | Candidate search terms |
|---|---|
| Open | folder_open, folder, open |
| Export / Save | save, download, export |
| Privacy ON | visibility_off, eye_slash, hide |
| Privacy OFF | visibility, eye |
| Pan | pan_tool, hand, move |
| Window / Level | contrast, brightness, tune, exposure |
| Zoom | zoom_in, magnify, search_plus |
| Reset View | fit_screen, fullscreen_exit, center_focus |
| Measure Distance | straighten, ruler |
| Measure Angle | architecture, angle |
| Ellipse ROI | radio_button_unchecked, circle |
| Rectangle ROI | crop_square, rectangle |
| Text Annotation | text_fields, title, edit_note |
| Overlay Toggle | layers, overlay, stack |
| MPR | view_in_ar, grid_view, 3d_rotation |
| Cine Play / Stop | play_circle, play_arrow / stop_circle |
| Study Index | table_view, list, database |
| Screenshot | photo_camera, camera |

---

## 5. Spacing & Sizing

| Component | Specification |
|---|---|
| Splitter hit zone | 5 px wide/tall — interactive width, not visual width |
| Splitter visual at rest | 1 px centred `--border` line; rest of hit zone transparent |
| Splitter visual on hover | Full 5 px fill at `--border` colour |
| Toolbar icon size | 20 × 20 px |
| Toolbar button padding | 4 px all sides |
| ROI resize handle | 8 × 8 px filled square (`HANDLE_HALF = 4.0` in `roi_manager.py`); currently hardcoded cyan — goal: `--accent` |
| Tooltip padding | 4 px H, 3 px V |
| Dialog minimum width | 400 px |
| Right panel minimum width | 250 px (before collapse) |
| Toast width | 300 px; left border 4 px severity color |

---

## 6. Keyboard Shortcuts

All shortcuts must be registered via `QAction.setShortcut()` or `QKeySequence.StandardKey`. Do not embed shortcut hints in label text.

### 6.1 Canonical Bindings

| Action | Shortcut | Notes |
|---|---|---|
| Open File | Ctrl+O | |
| Open Folder | Ctrl+Shift+O | |
| DICOM File Info | Ctrl+I | replaces "About this File" Ctrl+A |
| Select All | Ctrl+A | standard; must not be shadowed |
| Copy | Ctrl+C | annotation/ROI scope |
| Cut | Ctrl+X | annotation/ROI scope |
| Paste | Ctrl+V | annotation/ROI scope |
| Undo | Ctrl+Z | |
| Redo | Ctrl+Y | |
| Privacy Toggle | Ctrl+P | |
| Layout 1×1 | 1 | registered as `QAction` shortcut |
| Layout 1×2 / 2×1 | 2 | cycles between orientations |
| Layout 3-window | 3 | cycles between 3-window variants |
| Layout 2×2 | 4 | |
| Cycle Overlay | Space | |
| Zoom In | Ctrl++ | |
| Zoom Out | Ctrl+- | |
| Reset View | Ctrl+0 | |

> Shortcut table must be kept complete; add new bindings here before implementing them.

---

## 7. Interaction Patterns

### 7.1 Tool Modes & Cursors

Each viewport tool mode must set a distinct cursor on the viewport widget:

| Mode | Cursor |
|---|---|
| Pan | `Qt.OpenHandCursor` (dragging: `Qt.ClosedHandCursor`) |
| Window/Level | `Qt.SizeVerCursor` |
| Zoom | `Qt.SizeBDiagCursor` |
| Measure Distance | `Qt.CrossCursor` |
| Measure Angle | `Qt.CrossCursor` |
| ROI Draw | `Qt.CrossCursor` |
| Text Annotation | `Qt.IBeamCursor` |
| Default | `Qt.ArrowCursor` |

### 7.2 Drag-and-Drop

Show a dashed `--accent` border (2 px, rounded 4 px) over the viewport while DICOM files are dragged over it. Remove on drop or drag-leave.

### 7.3 Empty State

Cold-start status bar message: `"Open a DICOM file or folder to begin  (File → Open  or drag here)"`

### 7.4 Toast Notifications

Each toast has:
- Left border 4 px, colored by severity (`--success`, `--warning`, `--danger`, `--accent` for info)
- Icon 16 × 16 px (check, warning, error, info) to the left of the message text
- Auto-dismiss after 4 s (errors: 8 s or manual dismiss)

### 7.5 Privacy Toggle

- **Privacy ON:** toolbar button background `--danger`; label "Privacy ON — PHI Hidden"
- **Privacy OFF:** toolbar button background transparent / default; label "Privacy OFF — PHI Visible"

---

## 8. Menu Architecture

Each menu sketch shows the **target state** — what the menu should look like after plan fixes are applied. The current state is noted where it differs significantly.

### 8.1 File Menu

```
File
  ── Open File(s)…            Ctrl+O
  ── Open Folder…             Ctrl+Shift+O
  ─────────────────────────
  ▶ Recent
  ── Edit Recent List…
  ─────────────────────────
  ── Export…
  ── Export Screenshots…
  ── Export Cine…
  ── Save MPR as DICOM…
  ─────────────────────────
  ── Export Customizations…
  ── Import Customizations…
  ─────────────────────────
  ── Export Tag Presets…
  ── Import Tag Presets…
  ─────────────────────────
  ── Close
  ─────────────────────────
  ── Exit
```

**Current vs. target:** File menu currently also contains "Study Index Search" — this is duplicated in Tools. Per plan C3, remove it from one location; canonical home is File (it is a file/study opening operation).

**Notes:**
- "Edit Recent List…" is technically a management action rather than a file operation (HIG would prefer it elsewhere), but moving it would break familiarity — leave it here for now.
- Customization and tag preset import/export belong here: they are file operations even if not DICOM files.

### 8.2 Edit Menu

```
Edit
  ── Copy Annotation          Ctrl+C
  ── Cut Annotation           Ctrl+X
  ── Paste Annotation         Ctrl+V
  ─────────────────────────
  ── Undo Tag Edit            Ctrl+Z
  ── Redo Tag Edit            Ctrl+Y
```

**Current vs. target:**
- Currently contains a "Settings" item — Settings does not belong in Edit (per HIG, Edit is for selection and clipboard only). Settings is already accessible via its own dialog; remove the Edit menu shortcut to it or move it to a dedicated top-level menu if Settings grows.
- "Copy" / "Paste" labels currently have no scope qualifier — plan C1 adds "Annotation" suffix.
- "Cut Annotation" (Ctrl+X) is not yet implemented — plan item in TO_DO.md UX section.
- Undo/Redo are currently scoped to tag edits only, not annotations/ROIs — label should reflect this until general undo is implemented: "Undo Tag Edit" / "Redo Tag Edit".

### 8.3 Tools Menu

```
Tools
  ── View / Edit DICOM Tags…
  ── Export Tags…
  ── DICOM File Info…         Ctrl+I
  ── Study Index…
  ── Structured Report…
  ─────────────────────────
  ── Create MPR View…
  ── Histogram…
  ── Export ROI Statistics…
  ─────────────────────────
  ▶ ACR QA (pylinac)
      ACR CT Analysis (pylinac)…
      ACR MRI Analysis (pylinac)…
```

**Current vs. target:**
- "About this File…" renamed to "DICOM File Info…" with shortcut Ctrl+I (plan B3).
- ACR tools grouped under "ACR QA (pylinac) ▶" submenu (plan D2).
- "Study Index Search" removed if it is deduplicated from here to File only (plan C3).

### 8.4 View Menu

```
View
  ── Reset View               Ctrl+0
  ─────────────────────────
  ▶ Theme
      Dark
      Light
  ▶ Layout
      1×1   (1)
      1×2   (2)
      2×1   (2)
      2×2   (4)
  ▶ Orientation
      Flip Horizontal
      Flip Vertical
      ──────────────
      Rotate CW
      Rotate CCW
      Rotate 180°
      ──────────────
      Reset Orientation
  ─────────────────────────
  ── Left Pane               ✓
  ── Right Pane              ✓
  ── Series Navigator        ✓
  ── Navigator Frame Count   ✓
  ── Window Map              ✓
  ── Fullscreen
  ─────────────────────────
  ── Overlay Tags Config…
  ── Overlay Settings…
  ── Annotation Options…
  ── Smooth when Zoomed      ✓
  ── Scale Markers           ✓
  ── Direction Labels        ✓
  ── Scale Markers Color…
  ── Direction Labels Color…
  ── Slice Slider            ✓
  ── Show Instances Separately  (disabled — tooltip needed)
  ─────────────────────────
  ▶ Slice Sync
      Enable Slice Sync      ✓
      Manage Sync Groups…
  ▶ Show Slice Location Lines
      [options]
  ─────────────────────────
  ┌─ PRIVACY ──────────────────
  │  Privacy Mode             ✓
  └────────────────────────────
```

**Current vs. target:** This is the most over-crowded menu in the app (25+ items). The target above groups items with separators but does not yet move items to submenus beyond what already exists. A future pass could consolidate the overlay/display group further. Privacy is isolated with separators above and below — the compliance signal.

### 8.5 Help Menu

```
Help
  ── Quick Start Guide…
  ── Documentation…
  ── Disclaimer…
  ─────────────────────────
  ── About
```

**Current vs. target:**
- "Documentation (browser)…" renamed to "Documentation…" (plan D8).
- "Fusion Technical Documentation" removed from top level — move to a help link inside the Fusion/Fuse tab (plan D8).

### 8.6 Context Menu (right-click on viewport)

```
  ── Window / Level presets
  ── Reset View
  ─────────────────────────
  ▶ Tools
      Pan, Zoom, Measure Distance, Measure Angle,
      Ellipse ROI, Rectangle ROI, Free ROI,
      Text Annotation, …  (all tool modes)
  ─────────────────────────
  ▶ Annotations
      Copy Annotation
      Paste Annotation
      Delete Selected
      Delete All
  ─────────────────────────
  ── Toggle Overlay Detail
  ── Overlay Tags Configuration…
```

**Current vs. target:** Currently ~40 flat items. Plan C4 groups tool modes under "Tools ▶" and annotation actions under "Annotations ▶".

```
Tools
  ── DICOM File Info…        Ctrl+I
  ── Overlay Tags Config…    Ctrl+Shift+L
  ─────────────────────────
  ── [measurement tools]
  ── [ROI tools]
  ─────────────────────────
  ▶ ACR QA
      ACR MRI Analysis…
      ACR CT Analysis…
      …
  ─────────────────────────
  ── Study Index…
```

### 8.2 View Menu Groups

```
View
  ── [Layout: 1×1, 1×2, 2×1, 2×2]
  ─────────────────────────
  ── Left Pane             (checkmark)
  ── Right Pane            (checkmark)
  ─────────────────────────
  ── Overlay               (checkmark)
  ── Overlay Detail        (checkmark)
  ── Show Instances Separately
  ─────────────────────────
  ── Slice Sync…
  ─────────────────────────
  ┌─ PRIVACY ─────────────────
  │  Privacy Mode           (checkmark)
  └───────────────────────────
```

### 8.3 Context Menu (right-click on viewport)

```
  ── Window / Level actions
  ── Reset View
  ─────────────────────────
  ▶ Tools
      Pan, Zoom, Measure Distance, …  (13 items)
  ─────────────────────────
  ▶ Annotations
      Copy, Paste, Delete Selected, Delete All
  ─────────────────────────
  ── Toggle Overlay Detail
  ── Overlay Tags Configuration…
```

---

## 9. Naming Conventions

| Old label | Canonical label | Notes |
|---|---|---|
| About this File… | DICOM File Info… | shortcut Ctrl+I |
| Privacy is OFF | Privacy OFF — PHI Visible | status label |
| Privacy is ON | Privacy ON — PHI Hidden | status label |
| Documentation (browser)… | Documentation… | drop "(browser)" |
| Fusion Technical Documentation | (move to Fusion tab help link) | not a top-level Help item |
| Vanilla pylinac (stock ACRCT) | Stock pylinac mode (ACRCT) | ACR CT dialog checkbox — "vanilla" is internal jargon |
| Vanilla pylinac (stock ACRMRILarge) | Stock pylinac mode (ACRMRILarge) | ACR MRI dialog checkbox |
| Vanilla equivalent | Stock pylinac mode | MRI compare result dialog column header |
| Cycle overlay detail / legacy toggle | Toggle Overlay Detail | context menu |
| Overlay Configuration | Overlay Tags Configuration… | context menu — must match menu bar |
| Default (Space) | Default tag set (Spacebar) | Overlay Tags Config dialog |
| Overlay mode_modality | Overlay Mode / Modality | raw identifier — fix display label |
| Window/Zoom/ROI (tab) | Window · Zoom · ROI | use middle dot to reduce visual noise |
| Show/Hide Left Pane | Left Pane ✓ | checkmark replaces Show/Hide prefix |
| Show/Hide Right Pane | Right Pane ✓ | same |

**Labels to keep as-is (do not rename):**

| Label | Reason |
|---|---|
| ACR MRI (pylinac)… / ACR CT (pylinac)… | Keep "(pylinac)" — intentional attribution to the pylinac library |
| Sanity multiplier | pylinac's own parameter name (`low_contrast_visibility_sanity_multiplier`) — matches the underlying API |

---

## 10. Accessibility (baseline)

- Every interactive widget must have an accessible name (`setAccessibleName()`).
- All icon-only buttons must have a tooltip with text + keyboard shortcut.
- Minimum touch/click target: 24 × 24 px.
- Color must not be the only differentiator for state (use icon + color).
- High-contrast theme: deferred — track in TO_DO.md.

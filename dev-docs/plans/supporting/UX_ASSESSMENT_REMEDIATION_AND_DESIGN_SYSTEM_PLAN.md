# UX Assessment Remediation & Design System Plan

**Created:** 2026-05-03  
**Source:** [ux-summary.md](../../dev-docs/ux-assessments/ux-summary.md) · [ux-assessment-overall-2026-04-30.md](../../dev-docs/ux-assessments/ux-assessment-overall-2026-04-30.md)  
**Design reference:** [DESIGN.md](../../DESIGN.md)  
**TO_DO section:** UX / Workflow

This plan addresses all P0, P1, and selected P2 findings from the 2026-04-30 UX assessment, and defines the steps to produce `DESIGN.md` as the canonical design specification for the project.

---

## Part A — Design System (prerequisite for consistent fixes)

Goal: produce `DESIGN.md` at the repo root with a living specification for color tokens, typography, spacing, iconography, and interaction patterns. Fixes in Parts B–D must conform to it.

### A1 — Define color tokens [ ]

- Audit current QSS dark and light theme files; extract every literal color value.
- Resolve the inconsistency: dark theme uses blue slider accent; light theme uses purple/violet.
- Decide on a single accent color (recommendation: blue, `#2979FF` or equivalent); update both themes.
- Replace the dated `#ffffdc` tooltip background with a token that matches the overall palette.
- Document all tokens in `DESIGN.md § Color tokens`.

### A2 — Define type scale [ ]

- Choose one UI font: IBM Plex Sans (already used as the primary); remove Open Sans and Noto Sans from Annotation Options dialog by forcing `QFont` programmatically rather than relying on system fallback.
- Ensure overlay font defaults to IBM Plex Sans, not Liberation Sans.
- Define a minimal type scale (caption 11 px, body 13 px, label-bold 13 px/600, heading 15 px) and document in `DESIGN.md § Typography`.

### A3 — Define icon strategy [ ]

- Select one icon library (recommendation: Material Symbols or IBM Carbon).
- Map all 22 toolbar actions to specific named icons from that library; document the map in `DESIGN.md § Iconography`.
- Decide and document the icon delivery mechanism (bundled SVG, Qt resource `.qrc`, or font-based).

### A4 — Define spacing & sizing tokens [ ]

- Document splitter handle target width (≥ 6 px visible hit zone).
- Document ROI handle size (≥ 10 × 10 px).
- Document toolbar row height and overflow policy.
- Document minimum tab label width and truncation policy.

### A5 — Write DESIGN.md [ ]

- Compile A1–A4 into `DESIGN.md` (see structure in that file).
- Link from `README.md` and `CLAUDE.md` so contributors can find it.

---

## Part B — P0 Bugs (every session)

### B1 — Add toolbar icons [ ]

**Issue:** All 22 tool buttons are text-only.  
**Steps:**
- After A3 is done, bundle selected icons into a Qt resource (`icons.qrc`) or load from a `resources/icons/` directory.
- Replace each `QPushButton`/`QAction` text-only initialization with `setIcon(QIcon(...))` + `setToolButtonStyle(Qt.ToolButtonIconOnly)` (or `TextBesideIcon` if labels are needed for accessibility).
- Keep full text as tooltip fallback.

### B2 — Fix toolbar overflow (two rows) [ ]

**Issue:** "Font Color" and "Use Rescaled Values" overflow to a second row.  
**Steps:**
- Move "Font Color" out of the main toolbar into the Overlay Settings dialog (it is a low-frequency control).
- Convert "Use Rescaled Values" to a `QCheckBox` embedded in the right panel (Window/Zoom/ROI tab) so it no longer consumes toolbar space.
- Verify toolbar fits in a single row at 1280 px width.

### B3 — Fix Ctrl+O and Ctrl+A shortcut conflicts [ ]

**Issue:** Ctrl+O assigned to both Open File and Overlay Tags Config; Ctrl+A shadows Select All.  
**Steps:**
- Assign Overlay Tags Config a unique shortcut (e.g. Ctrl+Shift+O).
- Rename "About this File…" menu item to "DICOM File Info…" (also fixes P1 naming issue).
- Re-bind its shortcut to Ctrl+I (Info).
- Audit all shortcuts against the table in `DESIGN.md § Keyboard shortcuts`; add all bindings to that table.

### B4 — Widen splitter handles [ ]

**Issue:** 2 px splitter handles are invisible and nearly impossible to grab.  
**Steps:**
- Subclass `QSplitter` or apply QSS `QSplitter::handle { width: 6px; height: 6px; }` plus a hover/drag background color token from the design system.
- Add grip dots (2 × 3 array of 2 px dots, 50 % opacity) via `paintEvent` override or SVG background in QSS.

### B5 — Fix "overlay mode_modality" raw identifier [ ]

**Issue:** Raw Python attribute name shown in the Overlay Tags Configuration dialog.  
**Steps:**
- Locate the label source; replace with "Overlay Mode / Modality" or remove if it is merely a placeholder.

### B6 — Unify slider accent color [ ]

**Issue:** Light theme uses purple/violet; dark theme uses blue.  
**Steps:**
- Apply the single accent token from A1 to `QSlider::groove:horizontal::sub-page` in both theme QSS files.

### B7 — Settings dialog dark-theme rendering [ ]

**Issue:** Settings dialog renders white interior; suspected light-theme stylesheet leakage.  
**Steps:**
- Verify the `QDialog` subclass applies the active palette (not a hard-coded light QSS block).
- Test in both themes; document result.

### B8 — Unify app name [ ]

**Issue:** "DICOM Viewer V3" in title bar vs "Medical Physics DICOM Viewer / MPDV" in About dialog.  
**Steps:**
- Decide on canonical name (document choice in `DESIGN.md § Product identity`).
- Apply consistently: `QMainWindow.setWindowTitle`, About dialog, `setup.cfg`/`pyproject.toml` `name`, installer config, icon tooltip.

---

## Part C — P1 Ergonomic / Discoverability Fixes

### C1 — Label copy/paste/undo scope [ ]

Add scope qualifiers to Edit menu items: e.g. "Copy Annotation", "Paste Annotation", "Undo (Annotation/ROI)", or prefix with "Edit:" as a submenu grouping.

### C2 — View menu reorganization [ ]

**Issue:** 25+ items across 7 categories; Privacy View not separated.  
**Steps:**
- Group into logical sections with `addSeparator()`:
  1. Layout (grid modes, pane toggles)
  2. Overlays & annotations
  3. Slice sync / link
  4. Privacy (separator before and after — isolation is the compliance signal)
  5. Preferences
- Cap each section at ≤ 8 items; move low-frequency items to submenus if needed.
- Remove redundant "Show/Hide" prefix from pane toggles (P2, low effort, do it now).

### C3 — Flatten Study Index Search duplication [ ]

Remove the duplicate "Study Index Search" from the Tools menu; keep it only in File. Or vice versa — pick one canonical location.

### C4 — Reduce right-click context menu depth [ ]

**Issue:** ~40 items flat; 13 tool modes.  
**Steps:**
- Group the 13 tool modes under a "Tools ▶" submenu.
- Group annotation/ROI actions under "Annotations ▶" submenu.
- Rename "Cycle overlay detail / legacy toggle" → "Toggle Overlay Detail".
- Align "Overlay Configuration" label with the menu-bar name "Overlay Tags Configuration…".

### C5 — Series navigator: show series descriptions [ ]

Replace truncated UIDs in navigator labels with `SeriesDescription` (fallback to `Modality + SeriesNumber` if empty, then UID last resort).

### C6 — Fix font consistency in Annotation Options dialog [ ]

Force IBM Plex Sans via `QFont` on all widgets inside the dialog at construction time; remove implicit system-font reliance.

### C7 — Fix "Default (Space)" overlay tag label [ ]

Replace cryptic placeholder with human-readable text, e.g. "Default layout" or "Default tag set (Spacebar)".

### C8 — Add keyboard shortcut display to toolbar tooltips [ ]

Set `QAction.setToolTip("<action name> (<shortcut>)")` for all toolbar actions that have a bound key.

### C9 — Privacy label clarity [ ]

Change "Privacy is OFF" → "Privacy OFF — PHI Visible" (and "Privacy is ON" → "Privacy ON — PHI Hidden").

### C10 — Status bar empty-state guidance [ ]

Replace "Ready" cold-start message with "Open a DICOM file or folder to begin (File → Open or drag here)".

### C11 — Tool-mode cursor feedback [ ]

Set a per-mode cursor on the viewport widget (`setCursor(Qt.CrossCursor)` for measurement, `Qt.OpenHandCursor` for pan, etc.) whenever the active tool mode changes.

### C12 — Histogram / chart axis label size [ ]

Increase axis label font size to ≥ 11 px in all chart/histogram widgets.

### C13 — SR Dose table column truncation [ ]

- Fix column headers: "tAcquisition plan", "DateTime start" etc.
- Set `QHeaderView` `ResizeToContents` or assign minimum widths so "Field" column does not clip every row.
- Replace "Parse hit node … | No" with user-friendly text ("No matching node found").

### C14 — Conditional "Delete Selected" / "Delete All" visibility [ ]

Show "Delete Selected" only when at least one ROI is selected; show "Delete All" only when at least one ROI exists. Use `QAction.setEnabled()` tied to the ROI model's count signal.

### C15 — MPR crosshair / reference lines [ ]

When an MPR pane is paired with source panes, draw the intersection line of the MPR cut plane onto each source pane. See §12.23 of full assessment for detail.

---

## Part D — P2 Polish / Learnability (selected)

Lower urgency; address opportunistically alongside related P0/P1 work.

### D1 — Move "(pylinac)" out of user-facing labels [ ]

Strip "(pylinac)" from ACR tool names, dialog titles, and button labels. Replace "Vanilla pylinac" with "Standard analysis"; replace "Sanity multiplier" with "Validation threshold".

### D2 — Group ACR / QA tools in Tools menu [ ]

Add an "ACR QA ▶" submenu under Tools containing all pylinac/ACR entries.

### D3 — Toast notification severity icons [ ]

Add a small icon (info, warning, error) and tint the left border of each toast to the corresponding severity color token.

### D4 — Drag-and-drop target indicator [ ]

Show a dashed border on the viewport when the user drags files over it.

### D5 — Lime green overlay color default [ ]

Change default overlay font color from lime green to white (`#FFFFFF`) or light gray (`#CCCCCC`).

### D6 — "Combine/Fuse" tab rename [ ]

Separate the slab combination and image fusion features into distinct tabs, or rename to "Slab / Fuse" with a visible divider between the two feature groups inside the tab.

### D7 — Layout shortcut registration [ ]

Register layout shortcuts (1, 2, 3, 4) via `QAction.setShortcut()` instead of embedding them in label text.

### D8 — "Documentation (browser)…" label cleanup [ ]

Rename to "Documentation…"; move "Fusion Technical Documentation" to a "Help ▶" submenu or a tooltip link inside the Fusion tab.

### D9 — QGroupBox theming [ ]

Apply explicit QSS for `QGroupBox` title and border so it is not left to the OS/platform style.

---

## Verification gates

1. **A5 done** before any B/C/D work starts — ensures all fixes reference the spec.
2. **B1, B2, B3 done** before any release candidate build.
3. All P0 items (B1–B8) resolved and manually tested in both dark and light themes.
4. Toolbar fits single row at 1280 px in both themes (screenshot evidence).
5. No duplicate shortcut bindings in the shortcut table in `DESIGN.md`.
6. SR Dose table renders without truncation at default dialog width (screenshot evidence).
7. QSS lint pass: no remaining literal color values outside the token definitions.

---

## File references (key implementation files)

Locate these via `grep` or the codebase directly:

- Main QSS theme files — search for `dark_theme.qss` / `light_theme.qss`
- Toolbar builder — search for `QToolBar` or `addAction` near `toolbar`
- Menu builder — `main_window_menu_builder.py`
- Context menu — search for `QMenu` + `exec_` in viewer widgets
- Series navigator — search for `SeriesNavigator` or `navigator`
- Toast — search for `toast` or `notification`
- Splitter — search for `QSplitter`
- Overlay settings — search for `OverlaySettings` or `overlay_settings`

# DESIGN.md — MPDV Design Specification

**Project:** Medical Physics DICOM Viewer (MPDV)  
**Last updated:** 2026-05-03  
**Status:** Draft — being populated as part of [UX Assessment Remediation Plan](dev-docs/plans/supporting/UX_ASSESSMENT_REMEDIATION_AND_DESIGN_SYSTEM_PLAN.md)

This document is the single source of truth for visual design, interaction design, and naming conventions across the application. All UI code and QSS changes must be consistent with what is defined here. When this document conflicts with the code, update the code; when the code introduces a new pattern, document it here before the change is merged.

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

All colors in QSS and Python UI code must reference one of these tokens. Do not use literal hex values outside of this table.

### 2.1 Dark Theme (primary)

| Token | Hex | Usage |
|---|---|---|
| `--bg-window` | `#1E1E1E` | Main window background |
| `--bg-panel` | `#252526` | Side panel, toolbar background |
| `--bg-surface` | `#2D2D2D` | Dialog, card, list item background |
| `--bg-surface-raised` | `#3C3C3C` | Hover / selected surface |
| `--border` | `#3F3F46` | Borders, separators |
| `--fg-primary` | `#D4D4D4` | Primary text |
| `--fg-secondary` | `#9CDCFE` | Secondary / muted text, labels |
| `--fg-disabled` | `#6A6A6A` | Disabled text |
| `--accent` | `#2979FF` | Buttons, active state, slider fill, checkbox, focus ring |
| `--accent-hover` | `#448AFF` | Accent on hover |
| `--accent-pressed` | `#1565C0` | Accent on press |
| `--danger` | `#F44336` | Privacy ON button, error states, destructive actions |
| `--warning` | `#FF9800` | Warning toasts, caution labels |
| `--success` | `#4CAF50` | Success toasts |
| `--menu-hover` | `#094771` | Menu bar item hover |
| `--tooltip-bg` | `#3C3C3C` | Tooltip background |
| `--tooltip-fg` | `#D4D4D4` | Tooltip text |

### 2.2 Light Theme

| Token | Hex | Usage |
|---|---|---|
| `--bg-window` | `#F3F3F3` | Main window background |
| `--bg-panel` | `#FFFFFF` | Side panel, toolbar background |
| `--bg-surface` | `#FAFAFA` | Dialog, card |
| `--bg-surface-raised` | `#E8E8E8` | Hover / selected surface |
| `--border` | `#C8C8C8` | Borders, separators |
| `--fg-primary` | `#1E1E1E` | Primary text |
| `--fg-secondary` | `#5F5F5F` | Secondary text |
| `--fg-disabled` | `#A0A0A0` | Disabled text |
| `--accent` | `#2979FF` | Same accent as dark — single source of truth |
| `--accent-hover` | `#1565C0` | Accent on hover (inverted vs dark) |
| `--danger` | `#D32F2F` | Privacy ON, errors |
| `--warning` | `#E65100` | Warning |
| `--success` | `#388E3C` | Success |
| `--tooltip-bg` | `#424242` | Tooltip background (dark even in light theme for contrast) |
| `--tooltip-fg` | `#FFFFFF` | Tooltip text |

> **Slider accent note:** Both themes use `--accent` (`#2979FF`) for slider sub-page fill. The purple/violet light-theme slider is a bug; fix it in `light_theme.qss`.

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

| Name | Size | Weight | Usage |
|---|---|---|---|
| caption | 11 px | 400 | Axis labels, status bar secondary text |
| body | 13 px | 400 | Default widget text, list items |
| label-bold | 13 px | 600 | Dialog section headings, key labels |
| heading | 15 px | 600 | Dialog titles, panel headings |

---

## 4. Iconography

### 4.1 Library

**Selected library:** Material Symbols (Outlined variant)  
**Delivery:** Bundled SVGs in `resources/icons/material/`; loaded via Qt resource system (`.qrc`).  
**Size:** 20 × 20 px rendered; use 24 px source SVG with 2 px padding.  
**Color:** Use `--fg-primary` token; override to `--accent` for active/checked state.

### 4.2 Toolbar Action → Icon Map

| Action | Material Symbol name | Notes |
|---|---|---|
| Open File | `folder_open` | |
| Open Folder | `drive_folder_upload` | |
| Save / Export | `save` | |
| Privacy Toggle | `visibility` / `visibility_off` | swap on state change |
| Zoom In | `zoom_in` | |
| Zoom Out | `zoom_out` | |
| Pan | `pan_tool` | |
| Reset View | `fit_screen` | |
| Window / Level | `contrast` | |
| Measure Distance | `straighten` | |
| Measure Angle | `architecture` | |
| Ellipse ROI | `radio_button_unchecked` | |
| Rectangle ROI | `crop_square` | |
| Free ROI | `gesture` | |
| Text Annotation | `text_fields` | |
| Cine Play | `play_circle` | |
| MPR | `view_in_ar` | |
| Sync Slices | `sync` | |
| Overlay Toggle | `layers` | |
| Use Rescaled Values | `tune` | move to right panel (B2) |
| Screenshot | `photo_camera` | |
| Study Index | `table_view` | |

> Remaining mappings TBD during implementation. Icon name must be confirmed against the material-symbols repo before shipping.

---

## 5. Spacing & Sizing

| Component | Specification |
|---|---|
| Splitter handle hit zone | ≥ 6 px wide/tall; grip dots (2 × 3, 2 px each, 50 % opacity) centered |
| Splitter handle hover color | `--bg-surface-raised` |
| Toolbar icon size | 20 × 20 px |
| Toolbar button padding | 4 px all sides |
| ROI resize handle | 10 × 10 px filled square, `--accent` color |
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
| Overlay Tags Config | Ctrl+Shift+L | |
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

> Conflicts to resolve: Ctrl+A (fixed by B3). Shortcut table must be kept complete; add new bindings here before implementing them.

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

### 8.1 Tools Menu Groups

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
| ACR MRI (pylinac)… | ACR MRI Analysis… | drop "(pylinac)" |
| ACR CT (pylinac)… | ACR CT Analysis… | drop "(pylinac)" |
| Vanilla pylinac | Standard analysis | in ACR dialogs |
| Sanity multiplier | Validation threshold | in ACR dialogs |
| Cycle overlay detail / legacy toggle | Toggle Overlay Detail | context menu |
| Overlay Configuration | Overlay Tags Configuration… | context menu — must match menu bar |
| Default (Space) | Default tag set (Spacebar) | Overlay Tags Config dialog |
| Overlay mode_modality | Overlay Mode / Modality | raw identifier — fix display label |
| Window/Zoom/ROI (tab) | Window · Zoom · ROI | use middle dot to reduce visual noise |
| Show/Hide Left Pane | Left Pane ✓ | checkmark replaces Show/Hide prefix |
| Show/Hide Right Pane | Right Pane ✓ | same |

---

## 10. Accessibility (baseline)

- Every interactive widget must have an accessible name (`setAccessibleName()`).
- All icon-only buttons must have a tooltip with text + keyboard shortcut.
- Minimum touch/click target: 24 × 24 px.
- Color must not be the only differentiator for state (use icon + color).
- High-contrast theme: deferred — track in TO_DO.md.

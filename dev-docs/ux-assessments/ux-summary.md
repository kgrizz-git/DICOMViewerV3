# UX Assessment — Priority Summary

**Full assessment:** [ux-assessment-overall-2026-04-30.md](ux-assessment-overall-2026-04-30.md)  
**33 screenshots · Code + QSS analysis · Completed 2026-05-02**

Actionable findings only. Each "Details" link jumps to the relevant section of the full assessment.

---

## P0 — Bugs / Affects Every Session

| Issue | Details |
|---|---|
| **No toolbar icons** — all 22 tool buttons are text-only | [§4][s4] · [§12.8][s12_8] |
| **Toolbar wraps to two rows** — "Font Color" and "Use Rescaled Values" overflow | [§4][s4] · [§12.8][s12_8] |
| **Ctrl+O conflict** — Open File and Overlay Tags Config share the same shortcut | [§11.7][s11_7] |
| **Ctrl+A conflict** — "About this File" shadows platform-standard Select All | [§11.7][s11_7] |
| **2px splitter handles** — invisible, impossible to grab precisely | [§3.1][s3_1] |
| **"Overlay mode_modality" raw identifier** shown in dialog UI | [§12.9][s12_9] |
| **Light theme purple/violet slider accent** — undocumented; inconsistent with the blue dark-theme token | [§12.1][s12_1] · [§12.12][s12_12] |
| **Settings dialog renders with OS light theme** — white interior; needs verification in dark theme (screenshot may have been captured in light theme mode) | [§12.10][s12_10] |
| **App has two names** — "DICOM Viewer V3" (title bar) vs "Medical Physics DICOM Viewer / MPDV" (About dialog, icon) | [§12.17][s12_17] |

---

## P1 — High Priority: Ergonomic / Discoverability

| Issue | Details |
|---|---|
| "Copy" / "Paste" / "Undo" / "Redo" scope not labelled — applies to annotations, ROIs, and tags; labels give no hint which objects are affected | [§11.3][s11_3] |
| "About this File…" in Tools menu — Ctrl+A conflict; rename to "DICOM File Info…" or add qualifier to remove ambiguity with Select All | [§11.5][s11_5] |
| Study Index Search duplicated across File and Tools menus | [§11.2][s11_2] · [§11.5][s11_5] |
| View menu has 25+ items across 7 conceptual categories — requires scrolling | [§11.4][s11_4] |
| Privacy View not visually separated in View menu — compliance-critical item mixed with display options | [§11.4][s11_4] |
| Right-click context menu has ~40 items — requires scrolling; flat structure makes it hard to scan | [§12.5][s12_5] |
| 13 tool modes listed flat in right-click menu — group into a "Tools ▶" submenu to reduce depth without removing access | [§12.5][s12_5] |
| Overlay text default density — size and content are configurable, but defaults may overwhelm new users; consider lighter out-of-box defaults | [§10.2][s10_2] · [§10.5][s10_5] |
| "Delete Selected" / "Delete All" visible when no ROIs exist — visual noise, invites accident | [§10.1][s10_1] · [§12.1][s12_1] |
| "Use Rescaled Values" not visually checkable; on second toolbar row | [§4][s4] · [§12.8][s12_8] |
| "Font Color" on second toolbar row — low-frequency control using prime real estate | [§12.8][s12_8] |
| Series navigator labels are truncated UIDs, not series descriptions | [§12.3][s12_3] |
| Three different font families in Annotation Options dialog — IBM Plex Sans, Open Sans, Noto Sans | [§12.7][s12_7] |
| "Default (Space)" combobox label in Overlay Tags Configuration is cryptic | [§12.9][s12_9] |
| Settings dialog contains only 1 setting; redirects to menus for everything else | [§12.10][s12_10] |
| "Move Up" / "Move Down" in Edit Recent List — reordering by hand vs. auto-recency is confusing | [§12.11][s12_11] |
| **No reference/crosshair lines between MPR and source panes** | [§12.23][s12_23] |
| SR Dose events column headers truncated — "tcquisition plan", "DateTime starter" etc. | [§12.20][s12_20] |
| SR Dose summary "Field" column too narrow — truncates every field name | [§12.21][s12_21] |
| SR Dose summary "Parse hit node … \| No" is raw internal language | [§12.21][s12_21] |
| "Privacy is OFF" label could be "Privacy OFF — PHI Visible" for clarity | [§10.1][s10_1] · [§12.4][s12_4] |
| No type scale defined — inconsistent text hierarchy throughout | [§2.2][s2_2] |
| No cursor change on tool mode switch — no per-mode visual feedback | [§6.1][s6_1] |
| Status bar shows "Ready" on cold start — no empty-state onboarding guidance | [§5][s5] · [§12.1][s12_1] |
| Toolbar tooltips do not show keyboard shortcuts | [§4][s4] · [§6.3][s6_3] |
| Histogram and chart axis labels are very small | [§10.4][s10_4] |

---

## P2 — Medium Priority: Polish / Learnability

| Issue | Details |
|---|---|
| "Show/Hide Left Pane" / "Show/Hide Right Pane" — "Show/Hide" is redundant (checkmark communicates it) | [§11.4][s11_4] |
| "Show Instances Separately" permanently disabled with no tooltip explaining why | [§11.4][s11_4] |
| Layout shortcuts (1, 2, 3, 4) embedded in label text rather than `setShortcut()` | [§11.4][s11_4] |
| "(pylinac)" in ACR tool names and dialog titles — implementation detail in user-facing labels | [§11.5][s11_5] · [§12.14][s12_14] · [§12.15][s12_15] |
| "Vanilla pylinac" and "Sanity multiplier" in ACR dialogs — developer jargon | [§12.14][s12_14] · [§12.15][s12_15] |
| ACR QA tools ungrouped alongside everyday utilities in Tools menu | [§11.5][s11_5] |
| "Fusion Technical Documentation" as a top-level Help item — should be contextual | [§11.6][s11_6] |
| "Documentation (browser)…" — "(browser)" is an implementation detail | [§11.6][s11_6] |
| Light tooltip color `#ffffdc` — dated; inconsistent with overall theme | [§2.1][s2_1] |
| `QGroupBox` unthemed — cross-platform inconsistency | [§2.1][s2_1] |
| Splitter handles have no visual affordance (no grip dots, no hover highlight) | [§3.1][s3_1] |
| Right panel tab label "Window/Zoom/ROI" is three concepts — verbose | [§3.4][s3_4] |
| No drag-and-drop target indicator on the viewport | [§6.2][s6_2] |
| Toast notifications have no icon or severity color — all messages look equal | [§6.4][s6_4] |
| ROI resize handles are small dots — difficult with fine-motor impairments | [§10.5][s10_5] |
| "Cycle overlay detail / legacy toggle" label exposes internal terminology | [§12.5][s12_5] |
| "Overlay Configuration" in context menu differs from "Overlay Tags Configuration…" in menu bar | [§12.5][s12_5] |
| "(45 non-DICOM skipped)" in status bar is jargon for clinical users | [§12.2][s12_2] |
| Overlay font defaults to Liberation Sans, not IBM Plex Sans | [§12.6][s12_6] |
| Lime green as default overlay font color — should be white or light gray | [§12.6][s12_6] |
| "Add to Simple" / "Add to Detailed" buttons redundant with the center arrow buttons | [§12.9][s12_9] |
| Combine/Fuse tab covers two distinct feature domains (slab combination ≠ image fusion) | [§12.4][s12_4] |
| "Slice sync group strip height (px)" exposed at top level — should be collapsed "Advanced" | [§12.6][s12_6] |
| SR Dose summary has no "Hide empty rows" toggle (CTDIvol / DLP / SSDE are empty) | [§12.21][s12_21] |
| SR dialog title very long — may clip on smaller screens | [§12.19][s12_19] |
| No MPR-specific controls in right panel when an MPR pane is focused | [§12.22][s12_22] |
| MPR creation only discoverable via right-click and Tools menu — not on toolbar | [§12.23][s12_23] |

---

## Positive Foundations

- Privacy red toolbar button — correct safety pattern; red state impossible to miss in both themes  
- Dark and light themes — both clean and professionally calibrated; dark appropriate for radiology  
- Menu bar styling (dark bg, blue hover, clean separators) — most polished surface in the app  
- ROI rendering (cyan ellipses, yellow measurement line) — distinctive and clear  
- Floating dialogs (Histogram, Slice Sync) — coexist correctly without obscuring critical content  
- Cine playback (Play / Stop / Loop) — active-state blue highlight is clean and functional  
- "Filter tags…" in metadata panel — strong affordance for a dense list  
- IBM Plex Sans — excellent technical font choice for primary UI  
- Multi-window grid (1×1 to 2×2) — strong clinical workflow differentiator  
- Quick Start Guide — in-app rich-text viewer with search, Prev/Next, and section navigation  
- Structured Report dialog — four-tab structure; row↔Document cross-linking; CSV/XLSX export  
- Overlay Tags Configuration dual-list widget — sophisticated and correct pattern  
- MPR integrated into multi-window grid — first-class viewport, correct direction labels, cine works  
- Help menu structure — nearly HIG-standard; best-organized menu in the app  
- Encryption note in Settings — right security transparency for a medical app  

---

## Section Map

| Section | Topics covered |
|---|---|
| [§1][s1] | App architecture, three-panel layout overview |
| [§2][s2] | Theming tokens, typography, iconography (the icon gap) |
| [§3][s3] | Splitter layout, center panel, left/right panels, series navigator |
| [§4][s4] | Toolbar contents, all 22 actions, icon roadmap |
| [§5][s5] | Status bar three-section layout |
| [§6][s6] | Mouse modes, drag-and-drop, keyboard shortcuts, toast |
| [§7][s7] | Accessibility gaps (no accessible names, no high-contrast theme) |
| [§8][s8] | M3 / Carbon / Apple HIG design system comparison |
| [§9][s9] | Icon library recommendations (Carbon, Material Symbols) |
| [§10][s10] | Visual findings — batch 1 screenshots (cold start, menus, annotations, overlays) |
| [§11][s11] | Full menu bar deep-dive: File, Edit, View, Tools, Help, shortcut conflicts |
| [§12][s12] | Visual findings — batches 2–5 (light theme, SR dialog, MPR, settings, ACR, context menu, …) |
| [§13][s13] | **This file** — priority summary tables |
| [§14][s14] | Screenshot coverage log |
| [§15][s15] | Tools used, screenshot batch index |

---

<!-- Reference-style link definitions -->
[s1]: ux-assessment-overall-2026-04-30.md#1-application-architecture-overview
[s2]: ux-assessment-overall-2026-04-30.md#2-visual-design
[s2_1]: ux-assessment-overall-2026-04-30.md#21-theming
[s2_2]: ux-assessment-overall-2026-04-30.md#22-typography
[s3]: ux-assessment-overall-2026-04-30.md#3-layout--structural-ux
[s3_1]: ux-assessment-overall-2026-04-30.md#31-three-panel-splitter-layout
[s3_4]: ux-assessment-overall-2026-04-30.md#34-right-panel--tabbed-controls
[s4]: ux-assessment-overall-2026-04-30.md#4-toolbar-assessment
[s5]: ux-assessment-overall-2026-04-30.md#5-status-bar
[s6]: ux-assessment-overall-2026-04-30.md#6-interaction-design
[s6_1]: ux-assessment-overall-2026-04-30.md#61-mouse-interaction-model
[s6_2]: ux-assessment-overall-2026-04-30.md#62-drag-and-drop
[s6_3]: ux-assessment-overall-2026-04-30.md#63-keyboard-shortcuts
[s6_4]: ux-assessment-overall-2026-04-30.md#64-toast-notifications
[s7]: ux-assessment-overall-2026-04-30.md#7-accessibility
[s8]: ux-assessment-overall-2026-04-30.md#8-design-system-comparison-preview
[s9]: ux-assessment-overall-2026-04-30.md#9-icon-resources
[s10]: ux-assessment-overall-2026-04-30.md#10-visual-findings-from-screenshots
[s10_1]: ux-assessment-overall-2026-04-30.md#101-empty--cold-start-state-002101
[s10_2]: ux-assessment-overall-2026-04-30.md#102-loaded-state--dual-pane-with-ct--photo-002253
[s10_4]: ux-assessment-overall-2026-04-30.md#104-annotation-options-dialog--histogram-002551
[s10_5]: ux-assessment-overall-2026-04-30.md#105-rois-drawn--slice-sync-dialog-002649
[s11]: ux-assessment-overall-2026-04-30.md#11-menu-bar-deep-dive
[s11_2]: ux-assessment-overall-2026-04-30.md#112-file-menu
[s11_3]: ux-assessment-overall-2026-04-30.md#113-edit-menu
[s11_4]: ux-assessment-overall-2026-04-30.md#114-view-menu
[s11_5]: ux-assessment-overall-2026-04-30.md#115-tools-menu
[s11_6]: ux-assessment-overall-2026-04-30.md#116-help-menu
[s11_7]: ux-assessment-overall-2026-04-30.md#117-cross-cutting-menu-issues
[s12]: ux-assessment-overall-2026-04-30.md#12-visual-findings-from-new-screenshots-batches-2-3--4--2026-05-02
[s12_1]: ux-assessment-overall-2026-04-30.md#121-light-theme--cold-start-232107
[s12_2]: ux-assessment-overall-2026-04-30.md#122-dicom-tag-viewer-dialog-and-series-navigator-232501
[s12_3]: ux-assessment-overall-2026-04-30.md#123-series-navigator-close-up-233854
[s12_4]: ux-assessment-overall-2026-04-30.md#124-combinefuse-tab-and-cine-playback-233936-234016
[s12_5]: ux-assessment-overall-2026-04-30.md#125-right-click-context-menu-deep-dive-234100
[s12_6]: ux-assessment-overall-2026-04-30.md#126-overlay-settings-dialog-234825
[s12_7]: ux-assessment-overall-2026-04-30.md#127-annotation-options--font-inconsistency-234902
[s12_8]: ux-assessment-overall-2026-04-30.md#128-toolbar-overflow--two-rows-confirmed-235112
[s12_9]: ux-assessment-overall-2026-04-30.md#129-overlay-tags-configuration-dialog-235159
[s12_10]: ux-assessment-overall-2026-04-30.md#1210-settings-dialog-001155
[s12_11]: ux-assessment-overall-2026-04-30.md#1211-edit-recent-list-dialog-001345-001359
[s12_12]: ux-assessment-overall-2026-04-30.md#1212-light-theme--loaded-state-with-ct-image-and-rois-001542
[s12_14]: ux-assessment-overall-2026-04-30.md#1214-acr-mri-options-dialog-001718
[s12_15]: ux-assessment-overall-2026-04-30.md#1215-acr-ct-options-dialog-001744
[s12_17]: ux-assessment-overall-2026-04-30.md#1217-about-dialog-001835
[s12_19]: ux-assessment-overall-2026-04-30.md#1219-structured-report-dialog--document-tab-004749
[s12_20]: ux-assessment-overall-2026-04-30.md#1220-structured-report-dialog--dose-events-tab-004848
[s12_21]: ux-assessment-overall-2026-04-30.md#1221-structured-report-dialog--dose-summary-tab-004914
[s12_22]: ux-assessment-overall-2026-04-30.md#1222-mpr-view--sagittal-single-pane-012434-mpr
[s12_23]: ux-assessment-overall-2026-04-30.md#1223-mpr-view--sagittal--axial-side-by-side-012652-mpr2
[s13]: ux-assessment-overall-2026-04-30.md#13-summary-key-findings
[s14]: ux-assessment-overall-2026-04-30.md#14-screenshots-still-needed
[s15]: ux-assessment-overall-2026-04-30.md#15-tools-used

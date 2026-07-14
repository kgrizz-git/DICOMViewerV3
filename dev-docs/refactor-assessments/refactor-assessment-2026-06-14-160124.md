# Refactor Assessment - 2026-06-14 16:01:24

## Assessment Date
- **Date**: 2026-06-14
- **Assessor**: Claude (AI agent)
- **Scope**: Repo-wide line-count scan of non-backup Python under `src/`; focused, scored
  analysis of the highest-value targets. **Analysis only — no code changed.**
- **Python threshold**: 600 lines (template guideline). Prior run:
  [`refactor-assessment-2026-05-25-025057.md`](refactor-assessment-2026-05-25-025057.md).

---

## Progress since 2026-05-25 (notable shrinkage — refactoring is working)

| File | 2026-05-25 | Now | Δ | Note |
|------|-----------:|----:|---|------|
| `src/main.py` | 3024 | **2374** | −650 | continued `core/actions/` extraction |
| `src/qa/pylinac_runner.py` | 1247 | **<600** | −650+ | split into `pylinac_acr_ct/_acr_mri/_nuclear` |
| `src/core/subwindow_lifecycle_controller.py` | 1552 | **846** | −706 | lifecycle split |

The QA-runner split is a **model to replicate**: one dispatcher + per-analysis modules. It directly
helped this week's pydicom-3 validation and the nuclear NaN guard (single dispatcher chokepoint).

---

## Files exceeding threshold (49 files > 600 lines)

Top of the list (full list available via `find src -name '*.py' | xargs wc -l | sort -rn`):

| # | File | Lines | Classes | Methods | Notes |
|---|------|------:|:-------:|:-------:|-------|
| 1 | `src/main.py` | 2374 | 1 | ~210 | composition root (God object), shrinking |
| 2 | `src/gui/main_window.py` | 1749 | 1 | 71 | God-widget |
| 3 | `src/gui/volume_viewer_widget.py` | 1726 | 1 | 68 | **14 section headers** (clear seams) |
| 4 | `src/gui/mpr_controller.py` | 1650 | 1 | 33 | 10 section headers |
| 5 | `src/gui/image_viewer_view.py` | 1386 | 1 | 47 | dense, no section markers |
| 6 | `src/gui/slice_display_manager.py` | 1322 | 1 | 28 | long methods |
| 7 | `src/gui/overlay_manager.py` | 1267 | 2 | 29 | |
| 8 | `src/tools/roi_manager.py` | 1246 | 2 | 36 | |
| 9 | `src/tools/annotation_manager.py` | 1215 | 1 | 19 | ~64 lines/method (very long methods) |
| 10 | `src/gui/dialogs/tag_export_dialog.py` | 1195 | 1 | 29 | dialog holding export logic |
| … | (39 more between 602–1189) | | | see scan |

---

## Detailed analysis (focused, highest-value)

### 1. `src/gui/volume_viewer_widget.py` (1726) — **best ROI extraction target**
**Why first:** largest *single-class* widget after main_window, but it already has **14 section
headers** marking cohesive groups (camera/controls, rendering pipeline, opacity/transfer function,
event handling, export). Section markers = pre-identified, low-risk seams.

**Opportunity:** extract non-Qt rendering/transfer-function logic into helpers
(`volume_render_pipeline.py`, `volume_transfer_function.py`) and keep the QWidget as a thin view that
wires signals to those helpers. Model on the existing `core/volume_opacity_model.py` split.

- **Ease** 4/5 (seams already marked) · **Safety** 3/5 (3D path, fewer unit tests) ·
  **Practicality** 4/5 · **Recommendation** 4/5 · **Overall 3.75** · **Priority: High**

### 2. `src/gui/main_window.py` (1749, 71 methods) — God-widget
**Opportunity:** it pairs with `main.py` as the other coordination hub. Extract menu/toolbar wiring
(already partly in `main_window_menu_builder.py`, `main_window_toolbar_builder.py`) fully out, and
move status-bar / W-L-readout / overlay-toggle clusters into small mixins or controller helpers
(`main_window_status_controller.py`). Keep `main_window` as layout + signal surface.

- **Ease** 3/5 · **Safety** 3/5 (central UI) · **Practicality** 4/5 · **Recommendation** 4/5 ·
  **Overall 3.5** · **Priority: High**

### 3. `src/gui/mpr_controller.py` (1650, 10 section headers)
**Opportunity:** sectioned already; split per-plane reslice math and the cine/scroll handling into
`mpr_reslice.py` (pure, testable) vs the controller (Qt + state). Aligns with existing `core/mpr_*`
modules (`mpr_volume`, `mpr_builder`).

- **Ease** 3/5 · **Safety** 3/5 · **Practicality** 4/5 · **Recommendation** 4/5 · **Overall 3.5** ·
  **Priority: High**

### 4. `src/tools/annotation_manager.py` (1215, only 19 methods ⇒ ~64 lines/method)
**Why notable:** the **long-method** smell (high lines-per-method) more than file size. Methods likely
do parse+validate+mutate+repaint in one. Extract per-annotation-type serialization and hit-testing
into helpers; shorten methods. Pairs with `annotation_paste_handler.py` (866) and
`measurement_items.py` (865).

- **Ease** 3/5 · **Safety** 3/5 · **Practicality** 3/5 · **Recommendation** 3/5 · **Overall 3.0** ·
  **Priority: Medium**

### 5. `src/gui/dialogs/tag_export_dialog.py` (1195, 29 methods) — logic-in-dialog
**Why notable:** the file/writer logic already moved to `core/tag_export_writer.py` (+ this week's
`spreadsheet_safety` centralization). The **dialog still holds selection/variation-analysis logic**
that isn't UI. Extract a `tag_export_controller.py` (pure: selection model, variation analysis) so the
dialog is presentation-only and the logic is unit-testable without Qt.

- **Ease** 4/5 · **Safety** 4/5 (logic is separable, well-tested writer already) ·
  **Practicality** 4/5 · **Recommendation** 4/5 · **Overall 4.0** · **Priority: High**

### 6. `src/gui/image_viewer_view.py` (1386, 47 methods, no section markers)
**Why notable:** dense and **unsectioned** — hardest to navigate. First low-cost step is *not* a split
but adding section markers + grouping; then extract the coordinate-transform / fit-to-window math into
a pure helper. Treat as Medium until seams are marked.

- **Ease** 2/5 · **Safety** 2/5 (core viewport, heavy interaction) · **Practicality** 3/5 ·
  **Recommendation** 3/5 · **Overall 2.5** · **Priority: Medium (stage it)**

### Perennial: `src/main.py` (2374)
Already covered in prior assessments and actively shrinking via `core/actions/`. Continue the planned
extraction of remaining `_on_*` signal clusters into `core/handlers/` (fusion, slice-sync,
study-navigation). Not re-scored here — see 2026-05-25 assessment Opportunity 1.

---

## Cross-cutting patterns & observations

1. **Replicate the QA-runner split pattern.** `pylinac_runner` → dispatcher + per-analysis modules is
   the cleanest recent refactor and made the dispatcher a single guard chokepoint (used for the nuclear
   NaN guard). Apply the same "thin coordinator + focused modules" shape to `main_window`/`main.py`.
2. **Centralize-then-reuse is paying off.** `core/spreadsheet_safety.py` (this week) deduped 3 copies
   of formula-injection logic. Look for the same opportunity in: ROI/measurement serialization
   (`roi_export_service`, `measurement_items`, `annotation_manager`) and DICOM tag formatting.
3. **Logic-in-dialog** recurs (`tag_export_dialog`, `annotation_options_dialog` 795,
   `overlay_config_dialog` 749, `export_dialog` 668). Extracting pure controllers/models from dialogs
   is repeatable, low-risk, and improves testability without Qt.
4. **Long-method smell** (`annotation_manager` ~64 lpm, `slice_display_manager`) matters more than raw
   line count — prioritize method decomposition there.
5. **Coordinator/facade proliferation** (`*_coordinator.py`, `*_facade.py`) is healthy delegation, but
   watch for thin pass-through wrappers that just forward to `main.py` — fold those back or give them
   real responsibility.

---

## Prioritized recommendations

### High (Overall ≥ 3.5)
1. **`tag_export_dialog` → extract pure `tag_export_controller`** — 4.0 (writer already split + tested;
   lowest-risk high-value).
2. **`volume_viewer_widget` → rendering/transfer-function helpers** — 3.75 (seams pre-marked).
3. **`main_window` → menu/toolbar/status controllers** — 3.5.
4. **`mpr_controller` → pure `mpr_reslice`** — 3.5.

### Medium (3.0–3.4)
5. **`annotation_manager` method decomposition** — 3.0.
6. **`image_viewer_view`** — stage it: add section markers first, then extract coord-transform math — 2.5.

### Continue (tracked elsewhere)
- `main.py` signal-cluster extraction into `core/handlers/` (per 2026-05-25 plan).

---

## Files appropriately large (refactor not recommended now)
- `src/utils/undo_redo.py` (1015): cohesive command framework; size is inherent to the command set.
- `src/core/rdsr_irradiation_events.py` (932): a faithful DICOM TID transcription; splitting hurts
  readability vs the standard.
- `src/tools/measurement_items.py` (865): a family of related QGraphics items; cohesive.

## Next steps
- [ ] Review priorities with user; pick 1–2 High items for an implementation plan (suggest starting
      with `tag_export_dialog` controller extraction — lowest risk, immediately testable).
- [ ] For each chosen item, create a `plans/supporting/*` plan with phased steps + tests before code.
- [ ] Re-run this assessment after the next batch to track shrinkage.

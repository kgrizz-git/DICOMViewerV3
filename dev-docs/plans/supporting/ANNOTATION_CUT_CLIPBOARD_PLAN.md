# Plan: Annotation Cut (Ctrl+X) — Edit Menu and Clipboard

**Created:** 2026-05-31  
**TO_DO:** UX / Workflow — *Ctrl+X does not cut ROIs/measurements/annotations like Ctrl+C / Ctrl+V* (confirmed in codebase).

---

## Goal and success criteria

### Goal

**Edit → Cut** and **Ctrl+X** (Cmd+X on macOS) copy the current selection to the annotation clipboard, then remove those items from the scene — matching standard desktop behavior and parity with existing **Copy** / **Paste**.

### Success criteria

| Check | Pass |
|-------|------|
| Cut with selection | Selected ROI(s), distance/angle measurement(s), crosshair(s), text, arrow(s) copied to clipboard and removed from view |
| Cut with no selection | Status: “No annotations selected” (same as copy) |
| Paste after cut | Paste recreates items; cut items do not remain on slice |
| Paste after cut (same slice) | No 10px offset — restores original scene coordinates (copy+same-slice paste still nudges 10px) |
| Undo | Cut is undoable where delete is already undoable (ROI, measurement, etc.) |
| Focus | Cut applies to **focused subwindow** only (same as copy/paste) |
| No regression | Copy, Paste, Delete key behavior unchanged |

---

## Context and links

### Backlog

`dev-docs/TO_DO.md` — UX / Workflow, Ctrl+X item (confirmed wiring gap).

### Current wiring (verified)

| Action | Menu | Shortcut | Handler |
|--------|------|----------|---------|
| Copy | Edit → Copy Annotation | `StandardKey.Copy` | `copy_annotation_requested` → `AnnotationPasteHandler.copy_annotations` |
| Paste | Edit → Paste Annotation | `StandardKey.Paste` | `paste_annotation_requested` → `paste_annotations` |
| Cut | **Missing** | **Not wired** | — |

Files:

- `src/gui/main_window_menu_builder.py` — Edit menu (~156–164): Copy + Paste only.
- `src/core/app_signal_wiring.py` — `wire_annotation_clipboard_signals` (~112–119): copy/paste only.
- `src/gui/main_window.py` — signals `copy_annotation_requested`, `paste_annotation_requested`; **no** `cut_annotation_requested`.
- `src/core/annotation_paste_handler.py` — `copy_annotations`, `paste_*` helpers; paste uses `ROICommand`, `MeasurementCommand`, etc. for **undo on paste**.
- `src/gui/keyboard_event_handler.py` — **Delete** removes selected items via `delete_roi_callback`, `delete_measurement_callback`, etc. (~158–194); does not intercept Ctrl+X (modifier check only on layout keys 1–4).

### Delete paths to reuse after copy

| Type | Delete entry point |
|------|-------------------|
| ROI | `roi_coordinator.handle_roi_delete_requested` / `roi_manager.delete_roi` |
| Measurement | `measurement_coordinator.handle_measurement_delete_requested` |
| Angle | Same measurement coordinator (AngleMeasurementItem) |
| Crosshair | `crosshair_coordinator.handle_crosshair_delete_requested` |
| Text | `text_annotation_coordinator.handle_text_annotation_delete_requested` |
| Arrow | `arrow_annotation_coordinator.handle_arrow_annotation_delete_requested` |

Paste already mirrors selection gathering in `get_selected_*` methods on `AnnotationPasteHandler`.

### Clipboard

- `src/utils/annotation_clipboard.py` — `copy_annotations`, `paste_annotations`, MIME/type `dicom_viewer_annotations`.
- Cut should call the same `copy_annotations` payload, then delete — **not** a separate clipboard format.

---

## Design

### `cut_annotations()` flow

1. Resolve focused subwindow (same guards as `copy_annotations`).
2. Collect selected ROIs, measurements, crosshairs, text, arrows via existing `get_selected_*`.
3. If total_count == 0 → status message; return.
4. Call `annotation_clipboard.copy_annotations(...)` with same arguments as copy.
5. Delete each selected item using the **same coordinators** as Delete key / context menu (preserves undo commands where implemented).
6. Update ROI list / statistics if ROI deleted; status: `Cut N annotation(s)`.

### Undo strategy

- **Preferred:** Each delete goes through coordinator paths that already push `ROICommand`, `MeasurementCommand`, etc.
- **Order:** Copy first (no scene change), then delete — if delete fails mid-way, clipboard still holds copy (acceptable; rare).
- **v2 (optional):** Single compound undo “Cut selection” — only if atomic undo is required; not needed for v1 if per-item undo matches Delete.

### UI

- Edit menu: **Cu&t Annotation** between Copy and Paste (platform convention).
- Shortcut: `QKeySequence(QKeySequence.StandardKey.Cut)`.
- Signal: `cut_annotation_requested` on `MainWindow`, wired like copy/paste in `app_signal_wiring.py` and `subwindow_signal_wiring.py` if focused handlers need it (copy/paste are app-global — same for cut).

### Out of scope

- System-wide OS clipboard (text/JSON export) — not required.
- Cut for tag editor / DICOM tree — separate app surface.
- Cut in 3D or MPR-only panes without annotation scene — same guards as copy.

---

## Implementation phases

### Phase 1 — Handler

- [x] (T1) Add `AnnotationPasteHandler.cut_annotations()` implementing copy-then-delete loop (owner: coder, parallel-safe: no, stream: none, after: none).
- [x] (T2) Extract small internal `_delete_selected_*` helpers if delete loop duplicates keyboard handler logic — optional; keep file &lt; 500 lines (owner: coder, parallel-safe: no, stream: none, after: T1). `_delete_selected_annotations` added.

### Phase 2 — Menu, signal, wiring

- [x] (T3) `main_window.py`: `cut_annotation_requested = Signal()` (owner: coder, parallel-safe: no, stream: none, after: T1).
- [x] (T4) `main_window_menu_builder.py`: Cut action + `StandardKey.Cut` (owner: coder, parallel-safe: no, stream: none, after: T3).
- [x] (T5) `app_signal_wiring.py`: connect cut signal to `cut_annotations` (owner: coder, parallel-safe: no, stream: none, after: T4).

### Phase 3 — Tests and docs

- [x] (T6) Add `tests/test_annotation_cut.py`: mock app, select ROI, cut → clipboard has data, ROI removed from manager dict (owner: coder, parallel-safe: yes, stream: none, after: T1).
- [ ] (T7) Manual smoke: copy/cut/paste/delete on one slice; undo after cut; **cut+paste same slice** at original position; **copy+paste same slice** still +10px (owner: tester, parallel-safe: no, stream: none, after: T5).
- [x] (T8) Update `user-docs` keyboard shortcut table if present; `CHANGELOG.md` patch entry (owner: coder, parallel-safe: no, stream: none, after: T7). Keyboard shortcuts dialog updated; manual smoke deferred to tester.

---

## Task graph and gates

- **T1 → T3–T5 → T6–T8** (T2 optional parallel after T1)
- **Gate G1:** Unit test green before manual smoke.
- **Gate G2:** Undo redo one cut on ROI and one measurement.

---

## Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Cut without undo on some types | Verify each coordinator’s delete path; add command if missing. |
| Multi-select partial failure | Delete in try/finally; log failures; status shows count deleted. |
| Ctrl+X in text annotation edit mode | If text editor focused, Qt may consume Cut for text — match Copy behavior (text tool may need `event.ignore()` pattern — verify in `text_annotation_tool`). |

---

## Modularity

- All logic in `annotation_paste_handler.py` + wiring only; no new top-level module required.

---

## Testing strategy

```text
.\.venv\Scripts\python.exe -m pytest tests/test_annotation_cut.py -v
```

Manual: [`dev-docs/orchestration/AGENT_SMOKE.md`](../orchestration/AGENT_SMOKE.md) annotation bullets if present.

---

## Questions for user

None blocking. Confirm whether **angle measurements** should be included in Cut (they are included in `get_selected_measurements` today).

---

## Completion notes

Implemented 2026-06-04: `cut_annotations` + `_delete_selected_annotations` in `annotation_paste_handler.py`; Edit → Cut Annotation (Ctrl+X); signal/wiring; `tests/test_annotation_cut.py` (2 tests green); keyboard shortcuts dialog + CHANGELOG 0.3.1. Manual smoke (T7) pending tester.

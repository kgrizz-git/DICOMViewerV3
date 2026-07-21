# Study Index — Recently-Indexed View & Easy Remove

**Status:** Done (2026-07-21) — both phases shipped on branch `chore/queue-followups`.
**Priority:** P1 (closes the "see and remove recently added studies" remainder of the first-launch opt-in item)
**Parent:** [Study index portability & encryption UI](STUDY_INDEX_PORTABILITY_AND_ENCRYPTION_UI_PLAN.md)

## Context / current state

The Study Index Search dialog (`src/gui/dialogs/study_index_search_dialog.py`) already has:
- An **Indexed** column (`indexed_at`) and **header-click server-side sorting**
  (`_on_header_section_clicked`, `search_grouped_studies(order_by=, descending=)`).
- A **single-row** Remove-from-index action (`_on_remove_from_index_clicked` →
  `_remove_study_at_row` → `index_service.delete_grouped_study`) plus a context-menu remove.

Missing for "easily see and remove recently added studies":
1. A **one-click** way to surface newest auto-adds (today you must open the dialog and
   click the Indexed header, possibly twice, to get descending order).
2. **Multi-select remove**, so a batch of unwanted auto-adds can be pruned at once.

No backend/query changes are required — reuse existing sort + `delete_grouped_study`.

## Phase 1 — "Recently indexed" quick view (UI only)

- Add a **Recently indexed** `QPushButton` to the existing `btn_row` (near *Check indexed
  studies…* / *Index folder…*).
- On click (`_on_recently_indexed_clicked`): clear all filter fields (`_patient_name`,
  `_patient_id`, `_modality`, `_accession`, `_study_desc`, `_date_from`, `_date_to`,
  `_global_fts`), set `self._sort_column_id = "indexed_at"` and `self._sort_descending = True`,
  call `_run_browse(reset=True)`, update the sort indicator, and select row 0 if present.
- Tooltip: "Clear filters and list studies newest-indexed first (most recent auto-adds at top)."
- Mention it in the dialog hint text.
- **Tests** (`tests/gui/test_study_index_search_dialog_sort.py` or a new file): clicking the
  button clears filter widgets and issues a query with `order_by="indexed_at"`,
  `descending=True`.

**Checkpoint:** ruff + `pytest tests/gui/test_study_index_search_dialog_sort.py` + repo harness. Coordinator commits.

## Phase 2 — Multi-select remove (depends on Phase 1)

- Change the table selection mode from `SingleSelection` to `ExtendedSelection`.
- Generalize remove to operate on **all selected rows**:
  - Collect distinct `(study_uid, study_root_path)` snapshots for every selected row.
  - One confirmation dialog: "Remove N study(ies) from the index? DICOM files are not
    deleted." — privacy-aware patient labels; list up to a few, summarize the rest.
  - Delete each via `delete_grouped_study`; reload once; report how many were removed.
  - Context menu label reflects count ("Remove N studies from index…").
- Keep **Open selected study** single-row (use the current/anchor row; if multiple are
  selected, act on the anchor and/or warn).
- **Tests**: multi-select remove deletes each selected study and reloads; single-row remove
  still works; cancel is a no-op; Open with a multi-selection stays sane.
- Docs: update user-docs study-index section + dialog hint; resolve the TO_DO "Remaining"
  note on the first-launch opt-in item; mark this plan **Done**.

**Checkpoint:** ruff + the study-index gui tests + repo harness. Coordinator commits, then pushes.

## Out of scope
- No `indexed_after` recency-window backend filter (descending sort + page 1 is sufficient).
- No bulk relocate (already covered by *Check indexed studies…*).

# Study Index — Browser Column, Integrity Scan & Portability (Execution Plan)

**Status:** Phases A, 3, and 2 complete (2026-07-21). Encryption toggle (parent Phase 1) and relative paths (parent Phase 4) remain backlog.
**Priority:** P1
**Parent plan:** [Study index portability & encryption UI](STUDY_INDEX_PORTABILITY_AND_ENCRYPTION_UI_PLAN.md) (this doc is the ordered execution breakdown for Phases A→2 below)
**Branch:** `feat/study-index-browser-integrity`

Ordered, agent-executable breakdown. Each phase is one or more commits with a
checkpoint (tests + a coordinator review) before the next phase begins. Do
**not** push; the coordinator pushes and opens the PR after Phase 2.

Shared files touched across phases (coordinate to avoid churn):
- `src/core/study_index/sqlcipher_store.py`
- `src/core/study_index/index_service.py`
- `src/gui/dialogs/study_index_search_dialog.py`
- `src/utils/config/study_index_config.py`

Conventions for every commit:
- Run the relevant tests (`QT_QPA_PLATFORM=offscreen PYTHONPATH=src python -m pytest <targets>`) before committing.
- Keep commits logically scoped (backend / UI / tests may be separate commits).
- Commit messages end with the trailer `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` (author email is already the GitHub noreply address — do not change it).
- `ruff check` and `python scripts/check_repo_harness.py` must pass (pre-commit hook enforces).

---

## Phase A — Indexed-date column + sortable headers

**Goal:** show when each study was last indexed, and let the user sort the
browser by clicking column headers. The schema already stores `indexed_at REAL`
(epoch seconds, `SCHEMA_VERSION = 3`), so **no migration** is needed — only
plumbing.

### A1 — Backend: return `indexed_at` and accept a sort order (commit 1)
- `sqlcipher_store.py::StudyIndexStore.search_grouped_studies`:
  - Add `MAX(e.indexed_at) AS indexed_at` to the grouped SELECT (last-indexed time for the study group).
  - Add optional params `order_by: str = "study_date"` and `descending: bool = True`. Validate `order_by` against a **whitelist** of grouped output columns (`study_date`, `patient_name`, `patient_id`, `accession_number`, `study_description`, `instance_count`, `series_count`, `indexed_at`); fall back to `study_date` for anything else (never interpolate raw user input into SQL). Build the `ORDER BY <col> ASC|DESC, patient_name ASC` clause from the validated column + direction.
- `index_service.py::LocalStudyIndexService.search_grouped_studies`: thread `order_by`/`descending` through to the store.
- **Tests** (`tests/test_study_index_store.py`): grouped result dicts contain `indexed_at`; a non-whitelisted `order_by` falls back to `study_date` (no SQL error / injection); ascending vs descending changes row order.

### A2 — Config: add the column id (commit 2, may fold into commit 3)
- `study_index_config.py`: add `"indexed_at"` to `STUDY_INDEX_BROWSER_COLUMN_IDS_DEFAULT` (place it after `study_date`). The existing order-normalization appends new ids after upgrades, so persisted orders survive.

### A3 — Dialog: label, formatting, sorting (commit 3)
- `study_index_search_dialog.py`:
  - `_COLUMN_LABELS["indexed_at"] = "Indexed"`.
  - `_StudyIndexGroupedModel.data`: format `indexed_at` (epoch float) as a local date/time string (e.g. `YYYY-MM-DD HH:MM`); empty string when missing. Add a helper next to the model.
  - Enable header-click sorting: `self._table.horizontalHeader().setSectionsClickable(True)` and `setSortIndicatorShown(True)`; connect `sectionClicked` → set the sort column id + toggle direction → re-run the browse query from the top (server-side sort via A1). Show the sort indicator on the active column. Preserve the current filters when re-querying.
  - Keep pagination ("Load more") consistent with the active sort (subsequent pages use the same `order_by`/`descending`).
- **Tests** (`tests/` new or extend an existing dialog/model test): model formats `indexed_at`; clicking a header re-queries with the expected `order_by`/`descending` (can assert against a fake service).

**Checkpoint A:** full study-index + dialog test subset green; coordinator eyeballs the diff. Then Phase 3.

---

## Phase 3 — Verify index (integrity scan + relocate/remove)

**Goal:** a button that finds indexed studies whose files are missing and lets
the user relocate or remove them. (TO_DO P1 "Allow a button in study index that
checks all indexed studies still exist…")

### 3.1 — Service: scan + relocate (commit 1)
- `index_service.py`:
  - `integrity_scan(progress=None) -> list[MissingStudyRecord]`: for each unique `(study_uid, study_root_path)`, check the root path exists and at least one member file exists on disk; collect studies with missing files. Use a small dataclass `MissingStudyRecord(study_uid, study_root_path, patient_name, study_date, modalities, missing_count, total_count)`. Read paths via the store (add a store helper if needed, e.g. `iter_study_groups()` / reuse `get_file_paths`).
  - `relocate_study(study_uid, old_root, new_root) -> int`: update `file_path`/`study_root_path` entries by replacing the `old_root` prefix with `new_root`; verify at least one relocated path exists before committing; return rows updated.
- **Tests** (`tests/test_study_index_integrity_scan.py`, new): seed a temp encrypted DB, delete some files, assert the scan reports the right missing studies; relocate rewrites paths; remove purges rows. Backend-only (no Qt).

### 3.2 — UI: Check button + results dialog (commit 2)
- `study_index_search_dialog.py`: add a **Check indexed studies…** button to the top button row. Run `integrity_scan` on a `QThread` with a modal progress dialog (can be many studies). Results dialog: table of missing studies; per-row **Relocate…** (folder picker → `relocate_study`) and **Remove from index** (reuse existing `delete_grouped_study`); bulk **Remove all missing**. Refresh the browse list after changes.
- Wire a **Relocate…** quick-action into the existing "files missing" warning shown on load-from-index (only if low-risk; otherwise defer to a follow-up).
- **Tests:** thread/handler logic where feasible with a fake service (mirror the existing `test_index_service`/dialog test style).

**Checkpoint 3:** integrity tests + dialog subset green; coordinator review. Then Phase 2.

---

## Phase 2 — About-this-index panel + Move / Export / Import

**Goal:** finish the portability surface (the **Open index location** button
already shipped).

### 2.1 — Service/store metadata (commit 1)
- `index_service.py` / `sqlcipher_store.py`: helpers for `row_count()`, DB file size on disk, last-modified time, encryption status (always on today), credential-store note.
- **Tests:** counts/size on a seeded DB.

### 2.2 — About-this-index panel (commit 2)
- Add an **About this index…** panel/dialog reachable from the Study Index dialog: DB path (clickable → reuse `open_study_index_location`), encryption status + credential-store location, row count, size on disk, last modified.

### 2.3 — Move / Export / Import (commit 3, may split)
- **Move index…**: file dialog → copy DB → `PRAGMA integrity_check` → update config path → delete old; confirm first.
- **Export index…**: CSV/JSON of **metadata + file paths only** (no pixel data), with an explicit label to that effect.
- **Import index…**: read a prior export and upsert rows (skip duplicates on `study_uid` + `file_path`).
- **Tests** (`tests/test_study_index_portability_ui.py`, new): move → reopen → search works; export → import round-trip preserves rows.

**Checkpoint 2:** full suite green. Coordinator pushes branch + opens PR. Mark
Phase A/3/2 done here and in the parent plan + TO_DO.

---

## Out of scope (remains backlog)
- Optional-encryption toggle + migration (parent plan Phase 1) — riskier, separate PR.
- Relative file paths for USB portability (parent plan Phase 4).

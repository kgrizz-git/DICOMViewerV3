# Canceled Folder Load Behavior Plan

**Status:** Done (2026-06-04)  
**Priority:** P1  
**TO_DO ref:** Bugs / Correctness — "Check what happens if loading a new folder with many files is canceled halfway through"

---

## Goal

Define and implement correct behavior when a user cancels a folder load midway, addressing three concerns:

1. **Viewer state:** What appears in the navigator and viewer after cancel?
2. **Study index:** Does a partial load auto-index incomplete data?
3. **Re-open:** When re-opening the same folder (recent menu or index), does the user get a full load or only the previously-loaded subset?

---

## Investigation findings (2026-06-04)

### Q1 — Partial auto-index on cancel?

**Before fix:** Yes. `run_load_pipeline` / `run_load_pipeline_async` continued with partial datasets and called `on_load_success` → `schedule_index_after_load`, indexing only files read before cancel.

**After fix:** No. `on_load_success(..., was_cancelled=True)` and `schedule_index_after_load(..., was_cancelled=True)` skip the encrypted index write. Partial data still organizes and displays in the viewer.

### Q2 — Re-open from study index vs recent?

| Entry point | Behavior |
|-------------|----------|
| **Recent menu** (folder) | `FileOperationsHandler.open_recent_file` → `load_directory` — **full folder rescan**. |
| **Study index** (before fix) | `StudyIndexSearchDialog._open_row` → `get_file_paths_for_study` → `open_paths(file list)` — **only paths stored in the DB** (incomplete if index was partial). |
| **Study index** (after fix) | When `study_root_path` is an existing directory, open via `open_paths([study_root])` → **`load_directory` full rescan** (same as recent folder). File-list path kept only when the study root is not a directory on disk. |

### Viewer on cancel

- **Some files loaded:** partial navigator/viewer state (unchanged — intentional).
- **Zero files loaded:** `(None, None)` / pipeline complete with null; status **"Loading cancelled."**

### Status bar (after fix)

Partial cancel: **"Loading cancelled — N of M file(s) loaded. Study index update skipped."** (or without M when totals unknown).

---

## Phase 1 — Investigation & verification

- [x] Code trace + findings documented above (2026-06-04).
- [ ] **Manual test** (optional): folder 100+ files, cancel ~30%; confirm DB has no new rows when auto-add on open is enabled.

## Phase 2 — Fix: suppress auto-index on partial load

- [x] `loading_pipeline.py`: `on_load_success(..., was_cancelled=...)`.
- [x] `index_service.py`: skip `schedule_index_after_load` when `was_cancelled`.

## Phase 3 — User feedback on cancel

- [x] Status bar via `format_cancelled_partial_status` (includes index skip note).
- [x] Zero-file cancel unchanged.

## Phase 4 — Re-open safety

- [x] Study index: folder rescan when `study_root_path` is a directory (`study_index_search_dialog.py`).
- [x] Recent menu: documented — `load_directory` full scan.

## Phase 5 — Tests

- [x] `tests/test_canceled_load_behavior.py` (pipeline flag + index skip + status helper).

---

## Open questions

1. **Should partial data display at all?** Current code continues with partial data on cancel, which is useful (user sees something). Recommend keeping this but just suppressing the index write.
2. **Warning on re-open?** If a user opens a previously-canceled folder, should we note "This folder was previously partially loaded"? Probably not — a fresh full load is the correct behavior and needs no warning.
3. **Large-file threshold interaction:** The TO_DO has a separate item about the large-file warning at 50 MB. That's independent but could share the progress/cancel UX.

---

## Files likely touched

| File | Change |
|------|--------|
| `src/core/loading_pipeline.py` | Pass `was_cancelled` to `on_load_success` or skip call |
| `src/core/study_index/index_service.py` | Respect cancel flag in `schedule_index_after_load` |
| `src/core/loading_progress_manager.py` | No change expected |
| `tests/test_canceled_load_behavior.py` | **New** |

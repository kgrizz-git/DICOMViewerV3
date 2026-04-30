# Study Index: Loading Only One Instance — Root Cause & Fix Plan

**Filed:** 2026-04-29  
**Priority:** P0  
**Related TO_DO item:** [TO_DO.md L32](../TO_DO.md#L32)

---

## 1. Problem Statement

When a user opens a study from the local study index browser (Study Index dialog), only **one DICOM instance/file** is loaded into the viewer — not the full study or series.

Expected behavior: all instances belonging to the selected study (and stored under its indexed folder root) are loaded, exactly as if the user had used File → Open Folder on the study's directory.

---

## 2. Root Cause — Confirmed

The bug is a **design gap** in the "Open" flow inside the Study Index search dialog.

### 2a. What `search_grouped_studies` returns

`StudyIndexStore.search_grouped_studies` (`src/core/study_index/sqlcipher_store.py`, line 395–435) produces one grouped row per `(study_uid, study_root_path)` pair.  The row includes:

```sql
MIN(e.file_path) AS open_file_path
```

`open_file_path` is an **arbitrary single file** — the alphabetically lowest path for that study group.  It is used as a stable default, not as "the whole study."

### 2b. What `_open_row` does with that path

`StudyIndexSearchDialog._open_row` (`src/gui/dialogs/study_index_search_dialog.py`, lines 450–459):

```python
def _open_row(self, row: int) -> None:
    path = self._model.open_path_for_row(row)   # → MIN(file_path): one file
    if not os.path.isfile(path):
        ...
    self._open_paths([path])                      # passes one-element list
    self.accept()
```

And `open_path_for_row` (`_StudyIndexGroupedModel`, line 174–178):

```python
def open_path_for_row(self, row: int) -> str:
    p = (self._rows[row].get("open_file_path") or "").strip()
    return p
```

### 2c. What the loader does

`self._open_paths([path])` emits `open_files_from_paths_requested` → `FileOperationsHandler.open_paths` → `DICOMLoader.load_files([single_path])`.

Result: only that one file is read.  The viewer loads exactly 1 instance.

### 2d. Why `study_root_path` is not used

`study_root_path` **is** present in each grouped row (it is a GROUP BY key), and it is a directory path that was recorded as the `source_dir` at index time.  The existing folder-loading code path (`DICOMLoader.load_directory`, used by "Open Folder") would correctly load all DICOM files recursively from that path.  However, `_open_row` never looks at `study_root_path`.

---

## 3. Candidate Fixes

Three approaches were considered. Fix B is the recommended one.

---

### Fix A — Open `study_root_path` as a folder (**Not recommended — correctness flaw**)

**Core idea:** Pass `study_root_path` (a directory) to the existing folder-loading path instead of `open_file_path` (a single file).

**Critical flaw:** The study index groups by `(study_uid, study_root_path)`, so two studies in the same folder appear as **two separate rows sharing the same `study_root_path`**. Opening the folder would load **all studies** in that folder — defeating the purpose of the per-study index rows entirely. This makes Fix A fundamentally incorrect when multiple studies share a root directory (a common scenario: a hospital folder, a PACS export directory, etc.).

**Verdict:** ❌ Rejected. Correctness failure on shared-folder layouts.

### Fix B — Query all `file_path` values for the study from the DB before opening (**Recommended**)

**Core idea:** Add a new method to `StudyIndexStore` / `LocalStudyIndexService` that returns every `file_path` for a `(study_uid, study_root_path)` pair.  Pass that list to `open_paths`.

This is correct by construction: the index already stores one row per instance file, keyed by `(study_uid, study_root_path)`. The DB query uses the existing `idx_study_uid_root` index and is essentially instant regardless of study size.

```python
# New store method (sqlcipher_store.py):
def get_file_paths_for_study(self, study_uid: str, study_root_path: str) -> list[str]:
    ...  # SELECT file_path FROM study_index_entry WHERE study_uid=? AND study_root_path=?

# In dialog._open_row:
paths = self._service.get_file_paths_for_study(study_uid, root)
existing = [p for p in paths if os.path.isfile(p)]
if not existing:
    QMessageBox.warning(...)
    return
self._open_paths(existing)
```

**Pros:**
- **Correct for shared folders:** isolates exactly the selected study even when multiple studies share `study_root_path`.
- Skips the directory-scan step entirely — the file list comes from an indexed DB query.
- `os.path.isfile()` on missing paths is fast and provides clear feedback if files have moved.
- No change to the load pipeline or `DICOMLoader`.

**Cons:**
- Requires a new DB query method in `StudyIndexStore` and `LocalStudyIndexService` (and `StudyIndexPort` protocol update).
- If files have been moved/renamed individually, those paths silently drop out of `existing`. A warning is shown if *all* paths are missing; partial moves degrade gracefully (loads whatever is still there).

**Verdict:** ✅ Recommended. Correct for all folder layouts; not meaningfully slower than Fix A.

---

### Fix C — Store `study_root_path` as a virtual "folder" path column and open it

This is essentially Fix A but naming the column `open_folder_path` in the grouped result.  Already architecturally covered by Fix A without schema changes.

---

## 4. Recommended Implementation Plan (Fix B)

### 4.1 Files to change

| File | Change |
|---|---|
| `src/core/study_index/sqlcipher_store.py` | Add `get_file_paths_for_study` query method |
| `src/core/study_index/index_service.py` | Add wrapper method delegating to store |
| `src/core/study_index/port.py` | Add method signature to `StudyIndexPort` protocol |
| `src/gui/dialogs/study_index_search_dialog.py` | Update `_open_row`, update button label |

### 4.2 Step-by-step

**Step 1 — Add `get_file_paths_for_study` to `StudyIndexStore`**

In `src/core/study_index/sqlcipher_store.py`, add after `delete_study_group`:

```python
def get_file_paths_for_study(
    self, study_uid: str, study_root_path: str
) -> list[str]:
    """
    Return every indexed ``file_path`` for one logical study
    (``study_uid`` + ``study_root_path``).

    Uses the existing ``idx_study_uid_root`` index; fast even for large studies.
    """
    su = (study_uid or "").strip()
    sr = os.path.normpath(os.path.abspath((study_root_path or "").strip()))
    if not su or not sr:
        return []
    with self._connect() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT file_path FROM study_index_entry "
            "WHERE study_uid = ? AND study_root_path = ?",
            (su, sr),
        )
        return [row[0] for row in cur.fetchall()]
```

**Step 2 — Add wrapper to `LocalStudyIndexService`**

In `src/core/study_index/index_service.py`:

```python
def get_file_paths_for_study(
    self, study_uid: str, study_root_path: str
) -> list[str]:
    """Return every indexed file path for one (study UID, study folder) pair."""
    if not self.is_backend_available():
        return []
    store = StudyIndexStore(self._db_path(), self._passphrase())
    store.init_schema()
    return store.get_file_paths_for_study(study_uid, study_root_path)
```

**Step 3 — Add to `StudyIndexPort` protocol**

In `src/core/study_index/port.py`:

```python
def get_file_paths_for_study(
    self, study_uid: str, study_root_path: str
) -> list[str]:
    """Return every indexed file path for one (study UID, study folder) pair."""
    ...
```

**Step 4 — Update `_open_row` in `StudyIndexSearchDialog`**

Replace (lines 450–459):

```python
def _open_row(self, row: int) -> None:
    path = self._model.open_path_for_row(row)
    if not path:
        QMessageBox.information(self, "Study index", "No file path for this row.")
        return
    if not os.path.isfile(path):
        QMessageBox.warning(self, "Study index", f"File not found:\n{path}")
        return
    self._open_paths([path])
    self.accept()
```

With:

```python
def _open_row(self, row: int) -> None:
    snap = self._model.group_row_snapshot(row)
    study_uid = (snap.get("study_uid") or "").strip()
    study_root = (snap.get("study_root_path") or "").strip()
    fallback = (snap.get("open_file_path") or "").strip()

    if not study_uid or not study_root:
        QMessageBox.warning(self, "Study index", "Row is missing study UID or folder.")
        return

    try:
        paths = self._service.get_file_paths_for_study(study_uid, study_root)
    except Exception as e:
        QMessageBox.critical(
            self, "Study index", f"Failed to retrieve file list:\n{e}"
        )
        return

    existing = [p for p in paths if os.path.isfile(p)]

    if not existing:
        # All indexed paths are missing — files may have been moved/deleted.
        if fallback and os.path.isfile(fallback):
            QMessageBox.information(
                self,
                "Study index",
                (
                    "None of the indexed file paths were found at their recorded locations.\n"
                    "Loading only the sample file as a fallback.\n\n"
                    f"Study folder: {study_root}"
                ),
            )
            self._open_paths([fallback])
            self.accept()
            return
        QMessageBox.warning(
            self,
            "Study index",
            (
                "None of the indexed files were found on disk.\n"
                "The study may have been moved or deleted.\n\n"
                f"Study folder: {study_root}"
            ),
        )
        return

    self._open_paths(existing)
    self.accept()
```

**Step 5 — Rename the button**

In `_build_ui` (line ~302), change:

```python
open_btn = QPushButton("Open selected file")
```

to:

```python
open_btn = QPushButton("Open selected study")
open_btn.setToolTip(
    "Load all indexed DICOM files for this study into the viewer"
)
```

**Step 6 — Update `_COLUMN_LABELS`** (optional polish)

```python
"open_file_path": "Sample file",   # was: "Open file" — clarifies it is not the load target
```

**Step 7 — Smoke test**

1. Index a folder containing **two or more distinct studies** via "Index folder…"
2. Verify the dialog shows a separate row per study (confirming shared-folder grouping).
3. Select one study row and click "Open selected study" (or double-click).
4. Verify **only that study's** series and instances appear in the viewer — the other study's files should not be loaded.
5. Verify the series navigator shows the expected instance count.
6. Test single-study folders to confirm normal operation.
7. Test the fallback: move/delete the files for one study, then try to open it — should show the appropriate warning.

---

## 5. Secondary Improvements (Non-blocking)

These are UX polish items discovered during the investigation; they can be done in the same PR or deferred.

| Item | Details |
|---|---|
| TO_DO item: "allow a button to check paths still exist" | `study_root_path` is the right anchor for a path-check pass; confirm it still applies. |
| `open_file_path` column is still useful | Rename column header to "Sample file" so it is clear it is not the "load target". |
| Multi-selection | Consider allowing multi-row selection to open multiple studies (append mode). |
| FTS search covers file paths | `fts_doc.py` might include `file_path` content; `open_file_path` renaming has no FTS impact (it is a computed alias). |

---

## 6. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Files moved/renamed individually | Low | Low | `os.path.isfile()` filter silently drops missing paths; warning if all missing. |
| Very large study (1000s of paths from DB) | Low | Low | DB query is indexed; `open_paths(list)` handles large lists fine. |
| Protocol change breaks mock in tests | Low | Low | Add method to any test mock that implements `StudyIndexPort`. |
| Regression in drag-and-drop loading | None | N/A | No change to `open_paths`, `load_files`, or any caller outside the dialog. |

Overall risk: **Low**.  The change is limited to `study_index_search_dialog.py`, reuses mature code paths, and has a clear fallback.

---

## 7. Files Changed Summary

```
src/core/study_index/sqlcipher_store.py
  - get_file_paths_for_study(): SELECT all file_path for (study_uid, study_root_path)

src/core/study_index/index_service.py
  - get_file_paths_for_study(): wrapper delegating to store

src/core/study_index/port.py
  - get_file_paths_for_study(): add to StudyIndexPort protocol

src/gui/dialogs/study_index_search_dialog.py
  - _open_row(): query all indexed paths via service, filter missing, open list
  - _build_ui(): rename button to "Open selected study" + tooltip
  - _COLUMN_LABELS: rename "open_file_path" display label to "Sample file"
```

No schema changes required. The `idx_study_uid_root` index already supports the new query.

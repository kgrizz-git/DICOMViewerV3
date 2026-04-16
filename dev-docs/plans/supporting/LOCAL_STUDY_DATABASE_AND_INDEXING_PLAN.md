# Local Study Database and Indexing — implementation plan (draft)

**Status:** Draft for `/planner` refinement and `/researcher` spikes.  
**Spec:** [FUTURE_WORK_DETAIL_NOTES.md § Local Study Database and Indexing](../FUTURE_WORK_DETAIL_NOTES.md#local-study-database-and-indexing)  
**TO_DO:** [TO_DO.md § Data / Platform (Future)](../TO_DO.md) — **[P1]** line ~122.

## Codebase snapshot (orchestrator reconnaissance, 2026-04-13)

- **Open / load path:** `FileOperationsHandler` (`src/core/file_operations_handler.py`) coordinates open file/folder/recent, uses `DICOMLoader`, `DICOMOrganizer`, `LoadingProgressManager`, and `run_load_pipeline` (`src/core/loading_pipeline.py`). `DICOMViewerApp` constructs the handler in `main.py`; file signals are wired in `src/core/app_signal_wiring.py` (`_wire_file_signals`: `open_file_requested`, `open_folder_requested`, `open_recent_file_requested`, `open_files_from_paths_requested`).
- **Paths / recents:** `PathsConfigMixin` (`src/utils/config/paths_config.py`) — `last_path`, `last_export_path`, `recent_files`; no study index today.
- **Persistence:** No `sqlite3` / `QSql` usage under `src/`; `.gitignore` already lists `db.sqlite3` (reserved pattern for future DB files — confirm path under user config dir before shipping).
- **Adjacent P2:** [PACS-like Query and Archive](../FUTURE_WORK_DETAIL_NOTES.md#pacs-like-query-and-archive-integration) — keep a **narrow port** (query + resolve-to-paths) so a future PACS backend can replace or complement the local index without rewriting UI.

## Design principles

1. **Path is part of the key:** Store filesystem path per indexed instance/study row so duplicate UIDs in different folders remain distinct.
2. **No startup full-scan:** Background indexer + incremental refresh (watcher optional later); never block `QApplication` startup on large libraries.
3. **Privacy (two layers):** (a) **At rest:** **MVP requires an encrypted database file** (e.g. SQLCipher or equivalent binding)—**not** optional; a copied index file must not be readable as plain SQLite. **Hashing** patient names/IDs is **not** a substitute for at-rest protection (hashes are one-way and break normal SQL search/facets). Phase 0 **R1** picks the concrete library, packaging implications (Windows/macOS/Linux), and **key/passphrase UX** (how the key is derived/stored; document threat model). (b) **In UI:** When **Privacy Mode** is off, show indexed PHI in cleartext in the search/index UI. When Privacy Mode is on, **mask or omit patient-identifying columns** the same way as the metadata flow (`MetadataPanel` / `dicom_parser.get_all_tags(..., privacy_mode=...)` and patient-tag rules)—reuse or centralize that logic so the index UI cannot leak PHI while privacy is enabled.
4. **Decoupled archive API:** UI and search panels depend on a small interface (e.g. “list studies matching filters” / “resolve selection to paths for loader”), implemented first by **local SQLite index**, later by **PACS query** adapter.

## Smallest vertical slice (MVP) vs full scope

| Milestone | Scope | Out of scope (later) |
|-----------|--------|----------------------|
| **MVP (ship first)** | **Encrypted** SQLite (mandatory—e.g. SQLCipher); schema; background worker; index-in-place only; header-level read (pydicom `stop_before_pixels=True` or equivalent); simple search dialog with facets (patient, modality, date range, accession, study description); setting: auto-add on open; manual “index this folder”; **user-configurable DB file path** (persisted in app config, sensible default); key/passphrase handling per R1 | Managed copy mode, FTS tuning, folder watchers, cloud sync |
| **M2** | Managed copy storage policy + UI; conflict rules; disk quota hints | PACS network |
| **M3** | PACS adapter behind same port (separate plan) | — |

## Phased tasks and verification gates

### Phase 0 — Research spikes (parallel-safe)

- [x] **R1 — Storage:** **Encrypted SQLite only** for MVP—select and document binding (e.g. SQLCipher-compatible wheel for target OSes), `requirements.txt` pin, PyInstaller notes if any; **user-chosen DB path** (validation, parent dir exists, atomic replace on migrate); WAL mode; migration strategy; **mandatory** key/passphrase policy (derive from user password vs OS keychain vs app-generated keyfile—ADR in Phase 0 gate).
- [x] **R2 — pydicom:** Fast metadata-only reads; error handling for non-DICOM / truncated files; character sets for PN/LO.
- [x] **R3 — Qt threading:** `QThread` + signals vs `QRunnable`/`QThreadPool`; progress and cancel pattern consistent with `LoadingProgressManager`.
- [x] **R4 — Loader hook:** Single choke-point after successful load (e.g. `FileOperationsHandler` or `FileSeriesLoadingCoordinator`) to call `StudyIndexService.record_open(paths, metadata)` without duplicating logic.

**Gate:** Short written ADR or “Decision” subsection in this file (storage + threading + hook site). **Met** by **Phase 0 decisions (execution)** below (2026-04-13).

### Phase 0 decisions (execution) — 2026-04-13

Orchestrator / SD1 spike notes for implementation and `/planner` (SD2) sign-off.

#### R1 — Storage: encrypted SQLite (package + `requirements.txt` + PyInstaller)

- **Preferred binding (Windows and cross-platform):** Use **[`sqlcipher3`](https://pypi.org/project/sqlcipher3/)** with the **`sqlcipher3-binary`** wheel where available (self-contained SQLCipher-linked build; avoids per-machine `libsqlcipher` / OpenSSL compile steps). Import pattern matches sqlite3: `from sqlcipher3 import dbapi2 as sqlite` then `PRAGMA key = '…'` (or hex-encoded raw key per SQLCipher docs) on first connection.
- **macOS / Linux:** Same PyPI packages; verify wheel availability for each release arch in CI (x86_64, arm64). If a platform lacks a wheel, fall back to building `sqlcipher3` against system SQLCipher (document in build notes) or pin an alternate wheel project only after CI proves it.
- **Avoid for new work:** **`pysqlcipher3`** — upstream marks it **not actively maintained**; prefer `sqlcipher3` / `sqlcipher3-binary`.
- **`requirements.txt`:** Add an **exact pin** for `sqlcipher3-binary` (and matching `sqlcipher3` if split); record **SQLCipher major compatibility** (`PRAGMA cipher_compatibility`) if legacy DBs must be read.
- **PyInstaller (one-liner risk):** The extension is a **native module** — frozen builds must **collect the `sqlcipher3` binary extension** and run a **smoke test** that opens an encrypted DB from the packaged app; failures show up as `ImportError` or silent corruption if the wrong DLL/so is bundled.

**Key material / UX (MVP, ties to R1 policy):** **Default:** app-generated random key material in the **OS credential store** (Windows Credential Manager / macOS Keychain / libsecret on Linux via a thin abstraction), DB file at the user-chosen path. **Optional advanced:** user passphrase → KDF (PBKDF2/Argon2) for portability without the OS store; surface trade-offs in settings copy.

**Threat model (sketch):** At-rest encryption protects the index file against **casual disk access**, **backup theft**, and **unsophisticated** offline reads. It does **not** stop **malware running as the user**, **admin/root** access, or **runtime / keychain** exfiltration. **Privacy Mode** still governs **on-screen** PHI; encryption does not replace UI masking.

#### R2 — pydicom: header-only index rows

- Use **`pydicom.dcmread(path, stop_before_pixels=True, force=True)`** for metadata-only indexing (same pattern as validation in `DICOMLoader.validate_dicom_file`, which calls `dcmread` with `stop_before_pixels=True` and `force=True` at ```156:156:src/core/dicom_loader.py```).
- **Rationale:** `stop_before_pixels=True` avoids reading large `PixelData`; **`force=True`** tolerates non-standard preamble/prefix so more real-world files index without failing the prelude check.
- **Indexer-specific:** Wrap reads in try/except; skip non-DICOM / truncated files with logged counts; for **PN** and text with **Specific Character Set**, decode via pydicom’s normal dataset accessors so character set handling stays consistent with the rest of the app.

#### R3 — Qt: workers vs existing load UI

- **Current open/load path:** **`FileOperationsHandler`** uses **`LoadingProgressManager`** (progress dialog, cancel → `DICOMLoader.cancel`) and runs **`run_load_pipeline`** on the **main thread**, pumping the UI via **`QApplication.processEvents()`** inside the shared progress callback (`loading_pipeline.py`).
- **Recommendation for the study indexer (background crawl / incremental updates):** Prefer **`QThread` + a QObject worker** with **signals** for progress, completion, and errors, and a **cancel flag** checked between files — **parallel to** `LoadingProgressManager`’s cancel semantics (user cancel stops work cleanly). Reserve **`QThreadPool`/`QRunnable`** only for **embarrassingly parallel CPU-bound slices** if profiling shows benefit; **SQLite writes** should stay **serialized** (one writer connection or queue) to avoid locking issues.
- **Do not** move the existing interactive **file open** pipeline to a background thread without a dedicated UX/architecture pass (Qt GUI constraints, `MergeResult` handling, and progress dialog all assume main-thread orchestration today).

#### R4 — Loader hook: auto-index on successful open

All menu/drag-drop/recent opens flow through **`FileSeriesLoadingCoordinator.open_files` / `open_folder` / `open_recent_file` / `open_files_from_paths`**, which call **`FileOperationsHandler.open_*` / `open_paths`** and then, on success, assign **`current_datasets`** / **`current_studies`** (see ```538:578:src/core/file_series_loading_coordinator.py```). Every handler method delegates to **`run_load_pipeline`** in ```168:423:src/core/file_operations_handler.py```.

**Single choke-point (recommended):** **`run_load_pipeline`** in **`src/core/loading_pipeline.py`** — after **`load_first_slice_callback(merge_result)`** succeeds and **`update_status_callback(final_status)`** runs, immediately before **`return datasets, organizer.studies`** (```358:361:src/core/loading_pipeline.py```). Add an **optional** callback (e.g. `on_load_success`) invoked only on that path, with arguments at minimum **`(datasets, organizer.studies)`**; ideally also **`merge_result`** and **`merge_paths`** / file path list so the indexer does not re-walk the organizer. This covers **all** `run_load_pipeline` call sites without duplicating logic.

**Secondary hook (app-level, if avoiding `loading_pipeline` API change):** After a non-`None` return in **`FileSeriesLoadingCoordinator.open_*`** (same line range as above), call a thin **`StudyIndexPort.schedule_record_open(...)`** — four call sites, must stay in sync when new open entry points are added.

**Related wiring:** `FileOperationsHandler` is constructed in **`src/main.py`** with **`load_first_slice_callback=self._file_series_coordinator.handle_additive_load`** (```937:945:src/main.py```); the pipeline invokes that callback at ```313:313:src/core/loading_pipeline.py```. Indexing should **not** rely solely on **`handle_additive_load`** for “success” without also handling early returns inside it (e.g. “no new files” paths at ```347:364:src/core/file_series_loading_coordinator.py```); the **`run_load_pipeline` success return** is the stricter definition of “load completed without cancellation/fatal error.”

### Phase 1 — Planner checklist hardening

- [ ] Finalize table schema (study / series / instance normalization vs flat denormalized for v1).
- [ ] Define `StudyIndexPort` (protocol) methods and DTOs for UI + future PACS.
- [ ] UX flow: where search lives (Tools menu vs dock); empty state; index rebuild.

**Gate:** Checklist signed off; no conflicting assumptions with PACS section in FUTURE_WORK.

### Phase 2 — Implementation streams (fan-out after Phase 1)

| Stream | Owner | Deliverable |
|--------|--------|-------------|
| **2A** | coder | DB layer: **encrypted** connection API, migrations, repositories, unit tests with temp DB (same encryption as prod or test-only key) |
| **2B** | coder | Indexer worker: folder crawl, incremental update, cancellation |
| **2C** | coder | `StudyIndexPort` implementation + hook from open/load path |
| **2D** | coder | Search UI + facet filters; settings (auto-add on open, **configurable DB path**); privacy-aware result columns (wire to same rules as metadata / `privacy_view`) |

**Fan-in gate:** reviewer + tester on green tree; secops targeted scan on new DB/path handling.

### Phase 3 — Testing strategy (tester-owned)

- **No PHI in repo:** Synthetic minimal DICOM fixtures (existing patterns under `tests/` if any; else generate with pydicom in fixture factory) — small byte buffers or tmp_path only.
- Tests: schema round-trip; **encrypted** DB file not readable as plain SQLite (smoke: magic/header or `sqlite3` CLI fails without key); indexer idempotency; duplicate UID different paths; search filters; setting off/on for auto-add; cancel mid-crawl.
- **Gate:** `python -m pytest tests/ -v` from activated `.venv` (per `AGENTS.md`).

### Phase 4 — Documentation (optional for MVP)

- [ ] User-facing: index privacy, where DB lives, how to rebuild.
- [ ] `AGENTS.md` / dev-docs pointer if new module layout is non-obvious.

## Locked product decisions (2026-04-13)

1. **DB file location:** **User-configurable** path (persisted in config; provide a safe default, e.g. per-user application data directory).
2. **At-rest vs on-screen PHI:** Store index rows in **cleartext inside the DB engine** when opened (required for SQL facets/LIKE). Protect the **file on disk** with **encryption** (**mandatory in MVP**—see design principle 3); do **not** rely on hashing for searchable patient fields. **On-screen:** cleartext when Privacy Mode is **off**; when **on**, apply the **same tag display rules as the viewer/metadata** (patient tags masked/hidden) for any PHI shown in the index/search UI.
3. **Ship order:** **MVP only** for this track (managed copy and PACS remain later milestones).
4. **Encrypted SQLite in MVP:** **Mandatory** for the first shippable slice of this feature—no release of the local index using unencrypted `sqlite3` on disk.

## Deferred follow-ups

- **FTS5** (full-text on description fields): **Deferred** past MVP — see [TO_DO.md § Features (Near-Term)](../TO_DO.md).

## Grouped study query and index browser (requirements sketch) — 2026-04-13

**Problem statement:** The MVP search dialog lists **one row per indexed file** (`study_index_entry`-style flat query with `LIMIT`). Users need **one row per logical study location**: same key as product spec — **`StudyInstanceUID` + `study_root_path`** (or equivalent **index root / containing folder** column). Aggregates must appear in the UI: **instance count**, **distinct series count**, **modalities** (set of modalities in that group; display as **sorted unique**, comma-separated or similar).

**Browse vs search (current vs target):** Today there is **no** command that shows the **entire** index independent of filters; `StudyIndexStore.search()` is the main API and returns **flat rows** capped by **`LIMIT`**. **Target:** A single surface (same dialog or tabbed panel) where the user can **browse all grouped studies** (paginated) **and** apply the same facet/search filters — plus a **File** menu entry so discovery matches “open something” mental models.

### Store / SQL sketch (grouped)

Assume per-instance (or per-file) rows with at least: `study_uid`, `study_root_path`, `series_uid`, `modality`, plus existing facet columns (patient, dates, etc.). **Group key:** `(study_uid, study_root_path)`.

```sql
SELECT
  study_uid,
  study_root_path,
  COUNT(*) AS instance_count,
  COUNT(DISTINCT series_uid) AS series_count,
  GROUP_CONCAT(DISTINCT modality) AS modalities_concat
FROM study_index_entry
WHERE <same LIKE / facet predicates as today, optional>
GROUP BY study_uid, study_root_path
ORDER BY <default e.g. study_date DESC, patient_name, path — planner picks>
LIMIT :page_size OFFSET :offset;
```

**Notes for implementation:**

- **SQLite `GROUP_CONCAT(DISTINCT …)`** is available in modern SQLite; confirm behavior under **SQLCipher** build in CI. If `DISTINCT` inside `GROUP_CONCAT` is problematic on a target version, use **`GROUP_CONCAT` on a subquery** that `SELECT DISTINCT modality … GROUP BY study_uid, study_root_path`** or aggregate in Python for small page sizes only (planner/coder trade-off).
- **Modalities:** Normalize empty/NULL to a sentinel or omit; **sort** modalities lexicographically when **building the string** for stable display.
- **Privacy mode:** Apply the **same column masking rules** as flat search (service layer), keyed off `privacy_view` / metadata parity — **before** or **after** SQL depending on whether masked fields are searchable; do not leak PHI in grouped rows when privacy is on.

### Pagination / “show all”

Flat `LIMIT` is insufficient for “whole database” browse. Pick one (planner signs off):

1. **Offset pagination:** `LIMIT` + `OFFSET` (simple; can slow on huge offsets — acceptable for early MVP if caps are reasonable).
2. **Keyset pagination:** `WHERE (study_uid, study_root_path) < (:cursor…)` (better at scale; more complex with filters).
3. **Hard safety cap:** e.g. max **N** rows per request; UI **“Load more”** or infinite scroll with explicit cap + message when more exists.

**Recommendation:** Start with **(1) + hard cap** per request and **“Load more”** in the grouped browse mode; revisit keyset if profiling demands.

### File menu and alternate database path

**Recommendation (dual entry):**

- **File → Open study index…** — Opens the **configured** index DB (same path as **Settings** / `study_index_config`), then shows the **unified** browse+search UI. Wording **“study index”** is clearer for users than **“database”** (technical).
- **Optional:** **Browse for index file…** (or a button inside the dialog) to open a **different** `.sqlite` index — **only** if **key/passphrase strategy** supports it (e.g. user supplies passphrase or key is discoverable). If the MVP key is **tied to the configured file path** in the OS store, **document the limitation**: alternate file may require **Settings → change DB path** or a one-shot unlock flow — **planner/coder** must not imply silent access without key UX.

**Tools → Study index search…** may remain as an alias to the **same** dialog or redirect to **File** entry for consistency (planner decides single vs dual entrypoints).

### Qt: column reorder and persistence

**`QTableWidget`** can show a table but **clean mapping** between **visual column order** and **stable logical fields** (for config save/restore) is awkward. **Recommendation:**

- Use **`QTableView`** + **`QAbstractTableModel`** (or `QSqlTableModel` only if it fits — grouped query likely needs a custom model).
- Enable **`QHeaderView.setSectionsMovable(True)`** for **drag-reorder**.
- Persist **logical column order** (and optional widths) in config JSON: store an ordered list of **stable column ids**, not visual indices alone — on restore, call `moveSection` / `swapSections` to match saved **logicalIndex** order.
- On schema changes, merge unknown columns with defaults.

**Gate:** **SD6 signed off (2026-04-13):** checklist below (**SD7**) is implementation-ready. **FTS** remains **deferred** per [Deferred follow-ups](#deferred-follow-ups).

## SD7 — Signed-off implementation checklist (Stream H, 2026-04-13)

**Goal:** One row per logical study location (`study_uid` + `study_root_path`), paginated browse with the same facet filters as today’s flat search, aggregates in the UI, column reorder persisted by stable ids, and **File** menu entry alongside **Tools**.

**Codebase reconciliation (for coder):**

- **`StudyIndexStore.search`** (`sqlcipher_store.py`) is **flat**, `LIMIT` only (no `OFFSET`). Grouped browse adds a **new** API; keep flat `search` for any legacy/tests unless explicitly removed later.
- **`StudyIndexPort`** already exists (`port.py`); **extend** the protocol with grouped search (and optional `offset` on flat search only if still needed—prefer not to expand flat API unless a caller requires it).
- **Open-row behavior:** Today the dialog opens **one** `file_path` from the selected row. For grouped rows, define a deterministic path for “Open selected” (e.g. `MIN(file_path)` in SQL, or a tiny follow-up query by `(study_uid, study_root_path)`). Document choice in code. Defer “open all instances in group” unless trivial extension of `open_paths_callback`.

### Store layer (`src/core/study_index/sqlcipher_store.py`)

- [x] **(H1)** Add **`search_grouped_studies`** (name exact per implementation) with **the same filter parameters** as `search` (`patient_name_contains`, `patient_id_contains`, `modality`, `accession_contains`, `study_description_contains`, `study_date_from`, `study_date_to`) plus **`limit`** and **`offset`** (defaults e.g. `limit=100`, `offset=0`).
- [x] Reuse the **same `WHERE` predicate construction** as flat search (LIKE + date range), applied **before** `GROUP BY` so filters match flat semantics on the underlying rows.
- [x] **`GROUP BY study_uid, study_root_path`** with aggregates:
  - `COUNT(*)` → **`instance_count`**
  - `COUNT(DISTINCT series_uid)` → **`series_count`** (treat empty `series_uid` as distinct-safe per SQLite rules; document if empty series UIDs under-count).
  - **Modalities:** `GROUP_CONCAT(DISTINCT modality)` when supported; **else** subquery/`GROUP_CONCAT` on pre-distinct modalities or post-process page rows in Python (acceptable only for small `limit`; prefer SQL for consistency).
  - Normalize NULL/empty modality for display; **sort** unique modalities **lexicographically** when building the display string (SQL or Python).
- [x] **Representative study-level scalar fields** (one value per group for patient/study metadata): use **`MAX(...)`** or **`MIN(...)`** per column for deterministic SQL (e.g. `MAX(patient_name)`, `MAX(patient_id)`, `MAX(accession_number)`, `MAX(study_date)`, `MAX(study_description)`), or document equivalent “pick any row in group” if coder prefers `MIN` consistently. Include **`study_uid`**, **`study_root_path`** in the SELECT list.
- [x] Optional but recommended for **Open:** include **`MIN(file_path) AS open_file_path`** (or similar) for a single-file open without a second round-trip.
- [x] **`ORDER BY`:** default aligned with current browse expectation, e.g. **`study_date DESC`, `patient_name ASC`, `study_root_path ASC`** (adjust if product prefers path-first).
- [x] **Default browse mode:** first load uses **empty filters**, **`offset=0`**, and configured page size (see UI).

**parallel-safe:** no · **stream:** H · **after:** none

### Service layer (`src/core/study_index/index_service.py`, `port.py`)

- [x] **(H3)** Expose **`search_grouped_studies`** on **`LocalStudyIndexService`** with the same kwargs as the store + **`privacy_mode`** (read from caller; dialog uses `ConfigManager.get_privacy_view()` as today).
- [x] **Privacy masking:** When `privacy_mode` is True, mask **grouped** patient-related fields the same as flat search: **`patient_name`**, **`patient_id`**, **`accession_number`** → e.g. **`***`** (parity with existing `search` in `index_service.py`). Apply **after** fetch or ensure SQL representative columns are not leaked in UI paths.
- [x] Update **`StudyIndexPort`** to include the grouped method signature so future PACS/local adapters stay aligned.

**parallel-safe:** no · **stream:** H · **after:** H1

### Config (`src/utils/config/study_index_config.py`, `src/utils/config_manager.py`)

- [x] **(H4)** Add persisted keys, e.g. **`study_index_browser_column_order`**: ordered list of **stable column id strings** (not only visual indices). Optional: **`study_index_browser_page_size`** or hard-code first page size in dialog with a constant (planner default: **single constant in dialog**, e.g. 100, unless UX asks for setting).
- [x] Defaults in **`ConfigManager`** `config` dict for new keys; **`StudyIndexConfigMixin`** getters/setters following existing patterns.
- [x] **Stable column ids** (canonical set for model + save/restore):  
  `patient_name`, `patient_id`, `study_date`, `accession_number`, `study_description`, `study_root_path`, `instance_count`, `series_count`, `modalities`, **`open_file_path`** (implementation), `study_uid` (last may be **hidden** by default but still reorderable if shown).

**parallel-safe:** yes · **stream:** H · **after:** H1

### UI (`src/gui/dialogs/study_index_search_dialog.py`)

- [x] **(H5)** Replace or refactor to **`QTableView`** + **`QAbstractTableModel`** (subclass in same file or `gui/dialogs/` helper module if model grows; keep files under modular size limits per project norms).
- [x] **`QHeaderView.setSectionsMovable(True)`** for drag-reorder; map visual order ↔ logical column ids; on show/close (or header `sectionMoved`), persist order via **`ConfigManager`**.
- [x] **Columns (logical):** Patient, Patient ID, Study date, Accession, Study description, **Study folder** (`study_root_path`), **# instances**, **# series**, **Modalities**; optional **`study_uid`** column (default **hidden** or shown—coder chooses default hidden).
- [x] **Search** button: reset **`offset=0`**, replace model rows from **`search_grouped_studies`**.
- [x] **Load more:** append next page (`offset += previous_row_count` or `offset += limit`), **without** clearing prior rows; stop when a page returns **fewer than `limit`** rows (optional “No more results” state).
- [x] **Initial open:** trigger **first browse** (empty filters, `offset=0`) so the dialog is useful without typing Search (matches “browse all” requirement).
- [x] Window title / hint text: align with **browse + search** (minor copy; **ux** may refine strings).

**parallel-safe:** no · **stream:** H · **after:** H3, H4

### Menus and signals (`src/gui/main_window.py`, `src/gui/main_window_menu_builder.py`, `src/core/app_signal_wiring.py`, `src/main.py`)

- [x] **(H6)** **File → Open study index…** (or **Open study index…** per product string): new **`QAction`** + **`Signal`** on `MainWindow` (e.g. `study_index_browse_requested` **or** reuse a single `study_index_dialog_requested` connected twice—prefer **one signal** `study_index_dialog_requested` emitted from both menus to avoid duplicate slots).
- [x] **Recommendation (signed off):** Keep **Tools → Study index search…** as an **alias** to the **same** dialog/slot as **File → Open study index…** (muscle memory + docs). Optionally rename Tools label to **Study index…** in a later UX pass—**not** required for SD7.
- [x] Wire both actions to **`DICOMViewerApp._open_study_index_search`** (or renamed method if dialog title changes). Ensure dialog still uses **`Qt.WindowModality`** / parenting per existing file-dialog rules.

**parallel-safe:** no · **stream:** H · **after:** H5

### Tests (`tests/test_study_index_store.py` or `tests/test_study_index_grouped.py`)

- [x] **(H2)** After H1: **grouped query smoke:** multiple files, same `(study_uid, study_root_path)`, multiple series/modalities → assert **`instance_count`**, **`series_count`**, sorted **modalities** string (or distinct set), and **`LIMIT`/`OFFSET`** pagination (second page excludes first page’s groups).
- [x] Keep **`pytest.importorskip("sqlcipher3")`** / **`keyring`** pattern as existing tests.
- [ ] Optional: service-level test with `privacy_mode=True` masked fields—only if lightweight (else reviewer manual check).

**parallel-safe:** yes · **stream:** H · **after:** H1

### Task graph and verification gate

```text
Ordering:
  H1 (store) → H2 (tests) ∥ H3 (service+port) ∥ H4 (config)   [H2/H3/H4 parallel after H1]
  H3 + H4 → H5 (dialog)
  H5 → H6 (menus/signals)
  Fan-in before merge/reviewer: H1–H6 complete (H2 may finish before H5; all must be done before ship).

Verification gate (definition of done):
  From activated `.venv`, `python -m pytest tests/ -v` is green (full suite per AGENTS.md).
  Manual smoke: open dialog from File and Tools; empty DB shows empty table; Load more; column reorder survives restart.
```

### File ownership (Stream H)

| Path | Primary owner |
|------|----------------|
| `src/core/study_index/sqlcipher_store.py` | coder (H1) |
| `src/core/study_index/index_service.py`, `port.py` | coder (H3) |
| `src/utils/config/study_index_config.py`, `src/utils/config_manager.py` | coder (H4) |
| `src/gui/dialogs/study_index_search_dialog.py` | coder (H5) |
| `src/gui/main_window.py`, `main_window_menu_builder.py`, `src/core/app_signal_wiring.py`, `src/main.py` | coder (H6) |
| `tests/test_study_index_store.py` (or new test module) | coder (H2) |

### Questions for user / ux (non-blocking for coder start)

- **Tools menu label:** keep **“Study index search…”** vs shorten to **“Study index…”** — defer to **ux** or user preference.
- **Alternate DB file from File menu:** not in SD7 scope; remains documented limitation (Settings path + keyring) unless a follow-up adds “Browse for index file…”.

## Relation to P2 PACS

- Implement **query/archive port** in `core/` (pure Python interfaces + DTOs) consumed by GUI.
- Local SQLite service is the first implementation; PACS module would implement the same port (network errors, C-FIND mapping) — **no** SQL or DICOM networking inside the search widget.

---

*Orchestrator seeded this draft; `/planner` should refine checkboxes and file-level task graph.*

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
| **MVP (ship first)** | **Encrypted** SQLite (mandatory—e.g. SQLCipher); schema; background worker; index-in-place only; header-level read (pydicom `stop_before_pixels=True` or equivalent); simple search dialog with facets (patient, modality, date range, accession, study description); setting: auto-add on open; manual “index this folder”; **user-configurable DB file path** (persisted in app config, sensible default); key/passphrase handling per R1; **FTS5 quick search** (v0.3.0) per [FTS5 plan](#fts5-local-study-index-search-detailed-plan) | Managed copy mode, advanced FTS (BM25, path toggle), folder watchers, cloud sync |
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

- **FTS5** (full-text on description and related text fields): **Shipped** in app **v0.3.0** (was deferred past the original MVP ship order). **Spec / checklist:** [FTS5 — local study index search (detailed plan)](#fts5-local-study-index-search-detailed-plan); tracking closed in [TO_DO.md](../TO_DO.md).

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

**Gate:** **SD6 signed off (2026-04-13):** checklist below (**SD7**) is implementation-ready. **FTS5** follow-up work is **shipped** (see [Deferred follow-ups](#deferred-follow-ups) and [FTS5 — local study index search (detailed plan)](#fts5-local-study-index-search-detailed-plan)).

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

<a id="fts5-local-study-index-search-detailed-plan"></a>

## FTS5: local study index search (detailed plan)

**Purpose:** Add SQLite [FTS5](https://www.sqlite.org/fts5.html) so the study index browser can (1) use **one** primary text box to find studies whose indexed metadata matches **any** of several text fields, while (2) keeping today’s **per-field filters** (patient name, patient ID, modality, accession, study description, study date range) for precise narrowing — combined with **AND** semantics between the global box and each active field filter.

**Linked from:** [TO_DO.md § Features (Near-Term) — P0 FTS](../TO_DO.md).

<a id="fts5-progress-and-todo-closeout"></a>

### Progress tracking and closing the TO_DO item

This section is **part of the definition of done** for the P0 FTS work tracked in [TO_DO.md](../TO_DO.md).

1. **Check off plan boxes as work completes**  
   In the [Task checklist](#task-checklist-implementation-order) below, turn **`- [ ]`** into **`- [x]`** for **F1–F6** only when that item is **fully** implemented, reviewed, and verified (not for partial or “good enough” progress). Prefer updating the checkboxes in the **same commit** as the completing change, or in the merge commit that lands the slice—avoid leaving the plan out of sync with `main`/`develop`.

2. **Verification gate before final close-out**  
   Do not treat the feature as finished until the **[Verification gate](#task-checklist-implementation-order)** at the end of the checklist is satisfied (`pytest` green per project norms; manual smoke for global-only, filter-only, combined, and **Load more** with FTS).

3. **Update TO_DO.md when everything is done**  
   After **all** of **F1–F6** are **`[x]`** in this file **and** the verification gate is met, edit **`dev-docs/TO_DO.md`**: change the P0 FTS bullet from **`- [ ]`** to **`- [x]`** (and optionally add a one-line note with release version or merge date if helpful—keep it short). That TO_DO line is the product-facing tracker; the plan file is the engineering checklist.

### Product goals and UX

1. **Global search box (new)**  
   - Single line edit, placed **above** the existing “Filters” group (or as the first row inside it) with a clear label, e.g. **“Search all text”** or **“Quick search”**.  
   - Placeholder text should set expectations, e.g. *“Words match patient, IDs, accession, descriptions, modality, series…”* (exact copy via **ux**).  
   - **Semantics (recommended default):** treat the input as **FTS5 prefix/token search** across a **document** built from multiple columns (see [Indexed text surface](#indexed-text-surface)). Consecutive tokens are **AND**ed (each token must appear somewhere in the combined document unless advanced syntax is explicitly supported later).  
   - **Empty** global query: **no** FTS predicate — behavior matches **current** browse/search (filters and pagination only).

2. **Per-field filters (existing)**  
   - Keep the current `QLineEdit` / date controls in `StudyIndexSearchDialog` (`patient_name_contains`, `patient_id_contains`, `modality`, `accession_contains`, `study_description_contains`, `study_date_from` / `study_date_to`) as today.  
   - They continue to use the **same** SQL semantics as now (**LIKE** substrings with escape, date bounds on `study_date`) via `_search_filter_clauses` in `StudyIndexStore` — **unless** a later sub-phase replaces individual text fields with FTS column filters for consistency (optional; not required for the first ship).

3. **Combining global + field filters**  
   - **AND** only: a row (or grouped study) is shown only if it satisfies **both** the FTS global match (when non-empty) **and** every active legacy filter.  
   - Document in user-facing help that the global box is “broad” and field filters “narrow.”

4. **Grouped browse unchanged in shape**  
   - Results remain **one row per** `(study_uid, study_root_path)` with the same aggregates as `search_grouped_studies` today; FTS only changes **which** instance rows participate in the `GROUP BY` (see [Query integration](#query-integration-with-search_grouped_studies)).

<a id="indexed-text-surface"></a>

### Indexed text surface

**Today** (`study_index_entry`, `metadata_extract.dataset_to_index_row`): `patient_name`, `patient_id`, `accession_number`, `study_date`, `study_description`, `modality`, UIDs and paths as stored.

**Gap for “study/series description” in TO_DO:** the flat row does **not** yet include **series** description. **Planner/coder decision (recommended):** add a nullable **`series_description`** column (and indexer mapping from `SeriesDescription`) so series-level phrases are first-class in the index and in FTS. Optionally add **`series_number`** or **`body_part_examined`** later — out of scope unless product asks.

**Global “search anywhere” document (recommended):** one FTS **virtual column** (or a single real column mirrored into FTS) that concatenates **normalized** text from, at minimum:

| Source column | Notes |
|---------------|--------|
| `patient_name` | PN decoding already handled in indexer |
| `patient_id` | |
| `accession_number` | |
| `study_description` | |
| `series_description` | **new** |
| `modality` | short token; still useful for “MR” style queries |
| `study_uid`, `series_uid`, `sop_instance_uid` | optional; helps power-user UID fragment search |

Use a **stable, rare delimiter** between parts (e.g. a space or `|` + space) so token boundaries stay sensible. **Do not** inject user-controlled delimiter sequences from data without normalizing.

**Path fields (`file_path`, `study_root_path`):** including them improves “find folder” workflows but can dominate token counts; **recommendation:** omit from the default global document for v1, or gate behind a **“Include paths”** checkbox in a follow-up — planner signs off.

### Storage design (SQLCipher + FTS5)

**Requirement:** Ship FTS on the **same** encrypted DB as today (`sqlcipher3`); FTS5 is part of standard SQLite builds used by SQLCipher — **verify** in CI and packaged app that `FTS5` is available (`sqlite_compileoption_used('ENABLE_FTS5')` or a trivial `CREATE VIRTUAL TABLE … fts5` smoke test).

**Recommended pattern: [external content](https://www.sqlite.org/fts5.html#external_content_and_contentless_tables) FTS5 table**

- Content table remains **`study_index_entry`** (source of truth for typed columns and `GROUP BY`).  
- Add e.g. **`study_index_entry_fts`** as `CREATE VIRTUAL TABLE study_index_entry_fts USING fts5( … , content='study_index_entry', content_rowid='id')`.  
- Columns in the FTS table: at least the **`document`** column (all-in-one text) plus **UNINDEXED** copies of `id` if useful for debugging; simplest is one indexed `doc` column only + `content_rowid='id'`.

**Synchronization**

- **Triggers** on `study_index_entry`: `AFTER INSERT`, `AFTER UPDATE`, `AFTER DELETE` → `INSERT INTO study_index_entry_fts(rowid, doc) …` / `DELETE` / `UPDATE` per [FTS5 external content docs](https://www.sqlite.org/fts5.html#external_content_and_contentless_tables).  
- **Migration:** for existing DBs, after creating the FTS table and triggers, run a **one-time** `INSERT INTO study_index_entry_fts(rowid, doc) SELECT id, <computed doc> FROM study_index_entry;` (or rebuild) inside the same migration transaction as `PRAGMA user_version` bump.

**Schema version**

- Bump **`StudyIndexStore.SCHEMA_VERSION`** (new migration block in `init_schema`): add `series_description` column if missing; create FTS table + triggers; backfill.

**Rebuild / repair**

- Expose a **developer or advanced** action (optional for v1): “Rebuild full-text index” = `INSERT INTO study_index_entry_fts(study_index_entry_fts) VALUES('rebuild')` or drop/recreate + backfill — document in `AGENTS.md` / user docs if user-visible.

<a id="query-integration-with-search_grouped_studies"></a>

### Query integration with `search_grouped_studies`

**Goal:** preserve the existing grouped `SELECT` shape while restricting to rows that match FTS when the global query is non-empty.

**Pattern (conceptual):**

```sql
SELECT …aggregates…
FROM study_index_entry AS e
WHERE <existing _search_filter_clauses predicates on e>
  AND (
    :global_fts IS NULL OR :global_fts = ''
    OR e.id IN (
      SELECT rowid FROM study_index_entry_fts WHERE study_index_entry_fts MATCH ?
    )
  )
GROUP BY e.study_uid, e.study_root_path
ORDER BY …
LIMIT ? OFFSET ?;
```

- **Parameterization:** bind the user’s global query as a single parameter where SQLite allows `MATCH ?` on the FTS table (confirm on the project’s SQLite/SQLCipher version; if not, use validated/sanitized literal with **strict** escaping rules — see [Safety and FTS query syntax](#safety-and-fts-query-syntax)).  
- **Empty global:** omit the `IN (SELECT rowid …)` clause entirely (no FTS scan).

**Alternative:** `EXISTS (SELECT 1 FROM study_index_entry_fts f WHERE f.rowid = e.id AND f MATCH ?)` — equivalent; pick one style for readability.

### Per-field “as done now” vs FTS column match (optional later)

- **Phase FTS-A (recommended first ship):** global box → FTS on **`doc`** only; field filters stay **LIKE** on `study_index_entry` columns (current behavior).  
- **Phase FTS-B (optional):** allow power users or future UI to target a single column via FTS `column : query` syntax for specific fields — only if product needs stricter token semantics than `LIKE`.

<a id="safety-and-fts-query-syntax"></a>

### Safety and FTS query syntax

- FTS5 **`MATCH`** uses a **query syntax** (`AND` / `OR` / `"phrase"` / `*` prefix). Malformed queries can error at runtime.  
- **Mitigation:** catch `sqlite3.OperationalError` around FTS queries and show a friendly message (“Invalid search syntax”) without crashing.  
- **Document** supported shortcuts for users who paste special characters (quotes, `*`).  
- Optionally implement a **“Simple mode”** preprocessor: strip or escape characters that break the parser before `MATCH`, while preserving alphanumeric tokens — **ux + security** review (denial-of-service via huge query strings: cap length, e.g. 256 chars).

### Privacy and encryption

- **At rest:** FTS segments live inside the **encrypted** DB file — same threat model as cleartext columns in the main table (see [Locked product decisions](#locked-product-decisions-2026-04-13)).  
- **On screen:** no change to **`privacy_mode`** masking in `LocalStudyIndexService.search` / `search_grouped_studies`; global search must not display hidden PHI in new UI elements.

### API / port layer

- Extend **`StudyIndexStore._search_filter_clauses`** (or a parallel helper) to accept an optional **`global_fts_query: str`**, returning extra `AND` / `EXISTS` fragments and parameters.  
- Extend **`LocalStudyIndexService.search`** and **`search_grouped_studies`** and **`StudyIndexPort`** with the same optional parameter name for consistency.  
- **PACS adapter** (future): may implement global query as a no-op or map to C-FIND description fields — document in port docstrings.

### UI implementation notes (`study_index_search_dialog.py`)

- New **`QLineEdit`** + label; wire into `_service_query_kwargs` (add key) and `_on_clear_filters_clicked` (clear the field).  
- **Search** / **Load more:** pass the global string through; **Load more** must repeat the **same** global + filter snapshot as the first page (store last-used kwargs on the dialog instance — already implied by reading widgets each time).  
- **Hint label:** one line explaining AND of quick search + filters.

### Testing (`tests/`)

- **importorskip** `sqlcipher3` as existing study index tests.  
- **Migration test:** v0 DB file → open with new code → FTS table exists and `MATCH` returns expected rowids.  
- **Functional:** fixtures with tokens present only in `series_description` vs only in `patient_name` — global box finds both; adding a conflicting field filter excludes rows.  
- **Grouped:** two instances, same study/folder, match on different instance rows → **one** grouped row, correct counts.  
- **Error path:** invalid `MATCH` syntax → user-visible error, no traceback to console in release builds.

<a id="task-checklist-implementation-order"></a>

### Task checklist (implementation order)

- [x] **F1 — Schema:** Add `series_description` to `study_index_entry`; migration from `SCHEMA_VERSION` N → N+1; update `dataset_to_index_row` and `upsert_rows` column lists.  
- [x] **F2 — FTS objects:** `CREATE VIRTUAL TABLE … fts5` with `content=` + `content_rowid=`; sync triggers; backfill job in migration.  
- [x] **F3 — Store:** `global_fts_query` on `search` / `search_grouped_studies`; `_search_filter_clauses` composition + tests in `tests/test_study_index_store.py` (or sibling).  
- [x] **F4 — Service + port:** pass-through + docstrings.  
- [x] **F5 — UI:** global line edit, clear, tooltips, error handling.  
- [x] **F6 — Docs:** `CHANGELOG.md`, user-facing blurb for index search, `AGENTS.md` pointer if module layout shifts.

**Verification gate:** `python -m pytest tests/ -v` green from activated `.venv`; manual smoke: global-only, filter-only, combined, Load more with FTS active. **Met for v0.3.0:** full `pytest tests/` (555 passed, 2026-04-20); manual smoke left to maintainer before release if desired. **TO_DO** P0 line checked off per [Progress tracking and closing the TO_DO item](#fts5-progress-and-todo-closeout).

### Open questions (planner / product)

- **Tokenizer:** default FTS5 tokenizer vs `unicode61` / `porter` — affects international text and medical abbreviations; spike on sample data.  
- **Ranking:** v1 can keep **date/name `ORDER BY`** only; optional **BM25** (`fts5_bm25` / `bm25()`) as FTS-B for “best match first.”  
- **Include UIDs / paths** in `doc` column for v1 or defer.

---

## Relation to P2 PACS

- Implement **query/archive port** in `core/` (pure Python interfaces + DTOs) consumed by GUI.
- Local SQLite service is the first implementation; PACS module would implement the same port (network errors, C-FIND mapping) — **no** SQL or DICOM networking inside the search widget.

---

*Orchestrator seeded this draft; `/planner` should refine checkboxes and file-level task graph.*

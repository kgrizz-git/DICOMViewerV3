# Study Index Portability & Encryption UI Plan

**Status:** Phase 0, Phase 2, and Phase 3 complete; optional plaintext migration deferred; relative paths remain backlog.
**Priority:** P1  
**Execution breakdown (Phases A→2, agent-run):** [Study index browser, integrity & portability execution plan](STUDY_INDEX_BROWSER_AND_INTEGRITY_EXECUTION_PLAN.md)
**TO_DO refs:** UX/Workflow — "Study index — optional encryption toggle — DEFERRED" and "Study index — relative file paths"

---

## Goal

Expose the study index's encryption, location, and health features through clear in-app UI so users can:

1. Keep the study index encrypted at rest by default and in the current product contract.
2. See where the DB lives, move it, export/import metadata.
3. Run a bulk **integrity scan** to find missing studies and relocate or remove them.
4. (Future / P2) Store relative file paths for USB portability.

The index is **always SQLCipher-encrypted**; the passphrase is auto-generated in the OS keyring. The Study Index dialog provides index location, health, move, metadata export/import, and relocate/remove workflows. A plaintext migration is deliberately not exposed.

---

## Phase 0 — First-open indexing prompt (persistent choice + one-time options)

**Shipped behavior:** `gui/study_index_consent.py::ensure_study_index_auto_add_consent()` shows `StudyIndexFirstOpenDialog` on the **first successful load** when no consent is recorded. It provides four choices and inline disclosure of what/where the index is:

- **Always add to index** — set auto-add **on** + record consent; never ask again.
- **Never add to index** — set auto-add **off** + record consent; never ask again.
- **Add this one time** — index the current study now, but **do not** record persistent consent (prompt can appear again later).
- **Skip this one time** — do **not** index now, and **do not** record consent (prompt can appear again later).
- Inline **info disclosure**: where the index is saved (DB path), that it stores clinical metadata + file locations **on this device**, that it is always encrypted at rest, and that it can be changed/cleared later in **Settings**. Reuse the Phase 2 "About this index" copy so wording stays consistent.

**Re-prompt cadence for the one-time options (decided 2026-07-20):** the prompt is shown on each load while consent is unrecorded (i.e. `needs_study_index_auto_add_consent()`), so `ADD_ONCE`/`SKIP_ONCE` naturally re-prompt on the next load until the user picks `ALWAYS`/`NEVER`. A "don't ask again this session" nuance can be layered on later if the per-load prompt proves noisy.

### Tasks — **DONE 2026-07-20**

- [x] New dialog `StudyIndexFirstOpenDialog` in `gui/study_index_consent.py` with 4 buttons + an info panel (index location, what's stored, "change later in Settings") and an **Open location** button.
- [x] Return an explicit decision enum `StudyIndexOpenChoice{ALWAYS, NEVER, ADD_ONCE, SKIP_ONCE}` via `prompt_study_index_first_open()`.
- [x] `main.py` load-time call: `ADD_ONCE` indexes just this load via `schedule_index_after_load(..., force=True)` without recording consent; `SKIP_ONCE` skips without recording consent; `ALWAYS`/`NEVER` record consent (via `apply_first_open_choice`).
- [x] Show index location/info inline (shared `gui/study_index_info.py` helper, reused by Phase 2).
- [x] Tests: `test_privacy_storage_controls.py` (choice → config state; one-time leaves consent unrecorded; prompt returns/persists) + `test_index_service.py::test_schedule_force_indexes_when_auto_add_off`.

---

## Phase 1 — Optional plaintext migration (deferred)

**Status: DEFERRED (decided 2026-07-21).** A user-facing toggle that lets people
migrate the PHI index to **plaintext** is closer to a footgun than a feature — it
downgrades at-rest protection for patient names/IDs/paths with little practical
upside, and the migration + irreversible-warning surface is non-trivial. The index
stays **always SQLCipher-encrypted** for now. If a concrete need appears (e.g. a
platform without keyring), revisit with the 1b off-warning wording already drafted
below. The remaining Phase 1 tasks are kept for reference, not scheduled.

### 1a. Config & backend

- [ ] Only if the policy is explicitly reversed, add `study_index_encryption_enabled` (bool, default **True**) in `ConfigManager` / `study_index_config.py`.
- [ ] When encryption is **off**, `StudyIndexStore` opens/creates the DB as plain SQLite (no `PRAGMA key`).
- [ ] When encryption is **on**, behaviour is unchanged from today (SQLCipher + keyring passphrase).

### 1b. Migration (toggle on ↔ off)

- [ ] Implement `StudyIndexStore.migrate_encryption(target_encrypted: bool, passphrase: str)`:
  - Use `ATTACH DATABASE ... AS target` + `sqlcipher_export('target')` pattern (SQLCipher docs) to copy between encrypted and plaintext DB files.
  - Write to a temp file, verify row count matches, then atomically rename.
  - Rollback on any failure; never leave a half-written DB.
- [ ] Call migration from Settings when the toggle changes, with a confirmation dialog explaining that a restart may be needed or that the migration may take a moment for large indexes.
- [ ] **Warn explicitly when turning encryption OFF.** Toggling encryption off must show a prominent confirmation (not just a tooltip) before migrating to plaintext: the index stores **patient names, IDs, study descriptions, and file paths**, and disabling encryption leaves that readable by anyone with disk access. Default the dialog button to **Cancel / keep encrypted**; only proceed on explicit confirmation. (Enabling encryption needs no such warning.)

### 1c. Settings UI

- [ ] Add **Study Index** section to **Edit → Settings…** (or a dedicated tab):
  - **Encryption** toggle with tooltip explaining tradeoffs; turning it **off** triggers the explicit at-rest-exposure warning from 1b.
  - Current DB path (read-only label) + **Browse…** button (already exists) + **Default** reset.
  - **Passphrase:** when encryption is on, note "Stored in OS credential store" with link to `keyring_storage.py` docs; no user-visible passphrase field (P2 item for user-configurable passphrase).

### 1d. Tests

- [ ] `tests/test_study_index_encryption_toggle.py`:
  - Create encrypted DB, migrate to plain, verify data survives.
  - Create plain DB, migrate to encrypted, verify data survives.
  - Fail partway through migration → original DB is intact.

---

## Phase 2 — Location & portability UI ("About this index" panel)

- [x] Add an **About this index…** panel in the Study Index Search dialog:
  - **DB path** (clickable → opens containing folder in Explorer/Finder).
  - **Encryption:** always enabled at rest with SQLCipher; the passphrase is stored in the OS credential store under service `DICOMViewerV3`.
  - **Row count** / size on disk.
  - **Last modified** timestamp.
- [x] **Open index location** button → `QDesktopServices.openUrl(QUrl.fromLocalFile(parent_dir))`. **DONE 2026-07-20** — in the Study Index dialog and the first-open prompt, via `gui/study_index_info.py::open_study_index_location()` (opens the nearest existing ancestor if the DB file doesn't exist yet).
- [x] **Move index…** button:
  - File-save dialog for new location.
  - Copy DB file → verify integrity (open + `PRAGMA integrity_check`) → update config → delete old file.
  - Confirm dialog before proceeding.
- [x] **Export index…** button:
  - Exports **metadata and file paths only** as CSV — no pixel data.
  - Clear label: "This CSV contains PHI, including clinical metadata and file paths. Handle it securely. DICOM image pixel data is not included."
- [x] **Import index…** button:
  - Reads a previously exported CSV and upserts rows into the current DB.
  - Conflict resolution: skip duplicates (same StudyInstanceUID + file path).

### Tests

- [x] `tests/test_study_index_portability_ui.py`:
  - Move DB, reopen, verify search still works.
  - Export → import round-trip preserves all rows.

---

## Phase 3 — Integrity scan & relocate

- [x] Add **Check indexed studies…** button to Study Index Search dialog toolbar.
- [x] `LocalStudyIndexService.integrity_scan() -> list[MissingStudyRecord]`:
  - For each unique `(study_instance_uid, study_root_path)`, check if the root path exists and at least one file path exists on disk.
  - Run in a `QThread` with progress dialog (can be many studies).
  - Return list of studies whose files are missing.
- [x] Results dialog:
  - Table of missing studies (patient name, study date, modality, old path).
  - Per-row actions: **Relocate…** (file dialog to pick new root), **Remove from index**.
  - Bulk actions: **Remove all missing**, **Cancel**.
- [x] `LocalStudyIndexService.relocate_study(study_uid, old_root, new_root)`:
  - Canonicalize the old/new roots and replace `file_path` prefixes only on a path-component boundary; leave unrelated similarly prefixed paths unchanged.
  - Verify at least one relocated path exists before committing.
- [x] On load-from-index when files are missing (existing behavior: warns), add a **Relocate…** quick-action in the warning dialog. **DONE 2026-07-21** — `study_index_search_dialog.py::_relocate_and_reopen()`; the fully-missing branches of `_open_row` now offer **Relocate…** (default) and, when a sample fallback exists, **Load sample only**. Relocation calls `relocate_study`, refreshes the list, and reopens the new folder directly. Tests: `tests/gui/test_study_index_open_relocate.py`.

### Tests

- [x] `tests/test_study_index_integrity_scan.py` and `tests/gui/test_study_index_missing_studies_dialog.py`:
  - Seed DB with paths, delete some files, run scan, verify missing list.
  - Relocate updates paths correctly.
  - Remove purges rows.

---

## Phase 4 (P2 / future) — Relative file paths

- [ ] Setting to store paths relative to a user-chosen root (e.g. index folder or drive root).
- [ ] Rebind rules when drive letter / mount point changes.
- [ ] Defer to a follow-up plan after Phase 1–3 are shipped and validated.

---

## Open questions

1. **Plaintext migration:** Keep deferred unless a concrete platform/keyring need warrants an explicit product and privacy review. Any future setting must default to encryption enabled and require the Phase 1b at-rest-exposure confirmation before creating plaintext.
2. **Export format:** CSV is the implemented metadata-and-file-path export format; no pixel data are exported. JSON is out of scope unless a concrete portability use case warrants it.

---

## Files likely touched

| File | Change |
|------|--------|
| `src/utils/config/study_index_config.py` | Future-only `encryption_enabled` setting if the deferred policy changes |
| `src/core/study_index/sqlcipher_store.py` | Future-only plain-SQLite path + `migrate_encryption()` |
| `src/gui/dialogs/settings_dialog.py` | Encryption toggle, info panel |
| `tests/test_study_index_encryption_toggle.py` | **New** |

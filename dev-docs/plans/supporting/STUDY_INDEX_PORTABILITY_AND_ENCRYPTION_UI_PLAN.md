# Study Index Portability & Encryption UI Plan

**Status:** Not started  
**Priority:** P1  
**Execution breakdown (Phases A→2, agent-run):** [Study index browser, integrity & portability execution plan](STUDY_INDEX_BROWSER_AND_INTEGRITY_EXECUTION_PLAN.md)
**TO_DO refs:** UX/Workflow — "First-launch study-index opt-in prompt," "Study index — optional encryption (off by default)," "Study index — location & portability UI," "Allow a button in study index that checks all indexed studies still exist," "Study index — relative file paths"

---

## Goal

Expose the study index's encryption, location, and health features through clear in-app UI so users can:

1. Turn encryption **off** (default) or on, with safe migration.
2. See where the DB lives, move it, export/import metadata.
3. Run a bulk **integrity scan** to find missing studies and relocate or remove them.
4. (Future / P2) Store relative file paths for USB portability.

Currently the index is **always SQLCipher-encrypted**, the passphrase is auto-generated in the OS keyring, the DB path is configurable in **Edit → Settings…**, and there is no integrity scan or export/import UI.

---

## Phase 0 — First-open indexing prompt (persistent choice + one-time options)

**Current behavior:** `gui/study_index_consent.py::ensure_study_index_auto_add_consent()` shows a binary **Yes / No** `QMessageBox` on the **first successful load** when no consent is recorded (invoked from `main.py:1564`), and remembers the answer via `study_index_auto_add_consent` / `study_index_auto_add_on_open`. Auto-add defaults **off**.

**Target:** replace the binary prompt with a small custom dialog offering **four** choices, plus inline disclosure of what/where the index is:

- **Always add to index** — set auto-add **on** + record consent; never ask again.
- **Never add to index** — set auto-add **off** + record consent; never ask again.
- **Add this one time** — index the current study now, but **do not** record persistent consent (prompt can appear again later).
- **Skip this one time** — do **not** index now, and **do not** record consent (prompt can appear again later).
- Inline **info disclosure**: where the index is saved (DB path), that it stores clinical metadata + file locations **on this device**, encryption status, and that it can be changed/cleared later in **Settings**. Reuse the Phase 2 "About this index" copy so wording stays consistent.

**Re-prompt cadence for the one-time options (decided 2026-07-20):** the prompt is shown on each load while consent is unrecorded (i.e. `needs_study_index_auto_add_consent()`), so `ADD_ONCE`/`SKIP_ONCE` naturally re-prompt on the next load until the user picks `ALWAYS`/`NEVER`. A "don't ask again this session" nuance can be layered on later if the per-load prompt proves noisy.

### Tasks — **DONE 2026-07-20**

- [x] New dialog `StudyIndexFirstOpenDialog` in `gui/study_index_consent.py` with 4 buttons + an info panel (index location, what's stored, "change later in Settings") and an **Open location** button.
- [x] Return an explicit decision enum `StudyIndexOpenChoice{ALWAYS, NEVER, ADD_ONCE, SKIP_ONCE}` via `prompt_study_index_first_open()`.
- [x] `main.py` load-time call: `ADD_ONCE` indexes just this load via `schedule_index_after_load(..., force=True)` without recording consent; `SKIP_ONCE` skips without recording consent; `ALWAYS`/`NEVER` record consent (via `apply_first_open_choice`).
- [x] Show index location/info inline (shared `gui/study_index_info.py` helper, reused by Phase 2).
- [x] Tests: `test_privacy_storage_controls.py` (choice → config state; one-time leaves consent unrecorded; prompt returns/persists) + `test_index_service.py::test_schedule_force_indexes_when_auto_add_off`.

---

## Phase 1 — Optional encryption toggle + migration

### 1a. Config & backend

- [ ] Add setting `study_index_encryption_enabled` (bool, default **False**) in `ConfigManager` / `study_index_config.py`.
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

- [ ] Add an **About this index…** button or info panel accessible from the Study Index Search dialog and from Settings:
  - **DB path** (clickable → opens containing folder in Explorer/Finder).
  - **Encryption status** (on/off, credential-store location).
  - **Row count** / size on disk.
  - **Last modified** timestamp.
- [x] **Open index location** button → `QDesktopServices.openUrl(QUrl.fromLocalFile(parent_dir))`. **DONE 2026-07-20** — in the Study Index dialog and the first-open prompt, via `gui/study_index_info.py::open_study_index_location()` (opens the nearest existing ancestor if the DB file doesn't exist yet).
- [ ] **Move index…** button:
  - File-save dialog for new location.
  - Copy DB file → verify integrity (open + `PRAGMA integrity_check`) → update config → delete old file.
  - Confirm dialog before proceeding.
- [ ] **Export index…** button:
  - Exports **metadata and file paths only** (CSV or JSON) — no pixel data.
  - Clear label: "This export contains study metadata and file paths. DICOM image data is NOT included."
- [ ] **Import index…** button:
  - Reads a previously exported CSV/JSON and upserts rows into the current DB.
  - Conflict resolution: skip duplicates (same StudyInstanceUID + file path).

### Tests

- [ ] `tests/test_study_index_portability_ui.py`:
  - Move DB, reopen, verify search still works.
  - Export → import round-trip preserves all rows.

---

## Phase 3 — Integrity scan & relocate

- [ ] Add **Check indexed studies…** button to Study Index Search dialog toolbar.
- [ ] `LocalStudyIndexService.integrity_scan() -> list[MissingStudyRecord]`:
  - For each unique `(study_instance_uid, study_root_path)`, check if the root path exists and at least one file path exists on disk.
  - Run in a `QThread` with progress dialog (can be many studies).
  - Return list of studies whose files are missing.
- [ ] Results dialog:
  - Table of missing studies (patient name, study date, modality, old path).
  - Per-row actions: **Relocate…** (file dialog to pick new root), **Remove from index**.
  - Bulk actions: **Remove all missing**, **Cancel**.
- [ ] `LocalStudyIndexService.relocate_study(study_uid, old_root, new_root)`:
  - Update all `file_path` entries by replacing `old_root` prefix with `new_root`.
  - Verify at least one relocated path exists before committing.
- [ ] On load-from-index when files are missing (existing behavior: warns), add a **Relocate…** quick-action in the warning dialog.

### Tests

- [ ] `tests/test_study_index_integrity_scan.py`:
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

1. **Default encryption off:** Confirm this is acceptable from a privacy standpoint. The index stores patient names, IDs, study descriptions — but Privacy Mode already governs on-screen display. Encryption protects the file at rest; without it, the SQLite file is readable by anyone with disk access.
2. **Export format:** CSV (simple, Excel-friendly) vs JSON (richer, nested) vs both? Recommend CSV as primary.
3. **Auto-add on open + canceled loads:** Should partial loads still auto-index? (Separate bug item in TO_DO, but interacts with this plan.)

---

## Files likely touched

| File | Change |
|------|--------|
| `src/utils/config/study_index_config.py` | New `encryption_enabled` setting |
| `src/core/study_index/sqlcipher_store.py` | Plain-SQLite path + `migrate_encryption()` |
| `src/core/study_index/index_service.py` | `integrity_scan()`, `relocate_study()` |
| `src/gui/dialogs/settings_dialog.py` | Encryption toggle, info panel |
| `src/gui/dialogs/study_index_search_dialog.py` | Check button, about-index, relocate |
| `tests/test_study_index_encryption_toggle.py` | **New** |
| `tests/test_study_index_portability_ui.py` | **New** |
| `tests/test_study_index_integrity_scan.py` | **New** |

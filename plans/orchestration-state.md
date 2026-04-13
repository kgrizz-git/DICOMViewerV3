# Orchestration state

## Goal

### Track A — UX / navigator backlog (ongoing)

Backlog from `dev-docs/TO_DO.md`: ship P1 items (MPR navigator assign/clear follow-up, privacy-aware navigator tooltips, slice-position line thickness, **Create MPR view…** menu) and queue P2 items (interactive window map, ROI resize handles, PNG/JPG export anonymization + embedded WL default, navigator slice/frame count). Success: prioritized execution, minimal merge conflict, full pytest from activated venv.

### Track B — Local study database and indexing **[P1]** (new)

Ship a **local metadata index** (background scanning, incremental refresh, path-keyed records for duplicate UIDs across folders), **fast search facets** (patient, modality, date, accession, study description), **optional auto-add on open**, and **index-in-place** first; **managed copy** mode deferred per milestone table. **User-configurable** index DB path; **encryption-at-rest mandatory in MVP** (encrypted SQLite—no unencrypted index DB at ship); **Privacy Mode** masks index/search PHI like metadata. Keep a **decoupled study-query port** so **[P2] PACS-like query/archive** can plug in later without rewriting search UI. Canonical draft plan: **`dev-docs/plans/LOCAL_STUDY_DATABASE_AND_INDEXING_PLAN.md`**. Spec: **`dev-docs/FUTURE_WORK_DETAIL_NOTES.md#local-study-database-and-indexing`**.

**Track B — UX + query follow-up (2026-04-13):** Present index results **grouped by study + containing folder** (logical key: **`StudyInstanceUID` + `study_root_path` / index root**) — **not** one row per file. Show **# instances**, **# series**, **modalities** (sorted unique, comma-separated). **Column order** user-customizable (**drag-reorder** preferred), persisted in config. **Browse vs search:** Current MVP entry is **Tools → Study index search…** only; `StudyIndexStore.search()` returns **flat per-file rows** with a **row limit** — there is **no** “whole database” browse today. Add **File → Open study index…** (or equivalent) so users **browse the full index** and **search in one surface** (see plan: default opens **configured** DB; optional path to open/browse another encrypted DB where key UX allows — document limits).

## Phase

`multi-track` — Track A unchanged (`planning` / pending streams). Track B Stream **G**: **`implementation_active`** (MVP landed). Stream **H**: **`done`** — **SD7** landed; **`python -m pytest tests/ -v`** green (**394** passed, 2026-04-13).

## Execution mode

- Track A: `full` (multi-surface UX + export + ROI).
- Track B: `full` (new subsystem: DB + workers + UI + privacy implications).

## Risk tier

- Track A: `medium` (privacy/tooltips, Qt drag-drop, export pipeline, ROI scene interaction).
- Track B: `medium` (PHI persistence on disk, threading/cancellation, path traversal safety).

## Chain mode

`autonomous`

## Global orchestration guard

| Field | Value |
|-------|-------|
| Orchestrator cycles (this run) | 0 |
| Max orchestrator cycles | 40 |
| Specialist completions (this run) | 0 |
| Max specialist completions | 120 |

## Streams

| Stream | Scope | Status |
|--------|--------|--------|
| A | MPR: assign/clear + menu entry | pending |
| B | Navigator: tooltips + optional slice/frame count | pending |
| C | Window map widget | pending |
| D | ROI edit handles | pending |
| E | Export PNG/JPG options | pending |
| F | Slice position indicator thickness | pending |
| **G** | **Local study DB: DB/indexer/UI (MVP landed; refine via H)** | **implementation_active** |
| **H** | **Study index UX: grouped rows, browse all, column order, File menu** | **done** |

## Assignments

| ID | Owner | Task | Plan / notes | Status |
|----|-------|------|--------------|--------|
| T1 | coder (+ short spec) | MPR thumbnail: assign to empty/focus window via click/drag; clear MPR from window without deleting study MPR | `MprThumbnailWidget`, `SeriesNavigator`, `MprController`, MIME `application/x-dv3-mpr-assign`, `SubWindowContainer.mpr_focus_requested` | pending |
| T2 | coder | Navigator tooltips (study + thumbnails), privacy-aware refresh | `dev-docs/plans/NAVIGATOR_AND_FILE_LOADING_FEEDBACK_PLAN.md` §1 | pending |
| T3 | coder | Window map: click cell → focus + reveal in 1×2/2×1 | `dev-docs/plans/UX_IMPROVEMENTS_BATCH1_PLAN.md` §1 | pending |
| T4 | coder | ROI ellipse/rect resize handles + edit mode | `dev-docs/plans/VIEWER_UX_FEATURES_PLAN.md` §1 | pending |
| T5 | coder | PNG/JPG: anonymize option; default embedded WL | `dev-docs/plans/EXPORT_PRIVACY_AND_WL_DEFAULT_PLAN.md` | pending |
| T6 | coder | User-configurable thickness for slice position indicator | Confirm target widget (crosshair vs slice-location line vs other); may tie to `dev-docs/plans/SLICE_LOCATION_LINE_PLAN.md` | pending |
| T7 | coder | Navigator: show frames/slices count per series (default on, compact) | No dedicated plan in backlog cite — small spec or planner blurb | pending |
| T8 | coder | **Create MPR view…** under Tools or View | Menu placement: confirm with user or follow existing MPR entrypoints | pending |
| **SD0** | **orchestrator** | **Seed plan + state for Track B** | **`dev-docs/plans/LOCAL_STUDY_DATABASE_AND_INDEXING_PLAN.md`** | **done** |
| **SD1** | **orchestrator** (SD1 deliverable landed in plan) | **Spikes: SQLite/WAL + pydicom header-only + Qt worker pattern + single load-path hook for auto-index** | **`dev-docs/plans/LOCAL_STUDY_DATABASE_AND_INDEXING_PLAN.md` § Phase 0 decisions (execution)** | **done** |
| **SD2** | **planner** | **Refine draft plan: schema sketch, `StudyIndexPort` API, task DAG, file ownership** | **Edit:** `LOCAL_STUDY_DATABASE_AND_INDEXING_PLAN.md` | **superseded in part** — MVP + Stream H landed `StudyIndexPort`, schema, and task DAG; remaining Phase‑1 depth (normalization/DTOs, etc.) may still apply per plan |
| **SD3** | **coder** | **Implement streams 2A–2D per plan (after SD2 gate)** | **Branch proposal in HANDOFF** | **pending** |
| **SD4** | **tester** | **pytest strategy: synthetic fixtures, no PHI; full suite after merge** | **`tests/README.md`** | **pending** |
| **SD5** | **researcher** *(optional)* | **SQLite/sqlcipher: `GROUP BY` aggregates, `GROUP_CONCAT(DISTINCT …)` / portable alternatives; pagination cost at large N** | **`dev-docs/plans/LOCAL_STUDY_DATABASE_AND_INDEXING_PLAN.md` § Grouped study query** | **skipped** (coder implemented aggregates + tests) |
| **SD6** | **planner** | **Extend plan: grouped API + pagination policy + File menu entrypoints + Qt model/column-persist spec; task DAG for SD7** | **Edit:** `LOCAL_STUDY_DATABASE_AND_INDEXING_PLAN.md` | **done** |
| **SD7** | **coder** | **Implement after SD6: store/service grouped query + browse mode; refactor dialog (`QTableView`/model); config for column order; File + Tools entry** | **Plan § Stream H;** `study_index_search_dialog.py`, `sqlcipher_store.py`, `index_service.py`, `main_window_menu_builder.py`, `study_index_config.py` | **done** |

## Git / worktree

- Branch: none yet (user controls commits; **do not push** without user request).
- Track A proposal: unchanged (`feature/mpr-navigator-followup`, etc.).
- **Track B proposal:** `feature/local-study-index` (single branch for MVP vertical slice) **or** separate branches per stream (2A/2B) only if two coders — default **one** branch to reduce merge pain.

## Cloud

`none`

## Blockers

`none` — Track B **user decisions (2026-04-13):** configurable DB path; **encrypted SQLite mandatory for MVP** + Privacy Mode for index UI (see plan); MVP scope only.

## Next action

1. **Track A:** T1–T8 backlog as prioritized by user; T8 menu placement still user-dependent.
2. **Track B follow-up (optional):** **`/reviewer`** / **`/secops`** on Stream H delta if desired; plan optional service-level **`privacy_mode`** grouped test still open.
3. **Follow-up (product):** alternate encrypted DB path from **File** menu (browse for index file) remains a documented limitation (Settings + keyring).

## Session checkpoint

- Context: **Track B** — local study index modules exist under **`src/core/study_index/`** and **`study_index_search_dialog.py`** (MVP: Tools entry, flat `search()` + limit). **Stream H** adds grouped rows, full-index browse (paginated), column reorder persistence, **File** menu entry. Open path centralized in **`FileOperationsHandler`** / **`app_signal_wiring`**; recents via **`paths_config`**.
- Locked decisions (**Track B, 2026-04-13**): **User-configurable** study-index DB path. **Disk:** **encrypted SQLite mandatory for MVP** (not hashing for searchable fields—see plan). **UI:** cleartext when privacy off; **Privacy Mode on** → index/search columns follow **same rules as metadata** (`privacy_mode` / patient tags). **Scope:** **MVP only** (no managed copy in this track yet).
- Canonical files: `dev-docs/plans/LOCAL_STUDY_DATABASE_AND_INDEXING_PLAN.md`, `dev-docs/FUTURE_WORK_DETAIL_NOTES.md` (§ Local Study + § PACS), `dev-docs/TO_DO.md`.
- Last verified ref: `run_load_pipeline` success return `loading_pipeline.py` ~358–361; coordinator opens `file_series_loading_coordinator.py` ~538–578; `FileOperationsHandler` → `run_load_pipeline` `file_operations_handler.py` ~168–423.
- Last updated: 2026-04-13 (Stream **H** queued: grouped study UI + browse; SD5–SD7 added; plan doc subsection appended by orchestrator).

## Iteration guard

| Task ID | Cycles | Soft cap | Notes |
|---------|--------|----------|-------|
| T1–T8 | 0 | 5 each | Escalate if DnD or ROI edit loops without progress |
| SD1–SD4 | 0 | 5 each | Escalate if indexer deadlocks or test flakiness without root cause |
| SD5–SD7 | 0 | 5 each | Escalate if grouped-query performance or column-persist regressions loop without root cause |

## Handoff log (newest first)

### 2026-04-13 — primary agent (Track B Stream H / SD7 implementation)

- **Executed:** **`search_grouped_studies`** in **`sqlcipher_store.py`** (`GROUP BY`, counts, `MIN(file_path)` → **`open_file_path`**, modalities normalized); **`StudyIndexPort`** + **`LocalStudyIndexService.search_grouped_studies`**; **`study_index_browser_column_order`** in **`study_index_config.py`** / defaults; dialog refactor **`QTableView`** + **`QAbstractTableModel`**, **Load more**, **`showEvent`** initial browse, column persist; **File → Open study index…** (reuses **`study_index_search_requested`**); tests **`test_study_index_store_grouped_aggregates_and_pagination`**.
- **Verification:** **`python -m pytest tests/ -v`** green — **394 passed** (~68 s).
- **HANDOFF → orchestrator:** Stream **H** marked **`done`**; plan § SD7 checkboxes updated; optional grouped **`privacy_mode`** service test still listed in plan.

### 2026-04-13 — orchestrator (Track B Stream H: grouped study + browse + columns)

- **User ask:** Group results by **study + folder** (`StudyInstanceUID` + `study_root_path`); columns **#instances**, **#series**, **modalities**; drag-reorder columns + persist; document that **no full-DB browse** exists today (Tools search only, flat rows + limit); add **File** entry to open/browse index in one place. **FTS** stays deferred. **Do not push** git.
- **Executed:** Updated **`plans/orchestration-state.md`** (Goal, Phase, Streams G/H, Assignments **SD5–SD7**, Next action, Session checkpoint, Iteration guard). Appended **`dev-docs/plans/LOCAL_STUDY_DATABASE_AND_INDEXING_PLAN.md`** with **§ Grouped study query and index browser (requirements sketch)** — SQL sketch, pagination options, File menu recommendation (configured DB default + optional alternate file), Qt **`QTableView` + model** note vs `QTableWidget`.
- **Delegated:** **SD6** → **`/planner`** (primary). **SD5** researcher optional. **SD7** coder after SD6.
- **HANDOFF → parent:** Status done. Artifacts: `plans/orchestration-state.md`, `dev-docs/plans/LOCAL_STUDY_DATABASE_AND_INDEXING_PLAN.md`. **File menu wording:** recommend **Open study index…**; user may override — not a hard blocker for planning.

### 2026-04-13 — orchestrator execute (Track B SD1 → done, Stream G research_active)

- **Executed:** Updated **`plans/orchestration-state.md`** (Phase/Stream G/SD1/SD2/Next action/session checkpoint). Appended **`dev-docs/plans/LOCAL_STUDY_DATABASE_AND_INDEXING_PLAN.md`** with **Phase 0 decisions (execution)** — R1–R4: `sqlcipher3`/`sqlcipher3-binary` + key UX/threat sketch, pydicom `stop_before_pixels`/`force=True`, Qt `QThread`+worker vs main-thread `run_load_pipeline` + `LoadingProgressManager`, **hook site** `run_load_pipeline` before return (lines 358–361) with coordinator fallback (538–578).
- **Delegated:** **SD2** remains **`pending`** — invoke **`/planner`** (no existing `StudyIndexPort` in `src/` to ground API without planner).
- **HANDOFF → parent:** Status done (orchestrator turn). Artifacts: two files above. Next slash-command: **`/planner`** (SD2). Git: user commits; do not push.

### 2026-04-13 — user decision (Track B: encryption mandatory in MVP)

- **Encrypted SQLite** is **required** for the first shippable local study index—not optional, not deferred after plain `sqlite3`.
- **Artifacts:** `dev-docs/plans/LOCAL_STUDY_DATABASE_AND_INDEXING_PLAN.md`, this file.

### 2026-04-13 — user decisions (Track B: storage + privacy + scope)

- **DB path:** user-configurable (persisted in app config).
- **At rest:** encrypted DB file; hashing not used for searchable PHI; cleartext at SQL layer when DB is open.
- **Privacy Mode:** index/search UI respects same display rules as viewer/metadata when privacy is enabled.
- **Scope:** MVP only (managed copy later).
- **Artifacts:** `dev-docs/plans/LOCAL_STUDY_DATABASE_AND_INDEXING_PLAN.md` (Locked decisions + revised open questions), this file.

### 2026-04-13 — orchestrator (Track B: local study database P1)

- **HANDOFF → parent / user:**
  - **Status:** done (orchestration only)
  - **Artifacts:** `dev-docs/plans/LOCAL_STUDY_DATABASE_AND_INDEXING_PLAN.md`; updated `plans/orchestration-state.md`
  - **Plan deltas:** New draft plan with phases 0–4, streams 2A–2D, MVP vs M2 table, PACS decoupling note
  - **Risks:** PHI on disk; duplicate UID + path semantics must be tested
  - **Recommended next:** **`/researcher`** (SD1), then **`/planner`** (SD2)
  - **Stream:** G
  - **Git:** clean; branch: n/a; worktree: none
  - **Git proposal:** `feature/local-study-index` when coding starts (orchestrator-approved default)
  - **PR:** none
  - **Cloud:** none
  - **Merge recommendation:** n/a

_Specialists append dated subsections above this line._

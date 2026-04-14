# Orchestration state

## Goal

### Track A — UX / navigator backlog (ongoing)

Backlog from `dev-docs/TO_DO.md`: ship P1 items (MPR navigator assign/clear follow-up, privacy-aware navigator tooltips, slice-position line thickness, **Create MPR view…** menu, **View → Fullscreen**) and queue P2 items (interactive window map, ROI resize handles, PNG/JPG export anonymization + embedded WL default, navigator slice/frame count, **duplicate-skip toast** polish, **sync-group title-bar icon**). Success: prioritized execution, minimal merge conflict, full pytest from activated venv.

### Backlog slice — 2026-04-13 (integrated from `dev-docs/TO_DO.md`)

| Priority | Lines | Task ID | Summary |
|----------|-------|---------|---------|
| **P1** | 62 | **T2** | Navigator tooltips (study labels + thumbnails): study description, date, patient name; thumbnails add series description; **Privacy Mode** masks PHI like metadata. Plan: `dev-docs/plans/NAVIGATOR_AND_FILE_LOADING_FEEDBACK_PLAN.md` §1 (`navigator-tooltips-privacy-aware`). |
| **P1** | 66 | **T10** | **View → Fullscreen** (or equivalent): true fullscreen; hide left/right/bottom panes and toolbar; **do not duplicate** existing shortcuts — audit `main_window_*_builder`, `KeyboardEventHandler`, menu accelerators. Plan: `dev-docs/plans/WINDOW_LAYOUT_AND_NAVIGATION_POLISH_PLAN.md` §2 (`view-fullscreen-command-and-shortcut`). **Done** (pytest **421**, 2026-04-13). |
| **P2** | 63 | **T9** | Toast when duplicate/already-loaded files are skipped: **center of screen**, **slightly more opaque** background. Plan: `NAVIGATOR_AND_FILE_LOADING_FEEDBACK_PLAN.md` §2 (`duplicate-skip-toast-center--more-opaque`). **Done** (pytest **425**, 2026-04-13). |
| **P2** | 74 | **T11** | Small **colored icon** on each subwindow **title bar** for **sync group** membership (group color). No dedicated plan in TO_DO — spec anchor: `WINDOW_LAYOUT_AND_NAVIGATION_POLISH_PLAN.md` (window chrome / layout stream) + short **coder** notes in HANDOFF acceptable. **Code hints:** `SubWindowContainer` (or equivalent), sync-link / sync-group model, title-bar widgets. **Done** (pytest **429**, 2026-04-13). |
| **P2** | 83 | **SD8** | SQLite **FTS5** full-text search for local study index (study/series description, etc.) — **deferred past MVP** per TO_DO. Canonical: `dev-docs/plans/LOCAL_STUDY_DATABASE_AND_INDEXING_PLAN.md`. **Depends:** Track B MVP stable (`StudyIndexStore` / schema); **owner:** **planner** spike (schema + migration + query API) then **coder** after gate — **sequence after** current MVP refinements (Streams G/H). |

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
| Orchestrator cycles (this run) | 5 |
| Max orchestrator cycles | 40 |
| Specialist completions (this run) | 4 |
| Max specialist completions | 120 |

## Streams

| Stream | Scope | Status |
|--------|--------|--------|
| A | MPR: assign/clear + menu entry | pending |
| B | Navigator: **T2** tooltips (P1) **done**; **T7** slice/frame count; **T9** duplicate-skip toast (P2) **done** | active (**T7** open) |
| C | Window map widget | pending |
| D | ROI edit handles | pending |
| E | Export PNG/JPG options | pending |
| F | Slice position indicator thickness | pending |
| **G** | **Local study DB: DB/indexer/UI (MVP landed; refine via H)** | **implementation_active** |
| **H** | **Study index UX: grouped rows, browse all, column order, File menu** | **done** |
| **J** | **Window layout polish:** **T10** fullscreen (P1) **done**; **T11** sync-group title-bar icon (P2) **done** | **done** (no pending T10/T11 this slice) |
| **L** | **Track B — FTS5** (**SD8**): deferred post-MVP; planner → coder after schema | deferred |

## Assignments

| ID | Owner | Task | Plan / notes | Status |
|----|-------|------|--------------|--------|
| T1 | coder (+ short spec) | MPR thumbnail: assign to empty/focus window via click/drag; clear MPR from window without deleting study MPR | `MprThumbnailWidget`, `SeriesNavigator`, `MprController`, MIME `application/x-dv3-mpr-assign`, `SubWindowContainer.mpr_focus_requested` | pending |
| T2 | coder | **P1** Navigator tooltips: study **labels** + **thumbnails** — study description, date, patient name; thumbnails **+ series description**; **Privacy Mode** = same PHI masking rules as metadata (refresh on privacy toggle). **Files:** `gui/series_navigator_view.py`, `gui/series_navigator_model.py`, privacy helpers used by metadata/overlay | `dev-docs/plans/NAVIGATOR_AND_FILE_LOADING_FEEDBACK_PLAN.md` §1 | **done** |
| **T9** | **coder** | **P2** Duplicate/already-loaded skip **toast**: center screen, more opaque background | Same plan **§2**; **Files:** `main_window.py` (`show_toast_message` — **overlap with T10** if toast API changes again), `file_series_loading_coordinator.py`, `tests/test_main_window_toast.py`, `CHANGELOG.md` | **done** (**425** pytest green, 2026-04-13) |
| **T10** | **coder** | **P1** **View → Fullscreen**: true fullscreen; hide left/right/bottom + toolbar; **shortcut audit** — no duplicate accelerators vs existing | `dev-docs/plans/WINDOW_LAYOUT_AND_NAVIGATION_POLISH_PLAN.md` §2; **Files:** `main_window_*_builder.py`, `KeyboardEventHandler` (or `main_app_key_event_filter.py`), `MultiWindowLayout` / splitter visibility | **done** (**421** pytest green, 2026-04-13) |
| **T11** | **coder** | **P2** Subwindow **title bar**: small icon tinted to **sync group** color | Plan anchor: `dev-docs/plans/WINDOW_LAYOUT_AND_NAVIGATION_POLISH_PLAN.md`; **Files:** `slice_sync_group_palette.py`, `sub_window_container.py`, `main.py`, `tests/test_slice_sync_group_palette.py` | **done** (**429** pytest green, 2026-04-13) |
| **SD8** | **planner** → **coder** | **P2 (deferred)** **FTS5** on local study index — study/series description search; post-MVP | `LOCAL_STUDY_DATABASE_AND_INDEXING_PLAN.md`; `StudyIndexStore` / `sqlcipher_store.py`; spike: schema, migration, `StudyIndexPort` query surface | **deferred** (after Stream **G** MVP + H refinements) |
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

1. **Backlog slice (TO_DO L62, L63, L66, L74, L83):** **T2**, **T9**, **T10**, **T11** are **done**; **SD8** (FTS5) stays **deferred post-MVP** — **do not dispatch** **`planner`** / **`coder`** until the user lifts deferral (prefer no automatic SD8 spike queue).
2. **Stream J:** **T10** / **T11** complete — no pending layout items for this slice.
3. **Optional:** **`reviewer`** on **T11** artifacts (`slice_sync_group_palette.py`, `sub_window_container.py`, `main.py`, palette tests) or earlier toast/fullscreen deltas; **`tester`** ledger if desired — not blocking idle state.
4. **Track A (Stream B):** **T7** slice/frame count still **pending**; other Track A rows (T1, T3–T8) unchanged.
5. **Track B:** Optional **`/reviewer`** / **`/secops`** on Stream H delta; grouped **`privacy_mode`** service test still open per plan notes.
6. **Git:** **do not push** without user request.

## Session checkpoint

- Context: **Track B** — local study index modules exist under **`src/core/study_index/`** and **`study_index_search_dialog.py`** (MVP: Tools entry, flat `search()` + limit). **Stream H** adds grouped rows, full-index browse (paginated), column reorder persistence, **File** menu entry. Open path centralized in **`FileOperationsHandler`** / **`app_signal_wiring`**; recents via **`paths_config`**.
- Locked decisions (**Track B, 2026-04-13**): **User-configurable** study-index DB path. **Disk:** **encrypted SQLite mandatory for MVP** (not hashing for searchable fields—see plan). **UI:** cleartext when privacy off; **Privacy Mode on** → index/search columns follow **same rules as metadata** (`privacy_mode` / patient tags). **Scope:** **MVP only** (no managed copy in this track yet).
- Canonical files: `dev-docs/plans/LOCAL_STUDY_DATABASE_AND_INDEXING_PLAN.md`, `dev-docs/FUTURE_WORK_DETAIL_NOTES.md` (§ Local Study + § PACS), `dev-docs/TO_DO.md`.
- Last verified ref: `run_load_pipeline` success return `loading_pipeline.py` ~358–361; coordinator opens `file_series_loading_coordinator.py` ~538–578; `FileOperationsHandler` → `run_load_pipeline` `file_operations_handler.py` ~168–423.
- **Backlog slice 2026-04-13:** **T2** **landed** (navigator tooltips; pytest **416** green); **T10** **landed** (fullscreen; pytest **421** green); **T9** **landed** (duplicate-skip toast; pytest **425** green); **T11** **landed** (sync-group title-bar dot; pytest **429** green; L74); **SD8** FTS5 deferred (L83). Streams **B** (T2/T9 done; **T7** open), **J** (**T10**/**T11** done), **L** (FTS deferred).
- **T2 locked UX (2026-04-13):** Navigator tooltips use **plain text**; **Privacy Mode** shows **patient-name tags only** (group **0010**, same family as metadata); **dates** shown as **YYYY-MM-DD** when the value parses as a valid date.
- Last updated: 2026-04-13 (orchestrator: merged **T11** → done; guard cycles **5** / specialist completions **4**; slice queue idle except **SD8** deferral).

## Iteration guard

| Task ID | Cycles | Soft cap | Notes |
|---------|--------|----------|-------|
| T1–T11 | 0 | 5 each | Escalate if DnD, ROI edit, navigator tooltip, or fullscreen shortcut loops without progress |
| SD8 | 0 | 3 | FTS5 spike ↔ implementation; escalate if schema migration unclear |
| SD1–SD4 | 0 | 5 each | Escalate if indexer deadlocks or test flakiness without root cause |
| SD5–SD7 | 0 | 5 each | Escalate if grouped-query performance or column-persist regressions loop without root cause |

## Handoff log (newest first)

### 2026-04-13 — orchestrator (autonomous merge: **T11** done → slice queue complete)

- **Parent ask:** **coder** finished **T11** (sync-group title-bar dot; **429** pytest green). Merge **Assignments T11** → **done**; **Stream J** complete (no pending T10/T11); **Specialist completions** **3→4**; **Orchestrator cycles** **4→5**; record artifacts; TO_DO recap L62 **T2**, L63 **T9**, L66 **T10**, L74 **T11** done; L83 **SD8** deferred — **NEXT_TASK_TOOL** **`none`**; **do not push**.
- **Executed:** **Assignments** **T11** → **done**. **Stream J** → **done** (T10/T11 complete). **Global orchestration guard** incremented as above. **TO_DO:** L62/L63 checked to match landed work (L66/L74 already checked).
- **Coder artifacts (T11):** `src/utils/slice_sync_group_palette.py`; `src/gui/sub_window_container.py`; `src/main.py`; `tests/test_slice_sync_group_palette.py`; `CHANGELOG.md` [Unreleased]; `dev-docs/TO_DO.md` (L74).
- **HANDOFF → parent:** **NEXT_TASK_TOOL** **`none`**. **NEXT_TASK_TOOL_SECOND** **`none`**. Optional later: **`planner`** spike for **SD8** only after user lifts deferral.

### 2026-04-13 — coder (**T11** sync-group title-bar icon)

- **HANDOFF → orchestrator:**
- Status: done
- Artifacts: `src/utils/slice_sync_group_palette.py`; `src/gui/sub_window_container.py`; `src/main.py`; `tests/test_slice_sync_group_palette.py`; `CHANGELOG.md` [Unreleased]; `dev-docs/TO_DO.md` (L74 checked)
- Plan deltas: **T11** done; orchestrator may set **Assignments T11** → **done**, **Stream J**, **Next action**
- **Indexing contract:** `slice_sync_groups` = **view** indices 0–3 (`subwindows[i]` / `SliceSyncCoordinator`), not grid **slot** indices; swap does not require a separate indicator refresh.
- **Icon hidden when:** sync off; pane not in any group; singleton groups filtered by config.
- Risks: none
- Recommended next: **reviewer**; optional **ux** (light/dark strip)
- Stream: J
- Git: dirty; branch: n/a; worktree: none
- Git proposal: none
- PR: none
- Cloud: none
- Merge recommendation: n/a
- **Verify:** `python -m pytest tests/ -v --tb=short` — **429 passed** (venv), ~47 s

### 2026-04-13 — orchestrator (autonomous merge: **T9** done → dispatch **T11**)

- **Parent ask:** **coder** finished **T9** (duplicate-skip toast center + alpha; **425** pytest green). Merge **Assignments** / **Stream B** / guard; **Handoff** artifacts: `main_window.py` (toast API — note overlap with **T10** if touched again), `file_series_loading_coordinator.py`, `tests/test_main_window_toast.py`, `CHANGELOG.md`. **Next:** **T11** sync-group title-bar icon (`TO_DO` L74); **NEXT_TASK_TOOL_SECOND** **none**; **SD8** FTS5 **deferred**; **do not push**.
- **Executed:** **Assignments** **T9** → **done**. **Stream B** → **T9** complete; **T7** remains. **Global orchestration guard:** **Orchestrator cycles** **3→4**; **Specialist completions** **2→3**.
- **Coder artifacts (T9):** `src/gui/main_window.py`, `src/core/file_series_loading_coordinator.py`, `tests/test_main_window_toast.py`, `CHANGELOG.md` [Unreleased].
- **HANDOFF → parent:** **NEXT_TASK_TOOL** **`coder`** on **T11** (subwindow title-bar icon colored by sync group). **NEXT_TASK_TOOL_SECOND** **`none`**.

### 2026-04-13 — coder (**T9** duplicate-skip toast: center + more opaque)

- **HANDOFF → orchestrator:**
- Status: done
- Artifacts: `src/gui/main_window.py` (`show_toast_message`: `position`, `bg_alpha` clamped [0,1], `center` vs `bottom-center`); `src/core/file_series_loading_coordinator.py` (`_show_duplicate_skip_toast`, two branches in `handle_additive_load`); `tests/test_main_window_toast.py`; `CHANGELOG.md` [Unreleased]
- Plan deltas: `dev-docs/plans/NAVIGATOR_AND_FILE_LOADING_FEEDBACK_PLAN.md` §2 implemented; orchestrator may set **Assignments T9** → **done** and Stream **B** (T9 closed)
- Risks: none
- Recommended next: **reviewer** on touched paths; optional **tester** ledger
- Stream: B
- Git: dirty; branch: n/a; worktree: none
- Git proposal: none
- PR: none
- Cloud: none
- Merge recommendation: n/a
- **Verify:** `python -m pytest tests/ -v --tb=short` — **425 passed** (venv), ~57 s

### 2026-04-13 — orchestrator (autonomous merge: **T10** done → dispatch **T9**)

- **Parent ask:** **coder** finished **T10** (View Fullscreen; **421** pytest green). Merge **Assignments** / **Stream J** / guard; append handoff with T10 file list; **Next:** **T9** duplicate-skip toast per `NAVIGATOR_AND_FILE_LOADING_FEEDBACK_PLAN.md` §2; **NEXT_TASK_TOOL_SECOND** **none** vs **T11**; **do not push**.
- **Executed:** **Assignments** **T10** → **done**. **Stream J** → **T10** complete; **T11** pending. **Global orchestration guard:** **Orchestrator cycles** **2→3**; **Specialist completions** **1→2**.
- **Coder artifacts (T10):** `src/gui/main_window.py`, `src/gui/main_window_menu_builder.py`, `src/core/main_app_key_event_filter.py`, `tests/test_main_window_fullscreen.py`, `CHANGELOG.md`, `dev-docs/TO_DO.md` (fullscreen item checked).
- **HANDOFF → parent:** **NEXT_TASK_TOOL** **`coder`** on **T9** (toast center + more opaque). **NEXT_TASK_TOOL_SECOND** **`none`** — **T11** shares window chrome risk; sequence after **T9** unless coder confirms disjoint work.

### 2026-04-13 — coder (**T10** View → Fullscreen)

- **HANDOFF → orchestrator:**
- Status: done
- Artifacts: `src/gui/main_window.py`, `src/gui/main_window_menu_builder.py`, `src/core/main_app_key_event_filter.py`, `tests/test_main_window_fullscreen.py`, `CHANGELOG.md`, `dev-docs/TO_DO.md` (fullscreen item checked)
- Plan deltas: `WINDOW_LAYOUT_AND_NAVIGATION_POLISH_PLAN.md` §2 implemented (menu + snapshot restore + F11/Escape policy); orchestrator may set **Assignments T10** → **done** and **Stream J** note.
- **T10 done criteria:** View → **Fullscreen** checkable; **F11** toggle; **Escape** exits fullscreen when `activeModalWidget()` is None and focus is not `QLineEdit`/`QTextEdit`/`QPlainTextEdit`/`QAbstractSpinBox`; enter runs `showFullScreen()` after collapsing splitter to `[0, total, 0]`, hiding navigator container + `main_toolbar`; exit restores snapshot splitter sizes, navigator bar visibility, toolbar visibility, and `showMaximized()` if user was maximized pre-enter; `_on_splitter_moved` skips `config_manager.save_config` while `isFullScreen()` so fullscreen layout does not overwrite defaults; `changeEvent` restores chrome if OS leaves fullscreen; `closeEvent` tears down fullscreen before saving geometry. **Shortcut audit:** no pre-existing **F11** in repo menus/toolbar/handler.
- Risks: none observed
- Recommended next: **reviewer** on touched files; optional **tester** ledger
- Stream: J
- Git: dirty; branch: n/a; worktree: none
- Git proposal: none
- PR: none
- Cloud: none
- Merge recommendation: n/a

### 2026-04-13 — orchestrator (autonomous merge: **T2** done → dispatch **T10**)

- **Parent ask:** Chain after **coder** finished **T2** (416 pytest green); merge Assignments / Stream **B** / guard; record tooltip decisions; **Next:** **T10** then **T9** / **T11**; do not push; repo may be dirty.
- **Executed:** **Assignments** **T2** → **done**. **Stream B** → **T2** complete; **T7** / **T9** remain. **Global orchestration guard:** **Orchestrator cycles** **1→2**; **Specialist completions** **0→1**.
- **Decisions recorded (T2 product surface):** **Privacy Mode** in navigator tooltips = **patient tags only** (DICOM group **0010**); **plain text** tooltips (no rich HTML); **dates** as **YYYY-MM-DD** when valid.
- **Coder artifacts (T2):** `src/gui/series_navigator_model.py`, `src/gui/series_navigator.py`, `src/gui/series_navigator_view.py`, `src/main.py`, `tests/test_series_navigator_tooltips.py`, `CHANGELOG.md`.
- **HANDOFF → parent:** **NEXT_TASK_TOOL** **`coder`** on **T10** (fullscreen + shortcut audit). **NEXT_TASK_TOOL_SECOND** **`none`** — **Next action** sequences **T10** before **T9**/**T11**, and parallel **coder** streams would risk overlapping **main window / menu / chrome** edits (`NEXT_TASK_TOOL_SECOND` checklist not satisfied).

### 2026-04-13 — coder (T2 navigator tooltips, privacy-aware)

- **HANDOFF → orchestrator:**
- Status: done
- Artifacts: `src/gui/series_navigator_model.py`, `src/gui/series_navigator.py`, `src/gui/series_navigator_view.py`, `src/main.py`, `tests/test_series_navigator_tooltips.py`, `CHANGELOG.md`
- Plan deltas: T2 implemented per `dev-docs/plans/NAVIGATOR_AND_FILE_LOADING_FEEDBACK_PLAN.md` §1; orchestrator may set Assignments **T2** → **done** and Stream **B** note.
- Risks: none
- Recommended next: **reviewer** on touched files + **tester** full pytest if not run in CI yet
- Stream: B
- Git: dirty; branch: n/a; worktree: none
- Git proposal: none
- PR: none
- Cloud: none
- Merge recommendation: n/a

### 2026-04-13 — orchestrator (TO_DO backlog slice: navigator tooltips, toast, fullscreen, sync icon, FTS5)

- **User ask:** Integrate `dev-docs/TO_DO.md` items **L62, L63, L66, L74, L83** into state with priorities, owners, dependencies, file hints; increment guard; do not push.
- **Executed:** Goal extended with **Backlog slice — 2026-04-13** table; **T2** row refreshed; new **T9**, **T10**, **T11**, **SD8**; Streams **B** updated, **J** + **L** added; Next action → **P1: coder T2 then T10**; Session checkpoint + Iteration guard updated; **Orchestrator cycles (this run)** → **1**.
- **HANDOFF → parent:** **Recommended first specialist:** **`coder`** on **T2** (highest P1, plan §1, concrete files). **Rationale:** Spec is anchored in existing plan; no planner gate. **T10** (second P1) next for shortcut audit. **Parallel second:** `none` (same Qt surface / one branch default — avoid merge/toolbar conflicts).

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

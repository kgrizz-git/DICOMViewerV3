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
| **P2** | 78 / Features | **SD8** | SQLite **FTS5** full-text search for local study index — **re-queued** (2026-04-14 user slice). Canonical: `dev-docs/plans/LOCAL_STUDY_DATABASE_AND_INDEXING_PLAN.md`. **Depends:** stable `StudyIndexStore` / schema; **owner:** **planner** spike then **coder**; default **after** **MPR2** unless user assigns a second worktree. |

### Backlog slice — 2026-04-14 (from `dev-docs/TO_DO.md` via user `/orchestrator`)

| Priority | TO_DO | Task ID | Summary | Plan (repo paths under `dev-docs/plans/` unless noted) |
|----------|-------|---------|---------|--------|
| **P1** | L85 | **MPR2** | **Save MPRs as DICOM** — derived stack export, new UIDs, metadata from source + `MprResult` | `MPR_DICOM_SAVE_CINE_VIDEO_EXPORT_ANGLE_MEASUREMENT_PLAN.md` §1 |
| **P2** | L60–61 | **T4** + **T12** | **ROI** ellipse/rect **resize/edit handles**; **W/L remembered** when changing series focus and back | `VIEWER_UX_FEATURES_PLAN.md` §§1–2 |
| **P2** | L53 | **T14** | **Toolbar** contents and ordering **customizable** | `UX_IMPROVEMENTS_BATCH1_PLAN.md` §2 |
| **P2** | L52 | **T3** | **Window map** thumbnail in navigator: click cell → focus + reveal (1×2 / 2×1) | `UX_IMPROVEMENTS_BATCH1_PLAN.md` §1 |
| **P2** | L71 | **T7** | Navigator: show **# frames/slices** per series (default **on**, compact) | Small spec acceptable; align with `series_navigator_*` |
| **P2** | L78 | **SD8** | SQLite **FTS5** full-text search on local study index | `LOCAL_STUDY_DATABASE_AND_INDEXING_PLAN.md` — **planner** spike (schema/migration/query API) then **coder** |

**Phasing (recommended):** **Slice 1 — P1:** **MPR2** first (standalone writer + MPR-gated UI; DICOM conformance / UID policy per plan; **risk `high`** → **reviewer** + **tester** + **secops** at slice end). **Slice 2 — P2 navigator cluster:** **T7** then **T3** (same widgets; sequence reduces merge risk) or single **coder** PR with tests. **Slice 3 — P2 viewer:** **T12** (W/L cache keyed by series/view identity) then **T4** (ROI handles — scene interaction; may touch overlapping ROI paths). **Slice 4 — P2 chrome:** **T14** (toolbar model + persistence). **Slice 5 — Track B+:** **SD8** after **MPR2** ship or in parallel **only** if second branch/worktree — default **sequence after** MPR2 to limit merge conflicts on `main_window` / export paths.

### Track B — Local study database and indexing **[P1]** (new)

Ship a **local metadata index** (background scanning, incremental refresh, path-keyed records for duplicate UIDs across folders), **fast search facets** (patient, modality, date, accession, study description), **optional auto-add on open**, and **index-in-place** first; **managed copy** mode deferred per milestone table. **User-configurable** index DB path; **encryption-at-rest mandatory in MVP** (encrypted SQLite—no unencrypted index DB at ship); **Privacy Mode** masks index/search PHI like metadata. Keep a **decoupled study-query port** so **[P2] PACS-like query/archive** can plug in later without rewriting search UI. Canonical draft plan: **`dev-docs/plans/LOCAL_STUDY_DATABASE_AND_INDEXING_PLAN.md`**. Spec: **`dev-docs/FUTURE_WORK_DETAIL_NOTES.md#local-study-database-and-indexing`**.

**Track B — UX + query follow-up (2026-04-13):** Present index results **grouped by study + containing folder** (logical key: **`StudyInstanceUID` + `study_root_path` / index root**) — **not** one row per file. Show **# instances**, **# series**, **modalities** (sorted unique, comma-separated). **Column order** user-customizable (**drag-reorder** preferred), persisted in config. **Browse vs search:** Current MVP entry is **Tools → Study index search…** only; `StudyIndexStore.search()` returns **flat per-file rows** with a **row limit** — there is **no** “whole database” browse today. Add **File → Open study index…** (or equivalent) so users **browse the full index** and **search in one surface** (see plan: default opens **configured** DB; optional path to open/browse another encrypted DB where key UX allows — document limits).

## Phase

`multi-track` — **2026-04-14:** **MPR2** slice **`complete`** (export / verification gate **closed**): **reviewer** + **`MPR2-theme`** + **`tester`** (**439**→**441**/0 **`pytest`** after **T7**/**T3**/**T12** + display-config tests, **`logs/test-ledger.md`**) + **`secops`** targeted delta — **Semgrep** `p/security-audit` + `p/python` on scoped files **0** findings; artifact **`assessments/security-assessment-20260414-2000.md`**. **Post-ship hotfix (same day):** runtime **pydicom** **ambiguous VR OB/OW** on **Pixel Data** `(7FE0,0010)` under **ExplicitVRLittleEndian** — **parent/coder** fix: write **Pixel Data** as explicit **`OW`** **`DataElement`** in **`src/core/mpr_dicom_export.py`**, test assert, **`CHANGELOG`** **Fixed**; **user should re-smoke** **File → Save MPR as DICOM…** after the fix lands. **Track A P2 (2026-04-14 parent pass):** **`T7`** (navigator slice/frame count badge + config **`navigator_show_slice_frame_count`** + View menu), **`T3`** (window slot map **`cell_clicked`**, popup drag **top bar only**, **`main._on_window_slot_map_cell_clicked`**, **`MultiWindowLayout.set_focused_subwindow`** re-**`_arrange_subwindows`** for **1×2**/**2×1**), **`T12`** (**`ViewStateManager._user_wl_cache`**, save on series switch, restore on return, clear on **`reset_view`**, clear all on **`reset_series_tracking`**) + **`CHANGELOG`** [Unreleased] + **`default_config`** in **`config_manager.py`** — **all landed**. **Deferred this pass:** **`T4`** (ROI resize handles), **`T14`** (toolbar customization), **`SD8`** FTS5 (store migration + UI). **Next default:** **`coder`** **`T4`** *or* **`planner`** **`SD8`** if FTS5 spike first; **`SD8`** parallel only with second **worktree/branch** (**`NEXT_TASK_TOOL_SECOND: none`** on single branch).

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
| Orchestrator cycles (this run) | 15 |
| Max orchestrator cycles | 40 |
| Specialist completions (this run) | 10 |
| Max specialist completions | 120 |

## Streams

| Stream | Scope | Status |
|--------|--------|--------|
| A | MPR: assign/clear + menu entry | pending |
| B | Navigator: **T2** tooltips (P1) **done**; **T7** slice/frame count **done** (2026-04-14); **T9** duplicate-skip toast (P2) **done** | **T7** **done** — **T14** deferred |
| C | Window map widget (**T3**) | **done** (2026-04-14) |
| D | ROI edit handles (**T4** — deferred) | pending |
| E | Export PNG/JPG options | pending |
| F | Slice position indicator thickness | pending |
| **G** | **Local study DB: DB/indexer/UI (MVP landed; refine via H)** | **implementation_active** |
| **H** | **Study index UX: grouped rows, browse all, column order, File menu** | **done** |
| **J** | **Window layout polish:** **T10** fullscreen (P1) **done**; **T11** sync-group title-bar icon (P2) **done** | **done** (no pending T10/T11 this slice) |
| **L** | **Track B — FTS5** (**SD8**): user re-queued 2026-04-14; planner → coder (after **MPR2** unless second branch) | **queued** |
| **M** | **MPR DICOM export** (**MPR2** P1): save computed MPR stack as DICOM per plan §1 | **done** + **hotfix** (2026-04-14): **Pixel Data** explicit **`OW`** — **re-smoke** export after fix |

## Assignments

| ID | Owner | Task | Plan / notes | Status |
|----|-------|------|--------------|--------|
| T1 | coder (+ short spec) | MPR thumbnail: assign to empty/focus window via click/drag; clear MPR from window without deleting study MPR | `MprThumbnailWidget`, `SeriesNavigator`, `MprController`, MIME `application/x-dv3-mpr-assign`, `SubWindowContainer.mpr_focus_requested` | pending |
| T2 | coder | **P1** Navigator tooltips: study **labels** + **thumbnails** — study description, date, patient name; thumbnails **+ series description**; **Privacy Mode** = same PHI masking rules as metadata (refresh on privacy toggle). **Files:** `gui/series_navigator_view.py`, `gui/series_navigator_model.py`, privacy helpers used by metadata/overlay | `dev-docs/plans/NAVIGATOR_AND_FILE_LOADING_FEEDBACK_PLAN.md` §1 | **done** |
| **T9** | **coder** | **P2** Duplicate/already-loaded skip **toast**: center screen, more opaque background | Same plan **§2**; **Files:** `main_window.py` (`show_toast_message` — **overlap with T10** if toast API changes again), `file_series_loading_coordinator.py`, `tests/test_main_window_toast.py`, `CHANGELOG.md` | **done** (**425** pytest green, 2026-04-13) |
| **T10** | **coder** | **P1** **View → Fullscreen**: true fullscreen; hide left/right/bottom + toolbar; **shortcut audit** — no duplicate accelerators vs existing | `dev-docs/plans/WINDOW_LAYOUT_AND_NAVIGATION_POLISH_PLAN.md` §2; **Files:** `main_window_*_builder.py`, `KeyboardEventHandler` (or `main_app_key_event_filter.py`), `MultiWindowLayout` / splitter visibility | **done** (**421** pytest green, 2026-04-13) |
| **T11** | **coder** | **P2** Subwindow **title bar**: small icon tinted to **sync group** color | Plan anchor: `dev-docs/plans/WINDOW_LAYOUT_AND_NAVIGATION_POLISH_PLAN.md`; **Files:** `slice_sync_group_palette.py`, `sub_window_container.py`, `main.py`, `tests/test_slice_sync_group_palette.py` | **done** (**429** pytest green, 2026-04-13) |
| **SD8** | **planner** → **coder** | **P2** **FTS5** full-text search on local study index (study/series description, etc.) | `LOCAL_STUDY_DATABASE_AND_INDEXING_PLAN.md`; `StudyIndexStore` / `sqlcipher_store.py`; spike: schema, migration, query API + UI | **queued** (start after **MPR2** unless user approves parallel branch) |
| T3 | coder | Window map: click cell → focus + reveal in 1×2/2×1 (`cell_clicked`, popup drag top-bar only, `main._on_window_slot_map_cell_clicked`, `MultiWindowLayout.set_focused_subwindow` → `_arrange_subwindows`) | `dev-docs/plans/UX_IMPROVEMENTS_BATCH1_PLAN.md` §1 | **done** (2026-04-14; full **441** pytest) |
| T4 | coder | ROI ellipse/rect resize handles + edit mode | `dev-docs/plans/VIEWER_UX_FEATURES_PLAN.md` §1 | pending (**next** P2 viewer slice unless **`SD8`** spike first) |
| **T12** | **coder** | **P2** Window/level **remembered per series** — **`ViewStateManager._user_wl_cache`**, save on series switch, restore on return, clear on **`reset_view`**, clear all on **`reset_series_tracking`** | `dev-docs/plans/VIEWER_UX_FEATURES_PLAN.md` §2 | **done** (2026-04-14; full **441** pytest) |
| **T14** | **coder** | **P2** Toolbar **contents + ordering** customizable; persist in config | `dev-docs/plans/UX_IMPROVEMENTS_BATCH1_PLAN.md` §2 | **pending** |
| **MPR2** | **coder** | **P1** **Save MPR as DICOM** — entry when focused pane is MPR; `write_mpr_series`-style module; new UIDs; tests with synthetic `MprResult` | `dev-docs/plans/MPR_DICOM_SAVE_CINE_VIDEO_EXPORT_ANGLE_MEASUREMENT_PLAN.md` §1; see **Prerequisites** / **Design decisions** table in plan | **done** (2026-04-14) — **slice gates:** **reviewer** / **`tester`** (full suite **439**→**441**/0 after Track A P2 batch) / **`secops` done** (Semgrep scoped **0** findings; **`assessments/security-assessment-20260414-2000.md`**). **Typing:** `tests/test_mpr_dicom_export.py` — `basedpyright` **0** errors; **4** pytest. **Hotfix (2026-04-14):** **pydicom** ambiguous **OB/OW** on **(7FE0,0010)** — write **Pixel Data** as explicit **`OW`** **`DataElement`** (`mpr_dicom_export.py`), test assert, **`CHANGELOG`** **Fixed** — **user re-smoke** **Save MPR as DICOM** |
| **MPR2-theme** | **coder** | **`TestGetThemeViewerBackgroundColor`** — `src/gui/main_window_theme.py` letterbox / `get_theme_viewer_background_color` aligned with `tests/test_main_window_theme.py`. | `tests/test_main_window_theme.py`; `CHANGELOG` if user-visible | **done** (**2026-04-14** — full suite green) |
| T5 | coder | PNG/JPG: anonymize option; default embedded WL | `dev-docs/plans/EXPORT_PRIVACY_AND_WL_DEFAULT_PLAN.md` | pending |
| T6 | coder | User-configurable thickness for slice position indicator | Confirm target widget (crosshair vs slice-location line vs other); may tie to `dev-docs/plans/SLICE_LOCATION_LINE_PLAN.md` | pending |
| T7 | coder | Navigator: show frames/slices count per series (**`navigator_show_slice_frame_count`**, View menu, default on, compact) | `series_navigator_*`, `display_config`; **CHANGELOG** [Unreleased]; **`default_config`** in **`config_manager.py`** | **done** (2026-04-14; +**2** display-config tests → **441** pytest) |
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

**MPR2 slice:** **Cleared (2026-04-14)** — theme + full **`pytest`** + targeted **`secops`** (**`assessments/security-assessment-20260414-2000.md`**) — **no** open verification blockers on export slice. **Informational:** **MPR2** runtime **ambiguous VR** on save (**OB/OW** for **Pixel Data**) — **hotfix** in flight (**explicit `OW`**); not a merge **blocker** for **T7** once parent lands fix. **Informational (secops):** anonymizer scope **0010**-only; product may later tighten de-ID / UX copy if desired. **Track B** user decisions (2026-04-13) unchanged: configurable DB path; encrypted SQLite MVP; Privacy Mode for index UI.

## Next action

1. **Default dispatch (user chose idle orchestrator this turn):** **`Task(coder)`** on **`T4`** — ROI ellipse/rect **resize/edit handles** per **`VIEWER_UX_FEATURES_PLAN.md`** §1. **Alternate:** **`Task(planner)`** on **`SD8`** — **FTS5** spike (store migration + query API + UI) per **`LOCAL_STUDY_DATABASE_AND_INDEXING_PLAN.md`** when FTS5 should precede ROI work.
2. **After MPR2 Pixel Data VR hotfix lands:** **user** (or **`tester`** on request) **re-smoke** **File → Save MPR as DICOM…** (Explicit VR save path); optional **`reviewer`** if diff is large.
3. **P2 phasing (2026-04-14):** **T7** ✓ **T3** ✓ **T12** ✓ **landed**; **next** **T4** (ROI) → **T14** (toolbar); **`SD8`** after spike or **parallel** only with **second worktree** — **`NEXT_TASK_TOOL_SECOND: none`** on single branch.
4. **Optional `ux`:** Short manual smoke for **window map** + **navigator counts** + **W/L return** when convenient.
5. **Git:** **do not push** without user request.

## Session checkpoint

- Context: **Track B** — local study index modules exist under **`src/core/study_index/`** and **`study_index_search_dialog.py`** (MVP: Tools entry, flat `search()` + limit). **Stream H** adds grouped rows, full-index browse (paginated), column reorder persistence, **File** menu entry. Open path centralized in **`FileOperationsHandler`** / **`app_signal_wiring`**; recents via **`paths_config`**.
- Locked decisions (**Track B, 2026-04-13**): **User-configurable** study-index DB path. **Disk:** **encrypted SQLite mandatory for MVP** (not hashing for searchable fields—see plan). **UI:** cleartext when privacy off; **Privacy Mode on** → index/search columns follow **same rules as metadata** (`privacy_mode` / patient tags). **Scope:** **MVP only** (no managed copy in this track yet).
- Canonical files: `dev-docs/plans/LOCAL_STUDY_DATABASE_AND_INDEXING_PLAN.md`, `dev-docs/FUTURE_WORK_DETAIL_NOTES.md` (§ Local Study + § PACS), `dev-docs/TO_DO.md`.
- Last verified ref: `run_load_pipeline` success return `loading_pipeline.py` ~358–361; coordinator opens `file_series_loading_coordinator.py` ~538–578; `FileOperationsHandler` → `run_load_pipeline` `file_operations_handler.py` ~168–423.
- **Backlog slice 2026-04-13:** **T2** **landed** (navigator tooltips; pytest **416** green); **T10** **landed** (fullscreen; pytest **421** green); **T9** **landed** (duplicate-skip toast; pytest **425** green); **T11** **landed** (sync-group title-bar dot; pytest **429** green; L74); **SD8** FTS5 deferred (L83). Streams **B** (T2/T9 done; **T7** open), **J** (**T10**/**T11** done), **L** (FTS deferred).
- **T2 locked UX (2026-04-13):** Navigator tooltips use **plain text**; **Privacy Mode** shows **patient-name tags only** (group **0010**, same family as metadata); **dates** shown as **YYYY-MM-DD** when the value parses as a valid date.
- Last updated: 2026-04-14 — **T7**/**T3**/**T12** landed (parent pass); full **`pytest`** **441**/0; **`CHANGELOG`** [Unreleased] + **`navigator_show_slice_frame_count`** / **`default_config`**; defer **T4**, **T14**, **SD8**; orchestrator guard cycles **14→15** (prior: **MPR2** OB/OW hotfix + **re-smoke** note still applies).
- **2026-04-14:** User `/orchestrator` integrated TO_DO **L52, L53, L60–61, L71, L78, L85** → **Assignments** **MPR2**, **T12**, **T14**; **SD8** **queued**; **Stream M** + **L** updated; **Orchestrator cycles** **6→7**.
- **2026-04-14 (post-MPR2 coder):** **Stream M** → **done**; **Assignments** **MPR2** → **done** (implementation + `tests/test_mpr_dicom_export.py` **4** passed; `basedpyright` clean on touched modules); disk verified: `mpr_dicom_export.py`, `mpr_dicom_save_dialog.py`, wiring grep OK. Full **`pytest tests/`** **436 passed / 3 failed** (`test_main_window_theme.py`). **Orchestrator cycles** **7→8**; **Specialist completions** **4→5**.
- **2026-04-14 (post-MPR2 reviewer):** Reviewer verdict for **MPR2** = **approved**, merge recommendation **yes_with_followups**. Follow-ups captured: coder fix `basedpyright` errors in `tests/test_mpr_dicom_export.py` (typing-only), then batch **tester** + ledger, then targeted **secops**; optional **debugger** for the 3 orthogonal theme failures only if tester flags coupling. **Orchestrator cycles** **8→9**; **Specialist completions** **5→6**.
- **2026-04-14 (post-MPR2 coder typing follow-up):** **`tests/test_mpr_dicom_export.py`** — `basedpyright --level error` **0** errors on file; `pytest tests/test_mpr_dicom_export.py -v` **4** passed. **Orchestrator cycles** **9→10**; **Specialist completions** **6→7**. **Next:** **`tester`** full suite + **`logs/test-ledger.md`**, then **`secops`** delta.
- **2026-04-14 (post-MPR2 `tester`):** Full **`pytest tests/`** — **436** passed, **3** failed (theme `TestGetThemeViewerBackgroundColor` only); MPR export collection green; ledger updated. **Orchestrator cycles** **10→11**; **Specialist completions** **7→8**. **Decision:** **`secops` ∥ `coder`** rejected — **ordering** + same-branch **git** checklist; run **`coder`** theme fix first, then **re-`tester`**, then **`secops`**.
- **2026-04-14 (MPR2 slice — theme + batch `tester` green):** **`MPR2-theme`** resolved (letterbox / `get_theme_viewer_background_color` vs **`tests/test_main_window_theme.py`**); full **`pytest tests/`** **439** passed, **0** failed; **`logs/test-ledger.md`** green run. **MPR2** slice: **`secops`** only remaining gate. **Orchestrator cycles** **11→12**; **Specialist completions** **8→9** (re-**`tester`** gate).
- **2026-04-14 (MPR2 slice — `secops` closed):** Targeted **Semgrep** `p/security-audit` + `p/python` on scoped paths → **0** findings; **`assessments/security-assessment-20260414-2000.md`**; pip-audit clean on **requirements** pass; manual review: no RCE/path escape; anonymize scope informational (**0010** only). **Assignments** **MPR2** → **`secops` done** / slice **`complete`**. **Orchestrator cycles** **12→13**; **Specialist completions** **9→10**.

## Iteration guard

| Task ID | Cycles | Soft cap | Notes |
|---------|--------|----------|-------|
| T1–T11 | 0 | 5 each | Escalate if DnD, ROI edit, navigator tooltip, or fullscreen shortcut loops without progress |
| SD8 | 0 | 4 | FTS5 spike ↔ implementation; escalate if schema migration unclear |
| MPR2 | 0 | 5 | Escalate if SOP class / UID / pixel mapping blocks export without product decision |
| T12, T14 | 0 | 4 each | W/L cache key semantics; toolbar persistence vs upgrades |
| SD1–SD4 | 0 | 5 each | Escalate if indexer deadlocks or test flakiness without root cause |
| SD5–SD7 | 0 | 5 each | Escalate if grouped-query performance or column-persist regressions loop without root cause |

## Handoff log (newest first)

### 2026-04-14 — orchestrator (parent backlog merge: **T7**/**T3**/**T12** **done**, **441** pytest; defer **T4**/**T14**/**SD8**)

- **One-line merge:** Parent landed **T7**/**T3**/**T12** (+**2** display-config tests, **441** `pytest`); **Assignments** → **done**; defer **T4**, **T14**, **SD8** (FTS5 migration+UI); **Next action** → **`coder` `T4`** *or* **`planner` `SD8`**; guard **14→15**; **`NEXT_TASK_TOOL: none`** per user.

### 2026-04-14 — orchestrator (user **`/orchestrator continue`**: TO_DO P2 + **MPR2** VR **hotfix** note)

- **Parent ask:** Continue prior **TO_DO** backlog (**T7**, **T3**, **T12**, **T4**, **T14**; **SD8** FTS5 after **planner** spike). **Runtime:** **Save MPR as DICOM** failed with **pydicom** **ambiguous VR OB/OW** on **Pixel Data** `(7FE0,0010)` under **ExplicitVRLittleEndian** — **parent agent** fixing by writing **Pixel Data** as explicit **`OW`** **`DataElement`** in **`src/core/mpr_dicom_export.py`**, **test** assert, **`CHANGELOG`** **Fixed**.
- **Executed:** **Global orchestration guard:** **Orchestrator cycles** **13→14**. **Phase** / **Stream M** / **Assignments MPR2** / **Blockers** / **Next action** / **Session checkpoint** updated. **Handoff:** **MPR2** **hotfix** documented; **re-smoke** **File → Save MPR as DICOM…** after fix.
- **Decision:** **`NEXT_TASK_TOOL: coder`** on **`T7`** (navigator slice/frame count, **default on**) **unless** user wants **`planner`** **`SD8`** first. **`NEXT_TASK_TOOL_SECOND: none`** (no parallel **SD8** without second **worktree** / disjoint branch).

- **HANDOFF → parent:**
- Status: done
- Artifacts: `plans/orchestration-state.md`
- Plan deltas: none (MPR2 plan §1 unchanged; hotfix is conformance/VR detail)
- Risks: low — orthogonal to **T7** navigator work once **MPR2** hotfix merged
- Recommended next: **coder** (**T7**) | alt: **planner** (**SD8**) if user overrides phasing
- Stream: B (**T7**)
- Git: user-controlled; do not push
- Git proposal: none
- PR: none
- Cloud: none
- Merge recommendation: n/a

### 2026-04-14 — orchestrator (autonomous chain: **`secops`** MPR2 delta **done** → slice **complete**)

- **Parent ask:** Merge **`secops`** HANDOFF (artifact **`assessments/security-assessment-20260414-2000.md`**; scoped Semgrep **0**; pip-audit clean; recommended next **none**); set **Assignments** **MPR2** **`secops` done**; advance **P2** phasing (**T7** first); increment guards; emit **`NEXT_TASK_TOOL`**.
- **Executed:** **Phase** / **Stream M** / **Assignments** **MPR2** / **Blockers** / **Next action** / **Session checkpoint** updated. **Global orchestration guard:** **Orchestrator cycles** **12→13**; **Specialist completions** **9→10**.
- **Decision:** **`NEXT_TASK_TOOL: none`** until the user names the next slice (**`coder` T7** vs **`planner` SD8`** vs other); autonomous default avoids idle **`Task`** loops with no new goal.

- **HANDOFF → parent:**
- Status: done
- Artifacts: `plans/orchestration-state.md`
- Plan deltas: none
- Risks: none (informational de-ID scope already in **secops** assessment)
- Recommended next: **none** (user pulls **T7** / **SD8** / other)
- Stream: n/a
- Git: user-controlled; do not push
- Git proposal: none
- PR: none
- Cloud: none
- Merge recommendation: n/a

### 2026-04-14 — secops (MPR2 delta — Save MPR as DICOM, assignment re-run)

- **Scope:** Same delta set as **MPR2** slice (`mpr_dicom_export.py`, `mpr_dicom_save_dialog.py`, `mpr_controller.py` save path, `main_window*` / `app_signal_wiring` / `main.py` wiring).
- **Scans:** `PYTHONUTF8=1` **Semgrep** `--config=p/security-audit` + `--config=p/python` on **3** files → **0 findings**, exit **0**. **`semgrep scan --config auto`** still **fails** on this host (**cp1252** / Unicode in downloaded rules). **TruffleHog** / **Gitleaks** not in venv PATH. **`detect-secrets`** on the two primary modules → **empty `results`**. **`pip-audit -r requirements.txt`** → **no known vulnerabilities** (this pass).
- **Manual review:** Confirmed no `eval`/`exec`/`pickle.loads`, no `shell=True`, no permissive file modes; folder-name sanitization present; **info:** anonymizer is **0010-only**; **source series UID** remains in **`ImageComments`** / **`ReferencedSeriesSequence`** when anonymize is on; partial files on cancel.
- **Artifact:** `assessments/security-assessment-20260414-2000.md` (see also `security-assessment-20260414-1930.md` if present).

- **HANDOFF → orchestrator:**
- Status: done
- Artifacts: `assessments/security-assessment-20260414-2000.md`
- Plan deltas: none
- Risks: Privacy-expectation vs **DICOMAnonymizer** scope (documented); Windows **Semgrep `--config auto`** encoding friction for local devs
- Recommended next: **none** (optional **docwriter**/**coder** only if product tightens de-ID or UX copy)
- Stream: M
- Git: dirty; branch: WIP; worktree: none
- Git proposal: none
- PR: none
- Cloud: none
- Merge recommendation: n/a

### 2026-04-14 — secops (MPR2 delta: Save MPR as DICOM)

- **Scope:** `mpr_dicom_export.py`, `mpr_dicom_save_dialog.py`, MPR save wiring in `mpr_controller.py`, `main_window.py`, `main_window_menu_builder.py`, `app_signal_wiring.py`, `main.py`.
- **Scans:** Semgrep **`p/python`** + **`p/security-audit`** on scoped files — **clean** (exit 0). **`semgrep --config auto`** failed on this Windows env (**UnicodeEncodeError** / cp1252 while fetching rules). **TruffleHog** / **Gitleaks** not on PATH. **detect-secrets** on the two primary new modules — **no hits**. **pip-audit** (venv) — 3 upstream CVEs (**cryptography**, **pypdf**, **pytest**), not MPR2-specific.
- **Manual review:** No path traversal, `eval`/`exec`/`pickle`, or `shell=True` in scope. **Low/info:** `DICOMAnonymizer` is **patient 0010 only**; exporter still embeds **original source `SeriesInstanceUID`** in **`ImageComments`** / **`ReferencedSeriesSequence`** when anonymize is on; partial files possible on cancel.
- **Artifact:** `assessments/security-assessment-20260414-1930.md`

- **HANDOFF → orchestrator:**
- Status: done
- Artifacts: `assessments/security-assessment-20260414-1930.md`
- Plan deltas: none
- Risks: Privacy-expectation gap on “Anonymize” (documented in assessment); semgrep `auto` unusable locally without UTF-8-safe console or pinned local rules
- Recommended next: **none** (optional **coder** only if product wants stronger de-ID for MPR export or semgrep CI pinning)
- Stream: M
- Git: dirty; branch: WIP; worktree: none
- Git proposal: none
- PR: none
- Cloud: none
- Merge recommendation: n/a

### 2026-04-14 — orchestrator (autonomous chain: **MPR2** **`tester`** gate green → **`secops`** delta)

- **Parent ask:** User **continue**; **next is `secops`** after **MPR2** slice; facts: **`pytest tests/`** **439** passed (theme expectations aligned with **`main_window_theme.py`**); **`logs/test-ledger.md`** green row.
- **Executed:** **Guard:** **Orchestrator cycles** **11→12**; **Specialist completions** **8→9** (post-fix full-suite **`tester`**). **Phase** / **Assignments** **MPR2** + **MPR2-theme** / **Blockers** / **Next action** updated — **Blockers:** prior theme RGB mismatch **cleared**; **Next action** lead → **`secops`** on **MPR2** touch set (+ **`main_window_theme.py`** if in diff).
- **HANDOFF → parent:** **`NEXT_TASK_TOOL`** **`secops`**. **`NEXT_TASK_TOOL_SECOND`** **`none`**.

### 2026-04-14 — orchestrator (autonomous merge: **tester** done → **MPR2-theme** + sequence **secops**)

- **Parent ask:** **tester** completed full pytest (**436**/3 theme); merge HANDOFF; clarify **secops** vs **coder** parallel; emit **NEXT_TASK_TOOL** / **SECOND**.
- **Executed:** **Guard:** **Orchestrator cycles** **10→11**; **Specialist completions** **7→8**. **Assignments:** **MPR2** slice note → **tester** done, **secops** pending; added **`MPR2-theme`** (**coder**). **Phase** / **Next action** / **Blockers** updated. **Parallel `coder`+`secops`:** **`NEXT_TASK_TOOL_SECOND: none`** — checklist **ordering** (secops should reflect final tree) + single dirty branch.
- **HANDOFF → parent:** **`NEXT_TASK_TOOL`** **`coder`**. **`NEXT_TASK_TOOL_SECOND`** **`none`**.

### 2026-04-14 — tester (MPR2 slice gate: full `pytest tests/`)

- **Run:** `.\.venv\Scripts\Activate.ps1`; `python -m pytest tests/ -v --tb=short` — **439** collected, **436 passed**, **3 failed**, ~53 s (no edits to product/tests).
- **Failures (all theme):** `tests/test_main_window_theme.py::TestGetThemeViewerBackgroundColor` — dark `red()` 14≠27; light/unknown 38≠64.
- **Ledger:** `logs/test-ledger.md` (new row, newest first).
- **Suggested manual smoke (File → Save MPR as DICOM…):**
  1. Load a volume, build MPR so a **pane shows MPR** and the stack is non-empty; **focus** that MPR pane.
  2. Open **File → Save MPR as DICOM…** — dialog should appear **on top** and in focus initially.
  3. Pick an **output folder**, toggle **anonymize** on/off as desired, confirm **Save** — verify DICOM files land under the folder and open in the viewer.
  4. Repeat but **Cancel** at the folder dialog — no export, app remains stable.
  5. If export is long-running, **Cancel** mid-run where offered — confirm behavior matches spec (reviewer noted possible partial files).
  6. With **no MPR / wrong focus**, confirm action is **disabled** or shows a clear message (no crash).
  7. Re-import saved series — **slice count / orientation** look plausible vs source MPR.

- **HANDOFF → orchestrator:**
- Status: done
- Artifacts: `logs/test-ledger.md`
- Plan deltas: none
- Risks: Theme failures block “all green” slice gate; orthogonal to MPR2 export tests (436 passed including MPR export suite collection).
- Recommended next: **coder** (align `get_theme_viewer_background_color` / palette with `tests/test_main_window_theme.py` expectations, or restore prior RGB contract — triage vs `main_window_theme.py` edits); optional **debugger** if palette change intent is unclear. After theme green: **secops** per slice-end plan.
- Stream: M
- Git: dirty; branch: WIP; worktree: none
- Git proposal: none
- PR: none
- Cloud: none
- Merge recommendation: n/a

### 2026-04-14 — orchestrator (autonomous merge: **MPR2** typing follow-up **done** → **tester** gate)

- **Parent ask:** **coder** completed MPR2 follow-up (`tests/test_mpr_dicom_export.py` typing); basedpyright **0** errors on that file; pytest **4** passed; optional cancel cleanup skipped.
- **Executed:** **Global orchestration guard:** **Orchestrator cycles** **9→10**; **Specialist completions** **6→7**. **Assignments** **MPR2:** removed open **coder** typing follow-up; recorded verify lines for test file. **Next action** reordered: **lead with `tester`** (full pytest + **`logs/test-ledger.md`**); **`secops`** remains **after** tester (ordering dependency — **`NEXT_TASK_TOOL_SECOND: none`**).
- **HANDOFF → parent:** **`NEXT_TASK_TOOL`** **`tester`**. **`NEXT_TASK_TOOL_SECOND`** **`none`**.

### 2026-04-14 — coder (MPR2 follow-up: test typing cleanup)

- **HANDOFF → orchestrator:**
- Status: done
- Artifacts: `tests/test_mpr_dicom_export.py`
- Plan deltas: none (MPR2 assignment already done; follow-up typing fix only)
- Risks: none
- Recommended next: tester (continue high-risk slice gate sequence) | optional parallel: none
- Stream: M
- Git: dirty; branch: n/a; worktree: none
- Git proposal: none
- PR: none
- Cloud: none
- Merge recommendation: n/a
- Verify: `basedpyright --level error tests/test_mpr_dicom_export.py` (0 errors); `pytest tests/test_mpr_dicom_export.py -v` (4 passed)

### 2026-04-14 — orchestrator (autonomous merge: reviewer **MPR2** done → follow-up + gates)

- **Parent ask:** reviewer completed **MPR2** with verdict **approved** and merge recommendation **yes_with_followups**; update state/counters and choose next dispatch ordering between coder typing follow-up vs tester gate.
- **Executed:** Reviewer handoff already present (no duplicate append). **Global orchestration guard** incremented: **Orchestrator cycles** **8→9**, **Specialist completions** **5→6**. **Assignments MPR2** gate note clarified to **review done; tester/secops pending**.
- **Decision:** Run **`coder`** first for `basedpyright` cleanup in `tests/test_mpr_dicom_export.py` so the subsequent **`tester`** full-suite ledger reflects post-follow-up state; keep **`secops`** after tester. Theme failures remain orthogonal unless tester evidence suggests coupling.
- **HANDOFF → parent:** **NEXT_TASK_TOOL** **`coder`**. **NEXT_TASK_TOOL_SECOND** **`none`** (single-stream gate sequence; ordering dependency).

### 2026-04-14 — reviewer (**MPR2** plan §1 gate)

- **HANDOFF → orchestrator:**
- Status: done
- Artifacts: `src/core/mpr_dicom_export.py`, `src/gui/dialogs/mpr_dicom_save_dialog.py`, `src/core/mpr_controller.py` (`prompt_save_mpr_as_dicom`), `src/gui/main_window.py`, `src/gui/main_window_menu_builder.py`, `src/core/app_signal_wiring.py`, `src/main.py`, `tests/test_mpr_dicom_export.py`, `CHANGELOG.md`, `dev-docs/plans/MPR_DICOM_SAVE_CINE_VIDEO_EXPORT_ANGLE_MEASUREMENT_PLAN.md` (MPR checklist)
- Plan deltas: **none** (§1 MPR checklist already `[x]`; top-of-plan **Prerequisites** legal/inventory rows remain `[ ]` — product/process, not blocking code merge)
- Risks: **Cancel mid-export** leaves partial files under output tree; **SC** path may still draw validator warnings vs full Secondary Capture IOD (acceptable MVP per plan). **`tests/test_mpr_dicom_export.py`:** `basedpyright --level error` reports **7** issues (`pydicom.uid` stubs, `SimpleNamespace` vs `MprVolume`); **`src/**`** touched modules **0** errors.
- Recommended next: **tester** (full pytest + ledger; theme failures orthogonal); optional **coder** follow-up: test typing or `cast`/fixtures; optional **ux**: `WindowStaysOnTopHint` vs “do not stay on top after defocus” rule
- Stream: M
- Git: dirty (expected); branch: n/a; worktree: none
- Git proposal: none
- PR: none
- Cloud: none
- Merge recommendation: **yes_with_followups**

### 2026-04-14 — orchestrator (autonomous merge: **MPR2** landed → verification chain)

- **Parent ask:** **coder** finished **MPR2**; merge **Assignments** / **Stream M** / guard; set **Next action** / **Phase**; **NEXT_TASK_TOOL** for high-risk slice.
- **Executed:** **Assignments** **MPR2** → **done** (with slice-gate note); **Stream M** → **done**. **Orchestrator cycles** **7→8**; **Specialist completions** **4→5**. **Blockers** unchanged; **FYI** theme-test failures recorded. **Phase** text → MPR2 landed, verification in flight.
- **Disk verify (spot):** `src/core/mpr_dicom_export.py`, `src/gui/dialogs/mpr_dicom_save_dialog.py`, `tests/test_mpr_dicom_export.py` present; `save_mpr_dicom_requested` / `_on_save_mpr_as_dicom` / menu action wired in repo.
- **Decision:** **`debugger`** deferred — **theme** failures orthogonal by default; **`reviewer`** first to confirm MPR2 vs plan and whether theme regressions couple; then **`tester`** batch + ledger; then **`secops`** delta. **`NEXT_TASK_TOOL_SECOND`:** **`none`** (sequential gates, single branch).
- **HANDOFF → parent:** **NEXT_TASK_TOOL** **`reviewer`**. **NEXT_TASK_TOOL_SECOND** **`none`**.

### 2026-04-14 — coder (**MPR2** Save MPR as DICOM, plan §1)

- **HANDOFF → orchestrator:**
- Status: done
- Artifacts: `src/core/mpr_dicom_export.py`; `src/gui/dialogs/mpr_dicom_save_dialog.py`; `src/core/mpr_controller.py` (`prompt_save_mpr_as_dicom`); `src/gui/main_window.py` (signal `save_mpr_dicom_requested`); `src/gui/main_window_menu_builder.py` (File menu); `src/core/app_signal_wiring.py`; `src/main.py` (`_on_save_mpr_as_dicom`); `tests/test_mpr_dicom_export.py`; `CHANGELOG.md` [Unreleased]; `dev-docs/plans/MPR_DICOM_SAVE_CINE_VIDEO_EXPORT_ANGLE_MEASUREMENT_PLAN.md` (MPR DICOM checklist → done)
- Plan deltas: **MPR2** §1 implemented; plan checklist rows marked **[x]**; **Assignments** **MPR2** → orchestrator should set **done**; **Stream M** → **done**
- Risks: Full **pytest** run: **436 passed**, **3 failed** — all **`tests/test_main_window_theme.py::TestGetThemeViewerBackgroundColor`** (expected colors vs current `main_window_theme.py`); **unrelated to MPR2** — no test edits per user policy; flag for **tester** / owner
- Recommended next: **reviewer** then **tester** (slice-end **high** risk); optional **secops** on touched paths
- Stream: M
- Git: dirty; branch: n/a; worktree: none
- Git proposal: none
- PR: none
- Cloud: none
- Merge recommendation: n/a
- **Verify:** `basedpyright --level error` on `mpr_dicom_export.py`, `mpr_controller.py`, `mpr_dicom_save_dialog.py` → **0 errors**; `pytest tests/test_mpr_dicom_export.py` → **4 passed**; full `pytest tests/` → **436 passed, 3 failed** (theme tests above)

### 2026-04-14 — orchestrator (TO_DO slice: MPR DICOM save + P2 UX + FTS5 queue)

- **User ask:** Prioritize **P1** TO_DO **L85** (save MPRs as DICOM) vs **P2** L52/L53/L60–61/L71/L78; phased slices; autonomous chain; no push; venv per AGENTS.
- **Executed:** Goal + table **Backlog slice — 2026-04-14**; **Assignments** **MPR2**, **T12**, **T14**; **SD8** **deferred → queued**; **Streams M** (MPR export), **L** updated; **Next action** → **`coder`** **MPR2** first; **Orchestrator cycles** **6→7**; iteration guard rows **MPR2**, **T12**, **T14**.
- **Rationale:** **MPR2** is **P1** and plan §1 is implementation-ready (resolve design table in-code per recommendations). P2 navigator (**T7**, **T3**) batchable; **T12**+**T4** share display state risk — sequence. **T14** separate chrome stream. **SD8** needs schema spike — **after MPR2** default. **`NEXT_TASK_TOOL_SECOND`:** **`none`** (overlapping touch surfaces / single-branch default).
- **HANDOFF → parent:** **NEXT_TASK_TOOL** **`coder`**. **NEXT_TASK_TOOL_SECOND** **`none`**.

### 2026-04-14 — primary agent (basedpyright **errors** = 0 on `src/`)

- **User ask:** Run **basedpyright** on `src/`, fix **errors** (not warnings), venv `.\.venv\Scripts\Activate.ps1`, update **CHANGELOG** if warranted, **do not push**; update this Handoff if used.
- **Verify:** `basedpyright --level error src/` → **0 errors**; `basedpyright --outputjson src/` → **summary.errorCount 0** (warnings remain ~18k). Targeted pytest: **`tests/test_undo_redo_tag_commands.py`** + **`tests/test_mpr_overlay_and_rescale.py`** — **11 passed**.
- **Artifacts:** New **`src/utils/undo_redo_command.py`** (`Command` base — breaks `undo_redo` ↔ `undo_redo_tag_commands` cycle); **`src/core/mpr_combine_slice_count.py`** (breaks `mpr_controller` ↔ `mpr_dialog` cycle); edits across **`main_window.py`**, **`image_viewer_input.py`** / **`image_viewer_view.py`** (pyright pragmas + `QMouseEvent`), **`slice_location_line_helper.py`**, **`sqlcipher_store.py`**, **`study_index_search_dialog.py`**, **`cine_app_facade.py`**, **`series_navigator.py`** / **`series_navigator_view.py`**, **`sub_window_container.py`**, **`main.py`**, **`mouse_mode_handler.py`**, **`roi_coordinator.py`**, **`mpr_thumbnail_widget.py`**, **`undo_redo.py`**, **`mpr_controller.py`**, **`mpr_dialog.py`**, **`CHANGELOG.md`** [Unreleased].
- **HANDOFF → parent:** **NEXT_TASK_TOOL** **`none`**. **NEXT_TASK_TOOL_SECOND** **`none`**. Optional: full **`pytest`** + **`basedpyright src/ --warnings`** if CI treats warnings as failure.

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

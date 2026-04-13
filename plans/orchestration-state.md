# Orchestration state

## Goal

Backlog from `dev-docs/TO_DO.md`: ship P1 items (MPR navigator assign/clear follow-up, privacy-aware navigator tooltips, slice-position line thickness, **Create MPR view…** menu) and queue P2 items (interactive window map, ROI resize handles, PNG/JPG export anonymization + embedded WL default, navigator slice/frame count). Success: prioritized execution, minimal merge conflict, full pytest from activated venv.

## Phase

`planning` — backlog structured; no implementation started.

## Execution mode

`full` (multi-surface UX + export + ROI).

## Risk tier

`medium` (privacy/tooltips, Qt drag-drop, export pipeline, ROI scene interaction).

## Streams

| Stream | Scope | Status |
|--------|--------|--------|
| A | MPR: assign/clear + menu entry | pending |
| B | Navigator: tooltips + optional slice/frame count | pending |
| C | Window map widget | pending |
| D | ROI edit handles | pending |
| E | Export PNG/JPG options | pending |
| F | Slice position indicator thickness | pending |

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

## Git / worktree

- Branch: none yet (user controls commits; **do not push** without user request).
- Proposal: `feature/mpr-navigator-followup` (T1+T8), `feature/navigator-tooltips` (T2), `feature/window-map-interactive` (T3), `feature/roi-resize-handles` (T4), `feature/export-png-jpg-privacy-wl` (T5), `feature/slice-indicator-thickness` (T6), `feature/navigator-slice-count` (T7) — merge related small items if desired.

## Cloud

`none`

## Blockers

`none` (menu placement T8 and slice-indicator scope T6 are open questions, not hard blocks).

## Next action

1. User: confirm **Tools vs View** for **Create MPR view…** and which **slice position** UI T6 refers to.  
2. Invoke **`/coder`** on **T1** (MPR assign/clear) after optional **`/researcher`** spike on drop targets and clear semantics, **or** invoke **`/planner`** only if assign/clear behavior needs a written decision record.  
3. **`/tester`**: `python -m pytest tests/ -v` (venv per `AGENTS.md`) after each merged stream; add **`/reviewer`** before considering done.

## Session checkpoint

- Context: TO_DO UX batch parsed; canonical plans live under **`dev-docs/plans/`** (TO_DO links are relative to `dev-docs/`).
- Locked decisions: none.
- Canonical files: `dev-docs/TO_DO.md`, plans cited in Assignments table.
- Last verified ref: n/a.
- Last updated: 2026-04-12 (orchestrator).

## Iteration guard

| Task ID | Cycles | Soft cap | Notes |
|---------|--------|----------|-------|
| T1–T8 | 0 | 5 each | Escalate if DnD or ROI edit loops without progress |

## Handoff log (newest first)

_Specialists append dated subsections here._

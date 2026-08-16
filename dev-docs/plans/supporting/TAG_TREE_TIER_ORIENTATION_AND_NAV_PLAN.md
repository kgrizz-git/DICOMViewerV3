# Plan: Tag Tree Tier Orientation & Navigation Backbone (Phase C)

**Created:** 2026-08-16  
**Last updated:** 2026-08-16  
**Status:** proposed  
**Priority:** P2  
**Phase:** C of the tag-tree visual-hierarchy workstream  
**Depends on:** [TAG_TREE_GROUP_HEADER_AND_STRIPING_PLAN.md](TAG_TREE_GROUP_HEADER_AND_STRIPING_PLAN.md) (Phase B)

In-scope Part 2 backbone: shared tier language on the **export dialog + metadata
panel only**, navigation affordances, and light orientation aids. Keeps Carbon
“clarity over decoration.”

## Context and links

- **Hub:** [TAG_TREE_VISUAL_HIERARCHY_PLAN.md](TAG_TREE_VISUAL_HIERARCHY_PLAN.md)
- **Investigation:** [tag-tree-visual-hierarchy-investigation-2026-08-16.md](../../ux-assessments/tag-tree-visual-hierarchy-investigation-2026-08-16.md)
  (P1, P5 phase 1, P7–P10, C2, C5–C7, D4, D9/D10/D18, E2/E4/E6; Part 7 verdicts)
- **Previous:** Phase B  
- **Follow-ups:** [TAG_TREE_VISUAL_FOLLOWUPS_PLAN.md](TAG_TREE_VISUAL_FOLLOWUPS_PLAN.md)  
- **Pane/toolbar (split-out):** [PANE_AND_TOOLBAR_STATE_VISUAL_PLAN.md](PANE_AND_TOOLBAR_STATE_VISUAL_PLAN.md)  
- **Design:** [DESIGN.md](../../../DESIGN.md) — document tier/state language before merge

## Goal and success criteria

- One tier helper / shared chrome for export + metadata trees (P5 phase 1).
- Depth-aware typography (restrained; no italics on long editable tag strings
  if they hurt readability — prefer weight/size).
- Mono font for Tag (and VR where present) via **platform monospace fallback**,
  not a new bundled Plex Mono (investigation A7 / Part 7).
- Filter match highlight with **cached** draw (no live `QTextDocument` in
  `paint()` — E2).
- Dimmed empty values; filter no-match + Clear; collapsed-group selection chip;
  Expand/Collapse All + shortcuts + context menu as **one** unit.
- `DESIGN.md` updated with the tier language; motion restraint recorded (C7).

## Checklist

- [ ] **(C1)** Shared tier helper (font weight/size ladder; optional **left
      color bar only** — **no new kind-icon SVG set** unless usability later
      requires it; Part 7 discourage on D17 icons). Export fill-scope rules from
      Phase B still apply.
- [ ] **(C2)** P5 phase 1: shared QSS classes / tokens for export + metadata
      trees only (`.mpdv-tree` / group-header as needed). SR / nuclear / ROI =
      follow-ups plan.
- [ ] **(C3)** Mono Tag/VR columns via `"monospace"` / platform fallback stack;
      verify cross-OS metrics before considering any font bundle.
- [ ] **(C4)** Filter substring highlight in shared delegate; cache
      `QStaticText` / precomputed rects (E2).
- [ ] **(C5)** Dim empty/null values (`--fg-disabled`); filter empty state +
      one-click Clear (P9, C2).
- [ ] **(C6)** Collapsed-group chip in header text, e.g. `Group 0008 (12/40)`
      (D10). Prefer over hover-only tooltip (C4 redundant once chip ships).
- [ ] **(C7)** Expand/Collapse All buttons + keyboard shortcuts + context menu
      as one feature (D4 / P10 / C5); audit `DESIGN.md §6` once for conflicts.
- [ ] **(C8)** Token-driven hover tint verify via objectName (E6).
- [ ] **(C9)** Document tier/state language in `DESIGN.md` (D9/D18); add
      motion-restraint note for dense trees (C7/D8).
- [ ] **(C10)** Color-blind screenshot pass (C6) for any new hues; harness smoke.

## Verification

- `python -m pytest tests/gui -q`
- `python scripts/agent_smoke_harness.py`
- `python scripts/check_user_docs_links.py` if `DESIGN.md` / README links change

## Files likely touched

- `src/gui/dialogs/tag_export_dialog.py`, `src/gui/metadata_panel.py`,
  shared delegate/helpers
- `resources/themes/*.qss`, `src/gui/main_window_theme.py` if tokens added
- `DESIGN.md`
- `tests/gui/…`

## Out of scope

- P2 selected/edited state colors → follow-ups  
- P4/C3 pane & toolbar active state → [PANE_AND_TOOLBAR_STATE_VISUAL_PLAN.md](PANE_AND_TOOLBAR_STATE_VISUAL_PLAN.md)  
- P5 phase 2 (SR/nuclear/ROI), PHI marker, series_tree, Select-group menu →
  follow-ups  
- Fuzzy filter (discouraged as default), search history, sticky filter bar

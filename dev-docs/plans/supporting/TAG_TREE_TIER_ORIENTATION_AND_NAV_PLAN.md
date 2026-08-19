# Plan: Tag Tree Tier Orientation & Navigation Backbone (Phase C)

**Created:** 2026-08-16  
**Last updated:** 2026-08-17  
**Status:** in progress (`feature/tag-tree-tier-orientation-nav`)  
**Priority:** P2  
**Phase:** C of the tag-tree visual-hierarchy workstream  
**Depends on:** [TAG_TREE_GROUP_HEADER_AND_STRIPING_PLAN.md](../completed/TAG_TREE_GROUP_HEADER_AND_STRIPING_PLAN.md) (Phase B, implemented)
**Primary surface:** **left-pane metadata panel**  
**Export visuals:** Phase B appearance gate (`B7` / `D-export-visual`) chose
**(c) none** — retain the checkbox indicator glyphs and provide **navigation
affordances only**, with no header/stripe/tier chrome on export.

In-scope Part 2 backbone for the **metadata panel** (values + IDs + names):
shared tier language, navigation/orientation aids, `DESIGN.md` update. Keeps
Carbon “clarity over decoration.”

## Context and links

- **Hub:** [TAG_TREE_VISUAL_HIERARCHY_PLAN.md](TAG_TREE_VISUAL_HIERARCHY_PLAN.md)
- **Investigation:** [tag-tree-visual-hierarchy-investigation-2026-08-16.md](../../ux-assessments/tag-tree-visual-hierarchy-investigation-2026-08-16.md)
  (Part 7–9)
- **Previous:** Phase B (metadata Goals 1–2; export Goal 3 + appearance gate)  
- **Follow-ups:** [TAG_TREE_VISUAL_FOLLOWUPS_PLAN.md](TAG_TREE_VISUAL_FOLLOWUPS_PLAN.md) (`D-export-visual` recorded **(c) none**)  
- **Pane/toolbar (split-out):** [PANE_AND_TOOLBAR_STATE_VISUAL_PLAN.md](PANE_AND_TOOLBAR_STATE_VISUAL_PLAN.md)  
- **Design:** [DESIGN.md](../../../DESIGN.md)

## Goal and success criteria

- Tier helper / chrome on the **metadata panel** (P5 phase 1 for that tree).
- Depth-aware typography (restrained; prefer weight/size over italics on long
  editable strings).
- Mono font for Tag/VR via **platform monospace fallback** (metadata VR column
  is the natural home).
- Filter match highlight with **cached** draw (no live `QTextDocument` in
  `paint()`), dimmed empties, filter no-match + Clear — on metadata; on export
  filter UI only if useful without implying full visual parity.
- Export Expand/Collapse All / shortcuts / context menu remain useful
  **navigation** parity (independent of rich styling).
- `DESIGN.md` documents the metadata tier language; export stays checkbox- and
  navigation-focused (appearance gate **(c) none**).

## Checklist

- [x] **(C1)** Tier helper on **metadata panel** (font weight/size ladder;
      optional left color bar only — no new kind-icon set unless needed).
- [x] **(C2)** Shared tokens/QSS for the metadata tree (target
      `QTreeWidget#metadata_tag_tree` / group-header as needed). Do **not**
      force the same classes onto export until `D-export-visual` says so.
- [x] **(C3)** Mono Tag/VR columns via platform fallback on metadata.
- [x] **(C4)** Filter substring highlight (cached draw) on metadata filter.
- [x] **(C5)** Dim empty/null values; filter empty state + Clear on metadata
      (and export filter box if cheap / already shared).
- [x] **(C6)** Export navigation only (unless gate promoted visuals):
      Expand/Collapse All + shortcuts + context menu (D4 / P10 / C5); audit
      `DESIGN.md §6`. Collapsed-group selection chip only if still wanted for
      selection UX (not as “visual hierarchy parity”).
- [x] **(C7) Skipped/cancelled:** `D-export-visual` recorded **(c) none** on
      2026-08-17; do not implement export header/stripe/tier chrome. C6 remains
      in scope for export Expand/Collapse All, shortcuts, and context menu.
- [x] **(C8)** Token-driven hover tint verify on metadata objectName (E6).
- [x] **(C9)** Document tier/state language in `DESIGN.md` for the **metadata
      panel**; record export as checkbox-focused unless gate decided otherwise.
- [x] **(C10)** Color-blind / harness smoke with **left-pane metadata** as the
      primary visual check.

## Verification

- `python -m pytest tests/gui -q`
- `python scripts/agent_smoke_harness.py` (metadata panel first)
- `python scripts/check_user_docs_links.py` if `DESIGN.md` / README links change

## Files likely touched

- **`src/gui/metadata_panel.py`** (primary)
- `src/gui/dialogs/tag_export_dialog.py` (nav / Goal 3 already done; visuals
  only if gated)
- Shared helpers / themes / `DESIGN.md` / `tests/gui/…`

## Out of scope

- Assuming export must match metadata chrome  
- P2 state colors → follow-ups  
- P4/C3 pane & toolbar → [PANE_AND_TOOLBAR_STATE_VISUAL_PLAN.md](PANE_AND_TOOLBAR_STATE_VISUAL_PLAN.md)  
- Fuzzy filter by default, search history, sticky filter bar

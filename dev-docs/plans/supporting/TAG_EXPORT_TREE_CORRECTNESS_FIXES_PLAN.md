# Plan: Tag Export Tree — Correctness Fixes (Phase A)

**Created:** 2026-08-16  
**Last updated:** 2026-08-16  
**Status:** proposed  
**Priority:** P1  
**Phase:** A of the tag-tree visual-hierarchy workstream  
**Branch (planning):** `feature/tag-tree-visual-hierarchy-plan`

Bug fixes and prerequisites with **no intentional visual redesign**. Ships
immediately useful correctness and unblocks later phases.

## Context and links

- **Hub:** [TAG_TREE_VISUAL_HIERARCHY_PLAN.md](TAG_TREE_VISUAL_HIERARCHY_PLAN.md)
- **Investigation / review history:** [tag-tree-visual-hierarchy-investigation-2026-08-16.md](../../ux-assessments/tag-tree-visual-hierarchy-investigation-2026-08-16.md) (esp. Part 7; A5, D1/D11, D2, D5/E1)
- **Next:** [TAG_TREE_GROUP_HEADER_AND_STRIPING_PLAN.md](TAG_TREE_GROUP_HEADER_AND_STRIPING_PLAN.md) (Phase B)
- **Backlog:** [TO_DO.md](../../TO_DO.md) UX / Workflow
- **Design:** [DESIGN.md](../../../DESIGN.md) §2 (token discipline for D2)

## Goal and success criteria

- `tags_tree` is QSS-targetable via a stable `objectName`.
- Top **Select All** (checkbox and button) leaves group headers in the correct
  tri-state (`Checked` / `PartiallyChecked` / `Unchecked`) for visible children.
- Filtering does not leave stripe-related (or future parity) handlers racing
  mid-walk.
- Edited-row purple in the metadata panel resolves through a **token**, not a
  hardcoded `QColor(80, 50, 120)`.

## Checklist

- [ ] **(A1)** Set `self.tags_tree.setObjectName("tag_export_tags_tree")` and add
      a scoped `QTreeWidget#tag_export_tags_tree` block in both theme QSS files
      (investigation D1/D11). No visual change required yet — structure only.
- [ ] **(A2)** Add a targeted pass that recomputes **only group-header**
      tri-state from visible children; call it from `_toggle_all_tags`,
      `_on_select_all_tag_checkbox`, the Select-All **button**, and after
      `_filter_tags` (investigation A5). Do **not** clobber independently
      checked Sequence/Item parents.
- [ ] **(A3)** Filter-walk guard: boolean `_is_filtering` inside
      `itemExpanded` / `itemCollapsed` slots (return early); recompute any
      structural state **once** at end of `_filter_tags` — do **not** blanket
      `blockSignals` on the whole tree (investigation D5/E1).
- [ ] **(A4)** Fix `metadata_panel.py` hardcoded edited-row
      `QColor(80, 50, 120)` via a tokenized helper (mirror
      `tag_viewer_dialog` / `_edited_tag_row_colors()` pattern)
      (investigation D2). Regression test: edited-row color is not a raw RGB
      literal.
- [ ] **(A5)** Tests: group headers reach `Checked` after top Select All and
      after the Select-All button; remain coherent after filter; objectName
      present on `tags_tree`.

## Verification

- `python -m pytest tests/gui -q` (focused tag-export / metadata panel tests)
- Manual: Select All → every group header checked; deselect one leaf → that
  group `PartiallyChecked`; filter then Select All still updates headers.

## Files likely touched

- `src/gui/dialogs/tag_export_dialog.py` (+ selection helper modules if used)
- `src/gui/metadata_panel.py`
- `resources/themes/*.qss`
- `tests/gui/test_tag_export_dialog*.py` (and/or metadata panel tests)

## Out of scope

Header styling, striping, custom partial glyphs, Expand/Collapse All, PHI
markers, pane/toolbar chrome — see later phases.

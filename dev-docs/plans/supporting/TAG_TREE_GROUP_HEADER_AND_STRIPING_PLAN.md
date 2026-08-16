# Plan: Tag Tree Group Headers, Striping & Checkbox Indicators (Phase B)

**Created:** 2026-08-16  
**Last updated:** 2026-08-16  
**Status:** proposed  
**Priority:** P2  
**Phase:** B of the tag-tree visual-hierarchy workstream  
**Depends on:** [TAG_EXPORT_TREE_CORRECTNESS_FIXES_PLAN.md](TAG_EXPORT_TREE_CORRECTNESS_FIXES_PLAN.md) (Phase A)

Implements the original user ask: distinct group headers, per-group alternating
rows, and clearer group checkbox states — plus the de-risking spike and perf
guard called out in the investigation Part 7.

## Context and links

- **Hub:** [TAG_TREE_VISUAL_HIERARCHY_PLAN.md](TAG_TREE_VISUAL_HIERARCHY_PLAN.md)
- **Investigation:** [tag-tree-visual-hierarchy-investigation-2026-08-16.md](../../ux-assessments/tag-tree-visual-hierarchy-investigation-2026-08-16.md)
  (Goals 1–3; corrections A1–A7; Part 7 spike + stripe fallback)
- **Previous:** Phase A correctness fixes  
- **Next:** [TAG_TREE_TIER_ORIENTATION_AND_NAV_PLAN.md](TAG_TREE_TIER_ORIENTATION_AND_NAV_PLAN.md) (Phase C)
- **Design:** [DESIGN.md](../../../DESIGN.md); [UX remediation plan](UX_ASSESSMENT_REMEDIATION_AND_DESIGN_SYSTEM_PLAN.md)

## Goal and success criteria

1. Group headers: distinct tokenized shade (**export dialog only** — metadata
   panel stays Base + rules), slightly taller, bold font via relative size bump
   (`setPointSizeF(base * 1.1)`), heavier **top** rule via extended shared
   `GroupHeaderDelegate`.
2. Alternating row shades **reset per group**; parity via a role (O(n) assign /
   recompute on expand/collapse/filter); `paint()` stays O(1).
3. Full selection → checkmark on group header (already partly plumbing; verify).
   Partial → clearer indeterminate glyph after a **spike** decides QSS vs
   delegate fallback.
4. Automated perf regression on a synthetic large tree (investigation Part 7 #2).

## Prerequisites (spike — do before full implement)

- [ ] **(B0a)** Spike: `GroupHeaderDelegate` reuse on `tags_tree` with
      `GROUP_HEADER_KEY_ROLE` set, role-collision audit (`UserRole+1` leaf count,
      `+2` header, new stripe role), full-width top rule (no
      `setFirstColumnSpanned`). Scratch under `tmp/` OK.
- [ ] **(B0b)** Spike: `QTreeWidget#tag_export_tags_tree::indicator:indeterminate`
      on pinned `PySide6>=6.11.1`. If it fails, document fallback:
      `PE_IndicatorItemViewItemCheck` over native `paint()`.

## Checklist

- [ ] **(B1)** Extend shared `GroupHeaderDelegate`
      (`src/gui/metadata_table_model.py`); export headers set
      `GROUP_HEADER_KEY_ROLE`; heavier top rule via token (e.g. `--border-strong`)
      + contrast check (investigation D6/D7). Metadata panel: **no new fills**
      (A4).
- [ ] **(B2)** `_style_group_header_item(item)`: bold + relative font bump,
      export-only header fill token, taller `sizeHint`.
- [ ] **(B3)** Stripe-parity role at build; recompute on expand/collapse/filter
      (Phase A filter guard already in place). Group headers do not stripe.
      **Fallback if fragile:** drop intra-group striping; keep header rule +
      hover + selection (investigation Part 7 #1).
- [ ] **(B4)** Partial indicator: scoped QSS glyph **or** delegate fallback from
      B0b. New SVG assets need approved-media review. Prefer objectName scope
      (no app-wide blast radius).
- [ ] **(B5)** Disable tree expand animation for dense UI (D8); theme/accent
      flip re-applies header/stripe colors (B2 from investigation).
- [ ] **(B6)** Perf test: synthetic large tree (e.g. 50×100 + deep sequences)
      build / expand-all / filter under a generous wall-clock bound (e.g. 2s).
- [ ] **(B7)** Widget tests: header font/size/bg ≠ leaf; stripe resets at group
      after expand/collapse **and** filter; HiDPI smoke of heavier top rule;
      color-blind screenshot pass if new hues land here.

## Verification

- `python -m pytest tests/gui -q`
- `python scripts/agent_smoke_harness.py` (tag export / tree UI steps)
- Visual check: header differentiation, stripe reset, checkbox states

## Files likely touched

- `src/gui/metadata_table_model.py`, `src/gui/dialogs/tag_export_dialog.py`
- `src/gui/metadata_panel.py` (shared delegate only; no fill regression)
- `resources/themes/*.qss`
- `tests/gui/…`

## Out of scope

Tier font ladder, filter-match highlight, Expand/Collapse All, mono columns,
PHI markers, pane focus frames — Phase C / follow-ups / pane-toolbar plan.

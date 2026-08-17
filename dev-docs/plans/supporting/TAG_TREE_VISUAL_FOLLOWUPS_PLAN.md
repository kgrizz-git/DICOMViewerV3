# Plan: Tag Tree Visual Follow-ups (Phase D)

**Created:** 2026-08-16  
**Last updated:** 2026-08-16  
**Status:** proposed / deferred  
**Priority:** P3 (unless a subsection is promoted)  
**Phase:** D of the tag-tree visual-hierarchy workstream  
**Depends on:** [TAG_TREE_TIER_ORIENTATION_AND_NAV_PLAN.md](TAG_TREE_TIER_ORIENTATION_AND_NAV_PLAN.md) (Phase C)

Lower-priority and split-scope items kept out of Phases A–C so those PRs stay
reviewable. Implement as separate small PRs when needed; do not treat this file
as one mega-diff.

## Context and links

- **Hub:** [TAG_TREE_VISUAL_HIERARCHY_PLAN.md](TAG_TREE_VISUAL_HIERARCHY_PLAN.md)
- **Investigation:** [tag-tree-visual-hierarchy-investigation-2026-08-16.md](../../ux-assessments/tag-tree-visual-hierarchy-investigation-2026-08-16.md)
  (P2, P3, P5 phase 2, P6, C1, C8–C11, D3, D12–D16, D20–D24, E5; Part 7 deferrals)
- **Pane/toolbar (separate plan):** [PANE_AND_TOOLBAR_STATE_VISUAL_PLAN.md](PANE_AND_TOOLBAR_STATE_VISUAL_PLAN.md)
- **Privacy guardrails (for C1):** [PHI_PII_REPOSITORY_GUARDRAILS.md](../../PHI_PII_REPOSITORY_GUARDRAILS.md)

## Checklist (promote subsections to their own PR when starting)

### After Phase C — still tag-tree / metadata

- [ ] **(D-export-visual)** **Open question — export tree richer formatting.**
      The export `tags_tree` is mostly ID + name for selection; it may not need
      metadata-panel header/stripe/tier chrome. **Default: defer / leave alone**
      beyond Goal 3 checkboxes. **Gate (Phase B item B7):** after metadata
      Goals 1–2 ship, side-by-side appearance check → choose
      (a) full parity, (b) light-touch subset, or (c) none. Record the decision
      here before any export visual PR. Do not lock styling in without this
      check.
- [ ] **(D-P2)** State color for selected / edited rows (tokenized); sequence
      **after** Phase C tier chrome so regressions are bisectable. Include any
      leftover edited-row polish beyond Phase A’s D2 fix.
- [ ] **(D-series)** Explicit decision: style `series_tree` with a
      **selection-aware** header-delegate variant, **or** mark permanently
      out-of-scope here (investigation D3). Do not copy tag-tree headers blindly.
- [ ] **(D-select)** “Select group” context action (check all visible leaves under
      a group); must re-run Phase A group-header tri-state refresh (D12).
- [ ] **(D-filter-badge)** Filter focus shortcut + match-count badge (D13);
      audit `DESIGN.md §6`.
- [ ] **(D-indent)** Indentation parity: **verify visually** at metadata’s 7px
      before forcing — export checkboxes may need more room (Part 7).
- [ ] **(D-chips)** Filter chips **only** for filters that are **not** already
      top checkboxes (e.g. `[Selected]`, `[Empties]`). Audit overlap with Include
      private / Include sequences first (E5). **No fuzzy matching by default.**
- [ ] **(D-p5-2)** P5 phase 2: apply shared tree/table chrome to SR browser,
      nuclear results, ROI stats — informed by Phase C’s real shared classes.

### Privacy-gated (may become its own plan before coding)

- [ ] **(D-phi)** Unified private/PHI tag marker across panel / viewer / export
      (C1). Requires privacy/UI review lane; do not land as a drive-by in a
      visual-hierarchy PR.

### Explicitly deferred / discouraged (do not schedule without new evidence)

- Sticky filter row (D14), search-history dropdown, fuzzy filter as default,
  sticky/pinned headers, sequence block tint, density toggle, frozen Tag column,
  selection-count color ladder on chips, distinct partial glyph for group vs SQ,
  VR column in export dialog, persist expand/collapse in export dialog,
  “recently exported” auto-pin, skeleton/shimmer loading, floating sticky-header
  `QLabel`.

## Verification (when a subsection ships)

- Focused `tests/gui` for that subsection  
- Manual smoke for the touched dialog(s)  
- Privacy gate / approved-media if new glyphs

## Out of scope here

Phases A–C work; pane/toolbar active-state chrome (own plan).

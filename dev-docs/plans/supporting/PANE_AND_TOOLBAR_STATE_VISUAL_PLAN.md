# Plan: Pane Focus & Toolbar Active-State Visual Cues

**Created:** 2026-08-16  
**Last updated:** 2026-08-16  
**Status:** proposed  
**Priority:** P2  
**Split from:** tag-tree visual-hierarchy investigation (P4 / C3) — wrong scope
for the tag-tree branch; lives in main window / image viewer / toolbar code.

## Context and links

- **Investigation (origin):** [tag-tree-visual-hierarchy-investigation-2026-08-16.md](../../ux-assessments/tag-tree-visual-hierarchy-investigation-2026-08-16.md)
  Part 2 P4, C3; Part 7 “split into separate plan”
- **Hub (tag-tree workstream):** [TAG_TREE_VISUAL_HIERARCHY_PLAN.md](TAG_TREE_VISUAL_HIERARCHY_PLAN.md)
- **Design system:** [DESIGN.md](../../../DESIGN.md); [UX remediation](UX_ASSESSMENT_REMEDIATION_AND_DESIGN_SYSTEM_PLAN.md)
- **Backlog:** [TO_DO.md](../../TO_DO.md) UX / Workflow

## Problem

Two of the largest whole-app orientation gaps are **not** in the tag tree:

1. Toolbar toggles (privacy, cine, sync, …) often signal state only via icon swap —
   easy to miss.
2. Focused vs non-focused image panes (1×2 / 2×1 / 2×2 / MPR) are not obvious.

## Goal and success criteria

- Active toolbar toggles get a **restrained** persistent cue (accent outline or
  light fill + optional state dot) — not “every button lit up.”
- Focused pane gets a clear accent frame; non-focused panes stay muted.
- Token-driven; contrast-checked light/dark; **no animation** in dense viewing
  chrome (align with investigation C7).
- Does not regress multi-window, expand/revert, or overlay draw stack.

## Checklist

- [ ] **(PT1)** Inventory current toggle actions and how they show state today
      (icon swap vs checked vs stylesheet).
- [ ] **(PT2)** Spec active-toggle treatment in `DESIGN.md` (one accent treatment;
      outline-first preference per investigation Part 2).
- [ ] **(PT3)** Implement toolbar active-state styling via tokens / QSS /
      `main_window` toolbar builder — no per-dialog hacks.
- [ ] **(PT4)** Focused-pane accent frame (start with frame only; defer dimming
      non-focused overlays until frame alone is validated) — C3 “small first step.”
- [ ] **(PT5)** Tests or harness steps for 1×1 / 1×2 / 2×2 focus change; manual
      smoke for privacy/cine toggles.

## Verification

- Manual multi-pane focus + toolbar toggle smoke  
- Theme/accent flip does not leave stale frames  
- `python scripts/agent_smoke_harness.py` where applicable

## Files likely touched

- `src/gui/main_window.py` / toolbar builder modules  
- `src/gui/image_viewer*.py` (pane chrome)  
- `resources/themes/*.qss`, `DESIGN.md`  
- Possibly `src/gui/main_window_theme.py`

## Out of scope

Tag-export / metadata tree styling (Phases A–D of the tag-tree workstream).

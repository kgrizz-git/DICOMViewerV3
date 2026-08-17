# Tag Tree Visual Hierarchy — Plan Hub

**Created:** 2026-08-16  
**Last updated:** 2026-08-17  
**Status:** index (implementation lives in phased plans below)  
**Branch (planning):** `feature/tag-tree-visual-hierarchy-plan`

This file is the **entry point** for the tag-tree / visual-orientation workstream.
The former monolithic plan was moved to an investigation document so actionable
work can proceed in small, ordered plans.

## Primary surface & export stance

**Goals 1–2 (group heading chrome + per-group striping)** target the
**main-window left-pane metadata panel** (`metadata_panel` /
`metadata_tag_tree`). That tree shows tag numbers, names, **and values**, so
hierarchy styling carries more load.

**Tag export dialog:** ship **Goal 3** (group checkbox tri-state / partial
indicator). **Phase A** owns group-header tri-state **correctness/behavior**.
**Phase B** owns checkbox **visual presentation** (indicator glyphs) and
**runs** the **appearance gate** (side-by-side with the restyled metadata
panel) to decide whether export needs richer formatting; **Phase D**
**records** the appearance-gate outcome. **Richer export-tree formatting is an
open question** — defer by default; do not lock in header/stripe/tier parity
on export without the appearance gate. See Phase D `D-export-visual`.

## Investigation (full history)

[tag-tree-visual-hierarchy-investigation-2026-08-16.md](../../ux-assessments/tag-tree-visual-hierarchy-investigation-2026-08-16.md)

Parts 1–7: archaeology. **Part 8–9:** scope corrections (metadata primary;
export rich chrome deferred / gated). **Not an implementation checklist.**

## Phased implementation plans (recommended order)

| Phase | Priority | Plan | What it covers |
|---|---|---|---|
| **A** | P1 | [TAG_EXPORT_TREE_CORRECTNESS_FIXES_PLAN.md](TAG_EXPORT_TREE_CORRECTNESS_FIXES_PLAN.md) | Export Select-All → group-header tri-state **correctness/behavior**; filter guard; `tags_tree` objectName; tokenized edited-row color (metadata) |
| **B** | P2 | [TAG_TREE_GROUP_HEADER_AND_STRIPING_PLAN.md](TAG_TREE_GROUP_HEADER_AND_STRIPING_PLAN.md) | **Metadata:** Goals 1–2. **Export:** Goal 3 checkbox **visual presentation** (indicator glyphs) + runs appearance gate (no rich chrome locked in) |
| **C** | P2 | [TAG_TREE_TIER_ORIENTATION_AND_NAV_PLAN.md](TAG_TREE_TIER_ORIENTATION_AND_NAV_PLAN.md) | Tier / orientation / nav on **metadata**; export only if appearance gate said so (else leave export visual alone) |
| **D** | P3 | [TAG_TREE_VISUAL_FOLLOWUPS_PLAN.md](TAG_TREE_VISUAL_FOLLOWUPS_PLAN.md) | `D-export-visual` records appearance-gate outcome; other follow-ups |

## Split-out (not tag-tree scope)

| Priority | Plan | What it covers |
|---|---|---|
| P2 | [PANE_AND_TOOLBAR_STATE_VISUAL_PLAN.md](PANE_AND_TOOLBAR_STATE_VISUAL_PLAN.md) | Active toolbar toggles + focused-pane accent frame |

## Related

- Backlog: [TO_DO.md](../../TO_DO.md) (UX / Workflow)
- Design: [DESIGN.md](../../../DESIGN.md)
- UX remediation: [UX_ASSESSMENT_REMEDIATION_AND_DESIGN_SYSTEM_PLAN.md](UX_ASSESSMENT_REMEDIATION_AND_DESIGN_SYSTEM_PLAN.md)
- Prior tag-export UX: [TAG_EXPORT_UX_IMPROVEMENTS.md](../completed/TAG_EXPORT_UX_IMPROVEMENTS.md)

## Quick "what to do next"

1. **Phase B** (headers/stripes + export Goal 3 glyphs) is implemented; confirm
   visually in the left-pane metadata panel, then **Phase C** on metadata
   (tier/orientation/nav). Do not restyle the export tree — B7 recorded **(c) none**.
2. Other Phase D / pane-toolbar items as separate PRs.

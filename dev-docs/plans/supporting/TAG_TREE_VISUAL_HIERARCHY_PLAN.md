# Tag Tree Visual Hierarchy — Plan Hub

**Created:** 2026-08-16  
**Last updated:** 2026-08-16  
**Status:** index (implementation lives in phased plans below)  
**Branch (planning):** `feature/tag-tree-visual-hierarchy-plan`

This file is the **entry point** for the tag-tree / visual-orientation workstream.
The former monolithic plan (goals, Part 2 proposals, three external reviews, and
the Part 7 recommendation pass) was moved to an investigation document so
actionable work can proceed in small, ordered plans.

## Investigation (full history)

[tag-tree-visual-hierarchy-investigation-2026-08-16.md](../../ux-assessments/tag-tree-visual-hierarchy-investigation-2026-08-16.md)

Contains: stated goals, current-implementation facts, Goals 1–4 proposals,
Part 2 whole-app ideas (P1–P10), external reviews (Gemini / DeepSeek / GLM),
ad-hoc assessment refinements (E-series), and the Part 7 recommend / discourage /
defer / phase guidance. **Not an implementation checklist.**

## Phased implementation plans (recommended order)

| Phase | Priority | Plan | What it covers |
|---|---|---|---|
| **A** | P1 | [TAG_EXPORT_TREE_CORRECTNESS_FIXES_PLAN.md](TAG_EXPORT_TREE_CORRECTNESS_FIXES_PLAN.md) | objectName/scoped QSS; Select-All → group-header tri-state; filter guard; fix hardcoded edited-row color |
| **B** | P2 | [TAG_TREE_GROUP_HEADER_AND_STRIPING_PLAN.md](TAG_TREE_GROUP_HEADER_AND_STRIPING_PLAN.md) | Goals 1–3: header chrome via shared delegate, per-group striping, partial checkbox spike + indicator, perf test |
| **C** | P2 | [TAG_TREE_TIER_ORIENTATION_AND_NAV_PLAN.md](TAG_TREE_TIER_ORIENTATION_AND_NAV_PLAN.md) | Tier ladder + P5 phase 1 (export + metadata); mono fallback; filter highlight; empties; Expand/Collapse unit; `DESIGN.md` |
| **D** | P3 | [TAG_TREE_VISUAL_FOLLOWUPS_PLAN.md](TAG_TREE_VISUAL_FOLLOWUPS_PLAN.md) | State colors, series_tree decision, select-group, P5 phase 2, PHI marker (privacy-gated), deferred items |

## Split-out (not tag-tree scope)

| Priority | Plan | What it covers |
|---|---|---|
| P2 | [PANE_AND_TOOLBAR_STATE_VISUAL_PLAN.md](PANE_AND_TOOLBAR_STATE_VISUAL_PLAN.md) | Active toolbar toggles + focused-pane accent frame (investigation P4 / C3) |

## Related

- Backlog: [TO_DO.md](../../TO_DO.md) (UX / Workflow)
- Design: [DESIGN.md](../../../DESIGN.md)
- UX remediation: [UX_ASSESSMENT_REMEDIATION_AND_DESIGN_SYSTEM_PLAN.md](UX_ASSESSMENT_REMEDIATION_AND_DESIGN_SYSTEM_PLAN.md)
- Prior tag-export UX: [TAG_EXPORT_UX_IMPROVEMENTS.md](../completed/TAG_EXPORT_UX_IMPROVEMENTS.md)

## Quick “what to do next”

1. Implement **Phase A** (correctness, no visual redesign).  
2. Run Phase B spikes (delegate reuse + `::indicator` QSS) before coding Goals 1–3.  
3. Land **Phase B**, then **Phase C**.  
4. Pull items from **Phase D** / the pane-toolbar plan only when needed; prefer
   one small PR per follow-up subsection.

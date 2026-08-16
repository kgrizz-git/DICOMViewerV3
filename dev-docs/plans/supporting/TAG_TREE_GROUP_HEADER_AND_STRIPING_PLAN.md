# Plan: Tag Tree Group Headers, Striping & Checkbox Indicators (Phase B)

**Created:** 2026-08-16  
**Last updated:** 2026-08-16  
**Status:** proposed  
**Priority:** P2  
**Phase:** B of the tag-tree visual-hierarchy workstream  
**Primary surface:** **left-pane metadata panel** (`src/gui/metadata_panel.py`)  
**Export dialog in this phase:** **Goal 3 checkboxes only** (not rich header/stripe
chrome)  
**Soft depends on:** Phase A for export checkbox / filter correctness only —
**metadata-panel visual work does not wait on Phase A.**

## Scope (refined 2026-08-16)

1. **Metadata panel** — full Goals 1–2 (group heading shade/height/font/heavier
   top border; per-group alternating rows). This tree shows tag number, name,
   **and values**, so visual hierarchy carries more information load.
2. **Export dialog** — **checkbox correctness / clarity only** in Phase B
   (Goal 3). The export tree is mostly tag ID + name for selection; it may not
   need the same rich chrome.
3. **Open question (do not lock in during Phase B):** whether the export
   `tags_tree` should later adopt metadata-panel header/stripe (or lighter)
   styling. **Gate:** after metadata Phase B lands, do an explicit side-by-side
   appearance check of the export tree; only then decide apply / light-touch /
   leave alone. Tracked under Phase D until decided.

Earlier “export gets the same visual language automatically” is **withdrawn**
as a Phase B commitment.

## Context and links

- **Hub:** [TAG_TREE_VISUAL_HIERARCHY_PLAN.md](TAG_TREE_VISUAL_HIERARCHY_PLAN.md)
- **Investigation:** [tag-tree-visual-hierarchy-investigation-2026-08-16.md](../../ux-assessments/tag-tree-visual-hierarchy-investigation-2026-08-16.md)
  (Goals 1–3; Part 8–9 scope)
- **Backlog (original left-pane ask):** [TO_DO.md](../../TO_DO.md) — “Tag browser
  group-heading styling (left pane)”
- **Export richer styling (open):** [TAG_TREE_VISUAL_FOLLOWUPS_PLAN.md](TAG_TREE_VISUAL_FOLLOWUPS_PLAN.md) (D-export-visual)
- **Next:** [TAG_TREE_TIER_ORIENTATION_AND_NAV_PLAN.md](TAG_TREE_TIER_ORIENTATION_AND_NAV_PLAN.md) (Phase C — metadata-first)
- **Design:** [DESIGN.md](../../../DESIGN.md); [UX remediation plan](UX_ASSESSMENT_REMEDIATION_AND_DESIGN_SYSTEM_PLAN.md)

## Goal and success criteria

1. **Metadata panel** group headers: distinct tokenized shade (or equally clear
   differentiation if a fill still fails visual review — then strengthen rule +
   font/height first and document the fill decision), slightly taller, bold font
   via relative size bump (`setPointSizeF(base * 1.1)`), heavier **top** rule via
   extended `GroupHeaderDelegate`.
2. Alternating row shades **reset per group** on the metadata tree; parity via a
   role (O(n) assign / recompute on expand/collapse/filter); `paint()` stays O(1).
3. **Export dialog Goal 3 only:** full selection → checkmark on group header;
   partial → clearer indeterminate glyph after a spike (QSS vs delegate).
   Depends on Phase A’s Select-All header fix where relevant. **No requirement**
   in this phase to restyle export headers/stripes to match metadata.
4. Automated perf regression on the **metadata** population path (investigation
   Part 7 #2): compare **at least two** synthetic tree sizes and assert
   **near-linear** growth (or a calibrated wall-clock bound with a generous CI
   margin **plus** an explicit growth check). Do not rely on a single fixed
   two-second limit alone.

## Prerequisites (spike — do before full implement)

- [ ] **(B0a)** Spike on **`metadata_tag_tree`:** extend `GroupHeaderDelegate`
      for heavier top rule + try tokenized header fill / taller / font bump;
      confirm theme flip (`changeEvent` / `_apply_group_header_colors`) still
      works. Scratch under `tmp/` OK.
- [ ] **(B0b)** Spike: per-group stripe-parity role on the metadata tree under
      expand/collapse/filter (no `visualIndex`, no O(n²) in `paint()`).
- [ ] **(B0c)** Spike (export): `::indicator:indeterminate` on the
      **resolver-selected** PySide6/Qt in the active env (floor
      `PySide6>=6.11.1` in `requirements.txt`, not a pinned exact version).
      Record resolved `PySide6` and Qt versions in the spike notes. Fallback:
      `PE_IndicatorItemViewItemCheck` if needed. Can run parallel to B0a/B0b.

## Checklist

### Metadata panel (Goals 1–2)

- [ ] **(B1)** Extend `GroupHeaderDelegate` (`metadata_table_model.py`): heavier
      top rule via token (e.g. `--border-strong`) + contrast check; keep
      hover/selection suppression sensible for headings.
- [ ] **(B2)** Metadata `_style_group_header_item` / `_group_header_colors`:
      bold + relative font bump, **tokenized header background** (supersedes
      “Base only forever”), taller `sizeHint`. Update the docstring that
      currently forbids fills so it records the new product decision and any
      fill that failed review.
- [ ] **(B3)** Per-group stripe-parity on `metadata_tag_tree`; recompute on
      structural change; headers do not stripe. Theme/accent flip re-applies
      colors. **Fallback if striping fragile:** drop intra-group striping; keep
      header chrome + hover + selection.
- [ ] **(B4)** Widget + visual tests centered on the **metadata panel**; HiDPI
      smoke of heavier top rule; color-blind pass if new hues land.
- [ ] **(B5)** Disable expand animation where applicable; add metadata dense-tree
      perf coverage with **≥2 sizes** and near-linear growth (or calibrated
      bound + growth check) — see success criterion 4.

### Export dialog (Goal 3 only)

- [ ] **(B6)** Partial / full group checkbox indicator (scoped QSS or delegate
      fallback from B0c). Prefer objectName scope. Confirm Select-All paths
      (Phase A) leave headers correct.
- [ ] **(B7)** **Appearance gate (decision only — do not implement rich chrome
      here):** after metadata B1–B5 look right, open the export dialog beside it
      and record whether export needs (a) full header/stripe parity, (b) a
      light-touch subset, or (c) checkbox-only / leave visual alone. Write the
      decision into Phase D `D-export-visual` (or close that item as “none”).

## Verification

- `python -m pytest tests/gui -q`
- Manual smoke: **left-pane metadata panel** group headers + per-group stripes
  (required); export **checkbox** states (required); export rich styling only if
  B7 decided “apply”
- `python scripts/agent_smoke_harness.py` (metadata / tag steps as applicable)

## Files likely touched

- **`src/gui/metadata_panel.py`** (primary)
- `src/gui/metadata_table_model.py` (shared delegate — used by metadata; keep
  export-safe if shared)
- `src/gui/dialogs/tag_export_dialog.py` (**checkbox / Goal 3 only** unless B7
  promotes more)
- `resources/themes/*.qss`
- `tests/gui/…` (metadata panel tests first)

## Out of scope

Export header/stripe/tier chrome (unless B7 promotes it into Phase D);
filter-match highlight; Expand/Collapse All on export; mono columns; PHI
markers; pane focus frames — Phase C / follow-ups / pane-toolbar plan.

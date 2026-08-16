# Tag Tree Visual Hierarchy & Group Checkbox-State Plan

**Branch:** `feature/tag-tree-visual-hierarchy-plan`
**Created:** 2026-08-16
**Status:** proposed
**Scope:** `src/gui/dialogs/tag_export_dialog.py` (the left-pane "tag browser" tree
= `self.tags_tree`, a `QTreeWidget` with depth-0 group headers and nested
sequence/item/leaf rows). No behavior change to export logic — visual/UX only.

---

## Stated goals (verbatim from request)

1. **Group heading rows** in the left-pane tag browser should be visually
   distinct from regular tag rows:
   - use a **different shade** (background) than regular tag rows;
   - be **a tiny bit taller** than regular rows;
   - use a **font size 1–2 pt larger** than regular rows;
   - have a **1 pt heavier border on top** of the group heading row.

2. **Alternating colors** in tag rows should **reset for each group** (currently
   `QTreeWidget` alternating row colors run continuously across the whole tree,
   not per group).

3. **Tag export dialog group checkbox state:**
   - when **all** tags in a group are selected, show a **checkmark** for the
     group box;
   - when **some but not all** tags in a group are selected, show a
     **dot / rectangle / some indicator** in the group box.

4. **(Open question / exploration)** More variety in **font color, size, weight,
   and/or color of icons, borders, etc.** might help users orient visually.
   Provide a layout/design summary plus multiple ideas with pros/cons.

---

## Current implementation facts (so the plan stays grounded)

- `_build_tag_tree_from_items` (`tag_export_dialog.py:555`) builds the tree:
  - `group_item = QTreeWidgetItem(self.tags_tree)` with `text(0)=f"Group {group[1:5]}"`,
    `text(1)=f"{len(tag_list)} tags"`, `UserRole` **unset** (no tag string).
  - Regular rows come from `_build_export_tag_tree_item` (`:594`), which sets
    `UserRole` to the tag string and supports sequence/item/leaf nesting.
  - Group headers are **already checkable** (`ItemIsUserCheckable`) and
    `_on_tag_selection_changed` (`:874`) → `_update_ancestors_check_state`
    (`:724`) already recomputes each group header's tri-state
    (`Checked` / `PartiallyChecked` / `Unchecked`) from its visible children.
- **Implication for Goal 3:** Qt's default tri-state check box *already* renders a
  filled/dash box when `PartiallyChecked`. So "some selected → indicator" is
  *partially* present today via the native tristate box. The request is to make
  the partial state more visually obvious (e.g., a dot/rectangle vs. the native
  dash), and to confirm the full-checkmark path is correct. See §"Group checkbox
  state" below.
- `setAlternatingRowColors` is **not** currently called on `tags_tree`; the tree
  uses the default platform background. Goal 2 requires *per-group* alternation
  reset, which `QTreeWidget`'s built-in alternating colors cannot do (they are
  keyed on global visual row index). A delegate or per-item background is
  required.
- Group headers currently share the same font/size/height as rows — no distinct
  styling is applied. Goal 1 needs explicit styling hooks.
- No `QStyledItemDelegate` is currently installed on `tags_tree`; custom drawing
  (borders, per-group alternation, partial indicators) would go through a new
  delegate or via `QTreeWidgetItem.setFont` / `setBackground` / `setSizeHint`.

---

## Proposed approach (summary)

### Goal 1 — Group heading differentiation

Apply at group-header creation time in `_build_tag_tree_from_items` (and also
re-apply in the nested/sequence render path so headers stay consistent):

- **Shade:** `group_item.setBackground(0/1, QBrush(GROUP_HEADER_COLOR))` — a
  muted tint distinct from both alternating row shades. Set on all columns.
- **Height:** `group_item.setSizeHint(0, QSize(0, base_row_height + 4))` (or
  install a delegate that returns a slightly taller `sizeHint` for items whose
  `UserRole` is `None`).
- **Font:** build one shared `QFont` from the tree's base font, bump
  `setPointSize(base + 1 or 2)`, set `setBold(True)`, and call
  `group_item.setFont(0/1, font)`.
- **Top border (1 pt heavier):** `QTreeWidgetItem` has no per-side border API.
  Options:
  - (a) Draw a 1px top line via a small `QStyledItemDelegate.paint` override for
    header rows; or
  - (b) Use a 1px top `QFrame`/spacer look by drawing the border in the
    delegate's `paint` (recommended — keeps it inside the tree, no layout
    surgery).
  - A CSS `border-top` on the `QTreeWidget` cannot target only header rows, so a
    delegate is the clean path.

All four sub-goals are best centralized in a single helper,
`_style_group_header_item(item)`, called wherever a group header is created, to
avoid drift between the standard and sequence render paths.

### Goal 2 — Alternating colors reset per group

Because built-in alternation is global, compute the alternating shade
**per group** when building rows:

- In `_build_tag_tree_from_items`, reset an `alt_toggle = False` for each group.
  For each regular row in the group, set
  `row_item.setBackground(0/1, SHADE_A if alt_toggle else SHADE_B)` and flip
  `alt_toggle`.
- For nested sequence/item/leaf rows (`_build_export_tag_tree_item`), pass the
  running `alt_toggle` down the recursion so the alternation continues
  contiguously *within* a group (it only *resets* at group boundaries, not at
  every sequence parent). This matches "reset for each group" while keeping
  nested rows readable.
- Decide whether the group header row itself participates in alternation:
  recommended **no** — the header uses the dedicated `GROUP_HEADER_COLOR` so the
  reset is visually clean.

### Goal 3 — Group checkbox state (checkmark / partial indicator)

The tri-state plumbing already exists. Two refinements:

- **Confirm all-selected → checkmark:** `_update_ancestors_check_state` already
  sets `Checked` when every visible child is checked. Verify the top
  `select_all_tags_checkbox` and the group header both show a full checkmark in
  this case. (Near-zero code; mostly a verification + a screenshot check.)
- **Partial → clearer indicator:** native `PartiallyChecked` shows a dash/fill.
  To meet "dot or rectangle or something," add a delegate `paint` for the
  checkbox of header rows when state == `PartiallyChecked` that draws a small
  filled dot or inset rectangle instead of (or in addition to) the native dash.
  This is an aesthetic layer on top of the existing state — it does not change
  selection semantics.

> Note: the same tri-state logic already drives the *top* Select-All checkbox
> (`_refresh_select_all_checkbox_state`, `tag_export_dialog_selection.py:86`).
> Keep that behavior; only the *group header* indicator is enhanced.

### Goal 4 — Broader visual-orientation variety (summary + ideas)

#### Layout & design elements (current)

- Two-column `QTreeWidget`: column 0 = Tag (e.g. `(0008,0005)`), column 1 = Name
  (+ sequence leaf counts).
- Three visual tiers exist already: **group header** → **sequence/item parent**
  → **leaf**. Today only indentation + the checkbox differentiate them.
- Controls above the tree: filter box, Include private, Include sequences,
  Select-All checkbox; a tag-count label below.
- Color vocabulary is currently limited to: default text, default background,
  default selection highlight, native checkboxes. No iconography per row kind.

#### Multiple ideas (with pros / cons)

**Idea A — Kind-coded row accents (icons + left color bar).**
Add a small column-0 icon (or a 3px left border) distinguishing
group / sequence / item / leaf (e.g., folder-ish tint for sequences, dot for
leaves).
- *Pros:* fast scanning; maps directly to the 3–4 tiers users already think in;
  cheap to implement with `setIcon` / `setBackground` on column 0.
- *Cons:* needs an icon set or drawn glyphs; color-blind users need shape
  differentiation too; risk of visual clutter on large trees.

**Idea B — Font weight/size ladder by depth.**
Group = bold +2pt; sequence parent = bold; item = italic; leaf = regular.
- *Pros:* zero new assets; pure `QFont` changes; very legible hierarchy.
- *Cons:* italics can hurt readability for long tag strings; must keep within
  the 1–2pt bump requested for headers.

**Idea C — Per-kind foreground color (subtle).**
Tint text: sequences in one hue, private tags in another, leaves neutral.
- *Pros:* immediately flags private/sensitive tags (privacy aid); low clutter.
- *Cons:* too many hues = rainbow noise; must stay WCAG-contrast-safe on both
  alternating shades; risk of clashing with the alternating background.

**Idea D — Selected/focused row emphasis.**
Stronger selection highlight + a left "active" accent when a row is checked.
- *Pros:* reinforces the export-selection mental model; pairs with Goal 3.
- *Cons:* overlaps with native selection; needs care so checked-but-not-focused
  rows stay distinguishable from focused rows.

**Idea E — Group "summary chips".**
Show, on the group header's column 1, a `n/total selected` chip (e.g.,
`12 / 40 selected`) instead of only `40 tags`.
- *Pros:* directly answers "how much of this group is selected" without opening
  it; complements Goal 3.
- *Cons:* more text per header; must update on every selection change
  (cheap — already iterating ancestors).

**Recommendation:** implement Goal 1–3 as specified, and adopt a *restrained*
combination of **B (depth font ladder) + A (left color bar, not icons, for
color-blind safety) + E (selection chip on header)** as the Goal-4 pass. Keep
palette to 2 neutrals + 1 accent + 1 private-tag hue, all contrast-checked
against both alternating shades. Defer C/D to a follow-up unless user feedback
asks for more.

---

## Implementation checklist (for later, not in this branch)

- [ ] Add `GROUP_HEADER_COLOR`, `ROW_SHADE_A`, `ROW_SHADE_B` to the dialog's
      color constants (or to the app theme/palette if one exists).
- [ ] `_style_group_header_item(item)`: font (+1–2pt, bold), background,
      `sizeHint` height, (delegate-drawn top border).
- [ ] Reset `alt_toggle` per group in `_build_tag_tree_from_items`; thread it
      through `_build_export_tag_tree_item`.
- [ ] Install a `QStyledItemDelegate` on `tags_tree` for: header top border
      (1px) and partial-checkbox dot/rectangle for group headers.
- [ ] Verify all-selected → full checkmark on group header + top Select-All.
- [ ] (Goal 4, optional) depth font ladder, left color bar, header selection
      chip.
- [ ] Tests: `tests/gui` widget test asserting group header font/size/background
      differ from leaf rows; per-group alternation resets at group boundary;
      group header `CheckState` == `Checked` when all leaves checked,
      `PartiallyChecked` when partial.
- [ ] Manual smoke: open tag export, confirm header shading/height/font,
      per-group striping, partial/full group checkbox indicators.

## Verification (when implemented)

- `python -m pytest tests/gui -q`
- `python scripts/agent_smoke_harness.py` (tag export / tree UI steps)
- Visual check of alternating reset + group checkbox states.

## Files touched (expected)

- `src/gui/dialogs/tag_export_dialog.py` (tree build + new delegate/helper)
- `tests/gui/test_tag_export_dialog*.py` (new assertions)
- Possibly a small `src/gui/` delegate module if the delegate grows beyond the
  dialog file.

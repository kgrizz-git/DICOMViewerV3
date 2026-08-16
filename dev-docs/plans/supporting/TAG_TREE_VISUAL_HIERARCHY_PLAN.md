# Tag Tree Visual Hierarchy & Group Checkbox-State Plan

**Branch:** `feature/tag-tree-visual-hierarchy-plan`
**Created:** 2026-08-16
**Status:** proposed
**Scope:**
- **Part 1 (tag-tree specifics):** `src/gui/dialogs/tag_export_dialog.py`
  (the left-pane "tag browser" tree = `self.tags_tree`, a `QTreeWidget` with
  depth-0 group headers and nested sequence/item/leaf rows). No behavior change
  to export logic — visual/UX only.
- **Part 2 (whole-app UX exploration):** design summary + multiple proposals for
  broader visual-orientation variety across the entire interface. Exploration
  only; must conform to `DESIGN.md` and the UX Assessment Remediation Plan.

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

---

# Part 2 — Whole-application visual-orientation UX summary & proposals

> This part answers the broader question raised alongside Goals 1–3: **how could
> more varied font color / size / weight and icon / border color across the
> *entire* interface help users orient?** It is a design exploration only. Any
> implementation must conform to the existing design system
> (`DESIGN.md`) and the [UX Assessment Remediation & Design System
> Plan](../../dev-docs/plans/supporting/UX_ASSESSMENT_REMEDIATION_AND_DESIGN_SYSTEM_PLAN.md),
> which is the canonical source of truth. Ideas here are **additive**, not a
> replacement for that system.

## Current interface map (what users actually see)

| Region | Widget(s) | Pain points for orientation |
|---|---|---|
| Menu bar | `QMenuBar` (File/Edit/View/Tools/Help), many submenus | Deep nesting; hard to tell which menu owns an action after the fact. |
| Main toolbar | `QToolBar` of `QToolButton`s, **SVG icons + text-under-icon**, accent-tinted, 20×20 px | Mixed icon/label; toggled actions (privacy, cine) only signal state via icon swap — easy to miss. |
| Status bar / toast | `MainWindowStatusController` + `MainWindowToastController` | Transient info; severity (info/warn/error/success) already color-codes left border + icon. |
| Left panel | scrollable `QScrollArea` → `metadata_panel` (`QTreeWidget` with group headers + sequence/item/leaf nesting) | Group headers indistinguishable from rows (same font/size/bg) — **same problem as Goal 1**. |
| Center | `image_viewer` panes in a `QSplitter`; 1×1 / 1×2 / 2×1 / 2×2 layouts, tabs, MPR, overlays, corner text | Focused vs non-focused pane not obvious; many overlays compete for attention. |
| Right panel | scrollable `QScrollArea` → tools, `roi_statistics_panel` (`QTableWidget`), histogram, etc. | Multiple stacked tools; no visual grouping between tool sections. |
| Dialogs | tag export (tree), SR browser (`QTabWidget` + `QTableWidget`), nuclear results, settings, cine, screenshot — each with its own table/tree/list mix | Inconsistent table/tree styling between dialogs; users re-learn each one. |
| Theme | light / dark + 4 accent presets (`accent_presets.py`), color tokens in `DESIGN.md`, QSS in `resources/themes` | Already tokenized — good base to extend, not to bypass. |

**Key takeaway:** the app *already* has a token system, severity-coded toasts,
and themeable SVG icons. The weak spots are (a) **group/tier hierarchy is not
visually encoded** in trees/tables (metadata panel + tag export both suffer),
and (b) **state and section** are mostly conveyed by text/icon swap rather than
by color/weight/border cues. That is exactly where "more variety" helps most.

## Design principles to honor (from `DESIGN.md`)

- **Carbon-flavored density:** clarity over decoration; thin borders; neutral
  palette; don't introduce heavy shadows/elevation on a desktop medical UI.
- **Color roles, not literals:** any new color must be a token
  (`--accent`, `--danger`, `--warn`, `--bg-surface-*`, `--text-secondary`, …),
  not a raw hex in code.
- **Severity coding** (M3 borrow): error/warning/info/success already have
  rules — extend the same language to inline states, not a new one.
- **Hide-vs-disable (HIG):** prefer removing inapplicable controls over
  graying them; when something *is* disabled, say why (tooltip), don't just dim.
- **Icon requirement (HIG):** toolbar buttons need icons; iconography should
  stay in the existing SVG set (Carbon / Material Symbols per `DESIGN.md §0`).

## Multiple proposals (with pros / cons)

### P1 — Semantic "tier" typography + color ladder across all trees/tables
Encode hierarchy with a consistent font/size/weight + a 3 px left accent bar:
group header = bold +2 pt + neutral-dark left bar; sequence parent = bold +
accent left bar; item = italic; leaf = regular. Apply identically to
`metadata_panel`, `tag_export_dialog`, and SR/results tables.
- *Pros:* one rule, every tree in the app; directly fixes Goal 1 and the
  metadata-panel twin problem; cheap (font + border per item kind).
- *Cons:* italics hurt long tag strings; must be disabled for editable cells;
  needs a shared helper so panels don't diverge.

### P2 — Status / state color language for interactive rows
Give checkable/selected/edited/disabled rows a token-driven cue: selected =
accent-tinted background + accent left bar; edited (unsaved metadata) = amber
left bar + amber text; disabled-but-meaningful = dimmed *with* a tooltip reason.
- *Pros:* turns "did I select this?" and "is this saved?" into glanceable
  signals; consistent with toast severity coding.
- *Cons:* risks clutter if every hover/selection changes color; must keep
  contrast-safe on both alternating shades and both themes.

### P3 — Section grouping & separators in panels/dialogs
Replace flat stacks of controls with labeled group boxes / hairline section
dividers + small section headers (already partially in `DESIGN.md` `QGroupBox`
rules). Used in right panel tool sections and dialog column groups.
- *Pros:* reduces "wall of widgets"; maps to progressive-disclosure philosophy;
  mostly QSS, little code.
- *Cons:* can add vertical space on already-dense dialogs; needs spacing tokens
  to avoid inconsistency.

### P4 — Icon + color reinforcement for toggled/active toolbar & pane state
Toolbar toggles (privacy on/off, cine play/pause, sync on) get a persistent
accent "active" background + a small state dot, not just an icon swap; the
**focused** image pane gets an accent frame, non-focused a muted frame.
- *Pros:* answers "what mode am I in?" and "which pane is active?" at a glance —
  currently the two biggest orientation gaps in the center/toolbar.
- *Cons:* accent-on-every-toggle can look "lit up"; needs a restrained active
  treatment (e.g. outline only) to avoid noise.

### P5 — Consistent table/tree chrome across dialogs (design-system enforcement)
Standardize striping, header row, selection, and group-header styling via shared
QSS classes (`.mpdv-tree`, `.mpdv-table`, `.mpdv-group-header`) so the tag
export tree, SR browser, nuclear results, and ROI stats all read the same.
- *Pros:* users stop re-learning each dialog; enforces `DESIGN.md`; shrinks
  per-dialog duplication.
- *Cons:* requires auditing each dialog's current custom styling; some dialogs
  have legitimately different needs (read-only vs editable).

### P6 — "Why disabled / what's different" microcopy & affordances
Where a control or row is not applicable, show a tiny inline reason (tooltip +
optional `(locked)` / `(no data)` tag) instead of silent graying; flag private/
PHI tags with a distinct hue + lock glyph.
- *Pros:* satisfies HIG hide-vs-disable + privacy aid; directly helps
  orientation for sensitive data.
- *Cons:* more text in tight UIs; PHI hue must be unambiguous and not clash
  with error/warning.

## Recommendation (restrained, system-conformant)

Adopt a **coherent, token-driven tier + state language** rather than scattered
emphasis:

1. **P1 (tier ladder)** as the backbone — fixes Goal 1 and the metadata-panel
   twin, uniformly.
2. **P2 (state color)** for selected/edited rows — complements Goal 3's
   group-checkbox work.
3. **P4 (active toolbar/pane frame)** for the two biggest center/toolbar
   orientation gaps.
4. **P5 (shared chrome)** to keep all dialogs consistent.
5. Defer **P3/P6** to the broader design-system pass unless user feedback
   specifically asks for sectioning / PHI flags.

Keep the palette to the existing tokens + **one** new "active/accent" treatment
and **one** "edited/PHI" treatment, both contrast-checked against both
alternating shades and both themes. This matches the "clarity over decoration"
Carbon stance while delivering the requested variety where it actually aids
orientation.

## Files likely touched (Part 2, future)

- `resources/themes/*.qss` (new token rules: `.mpdv-group-header`, state rows,
  active frame)
- `src/gui/main_window_theme.py` (resolve any new tokens)
- `src/gui/metadata_panel.py`, `tag_export_dialog.py` (share tier helper)
- `src/gui/main_window.py` / toolbar builder (active-state styling)
- `DESIGN.md` (document the tier/state language before merge, per its rule)

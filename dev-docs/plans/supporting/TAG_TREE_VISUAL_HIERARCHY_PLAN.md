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
- **Top border (1 pt heavier than the existing rule):** `QTreeWidgetItem` has no
  per-side border API, **but a delegate already exists**. `metadata_panel.py:296`
  installs `GroupHeaderDelegate` (`src/gui/metadata_table_model.py:52`), which
  draws a **1px** rule above *and* below each group heading (color stepped from
  `Base`→`Text` by `GROUP_HEADER_RULE_STRENGTH`) and suppresses hover/selection
  washout. The request is for the group heading's **top** border to be **heavier
  than that existing 1px rule** — i.e. more prominent, not just a copy of it.
  So: **reuse/extend that delegate** for `tags_tree` rather than writing a new
  one, but make the top rule *heavier* — concretely, draw the top line with a
  thicker `QPen` (e.g. 2px, or `1px + 1px` via a slightly stronger color/weight)
  and/or a darker token than the existing symmetric 1px rule. A CSS
  `border-top` on the `QTreeWidget` cannot target only header rows, so the
  delegate is the right mechanism; we just shouldn't duplicate the existing one
  verbatim — it needs the heavier-top variant.

All four sub-goals are best centralized in a single helper,
`_style_group_header_item(item)`, called wherever a group header is created, to
avoid drift between the standard and sequence render paths. The font/shade/height
part of that helper is new; the top-border part should live in a *shared*
group-header delegate used by both `metadata_panel` and `tag_export_dialog`.

> **Review-correction note (Gemini Pro, 2026-08-16):** the plan's earlier
> "no `QStyledItemDelegate` is installed on `tags_tree`" / "write a new delegate
> from scratch" was **wrong** — `metadata_panel.py` already has
> `GroupHeaderDelegate`. Goal 1's heavier top border must reuse it (extend the
> existing delegate so the **top** rule is drawn *heavier* — thicker `QPen` /
> stronger token — than the current symmetric 1px rule) so the export dialog and
> metadata panel don't diverge — which would also violate this plan's
> own P5 (consistent chrome) goal.

### Goal 2 — Alternating colors reset per group

**Correction (Gemini Pro review, 2026-08-16):** the earlier approach of
statically assigning `SHADE_A`/`SHADE_B` by threading an `alt_toggle` boolean
down `_build_export_tag_tree_item` is **fragile and will visibly break**. The
export tree has collapsible sequence/item nodes; expanding or collapsing
re-orders rows in the visual flow, so two same-shade rows can end up adjacent
and the per-group reset is lost. Static per-item backgrounds cannot honor
"reset per group" in a tree with dynamic expansion.

Preferred approaches (pick one):

- **(A) Dynamic delegate (recommended).** Install a `QStyledItemDelegate` whose
  `background` / `paint` computes the row's shade from its *visual* index within
  its group — e.g. walk the group's visible leaf/child count via
  `QTreeWidget.indexFromItem` / `visualIndex`, or track a "stripe parity" reset
  at each group header. This stays correct under expand/collapse. (Pairs with the
  shared group-header delegate from Goal 1 — one delegate can own both the
  header rule and the per-group stripe.)
- **(B) Built-in global alternation only.** `setAlternatingRowColors(True)` is
  correct under collapse but alternates across the *whole* tree, not per group.
  Acceptable if the per-group reset is lowered in priority, but does **not**
  satisfy the stated goal.

Group headers should *not* participate in striping — they keep the dedicated
header treatment so each group's reset reads cleanly.

### Goal 3 — Group checkbox state (checkmark / partial indicator)

The tri-state plumbing already exists. Two refinements:

- **Confirm all-selected → checkmark:** `_update_ancestors_check_state` already
  sets `Checked` when every visible child is checked. Verify the top
  `select_all_tags_checkbox` and the group header both show a full checkmark in
  this case. (Near-zero code; mostly a verification + a screenshot check.)
- **Partial → clearer indicator:** native `PartiallyChecked` shows a dash/fill.
  **Prefer a QSS swap over manual delegate painting** (review correction): set
  `QTreeWidget::indicator:indeterminate { image: <dot-or-rect svg> }` so Qt
  keeps native hover/pressed/focus behavior and we only replace the glyph.
  - Caveat: this QSS selector applies to **every** indeterminate checkbox, i.e.
    also to partially-checked Sequence/Item parents — which is actually
    *desirable* consistency, not a bug. No special-casing needed.
  - Avoid hand-painting checkbox primitives in `paint()` (brittle: loses OS
    hover/pressed/focus rings).

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

> **Token discipline:** do **not** add raw hex constants like `GROUP_HEADER_COLOR`
> / `ROW_SHADE_A`. `DESIGN.md §2` mandates semantic tokens (e.g. `--bg-surface`,
> `--bg-surface-raised`, `--text-secondary`, `--accent`, `--fg-disabled`). Any new
> shade must be added as a token in `resources/themes/*.qss` (and resolved via
> `main_window_theme.py`), not hardcoded in the dialog.

- [ ] Reuse/extend `GroupHeaderDelegate` (`src/gui/metadata_table_model.py:52`,
      already used by `metadata_panel.py:296`) for `tags_tree`. Make the **top**
      group-heading rule *heavier* than the existing symmetric 1px rule (thicker
      `QPen` / stronger token), keep hover/selection suppression, and make it
      shared so both trees match (supports P5).
- [ ] `_style_group_header_item(item)`: font (+1–2pt, bold), header background
      (token), taller `sizeHint` (no layout surgery).
- [ ] Per-group alternation via a **dynamic delegate** keyed on visual index /
      group-boundary reset (correct under expand/collapse) — **not** static
      `alt_toggle` per-item. Single shared delegate can own both header rule and
      stripe.
- [ ] Partial-checkbox indicator via QSS
      `QTreeWidget::indicator:indeterminate { image: <dot-or-rect svg> }`
      (dot/rectangle glyph); covers group headers *and* partial Sequence/Item
      parents.
- [ ] Verify all-selected → full checkmark on group header + top Select-All.
- [ ] (Goal 4, optional) depth font ladder, left color bar, header selection
      chip.
- [ ] Tests: `tests/gui` widget test asserting group header font/size/background
      differ from leaf rows; per-group alternation resets at group boundary after
      expand/collapse; group header `CheckState` == `Checked` when all leaves
      checked, `PartiallyChecked` when partial.
- [ ] Manual smoke: open tag export, confirm header shading/height/font,
      per-group striping (and that it survives expand/collapse), partial/full
      group checkbox indicators.

## Verification (when implemented)

- `python -m pytest tests/gui -q`
- `python scripts/agent_smoke_harness.py` (tag export / tree UI steps)
- Visual check of alternating reset + group checkbox states.

## Files touched (expected)

- `src/gui/metadata_table_model.py` (extend shared `GroupHeaderDelegate`)
- `src/gui/dialogs/tag_export_dialog.py` (tree build + reuse delegate + helper)
- `resources/themes/*.qss` (any new tokens; `::indicator:indeterminate` glyph)
- `tests/gui/test_tag_export_dialog*.py` (new assertions)

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

---

# Part 3 — External review (Gemini Pro, 2026-08-16) & additional ideas

A Gemini Pro agent (provider `agy`) reviewed this plan read-only against the
codebase. Its feedback was reviewed critically (not assumed correct). Three of
its technical corrections were **verified accurate and adopted** (see inline
"Review-correction note" / Goal 1–3 above):

1. **Static per-group alternation breaks on collapse** → replaced with a dynamic
   delegate keyed on visual index (Goal 2).
2. **`metadata_panel` already has `GroupHeaderDelegate`** → reuse/extend it
   instead of writing a new delegate for the 1pt border (Goal 1), and share it
   to satisfy P5.
3. **Partial-checkbox indicator via QSS, not manual paint** → use
   `::indicator:indeterminate` (Goal 3).
Plus a valid **token-system warning**: the original checklist's raw hex
constants violate `DESIGN.md §2`; corrected to semantic tokens.

The reviewer also surfaced ideas beyond this plan's P1–P6. After critical
review, the worthwhile ones are captured below as **P7–P10** (added to Part 2's
proposal set); two were rejected as too costly/noisy (sticky group headers,
sequence block tinting) and are noted as **dropped**.

### P7 — Monospace font for Tag / VR columns (typography)  · **Adopt**
Apply a mono font (e.g. `IBM Plex Mono`, already bundled per `DESIGN.md §3.1`)
to the Tag ID and VR columns, leaving names in the sans font.
- *Pros:* perfect numeric alignment makes long tag lists dramatically easier to
  scan; already sanctioned by the design spec; zero new assets.
- *Cons:* monospace needs slightly more horizontal width (mitigated by the
  existing 120px Tag column).
- *Verdict:* low-hanging fruit the plan's typography ladder (Idea B) missed.

### P8 — Filter-match substring highlighting  · **Adopt**
When the filter box is used, paint the matched substring in `--accent` (or bold)
via a delegate, instead of only hiding non-matches.
- *Pros:* explains *why* a row survived the filter, especially when the match is
  buried in a long value; strong orientation aid in dense tables.
- *Cons:* requires a rich-text/span-painting delegate (moderate complexity);
  must coexist with the dynamic stripe delegate from Goal 2 (one delegate can
  own both).
- *Verdict:* high value, pairs naturally with the shared tree delegate.

### P9 — Dimmed empty / null value states  · **Adopt**
Render tags with empty values in `--fg-disabled` + italic (e.g. dimmed
`<empty>`), so missing data recedes.
- *Pros:* reduces noise, draws the eye to tags that actually carry data; matches
  Carbon "clarity over decoration".
- *Cons:* minor addition to tree-population logic.
- *Verdict:* cheap, conforms to tokens, directly aids orientation.

### P10 — Keyboard expand/collapse shortcuts for sequence blocks  · **Adopt**
Add shortcuts (e.g. `Ctrl+Right`/`Ctrl+Left`, or `Shift+Click`) to
expand/collapse whole sequence subtrees in the export dialog.
- *Pros:* large speed-up for power users navigating sequences that can hold
  thousands of items (`tag_export_dialog.py` large-sequence threshold); no
  discoverability cost if it mirrors OS tree conventions.
- *Cons:* must avoid clashing with existing shortcuts (audit `DESIGN.md §6`).
- *Verdict:* complements the visual hierarchy work with a navigation aid.

### Dropped (per review, with rationale)
- **Sticky / pinned group headers** — perfect for "what group am I in?" but very
  high effort to do robustly in `QTreeWidget` (overlay hacks / QML). Defer.
- **Sequence block background tint** — clashes with alternating rows; nesting is
  already conveyed by branch lines (`setRootIsDecorated`). Too noisy. Defer.

### Updated Part 2 recommendation
Add **P7, P8, P9, P10** to the adopt set. The combined rollout becomes:
tier ladder (P1) + state color (P2) + active toolbar/pane frame (P4) + shared
chrome (P5) + **mono tag columns (P7)** + **filter highlight (P8)** + **dimmed
empties (P9)** + **expand/collapse shortcuts (P10)**; defer P3/P6 and the two
dropped items until broader design-system feedback. All additions stay within
the token system and the "clarity over decoration" stance.

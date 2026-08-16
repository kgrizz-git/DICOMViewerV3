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

> **Review-correction note (DeepSeek v4 flash, 2026-08-16) — reuse trap (A3) and
> fill-scope (A4):**
> - The reused `GroupHeaderDelegate` keys off `GROUP_HEADER_KEY_ROLE =
>   UserRole + 2` (`metadata_table_model.py:33`); **tag-export group headers do
>   NOT set that role** (`tag_export_dialog.py:582-587`), so a verbatim reuse
>   would treat every export row as a leaf and never draw the rule. The export
>   tree must set `GROUP_HEADER_KEY_ROLE` (or a shared role) on its headers.
> - Tag-export rows already use `UserRole + 1` for large-sequence leaf counts
>   (`tag_export_dialog.py:631`); the new stripe-parity role must avoid colliding
>   with `UserRole + 1` / `UserRole + 2` — audit roles per widget before sharing.
> - Metadata-panel group rows are `setFirstColumnSpanned(True)`
>   (`metadata_panel.py:500`); export group rows are **not** spanned
>   (`tag_export_dialog.py:582`). The existing delegate paints the rule across
>   `option.rect` per column, so on the export tree a non-spanned header would
>   draw the heavier top border only across the 120px Tag column. Either span the
>   export header (which merges col-0/col-1 text — so Idea E's `n/total` chip must
>   move into the merged string) or paint the top rule from `rect.left()` to the
>   tree's full viewport width.
> - **Fill scope (A4):** `metadata_panel.py:553-573` deliberately uses **Base +
>   rule, no fill** because every colored band "read as an odd block floating on
>   the pane." Any *background fill* in Goal 1 / P1 must be scoped to the **export
>   dialog only**; the metadata panel stays on Base + rules (which the "heavier
>   top rule" already satisfies). Do not re-introduce panel fills.

### Goal 2 — Alternating colors reset per group

**Correction (Gemini Pro review, 2026-08-16):** the earlier approach of
statically assigning `SHADE_A`/`SHADE_B` by threading an `alt_toggle` boolean
down `_build_export_tag_tree_item` is **fragile and will visibly break**. The
export tree has collapsible sequence/item nodes; expanding or collapsing
re-orders rows in the visual flow, so two same-shade rows can end up adjacent
and the per-group reset is lost. Static per-item backgrounds cannot honor
"reset per group" in a tree with dynamic expansion.

**Correction (DeepSeek v4 flash review, 2026-08-16):** approach (A) above is
wrong on two counts and must not be used:
- `QTreeWidget` has **no** `visualIndex` API — the only `visualIndex` in the
  repo is `QHeaderView.visualIndex` (`metadata_panel.py:339`), which reorders
  *sections*, not tree rows. `indexFromItem` returns a flat model index, not a
  visual position. So "compute shade from visual index" references a
  nonexistent call.
- Computing parity per painted row (walking the group's visible children inside
  `paint()`) is **O(n²)** on a fully expanded large study — the exact trap this
  codebase already paid for at `tag_export_dialog.py:565` and
  `metadata_table_model.py:215-216` (~19s). Forbidden.

**Adopted approach — parity in a role, recomputed on structural change (O(n)):**
- At build time (`_build_tag_tree_from_items` / `_build_export_tag_tree_item`),
  assign a **stripe-parity role** (`UserRole + N`, distinct from the existing
  `UserRole + 1` large-sequence-leaf-count and `UserRole + 2`
  `GROUP_HEADER_KEY_ROLE`) per visible row, resetting parity at each group
  header. One O(n) pass.
- Recompute that role (not in `paint`) whenever the visible set changes: on
  `itemExpanded` (`tag_export_dialog.py:345`), a new `itemCollapsed` connection,
  and after `_filter_tags` (the filter hides rows, which can make two
  same-parity visible rows adjacent — double-shade adjacency).
- The delegate reads the parity role in `paint()` and fills the background —
  `paint()` stays O(1) per row, correct under expand/collapse/filter.
- Group headers keep the dedicated header treatment (no stripe).

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

> **Review correction (DeepSeek v4 flash, 2026-08-16) — two real traps the
> earlier text missed:**
> 1. **Select-All does NOT update group headers.** `_toggle_all_tags`
>    (`tag_export_dialog.py:679`) deliberately skips `_update_ancestors_check_state`
>    (to avoid clobbering independently-checked SQ/Item parents). So after the top
>    "Select All" checkbox or the Select-All button, **every group header stays
>    `Unchecked`** — the "all-selected → checkmark on group header" goal fails.
>    Fix: add a *targeted* pass that recomputes only group-header tri-state from
>    their visible children (without touching SQ/Item parents), and call it from
>    `_toggle_all_tags` / `_on_select_all_tag_checkbox`. Add this to the Goal-3
>    checklist.
> 2. **`::indicator` QSS on trees is unproven on this Qt.** The app pins
>    `PySide6>=6.11.1` and the themes have **no** `QTreeWidget`/`QTreeView`
>    `::indicator` rules today (only `QMenu::indicator` + `QCheckBox::indicator`,
>    `resources/themes/*light/dark.qss`). Item-view `::indicator` styling has a
>    long Qt-6 bug history (QTBUG-98848 et al.). **Do not assume it works:**
>    spike it on the pinned PySide6 first; if it fails, the fallback is a delegate
>    that draws `PE_IndicatorItemViewItemCheck` over the native `paint()` (keeps
>    native hover/focus, unlike hand-painting the box). The selector also blast-
>    radiates to the series tree, tag-viewer dialog, and SR browser — scope it
>    `objectName`-based if app-wide unification is not intended.

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
      already used by `metadata_panel.py:296`) for `tags_tree`. Tag-export group
      headers must set `GROUP_HEADER_KEY_ROLE` (or a shared role) or the delegate
      treats them as leaves. Make the **top** group-heading rule *heavier* than
      the existing symmetric 1px rule (thicker `QPen` / stronger token), keep
      hover/selection suppression, and make it shared so both trees match (P5).
      Audit `UserRole + 1` (export leaf count) / `UserRole + 2` (header role)
      collisions before sharing. Paint the top rule across the tree's full width
      (export headers are not `setFirstColumnSpanned`).
- [ ] `_style_group_header_item(item)`: font (+1–2pt, bold), header background
      (token), taller `sizeHint` (no layout surgery). **Fill scoped to export
      dialog only** — metadata panel stays Base + rules (A4).
- [ ] Per-group alternation via a **stripe-parity role** assigned at build time
      (O(n) once), recomputed on `itemExpanded` / new `itemCollapsed` /
      after `_filter_tags` — **not** computed in `paint()` (would be O(n²)), and
      **not** via a nonexistent `QTreeWidget.visualIndex` (A2/A6). Delegate reads
      the role in `paint()` (O(1)). Single shared delegate can own header rule +
      stripe.
- [ ] Partial-checkbox indicator: **spike the QSS
      `QTreeWidget::indicator:indeterminate` on pinned PySide6>=6.11.1 first**
      (trees have no such rule today; Qt-6 `::indicator` has a bug history, A1).
      If it works, use a scoped (objectName) `image: <dot-or-rect svg>` glyph
      covering group headers + partial SQ/Item parents. If not, fall back to a
      delegate drawing `PE_IndicatorItemViewItemCheck` over native `paint()`.
      New SVG glyph assets must pass the repo's artifact/approved-media review.
- [ ] **Goal-3 fix (A5):** add a targeted pass that recomputes only group-header
      tri-state from their visible children, and call it from
      `_toggle_all_tags` / `_on_select_all_tag_checkbox` / the **Select-All
      button** (`tag_export_dialog.py:314`) / **after `_filter_tags`** — all
      currently skip ancestor update, leaving headers `Unchecked`.
- [ ] **Set `self.tags_tree.setObjectName("tag_export_tags_tree")`** (D1) + a
      scoped `QTreeWidget#tag_export_tags_tree` block in both themes, so the
      `::indicator` / striping / active-row QSS can be targeted without app-wide
      blast radius (prereq for A1/B2).
- [ ] **Fix the existing token violation** in `metadata_panel.py:626`
      (hardcoded `QColor(80,50,120)` edited-row color) as part of P2 unification
      — route through a tokenized `_edited_tag_row_colors()` (D2), not just new
      token states.
- [ ] **Export dialog Expand/Collapse All buttons** (parity with metadata panel
      `metadata_panel.py:267`) folded into the export-dialog work (D4).
- [ ] **Filter parity guard (D5/B7):** do **not** block *all* `QTreeWidget`
      signals during filtering (blunt — can suppress selection/repaint). Instead
      set a boolean `_is_filtering = True` guard inside the `itemExpanded`/
      `itemCollapsed` slots so they return early, then recompute stripe parity
      **once** at the end of `_filter_tags` and clear the flag — do not let
      in-walk `setExpanded` re-enter the recompute.
- [ ] **Heavier top rule as a token** (`--border-strong`, D6) + a **contrast
      check** (rule vs header fill *and* adjacent row shade, Carbon band); no
      hand-waved "thicker QPen."
- [ ] **Span decision (D7):** do NOT `setFirstColumnSpanned` export headers
      (preserve two-column alignment); delegate paints the top rule
      `rect.left()` → full viewport width.
- [ ] **Disable tree expand animation** for dense UI (extends C7/D8); verify in
      harness smoke.
- [ ] Re-apply header shade/rule + stripe-parity colors on **theme/accent flip**
      (`PaletteChange` / `changeEvent`, as `metadata_panel.py:531-552` already
      does) so they don't go stale — B2.
- [ ] **`series_tree` decision (D3):** either give it the same group-header
      treatment (with a delegate variant that *allows* selection, since study/
      series rows are interactive) or mark it explicitly out-of-scope.
- [ ] (Goal 4, optional) depth font ladder, left color bar, header selection
      chip (fill-scope caveat applies); enforce **shape/position redundancy, not
      hue alone**, for color-blind safety (B8/D17).
- [ ] **Document the tier/state language in `DESIGN.md`** as an explicit step
      (D9/D18) — the hierarchy system is not a system if undocumented.
- [ ] Tests: `tests/gui` widget test asserting group header font/size/background
      differ from leaf rows; per-group alternation resets at group boundary after
      expand/collapse AND after filter; group header `CheckState` == `Checked`
      when all leaves checked, `PartiallyChecked` when partial; **group headers
      reach `Checked` after top Select All** (A5 regression) **and after the
      Select-All button and after filter**.
- [ ] Manual smoke + **device-pixel (HiDPI) check** of the heavier top rule
      (B4); **color-blind (deuteranopia/protanopia) screenshot pass** for the new
      tier/state hues (C6).

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

### P7 — Monospace font for Tag / VR columns (typography)  · **Adopt (with correction)**
Apply a mono font to the Tag ID and VR columns, leaving names in the sans font.
- *Pros:* perfect numeric alignment makes long tag lists dramatically easier to
  scan; sanctioned by the design spec (`DESIGN.md §3.1` specifies Plex Mono as the
  mono family).
- *Cons:* monospace needs slightly more horizontal width (mitigated by the
  existing 120px Tag column).
- *Correction (DeepSeek review, A7):* **`IBM Plex Mono` is NOT actually
  bundled.** `DESIGN.md` *specifies* it, but `resources/fonts/` ships none and
  `bundled_fonts.py` registers only Plex Sans / Noto / Spectral / Raleway / Red
  Hat Text / Open Sans / DejaVu — no Mono key. So this is **not** "zero new
  assets": it needs a newly bundled mono font (license + artifact/approved-media
  review) or a platform `Consolas, monospace` fallback with variable metrics.
  **Reduce P7 to: tag/VR columns get a mono font — pending the font-bundling
  decision** (track as a pre-req, not a free win).
- *Verdict:* still worthwhile, but scope the bundling cost honestly.

### P8 — Filter-match substring highlighting  · **Adopt**
When the filter box is used, paint the matched substring in `--accent` (or bold)
via a delegate, instead of only hiding non-matches.
- *Pros:* explains *why* a row survived the filter, especially when the match is
  buried in a long value; strong orientation aid in dense tables.
- *Cons:* requires a rich-text/span-painting delegate (moderate complexity);
  must coexist with the dynamic stripe delegate from Goal 2 (one delegate can
  own both). **Perf guard (E2):** never use a live `QTextDocument` inside
  `paint()` — it is O(expensive) per row and will destroy scroll perf on
  thousands of rows. Use `QStaticText` / `QPainter.drawText` with precomputed
  bounding rects, cached per cell.
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

---

# Part 4 — Second external review (DeepSeek v4-flash-free, 2026-08-16)

A second, independent read-only review was run with an opencode / DeepSeek
v4-flash-free subagent and critically evaluated (not assumed correct). It
confirmed the earlier Gemini corrections and surfaced **additional, verified
technical errors** in the plan that the first review missed. The load-bearing
fixes (A2/A6, A3, A5, A1) are already folded into Goals 1–3 and the
implementation checklist above; the gaps (B1–B7) and new ideas (C1–C11) are
summarized here.

## Verified corrections adopted
- **A2 / A6 — no `QTreeWidget.visualIndex`; parity-in-`paint` is O(n²).** The
  Goal-2 "dynamic delegate keyed on visualIndex" used a nonexistent API and an
  O(n²) repaint. Replaced with a **stripe-parity role** assigned at build time
  (O(n)) and refreshed on expand/collapse/filter; `paint()` reads the role
  (O(1)). See Goal 2.
- **A3 — reuse trap.** `GroupHeaderDelegate` keys off `GROUP_HEADER_KEY_ROLE`
  (`UserRole + 2`), which tag-export headers never set; a verbatim reuse would
  render every export row as a leaf. Export headers must set the role; role
  collisions (`UserRole + 1` leaf count) must be audited; the export header is
  not `setFirstColumnSpanned`, so the heavier top rule must span the full tree
  width, not just the Tag column. See Goal 1 note.
- **A5 — Select All leaves group headers `Unchecked`.** `_toggle_all_tags`
  skips `_update_ancestors_check_state`, so the top Select-All never checks the
  group headers — the Goal-3 "all-selected → checkmark" goal silently fails.
  Added a targeted group-header-only recompute to the Select-All path.
- **A1 — tree `::indicator` QSS unproven on pinned PySide6>=6.11.1.** No tree
  `::indicator` rules exist today; Qt-6 item-view indicator styling has a long
  bug history. Made it **spike-first** with a `PE_IndicatorItemViewItemCheck`
  delegate fallback, and flagged the app-wide blast radius (series tree,
  tag-viewer, SR browser) → scope `objectName`-based.
- **A4 — fill scope.** Metadata panel deliberately uses Base + rule (no fill);
  Goal-1 / P1 fills must be export-dialog-only. Captured as a hard scope rule.
- **A7 — Plex Mono not bundled.** P7 corrected to "pending font-bundling
  decision," not "zero new assets."

## Gaps / risks the review flagged (B1–B7)
- **B1** shared-delegate scope creep touches the metadata panel's existing
  per-item `border-bottom` QSS — needs panel regression + theme-flip coverage.
- **B2** theme/accent flip (`PaletteChange`) must re-apply header/stripe colors
  (the panel already does via `changeEvent`/`_apply_group_header_colors`).
- **B3** global `::indicator` rule hits series tree, tag-viewer, SR browser too
  — decide app-wide vs scoped.
- **B4** "1pt heavier" is ambiguous on HiDPI — specify logical px + device-pixel
  smoke.
- **B5** `setPointSize` vs app-level QSS `font-size` override risk.
- **B6** new glyph SVG crosses the repo's asset/approved-media gate.
- **B7** no empty/disabled-state or selection-scoped test; the disabled-tree
  "Updating tag list…" state is never revisited.

## Additional ideas (C1–C11) — after critical review
**Adopt:**
- **C1 — Unified PHI/private-tag marker** (muted hue + "P" monogram on every
  private row across panel/viewer/export). *Pros:* privacy safety + cross-dialog
  consistency with repo PHI guardrails. *Cons:* one new glyph + audit when
  "Include private" is on.
- **C2 — Filter "no match" state with one-click Clear** in both filter boxes.
  *Pros:* explains the empty tree + hands back control. *Cons:* a few pixels.
- **C3 — Focused-pane chrome** (2px accent frame + dimmed non-focused overlays
  across 1×2/2×2/MPR). *Pros:* answers "which pane am I on?" directly. *Cons:*
  overlaps draw stack; keep animation-free. (Small first step: frame only.)
- **C4 — Group-header tri-state tooltip + count** ("7 of 40 selected") on hover,
  mirroring Idea E without permanent text. *Pros:* near-zero cost, no new glyph
  (weakens reliance on A1). *Cons:* tooltip delay on dense trees.
- **C5 — Tag-tree context menu + Expand/Collapse All** (mirror metadata panel's
  existing menu) + group-to-group collapse shortcut (audit `DESIGN.md §6`).
  *Pros:* huge for sequence-heavy studies; reuses a pattern. *Cons:* shortcut
  conflict risk only.
- **C6 — Color-blind screenshot pass** (deuteranopia/protanopia) for new tier/
  state hues before merge. *Pros:* cheap insurance for a color-coded UI. *Cons:*
  manual step. (Verification item, not code.)
- **C7 — Motion/restraint guardrail in DESIGN.md** ("no animation in dense tree
  UI; state changes instant or ≤120ms"). *Pros:* protects "clarity over
  decoration." *Cons:* none. (Governance.)

**Drop:**
- **C8 — Series/tag-union coherence** (show which series drove each row) — large
  pipeline change; revisit later.
- **C9 — Density toggle** (comfortable/compact) — scope + cross-panel testing;
  Carbon density is fixed.
- **C10 — Frozen/pinned Tag column** — not natively supported by QTreeWidget.
- **C11 — Keyboard group-hopping** — conflict/discovery burden; fold into C5's
  expand/collapse-all.

## Updated combined recommendation
Carry forward P1–P5 + P7(corrected)–P10, and add the lightweight, high-value
**C1–C7** (with C6/C7 as verification/governance items). Defer C8–C11 and the
earlier P3/P6. Keep everything token-scoped and "clarity over decoration"; the
C7 motion guardrail explicitly forbids animation creep in the tree UI.

---

# Part 5 — Third external review (Nvidia GLM 5.2, 2026-08-16)

A third, independent read-only review was run with an opencode / Nvidia GLM
5.2 subagent and critically evaluated (not assumed correct). It confirmed the
prior corrections and surfaced several **new, code-verified gaps** the first two
reviews missed. The non-duplicative, high-value items are folded in below as the
**D-series**; the prior P1–P10 / C1–C7 set stands.

## Verified new findings (adopted)
- **D1 — `tags_tree` has no `objectName`** (`grep setObjectName` in the export
  dialog finds only the status label at `:155`; the metadata tree is
  `metadata_tag_tree` at `metadata_panel.py:278`). Any scoped QSS
  (`::indicator`, striping, active-row) is therefore untargetable today.
  **Action:** add `self.tags_tree.setObjectName("tag_export_tags_tree")` and a
  scoped `QTreeWidget#tag_export_tags_tree` block in both themes before any
  tree-level token work (prereq for A1/B2).
- **D2 — Existing token violation in edited-row color (ties to P2).**
  `metadata_panel.py:626` hardcodes `QColor(80, 50, 120)` (dark purple, no
  token) for edited rows, bypassing `DESIGN.md §2` — exactly what the checklist
  forbids for *new* code. P2 unification must **also fix this existing
  violation** (route through a tokenized `_edited_tag_row_colors()` like
  `tag_viewer_dialog` does), not only add new token states.
- **D3 — `series_tree` is unaddressed (P5 gap, B6).** The export dialog has
  *two* trees (`series_tree` `:151`, `tags_tree` `:152`); all plan work targets
  `tags_tree`. `series_tree` has the same group/header + tri-state shape and no
  header styling. Acknowledge it: either give it the same group-header treatment
  (with a delegate variant that *allows* selection, since study/series rows are
  interactive) or mark it explicitly out-of-scope for this plan.
- **D4 — Export dialog lacks Expand/Collapse All (parity gap, B1).** The
  metadata panel has Expand All / Collapse All buttons (`metadata_panel.py:267`)
  and a group-collapse context menu; the export dialog has neither. Fold at least
  Expand/Collapse All buttons (matching the panel) into the export-dialog work;
  small addition, directly aids orienting sequence-heavy trees.
- **D5 — Filter walk can desync parity (B7).** `_apply_tag_filter_recursive`
  (`:771`) auto-expands matching descendants, firing `itemExpanded` *during* the
  `setHidden` walk. Parity recompute must run **once after** `_filter_tags`
  completes, not as a side effect of each in-walk `setExpanded`. Guard:
  blockSignals during the filter walk, then recompute parity once at the end.
- **D6 — "Heavier top rule" needs a token, not hand-waving (B4).** Specify the
  rule color as a token (e.g. `--border-strong`) and add a **contrast check**
  (rule vs header fill *and* vs adjacent row shade, within Carbon's band) —
  especially since export headers get a fill while metadata headers stay Base.
- **D7 — Set the span decision (B5).** The plan left "span vs full-width rule"
  open. Decision: **do not span** export headers (col-0 = "Group 0008", col-1 =
  "N tags" are separate, scannable cells; spanning forces a merged string that
  loses two-column alignment). Delegate paints the heavier top rule from
  `rect.left()` → full viewport width. State explicitly so an implementer
  doesn't span-and-merge by default.
- **D8 — Disable tree expand animation for dense UI (extends C7).** Qt's
  expand/collapse animation can feel laggy on huge groups; verify it is off (or
  disable) as part of the motion-restraint harness check.
- **D9 — Document the tier/state language in `DESIGN.md` as a checklist item.**
  The plan lists `DESIGN.md` under "Files likely touched" but the Goal-1–3
  checklist has no doc-edit task. An undocumented hierarchy system is not a
  system — make it an explicit implement step.

## Additional ideas (D10–D20) — after critical review
**Adopt:**
- **D10 — Collapsed-group selection chip in header text** (e.g. `"Group 0008
  (12/40)"`) so coverage is visible without expanding. *Pros:* always-visible,
  no tooltip latency (stronger than C4 for collapsed case). *Cons:* more text
  per header.
- **D11 — `setObjectName` + scoped QSS block for `tags_tree`** (mirrors
  `#metadata_tag_tree`). *Pros:* enables scoped striping/indicator/active-row
  without app-wide blast radius. *Cons:* small per-theme block. (Prereq D1.)
- **D12 — "Select group" right-click on export tree** (checks all visible leaves
  under that group); must re-run the Goal-3 group-header recompute. *Pros:*
  fast selection of e.g. all `(0008,*)`; complements Select-All. *Cons:* must
  wire the A5 header refresh.
- **D13 — Filter-box focus shortcut (`Ctrl+F`/`Ctrl+L`)** + **match-count badge
  (`"42 matches"`)** in both the export dialog and metadata panel. *Pros:* filter
  is the primary orientation tool; standard, high value-per-line; badge answers
  "did my filter do anything?" *Cons:* audit `DESIGN.md §6`.
- **D14 — Sticky filter + Select-All row** so scrolling a long tree doesn't lose
  the controls. *Pros:* prevents re-narrow loop. *Cons:* modest layout change.
- **D15 — Concrete empty + disabled states:** whole-tree empty body when
  `studies` is empty (`_initial_tag_tree_build` early-return `:442`) and a
  prominent banner/dim for the "Updating tag list…" disabled state (`:454`,
  today only `setEnabled(False)`). *Pros:* fills B7's gap with real artifacts.
  *Cons:* overlay is non-trivial; use a label/banner variant.
- **D16 — Indentation parity between the two trees** (metadata sets
  `setIndentation(7)`, export uses default ~20px). *Pros:* trustworthy shared
  visual language (P5). *Cons:* verify no test asserts default indentation.
- **D17 — Monochrome kind icons (folder/chevron/dot) + color bar** (color as
  *secondary* cue) to enforce B8's shape-redundancy rule for color-blind safety.
  *Pros:* satisfies B8's "differ by shape/position, not hue alone." *Cons:* new
  SVG assets → repo asset/approved-media gate.
- **D18 — DESIGN.md edit as an explicit checklist item** (see D9).
- **D19 — P5 as two phases:** export dialog + metadata panel *now*; SR browser /
  nuclear results / ROI stats *next* (their "Files touched" only lists the first
  two). *Pros:* keeps P5 from being silently aspirational.

**Drop (with rationale):**
- **D20 — Selection-count color ladder on the group chip** (muted/secondary/
  accent by 0/partial/full) — redundant with the checkbox tri-state, risks
  clutter. Drop.
- **D21 — Distinct partial glyph for group vs SQ parents** (dot only for groups)
  — contradicts P5 consistency; let them match. Drop.
- **D22 — VR column in export dialog** — scope creep; VR belongs to the metadata
  panel. Drop.
- **D23 — Persist group expand/collapse in the export dialog** — dialog is
  session-scoped; mark out-of-scope (don't copy the panel's pattern blindly).
  Drop.
- **D24 — "Recently exported" preset auto-pin** — belongs to a presets plan, not
  this tree-visual scope. Drop.

## Updated combined recommendation
Carry P1–P5 + P7(corrected)–P10, C1–C7, and add the high-value D-items:
`tags_tree` objectName + scoped QSS (D1/D11), fix the existing hardcoded edit
color as part of P2 (D2), export-dialog Expand/Collapse All (D4), filter focus
shortcut + match-count badge (D13), collapsed-group chip (D10), concrete
empty/disabled states (D15), indentation parity (D16), color-blind shape
redundancy via monochrome kind icons + bar (D17), and make `DESIGN.md` doc-edit
(D9/D18) and P5 two-phase (D19) explicit checklist items. Keep series-tree
treatment (D3) as an explicit in-scope-or-out decision. Defer D20–D24 and the
earlier P3/P6/C8–C11. All additions token-scoped, animation-free (C7/D8), and
color-blind-safe via shape redundancy (B8/D17).

---

# Part 6 — Ad-hoc assessment (tmp/tag_tree_assessment_20260816_171112.md)

A standalone assessment file was dropped in `tmp/` and reviewed critically. Most
of its points are **already covered** by earlier parts (stripe-parity role
`UserRole + 3` = A-7; no-fill metadata scope = A4; expand animation off = D8;
collapsed-group chip = D10; shared-chrome token fix = D2). A few points were
genuinely new or sharpened an existing one, and are captured here as the
**E-series** (low-churn; folded into the checklist where actionable).

## Adopted refinements / new ideas
- **E1 — D5 signal-blocking is too blunt (sharpened).** Blocking *all*
  `QTreeWidget` signals during the filter walk can suppress selection/repaint
  signals. Use a boolean `_is_filtering` guard inside the `itemExpanded`/
  `itemCollapsed` slots instead (return early), then recompute parity once.
  Applied to the D5 checklist item.
- **E2 — P8 highlight must be cached (new perf risk).** Painting filter-match
  substrings via `QTextDocument` inside `paint()` is O(expensive) per row and
  will destroy scroll perf on thousands of rows. Mandate `QStaticText` /
  `QPainter.drawText` with precomputed rects, cached per cell — not live
  `QTextDocument`. Add to the P8 implement note.
- **E3 — Dynamic insert/delete parity (gap closed).** The export tree is rebuilt
  wholesale (`_render_tag_tree` clears + rebuilds), so incremental add/remove
  doesn't occur; parity is recomputed at build. Note as a guard: any future
  incremental mutation path must recompute parity, not assume it persists.
- **E4 — Font bump, if kept, use a relative multiplier (B3 nuance).** GLM (D3/B3)
  preferred `setBold` only / QSS token over `setPointSize`. If a size bump is
  nonetheless kept, use `setPointSizeF(base * 1.1)` (relative) rather than an
  absolute `+1/+2` offset for better HiDPI/accessibility scaling.
- **E5 — Search/filter enhancements (new, adopt as follow-up).**
  - *Fuzzy matching* (`sqnc` → `Sequence`) — forgiving, fast; risk of false
    positives in dense dictionaries. **Adopt** as a later enhancement.
  - *Filter chips / quick toggles* (`[Private] [Sequences] [Empties]
    [Selected]`) for boolean filtering without typing. **Adopt** (high value,
    pairs with C1/C2); note vertical-space cost.
  - *Search-history dropdown* (last N terms). **Adopt** (cheap; aids repetitive
    validation); needs filter-state persistence (session or ConfigManager).
- **E6 — Subtle token-driven row hover tint** (`--bg-surface-hover`). Native
  hover exists but a token-driven, contrast-checked tint aids target
  acquisition in dense rows. **Adopt** lightly; must be contrast-checked against
  both stripe shades (Shade A/B). (Consistent with existing `QTreeWidget::item:hover`
  QSS already in themes — verify it covers both trees via the new objectName.)

## Considered and ruled out
- **E7 — Skeleton/shimmer loading for trees.** Conflicts with the C7/D8
  no-animation guardrail for dense UI; the existing "Updating tag list…" banner
  (D15) is the restrained equivalent. **Drop.**
- **E8 — Floating `QLabel` sticky-header simulation.** The plan already dropped
  native sticky headers (high effort); a viewport-floating label is a lighter
  variant but still needs scroll/viewport event sync and adds UI complexity for
  marginal gain. **Drop** (defer with the earlier sticky-header item).

## Updated combined recommendation (final)
Adds to the carry list: D5 via boolean guard (E1), P8 cached draw (E2), the
search enhancements E5 (fuzzy + chips + history) and subtle hover tint E6 as
follow-ups; font bump as relative multiplier only if kept (E4). Rules out
skeleton/shimmer (E7) and floating sticky header (E8). Everything else
unchanged.


# Plan: Metadata group-header chrome polish (font scale + bottom-rule opacity)

**Created:** 2026-08-20  
**Last updated:** 2026-08-20  
**Status:** completed 2026-08-20.

**Priority:** P3  
**Branch:** `feature/metadata-group-header-chrome-polish`  
**Primary surface:** left-pane metadata tag tree (`QTreeWidget#metadata_tag_tree`)  
**Export / Tag Viewer:** out of scope (they do not use `style_group_header_item` or `MetadataTagTree`)

Two targeted visual tweaks on group-heading rows, plus doc/token hygiene so
`DESIGN.md` and the live paint path stop disagreeing.

## Context and links

- **Hub:** [TAG_TREE_VISUAL_HIERARCHY_PLAN.md](../supporting/TAG_TREE_VISUAL_HIERARCHY_PLAN.md)
- **Prior chrome:** [TAG_TREE_GROUP_HEADER_AND_STRIPING_PLAN.md](../completed/TAG_TREE_GROUP_HEADER_AND_STRIPING_PLAN.md) (Phase B)
- **Design spec:** [DESIGN.md](../../../DESIGN.md) §2.3
- **Code:** `src/gui/metadata_table_model.py` (`style_group_header_item`,
  `MetadataTagTree._paint_header_rules`, `group_header_bottom_rule_color`)
- **Tests:** `tests/test_metadata_panel_tree_chrome.py`,
  `tests/test_metadata_panel.py`
- **Second-opinion notes (local, not committed):**
  `tmp/metadata_group_header_font_rec_20260819T235521.md`

## Goal and success criteria

1. Group headers stay **bold**. Keep `GROUP_HEADER_FONT_SCALE` as the size
   knob; change its value from `1.1` to `1` (`1.0`). The multiply in
   `style_group_header_item` stays (`point_size * GROUP_HEADER_FONT_SCALE`).
   Header size matches the tree font (sequence parents remain bold at the same
   size; headers still outrank them via fill + rules).
2. Keep a **1 px** bottom hairline (`fillRect` geometry unchanged). Reduce its
   **opacity by 35% of the current token alpha** (opaque 255 → remaining
   **65%** → alpha **166** after rounding). RGB of the bottom-rule tokens does
   not change.
3. Paint widths and the new opacity factor are **named constants**. No
   shared/role/fill/top-rule constants used elsewhere are edited.
4. `DESIGN.md` §2.3 and the Unreleased changelog describe the live chrome:
   bold at `GROUP_HEADER_FONT_SCALE = 1`; **fixed** per-theme fill
   (`#0B0B0C` / `#F3F3F3`, not palette-mixed); 1 px top; 1 px bottom at 65%
   opacity.

## Constant discipline (do not touch shared tokens)

Inventory of `GROUP_HEADER_*` in `metadata_table_model.py` at plan time:

| Constant | Callers besides this module | This plan |
|---|---|---|
| `GROUP_HEADER_KEY_ROLE` | `metadata_panel.py`, `metadata_tree_chrome.py`, tests | **Do not change** (value or name) |
| `GROUP_HEADER_FILL_DARK` / `_LIGHT` | tests via `group_header_fill_color` | **Do not change** RGB |
| `GROUP_HEADER_TOP_RULE_WIDTH` | tests (assert `== 1.0`); used by top `QPen` | **Do not change** value (`1.0`) |
| `GROUP_HEADER_TOP_RULE_DARK` / `_LIGHT` | tests via `group_header_top_rule_color` | **Do not change** RGB |
| `GROUP_HEADER_BOTTOM_RULE_WIDTH` | tests only (`== 1.0`); **unused in paint** | **Keep `1.0`**. Start using it as the `fillRect` height. Do not set `0.5`. |
| `GROUP_HEADER_BOTTOM_RULE_DARK` / `_LIGHT` | tests via `group_header_bottom_rule_color` only | **Keep RGB**. Do not rewrite hex. Apply opacity on a **copy** in the helper. |
| `GROUP_HEADER_FONT_SCALE` | `style_group_header_item` + one chrome test | **Keep the constant.** Change value `1.1` → `1` (`1.0`). Do not delete it or inline a literal. |

**New constant (this module only):**

```python
# Keep 65% of the bottom-rule token alpha (35% reduction from current opacity).
GROUP_HEADER_BOTTOM_RULE_OPACITY_FACTOR = 0.65
```

Apply inside `group_header_bottom_rule_color` (not by mutating the module-level
`QColor` objects):

```python
color = QColor(GROUP_HEADER_BOTTOM_RULE_DARK)  # copy; never setAlpha on the constant
color.setAlpha(round(color.alpha() * GROUP_HEADER_BOTTOM_RULE_OPACITY_FACTOR))
return color
```

`setAlpha` on the module-level token would permanently alter a shared
`QColor` and leak into later calls. `round(255 * 0.65) == 166`.

**Hardcoded `1` in `_paint_header_rules` `fillRect`:** replace with
`int(GROUP_HEADER_BOTTOM_RULE_WIDTH)` (or `1` derived from that constant).
Leave the top rule on `GROUP_HEADER_TOP_RULE_WIDTH`.

Do **not** change `STRIPE_PARITY_ROLE`, fill colors, top-rule colors/width,
or any QSS `{metadata_tag_*}` tokens.

## Implementation checklist

- [x] **(H1)** `GROUP_HEADER_FONT_SCALE = 1.0` (was `1.1`). Keep
      `font.setPointSizeF(point_size * GROUP_HEADER_FONT_SCALE)` and
      `setBold(True)`. Update the helper docstring (bold, scale 1.0 so the
      requested point size matches the tree; row height follows the bold
      face; no extra padding). **Do not** keep
      `header_size >= tree_size * SCALE - 0.05` as the only size contract:
      that floor was calibrated for a 10% bump. New contract (both):

  ```python
  assert header_size >= tree_size - 0.05  # no visible shrink vs tree font
  assert abs(header_size - tree_size * GROUP_HEADER_FONT_SCALE) <= 0.05
  ```

      The `0.05` pt dip matches the existing test epsilon. It is not a
      visible shrink; it covers Qt `pointSizeF()` round-trip on non-integer
      system fonts. At `SCALE == 1.0` the two asserts are the same lower
      bound (`tree_size - 0.05`) plus an upper cap at `tree_size + 0.05`.
      Do not use a strict `>= tree_size` with zero slop. Keep bold and
      `header_h >= tag_h`.
- [x] **(H2)** `group_header_bottom_rule_color`: copy token, scale alpha by
      `GROUP_HEADER_BOTTOM_RULE_OPACITY_FACTOR`. Update the helper docstring
      ("1 px bottom hairline, 65% of token opacity").
- [x] **(H3)** `_paint_header_rules`: `fillRect` height from
      `GROUP_HEADER_BOTTOM_RULE_WIDTH` (still `1.0`). Do not convert the bottom
      rule to a 0.5 `QPen`. No new antialiasing.
- [x] **(H4)** Tests — treated as a **spec change**, not a force-pass:
      - `test_group_header_font_and_height_are_bumped`: reword (scale is 1,
        not a bump). Size asserts per H1: `header_size >= tree_size - 0.05`
        and `abs(header_size - tree_size * GROUP_HEADER_FONT_SCALE) <= 0.05`.
        Keep bold and `header_h >= tag_h`.
      - `test_header_top_and_bottom_rules_are_one_px_and_full_width`: keep
        width asserts at `1.0`. The pixmap is filled with opaque `band`
        before `_paint_header_rules` so the SourceOver assertion is not
        affected by platform-style painting in `drawRow`. **Replace** the
        `abs(mid_bottom_pixel.lightness() - bottom_rule.lightness()) <= 40`
        check. Compute expected SourceOver blend of
        `group_header_bottom_rule_color` (RGB + alpha 166) over opaque
        `band`, then assert each sampled bottom RGB channel is within a
        small integer slop of that blend. Helper-level:
        `group_header_bottom_rule_color(...).alpha() ==
        round(255 * GROUP_HEADER_BOTTOM_RULE_OPACITY_FACTOR)`. Do not
        leave the old token-lightness compare in place — at 65% alpha the
        dark-theme rule (0x2D) over fill (0x0B) sits close to the fill and
        that compare neither proves the hairline nor the opacity.
      - `test_heading_takes_the_pane_background_and_is_ruled_off`: RGB
        lightness/saturation of the helper still ignore alpha; confirm it
        still passes. If it compares `==` on a QColor including alpha,
        compare RGB only or use the pre-alpha tokens.
      - Unit check: mutating the returned color does not change
        `GROUP_HEADER_BOTTOM_RULE_DARK.alpha()` (stays 255).
- [x] **(H5)** Docs:
      - `DESIGN.md` §2.3 **Metadata group header fill**: replace the stale
        “Base mixed 10% toward Text, then 65% toward black / #ffffff” with
        the live **fixed** fills (`#0B0B0C` dark / `#F3F3F3` light). This
        drift is already in the spec; this polish is the right time to fix
        it so DESIGN matches the paint path.
      - `DESIGN.md` §2.3 **Metadata group header rules**: replace “no bottom
        rule” with “1 px top hairline; 1 px bottom hairline at 65% of the
        bottom-rule token opacity (35% reduction from opaque).”
      - Bold / `GROUP_HEADER_FONT_SCALE = 1` on the header type/fill row if
        that is the natural home. Bump DESIGN **Last updated**.
      - `CHANGELOG.md` `[Unreleased]` **Changed**: one patch-level bullet for
        this polish. Reconcile the existing Unreleased bullets that already
        disagree with code (fill still “steps from the Phase B mix”;
        “bottom rule … gone”; Phase B “~10% font bump”). Fill wording must
        say fixed per-theme colors, not a mix. Do not bump
        `src/version.py` until a release cut.
      - Hub row + this plan’s status when implementing.
      - Do **not** rewrite the completed Phase B plan or the 2026-08-16
        investigation as if they had always specified this chrome; those are
        historical. A one-line “later polish: …” pointer on the hub is enough.
      - `user-docs/`: no change (no user-facing control).
- [x] **(H6)** SemVer: **patch** (visual polish of existing chrome; no new
      feature).

## Out of scope

- Subtracting 1 pt from the tree font (would put headers below sequence-parent
  size). Revisit only after H1 is seen in the live pane.
- 0.5 logical-px pens, dropping the bottom rule entirely, hover/selection,
  stripe parity, export-tree chrome, Tag Viewer dialog.
- Changing fill RGB, top-rule RGB/width, or `GROUP_HEADER_KEY_ROLE`.

## Verification

- `python -m pytest tests/test_metadata_panel_tree_chrome.py tests/test_metadata_panel.py -n 0 -v`
- Manual: left metadata pane, several groups expanded, dark and light. Headers
  still read as section labels (bold + band + top rule), bottom edge quieter.
- `python scripts/check_user_docs_links.py` if `dev-docs/README.md` / hub links
  change.

## Files expected (implementation)

- `src/gui/metadata_table_model.py`
- `tests/test_metadata_panel_tree_chrome.py` (and the small copy/alpha assert)
- `DESIGN.md`, `CHANGELOG.md`
- This plan + hub checklist ticks

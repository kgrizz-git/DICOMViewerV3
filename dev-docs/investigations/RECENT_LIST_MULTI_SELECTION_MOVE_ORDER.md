# Recent-List Multi-Selection Move Order

**Status:** Resolved — 2026-08-15

## Finding

`EditRecentListDialog._move_item_up()` does not preserve the order of adjacent
selected items. With synthetic entries `a, b, c, d`, selecting `b` and `c`, and
moving up once produces `c, a, b, d` rather than `b, c, a, d`.

## Resolution

`_move_item_up()` now processes selected rows from top to bottom. Moving an
earlier selected item therefore leaves the stored row of each later selected
item valid, preserving adjacent and non-adjacent relative order. The ordinary
regression in `tests/gui/test_edit_recent_list_dialog_coverage.py` verifies
both ordering and selection state; 32 focused dialog tests and the full
parallel suite pass.

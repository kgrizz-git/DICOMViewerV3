# Recent-List Multi-Selection Move Order

## Finding

`EditRecentListDialog._move_item_up()` does not preserve the order of adjacent
selected items. With synthetic entries `a, b, c, d`, selecting `b` and `c`, and
moving up once produces `c, a, b, d` rather than `b, c, a, d`.

## Scope

This is characterized by the strict xfail in
`tests/gui/test_edit_recent_list_dialog_coverage.py`. Production code was not
changed in the coverage slice. The fix should preserve both the selected
items' relative order and their selection state, then be followed by the
focused dialog tests and normal GUI verification.

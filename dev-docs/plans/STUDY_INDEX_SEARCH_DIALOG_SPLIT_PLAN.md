# Plan: Split the study index search dialog

**Created:** 2026-11-06
**Last updated:** 2026-11-06
**Status:** Reviewed — safe to implement. Not started
**Branch:** `fix/medium-bug-hunt-20261104`

Gemini 3.8 Flash (high) reviewed this draft on 2026-11-06. One blocking wording error is corrected below: the open-failure warning keeps the sanitized exception text. The hook, mixin, import, and test-patch claims were confirmed. Nits from that review (who imports the shared sentence, the constant's name, and that `--all` does not rewrite the grandfather file) are folded in. The stale line-count backlog item that review also flagged is removed; see below.

## Decision

Yes. Split [`src/gui/dialogs/study_index_search_dialog.py`](../../src/gui/dialogs/study_index_search_dialog.py).

The file is 1373 lines. [`scripts/line_complexity_grandfather.json`](../../scripts/line_complexity_grandfather.json) records that exact count. [`scripts/git_hook_line_complexity.py`](../../scripts/git_hook_line_complexity.py) blocks a file above 750 lines unless it stays at or under its recorded cap, and it blocks any growth past that cap. This file is already sitting on the cap, so one added line fails the commit.

Two different warnings are stuck on one physical line:

- Line 724 is the open-failure warning inside `_relocate_and_reopen`. It is the fixed sentence plus a newline plus `sanitize_message(str(exc), redact_paths=True)`. `tests/gui/test_study_index_open_relocate.py` requires both "could not be opened" and the exception detail (`"lookup failed"`).
- Lines 716 and 1119 are the same unchanged-relocate sentence, with no newline in the displayed text. Line 716 is the other branch of `_relocate_and_reopen`. Line 1119 is `_MissingStudiesDialog._relocate_selected`.

Ruff does not require either one-liner: `E501` is ignored in `ruff.toml`. Line 724 is long so the open-failure `try` could be added without growing the file.

Splitting is a move, not a behavior change. After it lands, those calls can be normal multiline source again, and the next study-index dialog edit does not have to delete a line somewhere else first. The displayed text stays the same, including the sanitized exception detail.

## What the hook will do

Measured with lizard on 2026-11-06 (`lizard==1.24.3` from the dev lock).

| Item | Recorded cap | Current | After this split |
|---|---|---|---|
| `study_index_search_dialog.py` file lines | 1373 | 1373 | File cap **removed**, because the file is under the 750-line block |
| `study_index_search_dialog.py::_open_row` | CCN 17 | CCN 17 (lines 610–694) | **Unchanged.** Stays in this file |
| `study_index_search_dialog.py::_remove_studies_at_rows` | CCN 22 | CCN 22 (lines 758–847) | **Unchanged.** Stays in this file |

Two traps:

1. **Do not land a commit while this file is still over 750 lines.** The hook ratchets a grandfather cap down when the staged file is smaller but still blocking. An intermediate file of 800 lines would lock the next cap at 800. One commit must leave the file at or under 750. Target **at or under 600** (the warn threshold) so the next small edit does not warn.
2. **Do not move `_open_row` or `_remove_studies_at_rows`.** Grandfather keys are `path::function`. A move is a new function. CCN 17 and 22 on a path that is not in the allowlist blocks the commit. Bringing them to CCN 15 or under is a separate edit of open and delete behavior. It is out of scope here. Leave both methods, and the thin wrappers that only call them (`_open_selected_file`, `_on_table_context_menu`, `_on_remove_from_index_clicked`, `_remove_study_at_row`), in `study_index_search_dialog.py`.

Do not run `--generate-grandfather`. That rewrites every hotspot in the repo. `python scripts/git_hook_line_complexity.py --all` checks the worktree and does not rewrite the grandfather file. The pre-commit `--staged` run is what ratchets. On the commit that drops this file under 750, that ratchet deletes the file entry and leaves the two function caps in place. Confirm that in the commit diff: the file key is gone, and both function keys are still 17 and 22.

## Target files

All new modules live under `src/gui/dialogs/`. `gui/` may import `gui/`, `core/`, and `utils/`. Nothing here imports `main`. No new `core/` → `gui/` edge.

Follow the existing dialog split: [`src/gui/dialogs/tag_export_dialog.py`](../../src/gui/dialogs/tag_export_dialog.py) keeps the `QDialog` and composes plain mixins. Mixins do not inherit `QObject` or `QDialog`, do not define `__init__`, and do not declare a `Signal`. `QDialog` stays the only Qt base and is listed last:

```python
class StudyIndexSearchDialog(StudyIndexSearchPanelsMixin, QDialog):
```

`super().__init__(parent)` in the dialog still reaches `QDialog` because the mixin has no `__init__`. Copy the file-level pyright pragma from `src/gui/dialogs/tag_export_dialog_selection.py` onto the mixin file only. Do not annotate `self` as `StudyIndexSearchDialog`. Do not import the dialog class from the mixin (that cycle is what the pragma is avoiding).

| File | Owns | Approx. lines | Highest CCN moving in |
|---|---|---|---|
| `src/gui/dialogs/study_index_dialog_common.py` | `_TITLE_STUDY_INDEX` and `_MSG_RELOCATE_UNCHANGED` | ~30 | none |
| `src/gui/dialogs/study_index_search_model.py` | `_StudyIndexMdyLineEdit`, `_format_indexed_at_display`, `_StudyIndexGroupedModel` (current lines 80–249) | ~210 | `data` CCN 8 |
| `src/gui/dialogs/study_index_missing_studies_dialog.py` | `_MISSING_COLUMNS` and `_MissingStudiesDialog` (current lines 984–1187) | ~250 | `_populate` CCN 8 |
| `src/gui/dialogs/study_index_about_dialog.py` | `_AboutStudyIndexDialog` (current lines 1189–1373) | ~240 | `_move_index` / `_import_index` CCN 4 |
| `src/gui/dialogs/study_index_search_panels.py` | `StudyIndexSearchPanelsMixin` | ~360 | `_relocate_and_reopen` CCN 7 |
| `src/gui/dialogs/study_index_search_dialog.py` | Dialog shell, query, sort, selection, open, remove. Re-exports the names tests already import | ~500, must be ≤ 600 | unchanged `_open_row` 17, `_remove_studies_at_rows` 22 |

`_build_ui` is CCN 1 (lines 277–415). It is safe to move. Every other method moving onto the mixin is CCN 7 or lower. If lizard reports any moved function above 15, extract a helper in the new file until it is at or under 15. Do not add a grandfather entry for it.

### Methods that stay on `StudyIndexSearchDialog`

`__init__` (including the `QTimer` that saves column order), `showEvent`, `_apply_hidden_columns`, `_privacy`, `_effective_date_filters`, `_service_query_kwargs`, `_backend_ok_or_warn`, `_run_browse`, `_on_search_clicked`, `_on_clear_filters_clicked`, `_on_recently_indexed_clicked`, `_on_load_more`, `_on_header_section_clicked`, `_update_sort_indicator`, `_on_double_click`, `_selected_row`, `_selected_rows`, `_open_selected_file`, `_open_row`, `_on_table_context_menu`, `_on_remove_from_index_clicked`, `_remove_study_at_row`, `_remove_studies_at_rows`.

The timer stays here because it is created with `QTimer(self)` and connected in `__init__`. The mixin method `_on_header_section_moved` only starts it.

### Methods that move to `StudyIndexSearchPanelsMixin`

`_build_ui`, `_relocate_and_reopen`, `_on_open_index_location`, `_show_about_index`, `_index_folder`, `_check_indexed_studies` (and its nested callbacks), `_show_missing_studies`, `_on_header_section_moved`, `_persist_column_visual_order`.

`_open_row` calls `_relocate_and_reopen`. Moving the callee onto the mixin is valid: the dialog inherits it. Leaving `_relocate_and_reopen` beside `_open_row` would also stay under 600 lines. This plan moves it so the long warning lives in a file that is not on the line cap.

The mixin calls back into the dialog through `self` (`_run_browse`, `_backend_ok_or_warn`, `_privacy`, `_open_paths`, `_service`, `_config`, `_model`, `_table`, `_save_columns_timer`). Those attributes stay assigned in the dialog `__init__` or in `_build_ui`. The mixin imports `_StudyIndexMdyLineEdit` from the model module, because the moved `_build_ui` constructs the two date fields. The dialog `__init__` still constructs `_StudyIndexGroupedModel` and imports the model module for that.

### Shared strings

Put these in `study_index_dialog_common.py`:

- `_TITLE_STUDY_INDEX = "Study index"`. Import it from every module that shows a study-index message box: the search dialog, the mixin, the missing-studies dialog, and the about dialog.
- `_MSG_RELOCATE_UNCHANGED`, the unchanged-relocate sentence, byte-for-byte the text now at lines 716 and 1119. One parenthesized string. Do not put a `\n` in it. The displayed message stays one paragraph. Import it only from the mixin (`_relocate_and_reopen`) and the missing-studies dialog (`_relocate_selected`). The search dialog and the about dialog do not use it.

The open-failure warning stays a different message. After the move, write it as a normal multiline expression that still appends the sanitized detail:

```python
safe = sanitize_message(str(exc), redact_paths=True)
QMessageBox.warning(
    self,
    _TITLE_STUDY_INDEX,
    "The index was updated, but the study could not be opened.\n" + safe,
)
```

Do not drop `safe`. `tests/gui/test_study_index_open_relocate.py` asserts both "could not be opened" and "lookup failed".

### Import cycle

`study_index_dialog_common.py` imports neither dialogs nor the mixin. The model module imports neither. The missing-studies dialog imports the common module and `core` / `utils` only (including `repair_str_bytes_repr_artifact`). It does not import `gui.study_index_info`.

The about dialog imports the common module, `core` / `utils`, and `gui.study_index_info`. `_refresh_info` uses `study_index_db_path`, `credential_store_note`, `format_size_on_disk`, and `format_last_modified`. `_open_location` uses `open_study_index_location` and `study_index_db_path`. `_move_index`, `_export_index`, and `_import_index` also use `study_index_db_path`.

The mixin imports the common module, the model module (`_StudyIndexMdyLineEdit`), the two extracted dialogs, and `gui.study_index_info` (`study_index_db_path` for the Open-location tooltip and failure text, `open_study_index_location` for `_on_open_index_location`). The search dialog imports the model module and the mixin, and re-exports the extracted names. Nothing imports the search dialog except `src/gui/actions/dialog_actions.py` and tests.

## Public imports that must keep working

Re-export these from `study_index_search_dialog.py`. Tests and `dialog_actions.py` keep importing them from there:

- `StudyIndexSearchDialog`
- `_AboutStudyIndexDialog`
- `_MissingStudiesDialog`
- `_StudyIndexGroupedModel`
- `_format_indexed_at_display`

`src/gui/actions/dialog_actions.py` imports only `StudyIndexSearchDialog`. Leave that import alone.

## Tests

Most tests patch `QMessageBox` or `QFileDialog` on the PySide class, or call methods on the dialog instance. Those keep working when a method moves, because they do not patch a module global.

Two string patches name a global in the dialog module. Retarget them to the module that will look the name up. Do not keep a dummy binding in the dialog module just so the old patch path still hits.

| Test | Patch | New target |
|---|---|---|
| `tests/gui/test_study_index_search_dialog_coverage.py` `test_about_import_and_export_errors` | `gui.dialogs.study_index_search_dialog.read_entries_csv` | `gui.dialogs.study_index_about_dialog.read_entries_csv` |
| same file, `test_missing_study_and_location_guards` | `gui.dialogs.study_index_search_dialog.open_study_index_location` | `gui.dialogs.study_index_search_panels.open_study_index_location` |

These stay on `study_index_search_dialog`, because `_remove_studies_at_rows` stays there:

- `tests/gui/test_study_index_multi_remove.py` (`QMessageBox.question` / `information`)
- `tests/test_dialog_error_sanitization.py` (`study_index_dialog.QMessageBox` around `_remove_studies_at_rows`)

No new test behavior. Do not loosen assertions. The only test edits are the two patch paths above.

## Stale line-count backlog item

Removed from [`dev-docs/TO_DO.md`](../TO_DO.md) Maintenance in the same commit as this plan. The item said the repo had no line-count hook and asked for a new `scripts/check_file_line_counts.py` plus a CI step.

That work is already done:

- [`scripts/git_hook_line_complexity.py`](../../scripts/git_hook_line_complexity.py) warns at 600 lines and blocks at 750, and blocks cyclomatic complexity above 15. Existing over-cap files stay on the grandfather list until they shrink.
- `.githooks/pre-commit` runs it with `--staged`.
- The `lizard` job in [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) runs it with `--all`.

Do not add `scripts/check_file_line_counts.py`. A second script would duplicate this hook. The fixed thresholds plus the grandfather file are the exclusion mechanism the old item was asking for. This split uses that hook; it does not replace it.

## Non-goals

- No change to search, relocate, remove, import, or export behavior. Wording of messages stays the same.
- No CCN rewrite of `_open_row` or `_remove_studies_at_rows`. Sonar cognitive complexity is also out of scope. The hook measures lizard CCN, not Sonar cognitive complexity.
- No edit to `sqlcipher_store.py` or `export_manager.py`. Both are already near the 750-line block.
- No `--generate-grandfather`, no hand-raised grandfather cap, and no new grandfather entry.
- No `src/version.py` bump and no changelog bullet. This is not user-visible. Record it in [`dev-docs/MAINTENANCE_LOG.md`](../MAINTENANCE_LOG.md) when the split lands.
- No user-docs edit.
- No docstring sweep of `study_index_search_dialog.py`. Interrogate already reports that file at about 25% (57 functions without docstrings). The file is on its 1373-line cap, so those docstrings cannot be added until this split lands. CodeRabbit's pre-merge docstring check still sees that pre-existing gap.

## Implementation order

Do this in one commit so the line cap is removed rather than ratcheted to a new over-750 number.

1. Copy `study_index_search_dialog.py` to `tmp/backups/study-index-dialog-split/` before editing. `tmp/` is gitignored. Delete that backup after the tests below pass. Do not stage it.
2. Add the new modules by moving the code above. Confirm each class and function is in the new file before deleting it from the source file.
3. Rewire imports, re-exports, and the two monkeypatches. Use `_MSG_RELOCATE_UNCHANGED` at both unchanged-relocate call sites. Break the open-failure `QMessageBox.warning` across lines and keep `"\n" + safe`. Do not change the words users see.
4. Run, from the project venv:
   - `python scripts/git_hook_line_complexity.py --all` and confirm this file is no longer a blocking line-count item, the two function caps are unchanged, and no new function is over CCN 15. This command does not edit `scripts/line_complexity_grandfather.json`. Check that edit in the commit diff after the pre-commit hook runs.
   - `python -m pytest tests/gui/test_study_index_search_dialog_coverage.py tests/gui/test_study_index_search_dialog_state.py tests/gui/test_study_index_search_dialog_sort.py tests/gui/test_study_index_open_relocate.py tests/gui/test_study_index_multi_remove.py tests/gui/test_study_index_missing_studies_dialog.py tests/test_dialog_error_sanitization.py -q`
   - `ruff check` on the touched modules, and `python scripts/check_basedpyright_errors.py` (or the equivalent scoped check if the full script is too broad — the touched files must report 0 errors)
   - `python scripts/check_architecture_boundaries.py`
5. Update the Study index search row in [`ARCHITECTURE.md`](../../ARCHITECTURE.md) so it names the new modules. Add the maintenance-log paragraph. Remove the matching item from [`dev-docs/TO_DO.md`](../TO_DO.md) in that same commit.

Focused tests are the acceptance gate. A manual pass of the Study Index dialog (search, open, relocate, remove, missing studies, about) is useful later and is not a blocker for this move.

## Closeout

When the split is done, archive this plan to `dev-docs/plans/completed/` in the same commit, and drop the backlog line that points here.

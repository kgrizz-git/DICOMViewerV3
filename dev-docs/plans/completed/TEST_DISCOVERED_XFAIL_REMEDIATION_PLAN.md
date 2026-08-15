# Test-Discovered Strict-Xfail Remediation Plan

**Status:** Completed
**Last updated:** 2026-08-15
**Scope:** Two validated production defects that were intentionally retained as
strict xfails during coverage work.

## Completion record

- `EditRecentListDialog._move_item_up()` now processes selected rows from top
  to bottom, preserving the relative order and selection of adjacent and
  non-adjacent items. The former strict xfail is an ordinary passing regression.
- Projection exports now use the valid DICOM CS values `MIP`, `AIP`, and
  `MINIP` in `ImageType`; full descriptions remain in `SeriesDescription` and
  `ImageComments`. The former strict xfail is an ordinary passing conformance
  regression with no CS-length warning.
- Focused parallel checks passed: 32 recent-list tests and 19 export-rendering
  tests. The CI-equivalent full parallel coverage gate passed: 6,193 passed,
  15 skipped, 81.52% total coverage, and `coverage.xml` produced.

## Goal

Correct the two known defects without weakening their regression coverage. Each
strict xfail becomes an ordinary, passing behavior test only after the intended
production behavior is implemented and verified.

## Guardrails

- Make the smallest production change that fixes each documented defect.
- Keep test data synthetic; do not add DICOM files, images, or PHI-bearing
  artifacts.
- Do not convert an xfail to a passing test before its production fix is in the
  same change.
- Do not broaden the work into export redesign, recent-list UI redesign, or
  unrelated coverage cleanup.
- Use the existing virtual environment and normal parallel test configuration
  for batch verification. `-n 0` is acceptable only for focused Qt debugging.

## Defect inventory

| Priority | Defect | Evidence | Intended outcome |
| --- | --- | --- | --- |
| P2 | Adjacent selected recent-list entries reverse when moved upward. | [Investigation](../../investigations/RECENT_LIST_MULTI_SELECTION_MOVE_ORDER.md) and `test_move_selected_items_preserves_order_and_selection`. | A move-up preserves relative order and selection; moving back down restores the original list. |
| P2 | Projection exports write an overlong DICOM CS `ImageType` component. | [Investigation](../../investigations/PROJECTION_IMAGE_TYPE_CS_VIOLATION.md) and `test_projection_dataset_image_type_values_are_dicom_cs_valid`. | Every `ImageType` component is a valid CS value no longer than 16 characters, while descriptive metadata remains useful. |

The nearby browser-column-order test is not part of this plan: the prior
duplicate-ID defect is already fixed in `study_index_config.py` and its
ordinary regressions pass.

## Phase 1 — Preserve recent-list order

1. Read `_move_item_up()` and `_move_item_down()` in
   `src/gui/dialogs/edit_recent_list_dialog.py`; characterize non-adjacent,
   adjacent, and boundary selections before changing the algorithm.
2. Replace the upward move loop with an order-preserving operation. It must move
   each contiguous selected block one row upward without swapping selected
   neighbours, and it must leave a selection containing row zero unchanged.
3. Confirm the current down-move behavior remains the inverse for the covered
   selection. Add a separate regression only if focused characterization exposes
   another defect; document it and use a strict xfail if it is deferred.
4. Remove the xfail marker from
   `tests/gui/test_edit_recent_list_dialog_coverage.py` only after the expected
   order and selected item identities pass.

**Validation:** run the focused recent-list test module serially if Qt event
debugging requires it, then with the repository's normal parallel settings;
run the nearest GUI tests and `ruff check` on changed Python files.

## Phase 2 — Make projection `ImageType` DICOM-conformant

1. Inspect `create_projection_dataset()` in `src/gui/export_rendering.py` and
   its callers to identify whether downstream code relies on the descriptive
   third `ImageType` component.
2. Replace the overlong mapping values with short valid CS components such as
   `MIP`, `AIP`, and `MINIP` (all upper-case and within the 16-character CS
   limit). Keep the fuller user-facing description in `SeriesDescription` or
   `ImageComments`.
3. Update the ordinary metadata test to expect the chosen short value and remove
   the xfail marker only when the conformance test passes with no CS-length
   warning.
4. Check every supported projection type plus the fallback mapping. Preserve
   existing UID, pixel, modality, and spacing behavior.

**Validation:** run `tests/gui/test_export_rendering_coverage.py`, then the
nearest export tests with normal parallel settings. Confirm the test that
records pydicom warnings finds no `ImageType` CS-length warning. Run `ruff
check` on changed Python files.

## Phase 3 — Integrate and verify

1. Remove or update each investigation's open/xfail status and the matching
   active `TO_DO.md` entry after its fix lands; retain a concise completion
   record in the maintenance log or completed plan as appropriate.
2. Run the full parallel test and branch-coverage command used by CI. Verify the
   80% coverage floor, complete `coverage.xml`, and no unexpected XPASS or
   xfail count changes.
3. Run repository harness and architecture checks. Run the user-document link
   checker only if user-facing documentation changes in the same branch.
4. Review the final diff for scope: production files should be limited to the
   two defect locations, and tests should assert behavior rather than merely
   suppress warnings or exceptions.

## Review checklist

- [x] Both previously failing tests are ordinary passing tests, not skipped or
  relaxed.
- [x] Recent-list entries and their selected identities preserve order across
  up/down operations.
- [x] Projection `ImageType` components satisfy DICOM CS length and character
  constraints for MIP, AIP, MinIP, and fallback paths.
- [x] Existing projection display/export metadata remains descriptive.
- [x] Focused, nearest, full parallel, coverage, lint, harness, and architecture
  checks have recorded results.

# Legacy DICOM Export Hardening Plan

**Status:** Implemented 2026-09-02; no DICOM-profile, IOD-validity, or legal/privacy claim.

**Priority:** P1

**Created / last updated:** 2026-09-02

**Related:** [De-identification compliance reassessment](DEIDENTIFICATION_COMPLIANCE_REASSESSMENT_PLAN.md); [DICOM output scope baseline](DICOM_OUTPUT_SCOPE_BASELINE.md).

## Goal

Prevent `ExportManager` from silently using its legacy standalone
`DICOMAnonymizer` path, and verify the normal deep DICOM export path after final
serialization. This is a small safety and regression-hardening change, not a
PS3.3 IOD-validation or PS3.15 profile-conformance project.

## Pre-change state

Before this change, the normal export dialogs selected `deep_anonymize=True`,
but `src/gui/export_manager.py` also accepted the older `anonymize=True`
request flag and could invoke `DICOMAnonymizer` directly for folder planning
and DICOM writing. Used on its own, that helper performed only the base
group-0010 transformation.

`DICOMAnonymizer` remains an intentional internal dependency of
`DeepDICOMAnonymizer`; this plan must not remove or weaken that deep-engine
first pass. MPR has already moved to the deep batch path and is out of this
implementation scope except as an existing serialized-output reference.

## Scope and decision

Adopt the fail-closed option:

- Preserve `anonymize` request fields temporarily for compatibility.
- Fail closed when `anonymize=True` is requested without
  `deep_anonymize=True`.
- Never fall back from a requested deep transformation to the standalone base
  helper.
- Do not remove the request fields in this change; a future API cleanup can do
  so only after callers have been deliberately audited.

## Implementation checklist

- [x] Add one centralized guard in `src/gui/export_manager.py` for an attempted
  standalone `anonymize=True` DICOM export. Use a stable, actionable error
  message that directs callers to the deep path.
- [x] Apply the guard before all four existing direct `DICOMAnonymizer` uses in
  `ExportManager`: `get_export_paths_for_selection` folder-path planning,
  `export_selected` folder-tag derivation, and regular plus projection DICOM
  writing in `export_slice`. Remove the standalone transformation branches once
  guarded.
- [x] Add field documentation for `ExportSelectedRequest.anonymize` and
  `ExportSliceRequest.anonymize`, and update relevant parameter documentation,
  to state that the legacy flag fails closed. Do not change
  `src/utils/dicom_anonymizer.py` or its use within
  `DeepDICOMAnonymizer`.
- [x] Add a wholly synthetic, on-disk `ExportManager` deep-export regression in
  `tests/test_export_manager.py`. Exercise `export_selected` through final
  DICOM write/read and assert the intended scoped outcomes: top-level and nested
  patient identifiers are blanked/removed, and output remains readable.
- [x] Add a synthetic regression showing `anonymize=True` with
  `deep_anonymize=False` raises before creating an output file.
- [x] Update the path inventory/R-11 status in the reassessment record and this
  plan with the result. Keep wording limited to metadata behavior and review
  before sharing; do not add PS3.3, PS3.15, or legal compliance claims.

## Result

`ExportManager` now rejects a standalone `anonymize=True` request before path
planning, directory creation, or output writing. Normal DICOM metadata
de-identification continues through the deep batch path. The synthetic
`ExportManager` regression writes and reloads a deep-transformed DICOM file,
including nested patient identifiers, and separately covers all public legacy
request entry points failing closed.

## Verification

- Focused `tests/test_export_manager.py`,
  `tests/gui/test_export_manager_round2.py`, `tests/test_deep_anonymizer.py`,
  and `tests/test_mpr_dicom_export.py` selection passed on 2026-09-02.
- Run the relevant documentation/harness checks and staged privacy hook before
  commit; run the required pre-push checks before push.
- Obtain two independent code reviews using the configured free-model workflow,
  independently validate their findings, and fix applicable issues before the
  commit.

## Completion criteria

The legacy request flag cannot silently produce a standalone base-anonymizer
export; the normal deep `ExportManager` DICOM path has a wholly synthetic final
serialized-output regression; documentation accurately distinguishes this from
formal DICOM or legal compliance assessment.

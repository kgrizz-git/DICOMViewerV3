# Derived projection `ImageType` CS violation

**Status:** Open — regression covered by a strict xfail
**Discovered:** 2026-08-13

## Summary

`create_projection_dataset()` writes the third component of DICOM `(0008,0008) ImageType` as descriptive text such as `MAXIMUM INTENSITY PROJECTION`. DICOM VR `CS` permits at most 16 characters per component. pydicom emits a validation warning when the derived MIP dataset is created.

## Reproduction

Run:

```bash
source .venv/bin/activate
QT_QPA_PLATFORM=offscreen python -m pytest -n 0 \
  tests/gui/test_export_rendering_coverage.py -q
```

`test_projection_dataset_image_type_values_are_dicom_cs_valid` is a strict xfail and records the warning without suppressing it.

## Impact

Projection exports can contain a non-conformant `ImageType` component. Strict DICOM consumers may reject or warn about the generated instance.

## Suggested resolution

Use valid, no-more-than-16-character CS defined terms or short application-defined components for MIP/AIP/MinIP, and retain the full descriptive phrase in `SeriesDescription` or `ImageComments`. Update the xfail to a passing conformance assertion after validating the selected values against the relevant DICOM profile.

# Derived projection `ImageType` CS violation

**Status:** Resolved — 2026-08-15
**Discovered:** 2026-08-13

## Summary

`create_projection_dataset()` previously wrote the third component of DICOM
`(0008,0008) ImageType` as descriptive text such as `MAXIMUM INTENSITY
PROJECTION`. DICOM VR `CS` permits at most 16 characters per component.

## Reproduction

Run:

```bash
source .venv/bin/activate
QT_QPA_PLATFORM=offscreen python -m pytest -n 0 \
  tests/gui/test_export_rendering_coverage.py -q
```

`test_projection_dataset_image_type_values_are_dicom_cs_valid` is now an
ordinary passing regression. Projection values are `MIP`, `AIP`, and `MINIP`;
the fuller description remains in `SeriesDescription` and `ImageComments`.

## Impact

Projection exports now contain conformant `ImageType` components, so strict
DICOM consumers should not receive the former CS-length warning.

## Suggested resolution

Implemented with the short values `MIP`, `AIP`, and `MINIP`, preserving the
full descriptive phrase in `SeriesDescription` or `ImageComments`. The
conformance test is now a passing assertion.

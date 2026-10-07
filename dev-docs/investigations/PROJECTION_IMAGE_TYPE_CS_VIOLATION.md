# Derived projection `ImageType` CS violation

**Status:** Resolved — 2026-08-15
**Discovered:** 2026-08-13

## Summary

`create_projection_dataset()` (now in `src/core/projection_dicom_export.py`) previously wrote the third component of DICOM
`(0008,0008) ImageType` as descriptive text such as `MAXIMUM INTENSITY
PROJECTION`. DICOM VR `CS` permits at most 16 characters per component.

## Reproduction

Run:

```bash
source .venv/bin/activate
QT_QPA_PLATFORM=offscreen python -m pytest -n 0 \
  tests/core/test_projection_dicom_export.py -q
```

`test_metadata_and_no_dicom_cs_warnings` is now an
ordinary passing regression. Projection values are `MIP`, `AIP`, and `MINIP`;
the fuller description remains in `SeriesDescription` and `ImageComments`.

## Impact

Projection exports now contain conformant `ImageType` components, so strict
DICOM consumers should not receive the former CS-length warning.

## Suggested resolution

Implemented with the short values `MIP`, `AIP`, and `MINIP`, preserving the
full descriptive phrase in `SeriesDescription` or `ImageComments`. The
conformance test is now a passing assertion.

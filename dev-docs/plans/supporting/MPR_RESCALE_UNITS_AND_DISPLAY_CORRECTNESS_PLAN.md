# MPR Rescale Units and Display Correctness Plan

## Goal

Fix the MPR export and ROI-stat display path so the viewer does not surface misleading rescale-unit text such as `UNSPECIFIED` or `US`, especially when MPR export generated `RescaleSlope` / `RescaleIntercept` only as an implementation detail of packing float output into `int16`.

## Problem Summary

Current behavior combines two separate concerns:

1. MPR DICOM export always writes `RescaleSlope` / `RescaleIntercept` and also always attempts to write `RescaleType`.
2. For non-CT exports, that path sets `RescaleType = "UNSPECIFIED"`.
3. For CT exports, that path sets `RescaleType = "US"`.
4. Downstream display code treats any non-empty `RescaleType` as a literal unit label for ROI statistics.

That means exported MPR series can show ROI-stat labels such as `4797.39 UNSPECIFIED`, even though `UNSPECIFIED` is a DICOM defined term meaning the units are not specified, not a user-facing measurement unit string. The same mechanism can also surface `US` for CT MPR exports, which is not the typical user-facing CT unit label expected in practice.

## Why This Matters

- It is misleading in the UI: users may interpret `UNSPECIFIED` as a real quantitative unit.
- It blurs metadata provenance: export-generated rescale packing details are being presented as if they were semantically meaningful modality units.
- It makes MPR-derived quantitative overlays look less trustworthy than source-image overlays.

## Current Code Path

### Export side

The MPR DICOM export path writes:

```python
ds.RescaleSlope = rs
ds.RescaleIntercept = ri
try:
    ds.RescaleType = "US" if modality.upper() == "CT" else "UNSPECIFIED"
except Exception:
```

This means the exported series gets an explicit `RescaleType` even when the source series had no meaningful rescale-unit concept to preserve.

### Display side

`get_rescale_parameters()` reads `RescaleType` directly if present and non-empty, and `infer_rescale_type()` currently returns that value unchanged. ROI-stat rendering then appends the resulting string directly:

```python
unit_suffix = f" {rescale_type}" if rescale_type else ""
```

So any populated `RescaleType` becomes visible in the ROI overlay.

## Recommended Direction

Prefer fixing this in both metadata generation and display handling:

1. Export:
   Omit `RescaleType` when the exported MPR has no real modality-specific unit to preserve.
2. Display:
   Treat DICOM defined terms such as `UNSPECIFIED` as display-none for ROI-stat unit labeling.
3. CT handling:
   Review whether exported CT MPR should preserve or infer `HU` when appropriate, instead of writing `US`.

This two-layer approach keeps exported metadata cleaner and also hardens the UI against legacy or third-party files that may still contain display-unhelpful `RescaleType` values.

## Proposed Implementation Steps

1. Audit the MPR DICOM export writer and identify where export-only rescale packing is applied.
2. Change export behavior so `RescaleType` is omitted when unknown rather than forced to `UNSPECIFIED`.
3. Review CT export expectations and decide whether `HU` should be preserved/inferred when the source semantics support it.
4. Update rescale-type inference for display so values like `UNSPECIFIED` do not produce ROI-stat unit suffixes.
5. Verify ROI overlay/statistics behavior for:
   - original CT series with meaningful rescale semantics
   - original non-CT series with no `RescaleType`
   - exported MPR CT series
   - exported MPR non-CT series
6. Add regression tests around both export metadata and ROI-stat display formatting.

## Acceptance Criteria

- Exported non-CT MPR DICOMs do not write misleading `RescaleType` values solely because rescale packing was used.
- ROI statistics do not append `UNSPECIFIED` as a visible unit label.
- CT behavior is explicitly chosen and documented, rather than implicitly showing `US`.
- Tests cover the chosen export and display rules.

## Notes

- `UNSPECIFIED` is a DICOM defined term meaning the units are not specified; it should not be presented as a friendly measurement unit in ROI overlays.
- This issue is related to export correctness and display correctness, so the fix should avoid solving only one side of the pipeline.

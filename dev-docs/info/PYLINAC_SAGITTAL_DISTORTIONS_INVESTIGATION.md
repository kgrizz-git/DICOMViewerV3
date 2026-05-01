# Investigation Report: Pylinac MRI "Sagittal Distortions: {}"

## Issue Description
When running the ACR MRI Large (pylinac) analysis in DICOM Viewer V3, the generated PDF report and internal result summaries show:
`Sagittal Distortions: {}`

The user is questioning why this field is returning empty brackets and whether it should contain more content.

---

## Root Cause Analysis

### 1. Data Availability
In standard ACR MRI phantom protocols, the acquisition consists of several series:
- **Sagittal Localizer** (usually 1 slice)
- **Axial T1/T2** (usually 11 slices each)

The `pylinac` ACR MRI analysis attempts to analyze the sagittal localizer image if it is present in the provided dataset. If found, it calculates geometric distortion metrics for that slice (e.g., phantom length measurements).

### 2. Integration Logic
In the current implementation of `QAAppFacade` (see `src/core/qa_app_facade.py`), the viewer passes the **focused series** to the pylinac runner:
```python
study_uid, series_uid, modality, ordered_paths, datasets = (
    app._resolve_focused_series_ordered_paths()
)
# ...
request = QARequest(
    # ...
    dicom_paths=ordered_paths,
    # ...
)
```
Since the user is typically focused on an axial series (to evaluate the 11 phantom slices for resolution, uniformity, etc.), the **sagittal localizer series is not included** in the paths passed to `pylinac`.

### 3. Pylinac Internal Behavior (v3.43.2)
- **Attribute**: `ACRMRILarge` has a property `has_sagittal_module` which is `True` only if a sagittal slice is detected.
- **Reporting**: The `ACRMRILarge.results()` method (used by `publish_pdf`) explicitly includes the line:
  `f"Sagittal Distortions: {self.sagittal_localization.distances()}"`
- **Empty Result**: If no sagittal slice was found, `self.sagittal_localization.profiles` is empty, and `distances()` returns `{}`.

### 4. Source of the String
The string "Sagittal Distortions: {}" is produced by `pylinac`'s `results()` method, which is called during the PDF generation process (`publish_pdf`) in `acr.py`.

---

## Findings

1.  **Is it a bug?**
    It is not a bug in the analysis logic itself, but rather a limitation of the current integration: the viewer does not "collect" all relevant series (Axial + Sagittal) before running the ACR QA. It only runs on the current view.
2.  **Should there be more content?**
    Yes. If a sagittal slice were provided, this field would contain a dictionary of length measurements (e.g., `{'ROI1': '189.50mm', ...}`).
3.  **Why `{}`?**
    Pylinac defaults to an empty dictionary representation when the sagittal localization module has no analyzed profiles.

---

## Proposed Next Steps

- **Short Term**: Update the UI or documentation to clarify that sagittal distortion analysis requires the sagittal localizer to be in the same dataset.
- **Long Term**: Modify `QAAppFacade.open_acr_mri_phantom_analysis` to automatically identify and include the sagittal localizer series from the same study (using the study index) if available.
- **Dependency Note**: Pylinac 3.44.0+ introduced more robust sagittal distortion reporting; however, the data availability issue (missing slice) remains the primary cause in our integration.

---

## References
- `src/qa/pylinac_runner.py` (Integration layer)
- `venv/Lib/site-packages/pylinac/acr.py:L2182` (Source of string in `results()`)
- `dev-docs/TO_DO.md:L35` (Issue tracker)

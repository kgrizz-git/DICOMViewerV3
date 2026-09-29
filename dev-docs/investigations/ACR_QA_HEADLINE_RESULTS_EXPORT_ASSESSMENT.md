# ACR QA headline results export assessment

**Last updated:** 2026-09-28
**Status:** Investigation; implementation plan to follow

## Purpose and user story

A medical physicist should be able to open an ACR phantom QA export, find the principal measured results immediately, and copy them into a physics QC report. The export should also expose the inputs behind calculated values and retain the full audit detail. A pylinac proxy must be labeled by its actual method rather than presented as a different ACR manual measurement.

This assessment covers ACR CT and ACR MRI Large analyses, the XLSX `Summary`/`Detail` split, and single-run and batch CSVs. It compares the repository with the installed **pylinac 3.43.2** source at `.venv/lib/python3.12/site-packages/pylinac/acr.py`. No phantom analysis or DICOM data were used. The [existing ACR phantom QA reference assessment](../info/ACR_PHANTOM_QA_METRICS_AND_PYLINAC_GAPS.md) distinguishes MRI accreditation phantom tests from broader routine QC. Verify current manual editions and site criteria before implementing any pass/fail rule.

## Current state

| Surface | Present structure | Source |
|---|---|---|
| Backlog | Headline values first, then CNR inputs, then supporting details, with no data dropped. Also names nuclear/flat CSVs as later scope. | `dev-docs/TO_DO.md:275` |
| XLSX `Summary` | `Series/Run ID`, CT object mean, background mean, background standard deviation, CNR, status, warnings, PIU, PSG, low-contrast score, MRI row/column MTF@50%, MRI slice thickness/shift, MRI SNR. The CNR inputs appear **before** status and headline results. | `src/qa/qa_xlsx_export.py:42-75,131-151` |
| XLSX `Detail` | Full two-column dotted-key flatten, one block per run. Images have a separate sheet. | `src/qa/qa_xlsx_export.py:154-176,309-328` |
| Single-run CSV | `metric,value` rows from the full flatten, alphabetically sorted by key. It has no leading status/warnings rows. | `src/qa/qa_export.py:192-212`; `src/qa/qa_result_flatten.py:91-124` |
| Batch CSV | One wide row per run. Provenance keys lead; all remaining metric keys form an alphabetically sorted union. | `src/qa/qa_export.py:215-270`; `src/qa/qa_result_flatten.py:147-185` |
| Stored result | `QAResult` holds curated `metrics`, opaque `raw_pylinac`, warnings/errors, series identity, and `pylinac_analysis_profile`. | `src/qa/analysis_types.py:518-546` |

Flattening walks `raw_pylinac` into dotted keys, then overlays curated metrics; path-bearing fields and duplicate audit-message keys are excluded (`src/qa/qa_result_flatten.py:47-124`). Both ACR runners obtain `results_data(as_dict=True)`. CT separately harvests live CNR inputs absent from that structured result (`src/qa/pylinac_acr_ct.py:64-112,270-321`). MRI curates low-contrast score and overlays viewer-computed SNR (`src/qa/pylinac_acr_mri.py:320-376`; `src/qa/pylinac_mri_snr.py:154-186`). The analysis profile records engine and choices but does not supply a Summary headline (`src/qa/analysis_types.py:534`).

Current tests assert the XLSX modality-aware header and mixed-run blanks (`tests/qa/test_qa_xlsx_summary_columns.py:90-106,206-227`), and CSV full flatten, provenance-first ordering, sorted overflow, and warning preservation (`tests/qa/test_qa_export_csv.py:96-106,145-183,256-279`). These order assertions will need intentional updates. The release history records CT CNR harvest (`CHANGELOG.md:433`), full-flatten CSVs (`CHANGELOG.md:188`), XLSX modality-aware fields (`CHANGELOG.md:68`), MRI batch export (`CHANGELOG.md:49`), and viewer SNR harvest (`CHANGELOG.md:48`).

## Vanilla pylinac 3.43.2 published results

The source citations in this section are line numbers in the installed `.venv/lib/python3.12/site-packages/pylinac/acr.py`. “PDF text” means quantitative text passed to `publish_pdf()`, not every value present in `results_data()`. Module images provide additional visual context.

### `ACRCT`

| Measurement | `results_data()` and live analyzer | `results()` / PDF text | Installed-source lines |
|---|---|---|---|
| HU accuracy | `ct_module.rois`: mean HU for Air, Poly, Acrylic, Bone, Water | Both print the HU ROI values. | `51-83,536-562,662-668` |
| HU uniformity | `uniformity_module.rois`: Center, Top, Right, Bottom, Left mean HU | Both print the ROI values. | `87-113,540-543,564-572,662-668` |
| Uniformity image noise | `uniformity_module.center_roi_stdev` | `results()` prints it; the PDF's quantitative text block does **not**. | `107-115,543,572,662-668` |
| Low contrast | `low_contrast_module.cnr`; object ROI value in `rois`. The live `cnr()` divides absolute object/background difference by background standard deviation. `results_data()` does not include the background mean/standard deviation. | `results()` says CNR; PDF says “Low contrast visibility” for the same CNR value. | `218-253,541,585-595,662-668` |
| Spatial resolution | `spatial_resolution_module.lpmm_to_rmtf` maps 0.4–1.2 lp/mm to relative MTF; live `mtf.relative_resolution(50)` produces interpolated MTF@50% in lp/mm. | `results()` prints MTF@50%; the PDF's quantitative text block does **not**. | `128-215,544,574-584,662-668` |
| Setup and provenance | Phantom model/roll, origin slice, image count, module offsets, ROI radius/distance/settings, and spatial-resolution ROI values. | Not primary PDF results. | `256-284,548-596` |

The `ACRCTResult` model has calibration, uniformity, low-contrast, and spatial-resolution modules only (`acr.py:256-284`). It publishes no measured CT slice thickness, geometric distance, CT SNR, or observer line-pair visibility score. Its `publish_pdf()` text is shorter than `results_data()` and `results()` (`acr.py:633-668`); “PDF parity” therefore must not mean blindly copying only PDF text.

### `ACRMRILarge`

The MRI PDF prints `results(as_str=False)` (`acr.py:2114-2164`), so the following `results()` text values are also PDF text.

| Measurement | `results_data()` and live analyzer | `results()` / PDF text | Installed-source lines |
|---|---|---|---|
| Geometric accuracy | Axial `geometric_distortion_module.profiles[*]["width (mm)"]` and sagittal `sagittal_localizer_module.profiles[*]["width (mm)"]`; `distances` are formatted strings. Profiles also contain plot lines. | Prints axial and sagittal distance dictionaries. | `1394-1496,1499-1515,1567-1609,2173,2182,2234-2238,2250-2253` |
| Slice thickness | `slice1.measured_slice_thickness_mm`, calculated from two thickness ROIs. | Prints measured thickness. | `868-873,914-916,2174,2220-2221` |
| Slice position | `slice1.slice_shift_mm`, `slice11.slice_shift_mm`; both also expose `bar_difference_mm`. | Prints both slice shifts. | `721-771,906-913,2175-2176,2219-2231` |
| Image intensity uniformity | `uniformity_module.piu`, `piu_passed`, center ROI values. PIU uses 99th/1st percentiles of the Center ROI's pixels; pylinac's `piu_passed` thresholds are `>85` below 3 T and `>80` at 3 T. | Prints PIU and Center ROI standard deviation. | `941-997,1021-1049,2177-2179,2239-2249` |
| Ghosting | `uniformity_module.psg` in percent, `ghosting_ratio`, and four ghost ROI values. | Prints PSG. | `949-954,999-1013,1033-1041,2178,2243-2246` |
| High-contrast resolution | Slice 1 row/column `mtf_50` (lp/mm), row/column 10–90% relative-resolution-to-lp/mm maps, and ROI values. | Prints row and column MTF@50%. These are automated proxies, not an observer's smallest visible hole pair. | `782-798,875-931,2180-2181,2190-2199,2222-2225` |
| Low-contrast detectability | `low_contrast_multi_slice_module.score`, the sum across analyzed slices, plus per-slice spoke results. | Prints total score. | `1052-1055,1170-1180,1382-1391,2183,2200-2208,2254-2257` |
| Setup and provenance | Phantom model/roll, origin slice, image count, ROI and ghost settings, profile coordinates, per-spoke data. | Not the primary result text. | `1614-1645,2210-2257` |

No `ACRMRISNR` class or native MRI SNR result was found in the installed `pylinac/acr.py` or its package exports. The viewer's `mri_snr` is an **uncorrected** Center-ROI signal-mean/background-noise ratio, with signal/noise components and ROI-pair provenance curated separately (`src/qa/pylinac_mri_snr.py:154-186`; `CHANGELOG.md:48`). It must not be labeled as vanilla pylinac or NEMA-corrected SNR.

## ACR manual physics-test quantities and mapping

The MRI phantom-guidance tests and the broader routine QC distinction are documented in [ACR phantom QA metrics and pylinac gaps](../info/ACR_PHANTOM_QA_METRICS_AND_PYLINAC_GAPS.md). The [additional-analysis catalog](../info/AUTOMATED_QA_ADDITIONAL_ANALYSIS.md) cites the ACR CT phantom overview and its CT number, low-contrast, high-contrast, uniformity, and noise capabilities. “Headline” below means present on today's XLSX `Summary`; “Detail” means retained in XLSX `Detail`/full CSV but not prioritized. No current CSV provides a deliberate clinical headline block.

| Modality | Manual or QC report quantity | Verified pylinac/viewer source | Current presence and gap |
|---|---|---|---|
| CT | Water and insert CT number accuracy | `ct_module.rois.Water/Air/Poly/Acrylic/Bone` | **Detail.** A principal CT QC result is absent from Summary. |
| CT | Center and four peripheral CT numbers for uniformity | `uniformity_module.rois.Center/Top/Right/Bottom/Left` | **Detail.** Promote the measured HU values; a derived max center-to-periphery difference needs its own defined calculation. |
| CT | Uniformity-image noise | `uniformity_module.center_roi_stdev` | **Detail.** Present in pylinac `results()` but absent from Summary. |
| CT | Low-contrast detectability/CNR | `low_contrast_module.cnr`; curated `low_contrast_cnr.cnr` | **Headline** as `CNR`, but after its inputs. State the method in the label. |
| CT | CNR calculation inputs | Curated `low_contrast_cnr.object_rois[*].mean`, `.background.mean`, `.background.std` | **Headline**, currently before CNR. Keep the aggregate inputs immediately after CNR; individual ROI records stay Detail. |
| CT | High-contrast spatial resolution | `spatial_resolution_module.lpmm_to_rmtf`; live `spatial_resolution_module.mtf.relative_resolution(50)` | rMTF grid **Detail**; scalar MTF@50% **missing** from structured export and requires live harvest. Neither is a visual line-pair read. |
| CT | Measured slice thickness | No `ACRCT` thickness module; future viewer-side Module 1 wire-ramp measurement is feasible | **Missing from vanilla pylinac and this viewer today.** DICOM `SliceThickness` is the scanner-reported reference value to compare with an independent measurement, never the measurement itself. See [wire-ramp investigation](#future-work-ct-module-1-wire-ramp-thickness-measurement). |
| CT | Geometric/positioning accuracy | No `ACRCT` geometric-distance result | **Missing.** Do not relabel another phantom module's geometry result as ACR CT geometry. |
| MRI | Geometric lengths | Axial and sagittal profile `width (mm)` values | **Detail.** PDF-prominent results absent from Summary. |
| MRI | High-contrast spatial resolution | `slice1.row_mtf_50`, `slice1.col_mtf_50` | **Headline** automated proxies; visual smallest resolved hole pair **missing**. |
| MRI | Measured slice thickness | `slice1.measured_slice_thickness_mm` | **Headline.** |
| MRI | Slice position accuracy | `slice1.slice_shift_mm`, `slice11.slice_shift_mm` | Slice 1 **headline**; slice 11 **detail**. Present them together. |
| MRI | Percent integral uniformity | `uniformity_module.piu` | **Headline**, but pylinac's percentile method differs from the ACR small high/low-region procedure. |
| MRI | Percent signal ghosting | `uniformity_module.psg` | **Headline**; add `%` to label. Ratio and four ROI values are Detail. |
| MRI | Low-contrast complete-spoke score | `low_contrast_multi_slice_module.score`; curated `low_contrast_score` | **Headline.** Check curated/nested agreement on successful runs. |
| MRI | Routine QC SNR | Viewer-curated `mri_snr`, `mri_snr_signal_mean`, `mri_snr_noise_mean` | SNR **headline**; inputs **detail**. Label as viewer-computed, uncorrected SNR. |
| MRI | ACR-procedure PIU and observer hole-pair score | No equivalent vanilla scalar | **Missing.** Keep their names distinct from pylinac PIU/MTF. |

The MRI phantom guidance names seven quantitative accreditation tests: geometric accuracy, high-contrast resolution, slice thickness, slice position, PIU, percent signal ghosting, and low-contrast detectability (`dev-docs/info/ACR_PHANTOM_QA_METRICS_AND_PYLINAC_GAPS.md:27-37`). SNR belongs to broader routine QC rather than those seven (`:45-74`). Pylinac's `piu_passed` cutoffs must not be treated as ACR submission limits (`acr.py:984-997`). Overall `QAResult.success` means analysis completed, **not** that the QC measurements passed a physicist's acceptance criteria.

## Recommended headline columns and ordering

Use one deterministic schema for a mixed-modality batch, leaving inapplicable cells blank. A single-modality export may omit wholly empty opposite-modality columns. Preserve a stable machine key alongside each human label, include units, and leave missing/failed measurements blank rather than writing zero.

### CT block

1. `Series/Run ID`, `Analysis type`, `Status`, `Warnings`, and `Errors` where applicable.
2. **CT low-contrast CNR** — `low_contrast_cnr.cnr`; only use `low_contrast_module.cnr` as a checked fallback.
3. **CT MTF@50% (lp/mm)** — new curated live harvest of `spatial_resolution_module.mtf.relative_resolution(50)`. Until harvested, leave blank; do not silently infer it from a rounded rMTF table.
4. **Water, Air, Poly, Acrylic, Bone (HU)** — `ct_module.rois.*`.
5. **Uniformity Center, Top, Right, Bottom, Left (HU)** — `uniformity_module.rois.*`.
6. **Uniformity center ROI standard deviation (HU)** — `uniformity_module.center_roi_stdev`.
7. **CNR object mean, background mean, background standard deviation** — curated `low_contrast_cnr` aggregates.
8. Audit fields: pylinac version, image count, study/series UID, and a concise analysis-profile identifier. The full profile remains in JSON/Detail.

There should be no CT measured-thickness or CT SNR headline cell that could imply a completed measurement. If the separately tracked DICOM tag harvest ships first, label it **Reported SliceThickness (DICOM, mm)** and place it with acquisition/reference data, never under **Measured slice thickness**. A later wire-ramp result should have distinct **Measured top ramp (mm)** and **Measured bottom ramp (mm)** fields, with the reported thickness alongside for comparison.

### MRI block

1. `Series/Run ID`, `Analysis type`, `Status`, `Warnings`, and `Errors` where applicable.
2. **Pylinac percentile PIU (%)** — `uniformity_module.piu`.
3. **Percent signal ghosting (%)** — `uniformity_module.psg`.
4. **Low-contrast complete-spoke score** — `low_contrast_score`, checked against `low_contrast_multi_slice_module.score`.
5. **Row and column MTF@50% (lp/mm)** — `slice1.row_mtf_50`, `slice1.col_mtf_50`, labeled as automated proxies.
6. **Measured slice thickness (mm)** — `slice1.measured_slice_thickness_mm`.
7. **Slice 1 and Slice 11 shifts (mm)** — `slice1.slice_shift_mm`, `slice11.slice_shift_mm`.
8. **Axial and sagittal geometric lengths (mm)** — stable, explicit columns sourced from each supported profile's numeric `width (mm)`. Confirm exact names and sagittal availability on representative results. Do not put the formatted `distances` strings in numeric cells.
9. **Viewer SNR, uncorrected** — `mri_snr`, then **SNR signal mean** and **SNR background noise** — `mri_snr_signal_mean`, `mri_snr_noise_mean`.
10. Audit fields as for CT, including resolved echo and relevant method choices when available.

### Format-specific presentation

For **batch CSV**, put identifier/status/warnings first, then the appropriate headline block, then calculation inputs, audit fields, and remaining flattened keys in stable order. A mixed CT/MRI batch keeps one header and blank inapplicable cells. For the **single-run `metric,value` CSV**, retain two columns, place the same ordered headlines first, then a clear Detail section containing all remaining flattened keys. For **XLSX `Summary`**, mirror the batch ordering and retain numeric cell types. Preserve the full flatten in `Detail` and the existing `Images` sheet. Repetition between Summary and Detail is acceptable; demotion means reducing visual prominence, not deleting values.

## Detail-only material

Keep module offsets, ROI size/area/radius, ROI placement settings, individual low-contrast disks and spokes, per-ROI dictionaries, full rMTF grids, ghost ROI values, phantom roll, profile endpoints and plot coordinates, and diagnostic analysis settings in XLSX Detail and trailing CSV detail rows. CNR's object-ROI records and background `means`/`stds` arrays remain there; only named aggregate inputs follow the CNR headline. This retains the backlog's no-data-loss requirement (`dev-docs/TO_DO.md:275`).

## Not computable as a headline measurement today

- **CT measured slice thickness in the current implementation:** no `ACRCT` ramp/FWHM thickness module (`acr.py:256-284`) and no viewer measurement yet. DICOM `SliceThickness` is the scanner-reported image thickness and **does not measure it**. Its harvest is separately tracked in `dev-docs/TO_DO.md:274`. A viewer-side wire-ramp method is a plausible future addition, described below.
- **CT geometric distance:** none in `ACRCTResult`. A CatPhan geometry measurement is not an ACR CT measurement by substitution.
- **CT SNR:** no native `ACRCT` field; center ROI noise alone does not create an SNR measurement.
- **Observer CT line-pair and MRI hole-pair resolution:** pylinac supplies rMTF/MTF proxies, not a manual visibility score (`acr.py:190-215,918-931`).
- **ACR-procedure MRI PIU:** pylinac's percentile calculation is not the small high/low-region procedure (`acr.py:984-989`).
- **Vanilla MRI SNR:** absent from `ACRMRILarge`; the viewer's value is uncorrected and method-specific (`src/qa/pylinac_mri_snr.py:154-186`).
- **MRI SNR uniformity or two-image difference SNR:** neither follows from one run's `mri_snr`; both require separate acquisition and method design ([reference assessment](../info/ACR_PHANTOM_QA_METRICS_AND_PYLINAC_GAPS.md#snr-and-snr-uniformity--not-accreditation-tests)).

## Future work: CT Module 1 wire-ramp thickness measurement

**Keep reported and measured values separate.** DICOM `(0018,0050) SliceThickness` is [nominal reconstructed slice thickness](https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_c.34.12.html). Reading that tag cannot establish actual thickness; the independent phantom result is what could be compared with it and with the site's recorded protocol. DICOM `SpacingBetweenSlices` or distance between image positions describes [slice-center spacing](https://dicom.nema.org/medical/dicom/2023a/output/chtml/part03/sect_C.7.6.2.html), not slice thickness. The [ACR phantom overview](https://accreditationsupport.acr.org/support/solutions/articles/11000053945-overview-of-the-ct-phantom) locates two wire ramps in Module 1, alongside the material inserts, and says adjacent wires represent 0.5 mm in the z direction. The [current ACR CT phantom scanning instructions](https://accreditationsupport.acr.org/support/solutions/articles/11000056197-acr-ct-phantom-scanning-instructions) use the Module 1 landmark/BB image and describe centered, symmetric wires for alignment. These support using the analyzed Module 1 origin image as the starting image, subject to confirming that the ramps are well centered and visible on the selected reconstruction.

The **historical** ACR CT accreditation phantom instructions describe viewing the Module 1 image at WW 400/WL 0, counting wires at least half as bright as the central wires **separately on the top and bottom ramps**, and dividing each count by two to obtain millimeters (0.5 mm per visible wire). A [peer-reviewed AAPM-hosted description of the ACR program](https://www.aapm.org/meetings/05AM/pdf/18-4146-57655-316.pdf) independently describes the discrete 0.5 mm ramp spacing, counts well-visualized wires, and notes about 0.5 mm observer variability. The exact 50% visual rule was verified in an [archived copy of the ACR instruction](https://manualzz.com/doc/27570347/acr-ct-accreditation-phantom-instruction-manual); it is a historical procedure, **not** a claim that the current CT QC manual mandates it. [ACR's current manual summary](https://accreditationsupport.acr.org/support/solutions/articles/11000069437-the-2017-ct-qc-manual) says image-thickness testing was removed as a required test for modern multidetector CT, while noting possible value on remaining single-slice systems. The [current ACR phantom scoring page](https://accreditationsupport.acr.org/support/solutions/articles/11000054129-acr-ct-phantom-scoring) still discusses submitted image thickness relative to the phantom data form. The implementation plan must establish which procedure and reporting context the site actually wants.

**Candidate algorithm for a future, physicist-reviewed spike:**

1. Reuse the CT runner's Module 1 origin selection (the material-insert slice), but verify BB alignment, ramp centering, and adequate coverage; let a physicist correct the slice and ramp regions when detection is uncertain. Do not assume every origin candidate has a usable thickness image.
2. Register the phantom center and orientation, locate top and bottom wire-ramp regions independently, and sample the original rescaled CT values rather than thresholding a saved screenshot. Use the historical WW 400/WL 0 view for manual comparison, while specifying precisely how pixel values are converted to a reproducible brightness or contrast score.
3. Estimate a local water-equivalent background for each ramp, detect distinct wire peaks at the expected spacing, and measure each peak above its local background. Set the candidate visibility threshold at 50% of a robust central-wire reference **per ramp**; validate how this numerical rule matches the historical *visual* half-brightness judgment. Avoid using raw HU divided by central-wire HU without background subtraction.
4. Count qualifying wires on each ramp separately and calculate `top_count × 0.5 mm` and `bottom_count × 0.5 mm`. Retain both counts, both measurements, the reference brightness/contrast, threshold, rejected peaks, selected image identity, and an annotated ramp image. Do not silently average discrepant top/bottom results.
5. Compare each measured width with the **reported** DICOM thickness and the site-recorded protocol value only after the measurement succeeds. Flag absent or inconsistent DICOM tags separately. Validate the method across thin/thick reconstructions, noise, iterative reconstruction, off-center ramps, partial-volume ends, artifacts from inserts/BBs, and ramps whose count extends beyond the available wires. Compare blinded manual counts from physicists before clinical use.

This is an engineering proposal, not a validated implementation or a current `ACRCT` capability. The 50% rule, background handling, tolerance, and whether a particular series is suitable need agreement from the physicist and the applicable site procedure before any automated pass/fail claim.

## Open questions and risks

1. Which current ACR manual edition and site QC report template govern labels, reference limits, and any eventual pass/fail fields? Do not conflate analysis success with clinical acceptance.
2. Which geometric profile keys and sagittal fields are reliably available for the site's MRI series? Confirm numeric names and ordering with representative de-identified results.
3. Does a newly harvested CT MTF@50% scalar agree with pylinac `results()` on representative scans? It should be harvested from the live analyzer rather than reconstructed from rounded export values.
4. How should downstream CSV consumers handle reordered columns and the new single-run section? Preserve existing keys and the complete trailing flatten, and document the ordering change.
5. Failed or partial `results_data()` extraction can leave `raw_pylinac` empty. Blank headline cells need retained warnings/errors so they cannot be mistaken for measured zeros.
6. The backlog also requests nuclear/flat CSV ordering. Their own metric inventory is needed before applying this presentation pattern to those exports.
7. Should the future CT wire-ramp measurement be offered for routine QC, accreditation preparation, or both? Confirm the site's procedure, reference value, and review workflow in light of the current manual's removal of image thickness as a generally required QC test.

## Next steps

Write a separate implementation plan that fixes the exact labels, units, mixed-batch schema, geometric profile names, and compatibility behavior. Add CT MTF@50% live harvest, then share a headline-order definition across XLSX Summary and both CSV forms while retaining the full Detail flatten. Update the existing order tests and add focused coverage for CT HU/noise, both MRI shifts, geometric lengths, missing values, warnings, and detail retention. Compare completed de-identified CT and MRI exports with vanilla pylinac report text and the site's QC template before adding acceptance rules.

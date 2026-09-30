# ACR QA headline results export implementation plan

**Last updated:** 2026-09-29
**Status:** Implemented; archived with the export implementation
**Scope:** ACR CT/MRI single-run CSV, batch CSV, and XLSX `Summary`; retained `Detail`/Images; subsequent nuclear CSV ordering
**Basis:** [ACR QA headline results export assessment](../../investigations/ACR_QA_HEADLINE_RESULTS_EXPORT_ASSESSMENT.md)

## Outcome and boundaries

A physicist can open a CSV or XLSX export and copy the principal ACR phantom QC measurements directly into a report. The first columns or rows identify the run and analysis status, then show measured or computed headline values, then their calculation inputs. Supporting measurements and placement/plot detail remain available without crowding the first view. Numbers retain units and method labels; a completed analysis is not presented as a clinical pass.

This plan changes **presentation and one missing pylinac result harvest**. It does not implement ACR pass/fail limits, CT wire-ramp thickness analysis, CT geometry, observer line-pair/hole-pair scoring, or ACR-procedure MRI PIU. Those require separate method design and physicist validation. In particular, DICOM `(0018,0050) SliceThickness` is a nominal, scanner-reported reference; it **cannot** populate a “measured CT slice thickness” cell. The separately tracked CT thickness work may later place a measured top- and bottom-ramp result beside this reported value, never substitute the tag for the measurement.

The [ACR CT phantom instructions](https://accreditationsupport.acr.org/support/solutions/articles/11000056197-acr-ct-phantom-scanning-instructions) name CT number, CNR, uniformity, and artifact checks for submitted images; the [2017 CT QC manual summary](https://accreditationsupport.acr.org/support/solutions/articles/11000069437-the-2017-ct-qc-manual) explains why image-thickness testing is no longer a generally required MDCT QC test. The [ACR MRI QC manual](https://www.acr.org/-/media/ACR/Files/Clinical-Resources/QC-Manuals/MR_QCManual.pdf) lists seven quantitative accreditation phantom tests and discusses SNR in the broader QC program. Pylinac's percentile PIU and MTF values are labeled as algorithm-specific proxies. No numeric accreditation limits are encoded in this export project.

## Existing contracts to preserve

- `QAResult` and JSON retain raw `results_data(as_dict=True)`, curated `metrics`, warnings/errors, identity, and analysis profile (`src/qa/analysis_types.py`; `src/qa/qa_export.py`). CT's new curated MTF field is additive to JSON; no raw pylinac keys are rewritten. The additive CT `acr_ct_mtf50_lpmm` metric keeps JSON `schema_version` 1.3: existing fields and meanings are unchanged, and consumers already permit extra metric keys.
- `build_metric_rows` remains the canonical full, sorted flatten, with curated values winning collisions and path/audit denylisted keys excluded (`src/qa/qa_result_flatten.py`). XLSX `Detail` continues to emit every allowed flattened key once per run; `Images` retains its current embedding/fallback behavior.
- Single-run CSV retains the two-column `metric,value` shape. Batch CSV retains one header and one data row per run. Excel and CSV formula neutralization (`neutralize_spreadsheet_value`/`SafeCsvWriter`) applies to **every** new label, warning, and string cell. Existing GUI callers should consume the shared builders without format-specific reordering (`src/gui/qa_app_facade.py`, `src/gui/qa_ct_batch_export.py`, `src/gui/qa_mri_batch_export.py`).
- Missing, inapplicable, failed, and nonfinite measurements produce blank measurement cells, never zero or `nan`/`inf`. Identity and audit fields retain their declared types and values, including status and merged preflight/pylinac warnings and errors from `build_run_provenance`. `success` means analysis completed; it is not an ACR acceptance result.

## Canonical ACR headline projection

Add a Qt-free module such as `src/qa/qa_headline_results.py` with an ordered immutable column specification: stable CSV key, human XLSX label, modality, units/method, and an extractor from `QAResult`/the canonical flatten. One projection per run includes the required identity, measurement, and audit fields. Only measurement columns are constrained to finite numeric scalars or blanks; identity and audit columns retain their declared types, including strings, status, warnings, and errors. Use exact-key lookups and type checks; do not parse formatted `distances` strings or crawl arbitrary nested dictionaries. Define the modality by `analysis_type` (`acr_ct` versus `acr_mri_large`), not by `modality` alone. Reuse provenance keys intentionally only for `analysis_type`, `warnings`, and `errors`; reuse the new curated CT MTF key intentionally; ensure all other projection keys are distinct from existing flatten/provenance keys. Preserve raw flatten values even when a headline is a renamed projection.

The following ordered blocks are the **contract to implement**. CSV uses the stable keys below; XLSX uses the corresponding readable labels. The same order governs the first portion of single-run CSV, batch CSV, and XLSX `Summary`. Keep XLSX measurement cells numeric. Source paths below refer to keys yielded by `build_metric_rows`; `metrics[...]` means a new or existing curated runner field.

### Identity and audit block (all runs)

| Order | Stable CSV key | XLSX label | Source / rule |
|---|---|---|---|
| 1 | `series_run_id` | Series/Run ID | Explicit batch label, else `series_uid`; keep existing `label` provenance key separately and formula protection. |
| 2 | `analysis_type` | Analysis type | `QAResult.analysis_type`. |
| 3 | `analysis_status` | Analysis status | Render `success`/`failed` for people; keep existing batch `success` boolean in the later audit block. |
| 4 | `warnings` | Warnings | Merged provenance warnings, joined with `; ` in tabular cells. |
| 5 | `errors` | Errors | Merged provenance errors, joined with `; `. |

For the single-run CSV, `series_run_id` is `series_uid` when no user label exists. Use the same status and warning/error projection as batch/XLSX; do not pull the unmerged raw `warnings` key. Keep `study_uid`, `series_uid`, `modality`, `pylinac_version`, and `num_images` in the later audit block. The batch `success` boolean remains unchanged for existing consumers.

### CT measurement block

| Order | Stable CSV key | XLSX label | Exact source and handling |
|---|---|---|---|
| 1 | `acr_ct_cnr` | CT low-contrast CNR (pylinac) | `low_contrast_cnr.cnr`; a missing curated value may fall back to `low_contrast_module.cnr` only when finite. The **runner**, not an export builder, cross-checks both sources and records a mismatch warning in `QAResult.warnings`. |
| 2 | `acr_ct_mtf50_lpmm` | CT MTF@50% (lp/mm, pylinac) | New curated live result `metrics["acr_ct_mtf50_lpmm"]` from `analyzer.spatial_resolution_module.mtf.relative_resolution(50)`. No estimate from rounded `lpmm_to_rmtf`. |
| 3–7 | `acr_ct_hu_water`, `_air`, `_poly`, `_acrylic`, `_bone` | CT number: Water, Air, Poly, Acrylic, Bone (HU) | `ct_module.rois.Water/Air/Poly/Acrylic/Bone`; leave absent ROIs blank. |
| 8–12 | `acr_ct_uniformity_hu_center`, `_top`, `_right`, `_bottom`, `_left` | Uniformity: Center, Top, Right, Bottom, Left (HU) | `uniformity_module.rois.Center/Top/Right/Bottom/Left`; distinct from a future derived max deviation. |
| 13 | `acr_ct_uniformity_center_std_hu` | Uniformity center ROI SD (HU) | `uniformity_module.center_roi_stdev`; image-noise context, not an ACR pass/fail verdict. |

CT calculation-input rows/columns immediately after the CT measurement block:

| Order | Stable CSV key | XLSX label | Exact source and handling |
|---|---|---|---|
| 14 | `acr_ct_cnr_object_mean_hu` | CNR object ROI mean (HU) | Existing `extract_low_contrast_cnr_values` aggregate over `low_contrast_cnr.object_rois[*].mean`. |
| 15 | `acr_ct_cnr_background_mean_hu` | CNR background mean (HU) | `low_contrast_cnr.background.mean`. |
| 16 | `acr_ct_cnr_background_std_hu` | CNR background SD (HU) | `low_contrast_cnr.background.std`. |

Do not produce a CT SNR or measured-thickness headline in this phase. Do not label `acr_ct_mtf50_lpmm` as ACR's visual highest resolved line-pair score. The DICOM reported thickness fields belong to the separate CT metadata backlog item; if available by implementation time, place **Reported SliceThickness (DICOM, mm)** and **Reported SpacingBetweenSlices (DICOM, mm)** in the audit/reference block with distinct keys, never in the CT measurement block.

### MRI measurement block

| Order | Stable CSV key | XLSX label | Exact source and handling |
|---|---|---|---|
| 1 | `acr_mri_pylinac_percentile_piu_pct` | MRI PIU (%; pylinac percentile method) | `uniformity_module.piu`; **not** an ACR small-ROI PIU. |
| 2 | `acr_mri_psg_pct` | MRI percent signal ghosting (%) | `uniformity_module.psg`; do not substitute `ghosting_ratio` without ×100. |
| 3 | `acr_mri_low_contrast_spokes` | MRI low-contrast complete-spoke score (pylinac) | `low_contrast_score`, checked against `low_contrast_multi_slice_module.score` by the runner; if curated value absent, finite structured fallback. |
| 4–5 | `acr_mri_row_mtf50_lpmm`, `acr_mri_col_mtf50_lpmm` | MRI row/column MTF@50% (lp/mm; pylinac proxy) | `slice1.row_mtf_50`, `slice1.col_mtf_50`; not observer hole-pair resolution. |
| 6 | `acr_mri_measured_slice_thickness_mm` | MRI measured slice thickness (mm) | `slice1.measured_slice_thickness_mm` from pylinac's image analysis. |
| 7–8 | `acr_mri_slice1_shift_mm`, `acr_mri_slice11_shift_mm` | MRI slice 1/11 position shift (mm) | `slice1.slice_shift_mm`, `slice11.slice_shift_mm`; preserve sign. |
| 9–12 | `acr_mri_axial_horizontal_mm`, `_vertical_mm`, `_negative_diagonal_mm`, `_positive_diagonal_mm` | MRI axial horizontal, vertical, negative diagonal, positive diagonal (mm) | `geometric_distortion_module.profiles[horizontal/vertical/negative diagonal/positive diagonal]["width (mm)"]`. |
| 13–16 | `acr_mri_sagittal_roi1_mm` … `_roi4_mm` | MRI sagittal ROI1–ROI4 length (mm) | `sagittal_localizer_module.profiles[ROI1..ROI4]["width (mm)"]`; do not parse `distances` text. |
| 17 | `acr_mri_viewer_snr_uncorrected` | Viewer MRI SNR (uncorrected) | Curated `mri_snr`; distinct from vanilla pylinac or NEMA-corrected SNR. |

MRI calculation-input rows/columns then show `mri_snr_signal_mean` and `mri_snr_noise_mean` under keys `acr_mri_snr_signal_mean` and `acr_mri_snr_background_noise`, labeled with the actual stored-value units/method once confirmed. Keep `uniformity_module.rois.Center.stdev` in Detail (serialized key; the live ROI attribute is `.std`): pylinac prints it, but it is neither the ACR PIU result nor the viewer SNR denominator. This classification is deliberate; if the site's QC template requires it, promote it with an explicit label in a later reviewed schema update.

### Audit/reference and detail order

After applicable measurement/input blocks: existing `success` and `label` provenance keys, then `pylinac_version`, `num_images`, `study_uid`, `series_uid`, `modality`, and a concise profile summary (engine/vanilla setting, resolved MRI echo and low-contrast method where present). Build the profile summary only from known profile keys; do not export a Python `dict` repr into a headline cell. The full profile stays in JSON/Detail. Preserve acquisition/reference metadata as labeled audit fields.

In mixed CT/MRI batch CSV or XLSX, use **identity → CT block → MRI block → common audit block**; cells for the other modality are blank. A single-modality export may omit the other modality's entire block, but ordering within a block is fixed. Keep a stable schema for the same set of analysis types, even when individual runs lack measurements. When there are no runs, batch CSV emits the identity/audit header only, retaining the current header-only behavior.

For the wide batch CSV, append every remaining key from the existing `build_tabular_run` union, sorted by key, after the audit block. Preserve pre-existing provenance keys, including `success`, without duplicate column names. Headline projection keys are additional readable shortcuts; original dotted keys still appear in the trailing detail, so no source data disappears. For an empty batch, emit exactly `series_run_id,analysis_type,analysis_status,warnings,errors,success,label,pylinac_version,num_images,study_uid,series_uid,modality` and no measurement columns. For single-run `metric,value` CSV, write the ordered identity/headline/input/audit key-value rows first, then an explicit two-cell blank separator row and the existing `build_metric_rows` rows sorted as today, **except** a key already emitted identically in the headline/audit block appears only once. This affects the new curated `acr_ct_mtf50_lpmm`; its value remains in the headline, so no metric is lost. Do not insert a fake `metric` key such as `Detail` that a parser could mistake for a measurement. The blank separator is the section boundary; original dotted keys retain their spelling. Document that positional CSV consumers must adapt to the deliberate ordering change. XLSX `Summary` contains only identity, headline, inputs, and audit columns; `Detail` retains the full flatten. No ROI-size/plot-coordinate columns belong in `Summary`.

## Implementation sequence

1. **Lock fixtures and compatibility:** capture existing headers and representative synthetic `QAResult`s for CT, MRI, mixed, failed/partial, and absent sagittal geometry. Confirm the actual `analysis_type` values, profile keys, and MRI numeric geometry keys against runner output or de-identified result fixtures; the tracked MRI fixture has empty sagittal profiles, so add a synthetic four-ROI sagittal fixture. Confirm the post-analysis `echo_number` profile key and SNR input value units. Retain CT JSON `schema_version` 1.3 for the additive MTF metric; no existing field is changed. Do not use PHI-bearing examples.
2. **Move the CNR helper and harvest CT MTF@50%:** move `extract_low_contrast_cnr_values` from `qa_export.py` to `qa_result_flatten.py`, retaining a compatibility re-export from `qa_export.py`; update XLSX and new projection imports to use the shared location, avoiding an import cycle. Inside `run_acr_ct_analysis` after `analyzer.analyze`, read the live MTF scalar, coerce finite numeric output, and store `metrics["acr_ct_mtf50_lpmm"]`. If unavailable, retain successful analysis and add a useful warning rather than fabricating a value. Compare curated/structured CT CNR values here and add any mismatch to `ct_warnings`; make the analogous MRI low-contrast check in its runner. Keep raw `lpmm_to_rmtf` intact. Compare harvested CT MTF with pylinac `results()` on a representative non-PHI or approved de-identified run.
3. **Implement the shared projection:** add the ordered spec and pure extractors in `src/qa/qa_headline_results.py`. Export builders only read already recorded runner warnings; they never mutate `QAResult`. Validate missing/nonfinite handling, modality routing, type coercion, duplicate key prevention, and numeric geometry extraction.
4. **Wire the three ACR surfaces:** update `build_metrics_csv`, `build_batch_metrics_csv`, and `qa_xlsx_export._build_summary_sheet` to consume the same projection/order. Preserve existing single-run `metric,value`, batch wide-row, `Detail`, `Images`, and formula-neutralization behavior. Update public docstrings and GUI copy that describes export content; do not create format-specific metric lists. Change the locked `_SUMMARY_HEADERS` tuple and its exact-tuple test intentionally.
5. **Nuclear/flat CSV follow-on within this backlog item:** inventory each nuclear analysis class and its relevant `metrics["frames"]`, `["results"]`, `["quadrants"]`, or `["spheres"]` shape, then set per-class headline order before editing `build_nuclear_flat_csv`. Preserve its two-column shape and every result key; keep `build_nuclear_frames_csv`, `build_nuclear_quadrants_csv`, and `build_nuclear_spheres_csv` as separate tabular files with their current row granularity, moving result/performance fields before spatial/ROI/geometry inputs where clinically meaningful. Define and test an explicit header for each specialized form. This phase has its own review checkpoint because ACR CT/MRI labels cannot be reused for nuclear QC. If it cannot be completed in the same PR, split a linked follow-up plan and leave the backlog item partial rather than declaring all CSV exports done.
6. **Docs and closeout:** update export-facing user documentation and maintenance/changelog entries as warranted; update `TO_DO.md` to remove only completed scope, record any remaining nuclear or thickness work under its own item, and archive this plan to `plans/completed/` when all planned export work ships. No clinical acceptance thresholds are added here.

## Verification and acceptance

- **Projection unit tests:** exact ordered CT/MRI stable keys and labels; eight geometry fields drawn from numeric profile widths (four axial and four sagittal); MRI slice 11 present; CNR input aggregation; PSG percent units; status/warnings/errors; missing/failed/nonfinite blanks; no CT thickness or SNR; no opposite-modality leakage. Use synthetic QAResults, not patient data.
- **CSV contract tests:** single-run `metric,value` with headline first, blank separator, full original flatten retained; batch mixed-modality header/row order and stable blanks; sorted trailing keys; no duplicate header names; neutralized formula-like labels/warnings/detail; existing provenance `success` and all warnings/errors retained. Update `tests/qa/test_qa_export_csv.py`, `tests/qa/test_qa_result_flatten.py`, and relevant nuclear builder tests.
- **XLSX tests:** exact Summary order for CT, MRI, and mixed runs; numeric cells; missing values blank; Detail still contains ROI size/placement and rMTF/plot coordinates; Images fallback unchanged. Update `tests/qa/test_qa_xlsx_summary_columns.py` and `tests/qa/test_qa_module_images.py` only where their public contract changes. An in-memory workbook round-trip should preserve numeric types and neutralization.
- **Runner parity:** focused CT runner test for `relative_resolution(50)` capture, absent MTF, and no mutation of raw pylinac; representative non-PHI/de-identified result comparison against vanilla `results()` and PDF text for CT/MRI. Compare method labels as well as values. No full analysis is required for pure-export tests.
- **Repository gates:** activate `.venv` before tests/application code; run focused QA tests, `python scripts/check_user_docs_links.py` when user docs or `dev-docs/README.md` change, `python scripts/check_repo_harness.py`, architecture check, `git diff --check`, and normal privacy/hooks before commit/push. Do not bypass any gate. A full test suite and independent review are appropriate before merging the implementation PR.

**Done when:** a physicist can locate and copy the listed CT/MRI headline numbers without searching the flattened detail; all prior allowed metrics remain exportable; labels and units distinguish pylinac proxies, viewer SNR, measured MRI thickness, and DICOM-reported CT thickness; tests lock the order and preservation behavior; and remaining clinical-method work is explicitly tracked.

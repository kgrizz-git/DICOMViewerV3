"""Contract checks for the ordered ACR CT/MRI XLSX Summary projection."""

from __future__ import annotations

from io import BytesIO

import openpyxl

from qa.analysis_types import QAResult
from qa.qa_headline_results import columns_for
from qa.qa_xlsx_export import _SUMMARY_HEADERS, build_qa_workbook


def _ct_result() -> QAResult:
    return QAResult(
        success=True,
        analysis_type="acr_ct",
        series_uid="ct-series",
        modality="CT",
        metrics={
            "acr_ct_mtf50_lpmm": 0.53,
            "low_contrast_cnr": {
                "cnr": 4.25,
                "object_rois": [{"mean": 105.0}, {"mean": 95.0}],
                "background": {"mean": 12.0, "std": 1.5},
            },
        },
        raw_pylinac={
            "ct_module": {"rois": {"Water": 5.2, "Air": -998.0}},
            "uniformity_module": {"rois": {"Center": 3.0}, "center_roi_stdev": 4.2},
            "spatial_resolution_module": {"lpmm_to_rmtf": {"0.5": 0.51}},
        },
    )


def _mri_result() -> QAResult:
    return QAResult(
        success=True,
        analysis_type="acr_mri_large",
        series_uid="mri-series",
        modality="MR",
        metrics={
            "low_contrast_score": 34,
            "mri_snr": 87.5,
            "mri_snr_signal_mean": 175.0,
            "mri_snr_noise_mean": 2.0,
        },
        raw_pylinac={
            "uniformity_module": {
                "piu": 99.1,
                "psg": 0.42,
                "rois": {"Center": {"stdev": 3.0}},
            },
            "slice1": {
                "row_mtf_50": 1.05,
                "col_mtf_50": 0.98,
                "measured_slice_thickness_mm": 5.1,
                "slice_shift_mm": -0.25,
            },
            "slice11": {"slice_shift_mm": 0.5},
            "geometric_distortion_module": {
                "profiles": {
                    "horizontal": {"width (mm)": 190.1},
                    "vertical": {"width (mm)": 190.2},
                    "negative diagonal": {"width (mm)": 190.3},
                    "positive diagonal": {"width (mm)": 190.4},
                }
            },
            "sagittal_localizer_module": {
                "profiles": {f"ROI{i}": {"width (mm)": 148.0 + i} for i in range(1, 5)}
            },
        },
    )


def _row(wb: openpyxl.Workbook, number: int) -> dict[str, object]:
    ws = wb["Summary"]
    return dict(
        zip(
            [cell.value for cell in ws[1]],
            [cell.value for cell in ws[number]],
            strict=True,
        )
    )


def test_ct_summary_headlines_precede_inputs_and_detail() -> None:
    wb = build_qa_workbook([_ct_result()], labels=["CT-1"])
    headers = [cell.value for cell in wb["Summary"][1]]
    assert headers[:7] == [
        "Series/Run ID",
        "Analysis type",
        "Analysis status",
        "Warnings",
        "Errors",
        "CT low-contrast CNR (pylinac)",
        "CT MTF@50% (lp/mm, pylinac)",
    ]
    assert headers.index("CNR object ROI mean (HU)") > headers.index(
        "Uniformity center ROI SD (HU)"
    )
    assert "MRI PIU (%; pylinac percentile method)" not in headers
    row = _row(wb, 2)
    assert row["Series/Run ID"] == "CT-1"
    assert row["CT low-contrast CNR (pylinac)"] == 4.25
    assert row["CT MTF@50% (lp/mm, pylinac)"] == 0.53
    assert row["CT number: Air (HU)"] == -998.0
    assert row["CNR object ROI mean (HU)"] == 100.0
    assert row["CNR background SD (HU)"] == 1.5
    assert "spatial_resolution_module.lpmm_to_rmtf.0.5" in [
        cell.value for cell in wb["Detail"]["A"]
    ]


def test_mri_summary_numeric_geometry_and_signed_shift() -> None:
    wb = build_qa_workbook([_mri_result()])
    row = _row(wb, 2)
    assert row["MRI PIU (%; pylinac percentile method)"] == 99.1
    assert row["MRI percent signal ghosting (%)"] == 0.42
    assert row["MRI low-contrast complete-spoke score (pylinac)"] == 34
    assert row["MRI slice 1 position shift (mm)"] == -0.25
    assert row["MRI slice 11 position shift (mm)"] == 0.5
    assert row["MRI axial negative diagonal (mm)"] == 190.3
    assert row["MRI sagittal ROI4 length (mm)"] == 152.0
    assert row["Viewer MRI SNR (uncorrected)"] == 87.5
    assert "CT low-contrast CNR (pylinac)" not in row
    assert "uniformity_module.rois.Center.stdev" in [
        cell.value for cell in wb["Detail"]["A"]
    ]


def test_mixed_header_and_modality_blanks() -> None:
    wb = build_qa_workbook([_ct_result(), _mri_result()])
    headers = [cell.value for cell in wb["Summary"][1]]
    assert tuple(headers) == _SUMMARY_HEADERS
    assert headers.index("CT MTF@50% (lp/mm, pylinac)") < headers.index(
        "MRI PIU (%; pylinac percentile method)"
    )
    assert headers.index(
        "MRI SNR background noise (stored pixel value SD)"
    ) < headers.index("Analysis completed")
    assert _row(wb, 2)["MRI PIU (%; pylinac percentile method)"] in (None, "")
    assert _row(wb, 3)["CT low-contrast CNR (pylinac)"] in (None, "")


def test_missing_nonfinite_and_formula_cells() -> None:
    result = _ct_result()
    result.metrics["acr_ct_mtf50_lpmm"] = float("nan")
    result.raw_pylinac["ct_module"]["rois"]["Water"] = "=1+1"
    result.warnings = ["=unexpected"]
    wb = build_qa_workbook([result], labels=["=Run1"])
    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)
    row = _row(openpyxl.load_workbook(stream), 2)
    assert row["CT MTF@50% (lp/mm, pylinac)"] in (None, "")
    assert row["CT number: Water (HU)"] in (None, "")
    assert row["Series/Run ID"] == "'=Run1"
    assert row["Warnings"] == "'=unexpected"


def test_exact_ct_and_mri_headline_key_order() -> None:
    keys = [column.key for column in columns_for([_ct_result(), _mri_result()])]
    assert keys == [
        "series_run_id",
        "analysis_type",
        "analysis_status",
        "warnings",
        "errors",
        "acr_ct_cnr",
        "acr_ct_mtf50_lpmm",
        "acr_ct_hu_water",
        "acr_ct_hu_air",
        "acr_ct_hu_poly",
        "acr_ct_hu_acrylic",
        "acr_ct_hu_bone",
        "acr_ct_uniformity_hu_center",
        "acr_ct_uniformity_hu_top",
        "acr_ct_uniformity_hu_right",
        "acr_ct_uniformity_hu_bottom",
        "acr_ct_uniformity_hu_left",
        "acr_ct_uniformity_center_std_hu",
        "acr_ct_cnr_object_mean_hu",
        "acr_ct_cnr_background_mean_hu",
        "acr_ct_cnr_background_std_hu",
        "acr_mri_pylinac_percentile_piu_pct",
        "acr_mri_psg_pct",
        "acr_mri_low_contrast_spokes",
        "acr_mri_row_mtf50_lpmm",
        "acr_mri_col_mtf50_lpmm",
        "acr_mri_measured_slice_thickness_mm",
        "acr_mri_slice1_shift_mm",
        "acr_mri_slice11_shift_mm",
        "acr_mri_axial_horizontal_mm",
        "acr_mri_axial_vertical_mm",
        "acr_mri_axial_negative_diagonal_mm",
        "acr_mri_axial_positive_diagonal_mm",
        "acr_mri_sagittal_roi1_mm",
        "acr_mri_sagittal_roi2_mm",
        "acr_mri_sagittal_roi3_mm",
        "acr_mri_sagittal_roi4_mm",
        "acr_mri_viewer_snr_uncorrected",
        "acr_mri_snr_signal_mean",
        "acr_mri_snr_background_noise",
        "success",
        "label",
        "pylinac_version",
        "num_images",
        "study_uid",
        "series_uid",
        "modality",
        "analysis_profile_summary",
    ]


def test_failed_run_keeps_audit_but_blanks_existing_measurements() -> None:
    result = _ct_result()
    result.success = False
    result.errors = ["analysis incomplete"]
    row = _row(build_qa_workbook([result]), 2)
    assert row["Analysis status"] == "failed"
    assert row["Errors"] == "analysis incomplete"
    assert row["CT MTF@50% (lp/mm, pylinac)"] in (None, "")
    assert row["CT number: Water (HU)"] in (None, "")


def test_mri_low_contrast_uses_structured_fallback_when_curated_absent() -> None:
    result = _mri_result()
    del result.metrics["low_contrast_score"]
    result.raw_pylinac["low_contrast_multi_slice_module"] = {"score": 29}
    row = _row(build_qa_workbook([result]), 2)
    assert row["MRI low-contrast complete-spoke score (pylinac)"] == 29

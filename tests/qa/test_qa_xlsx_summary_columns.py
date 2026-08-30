"""
Tests for P2-X1 — modality-aware key columns on the XLSX Summary sheet.

The Summary sheet keeps its original 7 columns, then appends modality-aware
columns pulled from the canonical flatten (``build_metric_rows``): PIU, PSG,
LC score, MTF@50% row/col, slice thickness, slice shift, and MRI SNR. Each is
best-effort: a column stays blank when its flatten key is absent for the run,
so CT and MRI rows share one header with blanks where a metric does not apply.
The synthetic MRI fixture plants ``metrics["mri_snr"] = 87.5`` so the harvest
column is asserted filled; CT rows leave it blank.
"""

from __future__ import annotations

import openpyxl

from qa.analysis_types import QAResult
from qa.qa_xlsx_export import _SUMMARY_HEADERS, build_qa_workbook


def _ct_result() -> QAResult:
    """Synthetic ACR CT run: has LC score, but no PIU/PSG/MTF/thickness/shift."""
    return QAResult(
        success=True,
        analysis_type="acr_ct",
        metrics={
            "low_contrast_cnr": {
                "cnr": 4.25,
                "object_rois": [{"mean": 105.0}],
                "background": {"mean": 12.0, "std": 1.5},
            },
            "low_contrast_score": 1,
            "num_images": 40,
            "phantom_roll": 0.31,
            "origin_slice": 5,
        },
        warnings=[],
        errors=[],
        raw_pylinac={
            "phantom_model": "ACR CT 464",
            "uniformity_module": {"offset": 70.0, "rois": {"Center": 3.0}},
        },
        study_uid="1.2.3.4",
        series_uid="1.2.3.4.5",
        modality="CT",
        num_images=40,
        pylinac_version="3.43.2",
    )


def _mri_result() -> QAResult:
    """Synthetic ACR MRI run: PIU, PSG, LC score, MTF, thickness, shift, planted SNR."""
    return QAResult(
        success=True,
        analysis_type="acr_mri_large",
        metrics={
            "low_contrast_score": 34,
            "num_images": 11,
            "phantom_roll": -0.42,
            "origin_slice": 0,
            "mri_snr": 87.5,
        },
        warnings=[],
        errors=[],
        raw_pylinac={
            "phantom_model": "ACR MRI Large",
            "slice1": {
                "measured_slice_thickness_mm": 5.1,
                "slice_shift_mm": 0.25,
                "row_mtf_50": 1.05,
                "col_mtf_50": 0.98,
            },
            "uniformity_module": {
                "piu": 99.1,
                "psg": 0.42,
            },
        },
        study_uid="2.3.4.5",
        series_uid="2.3.4.5.6",
        modality="MR",
        num_images=11,
        pylinac_version="3.43.2",
    )


def _headers(summary: openpyxl.worksheet.worksheet.Worksheet) -> list[str | None]:
    return [c.value for c in summary[1]]


def test_summary_header_includes_new_columns() -> None:
    """The full header tuple must end with the eight modality-aware columns."""
    result = _ct_result()
    wb = build_qa_workbook([result], labels=["Run 1"])
    header = _headers(wb["Summary"])
    assert header[-8:] == [
        "PIU (%)",
        "PSG",
        "LC Score",
        "MTF@50% Row",
        "MTF@50% Col",
        "Slice Thickness (mm)",
        "Slice Shift (mm)",
        "MRI SNR",
    ]


def test_summary_header_tuple_is_locked() -> None:
    """_SUMMARY_HEADERS must match the canonical 15-column tuple (regression guard)."""
    assert _SUMMARY_HEADERS == (
        "Series/Run ID",
        "Object ROI Mean",
        "Background Mean",
        "Background Std",
        "CNR",
        "Status",
        "Warnings",
        "PIU (%)",
        "PSG",
        "LC Score",
        "MTF@50% Row",
        "MTF@50% Col",
        "Slice Thickness (mm)",
        "Slice Shift (mm)",
        "MRI SNR",
    )


def test_ct_row_fills_ct_relevant_columns_only() -> None:
    """CT row: LC score fills; PIU/PSG/MTF/thickness/shift/MRI SNR stay blank."""
    result = _ct_result()
    wb = build_qa_workbook([result], labels=["CT-1"])
    row = [c.value for c in wb["Summary"][2]]
    # Original columns present.
    assert row[0] == "CT-1"
    assert row[4] == 4.25  # CNR stays numeric
    # LC Score (index 9) fills; PIU/PSG (7,8), MRI-only MTF/thickness/shift (10-13),
    # and reserved MRI SNR (14) stay blank.
    assert row[9] == 1
    for idx in (7, 8, 10, 11, 12, 13, 14):
        assert row[idx] in (None, ""), f"column {idx} ({_SUMMARY_HEADERS[idx]}) should be blank for CT"


def test_mri_row_fills_mri_relevant_columns() -> None:
    """MRI row: PIU/PSG/MTF/thickness/shift/SNR fill from the synthetic fixture."""
    result = _mri_result()
    wb = build_qa_workbook([result], labels=["MRI-1"])
    row = [c.value for c in wb["Summary"][2]]
    assert row[7] == 99.1  # PIU
    assert row[8] == 0.42  # PSG
    assert row[9] == 34  # LC Score
    assert row[10] == 1.05  # MTF@50% Row
    assert row[11] == 0.98  # MTF@50% Col
    assert row[12] == 5.1  # Slice Thickness
    assert row[13] == 0.25  # Slice Shift
    assert row[14] == 87.5  # MRI SNR (synthetic fixture, not a phantom measurement)


def test_missing_keys_stay_blank() -> None:
    """A run with empty raw_pylinac + metrics gets blanks in every extra column."""
    result = QAResult(
        success=True,
        analysis_type="acr_ct",
        metrics={},
        raw_pylinac={},
        modality="CT",
        series_uid="9.9",
    )
    wb = build_qa_workbook([result])
    row = [c.value for c in wb["Summary"][2]]
    for idx in range(7, 15):
        assert row[idx] in (None, ""), f"column {idx} should be blank for an empty run"


def test_formula_like_series_label_still_neutralized() -> None:
    """A '=' Series/Run label must still be neutralized with the new columns."""
    result = _ct_result()
    wb = build_qa_workbook([result], labels=["=Run1"])
    assert wb["Summary"].cell(row=2, column=1).value == "'=Run1"


def test_formula_like_extra_summary_value_is_neutralized() -> None:
    """Mapped Summary extras beginning with formula triggers are stored as text."""
    result = _mri_result()
    result.raw_pylinac["uniformity_module"]["piu"] = "=1+1"
    wb = build_qa_workbook([result], labels=["MRI-1"])
    assert wb["Summary"].cell(row=2, column=8).value == "'=1+1"


def test_cnr_numeric_cells_still_numbers() -> None:
    """CNR and the new numeric columns must remain numbers, not strings."""
    # Use the CT run (which carries low_contrast_cnr) to assert CNR stays numeric.
    result = _ct_result()
    wb = build_qa_workbook([result], labels=["CT-1"])
    row2 = wb["Summary"][2]
    assert isinstance(row2[4].value, (int, float))  # CNR
    assert isinstance(row2[9].value, (int, float))  # LC Score
    # And the MRI-only numeric columns on an MRI run.
    mri = _mri_result()
    wb2 = build_qa_workbook([mri], labels=["MRI-1"])
    mri_row = wb2["Summary"][2]
    assert isinstance(mri_row[7].value, (int, float))  # PIU
    assert isinstance(mri_row[12].value, (int, float))  # Slice Thickness
    assert isinstance(mri_row[14].value, (int, float))  # MRI SNR


def test_mixed_ct_and_mri_batch_share_header() -> None:
    """A CT + MRI batch shares one header; each row fills only its own fields."""
    wb = build_qa_workbook([_ct_result(), _mri_result()], labels=["C", "M"])
    ct_row = [c.value for c in wb["Summary"][2]]
    mri_row = [c.value for c in wb["Summary"][3]]

    # CT: blank PIU/PSG/MTF/thickness/shift/MRI SNR; fills LC score.
    assert ct_row[7] in (None, "")
    assert ct_row[8] in (None, "")
    assert ct_row[9] == 1
    assert ct_row[10] in (None, "")
    assert ct_row[14] in (None, "")

    # MRI: fills harvested fields including synthetic MRI SNR.
    assert mri_row[7] == 99.1
    assert mri_row[8] == 0.42
    assert mri_row[9] == 34
    assert mri_row[10] == 1.05
    assert mri_row[11] == 0.98
    assert mri_row[12] == 5.1
    assert mri_row[13] == 0.25
    assert mri_row[14] == 87.5

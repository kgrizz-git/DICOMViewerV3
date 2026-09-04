"""
Tests for src/qa/qa_result_flatten.py — canonical flatten builders.

Uses synthetic ``raw_pylinac`` trees shaped like pylinac 3.43.2
``results_data(as_dict=True)`` output (field names copied from the dataclasses
in pylinac/acr.py). No live ``analyze()``, no DICOM fixtures, no PHI.
"""

from __future__ import annotations

import re

from qa.analysis_types import QAResult
from qa.qa_result_flatten import (
    build_metric_rows,
    build_run_provenance,
    build_tabular_run,
)


def _roi_result(name: str, value: float, stdev: float = 1.0) -> dict:
    """Shape of pylinac 3.43.2 ``ROIResult`` after ``rois_to_results()``."""
    return {
        "name": name,
        "value": value,
        "stdev": stdev,
        "difference": None,
        "nominal_value": None,
        "passed": None,
    }

# ---------------------------------------------------------------------------
# Synthetic fixtures (field names from pylinac 3.43.2 dataclasses)
# ---------------------------------------------------------------------------


def _ct_raw_pylinac() -> dict:
    """Synthetic ACRCT results_data(as_dict=True)-shaped tree."""
    return {
        "phantom_model": "ACR CT 464",
        "phantom_roll_deg": 0.31,
        "origin_slice": 5,
        "num_images": 40,
        "ct_module": {
            "offset": 0.0,
            "roi_distance_from_center_mm": 63.0,
            "roi_radius_mm": 10.0,
            "roi_settings": {"Air": {"angle": 45}, "Water": {"angle": 180}},
            "rois": {
                "Air": -987.1,
                "Poly": 120.3,
                "Acrylic": 132.5,
                "Bone": 820.0,
                "Water": 5.2,
            },
        },
        "uniformity_module": {
            "offset": 70.0,
            "roi_distance_from_center_mm": 66.0,
            "roi_radius_mm": 11.0,
            "roi_settings": {"Top": {"angle": -90}, "Center": {"angle": 0}},
            "rois": {"Top": 3.1, "Right": 2.8, "Bottom": 3.5, "Left": 2.9, "Center": 3.0},
            "center_roi_stdev": 4.2,
        },
        "low_contrast_module": {
            "offset": 30.0,
            "roi_distance_from_center_mm": 60.0,
            "roi_radius_mm": 6.0,
            "roi_settings": {"ROI": {"angle": -90}},
            "rois": {"ROI": 105.2},
            "cnr": 4.25,
        },
        "spatial_resolution_module": {
            "offset": 100.0,
            "roi_distance_from_center_mm": 70.0,
            "roi_radius_mm": 6.0,
            "roi_settings": {"10oclock": {"angle": -135, "lp/mm": 0.4}},
            "rois": {"10oclock": 0.72, "12oclock": 0.65},
            "lpmm_to_rmtf": {"0.4": 0.91, "0.5": 0.83, "1.2": 0.32},
        },
    }


def _mri_raw_pylinac() -> dict:
    """Synthetic ACRMRILarge results_data(as_dict=True)-shaped tree."""
    return {
        "phantom_model": "ACR MRI Large",
        "phantom_roll_deg": -0.42,
        "origin_slice": 0,
        "num_images": 11,
        "slice1": {
            "offset": 0,
            "roi_settings": {"Row 1.1": {"angle": 0}},
            "rois": {
                "Row 1.1": _roi_result("Row 1.1", 0.85),
                "Col 1.1": _roi_result("Col 1.1", 0.78),
            },
            "bar_difference_mm": 0.5,
            "slice_shift_mm": 0.25,
            "measured_slice_thickness_mm": 5.1,
            "row_mtf_50": 1.05,
            "col_mtf_50": 0.98,
            "row_mtf_lp_mm": {10: 0.5, 50: 1.05, 90: 1.6},
            "col_mtf_lp_mm": {10: 0.45, 50: 0.98, 90: 1.5},
        },
        "slice11": {
            "offset": 100,
            "roi_settings": {"Left": {"angle": 180}},
            "rois": {
                "Left": _roi_result("Left", 0.7),
                "Right": _roi_result("Right", 0.72),
            },
            "bar_difference_mm": 0.4,
            "slice_shift_mm": 0.2,
        },
        "uniformity_module": {
            "offset": 60,
            "roi_settings": {"Center": {"angle": 90, "radius": 80}},
            "rois": {"Center": _roi_result("Center", 1500.0, stdev=12.0)},
            "ghost_roi_settings": {"Top": {"angle": -90}, "Left": {"angle": 180}},
            "ghost_rois": {
                "Top": _roi_result("Top", 12.0, 1.1),
                "Bottom": _roi_result("Bottom", 11.5, 1.0),
                "Left": _roi_result("Left", 10.8, 0.9),
                "Right": _roi_result("Right", 11.2, 1.2),
            },
            "psg": 0.42,
            "ghosting_ratio": 0.0042,
            "piu_passed": True,
            "piu": 99.1,
        },
        "geometric_distortion_module": {
            "offset": 40,
            "profiles": {
                "horizontal": {"width (mm)": 191.2, "line": {}},
                "vertical": {"width (mm)": 190.8, "line": {}},
            },
            "distances": {"horizontal": "191.20mm", "vertical": "190.80mm"},
        },
        "sagittal_localizer_module": {
            "profiles": {"ROI1": {"width (mm)": 150.0, "line": {}}},
            "distances": {"ROI1": "150.00mm"},
        },
        "low_contrast_multi_slice_module": {
            "score": 34,
            "low_contrast_rois": {
                "slice_8": {
                    "offset": 70,
                    "slice_num": 8,
                    "spoke_settings": {},
                    "background_settings": {},
                    "spokes": {},
                },
            },
        },
    }


def _ct_result() -> QAResult:
    return QAResult(
        success=True,
        analysis_type="acr_ct",
        metrics={
            "low_contrast_cnr": {
                "cnr": 4.25,
                "object_rois": [{"mean": 105.0}, {"mean": 95.0}],
                "background": {"mean": 12.0, "std": 1.5},
            },
            "low_contrast_score": 1,
            "num_images": 40,
            "phantom_roll": 0.31,
            "origin_slice": 5,
        },
        warnings=[],
        errors=[],
        raw_pylinac=_ct_raw_pylinac(),
        study_uid="1.2.3.4",
        series_uid="1.2.3.4.5",
        modality="CT",
        num_images=40,
        pylinac_version="3.43.2",
        pylinac_analysis_profile={"engine": "ACRCTForViewer"},
        analyzed_image_path="/tmp/some/analyzed_image.png",
    )


def _mri_result() -> QAResult:
    return QAResult(
        success=True,
        analysis_type="acr_mri_large",
        metrics={
            "low_contrast_score": 34,
            "num_images": 11,
            "phantom_roll": -0.42,
            "origin_slice": 0,
        },
        warnings=["Low signal on slice 9"],
        errors=[],
        raw_pylinac=_mri_raw_pylinac(),
        study_uid="2.3.4.5",
        series_uid="2.3.4.5.6",
        modality="MR",
        num_images=11,
        pylinac_version="3.43.2",
        pylinac_analysis_profile={"engine": "ACRMRILargeForViewer"},
        analyzed_image_path="/tmp/some/mri_image.png",
    )


# ---------------------------------------------------------------------------
# CT success
# ---------------------------------------------------------------------------


def test_ct_success_includes_keys_per_family() -> None:
    rows = dict(build_metric_rows(_ct_result()))
    # ct_module
    assert "ct_module.rois.Air" in rows
    assert "ct_module.rois.Water" in rows
    # uniformity_module
    assert "uniformity_module.rois.Center" in rows
    assert "uniformity_module.center_roi_stdev" in rows
    # low_contrast_module
    assert "low_contrast_module.cnr" in rows
    # spatial_resolution_module (nested dict → dotted leaves)
    assert "spatial_resolution_module.lpmm_to_rmtf.0.4" in rows
    assert "spatial_resolution_module.lpmm_to_rmtf.1.2" in rows
    # top-level
    assert "phantom_roll_deg" in rows
    assert "origin_slice" in rows
    assert "num_images" in rows


def test_ct_metrics_overlay_wins_on_collision() -> None:
    """Curated metrics overlay should win over raw_pylinac on key collision."""
    result = _ct_result()
    # Inject a collision: metrics has a top-level key that also exists in raw_pylinac
    result.metrics["phantom_roll_deg"] = 9.99  # raw has 0.31
    rows = dict(build_metric_rows(result))
    assert rows["phantom_roll_deg"] == 9.99


def test_ct_curated_metrics_top_level() -> None:
    """Curated metrics stay top-level (no literal 'metrics.' prefix)."""
    rows = dict(build_metric_rows(_ct_result()))
    # Scalar curated keys stay top-level
    assert "low_contrast_score" in rows
    # Nested curated dict gets dotted under its top-level key
    assert "low_contrast_cnr.cnr" in rows
    assert "low_contrast_cnr.background.std" in rows


# ---------------------------------------------------------------------------
# MRI success
# ---------------------------------------------------------------------------


def test_mri_success_includes_keys_per_family() -> None:
    rows = dict(build_metric_rows(_mri_result()))
    # slice1
    assert "slice1.measured_slice_thickness_mm" in rows
    assert "slice1.row_mtf_50" in rows
    # MTF lp_mm is a nested int→float dict → dotted leaves
    assert "slice1.row_mtf_lp_mm.50" in rows
    assert "slice1.row_mtf_lp_mm.10" in rows
    # slice11
    assert "slice11.bar_difference_mm" in rows
    # uniformity_module (PSG dict-complete)
    assert "uniformity_module.psg" in rows
    assert "uniformity_module.ghosting_ratio" in rows
    assert "uniformity_module.piu" in rows
    # MRI rois are ROIResult dicts (rois_to_results), not scalar HU maps
    assert "uniformity_module.rois.Center.value" in rows
    assert "uniformity_module.ghost_rois.Left.stdev" in rows
    # geometric_distortion_module
    assert "geometric_distortion_module.distances.horizontal" in rows
    # sagittal_localizer_module
    assert "sagittal_localizer_module.distances.ROI1" in rows
    # low_contrast_multi_slice_module
    assert "low_contrast_multi_slice_module.score" in rows
    # top-level
    assert "phantom_roll_deg" in rows


def test_mri_metrics_overlay_top_level() -> None:
    rows = dict(build_metric_rows(_mri_result()))
    assert "low_contrast_score" in rows
    assert rows["low_contrast_score"] == 34


# ---------------------------------------------------------------------------
# Failed run
# ---------------------------------------------------------------------------


def test_failed_run_no_crash() -> None:
    result = QAResult(
        success=False,
        analysis_type="acr_ct",
        errors=["physical scan extent does not cover the extent of module configuration"],
        raw_pylinac={},
        metrics={},
    )
    rows = build_metric_rows(result)
    assert rows == []
    prov = build_run_provenance(result)
    assert prov["success"] is False
    assert len(prov["errors"]) == 1
    tab = build_tabular_run(result)
    assert tab["success"] is False
    assert len(tab["errors"]) == 1


def test_failed_run_empty_raw_pylinac_with_metrics() -> None:
    """Even with empty raw_pylinac, curated metrics still surface."""
    result = QAResult(
        success=False,
        analysis_type="acr_mri_large",
        errors=["analyze failed"],
        raw_pylinac={},
        metrics={"low_contrast_score": 0, "num_images": 4},
    )
    rows = dict(build_metric_rows(result))
    assert rows["low_contrast_score"] == 0
    assert rows["num_images"] == 4


# ---------------------------------------------------------------------------
# Warnings preserved
# ---------------------------------------------------------------------------


def test_warnings_preserved_in_provenance() -> None:
    prov = build_run_provenance(_mri_result())
    assert prov["warnings"] == ["Low signal on slice 9"]


def test_warnings_empty_when_none() -> None:
    prov = build_run_provenance(_ct_result())
    assert prov["warnings"] == []


def test_tabular_run_keeps_result_warnings_when_raw_pylinac_has_empty_warnings() -> None:
    """Pylinac dumps always include top-level warnings=[]; must not clobber QAResult."""
    result = _ct_result()
    result.warnings = ["Slice spacing irregular: expected 5.00 mm"]
    result.raw_pylinac = {**result.raw_pylinac, "warnings": []}
    rows = dict(build_metric_rows(result))
    assert "warnings" not in rows
    tab = build_tabular_run(result, label="CT-1")
    assert tab["warnings"] == ["Slice spacing irregular: expected 5.00 mm"]


def test_provenance_keeps_raw_pylinac_audit_messages_when_result_is_silent() -> None:
    """Non-empty raw audit lists remain exportable even without runner messages."""
    result = QAResult(
        success=True,
        analysis_type="acr_ct",
        raw_pylinac={
            "warnings": ["pylinac: low contrast"],
            "errors": ["pylinac: incomplete module"],
        },
    )
    provenance = build_run_provenance(result)
    assert provenance["warnings"] == ["pylinac: low contrast"]
    assert provenance["errors"] == ["pylinac: incomplete module"]


def test_tabular_run_keeps_result_errors_when_raw_pylinac_has_errors_key() -> None:
    """Raw audit messages augment, rather than replace, runner/preflight messages."""
    result = QAResult(
        success=False,
        analysis_type="acr_ct",
        errors=["physical scan extent too short"],
        warnings=["preflight: duplicate ImagePositionPatient"],
        raw_pylinac={
            "num_images": 10,
            "warnings": ["pylinac: low contrast"],
            "errors": ["pylinac: incomplete module"],
        },
        metrics={},
    )
    tab = build_tabular_run(result)
    assert tab["errors"] == [
        "physical scan extent too short",
        "pylinac: incomplete module",
    ]
    assert tab["warnings"] == [
        "preflight: duplicate ImagePositionPatient",
        "pylinac: low contrast",
    ]
    assert "warnings" not in dict(build_metric_rows(result))
    assert "errors" not in dict(build_metric_rows(result))


# ---------------------------------------------------------------------------
# Stable sort order
# ---------------------------------------------------------------------------


def test_stable_sort_order() -> None:
    rows1 = build_metric_rows(_ct_result())
    rows2 = build_metric_rows(_ct_result())
    assert [k for k, _ in rows1] == [k for k, _ in rows2]
    # Verify actually sorted
    keys = [k for k, _ in rows1]
    assert keys == sorted(keys, key=str)


# ---------------------------------------------------------------------------
# No filesystem paths leak
# ---------------------------------------------------------------------------


def test_no_absolute_paths_in_flatten_output() -> None:
    for result in (_ct_result(), _mri_result()):
        for key, value in build_metric_rows(result):
            assert "analyzed_image_path" not in key, key
            # Value must not be an absolute filesystem path
            if isinstance(value, str):
                assert not re.match(r"^(/|[A-Za-z]:\\)", value), (key, value)
        tab = build_tabular_run(result)
        assert "analyzed_image_path" not in tab


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------


def test_provenance_fields() -> None:
    prov = build_run_provenance(_ct_result(), label="Series A")
    assert prov["analysis_type"] == "acr_ct"
    assert prov["success"] is True
    assert prov["pylinac_version"] == "3.43.2"
    assert prov["study_uid"] == "1.2.3.4"
    assert prov["series_uid"] == "1.2.3.4.5"
    assert prov["modality"] == "CT"
    assert prov["num_images"] == 40
    assert prov["label"] == "Series A"
    assert prov["errors"] == []
    assert prov["warnings"] == []


def test_provenance_label_none_by_default() -> None:
    prov = build_run_provenance(_mri_result())
    assert prov["label"] is None


# ---------------------------------------------------------------------------
# Tabular run
# ---------------------------------------------------------------------------


def test_tabular_run_merges_provenance_and_metrics() -> None:
    tab = build_tabular_run(_ct_result(), label="CT-1")
    # Provenance keys present
    assert tab["analysis_type"] == "acr_ct"
    assert tab["label"] == "CT-1"
    # Metric keys present
    assert "ct_module.rois.Air" in tab
    assert "low_contrast_cnr.cnr" in tab


def test_tabular_run_metrics_win_on_collision() -> None:
    """Flatten/metrics overlay wins and stays top-level (no metric. rename)."""
    result = _ct_result()
    result.metrics["modality"] = "OVERRIDE"
    tab = build_tabular_run(result)
    assert tab["modality"] == "OVERRIDE"
    assert "metric.modality" not in tab


def test_tabular_run_num_images_stays_top_level() -> None:
    """Production collision: provenance and raw_pylinac both expose num_images."""
    tab = build_tabular_run(_ct_result(), label="CT-1")
    assert "num_images" in tab
    assert "metric.num_images" not in tab
    assert tab["num_images"] == 40


def test_denylist_drops_path_keys_from_raw_and_metrics() -> None:
    """analyzed_image_path / pdf_report_path must not leak even if stuffed in dicts."""
    result = _ct_result()
    result.raw_pylinac["analyzed_image_path"] = "/tmp/raw_leak.png"
    result.raw_pylinac["ct_module"]["pdf_report_path"] = "/tmp/nested_leak.pdf"
    result.metrics["analyzed_image_path"] = "/tmp/metrics_leak.png"
    rows = dict(build_metric_rows(result))
    assert "analyzed_image_path" not in rows
    assert "ct_module.pdf_report_path" not in rows
    tab = build_tabular_run(result)
    assert "analyzed_image_path" not in tab
    assert "pdf_report_path" not in tab
    assert "ct_module.pdf_report_path" not in tab

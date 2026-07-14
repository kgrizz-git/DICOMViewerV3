"""
Unit tests for the shared QA export builders (no Qt).

Covers the single-run JSON document (ACR vs nuclear discriminator) and the
nuclear per-frame CSV text.
"""

from __future__ import annotations

import csv
import io

from qa.analysis_types import QAResult
from qa.qa_export import (
    build_metrics_csv,
    build_nuclear_frames_csv,
    build_nuclear_quadrants_csv,
    build_nuclear_spheres_csv,
    build_single_run_document,
)

_FRAMES = {
    "Frame 2": {
        "ufov_integral_uniformity": 28.16,
        "ufov_differential_uniformity": 4.05,
        "cfov_integral_uniformity": 17.67,
        "cfov_differential_uniformity": 3.33,
    },
    "Frame 1": {
        "ufov_integral_uniformity": 27.60,
        "ufov_differential_uniformity": 4.23,
        "cfov_integral_uniformity": 17.15,
        "cfov_differential_uniformity": 3.11,
    },
}


def _nuclear_result() -> QAResult:
    return QAResult(
        success=True,
        analysis_type="nuclear_planar_uniformity",
        metrics={"analysis_class": "PlanarUniformity", "frame_count": 2, "frames": _FRAMES},
        pylinac_version="3.43.2",
        pylinac_analysis_profile={
            "module": "pylinac.nuclear",
            "nuclear_analysis_class": "PlanarUniformity",
        },
    )


def test_single_run_document_nuclear_fields() -> None:
    doc = build_single_run_document(
        _nuclear_result(), app_version="9.9.9", inputs={"input_path": "p.dcm"}
    )
    assert doc["schema_version"] == "1.1"
    assert doc["run"]["app_version"] == "9.9.9"
    assert doc["run"]["analysis_type"] == "nuclear_planar_uniformity"
    assert doc["run"]["nuclear_analysis_class"] == "PlanarUniformity"
    assert doc["inputs"]["input_path"] == "p.dcm"
    assert doc["metrics"]["frame_count"] == 2


def test_single_run_document_acr_has_no_nuclear_key() -> None:
    acr = QAResult(
        success=True,
        analysis_type="acr_ct",
        pylinac_analysis_profile={"engine": "ACRCTForViewer"},
    )
    doc = build_single_run_document(acr, app_version="1.0.0")
    assert "nuclear_analysis_class" not in doc["run"]


def test_nuclear_frames_csv_is_sorted_and_complete() -> None:
    text = build_nuclear_frames_csv(_nuclear_result())
    rows = list(csv.reader(io.StringIO(text)))
    assert rows[0] == [
        "frame",
        "ufov_integral_uniformity",
        "ufov_differential_uniformity",
        "cfov_integral_uniformity",
        "cfov_differential_uniformity",
    ]
    # Sorted by frame number despite insertion order.
    assert rows[1][0] == "Frame 1"
    assert rows[2][0] == "Frame 2"
    assert rows[1][1] == "27.6"


def test_nuclear_frames_csv_empty_when_no_frames() -> None:
    result = QAResult(success=False, analysis_type="nuclear_planar_uniformity")
    rows = list(csv.reader(io.StringIO(build_nuclear_frames_csv(result))))
    assert rows[0][0] == "frame"
    assert len(rows) == 1  # header only


def test_nuclear_spheres_csv_one_row_per_sphere() -> None:
    result = QAResult(
        success=True,
        analysis_type="nuclear_tomographic_contrast",
        metrics={
            "spheres": {
                "2": {"x": 69.7, "y": 47.4, "z": 14.0, "radius": 3.9, "mean": 828.8,
                      "mean_contrast": 23.6, "max_contrast": 52.9},
                "1": {"x": 78.5, "y": 58.5, "z": 13.0, "radius": 4.6, "mean": 633.9,
                      "mean_contrast": 35.8, "max_contrast": 72.3},
            }
        },
    )
    rows = list(csv.reader(io.StringIO(build_nuclear_spheres_csv(result))))
    assert rows[0] == ["sphere", "x", "y", "z", "radius", "mean", "mean_contrast", "max_contrast"]
    assert rows[1][0] == "1"  # sorted
    assert rows[2][0] == "2"


def test_metrics_csv_flattens_acr_metrics() -> None:
    acr = QAResult(
        success=True,
        analysis_type="acr_ct",
        metrics={
            "catphan_model": "CatPhan504",
            "phantom_roll": 0.31,
            "num_images": 40,
            "origin_slice": None,
        },
    )
    rows = list(csv.reader(io.StringIO(build_metrics_csv(acr))))
    assert rows[0] == ["metric", "value"]
    body = {r[0]: r[1] for r in rows[1:]}
    assert body["catphan_model"] == "CatPhan504"
    assert body["phantom_roll"] == "0.31"
    assert body["num_images"] == "40"
    assert body["origin_slice"] == ""  # None -> blank


def test_nuclear_quadrants_csv_one_row_per_quadrant() -> None:
    result = QAResult(
        success=True,
        analysis_type="nuclear_quadrant_resolution",
        metrics={
            "quadrants": {
                "2": {"mtf": 0.47, "fwhm": 2.93, "lpmm": 0.157, "spacing": 3.18},
                "1": {"mtf": 0.65, "fwhm": 2.96, "lpmm": 0.118, "spacing": 4.23},
            }
        },
    )
    rows = list(csv.reader(io.StringIO(build_nuclear_quadrants_csv(result))))
    assert rows[0] == ["quadrant", "mtf", "fwhm", "lpmm", "spacing"]
    # Sorted by quadrant key.
    assert rows[1][0] == "1"
    assert rows[2][0] == "2"
    assert rows[1][1] == "0.65"


def test_metrics_csv_dotted_keys_for_nested() -> None:
    result = QAResult(
        success=True,
        analysis_type="acr_ct",
        metrics={"mtf": {"50%": 0.62, "10%": 1.1}, "tags": [1, 2, 3]},
    )
    body = {
        r[0]: r[1] for r in csv.reader(io.StringIO(build_metrics_csv(result)))
    }
    assert body["mtf.50%"] == "0.62"
    assert body["mtf.10%"] == "1.1"
    assert body["tags"] == "1; 2; 3"

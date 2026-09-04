"""
Tests for the full-flatten CSV builders in src/qa/qa_export.py (P1-F2/F3).

Covers:
    - P1-F2: build_metrics_csv emits the full flatten (raw_pylinac + metrics),
      row count greater than the legacy metrics-only flatten, formula cells
      neutralized, JSON document unchanged (no metrics_flat).
    - P1-F3: build_batch_metrics_csv produces a wide CSV with one row per run,
      provenance-first column order, num_images top-level (not metric.num_images),
      stable overflow sort, empty-results header-only, parallel labels.

No live analyze(), no DICOM fixtures, no PHI.
"""

from __future__ import annotations

import csv
import io

from qa.analysis_types import QAResult
from qa.qa_export import (
    build_batch_metrics_csv,
    build_metrics_csv,
    build_single_run_document,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _acr_result() -> QAResult:
    """ACR CT run with both curated metrics and a nested raw_pylinac tree."""
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
        raw_pylinac={
            "phantom_model": "ACR CT 464",
            "phantom_roll_deg": 0.31,
            "origin_slice": 5,
            "num_images": 40,
            "ct_module": {
                "offset": 0.0,
                "rois": {"Air": -987.1, "Water": 5.2},
            },
            "uniformity_module": {
                "offset": 70.0,
                "rois": {"Center": 3.0},
                "center_roi_stdev": 4.2,
            },
        },
        study_uid="1.2.3.4",
        series_uid="1.2.3.4.5",
        modality="CT",
        num_images=40,
        pylinac_version="3.43.2",
        pylinac_analysis_profile={"engine": "ACRCTForViewer"},
        analyzed_image_path="/tmp/analyzed_image.png",
    )


def _formula_result() -> QAResult:
    """Run whose metric values include formula-trigger strings."""
    return QAResult(
        success=True,
        analysis_type="acr_ct",
        metrics={
            "catphan_model": "=SUM(A1)",
            "phantom_roll": "+1.5",
            "note": "-see sheet",
            "tag": "@IMPORT(A1:B2)",
            "safe_value": "CatPhan504",
        },
        raw_pylinac={"phantom_model": "ok", "origin_slice": 3},
    )


# ---------------------------------------------------------------------------
# P1-F2 — build_metrics_csv uses full flatten
# ---------------------------------------------------------------------------


def test_metrics_csv_row_count_exceeds_metrics_only() -> None:
    """Full flatten must emit more rows than the metrics-only walk."""
    result = _acr_result()
    full_rows = list(csv.reader(io.StringIO(build_metrics_csv(result))))
    legacy_rows = list(csv.reader(io.StringIO(_legacy_metrics_csv(result))))
    # Header + body.
    assert len(full_rows) > len(legacy_rows)
    # Full flatten includes raw_pylinac keys absent from metrics-only output.
    full_keys = {r[0] for r in full_rows[1:]}
    assert "ct_module.rois.Air" in full_keys
    assert "uniformity_module.center_roi_stdev" in full_keys


def test_metrics_csv_formula_cells_neutralized() -> None:
    """Leading = + - @ string cells must be prefixed with an apostrophe."""
    result = _formula_result()
    body = {
        r[0]: r[1] for r in csv.reader(io.StringIO(build_metrics_csv(result)))
    }
    assert body["catphan_model"] == "'=SUM(A1)"
    assert body["phantom_roll"] == "'+1.5"
    assert body["note"] == "'-see sheet"
    assert body["tag"] == "'@IMPORT(A1:B2)"
    # A safe value is left untouched.
    assert body["safe_value"] == "CatPhan504"


def test_metrics_csv_does_not_leak_analyzed_image_path() -> None:
    """The path denylist must hold in the full-flatten CSV."""
    result = _acr_result()
    keys = [
        r[0] for r in csv.reader(io.StringIO(build_metrics_csv(result)))
    ]
    assert "analyzed_image_path" not in keys


def test_json_document_has_no_metrics_flat() -> None:
    """JSON schema is export-layer only — no metrics_flat key added."""
    doc = build_single_run_document(_acr_result(), app_version="1.0.0")
    assert "metrics_flat" not in doc
    # raw_pylinac still present (opaque passthrough).
    assert doc["raw_pylinac"]["phantom_model"] == "ACR CT 464"


# ---------------------------------------------------------------------------
# P1-F3 — build_batch_metrics_csv
# ---------------------------------------------------------------------------


def test_batch_csv_header_and_row_count() -> None:
    """N data rows + one header for N results."""
    results = [_acr_result(), _acr_result()]
    text = build_batch_metrics_csv(results, labels=["A", "B"])
    rows = list(csv.reader(io.StringIO(text)))
    assert len(rows) == 3  # header + 2 data rows
    # Provenance keys lead the header.
    assert rows[0][0] == "analysis_type"
    assert "success" in rows[0]
    # Metric overflow keys present after provenance block.
    assert "ct_module.rois.Air" in rows[0]


def test_batch_csv_num_images_top_level_not_metric_namespaced() -> None:
    """num_images must be top-level (build_tabular_run overlay), not metric.num_images."""
    text = build_batch_metrics_csv([_acr_result()], labels=["Run1"])
    rows = list(csv.reader(io.StringIO(text)))
    assert "num_images" in rows[0]
    assert "metric.num_images" not in rows[0]
    col = rows[0].index("num_images")
    assert rows[1][col] == "40"


def test_batch_csv_labels_parallel_and_overflow_sorted() -> None:
    """Labels align with results; overflow metric keys sorted by str (stable)."""
    r1 = QAResult(success=True, analysis_type="acr_ct", metrics={"aaa": 1},
                  raw_pylinac={"zz": 1})
    r2 = QAResult(success=True, analysis_type="acr_ct", metrics={"bbb": 2},
                  raw_pylinac={"aa": 2})
    text = build_batch_metrics_csv([r1, r2], labels=["L1", "L2"])
    rows = list(csv.reader(io.StringIO(text)))
    header = rows[0]
    label_idx = header.index("label")
    assert rows[1][label_idx] == "L1"
    assert rows[2][label_idx] == "L2"
    # Overflow keys sorted by str: "aa" < "aaa" < "bbb" < "zz"
    overflow = [k for k in header if k not in _PROV_KEYS]
    assert overflow == sorted(overflow, key=str)
    assert overflow == ["aa", "aaa", "bbb", "zz"]


def test_batch_csv_missing_cells_empty() -> None:
    """A key present in one run but not another yields an empty cell."""
    r1 = QAResult(success=True, analysis_type="acr_ct", metrics={}, raw_pylinac={"only_here": 1})
    r2 = QAResult(success=True, analysis_type="acr_ct", metrics={}, raw_pylinac={})
    text = build_batch_metrics_csv([r1, r2])
    rows = list(csv.reader(io.StringIO(text)))
    col = rows[0].index("only_here")
    assert rows[1][col] == "1"
    assert rows[2][col] == ""


def test_batch_csv_formula_label_neutralized() -> None:
    """DICOM-derived run labels can start with formula chars (R0-8)."""
    result = _acr_result()
    text = build_batch_metrics_csv([result], labels=["=Run1"])
    rows = list(csv.reader(io.StringIO(text)))
    label_idx = rows[0].index("label")
    assert rows[1][label_idx] == "'=Run1"


def test_batch_csv_labels_shorter_than_results() -> None:
    """If labels is shorter, unmatched results get label=None (empty cell)."""
    results = [_acr_result(), _acr_result(), _acr_result()]
    text = build_batch_metrics_csv(results, labels=["only-one"])
    rows = list(csv.reader(io.StringIO(text)))
    label_idx = rows[0].index("label")
    assert rows[1][label_idx] == "only-one"
    assert rows[2][label_idx] == ""
    assert rows[3][label_idx] == ""


def test_batch_csv_empty_results_header_only() -> None:
    """Empty results → header-only CSV with provenance keys, no metric columns."""
    text = build_batch_metrics_csv([])
    rows = list(csv.reader(io.StringIO(text)))
    assert len(rows) == 1
    assert rows[0] == _PROV_KEYS


def test_batch_csv_formula_cells_neutralized() -> None:
    """Formula-like cells in batch rows are neutralized too."""
    result = _formula_result()
    text = build_batch_metrics_csv([result])
    rows = list(csv.reader(io.StringIO(text)))
    header = rows[0]
    cat_idx = header.index("catphan_model")
    assert rows[1][cat_idx] == "'=SUM(A1)"


def test_batch_csv_list_error_cells_joined_and_neutralized() -> None:
    """errors/warnings lists must be joined so SafeCsvWriter sees the string."""
    result = QAResult(
        success=False,
        analysis_type="acr_ct",
        errors=["=SUM(A1)", "physical scan extent too short"],
        warnings=["+cmd"],
        raw_pylinac={},
        metrics={},
    )
    text = build_batch_metrics_csv([result])
    rows = list(csv.reader(io.StringIO(text)))
    header = rows[0]
    errors_cell = rows[1][header.index("errors")]
    warnings_cell = rows[1][header.index("warnings")]
    assert errors_cell.startswith("'=")
    assert "physical scan extent too short" in errors_cell
    assert warnings_cell == "'+cmd"
    assert errors_cell.startswith("[") is False


def test_batch_csv_preserves_all_preflight_and_pylinac_warnings() -> None:
    """Batch CSV audit warnings retain normalized and non-empty raw messages."""
    result = QAResult(
        success=True,
        analysis_type="acr_ct",
        warnings=["Slice spacing irregular: expected 5.00 mm"],
        errors=[],
        raw_pylinac={
            "num_images": 25,
            "warnings": ["pylinac: low contrast"],
            "ct_module": {"rois": {"Water": 0.1}},
        },
        metrics={"num_images": 25},
    )
    text = build_batch_metrics_csv([result], labels=["Series-A"])
    rows = list(csv.reader(io.StringIO(text)))
    header = rows[0]
    warnings_cell = rows[1][header.index("warnings")]
    assert "Slice spacing irregular" in warnings_cell
    assert "pylinac: low contrast" in warnings_cell
    # Single-run metric CSV must not emit a hollow warnings metric row.
    single_rows = list(csv.reader(io.StringIO(build_metrics_csv(result))))
    single_keys = [row[0] for row in single_rows[1:] if row]
    assert "warnings" not in single_keys


def test_failed_run_empty_raw_pylinac_csv_no_crash() -> None:
    """Failed/empty raw_pylinac still yields provenance CSV rows."""
    result = QAResult(
        success=False,
        analysis_type="acr_mri_large",
        errors=["analyze failed"],
        raw_pylinac={},
        metrics={},
    )
    single = list(csv.reader(io.StringIO(build_metrics_csv(result))))
    assert single[0] == ["metric", "value"]
    assert len(single) == 1  # header only; no metric rows
    batch = list(csv.reader(io.StringIO(build_batch_metrics_csv([result]))))
    assert batch[0][0] == "analysis_type"
    assert batch[1][batch[0].index("success")] == "False"
    assert "analyze failed" in batch[1][batch[0].index("errors")]


def test_metrics_csv_nested_path_denylist() -> None:
    """Denied path keys nested under raw_pylinac must not appear in CSV."""
    result = _acr_result()
    result.raw_pylinac["ct_module"]["analyzed_image_path"] = "/tmp/nested.png"
    keys = [r[0] for r in csv.reader(io.StringIO(build_metrics_csv(result)))]
    assert "ct_module.analyzed_image_path" not in keys
    assert "/tmp/nested.png" not in build_metrics_csv(result)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_PROV_KEYS = [
    "analysis_type",
    "success",
    "pylinac_version",
    "study_uid",
    "series_uid",
    "modality",
    "num_images",
    "label",
    "errors",
    "warnings",
]


def _legacy_metrics_csv(result: QAResult) -> str:
    """Emulate the pre-P1-F2 metrics-only CSV for comparison."""
    from qa.qa_export import flatten_metrics

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["metric", "value"])
    for key, value in flatten_metrics(result.metrics or {}):
        writer.writerow([key, value])
    return buffer.getvalue()

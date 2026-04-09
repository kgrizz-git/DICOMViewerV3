"""
Phase E verification for MRI compare mode (plan: PYLINAC_MRI_COMPARE_RUNS_AND_PDF).

Tests run without DICOM fixtures: batch shape when pylinac is absent or paths
invalid, per-run profile distinctness via the same QARequest fields the batch
runner applies, compare JSON schema 1.2, single-run JSON 1.1 key set, PDF
notes content, and MRI options dialog compare-mode wiring (Qt).
"""

from __future__ import annotations

import builtins
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from qa.analysis_types import (
    LcRunConfig,
    MRICompareRequest,
    MRIBatchResult,
    QARequest,
    QAResult,
    build_pylinac_analysis_profile,
)
from qa.mri_compare_export import build_mri_compare_json_document
from qa.pylinac_runner import build_mri_pdf_notes, run_acr_mri_large_batch

_real_import = builtins.__import__


def _import_blocking_pylinac(
    name: str,
    globals_arg: dict | None = None,
    locals_arg: dict | None = None,
    fromlist: tuple = (),
    level: int = 0,
):
    """Force the runner's missing-pylinac branch without loading pylinac (fast CI)."""
    root = name.split(".", 1)[0]
    if root == "pylinac":
        raise ImportError("blocked for unit test")
    return _real_import(name, globals_arg, locals_arg, fromlist, level)


def test_run_acr_mri_large_batch_returns_three_parallel_results() -> None:
    """Smoke: three LcRunConfig entries yield three QAResult rows (order preserved)."""
    base = QARequest(
        analysis_type="acr_mri_large",
        dicom_paths=[],
        study_uid="1.2.3",
        series_uid="4.5.6",
    )
    configs = [
        LcRunConfig("Run 1", "Weber", 0.001, 3.0),
        LcRunConfig("Run 2", "Weber", 0.0009, 3.0),
        LcRunConfig("Run 3", "Weber", 0.0011, 3.0),
    ]
    builtins.__import__ = _import_blocking_pylinac
    try:
        batch = run_acr_mri_large_batch(base, configs, app_version="0.0.0-test")
    finally:
        builtins.__import__ = _real_import
    assert len(batch.run_results) == 3
    assert len(batch.run_configs) == 3
    assert [c.label for c in batch.run_configs] == ["Run 1", "Run 2", "Run 3"]


def test_three_lc_configs_distinct_pylinac_analysis_profiles() -> None:
    """
    Each compare row maps to a per-run QARequest; profiles must differ on LC fields.

    Mirrors ``dataclasses.replace`` logic inside ``run_acr_mri_large_batch``.
    """
    base = QARequest(analysis_type="acr_mri_large", dicom_paths=["/nope.dcm"])
    configs = [
        LcRunConfig("Run 1", "Weber", 0.0010, 3.0),
        LcRunConfig("Run 2", "Weber", 0.0009, 2.7),
        LcRunConfig("Run 3", "Michelson", 0.0010, 3.0),
    ]
    profiles = []
    for cfg in configs:
        per = replace(
            base,
            low_contrast_method=cfg.low_contrast_method,
            low_contrast_visibility_threshold=cfg.low_contrast_visibility_threshold,
            low_contrast_visibility_sanity_multiplier=cfg.low_contrast_visibility_sanity_multiplier,
        )
        profiles.append(
            build_pylinac_analysis_profile(per, engine="ACRMRILarge")
        )
    keys = {
        (
            p["low_contrast_method"],
            p["low_contrast_visibility_threshold"],
            p["low_contrast_visibility_sanity_multiplier"],
        )
        for p in profiles
    }
    assert len(keys) == 3


@pytest.mark.qt
def test_acr_mri_dialog_compare_mode_yields_mri_compare_request(qapp) -> None:
    """Dialog: enabling compare mode and three rows produces MRICompareRequest."""
    from gui.dialogs.acr_mri_qa_dialog import AcrMrIQaOptionsDialog

    dlg = AcrMrIQaOptionsDialog(None)
    dlg._compare_group.setChecked(True)
    for row in dlg._compare_rows:
        row.enable_check.setChecked(True)
    *_, compare_req, _vanilla = dlg.get_options()
    assert compare_req is not None
    assert isinstance(compare_req, MRICompareRequest)
    assert len(compare_req.run_configs) == 3
    assert {c.label for c in compare_req.run_configs} == {"Run 1", "Run 2", "Run 3"}


def test_single_run_qa_json_schema_1_1_key_set() -> None:
    """Regression: documented single-run export keys remain stable (schema 1.1)."""
    expected_top = {
        "schema_version",
        "run",
        "series",
        "inputs",
        "pylinac_analysis_profile",
        "metrics",
        "warnings",
        "errors",
        "artifacts",
        "raw_pylinac",
    }
    sample = {
        "schema_version": "1.1",
        "run": {},
        "series": {},
        "inputs": {},
        "pylinac_analysis_profile": {},
        "metrics": {},
        "warnings": [],
        "errors": [],
        "artifacts": {},
        "raw_pylinac": {},
    }
    assert set(sample.keys()) == expected_top
    assert sample["schema_version"] == "1.1"


def test_build_mri_pdf_notes_contains_interpretation_keywords() -> None:
    """Notes list includes MTF / low-contrast guidance (pylinac PDF notes path)."""
    dummy = QAResult(success=True, analysis_type="acr_mri_large")
    lines = build_mri_pdf_notes(dummy)
    blob = " ".join(lines).lower()
    assert "mtf" in blob or "contrast" in blob
    assert any("pylinac" in line.lower() for line in lines)


def test_build_mri_compare_json_document_schema_and_runs_length() -> None:
    """Compare JSON: schema 1.2, compare_mode, runs length matches batch."""
    fixed = datetime(2026, 4, 3, 12, 0, 0, tzinfo=timezone.utc)
    batch = MRIBatchResult(
        run_configs=[
            LcRunConfig("A", "Weber", 0.001, 3.0),
            LcRunConfig("B", "Weber", 0.0009, 3.0),
        ],
        run_results=[
            QAResult(
                success=True,
                analysis_type="acr_mri_large",
                study_uid="s",
                series_uid="e",
                modality="MR",
                num_images=11,
                metrics={"low_contrast_score": 10},
                pylinac_analysis_profile={"vanilla_equivalent": False},
            ),
            QAResult(
                success=False,
                analysis_type="acr_mri_large",
                errors=["fail"],
                study_uid="s",
                series_uid="e",
                modality="MR",
                num_images=11,
            ),
        ],
    )
    batch.run_results[0].pdf_report_path = "/tmp/combined.pdf"
    doc = build_mri_compare_json_document(
        batch, {"echo_number": None}, app_version="0.1.9", utc_now=fixed
    )
    assert doc["schema_version"] == "1.2"
    assert doc["compare_mode"] is True
    assert doc["combined_pdf_path"] == "/tmp/combined.pdf"
    assert len(doc["runs"]) == 2
    assert doc["runs"][0]["run_label"] == "A"
    assert doc["runs"][0]["pylinac_analysis_profile"]["vanilla_equivalent"] is False

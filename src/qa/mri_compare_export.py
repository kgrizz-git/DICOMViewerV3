"""
Compare-mode ACR MRI QA JSON export (schema 1.2).

Builds the serializable dict written by the compare-results flow in ``main.py``.
Kept in ``qa/`` so tests can assert structure without a GUI or file I/O.

Inputs:
    ``MRIBatchResult`` from ``run_acr_mri_large_batch``, optional top-level
    ``inputs`` dict, and ``app_version`` string.

Outputs:
    A ``dict`` suitable for ``json.dump`` with ``schema_version`` ``"1.2"``,
    ``compare_mode`` true, ``combined_pdf_path``, and a ``runs`` array.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from qa.analysis_types import MRIBatchResult


def build_mri_compare_json_document(
    batch: MRIBatchResult,
    inputs: Optional[Dict[str, Any]],
    *,
    app_version: str,
    utc_now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Assemble the compare-mode QA JSON payload (schema 1.2).

    Args:
        batch: Parallel ``run_configs`` and ``run_results``.
        inputs: Optional dict merged at top level (dialog-derived inputs).
        app_version: Application version string for each run block.
        utc_now: Optional fixed timestamp for tests; default is current UTC.

    Returns:
        Dictionary with schema_version, compare_mode, inputs, combined_pdf_path, runs.
    """
    now = utc_now if utc_now is not None else datetime.now(timezone.utc)
    iso = now.isoformat()

    runs_data: List[Dict[str, Any]] = []
    for cfg, result in zip(batch.run_configs, batch.run_results):
        prof = result.pylinac_analysis_profile or {}
        runs_data.append(
            {
                "run_label": cfg.label,
                "run_config": {
                    "low_contrast_method": cfg.low_contrast_method,
                    "low_contrast_visibility_threshold": cfg.low_contrast_visibility_threshold,
                    "low_contrast_visibility_sanity_multiplier": cfg.low_contrast_visibility_sanity_multiplier,
                },
                "run": {
                    "timestamp_utc": iso,
                    "app_version": app_version,
                    "pylinac_version": result.pylinac_version or "",
                    "analysis_type": result.analysis_type,
                    "status": "success" if result.success else "failed",
                    "vanilla_pylinac": bool(prof.get("vanilla_pylinac", False)),
                },
                "series": {
                    "study_uid": result.study_uid,
                    "series_uid": result.series_uid,
                    "modality": result.modality,
                    "num_images": result.num_images,
                },
                "pylinac_analysis_profile": result.pylinac_analysis_profile or {},
                "metrics": result.metrics,
                "warnings": result.warnings,
                "errors": result.errors,
                "artifacts": {"pdf_report_path": result.pdf_report_path or ""},
            }
        )

    combined_pdf_path = ""
    if batch.run_results and batch.run_results[0].pdf_report_path:
        combined_pdf_path = batch.run_results[0].pdf_report_path or ""

    return {
        "schema_version": "1.2",
        "compare_mode": True,
        "inputs": inputs or {},
        "combined_pdf_path": combined_pdf_path,
        "runs": runs_data,
    }

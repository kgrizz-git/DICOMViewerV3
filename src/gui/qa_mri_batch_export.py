"""
Save-dialog helpers for a finished ACR MRI Large batch (XLSX, JSON, CSV).

``QAAppFacade`` stays the public slot owner; these functions hold the prompt,
extension, and write steps so the facade does not grow past its grandfathered
line cap. Callers pass the app for ``_prompt_save_path`` and status updates.

Inputs:
    - App duck-type with ``_prompt_save_path`` and ``main_window.update_status``.
    - ``ACRMBatchResult`` with parallel ``run_results`` / ``run_labels``.

Outputs:
    - A file on disk when the user confirms a path; no-op on cancel.

Requirements:
    - ``qa.qa_export`` / ``qa.qa_xlsx_export``; UTF-8 text for JSON/CSV.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from qa.analysis_types import ACRMBatchResult
from qa.qa_export import build_batch_metrics_csv, build_single_run_document
from qa.qa_xlsx_export import build_qa_workbook
from version import __version__ as APP_VERSION

_UTC_TIMESTAMP_FMT = "%Y%m%dT%H%M%SZ"


def _timestamp() -> str:
    """UTC stamp used in default batch export filenames."""
    return datetime.now(UTC).strftime(_UTC_TIMESTAMP_FMT)


def save_mri_batch_xlsx(app: Any, batch: ACRMBatchResult) -> None:
    """
    Offer XLSX export for a finished ACR MRI Large batch (OQ-9 workbook).

    Args:
        app: Host with ``_prompt_save_path`` and ``main_window.update_status``.
        batch: Completed batch; Summary rows follow ``run_labels``.
    """
    timestamp = _timestamp()
    path = app._prompt_save_path(
        "Save QA Batch Results XLSX",
        f"qa-acr-mri-batch-{timestamp}.xlsx",
        "Excel Files (*.xlsx)",
        remember_pylinac_output_dir=True,
    )
    if not path:
        return
    if not path.lower().endswith(".xlsx"):
        path = f"{path}.xlsx"
    workbook = build_qa_workbook(
        batch.run_results, labels=batch.run_labels, app_version=APP_VERSION
    )
    workbook.save(path)
    app.main_window.update_status(f"Saved QA batch XLSX: {path}")


def save_mri_batch_json(app: Any, batch: ACRMBatchResult) -> None:
    """
    Offer JSON export for a finished ACR MRI Large batch.

    Emits a JSON array of per-run ``build_single_run_document`` documents
    (schema_version "1.1" each). There is no dedicated batch JSON schema for
    ACR MRI, so a list wrapper stays lossless.

    Args:
        app: Host with ``_prompt_save_path`` and ``main_window.update_status``.
        batch: Completed batch; ``series_label`` is stored per document.
    """
    timestamp = _timestamp()
    json_path = app._prompt_save_path(
        "Save QA Batch Results JSON",
        f"qa-acr-mri-batch-{timestamp}.json",
        "JSON Files (*.json)",
        remember_pylinac_output_dir=True,
    )
    if not json_path:
        return
    if not json_path.lower().endswith(".json"):
        json_path = f"{json_path}.json"
    payload = [
        build_single_run_document(
            result, app_version=APP_VERSION, inputs={"series_label": label}
        )
        for label, result in zip(batch.run_labels, batch.run_results, strict=True)
    ]
    with open(json_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    app.main_window.update_status(f"Saved QA batch JSON: {json_path}")


def save_mri_batch_csv(app: Any, batch: ACRMBatchResult) -> None:
    """
    Offer CSV export for a finished ACR MRI Large batch (full flatten, one row per series).

    Args:
        app: Host with ``_prompt_save_path`` and ``main_window.update_status``.
        batch: Completed batch; labels become the provenance ``label`` column.
    """
    timestamp = _timestamp()
    path = app._prompt_save_path(
        "Save QA Batch Results CSV",
        f"qa-acr-mri-batch-{timestamp}.csv",
        "CSV Files (*.csv)",
        remember_pylinac_output_dir=True,
    )
    if not path:
        return
    if not path.lower().endswith(".csv"):
        path = f"{path}.csv"
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(
            build_batch_metrics_csv(batch.run_results, labels=batch.run_labels)
        )
    app.main_window.update_status(f"Saved QA batch CSV: {path}")

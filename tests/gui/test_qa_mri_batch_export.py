"""Focused tests for ACR MRI Large batch export helpers (P4-M4).

Mirrors ``tests/gui/test_qa_app_facade_ct_batch_csv.py`` for the MRI batch
path: CSV uses ``build_batch_metrics_csv`` (full flatten), XLSX builds a
``build_qa_workbook`` from ``ACRMBatchResult.run_results``, JSON emits the
per-run document array. No live ``analyze()`` runs; save paths are mocked.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from gui.qa_mri_batch_export import (
    save_mri_batch_csv,
    save_mri_batch_json,
    save_mri_batch_xlsx,
)
from qa.analysis_types import ACRMBatchResult, QAResult


def _app(save_path: str = "") -> SimpleNamespace:
    return SimpleNamespace(
        main_window=MagicMock(),
        _prompt_save_path=MagicMock(return_value=save_path),
    )


def _batch() -> ACRMBatchResult:
    r0 = QAResult(
        success=True,
        analysis_type="acr_mri_large",
        metrics={"low_contrast_score": 42.5},
    )
    r1 = QAResult(
        success=True,
        analysis_type="acr_mri_large",
        metrics={"low_contrast_score": 10.0},
    )
    return ACRMBatchResult(run_results=[r0, r1], run_labels=["S1", "S2"])


def test_export_mri_batch_csv_writes_file_and_updates_status(tmp_path) -> None:
    output = tmp_path / "qa-acr-mri-batch.csv"
    app = _app(str(output))

    save_mri_batch_csv(app, _batch())

    text = output.read_text(encoding="utf-8")
    header = text.splitlines()[0]
    assert "label" in header
    assert "S1" in text
    assert "S2" in text
    assert "low_contrast_score" in text
    app.main_window.update_status.assert_called_once_with(f"Saved QA batch CSV: {output}")


def test_export_mri_batch_csv_appends_extension(tmp_path) -> None:
    output = tmp_path / "no-ext"
    app = _app(str(output))
    save_mri_batch_csv(app, _batch())
    assert (tmp_path / "no-ext.csv").is_file()


def test_export_mri_batch_csv_cancels_when_no_path() -> None:
    app = _app("")
    save_mri_batch_csv(app, _batch())
    app.main_window.update_status.assert_not_called()


def test_export_mri_batch_json_writes_document_array(tmp_path) -> None:
    output = tmp_path / "qa-acr-mri-batch.json"
    app = _app(str(output))

    save_mri_batch_json(app, _batch())

    import json

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert isinstance(payload, list)
    assert len(payload) == 2
    assert payload[0]["run"]["analysis_type"] == "acr_mri_large"
    assert payload[0]["inputs"]["series_label"] == "S1"
    assert payload[1]["inputs"]["series_label"] == "S2"
    app.main_window.update_status.assert_called_once_with(f"Saved QA batch JSON: {output}")


def test_export_mri_batch_json_cancels_when_no_path() -> None:
    app = _app("")
    save_mri_batch_json(app, _batch())
    app.main_window.update_status.assert_not_called()


def test_export_mri_batch_xlsx_builds_workbook(tmp_path) -> None:
    """XLSX export builds a workbook from run_results (OQ-9 Images sheet path)."""
    output = tmp_path / "qa-acr-mri-batch.xlsx"
    app = _app(str(output))

    save_mri_batch_xlsx(app, _batch())

    assert output.is_file()
    app.main_window.update_status.assert_called_once_with(f"Saved QA batch XLSX: {output}")


def test_export_mri_batch_xlsx_cancels_when_no_path() -> None:
    app = _app("")
    save_mri_batch_xlsx(app, _batch())
    app.main_window.update_status.assert_not_called()


def test_csv_no_path_leak(tmp_path) -> None:
    """CSV flatten never emits denylisted analyzed_image_path or module images."""
    r = QAResult(
        success=True,
        analysis_type="acr_mri_large",
        metrics={"low_contrast_score": 1.0},
        analyzed_image_path="/secret/image.png",
        analyzed_module_images={"hu": "/secret/modules/hu.png"},
    )
    batch = ACRMBatchResult(run_results=[r], run_labels=["S1"])
    output = tmp_path / "qa-acr-mri-batch.csv"
    app = _app(str(output))

    save_mri_batch_csv(app, batch)

    text = output.read_text(encoding="utf-8")
    assert "/secret/image.png" not in text
    assert "/secret/modules/hu.png" not in text
    assert "analyzed_image_path" not in text
    assert "analyzed_module_images" not in text

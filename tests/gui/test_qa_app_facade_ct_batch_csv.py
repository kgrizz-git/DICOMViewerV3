"""Focused QA facade test for ACR CT batch CSV export (P3-C1)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from gui.qa_app_facade import QAAppFacade
from qa.analysis_types import CTBatchResult, QAResult


def _app(save_path: str = "") -> SimpleNamespace:
    return SimpleNamespace(
        main_window=MagicMock(),
        _prompt_save_path=MagicMock(return_value=save_path),
    )


def _batch() -> CTBatchResult:
    r0 = QAResult(
        success=True,
        analysis_type="acr_ct",
        metrics={"score": 1},
    )
    r1 = QAResult(
        success=True,
        analysis_type="acr_ct",
        metrics={"score": 2},
    )
    return CTBatchResult(run_results=[r0, r1], run_labels=["S1", "S2"])


def test_export_ct_batch_csv_writes_file_and_updates_status(tmp_path) -> None:
    output = tmp_path / "qa-acr-ct-batch.csv"
    app = _app(str(output))

    QAAppFacade(app).export_ct_batch_csv(_batch())

    text = output.read_text(encoding="utf-8")
    header = text.splitlines()[0]
    assert "label" in header
    assert "S1" in text
    assert "S2" in text
    assert "score" in text
    app.main_window.update_status.assert_called_once_with(f"Saved QA batch CSV: {output}")


def test_export_ct_batch_csv_appends_extension(tmp_path) -> None:
    output = tmp_path / "no-ext"
    app = _app(str(output))
    QAAppFacade(app).export_ct_batch_csv(_batch())
    assert (tmp_path / "no-ext.csv").is_file()


def test_export_ct_batch_csv_cancels_when_no_path() -> None:
    app = _app("")
    QAAppFacade(app).export_ct_batch_csv(_batch())
    app.main_window.update_status.assert_not_called()

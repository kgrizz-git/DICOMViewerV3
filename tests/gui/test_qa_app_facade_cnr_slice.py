"""Focused tests for QAAppFacade CNR summary formatting (no MainWindow)."""

from __future__ import annotations

from types import SimpleNamespace

from gui.qa_app_facade import QAAppFacade
from qa.analysis_types import QAResult


def test_format_cnr_summary_empty_when_no_metrics() -> None:
    facade = QAAppFacade(SimpleNamespace())
    result = QAResult(success=True, analysis_type="acr_ct", metrics={})
    assert facade._format_low_contrast_cnr_summary(result) == ""


def test_format_cnr_summary_includes_intermediates() -> None:
    facade = QAAppFacade(SimpleNamespace())
    result = QAResult(
        success=True,
        analysis_type="acr_ct",
        metrics={
            "low_contrast_cnr": {
                "object_rois": [{"mean": 10.0}, {"mean": 14.0}],
                "background_mean": 2.0,
                "background_std": 1.5,
                "cnr": 4.0,
            }
        },
    )
    text = facade._format_low_contrast_cnr_summary(result)
    assert "CNR intermediates" in text
    assert "CNR: 4.00" in text
    assert "Object ROI mean: 12.00" in text  # mean of 10 and 14

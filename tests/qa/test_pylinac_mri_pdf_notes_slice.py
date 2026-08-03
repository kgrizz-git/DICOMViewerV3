"""Tests for MRI PDF note builders (no real patient PDFs)."""

from __future__ import annotations

from qa.analysis_types import LcRunConfig, MRIBatchResult, QAResult
from qa.pylinac_mri_pdf import build_mri_compare_pdf_notes, build_mri_pdf_notes


def test_build_mri_pdf_notes_includes_doc_link() -> None:
    result = QAResult(success=True, analysis_type="acr_mri_large", metrics={})
    notes = build_mri_pdf_notes(result)
    assert isinstance(notes, list)
    assert notes
    assert any("pylinac" in n.lower() or "http" in n.lower() for n in notes)


def test_build_mri_compare_pdf_notes_lists_runs() -> None:
    batch = MRIBatchResult(
        run_configs=[
            LcRunConfig("Run A", "Weber", 0.001, 3.0),
            LcRunConfig("Run B", "Michelson", 0.0009, 2.5),
        ],
        run_results=[
            QAResult(success=True, analysis_type="acr_mri_large", metrics={"low_contrast_score": 10}),
            QAResult(success=False, analysis_type="acr_mri_large", metrics={}, errors=["x"]),
        ],
    )
    notes = build_mri_compare_pdf_notes(batch)
    assert isinstance(notes, list)
    text = "\n".join(notes)
    assert "Run A" in text
    assert "Run B" in text
    assert "score=10" in text
    assert "score=FAILED" in text

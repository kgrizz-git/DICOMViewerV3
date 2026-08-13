"""Synthetic-file tests for ACR MRI compare-report helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from pypdf import PdfReader, PdfWriter

from qa.analysis_types import LcRunConfig, MRIBatchResult, QARequest, QAResult
from qa.pylinac_mri_pdf import (
    _write_per_run_temp_pdf,
    assemble_mri_compare_pdf,
    build_mri_compare_summary_pdf,
)


def _batch() -> MRIBatchResult:
    return MRIBatchResult(
        run_configs=[
            LcRunConfig("Synthetic A", "Weber", 0.001, 3.0),
            LcRunConfig("Synthetic B", "Michelson", 0.002, 2.5),
        ],
        run_results=[
            QAResult(
                success=True,
                analysis_type="acr_mri_large",
                metrics={"low_contrast_score": 11},
                pylinac_version="synthetic",
            ),
            QAResult(success=False, analysis_type="acr_mri_large", errors=["synthetic"]),
        ],
    )


def _blank_pdf(path: Path) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    with path.open("wb") as stream:
        writer.write(stream)


def test_write_per_run_temp_pdf_passes_compact_settings_notes(tmp_path: Path) -> None:
    analyzer = MagicMock()
    target = tmp_path / "per-run.pdf"
    config = _batch().run_configs[0]

    returned = _write_per_run_temp_pdf(analyzer, target, "Run 1", config)

    assert returned == target
    analyzer.publish_pdf.assert_called_once()
    assert analyzer.publish_pdf.call_args.args == (str(target),)
    notes = analyzer.publish_pdf.call_args.kwargs["notes"]
    assert len(notes) == 4
    assert "Weber" in notes[0]
    assert "0.001000" in notes[1]


def test_write_per_run_temp_pdf_returns_none_when_publish_fails(tmp_path: Path) -> None:
    analyzer = MagicMock()
    analyzer.publish_pdf.side_effect = RuntimeError("synthetic failure")

    assert _write_per_run_temp_pdf(analyzer, tmp_path / "run.pdf", "Run 1", _batch().run_configs[0]) is None


def test_summary_pdf_contains_a_readable_synthetic_compare_page(tmp_path: Path) -> None:
    output = tmp_path / "summary.pdf"
    request = QARequest(
        analysis_type="acr_mri_large",
        dicom_paths=["synthetic-a.dcm", "synthetic-b.dcm"],
        study_uid="1.2.3",
        series_uid="1.2.3.4",
    )

    build_mri_compare_summary_pdf(_batch(), output, base_request=request, app_version="test")

    reader = PdfReader(str(output))
    assert len(reader.pages) == 1
    page_text = reader.pages[0].extract_text()
    assert "ACR MRI Large" in page_text
    assert "Low-Contrast Compare Mode" in page_text
    assert "Synthetic A" in page_text
    assert "Synthetic B" in page_text


def test_assemble_merges_available_inputs_and_removes_temporary_files(tmp_path: Path) -> None:
    summary = tmp_path / "summary.pdf"
    run = tmp_path / "run.pdf"
    output = tmp_path / "combined.pdf"
    _blank_pdf(summary)
    _blank_pdf(run)

    assert assemble_mri_compare_pdf(summary, [run, None], output) is True
    assert len(PdfReader(str(output)).pages) == 2
    assert summary.exists() is False
    assert run.exists() is False


def test_assemble_returns_false_when_no_input_pdf_exists(tmp_path: Path) -> None:
    assert assemble_mri_compare_pdf(tmp_path / "missing.pdf", [None], tmp_path / "out.pdf") is False

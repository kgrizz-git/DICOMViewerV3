"""
Qt worker for running QA analysis off the GUI thread.
"""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from qa.analysis_types import QARequest, QAResult
from qa.pylinac_runner import run_acr_ct_analysis, run_acr_mri_large_analysis


class QAAnalysisWorker(QThread):
    """Runs Stage 1 QA analysis and emits a normalized result."""

    result_ready = Signal(object)  # QAResult

    def __init__(self, request: QARequest):
        super().__init__()
        self.request = request

    def run(self) -> None:
        result: QAResult
        if self.request.analysis_type == "acr_ct":
            result = run_acr_ct_analysis(self.request)
        elif self.request.analysis_type == "acr_mri_large":
            result = run_acr_mri_large_analysis(self.request)
        else:
            result = QAResult(
                success=False,
                analysis_type=self.request.analysis_type,
                errors=[f"Unsupported analysis type: {self.request.analysis_type}"],
            )
        if self.request.preflight_warnings:
            merged = list(self.request.preflight_warnings)
            for w in result.warnings:
                if w and w not in merged:
                    merged.append(w)
            result.warnings = merged
        self.result_ready.emit(result)


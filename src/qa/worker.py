"""
Qt workers for running QA analysis off the GUI thread.

Classes:
    QAAnalysisWorker  -- single-run worker; emits result_ready(QAResult)
    QABatchWorker     -- compare-mode worker; emits batch_result_ready(MRIBatchResult)

Both workers accept a QARequest as their base payload.  QABatchWorker also
receives an MRICompareRequest and uses run_acr_mri_large_batch() to produce
one QAResult per enabled LcRunConfig row.
"""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from qa.analysis_types import (
    MRIBatchResult,
    MRICompareRequest,
    QARequest,
    QAResult,
    build_pylinac_analysis_profile,
)
from qa.pylinac_runner import (
    run_acr_ct_analysis,
    run_acr_mri_large_analysis,
    run_acr_mri_large_batch,
)


class QAAnalysisWorker(QThread):
    """
    Runs a single Stage 1 QA analysis and emits a normalized result.

    Signals:
        result_ready(QAResult): emitted when the analysis finishes (success or
            failure).  Connect before calling start().
    """

    result_ready = Signal(object)  # QAResult

    def __init__(self, request: QARequest) -> None:
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
                pylinac_analysis_profile=build_pylinac_analysis_profile(
                    self.request, engine="(unsupported analysis_type)"
                ),
            )
        if self.request.preflight_warnings:
            merged = list(self.request.preflight_warnings)
            for w in result.warnings:
                if w and w not in merged:
                    merged.append(w)
            result.warnings = merged
        self.result_ready.emit(result)


class QABatchWorker(QThread):
    """
    Runs a multi-run ACR MRI Large compare-mode batch and emits results.

    Runs one pylinac analysis per enabled LcRunConfig in the MRICompareRequest.
    The analyzer is re-instantiated for each run (see run_acr_mri_large_batch).

    After all runs finish, a combined PDF is assembled if an output PDF path
    was provided on the base request.  The combined PDF path is stored in
    batch.run_results[0].pdf_report_path.

    Signals:
        batch_result_ready(MRIBatchResult): emitted when all runs finish.
            Individual runs may have succeeded or failed independently.
    """

    batch_result_ready = Signal(object)  # MRIBatchResult

    def __init__(
        self,
        base_request: QARequest,
        compare_request: MRICompareRequest,
        *,
        app_version: str = "",
    ) -> None:
        """
        Args:
            base_request: QARequest with DICOM source, echo, scan-extent, and
                other shared options.  LC fields are overridden per run.
            compare_request: MRICompareRequest carrying the per-run LcRunConfig
                list (1–3 entries).
            app_version: Application version string embedded in the summary PDF.
        """
        super().__init__()
        self.base_request = base_request
        self.compare_request = compare_request
        self.app_version = app_version

    def run(self) -> None:
        batch = run_acr_mri_large_batch(
            self.base_request,
            self.compare_request.run_configs,
            app_version=self.app_version,
        )
        # Merge any preflight warnings into every run result
        if self.base_request.preflight_warnings:
            preflight = list(self.base_request.preflight_warnings)
            for result in batch.run_results:
                merged = list(preflight)
                for w in result.warnings:
                    if w and w not in merged:
                        merged.append(w)
                result.warnings = merged
        self.batch_result_ready.emit(batch)

"""
Qt workers for running QA analysis off the GUI thread.

Classes:
    QAAnalysisWorker  -- single-run worker; emits result_ready(QAResult)
    QABatchWorker     -- compare-mode worker; emits batch_result_ready(MRIBatchResult)
    QACTBatchWorker   -- multi-series ACR CT worker; emits batch_result_ready(CTBatchResult)

Both QAAnalysisWorker/QABatchWorker accept a QARequest as their base payload.
QABatchWorker also receives an MRICompareRequest and uses
run_acr_mri_large_batch() to produce one QAResult per enabled LcRunConfig row.

QACTBatchWorker runs run_acr_ct_analysis() serially, once per selected series
(see PYLINAC_CT_CNR_BATCH_XLSX_PLAN.md Feature 2). It deliberately does not
hold an organizer/app reference -- it runs off the GUI thread, and display
labels are resolved on the GUI thread by the selection dialog and passed in
parallel to the requests.
"""

from __future__ import annotations

import dataclasses
import os
import tempfile
import uuid
import warnings

# Suppress known-noisy FutureWarnings from pylinac using deprecated scikit-image
# RegionProperties attribute names (filled_area → area_filled, bbox_area → area_bbox).
# These are upstream bugs in pylinac; they do not affect analysis results.
warnings.filterwarnings("ignore", category=FutureWarning, message=r".*filled_area.*", module=r"pylinac.*")
warnings.filterwarnings("ignore", category=FutureWarning, message=r".*bbox_area.*", module=r"pylinac.*")
# Suppress matplotlib's complaint about plt.subplots() being called from this QThread.
# Pylinac uses matplotlib only to generate PDF figures, not interactive displays, so
# the warning is harmless.
warnings.filterwarnings("ignore", category=UserWarning, message=r".*Starting a Matplotlib GUI outside of the main thread.*")

from PySide6.QtCore import QThread, Signal

from qa.analysis_types import (
    CTBatchResult,
    MRICompareRequest,
    QARequest,
    QAResult,
    build_pylinac_analysis_profile,
)
from qa.pylinac_runner import (
    NUCLEAR_ANALYSIS_TYPES,
    run_acr_ct_analysis,
    run_acr_mri_large_analysis,
    run_acr_mri_large_batch,
    run_nuclear_analysis,
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
        elif self.request.analysis_type in NUCLEAR_ANALYSIS_TYPES:
            result = run_nuclear_analysis(self.request)
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


class QACTBatchWorker(QThread):
    """
    Runs a multi-series ACR CT (pylinac) batch, one series at a time.

    Serial execution (see PYLINAC_CT_CNR_BATCH_XLSX_PLAN.md Feature 2):
    process-based parallelism would be the only *safe* concurrency (pylinac
    drives matplotlib's global pyplot state, and thread-based parallelism is
    GIL-bound anyway), but a process pool multiplies peak RAM and adds
    packaging/cancellation complexity that outweighs the wall-clock win at
    typical batch sizes.

    Does NOT hold an ``organizer`` reference -- it runs off the GUI thread;
    the selection dialog resolves display labels on the GUI thread and passes
    them in, parallel to ``requests``.

    Batch image temp-dir ownership: this worker owns a single
    ``tempfile.TemporaryDirectory`` for the whole batch (created in
    ``__init__``, mirroring how the single-run facade owns its temp dir until
    after ``workbook.save()`` -- see ``QAAppFacade.open_acr_ct_phantom_analysis``
    / ``start_qa_worker``). Before running each request, the worker assigns it
    a unique PNG path inside that directory via
    ``request.analyzed_image_out_path`` so ``run_acr_ct_analysis`` can save the
    analyzed image (see ``QARequest.analyzed_image_out_path``). The directory
    is exposed as ``self.image_temp_dir`` and is intentionally NOT cleaned up
    by this worker -- the facade must keep it alive until the batch result
    dialog's XLSX export has run, then call ``image_temp_dir.cleanup()``
    (same pattern as ``start_qa_worker``'s ``analyzed_image_temp_dir``).

    P2-I3: when any request has ``embed_module_images_in_xlsx`` True, the worker
    also creates a sibling ``module_images_temp_dir`` (prefix
    ``qa-ct-batch-module-images-``) and assigns each cloned request a
    **per-series subdirectory** so pylinac's fixed ``hu.png`` / ``mtf.png``
    names cannot overwrite another series. The facade cleans up
    ``module_images_temp_dir`` alongside ``image_temp_dir`` when the batch
    result dialog is destroyed. When no request requests embed, no
    module-images dir is created.

    Signals:
        series_completed(int done, int total, object QAResult): emitted after
            each series finishes (success or failure), to drive N-of-M
            progress.
        batch_result_ready(object CTBatchResult): emitted once, after all
            series finish or the batch is cancelled (partial result).
    """

    series_completed = Signal(int, int, object)  # done, total, QAResult
    batch_result_ready = Signal(object)  # CTBatchResult

    def __init__(
        self,
        requests: list[QARequest],
        series_labels: list[str],
        *,
        app_version: str = "",
    ) -> None:
        """
        Args:
            requests: One QARequest per selected series (analysis_type
                "acr_ct"), in selection order.
            series_labels: Display label per request, parallel to
                ``requests``. Built on the GUI thread (organizer access) by
                the selection dialog; appended to ``CTBatchResult.run_labels``
                only when the corresponding result is collected.
            app_version: Reserved for parity with QABatchWorker; unused today
                (ACR CT batch has no combined-PDF/summary-PDF step).
        """
        super().__init__()
        if len(series_labels) != len(requests):
            raise ValueError("series_labels must be parallel to requests (same length)")
        self.requests = requests
        self.series_labels = series_labels
        self.app_version = app_version
        self._cancelled = False
        # Worker-owned temp dir for analyzed-image PNGs (see class docstring).
        # The facade is responsible for calling cleanup() once the batch
        # result has been consumed (result dialog shown + XLSX export done).
        self.image_temp_dir = tempfile.TemporaryDirectory(prefix="qa-ct-batch-image-")
        # P2-I3: module-images temp dir for per-module PNGs. Created when any
        # request requests embed; None when embed is off for all requests.
        if any(getattr(req, "embed_module_images_in_xlsx", True) for req in requests):
            self.module_images_temp_dir: tempfile.TemporaryDirectory[str] | None = (
                tempfile.TemporaryDirectory(prefix="qa-ct-batch-module-images-")
            )
        else:
            self.module_images_temp_dir = None

    def cancel(self) -> None:
        """Request cooperative cancellation; checked between series."""
        self._cancelled = True

    def run(self) -> None:
        total = len(self.requests)
        run_results: list[QAResult] = []
        run_labels: list[str] = []
        for index, (request, label) in enumerate(
            zip(self.requests, self.series_labels, strict=True)
        ):
            if self._cancelled:
                # Cooperative cancellation: skip remaining series, emit the
                # partial batch collected so far.
                break
            module_out: str | None = None
            if self.module_images_temp_dir is not None:
                module_out = os.path.join(
                    self.module_images_temp_dir.name, uuid.uuid4().hex
                )
                os.makedirs(module_out, exist_ok=True)
            cloned_request = dataclasses.replace(
                request,
                analyzed_image_out_path=os.path.join(
                    self.image_temp_dir.name, f"{uuid.uuid4().hex}.png"
                ),
                module_images_out_dir=module_out,
            )
            try:
                result = run_acr_ct_analysis(cloned_request)
            except Exception as exc:
                # Per-series error isolation: a failure here (e.g. a
                # malformed request) must not abort the rest of the batch.
                result = QAResult(
                    success=False,
                    analysis_type=request.analysis_type,
                    errors=[f"ACR CT batch series failed: {exc}"],
                    study_uid=request.study_uid,
                    series_uid=request.series_uid,
                    modality=request.modality,
                    pylinac_analysis_profile=build_pylinac_analysis_profile(
                        request, engine="(batch series error)"
                    ),
                )
            if request.preflight_warnings:
                merged = list(request.preflight_warnings)
                for w in result.warnings:
                    if w and w not in merged:
                        merged.append(w)
                result.warnings = merged
            run_results.append(result)
            run_labels.append(label)
            self.series_completed.emit(index + 1, total, result)
        batch = CTBatchResult(run_results=run_results, run_labels=run_labels)
        self.batch_result_ready.emit(batch)

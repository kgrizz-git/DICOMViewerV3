"""
Stage 1 pylinac runner entrypoints.

The GUI should call this module (via a worker) instead of importing pylinac
directly. This keeps pylinac optional and allows graceful error handling when
the dependency is missing.
"""

from __future__ import annotations

import inspect
from typing import Any, Dict, Optional

from qa.analysis_types import QARequest, QAResult


def _jsonable(value: Any) -> Any:
    """Best-effort conversion to JSON-friendly primitives."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    return str(value)


def _image_count(analyzer: Any, request: QARequest) -> int:
    n = len(request.dicom_paths)
    stack = getattr(analyzer, "dicom_stack", None)
    if stack is not None:
        try:
            return int(len(stack))
        except Exception:
            pass
    return n


def run_acr_ct_analysis(request: QARequest) -> QAResult:
    """
    Run ACR CT analysis through pylinac with normalized output.

    Args:
        request: Normalized request payload from UI/worker.

    Returns:
        QAResult with success/failure details and normalized payload.
    """
    try:
        from pylinac import ACRCT  # type: ignore[import-not-found]
        import pylinac  # type: ignore[import-not-found]
    except Exception:
        return QAResult(
            success=False,
            analysis_type=request.analysis_type,
            errors=[
                "pylinac is not installed. Install required dependencies and retry."
            ],
            study_uid=request.study_uid,
            series_uid=request.series_uid,
            modality=request.modality,
            num_images=len(request.dicom_paths),
        )

    try:
        if request.dicom_paths:
            analyzer = ACRCT(request.dicom_paths)
        elif request.folder_path:
            analyzer = ACRCT.from_folder(request.folder_path)
        else:
            return QAResult(
                success=False,
                analysis_type=request.analysis_type,
                errors=["No DICOM paths or folder were provided."],
                study_uid=request.study_uid,
                series_uid=request.series_uid,
                modality=request.modality,
                pylinac_version=getattr(pylinac, "__version__", None),
            )

        analyze_kwargs: Dict[str, Any] = {}
        if request.origin_slice is not None:
            analyze_kwargs["origin_slice"] = int(request.origin_slice)
        analyzer.analyze(**analyze_kwargs)

        raw: Dict[str, Any] = {}
        try:
            rd = analyzer.results_data()
            if isinstance(rd, dict):
                raw = _jsonable(rd)
            else:
                raw = {"results_data": _jsonable(rd)}
        except Exception:
            raw = {}

        pdf_report_path: Optional[str] = None
        if request.output_pdf_path:
            try:
                analyzer.publish_pdf(request.output_pdf_path)
                pdf_report_path = request.output_pdf_path
            except Exception:
                pdf_report_path = None

        num_images = _image_count(analyzer, request)
        metrics: Dict[str, Any] = {
            "input_count": len(request.dicom_paths),
            "origin_slice_override": request.origin_slice,
        }
        for key in ("num_images", "phantom_roll", "catphan_model", "origin_slice"):
            if key in raw:
                metrics[key] = raw[key]

        return QAResult(
            success=True,
            analysis_type=request.analysis_type,
            metrics=metrics,
            warnings=[],
            errors=[],
            raw_pylinac=raw,
            pdf_report_path=pdf_report_path,
            study_uid=request.study_uid,
            series_uid=request.series_uid,
            modality=request.modality,
            num_images=num_images,
            pylinac_version=getattr(pylinac, "__version__", None),
        )
    except Exception as exc:
        return QAResult(
            success=False,
            analysis_type=request.analysis_type,
            errors=[f"ACR CT analysis failed: {exc}"],
            study_uid=request.study_uid,
            series_uid=request.series_uid,
            modality=request.modality,
            num_images=len(request.dicom_paths),
            pylinac_version=getattr(pylinac, "__version__", None),
        )


def run_acr_mri_large_analysis(request: QARequest) -> QAResult:
    """
    Run ACR MRI Large analysis through pylinac with normalized output.

    Args:
        request: Normalized request payload from UI/worker.

    Returns:
        QAResult with success/failure details and normalized payload.
    """
    try:
        from pylinac import ACRMRILarge  # type: ignore[import-not-found]
        import pylinac  # type: ignore[import-not-found]
    except Exception:
        return QAResult(
            success=False,
            analysis_type=request.analysis_type,
            errors=[
                "pylinac is not installed. Install required dependencies and retry."
            ],
            study_uid=request.study_uid,
            series_uid=request.series_uid,
            modality=request.modality,
            num_images=len(request.dicom_paths),
        )

    try:
        if request.dicom_paths:
            analyzer = ACRMRILarge(request.dicom_paths)
        elif request.folder_path:
            analyzer = ACRMRILarge.from_folder(request.folder_path)
        else:
            return QAResult(
                success=False,
                analysis_type=request.analysis_type,
                errors=["No DICOM paths or folder were provided."],
                study_uid=request.study_uid,
                series_uid=request.series_uid,
                modality=request.modality,
                pylinac_version=getattr(pylinac, "__version__", None),
            )

        analyze_sig = inspect.signature(analyzer.analyze)
        analyze_kwargs: Dict[str, Any] = {}
        if "echo_number" in analyze_sig.parameters:
            analyze_kwargs["echo_number"] = request.echo_number
        if "check_uid" in analyze_sig.parameters:
            analyze_kwargs["check_uid"] = request.check_uid
        if request.origin_slice is not None and "origin_slice" in analyze_sig.parameters:
            analyze_kwargs["origin_slice"] = int(request.origin_slice)

        analyzer.analyze(**analyze_kwargs)

        raw: Dict[str, Any] = {}
        try:
            rd = analyzer.results_data()
            if isinstance(rd, dict):
                raw = _jsonable(rd)
            else:
                raw = {"results_data": _jsonable(rd)}
        except Exception:
            raw = {}

        pdf_report_path: Optional[str] = None
        if request.output_pdf_path:
            try:
                analyzer.publish_pdf(request.output_pdf_path)
                pdf_report_path = request.output_pdf_path
            except Exception:
                pdf_report_path = None

        num_images = _image_count(analyzer, request)
        metrics: Dict[str, Any] = {
            "input_count": len(request.dicom_paths),
            "echo_number": request.echo_number,
            "check_uid": request.check_uid,
            "origin_slice_override": request.origin_slice,
        }
        for key in (
            "num_images",
            "phantom_roll",
            "has_sagittal_module",
            "origin_slice",
        ):
            if key in raw:
                metrics[key] = raw[key]

        extra_warnings: list[str] = []
        if "check_uid" not in analyze_sig.parameters:
            extra_warnings.append(
                "This pylinac build does not expose analyze(check_uid=...); "
                "the value is stored in JSON for reproducibility only."
            )

        return QAResult(
            success=True,
            analysis_type=request.analysis_type,
            metrics=metrics,
            warnings=extra_warnings,
            errors=[],
            raw_pylinac=raw,
            pdf_report_path=pdf_report_path,
            study_uid=request.study_uid,
            series_uid=request.series_uid,
            modality=request.modality,
            num_images=num_images,
            pylinac_version=getattr(pylinac, "__version__", None),
        )
    except Exception as exc:
        return QAResult(
            success=False,
            analysis_type=request.analysis_type,
            errors=[f"ACR MRI Large analysis failed: {exc}"],
            study_uid=request.study_uid,
            series_uid=request.series_uid,
            modality=request.modality,
            num_images=len(request.dicom_paths),
            pylinac_version=getattr(pylinac, "__version__", None),
        )


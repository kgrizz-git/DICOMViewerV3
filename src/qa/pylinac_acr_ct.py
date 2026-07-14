"""
ACR CT analysis entrypoints and helpers.

Extracted from pylinac_runner.py (Phase 6 refactor). All public names are
re-exported from pylinac_runner.py for backward compatibility.

Public functions:
    run_acr_ct_analysis(request) -- single-run ACR CT analysis
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

from qa.analysis_types import QARequest, QAResult, build_pylinac_analysis_profile
from utils.debug_flags import DEBUG_PYLINAC_QA

# Stock pylinac CatPhanBase message; viewer mixin uses a different out-of-range wording.
_PYLINAC_IMAGE_INDEX_FAILURE_MARKERS = (
    "beyond the image extent",
    "out of range for the loaded stack",
)


# ---------------------------------------------------------------------------
# Shared utilities (local copies; also kept in pylinac_runner for compat)
# ---------------------------------------------------------------------------


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
            return len(stack)
        except Exception:
            pass
    return n


def _missing_pylinac_result(request: QARequest) -> QAResult:
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
        pylinac_analysis_profile=build_pylinac_analysis_profile(
            request, engine="(pylinac not installed)"
        ),
    )


# ---------------------------------------------------------------------------
# ACR CT
# ---------------------------------------------------------------------------


def _acr_ct_stack_diagnostic_lines(analyzer: Any) -> list[str]:
    """
    Best-effort context when slice indexing fails during ACR CT analysis.

    DICOM Viewer uses ``ACRCTForViewer``, which allows origin indices
    ``0 .. num_images-1``. If this still fails, the index is out of range for
    the loaded stack or another stage failed after localization.
    """
    lines: list[str] = []
    try:
        stack = getattr(analyzer, "dicom_stack", None)
        n = len(stack) if stack is not None else 0
    except Exception:
        n = 0
    lines.append(f"Images in stack (pylinac): {n}")
    if n <= 0:
        lines.append("Stack reports zero images — check DICOM paths or folder contents.")
    else:
        lines.append(
            "This app allows origin_slice indices 0 … N-1 (N = num_images). "
            "Stock pylinac alone allows only strictly interior indices "
            "(see JSON pylinac_analysis_profile.relaxed_image_extent)."
        )
    try:
        stack = getattr(analyzer, "dicom_stack", None)
        sp = getattr(stack, "slice_spacing", None) if stack is not None else None
        if sp is not None:
            lines.append(f"dicom_stack.slice_spacing (mm): {sp}")
    except Exception:
        pass
    try:
        from pylinac.core.image import z_position  # type: ignore[import-not-found]

        stack = getattr(analyzer, "dicom_stack", None)
        metas = getattr(stack, "metadatas", None) if stack is not None else None
        if metas:
            zs = [float(z_position(m)) for m in metas]
            lines.append(
                f"ImagePositionPatient Z (mm) min/max: {min(zs):.3f} … {max(zs):.3f} "
                f"(span {max(zs) - min(zs):.3f})"
            )
    except Exception:
        pass
    lines.append(
        "Typical causes: wrong/empty series, non-axial order, partial phantom, or "
        "bad HU localization. Override with analyze(origin_slice=...) from the CT "
        "options dialog if needed."
    )
    return lines


def run_acr_ct_analysis(request: QARequest) -> QAResult:
    """
    Run ACR CT analysis through pylinac with normalized output.

    Args:
        request: Normalized request payload from UI/worker.

    Returns:
        QAResult with success/failure details and normalized payload.
    """
    try:
        import pylinac  # type: ignore[import-not-found]
        from pylinac import ACRCT  # type: ignore[import-not-found]

        from qa.pylinac_extent_subclasses import ACRCTForViewer
    except Exception:
        return _missing_pylinac_result(request)

    py_ver = getattr(pylinac, "__version__", None)
    tol = float(request.scan_extent_tolerance_mm or 0.0)
    vanilla = bool(getattr(request, "vanilla_pylinac", False))
    eff_tol = 0.0 if vanilla else tol
    warn_ignore_tol = vanilla and tol > 0.0
    cls = ACRCT if vanilla else ACRCTForViewer
    engine = "ACRCT" if vanilla else "ACRCTForViewer"
    profile = build_pylinac_analysis_profile(request, engine=engine)

    analyzer: Any = None
    try:
        if request.dicom_paths:
            analyzer = cls(request.dicom_paths, check_uid=request.check_uid)
        elif request.folder_path:
            # CatPhanBase / ACRCT load from a folder via __init__, not from_folder.
            analyzer = cls(request.folder_path, check_uid=request.check_uid)
        else:
            return QAResult(
                success=False,
                analysis_type=request.analysis_type,
                errors=["No DICOM paths or folder were provided."],
                study_uid=request.study_uid,
                series_uid=request.series_uid,
                modality=request.modality,
                pylinac_version=py_ver,
                pylinac_analysis_profile=profile,
            )

        if not vanilla:
            analyzer._scan_extent_tolerance_mm = eff_tol

        if DEBUG_PYLINAC_QA and analyzer is not None:
            for ln in _acr_ct_stack_diagnostic_lines(analyzer):
                print(f"[DEBUG-PYLINAC-QA] {ln}")

        if analyzer is None:
            return QAResult(
                success=False,
                analysis_type=request.analysis_type,
                errors=["Analyzer could not be constructed."],
                study_uid=request.study_uid,
                series_uid=request.series_uid,
                modality=request.modality,
                pylinac_version=py_ver,
                pylinac_analysis_profile=profile,
            )

        analyze_kwargs: dict[str, Any] = {}
        if request.origin_slice is not None:
            analyze_kwargs["origin_slice"] = int(request.origin_slice)
        analyzer.analyze(**analyze_kwargs)

        raw: dict[str, Any] = {}
        try:
            rd = analyzer.results_data()
            if isinstance(rd, dict):
                raw = _jsonable(rd)
            else:
                raw = {"results_data": _jsonable(rd)}
        except Exception:
            raw = {}

        pdf_report_path: str | None = None
        if request.output_pdf_path:
            try:
                analyzer.publish_pdf(request.output_pdf_path)
                pdf_report_path = request.output_pdf_path
            except Exception:
                pdf_report_path = None

        num_images = _image_count(analyzer, request)
        metrics: dict[str, Any] = {
            "input_count": len(request.dicom_paths),
            "origin_slice_override": request.origin_slice,
            "scan_extent_tolerance_mm": eff_tol,
            "vanilla_pylinac": vanilla,
        }
        if warn_ignore_tol:
            metrics["scan_extent_tolerance_requested_mm"] = tol
        for key in ("num_images", "phantom_roll", "catphan_model", "origin_slice"):
            if key in raw:
                metrics[key] = raw[key]

        ct_warnings: list[str] = []
        if warn_ignore_tol:
            ct_warnings.append(
                "Scan extent tolerance is ignored in stock pylinac mode (ACRCT)."
            )

        return QAResult(
            success=True,
            analysis_type=request.analysis_type,
            metrics=metrics,
            warnings=ct_warnings,
            errors=[],
            raw_pylinac=raw,
            pdf_report_path=pdf_report_path,
            study_uid=request.study_uid,
            series_uid=request.series_uid,
            modality=request.modality,
            num_images=num_images,
            pylinac_version=py_ver,
            pylinac_analysis_profile=profile,
        )
    except Exception as exc:
        err_text = f"ACR CT analysis failed: {exc}"
        msg = str(exc)
        if analyzer is not None and any(
            m in msg.lower() for m in _PYLINAC_IMAGE_INDEX_FAILURE_MARKERS
        ):
            extra = "\n".join(_acr_ct_stack_diagnostic_lines(analyzer))
            err_text = f"{err_text}\n\n{extra}"
        n_fail = len(request.dicom_paths)
        if analyzer is not None:
            try:
                n_fail = len(analyzer.dicom_stack)
            except Exception:
                pass
        return QAResult(
            success=False,
            analysis_type=request.analysis_type,
            errors=[err_text],
            study_uid=request.study_uid,
            series_uid=request.series_uid,
            modality=request.modality,
            num_images=n_fail,
            pylinac_version=py_ver,
            pylinac_analysis_profile=profile,
        )

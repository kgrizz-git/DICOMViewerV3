"""
ACR MRI Large analysis entrypoints and helpers.

Extracted from pylinac_runner.py (Phase 6 refactor). All public names are
re-exported from pylinac_runner.py for backward compatibility.

Public functions:
    run_acr_mri_large_analysis(request)   -- single-run ACR MRI Large analysis
    run_acr_mri_large_batch(base, configs)-- multi-run compare-mode batch;
                                            produces a combined PDF via pypdf
"""

from __future__ import annotations

import inspect
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Any

from utils.log_sanitizer import sanitize_exception

logger = logging.getLogger(__name__)

from qa.analysis_types import (
    LcRunConfig,
    MRIBatchResult,
    QARequest,
    QAResult,
    build_pylinac_analysis_profile,
)
from qa.pylinac_mri_pdf import (
    _build_mri_notes_lines,
    _write_per_run_temp_pdf,
    assemble_mri_compare_pdf,
    build_mri_compare_summary_pdf,
)
from utils.config.qa_pylinac_config import (
    DEFAULT_ACR_MRI_LOW_CONTRAST_METHOD,
    DEFAULT_ACR_MRI_LOW_CONTRAST_VISIBILITY_SANITY_MULTIPLIER,
    DEFAULT_ACR_MRI_LOW_CONTRAST_VISIBILITY_THRESHOLD,
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
# MRI analyzer construction helper
# ---------------------------------------------------------------------------


def _build_mri_analyzer(
    request: QARequest,
    *,
    cls: Any,
    extent_tol_mm: float | None = None,
) -> Any:
    """
    Construct an ACRMRILarge (or subclass) analyzer from a QARequest.

    Handles both dicom_paths and folder_path source modes. When
    ``extent_tol_mm`` is not None, sets ``_scan_extent_tolerance_mm`` on the
    instance (viewer subclasses only; omit for stock ``ACRMRILarge``).

    Does NOT call analyze().

    Args:
        request: Input payload carrying paths and check_uid.
        cls: ``ACRMRILarge`` or ``ACRMRILargeForViewer``.
        extent_tol_mm: Optional scan-extent tolerance in mm for viewer class.

    Returns:
        An unanalyzed analyzer instance.

    Raises:
        ValueError: If neither dicom_paths nor folder_path are provided.
    """
    if request.dicom_paths:
        analyzer = cls(request.dicom_paths, check_uid=request.check_uid)
    elif request.folder_path:
        analyzer = cls(request.folder_path, check_uid=request.check_uid)
    else:
        raise ValueError("No DICOM paths or folder were provided.")
    if extent_tol_mm is not None:
        analyzer._scan_extent_tolerance_mm = float(extent_tol_mm)
    return analyzer


def _build_mri_analyze_kwargs(
    analyzer: Any,
    request: QARequest,
    *,
    lc_method: str,
    lc_vis: float,
    lc_sanity: float,
) -> dict[str, Any]:
    """
    Build the keyword-argument dict for analyze() using signature inspection.

    Only passes kwargs that the installed pylinac version exposes, ensuring
    backward compatibility with older builds.

    Args:
        analyzer: An unanalyzed ACRMRILarge instance (used for signature).
        request: Input payload for echo, check_uid, origin_slice.
        lc_method: Contrast method string.
        lc_vis: Visibility threshold float.
        lc_sanity: Sanity multiplier float.

    Returns:
        Dict of kwargs ready to unpack into analyzer.analyze(**kwargs).
    """
    sig = inspect.signature(analyzer.analyze)
    kwargs: dict[str, Any] = {}
    if "echo_number" in sig.parameters:
        kwargs["echo_number"] = request.echo_number
    if "check_uid" in sig.parameters:
        kwargs["check_uid"] = request.check_uid
    if request.origin_slice is not None and "origin_slice" in sig.parameters:
        kwargs["origin_slice"] = int(request.origin_slice)
    if "low_contrast_method" in sig.parameters:
        kwargs["low_contrast_method"] = lc_method
    if "low_contrast_visibility_threshold" in sig.parameters:
        kwargs["low_contrast_visibility_threshold"] = lc_vis
    if "low_contrast_visibility_sanity_multiplier" in sig.parameters:
        kwargs["low_contrast_visibility_sanity_multiplier"] = lc_sanity
    return kwargs


def _build_mri_extra_warnings(analyzer: Any) -> list[str]:
    """
    Return warnings for any low-contrast kwargs that the installed pylinac
    version does not expose on analyze().
    """
    sig = inspect.signature(analyzer.analyze)
    warnings: list[str] = []
    if "check_uid" not in sig.parameters:
        warnings.append(
            "This pylinac build does not expose analyze(check_uid=...); "
            "the value is stored in JSON for reproducibility only."
        )
    if "low_contrast_visibility_threshold" not in sig.parameters:
        warnings.append(
            "This pylinac build does not expose "
            "analyze(low_contrast_visibility_threshold=...); "
            "the value is stored in JSON for reproducibility only."
        )
    if "low_contrast_method" not in sig.parameters:
        warnings.append(
            "This pylinac build does not expose "
            "analyze(low_contrast_method=...); "
            "the value is stored in JSON for reproducibility only."
        )
    if "low_contrast_visibility_sanity_multiplier" not in sig.parameters:
        warnings.append(
            "This pylinac build does not expose "
            "analyze(low_contrast_visibility_sanity_multiplier=...); "
            "the value is stored in JSON for reproducibility only."
        )
    return warnings


# ---------------------------------------------------------------------------
# ACR MRI Large — single run
# ---------------------------------------------------------------------------


def run_acr_mri_large_analysis(request: QARequest) -> QAResult:
    """
    Run ACR MRI Large analysis through pylinac with normalized output.

    Always-on interpretation notes (MTF, low-contrast, circle colors, pylinac
    documentation links) are passed to publish_pdf via the ``notes`` argument.

    Args:
        request: Normalized request payload from UI/worker.

    Returns:
        QAResult with success/failure details and normalized payload.
    """
    try:
        import pylinac  # type: ignore[import-not-found]
        from pylinac import ACRMRILarge  # type: ignore[import-not-found]

        from qa.pylinac_extent_subclasses import ACRMRILargeForViewer
    except Exception:
        return _missing_pylinac_result(request)

    py_ver = getattr(pylinac, "__version__", None)
    tol = float(request.scan_extent_tolerance_mm or 0.0)
    vanilla = bool(getattr(request, "vanilla_pylinac", False))
    eff_tol = 0.0 if vanilla else tol
    warn_ignore_tol = vanilla and tol > 0.0
    mri_cls = ACRMRILarge if vanilla else ACRMRILargeForViewer
    engine = "ACRMRILarge" if vanilla else "ACRMRILargeForViewer"
    profile = build_pylinac_analysis_profile(request, engine=engine)

    lc_method = str(
        getattr(request, "low_contrast_method", DEFAULT_ACR_MRI_LOW_CONTRAST_METHOD)
        or DEFAULT_ACR_MRI_LOW_CONTRAST_METHOD
    )
    lc_vis = float(
        getattr(
            request,
            "low_contrast_visibility_threshold",
            DEFAULT_ACR_MRI_LOW_CONTRAST_VISIBILITY_THRESHOLD,
        )
        or DEFAULT_ACR_MRI_LOW_CONTRAST_VISIBILITY_THRESHOLD
    )
    lc_sanity = float(
        getattr(
            request,
            "low_contrast_visibility_sanity_multiplier",
            DEFAULT_ACR_MRI_LOW_CONTRAST_VISIBILITY_SANITY_MULTIPLIER,
        )
        or DEFAULT_ACR_MRI_LOW_CONTRAST_VISIBILITY_SANITY_MULTIPLIER
    )

    try:
        try:
            analyzer = _build_mri_analyzer(
                request,
                cls=mri_cls,
                extent_tol_mm=None if vanilla else eff_tol,
            )
        except ValueError as ve:
            return QAResult(
                success=False,
                analysis_type=request.analysis_type,
                errors=[str(ve)],
                study_uid=request.study_uid,
                series_uid=request.series_uid,
                modality=request.modality,
                pylinac_version=py_ver,
                pylinac_analysis_profile=profile,
            )

        analyze_kwargs = _build_mri_analyze_kwargs(
            analyzer, request, lc_method=lc_method, lc_vis=lc_vis, lc_sanity=lc_sanity
        )
        extra_warnings = list(_build_mri_extra_warnings(analyzer))
        if warn_ignore_tol:
            extra_warnings.append(
                "Scan extent tolerance is ignored in stock pylinac mode "
                "(ACRMRILarge)."
            )

        analyzer.analyze(**analyze_kwargs)

        # as_dict=True returns a plain dict (via pydantic model_dump_json + json.loads)
        # so raw_pylinac is always a proper serializable dict.
        raw: dict[str, Any] = {}
        try:
            raw = _jsonable(analyzer.results_data(as_dict=True))
        except Exception:
            raw = {}

        pdf_report_path: str | None = None
        if request.output_pdf_path:
            try:
                notes_lines = _build_mri_notes_lines()
                analyzer.publish_pdf(request.output_pdf_path, notes=notes_lines)
                pdf_report_path = request.output_pdf_path
            except Exception:
                pdf_report_path = None

        num_images = _image_count(analyzer, request)
        metrics: dict[str, Any] = {
            "input_count": len(request.dicom_paths),
            "echo_number": request.echo_number,
            "check_uid": request.check_uid,
            "origin_slice_override": request.origin_slice,
            "scan_extent_tolerance_mm": eff_tol,
            "vanilla_pylinac": vanilla,
            "low_contrast_method": lc_method,
            "low_contrast_visibility_threshold": lc_vis,
            "low_contrast_visibility_sanity_multiplier": lc_sanity,
        }
        if warn_ignore_tol:
            metrics["scan_extent_tolerance_requested_mm"] = tol
        for key in (
            "num_images",
            "phantom_roll",
            "has_sagittal_module",
            "origin_slice",
        ):
            if key in raw:
                metrics[key] = raw[key]
        # Pull top-level low-contrast score for compare tables
        lc_score = _extract_lc_score(raw)
        if lc_score is not None:
            metrics["low_contrast_score"] = lc_score

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
            pylinac_version=py_ver,
            pylinac_analysis_profile=profile,
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
            pylinac_version=py_ver,
            pylinac_analysis_profile=profile,
        )


def _extract_lc_score(raw: dict[str, Any]) -> int | None:
    """
    Best-effort extraction of the low-contrast score from raw pylinac output.

    When results_data(as_dict=True) is used the pydantic model is serialized
    via model_dump_json, so the field name is the pydantic field name:
    ``low_contrast_multi_slice_module``.  Legacy or future shapes may use
    ``low_contrast_multi_slice`` or a top-level ``low_contrast_score``.

    Args:
        raw: Plain dict from analyzer.results_data(as_dict=True).

    Returns:
        Integer score if found, else None.
    """
    # Top-level convenience key (older / future shape)
    if "low_contrast_score" in raw:
        try:
            return int(raw["low_contrast_score"])
        except (TypeError, ValueError):
            pass
    # Pydantic serialized shape from pylinac 3.43.2 (via as_dict=True)
    lc_multi = raw.get("low_contrast_multi_slice_module") or raw.get(
        "low_contrast_multi_slice"
    )
    if isinstance(lc_multi, dict) and "score" in lc_multi:
        try:
            return int(lc_multi["score"])
        except (TypeError, ValueError):
            pass
    return None


# ---------------------------------------------------------------------------
# ACR MRI Large — multi-run compare mode
# ---------------------------------------------------------------------------


def run_acr_mri_large_batch(
    base_request: QARequest,
    run_configs: list[LcRunConfig],
    *,
    app_version: str = "",
) -> MRIBatchResult:
    """
    Run ACR MRI Large analysis for each LcRunConfig in a compare-mode batch.

    The analyzer is re-instantiated for every run to guarantee independence
    (pylinac does not guarantee idempotent multiple analyze() calls on the
    same object).

    PDF output (when base_request.output_pdf_path is set):
        Each run writes a temporary pylinac PDF to a temp directory.
        After all runs finish, a viewer-authored summary page is prepended and
        all pages are merged into a single combined PDF via pypdf.  The temp
        files are cleaned up automatically.  The combined PDF path is stored
        in run_results[0].pdf_report_path.

    Args:
        base_request: A QARequest carrying DICOM source info, echo, check_uid,
            scan-extent tolerance, and origin_slice.  The low-contrast fields
            on base_request are IGNORED; each run_config provides its own.
        run_configs: 1–3 LcRunConfig entries in the order to run them.
        app_version: Application version string embedded in the summary PDF.

    Returns:
        MRIBatchResult with one QAResult per config, in the same order.
        run_results[0].pdf_report_path is the combined PDF path if PDF output
        was requested and succeeded, else None / empty string.
    """
    from dataclasses import replace as dc_replace

    try:
        import pylinac  # type: ignore[import-not-found]
        from pylinac import ACRMRILarge  # type: ignore[import-not-found]

        from qa.pylinac_extent_subclasses import ACRMRILargeForViewer
    except Exception:
        # pylinac missing — return a failed result for every config
        failed = _missing_pylinac_result(base_request)
        return MRIBatchResult(
            run_results=[failed for _ in run_configs],
            run_configs=list(run_configs),
        )

    py_ver = getattr(pylinac, "__version__", None)
    tol = float(base_request.scan_extent_tolerance_mm or 0.0)
    vanilla = bool(getattr(base_request, "vanilla_pylinac", False))
    eff_tol = 0.0 if vanilla else tol
    warn_ignore_tol = vanilla and tol > 0.0
    mri_cls = ACRMRILarge if vanilla else ACRMRILargeForViewer

    # Allocate a temp directory for per-run PDFs (used only when PDF output is requested)
    tmp_dir: Path | None = None
    run_pdf_paths: list[Path | None] = []
    if base_request.output_pdf_path:
        try:
            tmp_dir = Path(tempfile.mkdtemp(prefix="dicom_viewer_mri_compare_"))
        except Exception as exc:
            logger.warning("Could not create temp dir for compare PDFs: %s", sanitize_exception(str(exc)))
            tmp_dir = None

    run_results: list[QAResult] = []
    for run_idx, cfg in enumerate(run_configs):
        # Build a per-run QARequest; PDF path is handled via temp files, not QARequest.
        per_run_request = dc_replace(
            base_request,
            low_contrast_method=cfg.low_contrast_method,
            low_contrast_visibility_threshold=cfg.low_contrast_visibility_threshold,
            low_contrast_visibility_sanity_multiplier=cfg.low_contrast_visibility_sanity_multiplier,
            output_pdf_path=None,  # temp PDFs written directly, not via QARequest
        )
        engine = "ACRMRILarge" if vanilla else "ACRMRILargeForViewer"
        profile = build_pylinac_analysis_profile(per_run_request, engine=engine)

        try:
            analyzer = _build_mri_analyzer(
                per_run_request,
                cls=mri_cls,
                extent_tol_mm=None if vanilla else eff_tol,
            )
        except ValueError as ve:
            run_results.append(
                QAResult(
                    success=False,
                    analysis_type=base_request.analysis_type,
                    errors=[str(ve)],
                    study_uid=base_request.study_uid,
                    series_uid=base_request.series_uid,
                    modality=base_request.modality,
                    pylinac_version=py_ver,
                    pylinac_analysis_profile=profile,
                )
            )
            run_pdf_paths.append(None)
            continue

        analyze_kwargs = _build_mri_analyze_kwargs(
            analyzer,
            per_run_request,
            lc_method=cfg.low_contrast_method,
            lc_vis=cfg.low_contrast_visibility_threshold,
            lc_sanity=cfg.low_contrast_visibility_sanity_multiplier,
        )
        extra_warnings = list(_build_mri_extra_warnings(analyzer))
        if warn_ignore_tol:
            extra_warnings.append(
                "Scan extent tolerance is ignored in stock pylinac mode "
                "(ACRMRILarge)."
            )

        try:
            analyzer.analyze(**analyze_kwargs)

            raw: dict[str, Any] = {}
            try:
                raw = _jsonable(analyzer.results_data(as_dict=True))
            except Exception:
                raw = {}

            # Write a temp PDF for this run (merged later into the combined PDF)
            run_pdf: Path | None = None
            if tmp_dir is not None:
                temp_path = tmp_dir / f"run{run_idx + 1}.pdf"
                run_pdf = _write_per_run_temp_pdf(
                    analyzer, temp_path, cfg.label, cfg
                )
            run_pdf_paths.append(run_pdf)

            num_images = _image_count(analyzer, per_run_request)
            metrics: dict[str, Any] = {
                "input_count": len(per_run_request.dicom_paths),
                "echo_number": per_run_request.echo_number,
                "check_uid": per_run_request.check_uid,
                "origin_slice_override": per_run_request.origin_slice,
                "scan_extent_tolerance_mm": eff_tol,
                "vanilla_pylinac": vanilla,
                "low_contrast_method": cfg.low_contrast_method,
                "low_contrast_visibility_threshold": cfg.low_contrast_visibility_threshold,
                "low_contrast_visibility_sanity_multiplier": cfg.low_contrast_visibility_sanity_multiplier,
                "run_label": cfg.label,
            }
            if warn_ignore_tol:
                metrics["scan_extent_tolerance_requested_mm"] = tol
            for key in (
                "num_images",
                "phantom_roll",
                "has_sagittal_module",
                "origin_slice",
            ):
                if key in raw:
                    metrics[key] = raw[key]
            lc_score = _extract_lc_score(raw)
            if lc_score is not None:
                metrics["low_contrast_score"] = lc_score

            run_results.append(
                QAResult(
                    success=True,
                    analysis_type=per_run_request.analysis_type,
                    metrics=metrics,
                    warnings=extra_warnings,
                    errors=[],
                    raw_pylinac=raw,
                    pdf_report_path=None,  # set on run_results[0] after merge
                    study_uid=per_run_request.study_uid,
                    series_uid=per_run_request.series_uid,
                    modality=per_run_request.modality,
                    num_images=num_images,
                    pylinac_version=py_ver,
                    pylinac_analysis_profile=profile,
                )
            )
        except Exception as exc:
            run_results.append(
                QAResult(
                    success=False,
                    analysis_type=per_run_request.analysis_type,
                    errors=[f"ACR MRI Large batch run ({cfg.label}) failed: {exc}"],
                    study_uid=per_run_request.study_uid,
                    series_uid=per_run_request.series_uid,
                    modality=per_run_request.modality,
                    num_images=len(per_run_request.dicom_paths),
                    pylinac_version=py_ver,
                    pylinac_analysis_profile=profile,
                )
            )
            run_pdf_paths.append(None)

    batch = MRIBatchResult(run_results=run_results, run_configs=list(run_configs))

    # Assemble combined PDF: [summary page] + [run0.pdf] + [run1.pdf] + ...
    final_pdf_path: str | None = None
    if base_request.output_pdf_path and tmp_dir is not None:
        try:
            summary_path = tmp_dir / "summary.pdf"
            build_mri_compare_summary_pdf(
                batch,
                summary_path,
                base_request=base_request,
                app_version=app_version,
            )
            output_path = Path(base_request.output_pdf_path)
            ok = assemble_mri_compare_pdf(summary_path, run_pdf_paths, output_path)
            if ok:
                final_pdf_path = str(output_path)
        except Exception as exc:
            logger.error("compare PDF assembly failed: %s", sanitize_exception(str(exc)))
        finally:
            # Clean up temp dir regardless of success
            try:
                shutil.rmtree(tmp_dir, ignore_errors=True)
            except Exception:
                pass

    # Store combined PDF path on the first run result
    if run_results and final_pdf_path:
        run_results[0].pdf_report_path = final_pdf_path

    return batch

"""
pylinac.nuclear runner entrypoints (nuclear-medicine QA).

Separate from the ACR CT/MRI runners because nuclear classes take a single
DICOM file and return frame-keyed results rather than a CatPhan-style stack.

Public functions:
    run_nuclear_analysis(request)               -- dispatch by analysis_type
    run_planar_uniformity_analysis(request)     -- PlanarUniformity (frame-keyed)
    run_four_bar_resolution_analysis(request)   -- FourBarResolution (flat result)
    run_quadrant_resolution_analysis(request)   -- QuadrantResolution (per-quadrant)
    run_center_of_rotation_analysis(request)    -- CenterOfRotation (flat)
    run_tomographic_resolution_analysis(request)-- TomographicResolution (flat)
    run_max_count_rate_analysis(request)        -- MaxCountRate (flat; drops sums)
    run_tomographic_uniformity_analysis(request)-- TomographicUniformity (flat)
    run_tomographic_contrast_analysis(request)  -- TomographicContrast (per-sphere)
    run_simple_sensitivity_analysis(request)    -- SimpleSensitivity (2-file + nuclide)

Normalization notes:
    pylinac ``PlanarUniformity.results_data(as_dict=True)`` returns a dict keyed
    by frame ("Frame 1", "Frame 2", ...), each value a 4-float uniformity dict —
    stored verbatim in ``raw_pylinac`` with a per-frame copy under
    ``metrics["frames"]``.
    ``FourBarResolution.results_data(as_dict=True)`` returns a single flat dict
    of 8 floats (x/y FWHM, FWTM, measured pixel size, pixel-size difference) —
    stored under ``metrics["results"]`` and verbatim in ``raw_pylinac``.
"""

from __future__ import annotations

import logging
import math
from typing import Any

from qa.analysis_types import (
    QARequest,
    QAResult,
    build_nuclear_analysis_profile,
)
from qa.preflight import modality_preflight_warning
from utils.config.qa_nuclear_config import (
    CENTER_OF_ROTATION_CLASS,
    FOUR_BAR_RESOLUTION_CLASS,
    MAX_COUNT_RATE_CLASS,
    NUCLEAR_CENTER_OF_ROTATION,
    NUCLEAR_FOUR_BAR_RESOLUTION,
    NUCLEAR_MAX_COUNT_RATE,
    NUCLEAR_PLANAR_UNIFORMITY,
    NUCLEAR_QUADRANT_RESOLUTION,
    NUCLEAR_SIMPLE_SENSITIVITY,
    NUCLEAR_TOMOGRAPHIC_CONTRAST,
    NUCLEAR_TOMOGRAPHIC_RESOLUTION,
    NUCLEAR_TOMOGRAPHIC_UNIFORMITY,
    PLANAR_UNIFORMITY_CLASS,
    QUADRANT_RESOLUTION_CLASS,
    SIMPLE_SENSITIVITY_CLASS,
    TOMOGRAPHIC_CONTRAST_CLASS,
    TOMOGRAPHIC_RESOLUTION_CLASS,
    TOMOGRAPHIC_UNIFORMITY_CLASS,
)

logger = logging.getLogger(__name__)

# Modality nuclear classes expect (gamma camera / SPECT planar acquisitions).
_NUCLEAR_MODALITY = "NM"


def _jsonable(value: Any) -> Any:
    """Best-effort conversion to JSON-friendly primitives (mirrors ACR runner)."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    return str(value)


def _missing_pylinac_result(request: QARequest) -> QAResult:
    """Uniform failure when pylinac is unavailable."""
    return QAResult(
        success=False,
        analysis_type=request.analysis_type,
        errors=["pylinac is not installed. Install required dependencies and retry."],
        study_uid=request.study_uid,
        series_uid=request.series_uid,
        modality=request.modality,
        num_images=len(request.dicom_paths),
        pylinac_analysis_profile=build_nuclear_analysis_profile(
            request, engine="(pylinac not installed)"
        ),
    )


def _resolve_input_path(request: QARequest) -> tuple[str | None, list[str]]:
    """
    Pick the single DICOM file nuclear classes expect.

    Returns (path, warnings). path is None when no input is available.
    """
    warnings: list[str] = []
    paths = list(request.dicom_paths or [])
    if not paths:
        return None, warnings
    if len(paths) > 1:
        warnings.append(
            f"{len(paths)} files supplied; nuclear analysis uses only the first "
            "(single-file input)."
        )
    return paths[0], warnings


def _resolve_run_inputs(
    request: QARequest,
    *,
    profile: dict[str, Any],
    py_ver: str | None,
) -> tuple[str | None, list[str], QAResult | None]:
    """
    Shared preamble: NM modality preflight + single-file resolution.

    Returns ``(input_path, pre_warnings, failure)``. ``failure`` is a QAResult to
    return immediately when no input file is available; otherwise it is None.
    """
    pre_warnings: list[str] = []
    mod_warning = modality_preflight_warning(request.modality, _NUCLEAR_MODALITY)
    if mod_warning:
        pre_warnings.append(mod_warning)
    input_path, path_warnings = _resolve_input_path(request)
    pre_warnings.extend(path_warnings)
    if not input_path:
        return (
            None,
            pre_warnings,
            QAResult(
                success=False,
                analysis_type=request.analysis_type,
                warnings=pre_warnings,
                errors=["No DICOM file was provided for nuclear analysis."],
                study_uid=request.study_uid,
                series_uid=request.series_uid,
                modality=request.modality,
                pylinac_version=py_ver,
                pylinac_analysis_profile=profile,
            ),
        )
    return input_path, pre_warnings, None


def _frame_count_warning(input_path: str, analysis_class: str) -> str | None:
    """Warn when a multi-frame image is supplied to a first-frame-only class."""
    try:
        import pydicom

        ds = pydicom.dcmread(input_path, stop_before_pixels=True, force=True)
        frames = int(getattr(ds, "NumberOfFrames", 1) or 1)
    except Exception:
        return None
    if frames > 1:
        return (
            f"Image has {frames} frames; {analysis_class} analyzes the first "
            "frame only."
        )
    return None


def run_planar_uniformity_analysis(request: QARequest) -> QAResult:
    """
    Run pylinac.nuclear PlanarUniformity with normalized output.

    Args:
        request: QARequest with a single DICOM file in ``dicom_paths`` and a
            ``nuclear_options`` payload (defaults are used if it is None).

    Returns:
        QAResult with per-frame uniformity metrics or a user-readable error.
    """
    try:
        import pylinac  # type: ignore[import-not-found]
        from pylinac.nuclear import PlanarUniformity  # type: ignore[import-not-found]
    except Exception:
        return _missing_pylinac_result(request)

    py_ver = getattr(pylinac, "__version__", None)
    profile = build_nuclear_analysis_profile(request, engine=PLANAR_UNIFORMITY_CLASS)

    input_path, pre_warnings, failure = _resolve_run_inputs(
        request, profile=profile, py_ver=py_ver
    )
    if failure is not None:
        return failure
    assert input_path is not None  # guaranteed non-None when failure is None

    opts = request.nuclear_options
    analyze_kwargs = opts.analyze_kwargs() if opts is not None else {}

    try:
        analyzer = PlanarUniformity(input_path)
        analyzer.analyze(**analyze_kwargs)

        raw: dict[str, Any] = {}
        try:
            raw = _jsonable(analyzer.results_data(as_dict=True))
        except Exception:
            raw = {}

        frames = raw if isinstance(raw, dict) else {}
        metrics: dict[str, Any] = {
            "analysis_class": PLANAR_UNIFORMITY_CLASS,
            "frame_count": len(frames),
            "frames": frames,
            "analysis_parameters": analyze_kwargs,
        }

        return QAResult(
            success=True,
            analysis_type=request.analysis_type,
            metrics=metrics,
            warnings=pre_warnings,
            errors=[],
            raw_pylinac=raw,
            study_uid=request.study_uid,
            series_uid=request.series_uid,
            modality=request.modality,
            num_images=1,
            pylinac_version=py_ver,
            pylinac_analysis_profile=profile,
        )
    except Exception as exc:
        return QAResult(
            success=False,
            analysis_type=request.analysis_type,
            warnings=pre_warnings,
            errors=[f"PlanarUniformity analysis failed: {exc}"],
            study_uid=request.study_uid,
            series_uid=request.series_uid,
            modality=request.modality,
            pylinac_version=py_ver,
            pylinac_analysis_profile=profile,
        )


def run_four_bar_resolution_analysis(request: QARequest) -> QAResult:
    """
    Run pylinac.nuclear FourBarResolution with normalized output.

    FourBar returns a single flat result (8 floats), not a per-frame dict, and
    analyzes only the first frame of a multi-frame image.

    Args:
        request: QARequest with a single DICOM file and a ``nuclear_options``
            payload (defaults used if None).

    Returns:
        QAResult with the flat resolution metrics under ``metrics["results"]``
        or a user-readable error.
    """
    try:
        import pylinac  # type: ignore[import-not-found]
        from pylinac.nuclear import FourBarResolution  # type: ignore[import-not-found]
    except Exception:
        return _missing_pylinac_result(request)

    py_ver = getattr(pylinac, "__version__", None)
    profile = build_nuclear_analysis_profile(request, engine=FOUR_BAR_RESOLUTION_CLASS)

    input_path, pre_warnings, failure = _resolve_run_inputs(
        request, profile=profile, py_ver=py_ver
    )
    if failure is not None:
        return failure
    assert input_path is not None  # guaranteed non-None when failure is None

    frame_warning = _frame_count_warning(input_path, FOUR_BAR_RESOLUTION_CLASS)
    if frame_warning:
        pre_warnings.append(frame_warning)

    opts = request.nuclear_options
    analyze_kwargs = opts.analyze_kwargs() if opts is not None else {}

    try:
        analyzer = FourBarResolution(input_path)
        analyzer.analyze(**analyze_kwargs)

        raw: dict[str, Any] = {}
        try:
            raw = _jsonable(analyzer.results_data(as_dict=True))
        except Exception:
            raw = {}

        results = raw if isinstance(raw, dict) else {}
        metrics: dict[str, Any] = {
            "analysis_class": FOUR_BAR_RESOLUTION_CLASS,
            "results": results,
            "analysis_parameters": analyze_kwargs,
        }

        return QAResult(
            success=True,
            analysis_type=request.analysis_type,
            metrics=metrics,
            warnings=pre_warnings,
            errors=[],
            raw_pylinac=raw,
            study_uid=request.study_uid,
            series_uid=request.series_uid,
            modality=request.modality,
            num_images=1,
            pylinac_version=py_ver,
            pylinac_analysis_profile=profile,
        )
    except Exception as exc:
        return QAResult(
            success=False,
            analysis_type=request.analysis_type,
            warnings=pre_warnings,
            errors=[f"FourBarResolution analysis failed: {exc}"],
            study_uid=request.study_uid,
            series_uid=request.series_uid,
            modality=request.modality,
            pylinac_version=py_ver,
            pylinac_analysis_profile=profile,
        )


def run_quadrant_resolution_analysis(request: QARequest) -> QAResult:
    """
    Run pylinac.nuclear QuadrantResolution with normalized output.

    Requires ``bar_widths`` (exactly 4, one per quadrant) via the options
    payload; pylinac raises if the count is wrong, surfaced as a readable error.
    Result is a nested per-quadrant dict stored under ``metrics["quadrants"]``.

    Returns:
        QAResult with per-quadrant MTF/FWHM/lp-mm metrics or a readable error.
    """
    try:
        import pylinac  # type: ignore[import-not-found]
        from pylinac.nuclear import QuadrantResolution  # type: ignore[import-not-found]
    except Exception:
        return _missing_pylinac_result(request)

    py_ver = getattr(pylinac, "__version__", None)
    profile = build_nuclear_analysis_profile(request, engine=QUADRANT_RESOLUTION_CLASS)

    input_path, pre_warnings, failure = _resolve_run_inputs(
        request, profile=profile, py_ver=py_ver
    )
    if failure is not None:
        return failure
    assert input_path is not None  # guaranteed non-None when failure is None

    frame_warning = _frame_count_warning(input_path, QUADRANT_RESOLUTION_CLASS)
    if frame_warning:
        pre_warnings.append(frame_warning)

    opts = request.nuclear_options
    analyze_kwargs = opts.analyze_kwargs() if opts is not None else {}

    try:
        analyzer = QuadrantResolution(input_path)
        analyzer.analyze(**analyze_kwargs)

        raw: dict[str, Any] = {}
        try:
            raw = _jsonable(analyzer.results_data(as_dict=True))
        except Exception:
            raw = {}

        quadrants = raw.get("quadrants", {}) if isinstance(raw, dict) else {}
        metrics: dict[str, Any] = {
            "analysis_class": QUADRANT_RESOLUTION_CLASS,
            "quadrants": quadrants,
            "analysis_parameters": analyze_kwargs,
        }

        return QAResult(
            success=True,
            analysis_type=request.analysis_type,
            metrics=metrics,
            warnings=pre_warnings,
            errors=[],
            raw_pylinac=raw,
            study_uid=request.study_uid,
            series_uid=request.series_uid,
            modality=request.modality,
            num_images=1,
            pylinac_version=py_ver,
            pylinac_analysis_profile=profile,
        )
    except Exception as exc:
        return QAResult(
            success=False,
            analysis_type=request.analysis_type,
            warnings=pre_warnings,
            errors=[f"QuadrantResolution analysis failed: {exc}"],
            study_uid=request.study_uid,
            series_uid=request.series_uid,
            modality=request.modality,
            pylinac_version=py_ver,
            pylinac_analysis_profile=profile,
        )


def _run_flat_nuclear_analysis(
    request: QARequest,
    *,
    class_name: str,
    strip_keys: tuple[str, ...] = (),
) -> QAResult:
    """
    Generic runner for nuclear classes that produce a single flat result dict.

    Mirrors the PlanarUniformity preamble (single-file, NM preflight, no
    first-frame warning — these tests use all frames). Normalizes
    ``results_data(as_dict=True)`` into ``metrics["results"]`` minus
    ``strip_keys`` (e.g. MaxCountRate's per-frame ``sums``), keeping the full
    payload in ``raw_pylinac``.
    """
    try:
        import pylinac  # type: ignore[import-not-found]
        import pylinac.nuclear as _nuclear  # type: ignore[import-not-found]
    except Exception:
        return _missing_pylinac_result(request)

    py_ver = getattr(pylinac, "__version__", None)
    profile = build_nuclear_analysis_profile(request, engine=class_name)

    input_path, pre_warnings, failure = _resolve_run_inputs(
        request, profile=profile, py_ver=py_ver
    )
    if failure is not None:
        return failure
    assert input_path is not None  # guaranteed non-None when failure is None

    cls = getattr(_nuclear, class_name, None)
    if cls is None:
        return QAResult(
            success=False,
            analysis_type=request.analysis_type,
            warnings=pre_warnings,
            errors=[f"pylinac.nuclear has no class '{class_name}'."],
            study_uid=request.study_uid,
            series_uid=request.series_uid,
            modality=request.modality,
            pylinac_version=py_ver,
            pylinac_analysis_profile=profile,
        )

    opts = request.nuclear_options
    analyze_kwargs = opts.analyze_kwargs() if opts is not None else {}

    try:
        analyzer = cls(input_path)
        analyzer.analyze(**analyze_kwargs)

        raw: dict[str, Any] = {}
        try:
            raw = _jsonable(analyzer.results_data(as_dict=True))
        except Exception:
            raw = {}

        if isinstance(raw, dict):
            results = {k: v for k, v in raw.items() if k not in strip_keys}
        else:
            results = {}
        metrics: dict[str, Any] = {
            "analysis_class": class_name,
            "results": results,
            "analysis_parameters": analyze_kwargs,
        }

        return QAResult(
            success=True,
            analysis_type=request.analysis_type,
            metrics=metrics,
            warnings=pre_warnings,
            errors=[],
            raw_pylinac=raw,
            study_uid=request.study_uid,
            series_uid=request.series_uid,
            modality=request.modality,
            num_images=1,
            pylinac_version=py_ver,
            pylinac_analysis_profile=profile,
        )
    except Exception as exc:
        return QAResult(
            success=False,
            analysis_type=request.analysis_type,
            warnings=pre_warnings,
            errors=[f"{class_name} analysis failed: {exc}"],
            study_uid=request.study_uid,
            series_uid=request.series_uid,
            modality=request.modality,
            pylinac_version=py_ver,
            pylinac_analysis_profile=profile,
        )


def run_center_of_rotation_analysis(request: QARequest) -> QAResult:
    """Run pylinac.nuclear CenterOfRotation (flat x/y deviation result)."""
    return _run_flat_nuclear_analysis(request, class_name=CENTER_OF_ROTATION_CLASS)


def run_tomographic_resolution_analysis(request: QARequest) -> QAResult:
    """Run pylinac.nuclear TomographicResolution (flat x/y/z FWHM/FWTM result)."""
    return _run_flat_nuclear_analysis(
        request, class_name=TOMOGRAPHIC_RESOLUTION_CLASS
    )


def run_max_count_rate_analysis(request: QARequest) -> QAResult:
    """Run pylinac.nuclear MaxCountRate; drop per-frame ``sums`` from headline."""
    return _run_flat_nuclear_analysis(
        request, class_name=MAX_COUNT_RATE_CLASS, strip_keys=("sums",)
    )


def run_tomographic_uniformity_analysis(request: QARequest) -> QAResult:
    """Run pylinac.nuclear TomographicUniformity (flat result; uses all frames)."""
    return _run_flat_nuclear_analysis(
        request, class_name=TOMOGRAPHIC_UNIFORMITY_CLASS
    )


def run_tomographic_contrast_analysis(request: QARequest) -> QAResult:
    """
    Run pylinac.nuclear TomographicContrast with normalized output.

    Result is a per-sphere nested dict plus a scalar ``uniformity_baseline``,
    stored under ``metrics["spheres"]`` and ``metrics["uniformity_baseline"]``.
    """
    try:
        import pylinac  # type: ignore[import-not-found]
        from pylinac.nuclear import (
            TomographicContrast,  # type: ignore[import-not-found]
        )
    except Exception:
        return _missing_pylinac_result(request)

    py_ver = getattr(pylinac, "__version__", None)
    profile = build_nuclear_analysis_profile(request, engine=TOMOGRAPHIC_CONTRAST_CLASS)

    input_path, pre_warnings, failure = _resolve_run_inputs(
        request, profile=profile, py_ver=py_ver
    )
    if failure is not None:
        return failure
    assert input_path is not None  # guaranteed non-None when failure is None

    opts = request.nuclear_options
    analyze_kwargs = opts.analyze_kwargs() if opts is not None else {}

    try:
        analyzer = TomographicContrast(input_path)
        analyzer.analyze(**analyze_kwargs)

        raw: dict[str, Any] = {}
        try:
            raw = _jsonable(analyzer.results_data(as_dict=True))
        except Exception:
            raw = {}

        spheres = raw.get("spheres", {}) if isinstance(raw, dict) else {}
        metrics: dict[str, Any] = {
            "analysis_class": TOMOGRAPHIC_CONTRAST_CLASS,
            "spheres": spheres,
            "uniformity_baseline": raw.get("uniformity_baseline")
            if isinstance(raw, dict)
            else None,
            "analysis_parameters": analyze_kwargs,
        }

        return QAResult(
            success=True,
            analysis_type=request.analysis_type,
            metrics=metrics,
            warnings=pre_warnings,
            errors=[],
            raw_pylinac=raw,
            study_uid=request.study_uid,
            series_uid=request.series_uid,
            modality=request.modality,
            num_images=1,
            pylinac_version=py_ver,
            pylinac_analysis_profile=profile,
        )
    except Exception as exc:
        return QAResult(
            success=False,
            analysis_type=request.analysis_type,
            warnings=pre_warnings,
            errors=[f"TomographicContrast analysis failed: {exc}"],
            study_uid=request.study_uid,
            series_uid=request.series_uid,
            modality=request.modality,
            pylinac_version=py_ver,
            pylinac_analysis_profile=profile,
        )


def run_simple_sensitivity_analysis(request: QARequest) -> QAResult:
    """
    Run pylinac.nuclear SimpleSensitivity with normalized output.

    Differs from the other runners: the constructor takes an optional second
    (background) DICOM, and ``analyze`` requires ``activity_mbq`` plus a pylinac
    ``Nuclide`` enum (mapped from the options' string name). Validates the
    activity and nuclide so pylinac assertions don't leak as tracebacks.
    """
    try:
        import pylinac  # type: ignore[import-not-found]
        from pylinac.nuclear import (  # type: ignore[import-not-found]
            Nuclide,
            SimpleSensitivity,
        )
    except Exception:
        return _missing_pylinac_result(request)

    py_ver = getattr(pylinac, "__version__", None)
    profile = build_nuclear_analysis_profile(request, engine=SIMPLE_SENSITIVITY_CLASS)

    input_path, pre_warnings, failure = _resolve_run_inputs(
        request, profile=profile, py_ver=py_ver
    )
    if failure is not None:
        return failure
    assert input_path is not None  # guaranteed non-None when failure is None

    opts = request.nuclear_options
    activity_mbq = float(getattr(opts, "activity_mbq", 0.0) or 0.0)
    nuclide_name = str(getattr(opts, "nuclide", "") or "")
    background_path = getattr(opts, "background_path", None) or None

    def _fail(message: str) -> QAResult:
        return QAResult(
            success=False,
            analysis_type=request.analysis_type,
            warnings=pre_warnings,
            errors=[message],
            study_uid=request.study_uid,
            series_uid=request.series_uid,
            modality=request.modality,
            pylinac_version=py_ver,
            pylinac_analysis_profile=profile,
        )

    if activity_mbq <= 0.0:
        return _fail("Administered activity (MBq) must be greater than 0.")
    nuclide = getattr(Nuclide, nuclide_name, None)
    if nuclide is None:
        return _fail(f"Unknown nuclide '{nuclide_name}'.")

    try:
        analyzer = SimpleSensitivity(input_path, background_path=background_path)
        analyzer.analyze(activity_mbq=activity_mbq, nuclide=nuclide)

        raw: dict[str, Any] = {}
        try:
            raw = _jsonable(analyzer.results_data(as_dict=True))
        except Exception:
            raw = {}

        results = raw if isinstance(raw, dict) else {}
        metrics: dict[str, Any] = {
            "analysis_class": SIMPLE_SENSITIVITY_CLASS,
            "results": results,
            "analysis_parameters": opts.analyze_kwargs() if opts is not None else {},
        }

        return QAResult(
            success=True,
            analysis_type=request.analysis_type,
            metrics=metrics,
            warnings=pre_warnings,
            errors=[],
            raw_pylinac=raw,
            study_uid=request.study_uid,
            series_uid=request.series_uid,
            modality=request.modality,
            num_images=2 if background_path else 1,
            pylinac_version=py_ver,
            pylinac_analysis_profile=profile,
        )
    except Exception as exc:
        return _fail(f"SimpleSensitivity analysis failed: {exc}")


# Map analysis_type discriminator -> runner.
_NUCLEAR_RUNNERS = {
    NUCLEAR_PLANAR_UNIFORMITY: run_planar_uniformity_analysis,
    NUCLEAR_FOUR_BAR_RESOLUTION: run_four_bar_resolution_analysis,
    NUCLEAR_QUADRANT_RESOLUTION: run_quadrant_resolution_analysis,
    NUCLEAR_CENTER_OF_ROTATION: run_center_of_rotation_analysis,
    NUCLEAR_TOMOGRAPHIC_RESOLUTION: run_tomographic_resolution_analysis,
    NUCLEAR_MAX_COUNT_RATE: run_max_count_rate_analysis,
    NUCLEAR_TOMOGRAPHIC_UNIFORMITY: run_tomographic_uniformity_analysis,
    NUCLEAR_TOMOGRAPHIC_CONTRAST: run_tomographic_contrast_analysis,
    NUCLEAR_SIMPLE_SENSITIVITY: run_simple_sensitivity_analysis,
}

# Analysis types the worker should route to run_nuclear_analysis.
NUCLEAR_ANALYSIS_TYPES = frozenset(_NUCLEAR_RUNNERS)


def _nonfinite_metric_paths(value: Any, path: str = "") -> list[str]:
    """Return dotted paths of any NaN/inf float within a nested metrics structure."""
    found: list[str] = []
    if isinstance(value, bool):
        return found
    if isinstance(value, float):
        if not math.isfinite(value):
            found.append(path or "<value>")
    elif isinstance(value, dict):
        for key, sub in value.items():
            found.extend(_nonfinite_metric_paths(sub, f"{path}.{key}" if path else str(key)))
    elif isinstance(value, (list, tuple)):
        for idx, sub in enumerate(value):
            found.extend(_nonfinite_metric_paths(sub, f"{path}[{idx}]"))
    return found


def _warn_on_nonfinite_metrics(result: QAResult) -> None:
    """Append a clear warning if any reported nuclear metric is NaN/inf.

    Defensive guard for degenerate acquisitions (e.g. empty/low-count SPECT
    frames) where pylinac's contrast/uniformity math can yield a non-finite
    value. Surfaces it instead of letting a silent NaN reach exports/reports.
    """
    if not result.success:
        return
    bad = _nonfinite_metric_paths(result.metrics)
    if not bad:
        return
    preview = ", ".join(bad[:8]) + (" …" if len(bad) > 8 else "")
    result.warnings.append(
        "Non-finite (NaN/inf) value(s) in reported metrics: "
        f"{preview}. This usually indicates empty or very-low-count frames; "
        "interpret the affected results with caution and verify the acquisition."
    )


def run_nuclear_analysis(request: QARequest) -> QAResult:
    """
    Dispatch a nuclear-medicine QA request to the matching runner.

    Returns a failure QAResult (not a raise) for unknown analysis types so the
    worker thread surfaces a user-readable error.
    """
    runner = _NUCLEAR_RUNNERS.get(request.analysis_type)
    if runner is None:
        return QAResult(
            success=False,
            analysis_type=request.analysis_type,
            errors=[f"Unsupported nuclear analysis type: {request.analysis_type}"],
            study_uid=request.study_uid,
            series_uid=request.series_uid,
            modality=request.modality,
            pylinac_analysis_profile=build_nuclear_analysis_profile(
                request, engine="(unsupported nuclear analysis_type)"
            ),
        )
    result = runner(request)
    _warn_on_nonfinite_metrics(result)
    return result

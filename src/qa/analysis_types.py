"""
Normalized QA analysis types for Stage 1 pylinac integration.

This module defines small dataclasses used by the UI and worker thread to pass
requests/results without exposing pylinac internals directly to the rest of the
application.

Exports:
    LcRunConfig          -- one low-contrast parameter set for compare mode
    MRICompareRequest    -- batch of up to 3 LcRunConfig rows from the dialog
    MRIBatchResult       -- collected QAResult objects for a compare-mode run
    QARequest            -- input payload for a single QA analysis run
    QAResult             -- normalized output payload for a single QA run
    NuclearOptions       -- base for per-class pylinac.nuclear option payloads
    PlanarUniformityOptions / FourBarResolutionOptions / QuadrantResolutionOptions /
    CenterOfRotationOptions / TomographicResolutionOptions / MaxCountRateOptions /
    TomographicUniformityOptions / TomographicContrastOptions /
    SimpleSensitivityOptions
                         -- per-test nuclear option dataclasses
    build_pylinac_analysis_profile -- audit-trail dict for a QARequest
    build_nuclear_analysis_profile -- audit-trail dict for a nuclear QARequest
    physical_scan_extent_passes_relaxed -- relaxed z-extent helper
    is_physical_scan_extent_failure     -- error-list classifier
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar

from utils.config.qa_nuclear_config import (
    CENTER_OF_ROTATION_CLASS,
    DEFAULT_ACTIVITY_MBQ,
    DEFAULT_BAR_WIDTHS_MM,
    DEFAULT_CENTER_RATIO,
    DEFAULT_CFOV_RATIO,
    DEFAULT_DISTANCE_FROM_CENTER_MM,
    DEFAULT_FRAME_DURATION_S,
    DEFAULT_NUCLIDE,
    DEFAULT_ROI_DIAMETER_MM,
    DEFAULT_ROI_WIDTH_MM,
    DEFAULT_SEARCH_SLICES,
    DEFAULT_SEARCH_WINDOW_PX,
    DEFAULT_SEPARATION_MM,
    DEFAULT_SPHERE_ANGLES,
    DEFAULT_SPHERE_DIAMETERS_MM,
    DEFAULT_TC_UFOV_RATIO,
    DEFAULT_THRESHOLD,
    DEFAULT_TU_CFOV_RATIO,
    DEFAULT_TU_FIRST_FRAME,
    DEFAULT_TU_LAST_FRAME,
    DEFAULT_TU_THRESHOLD,
    DEFAULT_TU_UFOV_RATIO,
    DEFAULT_TU_WINDOW_SIZE,
    DEFAULT_UFOV_RATIO,
    DEFAULT_WINDOW_SIZE,
    FOUR_BAR_RESOLUTION_CLASS,
    MAX_COUNT_RATE_CLASS,
    PLANAR_UNIFORMITY_CLASS,
    QUADRANT_RESOLUTION_CLASS,
    SIMPLE_SENSITIVITY_CLASS,
    TOMOGRAPHIC_CONTRAST_CLASS,
    TOMOGRAPHIC_RESOLUTION_CLASS,
    TOMOGRAPHIC_UNIFORMITY_CLASS,
)
from utils.config.qa_pylinac_config import (
    DEFAULT_ACR_MRI_LOW_CONTRAST_METHOD,
    DEFAULT_ACR_MRI_LOW_CONTRAST_VISIBILITY_SANITY_MULTIPLIER,
    DEFAULT_ACR_MRI_LOW_CONTRAST_VISIBILITY_THRESHOLD,
)

# Substrings that identify pylinac's physical scan extent ValueError (CT/MRI/CatPhan base).
_PHYSICAL_SCAN_EXTENT_MARKERS = (
    "physical scan extent",
    "extent of module configuration",
    "scan extent does not",
)


def physical_scan_extent_passes_relaxed(
    min_scan: float,
    max_scan: float,
    min_config: float,
    max_config: float,
    tolerance_mm: float,
) -> bool:
    """
    Same comparison as pylinac CatPhanBase._ensure_physical_scan_extent, but
    widen the accepted scan range by tolerance_mm on both ends (pure math).
    """
    tol = max(0.0, float(tolerance_mm))
    min_s = round(float(min_scan), 1)
    max_s = round(float(max_scan), 1)
    min_c = round(float(min_config), 1)
    max_c = round(float(max_config), 1)
    return (min_c >= min_s - tol) and (max_c <= max_s + tol)


def is_physical_scan_extent_failure(errors: list[str]) -> bool:
    """True if error messages indicate CatPhanBase._ensure_physical_scan_extent failure."""
    if not errors:
        return False
    blob = " ".join(errors).lower()
    return any(m in blob for m in _PHYSICAL_SCAN_EXTENT_MARKERS)


def build_pylinac_analysis_profile(
    request: QARequest,
    *,
    engine: str,
) -> dict[str, Any]:
    """
    Canonical record of how this run differed from stock pylinac defaults.

    Populated for every run (success or failure). ``engine`` is the concrete
    class name used (e.g. ``ACRMRILargeForViewer``).

    ``relaxed_image_extent`` is True for viewer integration classes, which
    widen ``_is_within_image_extent`` vs stock pylinac (edge slices allowed).
    ``vanilla_pylinac`` mirrors ``QARequest.vanilla_pylinac`` (stock classes).
    ``vanilla_equivalent`` is only True when the run matches stock pylinac
    class + analyze defaults (typically false for bundled ACR workflows).
    """
    tol = float(getattr(request, "scan_extent_tolerance_mm", 0.0) or 0.0)
    req_vanilla = bool(getattr(request, "vanilla_pylinac", False))
    relaxed_image = "ForViewer" in engine and not req_vanilla
    scan_only_vanilla = tol <= 0.0 and "RelaxedExtent" not in engine
    vanilla = scan_only_vanilla and not relaxed_image
    profile: dict[str, Any] = {
        "engine": engine,
        "vanilla_equivalent": vanilla,
        "vanilla_pylinac": req_vanilla,
        "relaxed_image_extent": relaxed_image,
        "scan_extent_tolerance_mm": tol,
        "attempt": int(getattr(request, "qa_attempt", 1) or 1),
        "parent_attempt_outcome": getattr(request, "parent_attempt_outcome", None),
        "origin_slice_override": request.origin_slice,
        "check_uid": request.check_uid,
    }
    if request.analysis_type == "acr_mri_large":
        lc_method = str(
            getattr(
                request,
                "low_contrast_method",
                DEFAULT_ACR_MRI_LOW_CONTRAST_METHOD,
            )
            or DEFAULT_ACR_MRI_LOW_CONTRAST_METHOD
        )
        lc_threshold = float(
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
        profile["echo_number"] = request.echo_number
        profile["low_contrast_method"] = lc_method
        profile["low_contrast_visibility_threshold"] = lc_threshold
        profile["low_contrast_visibility_sanity_multiplier"] = lc_sanity
        profile["vanilla_equivalent"] = bool(
            vanilla
            and lc_method == DEFAULT_ACR_MRI_LOW_CONTRAST_METHOD
            and lc_threshold == DEFAULT_ACR_MRI_LOW_CONTRAST_VISIBILITY_THRESHOLD
            and lc_sanity
            == DEFAULT_ACR_MRI_LOW_CONTRAST_VISIBILITY_SANITY_MULTIPLIER
        )
    return profile


class NuclearOptions(ABC):
    """
    Base for per-class pylinac.nuclear option payloads.

    Each concrete subclass is a dataclass for one pylinac.nuclear test, fixes
    ``analysis_class`` as a ClassVar, and implements ``analyze_kwargs`` /
    ``is_pylinac_default``. Stored as the nested ``QARequest.nuclear_options``;
    runners and the dialog treat them polymorphically (a tagged union keyed on
    ``analysis_class``).
    """

    analysis_class: ClassVar[str] = ""

    @abstractmethod
    def analyze_kwargs(self) -> dict[str, Any]:
        """Return the kwargs to pass to this class's ``analyze()``."""

    @abstractmethod
    def is_pylinac_default(self) -> bool:
        """True when parameters match stock pylinac analyze() defaults."""


@dataclass
class PlanarUniformityOptions(NuclearOptions):
    """PlanarUniformity analyze() parameters (defaults mirror pylinac)."""

    analysis_class: ClassVar[str] = PLANAR_UNIFORMITY_CLASS
    ufov_ratio: float = DEFAULT_UFOV_RATIO
    cfov_ratio: float = DEFAULT_CFOV_RATIO
    window_size: int = DEFAULT_WINDOW_SIZE
    threshold: float = DEFAULT_THRESHOLD

    def analyze_kwargs(self) -> dict[str, Any]:
        return {
            "ufov_ratio": float(self.ufov_ratio),
            "cfov_ratio": float(self.cfov_ratio),
            "window_size": int(self.window_size),
            "threshold": float(self.threshold),
        }

    def is_pylinac_default(self) -> bool:
        return (
            float(self.ufov_ratio) == DEFAULT_UFOV_RATIO
            and float(self.cfov_ratio) == DEFAULT_CFOV_RATIO
            and int(self.window_size) == DEFAULT_WINDOW_SIZE
            and float(self.threshold) == DEFAULT_THRESHOLD
        )


@dataclass
class FourBarResolutionOptions(NuclearOptions):
    """FourBarResolution analyze() parameters."""

    analysis_class: ClassVar[str] = FOUR_BAR_RESOLUTION_CLASS
    separation_mm: float = DEFAULT_SEPARATION_MM
    roi_width_mm: float = DEFAULT_ROI_WIDTH_MM

    def analyze_kwargs(self) -> dict[str, Any]:
        return {
            "separation_mm": float(self.separation_mm),
            "roi_width_mm": float(self.roi_width_mm),
        }

    def is_pylinac_default(self) -> bool:
        return (
            float(self.separation_mm) == DEFAULT_SEPARATION_MM
            and float(self.roi_width_mm) == DEFAULT_ROI_WIDTH_MM
        )


@dataclass
class QuadrantResolutionOptions(NuclearOptions):
    """
    QuadrantResolution analyze() parameters.

    ``bar_widths_mm`` must be 4 values (one per quadrant); pylinac requires it
    and it is phantom-specific (no pylinac default), so only the ROI geometry is
    compared against pylinac defaults in ``is_pylinac_default``.
    """

    analysis_class: ClassVar[str] = QUADRANT_RESOLUTION_CLASS
    bar_widths_mm: tuple[float, ...] = DEFAULT_BAR_WIDTHS_MM
    roi_diameter_mm: float = DEFAULT_ROI_DIAMETER_MM
    distance_from_center_mm: float = DEFAULT_DISTANCE_FROM_CENTER_MM

    def analyze_kwargs(self) -> dict[str, Any]:
        return {
            "bar_widths": [float(w) for w in self.bar_widths_mm],
            "roi_diameter_mm": float(self.roi_diameter_mm),
            "distance_from_center_mm": float(self.distance_from_center_mm),
        }

    def is_pylinac_default(self) -> bool:
        return (
            float(self.roi_diameter_mm) == DEFAULT_ROI_DIAMETER_MM
            and float(self.distance_from_center_mm)
            == DEFAULT_DISTANCE_FROM_CENTER_MM
        )


@dataclass
class CenterOfRotationOptions(NuclearOptions):
    """CenterOfRotation — no analyze() parameters."""

    analysis_class: ClassVar[str] = CENTER_OF_ROTATION_CLASS

    def analyze_kwargs(self) -> dict[str, Any]:
        return {}

    def is_pylinac_default(self) -> bool:
        return True


@dataclass
class TomographicResolutionOptions(NuclearOptions):
    """TomographicResolution — no analyze() parameters."""

    analysis_class: ClassVar[str] = TOMOGRAPHIC_RESOLUTION_CLASS

    def analyze_kwargs(self) -> dict[str, Any]:
        return {}

    def is_pylinac_default(self) -> bool:
        return True


@dataclass
class MaxCountRateOptions(NuclearOptions):
    """MaxCountRate analyze() parameter (seconds per dynamic frame)."""

    analysis_class: ClassVar[str] = MAX_COUNT_RATE_CLASS
    frame_duration: float = DEFAULT_FRAME_DURATION_S

    def analyze_kwargs(self) -> dict[str, Any]:
        return {"frame_duration": float(self.frame_duration)}

    def is_pylinac_default(self) -> bool:
        return float(self.frame_duration) == DEFAULT_FRAME_DURATION_S


@dataclass
class TomographicUniformityOptions(NuclearOptions):
    """TomographicUniformity analyze() parameters (frame range + ratios)."""

    analysis_class: ClassVar[str] = TOMOGRAPHIC_UNIFORMITY_CLASS
    first_frame: int = DEFAULT_TU_FIRST_FRAME
    last_frame: int = DEFAULT_TU_LAST_FRAME
    ufov_ratio: float = DEFAULT_TU_UFOV_RATIO
    cfov_ratio: float = DEFAULT_TU_CFOV_RATIO
    center_ratio: float = DEFAULT_CENTER_RATIO
    threshold: float = DEFAULT_TU_THRESHOLD
    window_size: int = DEFAULT_TU_WINDOW_SIZE

    def analyze_kwargs(self) -> dict[str, Any]:
        return {
            "first_frame": int(self.first_frame),
            "last_frame": int(self.last_frame),
            "ufov_ratio": float(self.ufov_ratio),
            "cfov_ratio": float(self.cfov_ratio),
            "center_ratio": float(self.center_ratio),
            "threshold": float(self.threshold),
            "window_size": int(self.window_size),
        }

    def is_pylinac_default(self) -> bool:
        return (
            int(self.first_frame) == DEFAULT_TU_FIRST_FRAME
            and int(self.last_frame) == DEFAULT_TU_LAST_FRAME
            and float(self.ufov_ratio) == DEFAULT_TU_UFOV_RATIO
            and float(self.cfov_ratio) == DEFAULT_TU_CFOV_RATIO
            and float(self.center_ratio) == DEFAULT_CENTER_RATIO
            and float(self.threshold) == DEFAULT_TU_THRESHOLD
            and int(self.window_size) == DEFAULT_TU_WINDOW_SIZE
        )


@dataclass
class TomographicContrastOptions(NuclearOptions):
    """
    TomographicContrast analyze() parameters.

    ``sphere_diameters_mm`` and ``sphere_angles`` are 6-element sequences with
    pylinac defaults; the runner finds the spheres at those angles.
    """

    analysis_class: ClassVar[str] = TOMOGRAPHIC_CONTRAST_CLASS
    sphere_diameters_mm: tuple[float, ...] = DEFAULT_SPHERE_DIAMETERS_MM
    sphere_angles: tuple[float, ...] = DEFAULT_SPHERE_ANGLES
    ufov_ratio: float = DEFAULT_TC_UFOV_RATIO
    search_window_px: int = DEFAULT_SEARCH_WINDOW_PX
    search_slices: int = DEFAULT_SEARCH_SLICES

    def analyze_kwargs(self) -> dict[str, Any]:
        return {
            "sphere_diameters_mm": [float(d) for d in self.sphere_diameters_mm],
            "sphere_angles": [float(a) for a in self.sphere_angles],
            "ufov_ratio": float(self.ufov_ratio),
            "search_window_px": int(self.search_window_px),
            "search_slices": int(self.search_slices),
        }

    def is_pylinac_default(self) -> bool:
        return (
            tuple(float(d) for d in self.sphere_diameters_mm)
            == tuple(float(d) for d in DEFAULT_SPHERE_DIAMETERS_MM)
            and tuple(float(a) for a in self.sphere_angles)
            == tuple(float(a) for a in DEFAULT_SPHERE_ANGLES)
            and float(self.ufov_ratio) == DEFAULT_TC_UFOV_RATIO
            and int(self.search_window_px) == DEFAULT_SEARCH_WINDOW_PX
            and int(self.search_slices) == DEFAULT_SEARCH_SLICES
        )


@dataclass
class SimpleSensitivityOptions(NuclearOptions):
    """
    SimpleSensitivity parameters.

    Unlike every other nuclear test, this one takes a **second** (background)
    DICOM and an administered activity + nuclide. ``nuclide`` is a string name
    (the dialog must not import pylinac); the runner maps it to pylinac's
    ``Nuclide`` enum. ``analyze_kwargs`` is provenance-only — the runner does NOT
    splat it into ``analyze()`` (``background_path`` is a constructor arg and the
    nuclide must be converted to the enum first).
    """

    analysis_class: ClassVar[str] = SIMPLE_SENSITIVITY_CLASS
    activity_mbq: float = DEFAULT_ACTIVITY_MBQ
    nuclide: str = DEFAULT_NUCLIDE
    background_path: str | None = None

    def analyze_kwargs(self) -> dict[str, Any]:
        return {
            "activity_mbq": float(self.activity_mbq),
            "nuclide": str(self.nuclide),
            "background_path": self.background_path,
        }

    def is_pylinac_default(self) -> bool:
        # Activity/nuclide are always user-supplied (no pylinac default), so a
        # SimpleSensitivity run is never "stock-default".
        return False


def build_nuclear_analysis_profile(
    request: QARequest,
    *,
    engine: str,
) -> dict[str, Any]:
    """
    Provenance record for a pylinac.nuclear run.

    Deliberately omits the ACR-only keys produced by
    ``build_pylinac_analysis_profile`` (scan-extent tolerance, relaxed image
    extent, origin slice) which have no meaning for nuclear analyses. Populated
    for every run, success or failure.
    """
    opts = getattr(request, "nuclear_options", None)
    input_path = request.dicom_paths[0] if request.dicom_paths else None
    return {
        "engine": engine,
        "module": "pylinac.nuclear",
        "nuclear_analysis_class": getattr(opts, "analysis_class", None),
        "analysis_parameters": opts.analyze_kwargs() if opts is not None else {},
        "vanilla_equivalent": opts.is_pylinac_default() if opts is not None else None,
        "input_path": input_path,
    }


@dataclass
class QARequest:
    """Input payload for a QA analysis run."""

    analysis_type: str
    dicom_paths: list[str] = field(default_factory=list)
    folder_path: str | None = None
    origin_slice: int | None = None
    output_pdf_path: str | None = None
    study_uid: str = ""
    series_uid: str = ""
    modality: str = ""
    # ACR MRI Large (pylinac): echo selection; None = library default (lowest echo).
    echo_number: int | None = None
    # Documented for sagittal-in-separate-series workflows; stored in JSON for reproducibility.
    # Current pylinac ACRMRILarge may not expose this flag on analyze().
    check_uid: bool = True
    preflight_warnings: list[str] = field(default_factory=list)
    # Relaxed CatPhanBase scan-extent check (mm). 0 = delegate to stock
    # _ensure_physical_scan_extent on ACRCTForViewer / ACRMRILargeForViewer.
    # Ignored when vanilla_pylinac is True (stock classes have no viewer tolerance hook).
    scan_extent_tolerance_mm: float = 0.0
    # Use stock ACRCT / ACRMRILarge (strict interior-only origin slice rule in pylinac).
    vanilla_pylinac: bool = False
    # ACR MRI Large: passed to pylinac analyze(low_contrast_method=...).
    low_contrast_method: str = DEFAULT_ACR_MRI_LOW_CONTRAST_METHOD
    # ACR MRI Large: passed to pylinac analyze(low_contrast_visibility_threshold=...).
    low_contrast_visibility_threshold: float = (
        DEFAULT_ACR_MRI_LOW_CONTRAST_VISIBILITY_THRESHOLD
    )
    # ACR MRI Large: passed to pylinac analyze(low_contrast_visibility_sanity_multiplier=...).
    low_contrast_visibility_sanity_multiplier: float = (
        DEFAULT_ACR_MRI_LOW_CONTRAST_VISIBILITY_SANITY_MULTIPLIER
    )
    # Run attempt for user-visible retries (1 = first run).
    qa_attempt: int = 1
    # When set, documents why this attempt was started (e.g. strict extent failure).
    parent_attempt_outcome: str | None = None
    # Nuclear-medicine QA parameters (None for ACR analyses). One of the
    # NuclearOptions subclasses. Nuclear classes take a single DICOM file; the
    # runner uses dicom_paths[0]. See qa.pylinac_nuclear.
    nuclear_options: NuclearOptions | None = None


@dataclass
class QAResult:
    """Normalized output payload for a QA analysis run."""

    success: bool
    analysis_type: str
    metrics: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    raw_pylinac: dict[str, Any] = field(default_factory=dict)
    pdf_report_path: str | None = None
    study_uid: str = ""
    series_uid: str = ""
    modality: str = ""
    num_images: int = 0
    pylinac_version: str | None = None
    pylinac_analysis_profile: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Compare-mode types (multi-run low-contrast analysis)
# ---------------------------------------------------------------------------


@dataclass
class LcRunConfig:
    """
    One low-contrast parameter set for a compare-mode batch.

    Each enabled row in the compare table produces one LcRunConfig which is
    passed to run_acr_mri_large_batch().  The label is shown in the results
    table and stored in JSON for traceability.

    Fields:
        label: Short user-visible name, e.g. "Run 1".
        low_contrast_method: Contrast algorithm (one of ACR_MRI_LOW_CONTRAST_METHODS).
        low_contrast_visibility_threshold: Rose-model visibility cut-off passed to
            pylinac analyze().
        low_contrast_visibility_sanity_multiplier: Spoke-1 sanity cap multiplier passed
            to pylinac analyze().
    """

    label: str
    low_contrast_method: str
    low_contrast_visibility_threshold: float
    low_contrast_visibility_sanity_multiplier: float


@dataclass
class MRICompareRequest:
    """
    Carries the per-run low-contrast configs chosen in the options dialog.

    Populated only when the user enables compare mode.  The base QARequest
    (first enabled row) still drives the standard pylinac PDF; MRICompareRequest
    drives the remaining runs and the batch JSON export.

    Fields:
        run_configs: 1–3 LcRunConfig entries, guaranteed non-empty and
            in the order the user configured them.
    """

    run_configs: list[LcRunConfig] = field(default_factory=list)


@dataclass
class MRIBatchResult:
    """
    Result container for a multi-run low-contrast comparison.

    run_results and run_configs are parallel lists (same length).

    Fields:
        run_results: One QAResult per LcRunConfig, in the same order.
        run_configs: The LcRunConfig list that drove this batch.
    """

    run_results: list[QAResult] = field(default_factory=list)
    run_configs: list[LcRunConfig] = field(default_factory=list)

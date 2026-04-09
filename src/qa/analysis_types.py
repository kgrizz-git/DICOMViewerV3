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
    build_pylinac_analysis_profile -- audit-trail dict for a QARequest
    physical_scan_extent_passes_relaxed -- relaxed z-extent helper
    is_physical_scan_extent_failure     -- error-list classifier
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

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


def is_physical_scan_extent_failure(errors: List[str]) -> bool:
    """True if error messages indicate CatPhanBase._ensure_physical_scan_extent failure."""
    if not errors:
        return False
    blob = " ".join(errors).lower()
    return any(m in blob for m in _PHYSICAL_SCAN_EXTENT_MARKERS)


def build_pylinac_analysis_profile(
    request: "QARequest",
    *,
    engine: str,
) -> Dict[str, Any]:
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
    profile: Dict[str, Any] = {
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


@dataclass
class QARequest:
    """Input payload for a QA analysis run."""

    analysis_type: str
    dicom_paths: List[str] = field(default_factory=list)
    folder_path: Optional[str] = None
    origin_slice: Optional[int] = None
    output_pdf_path: Optional[str] = None
    study_uid: str = ""
    series_uid: str = ""
    modality: str = ""
    # ACR MRI Large (pylinac): echo selection; None = library default (lowest echo).
    echo_number: Optional[int] = None
    # Documented for sagittal-in-separate-series workflows; stored in JSON for reproducibility.
    # Current pylinac ACRMRILarge may not expose this flag on analyze().
    check_uid: bool = True
    preflight_warnings: List[str] = field(default_factory=list)
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
    parent_attempt_outcome: Optional[str] = None


@dataclass
class QAResult:
    """Normalized output payload for a QA analysis run."""

    success: bool
    analysis_type: str
    metrics: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    raw_pylinac: Dict[str, Any] = field(default_factory=dict)
    pdf_report_path: Optional[str] = None
    study_uid: str = ""
    series_uid: str = ""
    modality: str = ""
    num_images: int = 0
    pylinac_version: Optional[str] = None
    pylinac_analysis_profile: Dict[str, Any] = field(default_factory=dict)


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

    run_configs: List[LcRunConfig] = field(default_factory=list)


@dataclass
class MRIBatchResult:
    """
    Result container for a multi-run low-contrast comparison.

    run_results and run_configs are parallel lists (same length).

    Fields:
        run_results: One QAResult per LcRunConfig, in the same order.
        run_configs: The LcRunConfig list that drove this batch.
    """

    run_results: List[QAResult] = field(default_factory=list)
    run_configs: List[LcRunConfig] = field(default_factory=list)

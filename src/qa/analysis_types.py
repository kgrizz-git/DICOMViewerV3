"""
Normalized QA analysis types for Stage 1 pylinac integration.

This module defines small dataclasses used by the UI and worker thread to pass
requests/results without exposing pylinac internals directly to the rest of the
application.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

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
    class name used (e.g. ``ACRMRILarge`` or ``ACRMRILargeRelaxedExtent``).
    """
    tol = float(getattr(request, "scan_extent_tolerance_mm", 0.0) or 0.0)
    vanilla = tol <= 0.0 and "RelaxedExtent" not in engine
    profile: Dict[str, Any] = {
        "engine": engine,
        "vanilla_equivalent": vanilla,
        "scan_extent_tolerance_mm": tol,
        "attempt": int(getattr(request, "qa_attempt", 1) or 1),
        "parent_attempt_outcome": getattr(request, "parent_attempt_outcome", None),
        "origin_slice_override": request.origin_slice,
        "check_uid": request.check_uid,
    }
    if request.analysis_type == "acr_mri_large":
        profile["echo_number"] = request.echo_number
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
    # Relaxed CatPhanBase scan-extent check (mm). 0 = stock pylinac behavior.
    scan_extent_tolerance_mm: float = 0.0
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

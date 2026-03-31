"""
Normalized QA analysis types for Stage 1 pylinac integration.

This module defines small dataclasses used by the UI and worker thread to pass
requests/results without exposing pylinac internals directly to the rest of the
application.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


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


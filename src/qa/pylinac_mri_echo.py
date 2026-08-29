"""
Resolve which MRI echo to pass into pylinac ``ACRMRILarge.analyze()``.

Stock pylinac uses the **lowest** ``EchoNumber`` when ``echo_number=None``.
ACR T2 dual-echo series put T2-weighted images on the **highest** echo
(typically echo 2 / TE≈80); echo 1 is proton-density and is not used for ACR
QC. This helper therefore treats ``QARequest.echo_number is None`` as
**auto-highest**.

Inputs:
    A ``QARequest`` (explicit ``echo_number``, or DICOM paths / folder).

Outputs:
    The integer echo to pass to ``analyze()``, or ``None`` when no
    ``EchoNumber`` / ``EchoNumbers`` tags can be read (pylinac then falls
    back to its library minimum).

Requirements:
    pydicom header-only reads (``stop_before_pixels=True``). Never log paths
    or PHI. Qt-free.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from qa.analysis_types import QARequest


def coerce_echo_number(value: object) -> int | None:
    """Parse a DICOM EchoNumber / EchoNumbers value to a positive int."""
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        parsed = [coerce_echo_number(item) for item in value]
        found = [item for item in parsed if item is not None]
        return max(found) if found else None
    try:
        # MultiValue and IS types stringify to a digit; skip empty.
        text = str(value).strip()
        if not text:
            return None
        number = int(float(text))
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _echo_from_dataset(dataset: Any) -> int | None:
    """Read EchoNumbers (0018,0086) then EchoNumber from a pydicom dataset."""
    for attr in ("EchoNumbers", "EchoNumber"):
        parsed = coerce_echo_number(getattr(dataset, attr, None))
        if parsed is not None:
            return parsed
    return None


def _candidate_dicom_paths(request: QARequest) -> list[str]:
    """Paths to scan for echo tags.

    ``dicom_paths`` wins. ``folder_path`` walks files recursively so a series
    nested under the selected folder still contributes EchoNumber tags.
    Unreadable or non-DICOM files are skipped later.
    """
    if request.dicom_paths:
        return [str(path) for path in request.dicom_paths]
    folder = request.folder_path
    if not folder:
        return []
    root = Path(folder)
    if not root.is_dir():
        return []
    return [str(path) for path in sorted(root.rglob("*")) if path.is_file()]


def highest_echo_number_from_paths(paths: list[str]) -> int | None:
    """
    Return the maximum EchoNumber found in *paths*.

    Unreadable files are skipped. Does not log path names.
    """
    if not paths:
        return None
    try:
        import pydicom
    except Exception:
        return None

    found: list[int] = []
    for path in paths:
        try:
            dataset = pydicom.dcmread(path, stop_before_pixels=True, force=True)
        except Exception:
            continue
        parsed = _echo_from_dataset(dataset)
        if parsed is not None:
            found.append(parsed)
    return max(found) if found else None


def resolve_mri_analyze_echo_number(request: QARequest) -> int | None:
    """
    Echo integer to pass to pylinac ``analyze(echo_number=...)``.

    Explicit ``request.echo_number`` wins. ``None`` means auto-highest from
    DICOM headers; when no tags are present, returns ``None`` so pylinac uses
    its library minimum.
    """
    if request.echo_number is not None:
        try:
            return int(request.echo_number)
        except (TypeError, ValueError):
            return None
    return highest_echo_number_from_paths(_candidate_dicom_paths(request))


def stamp_analyzed_echo_on_profile(
    profile: dict[str, Any],
    request: QARequest,
    analyzed_echo: int | None,
) -> None:
    """Record requested vs analyzed echo on ``pylinac_analysis_profile``."""
    profile["echo_number"] = analyzed_echo
    profile["echo_number_requested"] = request.echo_number
    profile["echo_number_auto_highest"] = request.echo_number is None


def stamp_resolved_echo_on_profile(
    profile: dict[str, Any], request: QARequest
) -> int | None:
    """Resolve echo from the request and stamp requested vs analyzed on *profile*.

    Call this as soon as the audit profile exists so early returns (missing
    pylinac, invalid source, worker isolation) still record echo provenance.
    """
    analyzed_echo = resolve_mri_analyze_echo_number(request)
    stamp_analyzed_echo_on_profile(profile, request, analyzed_echo)
    return analyzed_echo


def overlay_analyzed_echo_metrics(
    metrics: dict[str, Any],
    request: QARequest,
    analyzed_echo: int | None,
) -> None:
    """Record requested vs analyzed echo on curated ``QAResult.metrics``."""
    metrics["echo_number"] = analyzed_echo
    metrics["echo_number_requested"] = request.echo_number
    if request.echo_number is None:
        metrics["echo_number_auto_highest"] = True

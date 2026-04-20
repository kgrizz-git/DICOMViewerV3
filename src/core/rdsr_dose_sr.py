"""
Radiation dose structured report (RDSR / X-Ray Radiation Dose SR) — detection and CT dose extraction.

This module provides **bounded** walks of DICOM SR ``ContentSequence`` trees to recognize
**X-Ray Radiation Dose SR** instances (DICOM TID **10001** *CT Radiation Dose* family) and to
collect a small set of **CT** metrics and identifiers useful for in-app traceability.

**Inputs:** a ``pydicom.dataset.Dataset`` loaded from disk (header + document content).

**Outputs:** ``CtRadiationDoseSummary`` (dataclass) and boolean helpers for load/index gates.

**Requirements:** ``pydicom`` plus :mod:`core.sr_concept_identity` for normalized concept-name
matching (same rules as dose-event extraction). Parsing is **not** a full generic SR renderer;
unknown vendor templates may yield partial summaries without error.

**DICOM references (concept codes, DCM):** PS3.16 **DCM** codes **113830** (CTDIvol), **113838**
(DLP), **113835** (size-specific dose estimate), **113819** (CT irradiation event data container).

See ``dev-docs/plans/supporting/HANGING_PROTOCOLS_PRIORS_RDSR_PLAN.md`` §3 for scope and MVP limits.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
import csv
import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Final, TypedDict, cast

from pydicom.dataset import Dataset
from pydicom.uid import (
    Comprehensive3DSRStorage,
    ComprehensiveSRStorage,
    EnhancedSRStorage,
    EnhancedXRayRadiationDoseSRStorage,
    ExtensibleSRStorage,
    XRayRadiationDoseSRStorage,
)

from core.sr_concept_identity import concept_identity_matches

# pydicom element access is largely untyped in stubs; keep checks explicit at runtime.
# pyright: reportAny=false
# pyright: reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false

# --- SOP Class UID sets (string form for stable comparisons) ---

PRIMARY_XRAY_RADIATION_DOSE_SR_SOP_CLASS_UIDS: Final[frozenset[str]] = frozenset(
    {
        str(XRayRadiationDoseSRStorage),
        str(EnhancedXRayRadiationDoseSRStorage),
    }
)

GENERIC_SR_STORAGE_SOP_CLASS_UIDS: Final[frozenset[str]] = frozenset(
    {
        str(ComprehensiveSRStorage),
        str(Comprehensive3DSRStorage),
        str(ExtensibleSRStorage),
        str(EnhancedSRStorage),
    }
)

# --- DICOM PS3.16 DCM concept codes (Code Value, Coding Scheme Designator) ---

_CODE_CTDI_VOL: Final[tuple[str, str]] = ("113830", "DCM")
_CODE_DLP: Final[tuple[str, str]] = ("113838", "DCM")
_CODE_SSDE: Final[tuple[str, str]] = ("113835", "DCM")
_CODE_CT_IRRADIATION_EVENT: Final[tuple[str, str]] = ("113819", "DCM")

_DEFAULT_MAX_DEPTH: Final[int] = 24
_DEFAULT_MAX_NODES: Final[int] = 8000
_SIGNATURE_PROBE_NODES: Final[int] = 512
_SIGNATURE_PROBE_DEPTH: Final[int] = 16


class RadiationDoseSrParseError(ValueError):
    """Raised when ``parse_ct_radiation_dose_summary`` is called on a non–dose-SR dataset."""


class _HeaderFields(TypedDict):
    study_instance_uid: str | None
    series_instance_uid: str | None
    sop_instance_uid: str | None
    manufacturer: str | None
    manufacturer_model_name: str | None
    device_serial_number: str | None


@dataclass(frozen=True)
class CtRadiationDoseSummary:
    """Minimal CT radiation dose fields extracted from an SR document."""

    study_instance_uid: str | None = None
    series_instance_uid: str | None = None
    sop_instance_uid: str | None = None
    manufacturer: str | None = None
    manufacturer_model_name: str | None = None
    device_serial_number: str | None = None
    ctdi_vol_mgy: float | None = None
    dlp_mgy_cm: float | None = None
    ssde_mgy: float | None = None
    irradiation_event_count: int = 0
    parse_node_cap_hit: bool = field(default=False, compare=False)


def _sop_class_uid_str(ds: Dataset) -> str:
    uid = getattr(ds, "SOPClassUID", None)
    return str(uid) if uid is not None else ""


def _modality_str(ds: Dataset) -> str:
    m = getattr(ds, "Modality", None)
    return str(m).strip() if m is not None else ""


def _concept_matches(item: Dataset, expected: tuple[str, str]) -> bool:
    """True when the item's concept name matches ``expected`` after :mod:`core.sr_concept_identity` normalization."""
    return concept_identity_matches(item, expected)


def _parse_numeric_measurement(item: Dataset) -> float | None:
    """Read the first numeric value from a NUM content item's Measured Value Sequence."""
    mseq = getattr(item, "MeasuredValueSequence", None)
    if not mseq:
        return None
    mlist = cast(Sequence[Dataset], mseq)
    if len(mlist) == 0:
        return None
    mv = mlist[0]
    fpv = getattr(mv, "FloatingPointValue", None)
    if fpv is not None:
        try:
            return float(fpv)
        except (TypeError, ValueError):
            pass
    nv_raw = getattr(mv, "NumericValue", None)
    if nv_raw is None:
        return None
    nv_first: object
    if isinstance(nv_raw, (list, tuple)):
        nseq = cast(Sequence[object], nv_raw)
        if len(nseq) == 0:
            return None
        nv_first = nseq[0]
    else:
        nv_first = nv_raw
    try:
        return float(str(nv_first).strip())
    except (TypeError, ValueError):
        return None


def _walk_content_items(
    items: Sequence[Dataset],
    *,
    max_depth: int,
    max_nodes: int,
    truncation_flag: list[bool] | None = None,
) -> Iterator[tuple[Dataset, int]]:
    """
    Depth-first iteration over SR content items.

    Yields ``(item, depth)`` until ``max_nodes`` items have been yielded. If the tree still has
    unvisited nodes after the cap, ``truncation_flag[0]`` is set to True when ``truncation_flag``
    is a single-element list passed by the caller.
    """
    if len(items) == 0:
        return
    stack: list[tuple[Dataset, int]] = [(it, 0) for it in list(items)][::-1]
    yielded = 0
    while stack and yielded < max_nodes:
        item, depth = stack.pop()
        yielded += 1
        yield item, depth
        if depth >= max_depth:
            if truncation_flag is not None and getattr(item, "ContentSequence", None):
                truncation_flag[0] = True
            continue
        nested = getattr(item, "ContentSequence", None)
        if nested:
            children = cast(Sequence[Dataset], nested)
            for child in reversed(list(children)):
                stack.append((child, depth + 1))
    if truncation_flag is not None and stack:
        truncation_flag[0] = True


def _bounded_has_ct_dose_numeric_signature(
    ds: Dataset,
    *,
    max_nodes: int = _SIGNATURE_PROBE_NODES,
    max_depth: int = _SIGNATURE_PROBE_DEPTH,
) -> bool:
    """
    True if a bounded walk finds a NUM item named (113830) or (113838) in DCM — CT dose family.
    Used for legacy / generic SR SOP classes that may embed TID 10001 content.
    """
    root = getattr(ds, "ContentSequence", None)
    if not root:
        return False
    root_items = cast(Sequence[Dataset], root)
    for item, _depth in _walk_content_items(
        list(root_items), max_depth=max_depth, max_nodes=max_nodes, truncation_flag=None
    ):
        vt = getattr(item, "ValueType", None)
        if str(vt).strip().upper() != "NUM":
            continue
        if _concept_matches(item, _CODE_CTDI_VOL) or _concept_matches(item, _CODE_DLP):
            return True
    return False


def is_radiation_dose_sr(
    ds: Dataset,
    *,
    max_signature_nodes: int = _SIGNATURE_PROBE_NODES,
    max_signature_depth: int = _SIGNATURE_PROBE_DEPTH,
) -> bool:
    """
    Return True if ``ds`` should be treated as a radiation dose SR for CT dose parsing.

    **Primary:** ``SOPClassUID`` is **X-Ray Radiation Dose SR** or **Enhanced X-Ray Radiation Dose SR**
    (DICOM storage classes for CT/projection dose reporting templates).

    **Secondary:** ``Modality`` is **SR** and ``SOPClassUID`` is a generic SR storage class, and a
    bounded ``ContentSequence`` scan finds CT dose **NUM** concepts (**113830** / **113838**, DCM).
    """
    sop = _sop_class_uid_str(ds)
    if sop in PRIMARY_XRAY_RADIATION_DOSE_SR_SOP_CLASS_UIDS:
        return True
    if _modality_str(ds).upper() == "SR" and sop in GENERIC_SR_STORAGE_SOP_CLASS_UIDS:
        return _bounded_has_ct_dose_numeric_signature(
            ds, max_nodes=max_signature_nodes, max_depth=max_signature_depth
        )
    return False


def _header_uids_and_device(ds: Dataset) -> _HeaderFields:
    def _clean_uid(val: object) -> str | None:
        if val is None or val == "":
            return None
        return str(val).strip() or None

    return cast(
        _HeaderFields,
        cast(
            object,
            {
                "study_instance_uid": _clean_uid(getattr(ds, "StudyInstanceUID", None)),
                "series_instance_uid": _clean_uid(getattr(ds, "SeriesInstanceUID", None)),
                "sop_instance_uid": _clean_uid(getattr(ds, "SOPInstanceUID", None)),
                "manufacturer": _clean_uid(getattr(ds, "Manufacturer", None)),
                "manufacturer_model_name": _clean_uid(getattr(ds, "ManufacturerModelName", None)),
                "device_serial_number": _clean_uid(getattr(ds, "DeviceSerialNumber", None)),
            },
        ),
    )


def parse_ct_radiation_dose_summary(
    ds: Dataset,
    *,
    max_depth: int = _DEFAULT_MAX_DEPTH,
    max_nodes: int = _DEFAULT_MAX_NODES,
) -> CtRadiationDoseSummary:
    """
    Parse CT radiation dose metrics from a dose SR dataset.

    Walks ``ContentSequence`` up to ``max_depth`` / ``max_nodes``. The first matching **NUM**
    for each of CTDIvol, DLP, and SSDE wins (document order). **Irradiation event** count is the
    number of content items whose concept matches **113819** (DCM).

    Raises:
        RadiationDoseSrParseError: if :func:`is_radiation_dose_sr` is False for ``ds``.
    """
    if not is_radiation_dose_sr(
        ds,
        max_signature_nodes=min(_SIGNATURE_PROBE_NODES, max_nodes),
        max_signature_depth=min(_SIGNATURE_PROBE_DEPTH, max_depth),
    ):
        raise RadiationDoseSrParseError(
            "Dataset is not a recognized radiation dose SR (SOP Class / modality / content signature)."
        )

    header: _HeaderFields = _header_uids_and_device(ds)
    ctdi: float | None = None
    dlp: float | None = None
    ssde: float | None = None
    events = 0
    cap_hit = False

    root = getattr(ds, "ContentSequence", None)
    trunc: list[bool] = [False]
    if root:
        root_list = cast(Sequence[Dataset], root)
        for item, _depth in _walk_content_items(
            list(root_list), max_depth=max_depth, max_nodes=max_nodes, truncation_flag=trunc
        ):
            if _concept_matches(item, _CODE_CT_IRRADIATION_EVENT):
                events += 1
            vt = getattr(item, "ValueType", None)
            if str(vt).strip().upper() != "NUM":
                continue
            val = _parse_numeric_measurement(item)
            if val is None:
                continue
            if ctdi is None and _concept_matches(item, _CODE_CTDI_VOL):
                ctdi = val
            elif dlp is None and _concept_matches(item, _CODE_DLP):
                dlp = val
            elif ssde is None and _concept_matches(item, _CODE_SSDE):
                ssde = val
        cap_hit = bool(trunc[0])

    return CtRadiationDoseSummary(
        study_instance_uid=header["study_instance_uid"],
        series_instance_uid=header["series_instance_uid"],
        sop_instance_uid=header["sop_instance_uid"],
        manufacturer=header["manufacturer"],
        manufacturer_model_name=header["manufacturer_model_name"],
        device_serial_number=header["device_serial_number"],
        ctdi_vol_mgy=ctdi,
        dlp_mgy_cm=dlp,
        ssde_mgy=ssde,
        irradiation_event_count=events,
        parse_node_cap_hit=cap_hit,
    )


DOSE_SUMMARY_EXPORT_VERSION: Final[str] = "1"


def apply_privacy_to_ct_radiation_dose_summary(
    summary: CtRadiationDoseSummary,
) -> CtRadiationDoseSummary:
    """
    Return a copy of ``summary`` with study/series/SOP UIDs and device-identifying
    strings replaced for **Privacy Mode** display (align with study index masking style).
    """
    mask = "***"
    return replace(
        summary,
        study_instance_uid=mask if summary.study_instance_uid else None,
        series_instance_uid=mask if summary.series_instance_uid else None,
        sop_instance_uid=mask if summary.sop_instance_uid else None,
        manufacturer=mask if summary.manufacturer else None,
        manufacturer_model_name=mask if summary.manufacturer_model_name else None,
        device_serial_number=mask if summary.device_serial_number else None,
    )


def dose_summary_to_export_dict(
    summary: CtRadiationDoseSummary,
    *,
    anonymize: bool,
) -> dict[str, Any]:
    """
    Flat dict for JSON/CSV export. When ``anonymize`` is True, string identifiers are masked.

    Numeric dose fields are always included (not considered direct PHI in typical workflows).
    """
    priv = apply_privacy_to_ct_radiation_dose_summary(summary) if anonymize else summary
    return {
        "dose_summary_version": DOSE_SUMMARY_EXPORT_VERSION,
        "study_instance_uid": priv.study_instance_uid,
        "series_instance_uid": priv.series_instance_uid,
        "sop_instance_uid": priv.sop_instance_uid,
        "manufacturer": priv.manufacturer,
        "manufacturer_model_name": priv.manufacturer_model_name,
        "device_serial_number": priv.device_serial_number,
        "ctdi_vol_mgy": priv.ctdi_vol_mgy,
        "dlp_mgy_cm": priv.dlp_mgy_cm,
        "ssde_mgy": priv.ssde_mgy,
        "irradiation_event_count": priv.irradiation_event_count,
        "parse_node_cap_hit": priv.parse_node_cap_hit,
    }


def write_dose_summary_json(
    path: str | Path,
    summary: CtRadiationDoseSummary,
    *,
    anonymize: bool,
) -> None:
    """Write :func:`dose_summary_to_export_dict` as UTF-8 JSON."""
    p = Path(path)
    payload = dose_summary_to_export_dict(summary, anonymize=anonymize)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_dose_summary_csv(
    path: str | Path,
    summary: CtRadiationDoseSummary,
    *,
    anonymize: bool,
) -> None:
    """Write a single-row CSV of the dose summary (flattened)."""

    def _safe_spreadsheet_value(v: object) -> object:
        if isinstance(v, str) and v[:1] in ("=", "+", "-", "@"):
            return "'" + v
        return v

    p = Path(path)
    row = dose_summary_to_export_dict(summary, anonymize=anonymize)
    fieldnames = [
        "dose_summary_version",
        "study_instance_uid",
        "series_instance_uid",
        "sop_instance_uid",
        "manufacturer",
        "manufacturer_model_name",
        "device_serial_number",
        "ctdi_vol_mgy",
        "dlp_mgy_cm",
        "ssde_mgy",
        "irradiation_event_count",
        "parse_node_cap_hit",
    ]
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerow({k: _safe_spreadsheet_value(row.get(k, "")) for k in fieldnames})

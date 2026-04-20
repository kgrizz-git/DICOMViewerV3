"""
RDSR irradiation event rows — table-oriented extract from X-Ray / CT dose SR templates.

**Purpose:** Find **irradiation event** containers in radiation dose SR instances (PS3.16
**TID 10003** *Irradiation Event X-Ray Data* code **113706**, **TID 10011**-style **CT**
events **113819**, and Enhanced-RDSR event-summary style concept names), then flatten common
NUM/CODE/TEXT children into string columns for a ``QTableView``.

**Inputs:** ``pydicom.dataset.Dataset`` (typically ``Modality`` **SR**, dose-related SOP class).

**Outputs:** :class:`IrradiationEventExtraction` with rows and optional notes.

**Requirements:** ``pydicom`` only. Uses the same concept matching style as ``rdsr_dose_sr``.

This is **not** a full TID validator; unknown vendor nesting may yield partial columns.
After a curated set of **standard** columns, any remaining **NUM/CODE/TEXT/DATETIME/UIDREF**
items under the event (including private coding schemes) are appended as **dynamic** columns
so vendor-specific geometry (e.g. Philips ``99PHI-IXR-XPER``) still appears in the dose-events table.

See ``dev-docs/plans/supporting/SR_FULL_FIDELITY_BROWSER_PLAN.md`` §6 Phase 3.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Final, cast

from pydicom.dataset import Dataset
from pydicom.sequence import Sequence as DicomSequence

from core.rdsr_dose_sr import _concept_tuple, is_radiation_dose_sr

_CODE_IRR_EVENT_XRAY: Final[tuple[str, str]] = ("113706", "DCM")
_CODE_IRR_EVENT_CT: Final[tuple[str, str]] = ("113819", "DCM")

_EVENT_CONCEPTS: Final[tuple[tuple[str, str], ...]] = (
    _CODE_IRR_EVENT_XRAY,
    _CODE_IRR_EVENT_CT,
)


def _concept_matches(item: Dataset, expected: tuple[str, str]) -> bool:
    cv, scheme = _concept_tuple(item)
    return cv == expected[0] and scheme == expected[1]


def _concept_meta(item: Dataset) -> tuple[str, str, str]:
    """Return (code_value, scheme, code_meaning) from Concept Name Code Sequence."""
    cseq = getattr(item, "ConceptNameCodeSequence", None)
    if not cseq or len(cast(DicomSequence, cseq)) == 0:
        return ("", "", "")
    c0 = cast(DicomSequence, cseq)[0]
    cv = str(getattr(c0, "CodeValue", "") or "").strip()
    scheme = str(getattr(c0, "CodingSchemeDesignator", "") or "").strip()
    meaning = str(getattr(c0, "CodeMeaning", "") or "").strip()
    return (cv, scheme, meaning)


def _concept_column_title(item: Dataset) -> str:
    cv, scheme, meaning = _concept_meta(item)
    if meaning and cv and scheme:
        return f"{meaning} ({cv}, {scheme})"
    if cv and scheme:
        return f"({cv}, {scheme})"
    return meaning or "Concept"


def _is_event_root(item: Dataset) -> tuple[str, str] | None:
    if str(getattr(item, "ValueType", "") or "").strip().upper() != "CONTAINER":
        return None
    for code in _EVENT_CONCEPTS:
        if _concept_matches(item, code):
            return code
    cseq = getattr(item, "ConceptNameCodeSequence", None)
    if cseq and len(cast(DicomSequence, cseq)) > 0:
        c0 = cast(DicomSequence, cseq)[0]
        meaning = str(getattr(c0, "CodeMeaning", "") or "").strip().upper()
        if "IRRADIATION EVENT" in meaning and (
            "SUMMARY" in meaning or "X-RAY DATA" in meaning or "CT IRRADIATION EVENT" in meaning
        ):
            return ("MEANING_MATCH", "N/A")
    return None


def _flatten_descendants(
    item: Dataset,
    *,
    max_depth: int = 14,
    max_items: int = 1500,
) -> list[Dataset]:
    """Depth-first list of content items under ``item`` (excluding ``item`` itself)."""
    out: list[Dataset] = []
    stack: list[tuple[Dataset, int]] = []
    nested = getattr(item, "ContentSequence", None)
    if nested:
        for ch in reversed(list(cast(DicomSequence, nested))):
            stack.append((ch, 1))
    while stack and len(out) < max_items:
        it, d = stack.pop()
        out.append(it)
        if d >= max_depth:
            continue
        n2 = getattr(it, "ContentSequence", None)
        if n2:
            for ch in reversed(list(cast(DicomSequence, n2))):
                stack.append((ch, d + 1))
    return out


def _num_value_from_item(it: Dataset) -> str:
    """Numeric portion only (matches dose-summary style and existing fixture tests)."""
    if str(getattr(it, "ValueType", "") or "").strip().upper() != "NUM":
        return ""
    mseq = getattr(it, "MeasuredValueSequence", None)
    if not mseq or len(cast(DicomSequence, mseq)) == 0:
        return ""
    mv = cast(DicomSequence, mseq)[0]
    for attr in ("FloatingPointValue", "NumericValue"):
        v = getattr(mv, attr, None)
        if v is None:
            continue
        try:
            if isinstance(v, (list, tuple)) and len(v) > 0:
                return str(float(str(v[0]).strip()))
            return str(float(str(v).strip()))
        except (TypeError, ValueError):
            return str(v)
    return ""


def _num_value_from_item_with_units(it: Dataset) -> str:
    """NUM display with UCUM / code-meaning suffix for dynamic vendor columns."""
    if str(getattr(it, "ValueType", "") or "").strip().upper() != "NUM":
        return ""
    mseq = getattr(it, "MeasuredValueSequence", None)
    if not mseq or len(cast(DicomSequence, mseq)) == 0:
        return ""
    mv = cast(DicomSequence, mseq)[0]
    num = ""
    for attr in ("FloatingPointValue", "NumericValue"):
        v = getattr(mv, attr, None)
        if v is None:
            continue
        try:
            if isinstance(v, (list, tuple)) and len(v) > 0:
                num = str(float(str(v[0]).strip()))
            else:
                num = str(float(str(v).strip()))
        except (TypeError, ValueError):
            num = str(v)
        break
    if not num:
        return ""
    uc = getattr(mv, "MeasurementUnitsCodeSequence", None)
    if uc and len(cast(DicomSequence, uc)) > 0:
        u0 = cast(DicomSequence, uc)[0]
        um = getattr(u0, "CodeMeaning", None) or getattr(u0, "CodeValue", None)
        if um:
            return f"{num} {str(um).strip()}"
    return num


def _code_value_display(it: Dataset) -> str:
    if str(getattr(it, "ValueType", "") or "").strip().upper() != "CODE":
        return ""
    cseq = getattr(it, "ConceptCodeSequence", None)
    if not cseq or len(cast(DicomSequence, cseq)) == 0:
        return ""
    c0 = cast(DicomSequence, cseq)[0]
    meaning = str(getattr(c0, "CodeMeaning", "") or "").strip()
    cv = str(getattr(c0, "CodeValue", "") or "").strip()
    scheme = str(getattr(c0, "CodingSchemeDesignator", "") or "").strip()
    if meaning and cv and scheme:
        return f"{meaning} — {cv} — {scheme}"
    if meaning:
        return meaning
    if cv and scheme:
        return f"{cv} — {scheme}"
    return cv or ""


def _text_value(it: Dataset) -> str:
    tv = getattr(it, "TextValue", None)
    return str(tv).strip() if tv is not None else ""


def _datetime_value(it: Dataset) -> str:
    for attr in ("DateTime", "TemporalRangeType", "TimeRange", "Date", "Time"):
        v = getattr(it, attr, None)
        if v is not None:
            return f"{attr}={v}"
    return ""


def _uidref_value(it: Dataset) -> str:
    u = getattr(it, "UID", None)
    if u:
        return str(u).strip()
    for attr in ("ReferencedSOPInstanceUID", "ReferencedStudyInstanceUID", "ReferencedSeriesInstanceUID"):
        v = getattr(it, attr, None)
        if v:
            return f"{attr}={v}"
    return ""


def _format_item_value(it: Dataset) -> str:
    vt = str(getattr(it, "ValueType", "") or "").strip().upper()
    if vt == "NUM":
        return _num_value_from_item_with_units(it)
    if vt == "CODE":
        return _code_value_display(it)
    if vt == "TEXT":
        return _text_value(it)
    if vt in ("DATETIME", "DATE", "TIME"):
        return _datetime_value(it)
    if vt == "UIDREF":
        return _uidref_value(it)
    return ""


def _num_value_by_concept(items: Sequence[Dataset], code: tuple[str, str]) -> str:
    for it in items:
        if str(getattr(it, "ValueType", "") or "").strip().upper() != "NUM":
            continue
        if not _concept_matches(it, code):
            continue
        return _num_value_from_item(it)
    return ""


def _num_value_by_meaning_keywords(items: Sequence[Dataset], keywords: tuple[str, ...]) -> str:
    keys = tuple(k.upper() for k in keywords)
    for it in items:
        if str(getattr(it, "ValueType", "") or "").strip().upper() != "NUM":
            continue
        _cv, _sc, meaning = _concept_meta(it)
        up = meaning.upper()
        if up and all(k in up for k in keys):
            val = _num_value_from_item(it)
            if val:
                return val
    return ""


def _container_or_text_by_meaning_keywords(items: Sequence[Dataset], keywords: tuple[str, ...]) -> str:
    keys = tuple(k.upper() for k in keywords)
    for it in items:
        _cv, _sc, meaning = _concept_meta(it)
        up = meaning.upper()
        if up and all(k in up for k in keys):
            vt = str(getattr(it, "ValueType", "") or "").strip().upper()
            if vt == "TEXT":
                return _text_value(it) or meaning
            if vt == "NUM":
                return _num_value_from_item(it) or meaning
            return meaning
    return ""


def _code_meaning_by_concept(items: Sequence[Dataset], code: tuple[str, str]) -> str:
    for it in items:
        if str(getattr(it, "ValueType", "") or "").strip().upper() != "CODE":
            continue
        if not _concept_matches(it, code):
            continue
        return _code_value_display(it)
    return ""


def _text_by_concept(items: Sequence[Dataset], code: tuple[str, str]) -> str:
    for it in items:
        if str(getattr(it, "ValueType", "") or "").strip().upper() != "TEXT":
            continue
        if not _concept_matches(it, code):
            continue
        return _text_value(it)
    return ""


# --- Standard PS3.16 DCM concept codes (TID 10003 / dose SR family) ---

_COL_CTDI: Final[tuple[str, str]] = ("113830", "DCM")
_COL_DLP: Final[tuple[str, str]] = ("113838", "DCM")
_COL_DAP: Final[tuple[str, str]] = ("122130", "DCM")
_COL_DOSE_RP: Final[tuple[str, str]] = ("113738", "DCM")
_COL_KVP: Final[tuple[str, str]] = ("113733", "DCM")
_COL_FLUORO_MODE: Final[tuple[str, str]] = ("113732", "DCM")
_COL_XRAY_TUBE_CURRENT: Final[tuple[str, str]] = ("113734", "DCM")
_COL_PULSE_RATE: Final[tuple[str, str]] = ("113791", "DCM")
_COL_EXPOSURE_TIME: Final[tuple[str, str]] = ("113725", "DCM")
_COL_POSITIONER_PRIMARY_ANGLE: Final[tuple[str, str]] = ("112011", "DCM")
_COL_POSITIONER_SECONDARY_ANGLE: Final[tuple[str, str]] = ("112012", "DCM")
_COL_DIST_SOURCE_TO_DETECTOR: Final[tuple[str, str]] = ("113750", "DCM")
_COL_DIST_SOURCE_TO_ISOCENTER: Final[tuple[str, str]] = ("113748", "DCM")
_COL_COLLIMATED_FIELD_AREA: Final[tuple[str, str]] = ("113790", "DCM")
_COL_ACQUISITION_PLANE: Final[tuple[str, str]] = ("113764", "DCM")
_COL_DATETIME_STARTED: Final[tuple[str, str]] = ("111526", "DCM")
_COL_IRR_EVENT_TYPE: Final[tuple[str, str]] = ("113721", "DCM")
_COL_REFERENCE_POINT: Final[tuple[str, str]] = ("113780", "DCM")
_COL_IRR_EVENT_UID: Final[tuple[str, str]] = ("113769", "DCM")
_COL_NUM_PULSES: Final[tuple[str, str]] = ("113768", "DCM")
_COL_PULSE_WIDTH: Final[tuple[str, str]] = ("113793", "DCM")
_COL_IRR_DURATION: Final[tuple[str, str]] = ("113742", "DCM")
_COL_PATIENT_TABLE_REL: Final[tuple[str, str]] = ("113745", "DCM")
_COL_PATIENT_ORIENTATION: Final[tuple[str, str]] = ("113743", "DCM")
_COL_TABLE_LONG: Final[tuple[str, str]] = ("113751", "DCM")
_COL_TABLE_LAT: Final[tuple[str, str]] = ("113752", "DCM")
_COL_TABLE_HEAD_TILT: Final[tuple[str, str]] = ("113754", "DCM")
_COL_TABLE_HORIZ_ROT: Final[tuple[str, str]] = ("113755", "DCM")
_COL_TABLE_CRADLE_TILT: Final[tuple[str, str]] = ("113756", "DCM")

# Codes used in fixed columns — excluded from dynamic duplicate columns
_FIXED_CONCEPT_CODES: Final[frozenset[tuple[str, str]]] = frozenset(
    {
        _COL_CTDI,
        _COL_DLP,
        _COL_DAP,
        _COL_DOSE_RP,
        _COL_KVP,
        _COL_FLUORO_MODE,
        _COL_XRAY_TUBE_CURRENT,
        _COL_PULSE_RATE,
        _COL_EXPOSURE_TIME,
        _COL_POSITIONER_PRIMARY_ANGLE,
        _COL_POSITIONER_SECONDARY_ANGLE,
        _COL_DIST_SOURCE_TO_DETECTOR,
        _COL_DIST_SOURCE_TO_ISOCENTER,
        _COL_COLLIMATED_FIELD_AREA,
        _COL_ACQUISITION_PLANE,
        _COL_DATETIME_STARTED,
        _COL_IRR_EVENT_TYPE,
        _COL_REFERENCE_POINT,
        _COL_IRR_EVENT_UID,
        _COL_NUM_PULSES,
        _COL_PULSE_WIDTH,
        _COL_IRR_DURATION,
        _COL_PATIENT_TABLE_REL,
        _COL_PATIENT_ORIENTATION,
        _COL_TABLE_LONG,
        _COL_TABLE_LAT,
        _COL_TABLE_HEAD_TILT,
        _COL_TABLE_HORIZ_ROT,
        _COL_TABLE_CRADLE_TILT,
    }
)


def _datetime_started_display(items: Sequence[Dataset]) -> str:
    for it in items:
        if not _concept_matches(it, _COL_DATETIME_STARTED):
            continue
        return _datetime_value(it)
    return ""


def _irr_event_uid_display(items: Sequence[Dataset]) -> str:
    for it in items:
        if not _concept_matches(it, _COL_IRR_EVENT_UID):
            continue
        vt = str(getattr(it, "ValueType", "") or "").strip().upper()
        if vt == "UIDREF":
            return _uidref_value(it)
    return ""


def _dynamic_extra_columns(desc: Sequence[Dataset]) -> dict[str, str]:
    """
    Add any NUM/CODE/TEXT/DATETIME/UIDREF not already represented in the fixed-code set.

    Column titles match the SR tree (Concept Name + code + scheme) so private vendor nodes
    (e.g. Philips ``99PHI-IXR-XPER``) appear as first-class columns.
    """
    out: dict[str, str] = {}
    for it in desc:
        vt = str(getattr(it, "ValueType", "") or "").strip().upper()
        if vt in ("CONTAINER", "COMPOSITE", "IMAGE", "WAVEFORM", "SCOORD", "SCOORD3D", "TCOORD", ""):
            continue
        cv, scheme, _meaning = _concept_meta(it)
        if not cv and not scheme:
            continue
        key_cv = (cv, scheme) if cv and scheme else ("", "")
        if key_cv in _FIXED_CONCEPT_CODES:
            continue
        title = _concept_column_title(it)
        if not title or title == "Concept":
            continue
        val = _format_item_value(it)
        if not val:
            continue
        if title not in out:
            out[title] = val
    return out


@dataclass
class IrradiationEventRow:
    """One irradiation-related event row for tabular display."""

    node_id_placeholder: int
    path_indices: tuple[int, ...]
    event_concept: str
    columns: dict[str, str] = field(default_factory=dict)


@dataclass
class IrradiationEventExtraction:
    """All event rows found in a dataset."""

    rows: list[IrradiationEventRow]
    notes: list[str]


def _build_event_columns(desc: Sequence[Dataset]) -> dict[str, str]:
    """Ordered standard columns + sorted dynamic vendor/private columns."""
    fixed: list[tuple[str, str]] = [
        ("CTDIvol (mGy)", _num_value_by_concept(desc, _COL_CTDI)),
        ("DLP (mGy·cm)", _num_value_by_concept(desc, _COL_DLP)),
        ("DAP", _num_value_by_concept(desc, _COL_DAP)),
        ("Dose (RP)", _num_value_by_concept(desc, _COL_DOSE_RP)),
        ("kVp", _num_value_by_concept(desc, _COL_KVP)),
        ("Acquisition plane", _code_meaning_by_concept(desc, _COL_ACQUISITION_PLANE)),
        ("DateTime started", _datetime_started_display(desc)),
        ("Irradiation event type", _code_meaning_by_concept(desc, _COL_IRR_EVENT_TYPE)),
        ("Reference point definition", _text_by_concept(desc, _COL_REFERENCE_POINT)),
        ("Irradiation event UID", _irr_event_uid_display(desc)),
        ("Primary angle (deg)", _num_value_by_concept(desc, _COL_POSITIONER_PRIMARY_ANGLE)),
        ("Secondary angle (deg)", _num_value_by_concept(desc, _COL_POSITIONER_SECONDARY_ANGLE)),
        ("Source-to-detector distance (mm)", _num_value_by_concept(desc, _COL_DIST_SOURCE_TO_DETECTOR)),
        ("Source-to-isocenter distance (mm)", _num_value_by_concept(desc, _COL_DIST_SOURCE_TO_ISOCENTER)),
        ("Collimated field area (mm²)", _num_value_by_concept(desc, _COL_COLLIMATED_FIELD_AREA)),
        ("Detector field size", _container_or_text_by_meaning_keywords(desc, ("DETECTOR", "FIELD", "SIZE"))),
        ("Fluoro mode", _code_meaning_by_concept(desc, _COL_FLUORO_MODE)),
        ("Pulse rate", _num_value_by_concept(desc, _COL_PULSE_RATE)),
        ("X-Ray tube current", _num_value_by_concept(desc, _COL_XRAY_TUBE_CURRENT)),
        ("Number of pulses", _num_value_by_concept(desc, _COL_NUM_PULSES)),
        ("Pulse width", _num_value_by_concept(desc, _COL_PULSE_WIDTH)),
        ("Irradiation duration", _num_value_by_concept(desc, _COL_IRR_DURATION)),
        ("Exposure time", _num_value_by_concept(desc, _COL_EXPOSURE_TIME)),
        ("Patient table relationship", _code_meaning_by_concept(desc, _COL_PATIENT_TABLE_REL)),
        ("Patient orientation", _code_meaning_by_concept(desc, _COL_PATIENT_ORIENTATION)),
        ("Table longitudinal position (mm)", _num_value_by_concept(desc, _COL_TABLE_LONG)),
        ("Table lateral position (mm)", _num_value_by_concept(desc, _COL_TABLE_LAT)),
        ("Table head tilt angle (deg)", _num_value_by_concept(desc, _COL_TABLE_HEAD_TILT)),
        ("Table horizontal rotation angle (deg)", _num_value_by_concept(desc, _COL_TABLE_HORIZ_ROT)),
        ("Table cradle tilt angle (deg)", _num_value_by_concept(desc, _COL_TABLE_CRADLE_TILT)),
    ]
    cols: dict[str, str] = {}
    for k, v in fixed:
        cols[k] = v
    dyn = _dynamic_extra_columns(desc)
    for title in sorted(dyn.keys()):
        if title not in cols:
            cols[title] = dyn[title]
    return cols


def extract_irradiation_events(
    ds: Dataset,
    *,
    node_id_start: int = 0,
) -> IrradiationEventExtraction:
    """
    Extract irradiation event rows when ``ContentSequence`` contains known event containers.

    ``node_id_placeholder`` is filled with sequential ids for UI mapping; the SR tree assigns
    real ``node_id`` separately—call :func:`attach_tree_node_ids` after building ``SrDocumentTree``.
    """
    notes: list[str] = []
    rows: list[IrradiationEventRow] = []
    if not is_radiation_dose_sr(ds):
        notes.append("Not a recognized radiation dose SR; per-event table may be empty.")
    root_seq = getattr(ds, "ContentSequence", None)
    if not root_seq:
        return IrradiationEventExtraction(rows=[], notes=["No ContentSequence."])

    stack: list[tuple[Dataset, tuple[int, ...]]] = [
        (cast(DicomSequence, root_seq)[i], (i,))
        for i in range(len(cast(DicomSequence, root_seq)) - 1, -1, -1)
    ]
    seen_paths: set[tuple[int, ...]] = set()
    nid = node_id_start

    while stack:
        item, path = stack.pop()
        match = _is_event_root(item)
        if match and path not in seen_paths:
            seen_paths.add(path)
            desc = _flatten_descendants(item)
            kind = f"{match[0]} ({match[1]})"
            cols: dict[str, str] = {"Event concept": kind}
            cols.update(_build_event_columns(desc))
            rows.append(
                IrradiationEventRow(
                    node_id_placeholder=nid,
                    path_indices=path,
                    event_concept=kind,
                    columns=cols,
                )
            )
            nid += 1
        nested = getattr(item, "ContentSequence", None)
        if nested:
            seq = cast(DicomSequence, nested)
            for i in range(len(seq) - 1, -1, -1):
                stack.append((seq[i], path + (i,)))

    if not rows:
        notes.append(
            "No irradiation event containers (113706 X-Ray / 113819 CT, DCM) found in this document."
        )
    return IrradiationEventExtraction(rows=rows, notes=notes)


def attach_tree_node_ids(
    extraction: IrradiationEventExtraction,
    node_by_path: dict[tuple[int, ...], int],
) -> None:
    """Mutate rows' ``node_id_placeholder`` to real SR tree ``node_id`` when ``path`` matches."""
    for row in extraction.rows:
        rid = node_by_path.get(row.path_indices)
        if rid is not None:
            row.node_id_placeholder = rid

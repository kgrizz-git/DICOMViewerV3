"""
RDSR irradiation event rows — table-oriented extract from X-Ray / CT dose SR templates.

**Purpose:** Find **irradiation event** containers in radiation dose SR instances (PS3.16
**TID 10003** *Irradiation Event X-Ray Data* code **113706**, **TID 10011**-style **CT**
events **113819**, and Enhanced-RDSR event-summary style concept names), then flatten common
NUM/CODE/TEXT children into string columns for a ``QTableView``.

**Inputs:** ``pydicom.dataset.Dataset`` (typically ``Modality`` **SR**, dose-related SOP class).

**Outputs:** :class:`IrradiationEventExtraction` with rows, optional notes, and
``truncated_subtree`` when flattening caps apply.

**Requirements:** ``pydicom`` only. Concept identity matching uses :mod:`core.sr_concept_identity`
(normalized designators, ``LongCodeValue`` fallback).

This is **not** a full TID validator; unknown vendor nesting may yield partial columns.
After a curated set of **standard** columns, any remaining **NUM/CODE/TEXT/DATETIME/UIDREF**
items under the event (including private coding schemes) are appended as **dynamic** columns
so vendor-specific geometry (e.g. Philips ``99PHI-IXR-XPER``) still appears in the dose-events table.
**113780** reference point rows may be **TEXT** or **CODE** (TID 10003). **Source-to-detector**
prefers **113750**, then concept-name matches such as *Final Distance Source to Detector*.
**Exposure time** tries **113735** then **113824** (DCM). **Patient orientation** uses **113743**
and optional modifier **113744**.

**Ambiguity policy (high-risk NUM and keyword NUMs):** Prefer **exact DCM** concept codes over
meaning-keyword fallbacks. Among several matching NUMs with the same normalized concept, prefer
the **shallowest** ``ContentSequence`` depth (distance 1 = direct child of the event container),
then **document order** in the depth-first flatten walk. If multiple candidates at the minimum
depth disagree numerically, a short note is appended to :attr:`IrradiationEventExtraction.notes`.

See ``dev-docs/plans/supporting/SR_FULL_FIDELITY_BROWSER_PLAN.md`` §6 Phase 3 and
``dev-docs/plans/supporting/SR_DOSE_EVENTS_NORMALIZATION_AND_HIGHDICOM_PLAN.md`` Stage 1.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Final, TypeAlias, cast

from pydicom.dataset import Dataset
from pydicom.sequence import Sequence as DicomSequence

from core.rdsr_dose_sr import is_radiation_dose_sr
from core.sr_concept_identity import (
    concept_identity_matches,
    concept_name_identity_pair,
    normalized_expected_tuple,
)

_CODE_IRR_EVENT_XRAY: Final[tuple[str, str]] = ("113706", "DCM")
_CODE_IRR_EVENT_CT: Final[tuple[str, str]] = ("113819", "DCM")

_EVENT_CONCEPTS: Final[tuple[tuple[str, str], ...]] = (
    _CODE_IRR_EVENT_XRAY,
    _CODE_IRR_EVENT_CT,
)

DescWalk: TypeAlias = Sequence[tuple[Dataset, int]]


@dataclass(frozen=True)
class FlattenedSubtree:
    """Depth-first descendants under an event ``CONTAINER`` (excluding the root), with caps."""

    items: tuple[tuple[Dataset, int], ...]
    truncated: bool


def _concept_meta(item: Dataset) -> tuple[str, str, str]:
    """Return (code_value, scheme, code_meaning) from Concept Name Code Sequence (display/raw)."""
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
        if concept_identity_matches(item, code):
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
) -> FlattenedSubtree:
    """
    Depth-first list of content items under ``item`` (excluding ``item`` itself).

    ``truncated`` is True when ``max_items`` or ``max_depth`` prevented a full listing.
    """
    out: list[tuple[Dataset, int]] = []
    stack: list[tuple[Dataset, int]] = []
    truncated = False
    nested = getattr(item, "ContentSequence", None)
    if nested:
        for ch in reversed(list(cast(DicomSequence, nested))):
            stack.append((ch, 1))
    while stack:
        if len(out) >= max_items:
            truncated = True
            break
        it, d = stack.pop()
        out.append((it, d))
        n2 = getattr(it, "ContentSequence", None)
        if n2:
            if d >= max_depth:
                truncated = True
                continue
            for ch in reversed(list(cast(DicomSequence, n2))):
                stack.append((ch, d + 1))
    if stack:
        truncated = True
    return FlattenedSubtree(items=tuple(out), truncated=truncated)


def _mv_numeric_segment(mv: Dataset) -> str:
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


def _mv_with_units_segment(mv: Dataset) -> str:
    num = _mv_numeric_segment(mv)
    if not num:
        return ""
    uc = getattr(mv, "MeasurementUnitsCodeSequence", None)
    if uc and len(cast(DicomSequence, uc)) > 0:
        u0 = cast(DicomSequence, uc)[0]
        um = getattr(u0, "CodeMeaning", None) or getattr(u0, "CodeValue", None)
        if um:
            return f"{num} {str(um).strip()}"
    return num


def _num_value_from_item(it: Dataset) -> str:
    """All ``MeasuredValueSequence`` rows joined with ``; `` when multi-valued on one NUM item."""
    if str(getattr(it, "ValueType", "") or "").strip().upper() != "NUM":
        return ""
    mseq = getattr(it, "MeasuredValueSequence", None)
    if not mseq or len(cast(DicomSequence, mseq)) == 0:
        return ""
    parts: list[str] = []
    for mv in cast(DicomSequence, mseq):
        seg = _mv_numeric_segment(mv)
        if seg:
            parts.append(seg)
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return "; ".join(parts)


def _num_value_from_item_with_units(it: Dataset) -> str:
    """NUM display with units; multiple ``MeasuredValueSequence`` entries joined with ``; ``."""
    if str(getattr(it, "ValueType", "") or "").strip().upper() != "NUM":
        return ""
    mseq = getattr(it, "MeasuredValueSequence", None)
    if not mseq or len(cast(DicomSequence, mseq)) == 0:
        return ""
    parts: list[str] = []
    for mv in cast(DicomSequence, mseq):
        seg = _mv_with_units_segment(mv)
        if seg:
            parts.append(seg)
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return "; ".join(parts)


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


def _best_num_for_concept(
    items: DescWalk,
    code: tuple[str, str],
    *,
    label: str,
    notes: list[str],
) -> str:
    """Shallowest-first NUM for a normalized concept; note when min-depth candidates disagree."""
    matches: list[tuple[int, int, str]] = []
    for walk_idx, (it, depth) in enumerate(items):
        if str(getattr(it, "ValueType", "") or "").strip().upper() != "NUM":
            continue
        if not concept_identity_matches(it, code):
            continue
        val = _num_value_from_item(it)
        if not val:
            continue
        matches.append((depth, walk_idx, val))
    if not matches:
        return ""
    matches.sort(key=lambda t: (t[0], t[1]))
    min_depth = matches[0][0]
    at_min = [m for m in matches if m[0] == min_depth]
    vals = {m[2] for m in at_min}
    if len(vals) > 1:
        joined = ", ".join(sorted(vals))
        notes.append(
            f"Ambiguous NUM for {label} ({code[0]}, {code[1]}): {joined}; "
            f"using shallowest/earliest in walk ({matches[0][2]})."
        )
    return matches[0][2]


def _best_code_display_for_concept(items: DescWalk, code: tuple[str, str], *, label: str, notes: list[str]) -> str:
    matches: list[tuple[int, int, str]] = []
    for walk_idx, (it, depth) in enumerate(items):
        if str(getattr(it, "ValueType", "") or "").strip().upper() != "CODE":
            continue
        if not concept_identity_matches(it, code):
            continue
        disp = _code_value_display(it)
        if not disp:
            continue
        matches.append((depth, walk_idx, disp))
    if not matches:
        return ""
    matches.sort(key=lambda t: (t[0], t[1]))
    min_depth = matches[0][0]
    at_min = [m for m in matches if m[0] == min_depth]
    vals = {m[2] for m in at_min}
    if len(vals) > 1:
        notes.append(
            f"Ambiguous CODE for {label} ({code[0]}, {code[1]}); using shallowest/earliest in walk."
        )
    return matches[0][2]


def _best_text_for_concept(items: DescWalk, code: tuple[str, str], *, label: str, notes: list[str]) -> str:
    matches: list[tuple[int, int, str]] = []
    for walk_idx, (it, depth) in enumerate(items):
        if str(getattr(it, "ValueType", "") or "").strip().upper() != "TEXT":
            continue
        if not concept_identity_matches(it, code):
            continue
        t = _text_value(it)
        if not t:
            continue
        matches.append((depth, walk_idx, t))
    if not matches:
        return ""
    matches.sort(key=lambda t: (t[0], t[1]))
    min_depth = matches[0][0]
    at_min = [m for m in matches if m[0] == min_depth]
    vals = {m[2] for m in at_min}
    if len(vals) > 1:
        notes.append(
            f"Ambiguous TEXT for {label} ({code[0]}, {code[1]}); using shallowest/earliest in walk."
        )
    return matches[0][2]


def _num_value_by_concept(items: DescWalk, code: tuple[str, str], notes: list[str]) -> str:
    return _best_num_for_concept(items, code, label=f"concept {code[0]}", notes=notes)


def _num_value_by_meaning_keywords(
    items: DescWalk,
    keywords: tuple[str, ...],
    *,
    notes: list[str],
    label: str,
) -> str:
    keys = tuple(k.upper() for k in keywords)
    matches: list[tuple[int, int, str]] = []
    for walk_idx, (it, depth) in enumerate(items):
        if str(getattr(it, "ValueType", "") or "").strip().upper() != "NUM":
            continue
        _cv, _sc, meaning = _concept_meta(it)
        up = meaning.upper()
        if up and all(k in up for k in keys):
            val = _num_value_from_item(it)
            if val:
                matches.append((depth, walk_idx, val))
    if not matches:
        return ""
    matches.sort(key=lambda t: (t[0], t[1]))
    min_depth = matches[0][0]
    at_min = [m for m in matches if m[0] == min_depth]
    vals = {m[2] for m in at_min}
    if len(vals) > 1:
        joined = ", ".join(sorted(vals))
        notes.append(
            f"Ambiguous keyword NUM ({label}): {joined}; using shallowest/earliest ({matches[0][2]})."
        )
    return matches[0][2]


def _container_or_text_by_meaning_keywords(items: DescWalk, keywords: tuple[str, ...]) -> str:
    keys = tuple(k.upper() for k in keywords)
    for it, _depth in items:
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


def _code_meaning_by_concept(items: DescWalk, code: tuple[str, str], notes: list[str]) -> str:
    return _best_code_display_for_concept(items, code, label=f"concept {code[0]}", notes=notes)


def _text_by_concept(items: DescWalk, code: tuple[str, str], notes: list[str]) -> str:
    return _best_text_for_concept(items, code, label=f"concept {code[0]}", notes=notes)


def _text_or_code_by_concept(items: DescWalk, code: tuple[str, str], notes: list[str]) -> str:
    """TID 10003 rows 22–23: **113780** Reference Point Definition may be TEXT or CODE (CID 10025)."""
    matches: list[tuple[int, int, str, str]] = []
    for walk_idx, (it, depth) in enumerate(items):
        if not concept_identity_matches(it, code):
            continue
        vt = str(getattr(it, "ValueType", "") or "").strip().upper()
        if vt == "TEXT":
            t = _text_value(it)
            if t:
                matches.append((depth, walk_idx, "TEXT", t))
        elif vt == "CODE":
            c = _code_value_display(it)
            if c:
                matches.append((depth, walk_idx, "CODE", c))
    if not matches:
        return ""
    matches.sort(key=lambda t: (t[0], t[1]))
    min_depth = matches[0][0]
    at_min = [m for m in matches if m[0] == min_depth]
    texts = {m[3] for m in at_min}
    if len(texts) > 1:
        notes.append(
            f"Ambiguous TEXT/CODE for reference point (113780); using shallowest/earliest in walk."
        )
    return matches[0][3]


def _num_exposure_time_ms(items: DescWalk, notes: list[str]) -> str:
    """
    Exposure time as NUM (ms typical).

    Vendors differ: **113735** (seen in Philips RDSR), **113824** (TID 10003B / current PS3.16).
    Policy: prefer **113735** over **113824** when both are present; note if values disagree.
    """
    v735 = _best_num_for_concept(items, _COL_EXPOSURE_TIME_113735, label="Exposure time (113735)", notes=notes)
    v824 = _best_num_for_concept(items, _COL_EXPOSURE_TIME_113824, label="Exposure time (113824)", notes=notes)
    if v735 and v824 and v735 != v824:
        notes.append(
            f"Exposure time: both 113735 and 113824 present with different values ({v735} vs {v824}); "
            "using 113735 per policy."
        )
    if v735:
        return v735
    return v824


def _source_to_detector_mm_display(items: DescWalk, notes: list[str]) -> str:
    """
    Standard **113750** Distance Source to Detector, or vendor synonyms on the NUM concept name
    (e.g. Philips ``Final Distance Source to Detector`` under private schemes).
    """
    v = _best_num_for_concept(
        items,
        _COL_DIST_SOURCE_TO_DETECTOR,
        label="Distance source to detector (113750)",
        notes=notes,
    )
    if v:
        return v
    v = _num_value_by_meaning_keywords(
        items,
        ("FINAL", "DISTANCE", "SOURCE", "DETECTOR"),
        notes=notes,
        label="FINAL+DISTANCE+SOURCE+DETECTOR",
    )
    if v:
        return v
    v = _num_value_by_meaning_keywords(
        items, ("FINAL", "SOURCE", "DETECTOR"), notes=notes, label="FINAL+SOURCE+DETECTOR"
    )
    if v:
        return v
    return _num_value_by_meaning_keywords(
        items, ("DISTANCE", "SOURCE", "DETECTOR"), notes=notes, label="DISTANCE+SOURCE+DETECTOR"
    )


def _final_source_to_detector_mm_display(items: DescWalk, notes: list[str]) -> str:
    """NUM whose concept name is clearly a *final* source-to-detector distance (parallel to 113750)."""
    v = _num_value_by_meaning_keywords(
        items,
        ("FINAL", "DISTANCE", "SOURCE", "DETECTOR"),
        notes=notes,
        label="FINAL+DISTANCE+SOURCE+DETECTOR",
    )
    if v:
        return v
    return _num_value_by_meaning_keywords(
        items, ("FINAL", "SOURCE", "DETECTOR"), notes=notes, label="FINAL+SOURCE+DETECTOR"
    )


def _patient_orientation_display(items: DescWalk, notes: list[str]) -> str:
    """
    **113743** Patient Orientation (CODE per TID 10003), plus meaning-based fallback for equivalent
    private or alternate encodings.
    """
    v = _best_code_display_for_concept(
        items, _COL_PATIENT_ORIENTATION, label="Patient orientation (113743)", notes=notes
    )
    if v:
        return v
    for it, _depth in items:
        vt = str(getattr(it, "ValueType", "") or "").strip().upper()
        if vt not in ("CODE", "TEXT"):
            continue
        _cv, _sc, meaning = _concept_meta(it)
        up = meaning.upper()
        if "PATIENT" in up and "ORIENTATION" in up and "MODIFIER" not in up:
            if vt == "CODE":
                c = _code_value_display(it)
                if c:
                    return c
            else:
                t = _text_value(it)
                if t:
                    return t
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
_COL_EXPOSURE_TIME_113735: Final[tuple[str, str]] = ("113735", "DCM")
_COL_EXPOSURE_TIME_113824: Final[tuple[str, str]] = ("113824", "DCM")
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
_COL_PATIENT_ORIENTATION_MODIFIER: Final[tuple[str, str]] = ("113744", "DCM")
_COL_TABLE_LONG: Final[tuple[str, str]] = ("113751", "DCM")
_COL_TABLE_LAT: Final[tuple[str, str]] = ("113752", "DCM")
_COL_TABLE_HEAD_TILT: Final[tuple[str, str]] = ("113754", "DCM")
_COL_TABLE_HORIZ_ROT: Final[tuple[str, str]] = ("113755", "DCM")
_COL_TABLE_CRADLE_TILT: Final[tuple[str, str]] = ("113756", "DCM")

_RAW_FIXED_CONCEPT_CODES: Final[tuple[tuple[str, str], ...]] = (
    _COL_CTDI,
    _COL_DLP,
    _COL_DAP,
    _COL_DOSE_RP,
    _COL_KVP,
    _COL_FLUORO_MODE,
    _COL_XRAY_TUBE_CURRENT,
    _COL_PULSE_RATE,
    _COL_EXPOSURE_TIME_113735,
    _COL_EXPOSURE_TIME_113824,
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
    _COL_PATIENT_ORIENTATION_MODIFIER,
    _COL_TABLE_LONG,
    _COL_TABLE_LAT,
    _COL_TABLE_HEAD_TILT,
    _COL_TABLE_HORIZ_ROT,
    _COL_TABLE_CRADLE_TILT,
)

_FIXED_CONCEPT_CODES_NORM: Final[frozenset[tuple[str, str]]] = frozenset(
    normalized_expected_tuple(c) for c in _RAW_FIXED_CONCEPT_CODES
)


def _datetime_started_display(items: DescWalk, notes: list[str]) -> str:
    matches: list[tuple[int, int, str]] = []
    for walk_idx, (it, depth) in enumerate(items):
        if not concept_identity_matches(it, _COL_DATETIME_STARTED):
            continue
        dv = _datetime_value(it)
        if dv:
            matches.append((depth, walk_idx, dv))
    if not matches:
        return ""
    matches.sort(key=lambda t: (t[0], t[1]))
    min_depth = matches[0][0]
    at_min = [m for m in matches if m[0] == min_depth]
    vals = {m[2] for m in at_min}
    if len(vals) > 1:
        notes.append("Ambiguous DateTime started (111526); using shallowest/earliest in walk.")
    return matches[0][2]


def _irr_event_uid_display(items: DescWalk, notes: list[str]) -> str:
    """**113769** may be **UIDREF** or **TEXT** carrying a UID in some exports."""
    matches: list[tuple[int, int, str, str]] = []
    for walk_idx, (it, depth) in enumerate(items):
        if not concept_identity_matches(it, _COL_IRR_EVENT_UID):
            continue
        vt = str(getattr(it, "ValueType", "") or "").strip().upper()
        if vt == "UIDREF":
            u = _uidref_value(it)
            if u:
                matches.append((depth, walk_idx, "UIDREF", u))
        elif vt == "TEXT":
            t = _text_value(it)
            if t:
                matches.append((depth, walk_idx, "TEXT", t))
    if not matches:
        return ""
    matches.sort(key=lambda t: (t[0], t[1]))
    min_depth = matches[0][0]
    at_min = [m for m in matches if m[0] == min_depth]
    vals = {m[3] for m in at_min}
    if len(vals) > 1:
        notes.append("Ambiguous irradiation event UID (113769); using shallowest/earliest in walk.")
    return matches[0][3]


def _dynamic_extra_columns(items: DescWalk) -> dict[str, str]:
    """
    Add any NUM/CODE/TEXT/DATETIME/UIDREF not already represented in the fixed-code set.

    Column titles match the SR tree (Concept Name + code + scheme) so private vendor nodes
    (e.g. Philips ``99PHI-IXR-XPER``) appear as first-class columns.
    """
    out: dict[str, str] = {}
    for it, _depth in items:
        vt = str(getattr(it, "ValueType", "") or "").strip().upper()
        if vt in ("CONTAINER", "COMPOSITE", "IMAGE", "WAVEFORM", "SCOORD", "SCOORD3D", "TCOORD", ""):
            continue
        id_pair = concept_name_identity_pair(it)
        if id_pair in _FIXED_CONCEPT_CODES_NORM:
            continue
        cv, scheme, _meaning = _concept_meta(it)
        if not cv and not scheme:
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
    subtree_truncated: bool = False


@dataclass
class IrradiationEventExtraction:
    """All event rows found in a dataset."""

    rows: list[IrradiationEventRow]
    notes: list[str]
    truncated_subtree: bool = False


def _build_event_columns(desc: FlattenedSubtree, notes: list[str]) -> dict[str, str]:
    """Ordered standard columns + sorted dynamic vendor/private columns."""
    items = desc.items
    fixed: list[tuple[str, str]] = [
        ("CTDIvol (mGy)", _num_value_by_concept(items, _COL_CTDI, notes)),
        ("DLP (mGy·cm)", _num_value_by_concept(items, _COL_DLP, notes)),
        ("DAP", _num_value_by_concept(items, _COL_DAP, notes)),
        ("Dose (RP)", _num_value_by_concept(items, _COL_DOSE_RP, notes)),
        ("kVp", _num_value_by_concept(items, _COL_KVP, notes)),
        ("Acquisition plane", _code_meaning_by_concept(items, _COL_ACQUISITION_PLANE, notes)),
        ("DateTime started", _datetime_started_display(items, notes)),
        ("Irradiation event type", _code_meaning_by_concept(items, _COL_IRR_EVENT_TYPE, notes)),
        ("Reference point definition", _text_or_code_by_concept(items, _COL_REFERENCE_POINT, notes)),
        ("Irradiation event UID", _irr_event_uid_display(items, notes)),
        ("Primary angle (deg)", _num_value_by_concept(items, _COL_POSITIONER_PRIMARY_ANGLE, notes)),
        ("Secondary angle (deg)", _num_value_by_concept(items, _COL_POSITIONER_SECONDARY_ANGLE, notes)),
        ("Source-to-detector distance (mm)", _source_to_detector_mm_display(items, notes)),
        ("Final source-to-detector distance (mm)", _final_source_to_detector_mm_display(items, notes)),
        ("Source-to-isocenter distance (mm)", _num_value_by_concept(items, _COL_DIST_SOURCE_TO_ISOCENTER, notes)),
        ("Collimated field area (mm²)", _num_value_by_concept(items, _COL_COLLIMATED_FIELD_AREA, notes)),
        ("Detector field size", _container_or_text_by_meaning_keywords(items, ("DETECTOR", "FIELD", "SIZE"))),
        ("Fluoro mode", _code_meaning_by_concept(items, _COL_FLUORO_MODE, notes)),
        ("Pulse rate", _num_value_by_concept(items, _COL_PULSE_RATE, notes)),
        ("X-Ray tube current", _num_value_by_concept(items, _COL_XRAY_TUBE_CURRENT, notes)),
        ("Number of pulses", _num_value_by_concept(items, _COL_NUM_PULSES, notes)),
        ("Pulse width", _num_value_by_concept(items, _COL_PULSE_WIDTH, notes)),
        ("Irradiation duration", _num_value_by_concept(items, _COL_IRR_DURATION, notes)),
        ("Exposure time", _num_exposure_time_ms(items, notes)),
        ("Patient table relationship", _code_meaning_by_concept(items, _COL_PATIENT_TABLE_REL, notes)),
        ("Patient orientation", _patient_orientation_display(items, notes)),
        ("Patient orientation modifier", _code_meaning_by_concept(items, _COL_PATIENT_ORIENTATION_MODIFIER, notes)),
        ("Table longitudinal position (mm)", _num_value_by_concept(items, _COL_TABLE_LONG, notes)),
        ("Table lateral position (mm)", _num_value_by_concept(items, _COL_TABLE_LAT, notes)),
        ("Table head tilt angle (deg)", _num_value_by_concept(items, _COL_TABLE_HEAD_TILT, notes)),
        ("Table horizontal rotation angle (deg)", _num_value_by_concept(items, _COL_TABLE_HORIZ_ROT, notes)),
        ("Table cradle tilt angle (deg)", _num_value_by_concept(items, _COL_TABLE_CRADLE_TILT, notes)),
    ]
    cols: dict[str, str] = {}
    for k, v in fixed:
        cols[k] = v
    dyn = _dynamic_extra_columns(items)
    for title in sorted(dyn.keys()):
        if title not in cols:
            cols[title] = dyn[title]
    return cols


def extract_irradiation_events(
    ds: Dataset,
    *,
    node_id_start: int = 0,
    max_flat_depth: int = 14,
    max_flat_items: int = 1500,
) -> IrradiationEventExtraction:
    """
    Extract irradiation event rows when ``ContentSequence`` contains known event containers.

    ``node_id_placeholder`` is filled with sequential ids for UI mapping; the SR tree assigns
    real ``node_id`` separately—call :func:`attach_tree_node_ids` after building ``SrDocumentTree``.

    ``max_flat_depth`` / ``max_flat_items`` bound per-event subtree flattening (testing may lower
    these to assert truncation behavior).
    """
    notes: list[str] = []
    rows: list[IrradiationEventRow] = []
    truncated_any = False
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
            flat = _flatten_descendants(item, max_depth=max_flat_depth, max_items=max_flat_items)
            if flat.truncated:
                truncated_any = True
            row_notes: list[str] = []
            kind = f"{match[0]} ({match[1]})"
            cols: dict[str, str] = {"Event concept": kind}
            cols.update(_build_event_columns(flat, row_notes))
            path_label = " → ".join(str(i) for i in path)
            for msg in row_notes:
                notes.append(f"Dose event path {path_label}: {msg}")
            if flat.truncated:
                notes.append(
                    f"Dose event path {path_label}: flattening hit max_depth={max_flat_depth} "
                    f"or max_items={max_flat_items}; some descendant nodes may be missing from columns."
                )
            rows.append(
                IrradiationEventRow(
                    node_id_placeholder=nid,
                    path_indices=path,
                    event_concept=kind,
                    columns=cols,
                    subtree_truncated=flat.truncated,
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
    return IrradiationEventExtraction(rows=rows, notes=notes, truncated_subtree=truncated_any)


def attach_tree_node_ids(
    extraction: IrradiationEventExtraction,
    node_by_path: dict[tuple[int, ...], int],
) -> None:
    """Mutate rows' ``node_id_placeholder`` to real SR tree ``node_id`` when ``path`` matches."""
    for row in extraction.rows:
        rid = node_by_path.get(row.path_indices)
        if rid is not None:
            row.node_id_placeholder = rid

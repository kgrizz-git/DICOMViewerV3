"""
Curated standard DICOM tags for the tag-export dialog.

Supplements the tag picker with common Patient / Study / Series / Image and
modality-specific elements when those tags are absent from the sample dataset,
so users can still select them for export (values empty or filled per instance
after collection).

Sequence-valued tags (VR SQ) are omitted: export rows are scalar-oriented.
Explicit (group, element) tuples cover tags when keyword lookup is unreliable.

Inputs:
    - Tag dict from :meth:`DICOMParser.get_all_tags`
Outputs:
    - In-place merge of synthetic entries (empty value, standard name/VR)
    - :func:`synthetic_tag_export_tree_entry` — one row for a tag string (e.g. from a preset) absent from the union

See :mod:`core.tag_export_union` for :func:`~core.tag_export_union.union_tags_across_datasets`.
Requirements:
    - pydicom (:class:`~pydicom.tag.Tag` keywords, datadict)
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from pydicom.datadict import dictionary_description, dictionary_keyword, dictionary_VR
from pydicom.tag import BaseTag, Tag


# Curated keywords across common modalities; SQ tags resolved at load time are skipped.
_CATALOG_KEYWORDS: List[str] = [
    # Patient / demographics
    "PatientName",
    "PatientID",
    "IssuerOfPatientID",
    "PatientBirthDate",
    "PatientBirthTime",
    "PatientSex",
    "PatientAge",
    "PatientWeight",
    "PatientSize",
    "PatientAddress",
    "EthnicGroup",
    "Occupation",
    "PatientComments",
    "PatientOrientation",
    "PatientPosition",
    "AdditionalPatientHistory",
    # Study
    "StudyInstanceUID",
    "StudyDate",
    "StudyTime",
    "StudyID",
    "StudyDescription",
    "AccessionNumber",
    "ReferringPhysicianName",
    "RequestingPhysician",
    "PerformingPhysicianName",
    "RequestingService",
    "RequestedProcedureDescription",
    "StudyStatusID",
    "AdmittingDiagnosesDescription",
    "IssuerOfAccessionNumberIdentifier",
    "InstitutionName",
    "InstitutionAddress",
    "InstitutionDepartmentName",
    # Series
    "SeriesInstanceUID",
    "SeriesNumber",
    "SeriesDate",
    "SeriesTime",
    "SeriesDescription",
    "SeriesType",
    "Modality",
    "BodyPartExamined",
    "Laterality",
    "ProtocolName",
    "FrameOfReferenceUID",
    # Equipment
    "Manufacturer",
    "ManufacturerModelName",
    "StationName",
    "DeviceSerialNumber",
    "SoftwareVersions",
    # General image / object
    "SOPClassUID",
    "SOPInstanceUID",
    "InstanceNumber",
    "AcquisitionNumber",
    "AcquisitionDate",
    "AcquisitionTime",
    "ContentDate",
    "ContentTime",
    "AcquisitionDatetime",
    "ImageType",
    "SamplesPerPixel",
    "PhotometricInterpretation",
    "Rows",
    "Columns",
    "BitsAllocated",
    "BitsStored",
    "HighBit",
    "PixelRepresentation",
    "PixelSpacing",
    "PlanarConfiguration",
    "SmallestImagePixelValue",
    "LargestImagePixelValue",
    "WindowCenter",
    "WindowWidth",
    "RescaleIntercept",
    "RescaleSlope",
    "RescaleType",
    "BurnedInAnnotation",
    "LossyImageCompression",
    "PresentationLUTShape",
    "PixelPaddingValue",
    # Spatial / geometry
    "SliceThickness",
    "SpacingBetweenSlices",
    "SliceLocation",
    "ImagePositionPatient",
    "ImageOrientationPatient",
    "PixelAspectRatio",
    "ImagerPixelSpacing",
    # CT acquisition / dose
    "KVP",
    "ExposureTime",
    "XRayTubeCurrent",
    "XRayTubeCurrentInuA",
    "Exposure",
    "ExposureInuAs",
    "SpiralPitchFactor",
    "SingleCollimationWidth",
    "TotalCollimationWidth",
    "TableSpeed",
    "TableTravelSpeed",
    "TableHeight",
    "RotationDirection",
    "FilterType",
    "ConvolutionKernel",
    "BodyPartThickness",
    "DataCollectionDiameter",
    "ReconstructionDiameter",
    "GantryDetectorTilt",
    "DistanceSourceToDetector",
    "DistanceSourceToPatient",
    "ExposureModulationType",
    "CTDIvol",
    "RevolutionTime",
    # MR
    "ScanningSequence",
    "SequenceVariant",
    "ScanOptions",
    "MRAcquisitionType",
    "RepetitionTime",
    "EchoTime",
    "EchoTrainLength",
    "EchoNumbers",
    "InversionTime",
    "FlipAngle",
    "NumberOfAverages",
    "ImagedNucleus",
    "MagneticFieldStrength",
    "ImagingFrequency",
    "PixelBandwidth",
    "PhaseEncodingDirection",
    "VariableFlipAngleFlag",
    "SAR",
    "dBdt",
    # PET / NM
    "Radiopharmaceutical",
    "RadiopharmaceuticalStartTime",
    "RadiopharmaceuticalStartDateTime",
    "DecayCorrection",
    "CorrectedImage",
    "Units",
    "CountsAccumulated",
    "ActualFrameDuration",
    "NumberOfFrames",
    # Ultrasound
    "TransducerType",
    "TransducerFrequency",
    # DX / CR / general X-ray
    "ViewPosition",
    "RelativeXRayExposure",
    "AnalogDigitalFlags",
    # Display / cine
    "RecommendedDisplayFrameRate",
    "CineRate",
    "FrameTime",
    "PreferredPlaybackSequencing",
]

# Explicit tags when keyword resolution fails or is version-dependent (group, element).
_CATALOG_EXTRA_TAGS: List[Tuple[int, int]] = [
    (0x0018, 0x1150),  # ExposureTime — backup if needed
    (0x0018, 0x1151),  # XRayTubeCurrent
    (0x0018, 0x1152),  # Exposure
    (0x0018, 0x9320),  # ExposureModulationType (common hex)
    (0x0018, 0x9309),  # TableSpeed
    (0x0028, 0x0030),  # PixelSpacing (backup)
    (0x0028, 0x1052),  # RescaleIntercept
    (0x0028, 0x1053),  # RescaleSlope
    (0x0020, 0x1041),  # SliceLocation
    (0x0020, 0x0032),  # ImagePositionPatient
    (0x0020, 0x0037),  # ImageOrientationPatient
    (0x0008, 0x0060),  # Modality (redundant with keyword; ensures presence)
]

_resolved_catalog: Optional[List[Tuple[str, str, str, str]]] = None


def _invalid_tag_sentinel(t: BaseTag) -> bool:
    return t == Tag(0xFFFF, 0xFFFF)


def _resolve_catalog() -> List[Tuple[str, str, str, str]]:
    """
    Build (tag_str, keyword, name, vr) rows for the export picker supplement.

    Returns:
        Deduplicated catalog rows; SQ and private tags omitted.
    """
    global _resolved_catalog
    if _resolved_catalog is not None:
        return _resolved_catalog

    out: List[Tuple[str, str, str, str]] = []
    seen: set[str] = set()

    def add_tag(tag: BaseTag, keyword: str) -> None:
        if tag.is_private or _invalid_tag_sentinel(tag):
            return
        vr = dictionary_VR(tag) or ""
        if vr == "SQ":
            return
        tag_str = str(tag)
        if tag_str in seen:
            return
        seen.add(tag_str)
        name = dictionary_description(tag) or keyword
        out.append((tag_str, keyword, name, vr))

    for kw in _CATALOG_KEYWORDS:
        try:
            tag = Tag(kw)
        except ValueError:
            continue
        add_tag(tag, kw)

    for group, element in _CATALOG_EXTRA_TAGS:
        tag = Tag((group, element))
        add_tag(tag, dictionary_description(tag) or f"({group:04X},{element:04X})")

    _resolved_catalog = out
    return _resolved_catalog


def supplement_export_tags_dict(tags: Dict[str, Any]) -> None:
    """
    Merge standard catalog entries into *tags* for any tag not already present.

    Synthetic entries use an empty string value and is_private False.
    """
    for tag_str, keyword, name, vr in _resolve_catalog():
        if tag_str not in tags:
            tags[tag_str] = {
                "tag": tag_str,
                "keyword": keyword,
                "VR": vr,
                "value": "",
                "is_private": False,
                "name": name,
            }


def missing_tag_export_display_fields(tag_str: str) -> Tuple[str, str]:
    """
    Return canonical tag string and dictionary name for export rows when the
    element is not present on the current dataset.
    """
    from utils.dicom_utils import canonical_dicom_tag_string

    canon = canonical_dicom_tag_string(tag_str)
    raw = (tag_str or "").strip()
    if not canon and not raw:
        return "", ""
    if canon:
        try:
            tg = Tag(canon)
            disp = str(tg)
            name = dictionary_description(tg) or disp
            return disp, name
        except Exception:
            return canon, canon
    try:
        tg = Tag(raw)
        disp = str(tg)
        name = dictionary_description(tg) or disp
        return disp, name
    except Exception:
        return raw, raw


def _tag_from_identifier_string(s: str) -> Optional[BaseTag]:
    """
    Build a pydicom Tag from ``(gggg, eeee)``, 8-digit hex, or a keyword string.

    pydicom's ``Tag('(0010, 0010)')`` rejects parenthesized display text; parse it explicitly.
    """
    raw = (s or "").strip()
    if not raw:
        return None
    m = re.fullmatch(r"\(\s*([0-9a-fA-F]{4})\s*,\s*([0-9a-fA-F]{4})\s*\)", raw)
    if m:
        return Tag((int(m.group(1), 16), int(m.group(2), 16)))
    compact = re.sub(r"\s+", "", raw)
    m8 = re.fullmatch(r"([0-9a-fA-F]{8})", compact)
    if m8:
        h = m8.group(1)
        return Tag((int(h[0:4], 16), int(h[4:8], 16)))
    try:
        return Tag(raw)
    except Exception:
        return None


def synthetic_tag_export_tree_entry(
    raw_tag_str: str,
) -> Optional[Tuple[str, Dict[str, Any]]]:
    """
    Build one merged-style tag dict entry for the export dialog tree when a tag
    appears in a preset (or similar) but is missing from the union of loaded files.

    Returns ``(canonical_key, tag_data)`` compatible with
    :func:`~core.tag_export_union.union_tags_across_datasets` / :func:`supplement_export_tags_dict`, or
    ``None`` if *raw_tag_str* cannot be interpreted as a DICOM tag identifier.
    """
    disp, name = missing_tag_export_display_fields(raw_tag_str)
    if not disp:
        return None
    tg = _tag_from_identifier_string(disp)
    if tg is None:
        tg = _tag_from_identifier_string((raw_tag_str or "").strip())
    if tg is None:
        return None
    key = str(tg)
    keyword = ""
    vr = ""
    try:
        keyword = dictionary_keyword(tg) or ""
    except Exception:
        pass
    try:
        vr = dictionary_VR(tg) or ""
    except Exception:
        pass
    return key, {
        "tag": key,
        "keyword": keyword,
        "VR": vr,
        "value": "",
        "is_private": bool(getattr(tg, "is_private", False)),
        "name": dictionary_description(tg) or name or key,
    }

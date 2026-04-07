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
    - :func:`union_tags_across_datasets` — merged tag map for export UI
Requirements:
    - pydicom (:class:`~pydicom.tag.Tag` keywords, datadict)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from pydicom.dataset import Dataset
from pydicom.datadict import dictionary_description, dictionary_VR
from pydicom.tag import Tag


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

_RESOLVED_CATALOG: Optional[List[Tuple[str, str, str, str]]] = None


def _invalid_tag_sentinel(t: Tag) -> bool:
    return t == Tag(0xFFFF, 0xFFFF)


def _resolve_catalog() -> List[Tuple[str, str, str, str]]:
    """
    Build (tag_str, keyword, name, vr) rows for the export picker supplement.

    Returns:
        Deduplicated catalog rows; SQ and private tags omitted.
    """
    global _RESOLVED_CATALOG
    if _RESOLVED_CATALOG is not None:
        return _RESOLVED_CATALOG

    out: List[Tuple[str, str, str, str]] = []
    seen: set[str] = set()

    def add_tag(tag: Tag, keyword: str) -> None:
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

    _RESOLVED_CATALOG = out
    return _RESOLVED_CATALOG


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


def union_tags_across_datasets(
    datasets: List[Dataset],
    *,
    include_private: bool,
    supplement_standard_tags: bool = False,
) -> Dict[str, Any]:
    """
    Build the union of tag keys across many datasets (nested elements included).

    For each canonical ``str(Tag)``, the **first** occurrence in *datasets* order
    supplies display metadata (name, sample value in the tree). Later instances
    can still contribute **new** keys not present on earlier slices.

    Args:
        datasets: All instances from loaded studies/series (any order; typically
            study → series → instance).
        include_private: Passed to :meth:`~core.dicom_parser.DICOMParser.get_all_tags`.
        supplement_standard_tags: If True, apply :func:`supplement_export_tags_dict`
            after the union.

    Returns:
        Merged tag dict suitable for the export dialog tree.
    """
    # Local import avoids import cycle (dicom_parser imports this module).
    from core.dicom_parser import DICOMParser

    merged: Dict[str, Any] = {}
    for ds in datasets:
        parser = DICOMParser(ds)
        part = parser.get_all_tags(
            include_private=include_private,
            supplement_standard_tags=False,
        )
        for tag_str, tag_data in part.items():
            if tag_str not in merged:
                merged[tag_str] = tag_data
    if supplement_standard_tags:
        supplement_export_tags_dict(merged)
    return merged


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

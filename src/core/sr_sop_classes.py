"""
Structured Report (SR) storage SOP class registry — labels and detection helpers.

**Purpose:** Decide whether a loaded DICOM instance should open the **Structured Report browser**
(full ``ContentSequence`` tree) versus the image viewer, based on ``SOPClassUID`` / ``Modality``.

**Inputs:** ``pydicom.dataset.Dataset`` with standard header attributes.

**Outputs:** Boolean ``is_structured_report_storage`` / ``is_structured_report_dataset``, human-readable
labels for window titles.

**Requirements:** ``pydicom`` only (no Qt).

See ``dev-docs/plans/supporting/SR_FULL_FIDELITY_BROWSER_PLAN.md`` §5.
"""

from __future__ import annotations

from typing import Final

from pydicom.dataset import Dataset
from pydicom.uid import (
    AcquisitionContextSRStorage,
    BasicTextSRStorage,
    ChestCADSRStorage,
    ColonCADSRStorage,
    Comprehensive3DSRStorage,
    ComprehensiveSRStorage,
    EnhancedSRStorage,
    EnhancedXRayRadiationDoseSRStorage,
    ExtensibleSRStorage,
    ImplantationPlanSRStorage,
    KeyObjectSelectionDocumentStorage,
    MammographyCADSRStorage,
    PatientRadiationDoseSRStorage,
    PerformedImagingAgentAdministrationSRStorage,
    PlannedImagingAgentAdministrationSRStorage,
    ProcedureLogStorage,
    RadiopharmaceuticalRadiationDoseSRStorage,
    SimplifiedAdultEchoSRStorage,
    XRayRadiationDoseSRStorage,
)

# pyright: reportUnknownMemberType=false

_SR_STORAGE_UID_TO_LABEL: Final[dict[str, str]] = {
    str(BasicTextSRStorage): "Basic Text SR",
    str(EnhancedSRStorage): "Enhanced SR",
    str(ComprehensiveSRStorage): "Comprehensive SR",
    str(Comprehensive3DSRStorage): "Comprehensive 3D SR",
    str(ExtensibleSRStorage): "Extensible SR",
    str(XRayRadiationDoseSRStorage): "X-Ray Radiation Dose SR",
    str(EnhancedXRayRadiationDoseSRStorage): "Enhanced X-Ray Radiation Dose SR",
    str(KeyObjectSelectionDocumentStorage): "Key Object Selection Document",
    str(ProcedureLogStorage): "Procedure Log",
    str(MammographyCADSRStorage): "Mammography CAD SR",
    str(ChestCADSRStorage): "Chest CAD SR",
    str(ColonCADSRStorage): "Colon CAD SR",
    str(ImplantationPlanSRStorage): "Implantation Plan SR",
    str(AcquisitionContextSRStorage): "Acquisition Context SR",
    str(SimplifiedAdultEchoSRStorage): "Simplified Adult Echo SR",
    str(RadiopharmaceuticalRadiationDoseSRStorage): "Radiopharmaceutical Radiation Dose SR",
    str(PatientRadiationDoseSRStorage): "Patient Radiation Dose SR",
    str(PlannedImagingAgentAdministrationSRStorage): "Planned Imaging Agent Administration SR",
    str(PerformedImagingAgentAdministrationSRStorage): "Performed Imaging Agent Administration SR",
}

STRUCTURED_REPORT_STORAGE_SOP_CLASS_UIDS: Final[frozenset[str]] = frozenset(_SR_STORAGE_UID_TO_LABEL)


def structured_report_storage_label(sop_class_uid: str) -> str:
    """Return a short UI label for a known SR storage class UID, else a generic fallback."""
    s = str(sop_class_uid or "").strip()
    if not s:
        return "Structured Report"
    return _SR_STORAGE_UID_TO_LABEL.get(s, "Structured Report")


def is_structured_report_storage(sop_class_uid: str) -> bool:
    """True if ``SOPClassUID`` is a registered SR *Storage* class (tree browser applies)."""
    return str(sop_class_uid or "").strip() in STRUCTURED_REPORT_STORAGE_SOP_CLASS_UIDS


def is_structured_report_dataset(ds: Dataset) -> bool:
    """
    True if ``ds`` should be treated as a Structured Report document for browser purposes.

    Uses ``SOPClassUID`` when it matches a known SR storage class; otherwise accepts
    ``Modality`` **SR** as a fallback for odd encoders.
    """
    sop = str(getattr(ds, "SOPClassUID", "") or "").strip()
    if sop and is_structured_report_storage(sop):
        return True
    mod = str(getattr(ds, "Modality", "") or "").strip().upper()
    return mod == "SR"

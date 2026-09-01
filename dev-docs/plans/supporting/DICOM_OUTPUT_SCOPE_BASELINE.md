# DICOM Output Scope Baseline

**Status:** Current implementation inventory; not an IOD-validation record or
a DICOM conformance statement.

**Last updated:** 2026-09-01

**Related plan:** [De-identification compliance reassessment](DEIDENTIFICATION_COMPLIANCE_REASSESSMENT_PLAN.md)

## Purpose and boundary

This record answers a narrow, factual question required before resolving the
PS3.15 Table E.1-1 inventory: which DICOM objects does the application write
today? It is an output-surface inventory, not a promise that every loaded or
written object conforms to a particular PS3.3 Information Object Definition
(IOD), nor evidence that a de-identification profile has been implemented.

The viewer currently accepts loaded DICOM datasets and, for ordinary DICOM
export, serializes the selected in-memory dataset or a derived projection of
it. It therefore has **no declared finite set of source SOP Classes/IODs that
it promises to preserve after export or metadata de-identification**. Before
any technical profile claim, the maintainer must either define that finite
scope and its Type 1/2/conditional validation strategy, or keep the no-claim
boundary in place.

## Repository evidence provenance

| ID | Organization / source | Reviewed material | Link / locator | Retrieved | Status |
|---|---|---|---|---|---|
| E-01 | DICOMViewerV3 project repository | Current DICOM writer implementations and their focused regressions | `src/gui/export_manager.py`, `src/core/mpr_dicom_export.py`, `tests/test_mpr_dicom_export.py` | 2026-09-01 | Repository implementation evidence only; it does not establish an external DICOM requirement or an IOD/profile claim. |
| E-02 | DICOMViewerV3 project repository | User-reachable DICOM-export descriptions | `user-docs/USER_GUIDE_EXPORT.md`, `user-docs/USER_GUIDE_ANONYMIZATION.md`, `user-docs/USER_GUIDE_MPR.md` | 2026-09-01 | Used only to identify documented entry points and scope wording. |

## User-reachable DICOM writers

| Output family | User entry point | What the writer does today | SOP Class / IOD scope recorded here | Evidence anchors | Assessment boundary |
|---|---|---|---|---|---|
| Ordinary (non-projection) DICOM export | **File → Export…** with format **DICOM** and no projection | Serializes the selected loaded dataset. With the deep workflow selected, it serializes the transformed copy; without it, it serializes the in-memory dataset. | Preserves the source dataset's SOP Class UID rather than selecting from an app-owned allowlist. Source IOD validity is not independently validated by this path. | `src/gui/export_manager.py` `ExportManager.export_slice()` DICOM branch; `user-docs/USER_GUIDE_EXPORT.md` “DICOM export” section | No formal source-IOD preservation promise or profile coverage conclusion. |
| Dedicated metadata-deidentified DICOM export | **File → De-identify & Export DICOM…** | Uses the ordinary export writer with a batch transformed by `DeepDICOMAnonymizer`. | Same source SOP Class/IOD boundary as ordinary export. | `src/gui/export_manager.py` `build_deep_anonymized_selection()` and `export_slice()`; `user-docs/USER_GUIDE_ANONYMIZATION.md` workflows table | The shared transformation does not itself validate every source IOD's required attributes. |
| Projection DICOM export | **File → Export…** with DICOM projection options | Deep-copies the selected source, generates a new SOP Instance UID, then writes through the ordinary DICOM branch. | Derived-object SOP Class/IOD selection is inherited from the projection implementation and is not yet enumerated/validated in this record. | `src/gui/export_manager.py` projection branch in `export_slice()`; `src/gui/export_rendering.py` `create_projection_dataset()` | Requires a separate derived-projection IOD inventory before it can support an IOD or profile claim. |
| MPR DICOM save — CT source modality | **File → Save MPR as DICOM…** | Constructs a derived slice stack and sets `SOPClassUID`/File Meta to CT Image Storage when the template modality is `CT`. | Emits CT Image Storage for this branch. It is not yet a statement that every CT Image IOD requirement has been independently validated. | `src/core/mpr_dicom_export.py` module “SOP class selection”, `_choose_sop_class_uid()`, and `write_mpr_series()`; `tests/test_mpr_dicom_export.py::test_write_mpr_series_round_trip_ct` | Candidate formal IOD scope; Type 1/2/conditional matrix pending. |
| MPR DICOM save — MR source modality | **File → Save MPR as DICOM…** | Constructs a derived slice stack and sets `SOPClassUID`/File Meta to MR Image Storage when the template modality is `MR`. | Emits MR Image Storage for this branch. It is not yet a statement that every MR Image IOD requirement has been independently validated. | `src/core/mpr_dicom_export.py` `_choose_sop_class_uid()` and `write_mpr_series()`; `tests/test_mpr_dicom_export.py::test_write_mpr_series_selects_mr_storage_for_mr_template` | Candidate formal IOD scope; Type 1/2/conditional matrix pending. |
| MPR DICOM save — any other or absent source modality | **File → Save MPR as DICOM…** | Constructs a derived slice stack and sets `SOPClassUID`/File Meta to Secondary Capture Image Storage; sets `Modality` to `OT`. | Emits Secondary Capture Image Storage for this branch. It is not yet a statement that every Secondary Capture IOD requirement has been independently validated. | `src/core/mpr_dicom_export.py` module “SOP class selection”, `_choose_sop_class_uid()`, and `write_mpr_series()`; `tests/test_mpr_dicom_export.py::test_write_mpr_series_secondary_capture_nm` | Candidate formal IOD scope; Type 1/2/conditional matrix pending. |

## Explicit non-DICOM outputs

PNG/JPG, screenshots, cine, tag exports, ROI statistics, and radiation-dose
CSV/JSON are not DICOM SOP Instance writers. Their privacy wording and any
value masking remain in the reassessment plan, but they are outside the
PS3.15 Table E.1-1 action-to-IOD assessment.

## What action resolution needs next

For each candidate formal IOD scope, record a version-pinned PS3.3 source and
an assessment row containing:

| Field | Why it is needed |
|---|---|
| SOP Class UID and IOD name | States the exact object, rather than inferring it from modality alone. |
| Source edition, section/table, canonical URL, retrieval date, and digest | Makes the Type requirements reproducible and distinguishes a moving current URL from the reviewed edition. |
| Attribute path/tag and IOD Type (1, 1C, 2, 2C, 3) | Resolves the Table E.1-1 action when it has compound `X/Z/D` behavior. |
| Condition and assessment input | Keeps conditional requirements from being treated as unconditional. |
| Selected metadata-transformation option set | Required because retention options can change the applicable action. |
| Effective action and implementation/test evidence | Separates a standard-derived expected result from current code behavior and final serialized-output evidence. |
| Status: pass, fail, not applicable, or unresolved | Prevents an absent attribute or unreviewed condition from being counted as a pass. |

No raw Table E.1-1 row, source modality, successful pydicom write, or
successful pydicom read-back is sufficient by itself to establish IOD validity
or PS3.15 profile conformance.

## Update triggers

Update this baseline before changing a DICOM writer, adding a new derived
object type, advertising a supported SOP Class/IOD, changing the applicable
DICOM edition, or narrowing/broadening the metadata-deidentification scope.

# Deep Anonymizer Export Plan

**Status:** Phases 1–3 complete (2026-06-04); Phase 4 manual QA was superseded by the completed [PS3.15 De-identification Conformance Plan](../completed/PS315_DEIDENTIFICATION_CONFORMANCE_PLAN.md). That plan hardens this engine to the PS3.15 Basic Profile, makes the inline Export checkbox conformant, and **merges both export paths onto one engine + shared options UI (Option B)** — the standalone "Deep Anonymization" dialog became "De-identify & Export DICOM (PS3.15)".
**Priority:** P1  
**TO_DO ref:** Features (Near-Term) — "Add a Deep Anonymizer export option"

---

## Goal

Add a **Deep Anonymizer** export mode that strips **all identifying metadata** — not just patient PHI (group `0010`) but also institution, scanner, location, operator, and device identifiers — so the exported DICOM is safe to share publicly or with researchers who should not see site-specific information.

The existing `DICOMAnonymizer` (`src/utils/dicom_anonymizer.py`) handles only **group 0010** (patient tags). Deep anonymization is a superset.

---

## Phase 1 — Tag inventory and profile definition

- [x] Define a **deep-anonymize tag profile** as a data structure (list of `(tag, action)` tuples or a YAML/dict config). Actions: `remove`, `replace_with(value)`, `hash`, `date_shift`.
- [x] Cover at minimum:
  - **Patient group (0010,xxxx):** already handled; reuse existing logic.
  - **Institution / site:** `InstitutionName` (0008,0080), `InstitutionAddress` (0008,0081), `InstitutionalDepartmentName` (0008,1040), `InstitutionCodeSequence` (0008,0082).
  - **Station / device:** `StationName` (0008,1010), `DeviceSerialNumber` (0018,1000), `ManufacturerModelName` (0008,1090), `Manufacturer` (0008,0070), `SoftwareVersions` (0018,1020), `DetectorID` (0018,700A), `GantryID` (0018,1008).
  - **Operator:** `OperatorsName` (0008,1070), `PerformingPhysicianName` (0008,1050), `ReferringPhysicianName` (0008,0090), `NameOfPhysiciansReadingStudy` (0008,1060), `RequestingPhysician` (0032,1032).
  - **UIDs (optional):** `StudyInstanceUID`, `SeriesInstanceUID`, `SOPInstanceUID` — option to re-mint with prefix `2.25.` + UUID, preserving internal cross-references within the export batch.
  - **Dates (optional):** shift all dates by a random per-study offset (preserving relative deltas within a study) or zero them.
  - **Private tags (group odd):** option to remove all private creator + data blocks.
  - **Other free-text tags** that commonly leak names: `ContentDescription`, `ImageComments`, `AdditionalPatientHistory`, `PatientComments`, `StudyComments`, `RequestedProcedureDescription`.
- [x] Cross-reference DICOM PS3.15 Annex E (Basic Application Level Confidentiality Profile) and the DICOM supplement 142 de-identification profiles for completeness.
- [x] Store profile in a new module `src/utils/deep_anonymizer_profile.py` as a Python constant (importable, testable).

## Phase 2 — Deep anonymizer implementation

- [x] Create `src/utils/deep_anonymizer.py` with class `DeepDICOMAnonymizer`:
  - Constructor accepts profile and options (retain manufacturer: bool, uid_remap: bool, date_shift_days: int | None, strip_private: bool).
  - `anonymize_dataset(ds: Dataset) -> Dataset` — applies profile to a copy.
  - `anonymize_batch(datasets: list[Dataset]) -> list[Dataset]` — consistent UID remapping and date shifting across a batch.
  - Internal UID remap table (old → new) built per batch, so intra-study references remain consistent.
- [x] Reuse `DICOMAnonymizer._is_text_vr()` / `_is_date_vr()` or factor them into a shared utility (`dicom_vr_helpers.py`).
- [x] Unit tests in `tests/test_deep_anonymizer.py`:
  - All profile tags removed/replaced on a synthetic dataset.
  - UID remapping preserves cross-references (Series A, Series B in same study).
  - Date shifting preserves relative order.
  - `strip_private` removes odd-group tags.
  - Round-trip: anonymized dataset is valid DICOM (pydicom can re-read).

## Phase 3 — UI integration

- [x] Add **File → Export → Export with Deep Anonymization…** menu entry (or a checkbox/radio in the existing export dialog).
- [x] Options dialog (modal before export):
  - Checkboxes: Strip institution/device, Strip operator/physician names, Re-mint UIDs, Shift dates, Remove private tags, Remove free-text comments.
  - All **on by default** (deep anonymize = maximum stripping).
- [x] Wire to the existing DICOM export pipeline (`export_manager.py` / file dialog flow).
- [ ] Also expose from context menu on navigator thumbnails if single-series export is supported there.

## Phase 4 — Verification

- [ ] Manual QA: export a CT and MR study with deep anonymize; reload; confirm no institution, station, operator, or patient data survives.
- [ ] Confirm standard viewer display (W/L, pixel data, spatial metadata) is unaffected.
- [x] Run existing export tests to ensure no regression. *(Reviewer 2026-06-04: full suite **856** passed incl. `tests/test_export_manager.py` — tester fan-in.)*

---

## Open questions

1. **Should manufacturer/model be optional?** Some research use-cases need to know the scanner model but not the site. Default strip, optional retain.
2. **Burned-in PHI detection:** out of scope for this plan (pixel-level OCR/redaction is a separate feature), but warn the user that burned-in text is not removed.
3. **DICOM PS3.15 compliance label:** should the exported file include the `PatientIdentityRemoved` (0012,0062) = `YES` and `DeidentificationMethod` (0012,0063) tags?  Recommend yes.

---

## Files likely touched

| File | Change |
|------|--------|
| `src/utils/deep_anonymizer_profile.py` | **New** — tag profile constant |
| `src/utils/deep_anonymizer.py` | **New** — `DeepDICOMAnonymizer` class |
| `src/utils/dicom_anonymizer.py` | Minor — extract shared VR helpers if desired |
| `src/gui/main_window_menu_builder.py` | **File → Export** menu entry (View → Layout is stream A — avoid that section) |
| `src/gui/dialogs/deep_anonymizer_export_dialog.py` | **New** (preferred) — options modal before export |
| `src/gui/dialogs/export_dialog.py` | Optional: deep-anonymize checkbox or delegate to new dialog |
| `src/gui/export_manager.py` | **Primary DICOM export hook** — apply `DeepDICOMAnonymizer` when deep mode selected (not `export_rendering.py`, which is Pillow raster only) |
| `src/gui/export_app_facade.py` / `src/gui/actions/dialog_actions.py` | Wire menu action → dialog → export manager |
| `tests/test_deep_anonymizer.py` | **New** — unit tests |

**Plan review (2026-06-04):** Corrected path — DICOM byte export flows through **`export_manager.py`** + **`export_dialog.py`**, not `src/gui/export_rendering.py` (image raster/projection only). Existing **`anonymize=True`** uses **`DICOMAnonymizer`** (group 0010 only); deep mode is a separate code path or superset flag.

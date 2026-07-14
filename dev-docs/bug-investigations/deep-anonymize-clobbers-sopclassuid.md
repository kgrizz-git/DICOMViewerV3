# Deep anonymize clobbers SOPClassUID (and other non-instance UIDs)

**Status:** ✅ **FIXED 2026-06-14** (was: confirmed pre-release blocker)
**Found:** 2026-06-14 (while validating an ACR CT phantom fixture)
**Severity:** High — produced non-conformant DICOM; broke pylinac QA and SOP-class dispatch

## Resolution (2026-06-14)

`src/utils/deep_anonymizer.py`: added `DICOM_STANDARD_UID_ROOT = "1.2.840.10008"` and guarded both
`_collect_ui_values_from_element` (don't collect standard UIDs) and `_remap_single_uid` (never remap
standard UIDs). Instance/study/series/frame-of-reference UIDs are organization-rooted (not under that
root), so they're still remapped — including **referenced instance UIDs in sequences** (referential
integrity preserved), while `SOPClassUID`, `ReferencedSOPClassUID`, and `TransferSyntaxUID` are kept.
Tests added in `tests/test_deep_anonymizer.py`:
`test_uid_remap_preserves_sop_class_and_standard_uids`, `test_uid_remap_referential_integrity`
(9/9 pass; 105 anon/export tests green).

---

## Summary

`DeepDICOMAnonymizer` (deep-anonymize export) **regenerates `SOPClassUID`** with a random
`generate_uid()` value instead of preserving it. `SOPClassUID` is **not PHI** and must be kept;
only instance-identifying UIDs should be remapped. The mangled SOP class makes the output
non-conformant and unusable by tools that dispatch on SOP class.

## Evidence (empirical)

Running the anonymizer on a clean `CT_small.dcm` (proper `CT Image Storage`):

```
SOPClassUID    : 1.2.840.10008.5.1.4.1.1.2 -> 1.2.826.0.1.3680043.8.498.2523...  CHANGED: True  (WRONG)
SOPInstanceUID : changed: True   (correct)
SeriesInstanceUID: changed: True (correct)
```

The replacement carries pydicom's root prefix `1.2.826.0.1.3680043.8.498`, i.e. `generate_uid()`.

## Root cause (`src/utils/deep_anonymizer.py`)

- `UID_TAGS` (in `deep_anonymizer_profile.py`) is **correct** — only `SOPInstanceUID`,
  `StudyInstanceUID`, `SeriesInstanceUID`, `FrameOfReferenceUID`, `SynchronizationFrameOfReferenceUID`.
- But `_build_uid_map` also calls **`_collect_ui_values_from_element(ds, seen)`** (≈line 137), which
  walks the dataset and collects **every element with VR `UI`** — including `SOPClassUID`,
  `ReferencedSOPClassUID`, coding-scheme UIDs, etc. — and assigns each a `generate_uid()` (≈line 141).
- `_apply_uid_remap` (≈line 182-184) then rewrites **every** `UI` element whose value is in the map.

So the blanket UI collection/replacement is the flaw: it remaps far more than instance identity.

## Impact

- **Breaks pylinac QA** on deep-anonymized data: pylinac's stack loader keeps files only if
  `"Image Storage" in SOPClassUID.name`; a random UID fails → **"No files were found"**. (This is
  exactly what blocked the ACR CT phantom fixture; see TO_DO demo-data item.)
- **Non-conformant DICOM**: SOP Class no longer matches the IOD; PACS/viewers that route by SOP
  class may reject or mishandle it.
- Likely also clobbers **`ReferencedSOPClassUID`** (in reference sequences) and **standard/well-known
  UIDs** (anything VR=UI under the DICOM root `1.2.840.10008`), which must never be remapped.

## Fix scope (not yet implemented)

Remap **only instance-identity UIDs**, preserve everything else:

1. Remap the explicit `UID_TAGS` instance UIDs (as today) **plus referenced *instance* UIDs** in
   sequences (`ReferencedSOPInstanceUID`, etc.) for referential integrity.
2. **Never remap**: `SOPClassUID`, `ReferencedSOPClassUID`, `TransferSyntaxUID`,
   `MediaStorageSOPClassUID`, coding-scheme UIDs, and **any UID in the `1.2.840.10008` standard
   space** (guard: skip remap if the value startswith `1.2.840.10008`).
3. Drop / narrow the blanket `_collect_ui_values_from_element` collection so it cannot capture
   class/standard UIDs.

## Validation to add with the fix

- Unit test: after deep-anonymize, `SOPClassUID` (and `ReferencedSOPClassUID`, `TransferSyntaxUID`)
  are **unchanged**, while `SOPInstanceUID`/`SeriesInstanceUID`/`StudyInstanceUID` **are** changed
  and remain internally consistent (referential integrity preserved).
- Regression: deep-anonymized ACR CT/MRI still load + analyze in pylinac.

## Workaround (already used to validate the ACR CT fixture)

Restoring `SOPClassUID` = `1.2.840.10008.5.1.4.1.1.2` on the affected files makes pylinac load them;
the app's `run_acr_ct_analysis` then analyzes successfully (`success=True`). The corrected copy lives
(git-ignored) at `test-DICOM-data/acr-ct-sopclass-fixed/`.

## Related
- TO_DO → Bugs/Correctness (this item) and Release/Product readiness gate.
- Demo-data collection TO_DO (the ACR CT fixture this surfaced).

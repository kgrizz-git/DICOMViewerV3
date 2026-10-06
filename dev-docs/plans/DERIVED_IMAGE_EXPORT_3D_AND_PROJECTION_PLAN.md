# Derived-Image Export Plan — 3D Render Images and Projection DICOM

**Status:** Active (not started)
**Last updated:** 2026-10-06
**TO_DO refs:** Next up slot "Derived-image export batch"; 3D volume rendering
sub-items "Export current 3D volume render as image" and "…as Secondary Capture
(SC) DICOM"; Measurements/projections item "Allow export of AIP, MIP, MinIP
stack as DICOM or images".
**Supersedes:** [`PROJECTION_EXPORT_PLAN.md`](supporting/PROJECTION_EXPORT_PLAN.md)
for scope and ordering. That plan predates the shipped projection export and its
"Current state" section is stale.

## Goal

Ship the derived-image exports users still lack, in order of value per effort:

1. **Phase A:** save the current 3D volume render as PNG or JPG.
2. **Phase B:** make the shipped projection **DICOM** export produce valid,
   distinct derived instances.
3. **Phase C:** save the 3D render as a Secondary Capture DICOM.

Each phase is one PR. Phase A is independent of B and C. Phase C reuses the
writer helpers that Phase B settles.

## Current state (verified 2026-10-06)

### Projection export is mostly shipped

When Combine Slices is on, the Export dialog already exports projections. The
dialog shows a note naming the projection type and slab size
(`gui/dialogs/export_dialog.py:185`).

- **PNG/JPG** route through `export_rendering.create_projection_for_export`
  with W/L, LUT, photometric polarity, and overlays
  (`gui/export_manager.py:571`). Cine export uses the same path.
- **DICOM** routes through `export_rendering.create_projection_dataset`
  (`gui/export_manager.py:549`).
- Series and multi-slice scopes run per slice, so a projection **stack** export
  already works for all three formats. Filenames carry a
  `_MIP_8slices`-style suffix.

That covers Phase 1a/1b and most of Phase 2 of the old plan. Phase 2's sliding
slab exists. Its non-overlapping-slab option and caching remain unbuilt and are
not in scope here.

### Projection DICOM output has correctness gaps

`create_projection_dataset` (`gui/export_rendering.py:388`) deep-copies the
source instance and swaps in new pixels. It sets a new `SOPInstanceUID`,
`ImageType = DERIVED\SECONDARY\{AIP|MIP|MINIP}`, and an `ImageComments` note.
It has these defects:

1. **The series UID is reused.** `SeriesInstanceUID` stays the source value, so
   exported projections merge into the original series on re-import or in PACS.
   A stack export should share one new series UID.
2. **`file_meta` goes stale.** `MediaStorageSOPInstanceUID` keeps the source
   SOP UID, so it disagrees with the dataset. `TransferSyntaxUID` is copied as
   is. For a compressed source (JPEG, JPEG 2000, RLE), raw `PixelData` is
   written under a compressed transfer syntax, and the file is unreadable.
3. **Native bytes go under an encapsulated syntax.** This is the same root
   cause as item 2. It also applies to the single-slice fallback.
4. **AIP truncates.** `astype` floors the float mean instead of rounding it.
5. **Rescale assumptions are unchecked.** Projections reduce over **stored**
   values, and the copied `RescaleSlope`/`RescaleIntercept` come from the first
   slice. That is right only when every slice in the slab shares one rescale
   (CT normally does; PET often does not).
6. **There is no derivation metadata.** There is no `DerivationDescription`, no
   `SourceImageSequence`, and no `ReferencedSeriesSequence`.
   `mpr_dicom_export.py` already writes these.
7. **Multi-frame `InstanceNumber` can collide.** `9000 + slice_index` is unique
   within one export but not across two exports of the same series.

### 3D render

- The default surface is the offscreen `VolumeRenderSurface`
  (`gui/volume/render_surface.py`). It caches the displayed frame as a detached
  `QImage` in `_image`. That frame is updated on every grab.
- The viewport text overlay is a separate `QLabel`
  (`volume_viewer_widget.py:187`). It is **not** burned into the `QImage`, so a
  saved frame carries no preset or status text and no patient text.
- The legacy `QVTKRenderWindowInteractor` surface (`gui/volume/legacy_surface.py`,
  behind `DICOMVIEWER_3D_LEGACY_INTERACTOR=1`) has no cached image. It is slated
  for removal.
- No export or save action exists in the 3D viewer today.

## Phase A — Save 3D render as PNG/JPG

### A1. Surface accessor

- [ ] Add `VolumeRenderSurface.current_image() -> QImage | None`. It returns a
  copy of `_image`, or `None` when no frame has been grabbed or the surface was
  cleaned up.
- [ ] Add the same method to the legacy surface, returning `None`. Do not add a
  `vtkWindowToImageFilter` readback for a path that is being removed. The UI
  disables the action instead.

### A2. Optional high-resolution capture

- [ ] Decide during implementation whether to offer a **scale factor** (1×, 2×,
  4×). This would re-render the offscreen window at a larger size, grab once,
  and restore the size. Start with **1× only**, the cached frame, and keep the
  scale option as a follow-up unless it falls out cheaply from `_grab(width,
  height)`. A larger render must not block the GUI thread for long on Fast GPU
  or software fallback.

### A3. UI

- [ ] Add a **Save Image…** button to the 3D viewer's bottom button row, next to
  **Reset View**. Bind `Ctrl+S` as a `QShortcut` on the 3D dialog.
  `gui/volume/shortcuts.py` dispatches bare VTK keysyms, so it is the wrong
  home for a modified key.
- [ ] Disable the button until the first frame is painted and while a build is
  in progress. Disable it on the legacy surface, with a tooltip saying why.
- [ ] Use a `QFileDialog` save dialog with PNG/JPG filters. Default the filename
  to `3D_<preset>_<YYYYMMDD-HHMMSS>.png`. Use the preset name only, never
  patient or study fields. Remember the last folder through
  `get_last_export_path` / `set_last_export_path` (`utils/config/paths_config.py`).
- [ ] Save with `QImage.save` (JPG quality 95). Report failure in a message box
  without the path text in logs (use the redacting logger helpers).

### A4. Optional overlay burn-in

- [ ] Add a checkbox in the save dialog, or a persisted option, to burn in the
  viewport overlay text. **Default off.** The overlay holds only render state
  today, but burn-in must reuse `build_overlay_text` output and never add
  patient fields.

### A5. Tests

- [ ] Unit: `current_image()` returns a detached copy, and mutating it does not
  change the surface. It returns `None` before the first grab and after cleanup.
- [ ] Qt: the button stays disabled until a frame exists. Saving to `tmp_path`
  writes a PNG of the expected size. Use a stub surface, not real VTK, so the
  test does not need native graphics.
- [ ] Filename builder: covers preset names with path-unsafe characters.

### A6. Docs and closeout

- [ ] User docs: add a 3D viewer section on saving an image.
- [ ] Add a `CHANGELOG.md` entry (minor: new user-visible capability).
- [ ] Remove the TO_DO 3D "export as image" sub-item.

## Phase B — Projection DICOM correctness

Refactor first, then fix. Move the DICOM builder out of `gui/export_rendering.py`
into `core/projection_dicom_export.py`. It has no Qt dependency, and
`mpr_dicom_export.py` already lives in `core/`. Check the move with
`scripts/check_architecture_boundaries.py`.

- [ ] **B1. New series per export run.** `ExportManager` creates one
  `SeriesInstanceUID` per (source series, projection type, slab) export run and
  passes it to the builder. Set `SeriesNumber` to the source value plus 500,
  matching `mpr_dicom_export.py:328`. Keep `SeriesDescription` as
  `"<source> - MIP"`.
- [ ] **B2. Fresh `file_meta`.** Rebuild `file_meta` the way
  `mpr_dicom_export.py:350` does. Set `MediaStorageSOPClassUID` and
  `MediaStorageSOPInstanceUID` to match the dataset, use
  `ExplicitVRLittleEndian`, and set the implementation UID. Apply this to the
  single-slice fallback too, which fixes defects 2 and 3.
- [ ] **B3. Round, don't floor.** Use `np.rint` before the integer cast.
- [ ] **B4. Rescale guard.** If slab slices disagree on `RescaleSlope` or
  `RescaleIntercept`, project in **rescaled** space and re-encode to int16 with
  a computed slope and intercept (the MPR export encoding). Otherwise keep the
  current stored-value path, which preserves exact pixel values.
- [ ] **B5. Derivation metadata.** Add `DerivationDescription` (for example,
  "Maximum Intensity Projection of 8 slices, instances 42–49"). Add
  `SourceImageSequence` entries for the slab's SOP instances and a
  `ReferencedSeriesSequence` for the source series. Use the
  `DerivationCodeSequence` codes from CID 7203 only if they map cleanly. If not,
  skip them rather than guess.
- [ ] **B6. Instance numbering.** Number instances 1..N within the new series
  instead of `9000 + index`.
- [ ] **B7. Anonymization.** Confirm that deep-anonymize runs on the
  **projection** dataset, after B1–B5, so the new reference sequences are also
  scrubbed. Add a test for this.
- [ ] **B8. Tests** (`tests/core/test_projection_dicom_export.py`):
  - A two-slice MIP stack shares one new series UID that differs from the
    source.
  - `file_meta` SOP UID equals the dataset SOP UID, and the transfer syntax is
    Explicit VR Little Endian.
  - A compressed-source fixture (RLE via pydicom, generated in the test) writes
    a readable file.
  - AIP rounding works, and mixed-rescale slabs go through the rescaled path.
  - Deep-anonymized output carries no source patient fields inside the
    reference sequences.
- [ ] **B9. Closeout.** Add a `CHANGELOG.md` entry (patch: export correctness).
  Mark `PROJECTION_EXPORT_PLAN.md` complete except for the deferred items, move
  it to `plans/completed/`, and remove the TO_DO projection-export item.

## Phase C — 3D render as Secondary Capture DICOM

- [ ] Write a single-frame RGB SC instance from the Phase A `QImage`. Use
  `SecondaryCaptureImageStorage`, `PhotometricInterpretation = RGB`,
  `SamplesPerPixel = 3`, `PlanarConfiguration = 0`, and a new Series and SOP UID.
  Set `ImageType = DERIVED\SECONDARY` and `ConversionType = WSD`.
- [ ] Copy the patient, study, and equipment modules from the source series
  template. Add a `ReferencedSeriesSequence`, and a `DerivationDescription`
  that names the preset and blend mode.
- [ ] Reuse the Phase B `file_meta` and series-numbering helpers. Do not create
  a third copy.
- [ ] Offer it as **Save Image…** format "DICOM (Secondary Capture)", with the
  existing deep-anonymize option.
- [ ] Tests: round-trip read with pydicom, check the pixel shape and SOP class,
  and confirm anonymized output carries no source patient fields.
- [ ] Closeout: add a CHANGELOG entry (minor) and remove the TO_DO SC sub-item.

## Out of scope

- Multi-frame or rotation-sweep 3D export (cine of the 3D view).
- Non-overlapping projection slabs, projection caching, and the slab-override
  control from the old plan's open questions. These stay in the superseded plan
  until someone promotes them.
- Changing MIP/MinIP polarity under MONOCHROME1. This is tracked separately in
  `TO_DO.md`.

## Risks

- **PHI:** Every new file write must go through the existing deep-anonymize
  option. 3D filenames must not use patient or study fields. Run
  `scripts/git_hook_privacy_checks.py --staged` before each commit.
- **Native VTK in tests:** Phase A tests stub the surface. Any real-VTK test
  follows the sandbox guidance in `AGENTS.md`.
- **Behavior change in shipped export:** Phase B changes the UIDs and the
  transfer syntax of files users already produce. This is a correctness fix, but
  the CHANGELOG entry must say so.

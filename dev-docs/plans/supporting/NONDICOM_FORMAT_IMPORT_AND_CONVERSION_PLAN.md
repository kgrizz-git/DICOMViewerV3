# Non-DICOM Format Import and Conversion Plan

## Goal and success criteria

Add a controlled path for opening, displaying, and converting selected non-DICOM medical image formats, starting with NIfTI (`.nii`, `.nii.gz`) and then evaluating NRRD (`.nrrd`, `.nhdr`), MetaImage (`.mha`, `.mhd`), and possibly Analyze (`.hdr` / `.img`) if there is a concrete need.

Success means:

- Users can open a supported non-DICOM volume and view it through the existing slice, MPR, 3D, W/L, histogram, and export workflows where geometry permits.
- DICOM-native workflows still receive `pydicom.Dataset` objects and are not silently broken by synthetic metadata.
- DICOM-to-NIfTI export and NIfTI-to-DICOM conversion are explicit conversion commands, not hidden side effects of open/display.
- Licensing, packaging size, subprocess safety, and metadata loss are reviewed before adding any new dependency or bundled converter.

## Context and links

- Backlog item: [`dev-docs/TO_DO.md`](../../TO_DO.md) under Features (Near-Term).
- Existing app stack:
  - `requirements.txt` already pins `SimpleITK>=2.5.4` for MPR/fusion and `vtk>=9.3.0` for 3D volume rendering.
  - `src/core/mpr_volume.py` builds a `SimpleITK` image from DICOM datasets and is the current geometry bridge for MPR/3D.
  - `src/gui/file_operations_handler.py` and `src/core/dicom_loader.py` are DICOM-specific today.
  - `src/gui/slice_display_manager.py`, `src/gui/series_navigator.py`, `src/core/dicom_processor.py`, and export/ROI/statistics paths assume `pydicom.Dataset` inputs.
- Candidate libraries / tools researched 2026-06-11:
  - [`SimpleITK`](https://github.com/SimpleITK/SimpleITK): Apache-2.0; already in this repo; can be the first reader/writer spike for NIfTI/NRRD/MHA volume files.
  - [`nibabel`](https://github.com/nipy/nibabel): MIT/BSD; strong Python NIfTI/Analyze/GIFTI/CIFTI/MINC/AFNI/PAR/REC support; useful if SimpleITK's NIfTI metadata handling is insufficient for neuroimaging-specific workflows.
  - [`dcm2niix`](https://github.com/rordenlab/dcm2niix): mostly BSD with some public-domain/MIT components; robust DICOM-to-NIfTI converter with BIDS JSON sidecar support; best treated as an external CLI/package, not vendored source, unless packaging review approves.
  - [`dicom2nifti`](https://github.com/icometrix/dicom2nifti): MIT; Python DICOM-to-NIfTI converter, supports command-line and Python API; may require GDCM for compressed DICOM support.
  - [`dcmqi`](https://github.com/QIICR/dcmqi): BSD-3-Clause; focused on DICOM SEG, Parametric Map, and SR/TID1500 conversions to/from research formats, not general CT/MR image DICOMization.
  - [`highdicom`](https://github.com/ImagingDataCommons/highdicom): MIT; useful for standards-compliant DICOM derived objects such as SEG, Parametric Map, Secondary Capture, GSPS, KO, SR, and legacy converted enhanced images.

## Non-goals

- Do not make a non-DICOM file look like a normal source DICOM series without clearly marking it as imported/synthetic.
- Do not promise lossless round-trip conversion. NIfTI generally cannot preserve the full DICOM object model, private tags, per-frame functional groups, presentation states, SR, dose, or acquisition provenance.
- Do not add GPL-only dependencies or bundled binaries without explicit release/packaging approval.
- Do not implement PACS send/store for converted objects in this plan; that belongs with the existing DICOM write / PACS interchange backlog.

## Task graph and gates

### Ordering

- S1 -> S2 -> Gate 1 -> T1/T2/T3.
- T1 -> T4 -> T5.
- T2 can run after Gate 1 and in parallel with T1 if it only touches conversion service modules.
- T6/T7 happen after the first working import/export path exists.

### Verification gates

- Gate 1: reviewer approves dependency/licensing choice and confirms whether `SimpleITK` alone is enough for initial NIfTI read/display.
- Gate 2: tester verifies geometry orientation, W/L, MPR, 3D, and export behavior on at least one NIfTI volume and one native DICOM series.
- Gate 3: release/packaging owner approves any bundled CLI binary, subprocess usage, and license notices.

## Phases

### Phase 0 - Dependency and format spike

- [ ] (S1) Spike `SimpleITK.ReadImage()` on `.nii`, `.nii.gz`, `.nrrd`, and `.mha` samples; record loaded dimension, spacing, origin, direction, scalar type, component count, and array orientation. (owner: coder, parallel-safe: yes, stream: A, after: none)
- [ ] (S2) Compare `SimpleITK` vs `nibabel` for NIfTI affine/orientation behavior and metadata retention; recommend whether `nibabel` is needed for v1. (owner: coder, parallel-safe: yes, stream: B, after: none)
- [ ] (S3) Evaluate DICOM-to-NIfTI conversion candidates (`dcm2niix`, `dicom2nifti`) using one CT/MR series and one multi-frame or enhanced edge case; document metadata outputs and failure modes. (owner: coder, parallel-safe: yes, stream: C, after: none)
- [ ] (S4) Evaluate NIfTI-to-DICOM target choices: simple Secondary Capture for display-only export, legacy converted enhanced objects when appropriate, and SEG/Parametric Map via `highdicom`/`dcmqi` for label maps or quantitative maps. (owner: coder, parallel-safe: yes, stream: D, after: none)

### Phase 1 - Internal volume abstraction

- [ ] (T1) Define a small `ImageVolume`/`LoadedVolume` model that carries pixel data or `sitk.Image`, spacing, origin, direction, scalar label, source format, source path, and optional source DICOM datasets. (owner: coder, parallel-safe: no, stream: none, after: Gate 1)
- [ ] (T2) Refactor MPR/3D volume entry points to accept either DICOM-backed `MprVolume` or a non-DICOM `sitk.Image` wrapper without forcing synthetic `pydicom.Dataset` objects through every call. (owner: coder, parallel-safe: no, stream: none, after: T1)
- [ ] (T3) Add format detection helpers for DICOM vs NIfTI/NRRD/MHA and keep DICOM skip rules (`DICOMDIR`, `VERSION`, `LOCKFILE`) separate from non-DICOM detection. (owner: coder, parallel-safe: yes, stream: E, after: Gate 1)

### Phase 2 - Open/display workflow

- [ ] (T4) Add Open Volume / non-DICOM selection UI, extension filters, drag-drop routing, and clear user-facing labels such as "NIfTI volume" instead of DICOM modality/study labels. (owner: coder, parallel-safe: no, stream: none, after: T1)
- [ ] (T5) Display non-DICOM slices with W/L, pan/zoom, histogram, MPR, and 3D where supported; disable or explain DICOM-only actions such as DICOM tag browser, DICOM metadata export, SR/KO/GSPS, and source DICOM anonymization. (owner: coder, parallel-safe: no, stream: none, after: T4)
- [ ] (T6) Add overlay and navigator rules for non-DICOM volumes: slice index/count, physical spacing/orientation when available, source format, and no fake `PatientName`, `StudyInstanceUID`, or modality. (owner: coder, parallel-safe: no, stream: none, after: T5)

### Phase 3 - Conversion workflows

- [ ] (T7) Add DICOM-to-NIfTI export using the approved backend; include sidecar JSON when backend supports it, progress/cancel UI, and clear warnings about metadata loss. (owner: coder, parallel-safe: no, stream: none, after: S3)
- [ ] (T8) Add NIfTI-to-DICOM export only after selecting the target object class: Secondary Capture for rendered/display pixels, Parametric Map for quantitative voxel maps, SEG for label maps, or legacy/enhanced image objects when enough source metadata exists. (owner: coder, parallel-safe: no, stream: none, after: S4)
- [ ] (T9) Add optional dependency/binary discovery UI if a conversion backend is not bundled; never silently download binaries at runtime. (owner: coder, parallel-safe: no, stream: none, after: T7)

### Phase 4 - Tests, docs, and packaging

- [ ] (T10) Add unit tests for format detection, geometry conversion, W/L/display decisions, and DICOM-only action gating. (owner: tester, parallel-safe: yes, stream: F, after: T5)
- [ ] (T11) Add small synthetic fixture generation for NIfTI/NRRD/MHA when licensing permits; avoid committing large patient datasets. (owner: tester, parallel-safe: yes, stream: F, after: S1)
- [ ] (T12) Update user docs with supported formats, limitations, conversion warnings, and dependency/binary requirements. (owner: docs, parallel-safe: yes, stream: G, after: T7)
- [ ] (T13) Update release/packaging notes with any new license notices, binary source URLs, checksums, and platform-specific install behavior. (owner: release, parallel-safe: no, stream: none, after: Gate 3)

## Risks and mitigations

| Risk | Mitigation |
|------|------------|
| NIfTI affine/orientation is mapped incorrectly into DICOM/LPS viewer coordinates | Spike with known-orientation fixtures; compare `SimpleITK` and `nibabel`; add visual and numeric geometry tests. |
| Non-DICOM volume is accidentally treated as source DICOM | Add explicit source-format type and gate DICOM-only features at the UI/controller boundary. |
| Metadata loss surprises users during conversion | Conversion dialogs must show a clear warning and write sidecar/provenance where available. |
| Bundled CLI increases release size or license obligations | Prefer installed package discovery first; require packaging approval before bundling binaries. |
| Synthetic DICOM export is non-compliant | Use `highdicom`/`dcmqi` where applicable; otherwise keep first implementation to Secondary Capture or explicitly non-diagnostic export. |
| Compressed DICOM conversion support differs by backend | Test compressed transfer syntaxes; document when GDCM or external codecs are required. |

## Testing strategy

- Unit tests:
  - format detection for `.dcm`, extensionless DICOM, `.nii`, `.nii.gz`, `.nrrd`, `.mha`, and unsupported files.
  - `sitk.Image` geometry extraction: spacing, origin, direction, dimensions, scalar range.
  - DICOM-only action gating for tag browser, SR, KO, GSPS, anonymization, and source DICOM export.
  - conversion command construction without `shell=True`, with path quoting and cancellation.
- Focused integration tests:
  - load a tiny synthetic NIfTI and verify first slice display data and navigator count.
  - load a native DICOM after a non-DICOM volume and verify normal DICOM behavior is unchanged.
  - export DICOM series to NIfTI with the approved backend and confirm output exists plus sidecar/provenance when enabled.
- Manual smoke:
  - Open NIfTI, scroll slices, adjust W/L, open histogram, launch MPR and 3D, export image screenshot.
  - Try DICOM tag browser on NIfTI and confirm the app explains why it is unavailable.
  - Convert DICOM to NIfTI and inspect with an external viewer.

## Questions for user

- Should the first implementation be read/display only for NIfTI, or should DICOM-to-NIfTI export ship in the same slice?
- Is NIfTI-to-DICOM intended for rendered Secondary Capture, quantitative map/SEG workflows, or reconstructing image-like DICOM series for downstream PACS/tools?
- Should optional formats beyond NIfTI include NRRD/MHA first because `SimpleITK` likely covers them with no new dependency, or should neuroimaging formats from `nibabel` be prioritized?

## Completion notes

Not started. This is a docs-only research/backlog plan as of 2026-06-11.

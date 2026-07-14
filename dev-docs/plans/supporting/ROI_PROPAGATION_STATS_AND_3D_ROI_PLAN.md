# ROI Propagation, Slice-Profile Statistics, and 3D ROI Plan

## Goal and success criteria

Extend ROI tooling from single-slice measurements into controlled multi-slice workflows:

- Propagate a 2D ROI shape across selected slices/frames in the same series.
- Plot propagated ROI statistics across slices, similar to PET viewer workflows where users inspect ROI metric profiles over slice position.
- Add true 3D ROI support with volumetric statistics and cross-view editing/display where geometry supports it.
- Build named 3D structures by joining 2D ROIs/contours across slices.
- Add pixel-value-guided irregular ROI boundaries for contouring and masking structures, with automatic and manual sensitivity controls.
- Add reusable structure-generation presets, starting with CT and MRI body contour generation and leaving detailed anatomy/site-specific presets as later validated work.
- Export ROI/contoured-structure data as appropriate DICOM objects and practical non-DICOM formats.

Success means:

- Existing single-slice ROI creation, editing, movement, statistics, export, copy/cut/paste, and persistence continue to work.
- Propagated 2D ROIs are explicitly represented as linked per-slice ROI instances, not silently treated as a single 3D object.
- Slice-profile plots show metric vs stack index and, when available, physical position from DICOM geometry.
- 3D ROIs have distinct data structures and statistics so volumetric behavior is not bolted onto 2D ROI assumptions.
- Pixel-value-guided boundaries are reproducible: every contour records the algorithm, seed/input ROI, threshold/sensitivity values, smoothing/cleanup choices, and source image identity.
- Structure-generation presets produce editable, named structures with preview/accept, recorded preset version/parameters, and clear modality assumptions.
- Export UI distinguishes display annotations, masks/segmentations, structure contours, and measurement reports so users do not mistake screenshots/GSPS for true structure interchange.

## Context and links

- Backlog item: [`dev-docs/TO_DO.md`](../../TO_DO.md) under `Advanced ROI/contouring abilities`.
- Existing ROI seams:
  - `src/tools/roi_manager.py` owns ROI lifecycle and statistics orchestration.
  - `src/tools/roi_graphics_items.py` owns ROI graphics primitives and resize handles.
  - `src/gui/roi_coordinator.py` coordinates ROI interactions, movement, statistics updates, overlays, and panel updates.
  - `src/gui/slice_display_manager.py` displays only ROIs associated with the current slice key.
  - `src/core/roi_export_service.py` already exports ROI statistics, including multichannel stats.
  - `src/tools/roi_persistence.py` handles ROI customization persistence.
- Related completed/follow-up work:
  - ROI edit handles in [`VIEWER_UX_FEATURES_PLAN.md`](VIEWER_UX_FEATURES_PLAN.md#1-roi-editing-resize-handles).
  - ROI graphics primitive split kept `ROIItem` / `ROIManager` orchestration in `roi_manager.py`; preserve that boundary unless a dedicated refactor phase changes it.
  - Multi-frame instance navigation follow-up warns that `current_slice_index` identity paths need audit before more per-instance behavior is added.
  - DICOM write/interchange notes in [`DICOM_GSPS_KO_SECONDARY_CAPTURE.md`](../info/DICOM_GSPS_KO_SECONDARY_CAPTURE.md): GSPS is for display annotations, not voxel masks or structure interchange.

## Task graph and gates

### Ordering

- T1 -> T2 -> T3/T4.
- T3 -> T5 -> T6.
- T4 -> T7.
- S1 -> Gate 2 -> T8/T9.
- S2 -> T13/T14.
- T10 -> T15/T16.

### Verification gates

- Gate 1: reviewer approves the propagated-ROI data model before UI work starts.
- Gate 2: reviewer approves the 3D ROI representation and whether first implementation is axis-aligned box, stacked contours, brush/segmentation mask, or another model.
- Gate 3: reviewer approves the contouring/sensitivity contract before pixel-value-guided ROI tools are enabled by default.
- Gate 4: reviewer approves export targets and object semantics before any DICOM ROI/structure writer is implemented.
- Gate 5: tester verifies existing single-slice ROI workflows after each phase.

## Phases

### Phase 1 - Data model and identity audit

- [ ] (T1) Audit ROI keys and slice/frame identity paths (`study_uid`, `series_uid`, instance identifier, stack index, multi-frame frame identity) before adding cross-slice propagation. (owner: coder, parallel-safe: no, stream: none, after: none)
- [ ] (T2) Define a propagated-ROI group model that links per-slice ROI instances with shared label/color/source metadata while allowing per-slice geometry edits. (owner: coder, parallel-safe: no, stream: none, after: T1)
- [ ] (T3) Add persistence/export schema changes for propagated ROI groups with backward-compatible loading of existing single-slice ROI records. (owner: coder, parallel-safe: no, stream: none, after: T2)

### Phase 2 - 2D ROI propagation across slices

- [ ] (T4) Add propagation commands for selected ROI: copy unchanged shape to a slice range, copy to all slices in current series, and copy with optional position/scale adjustment when pixel spacing or orientation differs. (owner: coder, parallel-safe: no, stream: none, after: T2)
- [ ] (T5) Add UI affordances for propagation range selection, overwrite behavior, linked-group naming, and undo/redo of propagation as one operation. (owner: ux/coder, parallel-safe: no, stream: none, after: T4)
- [ ] (T6) Update ROI list and selection behavior so propagated groups are discoverable without hiding individual slice instances. (owner: ux/coder, parallel-safe: no, stream: none, after: T5)

### Phase 3 - ROI statistics plotted across slices

- [ ] (T7) Compute propagated ROI metric profiles across the linked slice set: mean, std, min, max, area/count, sum, and modality-appropriate units when available. (owner: coder, parallel-safe: no, stream: none, after: T3)
- [ ] (T8) Add a profile plot for ROI statistics vs slice index and physical slice position when available; support metric selection and multiple ROI/group overlays. (owner: ux/coder, parallel-safe: no, stream: none, after: T7)
- [ ] (T9) Add CSV/XLSX export of ROI slice profiles, including slice index, instance number, frame identifier, physical position, metric values, and ROI/group identifiers. (owner: coder, parallel-safe: no, stream: none, after: T7)

### Phase 4 - True 3D ROI support

- [ ] (S1) Spike 3D ROI representation options: stacked 2D contours, binary mask/segmentation volume, axis-aligned/oblique box, ellipsoid, and future DICOM SEG interoperability. (owner: coder, parallel-safe: yes, stream: A, after: T1)
- [ ] (T10) Implement named structure groups that can join propagated or manually drawn 2D ROIs across slices into one structure with name, color, description, source series, and editable per-slice contours. (owner: coder, parallel-safe: no, stream: none, after: Gate 2)
- [ ] (T11) Implement the approved first true 3D ROI type with volumetric statistics, volume units, cross-slice display, and explicit distinction from propagated 2D groups and named structures. (owner: coder, parallel-safe: no, stream: none, after: T10)
- [ ] (T12) Add cross-view/MPR behavior for 3D ROIs where geometry is valid: show intersections on 2D/MPR planes and update stats after edits. (owner: coder, parallel-safe: no, stream: none, after: T11)

### Phase 5 - Pixel-value-guided contouring and finer ROI controls

- [ ] (S2) Spike irregular ROI boundary algorithms based on pixel-value differences: threshold/range grow, edge-aware region grow, active-contour-like refinement, morphology cleanup, and optional smoothing. (owner: coder, parallel-safe: yes, stream: B, after: T1)
- [ ] (T13) Add semi-automatic contour creation from a seed point or seed ROI using pixel-value similarity/difference, with a preview overlay before accepting the contour. (owner: coder, parallel-safe: no, stream: none, after: Gate 3)
- [ ] (T14) Add sensitivity controls: automatic sensitivity from local histogram/edge contrast, plus manual numeric threshold/tolerance controls with units matching raw/rescaled viewer mode. (owner: ux/coder, parallel-safe: no, stream: none, after: T13)
- [ ] (T15) Add structure-generation preset framework: named presets with modality applicability, editable threshold/sensitivity defaults, cleanup steps, preview/accept, versioned parameter recording, and output as editable named structures. (owner: coder/ux, parallel-safe: no, stream: none, after: T13)
- [ ] (T16) Add first body-contour presets for CT and MRI, using modality-aware threshold/range defaults, largest-component filtering, hole filling, island removal, optional smoothing, and warnings when image geometry/modality metadata is insufficient. (owner: coder, parallel-safe: no, stream: none, after: T15)
- [ ] (T17) Add finer ROI editing controls: add/remove contour points, smooth/simplify boundary, split/merge contours, nudge/scale/rotate, duplicate to neighboring slice, interpolate between key slices, boolean union/intersection/subtract, lock visibility/editing, and named presets for contour display style. (owner: ux/coder, parallel-safe: no, stream: none, after: T10)
- [ ] (T18) Add mask operations for accepted contours/structures: fill holes, keep largest component, remove islands, dilate/erode, and convert between contour and mask representations where valid. (owner: coder, parallel-safe: no, stream: none, after: T13)
- [ ] (T19) Spike later detailed structure-generation presets after body contours are reliable: anatomy/site-specific presets, protocol-specific presets, and optional model-assisted segmentation only if licensing, validation, and runtime requirements are acceptable. (owner: planner/coder, parallel-safe: yes, stream: B, after: T16)

### Phase 6 - ROI/structure export and interchange

- [ ] (S3) Decide export targets for ROI/structures with explicit semantics and a staged priority:
  - DICOM targets: DICOM SEG for masks/segmentations, RT Structure Set where radiotherapy-style contour interchange is useful, GSPS for display-only 2D annotations, and SR/TID-style measurement reports for derived statistics.
  - First non-DICOM targets: app-native JSON for round trip, JSON sidecars for metadata, CSV/XLSX for statistics/profiles, and research labelmaps/masks in NIfTI and NRRD/.seg.nrrd.
  - Priority vector/surface targets: per-slice contour JSON/CSV for editable/interchangeable contours, plus STL, OBJ+MTL, and PLY for early mesh/surface export once a structure mask can be converted to a surface.
  - Later mask targets: MHA/MHD where SimpleITK-based interoperability is useful.
  - Later advanced mesh/presentation targets: glTF/GLB, VTK PolyData (.vtp/.vtk), and optional per-slice SVG after coordinate-space, smoothing, decimation, metadata, and external-tool validation are defined. (owner: coder, parallel-safe: yes, stream: C, after: T10)
- [ ] (T20) Implement the first non-DICOM export slice for app-native JSON plus NIfTI/NRRD labelmaps with JSON sidecars, preserving structure names, labels, colors, source geometry, coordinate system, voxel spacing/origin/direction, source image identifiers, and pixel-value-guided contour parameters. (owner: coder, parallel-safe: no, stream: none, after: S3)
- [ ] (T21) Add CSV/XLSX export for structure-level and per-slice ROI statistics/profiles from the same export model used by plotting and future CLI/reporting paths. (owner: coder, parallel-safe: no, stream: none, after: T20)
- [ ] (T22) Add priority per-slice contour export in JSON/CSV for vector interchange, preserving slice/frame identity, contour naming, structure labels, coordinate system, and editability. (owner: coder, parallel-safe: no, stream: none, after: T20)
- [ ] (T23) Add priority mesh export generated from structure masks using marching cubes or equivalent extraction, with options for smoothing, decimation, largest-component filtering, coordinate-space selection, and sidecar metadata; include STL, OBJ+MTL, and PLY first, while warning about each format's metadata limits. (owner: coder, parallel-safe: no, stream: none, after: T20)
- [ ] (T24) Add MHA/MHD mask export after the SimpleITK/image-format dependency path is validated and geometry round-trip tests are in place. (owner: coder, parallel-safe: no, stream: none, after: T20)
- [ ] (T25) Add advanced mesh/presentation exports such as glTF/GLB, VTK PolyData (.vtp/.vtk), and optional per-slice SVG after the priority mesh/vector formats are validated in external tools. (owner: coder, parallel-safe: no, stream: none, after: T23)
- [ ] (T26) Implement DICOM object export only after Gate 4: SEG for masks/segmentations, optional RTSTRUCT for contour sets, GSPS for display annotations, and SR/TID-style measurement reports for derived statistics when applicable. (owner: coder, parallel-safe: no, stream: none, after: Gate 4)

## Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Slice identity mistakes attach ROIs to the wrong frame/slice | Audit and test composite keys before propagation; include multi-frame cases. |
| Propagated 2D ROI is confused with true 3D ROI | Use distinct model names, UI labels, and export fields. |
| Plot x-axis is misleading when slice spacing is irregular | Show both stack index and physical position when available; warn when geometry is missing or non-monotonic. |
| ROI statistics become slow across large volumes | Cache per-slice masks/metrics and invalidate only changed ROI geometry or source slice data. |
| 3D ROI implementation conflicts with future DICOM SEG | Spike representation choices first and keep DICOM SEG/export scope explicit. |
| Pixel-value-guided contours appear authoritative when they are only semi-automatic | Show preview/accept step, record parameters, and label generated contours as user-approved derived structures. |
| Auto sensitivity overfits noisy images or PET uptake variation | Provide manual numeric controls and show the selected value range/tolerance before accepting. |
| Body contour presets fail on unusual CT/MRI acquisitions | Require preview/accept, expose threshold/cleanup controls, warn on missing geometry or modality metadata, and keep generated contours editable. |
| Later detailed presets imply clinical-grade autosegmentation | Gate them behind validation notes, licensing review, and clear labeling as assistive structure generation. |
| DICOM export target is semantically wrong | Gate export semantics: SEG for masks, RTSTRUCT for contour structures, GSPS for display annotations, SR for derived measurements. |
| Non-DICOM export loses geometry or semantics | Treat labelmaps plus JSON sidecars as the first-class interchange path and test spacing/origin/direction, structure labels, colors, source image identifiers, and algorithm parameters. |
| Mesh export is mistaken for a lossless structure representation | Label mesh export as a derived surface, keep mask/labelmap export available, and record extraction parameters such as threshold, smoothing, decimation, and coordinate space. |
| Mesh formats have uneven metadata support | Use sidecars where needed; avoid depending on STL for colors, units, labels, or source geometry metadata. |
| Coordinate-space ambiguity makes exports misalign in external tools | Require explicit image-index, patient/world, or viewer-space export choices where applicable and include the selected coordinate system in metadata. |
| UI becomes crowded | Add commands to ROI context menu and ROI panel; keep plot in a dedicated dialog/tab. |

## Modularity and file-size guardrails

- Keep ROI model/data helpers separate from Qt graphics items.
- Avoid adding large plotting logic to `roi_manager.py`; use a dedicated profile/statistics module where practical.
- Keep 3D ROI representation separate from propagated 2D ROI groups.
- Keep pixel-value-guided contour algorithms in a testable, GUI-independent module.
- Keep structure-generation presets as data/config plus testable algorithms, not hard-coded dialog behavior.
- Keep DICOM export writers separate from ROI editing/graphics code.
- Keep export serialization reusable by GUI and future CLI/reporting paths.
- Keep mesh generation as a derived-export module, separate from ROI storage and mask/labelmap serialization.

## Testing strategy

- Unit tests:
  - propagation creates expected ROI instances for a slice range,
  - undo/redo removes/restores all propagated instances,
  - propagation respects series/study/frame identity,
  - profile statistics match known arrays across slices,
  - irregular slice positions produce correct x-axis metadata,
  - joining 2D contours creates a named structure with expected slice membership,
  - pixel-value-guided contouring produces deterministic masks on synthetic arrays for fixed sensitivity values,
  - auto sensitivity records the computed numeric parameters,
  - CT and MRI body-contour presets produce expected masks on synthetic volumes and record preset name/version/parameters,
  - contour cleanup operations produce expected masks,
  - ROI/structure export serializers preserve names, colors, source geometry, and algorithm parameters,
  - NIfTI/NRRD labelmap export preserves expected geometry and label values on synthetic volumes,
  - JSON sidecars include structure names, labels, colors, coordinate system, source identifiers, and export parameters,
  - MHA/MHD export round trips geometry once that format is enabled,
  - mesh export produces deterministic vertices/faces for a fixed synthetic mask and records extraction parameters,
  - per-slice contour JSON/CSV export preserves slice/frame identity and contour naming,
  - existing single-slice ROI persistence remains backward compatible.
- Integration/UI tests where feasible:
  - draw ROI, propagate across slices, scroll through slices, verify visibility and selection,
  - edit one propagated ROI instance and verify group metadata remains intact,
  - open profile plot and export CSV/XLSX.
  - create an irregular contour from a seed/ROI, adjust sensitivity, accept it, and verify it appears in the ROI list.
- 3D ROI tests after representation decision:
  - volume/statistics on synthetic 3D data,
  - 2D/MPR intersection display metadata,
  - persistence/export round trip,
  - DICOM SEG/RTSTRUCT writer tests once the export target is approved.
  - non-DICOM labelmap and mesh exports load in at least one independent tool/library during manual validation.

## Questions for user

- For first 2D propagation, should copied ROIs remain identical on each slice, or should there be interpolation/contour adjustment between edited key slices?
- For PET-style plotting, which default metrics matter most: mean, max, SUV-like normalized value, sum, area/count, or all available ROI statistics?
- For first 3D ROI, should the priority be a simple box/ellipsoid volume ROI, stacked 2D contours, or segmentation-mask style ROI?
- For DICOM export, is DICOM SEG enough for first structure interchange, or is RTSTRUCT needed early for compatibility with treatment-planning tools?
- For pixel-value-guided boundaries, should the first workflow be seed-based region growing, threshold/range from an existing ROI, or contour refinement around a manually drawn ROI?

## Completion notes

Not started. This is a docs-only supporting plan as of 2026-06-11.

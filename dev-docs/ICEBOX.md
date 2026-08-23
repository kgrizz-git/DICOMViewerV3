# Icebox

**Last updated:** 2026-08-23

Parked work, split out of [`TO_DO.md`](TO_DO.md) on 2026-08-23. Everything here
is **self-labelled** in its own text as P3, Optional, Deferred, or a spike — it
was already saying "not now". Nothing is dropped and nothing is decided against;
items are unchanged.

**Promote back to `TO_DO.md`** the moment one becomes real work — a user asks, a
measurement justifies it, or it starts blocking something in play. This file
exists so the active backlog reflects what is actually in play, not so ideas
disappear.

## From: Bugs / Correctness

- [ ] **[P3]** **Revisit enhanced-CT multi-frame merge bookkeeping only if it becomes visibly slow again.** The P1 post-Continue stall was fixed by making `FrameDatasetWrapper` a metadata view rather than deep-copying every non-pixel element per frame: 26.4 s -> 1.16 s full merge for the 364-frame / 182 MB enhanced CT benchmark. The remaining `series_multiframe_info` rebuild measured 575.7 ms, but first display after UI handoff was 178.1 ms and navigator work was small. Do not add deferred thumbnail/navigator scheduling complexity without a new measurement or user report — **Archived plan:** [Slow post-load first paint](plans/completed/POST_LOAD_FIRST_PAINT_PERFORMANCE_PLAN.md)

## From: DICOM write / PACS interchange (annotations & derived objects)

- [ ] **[P3]** **Export Key Object Selection (KO) document (optional):** let user save a **curated set** of key instances (e.g. current series/slices with annotations) as a KO SOP with **CurrentRequestedProcedureEvidenceSequence** / **ContentSequence** references — useful for “key images” workflows in PACS, **not** full geometry interchange (prefer GSPS for that). **Partial (read only today):** KO loads on open via `key_object_handler.py`; **writer** not implemented. Lower priority unless product asks for KO specifically — see [KO section](info/DICOM_GSPS_KO_SECONDARY_CAPTURE.md#key-object-selection-ko-document).

## From: Documentation

- [ ] **[P3]** **README end-user polish — hero screenshot(s).** Root [`README.md`](../README.md) was rewritten for end users (short intro, packaged-release-first, capability table, linked-out developer material). Remaining human-owned step: capture and PHI-review one primary hero screenshot (optional second) using wholly synthetic studies from approved demo fixtures only; after visual PHI review, record the approved asset hash in `security/approved-media-sha256.json` and insert into the README placeholder slot. **Plan:** [README end-user polish](plans/README_END_USER_POLISH_PLAN.md). Surfaced 2026-08-20.

## From: Features (Near-Term)

    - [ ] **[P3]** **Mesh export (OBJ / STL / PLY) from the 3D viewer:** let the user export the displayed anatomy as a 3D mesh for printing, external tooling, or teaching. **Depends on isosurface extraction** (next item): volume rendering has no polygonal geometry, so a surface must first be extracted (`vtkFlyingEdges3D` / `vtkMarchingCubes`) at a threshold before `vtkOBJWriter` / `vtkSTLWriter` / `vtkPLYWriter` can write anything — `vtkOBJExporter` on the current scene would export an empty file. Scope to consider: threshold/preset-derived surface, optional decimation + smoothing, units (mm) and LPS→mesh axis convention, and whether to offer it beyond the 3D viewer (e.g. from a segmentation/ROI). **Two caveats to resolve in the plan:** (1) an extracted surface is *visualization-derived, not a validated segmentation* — the threshold drives the geometry, so the UI must not imply clinical/dimensional fidelity; (2) **PHI risk** — a mesh from a head/face CT is re-identifiable surface geometry and carries no DICOM de-identification, so exports need an explicit warning and should follow [PHI/PII guardrails](PHI_PII_REPOSITORY_GUARDRAILS.md).

    - [ ] **[P3]** **Isosurface rendering mode:** spike `vtkFlyingEdges3D` at a threshold value as a separate rendering-mode plan; visualization-only, with memory/performance and mesh cleanup evaluated before implementation. **Plan:** [3D Viewer Visual and UX Improvements](plans/supporting/3D_VIEWER_VISUAL_AND_UX_IMPROVEMENTS_PLAN.md) S3

    - [ ] **[P3]** **MPR slice plane indicator in 3D:** spike showing the current 2D viewing plane as a translucent rectangle in the 3D viewport; requires signal forwarding from main window and should become a separate integration plan if feasible. **Plan:** [3D Viewer Visual and UX Improvements](plans/supporting/3D_VIEWER_VISUAL_AND_UX_IMPROVEMENTS_PLAN.md) S4

    - [ ] **[P3]** **Dual-volume PET/CT 3D overlay:** spike dual-volume rendering separately; high complexity because it needs registration/resampling, scalar-domain/unit handling, overlay opacity, and fusion-plan alignment, not just a second `vtkVolume`. **Plan:** [3D Viewer Visual and UX Improvements](plans/supporting/3D_VIEWER_VISUAL_AND_UX_IMPROVEMENTS_PLAN.md) S4

## From: Maintenance

- [ ] **[P3] Deferred:** **Trial agent navigation / output-efficiency tools without adopting a stack.** Start with a user-level Serena semantic-navigation trial and, separately, an RTK CLI-output trial; use the non-gating protocol in [`HARNESS.md`](HARNESS.md#agent-tool-trial-protocol). Compare against a no-tool baseline on representative Python/PySide6 tasks and record task completion, focused-test results, elapsed time, and lost diagnostics/source detail. Do not install tools into the application `.venv`, commit shared MCP/hook configuration, or add a project dependency unless a trial demonstrates a durable benefit and its source, license, data handling, and maintenance cost have been reviewed. Consider Graphify/other graph tools only if Serena does not adequately support a demonstrated navigation need.

## From: Performance / Packaging

- [ ] **[P3]** **Explore [awesome-medphys](https://github.com/jrkerns/awesome-medphys) for useful open-source tools.** Curated medical-physics tooling list; candidates to evaluate include **deidentifier** utilities and other DICOM/QA helpers that might complement or inform our PS3.15 de-identification engine, pylinac QA workflows, or import/export paths. Spike only: survey, note which tools are Python/license-compatible, and decide whether any are worth integrating vs. our existing implementations.

## From: UX / Workflow

- [ ] **[P3]** **More visual-orientation variety in UI chrome:** consider broader use of font color, size, weight, and icon/border color/styling to help users orient visually (e.g. distinct section/group emphasis, status-weighted emphasis). First concrete remaining case: Phase C of the tag-tree workstream; whole-app proposals and deferrals in the investigation. Broader design-system pass remains under UX remediation / `DESIGN.md`. Surfaced 2026-08-11. **Hub:** [Tag tree visual hierarchy](plans/supporting/TAG_TREE_VISUAL_HIERARCHY_PLAN.md). **Investigation:** [tag-tree visual hierarchy investigation](ux-assessments/tag-tree-visual-hierarchy-investigation-2026-08-16.md). **Related plans:** [Phase C tier/nav](plans/supporting/TAG_TREE_TIER_ORIENTATION_AND_NAV_PLAN.md), [Phase D follow-ups](plans/supporting/TAG_TREE_VISUAL_FOLLOWUPS_PLAN.md), [Pane & toolbar state](plans/supporting/PANE_AND_TOOLBAR_STATE_VISUAL_PLAN.md).

- [ ] **[P3]** **Study index — optional encryption toggle — DEFERRED (decided 2026-07-21).** A user-facing setting to migrate the PHI index to **plaintext** was judged closer to a footgun than a feature: it downgrades at-rest protection for patient names/IDs/descriptions/paths with little practical upside, and needs a non-trivial migration + irreversible-warning surface. Index stays **always SQLCipher-encrypted**. Revisit only if a concrete need appears (e.g. a platform without an OS keyring); the explicit **turn-OFF at-rest-exposure warning** wording is already drafted in the plan (Phase 1b). **Plan:** [Study index portability & encryption UI — Phase 1 (deferred)](plans/supporting/STUDY_INDEX_PORTABILITY_AND_ENCRYPTION_UI_PLAN.md)

## From: Validation / QA

- [ ] **[P3]** **Evaluate independent local PHI reviewers before choosing an optional integration.** Compare the clinical-note model `obi/deid_roberta_i2b2`, a GLiNER size variant, and—only as a schema-constrained second-pass reviewer—OpenAI `gpt-oss-20b` through LM Studio. Decide whether custom Presidio `EntityRecognizer` adapters for GLiNER, GLiNER2, and/or OpenAI Privacy Filter are justified; do not treat Presidio or an LLM as a replacement for the DICOM metadata gate or OCR/image review. See [model scope and integration details](info/LOCAL_PHI_PII_DETECTION_MODEL_OPTIONS.md).

## From: Deferred (section retired)

Archived-implementation-plan leftovers; the `Deferred` section in `TO_DO.md`
existed only for these and has been removed.

- [ ] **[P2]** **Tag-export richer formatting:** Phase B appearance gate decided **(c) none** on 2026-08-17; retain the implemented checkbox indicator glyphs and reopen header/stripe/tier chrome only after a new visual review. [Completed Phase B plan](plans/completed/TAG_TREE_GROUP_HEADER_AND_STRIPING_PLAN.md); [Phase D `D-export-visual`](plans/supporting/TAG_TREE_VISUAL_FOLLOWUPS_PLAN.md).
- [ ] **[P2]** **macOS PyInstaller bundle follow-ups:** record tagged-build baselines; narrow Qt plugins only with `du` evidence and feature tests; reconsider artifact retention only if billing/measurement evidence warrants it. [Completed bundle-size plan](plans/completed/pyinstaller-bundle-size-macos-2026-04-09.md).
- [ ] **[P2]** **Pylinac CT CNR batch per-series PDF:** evaluate per-series PDF output separately from the shipped batch XLSX workflow. [Completed CT CNR batch plan](plans/completed/PYLINAC_CT_CNR_BATCH_XLSX_PLAN.md).

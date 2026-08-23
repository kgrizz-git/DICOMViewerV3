# Competitive feature backlog (vs other DICOM viewers)

**Last updated:** 2026-08-23

Split out of [`TO_DO.md`](TO_DO.md) on 2026-08-23. This is product-strategy
scope on a different cadence from the active engineering backlog: it answers
"where are we against RadiAnt / Horos / OHIF", not "what am I doing this week".
Keeping it separate means `TO_DO.md` shows work that is actually in play.

**Nothing was dropped in the move.** Items are unchanged; pull one back into
`TO_DO.md` when it becomes real near-term work.


**Hub:** [DICOM_VIEWER_COMPETITIVE_FEATURE_GAP_ANALYSIS.md](info/DICOM_VIEWER_COMPETITIVE_FEATURE_GAP_ANALYSIS.md) (2026-06-02). **Recommended order:** Tier A → B → C; Tier D–E mostly **Optional** / **Deferred**. Items marked **Dup** are also tracked above (Features, Data/Platform, DICOM write, etc.) — keep one checkbox authoritative when implementing.

### Tier A — Workflow & interoperability (P1)

- [ ] **[P1]** **PACS read-only query/retrieve:** C-FIND/C-MOVE (or WADO-RS) with saved server profiles, progress UI, and audit log; offline mode unchanged when no server configured — **Gap:** §1. **Dup:** [Data / Platform](TO_DO.md#data--platform-future) (PACS-like).
- [ ] **[P1]** **Hanging protocols v1:** JSON protocols, resolver, Apply dialog, optional auto-apply on open — **Gap:** §2. **Dup:** Features (hanging protocols).
- [ ] **[P1]** **Prior comparison:** find prior studies via study index (Patient ID / accession), load into dedicated slots or side-by-side layout — **Gap:** §2. **Dup:** Features (pulling priors).
- [ ] **[P1]** **GSPS export** for in-viewer graphic annotations — **Gap:** §5. **Dup:** [DICOM write](TO_DO.md#dicom-write--pacs-interchange-annotations--derived-objects) (consider **P1** when scheduling Tier A).
- [ ] **[P1]** **Synchronized crosshair 2D ↔ MPR** (same patient position / slice location across native and MPR panes) — **Gap:** §3.
- [ ] **[P1]** **MPR measurements + slab projections:** enable ROI/measurement/W/L ROI on MPR; MIP/MinIP/AIP slab per MPR step — **Gap:** §4. **Plan:** [MPR measurements & combine slices](plans/MPR_MEASUREMENTS_ROI_TOOLS_AND_COMBINE_SLICES_PLAN.md).

### Tier B — MPR / 3D / derived DICOM (P1–P2)

- [ ] **[P1]** **2D↔MPR↔3D navigation polish:** extend sync to 3D plane indicator and shared focus behavior where feasible — **Gap:** §3. **Dup:** 3D spikes (MPR plane in 3D).
- [ ] **[P2]** **Interactive oblique MPR** (drag handles / crosshairs) — **Gap:** §3. **Dup:** Features.
- [ ] **[P1]** **Export AIP/MIP/MinIP stacks** (DICOM + images) — **Gap:** §5. **Dup:** Features (projection export). **Plan:** [Projection export](plans/supporting/PROJECTION_EXPORT_PLAN.md).
- [ ] **[P2]** **Save fused view as DICOM (SC)** — **Gap:** §5. **Dup:** Fusion follow-up.
- [ ] **[P1]** **Export 3D volume render as image (PNG/JPG)** — **Gap:** §5. **Dup:** 3D visualization sub-items.
- [ ] **[P1]** **Export 3D volume render as Secondary Capture DICOM** — **Gap:** §5. **Dup:** 3D visualization sub-items.
- [ ] **[P2]** **PACS send (C-STORE SCU):** send derived or source series to configured node after Q/R exists — **Gap:** §1.
- [ ] **[P2]** **DICOMweb client** (QIDO/WADO/STOW) as alternative to DIMSE for sites that require it — **Gap:** §1.

### Tier C — Measurements & modality niches (P2–P3)

- [ ] **[P2]** **Cobb angle** measurement tool — **Gap:** §6.
- [ ] **[P1]** **Line profile measurement and analysis** — interactive profiles across images plus CT film beam-width FWHM/FWTM workflow. **Plan:** [Line profile and CT film beam-width analysis](plans/supporting/LINE_PROFILE_AND_CT_FILM_BEAM_WIDTH_PLAN.md).
- [ ] **[P2]** **Manual length calibration** when pixel spacing is missing (measure known structure, set scale) — **Gap:** §6.
- [ ] **[P2]** **3D cursor / linked localization** across panes (RadiAnt/MicroDicom-style) — **Gap:** §3, §6.
- [ ] **[P3]** **Optional:** deviation distance measurement — **Gap:** §6.
- [ ] **[P3]** **Optional:** US calibrated-region measurements — **Gap:** §6.
- [ ] **[P3]** **Optional:** open/closed curve measurements — **Gap:** §6.
- [ ] **[P3]** **Optional:** spine labeling tool — **Gap:** §6.
- [ ] **[P2]** **Print / PDF** from 2D, MPR, and 3D views (RadiAnt 2024.2+ class) — **Gap:** §11.

### Tier D — Platform & optional polish (P2–P3, often Optional)

- [ ] **[P2]** **PACS inbound C-STORE** listener (optional, site-specific) — **Gap:** §1. **Optional.**
- [ ] **[P2]** **Import encrypted ZIP** archives containing DICOM — **Gap:** §1. **Optional.**
- [ ] **[P3]** **URL / CLI deep link** for third-party launch (`dicomviewerv3://` or documented args) — **Gap:** §11. **Optional.**
- [ ] **[P3]** **3D VR scalpel / crop** tool (volume cutaway) — **Gap:** §11. **Optional.**
- [ ] **[P3]** **JPEG2000** transfer syntax support — **Gap:** §9. **Optional.**
- [ ] **[P3]** **Modular / optional-feature install profiles:** consider splitting the app into a lightweight core install with basic DICOM viewing and optional feature packs that can be selected at install time or added later on demand, such as pylinac/QA analysis, NIfTI/NRRD/MHA support, advanced 3D/VTK, DICOM networking, and structure/mesh export dependencies. **Plan:** [Modular optional-feature packaging](plans/supporting/MODULAR_OPTIONAL_FEATURE_PACKAGING_PLAN.md).

### Tier E — Optional / deferred (different product class)

- [ ] **[P3]** **Deferred:** DICOM **SEG** read + overlay — **Gap:** §9–10.
- [ ] **[P3]** **Deferred:** **RT** (structure set / dose / plan) browse-only — **Gap:** §9–10.
- [ ] **[P3]** **Deferred:** manual/semi-auto **3D segmentation** and contour editing — **Gap:** §10. **Dup:** Features (advanced ROI/contouring).
- [ ] **[P3]** **Deferred:** **deformable registration** beyond same–frame-of-reference fusion — **Gap:** §10.
- [ ] **[P3]** **Deferred:** **plugin / extension** architecture — **Gap:** §10.
- [ ] **[P3]** **Deferred:** **web / zero-footprint** viewer — **Gap:** §11.
- [ ] **[P3]** **Deferred:** **mobile (iOS)** companion app — **Gap:** §11.
- [ ] **[P3]** **Optional:** **time–intensity curves (TIC)** e.g. breast MRI — **Gap:** §7.
- [ ] **[P3]** **Optional:** **DSA** (digital subtraction angiography) mode — **Gap:** §7.
- [ ] **[P3]** **Optional:** **curved MPR** — **Gap:** §3.
- [ ] **[P3]** **Optional:** **CD/DVD DICOM** export / authoring — **Gap:** §11.
- [ ] **[P3]** **Deferred:** general **DICOM tag editor** — **Gap:** §5. **Dup:** Features (risk-aware general tag editor).
- [ ] **[P3]** **Optional:** **multilingual** UI — **Gap:** §11.
- [ ] **[P3]** **Optional:** **multi-touch** gestures (Windows tablets) — **Gap:** §11.
- [ ] **[P3]** **Deferred:** **dual-volume PET/CT 3D** overlay — **Gap:** §3. **Dup:** 3D visualization (dual-volume spike).
- [ ] **[P3]** **Deferred:** **AI-assisted** segmentation integration — **Gap:** §10.
- [ ] **[P3]** **Optional:** export **KO** (key object) documents — **Gap:** §5. **Dup:** DICOM write (KO).

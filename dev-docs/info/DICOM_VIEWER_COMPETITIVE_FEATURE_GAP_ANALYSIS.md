# DICOM Viewer V3 — Competitive feature gap analysis

**Created:** 2026-06-02  
**Purpose:** Compare this desktop viewer to common alternatives, record gaps, recommend priority tiers, and link to [`dev-docs/TO_DO.md`](../TO_DO.md) checkboxes.  
**Audience:** Product planning, implementers, and agents picking next work.

**Related:** [`ARCHITECTURE.md`](../../ARCHITECTURE.md) · [`TO_DO.md`](../TO_DO.md) · [`FUTURE_WORK_DETAIL_NOTES.md`](../FUTURE_WORK_DETAIL_NOTES.md)

---

## Executive summary

DICOM Viewer V3 is **strong** for a Python/PySide6 desktop tool in **PET/CT fusion**, **3D volume rendering (VTK)**, **local study index + FTS search**, **pylinac QA**, and **structured-report browsing (partial)**. Compared with **RadiAnt**, **Horos/OsiriX**, **MicroDicom**, and **Weasis**, the largest **general-viewer** gaps are:

1. **PACS / DICOM networking** (query/retrieve, send, DICOMweb)  
2. **Hanging protocols and prior comparison** (auto layout + current/prior)  
3. **Linked navigation** across 2D, MPR, and 3D (one crosshair / axis intersection)  
4. **MPR as a full measurement viewport** (tools + slab projections on reconstructed planes)  
5. **DICOM write-back** (GSPS annotations, Secondary Capture for fusion/MPR/3D, projection stacks)

Compared with **OHIF** and **3D Slicer**, gaps in **web delivery**, **DICOM SEG**, **RT**, **deformable registration**, and **AI segmentation** are expected unless the product scope expands into research-PACS or segmentation platforms.

**Recommended near-term focus (Tier A → B):** hanging protocols v1, priors via study index, PACS read-only Q/R, GSPS export, synchronized 2D↔MPR crosshair, MPR measurements + slab modes, then projection/fusion/3D SC export.

---

## Reference viewers (sources)

| Viewer | Typical use | Notes consulted |
|--------|-------------|-----------------|
| [RadiAnt](https://www.radiantviewer.com/) | Fast Windows desktop review | PACS, MPR/3D VR, fusion, TIC, DSA, measurements, 2025.2 sync across 2D/MPR/3D |
| [Horos](https://horosproject.org/) | Free macOS research/clinical-adjacent | Local DB, DICOM nodes, 3D MPR/VR, plugins, KO/SR optional |
| [OsiriX / OsiriX MD](https://www.osirix-viewer.com/) | macOS clinical (MD regulated) | 4D, PET-CT, advanced 3D; Lite limitations vs Horos |
| [MicroDicom](https://www.microdicom.com/) | Lightweight Windows | Cobb angle, curves, MPR oblique, image filters |
| [Weasis](https://weasis.org/) | Cross-platform + PACS hooks | Modular, MPEG-2/ECG/RT browse, MPR (no VR in older summaries) |
| [OHIF](https://ohif.org/) | Web PACS workstation | Hanging protocols, SEG, DICOMweb, priors in HP rules |
| [3D Slicer](https://slicer.org/) | Research segmentation/registration | SEG, RT, DICOMweb, plugins — different product class |
| [MedDream](https://meddream.com/) | Web zero-footprint | Hanging protocols, PACS URL integration |

This document is **not** a feature parity matrix for regulatory clearance (e.g. FDA-cleared OsiriX MD vs research builds).

---

## Where V3 already competes well

| Capability | V3 status | Peer comparison |
|------------|-----------|-----------------|
| Multi-pane layouts, W/L, cine, navigator | Shipped | On par with RadiAnt / MicroDicom / Horos |
| 2D fusion (PET/CT etc.) | Shipped, quantitatively verified | Ahead of many lightweight viewers |
| 3D volume rendering | Shipped (VTK, presets, MIP/MinIP in 3D) | RadiAnt / Horos / OsiriX class |
| 2D AIP/MIP/MinIP slabs | Display shipped; export open | RadiAnt-class display |
| Local study index + FTS | Shipped (SQLCipher) | Similar intent to Horos local DB |
| pylinac ACR CT/MRI QA | Shipped | **Differentiator** — rare in general viewers |
| SR / RDSR dose browser | Partial | Ahead of “tags only”; behind full OHIF SR |
| Distance + angle + ROI + annotations | Shipped | Core set present; see measurement gaps |
| GSPS / KO read on load | Shipped | Write-back not shipped |

---

## Gap catalog by theme

### 1. PACS and DICOM networking

**Peers:** RadiAnt (C-FIND/C-MOVE, push, import/send), Horos (unlimited DICOM nodes, web server), Weasis/OHIF/MedDream (PACS + DICOMweb).

**V3 today:** Folder/file open, drag-and-drop, local study index; **no** DIMSE or DICOMweb client.

**Gaps:**

| Item | Priority tier | TO_DO |
|------|---------------|-------|
| Read-only PACS query/retrieve (C-FIND/C-MOVE or WADO-RS) + server profiles | **A** | Tier A § PACS |
| Accept inbound C-STORE (optional listener) | **D** Optional | Tier D |
| Send studies/series to PACS (C-STORE SCU) | **B** | Tier A/B |
| DICOMweb (QIDO-RS / WADO-RS / STOW-RS) as alternative to DIMSE | **B** | Tier A |
| Audit log for network retrieve/send | **A** (with PACS) | Tier A |
| Encrypted ZIP import (RadiAnt) | **D** Optional | Tier D |

**Design notes:** Keep network stack **optional** and **decoupled** from offline UI ([`FUTURE_WORK_DETAIL_NOTES.md`](../FUTURE_WORK_DETAIL_NOTES.md#pacs-like-query-and-archive-integration)). Prefer **pydicom** + **pynetdicom** or a small DICOMweb client; evaluate **fo-dicom** only if a .NET sidecar is acceptable.

---

### 2. Hanging protocols and prior comparison

**Peers:** OHIF `HangingProtocolService`, MedDream/Stradus HP toolbar, enterprise PACS.

**V3 today:** Manual layout and series assignment; plans exist ([`HANGING_PROTOCOLS_PRIORS_RDSR_PLAN.md`](../plans/supporting/HANGING_PROTOCOLS_PRIORS_RDSR_PLAN.md)).

**Gaps:**

| Item | Priority tier | TO_DO |
|------|---------------|-------|
| JSON hanging protocols (layout + series match rules) + Apply dialog | **A** | Existing + Tier A |
| Auto-apply on study open (user setting) | **B** | Tier A |
| Prior study resolution via study index (Patient ID / accession) | **A** | Existing + Tier A |
| Side-by-side current vs prior in one layout | **A** | Tier A |
| Import/export HP definitions; DICOM Hanging Protocol IOD | **D** Deferred | Tier E |

**v1 recommendation:** Manual apply + modality/body-part/description glob matching; prior slot calls study index search — no DICOM HP IOD in v1.

---

### 3. Linked navigation (2D / MPR / 3D)

**Peers:** RadiAnt 2025.2 — synchronized axis intersection across 2D, 3D MPR, and 3D VR; MicroDicom 3D cursor; Horos cross-reference lines.

**V3 today:** Crosshair and slice sync on 2D panes; MPR often separate; 3D independent ([`USER_GUIDE_3D.md`](../../user-docs/USER_GUIDE_3D.md) — no fusion in 3D).

**Gaps:**

| Item | Priority tier | TO_DO |
|------|---------------|-------|
| Synchronized crosshair: 2D ↔ MPR (same patient position) | **A** | Tier B |
| MPR slice plane indicator in 3D viewport | **B** | Existing 3D spike |
| Dual-volume PET/CT in 3D | **E** Deferred | Existing 3D spike |
| Fusion overlay in MPR | **B** | Existing Features |
| Interactive oblique MPR (drag plane) | **B** | Existing Features |
| Curved MPR | **E** Deferred | Tier E |

---

### 4. MPR parity (tools + slabs + export)

**Peers:** RadiAnt/MicroDicom/Horos — MPR with measurements; oblique reconstruction.

**V3 today:** Orthogonal MPR, detached window; **tools disabled** on MPR in places; slab projection on **2D** not full MPR pipeline.

**Gaps:**

| Item | Priority tier | TO_DO |
|------|---------------|-------|
| ROI + distance + angle + W/L ROI on MPR pixels | **A** | Tier B + plan |
| MPR slab MIP/MinIP/AIP per navigator step | **A** | Tier B + plan |
| Export MPR stack as DICOM SC | **B** | MPR export exists; extend |
| Multiple MPR panes / assign target window | **B** | Existing UX |

**Plan:** [`MPR_MEASUREMENTS_ROI_TOOLS_AND_COMBINE_SLICES_PLAN.md`](../plans/MPR_MEASUREMENTS_ROI_TOOLS_AND_COMBINE_SLICES_PLAN.md)

---

### 5. DICOM write-back (annotations & derived pixels)

**Peers:** Horos GSPS/KO write; PACS workstations SC for key images; OHIF SEG (separate).

**V3 today:** GSPS/KO **read**; fusion **display-only**; MPR SC export path exists for MPR; 3D SC export open.

**Gaps:**

| Item | Priority tier | TO_DO |
|------|---------------|-------|
| Export GSPS (graphic annotations) | **A** | DICOM write § |
| Save fused view as multi-slice SC | **B** | Fusion follow-up |
| Export AIP/MIP/MinIP stacks (DICOM + images) | **B** | Projection export plan |
| 3D render → PNG/JPG + SC DICOM | **B** | 3D sub-items |
| Export KO document | **E** Optional | DICOM write § |
| DICOM tag editing (Horos) | **E** Deferred | Tier E |

**Reference:** [`DICOM_GSPS_KO_SECONDARY_CAPTURE.md`](DICOM_GSPS_KO_SECONDARY_CAPTURE.md)

---

### 6. Measurement and annotation toolkit

**Peers:** RadiAnt — Cobb, deviation, US calibrated regions; MicroDicom — curves, spine label, 3D cursor.

**V3 today:** Distance, angle, ellipse/rectangle ROI, text, arrows; ROI stats + export.

**Gaps:**

| Item | Priority tier | TO_DO |
|------|---------------|-------|
| Cobb angle | **C** | Tier C |
| Deviation distance | **C** Optional | Tier C |
| Manual pixel-size calibration (when tags missing) | **C** | Tier C |
| US calibrated region measurements | **C** Optional | Tier C |
| Open / closed curve measurements | **C** Optional | Tier C |
| Spine labeling tool | **E** Optional | Tier E |
| 3D cursor (linked 3-plane localization) | **B** | Tier B/C |

---

### 7. Dynamic / functional imaging

**Peers:** RadiAnt TIC (breast MRI), DSA (pixel shift, masks); OsiriX 4D emphasis.

**V3 today:** Multi-frame navigation partial (Tier 1–2); Tier 3 enhanced IOD open.

**Gaps:**

| Item | Priority tier | TO_DO |
|------|---------------|-------|
| Enhanced multi-frame IOD (per-frame functional groups) | **B** | Data/Platform |
| Dual-axis scroll (slice × time / b-value) | **B** | Data/Platform |
| Time–intensity curves (TIC) | **E** Optional | Tier E |
| DSA / digital subtraction mode | **E** Optional | Tier E |
| Synchronized multi-pane cine | **C** | Existing Features |

---

### 8. Image processing and derived series

**Peers:** MicroDicom filters; RadiAnt arithmetic/subtraction; research tools.

**V3 today:** Window/level, fusion blend; pixel arithmetic and convolution pipelines **planned**.

**Gaps:**

| Item | Priority tier | TO_DO |
|------|---------------|-------|
| Pixel-wise series arithmetic (+/−/×/÷) | **B** | Existing plan |
| Convolution kernels (smooth, edge, sharpen) | **B** | Existing Features |
| Non-linear LUTs beyond linear W/L | **B** | LUT plan |
| Deep anonymizer (scanner/institution tags) | **A** | Existing P1 |

---

### 9. Structured report and advanced DICOM objects

**Peers:** Weasis — MPEG-2, ECG, RT; OHIF — SEG overlay; Horos — JPEG2000.

**V3 today:** SR browser partial; highdicom deferred.

**Gaps:**

| Item | Priority tier | TO_DO |
|------|---------------|-------|
| SR full fidelity (lazy tree, TID plugins, SCOORD/WAVEFORM) | **A** | UX P0 partial |
| highdicom backend | **B** | Features |
| DICOM SEG read + overlay | **E** Deferred | Tier E |
| RTSTRUCT / RT dose browse-only | **E** Deferred | Tier E |
| ECG waveform presentation in SR | **C** Optional | Tier C |
| JPEG2000 transfer syntax | **D** Optional | Tier D |

---

### 10. Segmentation, registration, plugins (different product class)

**Peers:** 3D Slicer Segment Editor; OHIF segmentation extension; Horos plugins.

**Gaps (defer unless scope changes):**

| Item | Tier | Tag |
|------|------|-----|
| Manual/semi-auto 3D segmentation | E | Deferred |
| AI-assisted segmentation (MONAI etc.) | E | Deferred |
| Deformable registration beyond FoR fusion | E | Deferred |
| Plugin / extension API | E | Deferred |
| Advanced contouring / auto-ROI | E | Deferred |

**V3 note:** [`FUTURE_WORK_DETAIL_NOTES.md`](../FUTURE_WORK_DETAIL_NOTES.md#advanced-roi-and-contouring) — keep distinct from clinical 2D ROI tools.

---

### 11. Platform, distribution, and polish

| Item | Priority tier | TO_DO |
|------|---------------|-------|
| Print / PDF from 2D, MPR, 3D | **C** | Tier D |
| CD/DVD DICOM export | **E** Optional | Tier E |
| File association + Open With | **B** | Existing P1 |
| Metadata-only fast browser mode | **B** | Existing P1 |
| Multilingual UI | **E** Optional | Tier E |
| Multi-touch (Windows) | **E** Optional | Tier E |
| URL / CLI deep link (`dicomviewerv3://` or args) | **D** Optional | Tier D |
| Web / zero-footprint viewer | **E** Deferred | Tier E |
| Mobile (iOS) companion | **E** Deferred | Tier E |
| 3D VR scalpel / crop (RadiAnt) | **D** Optional | Tier D |

---

## Recommended priority tiers (implementation order)

### Tier A — Workflow & interoperability (do first)

Highest impact for users coming from RadiAnt/Horos/PACS habits.

1. Hanging protocols v1 (JSON + manual apply)  
2. Prior load/compare via study index  
3. PACS read-only Q/R (+ server profile UI)  
4. GSPS export for annotations  
5. Synchronized 2D ↔ MPR crosshair  
6. Deep anonymizer export  
7. SR browser gaps that block daily SR review (per existing P0 plan)

### Tier B — MPR / 3D / derived DICOM parity

1. MPR measurements + slab MIP/MinIP/AIP ([`MPR_MEASUREMENTS_ROI_TOOLS_AND_COMBINE_SLICES_PLAN.md`](../plans/MPR_MEASUREMENTS_ROI_TOOLS_AND_COMBINE_SLICES_PLAN.md))  
2. Projection stack export (AIP/MIP/MinIP)  
3. Fused view SC export  
4. 3D PNG + SC export  
5. Fusion on MPR  
6. Interactive oblique MPR  
7. PACS send (C-STORE) after Q/R stable  
8. Pixel arithmetic + LUT enhancements  
9. Performance / first-paint (competitive with RadiAnt “instant” feel)

### Tier C — Measurements & modality niches

1. Cobb angle, manual calibration  
2. 3D cursor / improved linked navigation polish  
3. Multi-distribution histogram compare (existing plan)  
4. Print/PDF  
5. ECG/WAVEFORM in SR (optional)

### Tier D — Platform & optional polish

1. DICOMweb client  
2. File association shipped in installer  
3. 3D scalpel/crop spike  
4. JPEG2000  
5. Inbound C-STORE listener (site-specific)

### Tier E — Optional / deferred (explicitly out of core scope for now)

- Web viewer, mobile app, plugin ecosystem  
- DICOM SEG / RT / deformable registration / AI segmentation  
- Curved MPR, TIC, DSA, CD authoring, DICOM tag editor  
- KO export (unless PACS key-image workflow requested)  
- Multilingual, multi-touch  

---

## Mapping: existing `TO_DO.md` entries

These items were **already** on the backlog before this analysis; the gap doc **elevates priority** for some and adds cross-links.

| TO_DO topic | Gap § | Suggested tier |
|-------------|-------|----------------|
| Hanging protocols | §2 | A (consider **P1**) |
| Pulling priors | §2 | A (consider **P1**) |
| PACS-like query/archive | §1 | A (consider **P1**) |
| Fusion on MPR | §3 | B |
| Interactive oblique MPR | §3 | B |
| Projection export | §5 | B |
| GSPS / KO / fused SC | §5 | A / B / E |
| 3D export image/SC | §5 | B |
| Pixel arithmetic, image processing, LUTs | §8 | B |
| Deep anonymizer, metadata browser, file association | §8, §11 | A / B |
| SR / highdicom | §9 | A / B |
| Enhanced multi-frame Tier 3 | §7 | B |
| Advanced ROI/contouring | §10 | E |

**New checkboxes** (not previously explicit on `TO_DO.md`) are listed in **§ Competitive feature gaps** in [`TO_DO.md`](../TO_DO.md).

---

## Strengths to preserve (do not regress while chasing parity)

- **pylinac QA** integration — market differentiator for medical physics workflows.  
- **Fusion accuracy** — verified PET/CT pipeline; prioritize edge UX (variable slice thickness) over rewrites.  
- **Offline-first** architecture — PACS should remain optional module.  
- **Harness / agent docs** — keep `TO_DO` and plans linked when adding large features.

---

## Changelog (this document)

| Date | Change |
|------|--------|
| 2026-06-02 | Initial analysis from desktop viewer survey (RadiAnt, Horos, OsiriX, MicroDicom, Weasis, OHIF, 3D Slicer) and V3 codebase/`TO_DO` review. |

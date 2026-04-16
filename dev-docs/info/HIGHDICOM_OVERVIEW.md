# Highdicom — capabilities, use cases, and fit for DICOM Viewer V3

**Purpose:** Summarize the [highdicom](https://pypi.org/project/highdicom/) library for maintainers evaluating optional integration (especially **Structured Reports**).  
**Status:** Research note — no runtime dependency is implied until a Phase 0 spike accepts it (see [SR full-fidelity plan](../plans/supporting/SR_FULL_FIDELITY_BROWSER_PLAN.md) §4).  
**Last reviewed:** 2026-04-16 (against highdicom **0.27.x** docs on Read the Docs).

---

## 1. What highdicom is

Highdicom is a **pure Python** library built on **[pydicom](https://pydicom.github.io/pydicom/stable/)** that exposes a **higher-level API** for tasks common in **machine learning, computer vision, and quantitative imaging** workflows: reading heterogeneous DICOM images, authoring **derived** objects (segmentations, structured reports, parametric maps, presentation states), and parsing some of those objects back into typed Python structures.

Official positioning (paraphrased from the [user guide index](https://highdicom.readthedocs.io/en/stable/index.html)):

- Read existing DICOM instances across many modalities.
- Store **image-derived** information in standard DICOM objects (notably **SEG**, **SR**, **PR**, **PM**), often with numpy-friendly accessors.
- Maintain interoperability with pydicom (`Dataset` subclasses appear throughout the SR API).

**Origin / ecosystem:** Development is associated with the **[Imaging Data Commons](https://datacommons.cancer.gov/research/imaging-data-commons)** (IDC) community; the source repository is **[ImagingDataCommons/highdicom](https://github.com/ImagingDataCommons/highdicom)**.

**License (distribution):** PyPI classifies the package under **MIT License** (verify the exact `LICENSE` text in the release sdist or GitHub tag before shipping in a frozen bundle). This is generally compatible with permissive redistribution alongside PySide6-based apps, but **legal review** remains the product owner’s responsibility.

---

## 2. Capability areas (beyond a flat tag dump)

The library is modular. Areas most relevant to a **diagnostic viewer** are below; see the [API / package overview](https://highdicom.readthedocs.io/en/stable/package.html) for the full surface.

| Area | Typical use | Viewer relevance |
|------|-------------|------------------|
| **`highdicom.sr`** | Author and parse **Structured Reports**; typed **content items**; **TID 1500** measurement reports | **Primary** candidate for optional SR helpers |
| **`highdicom.seg`** | Create / read **DICOM Segmentation** objects (`segread`, masks, source image UIDs) | Future: overlay SEG on CT/MR if the product roadmap adds SEG |
| **`highdicom.sc`** | Secondary Capture authoring | Low priority for a primary viewer |
| **`highdicom.pr`** / GSPS-style flows | Presentation states | Optional export / display polish |
| **`highdicom.pm`** | Parametric maps | Research / dose-colorization pipelines |
| **`highdicom.Image`** / **`highdicom.pixels`** | Frame access, decapsulated pixels | Overlaps with viewer’s existing decode path; adopt only if it removes duplication |
| **`highdicom.spatial`** | Coordinate transforms (e.g. SR graphics vs FoR) | Useful if we ever **render SR SCOORD** on top of pixels |

---

## 3. Structured Reports (`highdicom.sr`) — what it does well

### 3.1 Content model

SR documents are trees of **content items**. Highdicom maps value types to **pydicom `Dataset` subclasses**, for example ([SR overview](https://highdicom.readthedocs.io/en/stable/generalsr.html)):

- `CodeContentItem`, `NumContentItem`, `TextContentItem`, `PnameContentItem`
- `ContainerContentItem`, `CompositeContentItem`, `UIDRefContentItem`
- `ScoordContentItem`, `Scoord3DContentItem`, `TcoordContentItem`, `WaveformContentItem`
- `ContentSequence` for nesting, with `RelationshipTypeValues` (`CONTAINS`, `HAS_PROPERTIES`, …)

**Practical benefit:** When a dataset already conforms to expectations, you work with **attributes and properties** instead of re-implementing low-level walks for every NUM/CODE pair.

### 3.2 Authoring IODs (write path)

For **new** SR files, highdicom implements constructors for three SR IODs ([SR overview — Structured Reporting IODs](https://highdicom.readthedocs.io/en/stable/generalsr.html#structured-reporting-iods)):

- `EnhancedSR` — no **SCOORD3D** content items
- `ComprehensiveSR` — same SCOORD3D restriction; functionally similar to `EnhancedSR` for supported features
- `Comprehensive3DSR` — supports **SCOORD3D** (most general; newer in the ecosystem)

The viewer’s near-term roadmap is **read/browse/export**, not production SR authoring, so these classes matter mainly for **round-trip tests** or future “export measurement SR” features.

### 3.3 Reading / parsing (read path)

**`highdicom.sr.srread(path)`** loads an SR file and returns a highdicom SR object ([Parsing Measurement Reports](https://highdicom.readthedocs.io/en/stable/tid1500parsing.html)).

If you already have a `pydicom.Dataset`, the pattern is:

```python
sr = highdicom.sr.Comprehensive3DSR.from_dataset(ds)  # pick the IOD-appropriate class
```

**TID 1500 — Measurement Report:** When the document conforms to **TID 1500**, the `.content` property resolves to a **`MeasurementReport`** with query helpers, for example:

- `get_image_measurement_groups()`, `get_planar_roi_measurement_groups()`, `get_volumetric_roi_measurement_groups()` with filters (tracking UID, finding type/site, referenced SOP Instance UID, graphic type, reference type, …)
- Within groups: `get_measurements()`, `get_qualitative_evaluations()` with access to **values**, **units**, **ROI geometry as numpy** (for image-plane regions), references to **SEG** segments, etc.

This is the **strongest** template-specific parsing story in highdicom today and aligns with the product plan’s **Phase 5** interest in **TID 1500** ([SR plan](../plans/supporting/SR_FULL_FIDELITY_BROWSER_PLAN.md) §6 Phase 5).

**Non–TID-1500 documents:** The same docs state that when the file is **not** TID 1500, `.content` falls back to a generic **`ContentSequence`**. That is still useful (typed items, nesting), but you **do not** get the rich `MeasurementReport` query API.

### 3.4 Spatial graphics

For **SCOORD** / **SCOORD3D**, highdicom emphasizes **numpy** arrays for graphic data and documents the **image coordinate convention** (origin top-left of top-left pixel) vs **frame-of-reference** mm coordinates for 3D graphics ([SR overview — graphic data](https://highdicom.readthedocs.io/en/stable/generalsr.html#graphic-data-content-items-scoord-and-scoord3d)).  
**Viewer angle:** could shorten the path from SR nodes to “draw something on the slice” if we ever prioritize graphic overlays—today the SR browser plan explicitly **defers** canvas drawing for v1.

---

## 4. Important gaps relative to our SR roadmap

Our [SR full-fidelity browser plan](../plans/supporting/SR_FULL_FIDELITY_BROWSER_PLAN.md) prioritizes:

1. A **generic `ContentSequence` tree** for all supported SR storage classes (full fidelity display).
2. **RDSR** per-event tables (**TID 10003** / **113706** *Irradiation Event X-Ray Data*, Enhanced RDSR / **TID 10040** family, etc.).

**Highdicom’s documented template coverage** centers on **TID 1500** for high-level parsing helpers ([SR overview — templates](https://highdicom.readthedocs.io/en/stable/generalsr.html#structured-reporting-templates)). There is **no** similarly documented, first-class API in the stable user guide for **X-Ray Radiation Dose SR** template trees (TID 10001 / 10002 / 10003 / …) comparable to `MeasurementReport`.

**Implication:** For **RDSR** and many **non–TID-1500** clinical templates, the viewer should continue to rely on:

- **`pydicom`** + our **`sr_document_tree`** model for **display**, and  
- **`rdsr_irradiation_events`**, **`rdsr_dose_sr`**, and related modules for **dose semantics**,

…unless a Phase 0 spike shows a **specific** highdicom utility (or typed `ContentSequence` walk) that reduces code or bug risk measurably.

The plan already captures the right integration rule: **one canonical tree model**; use highdicom only where it clearly helps ([SR plan](../plans/supporting/SR_FULL_FIDELITY_BROWSER_PLAN.md) §11 item 4).

---

## 5. How highdicom could extend DICOM Viewer V3

| Opportunity | Mechanism | Notes |
|-------------|-----------|--------|
| **Faster TID 1500 analytics** | `srread` + `MeasurementReport` filters | Good if we surface measurement groups, diameters, qualitative evaluations, or SEG-linked ROIs in UI or exports |
| **Safer SCOORD handling** | Typed items + numpy reconstruction + `highdicom.spatial` | De-risks numeric parsing vs hand-rolled `GraphicData` decoding |
| **Future SEG support** | `highdicom.seg.segread` | Aligns with IDC-style pipelines; separate product decision |
| **Authoring derived SR/SEG** | IOD constructors | Research / QA export workflows—not required for read-only SR browser v1 |
| **Reduced bespoke SR code** | Reuse `ContentItem` subclasses when reading | Tradeoff: import weight and PyInstaller graph vs pydicom-only tree |

**Risks / costs** (called out in the SR plan):

- **Frozen bundle size** — extra dependency graph vs pydicom-only; document PyInstaller delta after a spike.
- **API scope** — excellent for TID 1500; **not** a drop-in replacement for the entire SR storage universe.
- **Two mental models** — team must avoid divergent “highdicom tree” vs “viewer `SrContentNode` tree” unless boundaries are strict.

---

## 6. Recommended evaluation steps (Phase 0)

1. **Spike** `srread` on: (a) a committed **RDSR** fixture, (b) a **TID 1500** sample if available, (c) a **Basic / Comprehensive** non–TID-1500 SR. Record what type `.content` returns and whether any highdicom helper beats our tree builder for that file.  
2. **Measure** import time and **PyInstaller** one-file / one-folder size delta.  
3. **Confirm** license text on the exact wheel/sdist version pinned in `requirements.txt`.  
4. **Decide** per submodule: adopt / defer / reject—document results in the SR plan appendix or here under **Revision history**.

---

## 7. References

- Highdicom documentation (stable): https://highdicom.readthedocs.io/en/stable/index.html  
- SR section hub: https://highdicom.readthedocs.io/en/stable/sr.html  
- SR overview (content items, IODs, TID 1500 scope): https://highdicom.readthedocs.io/en/stable/generalsr.html  
- Parsing TID 1500 measurement reports: https://highdicom.readthedocs.io/en/stable/tid1500parsing.html  
- PyPI project metadata: https://pypi.org/project/highdicom/  
- Internal SR plan (highdicom allowed, spike required): [SR_FULL_FIDELITY_BROWSER_PLAN.md](../plans/supporting/SR_FULL_FIDELITY_BROWSER_PLAN.md) §4 and Phase 0

---

## Revision history

| Date | Change |
|------|--------|
| 2026-04-16 | Initial research note from public docs / PyPI metadata. |

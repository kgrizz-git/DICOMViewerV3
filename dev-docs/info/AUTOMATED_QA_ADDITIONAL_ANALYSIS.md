# Additional Automated QA Analysis Beyond Pylinac

This document defines additional automated QA analyses that complement pylinac integration in DICOM Viewer V3.

Focus areas:
- ACR-style tests that may be partially covered, implementation-dependent, or not directly available via pylinac in the exact form desired.
- Practical baseline checks for common CT manufacturer/uniform phantoms.
- Mammography phantom and image-quality checks (often outside pylinac’s core scope).

The goal is a pragmatic QA layer that is:
- Clinically useful for trend monitoring.
- Transparent (clear formulas and assumptions).
- Modular and independent from the core viewer pipeline.

---

## 1. Scope and Rationale

Pylinac should remain the primary backend for standardized phantom analysis where supported and validated.

However, there are two recurring needs:
1. **Coverage gaps or workflow gaps** where users need specific institutional metrics not directly exposed in pylinac outputs.
2. **Simple, high-value baseline checks** users can run quickly on routine phantom scans (especially CT uniformity phantoms).

This document proposes a complementary "in-app QA primitives" layer for those needs.

### 1.1 Progressive automation: manual-first, suite later

Native QA features (CT primitives, MAP mammography scoring, Rose calibration, etc.) can follow the same product strategy as pylinac integration: **start with deliberate human steps**—user selects **phantom preset**, **series**, **slice or frame** where the metric is defined (e.g. DBT best slice, MPR source slice), and **which test or profile to run**—and only then add **defaults**, **suggestions**, **auto placement**, and **full multi-test pipelines**. That keeps physics validation tractable, avoids wrong automated answers on edge acquisitions, and matches how physicists usually roll out new QC software. Deeper automation should **reuse the same analysis entrypoints** so early manual workflows do not need to be thrown away. The same principle is stated for **pylinac-backed** QA in [PYLINAC_INTEGRATION_OVERVIEW.md](PYLINAC_INTEGRATION_OVERVIEW.md) under **Progressive automation**.

---

## 2. Cross-check: ACR documentation vs pylinac (coverage and phantom sizes)

This section summarizes what the **pylinac** and **ACR accreditation support** materials say today, so gaps are explicit when planning DICOM Viewer V3 QA features.

**Primary references (checked 2026-03-27):**
- Pylinac ACR module documentation: https://pylinac.readthedocs.io/en/latest/acr.html
- ACR CT phantom overview (Gammex 464, capabilities / modules): https://accreditationsupport.acr.org/support/solutions/articles/11000053945-overview-of-the-ct-phantom
- ACR MRI testing overview (program structure + phantom sizes): https://accreditationsupport.acr.org/support/solutions/articles/11000061018-testing-overview-mri-revised-10-21-2024

### 2.1 MRI ACR: tests pylinac does not automate

Per pylinac’s MRI section, **Section 0.4 of the ACR guidance lists eight tests**; pylinac states it **automates seven of eight**. The eighth is **artifact assessment**, which pylinac treats as a **visual inspection** task rather than an algorithmic output.

**Practical implication for this app:** reserve a first-class “Artifact checklist” step in any MRI QA workflow (checkboxes, free text, optional screenshot attachment) even when pylinac is the analysis engine.

**Not a “missing test,” but a known method difference:** pylinac’s **high-contrast** scoring for the ACR MRI phantom **does not perform dot counting** the way the written guidance describes qualitatively; it samples ROIs and derives MTF-related summaries. Pylinac suggests **periodic visual cross-checks** against its numeric high-contrast outputs until a site is comfortable with the automation.

**Workflow caveat from pylinac:** if the **sagittal** image is a **separate Series Instance UID**, pylinac will **ignore** it unless `check_uid=False` on `ACRMRILarge`. The viewer integration should detect multi-UID sagittal acquisitions and either merge with user consent or pass the correct flag intentionally.

### 2.2 MRI ACR: large, medium, and small phantoms

**What pylinac documents:** the ACR submodule is described as analyzing **DICOM images of the ACR CT 464 phantom and Large MR phantom**, with MRI analysis referencing **large-phantom** guidance. The public class is **`ACRMRILarge`**, and the low-contrast section explicitly refers to **slices 8–11 of the ACR MRI Large phantom** and expects **11 axial slices (12 if sagittal is included)**, matching the large-phantom workflow assumptions.

**What pylinac does not document:** separate first-class APIs or documented validation paths for **ACR medium** or **small** MRI phantoms. ACR’s program materials describe **large, medium, and small** phantom options for different clinical contexts; geometry and resolution targets differ (for example, the medium phantom adds finer resolution patterns per ACR’s large/medium testing article).

**Conclusion for integration planning:** treat pylinac as **Large ACR MRI–centric** unless/until upstream pylinac docs (or your own physicist validation) confirm medium/small geometry. For medium/small sites, plan either **manual scoring**, **custom offsets/subclassing** (high risk without validation), or **in-app primitives** (Sections 3–5) scoped to those phantom models.

### 2.3 CT ACR (Gammex 464): accreditation context vs pylinac’s CT module

The ACR CT phantom overview states the phantom is designed to examine **positioning accuracy**, **CT number accuracy**, **low-contrast resolution**, **high-contrast (spatial) resolution**, **CT number uniformity**, and **image noise**, and notes that **not every one of these measurements must be submitted** for accreditation, but all are intended for **routine QC**.

Pylinac’s **`ACRCT`** pipeline (as described in the same documentation page) is organized around **module-aligned analyses** (HU / calibration, uniformity—including a **center ROI standard deviation** useful for noise trending, **low-contrast CNR**, and **spatial resolution / MTF-style outputs**).

**Typical gaps outside pylinac (or outside “image stack only” automation):**
- **Dosimetry / CTDI workflows** and **dose pass/fail** for accreditation are **parallel** to image-quality analysis; they use **CTDI phantoms and forms**, not what pylinac’s ACR CT image module solves end-to-end.
- **Positioning accuracy** and **slice thickness** characterization on **Module 1** (BBs, ramps) are called out in ACR’s phantom overview. Pylinac’s public ACR CT section emphasizes the **four analysis modules** tied to calibration, low contrast, uniformity, and spatial resolution. **Before treating pylinac as a complete Module-1 substitute**, verify the **`ACRCTResult`** fields in the pylinac version you pin—if thickness/position metrics are absent, keep **physicist Module-1 checks** or add **viewer-native measurements** (distance tools, thickness from paired ramps, etc.) as an explicit supplement.

**Operational note:** ACR requires phantom acquisition to follow **clinical protocols** (with stated exceptions such as turning off automatic mA modulation and using a **21 cm DFOV** for submission). Automation should attach **protocol tags** (kVp, kernel, FOV, modulation state) to every exported QA record so results are comparable over time.

---

## 3. ACR-Related Analyses to Consider Beyond Direct Pylinac Use

## 3.1 MRI Low-Contrast Detectability (LCD)

### Relationship to pylinac
- For **ACR MRI Large**, pylinac already implements **low-contrast detectability** on slices 8–11 using a **visibility** algorithm and configurable thresholds (see pylinac `ACRMRILarge.analyze()` / contrast-visibility documentation).
- That coverage **does not extend** to **medium/small** phantoms in the public docs, and sites may still want workflows that **match historical manual scoring** or **add human confirmation**.

### Why supplementary workflows still matter
- MRI low-contrast outcomes remain **protocol-, coil-, and reconstruction-dependent**.
- Physicists often want **institutional baselines**, side-by-side images, and audit trails beyond a single numeric “spokes visible” style summary.

### Practical recommendation
- When pylinac is available: **surface pylinac LCD outputs** and store raw parameters (thresholds, method).
- Additionally (especially for **non-large** phantoms or when disputing an automated call): implement a **semi-automated LCD assist** mode:
  - Template ROIs or weakly guided placement on spoke disks.
  - CNR / visibility-style metrics with **explicit confidence** flags.
  - Guided visual checklist for human confirmation.

### Output
- Per-target CNR and detectability score (custom path) **plus** pylinac’s native metrics when both run.
- Overall pass/fail by local threshold and confidence level.
- "Automated estimate + human confirmed" dual-status field.

### Notes
- Prefer **transparent** formulas and stored ROI geometry so automated and semi-automated paths can be reconciled later.

## 3.2 MRI Ghosting / Artifact Indices (if not sufficiently covered in target workflow)

### Recommendation
- Add region-based ghosting metrics (phase-encode direction side ROIs vs central ROI).
- Store protocol metadata and coil used for trend comparability.

### Output
- Ghosting ratio per scan.
- Trend chart by scanner/protocol.

## 3.3 ACR Result Normalization Layer

Even when pylinac computes the core metrics, add a normalization layer in-app:
- Map metrics to a single schema across CT/MRI/vendor/protocol.
- Record thresholds and units in a consistent format.
- Keep a clear distinction between:
  - **Measured value** (physics output).
  - **Policy verdict** (site-specific pass/fail threshold).

---

## 4. Simple CT Phantom Checks (Manufacturer/Uniform Phantoms)

These checks are high value and straightforward to implement with existing viewer data flow.

## 4.1 Water HU Value

### Definition
- Measure mean HU in a central ROI on a uniform water-equivalent section.

### Suggested defaults
- Circular center ROI with fixed physical diameter (e.g., 20 mm) converted using PixelSpacing.
- Compute mean, median, standard deviation, and min/max.

### Example acceptance concept
- Water mean near 0 HU with configurable tolerance (site policy, often around plus/minus a few HU).

## 4.2 Image Noise (CT)

### Definition
- Noise as standard deviation of HU in a uniform ROI (typically same central ROI as water HU).

### Suggested defaults
- Use same ROI for simplicity and reproducibility.
- Optionally report robust noise estimate (IQR-based sigma) to reduce outlier sensitivity.

## 4.3 Uniformity (Center vs Periphery)

### Definition
- Compare center ROI mean HU with peripheral ROIs (top, bottom, left, right).

### Metrics
- Peripheral-center differences for each direction.
- Max absolute difference across all peripheral ROIs.
- Optional aggregate uniformity index.

### Suggested ROI strategy
- One center ROI + four peripheral ROIs placed with fixed margin from phantom edge.
- Use physical-size ROI defaults (mm) and store actual pixel radius used.

## 4.4 Optional Extension: CT Number Linearity (if suitable insert phantom available)

If the phantom has material inserts:
- Add per-insert ROI means and compare against expected HU ranges.
- Keep expectations configurable per phantom model and protocol (kVp-dependent).

---

## 5. Mammography Phantom and Image QA (Potential Automation)

Pylinac today is **not** centered on mammography phantom pipelines. Sites still need **repeatable QC** from vendor-specific phantoms (grids, wedges, contrast-detail phantoms, uniform slabs) and from **clinical QC** images. The approaches below are **engineering targets** for in-app automation; **accreditation submission rules** and phantom-specific scoring charts remain the physicist’s authority—software should output **transparent metrics and provenance**, not silent “pass ACR.”

### 5.1 What mammography QC typically assesses

| Area | Typical intent |
|------|----------------|
| **Noise / SNR** | Stability of noise in a uniform region at routine technique. |
| **Uniformity / dose response** | Left–right or regional signal flatness (scatter, heel effect, detector issues). |
| **Contrast / detail** | Visibility of small low-contrast objects (contrast-detail phantoms, e.g. CDMAM-style). |
| **Sharpness / resolution** | Edge spread or MTF proxy (thin wires, slanted edges, bar patterns if present). |
| **Artifacts** | Grid lines, stitching, dead lines, detector dropouts, scattered radiation patterns. |
| **Geometric / thickness** | Compression paddle–breast distance proxies (where metadata or fiducials exist), phantom dimension checks. |

**Dose and exposure indices** (e.g. AGD/MGD-related quantities) are often computed from **DICOM exposure tags and RDSR**, not from pixel ROIs alone; pair image QA with **metadata export** when building mammography QC.

### 5.2 Potential automated analysis approaches (viewer-centric)

1. **Uniform ROI pipeline (noise + uniformity)**  
   - After **optional manual or weak registration** (phantom outline click or Hough ellipse on field edge), place **fixed-size ROIs** in nominal uniform zones.  
   - **Automation:** mean, std dev, SNR proxy \( \mu / \sigma \), **integral uniformity** (max–min over peripheral ROIs vs center), optional **1D profiles** through center to catch heel effect.

2. **Contrast-detail automation (CDMAM / similar)**  
   - **Hard path:** detect grid of **gold discs**, threshold at local background, score **last visible diameter/thickness** per ACR or vendor worksheet (needs **calibrated pixel spacing** and phantom model preset).  
   - **Pragmatic path:** **semi-automated**—template overlay, user confirms column/row, algorithm scores visibility with **local contrast + CNR** and outputs an estimated threshold diagram for physicist sign-off.

3. **Sharpness / MTF proxy**  
   - If the phantom includes a **slanted edge** or thin wire: follow **ESF → LSF → MTF** (or simplified edge derivative) in a cropped ROI.  
   - If only bar groups exist: **peak-valley contrast** vs nominal spatial frequency as a **relative MTF index** for trending.

4. **Artifact screening**  
   - **FFT or directional gradient energy** to flag periodic grid noise; **column/row variance** maps for detector defects; **streak emphasis** via Radon or simple oriented filters (tune false-positive rate for clinical QC vs research).  
   - Default to **“flag for review”** rather than binary fail unless thresholds are site-validated.

5. **Protocol-aware trending**  
   - Bucket results by **kVp, filter, target/filter combo, grid yes/no, reconstruction “for processing” vs “for presentation,”** and **laterality** so noise/detail metrics stay comparable.

### 5.3 Integration notes for DICOM Viewer V3

- **Monochrome2** with **presentation intent** matters: mammography often uses **for-processing** DICOM; avoid mixing presentation-lut mangled images with physics metrics unless intentionally normalized.  
- Support **large matrix** images with **progressive ROI computation** or downsampled passes for preview.  
- Prefer **modality MG**, **secondary capture exclusion**, and optional **QA Acquisition Context** or workstation tags when filtering series for QC.

### 5.4 ACR MAP phantoms: approved models and geometry (fibers, specks, masses)

Official Mammography Accreditation Program (MAP) guidance distinguishes **two phantom categories**, both designed to simulate **4.2 cm compressed breast** of **average density** with a **wax insert** containing **fibers**, **speck groups**, and **lens-shaped masses**. Facilities must purchase an **ACR-approved** unit from the manufacturer; the current **approved list and exposure rules** are on ACR Accreditation Support (“Phantom Testing: Mammography”), e.g. https://accreditationsupport.acr.org/support/solutions/articles/11000065938-phantom-testing-mammography-revised-11-22-2024-

**Category A — “Small ACR Mammography Phantom” (screen-film–era lineage; still used on many FFDM/CR workflows per instructions)**  
- **Specks:** **aluminum oxide (Al₂O₃)** particles in **six graded groups** (one size class per row in the scoring table).  
- **Fibers:** **six** nylon fibers, diameters from largest to smallest per table below.  
- **Masses:** **six** masses graded by **thickness** (mm).  
- **ACR accreditation minimum visibility (no clinically significant artifacts):** the **four largest fibers**, **three largest speck groups**, and **three largest masses** must be visualized (see table—rows marked * are required for that minimum set).

**Category B — “ACR Digital Mammography Phantom” (FFDM / digital QC manual scoring)**  
- **Specks:** **glass spheres** in six groups (ACR states glass specks were matched so corresponding sizes have **similar visibility** to Al₂O₃ on the small phantom).  
- **Fibers** and **masses:** six grades each; **feature sizes are smaller** than on the small phantom.  
- **ACR accreditation minimum visibility:** **two largest fibers**, **three largest speck groups**, and **two largest masses** (rows marked * in digital table below).

**Approved manufacturers / models (consult ACR table for current part numbers — vendors update periodically):**

| Manufacturer | Small ACR Mammography Phantom | ACR Digital Mammography Phantom |
|--------------|--------------------------------|----------------------------------|
| CIRS, Inc. | Model **015** (legacy; **no longer sold**; existing units remain acceptable) | Model **086** (same sales note) |
| Sun Nuclear / Mirion (Gammex) | Model **156** | **Mammo FFDM Phantom** |
| Supertech® | e.g. **03-502-ST** | (per ACR listing) |
| Pro-Project (Diagnomatic) | **Pro-MAM Accreditation FF** / **03-501** (per ACR listing) | (per ACR listing) |

Vendor datasheets give **overall phantom dimensions** and **wax-insert** size (example from Sun Nuclear product pages): **Mammo FFDM** phantom on the order of **~31 × 19 × 4.1 cm** with a **~13 × 7 × 0.7 cm** wax insert; **Model 156** is a more compact assembly (~**6.7 × 6.8 × 6.1 cm** overall in one vendor sheet) with **four** nylon fiber diameters, **four** Al₂O₃ speck sizes, and **four** mass diameters arranged to meet **ACR specifications**—implementations should load **per-SKU geometry** from a config file rather than hard-coding one drawing.

**Stereotactic note:** Sun Nuclear’s **156D** stereotactic phantom is aimed at **biopsy/localization** QA (different visibility/size emphasis, **0.20–1.00 mm** detail range in marketing copy). Treat it as a **separate preset** from MAP **2D/FFDM** scoring—not interchangeable with the MAP pass tables above.

**DBT submission:** ACR currently requires **one “best slice” (e.g. ~1 mm)** phantom image for DBT submissions—not a slab—so any automation must run on that slice (or let the user pick the slice the team would submit).

**ACR nominal test-object sizes (from ACR phantom-testing article — use for presets and UI labels)**

*Small ACR Mammography Phantom (Al₂O₃ specks):*

| # | Fiber Ø (mm) | Speck Ø (mm) | Mass thick (mm) | Notes |
|---|----------------|---------------|-------------------|--------|
| 1 | 1.56* | 0.54* | 2.00* | * = among sizes that must be seen for stated pass tier |
| 2 | 1.12* | 0.40* | 1.00* | |
| 3 | 0.89* | 0.32* | 0.75* | |
| 4 | 0.75* | 0.24 | 0.50 | |
| 5 | 0.54 | 0.16 | 0.25 | |
| 6 | 0.40 | — | — | Sixth **fiber** grade (smallest). The ACR web table excerpt does not repeat speck/mass cells on this row; use the **[MAP Phantom Test Image Data Sheet](https://accreditationsupport.acr.org/helpdesk/attachments/11097509101)** and your physical phantom diagram for full **six-group** layout. **Accreditation minima** use the **four largest** fibers, **three largest speck groups**, and **three largest masses** (see ACR phantom-testing article). |

*ACR Digital Mammography Phantom (glass specks):*

| # | Fiber Ø (mm) | Speck Ø (mm) | Mass thick (mm) |
|---|----------------|---------------|-----------------|
| 1 | 0.89* | 0.33* | 1.00* |
| 2 | 0.75* | 0.28* | 0.75* |
| 3 | 0.61 | 0.23* | 0.50 |
| 4 | 0.54 | 0.20 | 0.38 |
| 5 | 0.40 | 0.17 | 0.25 |
| 6 | 0.30 | 0.14 | 0.20 |

Human scoring uses **fractional points** (e.g. half fiber), **artifact deductions** against the last scored group, and rules on **fiber length/breaks** and **speck-like artifacts**—full detail is in the same ACR article and the **1999** (small) / **2018** (digital) ACR Digital Mammography QC Manual processes. Automated tools should **surface raw counts** and let the physicist apply **artifact corrections** if you mirror ACR’s spreadsheet logic.

### 5.5 Automating “how many fibers / speck groups / masses are visible?”

Because MAP scoring is **defined as a visual judgment**, any algorithm is an **approximation**. A practical DICOM Viewer V3 approach:

1. **Phantom preset + registration**  
   - User selects **Small vs Digital** (and vendor SKU); app loads **nominal (x,y)** centers of each fiber cluster, speck group, and mass (from vendor diagram or measured once per institution).  
   - **One-shot alignment:** user places **3–4 fiducial clicks** (e.g. wax insert corners or embossed markers) or accepts a rough automatic corner detect; affine warp optional for MVP.

2. **Per-object features**  
   - **Fibers:** crop elongated ROI along expected angle; **ridge filter** or **directional Frangi** response; score **mean contrast** vs **local background**, **continuity length** vs expected mm (PixelSpacing).  
   - **Speck groups:** circular ROIs per group; **matched filter** or **blobness** (LoG); count **local maxima** above a threshold; compare to expected **specks per group** (vendor layout).  
   - **Masses:** slightly larger ROI; **low-contrast disk** metric—mean interior vs annular background **Δ**, divided by **σ** of background (see **§5.6**).

3. **Output**  
   - For each of **six grades**, **visible Y/N** + **confidence** + **debug overlay** (heat map, detected centroids).  
   - Summarize **“meets ACR minimum tier if no artifact deduction”** separately from **algorithm raw counts** so reviewers see both.

4. **Artifacts**  
   - Reuse **§5.2** screening; ACR subtracts **fiber-like** or **speck-like** artifacts from the **last scored** feature—UI can offer **“mark artifact polygons”** to reduce auto speck count.

### 5.6 User-calibrated visibility (Rose-type CNR, feature size, noise σ)

**Motivation:** A single global intensity threshold fails across techniques and displays. A **calibration workflow** aligns automation with **how a specific user scores**:

1. User opens **one or more reference phantom images** they have already scored manually (or side-by-side with an expert).  
2. User adjusts **tunable parameters** until the app’s **last-visible grade** matches theirs for **fibers, speck groups, and masses**.  
3. Store a **site profile** (JSON): phantom category, reconstruction tag, kernel/display tags if needed, and parameters below.

**Suggested tunable knobs (all logged in export):**

| Knob | Role |
|------|------|
| **k_Rose** (scalar) | Scales the **minimum detectability** threshold. Conceptually tied to **Rose / SNR criteria**: contrast detail visibility improves with **√(effective area)** and **CNR**; one simple composite is \( \mathrm{score} = \Delta / (\sigma \cdot f(d)) \) where **Δ** is signal difference vs background, **σ** is **local noise** from a **fixed-size background ROI** (or noise map), **d** is **nominal feature size** (fiber width, speck diameter, mass thickness), and **f(d)** is **monotone increasing** in **d** (larger features easier). User calibrates **k_Rose** so “visible” ⇔ score > k_Rose. |
| **σ source** | Same **fixed ROI** near insert (per protocol), or **per-patch** σ; optional **σ floor** to stabilize division. |
| **Δ definition** | Weber vs Michelson contrast; **masked interior** vs **annulus** for masses; **percentile-based** background for specks. |
| **Minimum contiguous length (fibers)** | mm of ridge above threshold. |
| **Speck count rules** | Peak **prominence**, **minimum separation** in mm, cap per group. |

**Generalization beyond mammography (same calibration pattern):**

| Domain | Δ | σ | Feature size **d** |
|--------|---|---|---------------------|
| **MRI low-contrast disks / spokes** | Mean disk − local background | **Fixed ROI** on **uniform** region of same slice (or annulus) | Nominal disk diameter or spoke width from phantom preset |
| **Spatial resolution (any modality)** | Peak–valley on bars/wires/edges | σ from **same-size ROI** placed on **uniform region adjacent** to resolution pattern (or separate noise ROI at same distance from edge) | **Nominal spatial frequency** (lp/mm) or **bar width**—Rose-type models predict **required contrast ∝ σ/√(effective width)**; combine **measured contrast / σ** with **d** in the same **f(d)** as mammo. |
| **CT low-contrast inserts** | HU difference vs background | Center ROIs std dev | Insert diameter from preset |

**Why this fits the product:** the viewer already excels at **ROI placement and DICOM metadata**; storing **“calibrated profile v3 for GE DBT best-slice 1 mm”** makes repeated QC a **one-click** check with **traceable** parameters. **Important:** exported JSON should state **“not an ACR substitution for human MAP review”** unless a site validates the pipeline under their QC policy.

---

## 6. Test Catalog: Definitions and Proposed Automation Approaches

This section ties together **every substantive test or workflow** referenced above: what it is trying to measure, and a concrete **automation strategy** suitable for this application stack (NumPy-friendly ROIs, optional OpenCV/scikit-image later).

**Note:** For ACR MRI tests that pylinac already automates on the **Large** phantom (geometric accuracy, slice thickness, slice position, uniformity, ghosting, low-contrast detectability on slices 8–11, high-contrast ROI/MTF summaries), the default integration strategy remains **delegate to pylinac**—see [PYLINAC_INTEGRATION_OVERVIEW.md](PYLINAC_INTEGRATION_OVERVIEW.md). The catalog below emphasizes **gaps, supplements, and native primitives**.

| ID | Test / workflow | What it measures | Proposed automation approach |
|----|-----------------|------------------|------------------------------|
| **C1** | MRI **artifact assessment** (pylinac gap) | Structured visual review of clips, ghosts, shading, banding per ACR-style checklist. | **Guided UI:** checklist, severity scale, required free-text on fail, optional **screenshot crop** attachment; store reader ID and timestamp. Optional future: **simple heuristics** (banding FFT peak, bright-column detector map) only as “suggest flag,” not verdict. |
| **C2** | MRI **high-contrast** vs manual dot scoring | High spatial-frequency object visibility. | **Dual track:** (a) show **pylinac-derived MTF / ROI contrast** when pylinac runs; (b) optional **side-by-side reference image** + manual dot count entry for periodic calibration. Compute **site calibration ratio** between manual and automated once per quarter. Optional: reuse **§5.6** **k_Rose** + **σ** from adjacent uniform ROI + **f(d)** with **nominal dot spacing**. |
| **C3** | MRI **sagittal geometric accuracy** (multi-UID) | 3D geometric consistency when sagittal is separate series. | **Detect** multiple Series UIDs; prompt user to **merge series** or set “include sagittal” flag before calling pylinac; pass through to wrapper with `check_uid=False` when intentional. |
| **C4** | MRI **medium/small phantom** LCD | Low-contrast detectability on non-large inserts/layouts. | **Phantom preset** selects **template ROI map** (coordinates in mm) + **visibility/CNR** per insert; **semi-auto** confirmation; no claim of ACR scoring equivalence until physicist validates. |
| **C5** | CT **CTDI / dose accreditation** | Dose index compliance vs regulatory/program limits. | **Not pixel-DICOM analysis:** ingest **RDSR / CTDIvol / SSDE** from tags or sidecar forms; **export CSV/JSON** aligned to site spreadsheet; link **series UID** of dose phantom acquisition for traceability. |
| **C6** | CT **Module 1 positioning / slice thickness** (Gammex) | Table position, tilt, **ramp-based thickness**. | **BB centroid** detection + **nominal 19.9 cm chord** check (tolerance in mm); **ramp ROI** profiles → **FWHM** or ACR formula for thickness; **reproduce in viewer** with overlay of detected points. |
| **C7** | **Protocol tagging** (CT/MR) | Comparability of repeated QC. | **Automated metadata scrape:** kVp, mAs, kernel, pitch, FOV, convolution, iterative recon flags, B1 shim tags (MR), into `qa_models` payload on every run. |
| **C8** | **MRI LCD** supplementary (§3.1) | Institutional LCD beyond or beside pylinac. | **Template ROIs** on spokes/disks; **Weber/Michelson visibility** optional; **§5.6**-style **Δ/σ** vs disk **d** with **user-calibrated k_Rose**; store **all ROI pixel stats** for audit. |
| **C9** | **MRI ghosting ratio** (§3.2) | Phase-encode ghost energy vs central signal. | **Fixed peripheral ROIs** (phase direction) vs **central ROI**; implement **ACR-style ratio** already used in pylinac MRI doc as reference; same formula in native code for **non-pylinac** paths. |
| **C10** | **QA normalization layer** (§3.3) | Single schema for dashboards. | **Pydantic/dataclass** `QARecord` with `measurement` vs `policy_verdict`; **versioned JSON schema**; migration field for threshold sets. |
| **C11** | **CT water HU** (§4.1) | Calibration of CT number for water-equivalent medium. | **Center circular ROI** diameter from **PixelSpacing**; mean/median/std; optional **2% trim** for outliers; W/L independent **HU** read from rescale slope if needed. |
| **C12** | **CT image noise** (§4.2) | Noise magnitude in uniform region. | **σ** from center ROI; optional **robust σ** via IQR; **NEQ or noise power** deferred to research mode. |
| **C13** | **CT uniformity** (§4.3) | Cupping / tube aging / beam hardening drift. | **Five-ROI** pattern; **max deviation** and **PIU-style** index; optional **radial polynomial fit** residual as advanced flag. |
| **C14** | **CT number linearity** (§4.4) | HU vs material for multi-insert phantoms. | **Per-insert ROI** template per phantom SKU; **lookup expected HU** table by kVp; **linear regression R²** and **max residual** as trending metrics. |
| **C15** | **Mammo noise / uniformity** (§5.2 item 1) | Detector and technique stability. | **Uniform ROI grid**; store **profiles**; alert if **left–right asymmetry** exceeds threshold. |
| **C16** | **MAP phantom scoring** (fibers / speck groups / masses) (§5.4–5.5) | Count of **visible** graded test objects vs ACR minima for **Small** vs **Digital** phantom. | **Preset geometry** + **registration**; per-group **Δ/σ** and structure-specific detectors (§5.5); **artifact** UI for deductions; export overlays + raw counts. |
| **C22** | **User-calibrated visibility (“Rose”) profile** (§5.6) | Match **human** last-visible grade across modalities. | **Calibration mode:** tune **k_Rose**, **σ** ROI, **f(d)**, speck rules on reference images; save **versioned JSON profile**; apply to batch QC with disclaimer. |
| **C23** | **Mammo contrast-detail (non-MAP CDMAM)** (§5.2 item 2) | CDMAM-style **threshold** curves unrelated to MAP wax insert. | **Disc detection** or **semi-auto grid**; separate preset from **C16** so MAP and CD tools do not share geometry files. |
| **C24** | **Spatial resolution (CT/MR/MG bar or edge targets)** | Last resolvable frequency or **MTF** proxy. | **Bar pair** peak–valley or **slanted-edge MTF**; pair with **fixed-size noise ROI** (§5.6); optional **user-calibrated** visibility index \( \Delta/\sigma \) vs **nominal bar width** or **f_Nyquist**. |
| **C17** | **Mammo sharpness** (§5.2 item 3) | MTF-like behavior. | **Slanted-edge** or **wire ROI** subwindow; report **MTF50** or Nyquist-normalized index. |
| **C18** | **Mammo artifacts** (§5.2 item 4) | Grid, lines, Moiré. | **Screening filters**; output **heat map** + “review recommended,” not auto-fail. |
| **C19** | **Validation: ground truth** (§8.1) | Correctness of automation. | **Frozen DICOM fixtures** + **golden JSON** metrics; pytest tolerance bands; physicist-signed **reference set** version field. |
| **C20** | **Validation: robustness** (§8.2) | Behavior under real-world variance. | **Monte Carlo** ±2 mm ROI jitter; **missing-tag** injection; ensure **structured warnings** not silent NaNs. |
| **C21** | **Validation: usability** (§8.3) | Operators can interpret results. | **UI copy review**; export sample **one-click XLSX** template for common sites. |

---

## 7. Implementation Plan for Additional QA Primitives

## 7.1 Proposed modules

```text
src/
  qa/
    ct_primitives.py          # water HU, noise, uniformity
    mri_primitives.py         # LCD helpers, ghosting ratios
    mg_primitives.py          # mammo MAP fiber/speck/mass scoring, Rose calibration, uniformity, CD assist
    roi_templates.py          # deterministic ROI placement helpers
    qa_models.py              # dataclasses: metrics, thresholds, verdicts
    qa_export.py              # JSON/CSV export
```

## 7.2 Workflow

1. User selects active phantom series (**early versions may require explicit phantom preset and slice/frame; later versions can suggest defaults**).
2. App runs preflight checks (modality, spacing, slice consistency).
3. User selects analysis profile (single test or subset first; **full-suite “run all”** can be a later preset):
   - "CT uniform phantom quick checks"
   - "MRI LCD assisted analysis"
   - "Mammography MAP scoring (fibers / specks / masses) + optional Rose calibration"
   - "Mammography QC (uniformity / CDMAM assist / edge MTF)"
4. App computes metrics and shows:
   - Raw values.
   - Thresholds used.
   - Pass/fail status with rationale.
5. Export JSON (required) and optional CSV/PDF summary.

## 7.3 Data model requirements

Each analysis run should persist:
- App version.
- Analysis module version.
- Input series UID / study UID.
- Modality and key acquisition parameters (slice thickness, kVp where present, reconstruction kernel if present).
- ROI geometry (center/radius in pixels and mm).
- Metric values, units, thresholds, verdict.

This enables trend analysis and auditability.

---

## 8. Suggested Validation Strategy

## 8.1 Ground truth and repeatability
- Validate metrics against a small reference set reviewed by a physicist.
- Run repeat scans to estimate metric variability.

## 8.2 Robustness checks
- Confirm behavior for slight phantom mis-centering.
- Confirm clear failure/warning when spacing tags are missing or inconsistent.
- Confirm deterministic ROI placement for identical input.

## 8.3 Clinical usability checks
- Ensure result dialog states both numeric values and what failed.
- Ensure exports are easy to ingest in spreadsheets or QA dashboards.

---

## 9. Recommended Rollout Order

1. Implement CT water HU + noise + uniformity quick-check profile.
2. Add structured export + trend-ready metadata.
3. Add MRI LCD assisted workflow with confidence labels.
4. Add optional ghosting/artifact metrics and deeper MRI profile support.
5. Add mammography **MAP preset** (Small vs Digital), **fiber/speck/mass** auto-score with overlays, and **Rose calibration** export/import.
6. Add **uniformity + noise** profile, then **CDMAM assist** and **edge MTF** for non-MAP phantoms as needed.

This sequence delivers immediate practical value while keeping complexity controlled.

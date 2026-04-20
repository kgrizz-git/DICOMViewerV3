## Pylinac Integration for Phantom QA (ACR Focus, CatPhan Aware)

**End-user guide (menus, inputs, exports):** [USER_GUIDE_QA_PYLINAC.md](../../user-docs/USER_GUIDE_QA_PYLINAC.md) in `user-docs/`.

This document outlines how **pylinac** could be integrated into DICOM Viewer V3 to provide **automated QA analysis of phantoms**, with a primary focus on **ACR CT/CBCT and MRI phantoms** and secondary support for **CatPhan** models.

**Actionable Stage 1 checklist:** [PYLINAC_AND_AUTOMATED_QA_STAGE1_PLAN.md](../plans/completed/PYLINAC_AND_AUTOMATED_QA_STAGE1_PLAN.md).

**Scan-extent tolerance + reproducibility metadata (planned implementation):** [PYLINAC_SCAN_EXTENT_TOLERANCE_AND_REPRODUCIBILITY_PLAN.md](../plans/PYLINAC_SCAN_EXTENT_TOLERANCE_AND_REPRODUCIBILITY_PLAN.md).

**What is already in the codebase vs planned:** see [Integration status (pylinac in DICOMViewerV3)](#integration-status-pylinac-in-dicomviewerv3) (living section—update it as integration progresses).

**Pylinac reference notes (project docs):**

- [PYLINAC_MRI_LOW_CONTRAST_DETECTABILITY.md](PYLINAC_MRI_LOW_CONTRAST_DETECTABILITY.md) — ACR MRI Large **low-contrast detectability** (algorithm, scoring, PDF/figure circle colors); aligned with **pylinac 3.42.0** (project pin).
- [PYLINAC_CUSTOMIZATION_AND_EXTENSIONS.md](PYLINAC_CUSTOMIZATION_AND_EXTENSIONS.md) — **Living tracker**: how we customize, extend, or wrap pylinac (config, runners, subclasses); persist vs per-run `analyze()` kwargs.
- [PYLINAC_CATPHAN_AND_NUCLEAR_MODULES.md](PYLINAC_CATPHAN_AND_NUCLEAR_MODULES.md) — **CatPhan / Quart CT** and **`pylinac.nuclear`** (IAEA/NMQC-style NM/SPECT): tests performed, expected DICOM inputs, demo ZIPs / external sample data.

The goals are:
- **Leverage pylinac** for robust, validated phantom analysis rather than re‑implementing QA physics.
- **Keep DICOMViewerV3 modular**: pylinac is an optional analysis backend, not a core dependency for basic viewing.
- **Provide a clear multi‑phase roadmap**: from proof‑of‑concept (PoC) to advanced QA workflows.

### Progressive automation: manual-first, pipeline later

Integration can start with **low automation** and still deliver value: the user **names or selects the phantom** (preset or modality), **chooses the series** (and, when relevant, **the slice, frame, or echo**), and **picks which analysis to run** (one module or a minimal subset) instead of relying on auto-identification or a full end‑to‑end suite on day one. Later work layers in **heuristic phantom detection**, **best-slice or best-volume hints**, **wizards**, **batch and queued runs**, and **combined QA pipelines**—all on top of the same wrappers so early, narrowly scoped workflows remain testable and valid. Complementary native QA (mammography MAP, CT primitives, calibration) follows the same idea in [AUTOMATED_QA_ADDITIONAL_ANALYSIS.md](AUTOMATED_QA_ADDITIONAL_ANALYSIS.md) §1.1.

---

## Integration status (pylinac in DICOMViewerV3)

**Living section:** keep this block current whenever pylinac-backed behavior is added, extended, or intentionally out of scope.

This is a **snapshot** of pylinac usage in **application code** (`src/qa`, Tools menu wiring in `src/main.py` / `src/gui`). It is not an exhaustive catalog of every class in the upstream library.

### Verified pylinac package version

**`requirements.txt`** pins **`pylinac==3.42.0`** and lists **`pypdf>=4.0.0`** as an explicit direct dependency (with a short comment in that file) for merging per-run pylinac PDFs into the combined compare report—see `dev-docs/plans/MRI_COMPARE_COMBINED_PDF_PLAN.md`. The **`pylinac==3.42.0`** pin is the **only** upstream pylinac release **verified end-to-end** with this project’s ACR CT / ACR MRI Large integration so far (constructors, `analyze()`, optional `check_uid`, and the relaxed scan-extent subclasses). Other pylinac versions may work but have **not** been regression-tested here; bump the pin only after explicit verification and update this subsection (and the comment in `requirements.txt`).

`reportlab` (a pylinac transitive dependency) is also used directly by the viewer to build the compare-mode summary page.

**Integrated in the application**

| Area | What is wired |
|------|----------------|
| **ACR CT** | **`ACRCTForViewer`** (`qa/pylinac_extent_subclasses.py`, aliases **`ACRCTRelaxedExtent`**) via **`pylinac_runner`** by default: relaxes **`CatPhanBase._is_within_image_extent`** to **0 … N−1** vs stock pylinac (interior-only); optional mm tolerance still relaxes **`_ensure_physical_scan_extent`** when **> 0**. **Vanilla pylinac** (options + **`acr_qa_vanilla_pylinac`**) switches to stock **`ACRCT`** with interior-only image bounds and disables tolerance UI; **`pylinac_analysis_profile`** includes **`vanilla_pylinac`** and sets **`relaxed_image_extent`** accordingly. |
| **ACR MRI Large** | **`ACRMRILargeForViewer`** (alias **`ACRMRILargeRelaxedExtent`**) — same runner/worker pattern and **relaxed image extent** as CT by default; **Tools → ACR MRI…**; dialog **`acr_mri_qa_dialog.py`** for echo, low-contrast kwargs (persisted), scan tolerance (hidden when vanilla), **`check_uid`**, **`origin_slice`**. **Vanilla pylinac** uses stock **`ACRMRILarge`**. |
| **Supporting code** | **`QARequest` / `QAResult`** (`src/qa/analysis_types.py`); **`src/qa/worker.py`** (`QThread`); **`src/qa/preflight.py`** stack **geometry warnings** (monotonicity along slice normal) when using in-viewer series; **JSON export** scaffold with reproducibility fields in `main.py`; **lazy import** so the viewer runs if pylinac is missing until the menu action is used. |

**Not integrated yet** (roadmap, other docs, spike-only, or explicitly deferred)

- **CatPhan** (503 / 504 / 600 / 604 / 700), **Quart DVT**, and other **non‑ACR** phantom families described in pylinac’s CBCT/phantom docs.
- **Automatic phantom identification** (metadata/heuristics) and a **single “phantom picker”** that routes to many analyzers—today the user picks **CT vs MRI ACR** via separate menu entries.
- **Deep GUI integration**: showing pylinac **annotated images or ROIs** as **overlays** in the main image viewer; **batch** or **queued** runs; **site-configurable pass/fail thresholds** in the viewer (beyond exporting metrics and optional PDF).
- **Broader pylinac domains** outside this project’s ACR focus—e.g. **Winston–Lutz**, **Picket Fence**, **Starshot**, **VMAT**, **log analysis**, and similar therapy-QA modules—unless/until explicitly scoped.
- **Relaxed image extent + scan-extent tolerance + JSON run profiles** — **shipped**: **`ACRCTForViewer`** / **`ACRMRILargeForViewer`** widen **`_is_within_image_extent`** for default Stage‑1 runs (edge slices allowed). **Vanilla pylinac** opt-out uses stock classes and stock interior-only bounds. Optional **0.5–2.0 mm** still relaxes **`_ensure_physical_scan_extent`** when `QARequest.scan_extent_tolerance_mm > 0` (stock physical check when **0**, and N/A when vanilla); proactive tolerance in **ACR CT** / **ACR MRI** dialogs; **reactive** retry after strict extent failure (skipped when vanilla); **`pylinac_analysis_profile`** includes **`relaxed_image_extent`** and **`vanilla_pylinac`**. Plan: [PYLINAC_SCAN_EXTENT_TOLERANCE_AND_REPRODUCIBILITY_PLAN.md](../plans/PYLINAC_SCAN_EXTENT_TOLERANCE_AND_REPRODUCIBILITY_PLAN.md). Background: [PYLINAC_FLEXIBILITY_AND_WORKAROUNDS.md](PYLINAC_FLEXIBILITY_AND_WORKAROUNDS.md).

### Pylinac docs coverage snapshot (public docs TOC)

Compared against pylinac’s public docs TOC (wording may vary slightly by release; **runtime is pinned to 3.42.0** — see [Verified pylinac package version](#verified-pylinac-package-version)), the app currently wires **ACR CT** and **ACR MRI Large** only. Additional documented areas not currently exposed in DICOMViewerV3 include:

- **Main modules not exposed**: Calibration (TG-51/TRS-398), Starshot, VMAT, CatPhan, "Cheese" phantoms, GE Helios, Quart, Log Analyzer, Picket Fence, Winston-Lutz (single + multi-target), Planar Imaging, Field Profile Analysis, Field Analysis, Nuclear. **Details (tests, inputs, demo data):** [PYLINAC_CATPHAN_AND_NUCLEAR_MODULES.md](PYLINAC_CATPHAN_AND_NUCLEAR_MODULES.md).
- **ACR-class capabilities not yet exposed in UI/runner surface**: zip-based load paths (`from_zip`), broader `analyze(...)` tuning knobs (e.g. x/y/angle and ROI/scale adjustments where supported), and subimage plotting/saving helpers (e.g. `plot_analyzed_subimage`, `save_analyzed_subimage`) as first-class app features.
- **Topic/ancillary tooling not surfaced as app features**: image/gamma/MTF/contrast/noise-power utilities, XIM handling, DICOM conversion helpers, and image/plan generators remain library-level tools rather than integrated user workflows.

**Related:** phased checklist and ordering of near-term work—[PYLINAC_AND_AUTOMATED_QA_STAGE1_PLAN.md](../plans/completed/PYLINAC_AND_AUTOMATED_QA_STAGE1_PLAN.md) (Stage 1 plan; not a duplicate of this status section).

---

## 1. Background: Pylinac and Phantom Types

### 1.1 What pylinac provides

Pylinac is an open‑source Python library for **radiation therapy and imaging QA**. For this project, the most relevant capabilities are:

- **CT / CBCT phantoms**:
  - ACR CT phantom (via its CT modules; ACR is explicitly supported alongside CatPhan/Quart).
  - CatPhan models: 503, 504, 600, 604, 700.
  - Quart DVT and related CT phantoms.
- **MRI phantoms**:
  - ACR MRI phantom (via pylinac’s MRI QA / phantom analysis modules).
  - Similar metric families to CT ACR (geometry, uniformity, low contrast, SNR), but on MR image data and MR‑specific acquisition protocols.
- **Automatic phantom handling**:
  - Automatic phantom localization and registration (translational + rotational).
  - Robust handling of image orientation and offsets.
- **Automated analysis outputs** (vary by phantom type, but typically include):
  - CT number (HU) linearity and calibration.
  - Geometric scaling and size accuracy.
  - High‑contrast resolution (MTF / line pairs).
  - Low‑contrast visibility.
  - Uniformity, noise statistics, and modulation.
- **Reporting**:
  - Plots/summary figures (e.g., analyzed image overlays).
  - PDF reports summarizing metrics and pass/fail criteria.

These capabilities map well to medical physics QA workflows and can sit **on top of** the existing DICOM viewing functionality.

### 1.2 Relevance to DICOMViewerV3

DICOMViewerV3 already provides:
- Robust **DICOM loading and organization** (`DICOMLoader`, `DICOMOrganizer`, `DICOMParser`).
- **Image processing** (`DICOMProcessor`, multi‑frame handling, window/level, projections).
- A rich **PySide6 GUI** (menus, dialogs, overlays, measurement and ROI tools).

Pylinac adds:
- **Domain‑specific QA analysis** of standardized phantoms (ACR CT, CatPhan, etc.).
- **Automated scoring and reporting**, reducing user effort and variability.

Because pylinac is also Python‑based, and DICOMViewerV3 already uses **pydicom**, **numpy**, and **matplotlib**, the dependency and data‑flow alignment is favorable.

---

## 2. Integration Feasibility and Scope

### 2.1 Technical fit

**Current stack:**
- Python 3.9+
- PySide6 (GUI)
- pydicom (DICOM I/O)
- numpy (image arrays)
- matplotlib (histograms)

**Pylinac typical dependencies** (high‑level):
- `pylinac` itself
- `numpy` (already present)
- `pydicom` (already present)
- `matplotlib` (already present)
- `scipy`
- `scikit-image`

From a dependency standpoint, integration mostly means **adding pylinac + SciPy/scikit‑image** to `requirements.txt`, which is low risk.

### 2.2 ACR (CT and MRI) vs. CatPhan in this project

- **Primary target: ACR CT and MRI phantoms**
  - **ACR CT**: Common in clinical CT QA, focusing on HU linearity, geometry, noise, and low‑contrast performance.
  - **ACR MRI**: Widely used for MRI QA, with metrics such as geometric distortion, slice thickness, image uniformity, SNR, ghosting/artefacts, and low‑contrast object visibility.
  - Pylinac provides ACR support via its CT and MRI analysis modules, and both align with well‑recognized ACR criteria.
  - Focusing on ACR CT and MRI first gives broad coverage of cross‑sectional imaging QA using standardized phantoms.

- **Secondary target: CatPhan**
  - Widely used in CBCT and CT QA.
  - Pylinac’s `CatPhan` classes are among its most mature and documented modules.
  - Once an ACR workflow is in place, extending to CatPhan is largely a matter of **swapping the analysis class and phantom‑specific configuration**.

### 2.3 High‑level integration boundaries

**What pylinac will handle:**
- Reading phantom image sets (DICOM folder or list of files).
- Detecting phantom position/orientation.
- Running the analysis (ACR or CatPhan).
- Producing:
  - A metrics object / attributes.
  - Plots and analyzed overlays.
  - Optional PDF reports.

**What DICOMViewerV3 will handle:**
- Selecting which **series** or **folder** to analyze.
- Providing a **GUI workflow** (menu actions, dialogs, progress reporting).
- Displaying **summaries and images** from pylinac.
- Managing **file paths**, export locations, and optional caching.

### 2.4 Reproducibility, JSON export, and non‑vanilla pylinac settings

Every pylinac-backed run should be **auditable**: a physicist or script must be able to tell whether the outcome used **stock pylinac behavior** or **viewer-assisted** behavior (subclasses, tolerances, manual overrides).

**As implemented (2026-04-01)**

- **`build_pylinac_analysis_profile()`** in `src/qa/analysis_types.py` builds the dict; **`pylinac_runner`** and **`worker`** attach **`QAResult.pylinac_analysis_profile`** on success, failure, and missing-input paths.
- **JSON** (`_export_qa_json` in `src/main.py`): top-level **`pylinac_analysis_profile`** with **`schema_version` `1.1`**; **`inputs`** unchanged for backward compatibility.
- **Scan extent:** proactive tolerance from **ACR CT** / **ACR MRI** option dialogs; reactive **`_qa_offer_extent_retry`** after strict extent failure; profile records **`scan_extent_tolerance_mm`**, **`engine`**, **`qa_attempt`**, **`parent_attempt_outcome`** when applicable.
- **Results dialog:** short note when **`vanilla_equivalent`** is false, pointing to JSON.

**Guidance for future extensions**

1. Keep populating the profile from a **single helper** in `src/qa` so CT, MRI, and future analyzers stay consistent.
2. **Vanilla default:** When the user does not opt into relaxations, **`vanilla_equivalent: true`**, **`scan_extent_tolerance_mm: 0`**, **`engine`** = upstream class name (`ACRMRILarge`, `ACRCT`, …).
3. **Any deviation** from stock defaults must appear in the profile, including **`origin_slice`**, **`echo_number`**, **`check_uid`**, future **`analyze()`** tuning, and retry lineage.
4. **Schema bumps:** When adding breaking JSON fields, increment **`schema_version`** and note in **`CHANGELOG.md`**.
5. **PDF / reports:** If added later, mirror the “non‑vanilla” hint when **`vanilla_equivalent`** is false.

**Plan (checklist complete):** [PYLINAC_SCAN_EXTENT_TOLERANCE_AND_REPRODUCIBILITY_PLAN.md](../plans/PYLINAC_SCAN_EXTENT_TOLERANCE_AND_REPRODUCIBILITY_PLAN.md).

### 2.5 ACR CT phantom datasets (`ACRCT`): slices, z‑coverage, and thickness

These notes summarize how **pylinac** treats **Gammex 464 / ACR CT** stacks so integrators can preflight series from DICOM Viewer V3. Authoritative API and offset constants: [pylinac ACR phantoms](https://pylinac.readthedocs.io/en/latest/acr.html).

**No fixed slice count for CT.** Pylinac does **not** document a required “exact *N* slices” for **`ACRCT`** (unlike **ACR MRI Large**, where the same module doc states **11 axial slices**, or **12** with sagittal, per the MRI guidance). In source, **`ACRCT`** sets **`min_num_images = 4`**, which is a **bare minimum** for the loader—not a claim that four slices suffice for meaningful QA.

**Z coverage (scan range) matters, not slice count alone.** After **`ACRCT`** finds the **HU linearity (module 1) origin slice**, it maps other modules using **fixed offsets in mm** along the stack from that origin (defaults: **low contrast +30 mm**, **uniformity +70 mm**, **spatial resolution +100 mm**—see *Customizing module offsets* in the pylinac ACR page). The series must include slices whose **positions** span **at least through ~100 mm beyond the origin** (plus tolerance so the nearest slice to each target *z* is correct). **Thinner collimation** ⇒ **more slices** over the same physical length; **thicker slices** ⇒ **fewer slices**, but the **phantom length** must still be covered. Missing ends, wrong order, or large gaps usually break localization or assign the wrong slice to a module.

**Nominal slice thickness:** Pylinac does **not** impose a single required **reconstruction thickness** for CT ACR in the public API; it **analyzes** the supplied volume. **Accreditation scanning** still follows **ACR / site protocol** (technique), which is separate from pylinac’s mechanics.

**`origin_slice`:** If automatic HU‑module detection fails, **`ACRCT.analyze(..., origin_slice=...)`** can pass the **index** of the HU linearity module slice—useful for edge cases when wiring the viewer.

**Clinical alignment:** ACR CT accreditation imaging is described as **contiguous coverage through the phantom** (module 1 → module 4). That matches the **z‑span** pylinac needs for its **offset‑based** module mapping; do not rely on **`min_num_images = 4`** as a QA standard.

**MRI contrast (brief):** For **`ACRMRILarge`**, treat the **11/12‑slice** and **sagittal / `check_uid`** rules in pylinac’s MRI section as **harder prerequisites** than CT slice count when validating datasets.

**Flexibility beyond stock pylinac** (tolerant scan-extent checks, offset tweaks, parameter surface): see [PYLINAC_FLEXIBILITY_AND_WORKAROUNDS.md](PYLINAC_FLEXIBILITY_AND_WORKAROUNDS.md).

---

## 3. Multi‑Phase Integration Plan (Overview)

This section gives the **high‑level phases**; details and PoC flows are in Section 4.

### Phase 1 – Proof‑of‑Concept (ACR‑First, Minimal UI)

**Goal:** Demonstrate end‑to‑end ACR analysis (CT and MRI) from inside DICOMViewerV3 with minimal new UI.

- **Assume explicit human choices in Phase 1:** user confirms **phantom type / modality**, **data scope** (active series or folder), and any **slice or echo** needed when a single stack is ambiguous—see **Progressive automation** above; avoid blocking the PoC on auto‑detection.
- Add optional dependencies (`pylinac`, `scipy`, `scikit-image`).
- Add a **Tools → ACR Phantom Analysis (pylinac)** menu action.
- For the currently loaded **ACR CT or MRI phantom series**, or via a simple folder picker:
  - Run pylinac ACR analysis for the appropriate modality (CT vs MRI).
  - Show a modal dialog summarizing key metrics and a pass/fail indication.
  - Allow the user to **export a PDF report** produced by pylinac.
- Keep scope intentionally limited:
  - ACR CT and ACR MRI only (CatPhan deferred to Phase 2).
  - One series at a time.
  - Simple, text‑based results + optional single image preview.

### Phase 2 – Expanded Phantom Support (CatPhan + Flexible Detection)

**Goal:** Support multiple CT/CBCT phantom types (ACR and CatPhan at minimum) with more flexibility and UI polish.

- Add a **phantom type selector** (ACR, CatPhan 504, CatPhan 604, etc.) with optional **auto‑detection heuristics** based on DICOM metadata and pylinac inspection.
- Support both:
  - Single‑series / single‑folder analysis (like Phase 1).
  - Selection of multiple series for **queued / batch analysis**.
- Provide a richer **results dialog**:
  - Phantom‑specific metric sections.
  - Visual indicators (green/red) for thresholds.
  - Direct preview of pylinac’s analyzed overlay image.
- Structure the code into a **dedicated phantom analysis package** within `src/tools`.

### Phase 3 – Advanced QA Workflows and Integration

**Goal:** Turn pylinac into a more integrated QA subsystem, while keeping it optional and modular.

- Add an **“Analysis History”** concept (lightweight, could be JSON files in a user‑selectable directory).
- Enable **batch QA runs** from a folder of studies (e.g., nightly or periodic QA).
- Optional **overlay integration**:
  - Display certain pylinac results as overlay annotations within the main viewer (e.g., region markers, measured values).
- Optional **protocol customization**:
  - GUI to adjust pass/fail thresholds or choose which pylinac tests to run.
- Prepare for possible integration with external systems (e.g., DICOM servers like Orthanc, similar in spirit to pyqaserver, but this can be deferred).

---

## 4. Proof‑of‑Concept Integration (Phase 1 – Detailed)

This section gives a **more concrete design** for the initial ACR‑focused PoC (CT and MRI), plus how CatPhan can be added with minimal extra work.

### 4.1 Scope and Constraints

- **Primary phantoms**: ACR CT phantom and ACR MRI phantom.
- **Secondary phantom (optional extension)**: CatPhan (e.g., `CatPhan504`).
- **Data source**:
  - Preferred: The current series (set of DICOM files) already loaded in DICOMViewerV3.
  - Fallback: A folder chooser that points pylinac to a directory of DICOMs.
- **UI constraints**:
  - Keep it simple: a new menu action + one analysis dialog.
  - Avoid complex state management or long‑running background processes beyond what’s necessary.

### 4.2 Dependencies and Configuration

**Requirements additions (initial proposal):**

```text
pylinac              # main QA library (pin after initial compatibility test)
scipy                # numeric routines used by pylinac
scikit-image         # image processing utilities used by pylinac
```

These should be added to `requirements.txt` once we commit to implementing integration.

**Runtime checks:**
- The PoC should **gracefully handle missing pylinac**:
  - Try to import pylinac when the user triggers the analysis.
  - If import fails, show a dialog explaining how to install the optional dependencies.

### 4.3 Proposed Code Structure (PoC)

Without changing existing behavior, we can introduce a small, focused set of new modules:

```text
src/
  qa/
    __init__.py
    analysis_types.py             # dataclasses for requests/results/errors
    phantom_series_selector.py    # resolve active series into ordered file paths
    pylinac_runner.py             # worker-safe pylinac orchestration entrypoints
    pylinac_acr.py                # ACR CT/MRI-specific analysis adapters
    pylinac_catphan.py            # CatPhan adapters (Phase 2)
    qa_thresholds.py              # configurable pass/fail thresholds
  gui/
    dialogs/
      qa_results_dialog.py        # UI presentation only (no direct pylinac imports)
```

**Key ideas:**
- Keep all QA analysis code in a dedicated `src/qa` package so it can evolve independently from ROI/metadata/fusion logic.
- `pylinac_runner.py`:
  - Encapsulates imports and version compatibility checks.
  - Provides one stable entrypoint used by UI/controllers.
- `analysis_types.py`:
  - Defines a normalized result schema (`status`, `metrics`, `warnings`, `artifacts`) independent of pylinac internals.
- `qa_results_dialog.py`:
  - Pure UI layer; no direct pylinac calls.
  - Presents normalized metrics and report/export actions.

This keeps pylinac‑specific logic in **one compartmentalized area**, making it easier to maintain or disable.

### 4.4 ACR PoC Workflow (User Flow)

1. **User selects ACR series**
   - Either:
     - The user has opened a CT series known to be an ACR phantom, and it is the **active series** in the viewer, or
     - The user chooses “Tools → ACR Phantom Analysis (pylinac)” and is prompted to select a folder containing the ACR DICOMs.

2. **User triggers analysis**
   - A new menu action, for example:
     - Main menu: `Tools → ACR Phantom Analysis (pylinac)…`
   - This invokes a coordinator method (e.g., on `MainWindow` or a new small controller class) that:
     - Collects the relevant DICOM file paths.
     - Calls into `pylinac_acr_wrapper.run_acr_analysis(...)`.

3. **Background execution**
   - The PoC should:
     - Run pylinac in a **background thread or worker** to keep the GUI responsive.
     - Provide a simple progress indicator (spinner or “Analyzing…” message) in a small modal/progress dialog.

4. **Pylinac analysis (inside `pylinac_acr.py`)**
   - Conceptually:

```python
def run_acr_analysis(dicom_paths: list[str], modality: str) -> ACRAnalysisResult:
    # Import classes lazily so QA remains optional.
    from pylinac import ACRCT, ACRMRILarge  # class names/version support must be validated

    # pylinac can typically take either a folder path or a list of files
    analyzer_cls = ACRCT if modality == "CT" else ACRMRILarge
    acr = analyzer_cls(dicom_paths)  # or analyzer_cls.from_folder(folder_path)
    acr.analyze()             # perform the main analysis

    # extract useful metrics (names depend on pylinac API)
    metrics = extract_metrics(acr, modality=modality)

    # optional: generate a PDF report to a temp path
    pdf_path = None
    try:
        pdf_path = acr.publish_pdf("acr_report_temp.pdf")
    except Exception:
        pdf_path = None

    return ACRAnalysisResult(
        success=True,
        metrics=metrics,
        pdf_path=pdf_path,
        warnings=acr.warnings if hasattr(acr, "warnings") else []
    )
```

> **Important:** Pylinac class names/attributes vary across versions. Before implementation, lock a tested pylinac version in `requirements.txt`, then update adapter code to match that exact API.

5. **Displaying results**
   - When the analysis completes, the main thread:
     - Receives an `ACRAnalysisResult` object (or an error).
     - Opens `phantom_analysis_dialog.py` with:
       - A table or structured list of metrics.
       - Pass/fail or warning status highlights.
       - If a PDF was generated, an **“Open Report”** or **“Save Report As…”** button.
       - Optional: a small preview image from pylinac’s analyzed overlay (if easily accessible).

6. **Error handling**
   - If pylinac is not installed:
     - Show a clear message: “Pylinac is not installed. To enable phantom analysis, install the optional QA dependencies…”
   - If analysis fails (e.g., non‑ACR data, missing slices):
     - Show the error reason and, if possible, pylinac’s hints (e.g., phantom not detected).

### 4.5 CatPhan PoC Extension

Once the ACR PoC is working, a **minimal CatPhan extension** can be introduced with relatively small incremental effort:

- Add `pylinac_catphan_wrapper.py`:

```python
def run_catphan_analysis(dicom_paths: list[str], model: str = "504") -> CatPhanAnalysisResult:
    from pylinac import CatPhan503, CatPhan504, CatPhan600, CatPhan604, CatPhan700

    model_class_map = {
        "503": CatPhan503,
        "504": CatPhan504,
        "600": CatPhan600,
        "604": CatPhan604,
        "700": CatPhan700,
    }

    catphan_cls = model_class_map[model]
    cp = catphan_cls(dicom_paths)  # or cp = catphan_cls.from_folder(folder_path)
    cp.analyze()

    metrics = {
        "hu_linearity": cp.hu_linearity,       # example
        "scaling": cp.scaling,
        "mtf": cp.mtf,                         # high‑contrast resolution
        "uniformity": cp.uniformity,
        "low_contrast": cp.low_contrast,
    }

    pdf_path = None
    try:
        pdf_path = cp.publish_pdf("catphan_report_temp.pdf")
    except Exception:
        pdf_path = None

    return CatPhanAnalysisResult(
        success=True,
        metrics=metrics,
        pdf_path=pdf_path,
        warnings=[]
    )
```

- UI changes for PoC can stay minimal:
  - A separate menu action (`Tools → CatPhan Analysis (pylinac)…`) **or**
  - A phantom type dropdown in the same analysis dialog.

This keeps the ACR‑first spirit while quickly adding CatPhan value for users who have those phantoms available.

### 4.6 Suggested Tests for PoC

To validate the PoC in a controlled way:

- **Functional tests**
  - Use known ACR DICOM datasets:
    - Verify that analysis completes without exceptions.
    - Confirm metrics are reasonable and stable across runs.
    - Confirm that a PDF report can be generated and opened externally.
  - Repeat with one or more CatPhan datasets once that extension is added.

- **UI/UX tests**
  - Confirm the new menu action appears and is disabled or hidden when no appropriate study is loaded, if applicable.
  - Ensure the viewer remains responsive while analysis runs.
  - Confirm that error messages are clear when:
    - pylinac is missing,
    - data is not recognized as an ACR or CatPhan phantom,
    - or required slices are missing.

- **Performance sanity checks**
  - Time the analysis for typical ACR and CatPhan datasets; verify it is acceptable for interactive use (seconds, not minutes, in normal scenarios).

---

## 6. Concrete Integration Observations and Suggestions

1. **Use active-series identity, not only folder browsing**
   - The viewer already tracks focused subwindows and active series. QA entrypoints should consume the same active-series abstraction used for measurement/overlay workflows, then resolve ordered source files from existing DICOM loading metadata.
   - Suggestion: expose a small helper in `DICOMViewerApp` (or a thin controller) returning `(series_uid, modality, ordered_file_paths)`.

2. **Normalize orientation and spacing before handing data to pylinac**
   - Some QA failures are caused by slice order/orientation mismatches rather than phantom content.
   - Suggestion: preflight checks should validate monotonic slice position and consistent pixel spacing/slice thickness; if inconsistent, surface a warning and offer "continue anyway".

3. **Separate "analysis physics" from "acceptance criteria"**
   - Pylinac calculates metrics; local clinics often apply site-specific tolerance thresholds.
   - Suggestion: store thresholds in a local config (`qa_thresholds.py` + config persistence), and evaluate pass/fail in-app against that configuration rather than hard-coding logic in pylinac adapters.

4. **Report reproducibility metadata**
   - QA trend utility depends on reproducibility.
   - Suggestion: every saved result should include analyzer version (`pylinac.__version__`), app version (`src/version.py`), phantom type, and acquisition date/time to avoid ambiguous trend comparisons.

5. **Avoid direct GUI-thread analysis calls**
   - Phantom analysis can be CPU-heavy and occasionally slow for large studies.
   - Suggestion: use a worker thread with explicit cancellation support and deterministic UI states (`idle -> running -> complete/failed`), reusing existing progress-management patterns where possible.

6. **Start with deterministic export outputs**
   - A minimal but useful first deliverable is structured JSON + optional PDF.
   - Suggestion: export machine-readable metrics (`.json`) alongside PDF from day one; this enables trend graphs and downstream integrations without reprocessing.

7. **Progressive automation**
   - Ship a **thin, manual‑driven** path first (phantom preset, series, slice/test selection). Defer **auto phantom ID**, **full‑suite single‑click**, and **batch pipelines** until wrappers and exports are stable—see the opening **Progressive automation** subsection.

---

## 7. Immediate Implementation Milestones (Practical Order)

- **Milestone A:** dependency spike branch, verify pylinac imports and one CT + one MRI sample analysis from a standalone script.
- **Milestone B:** add `src/qa` package with normalized result dataclasses and a single `run_acr_analysis` entrypoint.
- **Milestone C:** wire one menu action and results dialog; support active series + folder fallback.
- **Milestone D:** add JSON/PDF export and a small set of preflight validations with clear user-facing warnings.
- **Milestone E:** add CatPhan model selection and adapters once ACR workflow is stable.
- **Milestone F (later):** optional auto‑detection of phantom type, recommended slices, and **full automated analysis suite** / batch pipeline—built incrementally on the manual‑first UI.

---

## 5. Later Phases (Brief Notes)

After a successful PoC, the following enhancements can be considered:

- **Phase 2 details**
  - Auto‑detection of phantom type (ACR vs CatPhan vs Quart) with a manual override.
  - A richer results dialog with tabs for:
    - Overview metrics,
    - Per‑module details (e.g., slices/modules within the phantom),
    - Embedded thumbnails of pylinac’s annotated images.
  - Ability to queue multiple series or folders for sequential analysis.

- **Phase 3 details**
  - Lightweight analysis history (JSON or CSV) storing metrics, timestamps, and pass/fail results.
  - Optional overlay integration that maps pylinac‑identified regions back to the displayed DICOM images using existing overlay/annotation mechanisms.
  - Hooks for external systems (e.g., running analysis on studies pulled from a DICOM server, or exporting results in a standardized format).

These later phases should build directly on the **PoC structure** described above, preserving:
- Clear separation between pylinac wrappers and the main GUI code.
- Optionality of pylinac (the viewer still functions without it).
- Testable, well‑defined interfaces between components.



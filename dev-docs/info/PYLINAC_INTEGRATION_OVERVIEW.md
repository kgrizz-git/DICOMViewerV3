## Pylinac Integration for Phantom QA (ACR Focus, CatPhan Aware)

This document outlines how **pylinac** could be integrated into DICOM Viewer V3 to provide **automated QA analysis of phantoms**, with a primary focus on **ACR CT/CBCT and MRI phantoms** and secondary support for **CatPhan** models.

The goals are:
- **Leverage pylinac** for robust, validated phantom analysis rather than re‑implementing QA physics.
- **Keep DICOMViewerV3 modular**: pylinac is an optional analysis backend, not a core dependency for basic viewing.
- **Provide a clear multi‑phase roadmap**: from proof‑of‑concept (PoC) to advanced QA workflows.

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

---

## 3. Multi‑Phase Integration Plan (Overview)

This section gives the **high‑level phases**; details and PoC flows are in Section 4.

### Phase 1 – Proof‑of‑Concept (ACR‑First, Minimal UI)

**Goal:** Demonstrate end‑to‑end ACR analysis (CT and MRI) from inside DICOMViewerV3 with minimal new UI.

- Add optional dependencies (`pylinac`, `scipy`, `scikit-image`).
- Add a **Tools → ACR Phantom Analysis (pylinac)** menu action.
- For the currently loaded **ACR CT or MRI phantom series**, or via a simple folder picker:
  - Run pylinac ACR analysis for the appropriate modality (CT vs MRI).
  - Show a modal dialog summarizing key metrics and a pass/fail indication.
  - Allow the user to **export a PDF report** produced by pylinac.
- Keep scope intentionally limited:
  - ACR CT only.
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

**Requirements additions (conceptual):**

```text
pylinac>=3.0.0        # main QA library
scipy>=1.9.0          # numeric routines required by pylinac
scikit-image>=0.19.0  # image processing utilities used by pylinac
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
  tools/
    phantom_analysis/
      __init__.py
      pylinac_acr_wrapper.py      # ACR‑specific pylinac integration
      pylinac_catphan_wrapper.py  # CatPhan‑specific integration (PoC or Phase 2)
      common.py                   # Shared helpers (path handling, error processing)
  gui/
    dialogs/
      phantom_analysis_dialog.py  # UI to show metrics/results and export options
```

**Key ideas:**
- `pylinac_acr_wrapper.py`:
  - Encapsulate pylinac imports and usage for ACR analysis.
  - Provide a **simple function/API** that takes a list of DICOM file paths or a directory and returns:
    - A structured results object (metrics).
    - Optionally, a temporary path to a generated PDF or image(s).
- `phantom_analysis_dialog.py`:
  - Pure UI layer: display ACR metrics, allow user to export PDF, and handle error messages.
  - No direct pylinac calls—those go through the wrapper.

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

4. **Pylinac analysis (inside `pylinac_acr_wrapper`)**
   - Conceptually:

```python
def run_acr_analysis(dicom_paths: list[str]) -> ACRAnalysisResult:
    from pylinac import ACRCT  # example class; exact class may differ per pylinac version

    # pylinac can typically take either a folder path or a list of files
    acr = ACRCT(dicom_paths)  # or ACRCT.from_folder(folder_path)
    acr.analyze()             # perform the main analysis

    # extract useful metrics (names depend on pylinac API)
    metrics = {
        "hu_linearity": acr.hu_linearity,          # example
        "geometry": acr.geometry,                  # e.g., size or scaling metrics
        "uniformity": acr.uniformity,              # center vs periphery HU
        "noise": acr.noise,                        # noise metrics
        "low_contrast": acr.low_contrast          # number of visible low‑contrast objects
    }

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

> **Note:** The specific class names and attributes (e.g., `ACRCT`, `hu_linearity`) depend on the pylinac version and its ACR API; the above is **conceptual** and will need to be aligned with the actual pylinac documentation and source.

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
    from pylinac import CatPhan504, CatPhan604, CatPhan700  # etc.

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



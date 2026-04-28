# PyLinac CatPhan (CT/CBCT) and Nuclear (NM/SPECT) modules

**Purpose:** Summarize upstream **pylinac** capabilities that are **not** wired into DICOM Viewer V3 today, so integrators know **what analyses exist**, **what inputs they expect**, and **where demo or reference data comes from**.

**Primary references (public docs):**

- [CatPhan / CT module](https://pylinac.readthedocs.io/en/latest/cbct.html) (`pylinac.ct`)
- [Nuclear module](https://pylinac.readthedocs.io/en/latest/nuclear.html) (`pylinac.nuclear`)
- [Quart DVT](https://pylinac.readthedocs.io/en/latest/quart.html) (`pylinac.quart`)

**Version note:** This repository pins **`pylinac==3.43.2`** in `requirements.txt` (see [PYLINAC_INTEGRATION_OVERVIEW.md](PYLINAC_INTEGRATION_OVERVIEW.md)). Public ReadTheDocs pages may show a slightly newer release; confirm constructor and `analyze()` signatures against the installed package when implementing.

---

## 1. CatPhan and related CT phantom classes (`pylinac.ct`, `QuartDVT`)

### 1.1 Role of the module

The **CT / CatPhan** stack loads **CT-class DICOM** volumes (conventional CT or linac CBCT QA acquisitions), **registers** the phantom (translation and rotation; moderate yaw/pitch allowed per docs), and runs **phantom-specific sub-modules** (CTP inserts) to produce HU linearity, MTF, uniformity, low-contrast, slice thickness, optional noise power spectrum (NPS), and geometry-style checks, depending on model.

Pylinac documents support for **CatPhan 503, 504, 600, 604, 700**, **Quart DVT**, and **ACR CT** within the same broad “CBCT/CT QA” workflow (ACR CT is a separate class family; this viewer already integrates ACR CT/MR via `ACRCT` / `ACRMRILarge` — see the integration overview).

### 1.2 Concrete classes (typical constructor pattern)

| Class | Phantom / device | Notes |
|--------|------------------|--------|
| `CatPhan503` | CatPhan 503 | Older model; subset of modules vs 504. |
| `CatPhan504` | CatPhan 504 | Common reference; docs use it for examples. |
| `CatPhan600` | CatPhan 600 | Extra materials (e.g. iodine vial) per docs. |
| `CatPhan604` | CatPhan 604 | Adds bone-simulating inserts (documented HU override keys). |
| `CatPhan700` | CatPhan 700 | Different CTP naming (e.g. CTP404CP700, CTP528CP700); **no upstream `from_demo_images` ZIP** in current upstream `ct.py` (demo URL not set). |
| `QuartDVT` | Quart DVT | Implemented in `pylinac.quart`; same “folder / zip / demo” usage pattern as CatPhan. |

Each class inherits **`CatPhanBase`** patterns: load → `analyze(...)` → `results()` / `results_data()` / plots / `publish_pdf(...)`.

### 1.3 What analyses are performed (conceptual map)

Exact slice modules depend on **phantom model**. The public CatPhan overview describes the **504-style** decomposition; other models map analogous inserts (see class docstrings in upstream `ct.py` and the [CatPhan documentation](https://pylinac.readthedocs.io/en/latest/cbct.html)).

Typical **CatPhan 504**-class pipeline (names may differ slightly by version):

| Area | Phantom module (common label) | What is computed (high level) |
|------|------------------------------|------------------------------|
| **HU linearity & scaling** | CTP404 (HU module) | ROI HU values for known materials; pass/fail vs expected HU table; **image scaling** from geometry of known distances. |
| **Slice thickness** | CTP404 (ramps) | Measured slice thickness from ramp geometry; docs note optional **multi-slice averaging** for thin, noisy scans (`thickness_slice_straddle` / auto behavior). |
| **High-contrast resolution / MTF** | CTP528 | Line-pair region → **MTF** (and relative MTF helpers in docs). |
| **Uniformity** | CTP486 | Uniformity metrics across peripheral and central ROIs. |
| **Low contrast** | CTP515 | Low-contrast object “visibility” / scoring (algorithm options documented under low-contrast topics). |
| **Geometry** | Phantom-dependent | e.g. geometric line lengths / module spacing checks where applicable. |
| **NPS (optional / regulatory)** | CTP486 (FFT-based) | Noise power spectrum summary on uniformity module (added in newer pylinac; see docs § Noise Power Spectrum). |

**CatPhan 700** (per upstream class docstring): uniformity (**CTP486** / **CTP712**), high-contrast spatial resolution (**CTP714**), image scaling and HU linearity (**CTP404CP700** / **CTP682**), low contrast (**CTP515**), and slice geometry (**CTP721**). The implementation maps these to internal **`CTP*CP700`** slice-module classes in `ct.py` (offsets in millimeters along the stack).

**Important:** Default pylinac behavior expects the **full phantom module set** to be present in the scan; partial coverage or missing modules usually **errors** unless you **subclass** and adjust the `modules` mapping (documented under “Partial scans” / customizing offsets in the CatPhan docs).

### 1.4 Expected inputs (data and API)

**Imaging input**

- **Directory** containing CT DICOM slices for one acquisition, **or**
- **ZIP archive** of those DICOM files (`from_zip`), **or**
- **HTTPS URL** to a `.zip` (`from_url`), **or**
- **Bundled demo** (`from_demo_images` / `run_demo`) where the class defines `_demo_url` (see §3).

**Typical Python usage**

```python
from pylinac import CatPhan504

cbct = CatPhan504(r"C:\path\to\dicom\folder")
# or: CatPhan504.from_zip(r"C:\path\to\archive.zip")
cbct.analyze()
cbct.plot_analyzed_image()
```

**Common constructor / analysis parameters** (see upstream `analyze()` for the full, versioned list):

- **`check_uid`**: whether multiple Series/SOP UIDs in the folder should raise (stricter QA hygiene).
- **`expected_hu_values`**: optional dict override of nominal HU per material (per-material keys documented for 503/504/600/604).
- **ROI / registration tweaks:** `x_adjustment`, `y_adjustment`, `angle_adjustment`, `roi_size_factor`, `scaling_factor` (global shifts); advanced users may subclass module offsets.
- **`thickness_slice_straddle`**: control averaging across slices for slice-thickness measurement.

**Acquisition expectations** (from CatPhan docs — paraphrased):

- Field of view must **fully contain** the phantom with margin; phantom **must not touch** FOV edges or couch/high-HU structures that confuse segmentation.
- **All required modules** should be included in the scan volume; incomplete scans can yield misleading or failing analysis.
- For CBCT, align the scan range to capture **inferior modules**, not only the fiducial “white dot” region.

**Output**

- Text summaries (`results()`), structured results (`results_data()` / `as_dict=True`), matplotlib composite plots, optional **PDF** via `publish_pdf`, and per-submodule plots (e.g. `plot_analyzed_subimage(...)`).

---

## 2. Nuclear module (`pylinac.nuclear`)

### 2.1 Role of the module

**`pylinac.nuclear`** is documented as a **re-implementation of the IAEA NMQC ImageJ toolkit**, aligned with **IAEA QA for gamma cameras / SPECT** (see references on the [Nuclear](https://pylinac.readthedocs.io/en/latest/nuclear.html) page: NMQC operator manual, IAEA publication No. 6 for SPECT QA).

It is **not** the same subsystem as **`ACRCT` / `ACRMRILarge`**. Those classes implement **ACR CT 464** and **ACR Large MRI** phantom tests. Nuclear medicine **accreditation-style** SPECT QA (e.g. Jaszczak-based acquisitions) may use similar **phantoms**, but pylinac exposes them as **IAEA/NMQC-style algorithm classes** (planar / tomographic uniformity, contrast, sensitivity, etc.), not as a single “ACR NM module.”

### 2.2 Classes and what each test does

| Class | Typical modality | What the test does (summary) |
|--------|------------------|------------------------------|
| **`MaxCountRate`** | Dynamic MUGA / gated SPECT-style data | Per-frame **total counts** → maximum **count rate** vs time; plots count rate vs frame. |
| **`PlanarUniformity`** | Planar gamma camera | Per-frame **UFOV** and **CFOV**; **integral** and **differential** uniformity (IAEA-style smoothing, thresholding, erosion ratios). |
| **`CenterOfRotation`** | SPECT COR QC | Measures **detector orbit deviation** vs expected rotation (sinusoidal fit; residuals). |
| **`TomographicResolution`** | SPECT | 3D centroid → **1D profiles** along x/y/z → **Gaussian fit** → **FWHM / FWTM** (from fit parameters, not empirical MTF from line pairs). |
| **`SimpleSensitivity`** | SPECT sensitivity | **Sensitivity** from phantom counts vs administered activity (`activity_mbq`, **`Nuclide`** enum); optional **background** DICOM series. |
| **`FourBarResolution`** | Planar (single frame used) | **Four-bar** pattern: dual-Gaussian fits along axes → **FWHM/FWTM** and effective **pixel size** from known bar separation. |
| **`QuadrantResolution`** | Planar quadrant bar | Four circular ROIs on bar quadrants → **MTF / FWHM / lp/mm** via statistical-moment equations (Hander et al., cited in docs). |
| **`TomographicUniformity`** | SPECT (e.g. **Jaszczak**-type cylinder) | Collapse selected frames to **2D** (mean along z), then planar-style uniformity; adds **center ROI** and **center-to-edge** ratio; docs note default FOV ratios are close to NMQC defaults for **Jaszczak**. |
| **`TomographicContrast`** | SPECT cold spheres | **Cold-sphere contrast** vs background; requires **`sphere_diameters_mm`** and **`sphere_angles`**; automatically finds **uniformity** and **sphere** frames per algorithm notes. |

### 2.3 Expected inputs

**Universal**

- **Path to a DICOM file** (or path-like) that contains the **pixel data** appropriate to the test:
  - Most classes expect **NM image** conventions (counts, multi-frame dynamic or tomographic data as described in each section of the Nuclear docs).
  - **`FourBarResolution`** explicitly uses **only the first frame** if multiple are present.

**`SimpleSensitivity`**

- Phantom acquisition path; optional **`background_path`** second DICOM.
- **`analyze(activity_mbq=..., nuclide=Nuclide.Tc99m)`** (or other supported nuclide).

**`PlanarUniformity` / `TomographicUniformity`**

- **`analyze(...)`** parameters include UFOV/CFOV **ratios**, sliding **window_size** for differential uniformity, **threshold** fraction of mean, and (tomographic) **`center_ratio`** and frame selection.

**`TomographicContrast`**

- **`analyze(sphere_diameters_mm=(...), sphere_angles=(...), ufov_ratio=..., search_window_px=..., search_slices=...)`** — user must supply geometry matching the phantom acquisition; pylinac searches locally for optimal sphere centers.

**Outputs**

- `analyze()`, `results_data()`, string `results()`, matplotlib `plot()` where implemented, and typed result objects listed in the [Nuclear API](https://pylinac.readthedocs.io/en/latest/nuclear.html#api).

**Upstream disclaimer:** Nuclear docs state the toolkit is meant as a **Python alternative to ImageJ NMQC** for users who prefer Python (e.g. RadMachine); clinical validation remains the site’s responsibility.

---

## 3. Example and demo data

### 3.1 How pylinac distributes demos (not always in the Git repo)

The **GitHub source tree** does **not** necessarily ship large DICOM/ZIP phantoms under `pylinac/files/` (that folder is mainly branding assets). Instead, **`pylinac.core.io.retrieve_demo_file`** downloads lazily from public cloud storage:

- **Base URL:** `https://storage.googleapis.com/pylinac_demo_files/`
- **Local cache:** `<site-packages>/pylinac/demo_files/<filename>` (created on first use)

So “official” example data is **maintained by the pylinac project** on that bucket; first invocation of `from_demo_images()` **downloads** the ZIP once.

### 3.2 CatPhan / Quart — known demo archive names (upstream `master` branch)

These filenames appear in **`pylinac/ct.py`** and **`pylinac/quart.py`** as `_demo_url` values:

| Demo ZIP (bucket object) | Used by |
|---------------------------|---------|
| `CatPhan503.zip` | `CatPhan503.from_demo_images()` / `run_demo()` |
| `CatPhan504.zip` | `CatPhan504` (documented example: *Varian high-quality head scan*) |
| `CatPhan600.zip` | `CatPhan600` |
| `CatPhan604.zip` | `CatPhan604` |
| `quart.zip` | `QuartDVT` |

**`CatPhan700`:** upstream class **does not set `_demo_url`** (demo line commented); expect **no** `from_demo_images()` for 700 — use a real clinic acquisition or a shared QA ZIP.

### 3.3 Nuclear — reference data from IAEA / NMQC

Pylinac’s [Nuclear](https://pylinac.readthedocs.io/en/latest/nuclear.html) page cites the **same sample stack** the **IAEA NMQC ImageJ plugins** publish for training and regression: a ZIP of **simulated / reference images** (DICOM and related files) maintained on the IAEA Human Health server — **not** on the `pylinac_demo_files` Google bucket used for CatPhan.

**Direct link (as in pylinac Nuclear docs, reference [[4]]):**

`https://humanhealth.iaea.org/HHW/MedicalPhysics/NuclearMedicine/QualityAssurance/NMQC-Plugins/Simulated_images.zip`

That archive is meant for users of the **NMQC** workflow; **`pylinac.nuclear`** documents its algorithms against those images where applicable. Terms of use follow the **IAEA** / NMQC distribution, not this viewer project.

**Why there is no `run_demo()` for Nuclear in the same sense as CatPhan:** the public Nuclear chapter does not ship a one-call `TomographicUniformity.run_demo()` that downloads a pinned file from `pylinac_demo_files` like **`CatPhan504.run_demo()`**. You normally pass **your own** NM DICOM path(s) or use the **IAEA ZIP** above.

**About `jrkerns/pylinac` and `tests/`:** the upstream repo runs **automated tests** under `tests/`. Those tests **may** reference additional small files (downloaded at test time, or stored under the repo). That sentence in our overview was only a **practical caution**: if you ever copy files out of upstream **`tests/`** to build your own sample dataset or ship them elsewhere, **verify each file’s origin and license** first. It is **not** a requirement for day-to-day use, and **most users should rely on the IAEA `Simulated_images.zip` or clinic acquisitions**, not on scraping the pylinac test tree.

### 3.4 Quick smoke commands (developer environment)

After installing the project venv and **pylinac**:

```text
python -c "from pylinac import CatPhan504; CatPhan504.run_demo()"
```

```text
python -c "from pylinac import QuartDVT; QuartDVT.run_demo()"
```

Nuclear example (requires a suitable NM DICOM path):

```text
python -c "from pylinac.nuclear import PlanarUniformity; PlanarUniformity(r'C:\\path\\to\\planar.dcm').analyze(); print('ok')"
```

---

## 4. Relation to DICOM Viewer V3

CatPhan, Quart, and Nuclear analyses remain **library-level** options for this product until explicitly scoped in `src/qa` and the Tools menu. For current integration status, see [PYLINAC_INTEGRATION_OVERVIEW.md](PYLINAC_INTEGRATION_OVERVIEW.md).

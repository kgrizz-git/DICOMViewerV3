# User guide — ACR phantom QA (pylinac)

**Last updated:** 2026-06-12

The viewer can run **automated ACR phantom analysis** using the **pylinac** library (pinned in `requirements.txt`, currently **3.43.2**). This is **optional QA tooling**; the app still runs if pylinac is missing until you use these menus.

## Where to find it

| Menu | Action |
|------|--------|
| **Tools → Automated QA** | **ACR CT Phantom (pylinac)…** |
| **Tools → Automated QA** | **ACR MRI Phantom (pylinac)…** |
| **Tools → Automated QA** | **Nuclear Medicine QC (pylinac)…** |

## Inputs

- **Focused series:** The analysis prefers **slice files from the currently focused viewer** (ordered stack).  
- **Folder fallback:** If that is not available, you can point to a **folder** of DICOM slices when prompted.

**Preflight:** The app may warn about stack geometry (e.g. slice spacing along the normal) before running.

## During and after the run

- Work runs on a **background thread**; a progress dialog is shown.
- Results include **metrics**, **warnings/errors**, and optional **JSON or CSV** export with reproducibility fields (pylinac version, analysis profile). The save dialog offers both formats; choose by the file extension (`.json` writes the full document, `.csv` writes a flat `metric,value` summary). Exported JSON records **vanilla pylinac** (stock **ACRCT** / **ACRMRILarge** vs viewer integration classes) under **`run.vanilla_pylinac`**, **`inputs.vanilla_pylinac`**, and **`pylinac_analysis_profile.vanilla_pylinac`**.
- **PDF:** You can choose an output path for pylinac-generated PDFs where the flow supports it. After a **successful single** CT/MRI run, the app asks whether to **open that PDF** (compare mode still uses **Open PDF** on the results window).

### ACR MRI options (summary)

The MRI dialog can include:

- **Echo** and related acquisition choices (as exposed by the dialog).
- **Low-contrast detectability:** method (e.g. Weber), **visibility threshold**, **sanity multiplier** (persisted in config).
- **Compare mode:** run up to **three** low-contrast configurations and compare scores; combined **PDF** and JSON (`schema_version` **1.2**) may be produced (see [CHANGELOG.md](../CHANGELOG.md)). Each run in the **`runs`** array includes **`vanilla_pylinac`** on its **`run`** object (and in **`pylinac_analysis_profile`**) when relevant.
- **Scan-extent tolerance:** If pylinac rejects the volume for strict physical extent, you can retry with an optional **0.5–2.0 mm** tolerance; runs record a **`pylinac_analysis_profile`** for audit.

### ACR CT

- Similar worker flow; optional extent tolerance and JSON profile fields align with the MRI path where implemented.

## Interpretation

- Use exported **JSON/PDF** together with your institution’s QA policy.  
- MRI PDFs include **interpretation notes** (MTF, low-contrast scoring, colored ROI legends) where enabled.

## Nuclear Medicine QC (`pylinac.nuclear`)

**Tools → Automated QA → Nuclear Medicine QC (pylinac)…** runs IAEA NMQC–style nuclear-medicine tests via `pylinac.nuclear`. The first supported test is **Planar Uniformity**.

**Supported tests (today):**

| Test | What it computes |
|------|------------------|
| **Planar Uniformity** (`PlanarUniformity`) | Per-frame **UFOV** and **CFOV** **integral** and **differential** uniformity (IAEA-style). |
| **Four Bar Resolution** (`FourBarResolution`) | Planar **resolution**: x/y **FWHM** and **FWTM**, plus effective **measured pixel size** and pixel-size difference. Uses the **first frame** only. |
| **Quadrant Resolution** (`QuadrantResolution`) | Four-quadrant bar pattern: per-quadrant **MTF**, **FWHM**, **lp/mm**, and bar **spacing**. Uses the **first frame** only. |
| **Center of Rotation** (`CenterOfRotation`) | SPECT COR: detector orbit **x/y deviation** (mm). Uses the full rotation acquisition. |
| **Tomographic Resolution** (`TomographicResolution`) | SPECT 3D resolution: **x/y/z FWHM** and **FWTM**. |
| **Max Count Rate** (`MaxCountRate`) | Dynamic acquisition: maximum **count rate**, peak frame, and per-frame counts. |
| **Tomographic Uniformity** (`TomographicUniformity`) | SPECT (Jaszczak-type) uniformity over a selected frame range: UFOV/CFOV **integral** and **differential** uniformity plus **center-border ratio**. |
| **Tomographic Contrast** (`TomographicContrast`) | SPECT cold-sphere contrast: per-sphere **mean/max contrast**, position, and radius, plus a **uniformity baseline**. |
| **Simple Sensitivity** (`SimpleSensitivity`) | System **sensitivity** (MBq/cps and µCi/cps) from phantom counts vs administered activity, with decay correction. Takes a **second (background) image** (optional) and an administered **activity** + **nuclide**. |

Pick the test from the **Analysis** dropdown in the options dialog; the parameter controls change to match.

**Input:** a **single NM DICOM file** (nuclear classes are single-file, unlike the ACR stack workflow). When prompted you can **Use Focused Image** (the focused viewer item) or **Choose File**. Planar Uniformity produces **one result row per frame**; Four Bar and Quadrant Resolution analyze the **first frame only** (and warn if the image has more); the SPECT/dynamic tests (Center of Rotation, Tomographic Resolution, Max Count Rate, Tomographic Uniformity/Contrast) use the **whole acquisition**. **Simple Sensitivity** is the exception: it also accepts an **optional second (background) image** chosen in its options page.

**Options:**
- **Planar Uniformity:** `UFOV ratio` (0.95), `CFOV ratio` (0.75), `differential window` in px (5), `threshold` as a fraction of the mean (0.75).
- **Four Bar Resolution:** `bar separation` in mm (100), `ROI width` in mm (10).
- **Quadrant Resolution:** the **four quadrant bar widths** in mm (set these to match your phantom), `ROI diameter` in mm (70), `distance from center` in mm (130).
- **Center of Rotation / Tomographic Resolution:** no parameters.
- **Max Count Rate:** `frame duration` in seconds (1.0).
- **Tomographic Uniformity:** `first/last frame` (−1 = last), `UFOV/CFOV ratio` (0.8 / 0.75), `center ratio` (0.4), `threshold` (0.75), `differential window` in px (5).
- **Tomographic Contrast:** the **six sphere diameters** (mm) and **angles** (deg) — defaults match the standard phantom — plus `UFOV ratio` (0.8), `search window` in px (5), `search slices` (3).
- **Simple Sensitivity:** administered **activity** in MBq (required, must be > 0), **nuclide** (Tc99m / Ga67 / I131 / In111 / Lu177 / Y90), and an optional **background image**. No `Save Figure` (this test has no pylinac plot).

Defaults match pylinac; leaving them unchanged is recorded as stock-pylinac equivalent. (Quadrant bar widths are phantom-specific and have no pylinac default — set them to your phantom; the ROI geometry is what's checked for stock-equivalence.)

**Preflight:** if the file’s `Modality` is not **NM**, the app warns before running.

**Output:**
- Results are shown in the result dialog as a table — **per-frame** rows (Planar Uniformity), **per-quadrant** rows (Quadrant Resolution), **per-sphere** rows (Tomographic Contrast, with a uniformity-baseline line), or a **Metric/Value** table (the flat tests) — with **Export JSON…**, **Export CSV…**, and **Save Figure (PNG)…** buttons. The CSV matches the table shape (`frame,…`, `quadrant,…`, `sphere,…`, or `metric,value`). The JSON uses `schema_version` **1.1**; consumers tell nuclear from ACR by **`run.analysis_type`** (e.g. `nuclear_planar_uniformity`, `nuclear_tomographic_contrast`) and the convenience field **`run.nuclear_analysis_class`**. Per-frame values are under **`metrics.frames`**, per-quadrant under **`metrics.quadrants`**, per-sphere under **`metrics.spheres`**, flat results under **`metrics.results`**; the full pylinac payload is under **`raw_pylinac`**.
- **Save Figure (PNG)…** writes pylinac’s analyzed image(s): one PNG per frame for multi-frame uniformity (`…_Frame_1.png`, …), or one PNG per plot panel for Four Bar / Quadrant (`…_1.png`, `…_2.png`, …). **No PDF** is produced (pylinac’s nuclear classes have no `publish_pdf`).

> **Not clinically validated.** Output is **raw pylinac metrics** for review. There are **no pass/fail thresholds**; interpret results against your site’s NM QC program and validated baselines.

## Reference data for pylinac (CatPhan, Quart, NM / NMQC)

The **ACR CT / MRI** menus in this app use **your** DICOM series (or a folder you pick). As you **expand integration** (e.g. CatPhan, Quart, or **`pylinac.nuclear`**), it helps to keep **fixed test stacks** on disk. A practical layout is:

- **`SampleDICOMData/pylinac_demo_data/`** — local mirror of upstream archives (ZIPs and/or extracted folders).  
  The whole **`SampleDICOMData/`** tree is **gitignored** (see **`.gitignore`**) so large binaries are never committed.

**Where pylinac caches its own CatPhan demos:** calling **`CatPhan504.from_demo_images()`** (etc.) downloads once into the venv, typically **`<venv>\Lib\site-packages\pylinac\demo_files\`** (`retrieve_demo_file` in upstream `pylinac.core.io`). A project copy under **`SampleDICOMData/`** is optional but convenient for **File → Open** and for scripts without hitting the package cache.

### CatPhan and Quart (Google `pylinac_demo_files` bucket)

| Archive | URL |
|---------|-----|
| CatPhan 503 | `https://storage.googleapis.com/pylinac_demo_files/CatPhan503.zip` |
| CatPhan 504 | `https://storage.googleapis.com/pylinac_demo_files/CatPhan504.zip` |
| CatPhan 600 | `https://storage.googleapis.com/pylinac_demo_files/CatPhan600.zip` |
| CatPhan 604 | `https://storage.googleapis.com/pylinac_demo_files/CatPhan604.zip` |
| Quart DVT | `https://storage.googleapis.com/pylinac_demo_files/quart.zip` |

**Note:** **CatPhan 700** has no matching bundled demo ZIP in current upstream pylinac; use your own CBCT/CT acquisition for 700.

### NM / SPECT — IAEA NMQC sample images (for `pylinac.nuclear`)

The **`pylinac.nuclear`** module follows **IAEA NMQC (ImageJ)**–style tests. The IAEA publishes a **reference ZIP** of simulated/sample images used with that toolkit (also cited in pylinac’s [Nuclear](https://pylinac.readthedocs.io/en/latest/nuclear.html) documentation):

| Archive | URL |
|---------|-----|
| NMQC simulated / sample images | `https://humanhealth.iaea.org/HHW/MedicalPhysics/NuclearMedicine/QualityAssurance/NMQC-Plugins/Simulated_images.zip` |

Unzip into e.g. **`SampleDICOMData/pylinac_demo_data/nm_nmqc_simulated/`** and point **`pylinac.nuclear`** classes at the appropriate **`.dcm`** paths, or load slices in the viewer for visual checks. **Licensing and use** are governed by the **IAEA** / NMQC distribution, not this project.

**Further reading (tests, inputs, class list):** [PYLINAC_CATPHAN_AND_NUCLEAR_MODULES.md](../dev-docs/info/PYLINAC_CATPHAN_AND_NUCLEAR_MODULES.md).

## Integration details (developers)

For architecture, version pin rationale, and roadmap (CatPhan, overlays, batch, etc.), see [PYLINAC_INTEGRATION_OVERVIEW.md](../dev-docs/info/PYLINAC_INTEGRATION_OVERVIEW.md).

# User guide — ACR phantom QA (pylinac)

The viewer can run **automated ACR phantom analysis** using the **pylinac** library (pinned in `requirements.txt`, currently **3.43.2**). This is **optional QA tooling**; the app still runs if pylinac is missing until you use these menus.

## Where to find it

| Menu | Action |
|------|--------|
| **Tools** | **ACR CT Phantom (pylinac)…** |
| **Tools** | **ACR MRI Phantom (pylinac)…** |

## Inputs

- **Focused series:** The analysis prefers **slice files from the currently focused viewer** (ordered stack).  
- **Folder fallback:** If that is not available, you can point to a **folder** of DICOM slices when prompted.

**Preflight:** The app may warn about stack geometry (e.g. slice spacing along the normal) before running.

## During and after the run

- Work runs on a **background thread**; a progress dialog is shown.
- Results include **metrics**, **warnings/errors**, and optional **JSON** export with reproducibility fields (pylinac version, analysis profile). Exported JSON records **vanilla pylinac** (stock **ACRCT** / **ACRMRILarge** vs viewer integration classes) under **`run.vanilla_pylinac`**, **`inputs.vanilla_pylinac`**, and **`pylinac_analysis_profile.vanilla_pylinac`**.
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

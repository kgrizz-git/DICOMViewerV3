# User guide — ACR phantom QA (pylinac)

The viewer can run **automated ACR phantom analysis** using the **pylinac** library (pinned in `requirements.txt`, currently **3.42.0**). This is **optional QA tooling**; the app still runs if pylinac is missing until you use these menus.

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

## Integration details (developers)

For architecture, version pin rationale, and roadmap (CatPhan, overlays, batch, etc.), see [PYLINAC_INTEGRATION_OVERVIEW.md](../dev-docs/info/PYLINAC_INTEGRATION_OVERVIEW.md).

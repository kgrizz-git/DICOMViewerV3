# Pylinac customization, extensions, and wrappers (living tracker)

**Purpose:** Single place to record **how DICOM Viewer V3** adapts **pylinac**—without forking upstream—so physicists and developers can see what is stock vs viewer-assisted. Update this file when adding knobs, subclasses, or workarounds.

**Related:** [PYLINAC_INTEGRATION_OVERVIEW.md](PYLINAC_INTEGRATION_OVERVIEW.md) (product scope), [PYLINAC_FLEXIBILITY_AND_WORKAROUNDS.md](PYLINAC_FLEXIBILITY_AND_WORKAROUNDS.md) (gates & workarounds), [PYLINAC_MRI_LOW_CONTRAST_DETECTABILITY.md](PYLINAC_MRI_LOW_CONTRAST_DETECTABILITY.md) (MRI LC algorithm & PDF overlays, **pylinac 3.42.0**).

**Upstream pin:** `requirements.txt` uses **`pylinac==3.42.0`** (see **Verified pylinac package version** in the integration overview).

---

## Design principle: persist preferences, pass per run

Pylinac analyzers are constructed and **`analyze(...)`** is called **once per workflow**. There is **no need** to mutate pylinac globals for user preferences:

1. Store defaults in **`ConfigManager`** / `dicom_viewer_config.json` where appropriate.
2. Load into the **ACR MRI / CT options dialog** when opened.
3. On **OK**, save back to config and build a **`QARequest`** with the chosen values.
4. **`run_*_analysis`** passes those values as **keyword arguments** to **`analyze()`** if the installed pylinac exposes them (with **inspect.signature** guards).

Every run is therefore **explicit** in **`QAResult.pylinac_analysis_profile`**, **JSON `inputs`**, and **`metrics`** where applicable.

---

## Shipped customizations (inventory)

| Topic | What we do | Where | Stock pylinac? |
|--------|------------|--------|----------------|
| **Physical scan extent** | Optional mm tolerance via subclasses overriding `_ensure_physical_scan_extent` | `src/qa/pylinac_extent_subclasses.py`, `src/qa/pylinac_runner.py`, dialogs | No — non-vanilla when tolerance &gt; 0; recorded in `pylinac_analysis_profile` |
| **MRI low-contrast method / threshold / sanity multiplier** | User-set **`low_contrast_method`** (default **`Weber`**), **`low_contrast_visibility_threshold`** (default **0.001**), and **`low_contrast_visibility_sanity_multiplier`** (default **3.0**), all persisted in config | `src/utils/config/qa_pylinac_config.py`, `acr_mri_qa_dialog.py`, `QARequest`, `pylinac_runner.py` | Same **public API parameters** as upstream `ACRMRILarge.analyze`; values are **user-chosen** and persisted locally |
| **Echo / check_uid / origin slice** | Surfaced in MRI dialog, passed through `QARequest` | `acr_mri_qa_dialog.py`, `pylinac_runner.py` | Uses public API when available |
| **Reproducibility metadata** | `build_pylinac_analysis_profile()`, JSON **1.1** | `src/qa/analysis_types.py`, `src/main.py` | N/A (viewer layer) |

---

## Candidates (not implemented / future)

| Idea | Notes |
|------|--------|
| **CT low-contrast** | Different module (`ACRCT`); separate UX if we expose more than today. |
| **Dedicated `Pylinac Configuration...` dialog/menu item** | Consider once more persisted pylinac/site-level defaults accumulate across MRI, CT, or future analyzers. |
| **Subclass for other protected hooks** | Prefer upstream PR or narrow override; document here if added. |

---

## Changelog (this document)

| Date (approx.) | Change |
|----------------|--------|
| 2026-04 | Added persisted MRI **`low_contrast_method`** and **`low_contrast_visibility_sanity_multiplier`** alongside the visibility threshold; all are passed per-run through `QARequest` / `analyze()` and recorded in reproducibility metadata. |
| 2026-04 | Initial tracker; documented MRI **`low_contrast_visibility_threshold`** persistence and per-run `analyze()` passing. |

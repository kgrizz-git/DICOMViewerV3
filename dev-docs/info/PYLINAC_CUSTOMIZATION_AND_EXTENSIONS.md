# Pylinac customization, extensions, and wrappers (living tracker)

**Purpose:** Single place to record **how DICOM Viewer V3** adapts **pylinac**—without forking upstream—so physicists and developers can see what is stock vs viewer-assisted. Update this file when adding knobs, subclasses, or workarounds.

**Related:** [PYLINAC_INTEGRATION_OVERVIEW.md](PYLINAC_INTEGRATION_OVERVIEW.md) (product scope), [PYLINAC_FLEXIBILITY_AND_WORKAROUNDS.md](PYLINAC_FLEXIBILITY_AND_WORKAROUNDS.md) (gates & workarounds), [PYLINAC_MRI_LOW_CONTRAST_DETECTABILITY.md](PYLINAC_MRI_LOW_CONTRAST_DETECTABILITY.md) (MRI LC algorithm & PDF overlays, **pylinac 3.43.2**).

**Upstream pin:** `requirements.txt` uses **`pylinac==3.43.2`** (see **Verified pylinac package version** in the integration overview).

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
| **MRI compare mode** | Up to 3 independent low-contrast runs from one dialog; analyzer re-instantiated per run; comparison table dialog; **schema_version 1.2** JSON with `compare_mode: true`, `combined_pdf_path`, and `runs` array | `acr_mri_qa_dialog.py`, `QABatchWorker`, `run_acr_mri_large_batch`, `analysis_types.py`, `main.py` | Viewer layer only — each individual run uses stock pylinac API |
| **MRI compare combined PDF** | After all compare-mode runs finish, a viewer-authored summary page (parameter table, scores, full interpretation notes) is prepended to the per-run pylinac PDFs and merged via `pypdf` into a single combined PDF at the user-chosen path.  Temp files are cleaned up automatically.  Results dialog shows path and "Open PDF" button. | `pylinac_runner.build_mri_compare_summary_pdf`, `assemble_mri_compare_pdf`, `_write_per_run_temp_pdf` | Viewer extension — uses `reportlab.platypus` (pylinac dep) + `pypdf` |
| **MRI PDF interpretation notes** | Always-on notes passed to `publish_pdf(notes=list[str])` (6-line compact version for pylinac's constrained footer area); full version (`_NOTES_LINES_FULL`) used in compare summary page | `pylinac_runner._NOTES_LINES`, `_NOTES_LINES_FULL`, `build_mri_pdf_notes` | Uses public `notes=` argument on `ACRMRILarge.publish_pdf` |
| **Echo / check_uid / origin slice** | Surfaced in MRI dialog, passed through `QARequest` | `acr_mri_qa_dialog.py`, `pylinac_runner.py` | Uses public API when available |
| **Reproducibility metadata** | `build_pylinac_analysis_profile()`, JSON **1.1** (single-run) / **1.2** (compare) | `src/qa/analysis_types.py`, `src/main.py` | N/A (viewer layer) |

---

## Candidates (not implemented / future)

| Idea | Notes |
|------|--------|
| **MRI / CT MTF rMTF percentile grid** | **Console warnings:** `pylinac.core.mtf.MTF.relative_resolution(x)` warns when the requested **rMTF %** (`x`, 0–100) needs **extrapolation** past the finest sampled line-pair/mm region (`mtf > max(self.spacings)` after interpolation). **Not a fallback chain:** upstream does **not** try 10% then 20%. **ACR MRI** (`ACRMRILarge`) builds `row_mtf_lp_mm` / `col_mtf_lp_mm` by calling `relative_resolution(p)` for **`p in range(10, 91, 10)`** inside `_generate_results_data` (same 10% step grid is used for **CatPhan** CTP528 `mtf_lp_mm` in `ct.py`). The **`analyze()`** API in **pylinac 3.43.2** does **not** expose this grid; only the per-call argument to `relative_resolution` is configurable if we **subclass** or **reimplement** result assembly, or if **upstream** adds parameters. Optional viewer work: document-only, filter warnings, or wrap result generation with a smaller percentile set to avoid extrapolation noise. |
| **CT low-contrast** | Different module (`ACRCT`); separate UX if we expose more than today. |
| **Dedicated `Pylinac Configuration...` dialog/menu item** | Consider once more persisted pylinac/site-level defaults accumulate across MRI, CT, or future analyzers. |
| **Subclass for other protected hooks** | Prefer upstream PR or narrow override; document here if added. |

---

## Changelog (this document)

| Date (approx.) | Change |
|----------------|--------|
| 2026-04 | **Candidates:** Documented upstream **MTF `relative_resolution` extrapolation warnings** and the fixed **10–90% rMTF grid** used for ACR MRI / CatPhan CTP528 results (`analyze()` does not expose it in pylinac 3.43.2). |
| 2026-04 | Added MRI **combined PDF** for compare mode: viewer-authored summary page + per-run pylinac PDFs merged via `pypdf`; full interpretation notes (unconstrained). `combined_pdf_path` added to schema 1.2 JSON. |
| 2026-04 | Added MRI **compare mode** (up to 3 low-contrast runs with multiplier combos) and always-on **PDF interpretation notes** (MTF, LC scoring, circle colors, pylinac doc links). Schema bumped to 1.2 for compare exports. |
| 2026-04 | Added persisted MRI **`low_contrast_method`** and **`low_contrast_visibility_sanity_multiplier`** alongside the visibility threshold; all are passed per-run through `QARequest` / `analyze()` and recorded in reproducibility metadata. |
| 2026-04 | Initial tracker; documented MRI **`low_contrast_visibility_threshold`** persistence and per-run `analyze()` passing. |

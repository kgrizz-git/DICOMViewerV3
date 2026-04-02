# PyLinac flexibility: bottlenecks, parameters, and integration workarounds

This note is for **DICOM Viewer V3** developers extending the Stage 1 **`src/qa`** pylinac path. It summarizes where stock pylinac is strict, what is already tunable via **public API**, and how we can **relax gates responsibly** (wrapper logic, monkey-patches, small forks, or site-specific constants).

**Related:** [PYLINAC_INTEGRATION_OVERVIEW.md](PYLINAC_INTEGRATION_OVERVIEW.md) (integration scope + reproducibility guidance §2.4), [AUTOMATED_QA_ADDITIONAL_ANALYSIS.md](AUTOMATED_QA_ADDITIONAL_ANALYSIS.md) (physics gaps), [plans/PYLINAC_AND_AUTOMATED_QA_STAGE1_PLAN.md](../plans/PYLINAC_AND_AUTOMATED_QA_STAGE1_PLAN.md) (Stage 1 checklist), [plans/PYLINAC_SCAN_EXTENT_TOLERANCE_AND_REPRODUCIBILITY_PLAN.md](../plans/PYLINAC_SCAN_EXTENT_TOLERANCE_AND_REPRODUCIBILITY_PLAN.md) (vanilla default + optional extent tolerance + JSON profile).

**Upstream docs (version your install separately; project pins `pylinac>=3.38.0` in `requirements.txt`):**

- [ACR phantoms (ACRCT, ACRMRILarge)](https://pylinac.readthedocs.io/en/latest/acr.html)
- [CatPhan / CBCT module](https://pylinac.readthedocs.io/en/latest/cbct.html)
- [Images / DICOM stacks](https://pylinac.readthedocs.io/en/latest/topics/images.html)
- [Troubleshooting](https://pylinac.readthedocs.io/en/latest/troubleshooting.html)

---

## 1. The main hard gate: physical scan extent

### What it does

For **`CatPhanBase`** (shared by **CatPhan** analyzers, **`ACRCT`**, and **`ACRMRILarge`**), `localize()` ends by calling **`_ensure_physical_scan_extent()`**. That method compares:

- the **min/max z positions** of all slices in the loaded DICOM stack, and  
- the **min/max z positions implied by the phantom’s configured module offsets** relative to the detected HU / slice-1 origin.

The check is **strict** after rounding each bound to **0.1 mm**. If any module’s nominal z falls **outside** the scanned range, pylinac raises **`ValueError`** with text like: rescan to include all modules, **or change the offset values** / (for CatPhan) **remove modules from analysis**.

The docstring in source references **RAM-2897**: small discrepancies between DICOM z tags and true geometry can contribute to false failures—yet the implementation remains **exact** on the rounded comparison, so cases such as **“need 100 mm from origin, have 99.5 mm”** fail even when the mismatch is **sub-millimeter or dominated by tag rounding**.

### Why it matters for ACR CT

`ACRCT` defines module offsets along z from the HU-linearity (**module 1**) slice. Defaults (mm) are documented on the [ACR page](https://pylinac.readthedocs.io/en/latest/acr.html): low contrast **+30**, uniformity **+70**, spatial resolution **+100**. The **maximum** offset sets the **furthest z** the library expects; the stack must reach at least that physical position **using the same z convention pylinac derives** from DICOM (`ImagePositionPatient` / orientation), not only “ nominal couch travel.”

### Flexibility options (incremental risk)

| Approach | Idea | Tradeoff |
|----------|------|----------|
| **A. Tolerant extent check in our wrapper** | Subclass e.g. `ACRCT` and override `_ensure_physical_scan_extent` to allow a small **ε** (e.g. 0.5–2 mm) so `max_config <= max_scan + ε` (and symmetrically for `min`). | May accept scans that **omit** a sliver of a real module; must surface **“relaxed geometry gate”** in JSON/PDF notes. |
| **B. Retry ladder** | First run stock; on `ValueError` containing “physical scan extent”, retry once with **ε** or with **user-approved** ε from an advanced dialog. | Clear audit trail if we log the second attempt. |
| **C. Adjust module offsets (constants)** | Before constructing the analyzer, assign smaller offsets on **`pylinac.acr`** globals (e.g. `CT_SPATIAL_RESOLUTION_MODULE_OFFSET_MM`) so the **declared** module positions lie inside the scan. Pylinac’s own MRI error message suggests **“change the offset values”** when extent fails. | **Physically wrong** unless the phantom or staging truly matches; suitable only for **validated site calibration** or **non-standard phantoms**, with documentation. |
| **D. Partial analysis (heavy)** | Subclass and **skip constructing** some modules, or override `_module_offsets()` to consider only a subset so extent passes—then run a **reduced** result object. | Not a first-class feature upstream; we must avoid reporting “full ACR suite” if modules were dropped. |

**Recommendation:** Prefer **A + B** for the “99.5 mm vs 100 mm” class of failures tied to rounding; prefer **C** only with physicist-facing warnings and config; reserve **D** for explicit “subset QA” workflows.

**Implementation plan (productized path):** [PYLINAC_SCAN_EXTENT_TOLERANCE_AND_REPRODUCIBILITY_PLAN.md](../plans/PYLINAC_SCAN_EXTENT_TOLERANCE_AND_REPRODUCIBILITY_PLAN.md).

---

## 2. Parameters we should expose before patching source

Many issues are **registration / tuning**, not extent. Prefer wiring these in **`pylinac_runner`** / the QA dialog before any fork.

### `ACRCT.analyze(...)`

Documented on the [ACR page](https://pylinac.readthedocs.io/en/latest/acr.html): **`x_adjustment`**, **`y_adjustment`**, **`angle_adjustment`**, **`roi_size_factor`**, **`scaling_factor`**, **`origin_slice`**.

- **`origin_slice`**: Already supported in our **`QARequest`** path for CT/MRI where applicable. Fixes failures when automatic HU-slice search picks the wrong index (jigs, artifacts, weak contrast).
- **Fine geometric tuning**: Helps when the phantom is found but **ROIs sit on edges**; pair with visual review of pylinac plots.

### `ACRMRILarge.analyze(...)`

Echo selection (**`echo_number`**), low-contrast method/thresholds, and (where supported) **`check_uid`** for sagittal in a separate Series Instance UID—already partially reflected in our runner. Rotational error should be **≤ 1°** per pylinac MRI notes for rectangular ROIs.

#### Multi-echo series: let the user choose the echo to analyze

A **single DICOM series** the user selects for ACR MRI–large phantom QA can still contain **more than one echo**: instances differ by **`EchoNumber` (0018,0086)** and/or **`EchoTime` (0018,0081)** (multi-echo GRE, mixed TE export from the scanner or PACS, etc.). Pylinac’s **`ACRMRILarge.analyze(..., echo_number=...)`** analyzes slices for **one** echo; feeding an unfiltered mixed stack or the wrong echo can break localization or skew low-contrast / uniformity results.

**Product / integration direction:**

1. **Preflight or series binding:** When building the slice list for MRI phantom analysis, detect **distinct echo groups** (unique `(EchoNumber, EchoTime)` with slice counts and ordering). If only one group exists, keep today’s path; no extra UI.
2. **When multiple echoes are present:** Expose a **user choice**—e.g. a dropdown listing echo number and/or echo time (and slice count)—for **which echo to analyze**. Map the selection to the **`echo_number`** (and/or filter instances by TE before construct) per pylinac’s contract for the loaded stack.
3. **Audit / exports:** Record the chosen **`EchoNumber` / `EchoTime`** (and pylinac **`echo_number`** if relevant) in **`QAResult`** or JSON so reports distinguish “TE 12 ms” vs “TE 80 ms” runs.

This is **parameter exposure and UI clarity**, not a fork: it avoids silent ambiguity when the same series UID mixes echoes.

### `CatPhan*.analyze(...)`

See [CatPhan typical use / parameters](https://pylinac.readthedocs.io/en/latest/cbct.html): tolerances (**`hu_tolerance`**, **`scaling_tolerance`**, **`thickness_tolerance`**), low-contrast **`visibility_threshold`**, **`thickness_slice_straddle`** (padding for thin slices), **`expected_hu_values`** overrides, **`origin_slice`**, **`roll_slice_offset`** (mm shift for roll detection slice), and the same **x/y/angle/roi/scaling** adjustments as ACR.

### Stack loading

CatPhan constructors accept **`memory_efficient_mode`** for large stacks (slower, lower RAM)—useful for clinics sending full series.

---

## 3. Other bottlenecks (fail-fast vs workaround)

| Area | Symptom | Native mitigation |
|------|---------|-------------------|
| **Too few images** | `ACRCT` / `ACRMRILarge` set a small **`min_num_images`** for loading; real QA still needs enough slices to cover offsets. | Preflight **z-span** (we already warn on monotonic `ImagePositionPatient` in `src/qa/preflight.py`); extend with **min/max z delta** vs required module span. |
| **MRI localization** | `RuntimeError` if roll bubble not found on slice 1. | Better phantom positioning; expose **`origin_slice`** / future roll aids. |
| **MRI multi-echo series** | One series UID mixes echoes; wrong or merged stack confuses analysis. | Detect distinct **`EchoNumber` / `EchoTime`** groups; **user-selects** echo → pass **`echo_number`** / filter slices; log TE in results. |
| **MRI low-contrast** | `ValueError` if region not found. | Check protocol, echo, inclusion of slices 8–11; visibility thresholds. |
| **Sagittal handling** | Too many sagittal images or UID filtering. | **`check_uid=False`** when sagittal is separate series. |
| **CatPhan acquisition** | FOV, couch, edge contact; incomplete modules. | Follow pylinac **Image acquisition** section; cannot software-fix missing anatomy. |

---

## 4. Modifying pylinac itself (fork / vendor patch)

Upstream is **BSD-3-Clause**; forking is allowed but increases maintenance (merge security fixes, API churn).

**Lowest-churn edits** that solve many “almost fits” scans:

1. **`_ensure_physical_scan_extent`** — add an optional **tolerance** argument or compare with **`np.isclose`** at 0.5–1 mm; plumb through `localize()` from `analyze()`.
2. **`ACRCT` / MRI** — allow **per-module disable** flags so clinics can run **HU + uniformity only** when the table stopped short of resolution module (clear labeling in reports).

**Policy:** If we ship a patch, pin **exact** git SHA or version in docs, record differences in **`QAResult`** / JSON, and run regression tests on golden phantom folders.

---

## 5. DICOM Viewer V3 implementation sketch

1. **Preflight:** Compute `z_min`, `z_max` along slice normal (reuse preflight helpers); compare to **required span** from default or user-edited offsets (100 mm for stock ACR CT from module 1).
2. **Primary path:** Call stock `analyze()`.
3. **On extent `ValueError`:** Optional **“Retry with 1 mm geometry tolerance”** (subclass) + flag in **`metrics`**: `scan_extent_check: "strict" | "relaxed_epsilon_1mm"`.
4. **Advanced UI (later):** Optional field **“Max module offset (mm)”** or per-offset overrides → maps to monkey-patching **`pylinac.acr`** constants **before** `ACRCT(...)` with strong warnings.

This aligns with the **[P2] TO_DO** item on robustness: treat near-miss extent as **recoverable with disclosure**, not silent.

---

## 6. Disclaimer

Relaxing geometric gates or offsets changes **what geometry the software assumes**. Any tolerant or offset-edited run should be labeled in exports so physicists can separate **stock pylinac-equivalent** runs from **viewer-assisted** runs.

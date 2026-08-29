# ACR phantom QA metrics — references and pylinac gaps

**Last updated:** 2026-08-29  
**Purpose:** Tabulate what physicists are asked to measure on **ACR CT** and **ACR MRI** accreditation phantoms, how those quantities are defined in primary references, what **pylinac 3.43.2** already computes, and what remains **viewer-native** work (MRI **SNR**, direct resolution reads, etc.).  
**Related:** [PYLINAC_ACR_FULL_METRICS_EXPORT_AND_MRI_BATCH_PLAN.md](../plans/supporting/PYLINAC_ACR_FULL_METRICS_EXPORT_AND_MRI_BATCH_PLAN.md) (Phases 0–6), [PYLINAC_MRI_LOW_CONTRAST_DETECTABILITY.md](PYLINAC_MRI_LOW_CONTRAST_DETECTABILITY.md), [PYLINAC_CUSTOMIZATION_AND_EXTENSIONS.md](PYLINAC_CUSTOMIZATION_AND_EXTENSIONS.md) (MTF rMTF grid), [AUTOMATED_QA_ADDITIONAL_ANALYSIS.md](AUTOMATED_QA_ADDITIONAL_ANALYSIS.md) (**C2**, **C24**).

---

## Primary references (links)

| Document | What it covers | Link |
|----------|----------------|------|
| **ACR Large & Medium Phantom Test Guidance** (accreditation submission; seven quantitative tests + procedures) | Official pass/fail criteria for geometric accuracy, spatial resolution, slice thickness/position, PIU, PSG, low-contrast detectability | [ACR PDF (hosted mirror)](https://mriquestions.com/uploads/3/4/5/7/34572113/largephantomguidance.pdf) · [Alternate mirror (2022)](https://www.mtcbiomedical.vn/images/upload/ACR%20Large%20%20Med%20Phantom%20Guidance%20102022.pdf) |
| **ACR MRI Quality Control Manual** | Weekly technologist QC (center frequency, SNR, artifacts, LCD trend), annual physicist/MR scientist tests (B₀ homogeneity, RF coil SNR/uniformity, slice metrics, etc.) | [ACR MRI QC Manual (PDF)](https://edge.sitecorecloud.io/americancoldf5f-acrorgf92a-productioncb02-3650/media/ACR/Files/Clinical/Quality-Control-Manuals/MRI-Quality-Control-Manual.pdf) |
| **AAPM — Physics procedures for ACR MRI accreditation** (overview slide deck) | Accreditation vs routine QC scope; lists phantom tests and physicist responsibilities | [AAPM AMOS PDF](https://www.aapm.org/meetings/amos2/pdf/26-5963-1529-184.pdf) |
| **NEMA MS 1-2008** (cited by ACR QC manual) | Standard **SNR** definition for diagnostic MRI (single-image method with Rayleigh correction) | [NEMA MS 1-2008 (overview)](https://www.nema.org/standards/view/determination-of-signal-to-noise-ratio-in-diagnostic-magnetic-resonance-images) |
| **NEMA MS 3-2008** | Image **uniformity** measurement standard | [NEMA MS 3-2008 (overview)](https://www.nema.org/standards/view/determination-of-image-uniformity-in-diagnostic-magnetic-resonance-images) |
| **Automated ACR QC study (PMC)** | Implements PSG, PIU, **SNR**, **SNRU** with ROI automation; explicitly notes **SNR is not one of the seven ACR accreditation tests** but is ubiquitous in QC manuals | [PMC8321175](https://pmc.ncbi.nlm.nih.gov/articles/PMC8321175/) |
| **Low-contrast automation (2024)** | Uses slice-7 **SNR** (central ROI mean ÷ background σ) as covariate for LCD scoring | [PMC12257337](https://pmc.ncbi.nlm.nih.gov/articles/PMC12257337/) |
| **Legacy ACR MR accreditation phantom overview (AAPM 1999)** | Early phantom spec; **nickel-chloride vial SNR** on early slices + corner background ROIs; RF uniformity on the uniformity slice | [AAPM 99AM PDF](https://www.aapm.org/meetings/99am/pdf/2728-58500.pdf) |
| **pylinac ACR MRI Large** | What the library automates today | [pylinac ACR docs](https://pylinac.readthedocs.io/en/latest/acr.html) |

---

## Seven ACR accreditation phantom tests (Large / Medium)

These are the **quantitative tests** in the current **Phantom Test Guidance** used for accreditation submission. They are **not** the same as the full weekly/annual QC program in the MRI QC Manual (which adds SNR trending, center frequency, artifact checklists, B₀ homogeneity, etc.).

| # | Test | Typical series / slice | ACR procedure (summary) | Pass/fail in guidance | pylinac 3.43.2 `ACRMRILarge` |
|---|------|------------------------|---------------------------|------------------------|--------------------------------|
| 1 | **Geometric accuracy** | Sagittal localizer; axial slices **1** and **5** | Measure **seven** known lengths; compare to phantom dimensions | **≤ ±2 mm** per length ([PMC8321175](https://pmc.ncbi.nlm.nih.gov/articles/PMC8321175/) Table 1; Phantom Test Guidance) | **Yes** — `geometric_distortion_module` distances/profiles; sagittal module when present |
| 2 | **High-contrast spatial resolution** | Axial slice **1** | **Visual** assessment of hole pairs (0.9 / 1.0 / 1.1 mm); site-series fallback if ACR series fails | Qualitative (smallest resolved pair) | **Partial** — automated **MTF / rMTF grid** on slice 1 (`row_mtf_lp_mm`, `col_mtf_lp_mm`, 10–90%); not the same as human hole-pair read |
| 3 | **Slice thickness accuracy** | ACR T1 & T2, slice **1** | Ramp-based thickness from slice 1 geometry | **5.0 mm ± 0.7 mm** (fail **> ±1.0 mm**) | **Yes** — `slice1.measured_slice_thickness_mm` |
| 4 | **Slice position accuracy** | ACR T1 & T2, slices **1** and **11** | Wedge / bar displacement between slices 1 and 11 | **≤ ±5 mm** (stricter **±4 mm** in some tables) | **Yes** — `slice1` / `slice11` `bar_difference_mm`, `slice_shift_mm` |
| 5 | **Image intensity uniformity (PIU)** | ACR T1 & T2, slice **7** | Large circular ROI on the **uniformity slice**; find ~1 cm² max/min regions; **PIU = 100 × (1 − (high−low)/(high+low))** | **ACR guidance:** **≥ 87.5%** (<3 T); **≥ 82%** (3 T) | **Yes** — `uniformity_module.piu` (pylinac uses 99th/1st percentile variant, not the 1 cm² high/low regions); **`piu_passed`** in code uses **85% / 80%** (pylinac internal thresholds — **not** the ACR submission limits) |
| 6 | **Percent signal ghosting (PSG)** | ACR T1, slice **7** | Center ROI mean + four **background** ROIs (top, bottom, left, right outside phantom); **ghosting ratio = \|(left+right)−(top+bottom)\| / (2×center)** (same magnitude as other sign orderings); PSG = ratio × 100% | **≤ 2.5%** (ratio **≤ 0.025**) | **Yes** — same formula in `MRUniformityModule.ghosting_ratio` / `.psg` (`(L+R)−(T+B)` in pylinac source); ghost ROIs at fixed phantom-centered angles (Top/Bottom/Left/Right) |
| 7 | **Low-contrast object detectability** | ACR T1 & T2, slices **8–11** | Count **complete spokes** (all three disks visible per spoke); stop at first incomplete spoke; sum across slices | Score thresholds vary by field strength (e.g. **≥ 9** at 1.5 T, **≥ 37** at 3 T in some tables) | **Yes** — `low_contrast_multi_slice_module.score` (pylinac visibility algorithm; see [PYLINAC_MRI_LOW_CONTRAST_DETECTABILITY.md](PYLINAC_MRI_LOW_CONTRAST_DETECTABILITY.md)) |

**Note on slice numbering:** Guidance uses **ACR T1 axial series** slice indices (slice 7 = **uniformity slice**, also used for PSG). pylinac maps modules by **stack offset** from the HU/origin slice; verify alignment on real data in Phase 0. Do not call this a “flood” — that term is nuclear-medicine usage, not ACR MRI phantom testing.

---

## SNR and SNR uniformity — not accreditation tests, but routine QC

| Quantity | Where required | Typical definition | pylinac 3.43.2 |
|----------|----------------|-------------------|----------------|
| **SNR** | ACR **MRI QC Manual** (weekly technologist SNR check; physicist RF coil section); NEMA **MS 1-2008**; many papers | One ACR-style ratio on the **uniformity slice** (below); NEMA multiplies the same ratio by **0.655**. Two-image difference SNR is a different method. | **No** — no `snr` field in `acr.py` / `results_data` |
| **SNR uniformity (SNRU)** | PMC automation papers; some site QC programs | Ratio of max/min SNR across sub-ROIs in uniform region, or **SNR(slice 6) / SNR(slice 7)** in [PMC8321175 §2.3.3.B](https://pmc.ncbi.nlm.nih.gov/articles/PMC8321175/) (0.9–1.1) | **No** — defer after canonical slice-7 SNR |
| **Legacy MRAP nickel-vial SNR** | 1999 AAPM phantom overview | Signal from **~2.5 cm²** ROI on NiCl₂ vial (early slices); noise from **corner background** ROI σ (four corners, 15–20 cm²) | **No** (phantom insert layout differs on current Large phantom) |

### SNR formula (one ACR-style ratio)

**S̄** is the mean signal in a circular ROI on the ACR MRI phantom **uniformity slice** (ACR T1/T2 slice **7**), covering about **80% of the phantom diameter** (radius ≈ **0.80 ×** the phantom radius — not an 80% *area* construction with √0.80). Background noise is the pixel **σ** outside the phantom, typically averaged over ghost-free ROIs on the **frequency-encode** axis.

NEMA MS 1, LCD-paper “ACR-style” SNR, PMC8321175 Eq. 7, and the Phase 6 export are **the same ratio**. The only extra factor in NEMA single-image SNR is the Rayleigh correction **0.655**. Viewer v1 exports the **uncorrected** ratio (`mri_snr`); do not apply 0.655 (OQ-10).

| Method | Formula (conceptual) | Notes | Source |
|--------|----------------------|-------|--------|
| **ACR-style uncorrected** (QC / LCD / PMC Eq. 7 / Phase 6) | SNR = **S̄ / σ_bkg** | Uniformity slice; S̄ in ~**80% diameter** ROI; σ from background (freq-encode ghost-free pair, or a single background ROI in some write-ups) | ACR MRI QC Manual (requires the check); [PMC12257337](https://pmc.ncbi.nlm.nih.gov/articles/PMC12257337/); [PMC8321175 Eq. 7](https://pmc.ncbi.nlm.nih.gov/articles/PMC8321175/) (`S̄ / mean(σ_L, σ_R)` on slice 7) |
| **NEMA MS 1 single-image** | SNR ≈ **0.655 × S̄ / σ_bkg** | Same S̄ / σ_bkg family; **0.655** corrects Rayleigh noise on magnitude images | [PMC8321175 §2.3.3](https://pmc.ncbi.nlm.nih.gov/articles/PMC8321175/) citing NEMA MS 1 |
| **Two-image difference** | SNR ≈ **√2 × S̄ / σ_diff** (often written 1.41×) | **Different method** — two identical acquisitions; σ from the subtracted image | NEMA / PMC8321175 |

**Phase 6 noise ROIs:** use the two **ghost-free** background rectangles on the **frequency-encode** axis (pylinac `ghost_rois`). When frequency encode is image **columns**, use **Left/Right**; when frequency encode is image **rows**, use **Top/Bottom**. Do not hard-code Left/Right without `InPlanePhaseEncodingDirection` / orientation. That matches PSG ROI placement but uses **σ** instead of mean intensity.

**Phase/frequency encode:** PSG guidance places ghost-sensitive ROIs along **phase encode** (top/bottom) vs ghost-free controls along **frequency encode** (left/right) when frequency encode is left–right. DICOM tags such as **`InPlanePhaseEncodingDirection`** (0018,1312) and the image orientation matrix determine which image axis is phase vs frequency. **Fallback when tags are missing (R6-3):** assume **phase encode = ROW** / **frequency encode = COL** (ACR default in [PMC8321175 §2.2](https://pmc.ncbi.nlm.nih.gov/articles/PMC8321175/)) → noise from **Left/Right** ghost ROIs.

**SNR limits (export):** SNR has **no ACR accreditation pass/fail** threshold. Sites may apply QC-manual or local rules (e.g. [PMC8321175 §2.3.3.B](https://pmc.ncbi.nlm.nih.gov/articles/PMC8321175/) suggests **SNR ≥ 80×T** for technologist checks, or SNRU **0.9–1.1** between slices **6** and **7**). Viewer v1 exports **`mri_snr` as an uncorrected ratio** only — no pass/fail column unless added later.

---

## PSG vs SNR — shared geometry

pylinac `MRUniformityModule` (slice 7 / uniformity offset) already places:

| ROI | Role in ACR §6 | pylinac `ghost_roi_settings` |
|-----|----------------|------------------------------|
| **Center** | Large circular ROI on the **uniformity slice** (PSG denominator) | Circular ROI, radius ≈ 80 px (~200 cm² per code comment) |
| **Top / Bottom** | Phase-encode ghost sampling | Rectangles at ±90° from phantom center |
| **Left / Right** | Frequency-encode **ghost-free** background controls | Rectangles at 0° / 180° |

**PSG** uses **means** of Top, Bottom, Left, Right. **SNR** uses **S̄** in a circle of about **80% of the phantom diameter** on that same uniformity slice, and **mean of σ** in the two **frequency-encode (ghost-free)** background ROIs — **Left/Right** only when frequency encode is horizontal; **Top/Bottom** when frequency encode is vertical (phase-encode ROIs would inflate σ).

---

## Quantities outside the seven accreditation tests (QC manual / site practice)

| Quantity | Typical cadence | pylinac native? | Notes |
|----------|-----------------|-----------------|-------|
| Center / resonance frequency | Weekly | **No** | Prescan / auto-tune; not image ROI math |
| Transmitter gain / attenuation | Weekly | **No** | Console parameter |
| Artifact visual checklist | Weekly | **No** | Qualitative |
| LCD trend logging | Weekly | **Partial** — score only | No historical DB in viewer yet |
| **B₀ homogeneity** (ppm over DSV) | Annual physicist | **No** | Spectroscopy / vendor service tools |
| RF coil **SNR** & **uniformity** | Annual physicist | **No SNR**; **PIU only** on accreditation slice | NEMA MS 1 / MS 3 |
| Inter-slice RF interference | Optional | **No** | Removed from 2015 QC manual default list |
| Soft-copy (monitor) QC | Annual | **No** | TG18 / institutional |
| MR safety program review | Annual | **No** | Non-image |

---

## Gap summary — not native in pylinac 3.43.2 (viewer or extension candidates)

| Gap | Priority for DICOM Viewer V3 | Planned handling |
|-----|------------------------------|------------------|
| **MRI SNR** (ACR-style uncorrected ratio; NEMA adds 0.655) | **High** — user request | **Phase 6** — live harvest in `run_acr_mri_large_analysis`; export in flatten/CSV/XLSX |
| **SNR uniformity (SNRU)** | Low | Defer — slice-6/slice-7 ratio per PMC8321175 after slice-7 `mri_snr` ships |
| **Visual high-contrast resolution** (hole-pair / line-pair read) | Low | pylinac **rMTF** is interim automated substitute; see **§Direct resolution reads** for investigation avenues |
| **Weekly QC** (center frequency, TX gain, artifact form) | Out of scope | Not image-export metrics |
| **Annual B₀ homogeneity** | Out of scope | Vendor / spectroscopy |
| **Legacy nickel-vial SNR** (1999 MRAP) | Out of scope | Superseded by Large phantom layout |
| **Two-image difference SNR** | Medium (optional) | Needs paired series acquisition — future compare/batch feature |

**Already native (export via `raw_pylinac` / flatten plan):** PIU, PSG, ghosting ratio, slice thickness/position, geometric distances, MTF grids, low-contrast score, phantom roll, echo-specific inputs.

---

## Direct resolution reads — investigation avenues (deferred)

ACR accreditation **MRI test #2** (hole pairs) and the **CT spatial-resolution module** (line-pair / bar visibility) ask for a **human visibility** read, not interpolated **rMTF@50%** alone. pylinac exports **relative** MTF grids today ([PYLINAC_CUSTOMIZATION_AND_EXTENSIONS.md](PYLINAC_CUSTOMIZATION_AND_EXTENSIONS.md) — MRI 10–90% rMTF step). Extensions below are **after** the active export plan; catalog overlap with [AUTOMATED_QA_ADDITIONAL_ANALYSIS.md](AUTOMATED_QA_ADDITIONAL_ANALYSIS.md) **C2** (MRI high-contrast) and **C24** (spatial resolution).

| Avenue | Value | Effort | False-automation risk | Depends on | Ship vs spike | Kill criteria |
|--------|-------|--------|----------------------|------------|---------------|---------------|
| **MTF interpret UI** (site rMTF cutoff → lp/mm) | **High** | Low | Low | Ph0–5 export / rMTF in CSV | **Ship** (first) | Physicists ignore UI; keep Detail grid only |
| **Assisted visual scoring** (crops + user yes/no; smallest resolved hole/line group) | **High** | Low–med | **Low** (human read) | pylinac module images / slice 1 | **Ship** (second) | Duplicates PDF-only workflow with no export benefit |
| **Line profiles** (plateau-to-valley / modulation) | Med | Med | Med | Line profile tool ([LINE_PROFILE plan](../plans/supporting/LINE_PROFILE_AND_CT_FILM_BEAM_WIDTH_PLAN.md)) | **Spike** | No stable valley metric vs visual read |
| **Pattern ROI σ** | Low | Low | **High** (mixes noise + modulation + alignment) | — | **Drop** unless paired with Rose/modulation model | Cannot correlate with physicist reads on 2+ sites |
| **Absolute MTF** | Med–high | High | Med | pylinac geometry / spike vs internals | **Spike last** | rMTF@50% + interpret UI sufficient |
| **User calibration stepping** | Med (with interpret UI) | Med | Med | MTF interpret + optional crops | **Fold into interpret UI** (persist cutoff) | Full psychometric wizard unused |

**Modality note:** CT line-pair and MRI hole-pair **geometry differs** — share profile/UX patterns, not ROI code, until both are validated.

**Deferred roadmap (Grok 4.6 + maintainer):** (1) MTF interpret UI after export plan → (2) assisted visual scoring → (3) SNRU slice 6÷7 after Phase 6 `mri_snr` → (4) line-profile / absolute-MTF spikes. See [FUTURE_WORK_DETAIL_NOTES.md](../FUTURE_WORK_DETAIL_NOTES.md#interpreting-mtf-results).

---

## Phase 6+ pointer (SNR / SNRU)

- **Phase 6 MRI SNR** — [PYLINAC_ACR_FULL_METRICS_EXPORT_AND_MRI_BATCH_PLAN.md](../plans/supporting/PYLINAC_ACR_FULL_METRICS_EXPORT_AND_MRI_BATCH_PLAN.md) **Phase 6**; R6-* checklist there.
- **SNRU** (slice 6÷7 ratio, optional) — **Phase 6+** in the same plan; after `mri_snr` ships; no default pass/fail in v1.

# Plan: Line profile and CT film beam-width analysis

## Goal and success criteria

Add a general line profile tool for manual image analysis and a specialized CT film beam-width workflow for scanned film images.

Success means:

- Users can draw, edit, move, and measure a line profile on a loaded image and see the sampled intensity profile.
- Profile plots can report distance in pixels, image-calibrated units, or mm when pixel spacing/DPI is known.
- CT film beam-width analysis can detect the dominant radiation-darkening direction on a scanned film strip, build a baseline-corrected profile, and report full-width half-maximum (FWHM) and full-width tenth-maximum (FWTM).
- The automated result is inspectable and adjustable: users can override the profile line, calibration/DPI, baseline region, direction, smoothing/window size, and threshold levels.
- Results are exportable with provenance: image identity, calibration source, profile endpoints, baseline method, local-max window, FWHM/FWTM values, and warnings.

## Context and links

- Backlog: [`dev-docs/TO_DO.md`](../../TO_DO.md), near-term features and Tier C measurements.
- Related QA context:
  - [`AUTOMATED_QA_ADDITIONAL_ANALYSIS.md`](../../info/AUTOMATED_QA_ADDITIONAL_ANALYSIS.md) includes CT phantom slice-thickness/profile concepts.
  - [`PYLINAC_CATPHAN_AND_NUCLEAR_MODULES.md`](../../info/PYLINAC_CATPHAN_AND_NUCLEAR_MODULES.md) notes FWHM/FWTM profile analysis in nuclear modules.
- Related UI/measurement areas:
  - ROI/measurement graphics and exports should remain consistent with existing measurement tools.
  - Manual length calibration item in `TO_DO.md` is relevant when DPI/pixel spacing is missing.

## Task graph and gates

### Ordering

- S1 -> Gate 1 -> T1/T2.
- T1 -> T3/T4.
- S2 -> Gate 2 -> T5/T6.
- T3/T5 -> T7.
- T7 -> Gate 3 -> T8/T9.

### Verification gates

- Gate 1: reviewer approves line-profile sampling and unit/calibration model before UI wiring.
- Gate 2: reviewer approves CT film beam-width algorithm assumptions before automated reporting is exposed.
- Gate 3: tester verifies manual measurement and automated CT-film examples before user docs mark the workflow supported.

## Phases

### Phase 1 - Generic line profile tool

- [ ] (S1) Audit existing measurement/ROI graphics code and decide whether line profiles are a measurement type, ROI subtype, or separate analysis overlay. (owner: coder, parallel-safe: yes, stream: A, after: none)
- [ ] (T1) Implement profile sampling over image data along a line segment with interpolation choice, endpoint metadata, and support for raw vs rescaled values where applicable. (owner: coder, parallel-safe: no, stream: none, after: Gate 1)
- [ ] (T2) Define calibration handling: DICOM pixel spacing, non-DICOM image DPI metadata, manual DPI entry, manual known-distance calibration, and pixel-only fallback. (owner: coder/ux, parallel-safe: no, stream: none, after: Gate 1)
- [ ] (T3) Add interactive profile drawing/editing: create line, drag endpoints, move line, show length, show profile plot, and allow manual profile measurement over a user-selected line. (owner: ux/coder, parallel-safe: no, stream: none, after: T1)
- [ ] (T4) Add profile export to CSV/XLSX/JSON with sample index, distance, calibrated distance, intensity, line endpoints, calibration source, and viewer/raw/rescaled value mode. (owner: coder, parallel-safe: no, stream: none, after: T1)

### Phase 2 - CT film beam-width automation

- [ ] (S2) Spike CT film algorithm on synthetic and representative scanned-film examples: direction detection, baseline/background estimation, dark-vs-light polarity, smoothing, local maximum window, and FWHM/FWTM crossing interpolation. (owner: researcher/coder, parallel-safe: yes, stream: B, after: none)
- [ ] (T5) Add automated dominant-axis detection for film strips by comparing profile variation along candidate directions; prefer the axis where radiation darkening rises and falls, and warn when both directions are flat or ambiguous. (owner: coder, parallel-safe: no, stream: none, after: Gate 2)
- [ ] (T6) Add baseline/background correction with user-adjustable baseline region/method and support for inverted polarity when film darkening corresponds to lower or higher numeric pixel values depending on scan/import. (owner: coder/ux, parallel-safe: no, stream: none, after: Gate 2)
- [ ] (T7) Add FWHM/FWTM computation using a local-window maximum, defaulting to a small window such as 5 px, with configurable smoothing/window size and sub-pixel crossing interpolation. (owner: coder, parallel-safe: no, stream: none, after: T5)
- [ ] (T8) Add CT film beam-width result UI with detected direction overlay, profile plot, baseline-corrected profile, half/tenth max markers, warnings, manual override controls, and mm/pixel reporting. (owner: ux/coder, parallel-safe: no, stream: none, after: Gate 3)
- [ ] (T9) Add export/report integration for CT beam-width results, including FWHM/FWTM in pixels and mm when calibrated, DPI/calibration source, baseline method, local-max window, and algorithm warnings. (owner: coder, parallel-safe: no, stream: none, after: T8)

## Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Scanned film image lacks reliable DPI metadata | Prompt for DPI or report pixel units; record calibration source explicitly. |
| Numeric polarity differs by scanner/import path | Detect and expose dark-vs-light polarity; allow manual inversion. |
| Single-pixel noise corrupts max-based widths | Use a local-window maximum and optional smoothing; record window size. |
| Baseline/background varies across the film | Support baseline region selection and compare constant vs local baseline methods. |
| Direction detection picks the strip width instead of beam-width axis | Compare profile variation along axes, show overlay preview, and require user confirmation when confidence is low. |
| FWHM/FWTM crossing is unstable on noisy profiles | Use interpolation plus warnings when crossings are missing, duplicated, or low contrast. |
| Tool scope grows into a full film dosimetry package | Keep first scope to geometric beam-width metrics, not dose calibration. |

## Modularity and file-size guardrails

- Keep profile sampling and width calculations in testable core/analysis modules without Qt dependencies.
- Keep plotting/UI in GUI modules that consume structured profile/result objects.
- Reuse export serialization patterns from QA/ROI/profile exports where practical.
- Keep CT film beam-width analysis separate from generic line-profile measurement so the manual tool can ship first.

## Testing strategy

- Unit tests:
  - line sampling on synthetic arrays for horizontal, vertical, diagonal, and sub-pixel lines,
  - distance calibration from pixel spacing, DPI, manual DPI, and pixel-only fallback,
  - baseline correction on synthetic profiles,
  - local-window maximum behavior vs a noisy single-pixel spike,
  - FWHM/FWTM crossing interpolation on known synthetic profiles,
  - direction detection on synthetic film-strip images.
- Integration/UI tests where feasible:
  - draw and edit a line profile and verify plot/result updates,
  - run CT film beam-width analysis and override DPI/direction/baseline,
  - export profile/result CSV/JSON and verify provenance fields.
- Manual validation:
  - scanned film with DPI metadata,
  - scanned film without DPI metadata,
  - dark-on-light and light-on-dark imports,
  - ambiguous/flat profile case.

## UX / UI

- Add a line-profile tool near measurement tools, with profile plot opening in a dock/dialog.
- CT film beam-width can live under Tools/QA or the profile dialog as a specialized analysis mode.
- Show width results in pixels and mm when calibrated.
- Keep manual measurement possible even when automated direction/baseline detection fails.

## Questions for user

- Should CT film beam-width analysis accept ordinary image files immediately, or only images already loaded into the viewer?
- Should the first UI live in measurement tools, QA tools, or both?
- Should default local maximum window be fixed at 5 px first, or based on DPI/expected film resolution?
- Are representative scanned-film examples available for validation?

## Completion notes

Not started. This is a docs-only supporting plan as of 2026-06-11.

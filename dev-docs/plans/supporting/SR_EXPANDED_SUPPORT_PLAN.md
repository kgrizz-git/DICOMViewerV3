# SR expanded support beyond dose SR - implementation plan

**Created:** 2026-05-25
**Covers TO_DO item:**
- [P1] Expand Structured Report support beyond dose SR

**Related:** `dev-docs/TO_DO.md` (UX / Workflow), `dev-docs/plans/supporting/SR_FULL_FIDELITY_BROWSER_PLAN.md`, `dev-docs/plans/supporting/SR_DOSE_EVENTS_NORMALIZATION_AND_HIGHDICOM_PLAN.md`, `src/core/sr_sop_classes.py`, `src/core/sr_document_tree.py`, `src/gui/dialogs/structured_report_browser_dialog.py`, `src/core/rdsr_dose_sr.py`

---

## Context

The repo now recognizes SR datasets and has a generic SR browser plus dose-specific handling for RDSR. That is a strong foundation, but real-world SR support is still uneven:

- Dose SR has specialized parsing and summary views.
- Other SR families mostly fall back to the generic `ContentSequence` tree.
- Text-heavy or radiologist-style SRs are not surfaced as first-class report documents yet.
- Several SR-adjacent document types are identified by SOP class but do not have tailored workflows.

This plan expands support in a staged way without losing the current generic-tree fallback.

---

## Goals

1. Classify major SR families more clearly at load time and in the UI.
2. Distinguish dose SR from narrative/text SR, CAD SR, KO/procedure-log style documents, and generic unknown SR.
3. Make common non-dose SRs easier to interpret without requiring users to read only raw tags or a deep tree.
4. Preserve one generic browser path for all SRs, with specialized tabs or summaries added only where they add real value.
5. Keep scope realistic: detection and presentation first, template-specific parsing second.

---

## Current state

### What the repo already does well

- Detects many SR-family SOP classes in `src/core/sr_sop_classes.py`.
- Opens SRs in the modeless Structured Report browser.
- Builds a generic document tree from `ContentSequence`.
- Provides specialized dose handling for RDSR-like files.

### Gaps to close

- No higher-level SR family classification for status messages, overlays, or load summaries.
- No lightweight narrative-report presentation for text-centric SRs.
- No dedicated handling yet for common non-dose workflows like measurement reports, CAD SR review, or procedure logs.
- Key Object Selection Documents are identified, but the SR/browser path and the separate KO annotation path are not yet framed as one coherent document-support strategy.

---

## Scope buckets

### Bucket A - Classification

Add a small SR family classifier that maps a dataset to a user-facing family label and default presentation mode.

Initial family buckets:

- `Radiation dose SR`
- `Narrative / text SR`
- `Measurement / quantitative SR`
- `CAD SR`
- `Key Object / reference document`
- `Procedure / acquisition log`
- `Other structured report`

Signals may include:

- `SOPClassUID`
- `Modality`
- root/content concept codes
- presence of text-heavy vs numeric-heavy content
- known template signatures where cheap and reliable

Deliverable: one non-Qt helper module returning a structured classification result.

### Bucket B - Better presentation for narrative SRs

For Basic Text SR / many Comprehensive SR style documents:

- detect likely report sections such as Findings, Impression, Conclusion, Recommendation, History, Technique when concept names or headings make that possible
- present a simple "Report" tab above the raw tree when extraction is reliable enough
- fall back to the generic tree when extraction is partial or ambiguous

This is meant to help with radiologist-style SR documents, not to guess free text out of arbitrary trees.

### Bucket C - Better presentation for measurement / CAD style SRs

Investigate common structured measurement or CAD-report patterns, including TID-driven content where supported by `highdicom` or practical pydicom walks.

Potential targets:

- measurement-report style SRs
- Mammography / Chest / Colon CAD SR
- implantation-plan and related planning SRs

Phase goal is not full clinical interpretation. It is to identify whether a stable plugin path exists and document the first worthwhile target.

### Bucket D - SR-adjacent document workflow cleanup

Clarify the relationship between:

- generic SR browser
- RDSR-specific tabs
- Key Object document handling
- Procedure Log documents
- tag viewer fallback

Users should get a consistent answer to "what kind of document is this?" and "what is the best way to read it here?"

---

## Phased plan

### Phase 0 - Inventory and fixture matrix

- [ ] Build a small matrix of committed or locally available SR examples by SOP class and likely family.
- [ ] Record which examples are dose, text-centric, CAD-like, KO-like, or unknown.
- [ ] For each sample, note whether the current browser is already acceptable, confusing, or clearly missing a summary layer.
- [ ] Add any missing tiny synthetic fixtures only where a focused test truly needs them.

**Gate:** one markdown matrix added to this plan or a linked note with representative SR categories.

### Phase 1 - Family classifier and UI labels

- [ ] Add `classify_structured_report_dataset(ds)` helper returning:
  - family id
  - display label
  - confidence / reason
  - suggested default tab or mode
- [ ] Reuse existing SOP-class registry rather than duplicating constants.
- [ ] Surface the classification in:
  - no-pixel SR messaging
  - Structured Report browser title/subtitle
  - optional load/status text where helpful
- [ ] Add focused tests for representative classifications.

**Gate:** SRs no longer appear only as generic "Structured Report" when the family is known.

### Phase 2 - Narrative/text SR presentation

- [ ] Design a minimal "Report" tab for text-centric SRs.
- [ ] Extract readable sections when concept names or headings are stable enough.
- [ ] Keep privacy-mode behavior aligned with the existing SR browser and metadata masking.
- [ ] Fail soft: if section extraction is weak, show generic tree plus a note instead of inventing structure.
- [ ] Add at least one fixture-backed test for section extraction and one for graceful fallback.

**Gate:** at least one text-centric SR path is meaningfully easier to read than the raw tree alone.

### Phase 3 - Measurement/CAD/plugin decision

- [ ] Decide the first non-dose specialized plugin target after narrative SR.
- [ ] Compare pydicom-only vs `highdicom` for that target if the template path is complex.
- [ ] Document whether the target earns:
  - a dedicated tab/table
  - a summary card only
  - tree-only support for now
- [ ] Add a bounded implementation only if the sample set justifies it.

**Gate:** written go/no-go decision for the first extra plugin family.

### Phase 4 - Workflow consolidation

- [ ] Review overlap between SR browser, KO handling, and tag-viewer fallback.
- [ ] Decide which document families should open directly to a specialized tab and which should default to the tree.
- [ ] Update user-facing docs/help text once behavior settles.

**Gate:** a user can load a non-pixel DICOM document and quickly understand what it is and how best to read it.

---

## Risks and guardrails

- Do not overfit to one vendor's concept naming for narrative section extraction.
- Do not claim a "radiologist report parser" unless the supported document shapes are clearly bounded.
- Keep generic tree fallback available for every SR family.
- Avoid a large dependency expansion unless `highdicom` provides a clear benefit for a chosen plugin target.
- Keep privacy-mode masking consistent across any new text-summary views.

---

## Verification

- Classification unit tests for representative SOP classes and fallback `Modality=SR`.
- Fixture-backed tests for narrative/text SR extraction when implemented.
- Manual check that SR browser titles, no-pixel overlays, and tabs match the detected family.
- If `highdicom` is introduced for a new plugin path, verify packaging and startup/import impact before merging.

---

## Out of scope for this plan

- Replacing the generic SR tree with a fully template-aware browser for every SR class.
- Clinical-grade interpretation of all report templates.
- OCR or free-text parsing of non-SR radiology reports.
- Encapsulated PDF report support unless it is explicitly added as a separate document-family effort.

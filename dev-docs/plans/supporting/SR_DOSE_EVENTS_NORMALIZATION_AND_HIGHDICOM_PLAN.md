# SR dose-events robustness — normalization (Stage 1) and highdicom (Stage 2)

**Status:** Draft — actionable checklist for orchestration / implementation  
**Related:** `dev-docs/TO_DO.md` § Features (Near-Term) highdicom item; [SR full fidelity browser plan](SR_FULL_FIDELITY_BROWSER_PLAN.md) (architecture, lazy tree, highdicom allowance §4); [HIGHDICOM research](../../info/HIGHDICOM_OVERVIEW.md); current extractors `src/core/rdsr_irradiation_events.py`, `src/core/sr_document_tree.py`, `src/core/rdsr_dose_sr.py`

---

## Goal and success criteria

1. **Stage 1 (normalization & heuristics):** Reduce silent misses and wrong “first hit” choices for **irradiation-event table** columns when vendors vary **coding scheme designators**, **code value** forms, **multiplicity**, or **nesting**—without adding new runtime dependencies. Observable behavior when data are ambiguous or truncated.
2. **Stage 2 (highdicom):** Where a **supported highdicom SR / TID** path exists for radiation dose SR, optionally parse or validate content **template-aware**, then feed the same **column contract** used by the Structured Report browser’s **Dose events** tab (or a documented superset), with **safe fallback** to the existing pydicom-only path.

**Success (Stage 1 complete):** Checklist items through Phase 1.5 done; tests green; at least one note or metric when caps or duplicate candidates apply.  
**Success (Stage 2 complete):** Optional highdicom-backed path behind a clear switch (env or config); PyInstaller/import and license documented; CI runs tests with and without highdicom optional extra if feasible.

---

## Context

- Today’s **dose events** table is built by flattening descendants under **113706** / **113819** (and meaning-matched event roots) plus fixed DCM codes and **dynamic** columns for other typed leaves (`rdsr_irradiation_events.py`). This is fast and dependency-light but **not TID-complete**.
- **SR full fidelity** work (separate plan) covers lazy tree, exports, and long-term UX; *this* plan focuses on **tabular dose-event correctness** and the **highdicom adoption** called out in `TO_DO.md`.

---

## Task graph and gates

### Ordering

- **Stage 1 (Phases 1.1–1.5)** completes before **Stage 2 Phase 2.1** begins (normalization and interfaces stabilize the contract highdicom must satisfy).
- **Stage 2 Phase 2.0 (spike)** must complete and pass **Gate S** before Phase 2.2 merges highdicom into any user-facing default path.

### Verification gates

| Gate | When | Requirement |
|------|------|----------------|
| **G1** | After Phase 1.2 | Reviewer: no regression on committed fixtures in `tests/test_sr_document_tree.py` / dose SR tests; new unit tests for normalization helpers. |
| **G2** | After Phase 1.4 | Tester: `pytest` relevant suites green (full suite for release branch). |
| **Gate S** | After Phase 2.0 spike | Document: dependency pin, import cost, license, fallback behavior; orchestrator approves proceeding to 2.2. |

### Parallelism

- Phase 1.3 (truncation notes) can proceed **in parallel** with Phase 1.1 once module boundaries agreed (`parallel-safe: yes` for docs-only follow-ups).
- Phase 2.3 (CI matrix) **after** 2.1 adapter exists.

---

## Stage 1 — Normalization and heuristic hardening

*Objective: maximum practical robustness **without** highdicom.*

### Phase 1.1 — Concept identity normalization (owner: coder)

- [x] **(T1.1)** Add a small **`sr_concept_identity`** (or extend `rdsr_dose_sr` with shared helpers) module: normalize `(CodeValue, CodingSchemeDesignator)` for matching:
  - [x] Strip / case-fold designator where DICOM allows equivalence (document which folds are applied; do not fold URN schemes incorrectly).
  - [x] Support **Long Code Value** (`LongCodeValue`) when `CodeValue` empty (read from first concept name item).
  - [x] Optional: **Coding Scheme Version** ignored for equality v1; document as limitation or add version-aware map later.
- [x] **(T1.2)** Route `_concept_matches` / fixed-column lookups through normalized comparison; keep **dynamic** column titles using human-readable original strings from the file where possible.
- [x] **(T1.3)** Unit tests: paired fixtures or synthetic items for long-code + designator variants.

### Phase 1.2 — Multi-candidate and ambiguity (owner: coder)

- [x] **(T2.1)** For selected high-risk columns (e.g. **source-to-detector**, **exposure time**, meaning-keyword NUMs), detect **multiple** qualifying items in one event subtree.
- [x] **(T2.2)** Policy: prefer **113xxx DCM** exact match over keyword; prefer **shallower** depth or **CONTAINS** under known geometry containers when ties remain; document order in module docstring.
- [x] **(T2.3)** When policy still leaves ambiguity, append a short **per-row or extraction-level note** (e.g. into `IrradiationEventExtraction.notes` or a new `warnings` list) — do not fail silently.
- [x] **(T2.4)** Tests: synthetic `ContentSequence` with two competing NUMs; assert note or deterministic winner per policy.

### Phase 1.3 — Truncation and cap observability (owner: coder)

- [x] **(T3.1)** When `_flatten_descendants` hits **max_items** or **max_depth**, set a flag on the extraction result (e.g. `truncated_subtree: bool` or per-row) and surface one line in **Dose events** UI or dialog notes (wire through `StructuredReportBrowserDialog` from extraction).
- [ ] **(T3.2)** Consider raising `max_items` only after profiling; if raised, document memory impact in plan completion notes.

### Phase 1.4 — NUM / CODE presentation edge cases (owner: coder)

- [x] **(T4.1)** Evaluate **first** `MeasuredValueSequence` vs **multi-value** NUM (document “first only” or concatenate with `; ` for dynamic columns).
- [x] **(T4.2)** **UIDREF** / **113769**: already partial; confirm **TEXT** carry of UID in vendor files and extend if seen in fixtures.
- [x] **(T4.3)** Regression tests from **committed** `tests/fixtures/dicom_rdsr/`; optional local samples under `test-DICOM-data/` documented only.

### Phase 1.5 — Documentation (owner: docwriter | coder)

- [x] **(T5.1)** Short subsection in `user-docs/USER_GUIDE.md` or `dev-docs/info/`: “Dose events table is heuristic / template-hinted; use Document tab for full tree.”
- [x] **(T5.2)** Cross-link this plan from [SR_FULL_FIDELITY_BROWSER_PLAN.md](SR_FULL_FIDELITY_BROWSER_PLAN.md) §6 or appendix if appropriate (one sentence).

---

## Stage 2 — highdicom integration

*Objective: template-aware parsing **where it helps**, with pydicom fallback and bundle discipline.*

### Phase 2.0 — Spike and dependency decision (owner: researcher | coder, timebox: 1–2 sessions)

- [ ] **(S1)** Spike: `pip install highdicom` in venv; load **one** X-Ray RDSR + **one** Enhanced X-Ray RDSR from `tests/fixtures/dicom_rdsr/` (and optional local Philips sample if available).
- [ ] **(S2)** Record: which TID / SOP classes highdicom can **materialize** vs still require generic walk; **license** compatibility; **import time** and **PyInstaller** hidden-import needs (see `SR_FULL_FIDELITY_BROWSER_PLAN.md` §4, `dev-docs/info/` bundle notes).
- [ ] **(S3)** **Gate S:** decision table — adopt highdicom for (A) dose-event row build only, (B) validation + pydicom display, or (C) defer if no win vs Stage 1; update this plan’s “Completion notes”.

### Phase 2.1 — Adapter interface (owner: coder)

- [ ] **(T6.1)** Define a narrow protocol or functions, e.g. `build_irradiation_event_rows(ds: Dataset) -> IrradiationEventExtraction`, internally selecting **backend**: `pydicom_flat` | `highdicom` based on config + SOP class + spike outcomes.
- [ ] **(T6.2)** Keep **public column keys** stable for CSV/XLSX export where possible; map highdicom output into existing key names or version export with a `schema_version` row (decide in 2.0).

### Phase 2.2 — highdicom-backed extraction (owner: coder)

- [ ] **(T7.1)** Implement backend for at least **one** storage class verified in spike (e.g. Enhanced X-Ray Radiation Dose SR **if** supported).
- [ ] **(T7.2)** On any **highdicom** exception or unsupported document, **fall back** to current `extract_irradiation_events` without crashing; log debug line behind `DEBUG_*` flag if present.
- [ ] **(T7.3)** Tests: mock or fixture-driven; optional `pytest.importorskip("highdicom")` for optional extra in `requirements-dev.txt` or extras `[sr-highdicom]` in `pyproject.toml` / docs — align with repo dependency policy.

### Phase 2.3 — CI and packaging (owner: coder | secops)

- [ ] **(T8.1)** CI: default job unchanged; optional workflow or marker job **with** highdicom extra if network/install acceptable.
- [ ] **(T8.2)** Update frozen build docs: optional bundle with highdicom vs slim without; size baseline per `PYINSTALLER_BUNDLE_SIZE` docs.

### Phase 2.4 — Product toggle and UX (owner: coder | ux)

- [ ] **(T9.1)** User-facing or developer-only toggle (document which): e.g. environment variable `DICOMVIEWER_SR_DOSE_BACKEND=highdicom|pydicom|auto`.
- [ ] **(T9.2)** If `auto`: prefer highdicom only when import succeeds and SOP/TID in allowlist from spike.

---

## Risks and mitigations

| Risk | Mitigation |
|------|------------|
| highdicom **does not cover** all vendor RDSR shapes | Mandatory pydicom fallback; Stage 1 improves fallback quality. |
| **Bundle size** growth | Optional extra / slim build; spike documents import graph. |
| False confidence from partial TID support | UI copy + notes: “template-assisted” vs “generic flatten.” |
| Duplicate columns after Stage 2 merge | Adapter dedupes against `_FIXED_CONCEPT_CODES` / same keys as Stage 1. |

---

## Testing strategy

- **Stage 1:** Unit tests for normalization + ambiguity + truncation flags; no new large binaries in repo without fixture size policy (`tests/fixtures/dicom_rdsr/README.md`).
- **Stage 2:** Contract tests: same fixture produces **non-worse** column coverage vs pydicom path (define per-fixture expected keys in test). Optional skip when highdicom not installed.

---

## Modularity and file-size guardrails

- Prefer **`src/core/sr_concept_identity.py`** (or similar) under **~300 lines**; keep `rdsr_irradiation_events.py` orchestration-only where possible.
- highdicom imports **lazy** (inside backend function) to avoid slowing app startup when unused.

---

## Questions for user / product (non-blocking for Stage 1)

- Should **highdicom-on** ever become **default** for dose SR, or remain opt-in for power users / research builds?
- Tolerance for **extra columns** when highdicom exposes more structured fields than the flat table today?

---

## Completion notes

- **2026-04-16 — Stage 1 (partial):** Implemented Phases **1.1–1.4** and **1.5** (except **T3.2** profiling / default `max_items` change): `src/core/sr_concept_identity.py`, hardened `src/core/rdsr_irradiation_events.py` (normalized matching, depth-aware NUM/CODE/TEXT picks, ambiguity `notes`, `truncated_subtree` / per-row `subtree_truncated`, multi-`MeasuredValueSequence` joined with `; `, **113769** TEXT), `StructuredReportBrowserDialog` summary when capped, `tests/test_sr_document_tree.py`, **USER_GUIDE**, cross-link from **SR_FULL_FIDELITY_BROWSER_PLAN** § Phase 3. **Stage 2** (highdicom) not started; **T3.2** remains open pending profiling.

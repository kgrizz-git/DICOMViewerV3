# PySkinDose integration

**Status:** Draft — supports **P1** item in [`dev-docs/TO_DO.md`](../../TO_DO.md) (Features, near-term)  
**Last updated:** 2026-04-17  
**Related:** Sample path `test-DICOM-data/pyskindose_samples/`; RDSR UI in **Tools** and SR browser; `src/core/rdsr_*`, `src/gui/dialogs/structured_report_browser_dialog.py`

---

## Purpose

Optional **peak skin dose / 3D skin dose map** workflows built on **X-Ray Radiation Dose SR (RDSR)** that the viewer already loads, tabulates, and can export—without turning the viewer into a regulated dose-calculation product unless product/legal scope explicitly expands later.

---

## What PySkinDose is (scope)

**PySkinDose** ([`pyskindose` on PyPI](https://pypi.org/project/pyskindose/), [GitHub `rvbCMTS/PySkinDose`](https://github.com/rvbCMTS/PySkinDose)) is an open-source **Python** toolkit that estimates **patient peak skin dose** and **skin dose distributions** from **DICOM RDSR** (fluoroscopy / interventional-style dose reports), including geometry-aware mapping onto phantoms and **interactive Plotly HTML** outputs. License is **MIT** on the upstream repo (verify the exact release **LICENSE** before bundling).

It is **not** a general-purpose DICOM viewer; it is a **dose estimation** layer that expects RDSR inputs and normalization settings.

---

## Relationship to this viewer today

| Viewer capability | Relevance to PySkinDose |
|-------------------|-------------------------|
| Load RDSR / SR, navigator, tag browser, **Dose events** table | Source data and QA surface — columns should align with what PySkinDose or its **normalization settings** expect |
| JSON/CSV export of dose events | Potential **bridge** to external PySkinDose runs without embedding the library |
| Pylinac / QA tooling | Separate domain (phantom QA vs patient skin dose) — do not conflate UX |

---

## Integration strategies (pick after Phase 0 spike)

Ordered from **lowest** coupling to **highest**:

| Tier | Approach | Pros | Cons |
|------|-----------|------|------|
| **T0** | **Documented external workflow** — export RDSR from viewer or disk; user runs PySkinDose in their own venv | No new deps, no version lock | Poor discoverability |
| **T1** | **“Open with…” / launcher** — viewer writes a temp folder or manifest and invokes `python -m pyskindose` if configured | Keeps heavy deps out of default install | Path/config support, error UX |
| **T2** | **Optional dependency** (`extras_require` / optional install) — menu action **Tools → Peak skin dose (PySkinDose)…** calls library API | Integrated UX | **NumPy 2.x**, **pandas**, **plotly**, **scipy** pin conflicts with frozen app; **PyInstaller** size; support burden |
| **T3** | **Embedded WebEngine / browser** for HTML output | Polished in-app review | Qt + Plotly security/size; highest engineering cost |

**Recommendation:** complete **Phase 0** before choosing **T1 vs T2** for a first release. Default product stance should remain **diagnostic viewer**, not a regulated **dose calculation** product—**disclaimers** and **“research / educational”** labeling belong in user docs if any in-app launcher ships.

---

## Phase 0 — Technical spike (blocking)

- [ ] **(P0.1)** In a **throwaway venv**, install `pyskindose` alongside this project’s `requirements.txt`; record **version conflicts** (if any) with pinned packages.
- [ ] **(P0.2)** Run PySkinDose on **at least one real RDSR** (not placeholder HTML in `pyskindose_samples` if still invalid) and on **`tests/fixtures/dicom_rdsr/`** where applicable; note required **normalization** JSON/YAML if the library mandates it.
- [ ] **(P0.3)** Decide **minimum API surface** (file path in → HTML or numeric grid out) and whether the viewer passes **filesystem paths** or **in-memory `Dataset`**.
- [ ] **(P0.4)** **Gate A:** short decision memo in this plan or `dev-docs/info/`: chosen tier (**T0–T2**), license/transitive deps, **PyInstaller** impact if **T2**.

---

## Phase 1 — MVP (after Gate A)

- [ ] **(P1.1)** If **T1**: settings for PySkinDose executable / module path; stdout/stderr capture; user-visible failure modes.
- [ ] **(P1.2)** If **T2**: isolate imports; background worker (Qt thread) so UI stays responsive; output path under user temp or export folder.
- [ ] **(P1.3)** User guide paragraph: what inputs are supported, what PySkinDose computes, and that **clinical use** is the user’s responsibility.
- [ ] **(P1.4)** Tests: **mock** PySkinDose entrypoint in CI; optional **manual** job with real install documented in `tests/README.md`.

---

## Phase 2 — Polish (optional)

- [ ] Link from **SR browser** or **Dose events** tab: “Estimate skin dose…” when SOP class indicates X-Ray RDSR.
- [ ] Batch folder processing vs single-instance only—product decision.

---

## Risks

| Risk | Mitigation |
|------|------------|
| **Dependency bloat** (plotly/scipy/pandas stack) | Prefer **T0/T1** first; extras optional |
| **Medical-device claims** | UX copy + docs: viewer displays and exports; PySkinDose authors own algorithm validation |
| **Bad or synthetic fixtures** | CI uses committed DICOM bytes under `tests/fixtures/`; gitignored samples for dev only |
| **Duplicate SR logic** | Single **irradiation-event** extraction module as source of truth; PySkinDose consumes files or a **stable JSON schema** exported from that module |

---

## Open questions

1. **Product:** Is in-app PySkinDose (**T2**) a goal, or is **external tool + export** enough for v1?
2. **Clinical:** Any institutional requirement to log **software version** of dose engines used for a given study?
3. **Platform:** Will frozen **Windows** builds be the only target for integration, or must **macOS** parity be guaranteed day one?

---

## Changelog (this plan file)

| Date | Change |
|------|--------|
| 2026-04-17 | Initial PySkinDose-only plan |
| 2026-04-17 | Split from former umbrella doc; highdicom/SR rollout tracked only in `TO_DO.md` + SR plans |

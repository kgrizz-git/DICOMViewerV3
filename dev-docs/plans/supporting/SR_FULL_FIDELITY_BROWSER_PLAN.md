# SR full-fidelity browser and RDSR per-event presentation — implementation plan

**Status:** Draft for implementation — **product decisions locked** (revision below, 2026-04-17)  
**Related:** `dev-docs/TO_DO.md` (UX / SR full fidelity), `dev-docs/plans/supporting/HANGING_PROTOCOLS_PRIORS_RDSR_PLAN.md` §3 (existing RDSR MVP), `src/core/rdsr_dose_sr.py`, `src/gui/dialogs/radiation_dose_report_dialog.py`, `src/core/tag_export_writer.py` / `openpyxl` (reuse for **.xlsx** export), `test-DICOM-data/pyskindose_samples/` (local samples; gitignored — **CI fixtures** under `tests/fixtures/`, see §11)

---

## 1. Goals

1. **Full fidelity** for Structured Reports in the viewer: every content item in the SR document tree is discoverable and presentable—not only a small fixed subset of dose metrics.
2. **Per-event rows** for fluoroscopy (and other) **X-Ray Radiation Dose SR** instances: irradiation events appear as first-class table rows with nested parameters (DAP, kVp, pulse data, duration, etc.) when present in the file.
3. **Extensible coverage** of **SR storage SOP classes** and real-world **template** patterns (standard TID roots, vendor extensions, post-coordinated concepts)—without claiming “one UI fits all” before inventory.
4. **Clear separation** in the **UX** (not duplicate menus): **SR document browser** hosts the tree, template-driven dose tables, raw tag tab, and **exports**; any **legacy CT-style dose strip** from `RadiationDoseReportDialog` is absorbed as a **tab** or section inside that browser until removed (Phase 4).

---

## 2. Research summary — can we “determine fields from the file”?

### 2.1 Yes — dynamic discovery is the norm for generic SR

- The clinical payload of an SR lives primarily in **`ContentSequence` (0040,A730)** under the **SR Document Content** module: a **recursive tree** of items with attributes such as **Value Type** (0040,A040), **Concept Name Code Sequence**, **Relationship Type**, measured values, nested sequences, references to images/SOP instances, spatial coordinates, etc.
- **Any SR** can be walked generically: children are **not** limited to a single fixed list of top-level DICOM attributes. The set of “fields” is **the tree**, not eleven rows.
- **Standards** in DICOM constrain *valid* documents and provide **templates** (e.g. **TID** tables in PS3.16) and **relationship rules** (e.g. Basic Text SR allows only certain value types). Real devices still ship **template-compliant** trees, **profiled** variants, and **vendor extensions** (additional `CONTAINER` / `NUM` / `CODE` nodes).

### 2.2 “A few defined standards” is only half true

- **Storage SOP Class** (e.g. Basic Text vs Comprehensive vs **X-Ray Radiation Dose SR**) tells you **IOD-level** capabilities (which value types are allowed, whether waveform/SCOORD exist, etc.). See PS3.3 **A.35** Structured Report Document IODs ([Structured Report IODs](https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_A.35.html)) and PS3.4 **B.5** standard SOP classes ([Standard SOP Classes](https://dicom.nema.org/medical/dicom/current/output/chtml/part04/sect_B.5.html)).
- **Within** a class (especially **Comprehensive SR** and **X-Ray Radiation Dose SR**), **content** is organized by **templates** (TID) from PS3.16—e.g. **TID 10001** Projection X-Ray Radiation Dose, **TID 10040** Enhanced X-Ray Radiation Dose, nested **TID 10003** Irradiation Event X-Ray Data ([TID 10003](https://dicom.nema.org/medical/dicom/current/output/chtml/part16/sect_TID_10003.html)), **TID 10003B** source data including fluoro-specific rows ([TID 10003B](https://dicom.nema.org/medical/dicom/current/output/chtml/part16/sect_tid_10003b.html)), etc. ([X-Ray Radiation Dose SR IOD Templates](https://dicom.nema.org/medical/dicom/current/output/chtml/part16/sect_xrayradiationdosesriodtemplates.html)).
- **Conclusion:** Implement **(A)** a **generic tree** for 100% of nodes (full fidelity display), plus **(B)** optional **template-aware** extractors (tables) where we invest engineering (RDSR per-event first).

---

## 3. Current product state (gap analysis)

| Area | Today | Gap vs full fidelity |
|------|--------|----------------------|
| **Radiation dose report dialog** | Fixed rows from `CtRadiationDoseSummary` (`radiation_dose_report_dialog._populate_table`) | Not a document browser; CT-biased NUM codes in `rdsr_dose_sr`; fluoro-rich TID 10003 content largely invisible |
| **Tag viewer / metadata** | Flat `get_all_tags` / `iterall` + `file_meta` | Lists elements but not SR **semantics** (relationship, nesting, concept display names); poor for “how clinicians expect SR” |
| **Parser** | `rdsr_dose_sr` bounded walk for dose **signature** + summary | By design **not** a full SR renderer |

---

## 4. Target architecture

### 4.1 Layers

1. **SR document model (non-Qt)**  
   - Build an in-memory **tree** (or list of nodes with parent pointers) from `Dataset`: start at root `ContentSequence` items attached to the SR document content module (per pydicom layout).  
   - Each node: concept name (code meaning string if resolvable), value type, relationship type, raw value representation, children, optional references (IMAGE/COMPOSITE UID), measurement units, qualifiers.  
   - **Unit tests:** prefer **targeted asserts** (node count bands, presence of key concept codes, depth-cap behavior) on **committed** files under `tests/fixtures/` (see §11); optional **small** JSON golden for one minimal SR. Local `pyskindose_samples/` supplements dev-only runs.

2. **Generic SR browser UI**  
   - **Primary:** `QTreeView` + **lazy** model (populate children on expand, or windowed fetch)—avoid building 10k+ `QStandardItem`s up front. Columns: *Concept / Relationship / Value type / Value / Reference*.  
   - **Secondary tab:** “Raw tags” → existing tag viewer path for the same `Dataset`.  
   - **Value-type presentation (v1):** NUM/CODE/TEXT/DATETIME as readable strings; **UID refs** (IMAGE/COMPOSITE/WAVEFORM pointer) show **Study/Series/Instance** labels when resolvable else masked UID string; **SCOORD / SCOORD3D / TCOORD** show summary text (type + point/region count) without drawing on canvas; **WAVEFORM** show “N channels × M samples” + item reference—no waveform plot in v1 unless trivial.  
   - **Privacy:** in privacy mode, redact **TEXT**, **PNAME**, and **person-name subfields** in any value; mask **UIDs** in references consistently with metadata; keep numeric dose **values** visible unless product policy later says otherwise (document in `metadata_controller` / SR dialog parity).

3. **Template / profile plugins (RDSR first)**  
   - **Detector:** `SOPClassUID` + **multiple possible root templates** for the same storage class (e.g. X-Ray Radiation Dose SR may use **TID 10001** projection, **TID 10011** CT, **TID 10040** enhanced projection, etc.). Do **not** assume a single root TID; walk for **113706** *Irradiation Event X-Ray Data* (and Enhanced SR **TID 10042** event summaries in Phase 3) regardless of parent chain. If none found, show dose tab empty with explanation.  
   - **RDSR profile:** find `CONTAINER` items whose concept matches **Irradiation Event X-Ray Data** (113706, DCM) → one **table row** per event; columns from **TID 10003 / 10003B** NUM/CODE/TEXT (DAP 122130, KVP 113733, Fluoro Mode 113732, …). Odd nesting / duplicates: tree wins; tables labeled “interpreted per PS3.16 …”.  
   - **Accumulated dose** (TID 10002 / 10041): optional second table or tree section.  
   - Keep **`rdsr_dose_sr`** for **quick summary** / backwards compatibility or fold its logic into the profile as “legacy row builder.”

4. **Entry points**  
   - **Replace** the primary **Tools** entry that today opens the radiation dose summary with **Tools → Structured Report…** (final string in menus + `USER_GUIDE.md`) opening the **SR document browser**. Legacy fixed-row dose UI may live as a **tab** or secondary control inside that browser during transition—not a duplicate top-level item unless usability testing requires it.  
   - **No-pixel overlay** / image context menu: same primary action → structured report browser; optional submenu for legacy strip if needed briefly.  
   - **Export:** offer **JSON** (document tree or selected subtree), **CSV**, and **.xlsx** for tabular outputs (per-event table when dose tab is active; tree flatten or separate sheet policy TBD—implementation chooses clear UX). Reuse **`openpyxl`** patterns from `src/core/tag_export_writer.py` / ROI export dialogs.

5. **Dialog chrome**  
   - **Modeless** (same as tag viewer; not application-modal, not always-on-top).

### 4.2 Dependencies — **highdicom allowed**

| Layer | Role | Notes |
|-------|------|-------|
| **pydicom** | Walk `ContentSequence`, coding, I/O | Required |
| **highdicom** | SR/TID-oriented reads where they reduce code or bug risk | **Permitted in bundle** if Phase 0 spike shows benefit; record **PyInstaller size / import graph** in `dev-docs/info/` or Appendix C. Confirm **license** compatibility before merge. |

**Phase 0:** spike one RDSR (+ one non-dose SR): compare pydicom-only vs highdicom-assisted; per submodule, adopt highdicom only where it clearly helps—otherwise keep pydicom to limit surface area.

---

## 5. SR SOP class inventory (initial checklist)

Implement a small **registry** (`src/core/sr_sop_classes.py` or extend `rdsr_dose_sr`) mapping **SOP Class UID** → user-facing label + **default viewer mode** (tree / dose-profile / unsupported-with-tree-fallback).

**Initial rows to support with at least generic tree:**

| SOP class (name) | UID (1.2.840.10008.…) | Notes |
|------------------|----------------------|--------|
| Basic Text SR | …88.11 | Text-heavy; tree usually shallow |
| Enhanced SR | …88.22 | |
| Comprehensive SR | …88.33 | CAD, KO, many clinical templates |
| Comprehensive 3D SR | …88.34 | |
| X-Ray Radiation Dose SR | …88.67 | **RDSR** — per-event plan |
| Enhanced X-Ray Radiation Dose SR | …88.76 | **Enhanced RDSR** — TID 10040 family ([templates](https://dicom.nema.org/medical/dicom/current/output/chtml/part16/sect_EnhancedXRayRadiationDoseSRIODTemplates.html)) |
| Key Object Selection Document | …88.59 | Often small; references |
| Procedure Log Storage | …88.40 | |
| Mammography / Chest CAD SR | …88.50 / …88.65 | Lower priority; tree + later template |

*(UIDs: verify against current PS3.4 table in repo or pydicom `uid` constants.)*

---

## 6. Phased delivery

### Phase 0 — Discovery and design freeze (1–2 days)

- [ ] Document **fixture matrix**: each file in `pyskindose_samples/` + `tests/fixtures/dicom_rdsr/` + committed SR samples → SOP class, approximate node count, **113706** present Y/N, **88.76** sample present Y/N (acquire or generate minimal Enhanced RDSR for CI if missing).  
- [ ] **highdicom** spike + one-page note (`dev-docs/info/` or Appendix C): API fit, **PyInstaller** delta, license.  
- [ ] UX wire: tabs **Document** | **Dose tables (if detected)** | **Raw tags**; export actions (JSON / CSV / XLSX); privacy toggles.

### Phase 1 — SR tree builder (core, no Qt) (3–5 days)

- [ ] `src/core/sr_document_tree.py` (name TBD): `build_sr_document_nodes(ds) -> list[SrContentNode]`  
- [ ] Handle **continuity of content**, **included template**, **per-value-type** dispatch; bounded recursion (configurable max depth/nodes, reuse ideas from `rdsr_dose_sr`).  
- [ ] **Robustness:** empty/missing `ContentSequence`; items with **no Concept Name Code Sequence**; **private** content items; truncated reads—fail soft with visible error in UI, partial tree if safe.  
- [ ] **Concept display:** prefer first available **Code Meaning**; fallback `(CodingSchemeDesignator, CodeValue)`; optional English meaning from `pydicom.sr.coding` when available.  
- [ ] Tests: **targeted** asserts + depth-cap regression; avoid large brittle JSON dumps (§11).

### Phase 2 — Generic browser dialog (3–5 days)

- [ ] `StructuredReportBrowserDialog` (**modeless**, like tag viewer): lazy tree + detail `QTextBrowser` or property grid.  
- [ ] Wire from `main` / `dialog_coordinator`; **Window stays on top** only for file dialogs (export save-as), not for this window.  
- [ ] **Replace** Tools menu entry and overlay/callback paths so **all** SR opens this browser first (per §4.1 item 4).

### Phase 3 — RDSR per-event tables (5–8 days)

- [ ] `src/core/rdsr_irradiation_events.py`: extract **event roots** (113706) + flatten NUM/CODE for table model; **88.76** path via **TID 10042** per PS3.16 ([Enhanced templates](https://dicom.nema.org/medical/dicom/current/output/chtml/part16/sect_EnhancedXRayRadiationDoseSRIODTemplates.html)).  
- [ ] UI: `QTableView` + model; sort by datetime when present. **Row ↔ tree (“sync”):** *Selecting an irradiation-event row scrolls/expands the tree and selects the corresponding `CONTAINER` node* (minimum v1). **Optional v1.1:** selecting a tree node that maps to an event highlights the table row—implement if low cost after row→tree works.  
- [ ] Tests: vendor samples where available; CI uses **committed** fixtures; **N ≥ 1** only where fixture guarantees it.  
- [ ] **Export:** per-event **CSV** and **.xlsx** from table model; **JSON** tree export from document model (separate action or format picker).  
- **Related:** dose-event column **normalization**, ambiguity notes, flatten caps, and optional **highdicom** follow-up are tracked in [SR_DOSE_EVENTS_NORMALIZATION_AND_HIGHDICOM_PLAN.md](SR_DOSE_EVENTS_NORMALIZATION_AND_HIGHDICOM_PLAN.md) (Stage 1–2).

### Phase 4 — Consolidate legacy dose summary (1–2 days)

- [ ] Fold **RadiationDoseReportDialog** fixed rows into browser **tab** or remove after parity check; update `USER_GUIDE.md`, `CHANGELOG.md`, menus.  
- [ ] No duplicate top-level **Tools** dose entry (replaced per §4.1).

### Phase 5 — Additional templates (iterative)

- [ ] **TID 1500** Measurement Report (common in research / oncology apps)—evaluate pydicom `pydicom.sr` helpers.  
- [ ] Key Object / CAD SR: tree-only until demand.

---

## 7. Verification

- **Automated:** new `tests/test_sr_document_tree.py`, extend RDSR tests; full `pytest` green on **committed** fixtures.  
- **Manual:** load `pyskindose_samples` RDSRs where present; compare spot values to DCmtk `dsrdump` / pydicom print (document commands in Appendix A).  
- **Performance:** SR with >10k nodes remains usable (**lazy** model, caps, optional progress).

---

## 8. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Huge `ContentSequence` | Depth/node caps + **lazy** tree + progress UI |
| Wrong template assumed | Generic tree always available; tables labeled “interpreted per PS3.16 …” |
| PHI in free text | Privacy pass on TEXT/PNAME; UID masking consistent with metadata (§4.1) |
| **COMPOSITE** / **IMAGE** references | **v1:** masked UID + readable ref string when resolvable; **defer** in-app “open referenced object” unless trivial |
| **Golden / snapshot churn** | Prefer targeted asserts + one small optional golden (§11) |

---

## 9. Product decisions (resolved)

| Topic | Decision |
|-------|----------|
| **highdicom** | **Allowed to bundle** when Phase 0 spike shows it helps (PyInstaller + license documented). |
| **Tools menu** | **Replace** existing radiation-dose entry with **Structured Report…** (primary entry to new browser). |
| **Export** | **JSON** (tree), **CSV** (tabular / per-event), and **.xlsx** (tabular, reuse `openpyxl` / `tag_export_writer` patterns). |
| **Dialog modality** | **Modeless** (confirmed). |
| **Table + tree** | **v1 required:** selecting a **dose event row** scrolls/expands the tree and selects the matching **113706** (or **TID 10042**) node. **v1.1 optional:** tree selection highlights the dose table row. *(Review term “tree sync” meant this bidirectional linking; only row→tree is mandatory for v1.)* |

---

## 10. Handoff

- **Planner:** Phase 0 fixture matrix + highdicom note template.  
- **Coder:** Phases 1–3; `dialog_coordinator`, `main`, `main_window_menu_builder`, `slice_display_manager` / `subwindow_manager_factory`, new dialog under `src/gui/dialogs/`; `requirements.txt` if **highdicom** ships.  
- **Tester:** Committed fixtures + `tests/README.md` DCmtk cross-check note.  
- **Reviewer:** PHI parity, lazy-tree performance, export formats.

---

## 11. Implementation notes (design review backlog)

1. **Fixtures for CI:** commit **minimal anonymized** SR/RDSR under `tests/fixtures/` so CI does not depend on gitignored `pyskindose_samples/`.  
2. **Edge cases** in tree builder: empty content, missing concept name, private SQ items, parse errors—surface in UI, do not crash.  
3. **Row→tree** needs stable **node id** from `SrContentNode` to `QModelIndex`.  
4. **highdicom** vs **pydicom:** avoid two divergent tree models—e.g. canonical tree always pydicom; highdicom only for helpers where adopted.  
5. **Versioning:** bump `src/version.py` + `CHANGELOG.md` when user-visible SR browser ships.

---

## Appendix A — Useful standard links

- PS3.3 A.35 Structured Report Document IODs: https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_A.35.html  
- PS3.4 B.5 Standard SOP Classes (SR section): https://dicom.nema.org/medical/dicom/current/output/chtml/part04/sect_B.5.html  
- PS3.16 X-Ray Radiation Dose SR IOD Templates: https://dicom.nema.org/medical/dicom/current/output/chtml/part16/sect_xrayradiationdosesriodtemplates.html  
- TID 10003 Irradiation Event X-Ray Data: https://dicom.nema.org/medical/dicom/current/output/chtml/part16/sect_TID_10003.html  
- TID 10003B Irradiation Event X-Ray Source Data: https://dicom.nema.org/medical/dicom/current/output/chtml/part16/sect_tid_10003b.html  

**Manual cross-check (developer machine):** DCMTK `dcmdump` / `dsrdump` when installed, or a short Python snippet using `pydicom.dcmread` and printing selected `ContentSequence` paths—record exact commands in `tests/README.md` when SR tree tests are first added.

---

## Appendix B — Prior incremental work (2026-04-16)

Merged **file meta** into `get_all_tags`, fixed **no-pixel** `display_slice` early return, and improved overlay routing. That work addressed **flat tag completeness** and **pane refresh**, not **SR document fidelity**—this plan supersedes that scope for browser UX.

---

## Appendix C — Revision history

| Date | Change |
|------|--------|
| 2026-04-16 | Initial draft. |
| 2026-04-17 | Product decisions: highdicom OK to bundle; replace Tools menu; exports JSON+CSV+XLSX; modeless; row→tree selection; §11 review notes; lazy tree, multi-root TID, v1 reference scope, Phase checklist updates. |

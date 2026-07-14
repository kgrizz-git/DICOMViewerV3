# Hanging Protocols, Prior Retrieval, and RDSR – Implementation Plan

This document implements three related items from `dev-docs/TO_DO.md` (**Features (Near-Term)**):

1. **Hanging protocols** — configurable layouts and which series/views (and optionally priors) load into which tiles (P2).
2. **Pulling priors** — once a **local study database** exists, retrieve and open prior studies for the same patient (P2; depends on indexing).
3. **RDSR (Radiation Dose SR)** — parse dose reports from DICOM, optionally export; **sample objects in-repo** for tests and docs (P1).

**Related context**

- Multi-window layout and swap: `src/main.py` (`MultiWindowLayout`), [VIEW_SLOT_LAYOUT_AND_SWAP_PLAN.md](../completed/VIEW_SLOT_LAYOUT_AND_SWAP_PLAN.md), [WINDOW_LAYOUT_AND_NAVIGATION_POLISH_PLAN.md](WINDOW_LAYOUT_AND_NAVIGATION_POLISH_PLAN.md).
- File loading and study/series model: file operations handlers, `dicom_organizer`, navigator thumbnails.
- Future indexing / database notes: [FUTURE_WORK_DETAIL_NOTES.md](../FUTURE_WORK_DETAIL_NOTES.md#local-study-database-and-indexing), TO_DO **Data / Platform** → local study database item.
- DICOM I/O: `pydicom` usage elsewhere in `src/`; SR templates use `RawDataElement` / sequences as needed.

---

## 1. Hanging protocols

### Goal

Let the user define **named protocols** that, when applied (e.g. after opening a study or from a menu), configure **subwindow count/layout**, **which series** goes to **which slot**, and optional **display presets** (same spirit as PACS “hanging”: e.g. “chest PA + lateral”, “CT lung + bone”).

### Prerequisites

- [ ] Stable identifiers for “which series” beyond UI order: prefer **Series Instance UID** + fallback **Study Instance UID + Series Number + description** when UIDs are duplicated or missing.
- [ ] Clear interaction with **fusion** and **MPR**: protocol step may be “load series A in slot 1, series B in slot 2, enable fusion” as a later phase.

### Design decisions

| Topic | Recommendation |
|-------|----------------|
| **Storage format** | JSON on disk under user config dir (e.g. `hanging_protocols/*.json`) plus optional built-in presets shipped read-only. Version field per file for migrations. |
| **Matching rules** | Start with **explicit modality + body part + series description glob** (case-insensitive) or **per-modality ordered pick** (“first CT series”, “second MR series”). Avoid over-complex boolean DSL in v1. |
| **Application trigger** | **Manual**: “Apply protocol…” dialog after load; optional **auto-apply** when a single study is opened (user setting + last-used protocol). |
| **Priors** | If “prior slot” is defined, protocol references **prior resolution policy** (see Section 2) once the database exists; v1 can leave prior slots as “manual load” placeholders. |

### Implementation outline

1. **Data model** — `HangingProtocol`: name, layout mode (1×1, 2×2, 1×2, 2×1), list of `SlotAssignment` { slot_index, match_rule, optional fusion hint, optional W/L preset name }.
2. **Resolver** — Pure function: `(protocol, list[series_metadata]) -> list[resolved_series_uid_per_slot]`; unknown slots stay empty; surface conflicts in UI.
3. **UI** — Editor dialog (CRUD protocols); “Apply protocol” picker; integrate with **View** menu or **Study** menu when study is active.
4. **Execution** — Reuse existing APIs to assign series to subwindows (same paths as manual series selection / drag from navigator); do not duplicate low-level loading.
5. **Tests** — Resolver unit tests with synthetic study lists (0 hits, ambiguous, exact match).

### Out of scope (initial pass)

- DICOM **Hanging Protocol** IOD exchange with external systems (could be a future import/export of the JSON model).
- Per-user ACL or server-side protocol libraries.

---

## 2. Pulling priors after local database

### Goal

After **indexed metadata** can answer “other studies for this Patient ID” (or mapped corporate patient key), offer **one-click (or guided) prior loading** into dedicated slots or a new layout, aligned with hanging-protocol “prior” placeholders.

### Prerequisites

- [ ] **Local study database** milestone from [FUTURE_WORK_DETAIL_NOTES.md](../FUTURE_WORK_DETAIL_NOTES.md#local-study-database-and-indexing): patient/study/series index, incremental scan, stable paths or managed copies.
- [ ] **Patient identity policy**: match on `(0010,0020) Patient ID`, with optional institution-specific rules; document false-merge risk when IDs are reused.
- [ ] **Privacy**: prior search must respect **privacy mode** (mask patient in lists; audit what is logged).

### Implementation outline

1. **Query API** — `find_prior_studies(current_study_uid) -> list[StudySummary]` ordered by date (configurable ascending/descending).
2. **UI** — “Load priors…” from navigator or study context: checklist of candidate studies, preview date/modality/description, target layout (reuse hanging protocol or default 1×2 “current | prior”).
3. **Loading** — Batch open without wiping current session (additive load) unless user chooses “replace”; align with existing multi-study load behavior and toast/duplicate semantics.
4. **Hanging integration** — Protocol slot type `prior_nth` (e.g. most recent prior CT) resolved via the index after current study is known.

### Out of scope (initial pass)

- DICOM **Query/Retrieve** from remote PACS for priors (cross-link to PACS plan when C-FIND/C-MOVE exists).
- Cross-site MPI (master patient index) integration.

---

## 3. RDSR parsing and export — **Task ID: RDSR1**

### Goal

- **Ingest** DICOM objects that are (or reference) **Radiation Dose SR** (typically TID 10001 / CT / projection X-ray dose reporting templates under `Radiation Dose SR` Storage or legacy **Structured Report** with radiation content).
- **Surface** key metrics in a simple **panel or dialog** (optional) and support **export** (CSV/JSON or secondary SR) for workflows and QC.
- Add **de-identified sample RDSR / dose SR files** under e.g. `tests/fixtures/dicom_rdsr/` (or `dev-docs/samples/dicom/`) plus a short **README** describing dataset origin and license.

**Single-branch phasing:** **M2** — implement **after CINE1 (M1)** on default branch unless orchestrator approves a second worktree.

### Task graph and gates

| Phase | Owner | Gate |
|-------|-------|------|
| **P0** Sample policy + fixture README | **planner** / **coder** | Legal/size checklist signed off in repo README |
| **P1** Detection + parser (bounded TID) | **coder** | Unit tests on fixtures only |
| **P2** Browse UI | **coder** + **`ux`** review | **Privacy Mode** display test |
| **P3** Export surfaces | **coder** | **`secops`** + **`reviewer`** at slice end (**high** PHI sensitivity) |

### §3.1 DICOM SR / TID model scope (MVP)

**In MVP (proposed):**

- [x] **Storage SOP Classes:** detect `Radiation Dose SR` and related **SR Storage** objects carrying **CT dose** (TID **10001** *CT Radiation Dose*) and, if low incremental cost, **projection X-ray** dose templates commonly paired with TID **10001**-style summaries (document exact template IDs implemented). **P1 landed:** **X-Ray Radiation Dose SR** (`1.2.840.10008.5.1.4.1.1.88.67`), **Enhanced X-Ray Radiation Dose SR** (`…88.76`), plus **Comprehensive / Comprehensive3D / Extensible / Enhanced SR** when **Modality** `SR` and bounded tree finds CT dose **NUM** codes **113830**/**113838** (DCM). **Projection X-ray–specific** templates: not separately classified in code yet (same NUM codes where present).
- [x] **Extracted fields (minimum):** **CTDIvol**, **DLP**, **SSDE** (when present), **Study/Series/Equipment** identifiers needed for traceability in-app, **procedure / event** counts where trivially reachable via `ContentSequence` walk. **P1:** first matching **NUM** per metric in document order; **113819** (DCM) items counted as irradiation events.
- [x] **Parsing strategy:** **depth-limited** `ContentSequence` traversal with **Concept Name Code** matching (Code Value / Coding Scheme Designator), not a full generic SR renderer. **P1:** `max_depth` / `max_nodes` caps in `rdsr_dose_sr.parse_ct_radiation_dose_summary`.

**Explicitly out of MVP (document in UI + README):**

- [ ] Full **TID tree** browser for arbitrary **SR** (e.g. mammography report SR, NM structured reports).
- [ ] **Private vendor** template quirks beyond “best effort + clear unsupported error”.
- [ ] **DICOM SR write-back** as a **default** export (see §3.4 — tabular first).

### §3.2 Parse stack (`pydicom` vs `highdicom`)

| Option | When to use | Notes |
|--------|-------------|-------|
| **`pydicom` only** (aligns with rest of `src/`) | **Default MVP** | Walk `Dataset` / `ContentSequence`; no new dependency; more boilerplate; easier to pin in **PyInstaller** |
| **`highdicom`** | **Optional** follow-on if typed SR helpers justify extra wheel size | Evaluate **import graph** + **license** + **version pin**; add **`researcher`** brief before **`requirements.txt`** |

**Recorded (RDSR1 P1, 2026-04-15):** MVP parser uses **`pydicom` only** — implementation: **`src/core/rdsr_dose_sr.py`** (no **`highdicom`** dependency).

**Gate:** record the chosen row in this plan and in **`CHANGELOG`** / **`dev-docs/info`** pointer if **`highdicom`** is added.

### §3.3 Browse UI surface

- [ ] **Recommendation:** dedicated **modeless dialog** “**Radiation dose report**” / “**RDSR summary**” with **read-only** table (metric → value → unit) + optional **collapsible raw tree** for support — keeps **Metadata** panel focused on tags. **`ux`** may override (e.g. docked panel).
- [ ] **Entry points:** **Tools** menu and context menu when selected object is dose SR (or when series contains companion SR instances — detection rules in §3.1).
- [ ] **Empty / error states:** vendor-unsupported structure → single **actionable** message + copy technical summary for support (no silent failure).

### §3.4 Export formats

| Format | MVP | Notes |
|--------|-----|-------|
| **JSON** | Yes | Stable schema version key (`dose_summary_version`); easy QC diff |
| **CSV** | Yes | Flatten nested events to **multiple rows** or document “first event only” |
| **DICOM SR / RDSR file** | **Defer** unless product explicitly needs **write** path | Writing SR is **high risk** (conformance + liability); if later: separate plan slice + **reviewer** |

### §3.5 Privacy Mode behavior

- [ ] **Display:** mask **patient / participant** and other **PHI** fields in the browse UI using the **same rules** as metadata / study index when **Privacy Mode** is on (`privacy_mode` propagation — mirror existing controllers).
- [ ] **Export:** dialog warning that export may contain identifiers unless **anonymize** option is selected; if reusing **`DICOMAnonymizer`**, document **scope** (e.g. **0010**-only vs broader) — align **`secops`** assessment notes from other export slices.
- [ ] **Logging:** never log raw SR text to console in production paths.

### §3.6 Sample RDSR / dose SR in repo (licensing, de-ID, size, path)

**Preferred locations:**

| Path | Role |
|------|------|
| **`tests/fixtures/dicom_rdsr/`** | **Primary** — tiny files for pytest; **README.md** mandatory |
| **`SampleDICOMData/dose_sr/`** (or similar) | **Optional** larger curated examples for **manual** QA — only after **license** allows redistribution |

**Policy checklist (all must be true before commit):**

- [ ] **Provenance:** source named (e.g. **DICOM standard example**, **public TCIA collection**, **synthetic generator**, vendor-sanitized sample with written permission).
- [ ] **License:** license text or URL recorded in fixture **README**; **OSI** / **CC** / **DICOM PS3.17** examples preferred.
- [ ] **De-identification steps:** run documented **pydicom**-based tag scrub (remove burn-in dates if needed); verify **no** real **Patient ID** / **Patient Name**; rotate **UIDs** if sample was derived from clinical data.
- [ ] **Max size:** keep **git** objects small — target **≤ 200–500 KiB** per file unless **`git-lfs`** is already project-standard (today: prefer **small** fixtures).
- [ ] **No PHI in git** — **`secops`** spot-check.

### Implementation outline (unchanged intent, IDs for tracking)

1. **Detection** — On file/load or index: `SOPClassUID`, `Modality` == `SR`, template / concept codes hinting dose (avoid parsing every SR as dose).  
   `parallel-safe: no`, `stream: O`, `after: CINE1` (default single-branch; reduce churn on `main_window` / export menus)
2. **Parser module** — **`src/core/rdsr_dose_sr.py`** (MVP; earlier sketch: `src/utils/rdsr_parser.py` / `src/core/dose_sr/`): return a **typed dataclass** (CTDIvol, DLP, SSDE, device, procedure context, per-irradiation event if present). Handle missing optional attributes gracefully.
3. **Export** — “Export dose summary…” to JSON/CSV; optional “write minimal RDSR” only if clinically justified — default is **non-clinical tabular export** from parsed values.
4. **Tests** — Round-trip on **in-repo fixtures** only; no PHI in git.
5. **Documentation** — `dev-docs/` note: what is supported, what is not (e.g. full TID tree, legacy IODs), link to DICOM standard supplements as reference.

### Risks / caveats

- SR nesting and **private templates** vary by vendor; ship extensible parsing and clear “unsupported structure” errors.
- **Regulatory**: parsing for display/export in a research viewer differs from a certified dose tracking system; keep UX honest about limitations.

### Questions for user / orchestrator (blocking before SR **write**)

- [ ] Is **DICOM SR file export** required in **M1**, or strictly **JSON/CSV**?

---

## Suggested implementation order

1. **RDSR fixtures + parser skeleton** — bounded scope, no dependency on database or layout overhaul.
2. **Hanging protocols (JSON + resolver + apply)** — improves daily workflow without requiring the index.
3. **Prior loading** — follows naturally once the **local study database** exists; reuse resolver for “prior slot” rules.

---

## Checklist (high level)

### Hanging protocols

- [ ] JSON schema + on-disk CRUD
- [ ] Resolver + tests
- [ ] Apply protocol UI + wiring to existing load/focus APIs
- [ ] `CHANGELOG.md` on release

### Priors

- [ ] Index supports patient-derived prior queries
- [ ] Prior picker UI + additive load
- [ ] Hanging-protocol prior slot resolution
- [ ] Privacy review + `CHANGELOG.md`

### RDSR (**RDSR1** — see §3)

- [x] **(RDSR1-P0)** Fixture dir `tests/fixtures/dicom_rdsr/` + **README** (license, provenance, de-ID steps, max size) — **done** 2026-04-15 (synthetic `.dcm` + `tests/scripts/generate_rdsr_dose_sr_fixtures.py`)
- [x] **(RDSR1-P1)** Detection (`SOPClassUID` / modality / concept hints) + **pydicom** (or gated **highdicom**) parser + unit tests — **done** 2026-04-15 (`src/core/rdsr_dose_sr.py`, `tests/test_rdsr_dose_sr.py`; **pydicom-only** per §3.2)
- [x] **(RDSR1-P2)** Browse UI (dialog vs panel per §3.3) + **Privacy Mode** behavior — **done** 2026-04-15 (`RadiationDoseReportDialog`, **Tools** + context menu, privacy masking)
- [x] **(RDSR1-P3)** Export **JSON** + **CSV** + user copy; **no** SR write unless user answers §3 **Questions** — **done** 2026-04-15 (`write_dose_summary_json` / `write_dose_summary_csv`, anonymize checkbox)
- [ ] **(RDSR1-G)** Slice-end **`reviewer`** + **`tester`** + **`secops`**; **`CHANGELOG.md`**; **`requirements.txt`** only if new dependency

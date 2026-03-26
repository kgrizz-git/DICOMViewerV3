# Hanging Protocols, Prior Retrieval, and RDSR – Implementation Plan

This document implements three related items from `dev-docs/TO_DO.md` (**Features (Near-Term)**):

1. **Hanging protocols** — configurable layouts and which series/views (and optionally priors) load into which tiles (P2).
2. **Pulling priors** — once a **local study database** exists, retrieve and open prior studies for the same patient (P2; depends on indexing).
3. **RDSR (Radiation Dose SR)** — parse dose reports from DICOM, optionally export; **sample objects in-repo** for tests and docs (P1).

**Related context**

- Multi-window layout and swap: `src/main.py` (`MultiWindowLayout`), [VIEW_SLOT_LAYOUT_AND_SWAP_PLAN.md](VIEW_SLOT_LAYOUT_AND_SWAP_PLAN.md), [WINDOW_LAYOUT_AND_NAVIGATION_POLISH_PLAN.md](WINDOW_LAYOUT_AND_NAVIGATION_POLISH_PLAN.md).
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

## 3. RDSR parsing and export

### Goal

- **Ingest** DICOM objects that are (or reference) **Radiation Dose SR** (typically TID 10001 / CT / projection X-ray dose reporting templates under `Radiation Dose SR` Storage or legacy **Structured Report** with radiation content).
- **Surface** key metrics in a simple **panel or dialog** (optional) and support **export** (CSV/JSON or secondary SR) for workflows and QC.
- Add **de-identified sample RDSR / dose SR files** under e.g. `tests/fixtures/dicom_rdsr/` (or `dev-docs/samples/dicom/`) plus a short **README** describing dataset origin and license.

### Prerequisites

- [ ] Confirm target **SOP Classes** and real-world examples from your modalities (CT dose most common initially).
- [ ] Prefer **highdicom** or manual `pydicom` traversal — evaluate dependency size vs parsing depth; document choice in `requirements.txt`.

### Implementation outline

1. **Detection** — On file/load or index: `SOPClassUID`, `Modality` == `SR`, template / concept codes hinting dose (avoid parsing every SR as dose).
2. **Parser module** — `src/utils/rdsr_parser.py` (or `src/core/dose_sr/`): return a **typed dataclass** (CTDIvol, DLP, SSDE, device, procedure context, per-irradiation event if present). Handle missing optional attributes gracefully.
3. **Export** — “Export dose summary…” to JSON/CSV; optional “write minimal RDSR” only if clinically justified — default is **non-clinical tabular export** from parsed values.
4. **Tests** — Round-trip on **in-repo fixtures** only; no PHI in git.
5. **Documentation** — `dev-docs/` note: what is supported, what is not (e.g. full TID tree, legacy IODs), link to DICOM standard supplements as reference.

### Risks / caveats

- SR nesting and **private templates** vary by vendor; ship extensible parsing and clear “unsupported structure” errors.
- **Regulatory**: parsing for display/export in a research viewer differs from a certified dose tracking system; keep UX honest about limitations.

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

### RDSR

- [ ] Sample files in repo + README
- [ ] Parser + tests
- [ ] Optional UI summary + export
- [ ] `CHANGELOG.md` + `requirements.txt` if new dependency

# PS3.15 De-identification Conformance Plan

**Status:** ✅ Complete. **Engine Phases 1–6 + Phase 7 UI merge (Option B) CODE-COMPLETE 2026-06-16** (full suite 1004 passed / 17 skipped). **Phase 8 manual CT/MR GUI round-trip completed 2026-07-12**; active follow-up is the separate pydicom 3 / pylinac cap item in `dev-docs/TO_DO.md`.
**Priority:** P1 (Phase 1 item #1 is a correctness/leak bug; rest is conformance hardening)
**Created:** 2026-06-15
**TO_DO ref:** Maintenance / Bugs — deep-anonymize PS3.15 follow-ups (date-shift work landed 2026-06-15; this plan covers the remaining profile gaps surfaced in that review)

Related: [Deep Anonymizer Export Plan](../supporting/DEEP_ANONYMIZER_EXPORT_PLAN.md) (original feature), [Export privacy & W/L default](../supporting/EXPORT_PRIVACY_AND_WL_DEFAULT_PLAN.md)

---

## Goal

Bring **all** DICOM export de-identification into line with **PS3.15 Annex E (Basic Application Level Confidentiality Profile)** and other relevant industry standards (PS3.10 file-meta consistency, PS3.16 CID 7050 method codes), and fix one real UID-leak bug.

**Hard requirement (per user, 2026-06-15):** the **simple** "Anonymize patient information" export path must conform to PS3.15 too — it is **not** acceptable to leave it as a weaker "patient-tags-only" mode and merely relabel it. Any output the app presents as "anonymized" must satisfy the Basic Application Confidentiality Profile (at minimum) plus the provenance tags the standard requires.

**Consequence:** once both paths must meet the same profile, the difference between "simple" and "deep" collapses from *conformance level* to *configurable options* (e.g. retain device identity, retain UIDs vs re-mint, date handling). That makes "should we keep two paths at all?" a real decision — addressed in **Phase 0.5** below.

This plan was triggered by a gap review of `deep_anonymizer.py` against the profile. The findings (HIGH→LOW):

1. **(HIGH — bug)** File Meta UIDs not synced after UID remap → original `SOPInstanceUID` leaks in `(0002,0003)` MediaStorageSOPInstanceUID and violates the PS3.10 rule that `(0002,0003) == (0008,0018)`. `(0002,0016)` SourceApplicationEntityTitle may also leak.
2. **(HIGH)** `AccessionNumber (0008,0050)`, `StudyID (0020,0010)`, and procedure-step identifiers are never removed (PS3.15 action **Z**) — strong re-identification / RIS-PACS linkage.
3. **(HIGH)** Patient (group 0010) stripping is **top-level only** — PHI nested in sequences (Referenced Patient Sequence, Request Attributes Sequence, SR ContentSequence PNAME) survives.
4. **(MEDIUM)** `DeidentificationMethodCodeSequence (0012,0064)` not written — we set only the free-text `(0012,0063)`. Profile expects coded entries (CID 7050) declaring the profile + options applied.
5. **(MEDIUM)** "Retain" deviations (`retain_manufacturer`) not declared via the corresponding Retain-Option code.
6. **(LOW)** Curated-attribute coverage gaps: physician address/phone `(0008,0092/0094)`, `PhysiciansOfRecord (0008,1048/1049)`, admitting/visit dates, other Table E.1-1 entries.
7. **(Known/accepted)** Burned-in pixel PHI — warned, not cleaned; we correctly do **not** claim the Clean Pixel Data Option. No code change beyond keeping the claim honest.

> ⚠️ The tag/code numbers above are from working knowledge of PS3.15, **not** a verified fetch. **Phase 0 must confirm them before any implementation.**

---

## Phase 0 — Research & plan revision gate (DO FIRST)

**Do not write code until this phase is done and the plan is revised.**

- [x] Fetch and read **PS3.15 Annex E** — action codes, provenance requirements (E.1.1 step 6), and Table E.1-1 actions for the attributes in question. ✅ (see findings)
- [x] **CID 7050** (PS3.16) code values/meanings confirmed. ✅ (see findings table)
- [x] Profile **Options** and base-profile interaction (esp. temporal + retain-UIDs + retain-device). ✅
- [x] **File-meta rule** confirmed — actually stronger than assumed: regenerate File Meta **and** zero the 128-byte preamble (E.1.1 steps 5 & 7). ✅
- [ ] **(implementation-time)** Verify exactly what pydicom's `save_as(write_like_original=False)` does to file_meta + preamble in our save path, so Phase 1 only writes what's needed. (Deferred to Phase 1 coding — not a blocker for the decision.)
- [x] **Revised this plan** with verified numbers + two new refinements (blank-don't-delete Type-2; retain-UIDs fork). ✅

**Gate:** Phase 0 sign-off (tag/code numbers verified, table confirmed) before Phase 0.5.

### Phase 0 findings (verified 2026-06-16 against dicom.nema.org current edition)

Sources: [PS3.15 Annex E](https://dicom.nema.org/medical/dicom/current/output/chtml/part15/chapter_E.html), [PS3.16 CID 7050](https://dicom.nema.org/medical/dicom/current/output/chtml/part16/sect_CID_7050.html).

**Action codes (Table E.1-1a):** `D` replace w/ dummy non-zero; `Z` replace w/ **zero-length or dummy**; `X` remove attribute (and all sequence items); `K` keep (clean if sequence); `C` clean to similar non-identifying value; `U` replace w/ internally-consistent UID; `Z/D`, `X/Z`, `X/D`, `X/Z/D` = X/Z/D resolved by IOD Type (3/2/1); `X/Z/U*` = UID-reference variant.

**Provenance (E.1.1 step 6):** `PatientIdentityRemoved (0012,0062) = "YES"` is **mandatory**. Plus codes from CID 7050 in `DeidentificationMethodCodeSequence (0012,0064)` **and/or** a text string in `DeidentificationMethod (0012,0063)`. (So our free-text alone is *permitted*, but the coded sequence is the interoperable form — we will write both.)

**Verified action codes for the attributes in question:**

| Attribute | Tag | Action | Implication for us |
|-----------|-----|--------|--------------------|
| AccessionNumber | (0008,0050) | **Z** | blank (currently not touched) |
| StudyID | (0020,0010) | **Z** | blank (currently not touched) |
| StudyDate | (0008,0020) | **X/Z** | base profile removes/blanks dates; *keeping or shifting them is an Option* (see below) |
| PatientName | (0010,0010) | **Z** | "ANONYMIZED" dummy is OK (Z allows dummy) |
| PatientID | (0010,0020) | **Z/D** | dummy OK |
| PatientBirthDate | (0010,0030) | **Z** | **must blank, not delete** — Type 2 (our base anonymizer currently *deletes* it ⇒ IOD-nonconformant) |
| InstitutionName | (0008,0080) | **X/Z/D** | remove/blank |
| StationName | (0008,1010) | **X** | remove |
| ReferringPhysicianName | (0008,0090) | **X/Z/D** | remove/blank (currently removed — OK if not Type 2 in IOD) |
| Manufacturer | (0008,0070) | **X** | remove (retaining ⇒ Retain Device Identity Option) |
| DeviceSerialNumber | (0018,1000) | **X/Z/D** | remove/blank |
| SOPInstanceUID | (0008,0018) | **U** | re-mint consistently (we do) |
| StudyInstanceUID | (0020,000D) | **U** | re-mint (we do) |
| SeriesInstanceUID | (0020,000E) | **U** | re-mint (we do) |

**File-meta rule is STRONGER than first stated (E.1.1 steps 5 & 7):** must "always protect (encrypt and replace) the SOP Instance UID … as well as all references"; and if stored as a DICOM file, "the File Meta Information **including the 128-byte preamble** … shall be replaced." ⇒ Phase 1 must **regenerate File Meta + zero the preamble**, not merely sync `(0002,0003)`.

**CID 7050 codes (DCM scheme) — our mapping:**

| Code | Meaning | When we assert it |
|------|---------|-------------------|
| 113100 | Basic Application Confidentiality Profile | always (both paths) |
| 113105 | Clean Descriptors Option | when free-text descriptions/comments stripped |
| 113106 | Retain Longitudinal Temporal Information **Full Dates** Option | date mode = **Keep** |
| 113107 | Retain Longitudinal Temporal Information **Modified Dates** Option | date mode = **Shift** |
| 113109 | Retain Device Identity Option | `retain_manufacturer` / device kept |
| 113110 | Retain UIDs Option | when UIDs **not** re-minted |
| 113112 | Retain Institution Identity Option | if institution kept |

> Base profile = dates removed/blanked (X/Z). Our **date-blank** mode = pure base profile (no temporal option). **Shift** = +113107. **Keep** = +113106. Clean authoritative mapping for the code sequence.

**Retain-option semantics (PS3.15 §E.3.8 / §E.3.10 / §E.3.11, verified 2026-06-16):**

- **Retain Institution Identity Option (113112)** — "information about the identity of the institution … shall be retained, as described in Table E.1-1." Flips `InstitutionName (0008,0080)`, `InstitutionAddress (0008,0081)`, `InstitutionalDepartmentName (0008,1040)`, `InstitutionCodeSequence (0008,0082)` to **K (keep)**. ⇒ retaining institution **is** conformant **iff** 113112 is declared.
- **Retain Device Identity Option (113109)** — "information about the identity of the device … shall be retained." Covers `StationName (0008,1010)`, `DeviceSerialNumber (0018,1000)`, `Manufacturer (0008,0070)`, `ManufacturerModelName (0008,1090)`, etc. → **K**. ⇒ retaining station/device **is** conformant **iff** 113109 declared. (Our existing `retain_manufacturer` maps here — generalize it to "retain device identity.") *Implementation note: confirm the exact Table E.1-1 column for the Station Name row (Device vs Institution) when wiring.*
- **Retain Safe Private Option (113111)** — base profile is **X (remove ALL private)**; this option changes private to **C (clean)**, keeping **only** attributes positively known safe via: `Block Identifying Information Status (0008,0303) = SAFE`, the standard's **Table E.3.10-1** safe list, or vendor Conformance Statements. Standard explicitly warns vendors "do not guarantee them to be safe" and that `OB`/text private data is "particularly unsafe." ⇒ **There is no conformant "keep all private tags" toggle.** Blanket private retention = non-conformant. Implementing safe-private requires an allowlist engine (block-status + Table E.3.10-1) — **out of scope** for this plan; treat as a separate future feature. Our current "remove all private" is the conformant, conservative default and stays.

**Three refinements this surfaces:**
1. **Blank-don't-delete for Type-2 attributes.** `Z`/`X/Z`/`Z/D` attributes that are Type 2 in their IOD (e.g. PatientBirthDate, StudyDate) must be **present-but-empty**, not deleted. Our base `DICOMAnonymizer` currently *deletes* group-0010 date/non-text tags ⇒ refine to blank. Store the *resolved* action per curated tag rather than computing IOD Type dynamically.
2. **Retain UIDs is a real fork.** A preset that keeps UIDs is only conformant if it declares **113110** — and keeping UIDs is a re-identification vector. ⇒ a conformant simple preset should **re-mint UIDs** (base `U`) rather than silently keep them. This pulls UID remap into the simple path (or forces the 113110 declaration). Feeds Phase 0.5.
3. **Retain institution/device allowed only if declared; private not blanket-retainable.** Institution → 113112, device/station → 113109 (each toggleable + declared). Private → keep "remove all"; safe-private allowlist is a separate future feature.

**Plan revised below to reflect all of the above. Phase 0 complete.**

---

## Phase 0.5 — Path consolidation decision (keep one / merge / keep both)

**Do this after Phase 0 research, before bulk implementation** — the outcome decides *where* the Phase 1–7 code lands and how the UI is wired. Produce a short written recommendation (in this plan or a linked decision note) and get user sign-off.

Evaluate the three options against the now-known requirement (both paths conform to PS3.15):

- [ ] **Option A — Keep both entry points, one shared engine.** Two dialogs/checkboxes, both routed through the single conformant engine with different option *defaults* (e.g. simple = retain device + retain UIDs + keep-dates; deep = strip device + re-mint UIDs + shift/blank dates). Pro: familiar UX, minimal disruption. Con: two entry points for what is now one conformance level may confuse ("which one is 'really' anonymized?").
- [ ] **Option B — Merge into one export-anonymization dialog** with a clear options panel (and presets like "Standard share" / "Maximal strip"). Pro: one obviously-correct path, options explicit, no false tiering. Con: larger UX change; touches `export_dialog.py` + deep dialog + menu wiring; preset migration.
- [ ] **Option C — Keep only the deep dialog**, retire the simple checkbox (or make it open the deep dialog). Pro: simplest mental model, least conformance surface. Con: removes the lightweight inline checkbox some users expect during a normal export.
- [ ] Decision criteria to weigh: user mental model / least-surprise, conformance-surface (fewer paths = fewer ways to ship non-conformant output), UX disruption, test surface, and whether an inline "anonymize on export" checkbox is a must-keep affordance.
- [ ] **UID handling per preset (from Phase 0):** a conformant preset either **re-mints UIDs** (base profile `U`) or **declares Retain UIDs Option 113110** (a re-identification vector). Decide each preset's default. Recommendation: default to re-minting; offer "retain UIDs" only as an explicit, clearly-labeled option that adds 113110. This means even a "light" simple preset should re-mint by default — reinforcing that simple is no longer just a group-0010 pass.
- [ ] **Recommendation (post-research, pending user sign-off): Option B — merge to one engine, keep an inline one-click conformant default.** Once both paths conform, "simple/deep" tiering is misleading. UI shape:
  - Normal Export dialog: relabel checkbox `De-identify (PS3.15)` → applies the **Standard Share** preset (one click, safe default).
  - An **"Options…"** button (and the existing menu entry) opens the single anonymization dialog with a **preset dropdown + detailed toggles** — this *replaces* the separate "Deep Anonymization" dialog rather than duplicating it.
  - Old group-0010-only `DICOMAnonymizer` becomes an **internal layer**, never user-selectable alone.

  **Proposed presets** (all conformant; every retained category declared via CID 7050):

  | Toggle | Standard Share *(default)* | Maximal strip | Research (keep technical) |
  |---|---|---|---|
  | Re-mint UIDs (else 113110) | ✅ U | ✅ U | ✅ U |
  | Strip institution (retain ⇒ 113112) | ✅ strip | ✅ strip | ✅ strip *(institution off by default — more identifying than device)* |
  | Retain device identity (⇒ 113109) | ❌ strip | ❌ strip | ✅ **retain → 113109** |
  | Strip operators/physicians | ✅ | ✅ | ✅ |
  | Remove free text (descriptions/comments) | ✅ | ✅ | ✅ |
  | Dates | Shift → **113107** | Remove (base, no temporal code) | Shift → **113107** |
  | Private tags | remove all | remove all | remove all *(no blanket-retain — safe-private is a separate future feature)* |
  | Always | **113100** | **113100** | **113100** |

  > **Open Q4 RESOLVED (PS3.15 §E.3.5, 2026-06-16):** the Clean Descriptors Option (113105) means scrubbing PHI *embedded* in descriptor text broadly; we simply **remove** our curated free-text set (conservative, base-profile-aligned) and do **not** guarantee that breadth, so we do **not** claim 113105.

  - **Retain institution** is available as an explicit, clearly-labeled toggle (adds 113112) but **off in every default preset**.
  - **No "patient-tags-only" preset** (the non-conformant mode being eliminated) and **no "retain all private" toggle**.
- [ ] Record the decision; create/refresh TO_DO items (see "TO_DO items to add" below); set which later phases are in-scope (e.g. Phase 7 UI work depends on this).

**Gate:** consolidation decision signed off before Phase 7 (UI). Phases 1–6 (engine/profile correctness) can proceed in parallel regardless of the outcome, since they all land in the shared core.

---

## Architecture: two paths — what changes where

Today there are two anonymization entry points sharing one base class:

| Path | Entry point | Engine | Scope today | Provenance tags? | UID remap? | Batch? |
|------|-------------|--------|-------------|------------------|------------|--------|
| **Simple** ("Anonymize patient information") | `export_dialog.py` checkbox | `DICOMAnonymizer` | group 0010 only, **top-level** | ❌ none | ❌ no | ❌ per-dataset |
| **Deep** ("Export with Deep Anonymization") | `deep_anonymizer_export_dialog.py` | `DeepDICOMAnonymizer` (wraps `DICOMAnonymizer`) | full profile | ✅ YES + method | ✅ yes | ✅ yes |

### Recommendation: one conformance engine; both paths produce PS3.15-conformant output

Because **both** paths must now meet the Basic Application Confidentiality Profile, do **not** maintain two divergent de-id implementations. Build a single conformance engine (the existing `DeepDICOMAnonymizer`, hardened, on top of a shared `DICOMAnonymizer` + `deid_provenance.py`). The simple "Anonymize" checkbox becomes a **conformant preset** of that engine, not a lesser code path.

> Note: a *conformant* Basic Profile already removes far more than group 0010 — accession number, physician names, and (absent the explicit Retain-Device / Retain-Institution options) institution and device identity. So "make simple conformant" inherently pulls most of the deep-path stripping into the simple path. The two paths differ only in **options** (retain device/institution, re-mint vs retain UIDs, date handling), which is precisely why **Phase 0.5** evaluates whether two entry points still earn their keep.

Per-finding routing (revised — every conformance fix now applies to **both** paths):

| # | Fix | Simple path | Deep path | Notes |
|---|-----|-------------|-----------|-------|
| 1 | File-meta UID sync `(0002,0002/0003/0016)` | **Yes** — scrub `(0002,0016)` AE title always; sync `(0002,0003)` **iff** simple ever re-mints UIDs (Phase 0.5 decides whether it does) | **Yes** | AE-title leak applies regardless of UID remap |
| 2 | Remove `AccessionNumber`/`StudyID`/procedure IDs | **Yes** (profile requires it) | **Yes** | No longer optional for simple |
| 3 | Sequence-recursive patient stripping | **Yes** (shared base) | **Yes** | Pure correctness |
| 4 | `DeidentificationMethodCodeSequence (0012,0064)` | **Yes** (profile expects it) | **Yes** | Simple declares the same Basic Profile code; options differ |
| 5 | Declare retain deviations | **Yes** if simple exposes any retain option | **Yes** | Whatever is retained must be declared |
| 6 | Curated extra identifiers (Table E.1-1) | **Yes** | **Yes** | Both target the full table |
| 7 | Burned-in PHI handling | Keep warning | Keep warning | Don't claim Clean Pixel Data Option in either |

**Net:** the simple and deep paths converge on the same conformant core. The only remaining differences are option defaults — which feeds directly into the consolidation decision.

---

## Phase 1 — File-meta regeneration + preamble (HIGH, bug) — deep engine ✅ DONE 2026-06-16

- [x] `DeepDICOMAnonymizer._sanitize_file_meta`: syncs `MediaStorageSOPInstanceUID`/`MediaStorageSOPClassUID` to the (remapped) dataset; sets `ImplementationClassUID`/`ImplementationVersionName` ("DICOMViewerV3"); removes AE-title + private File Meta tags (`FILE_META_IDENTIFYING_TAGS`); zeroes the 128-byte preamble.
- [x] Guards datasets with no `file_meta` (no-op).
- [x] Tests: `test_file_meta_sop_instance_uid_synced_after_remap`, `test_file_meta_identifying_tags_removed`, `test_file_meta_preamble_zeroed` (19 deep-anon tests pass).

## Phase 2 — Remove study/order identifiers (HIGH) — deep engine ✅ DONE 2026-06-16

- [x] `IDENTIFIER_TAGS` in profile: AccessionNumber (0008,0050), StudyID (0020,0010), placer/filler order numbers, RequestedProcedureID, Scheduled/Performed Procedure Step IDs — all PS3.15 action **Z**.
- [x] Applied unconditionally in `DeepDICOMAnonymizer` via `_blank_tag` (Z = blank, Type-2 conformant) — not gated by strip flags.
- [x] Tests: `test_identifiers_blanked_not_deleted`, `test_identifiers_blanked_even_when_strip_flags_off`.

## Phase 3 — Sequence recursion + blank-don't-delete (HIGH) — shared base ✅ DONE 2026-06-16

- [x] Refactored `DICOMAnonymizer.anonymize_dataset` → new `_anonymize_in_place` recurses into **every** `SQ` (any group), applying the group-0010 rule to nested datasets.
- [x] **Blank-don't-delete:** date/time patient VRs (incl. `PatientBirthDate`) now set to zero-length instead of deleted (PS3.15 action Z, Type-2 conformant).
- [x] Text dummy behavior kept ("ANONYMIZED").
- [x] **Bonus fix:** switched `dataset.copy()` (shallow — was mutating the caller's in-memory dataset!) to `copy.deepcopy`, so anonymizing on export no longer corrupts the loaded study.
- [x] Tests: `tests/test_dicom_anonymizer.py` (new, 6 cases: nested 1–2 levels, blank birthdate, no-mutation) + updated `test_deep_anonymizer.py`. 22 anon tests pass; 159 anon/export/privacy green.

## Phase 4 — De-identification provenance (MEDIUM) — shared helper ✅ DONE 2026-06-16

Implemented `utils/deid_provenance.py` (`build_method_codes` + `apply_deidentification_provenance`); deep engine `_set_deidentification_tags` now derives `date_mode` and retain flags from options and writes `(0012,0062/0063/0064)`. Tests: `tests/test_deid_provenance.py` + method-code cases in `test_deep_anonymizer.py`. (Original checklist below.)

- [ ] New helper `utils/deid_provenance.py` writes:
  - [ ] `PatientIdentityRemoved (0012,0062) = "YES"` (mandatory).
  - [ ] `DeidentificationMethod (0012,0063)` free text.
  - [ ] `DeidentificationMethodCodeSequence (0012,0064)` from **verified CID 7050** codes (DCM scheme), driven by the options actually applied:

  | Condition | Code |
  |-----------|------|
  | always | **113100** Basic Application Confidentiality Profile |
  | date mode = Keep | **113106** Retain Longitudinal Temporal — Full Dates |
  | date mode = Shift | **113107** Retain Longitudinal Temporal — Modified Dates |
  | date mode = Remove/blank | *(no temporal code — pure base profile)* |
  | device/manufacturer retained | **113109** Retain Device Identity Option |
  | UIDs **not** re-minted | **113110** Retain UIDs Option |
  | institution retained | **113112** Retain Institution Identity Option |

- [ ] Build each code item as `(CodeValue, CodingSchemeDesignator="DCM", CodeMeaning)`.
- [ ] Both paths use this helper (per the conformance requirement) — deep builds from `self.options`; simple builds from its conformant preset.
- [ ] Tests: code sequence matches each option combination (date Keep→113106, Shift→113107, Remove→none; retain-device→113109; not-remapped→113110); 113100 always present.

## Phase 5 — Retain-option toggles + declaration (MEDIUM) — shared engine ✅ DONE 2026-06-16

Implemented: `DeepAnonymizerOptions` now has `retain_institution_identity` / `retain_device_identity` / `retain_uids` (replacing `strip_institution_device` + `retain_manufacturer`); stripping logic + `remint_uids` property honor them; declarations wired through Phase 4. Interim dialog updated to retain-checkbox model (full rebuild in Phase 7). Tests cover keep/declare for device (113109), institution (113112), UIDs (113110). (Original checklist below.)

- [ ] **Generalize `retain_manufacturer` → `retain_device_identity`** (covers StationName, DeviceSerialNumber, Manufacturer, ManufacturerModelName, etc. per §E.3.8). When on: keep those attributes (action K) **and** add code **113109** to `(0012,0064)`.
- [ ] Add **`retain_institution_identity`** toggle (off by default, all presets): when on, keep InstitutionName/Address/Dept/CodeSequence (action K) **and** add code **113112**.
- [ ] Add **`retain_uids`** toggle (off by default): when on, skip UID re-mint **and** add code **113110** (clearly label it a re-identification risk in the UI).
- [ ] Invariant: **any retained category must add its CID 7050 code.** Add a guard/test that fails if a retain flag is set without its declaration.
- [ ] Confirm the exact Table E.1-1 column for `StationName (0008,1010)` (Device vs Institution) when wiring; place it under the matching toggle.
- [ ] Tests: each retain toggle on → attributes kept + correct code present; off → attributes stripped + code absent.

## Phase 6 — Curated extra identifiers (LOW) — shared engine ✅ DONE 2026-06-16

- [x] Extended `OPERATOR_PHYSICIAN_TAGS` with physician address/phone `(0008,0092/0094)`, identification sequences, `PhysiciansOfRecord (0008,1048/1049)`, ConsultingPhysician, RequestingService. (Admitting/visit dates are already covered by the date shift/blank pass over all DA/DT VRs.)
- [x] Test: `test_curated_physician_contact_tags_removed`.

> **Out of scope (separate future feature):** Retain Safe Private Option (113111). Base profile removes **all** private; conformant retention requires a safe-private allowlist engine (Block Identifying Information Status `(0008,0303)=SAFE`, Table E.3.10-1, vendor conformance). We keep "remove all private" and do **not** offer a blanket retain-private toggle.

## Phase 7 — UI wiring (Option B — merge) ✅ CODE DONE 2026-06-16 (manual verification pending in Phase 8)

Implemented Option B with a single shared engine + one reusable options component:

- [x] **Conformant routing:** the inline "De-identify (PS3.15 Basic Profile)" checkbox in `export_dialog.py` now routes DICOM exports through the **deep_anonymize** batch path (Standard Share preset by default) — never the old group-0010-only `DICOMAnonymizer` call. `anonymize=` is forced `False` from the dialog; `DICOMAnonymizer` survives only as the internal base used by `DeepDICOMAnonymizer`.
- [x] **Shared options component:** new `gui/dialogs/anonymization_options_widget.py` — `AnonymizationOptionsWidget` (preset dropdown + detailed PS3.15 toggles, with burned-in-PHI warning and Custom… detection) + a thin options-only `AnonymizationOptionsDialog`.
- [x] **Presets:** `DeepAnonymizerOptions.standard_share()` / `maximal_strip()` / `research()` + `ANONYMIZER_PRESETS` registry (`utils/deep_anonymizer.py`), matching the Phase 0.5 table.
- [x] **Inline "Options…" button** in the normal Export dialog opens `AnonymizationOptionsDialog` and stores the chosen `DeepAnonymizerOptions`.
- [x] **Full de-id export dialog** (`deep_anonymizer_export_dialog.py`) retitled "De-identify & Export DICOM (PS3.15)" and rebuilt to embed `AnonymizationOptionsWidget` (preset dropdown replaces the hand-built checkboxes).
- [x] **Menu relabeled** ("De-identify & Export DICOM (PS3.15)…") with an accurate status tip; no claim of Options we don't implement (Clean Pixel Data); burned-in-PHI warning retained.
- [x] Tests: `tests/test_anonymization_options_ui.py` (preset factories + CID 7050 codes, widget preset round-trip / Custom detection). Full suite **1004 passed / 17 skipped**.

## Phase 8 — Verification

- [x] Full `tests/` green (1004 passed / 17 skipped, +9 new in `test_anonymization_options_ui.py`).
- [x] `pyright` clean on changed files **except** the 3 pre-existing `Tag`-as-annotation errors in `deep_anonymizer.py` (318/329/343) — systemic pydicom-bump drift, tracked as a separate Maintenance item; not introduced by this work. New widget + export-dialog changes add 0 errors.
- [x] **Manual round-trip (completed 2026-07-12):** via **both** the inline Export checkbox (Standard Share) and the De-identify & Export dialog (each preset), de-identify a real CT + MR; reload elsewhere; confirm (a) loads cleanly, (b) `(0002,0003) == (0008,0018)` and both differ from source, (c) no AccessionNumber/StudyID/nested-PN PHI survives, (d) `(0012,0064)` present and accurate per preset, (e) "Options…" round-trips a custom preset, (f) Custom… appears when a toggle deviates.
- [x] `CHANGELOG.md` already captures the user-visible PS3.15 export work; `dev-docs/MAINTENANCE_LOG.md` captures the later static typing cleanup. Closed the remaining `dev-docs/TO_DO.md` backlog item after manual round-trip.

---

## Open questions / decisions (resolve in Phase 0 or with user)

1. **~~Should SIMPLE strip `AccessionNumber`/`StudyID`?~~ RESOLVED (user, 2026-06-15):** yes — simple must conform to PS3.15, which requires it. No longer optional.
2. **~~Should SIMPLE write provenance tags?~~ RESOLVED (user, 2026-06-15):** yes — conformant output writes `(0012,0062)=YES`, `(0012,0063)`, and the `(0012,0064)` code sequence for the profile/options applied.
3. **Consolidation (keep one / merge / keep both):** now a dedicated decision — see **Phase 0.5**. Lean Option B (merge) or Option A with sharply distinct preset names; confirm with user after Phase 0 research.
4. **~~Clean Descriptors vs. our free-text strip?~~ RESOLVED (PS3.15 §E.3.5, 2026-06-16):** 113105 is about scrubbing PHI *embedded* in descriptor text broadly; we only *remove* a curated free-text set, so we do **not** claim 113105.
5. **Default option deltas between presets** (only if Phase 0.5 keeps >1 preset): what exactly differs — retain device identity, retain institution, re-mint vs retain UIDs, date shift/blank/keep? Each retained item must be declared via `(0012,0064)`. *(Proposed preset table in Phase 0.5.)*
6. **~~Can we retain institution / station / private and stay compliant?~~ RESOLVED (PS3.15 §E.3, 2026-06-16):** institution → yes via **113112**; device/station → yes via **113109**; private → **only known-safe** under **113111** (allowlist engine required) — so **no blanket private retention**; we keep "remove all private." Each retained category must declare its code.

---

## TO_DO items to add (tracking)

When this plan starts, add/refresh these under **Bugs / Correctness** and **Maintenance** in `dev-docs/TO_DO.md` (single umbrella item already added points here; split out if worked independently):

- [ ] **[P1]** PS3.15 conformance — **file-meta UID sync bug** (`0002,0003`) (Phase 1).
- [ ] **[P1]** PS3.15 conformance — **simple "Anonymize" path must conform** (not patient-only) (Phases 2–6 applied to simple).
- [ ] **[P1]** PS3.15 conformance — **path consolidation decision** (keep one / merge / keep both) (Phase 0.5) — UX + architecture decision, may spawn its own follow-up item for the chosen UI work.
- [ ] **[P2]** PS3.15 conformance — `DeidentificationMethodCodeSequence (0012,0064)` + retain-option declarations (Phases 4–5).
- [ ] **[P2]** PS3.15 conformance — curated Table E.1-1 coverage (Phase 6).

---

## Files likely touched

| File | Change |
|------|--------|
| `src/utils/deep_anonymizer.py` | File-meta regen + preamble (P1); identifiers (P2); provenance via helper (P4); retain toggles `retain_device_identity`/`retain_institution_identity`/`retain_uids` + declarations (P5); curated tags (P6) |
| `src/utils/deep_anonymizer_profile.py` | New `IDENTIFIER_TAGS`; institution/device retain groups; curated extras; CID 7050 code constants |
| `src/utils/dicom_anonymizer.py` | **Sequence-recursive** patient stripping (P3) — shared by both paths |
| `src/utils/deid_provenance.py` | **New** — provenance + `(0012,0064)` code-sequence builder |
| `src/gui/dialogs/export_dialog.py` | Relabel simple checkbox (P7); optional provenance for simple (Open Q2) |
| `src/gui/dialogs/deep_anonymizer_export_dialog.py` | Optional declared-options note (P7) |
| `src/gui/export_manager.py` | Only if consolidating engines (Open Q3 / P7) |
| `tests/test_deep_anonymizer.py`, `tests/test_dicom_anonymizer.py` (new if absent) | Cases for P1–P6 |

---

## Task DAG

- **Phase 0 (research)** → gates everything.
- **Phase 0.5 (consolidation decision)** → after Phase 0; gates **Phase 7 (UI)** only. Engine phases do not wait on it.
- Phases **1, 2, 3** are independent of each other (parallelize) once Phase 0 done; all land in the shared conformant core so both export paths inherit them.
- **Phase 4** depends on Phase 0 (code values) and feeds **Phase 5**.
- **Phase 6** depends on Phase 0 (Table E.1-1 confirmation).
- **Phase 7 (UI)** depends on the Phase 0.5 decision.
- **Phase 8 (verification)** last; manual round-trip must check **both** export entry points (or the merged one) emit conformant output.

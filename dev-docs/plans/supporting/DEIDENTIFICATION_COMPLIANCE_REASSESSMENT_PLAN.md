# De-identification Compliance Reassessment Plan

**Status:** Active — research and claim-audit gate in progress; implementation phases are intentionally stubs until that gate is signed off.

**Priority:** P1

**Created / last updated:** 2026-08-31

**Related:** [PS3.15 De-identification Conformance Plan](../completed/PS315_DEIDENTIFICATION_CONFORMANCE_PLAN.md) (historical implementation record, not a current certification); [Deep Anonymizer Export Plan](DEEP_ANONYMIZER_EXPORT_PLAN.md); [PHI/PII repository guardrails](../../PHI_PII_REPOSITORY_GUARDRAILS.md).

## Purpose and decision rule

Establish a maintained, evidence-backed view of what the application's export
features do, what DICOM and applicable privacy frameworks require, and what the
product may accurately say about them. This plan applies to **every output path
described as anonymized, de-identified, private, or safe to share**, not merely
the primary DICOM Export dialog.

This is not legal advice, certification, or a declaration that an output is
anonymous under any law. No product copy may claim a DICOM profile, HIPAA Safe
Harbor, GDPR anonymization, regulatory approval, or suitability for public
release unless this plan records the applicable evidence and an authorized human
approves the claim.

Until Phase 3 completes, use conservative wording such as **“de-identification
tools,” “metadata de-identification,”** and **“review before sharing.”** Do not
use “conformant,” “compliant,” “safe to share,” “anonymous,” or “HIPAA-safe” as
unqualified product claims.

## Scope

In scope:

- DICOM File → Export, De-identify & Export DICOM, projection DICOM export, and
  MPR DICOM save.
- Any derived DICOM writer or direct caller of `DICOMAnonymizer` or
  `DeepDICOMAnonymizer`.
- Non-DICOM exports whose UI labels use “anonymize” or imply removal of PHI
  (for example, report/CSV/XLSX export), assessed separately from DICOM profile
  conformance.
- Export UI, user docs, help text, docstrings, release notes, and provenance
  metadata.

Out of scope until separately approved:

- Pixel redaction, OCR, visual review automation, and a Clean Pixel Data claim.
- Legal certification, expert-determination services, a HIPAA Safe Harbor
  attestation, GDPR/UK GDPR legal advice, or regulatory submissions.
- Retaining private attributes under the PS3.15 Retain Safe Private Option.

## Evidence and source-provenance policy

Every requirement, recommendation, and implemented claim in this document must
have a row in the source register or an explicit **Unverified** label. Prefer
primary normative sources. A model, blog, or another repository may suggest a
lead, but is never evidence by itself; record it only in the research log and
verify it independently before updating any status below.

| ID | Organization / source | Authority and use | Canonical link | Retrieved | Status |
|---|---|---|---|---|---|
| S-01 | National Electrical Manufacturers Association (NEMA), DICOM Standard | Normative DICOM confidentiality profile, action codes, profile options, file-meta and provenance requirements | [PS3.15 2026c Annex E](https://dicom.nema.org/medical/dicom/current/output/chtml/part15/chapter_E.html) | 2026-08-31 | Verified primary source. The retrieved page identified itself as **PS3.15 2026c**; preserve that edition label, section/table identifiers, retrieval date, and a content fingerprint in the Phase 1 dataset rather than silently treating the moving `current` URL as immutable. |
| S-02 | NEMA, DICOM Standard | Normative meanings/codes for de-identification method code sequence | [PS3.16 CID 7050](https://dicom.nema.org/medical/dicom/current/output/chtml/part16/sect_CID_7050.html) | 2026-08-31 | Verified primary source; reconcile emitted codes in Phase 2 |
| S-03 | U.S. Department of Health and Human Services, Office for Civil Rights | HIPAA de-identification guidance; jurisdictional/legal framework, not a DICOM-conformance specification | [Guidance on De-identification of Protected Health Information](https://www.hhs.gov/guidance/sites/default/files/hhs-guidance-documents/hhs_deid_guidance.pdf) | 2026-08-31 | Verified primary source; use only after applicability review |
| S-04 | Office of the Federal Register / eCFR | Current U.S. regulatory text for HIPAA de-identification; eCFR is continuously updated and should be checked again before a legal claim | [45 CFR 164.514](https://www.ecfr.gov/current/title-45/subtitle-A/subchapter-C/part-164/subpart-E/section-164.514) | 2026-08-31 | Verified primary source for the U.S. requirement text; applicability remains a legal decision |
| S-05 | pydicom contributors | Implementation/documentation comparison; expressly a starting point, not a normative de-identification authority | [Anonymize DICOM data example](https://pydicom.github.io/pydicom/stable/auto_examples/metadata_processing/plot_anonymize.html) | 2026-08-31 | Verified comparison source; no compliance claim adopted |
| S-06 | pydicom/deid contributors | Comparison of deliberately cautious “best effort” wording; not a DICOM or legal authority | [deid documentation](https://pydicom.github.io/deid/) | 2026-08-31 | Verified comparison source; wording decision remains pending Phase 3 |
| S-07 | Orthanc Team / Université catholique de Louvain | Open-source DICOM-server documentation comparison; profile-version/configuration and identifier safeguards | [Orthanc official site](https://orthanc.uclouvain.be/) | 2026-08-31 | General official reference; detailed documentation was reviewed during research. No compliance claim adopted. |
| S-08 | XNAT project | Open-source research-imaging application comparison; explicit PHI-storage and rule-limit warning | [Limits of DICOM Anonymization in XNAT](https://wiki.xnat.org/documentation/limits-of-dicom-anonymization-in-xnat) | 2026-08-31 | Verified comparison source; no compliance claim adopted |
| S-09 | FireVoxel | Application documentation comparison; configurable PHI profile and user-responsibility warning | [DICOM Operations and De-identification](https://firevoxel.org/docs/html/userguide/dicom_ops.html) | 2026-08-31 | Verified comparison source; no compliance claim adopted |
| S-10 | Google Cloud | Commercial service documentation comparison; explicit rules/heuristics and legal-compliance disclaimer | [De-identify DICOM data using DicomTagConfig](https://cloud.google.com/healthcare-api/docs/how-tos/dicom-deidentify-dicomtagconfig) | 2026-08-31 | Verified comparison source; no compliance claim adopted |
| S-11 | Philips | Commercial product DICOM Conformance Statement comparison; profile declaration and processing/authorization context | [Advanced Visualization Workspace DICOM Conformance Statement](https://www.documents.philips.com/assets/DICOM%20Conformance%20Statement/20260617/565d5c4861cb49779284b46c00a813c9.pdf) | 2026-08-31 | Verified comparison source; product-specific, no claim adopted |
| S-12 | Applicable privacy/data-protection authority for the deployment jurisdiction | Candidate jurisdiction-specific legal review (e.g. HIPAA, GDPR/UK GDPR); determines whether a legal claim is appropriate | To be selected with product/legal owner | Not yet applicable | Pending decision |
| S-13 | Radiological Society of North America (RSNA), MIRC Clinical Trial Processor | Open-source DICOM anonymizer comparison; script/configuration and separate pixel-anonymizer workflow | [CTP DICOM Anonymizer](https://mircwiki.rsna.org/index.php?title=The_CTP_DICOM_Anonymizer) | 2026-08-31 | Verified comparison source; no blanket output guarantee inferred |
| S-14 | ARX developers | Open-source data-anonymization tool comparison; Apache-2.0 warranty language, not DICOM-specific de-identification guidance | [ARX downloads and license](https://arx.deidentifier.org/downloads/) | 2026-08-31 | Verified comparison source; license disclaimer is not adopted product wording |

### Evidence lifecycle

`Unverified` → `Primary source verified` → `Implementation assessed` →
`Automated evidence` → `Human review complete` → `Claim approved`.

A later standard revision, newly supported IOD/SOP Class, new export route,
dependency change, or wording change returns affected rows to at least
**Implementation assessed**.

## Initial requirement and compliance matrix

This matrix is deliberately incomplete at plan creation. “Observed” means a
code/document review on 2026-08-31, not a conformance finding. “Unknown” is a
required research result, not a pass.

| ID | Requirement / recommendation | Primary evidence | Current observed implementation | Assessment | Required evidence / next action |
|---|---|---|---|---|---|
| R-01 | Apply the correct PS3.15 Table E.1-1 action to every relevant attribute, including nested sequence items and IOD-dependent X/Z/D resolution. | S-01 | `DeepDICOMAnonymizer` has curated tag inventories and sequence recursion; `DICOMAnonymizer` applies a broad group-0010 rule. | Partial / unverified coverage | Build a machine-readable action inventory and test fixtures covering required IOD types and nested contexts. |
| R-02 | Patient Birth Date `(0010,0030)` uses Basic Profile action Z. Keep the Type-2 element present and zero-length; temporal retain options do not override that row. | S-01 | Both anonymizers blank it. Deep date-shift leaves the empty value unchanged. | Implemented for reviewed paths; source-to-test trace needed | Retain the regression; add the traceability row and cover every public export route. |
| R-03 | Replace/remap UID attributes and references consistently when the selected profile requires action U; preserve DICOM-defined class/transfer-syntax UIDs. | S-01 | MPR now constructs the complete derived batch, then invokes `DeepDICOMAnonymizer.anonymize_batch()` with the same `DeepAnonymizerOptions` shape/default as standard DICOM export. A serialized MPR test confirms new derived Study/Series/SOP/Frame-of-Reference UIDs are not source UIDs and MPR instances share their remapped series UID. | Implemented for the reviewed MPR path; overall coverage unverified | Add top-level and nested-reference assertions for every public deep/export path against the eventual action inventory. |
| R-04 | Replace File Meta Information and preamble as required for a de-identified DICOM file; keep media-storage UID/class consistency. | S-01 | The shared deep engine sanitizes File Meta and preamble; the serialized MPR regression asserts zero preamble and `MediaStorageSOPInstanceUID == SOPInstanceUID`. | Implemented for reviewed MPR path; other paths pending | Extend final-on-disk coverage to every deep export route and independent DICOM validation. |
| R-05 | When making a profile claim, mark DICOM output with Patient Identity Removed and accurately record method/profile/options. | S-01, S-02 | The deep engine now records only a factual `DeidentificationMethod` text and removes inherited `PatientIdentityRemoved` / CID 7050 code-sequence values. This avoids an unsupported machine-readable profile assertion while assessment is incomplete. | Interim claim remediation complete; profile behavior unverified | Revisit provenance only with the completed Table E.1-1 evidence and a scoped Conformance Statement. |
| R-06 | Date handling must match the selected temporal option; document which date/time VRs and attribute rows are retained, modified, blanked, or removed. | S-01, S-02 | Deep modes keep/shift/blank broad DA/DT values; TM is retained on removal; DOB is always blank. | Unverified option mapping | Compare every supported behavior to Table E.1-1 and option semantics; revise controls/copy before making a profile claim. |
| R-07 | Remove or clean identifying private attributes only as PS3.15 permits; do not imply that blanket private-tag removal removes all PHI. | S-01 | Deep default removes odd-group private attributes; simple/MPR path needs audit. | Partial | Validate recursion and creator blocks; document vendor/private and pixel limitations. |
| R-08 | Address identifying text/graphics/pixels only when the corresponding option is actually implemented; otherwise warn clearly and do not claim it. | S-01 | UI warns that burned-in text is neither detected nor removed. | Warning present; complete scope unverified | Audit overlays, presentation states, icons, encapsulated documents, and all UI claims. |
| R-09 | Preserve DICOM validity for every supported SOP Class/IOD after de-identification. | S-01 plus applicable PS3.3/PS3.5 requirements | Tests perform synthetic pydicom round-trips. | Insufficient evidence | Define a modality/SOP-class corpus, independent validation tools, and negative tests for Type 1/2/conditional attributes. |
| R-10 | HIPAA Safe Harbor, Expert Determination, GDPR/UK GDPR “anonymous,” and similar legal claims require their own applicability and evidence analysis. | S-03, S-04; S-08 when selected | Current reviewed de-identification copy avoids legal/compliance assurances and directs users to organization-appropriate review. The complete claims inventory remains pending. | Interim claim remediation complete; no legal claim | Keep the no-claim policy and obtain authorized legal/product decision before adding legal language. |
| R-11 | Every user-visible export path named “anonymize” or “de-identify” has a defined scope and does not inherit a DICOM claim accidentally. | Product wording; S-01 where DICOM is claimed | The MPR dialog now uses the shared deep options/default and presents the metadata-only burned-in-pixel limitation. Legacy `anonymize=True` projection/export branches still call the base anonymizer; report export has a separate masking option. | MPR gap remediated; inventory incomplete | Assess and align the remaining base-anonymizer call sites before making a common-path claim. |
| R-12 | Remove group `0004` elements from a non-DICOMDIR de-identified SOP Instance/DICOM File. | S-01, E.1.1 step 9 | The shared deep engine now removes group `0004` recursively. Synthetic deep and final serialized MPR regressions cover a non-DICOMDIR element. | Implemented for reviewed deep paths; base paths pending | Extend final-on-disk coverage and decide treatment of any non-deep export path. |
| R-13 | Supply a scoped de-identifier Conformance Statement if making a PS3.15 conformance claim, including supported profile/options, attribute handling, dummy/replacement behavior, UID consistency, and encrypted-attributes behavior where applicable. | S-01, E.1.3 | No current dedicated statement located. | Missing / unverified | Define the required statement content in Phase 1 and publish only after the matrix is evidenced. |
| R-14 | When retaining/modifying longitudinal temporal information, ensure every related DICOM attribute, option declaration, and output assertion is correctly mapped. | S-01, S-02 | Date modes and CID codes exist; completeness of related temporal attributes has not been verified. | Unverified | Research the exact option semantics and required attributes; do not infer requirements from model output. |
| R-15 | A de-identifier claiming the Basic Profile protects the SOP Instance UID and **all** references to other SOP Instances, including references in sequence items; replacements must be internally consistent across the protected set. | S-01, E.1.1 steps 2 and 5 | Deep engine has a per-batch UID map; basic/MPR paths do not use it. | Partial / unverified | Test top-level and nested references across a multi-instance batch; document which UID contexts are intentionally preserved and why. |
| R-16 | A table action applies to sequence contents: `K` requires recursive application, `C` requires context-aware cleaning or recursive application, and an `X` sequence removes its items. | S-01, E.1.1 and Table E.1-1a | Deep engine recurses selected routines; coverage is curated rather than action-table-derived. | Unverified | Map every sequence action and test sequence removal/cleaning/UID remapping in serialized output. |
| R-17 | The action table is normative but extensible; new, retired, private, and standard-extended attributes may still identify people. De-identification of Private SOP Classes is not defined. | S-01, E.1.1 notes after Table E.1-1 | Blanket private removal exists only in the deep path; unsupported-object policy is not defined. | Unverified | Version the table dataset, define an upgrade trigger and explicit unsupported Private SOP Class behavior. |
| R-18 | If encrypted attributes are used, they have defined encoding/encryption and sequence requirements; use is optional, not an implicit substitute for normal replacement/removal. | S-01, E.1.1 steps 1 and 4 | No encrypted-attribute implementation identified. | Not implemented / no claim | Record as unsupported in a future Conformance Statement; do not add ad-hoc hashes or recovery identifiers as a substitute. |
| R-19 | Original Attributes Sequence can retain unencrypted pre-modification values and generally needs removal or selective treatment; Digital Signatures Sequence requires removal. | S-01, E.1.1 notes after Table E.1-1 | The shared deep engine removes both recursively. Synthetic deep and final serialized MPR regressions cover both top-level sequences. | Implemented for reviewed deep paths; base paths pending | Extend output coverage to remaining public routes; retain the no-profile-claim gate. |
| R-20 | Clean Pixel Data / Clean Recognizable Visual Features are separate options. Icon-image pixel data, graphics, overlays, structured text, and encapsulated documents require their own handling; the standard does not specify a general content-cleaning method. | S-01, E.1.1; E.3 options; notes after Table E.1-1 | Pixel warning exists; engine has no approved clean-pixel/visual-feature option. | Scope boundary present, implementation unverified | Keep the exclusion prominent; inventory these objects and decide block/remove/warn behavior rather than implying they are cleaned. |
| R-21 | Replacement and dummy values must not identify the patient and must preserve Information Object integrity; Type 1, Type 2, and conditional requirements determine whether `D`, `Z`, or `X` applies. | S-01, E.1.1 step 2 and Table E.1-1a | Patient Type-2 values are blanked; general IOD/type resolution is not implemented as a table-driven policy. | Partial / unverified | Test Type 1/2/conditional cases against the explicitly supported IOD set and record all dummy-value strategies. |
| R-22 | Profile options override the base-table action when selected, and retention options can increase re-identification risk; option declarations must match behavior. | S-01, E.1.1; E.3; S-02 | UI exposes temporal/UID/private-related choices and deep provenance codes; complete option mapping is unverified. | Unverified | Reconcile every UI selection, effective transformation, and CID 7050 code in a versioned option matrix. |
| R-23 | Attribute-profile conformance does not itself guarantee confidentiality or resolve regulatory requirements; the standard requires the de-identifier to address remaining identifying information. | S-01, Annex E note and E.1.1 notes; S-03/S-04 for U.S. legal context | Some product copy currently makes broader profile/safety assertions. | Claim gap confirmed | Complete Phase 3 before any legal, universal-safety, or unqualified-profile assertion. |

## Current path inventory (to be validated in Phase 2)

| Path | Entry point / implementation | Current description | Profile/claim state at plan creation | Audit priority |
|---|---|---|---|---|
| Standard DICOM Export | `export_dialog.py` → `ExportManager.build_deep_anonymized_selection()` → `DeepDICOMAnonymizer` | Options/presets and DICOM provenance | Claims Basic Profile in UI/docs; verify all attribute/action coverage | P1 |
| Dedicated DICOM de-identification | `deep_anonymizer_export_dialog.py` → same deep engine | Same options/presets | Same claim; verify identical serialized results | P1 |
| Projection DICOM export | `ExportManager` projection branch | Derived DICOM may be pre-anonymized | Must validate source/projection ordering and final metadata | P1 |
| MPR DICOM save | `mpr_dicom_export.py` → derived batch → `DeepDICOMAnonymizer.anonymize_batch()` when selected | Uses the same deep option shape/default as normal DICOM export; UI states metadata scope and pixel limitation | Serialized regression covers MPR UID remap, provenance, file meta/preamble, private/group-0004/special-sequence removal, source-UID-free generated comments, and post-transform folder tags. This is not full profile evidence. | P1 |
| Legacy/direct base anonymizer callers | `DICOMAnonymizer` callers outside the deep engine | Group-0010 transformation | Internal helper; not a standalone PS3.15 claim | P1 |
| Radiation-dose report CSV/JSON | `RadiationDoseReportDialog` → `apply_privacy_to_ct_radiation_dose_summary` | Masks selected UID/device strings in a non-DICOM summary | Separate masking feature; no DICOM provenance or profile claim applies | P1 |
| PNG/JPG/screenshots/cine | Raster/export rendering paths | Not de-identified according to user guide | Must keep scope boundary prominent | P2 |
| Dose report / CSV/XLSX and other non-DICOM exports | Individual exporters | May mask selected values | Not DICOM Profile output; needs feature-specific wording | P2 |

## Research log and external cross-checks

Record model-assisted leads here only after independent confirmation. Do not copy
their claims into the requirement matrix without a primary source.

| Date | Lead / contributor | Topic | Independent verification outcome | Incorporated where |
|---|---|---|---|---|
| 2026-08-31 | Codex primary-source review | DOB behavior; PS3.15 action codes; HIPAA distinction | PS3.15 Table E.1-1 lists Patient’s Birth Date as Z; HHS Safe Harbor is a separate legal framework. Verified against S-01 and S-03. | R-02, R-10 |
| 2026-08-31 | Kilo HY3 free | PS3.15 research | No usable response received; no claim incorporated. | — |
| 2026-08-31 | OpenCode Muse Spark 1.2 free | Wording / comparative research | pydicom’s example calls itself a “starting point”; pydicom/deid describes best-effort work and disclaims guaranteed IRB-validated output. Independently read S-05/S-06; neither is normative or adopted as product wording. | Phase 3 |
| 2026-08-31 | OpenCode/OpenRouter MiniMax M3 free | Repository compliance cross-check | Detailed read-only inventory retrieved after the initial completion notification was incomplete. Independently confirmed: MPR calls the base anonymizer; legacy `anonymize=True` branches remain in `export_manager.py`; current docs/menu use unqualified profile/safety wording. Its source-dependent conformance conclusions remain subject to the matrix and primary-source review. | R-11; Phase 0/2/3 |
| 2026-08-31 | Kilo LongCat 2.0 free | UI disclaimer, DICOM, and HIPAA cross-check | Independently confirmed against S-01, S-03, and S-04: a disclaimer cannot make an implementation conformant or establish a HIPAA de-identification method; PS3.15 and HIPAA are distinct frameworks. Code review confirmed the registered wording/path concerns. Did **not** adopt its overbroad provenance wording or legal inferences about specific identifiers without the required source/legal review. | R-05, R-10, R-11; Phase 3 |
| 2026-08-31 | Kilo LongCat 2.0 free | Standards cross-check | Confirmed from S-01: group `0004` handling and the distinction between profile conformance and confidentiality require explicit assessment. A proposed temporal-attribute detail remains unverified and is retained only as R-14 research. | R-12–R-14 |
| 2026-08-31 | Kilo HY3 free (second pass) | Peer-product wording comparison | Agent completed without a usable research response; no claim incorporated. Direct source review instead established S-07–S-11. | — |
| 2026-08-31 | OpenCode Muse Spark 1.2 free | Peer wording and limitation research | Retrieved its full report after completion. Independently verified the key comparison leads against S-01, S-05, S-07, S-10, S-13, and S-14. Incorporated only their documented scope/limitation patterns, not its suggested legal wording or any assertion that a disclaimer shifts legal responsibility. | S-13–S-14; Phase 3 |
| 2026-08-31 | Kilo LongCat 2.0 free | User-reachable path audit | Retrieved its full report after completion. Independently confirmed the MPR base-anonymizer calls and lack of base-engine provenance, then corrected the unsupported MPR parity label. The report's profile-conformance characterizations were not adopted. Its non-DICOM radiation-dose-report lead was confirmed and added to the path inventory. | R-05, R-11; Phase 2 |
| 2026-08-31 | OpenCode/NVIDIA MiniMax M3 (zero-cost fallback) | MPR design review | Retrieved after its permission request. Independently confirmed its actionable code findings: MPR folder names must derive from the transformed derived dataset, and nested source-series UID references require a serialized assertion. Implemented both. Its stale claim that `SeriesDescription` was not in the free-text inventory and its unimplemented progress refactor were not adopted. | R-03, R-11; Phase 2 |
| 2026-08-31 | Kilo StepFun 3.7 Flash free | Current MPR/de-identification diff review | Retrieved after the review run. Independently confirmed one option-propagation issue: an MPR description suffix must remain available when the user explicitly disables free-text stripping. Added a regression. Its preamble speculation and untested cancellation/progress suggestions were not adopted. | R-11; Phase 2 |
| 2026-08-31 | Codex primary-source review | Structural sequence/removal requirements | Independently verified S-01 E.1.1 step 9 and notes after Table E.1-1: non-DICOMDIR group `0004` elements must be removed; Digital Signatures require removal; Original Attributes generally needs removal or selective treatment. Implemented conservative removal in the shared deep engine with synthetic and serialized MPR evidence. | R-12, R-19; Phase 2 |

### Comparative-practice observations (not authority)

The following records how established tools describe their scope; it is a
comparison set, **not** a ranking or a basis for a DICOM/legal-conformance
claim. The original source and retrieval date are in S-06–S-11.

| Product / category | Organization | Observed wording or safeguard | Implication to assess, not an adopted decision |
|---|---|---|---|
| `deid` / open-source Python library | pydicom/deid contributors | Calls its work “best effort,” describes header/pixel cleaning and custom logic, and says it does not guarantee IRB-validated output. | A limitation statement can be specific about capability and non-guarantee without purporting to decide legal status. Verify whether “best effort” is understandable to this product’s audience. |
| Orthanc / open-source DICOM server | Orthanc Team / UCLouvain | Names the DICOM edition used by its anonymization profiles; removes private tags by default, offers configuration, and requires an explicit `Force` flag for identifier modifications that can disrupt the DICOM model. | Versioned profile scope and friction around risky identifier changes are useful design subjects; its documentation is not a substitute for output validation or a disclaimer. |
| XNAT / open-source research-imaging application | XNAT project | States it does not claim user-authored rules remove all PHI and warns that PHI can be stored before de-identification runs. | A clear boundary should cover both output limitations and local processing/storage behavior where applicable. |
| FireVoxel / imaging application | FireVoxel | Provides a customizable PHI profile, calls out variation among tools, and says users are responsible for local privacy-law compliance. | The dialog and documentation should state the selected scope/configuration and direct users to their organization’s required review process rather than making a universal legal claim. |
| Cloud Healthcare API / commercial service | Google Cloud | Explicitly says its rules/heuristics may differ by resource/dataset, are not guaranteed to meet legal/regulatory/compliance requirements, and users must configure and evaluate results. | A concise non-guarantee plus a concrete review instruction is a strong candidate pattern; legal/product review must select final wording. |
| Advanced Visualization Workspace / commercial product | Philips | Publishes a product-specific DICOM Conformance Statement and separately treats de-identification as regulated processing that may require documented authorization/consent. | Separate technical claims from processing-governance claims; only publish a conformance statement after the implementation evidence exists. |

These observations reinforce S-01’s warning that applying Attribute
Confidentiality Profiles does not by itself guarantee that all identifying
information has been removed or replace a de-identification process. They do
not answer whether any particular deployment is subject to HIPAA or another
law.

### Preliminary claims register (2026-08-31)

This is an initial, code-reviewed sample rather than the completed Phase 3
inventory. It documents statements that need evidence or interim narrowing; it
does **not** decide their truth. Exact UI text is included so later changes are
traceable.

| Surface / current wording | Meaning a reasonable user could take | Evidence status | Required Phase 0/3 disposition |
|---|---|---|---|
| Historical `USER_GUIDE_ANONYMIZATION.md`: “conforming to” the Basic Profile and “same conformant engine” | Every stated export path fully meets the current PS3.15 Basic Profile. | Unverified; the matrix identifies unassessed rows and the former MPR divergence. | **Interim remediation complete 2026-08-31:** replaced with metadata-scope wording, limitations, and no profile/legal claim. |
| Historical same-guide phrase: “safe default for sharing” | Standard-share output is suitable for sharing generally. | Too broad; output scope and recipient/legal context are unassessed. | **Interim remediation complete 2026-08-31:** replaced with factual selected-option behavior and required review. |
| Historical same-guide phrase: “Always confirm … no PHI survives before sharing” | Helpful review instruction, but risks implying a user can conclusively establish absence. | Directionally cautious, but needs product/legal wording review. | **Interim remediation complete 2026-08-31:** requires organization-appropriate review and states that a successful scan/load does not establish absence of identifying information. |
| Historical file-menu status tip: “de-identified to the PS3.15 Basic Profile” | The invoked behavior is a completed profile implementation. | Unverified pending R-01–R-14. | **Interim remediation complete 2026-08-31:** uses a metadata-de-identification capability label until a claim is approved. |
| Historical deep-export provenance: CID 7050 `113100` | The exported instance was processed according to the Basic Application Confidentiality Profile. | Unverified pending R-01 and R-15–R-22. | **Interim remediation complete 2026-08-31:** deep export no longer emits profile/option codes or `PatientIdentityRemoved`; it records only scoped method text until evidence supports a profile claim. |
| Historical MPR checkbox: “same as DICOM export” | MPR has the same engine, option behavior, provenance, and profile coverage. | Formerly contradicted by the base-anonymizer path. | **Remediated 2026-08-31:** MPR now invokes the shared deep batch/options and uses scoped metadata wording; full-profile coverage remains unverified. |

## Phase 0 — Freeze unsupported claims and establish ownership

- [ ] Name a product owner and an authorized legal/compliance reviewer for any
  jurisdictional claim. The engineering team may describe implemented behavior,
  not grant legal clearance.
- [ ] Search UI, user docs, developer docs, changelog, release notes, and source
  strings for “anonymous,” “anonymize,” “de-identify,” “PS3.15,” “conform,”
  “safe,” “HIPAA,” “GDPR,” “public,” and “share.” Add every claim to the claims
  register in Phase 3.
- [ ] If a current claim outruns verified evidence, replace it with a scoped,
  factual statement plus the existing burned-in-pixel warning. Do not wait for
  feature work to correct misleading public language.
- [ ] Decide whether this plan covers only application DICOM export or also all
  file/report exports labelled “anonymize.” Default: include both, but keep
  separate matrices and claims.

**Gate:** owner, scope, and a temporary wording policy recorded before new
compliance claims or external distribution messaging.

## Phase 1 — Authoritative research and requirement register

- [ ] Pin the DICOM edition/date used for the assessment; save section/table
  identifiers, retrieval date, organization, canonical URL, retrieved-page
  edition label, and a content fingerprint for every requirement. The
  `current` URL is a discovery link, not a version pin.
- [ ] Normalize the complete PS3.15 Table E.1-1 action inventory into a
  versioned, machine-readable requirements dataset. Record action, option
  overrides, Type/IOD resolution notes, sequence handling, source row, and a
  stable table-row identifier. Store a source-derived representation or a
  reproducible extraction recipe with its digest; do not hand-maintain a
  partial tag list as though it were the table.
- [ ] Verify PS3.16 CID 7050 code values, meanings, and option declarations
  against the same DICOM edition.
- [ ] Define which PS3.3 IOD/SOP Classes the application promises to preserve;
  document the applicable Type 1/2/conditional validation strategy.
- [ ] Research PS3.15 requirements for private attributes, overlays/graphics,
  icon images, encapsulated documents, structured reports, original attributes,
  File Meta, preamble, UIDs and references, and pixel content.
- [ ] Research each potentially applicable privacy regime with a named owner.
  Record applicability, not an assumed global rule. For HIPAA, distinguish Safe
  Harbor, Expert Determination, a limited data set, and operational policy.
- [ ] Store retrieved-source metadata in the source register above; no copied
  standard text beyond short, necessary paraphrases/quotes.

**Gate:** two independent primary-source reviews of the requirements dataset;
unresolved interpretation questions are explicitly marked and escalated before
code design.

## Phase 2 — Repository and output evidence assessment

- [ ] Build a complete call graph of all anonymization/de-identification/masking
  paths, including background, projection, MPR, derived objects, report export,
  and saved configuration paths.
- [ ] For each path, create a synthetic fixture matrix by modality/SOP Class,
  nested sequence, private attribute, SR, overlay/icon, encapsulated document,
  UID reference, and File Meta/preamble case.
- [ ] Capture final serialized output (not just in-memory `Dataset`) and compare
  it to the Phase 1 requirements dataset. Record pass/fail/not-applicable with
  a stable test identifier.
- [ ] Validate selected exports using pydicom plus at least one independent
  DICOM validator/tool where feasible; distinguish syntax/VR validity from IOD
  validity and de-identification-profile coverage.
- [ ] Replace MPR's base-anonymizer branch with the regular DICOM export's deep
  batch operation and the same `DeepAnonymizerOptions` UI/defaults. Build each
  derived MPR dataset first, process the complete derived batch once, then write
  it; this preserves one UID/date mapping and removes generated free-text source
  references before serialization. Verify folder naming, provenance, File Meta,
  preamble, generated MPR UIDs, and progress/cancellation behavior.
- [ ] Update the matrices above with evidence links and statuses. Never turn
  “untested” into “pass” because a model or a generic round-trip succeeded.

**Gate:** all public paths have an assessed scope and no P0/P1 unknowns before
implementation phases are planned in detail.

## Phase 3 — Wording, claims, and comparative-practice research

- [ ] Create a claims register: exact string, surface, audience, product path,
  intended meaning, evidence required, owner, and decision.
- [ ] Retrieve and version-pin pydicom and at least two mature DICOM-project
  examples (for example DCMTK, dcm4che, highdicom) only to compare scope and
  wording. Record organization, URL, version/commit where available, and
  retrieval date. Their wording is not authority for our claims.
- [ ] Compare terms such as “anonymization,” “de-identification,” “metadata
  only,” “best effort,” “profile implementation,” and “Safe Harbor.” Determine
  whether “best-effort” informs users without understating known constraints;
  obtain product/legal approval for the selected term.
- [ ] Make limitations prominent and consistent: pixel/burned-in text, unusual
  private data, non-DICOM outputs, retained options, and the need for a
  recipient-appropriate review process.
- [ ] Design and test a persistent limitation notice for the DICOM
  de-identification dialog, its confirmation/progress state, and the matching
  user-guide section. It must name the selected scope/options and known
  exclusions, avoid an unqualified legal/compliance conclusion, link to the
  detailed limitations, and be approved through the claims register before
  release.
  The existing startup `DisclaimerDialog` is not the integration point: it
  concerns diagnostic use and can be suppressed persistently through
  `disclaimer_accepted`. Assess a separate, operation-scoped component in the
  anonymization-options/export flow; whether it requires a per-export
  acknowledgement remains a product/legal decision.
- [ ] Ensure code/docstrings never call an internal utility “conformant” merely
  because it satisfies a subset of table rows; reserve profile language for the
  assessed export behavior and exact option set.

**Gate:** product copy review and authorized legal/compliance review for every
claim that crosses from technical behavior into legal/regulatory assurance.

## Phase 4 — Remediation design (stub; populate after Phases 1–3)

- [ ] Convert the approved requirements dataset into an auditable policy engine
  or generated inventory; define exception/extension handling and versioning.
- [ ] Decide the single-engine boundary for every DICOM export route, including
  MPR and derived/projection objects. **Decision recorded for MPR:** it shares
  the regular DICOM export deep batch operation and options; no independent
  base-anonymizer mode remains.
- [ ] Define a safe unsupported-object policy (block export, remove object,
  retain with warning, or require review) for attributes/objects not yet
  covered.
- [ ] Specify option-to-provenance mapping, compatibility expectations, and
  migration behavior.

## Phase 5 — Remediation implementation (stub; populate after design approval)

- [ ] Implement approved policy/engine changes in small traceable batches.
- [ ] Align all public paths, final serialization, provenance, and user-facing
  copy with the approved scope.
- [ ] Add regression tests for every requirement-matrix row changed.
- [ ] Update this plan’s assessment matrix in the same change as the code; no
  unrecorded “complete” claims.

## Phase 6 — Verification, release, and ongoing maintenance (stub)

- [ ] Run the full automated matrix, independent validation, privacy gates, and
  human visual-review scenarios using only approved synthetic/de-identified
  data.
- [ ] Require human review of limitations, legal wording, and any release note.
- [ ] Publish a scoped conformance statement only if Phases 1–5 establish it;
  otherwise publish the approved limitation wording.
- [ ] Add a recurring review trigger for DICOM edition changes, new export
  features, new supported SOP Classes, dependency changes, and privacy-law/
  jurisdiction changes.

## Definition of done

This plan is complete only when every in-scope path has a traceable requirement
assessment, approved wording, automated serialized-output evidence, documented
limitations, and appropriate human sign-off. A passing pydicom round-trip or a
clean metadata scan alone is not sufficient.

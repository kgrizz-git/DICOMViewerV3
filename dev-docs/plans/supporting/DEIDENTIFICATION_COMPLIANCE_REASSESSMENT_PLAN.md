# De-identification Compliance Reassessment Plan

**Status:** Active supporting record — bounded metadata-de-identification safeguards are complete. Formal PS3.3/IOD and PS3.15 profile-conformance work is explicitly deferred and is not scheduled.

**Priority:** P1

**Created / last updated:** 2026-09-02

**Related:** [PS3.15 De-identification Conformance Plan](../completed/PS315_DEIDENTIFICATION_CONFORMANCE_PLAN.md) (historical implementation record, not a current certification); [Deep Anonymizer Export Plan](DEEP_ANONYMIZER_EXPORT_PLAN.md); [PHI/PII repository guardrails](../../PHI_PII_REPOSITORY_GUARDRAILS.md).

## Purpose and decision rule

Establish a maintained, evidence-backed view of what the application's export
features do, what DICOM and applicable privacy frameworks require, and what the
product may accurately say about them. This plan applies to **every output path
described as anonymized, de-identified, private, or safe to share**, not merely
the primary DICOM Export dialog.

This is not legal advice, certification, or a declaration that an output is
anonymous under any law. The project is sole-maintained and has no legal or
compliance department. Accordingly, it will not make HIPAA Safe Harbor, GDPR
anonymization, regulatory-approval, or public-release-suitability claims. A
future technical DICOM-profile claim is permitted only if this plan records the
applicable evidence and the maintainer deliberately approves its exact scope.

Until a formal technical claim is deliberately approved, use conservative wording such as **“de-identification
tools,” “metadata de-identification,”** and **“review before sharing.”** Do not
use “conformant,” “compliant,” “safe to share,” “anonymous,” or “HIPAA-safe” as
unqualified product claims.

### Current operating decision — 2026-09-01

The project has completed its proportionate track: source-backed scope and
limitation wording, a reproducible PS3.15/CID 7050 evidence baseline, shared
deep-batch handling for MPR, and wholly synthetic serialized-output regressions
for common metadata risks. This is sufficient to support the current narrow
product language; it is not a DICOM-profile, IOD-validity, or legal result.

Keep this document as the evidence and change-control record. Do not begin the
formal-conformance track below merely because an unchecked item remains. Start
it only through an explicit maintainer decision to make a named technical claim
or to support a defined IOD/SOP Class family.

The completed bounded implementation task is recorded in the
[Legacy DICOM Export Hardening Plan](LEGACY_DICOM_EXPORT_HARDENING_PLAN.md).
It removes the risk of standalone base-anonymizer export behavior and adds
normal-export serialized-output coverage; it is not part of the deferred formal
conformance track.

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
- The current DICOM writer surface and any future formally supported SOP
  Class/IOD preservation scope. The current baseline is recorded in
  [DICOM Output Scope Baseline](DICOM_OUTPUT_SCOPE_BASELINE.md); it explicitly
  records that no finite source-IOD preservation promise exists yet.

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
| S-02 | NEMA, DICOM Standard | Normative meanings/codes for de-identification method code sequence | [PS3.16 CID 7050](https://dicom.nema.org/medical/dicom/current/output/chtml/part16/sect_CID_7050.html) | 2026-09-01 | Source-derived [CID 7050 inventory](ps316_cid7050_inventory.json) records the retrieved PS3.16 2026c page, its context-group metadata, source fingerprint, and all 13 table rows. It is code-value evidence only, not a claim that any profile or option is applied. |
| S-03 | U.S. Department of Health and Human Services, Office for Civil Rights | HIPAA de-identification guidance; jurisdictional/legal framework, not a DICOM-conformance specification | [Guidance on De-identification of Protected Health Information](https://www.hhs.gov/guidance/sites/default/files/hhs-guidance-documents/hhs_deid_guidance.pdf) | 2026-08-31 | Verified primary source; use only after applicability review |
| S-04 | Office of the Federal Register / eCFR | Current U.S. regulatory text for HIPAA de-identification; eCFR is continuously updated and should be checked again before a legal claim | [45 CFR 164.514](https://www.ecfr.gov/current/title-45/subtitle-A/subchapter-C/part-164/subpart-E/section-164.514) | 2026-08-31 | Verified primary source for the U.S. requirement text; applicability remains a legal decision |
| S-05 | pydicom contributors | Implementation/documentation comparison; expressly a starting point, not a normative de-identification authority | [Anonymize DICOM data example](https://pydicom.github.io/pydicom/stable/auto_examples/metadata_processing/plot_anonymize.html) | 2026-08-31 | Verified comparison source; no compliance claim adopted |
| S-06 | pydicom/deid contributors | Comparison of deliberately cautious “best effort” wording; not a DICOM or legal authority | [deid documentation](https://pydicom.github.io/deid/) | 2026-08-31 | Verified comparison source; “best effort” was not adopted as product wording. |
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
`Automated evidence` → `Maintainer review complete` → `Technical claim approved`.

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
| R-07 | Remove or clean identifying private attributes only as PS3.15 permits; do not imply that blanket private-tag removal removes all PHI. | S-01 | Deep default removes odd-group private attributes; simple export paths need audit. | Partial | Validate recursion and creator blocks; document vendor/private and pixel limitations. |
| R-08 | Address identifying text/graphics/pixels only when the corresponding option is actually implemented; otherwise warn clearly and do not claim it. | S-01 | UI warns that burned-in text is neither detected nor removed. | Warning present; complete scope unverified | Audit overlays, presentation states, icons, encapsulated documents, and all UI claims. |
| R-09 | Preserve DICOM validity for every supported SOP Class/IOD after de-identification. | S-01 plus applicable PS3.3/PS3.5 requirements | Tests perform synthetic pydicom round-trips. The current [output-scope baseline](DICOM_OUTPUT_SCOPE_BASELINE.md) records no formal source-IOD preservation promise; it identifies CT, MR, and Secondary Capture only as MPR-emitted candidate scopes. | Insufficient evidence | Define a formal IOD corpus, independent validation tools, and negative tests for Type 1/2/conditional attributes before claiming support. |
| R-10 | HIPAA Safe Harbor, Expert Determination, GDPR/UK GDPR “anonymous,” and similar legal claims require their own applicability and evidence analysis. | S-03, S-04; S-08 when selected | Current reviewed de-identification copy avoids legal/compliance assurances and directs users to organization-appropriate review. The complete claims inventory remains pending. | Interim claim remediation complete; no legal claim | Keep the no-legal-claim policy. Defer any legal language unless future project ownership explicitly changes that policy. |
| R-11 | Every user-visible export path named “anonymize” or “de-identify” has a defined scope and does not inherit a DICOM claim accidentally. | Product wording; S-01 where DICOM is claimed | MPR uses the shared deep options/default and presents the metadata-only burned-in-pixel limitation. `ExportManager` standalone `anonymize=True` requests now fail closed; normal export dialogs use the deep path. Report export has a separate masking option. | Reviewed DICOM metadata paths aligned; broader inventory remains scoped | Maintain the path inventory and re-check it before adding or materially changing an export/de-identification route. |
| R-12 | Remove group `0004` elements from a non-DICOMDIR de-identified SOP Instance/DICOM File. | S-01, E.1.1 step 9 | The shared deep engine removes group `0004` recursively. Synthetic deep and final serialized MPR regressions cover a non-DICOMDIR element; the normal ExportManager serialized regression covers nested patient metadata. Standalone base export requests fail closed. | Implemented for reviewed deep paths; no standalone base export path | Extend final-on-disk coverage only when a material new DICOM export path is added. |
| R-13 | Supply a scoped de-identifier Conformance Statement if making a PS3.15 conformance claim, including supported profile/options, attribute handling, dummy/replacement behavior, UID consistency, and encrypted-attributes behavior where applicable. | S-01, E.1.3 | No current dedicated statement located. | Missing / unverified | Define the required statement content in Phase 1 and publish only after the matrix is evidenced. |
| R-14 | When retaining/modifying longitudinal temporal information, ensure every related DICOM attribute, option declaration, and output assertion is correctly mapped. | S-01, S-02 | Date modes and CID codes exist; completeness of related temporal attributes has not been verified. | Unverified | Research the exact option semantics and required attributes; do not infer requirements from model output. |
| R-15 | A de-identifier claiming the Basic Profile protects the SOP Instance UID and **all** references to other SOP Instances, including references in sequence items; replacements must be internally consistent across the protected set. | S-01, E.1.1 steps 2 and 5 | The deep engine has a per-batch UID map. Basic paths do not use it; MPR now uses the shared deep batch/UID map. | Partial / unverified | Test top-level and nested references across a multi-instance batch; document which UID contexts are intentionally preserved and why. |
| R-16 | A table action applies to sequence contents: `K` requires recursive application, `C` requires context-aware cleaning or recursive application, and an `X` sequence removes its items. | S-01, E.1.1 and Table E.1-1a | Deep engine recurses selected routines; coverage is curated rather than action-table-derived. | Unverified | Map every sequence action and test sequence removal/cleaning/UID remapping in serialized output. |
| R-17 | The action table is normative but extensible; new, retired, private, and standard-extended attributes may still identify people. De-identification of Private SOP Classes is not defined. | S-01, E.1.1 notes after Table E.1-1 | Blanket private removal exists only in the deep path; unsupported-object policy is not defined. | Unverified | Version the table dataset, define an upgrade trigger and explicit unsupported Private SOP Class behavior. |
| R-18 | If encrypted attributes are used, they have defined encoding/encryption and sequence requirements; use is optional, not an implicit substitute for normal replacement/removal. | S-01, E.1.1 steps 1 and 4 | No encrypted-attribute implementation identified. | Not implemented / no claim | Record as unsupported in a future Conformance Statement; do not add ad-hoc hashes or recovery identifiers as a substitute. |
| R-19 | Original Attributes Sequence can retain unencrypted pre-modification values and generally needs removal or selective treatment; Digital Signatures Sequence requires removal. | S-01, E.1.1 notes after Table E.1-1 | The shared deep engine removes both recursively. Synthetic deep and final serialized MPR regressions cover both top-level sequences. | Implemented for reviewed deep paths; base paths pending | Extend output coverage to remaining public routes; retain the no-profile-claim gate. |
| R-20 | Clean Pixel Data / Clean Recognizable Visual Features are separate options. Icon-image pixel data, graphics, overlays, structured text, and encapsulated documents require their own handling; the standard does not specify a general content-cleaning method. | S-01, E.1.1; E.3 options; notes after Table E.1-1 | Pixel warning exists; engine has no approved clean-pixel/visual-feature option. | Scope boundary present, implementation unverified | Keep the exclusion prominent; inventory these objects and decide block/remove/warn behavior rather than implying they are cleaned. |
| R-21 | Replacement and dummy values must not identify the patient and must preserve Information Object integrity; Type 1, Type 2, and conditional requirements determine whether `D`, `Z`, or `X` applies. | S-01, E.1.1 step 2 and Table E.1-1a | Patient Type-2 values are blanked; general IOD/type resolution is not implemented as a table-driven policy. | Partial / unverified | Test Type 1/2/conditional cases against the explicitly supported IOD set and record all dummy-value strategies. |
| R-22 | Profile options override the base-table action when selected, and retention options can increase re-identification risk; option declarations must match behavior. | S-01, E.1.1; E.3; S-02 | UI exposes temporal/UID/private-related choices; the deep path currently does not emit CID 7050 profile/option codes while the assessment remains incomplete. The complete option mapping is unverified. | Unverified | Reconcile every UI selection, effective transformation, and CID 7050 code in a versioned option matrix. |
| R-23 | Attribute-profile conformance does not itself guarantee confidentiality or resolve regulatory requirements; the standard requires the de-identifier to address remaining identifying information. | S-01, Annex E note and E.1.1 notes; S-03/S-04 for U.S. legal context | Reviewed product copy uses scoped metadata-de-identification wording and review-before-sharing limits. | Interim claim remediation complete; no profile/legal claim | Preserve the policy; re-open the formal track before any unqualified profile or legal assertion. |

## Current path inventory

| Path | Entry point / implementation | Current description | Current claim state | Audit priority |
|---|---|---|---|---|
| Standard DICOM Export | `export_dialog.py` → `ExportManager.build_deep_anonymized_selection()` → `DeepDICOMAnonymizer` | Options/presets and scoped method description | Metadata-de-identification wording; no profile/legal claim. Formal attribute/action coverage is deferred. | P1 |
| Dedicated DICOM de-identification | `deep_anonymizer_export_dialog.py` → same deep engine | Same options/presets | Metadata-de-identification wording; no profile/legal claim. Formal identical-output assessment is deferred. | P1 |
| Projection DICOM export | `ExportManager` projection branch | Derived DICOM may be pre-anonymized | Must validate source/projection ordering and final metadata | P1 |
| MPR DICOM save | `mpr_dicom_export.py` → derived batch → `DeepDICOMAnonymizer.anonymize_batch()` when selected | Uses the same deep option shape/default as normal DICOM export; UI states metadata scope and pixel limitation | Serialized regression covers MPR UID remap, provenance, file meta/preamble, private/group-0004/special-sequence removal, source-UID-free generated comments, and post-transform folder tags. This is not full profile evidence. | P1 |
| Legacy/direct base anonymizer callers | `ExportManager` rejects standalone `anonymize=True`; `DeepDICOMAnonymizer` retains its internal base helper | No standalone output; deep path remains the scoped metadata transformation | Internal helper; not a standalone PS3.15 claim | Remediated 2026-09-02 |
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

This is an initial, code-reviewed sample rather than a comprehensive future
inventory. It documents statements that need evidence or interim narrowing; it
does **not** decide their truth. Exact UI text is included so later changes are
traceable.

| Surface / current wording | Meaning a reasonable user could take | Evidence status | Required disposition |
|---|---|---|---|
| Historical `USER_GUIDE_ANONYMIZATION.md`: “conforming to” the Basic Profile and “same conformant engine” | Every stated export path fully meets the current PS3.15 Basic Profile. | Unverified; the matrix identifies unassessed rows and the former MPR divergence. | **Interim remediation complete 2026-08-31:** replaced with metadata-scope wording, limitations, and no profile/legal claim. |
| Historical same-guide phrase: “safe default for sharing” | Standard-share output is suitable for sharing generally. | Too broad; output scope and recipient/legal context are unassessed. | **Interim remediation complete 2026-08-31:** replaced with factual selected-option behavior and required review. |
| Historical same-guide phrase: “Always confirm … no PHI survives before sharing” | Helpful review instruction, but risks implying a user can conclusively establish absence. | Directionally cautious, but needs product/legal wording review. | **Interim remediation complete 2026-08-31:** requires organization-appropriate review and states that a successful scan/load does not establish absence of identifying information. |
| Historical file-menu status tip: “de-identified to the PS3.15 Basic Profile” | The invoked behavior is a completed profile implementation. | Unverified pending R-01–R-14. | **Interim remediation complete 2026-08-31:** uses a metadata-de-identification capability label until a claim is approved. |
| Historical deep-export provenance: CID 7050 `113100` | The exported instance was processed according to the Basic Application Confidentiality Profile. | Unverified pending R-01 and R-15–R-22. | **Interim remediation complete 2026-08-31:** deep export no longer emits profile/option codes or `PatientIdentityRemoved`; it records only scoped method text until evidence supports a profile claim. |
| Historical MPR checkbox: “same as DICOM export” | MPR has the same engine, option behavior, provenance, and profile coverage. | Formerly contradicted by the base-anonymizer path. | **Remediated 2026-08-31:** MPR now invokes the shared deep batch/options and uses scoped metadata wording; full-profile coverage remains unverified. |

## Completed safeguards — claim scope and wording

- [x] Record the project policy: it is sole-maintained with no legal/compliance
  department, and it will make no jurisdictional or regulatory de-identification
  claim. Engineering may describe verified technical behavior only.
- [x] Search UI, user docs, developer docs, changelog, release notes, and source
  strings for “anonymous,” “anonymize,” “de-identify,” “PS3.15,” “conform,”
  “safe,” “HIPAA,” “GDPR,” “public,” and “share.” The resulting scoped record
  is the preliminary claims register above; historic overclaims were preserved
  there for traceability rather than left in product copy.
- [x] If a current claim outruns verified evidence, replace it with a scoped,
  factual statement plus the existing burned-in-pixel warning. Do not wait for
  feature work to correct misleading public language. Completed 2026-08-31:
  UI/docs/provenance now describe metadata de-identification and direct review
  before sharing.
- [x] Decide whether this plan covers only application DICOM export or also all
  file/report exports labelled “anonymize.” Default: include both, but keep
  separate matrices and claims. The current path inventory records both and
  distinguishes DICOM metadata handling from non-DICOM masking.

**Gate met 2026-08-31:** scope and the no-legal-claim wording policy were
recorded before new technical-profile claims or external distribution messaging.

## Maintainer choices — 2026-09-01

The source evidence, output-scope baseline, action-resolution method, and
warning/wording work are recorded. They improve the implementation and keep
claims bounded; they do **not** establish PS3.15 profile conformance, IOD
validity, or a legal/privacy conclusion.

The selected practical hardening milestone is complete; see
[completed practical safeguards](#completed-practical-safeguards). It is
implementation evidence only, not a conformance result.

The maintainer may instead choose either of these explicitly deferred paths:

1. a narrow, named-object PS3.3 Type 1/2/conditional assessment, if a future
   technical statement about a particular output family is useful; or
2. a broad PS3.15 profile-conformance program, which would require resolving
   all applicable table actions, selected options, IOD validity, and ongoing
   maintenance. It is not needed for the current scoped warnings.

Do not start either deferred path implicitly during ordinary maintenance.

## Completed research baseline

- [x] Record the initial DICOM edition/date used for the assessment; the committed
  source-derived inventory records the retrieved page's edition label, digest,
  byte count, URLs, and timestamp. It also records whether a stable edition URL
  was published at retrieval time; the digest is the effective immutable pin
  when it was not. The raw source remains an ignored local retrieval artifact
  and can be regenerated using
  `scripts/build_ps315_e1_inventory.py`.
- [x] Normalize the complete PS3.15 Table E.1-1 action inventory into the
  versioned, machine-readable
  [`ps315_e1_inventory.json`](ps315_e1_inventory.json). It preserves raw base
  actions and option columns; IOD Type and option-dependent resolution remains
  intentionally unassessed.
- [x] Define the [IOD- and option-specific action-resolution method](PS315_E1_ACTION_RESOLUTION_METHOD.md).
  It records the inputs, compound-action procedure, and unresolved-status rule
  without resolving any row or selecting a formal IOD support scope.
- [x] Record the current DICOM writer surface in the
  [output-scope baseline](DICOM_OUTPUT_SCOPE_BASELINE.md). It explicitly
  distinguishes arbitrary source-dataset re-export from the MPR writer's CT,
  MR, and Secondary Capture SOP Class selection, and records that no formal
  IOD-preservation promise exists yet.
- [x] Verify PS3.16 CID 7050 code values, meanings, and option declarations
  against the same DICOM edition. The source-derived
  [`ps316_cid7050_inventory.json`](ps316_cid7050_inventory.json) records all
  13 rows and context-group metadata from the retrieved PS3.16 2026c page.
  It can be regenerated from the ignored
  `tmp/ps315-assessment/PS3.16-current-CID-7050.html` artifact using
  `scripts/build_ps316_cid7050_inventory.py`; the extractor verifies that the
  supplied edition matches the retrieved page before writing the inventory.
  It is an evidence register only: it does not reactivate code-sequence
  provenance or assert that an option/profile is implemented.
## Deferred formal-conformance track — do not schedule without an explicit claim

- [ ] For each inventory row, record the resolved action policy for each
  supported IOD Type and selected option set. Do not infer `X/Z/D` resolution
  from a generic dataset.
- [ ] Pin the DICOM edition/date used for every later assessment source; save section/table
  identifiers, retrieval date, organization, canonical URL, retrieved-page
  edition label, and a content fingerprint for every requirement. The
  `current` URL is a discovery link, not a version pin.
- [ ] Select any PS3.3 IOD/SOP Classes the application will formally promise
  to preserve; then document the applicable Type 1/2/conditional validation
  strategy. Do not mistake the current MPR SOP Class selection for that promise.
- [ ] Research PS3.15 requirements for private attributes, overlays/graphics,
  icon images, encapsulated documents, structured reports, original attributes,
  File Meta, preamble, UIDs and references, and pixel content.
- [ ] Research each potentially applicable privacy regime with a named owner.
  Record applicability, not an assumed global rule. For HIPAA, distinguish Safe
  Harbor, Expert Determination, a limited data set, and operational policy.
- [ ] Store retrieved-source metadata in the source register above; no copied
  standard text beyond short, necessary paraphrases/quotes.

**Formal-track gate:** two independent primary-source reviews of the requirements dataset;
unresolved interpretation questions remain explicitly marked and block a
technical profile claim before code design. The completed review evidence is in
the [PS3.15 Table E.1-1 primary-source review record](PS315_E1_PRIMARY_SOURCE_REVIEWS.md).

- [x] Complete independent primary-source review 1: compare the committed
  inventory's header, row count, complete extracted requirements array, and a
  documented sample of rows against the retained official source.
- [x] Complete independent primary-source review 2 using a separately retrieved
  official source snapshot. The source fingerprint and regenerated requirements
  array match the committed inventory.

## Completed practical safeguards

- [x] Build a compact, wholly synthetic serialized-output regression suite for
  the selected common sharing-risk cases: nested identifiers, private
  attributes, UID references, group `0004`, free text, File Meta, and
  MPR-derived output. The deep-batch round trip is covered by
  `tests/test_deep_anonymizer.py::TestDeepDICOMAnonymizer::test_serialized_batch_scrubs_common_nested_metadata_risks`;
  the on-disk MPR derived-output case is covered by
  `tests/test_mpr_dicom_export.py::test_write_mpr_series_deidentified_uses_deep_batch_on_disk`.
- [x] For every case, assert only the observed behavior and the intended
  metadata-de-identification invariant (for example, removal, blanking, or
  consistent remapping observed in the current implementation). The new
  deep-batch test docstring explicitly excludes IOD validity, PS3.15 profile
  coverage, and a legal/privacy result; the MPR assertions remain limited to
  observed serialized metadata behavior.
- [x] Re-check that the relevant dialog and user-guide warnings still direct
  users to review output before sharing. Verified the shared
  `BURNED_IN_PHI_WARNING`, the DICOM export/MPR surfaces, and
  [`USER_GUIDE_ANONYMIZATION.md`](../../../user-docs/USER_GUIDE_ANONYMIZATION.md).
- [x] Replace MPR's former base-anonymizer branch with the regular DICOM
  export's deep batch operation and the same `DeepAnonymizerOptions`
  UI/defaults. Derived MPR datasets are processed as one batch before writing,
  preserving a shared UID/date mapping and removing generated free-text source
  references before serialization. Completed 2026-08-31; serialized MPR
  regression coverage was extended on 2026-09-01.

**Completed-milestone gate:** the compact suite passes, is wholly synthetic, and makes
no conformance claim. Completion does not open the deferred PS3.3 or broad
profile-conformance paths above.

**Completed 2026-09-01:** This bounded regression milestone adds serialized
output evidence only. It does not change the scoped wording policy or begin
the deferred PS3.3/IOD or broad PS3.15 profile-conformance assessments.

The broader fixture matrix below is a separate deferred assessment of all
public paths and modalities. Do not duplicate it during ordinary maintenance;
promote a useful synthetic fixture only if the maintainer later deliberately
starts that broader assessment.

## Deferred repository / output assessment — formal track only

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
- [ ] Update the matrices above with evidence links and statuses. Never turn
  “untested” into “pass” because a model or a generic round-trip succeeded.

**Formal-track gate:** all public paths have an assessed scope and no P0/P1 unknowns before
implementation phases are planned in detail.

## Completed wording / comparison baseline

- [x] Create an initial claims register: exact historic string, surface,
  reasonable interpretation, evidence status, and disposition. The preliminary
  claims register above records the remediated scope. Expand it only before a
  new technical claim, not as standing work.
- [x] Retrieve and record pydicom and other mature DICOM-project comparison
  examples only to compare scope and
  wording. The source register records organization, URL, and retrieval date;
  their wording is not authority for our claims.
- [x] Compare terms such as “anonymization,” “de-identification,” “metadata
  only,” “best effort,” “profile implementation,” and “Safe Harbor.” Determine
  whether “best-effort” informs users without understating known constraints;
  maintain the no-legal-claim policy when selecting a term. Decision: do not
  adopt “best effort”; retain scoped metadata-de-identification wording.
- [x] Make limitations prominent and consistent: pixel/burned-in text, unusual
  private data, non-DICOM outputs, retained options, and the need for a
  recipient-appropriate review process.
- [ ] Consider a persistent limitation acknowledgement for the DICOM
  de-identification dialog, its confirmation/progress state, and the matching
  user-guide section. It must name the selected scope/options and known
  exclusions, avoid an unqualified legal/compliance conclusion, link to the
  detailed limitations, and be approved through the claims register by the
  maintainer before release.
  The existing startup `DisclaimerDialog` is not the integration point: it
  concerns diagnostic use and can be suppressed persistently through
  `disclaimer_accepted`. This is optional UX work, not a prerequisite for the
  current scoped wording; whether it requires a per-export acknowledgement
  remains a maintainer decision.
- [x] Ensure code/docstrings never call an internal utility “conformant” merely
  because it satisfies a subset of table rows; reserve profile language for the
  assessed export behavior and exact option set.

**Ongoing-copy gate:** maintainer review for new technical product copy. Claims that cross into
legal/regulatory assurance are out of scope and must not be added.

## Deferred implementation / verification — formal track only

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

If this formal track is deliberately started, populate and sequence the former
implementation and verification phases here. Each change must add its
requirement-matrix evidence, serialized regression, limitation wording review,
and appropriate validation. Publish a scoped conformance statement only if
that work establishes it; otherwise retain the approved limitation wording.

## Status and re-entry triggers

The selected modest track is complete. Re-open the deferred formal track only
when the maintainer chooses to make a named PS3.15 technical claim, promise
validity for named IOD/SOP Class output, or change the DICOM edition/engine in
a way that requires a formal conformance conclusion. A passing pydicom
round-trip or a clean metadata scan alone is not sufficient for a formal
conformance claim. Material DICOM export-route or de-identification-option
changes instead follow the maintenance trigger below; they do not by themselves
re-open the deferred formal track.

For any material DICOM export-route, de-identification-option, or user-facing
claim change, first update the path inventory, scoped limitation wording, and a
wholly synthetic serialized-output regression. This maintenance trigger does
not itself reopen the deferred formal-conformance track.

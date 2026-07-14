# Commercial Release Readiness — Master Gate

**Status:** Active — the single "can we sell this yet?" checklist
**Last updated:** 2026-06-13
**Owner:** product/release

> **Purpose.** One place to see everything that must be true **before charging money** for
> DICOM Viewer V3. This is a **gate and index**, not a how-to: each item links to the plan
> that owns the detail. Do not duplicate detail here — update the owning plan, then check the
> box here when its blocker is cleared.
>
> **How to read it:** **Tier 0 = hard blockers** (cannot legally/technically sell until done).
> **Tier 1 = required for a credible launch.** **Tier 2 = recommended / fast-follow.**
>
> **Not legal/business advice.** Items marked 🧑‍⚖️ need qualified counsel — see
> [License & compliance plan, "Open questions requiring counsel"](plans/supporting/LICENSE_AND_COMPLIANCE_PLAN.md#open-questions-requiring-counsel).

---

## Gate dashboard

| # | Blocker | Tier | Owner plan | Status |
|---|---------|------|-----------|--------|
| 1 | Replace GPL `pylibjpeg-libjpeg` + verify decode | 0 | [Decoder spike plan](plans/supporting/DECODER_REPLACEMENT_SPIKE_PLAN.md) | 🟡 Spike done → **GDCM recommended** (LGPL, full coverage, lossless bit-exact). Pending: frozen-build check, then productionize |
| 2 | Verify/replace FFmpeg (`imageio-ffmpeg`) license | 0 | [Compliance §0b](plans/supporting/LICENSE_AND_COMPLIANCE_PLAN.md#0b-ffmpeg-via-imageio-ffmpeg--likely-lgpl-only-but-verify-verify-before-treating-as-blocker) | ❌ Not started |
| 3 | Replace Liberation Sans font with OFL/Apache font | 0 | [Compliance §3b](plans/supporting/LICENSE_AND_COMPLIANCE_PLAN.md#3b-per-component-checklist-post-phase-0) | ❌ Not started |
| 4 | Choose project license + add `LICENSE` | 0 | [Compliance §1](plans/supporting/LICENSE_AND_COMPLIANCE_PLAN.md#1b-project-license-file) | ❌ Not started |
| 5 | Qt/PySide6 LGPL compliance (or Qt commercial) | 0 | [Compliance §2](plans/supporting/LICENSE_AND_COMPLIANCE_PLAN.md#phase-2--qt--pyside6-lgpl-compliance-for-commercial-distribution) | ❌ Not started |
| 6 | EULA + non-diagnostic intended-use statement | 0 | [Compliance §4a/§4b](plans/supporting/LICENSE_AND_COMPLIANCE_PLAN.md#4a-eula-end-user-license-agreement) | 🟡 Intended-use decided (2026-06-13) |
| 7 | Decide & document business/tier model | 0 | [Tiers §7 Phase A](plans/supporting/PRODUCT_TIERS_AND_LICENSING_ENFORCEMENT_PLAN.md#7-phased-rollout-future-work--unchecked) | 🟡 Leaning freemium |
| 8 | License-enforcement build (entitlements + signed file) | 0¹ | [Tiers §3–§4](plans/supporting/PRODUCT_TIERS_AND_LICENSING_ENFORCEMENT_PLAN.md#3-enforcement-architecture-single-build--entitlements) | ❌ Not started |
| 9 | Sales & delivery channel (payment + key delivery) | 0 | [Tiers §4d/§8](plans/supporting/PRODUCT_TIERS_AND_LICENSING_ENFORCEMENT_PLAN.md#4d-optional-later-online-activation--3rd-party-licensing) | ❌ Not started |
| 10 | Code signing (Win Authenticode + macOS notarization) | 0² | [Code signing guide](info/CODE_SIGNING_AND_NOTARIZATION.md) | ❌ Not started |
| 11 | Finalize product name + string consistency | 1 | [§ Naming](#naming) | ❌ Not started |
| 12 | Versioned release pipeline → signed installers | 1 | [Versioned release plan](plans/supporting/VERSIONED_RELEASE_PLAN.md) | ❌ Not started |
| 13 | `THIRD_PARTY_LICENSES.md` generated & bundled | 1 | [Compliance §3a/§5](plans/supporting/LICENSE_AND_COMPLIANCE_PLAN.md#3a-generate-sbom) | 🟡 Generator exists |
| 14 | Privacy policy | 1 | [Compliance §4c](plans/supporting/LICENSE_AND_COMPLIANCE_PLAN.md#4c-privacy-policy) | ❌ Not started |
| 15 | About dialog: version/tier/licenses/intended-use | 1 | [Tiers §3b](plans/supporting/PRODUCT_TIERS_AND_LICENSING_ENFORCEMENT_PLAN.md#3b-ui-affordances-no-dead-ends) | ❌ Not started |
| 16 | `pip-audit` clean or dispositioned | 1 | [Compliance §3c](plans/supporting/LICENSE_AND_COMPLIANCE_PLAN.md#3c-pip-audit-for-cves) | ❌ Not started |
| 17 | Cross-platform release QA pass | 1 | [Versioned release plan](plans/supporting/VERSIONED_RELEASE_PLAN.md) | ❌ Not started |

¹ Tier 0 only if you ship paid tiers from day one (you intend to). ²
Effectively required: unsigned installers trigger SmartScreen/Gatekeeper warnings that kill
trust in a paid product.

---

## Tier 0 — Hard blockers (must be done to sell)

### Licensing of dependencies (legal blockers)
- [ ] **Replace `pylibjpeg-libjpeg` (GPL-3.0)** and **verify the replacement decodes your real data.**
      This is *the* gating item — a closed-source paid binary cannot bundle GPL. Likely just drop it
      for **Pillow-only** decode; if CR/DX JPEG coverage gaps remain, use **GDCM (LGPL)**.
      → **executable plan: [Decoder Replacement Spike Plan](plans/supporting/DECODER_REPLACEMENT_SPIKE_PLAN.md)**
      (golden-reference + hash-diff to catch silent pixel corruption); options analysis:
      [`PYLIBJPEG_ALTERNATIVES_AND_DICOM_DECODER_STRATEGY.md`](info/PYLIBJPEG_ALTERNATIVES_AND_DICOM_DECODER_STRATEGY.md);
      legal gate: [Compliance §0a](plans/supporting/LICENSE_AND_COMPLIANCE_PLAN.md#0a-pylibjpeg-libjpeg--gpl-30-jpeg-decoder-blocking).
      **Verification is part of the blocker**: test decode on CT, MR, CR, DX, XA, US; log any
      transfer syntax that fails; run full test suite + manual smoke after removal.
- [ ] **Verify `imageio-ffmpeg` is the LGPL-only build** (likely fine) or replace it.
      → [Compliance §0b](plans/supporting/LICENSE_AND_COMPLIANCE_PLAN.md#0b-ffmpeg-via-imageio-ffmpeg--likely-lgpl-only-but-verify-verify-before-treating-as-blocker).
- [ ] **Replace Liberation Sans** (GPL-2.0 + ambiguous embedding exception) with an SIL OFL /
      Apache font (Noto Sans, Source Sans 3, Inter, or Roboto).
      → [Compliance §3b](plans/supporting/LICENSE_AND_COMPLIANCE_PLAN.md#3b-per-component-checklist-post-phase-0).
- [ ] **Confirm no other GPL/AGPL** in the release venv (the commit-time gate already enforces
      this; re-run in the *release* venv after the swaps). → [Compliance §3](plans/supporting/LICENSE_AND_COMPLIANCE_PLAN.md#phase-3--dependency-compliance-audit).

### Your product's license & legal artifacts
- [ ] **Choose the project license** (proprietary vs dual) and add a `LICENSE` file.
      → [Compliance §1](plans/supporting/LICENSE_AND_COMPLIANCE_PLAN.md#1b-project-license-file).
- [ ] **Qt/PySide6 LGPL compliance**: ship Qt notices + a relink path (dynamic link), or buy a
      Qt commercial license. → [Compliance §2](plans/supporting/LICENSE_AND_COMPLIANCE_PLAN.md#phase-2--qt--pyside6-lgpl-compliance-for-commercial-distribution).
- [ ] **EULA** presented and accepted at install. 🧑‍⚖️ → [Compliance §4a](plans/supporting/LICENSE_AND_COMPLIANCE_PLAN.md#4a-eula-end-user-license-agreement).
- [x] **Intended-use claim decided (2026-06-13): not for diagnostic use** (research/education/
      workflow). Still must be **placed** in EULA, README, About dialog, and all marketing.
      → [Compliance §4b](plans/supporting/LICENSE_AND_COMPLIANCE_PLAN.md#4b-medical-use-disclaimer-critical).

### Monetization mechanics
- [ ] **Document the business/tier model** in `dev-docs/info/COMMERCIAL_LICENSE_MODEL.md`
      (free basic / full trial / paid full; feature split). → [Tiers §2 + Phase A](plans/supporting/PRODUCT_TIERS_AND_LICENSING_ENFORCEMENT_PLAN.md#2-tier-feature-split-proposed--needs-your-sign-off).
- [ ] **Build license enforcement** — entitlement layer + offline signed-license verification +
      trial flow. → [Tiers §3–§4 + Phases C–E](plans/supporting/PRODUCT_TIERS_AND_LICENSING_ENFORCEMENT_PLAN.md#3-enforcement-architecture-single-build--entitlements).
- [ ] **Sales & delivery channel** — how customers pay and receive a key. Strongly consider a
      Merchant-of-Record (Paddle / Lemon Squeezy) to offload global sales tax/VAT. 🧑‍⚖️
      → [Tiers §4d/§8](plans/supporting/PRODUCT_TIERS_AND_LICENSING_ENFORCEMENT_PLAN.md#4d-optional-later-online-activation--3rd-party-licensing).

### Distribution trust
- [ ] **Code signing** — Windows Authenticode certificate + macOS Developer ID notarization.
      Unsigned paid software gets SmartScreen/Gatekeeper blocks. → [Code signing & notarization guide](info/CODE_SIGNING_AND_NOTARIZATION.md).

### Correctness blockers (user-flagged, must fix before release)
- [x] **Deep anonymize must not clobber `SOPClassUID`** (or other standard/class UIDs). **FIXED 2026-06-14** — standard UIDs preserved, instance UIDs still remapped (with tests). → [bug investigation](bug-investigations/deep-anonymize-clobbers-sopclassuid.md).
- [x] **Validate nuclear TomographicContrast All-NaN** — **DONE 2026-06-14**: not a metric-corrupting bug; pylinac drops empty/fully-eroded frames before the reported metric (demo doesn't reproduce). Optional defensive NaN guard tracked as P2. → [PYLINAC_FLEXIBILITY_AND_WORKAROUNDS §7b](info/PYLINAC_FLEXIBILITY_AND_WORKAROUNDS.md).

---

## Tier 1 — Required for a credible launch

<a id="naming"></a>
- [ ] **Finalize the product name**, then do a string-consistency pass (window title, About box,
      installer, docs, metadata currently mix "DICOM Viewer V3" / "DICOMViewerV3").
      → naming exploration in [`FUTURE_WORK_DETAIL_NOTES.md`](FUTURE_WORK_DETAIL_NOTES.md#product-naming-exploration);
      consistency item B8 in [`TO_DO.md`](TO_DO.md). *Check trademark availability for the chosen name.* 🧑‍⚖️
- [ ] **Versioned release pipeline** producing **signed** installers (not raw exes) for Windows
      and macOS (Linux optional). → [Versioned release plan](plans/supporting/VERSIONED_RELEASE_PLAN.md),
      [`BUILDING_EXECUTABLES.md`](info/BUILDING_EXECUTABLES.md).
- [ ] **Generate & bundle `THIRD_PARTY_LICENSES.md`** in the release artifact (generator exists;
      run in release venv after dependency swaps). → [Compliance §3a/§5](plans/supporting/LICENSE_AND_COMPLIANCE_PLAN.md#3a-generate-sbom).
- [ ] **Privacy policy** stating no data leaves the machine; link from About. → [Compliance §4c](plans/supporting/LICENSE_AND_COMPLIANCE_PLAN.md#4c-privacy-policy).
- [ ] **About dialog**: product name, version, tier + license status, "Open-source licenses"
      button, intended-use statement, copyright. → [Tiers §3b](plans/supporting/PRODUCT_TIERS_AND_LICENSING_ENFORCEMENT_PLAN.md#3b-ui-affordances-no-dead-ends).
- [ ] **`pip-audit`** clean or each CVE dispositioned. → [Compliance §3c](plans/supporting/LICENSE_AND_COMPLIANCE_PLAN.md#3c-pip-audit-for-cves).
- [ ] **Release QA pass** on each target OS (open folder, view, export, MPR, 3D, fusion, pylinac,
      tag/ROI export, trial→paid unlock). → [Versioned release plan](plans/supporting/VERSIONED_RELEASE_PLAN.md); harness: [`HARNESS.md`](HARNESS.md).
- [ ] **Per-release procedure** followed (version bump, changelog, tag). → [`RELEASING.md`](RELEASING.md).

---

## Tier 2 — Recommended / fast-follow

- [ ] **Copyright registration** of the source (cheap; strengthens enforcement). → [Compliance §1c](plans/supporting/LICENSE_AND_COMPLIANCE_PLAN.md#1c-copyright-registration-optional-but-recommended-for-commercial-sale).
- [ ] **Product website / landing page** with purchase, pricing, and the non-diagnostic disclaimer.
- [ ] **Auto-update** mechanism (or a clear "new version available" check).
- [ ] **Support channel** (email/portal) + a user technical guide. → [`TO_DO.md` Release/Product](TO_DO.md).
- [ ] **Telemetry decision** — default off; if ever added, it changes the privacy policy.
- [ ] **Contributor IP / CLA** if anyone else has contributed code. 🧑‍⚖️
- [ ] **Launch announcement** (LinkedIn, communities).

---

## Recommended sequencing

The dependency that gates everything is the **GPL decoder swap** — start there because it can
silently break image loading for some modalities, and nothing ships until it's resolved.

1. **Now (unblock + decide):**
   - Decoder replacement spike (#1) + verify on real CT/MR/CR/DX/XA/US data.
   - Pick the **product name** (#11) and the **business/tier model** (#7) — both feed many later items.
   - Pick the **project license** (#4).
2. **Next (build the commercial spine):**
   - License-enforcement layer + signed-license + trial (#8).
   - Sales/delivery channel + EULA + privacy policy (#9, #6, #14).
   - Font + FFmpeg + Qt compliance cleanup (#2, #3, #5); regenerate SBOM (#13).
3. **Then (make it shippable):**
   - Code signing (#10) → signed-installer release pipeline (#12).
   - About dialog (#15), `pip-audit` (#16), cross-platform QA (#17).
4. **Launch**, then Tier 2 fast-follow.

---

## Owning-plan index

| Workstream | Plan |
|------------|------|
| Dependency & project licensing, EULA, SaMD, privacy | [`LICENSE_AND_COMPLIANCE_PLAN.md`](plans/supporting/LICENSE_AND_COMPLIANCE_PLAN.md) |
| Tiers, entitlements, license enforcement, sales channel | [`PRODUCT_TIERS_AND_LICENSING_ENFORCEMENT_PLAN.md`](plans/supporting/PRODUCT_TIERS_AND_LICENSING_ENFORCEMENT_PLAN.md) |
| Versioned executables & release pipeline | [`VERSIONED_RELEASE_PLAN.md`](plans/supporting/VERSIONED_RELEASE_PLAN.md) |
| Per-release version/changelog/tag procedure | [`RELEASING.md`](RELEASING.md) |
| Decoder replacement engineering detail | [`PYLIBJPEG_ALTERNATIVES_AND_DICOM_DECODER_STRATEGY.md`](info/PYLIBJPEG_ALTERNATIVES_AND_DICOM_DECODER_STRATEGY.md) |
| Code signing / notarization | [`CODE_SIGNING_AND_NOTARIZATION.md`](info/CODE_SIGNING_AND_NOTARIZATION.md) |
| Building executables | [`BUILDING_EXECUTABLES.md`](info/BUILDING_EXECUTABLES.md) |
| Dependency license policy & gate | [`DEPENDENCY_LICENSE_POLICY.md`](info/DEPENDENCY_LICENSE_POLICY.md) |

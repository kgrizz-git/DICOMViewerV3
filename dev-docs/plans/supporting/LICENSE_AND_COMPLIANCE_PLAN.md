# License & Library Compliance Plan

**Status:** Not started  
**Priority:** P0  
**TO_DO ref:** Release / Product — "Figure out license; also check which libraries are covered by which licenses and make sure we are compliant."

---

## Context: commercial sale intended

**The project may be sold commercially, possibly as a closed-source product (or a closed-source paid tier).** This is the dominant constraint for every decision below. Commercial distribution does not by itself trigger copyleft obligations — GPL does not prohibit charging money. What matters is **whether recipients receive the binary without corresponding source under GPL terms**, which is incompatible with closed-source distribution.

**This plan is not legal advice.** The decisions made here have real legal and financial consequences. Engage qualified IP counsel before distributing commercially — especially on the Qt LGPL relinking obligation, the `pylibjpeg-libjpeg` GPL question, and any medical device regulatory angle.

---

## Prior work

- **Dependency inventory:** `dev-docs/info/BUNDLED_PACKAGES_AND_FONTS_LICENSES.md` — detailed assessment (last updated 2026-04-17). Key problem components identified: `pylibjpeg-libjpeg` (GPL-3.0), PySide6 (LGPL-3.0), FFmpeg via `imageio-ffmpeg` (LGPL or GPL build-dependent), Liberation Sans font (GPL-2.0 + embedding exception). For the detailed decoder replacement assessment, see [`PYLIBJPEG_ALTERNATIVES_AND_DICOM_DECODER_STRATEGY.md`](../../info/PYLIBJPEG_ALTERNATIVES_AND_DICOM_DECODER_STRATEGY.md).
- **SemVer guide:** `dev-docs/info/SEMANTIC_VERSIONING_GUIDE.md`.
- **Releases guide:** `dev-docs/info/GITHUB_RELEASES_AND_VERSIONING.md`.

---

## Phase 0 — Blocking issues (must resolve before any commercial release)

These are **hard blockers** for closed-source commercial sale. Nothing else in this plan matters until these are resolved.

### 0a. `pylibjpeg-libjpeg` — GPL-3.0 JPEG decoder (BLOCKING)

`pylibjpeg-libjpeg` is **GPL-3.0**. Distributing a closed-source binary that links or bundles GPL-3.0 code without providing corresponding source under GPL terms is a license violation. This is the single most critical item.

Detailed engineering assessment: [`PYLIBJPEG_ALTERNATIVES_AND_DICOM_DECODER_STRATEGY.md`](../../info/PYLIBJPEG_ALTERNATIVES_AND_DICOM_DECODER_STRATEGY.md).

**What it covers:** DICOM transfer syntaxes JPEG Baseline (`1.2.840.10008.1.2.4.50`) and JPEG Extended (`1.2.840.10008.1.2.4.51`). These are most common in CR, DX, and older XA/US. CT and MR are usually uncompressed or JPEG-LS/JPEG 2000 — already covered by `pyjpegls` and `pylibjpeg-openjpeg` (both MIT).

**Options — pick one:**

| Option | License | Effort | Notes |
|--------|---------|--------|-------|
| **A. Pillow-only JPEG decode** | MIT-CMU | Low | Already in stack. pydicom uses Pillow for JPEG Baseline in many cases. Pillow bundles libjpeg/libjpeg-turbo internally — both permissively licensed (IJG/BSD). Test coverage on your actual dataset mix first. **Best starting point.** |
| **B. GDCM via `python-gdcm`** | LGPL-2.0 | Medium | Broad DICOM decompression including JPEG Baseline, Extended, and others. Commercially viable under LGPL (same compliance path as Qt). Verify wheel availability on Windows/macOS/Linux for target Python versions. |
| **C. PyTurboJPEG / `libjpeg-turbo`** | MIT + BSD | High | libjpeg-turbo is BSD-licensed. Not wired into pydicom's decode pipeline today — needs a custom decoder plugin. Best coverage but most integration work. |
| **D. Remove; warn user on failure** | N/A | Low | Users who need it install `pylibjpeg-libjpeg` themselves (GPL becomes theirs). Acceptable if your target market is primarily CT/MR and coverage gaps affect only older CR/DX files. |
| **E. Keep GPL; release app source under GPL-3.0** | GPL-3.0 | Low | Forces the app to be open-source. Commercial sale is still permitted (GPL allows selling) but customers can redistribute source freely — undermines most proprietary models. |

**Recommendation:** Try **Option A** (Pillow-only) first — zero effort. If Pillow coverage on your real data is adequate (likely for CT/MR-focused workflows), just drop `pylibjpeg-libjpeg`. If gaps remain on CR/DX files, move to **Option B** (GDCM, LGPL).

- [ ] **Action:** Test Pillow-only JPEG decode coverage on representative datasets (CT, MR, CR, XA, US). Log which transfer syntaxes fail and with what error.
- [ ] **Action:** Remove `pylibjpeg-libjpeg` from `requirements.txt` in a test branch; run full test suite and manual smoke test.
- [ ] **Decision:** Document the chosen option in `dev-docs/info/BUNDLED_PACKAGES_AND_FONTS_LICENSES.md` with rationale.

### 0b. FFmpeg via `imageio-ffmpeg` — likely LGPL-only, but verify (VERIFY BEFORE TREATING AS BLOCKER)

`imageio-ffmpeg` ships a pre-built FFmpeg binary. **Their documentation states this is an LGPL-only build** — built without GPL components (no libx264, libx265, etc.). If accurate, this is **not a blocker**: LGPL is compatible with closed-source commercial distribution under the same compliance path as Qt (notices + relinking opportunity).

**Verify first before any engineering work:**
- [ ] Check `imageio-ffmpeg`'s GitHub README and the wheel's `.dist-info/METADATA` License field to confirm the LGPL-only claim for the version pinned in `requirements.txt`.
- [ ] Run: `pip show -f imageio-ffmpeg` and inspect the bundled binary's accompanying license text if any.

**If confirmed LGPL-only:** No blocker. Add FFmpeg LGPL notice to `THIRD_PARTY_LICENSES.md` and comply as with Qt (see Phase 2b). No engineering change needed.

**If it turns out to be GPL:** Replace with one of the following:

| Alternative | License | What you lose | Notes |
|-------------|---------|---------------|-------|
| **Pillow animated GIF only** | MIT-CMU | AVI/MP4/MPG. GIF is limited (256 colors, large file size) | `imageio` (BSD) can write GIFs via Pillow with no FFmpeg; drop `imageio-ffmpeg` entirely |
| **OpenCV `cv2.VideoWriter`** | Apache 2.0 | Nothing obvious | OpenCV is likely already a transitive dep via pylinac→scikit-image; can write AVI with platform codecs |
| **Multi-frame DICOM export** | N/A | Video portability | Export cine as a DICOM multi-frame object — any DICOM viewer plays it; lossless; arguably more appropriate for a medical app |
| **LGPL-only FFmpeg build (custom)** | LGPL | Build complexity | Bundle your own FFmpeg binary built without GPL codecs; drop `imageio-ffmpeg` |

**Recommendation:** Check the license first — this is likely already fine. If it is GPL, use **Pillow GIF + OpenCV AVI** as the replacement (both already available as transitive deps).

---

## Phase 1 — Choose your business model and project license

### 1a. Business model decision

The choice of project license is downstream of the business model. Common models for a DICOM viewer:

| Model | Description | Recommended project license |
|-------|-------------|------------------------------|
| **Proprietary closed-source** | Sell compiled binaries; source is not public | Proprietary (All Rights Reserved) — requires resolving all GPL deps |
| **Dual license: Open + Commercial** | Free open-source edition (GPL or AGPL) + paid commercial license for closed-source users | GPL-3.0 for open tier; custom commercial license for paid tier |
| **Open-source with paid support / hosting** | Code is public (MIT or Apache); revenue from support, cloud, or SaaS features | MIT or Apache-2.0 — but competitors can fork |
| **Freemium: free core + paid features** | Core viewer free (MIT/Apache); advanced features (e.g. deep anonymize, QA, 3D) in a paid closed-source plugin | MIT for core; proprietary for paid module — complex boundary |

**For a sold app with a proprietary component, the most defensible models are:**
1. **Proprietary closed-source** — requires removing all GPL deps (Phase 0 must be fully resolved).
2. **Dual license** — GPL open edition coexists with a commercial license you sell to customers who don't want GPL terms. Common model (MySQL, Qt itself, etc.). GitHub repo stays open but you also collect license fees.

- [ ] **Decision:** Which model? Document in `dev-docs/info/COMMERCIAL_LICENSE_MODEL.md` (new file).

> **Leaning (2026-06-13):** freemium — **free basic + full trial + paid full** tiers. The
> product packaging, feature split, and in-app enforcement (single build + entitlements +
> offline signed license file) are specified in
> [`PRODUCT_TIERS_AND_LICENSING_ENFORCEMENT_PLAN.md`](PRODUCT_TIERS_AND_LICENSING_ENFORCEMENT_PLAN.md).
> This still requires the **proprietary closed-source** path, so **Phase 0 GPL blockers
> remain hard prerequisites**.

### 1b. Project license file

- [ ] If **proprietary:** Add a `LICENSE` file stating "All Rights Reserved. No license is granted to use, copy, modify, or distribute this software without a written commercial license agreement." Do **not** choose an OSI license.
- [ ] If **dual license (GPL + commercial):** Add `LICENSE` with GPL-3.0 text; add `LICENSE-COMMERCIAL.md` describing the commercial license terms (or link to where customers purchase it).
- [ ] If **MIT/Apache (open):** Add `LICENSE` with chosen text.
- [ ] Register copyright explicitly: "Copyright © [Year] [Your Name / Company Name]. All rights reserved."

### 1c. Copyright registration (optional but recommended for commercial sale)

- [ ] Consider registering copyright with the US Copyright Office (relatively cheap, strengthens enforcement).
- [ ] Use a consistent copyright header in key source files.

---

## Phase 2 — Qt / PySide6 LGPL compliance for commercial distribution

PySide6 is **LGPL-3.0**. This license is compatible with closed-source commercial distribution if you meet its terms. It does **not** require you to open-source your app. However, it imposes relinking obligations:

> "You may convey a Combined Work under terms of your choice that, taken together, effectively do not restrict modification of the private portions and reverse engineering for debugging such modifications, if you also do each of the following: ... Provide ... the Minimal Corresponding Source ... and a copy of the written offer ... to provide ... object code and/or source code."

In practice for a PyInstaller desktop app this means:

- [ ] Include LGPL-3.0 license text and Qt copyright notices in the distribution.
- [ ] Allow users to relink the app against a different version of Qt. Two common ways:
  - **Provide object files** so a sophisticated user could relink your app against their own Qt build.
  - **Provide source** for the parts of your app that interface with Qt (not necessarily all of your proprietary code — just the Qt-interfacing layer). Counsel can advise on the minimum.
- [ ] Include an explicit written notice in the installer/About dialog that the app uses Qt under LGPL-3.0 and that users may replace the Qt libraries.

**Alternative: Qt Commercial License**
- Qt Company sells commercial licenses that remove the LGPL relinking obligation entirely.
- Pricing is significant (indie license as of 2025: ~$500–700/month, billed annually).
- Worth evaluating if the relinking obligation is operationally painful or if the legal risk of LGPL non-compliance concerns you.
- [ ] **Decision:** LGPL compliance path vs. Qt Commercial License. Document in `COMMERCIAL_LICENSE_MODEL.md`.

---

## Phase 3 — Dependency compliance audit

### 3a. Generate SBOM

- [x] **Generator tooling added.** `scripts/generate_third_party_licenses.py` (wraps `pip-licenses`, a dev dependency in `requirements-dev.txt`) produces `THIRD_PARTY_LICENSES.md`. Run `python scripts/generate_third_party_licenses.py --release [--with-texts]` in the release venv. The output file is git-ignored (regenerated at packaging time). See `dev-docs/info/DEPENDENCY_LICENSE_POLICY.md`.
- [ ] In the **release** venv (after Phase 0 changes), generate the final SBOM and verify contents.
- [ ] Check transitive deps via `pip freeze` — not just direct pins.
- [ ] Flag any **GPL / LGPL / MPL / EUPL** hits for review. After Phase 0, the only remaining copyleft should be LGPL (PySide6, possibly FFmpeg).

### 3b. Per-component checklist (post Phase 0)

- [ ] **MIT / BSD / Apache / SIL OFL deps:** Include license text in `THIRD_PARTY_LICENSES.md`. Attribution in About dialog satisfies most.
- [ ] **LGPL-3.0 (PySide6):** See Phase 2 above.
- [ ] **LGPL FFmpeg (if confirmed):** Include license text; provide notice; include source offer or configure flags from the build.
- [ ] **Liberation Sans (GPL-2.0 + embedding exception):** The embedding exception was written for documents (PDFs, Office files); its applicability to a PyInstaller frozen app bundle is legally ambiguous. Easiest fix is to replace it entirely with an SIL OFL 1.1 font — OFL explicitly permits bundling in applications with zero commercial ambiguity. Drop-in replacements with very similar metrics: **Noto Sans** (Google, SIL OFL 1.1 — best Unicode coverage), **Source Sans 3** (Adobe, SIL OFL 1.1 — visually closest), **Inter** (SIL OFL 1.1 — clean modern UI font). Also acceptable: **Roboto** (Apache 2.0). Check `resources/fonts/` — other bundled fonts may already be OFL.
- [ ] **`sqlcipher3` / SQLCipher:** SQLCipher itself is BSD-style — verify the wheel METADATA confirms this for the exact version in use.
- [ ] **`pylinac`:** MIT. Check that pylinac's own transitive deps (scikit-image, scipy, etc.) don't introduce any copyleft surprises.

### 3c. `pip-audit` for CVEs

- [ ] Run `pip-audit` against the release venv.
- [ ] Document any CVEs and disposition (accepted risk, mitigated, patched).

---

## Phase 4 — Commercial and legal artifacts

### 4a. EULA (End User License Agreement)

- [ ] Draft an EULA covering:
  - Grant of license (what the user may do with the purchased binary).
  - Restrictions (no reverse engineering, no redistribution without permission, no sublicensing).
  - Disclaimer of warranty and limitation of liability (critical for a DICOM tool — see 4b).
  - Governing law and jurisdiction.
- [ ] EULA must be presented and accepted at install time.
- [ ] Retain accepted EULA records if distributing digitally (e.g. via a portal).

### 4b. Medical use disclaimer (critical)

A DICOM viewer sold commercially may be considered a **Software as a Medical Device (SaMD)** under FDA (US) or MDR (EU) regulations, depending on its **intended use**. If it is marketed for clinical diagnosis or treatment planning, regulatory clearance (FDA 510(k) or EU CE mark) may be required. If it is marketed as **for research / educational / workflow use only**, that distinction must be explicit and consistently maintained.

- [x] **Decision (2026-06-13):** Position as **not for diagnostic use** — avoids FDA/CE SaMD classification. Use intended-use language such as: "For research, educational, and workflow use only. Not intended for clinical diagnosis or treatment. Images must be interpreted by qualified professionals using cleared diagnostic devices." Applies to **all tiers** (free/trial/paid). Marketing must not claim or imply diagnostic use. Options not chosen:
  - "For research and educational purposes only. Not intended for clinical diagnosis or treatment."
  - Pursue FDA/CE clearance (significant investment; out of scope for this plan — flag immediately if the sales pitch ever includes clinical/diagnostic use).
- [ ] Add the intended use statement to:
  - EULA (prominent, above the fold).
  - README and product website.
  - Help → About dialog in the app.
  - Any marketing materials.
- [ ] **Seek counsel** if there is any ambiguity about whether the intended use triggers SaMD classification.

### 4c. Privacy policy

The study index stores patient names, IDs, study dates, and modalities locally. If any version of the product transmits data (even telemetry or analytics) or is used in a jurisdiction with privacy law (HIPAA in the US, GDPR in the EU), a privacy policy is required.

- [ ] Confirm the app does not transmit any data to external servers (current understanding: it does not).
- [ ] Draft a minimal privacy policy stating no data leaves the local machine, what is stored (study index), and how to delete it.
- [ ] Post on the product website; link from the app's About dialog.

---

## Phase 5 — Attribution artifacts in distribution

- [ ] **`LICENSE`** — project license (Phase 1b).
- [ ] **`THIRD_PARTY_LICENSES.md`** — generated SBOM with license texts.
- [ ] **`EULA.txt`** or presented at install time (Phase 4a).
- [ ] **Help → About dialog:** Copyright notice, version, "Open Source Licenses" button, intended use statement.
- [ ] **PyInstaller bundle:** Ensure `LICENSE`, `THIRD_PARTY_LICENSES.md`, font license files are in `datas` in `DICOMViewerV3.spec`.
- [ ] **Installer** (when built): Present EULA for acceptance; display attributions.

---

## Phase 6 — Ongoing maintenance

- [x] **Dependency license gate implemented.** `scripts/check_dependency_licenses.py` (zero-dependency, stdlib only — no `pip-licenses` needed) classifies every installed dist and **fails** on a new strong-copyleft (GPL/AGPL) dependency unless it is in the policy's `accepted_exceptions`. Wired into `.githooks/pre-commit`. Policy: `dev-docs/info/dependency_license_policy.json`. Docs: `dev-docs/info/DEPENDENCY_LICENSE_POLICY.md`. (`pylibjpeg-libjpeg` is currently an accepted exception pending Phase 0a.)
- [ ] Add the same check as a CI step (run `python scripts/check_dependency_licenses.py` in the release venv) so PRs and release builds are also gated.
- [ ] Document in `dev-docs/CONTRIBUTING.md` that any new dependency must be reviewed for license before merging.
- [ ] Update `BUNDLED_PACKAGES_AND_FONTS_LICENSES.md` "Last updated" and basis version on each release.
- [ ] Re-run `pip-audit` for CVEs before each release.

---

## Decision summary (fill in as you decide)

| Item | Decision | Date |
|------|----------|------|
| Business model | | |
| `pylibjpeg-libjpeg` resolution | | |
| FFmpeg license (LGPL or GPL) | | |
| Qt: LGPL compliance vs commercial license | | |
| Liberation Sans: keep (verify exception) or replace with OFL font | | |
| Intended use claim (SaMD classification) | **Not for diagnostic use** (research/education/workflow; avoids FDA/CE SaMD) — all tiers | 2026-06-13 |
| Copyright holder (name / entity) | | |

---

## Open questions requiring counsel

1. **LGPL relinking obligation (Qt):** What is the minimum you must provide for a PyInstaller-frozen app? Object files? Source of Qt-interfacing layers? This is jurisdiction- and fact-specific.
2. **`pylibjpeg-libjpeg` GPL — Pillow-only alternative:** If some DICOM files fail to decode, is that an acceptable product limitation or does it affect your target market too much?
3. **SaMD classification:** Is a commercially sold DICOM viewer for general "workflow" use a medical device under FDA/MDR? What intended-use language avoids triggering clearance requirements?
4. **Copyright registration:** Worth filing before public commercial launch.
5. **Contributor IP:** If anyone else has contributed code (pull requests, etc.), do you have their IP or do you need a CLA to relicense?

---

## Files likely touched

| File | Change |
|------|--------|
| `LICENSE` | **New** — project license text |
| `THIRD_PARTY_LICENSES.md` | **New** — generated SBOM |
| `EULA.txt` | **New** — end user license agreement |
| `dev-docs/info/COMMERCIAL_LICENSE_MODEL.md` | **New** — business model and license decision record |
| `requirements.txt` | Remove `pylibjpeg-libjpeg` (if Option A/B chosen) |
| `DICOMViewerV3.spec` | Add LICENSE and THIRD_PARTY_LICENSES to `datas` |
| `src/gui/dialogs/about_dialog.py` (or equivalent) | Copyright, licenses button, intended use statement |
| `dev-docs/info/BUNDLED_PACKAGES_AND_FONTS_LICENSES.md` | Update basis version and decisions |
| `README.md` | License / intended use section |
| `.github/workflows/` | CI step: fail on new GPL dep |

# Decoder Replacement Spike Plan (`pylibjpeg-libjpeg` GPL removal)

**Status:** Spike complete — GDCM selected; productionization and frozen-build verification pending
**Last updated:** 2026-07-29
**Priority:** P0 — Tier 0 hard blocker for commercial release
**TO_DO ref:** Release / Product → [Commercial Release Readiness](../../COMMERCIAL_RELEASE_READINESS.md) item #1

> **Goal.** Remove the GPL-3.0 `pylibjpeg-libjpeg` dependency from the commercial build and
> **prove** the replacement decodes representative real DICOM data, with no silent pixel
> corruption. Output a go/no-go decision (Pillow-only vs GDCM) backed by data.
>
> **This plan operationalizes** the strategy/option analysis in
> [`PYLIBJPEG_ALTERNATIVES_AND_DICOM_DECODER_STRATEGY.md`](../../info/PYLIBJPEG_ALTERNATIVES_AND_DICOM_DECODER_STRATEGY.md)
> (the option matrix A–F). Read that for the *why*; this is the *what to do, in order*.
> Legal context: [`LICENSE_AND_COMPLIANCE_PLAN.md` §0a](LICENSE_AND_COMPLIANCE_PLAN.md#0a-pylibjpeg-libjpeg-replacement--gdcm-productionization-blocking).

---

## Why this is the first blocker to tackle

- It gates the entire commercial path (can't ship closed-source with a GPL dep).
- Unlike most blockers it has a **silent-failure mode**: a worse decoder can produce *wrong
  pixels* rather than an obvious error — unacceptable for a viewer. So the spike is
  measurement-first: establish a golden reference, then diff every candidate against it.

## Current state (grounding)

- **Production update (2026-07-29)** — `python-gdcm==3.2.6` replaces `pylibjpeg-libjpeg` in
  `requirements.txt`; the retained plugins cover JPEG 2000, JPEG-LS, and RLE. The GPL decoder's
  accepted-exception entry was removed from the dependency-license policy.
- **Decode entry point** — `src/core/dicom_pixel_array.py` `get_pixel_array()` → `dataset.pixel_array`;
  failures classified by `_classify_pixel_array_error()` (L31).
- **Messaging update (2026-07-29)** — `core.decoder_capabilities` provides transfer-syntax and
  installed-handler information; pixel/loader failures use it without raw native text or
  package-install advice.

## Transfer syntaxes `pylibjpeg-libjpeg` currently covers (the at-risk set)
- `1.2.840.10008.1.2.4.50` JPEG Baseline 8-bit
- `1.2.840.10008.1.2.4.51` JPEG Extended 12-bit
- `1.2.840.10008.1.2.4.57` JPEG Lossless (process 14)
- `1.2.840.10008.1.2.4.70` JPEG Lossless (first-order prediction)

JPEG2000 / JPEG-LS / RLE / uncompressed are covered by **other** plugins and must be
**regression-controlled** (prove we didn't break them).

---

## Phase 0 — Setup & test corpus

- [ ] Create spike branch `spike/no-pylibjpeg-libjpeg`.
- [ ] **Inventory existing fixtures** under `test-DICOM-data/` and `tests/fixtures/` — record
      which transfer syntaxes are already represented.
- [ ] **Fill corpus gaps** with small, **non-PHI** samples covering each at-risk syntax plus
      controls (see [strategy doc "Test corpus needed"](../../info/PYLIBJPEG_ALTERNATIVES_AND_DICOM_DECODER_STRATEGY.md#test-corpus-needed)):
      JPEG Baseline mono, JPEG Baseline color (YBR + RGB), JPEG Extended 12-bit, JPEG Lossless
      .57, JPEG Lossless .70, **controls:** JPEG-LS, JPEG2000, RLE, uncompressed.
      Source from public test sets (pydicom test data, GDCM data) or synthesize; document provenance.
- [ ] Write a **corpus harness script** `scripts/decoder_corpus_report.py` that, for every
      sample, records the data-capture schema below to CSV/JSON. Must run headless (no GUI),
      reusing `core.dicom_pixel_array.get_pixel_array` so it tests the *real* path.

**Data-capture schema (per sample):** file, transfer syntax UID, modality, samples/pixel,
photometric interpretation, bits allocated/stored, planar config, **decoder backend used**,
success/fail, **pixel array SHA-256** (or tolerance metric), decode time, visual-smoke note.

## Phase 1 — Golden reference (baseline WITH current decoders)
- [ ] Run `decoder_corpus_report.py` in the **current** environment (pylibjpeg-libjpeg present).
- [ ] Save output as the **golden reference** (`decoder_baseline_<date>.json`). This is the
      "correct" pixel hash set every candidate is judged against.

## Phase 2 — Option A: Pillow-only
- [ ] In the spike venv, **uninstall only `pylibjpeg-libjpeg`** (keep openjpeg/rle/pyjpegls/Pillow).
- [ ] Confirm pydicom's `pillow` decoder plugin is active.
- [ ] Re-run the corpus harness; diff against golden:
      - **Lossless syntaxes (.57/.70, RLE, uncompressed): pixel hash MUST match exactly.**
      - **Lossy (Baseline/Extended): within tolerance** (define ε; visually verify, check W/L
        and ROI-stat stability on a sample — quantitative workflows can't tolerate drift).
      - Record every syntax that now **fails** to decode.
- [ ] Run the existing pytest suite + manual app smoke (open folder, view, ROI, export) on the
      spike branch.

## Phase 3 — Decision Gate A
- [ ] **Decision:** Is Pillow-only acceptable for the commercial/default profile?
  - **Yes** (CT/MR-focused coverage holds; gaps only on rare older CR/DX and handled gracefully)
    → go to Phase 6 with Option A.
  - **No** (important Baseline/Extended/Lossless data fails or drifts) → Phase 4 (GDCM).
- [ ] Record the decision + evidence in the strategy doc and the readiness gate (#1).

## Phase 4 — Option C: GDCM (`python-gdcm`) — only if Gate A = No
- [ ] Spike `python-gdcm` install on Win/macOS/Linux for target Python (3.11/3.12); confirm
      wheel availability (packaging is the usual blocker, not code).
- [ ] Confirm pydicom selects the `gdcm` plugin for the target syntaxes; re-run corpus + diff.
- [ ] **Validate frozen-build discovery** of GDCM native libs via PyInstaller (`DICOMViewerV3.spec`)
      — decode from a built executable, not just the venv. Record bundle-size delta.
- [ ] Review the exact GDCM wheel/native-library notices in each release asset with the compliance plan.

## Phase 5 — Decision Gate B (only if Phase 4 ran)
- [ ] **Decision:** GDCM acceptable (coverage + frozen build + license)? If yes → Phase 6 with
      Option C. If no → escalate: PyTurboJPEG custom plugin (Option D, separate plan) or a
      reduced-coverage profile (Option B) — **do not** start D without explicit sign-off.

## Phase 6 — Productionize the chosen path
- [x] **`requirements.txt`** — remove `pylibjpeg-libjpeg`; add `python-gdcm` for Option C.
      **Done 2026-07-29:** pinned `python-gdcm==3.2.6` is the selected dependency.
- [x] **Capability-detection module** — a focused helper mapping transfer-syntax UID → installed
      decoder support + a clear user message (per strategy "Implementation guardrails": don't
      scatter `pylibjpeg` string checks; don't drive control flow off import errors). **Done
      2026-07-29:** `core.decoder_capabilities` is the single runtime capability source.
- [x] **Fix messaging** — stop recommending the GPL `pip install pylibjpeg`; show a
      profile-aware unsupported-transfer-syntax message naming the syntax. **Done 2026-07-29.**
- [ ] **Log decoder backend/version** in debug diagnostics + About/System Info (provenance —
      compressed input can affect numerical results in QA/export).
- [ ] **Remove the license-gate exception** for `pylibjpeg-libjpeg` from
      `dev-docs/info/dependency_license_policy.json`; re-run `scripts/check_dependency_licenses.py`
      in the release venv → must pass with **no** GPL exception.

## Phase 7 — Verification & docs
- [ ] Add a regression test that asserts the corpus decodes (lossless hashes exact) using the
      committed fixtures — guards against future decoder regressions.
- [ ] Full pytest + cross-platform manual smoke (incl. a **frozen build** decode check).
- [ ] Update [strategy doc](../../info/PYLIBJPEG_ALTERNATIVES_AND_DICOM_DECODER_STRATEGY.md)
      "Proposed next steps" with the outcome; check off readiness gate **#1** and compliance **§0a**.
- [ ] Update `BUNDLED_PACKAGES_AND_FONTS_LICENSES.md` to reflect the new decoder set.

---

## Acceptance criteria (definition of done)
1. Commercial build contains **no GPL/AGPL** dependency; license gate passes with no
   `pylibjpeg-libjpeg` exception.
2. **Lossless** transfer syntaxes decode **bit-exact** vs the golden reference.
3. **Lossy** syntaxes decode within defined tolerance, visually verified, with stable W/L and
   ROI statistics on sample data.
4. Any unsupported syntax produces a **clear, non-crashing** message naming the syntax — never
   a recommendation to install a GPL component in the commercial profile.
5. Decode works from a **frozen/packaged executable**, not just a dev venv.
6. Decoder backend is logged for provenance.
7. A committed regression test exercises the corpus.

## Risks & guardrails
- **Silent pixel corruption** is the top risk → hash-diff against golden, exact for lossless.
- **Frozen-build native-lib discovery** (esp. GDCM) often fails where the venv succeeds → test
  the packaged exe explicitly (Phase 4/7).
- **Color/photometric (YBR↔RGB) differences** between decoders → include color samples in corpus.
- **Coverage perceived as regression** by CR/DX/XA/US users → if Option A drops coverage, pair
  with excellent messaging and document the limitation before launch.

## Files likely touched
| File | Change |
|------|--------|
| `requirements.txt` | Remove `pylibjpeg-libjpeg`; maybe add `python-gdcm` |
| `scripts/decoder_corpus_report.py` | **New** — corpus harness |
| `src/core/dicom_pixel_array.py` | Profile-aware messaging (L149-150); backend logging; classifier tweak |
| `src/core/` decoder-capability helper | **New** — UID→support mapping + messages |
| `dev-docs/info/dependency_license_policy.json` | Remove GPL exception |
| `tests/` | Corpus regression test + fixtures |
| `DICOMViewerV3.spec` | GDCM native libs in `datas`/`binaries` (if Option C) |
| strategy doc, `BUNDLED_PACKAGES_AND_FONTS_LICENSES.md`, readiness gate | Record outcome |

## Results log

### 2026-06-13 — Phases 0–3 (Pillow-only)
- **Harness:** `scripts/decoder_corpus_report.py` (committed on `spike/no-pylibjpeg-libjpeg`).
- **Env:** pydicom 2.4.5, Pillow 12.2.0, pylibjpeg 2.1.0 + openjpeg 2.5.0 + rle 2.2.0,
  pyjpegls 1.5.1, numpy 2.4.5. (GDCM not installed.)
- **Corpus (38 files, git-ignored under `decoder-spike-artifacts/`):**
  - `pydicom/` — bundled **non-PHI** samples: `.50`×3, `.51`×2, `.70`×2, `.80`×1, `.90`×3,
    `.91`×3, RLE×3, ExplicitLE×3, ImplicitLE×3.
  - `real-tests/` — real samples from the external "Tests" folder: `.50`×2, `.70`×1,
    `.99` Deflated×2, `.2` Big-Endian×1, `.80`×1, `.90`×2, RLE×2, uncompressed×4.
  - **Gaps — CLOSED 2026-06-14** (see entry below): `.57` generated with GDCM; `.81` downloaded.
- **Golden baseline** captured with `pylibjpeg-libjpeg` present (`golden_baseline.json`). A few
  files fail even here (a non-conformant JP2-header `.91`, a tricky `.51`, a no-pixel file) —
  pre-existing, so they cannot produce false regressions.
- **Pillow-only run** (separate `.venv-spike`, same versions minus `pylibjpeg-libjpeg`),
  diffed vs golden:
  - **Hash mismatches: 0** → no silent pixel corruption; Pillow output is bit-exact where it works.
  - **New failures: 4** → `.50` `SC_jpeg_no_color_transform` (edge case), `.51` JPEG Extended
    12-bit, `.70` JPEG Lossless RGB (×2). **Lost coverage: JPEG Lossless (.57/.70), JPEG
    Extended 12-bit (.51), one JPEG Baseline edge case.** All other syntaxes unaffected & bit-exact.
- **Real-world prevalence (header-only scans):** CR/DX/XA almost entirely uncompressed +
  a little `.50` + one `.91`; the only real `.70` seen was a single OT file. JPEG Lossless/
  Extended appear **rare** in the sampled real data (big MR/CT/PT/Fusion folders not yet scanned).

### 2026-06-13 — Phase 4 (GDCM, `python-gdcm` 3.2.6)
Second spike venv (`.venv-gdcm`, same stack minus `pylibjpeg-libjpeg`, plus `python-gdcm`),
same `--baseline` diff:
- **New failures: 0** → GDCM recovers all coverage Pillow lost (`.50` 5/5, `.51` 2/2,
  `.70` 2/3 — the 1 fail also failed in the golden run, so not a regression).
- **Hash mismatches: 2** — both **lossy** synthetic fixtures, characterized by direct array diff:
  - `.51` `JPGExtended` (12-bit extended): **max abs diff = 1 LSB**, 1.4% of pixels, mean 0.01 →
    rounding noise, negligible.
  - `.50` `SC_jpeg_no_color_transform`: max diff 137, 100% pixels → **YBR↔RGB color-space
    interpretation** difference (file has no APP14 color-transform marker; a synthetic fixture
    built to expose exactly this). **Real** color baseline files (XA/OT `.50`) matched GDCM
    **bit-exact** — the diff is confined to this pathological synthetic case.

### 2026-06-14 — Corpus completed (`.57` + `.81` gaps closed), results reconfirmed
- **`.57`** (JPEG Lossless Process 14, non-SV1 — at-risk): **generated** from pydicom's
  uncompressed `CT_small.dcm` via GDCM (`scripts/generate_decoder_fixtures.py`, new). The GPL
  decoder decodes it in the golden run; GDCM decodes it **bit-exact** (not in mismatch list).
- **`.81`** (JPEG-LS near-lossless — a *control*; JPEG-LS is handled by `pyjpegls`, not libjpeg):
  **downloaded** `JLSN_RGB_ILV0.dcm` from the `pydicom-data` repo and verified. (Could not
  *generate* `.81`: this `python-gdcm` build doesn't expose the JPEG-LS NEAR setting through
  `ImageChangeTransferSyntax`.)
- Also downloaded extra real lossless-JPEG samples (`JPEG-LL.dcm`, `JPGLosslessP14SV1…` — both
  `.70`; `JLSL_16_15…` — `.80`) into `downloaded/`.
- **Corpus now 42 files.** Golden baseline rebuilt; both candidate diffs re-run:
  - **Pillow-only: 0 hash mismatches, 7 new failures** — now includes the new `.57` and both
    extra `.70`s. Confirms Pillow drops the **entire JPEG-Lossless family (`.57` + `.70`)** plus
    `.51` and the `.50` no-color-transform edge.
  - **GDCM: 0 new failures, 2 hash mismatches** (unchanged: `.50` no-color-transform colorspace,
    `.51` ±1 LSB). GDCM decodes the new `.57` bit-exact — its lossless path round-trips correctly.
- **Reusable capability:** `scripts/generate_decoder_fixtures.py` transcodes an uncompressed
  source to any GDCM-supported syntax keyword (`jpeg_baseline`, `jpeg_extended`,
  `jpeg_lossless_p14` = `.57`, `jpeg_lossless_sv1` = `.70`, `jpegls_lossless`, `jpeg2000*`, `rle`).
  Requires `python-gdcm` (tooling-only, not an app dependency).

### 2026-07-29 — Independent color decision and reproducible synthetic matrix
- **Independent tools:** DCMTK 3.7.0 and dcm4che 5.34.3 ran from isolated local validation
  environments; neither is a runtime candidate. Both decompressed the wholly synthetic marker-less
  RGB `.50` fixture to the exact GDCM raw-pixel hash under the application's pydicom 2.4.5 line.
  The former GPL decoder produced a different hash.
- **Valid `.51` fixture:** libjpeg-turbo 3.2.0 `cjpeg -precision 12` generated a valid 12-bit
  JPEG Extended SOF1 frame independently of GDCM. GDCM, DCMTK, and dcm4che agree exactly; the
  former GPL output differs by at most two values (285/3072 pixels; mean absolute difference
  0.099609).
- **Compatibility:** `python-gdcm` 3.2.6 registered with pydicom 2.4.5 and decoded the synthetic
  matrix in isolated CPython 3.11.15 and 3.12.10 macOS/arm64 environments. Frozen Windows/Linux
  builds remain unverified.
- **Open production criterion:** expected `.51` decode currently emits a native diagnostic despite
  returning the independently confirmed pixels. Resolve or safely suppress it before shipment.
- **Fixture admission:** human visual review and reviewed-asset hashes for the expanded grayscale
  matrix were completed on 2026-07-29.

### Decision Gate A/B — recommendation: **GDCM (Option C)**
| | Pillow-only | **GDCM** |
|---|---|---|
| Coverage (failures vs golden) | 4 fail (`.50` edge, `.51`, `.70`×2) | **0 fail** |
| Lossless bit-exact | yes (where decoded) | **yes** |
| Lossy diff vs GPL ref | none (refuses) | `.51` ±1 LSB; `.50` no-color-transform color-space (synthetic only) |
| License | MIT | `python-gdcm` wheel metadata declares Apache-2.0; release native assets need notice review |
| Frozen-build risk | low (Pillow already bundled) | **native libs need PyInstaller validation + bundle-size cost** |

GDCM eliminates the coverage regression; the selected wheel's package metadata declares
Apache-2.0, while its collected native assets remain subject to final notice review.
**Recommended path: replace `pylibjpeg-libjpeg` with `python-gdcm`.** This is a single
replacement for the GPL classic-JPEG plugin; retain the existing Pillow fallback and the
separate JPEG 2000, JPEG-LS, and RLE plugins. Remaining before finalizing (Phases 4/6/7):
- [x] Validate the no-color-transform `.50` behavior — DCMTK and dcm4che independently match
      GDCM's raw RGB output for a wholly synthetic marker-less RGB fixture; the former GPL result
      differs. **Done 2026-07-29;** details and the remaining production work are in the
      [GDCM productionization plan](GDCM_DECODER_PRODUCTIONIZATION_PLAN.md).
- [ ] **Frozen-build check** — confirm GDCM native libs load from a PyInstaller build (not just venv); record bundle-size delta.
- [x] Source `.57` (JPEG Lossless process 14) and `.81` (JPEG-LS near-lossless) fixtures to close corpus gaps — completed 2026-06-14.
- [x] Phase 6 dependency swap, capability messaging, and license-gate exception removal. **Done
      2026-07-29;** frozen-executable validation and provenance UI remain in the production plan.

---

## Deferred follow-up items (tracked; not blocking the GDCM decision)

These came out of the 2026-06-13 spike and should be done before final productionization /
release, but do not change the recommendation (GDCM):

1. **Frozen-build validation (highest priority of these).** Confirm `python-gdcm` native libs
   load from a PyInstaller build (`DICOMViewerV3.spec`), decoding the corpus from the packaged
   exe — not just the venv. Record bundle-size delta. This is the one open item that could still
   change the decision.
2. ~~**`.57` and `.81` corpus fixtures.**~~ **DONE 2026-06-14** — `.57` generated via GDCM
   (`scripts/generate_decoder_fixtures.py`), `.81` downloaded from `pydicom-data`. Both verified
   and in the 42-file corpus.
3. ~~**No-color-transform `.50` investigation.**~~ **DONE 2026-07-29.** A wholly synthetic
   marker-less RGB fixture was generated in-repo; DCMTK and dcm4che independently match GDCM's
   raw output, while the former GPL result differs. The production plan retains fixture admission,
   regression, and frozen-build requirements.
4. **Wider real-world prevalence scan (optional).** The big MR/CT/PT/Fusion folders
   (7k–24k files) were not scanned for `.51/.57/.70` prevalence. Not needed for the GDCM path
   (GDCM covers them), but would quantify how much a Pillow-only fallback would have cost.
5. **imagecodecs (BSD) instead of the selected GDCM path — gated by pydicom 3.** `imagecodecs` is a fully
   permissive (BSD-3) full-coverage decoder, but only as a **pydicom 3.x** plugin. **pydicom 3 is
   blocked by `pylinac 3.43.2` (`pydicom<3,>=2.0`)** — the same ceiling as highdicom (see
   [`HIGHDICOM_OVERVIEW.md`](../../info/HIGHDICOM_OVERVIEW.md) §4a). Only relevant if a fully
   permissive alternative becomes preferable; otherwise GDCM is the lower-effort choice. Full landscape in the strategy
   doc. Tracked in `TO_DO.md` (Maintenance).

### Why pydicom 2.x (not 3)?
Not a hard pin — `requirements.txt` allows `pydicom>=2.4.0,<3`. The `<3` ceiling comes from
**`pylinac 3.43.2` requiring `pydicom<3`**. This is the same constraint that defers highdicom
and the imagecodecs decoder option; all three would be unblocked by a coordinated pydicom 3 +
pylinac bump (with ACR QA re-verification).

## Spike artifacts & environment (for whoever resumes)
- **Branch:** `spike/no-pylibjpeg-libjpeg` (no worktree).
- **Harness:** `scripts/decoder_corpus_report.py`.
- **Corpus & reports (git-ignored):** `decoder-spike-artifacts/` (dedicated top-level folder) —
  `pydicom/`, `real-tests/`, `golden_baseline.json/.csv`, `pillow_only.json`, `gdcm.json`, inventory JSONs.
- **Spike venvs (git-ignored):** `.venv-spike` (Pillow-only), `.venv-gdcm` (+ `python-gdcm`).
  Recreate via the pinned versions in the Results log if deleted. Main `.venv` was never modified.

## Related
- Strategy / options: [`PYLIBJPEG_ALTERNATIVES_AND_DICOM_DECODER_STRATEGY.md`](../../info/PYLIBJPEG_ALTERNATIVES_AND_DICOM_DECODER_STRATEGY.md)
- Production execution: [`GDCM_DECODER_PRODUCTIONIZATION_PLAN.md`](GDCM_DECODER_PRODUCTIONIZATION_PLAN.md)
- Legal gate: [`LICENSE_AND_COMPLIANCE_PLAN.md` §0a](LICENSE_AND_COMPLIANCE_PLAN.md#0a-pylibjpeg-libjpeg-replacement--gdcm-productionization-blocking)
- Master gate: [`COMMERCIAL_RELEASE_READINESS.md`](../../COMMERCIAL_RELEASE_READINESS.md) item #1

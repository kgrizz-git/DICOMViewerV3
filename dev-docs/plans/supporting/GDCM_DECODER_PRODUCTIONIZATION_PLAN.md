# GDCM Decoder Productionization & Independent Validation Plan

**Status:** In progress — synthetic color-edge fixture generated; human asset review and productionization pending  
**Last updated:** 2026-07-29  
**Priority:** P0 — commercial-release Tier 0 blocker  
**Branch:** `plan/gdcm-decoder-productionization`  
**TO_DO ref:** Release / Product → “Replace GPL `pylibjpeg-libjpeg` with selected `python-gdcm` + verify decode”

---

## Decision and objective

The completed [decoder replacement spike](DECODER_REPLACEMENT_SPIKE_PLAN.md) selected
`python-gdcm` to replace the GPL-3.0 `pylibjpeg-libjpeg` runtime dependency. GDCM had no new
failures against the 42-file private corpus and produced bit-exact results for lossless samples.
Pillow-only was rejected because it lost JPEG Lossless (`.57`/`.70`) and some JPEG Extended (`.51`)
coverage.

This plan turns that selection into a shipped, validated dependency change. It also resolves the
one remaining color-semantics question: a synthetic JPEG Baseline `.50` fixture without an APP14
color-transform marker produces different colors with GDCM and the former GPL decoder.

**Target runtime decoder set**

| Transfer-syntax family | Shipped component | Purpose |
|---|---|---|
| Classic JPEG Baseline / Extended / Lossless | `python-gdcm` | Direct GPL replacement |
| JPEG 2000 | `pylibjpeg-openjpeg` | Existing non-GPL coverage |
| JPEG-LS | `pyjpegls` | Existing non-GPL coverage |
| RLE | `pylibjpeg-rle` | Existing non-GPL coverage |
| Other suitable classic JPEG inputs | Pillow/pydicom fallback | Existing fallback; not the selected primary replacement |

Do **not** add a custom PyTurboJPEG plugin, bundle `pylibjpeg-libjpeg`, or use a GPL tool as a
runtime dependency. The toolchain below is validation-only and must not be added to
`requirements.txt` unless a separate product decision explicitly changes scope.

## Completion criteria

This blocker is complete only when all of the following are true:

1. The release requirements and PyInstaller specification contain `python-gdcm`, not
   `pylibjpeg-libjpeg`, and a fresh release environment installs successfully.
2. The selected decoder set passes the approved corpus comparison: exact hashes for lossless
   data; documented, bounded comparison for lossy data; no unreviewed failures.
3. The synthetic no-color-transform JPEG behavior is resolved from DICOM metadata and at least
   two independent implementations or an independently reproducible reference—not by choosing
   whichever decoder matches the former GPL plugin.
4. The frozen macOS, Windows, and Linux builds discover GDCM native libraries and decode the
   corpus; their bundle-size deltas are recorded.
5. Runtime errors name the unsupported transfer syntax without advising a user to install a GPL
   package. Decoder backend and version are available in privacy-safe diagnostics.
6. Committed tests use only reviewed, wholly synthetic, non-PHI fixtures. The dependency license
   gate passes with no `pylibjpeg-libjpeg` exception.

## Scope, evidence, and non-goals

### Existing evidence

- Private spike corpus: 42 files; GDCM had zero new failures.
- JPEG Lossless `.57` decoded bit-exactly; no lossless mismatch was observed.
- One JPEG Extended synthetic file differed by at most one LSB, consistent with lossy rounding.
- One synthetic JPEG Baseline fixture without APP14 differed materially in color interpretation;
  real XA/OT color JPEG samples matched the former decoder bit-exactly.
- The spike corpus, reports, and spike environments are local-only under
  `decoder-spike-artifacts/`; they are not commit candidates.
- **2026-07-29 synthetic replacement fixture:**
  `tests/scripts/generate_decoder_color_fixture.py` creates a wholly synthetic RGB JPEG Baseline
  color-block image whose codestream contains neither APP0 nor APP14. Its DICOM metadata and JPEG
  component IDs both declare RGB. A human visually reviewed the color-block output on 2026-07-29,
  and its SHA-256 was recorded in `security/approved-media-sha256.json`.
- **Initial validator result (2026-07-29):** DCMTK 3.7.0 with `+cn` and pydicom 3.0.2's GDCM
  handler produced exactly the same decoded pixels for the synthetic fixture. The current GPL
  handler produced a different result. This supports GDCM honoring the fixture's explicit RGB
  semantics; retain dcm4che/fo-dicom as tie-breakers if later platform or standards evidence
  conflicts.

### Non-goals

- Do not change the pydicom 2.x / pylinac compatibility decision as part of this work.
- Do not make `imagecodecs`, DCMTK, libjpeg-turbo CLI tools, or a GPL FFmpeg build runtime
  dependencies. They may be isolated validation tools only.
- Do not claim that a decode match establishes clinical suitability, diagnostic accuracy, or legal
  compliance. License counsel still owns the legal conclusion.

## Privacy and artifact protocol

Before touching any corpus data, follow
[PHI / PII Repository Guardrails](../../PHI_PII_REPOSITORY_GUARDRAILS.md):

- Use the known wholly synthetic fixture for the color investigation plus approved public,
  non-PHI test samples only. Do not use real studies for the independent-decoder experiment.
- Keep venvs, command output, decoded images, hashes, reports, and temporary DICOM copies outside
  the checkout or under existing ignored local roots. Never commit a result report or rendered
  image without the required review gate.
- Record only decoder name/version, transfer-syntax UID, photometric interpretation, pass/fail,
  and aggregate difference metrics. Do not print paths, tag values that can identify a patient,
  raw exception strings, pixels, or image crops.

## Independent reference strategy for the color-edge fixture

The question is not simply “which decoder produces prettier colors.” It is whether the DICOM
`PhotometricInterpretation` and the embedded JPEG codestream require a particular native color
interpretation and whether display conversion should happen afterwards. Therefore compare both
the **raw decoded samples** and the **display-ready RGB result**, recording metadata at each step.

| Candidate | Independence and role | Install/use rule | Decision weight |
|---|---|---|---|
| **DCMTK** (`dcmdjpeg`, `dcm2img`) | Independent DICOM parser and JPEG decoder; strongest full-DICOM cross-check | Install in an isolated validation tool environment; first confirm exact command options with `--help` and preserve raw/unconverted versus converted output separately | Primary independent reference |
| **dcm4che** (`dcm2jpg` / `dcm2dcm`) | Independent Java DICOM parser and image-codec stack | Install a current JRE and the official binary distribution into an isolated validation-tools root; verify exact commands/options before use | Second independent DICOM reference |
| **fo-dicom** (minimal isolated .NET console validator) | Independent .NET DICOM parser/rendering stack | Install the .NET SDK and create a temporary validator outside the repository only if DCMTK and dcm4che disagree or one cannot handle the fixture | Tie-breaker; not a runtime candidate |
| **pydicom 3 + imagecodecs** | Separate JPEG codec library, but **not** a pydicom 3.0.2 decoder plugin for the required JPEG Baseline UID | Installed in a disposable venv and probed on 2026-07-29: no available plugin for `.50`; use only after frame extraction as a codec/marker corroboration, not a DICOM-aware reference | Supplemental evidence |
| **libjpeg-turbo** (`djpeg`, `jpegtran`) | Independent JPEG-codestream inspection/decode only; it does not read DICOM tags | Extract only the wholly synthetic encapsulated JPEG frame to a temporary location; use to inspect marker behavior and codec output, never as the sole DICOM-color authority | Supplemental evidence |
| **GDCM CLI** (`gdcminfo`, `gdcmconv`) | Same GDCM implementation as the proposed runtime binding | Use to verify Python-binding versus CLI behavior and later frozen-build parity, not as an independent adjudicator | Implementation-parity check |
| **Former `pylibjpeg-libjpeg` environment** | Historical golden baseline, but the GPL component being removed | Retain only in the pre-existing isolated spike environment; do not use as normative truth or ship it | Regression comparison only |
| Pillow/pydicom | Existing fallback code path | Run only if it can decode the fixture; preserve result but do not use it as the deciding authority because it already rejected part of the corpus | Supplemental evidence |

### Reference decision rule

1. Read the fixture’s Image Pixel metadata and inspect its JPEG marker structure without changing
   the source fixture.
2. Decode with DCMTK and dcm4che using explicitly documented raw and
   display-conversion modes. Record safe array hashes, shape/dtype, color-space metadata, and
   aggregate differences only.
3. If the two independent implementations agree, validate that result against the applicable
   DICOM/JPEG rule and adopt it as expected behavior.
4. If they disagree, construct a small wholly synthetic, known-color source fixture in a separate
   reproducible generator and repeat the test. Do not use GDCM to generate the ground truth being
   used to judge GDCM.
5. If DCMTK and dcm4che disagree, use an isolated fo-dicom validator as a third independent
   DICOM-aware comparison.
6. If disagreement remains, stop productionization of this syntax, document the ambiguity, and
   obtain a specialist review before deciding a runtime workaround.

## Phase 0 — Reproducible validation setup

- [ ] Record the target release matrix: Python 3.11 for current PyInstaller builds and Python
      3.12 for CI tests; macOS, Windows, and Linux packaging targets.
- [ ] Create isolated, disposable validation environments outside the repository for DCMTK and
      dcm4che. Pin and record their versions in a safe local report. **Partial (2026-07-29):**
      DCMTK 3.7.0 installed locally; dcm4che remains to be set up.
- [ ] Confirm the chosen DCMTK package exposes `dcmdjpeg` and `dcm2img`; confirm pydicom 3 plus
      imagecodecs exposes a decoder for the exact JPEG Baseline UID before relying on either.
      **Result (2026-07-29):** pydicom 3.0.2 exposes no imagecodecs decoder plugin for `.50`,
      so it is not a DICOM-aware reference candidate; use dcm4che instead.
- [ ] Add a small, source-controlled validation runner that accepts only an explicit synthetic
      fixture path, produces privacy-safe metrics, and refuses to write reports in the repository.
- [ ] Extend `scripts/decoder_corpus_report.py` only if it can record a requested backend without
      changing normal application behavior; otherwise keep validation helpers under `scripts/` as
      standalone, documented tooling.

**Gate 0:** every validator runs from its isolated environment, no validation output is staged,
and the test file’s synthetic provenance is recorded.

## Phase 1 — Resolve JPEG Baseline no-color-transform semantics

- [x] Generate a small, wholly synthetic RGB JPEG Baseline fixture with no APP0/APP14 markers,
      explicit RGB component IDs, empty patient Type 2 values, no rendered text, an in-repository
      generator, and structural tests. **Done 2026-07-29;** human visual review completed and the
      reviewed-asset manifest updated.
- [x] Decode the fixture with the GDCM candidate and independent DCMTK using `+cn` (do not infer
      YCbCr); the decoded arrays match exactly. **Done 2026-07-29.**
- [ ] Read and safely record the fixture's transfer syntax and Image Pixel attributes needed for
      color interpretation: Samples per Pixel, Photometric Interpretation, Bits Allocated/Stored,
      Planar Configuration, and any relevant encapsulated JPEG markers.
- [ ] Use DCMTK to decode the source without an implicit presentation/display transform and,
      separately, to render/convert it according to its documented color option. Verify the exact
      behavior from the installed tool's help/version rather than assuming flags.
- [ ] Use dcm4che to decode raw samples and display-ready samples separately; record its returned
      color-space metadata and aggregate difference metrics. Validate its exact options from the
      installed distribution before relying on them.
- [ ] Optionally use direct imagecodecs after frame extraction to compare JPEG-codec output. It
      has no DICOM metadata context and cannot by itself resolve Photometric Interpretation.
- [ ] Use libjpeg-turbo on the extracted synthetic JPEG frame to establish what the codestream
      itself signals. Treat this as marker/codec evidence only because it has no DICOM context.
- [ ] Compare all outputs to the current GDCM and historical baseline results: exact hashes when
      representations match, otherwise max/mean absolute difference, changed-pixel proportion,
      and a visual check of the wholly synthetic color pattern.
- [ ] Write the conclusion, applicable standard rationale, expected raw representation, and
      expected display representation in the decoder strategy document and a regression-test
      comment. If GDCM is correct, retain it unchanged; otherwise define the smallest
      standards-conformant conversion step and obtain review before implementation.

**Gate 1:** two independent DICOM-aware decoders agree, or an explicit review resolves a
standards-backed disagreement. A match only to the old GPL decoder is insufficient.

## Phase 2 — Package GDCM safely

- [ ] Add `python-gdcm` to `requirements.txt` with an evidence-backed compatible version/range;
      remove `pylibjpeg-libjpeg`.
- [ ] Update `DICOMViewerV3.spec` hidden imports, binaries, and data collection based on the
      actual `python-gdcm` wheel contents. Remove the `libjpeg` hidden import that existed only
      for `pylibjpeg-libjpeg`; do not guess native-library paths.
- [ ] Build from a clean environment on macOS, Windows, and Linux. For each bundle, use the
      packaged executable—not the build venv—to run a privacy-safe corpus-decode check.
- [ ] Record application startup, corpus result, selected backend/version, and before/after bundle
      size. Investigate any platform-specific loader failure before changing the decoder choice.
- [ ] Review the exact GDCM license/notices and dynamic-library distribution obligations with the
      license-compliance plan; do not treat the engineering result as legal advice.

**Gate 2:** all target bundles load GDCM and meet the corpus criteria; the release artifact has no
GPL `pylibjpeg-libjpeg` dependency.

## Phase 3 — Application behavior and provenance

- [ ] Add one focused capability module mapping relevant transfer-syntax UIDs to available
      decoder support. Avoid scattered package-name checks and import-error control flow.
- [ ] Update `src/core/dicom_pixel_array.py` and loader error handling to name the unsupported
      transfer syntax safely and provide product-profile-aware guidance; never advise installing a
      GPL decoder from a commercial build.
- [ ] Record selected decoder backend and version through existing privacy-safe debug diagnostics
      and future About/System Info surfaces. Keep all debug flags false by default.
- [ ] Add regression tests for: available classic JPEG decode; lossless exactness; expected
      color-edge result; unsupported syntax messaging; and no GPL-install recommendation.
- [ ] Confirm JPEG 2000, JPEG-LS, RLE, uncompressed, multi-frame, RGB/YBR, ROI/statistics, and
      export paths still work with the final plugin set.

**Gate 3:** user-facing failures are actionable and safe, decoder provenance is available, and all
non-classic decoder paths retain coverage.

## Phase 4 — Compliance, documentation, and release verification

- [ ] Remove the `pylibjpeg-libjpeg` accepted exception from
      `dev-docs/info/dependency_license_policy.json`; run the dependency license check in the
      release environment and resolve any newly surfaced licenses.
- [ ] Update `BUNDLED_PACKAGES_AND_FONTS_LICENSES.md`, the decoder strategy, commercial release
      readiness gate, `TO_DO.md`, and the spike plan with the final evidence and any bundled GDCM
      notices required by the compliance review.
- [ ] Move this plan and the spike plan to `plans/completed/` only when the commercial blocker is
      actually cleared; otherwise keep both under `plans/supporting/` with current status.
- [ ] Run the full test suite, repository harness, architecture-boundary check, agent smoke, and
      the relevant privacy/artifact gates. Perform cross-platform manual load and frozen-build
      decode smokes before marking the release gate complete.

## Files likely to change

| File / area | Expected change |
|---|---|
| `requirements.txt` | Replace GPL `pylibjpeg-libjpeg` with `python-gdcm` |
| `DICOMViewerV3.spec` | Package actual GDCM native libraries; remove old `libjpeg` hidden import |
| `src/core/` | Decoder capability and safe unsupported-syntax messaging |
| `src/utils/` / About-System Info | Privacy-safe backend/version provenance |
| `scripts/` | Optional isolated validation/corpus runner with safe output rules |
| `tests/` | Non-PHI decoder and messaging regression coverage |
| `dev-docs/info/dependency_license_policy.json` | Remove GPL exception |
| License, strategy, readiness, and changelog docs | Record dependency and validation outcome |

## Required verification commands

Activate the project venv before application/test commands. Run the final checks appropriate to
the actual diff:

```bash
python -m pytest tests/ -v
python scripts/check_dependency_licenses.py
python scripts/check_repo_harness.py
python scripts/check_architecture_boundaries.py
python scripts/agent_smoke_harness.py
python scripts/git_hook_privacy_checks.py --staged
python scripts/git_hook_privacy_checks.py --all --critical
```

Run the blocked frozen-build and corpus validation separately on each target platform, with
reports outside the checkout. A scanner `SKIP` is not a passing result.

## Linked records

- [Decoder replacement spike plan](DECODER_REPLACEMENT_SPIKE_PLAN.md) — completed option study
  and private-corpus results.
- [Decoder strategy](../../info/PYLIBJPEG_ALTERNATIVES_AND_DICOM_DECODER_STRATEGY.md) — option
  landscape and final technical rationale.
- [Commercial release readiness](../../COMMERCIAL_RELEASE_READINESS.md) — owner gate.
- [License & library compliance plan](LICENSE_AND_COMPLIANCE_PLAN.md#0a-pylibjpeg-libjpeg--gpl-30-jpeg-decoder-blocking) — license-review workstream.

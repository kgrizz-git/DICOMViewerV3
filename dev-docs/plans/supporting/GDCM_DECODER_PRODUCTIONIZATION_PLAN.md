# GDCM Decoder Productionization & Independent Validation Plan

**Status:** In progress — synthetic decision/matrix, dependency swap, capability messaging, and local regression coverage complete; frozen-build validation pending
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

This plan turns that selection into a shipped, validated dependency change. It has resolved the
remaining color-semantics question: a synthetic JPEG Baseline `.50` fixture without an APP14
color-transform marker produces different colors with GDCM and the former GPL decoder; GDCM's
result matches two independent DICOM implementations.

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
6. Expected successful decode does not write unreviewed native diagnostics to stdout/stderr or a
   user-visible surface. The sole current exception is the exact, documented one-line native
   diagnostic from `python-gdcm==3.2.6` while it successfully falls back to decode the approved
   12-bit JPEG Extended `.51` fixture; an isolated subprocess must assert that exact output and
   the independently confirmed pixels. Failures remain privacy-safe and identify only the
   transfer syntax.
7. Committed tests use only reviewed, wholly synthetic, non-PHI fixtures. The dependency license
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
  semantics.
- **Independent confirmation (2026-07-29):** dcm4che 5.34.3 `dcm2dcm` and DCMTK 3.7.0
  `dcmdjpeg +cn` each decompressed the marker-less RGB `.50` fixture to the exact same raw-pixel
  SHA-256 as pydicom 2.4.5 + GDCM 3.2.6. The former GPL handler produced a different hash.
  dcm4che's separately rendered lossless PNG was also produced successfully. This satisfies the
  two-independent-implementation rule for raw samples; fo-dicom is not needed unless a later
  platform result conflicts.
- **Valid 12-bit `.51` check (2026-07-29):** a reviewed in-repository fixture uses a libjpeg-turbo 3.2.0
  `cjpeg -precision 12` SOF1 frame, not a GDCM-encoded frame. pydicom 2.4.5 + GDCM 3.2.6,
  dcm4che 5.34.3, and DCMTK 3.7.0 agree exactly. The former GPL handler differs by at most two
  sample values (285/3072 pixels; mean absolute difference 0.099609). This is a decoder
  comparison result, not a clinical-accuracy claim.
- **Runtime-line compatibility (2026-07-29):** `python-gdcm` 3.2.6 registered and decoded the
  complete synthetic matrix with the application's pydicom 2.4.5 line under isolated CPython
  3.11.15 and 3.12.10 macOS/arm64 environments. Windows and Linux packaging validation remains
  required.
- **12-bit native-diagnostic investigation (2026-07-29):** the current published
  `python-gdcm` 3.2.6 wheel and Homebrew's default GDCM 3.2.7 build both correctly decode the
  valid `.51` fixture but write `Unsupported JPEG data precision 12`. Upstream GDCM 3.2.6 source
  shows why: it initially selects its fixed-precision JPEG decoder from DICOM `Bits Allocated`
  (16), that decoder rejects the valid 12-bit JPEG codestream, and GDCM retries the 12-bit
  decoder successfully. The source deliberately cannot simply select `Bits Stored`, because some
  valid inputs have 12 bits stored in a 16-bit JPEG codestream. A locally built GDCM 3.2.7 with
  `GDCM_USE_JPEGTURBO=ON` and libjpeg-turbo 3.2.0 made the full approved synthetic matrix quiet
  and produced the independently confirmed `.50` and `.51` hashes. This is evidence for the
  optional backend, not release evidence: PyPI currently publishes only `python-gdcm` 3.2.6.
- **Native-diagnostic release decision (2026-07-29):** permit the exact native stderr line
  `Unsupported JPEG data precision 12` only when the approved `.51` fixture decodes successfully
  to its independently confirmed GDCM/DCMTK/dcm4che pixel hash. Assert this contract in an
  isolated subprocess, so the test captures native stderr without process-wide redirection. Any
  other decoder stdout/stderr, a changed message, a non-zero exit, or a pixel/reference mismatch
  is a release failure. Do not redirect or hide process stderr in application code. The
  libjpeg-turbo-backed GDCM configuration remains the preferred cleanup, and the packaged-wheel
  behavior is tracked upstream in [python-gdcm issue #35](https://github.com/tfmoraes/python-gdcm/issues/35).

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

- [ ] Record the final target release matrix: Python 3.11 and 3.12; macOS, Windows, and Linux
      packaging targets. **Partial (2026-07-29):** the exact application compatibility line
      (`pydicom==2.4.5`, `python-gdcm==3.2.6`) works on isolated macOS/arm64 CPython 3.11.15 and
      3.12.10 environments. Validate Windows and Linux wheels, then pin the selected version
      before editing release requirements.
- [x] Create isolated, disposable validation environments outside the repository for DCMTK and
      dcm4che. Pin and record their versions in a safe local report. **Done 2026-07-29:** DCMTK
      3.7.0 and dcm4che 5.34.3 ran locally outside the repository; dcm4che used OpenJDK 26 plus
      its official Maven artifacts and matching macOS native library.
- [x] Confirm the chosen DCMTK package exposes `dcmdjpeg` and `dcm2img`; confirm pydicom 3 plus
      imagecodecs exposes a decoder for the exact JPEG Baseline UID before relying on either.
      **Result (2026-07-29):** pydicom 3.0.2 exposes no imagecodecs decoder plugin for `.50`,
      so it is not a DICOM-aware reference candidate; use dcm4che instead.
- [ ] Add a small, source-controlled validation runner that accepts only an explicit synthetic
      fixture path, produces privacy-safe metrics, and refuses to write reports in the repository.
- [ ] Extend `scripts/decoder_corpus_report.py` only if it can record a requested backend without
      changing normal application behavior; otherwise keep validation helpers under `scripts/` as
      standalone, documented tooling.
- [x] Add a focused frozen-executable smoke runner that accepts only the committed synthetic
      fixture directory, emits transfer syntax/backend/version plus hashes and aggregate metrics,
      and returns non-zero for a missing handler, unallowlisted stdout/stderr, or a reference
      mismatch. It must capture the `.51` decode in an isolated child process and allow only the
      exact approved diagnostic. **Done 2026-07-29:** `--decoder-fixture-smoke` produces a
      path-free JSON report; its child mode keeps the `.51` native diagnostic assertion isolated.

**Gate 0:** every validator runs from its isolated environment, no validation output is staged,
and the test file’s synthetic provenance is recorded.

## Phase 1 — Resolve JPEG Baseline no-color-transform semantics

- [x] Generate a small, wholly synthetic RGB JPEG Baseline fixture with no APP0/APP14 markers,
      explicit RGB component IDs, empty patient Type 2 values, no rendered text, an in-repository
      generator, and structural tests. **Done 2026-07-29;** human visual review completed and the
      reviewed-asset manifest updated.
- [x] Decode the fixture with the GDCM candidate and independent DCMTK using `+cn` (do not infer
      YCbCr); the decoded arrays match exactly. **Done 2026-07-29.**
- [x] Read and safely record the fixture's transfer syntax and Image Pixel attributes needed for
      color interpretation: Samples per Pixel, Photometric Interpretation, Bits Allocated/Stored,
      Planar Configuration, and any relevant encapsulated JPEG markers. **Done 2026-07-29:** the
      source is `.50`, RGB, 8-bit, planar 0, three RGB component IDs, and no APP0/APP14 marker.
- [x] Use DCMTK to decode the source without an implicit presentation/display transform and,
      separately, to render/convert it according to its documented color option. Verify the exact
      behavior from the installed tool's help/version rather than assuming flags. **Raw decode done
      2026-07-29:** `dcmdjpeg +cn` matches GDCM exactly; retain command/output capture in the
      validation runner.
- [x] Use dcm4che to decode raw samples and display-ready samples separately; record its returned
      color-space metadata and aggregate difference metrics. Validate its exact options from the
      installed distribution before relying on them. **Raw decode done 2026-07-29:** dcm4che 5.34.3
      `dcm2dcm` matches both DCMTK and GDCM exactly; `dcm2jpg --usedis -F PNG` rendered a lossless
      RGB PNG. Preserve this invocation in the validation runner rather than treating its PNG file
      bytes as a raw-pixel comparison.
- [ ] Optionally use direct imagecodecs after frame extraction to compare JPEG-codec output. It
      has no DICOM metadata context and cannot by itself resolve Photometric Interpretation.
- [ ] Use libjpeg-turbo on the extracted synthetic JPEG frame to establish what the codestream
      itself signals. Treat this as marker/codec evidence only because it has no DICOM context.
- [x] Compare all outputs to the current GDCM and historical baseline results: exact hashes when
      representations match, otherwise max/mean absolute difference, changed-pixel proportion,
      and a visual check of the wholly synthetic color pattern. **Done 2026-07-29:** DCMTK,
      dcm4che, and GDCM agree for `.50` RGB and valid `.51` 12-bit grayscale fixtures; the old GPL
      output differs for both. The `.51` delta is max 2, 285/3072 changed, mean 0.099609.
- [ ] Write the conclusion, applicable standard rationale, expected raw representation, and
      expected display representation in the decoder strategy document and a regression-test
      comment. If GDCM is correct, retain it unchanged; otherwise define the smallest
      standards-conformant conversion step and obtain review before implementation.

**Gate 1:** **Satisfied for raw samples on 2026-07-29.** DCMTK and dcm4che agree with GDCM on the
marker-less RGB `.50` fixture, and DCMTK/dcm4che also agree with GDCM on a valid independently
encoded 12-bit `.51` fixture. A match only to the old GPL decoder is insufficient. Retain fo-dicom
as a tie-breaker only if a platform-specific result conflicts.

### Compatibility and pin-decision checklist

This is an execution checklist, not a second decision plan. Complete it immediately before editing
`requirements.txt`.

| Check | Required evidence | Current state |
|---|---|---|
| Runtime pair | Exact `pydicom` and `python-gdcm` versions, Python version, OS/architecture, and wheel origin | `pydicom==2.4.5` + `python-gdcm==3.2.6` passed on macOS/arm64 CPython 3.11.15 and 3.12.10; other release platforms pending |
| Handler selection | `gdcm_handler.is_available()` and `supports_transfer_syntax()` for `.50`, `.51`, `.57`, `.70`; tests must not infer backend from an import alone | Verified for `.50`; add an application capability test for all at-risk UIDs |
| Fixture matrix | All committed fixture hashes and shapes pass in a GDCM-only environment; lossless cases match their deterministic source patterns | Verified on macOS/arm64; add CI/frozen-runner invocation after dependency change |
| Native diagnostics | A successful decode produces no unreviewed process stderr/stdout and no application-level suppression | **Approved narrow exception:** an isolated subprocess must assert that the `.51` fixture exits successfully, has its confirmed hash, writes exactly `Unsupported JPEG data precision 12` plus its line ending to stderr, and writes no other output. Any other output or mismatch blocks release. Track [python-gdcm #35](https://github.com/tfmoraes/python-gdcm/issues/35); a turbo-backed wheel remains preferred cleanup. |
| Release pin | Version is an exact, evidence-backed release pin at first shipment; upgrades follow the dependency-bump verification plan | Pending license, wheel, and frozen-build evidence |

Do not use a pydicom 3/imagecodecs result to satisfy this checklist: the shipped dependency line is
currently pydicom 2.x. Conversely, do not widen this task into a pydicom/pylinac upgrade merely
because that future option exists.

### Regression-test contract

The source-controlled target suite is intentionally smaller than the private corpus but independently reproducible:

| Fixture family | Expected assertion | Why it catches the relevant regression |
|---|---|---|
| RGB `.50` without APP0/APP14 | GDCM raw-pixel SHA-256 `9d2130…a1ef03c28`; RGB metadata/component IDs and no marker | Detects incorrect YCbCr inference or an unintended conversion |
| Valid 12-bit JPEG Extended `.51` | GDCM/DCMTK/dcm4che raw-pixel SHA-256 `8cb01f…6a1b6dc`; shape/dtype/range; isolated-subprocess stderr exactly `Unsupported JPEG data precision 12` | Detects an unavailable 12-bit decoder, different lossy rounding path, or changed/unexpected native output |
| JPEG Lossless `.57` and `.70` | Exact deterministic 12-bit source SHA-256 | Detects silent lossless corruption |
| JPEG-LS, JPEG 2000, RLE, uncompressed controls | Exact 12- or 16-bit source SHA-256 | Proves the retained non-classic handlers did not regress |
| Private corpus | Exact hashes for lossless; safe aggregate tolerances for lossy; no new failure | Preserves representative real-world coverage without committing private data |

`tests/test_synthetic_decoder_fixture.py` performs structural/privacy checks, exact lossless checks
in every supported environment, and GDCM-specific expected-output checks only when GDCM is
installed. Its `.51` regression invokes an isolated Python subprocess and asserts both the exact
approved native diagnostic and the independently confirmed pixel hash. The human review and
reviewed-asset hashes for the fixture matrix were completed on 2026-07-29. After the requirements
swap, the GDCM-specific checks must run rather than skip. The frozen runner must reuse the same
fixture set, expected values, and diagnostic allowlist; do not duplicate golden values in a
separate undocumented script.

### Frozen-build runbook

For **each** macOS, Windows, and Linux release target:

1. Create a clean build environment from the final locked requirements. Record only Python/OS/CPU,
   package versions, wheel filenames/hashes, and GDCM handler availability.
2. Run the focused fixture suite in that environment, then build the application using the final
   PyInstaller specification. Record pre/post bundle size with the same build mode.
3. Run the frozen executable's synthetic-fixture smoke runner, not Python from the build venv. It
   must report transfer syntax, decoder backend/version, shape/dtype, expected-hash result, and
   safe aggregate difference metrics only; no paths, identifiers, pixels, or raw exceptions.
4. Confirm all committed fixtures decode as specified, the private corpus has no unreviewed
   failure, and the successful `.51` child-process decode emits exactly the approved native
   diagnostic and no other output.
5. Inspect the packaged dependency manifest/binary inventory for `pylibjpeg-libjpeg` and its
   `pylibjpeg_libjpeg` Python/native plugin. Neither may be present. A `libjpeg` library supplied
   by Pillow or GDCM is not, by filename alone, evidence of the removed GPL plugin; inventory it
   under its actual owning component and license. Capture required GDCM notices before release.

Any Windows/Linux loader failure, platform output mismatch, unexpected native output, or GPL binary
found in the bundle blocks the swap; it is not a reason to silently add the old decoder back.

### Native GDCM asset and SBOM notice checklist

Complete this once per release target, using the **final frozen artifact**, not the development
environment or a generic package-license result:

- [ ] Preserve the exact `python-gdcm` wheel filename, version, SHA-256, and build platform in the
      release evidence.
- [ ] Produce a bundle-relative inventory of every collected `_gdcm` native library and data file,
      including file SHA-256 and the library/version it belongs to. Do not record local paths.
      Use `python scripts/report_gdcm_bundle_inventory.py <bundle>` and keep its JSON report
      outside the checkout as release evidence.
      **macOS/arm64 local evidence 2026-07-29:** the generated report contains 142 GDCM-named asset
      entries and no `pylibjpeg_libjpeg` paths. It also identifies three `libjpeg` paths requiring
      component review; they are attributable to Pillow collection, not evidence of the removed
      plugin. Repeat this inventory for every release target and complete notice attribution.
- [ ] Identify each library's license and required copyright/notice text from the exact wheel and
      its upstream release materials; include transitive native libraries revealed by platform
      linkage inspection.
- [ ] Reconcile that inventory with the generated release SBOM and `THIRD_PARTY_LICENSES.md`:
      every collected GDCM/native dependency has an entry and required notice, and no entry claims
      a license solely from Python package metadata.
- [ ] Produce and compare complementary release artifacts: `pip-licenses` for human-readable
      attribution/license texts; CycloneDX Python for the release-venv dependency graph; Syft for
      a CycloneDX or SPDX inventory of the final frozen artifact; and ScanCode Toolkit for
      file-level license/notice review of the exact GDCM wheel and collected native assets.
      Differences are review findings, not automatic failures. Run Grype against the Syft SBOM as
      the separate vulnerability check; it does not validate license attribution.
- [ ] Confirm the final artifact contains neither `pylibjpeg-libjpeg` nor its GPL
      `pylibjpeg_libjpeg` plugin, and record the result with the frozen-fixture smoke evidence.
      Do not flag a same-named library from Pillow or GDCM without tracing its owning component.
- [ ] Have the release/compliance owner review the completed inventory and required distribution
      obligations before shipment. This is an evidence and notice review, not legal advice.

## Phase 2 — Package GDCM safely

- [x] Add `python-gdcm` to `requirements.txt` as the exact version selected by the compatibility
      checklist (start from the validated `3.2.6` wheel unless later evidence requires a different
      version); remove `pylibjpeg-libjpeg`. Do not change pydicom's major version in this batch.
      **Done 2026-07-29:** `python-gdcm==3.2.6` replaces the GPL plugin in the release
      requirements and the local release-line test environment.
- [x] Update `DICOMViewerV3.spec` hidden imports, binaries, and data collection based on the
      actual `python-gdcm` wheel contents. Remove the `libjpeg` hidden import that existed only
      for `pylibjpeg-libjpeg`; do not guess native-library paths. **Done 2026-07-29:** the spec
      collects `_gdcm` dynamic libraries and data through PyInstaller hooks (47 native libraries
      and 71 data files in the validated macOS wheel) and imports `gdcm`/`_gdcm.gdcmswig`.
- [ ] Build from a clean environment on macOS, Windows, and Linux. For each bundle, use the
      packaged executable—not the build venv—to run a privacy-safe corpus-decode check.
      **macOS/arm64 local evidence 2026-07-29:** PyInstaller 6.21.0 built the `.app`; its
      executable passed all nine committed synthetic fixtures, including the isolated `.51`
      contract. Repeat this in a clean release environment; Windows and Linux remain required.
- [ ] Record application startup, corpus result, selected backend/version, and before/after bundle
      size. Investigate any platform-specific loader failure, unallowlisted successful-decode
      output, or `.51` diagnostic/pixel-contract change before changing the decoder choice.
      **Partial 2026-07-29:** the macOS/arm64 `.app` is 1.1 GiB and the frozen synthetic runner
      reports GDCM 3.2.6 with all expected hashes and the exact `.51` diagnostic. Collect the
      comparable Windows/Linux figures and release-corpus results.
- [ ] Review the exact GDCM license/notices and dynamic-library distribution obligations with the
      license-compliance plan; do not treat the engineering result as legal advice.

**Gate 2:** all target bundles load GDCM and meet the corpus criteria; the release artifact has no
GPL `pylibjpeg-libjpeg` dependency.

## Phase 3 — Application behavior and provenance

- [x] Add one focused capability module mapping relevant transfer-syntax UIDs to available
      decoder support. Avoid scattered package-name checks and import-error control flow.
      **Done 2026-07-29:** `core.decoder_capabilities` exposes installed pydicom handler support
      and package versions using only transfer-syntax and package metadata.
- [x] Update `src/core/dicom_pixel_array.py` and loader error handling to name the unsupported
      transfer syntax safely and provide product-profile-aware guidance; never advise installing a
      GPL decoder from a commercial build. **Done 2026-07-29:** errors identify the syntax and
      distinguish missing support from an installed-handler decode failure without raw native text
      or package-install advice.
- [ ] Record selected decoder backend and version through existing privacy-safe debug diagnostics
      and future About/System Info surfaces. Keep all debug flags false by default.
- [ ] Add regression tests for: available classic JPEG decode; lossless exactness; expected
      color-edge and 12-bit Extended results; the exact `.51` native-diagnostic allowlist in an
      isolated subprocess; unsupported syntax messaging; no GPL-install recommendation; and
      absence of all other native decoder output during an expected successful decode. **Partial
      2026-07-29:** the committed synthetic matrix, subprocess allowlist/hash assertion, and
      capability/error-message tests are complete; the macOS frozen executable passes the shared
      fixture contract. Remaining workflow-path and Windows/Linux frozen coverage remain.
- [ ] Confirm JPEG 2000, JPEG-LS, RLE, uncompressed, multi-frame, RGB/YBR, ROI/statistics, and
      export paths still work with the final plugin set.

**Gate 3:** user-facing failures are actionable and safe, decoder provenance is available, and all
non-classic decoder paths retain coverage.

## Phase 4 — Compliance, documentation, and release verification

- [x] Remove the `pylibjpeg-libjpeg` accepted exception from
      `dev-docs/info/dependency_license_policy.json`; run the dependency license check in the
      release environment and resolve any newly surfaced licenses. **Done 2026-07-29:** the policy
      is empty and the updated local release-line environment has zero forbidden distributions.
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
| `scripts/` | Isolated validation/corpus runner and frozen-fixture smoke runner with safe output rules |
| `tests/` | Non-PHI decoder, fixture provenance, expected-output, and messaging regression coverage |
| `tests/scripts/` and `tests/fixtures/dicom_decoder/` | Deterministic fixture generators, reviewed source patterns, and fixture contract |
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

Run the blocked frozen-build and corpus validation separately on each target platform using the
frozen-build runbook, with reports outside the checkout. Run the artifact gate and isolated DICOM
privacy-review lane for every newly generated or changed fixture; a scanner `SKIP` is not a passing
result.

## Linked records

- [Decoder replacement spike plan](DECODER_REPLACEMENT_SPIKE_PLAN.md) — completed option study
  and private-corpus results.
- [Decoder strategy](../../info/PYLIBJPEG_ALTERNATIVES_AND_DICOM_DECODER_STRATEGY.md) — option
  landscape and final technical rationale.
- [Commercial release readiness](../../COMMERCIAL_RELEASE_READINESS.md) — owner gate.
- [License & library compliance plan](LICENSE_AND_COMPLIANCE_PLAN.md#0a-pylibjpeg-libjpeg-replacement--gdcm-productionization-blocking) — license-review workstream.

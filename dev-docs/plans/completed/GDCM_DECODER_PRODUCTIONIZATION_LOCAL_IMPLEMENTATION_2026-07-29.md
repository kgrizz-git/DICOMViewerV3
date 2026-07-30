# GDCM Decoder Productionization — Local Implementation Record

**Status:** Completed local engineering record — release validation continues in the active plan
**Completed:** 2026-07-29
**Branch:** `plan/gdcm-decoder-productionization`
**Follow-on:** [GDCM decoder release validation plan](../supporting/GDCM_DECODER_PRODUCTIONIZATION_PLAN.md)

## Outcome

The commercial runtime no longer requires GPL-3.0 `pylibjpeg-libjpeg`.
`python-gdcm==3.2.6` is the selected classic-JPEG decoder; retained handlers continue to cover
JPEG 2000, JPEG-LS, and RLE. This record archives the completed local implementation and its
evidence. It is not evidence that a commercial frozen release has been cleared on every platform.

## Decisions established

- The reviewed marker-less RGB JPEG Baseline `.50` synthetic fixture declares RGB in both DICOM
  metadata and JPEG component IDs. GDCM, DCMTK, and dcm4che agree on its raw pixels; the former GPL
  decoder differs.
- The reviewed valid 12-bit JPEG Extended `.51` fixture is independently encoded with libjpeg-turbo.
  GDCM, DCMTK, and dcm4che agree exactly. The former GPL decoder has a small, documented lossy
  difference.
- `python-gdcm==3.2.6` successfully decodes the `.51` fixture but emits exactly
  `Unsupported JPEG data precision 12\n` while it falls back to its 12-bit decoder. Every
  synthetic fixture is decoded in an isolated child process: only that byte-exact `.51`
  diagnostic is allowed with the confirmed hash, and any other native output or mismatch fails.
  Application stderr is not redirected.
- A GDCM build with libjpeg-turbo removed the diagnostic locally and remains the preferred future
  upstream/wheel cleanup. The published wheel behavior is tracked in
  [python-gdcm issue #35](https://github.com/tfmoraes/python-gdcm/issues/35).

## Completed implementation

- Replaced `pylibjpeg-libjpeg` with `python-gdcm==3.2.6` in `requirements.txt` and removed the
  accepted GPL exception from the dependency-license policy.
- Updated the PyInstaller specification to collect `_gdcm` dynamic libraries/data and
  `python-gdcm` package metadata, while removing the obsolete GPL-plugin hidden import.
- Added privacy-safe decoder capability/version helpers and transfer-syntax-based error messaging;
  removed install-a-GPL-package advice and fragile package-name checks.
- Added the approved synthetic fixture contract, including an isolated subprocess assertion of the
  exact `.51` native diagnostic and pixel hash.
- Added `--decoder-fixture-smoke` to the application entry point. It reports only safe fixture and
  decoder provenance and performs the `.51` check in a child process, so it can validate a frozen
  executable.
- Added `scripts/report_gdcm_bundle_inventory.py` to write a relative-path/hash GDCM asset report
  for release evidence. It distinguishes the removed `pylibjpeg_libjpeg` plugin from same-named
  JPEG libraries owned by other components.
- Updated strategy, compliance, readiness, license, packaging, and backlog documentation.

## Local verification evidence

- Full regression after the implementation/frozen-runner work: `3271 passed, 19 skipped`.
- Targeted synthetic/frozen-runner/inventory tests: passed.
- Dependency license check: zero unaccepted strong-copyleft distributions.
- Repo harness, architecture check, staged privacy/artifact checks, lint, and agent smoke passed.
- A local macOS/arm64 PyInstaller 6.21.0 build completed. Its frozen executable passed all nine
  reviewed synthetic fixtures, reported GDCM 3.2.6, and enforced the exact `.51` diagnostic/hash
  contract. The preliminary inventory contained no `pylibjpeg_libjpeg` path; Pillow `libjpeg`
  artifacts require their own attribution review.

## Commits

- `32083b1 Replace GPL JPEG decoder with GDCM`
- `90c8a8d Add frozen decoder bundle validation`

## Remaining release work

See the active [GDCM decoder release validation plan](../supporting/GDCM_DECODER_PRODUCTIONIZATION_PLAN.md):
clean macOS build evidence, Windows/Linux validation, private-corpus frozen runs, final SBOM and
native-notice reconciliation, vulnerability report, and release/compliance approval.

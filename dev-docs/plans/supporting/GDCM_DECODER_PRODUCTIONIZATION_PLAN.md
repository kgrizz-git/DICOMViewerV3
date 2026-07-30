# GDCM Decoder Release Validation Plan

**Status:** In progress — release evidence and cross-platform validation remaining
**Last updated:** 2026-07-29  
**Priority:** P0 — commercial-release Tier 0 blocker  
**Branch:** `plan/gdcm-decoder-productionization`  
**TO_DO ref:** Release / Product → “Replace GPL `pylibjpeg-libjpeg` with selected `python-gdcm` + verify decode”

## Purpose

The GPL decoder has been replaced locally by `python-gdcm==3.2.6`. This plan covers only the
remaining release evidence: clean builds, independent frozen-artifact validation, corpus testing,
and native-asset license/SBOM review. The completed implementation, decisions, and local evidence
are preserved in the [archived implementation record](../completed/GDCM_DECODER_PRODUCTIONIZATION_LOCAL_IMPLEMENTATION_2026-07-29.md).

## Fixed release contract

- Runtime classic-JPEG support uses `python-gdcm==3.2.6`; JPEG 2000, JPEG-LS, and RLE retain their
  existing non-GPL handlers. Do not reintroduce `pylibjpeg-libjpeg` or a custom GPL decoder.
- The approved synthetic matrix is the canonical frozen smoke input. Lossless outputs require exact
  hashes; the reviewed RGB `.50` and 12-bit JPEG Extended `.51` cases require their independently
  confirmed GDCM/DCMTK/dcm4che hashes.
- The `.51` frozen child process may write exactly `Unsupported JPEG data precision 12\n` to stderr
  and must return the approved pixel hash. Any other stdout/stderr, changed line ending, non-zero
  child exit, or hash mismatch blocks release. Do not suppress process stderr in application code.
- Reports may contain fixture names, transfer-syntax UIDs, handler/package versions, shapes, dtypes,
  hashes, and aggregate metrics only. They must not contain file paths, DICOM identity attributes,
  pixels, or raw native exceptions.

## Completion criteria

1. Clean macOS, Windows, and Linux release environments install the locked requirements and build
   the final PyInstaller artifact successfully.
2. Each frozen executable passes `--decoder-fixture-smoke` with the fixed contract above, then the
   approved private corpus has no unreviewed regression.
3. Every bundle inventories GDCM assets, has no `pylibjpeg-libjpeg`/`pylibjpeg_libjpeg` artifact,
   and records comparable bundle-size and startup results.
4. The release SBOM, attribution texts, native-library notices, and vulnerability report are
   reconciled and reviewed by the release/compliance owner.
5. The normal regression suite, privacy/artifact gates, and relevant manual loading smoke pass in
   the exact release environment.

## Phase 1 — Clean release builds and frozen decode checks

For each macOS, Windows, and Linux target:

- [ ] Create a clean, requirements-only release environment. Record Python, OS, CPU, exact wheel
      filenames/SHA-256 values, and installed package versions; do not record local paths.
- [ ] Run the focused synthetic tests before packaging, then build with `DICOMViewerV3.spec`.
- [ ] Run the frozen executable, not the build interpreter:

  ```text
  <frozen-executable> --decoder-fixture-smoke <reviewed-synthetic-fixture-directory>
  ```

  Preserve the path-free JSON report outside the checkout. It must report GDCM 3.2.6 and pass all
  nine fixtures, including the isolated `.51` diagnostic/hash contract.
- [ ] Record startup result and before/after bundle size using the same build mode.
- [ ] Run the approved private corpus through the frozen artifact. Record only safe aggregate
      outcomes; any new failure, unexpected native output, or reference mismatch blocks release.

**Local evidence, not release sign-off:** a macOS/arm64 PyInstaller 6.21.0 build passed the nine
synthetic fixtures and reported GDCM 3.2.6. Repeat it in a clean release environment; Windows and
Linux are still unvalidated.

## Phase 2 — Native asset, SBOM, and notice review

- [ ] Preserve the exact `python-gdcm` wheel filename, SHA-256, version, and build platform.
- [ ] Generate a bundle-relative GDCM inventory with file hashes:

  ```text
  python scripts/report_gdcm_bundle_inventory.py <bundle>
  ```

  Keep the JSON report outside the checkout. The preliminary macOS report found no
  `pylibjpeg_libjpeg` paths. It found Pillow `libjpeg` copies, which need attribution under Pillow
  and are not, by filename alone, evidence of the removed GPL plugin.
- [ ] Produce and reconcile four complementary artifacts:

  | Tool | Required evidence |
  |---|---|
  | `pip-licenses` / project generator | Human-readable attribution and license texts from the clean release environment |
  | CycloneDX Python | Machine-readable dependency graph for that release environment |
  | Syft | CycloneDX or SPDX inventory of the final frozen artifact |
  | ScanCode Toolkit | File-level license/notice review of the exact GDCM wheel and collected native assets |

  Differences are review findings, not automatic failures.
- [ ] Run Grype against the Syft SBOM for the release vulnerability report. It is a vulnerability
      check, not a license/notice validator.
- [ ] Reconcile every GDCM/native asset with its actual license and notice source. Do not infer
      distribution rights solely from `python-gdcm` package metadata. Obtain release/compliance
      review before shipment.

## Phase 3 — Final release gate

- [ ] Run `python -m pytest tests/ -v`, `python scripts/check_dependency_licenses.py`, repo harness,
      architecture, privacy/artifact, and required manual smoke checks in the release environment.
- [ ] Update the commercial readiness gate, bundled-package notices, generated
      `THIRD_PARTY_LICENSES.md`, maintenance/release records, and this plan with per-platform
      evidence and any resolved notice obligations.
- [ ] Move this plan to `plans/completed/` only after all three release targets and the compliance
      owner have cleared the criteria above.

## References

- [Archived local implementation record](../completed/GDCM_DECODER_PRODUCTIONIZATION_LOCAL_IMPLEMENTATION_2026-07-29.md)
- [Decoder replacement spike](DECODER_REPLACEMENT_SPIKE_PLAN.md)
- [License & library compliance plan](LICENSE_AND_COMPLIANCE_PLAN.md)
- [Bundled packages and fonts licenses](../../info/BUNDLED_PACKAGES_AND_FONTS_LICENSES.md)
- [Commercial release readiness](../../COMMERCIAL_RELEASE_READINESS.md)

# pylibjpeg-libjpeg alternatives and DICOM decoder strategy

Last updated: 2026-06-13

> **Execution:** this note is the *options analysis*. The actionable, phased spike (corpus,
> golden-reference hash-diff, decision gates, productionization) is
> [`DECODER_REPLACEMENT_SPIKE_PLAN.md`](../plans/supporting/DECODER_REPLACEMENT_SPIKE_PLAN.md).

## Purpose

This note separates the engineering decision from the broader license checklist: how to replace or isolate `pylibjpeg-libjpeg`, what each alternative is expected to decode, and what risks or feature losses each path carries.

This is not legal advice. It is an engineering and release-planning aid for choosing a closed-source-friendly DICOM JPEG decode strategy.

## Current issue

`pylibjpeg-libjpeg` is the current blocker because its installed package metadata is treated as GPL-3.0 by the repo license gate. It provides the `pylibjpeg` plugin path for classic DICOM JPEG transfer syntaxes, especially:

- JPEG Baseline 8-bit, UID `1.2.840.10008.1.2.4.50`.
- JPEG Extended 12-bit, UID `1.2.840.10008.1.2.4.51`.
- JPEG Lossless process 14, UID `1.2.840.10008.1.2.4.57`.
- JPEG Lossless first-order prediction, UID `1.2.840.10008.1.2.4.70`.

Do not confuse this with:

- JPEG 2000: covered by `pylibjpeg-openjpeg` and sometimes Pillow/GDCM depending on bit depth and samples.
- JPEG-LS: covered by `pyjpegls` and also listed under `pylibjpeg-libjpeg` support.
- RLE: covered by `pylibjpeg-rle` and pydicom's own RLE support.
- Uncompressed transfer syntaxes: no decoder plugin needed.

Primary references checked while writing this note:

- pydicom plugin table: <https://pydicom.github.io/pydicom/stable/guides/plugin_table.html>
- pydicom decoder plugin API: <https://pydicom.github.io/pydicom/stable/guides/decoding/decoder_plugins.html>
- `pylibjpeg-libjpeg` README: <https://github.com/pydicom/pylibjpeg-libjpeg>
- Pillow license: <https://github.com/python-pillow/Pillow/blob/main/LICENSE>
- libjpeg-turbo license: <https://github.com/libjpeg-turbo/libjpeg-turbo/blob/main/LICENSE.md>

## Summary recommendation

Use a staged decision path:

1. Test a Pillow-only build without `pylibjpeg-libjpeg`.
2. If representative customer data still decodes acceptably, remove `pylibjpeg-libjpeg` from the default/commercial profile and improve missing-decoder messaging.
3. If coverage is not good enough, test `python-gdcm` as the next practical decoder option.
4. Treat a custom PyTurboJPEG/libjpeg-turbo pydicom plugin as a deeper engineering fallback, not the first replacement.
5. Keep `pylibjpeg-libjpeg` only in a clearly separated GPL-compatible or user-managed profile if a product decision allows that.

## Option matrix

| Option | Expected license posture | Engineering effort | Expected coverage | First use case |
|--------|--------------------------|--------------------|-------------------|----------------|
| A. Pillow-only | Permissive MIT-CMU style Pillow license | Low | Good for JPEG Baseline 8-bit; limited for 12-bit/extended/lossless paths | First experiment and likely default for CT/MR-heavy users |
| B. Omit plugin and warn | Removes GPL plugin from shipped build | Low to medium | Whatever remaining installed handlers cover | Lightweight/commercial profile where unsupported JPEG files can fail gracefully |
| C. GDCM / `python-gdcm` | Copyleft/notice obligations need review, often treated as weaker than GPL app-source exposure | Medium | Broad DICOM JPEG coverage, but still has known pydicom plugin limits | If Pillow-only fails on important CR/DX/XA/US data |
| D. PyTurboJPEG / libjpeg-turbo custom plugin | libjpeg-turbo is BSD/IJG-style, but Python wrapper/wheel must be verified | High | Potentially strong classic JPEG baseline performance; DICOM integration unproven in this repo | Engineering fallback when GDCM is undesirable |
| E. User-installed decoder pack | App avoids bundling GPL decoder by default | Medium | Depends on what user installs | Power-user or site-managed deployments |
| F. GPL-compatible distribution profile | GPL-compatible if app source/license path permits | Low technically, high product/legal impact | Keeps current behavior | Open-source/GPL build or internal-only experiments |

## Option A - Pillow-only

### Integration plan

- Remove `pylibjpeg-libjpeg` from a test branch or optional commercial profile.
- Keep Pillow installed; it is already part of the app stack.
- Confirm pydicom's `pillow` plugin is available at runtime.
- Run a compressed-DICOM corpus through `ds.pixel_array` and record transfer syntax, modality, photometric interpretation, bits allocated/stored, samples per pixel, success/failure, and visible output checks.
- Update missing-decoder messages so they do not tell commercial-profile users to install GPL components by default.

### Expected limitations and risks

- pydicom lists Pillow support for JPEG Baseline and JPEG Extended, but its known limitations include JPEG Extended 12-bit only when Bits Allocated is 8.
- Pillow's JPEG 2000 path is limited for some cases, though JPEG 2000 is not the main `pylibjpeg-libjpeg` replacement problem.
- Lossless classic JPEG coverage is likely weaker than `pylibjpeg-libjpeg` or GDCM.
- Color conversion and photometric interpretation behavior may differ from the current plugin path, especially for YBR/RGB data.
- Lossy JPEG pixel values may differ numerically by decoder. Visual QA is not enough for quantitative workflows.

### How easy is it?

This is the easiest path. The main work is testing and messaging, not integration.

### What would count as success?

- CT/MR-focused workflows still open all representative compressed samples.
- Known unsupported cases produce a clear, non-crashing unsupported-decoder message.
- License gate no longer needs an accepted exception for `pylibjpeg-libjpeg`.

## Option B - Omit the plugin and warn on failure

### Integration plan

- Define a `core` or commercial profile that does not install `pylibjpeg-libjpeg`.
- Keep `pylibjpeg`, `pylibjpeg-openjpeg`, `pylibjpeg-rle`, `pyjpegls`, and Pillow only if their licenses remain acceptable for the chosen profile.
- Add a decoder capability check that maps transfer syntax UID to installed support and user-facing explanation.
- Make file loading fail gracefully per series/image instead of collapsing the whole load.

### Expected limitations and risks

- Some JPEG Baseline, JPEG Extended, and JPEG Lossless DICOM files will not open.
- Users may perceive this as a product regression if they have CR/DX/XA/US or older compressed archives.
- Site support burden increases unless the unsupported-transfer-syntax message is excellent.
- If users install GPL decoder packs themselves, support and compliance boundaries must be documented plainly.

### How easy is it?

Low implementation effort if paired with Pillow-only testing. Medium product risk because it intentionally accepts reduced coverage.

### What would count as success?

- Unsupported files are identified by transfer syntax and decoder requirement.
- The lightweight profile is honest: it advertises basic DICOM support, not universal compressed DICOM support.
- User docs describe how to choose the full/open decoder profile if offered.

## Option C - GDCM / python-gdcm

### Integration plan

- Spike `python-gdcm` installation on supported Python versions and Windows/macOS/Linux targets.
- Verify pydicom's `gdcm` plugin is available and selected for target transfer syntaxes.
- Run the same compressed-DICOM corpus used for Pillow-only testing.
- Validate PyInstaller/frozen-build discovery of GDCM native libraries.
- Compare license obligations with the planned closed-source distribution model.

### Expected limitations and risks

- pydicom lists GDCM support for classic JPEG paths, but also lists plugin limitations: for example, JPEG Extended 12-bit only if Bits Allocated is 8, JPEG-LS restrictions for some bit depths, and maximum Bits Stored of 16.
- Wheel availability and native-library packaging can be the real blocker, not Python code.
- GDCM may add significant bundle size.
- It may still impose notice/relink/source-availability obligations depending on the exact package/license path. This is not a "no compliance work" option.
- Decoder output can differ from `pylibjpeg-libjpeg`; quantitative and color-image checks are still required.

### How easy is it?

Medium. pydicom already knows about GDCM, but packaging, platform coverage, and license review make this more work than Pillow-only.

### What would count as success?

- The app can decode representative JPEG Baseline/Extended/Lossless samples without `pylibjpeg-libjpeg`.
- Frozen builds include the needed native libraries reliably.
- Legal/release review accepts the obligations for the target distribution model.

## Option D - PyTurboJPEG / libjpeg-turbo custom plugin

### Integration plan

- Verify the specific Python wrapper and binary distribution license, not just upstream `libjpeg-turbo`.
- Build a pydicom decoder plugin using the documented decoder plugin API.
- Map pydicom runner metadata to TurboJPEG inputs and output buffers.
- Handle DICOM-specific details explicitly: bit depth, color space, planar configuration, photometric interpretation, encapsulated frames, and failure fallback.
- Package and test native library discovery in frozen builds.

### Expected limitations and risks

- This is not currently wired into pydicom in this repo.
- TurboJPEG is primarily attractive for classic JPEG; it is not a replacement for JPEG 2000, JPEG-LS, or RLE.
- DICOM JPEG Extended/lossless coverage may not match `pylibjpeg-libjpeg` without additional work.
- Custom decoder code becomes ours to maintain and validate.
- Bugs here are high-risk because they can silently produce wrong pixels rather than obvious failures.

### How easy is it?

High effort. Technically appealing, but it is a real feature project.

### What would count as success?

- A small pydicom plugin passes synthetic and real compressed-DICOM tests.
- Pixel output matches a trusted decoder within expected tolerance for lossy cases and exactly for lossless cases.
- Frozen builds work without manual library path setup.

## Option E - User-installed decoder pack

### Integration plan

- Ship the app without `pylibjpeg-libjpeg`.
- Detect when a missing transfer syntax could be solved by optional decoders.
- Offer site/admin documentation for installing optional decoder packs into a managed environment.
- Keep the default application messaging license-neutral and product-profile-aware.

### Expected limitations and risks

- On-demand installs may not be acceptable in clinical, locked-down, or offline environments.
- Support becomes more complex because decode behavior varies by site.
- The user/site may still need to understand GPL obligations if they install GPL decoders.
- Reproducibility across deployments gets worse unless the decoder environment is logged.

### How easy is it?

Medium. The coding is mostly capability detection and messaging; the hard part is support policy.

### What would count as success?

- About/System Info lists installed decoder plugins and versions.
- Error messages identify both the missing transfer syntax and possible optional decoder path.
- QA reports/export logs record decoder backend for traceability.

## Option F - GPL-compatible distribution profile

### Integration plan

- Keep `pylibjpeg-libjpeg`.
- Choose a GPL-compatible product/source distribution strategy.
- Make the dependency and source-offer obligations explicit in release docs.

### Expected limitations and risks

- This may be incompatible with a proprietary closed-source commercial product.
- Customers may receive rights to redistribute under GPL terms.
- A mixed SKU strategy can be confusing unless the open/GPL and commercial profiles are sharply separated.

### How easy is it?

Technically easy, product/legal impact high.

### What would count as success?

- The product strategy intentionally accepts GPL obligations.
- Release docs, license files, and source availability match that choice.

## Test corpus needed

At minimum, create or collect small, non-PHI fixtures for:

- JPEG Baseline 8-bit monochrome.
- JPEG Baseline 8-bit color, including YBR/RGB cases if available.
- JPEG Extended 12-bit.
- JPEG Lossless process 14.
- JPEG Lossless first-order prediction.
- JPEG-LS and JPEG 2000 controls to ensure replacements do not regress unrelated paths.
- RLE control.
- Uncompressed control.

For each sample record:

- transfer syntax UID,
- modality,
- samples per pixel,
- photometric interpretation,
- bits allocated/stored,
- planar configuration,
- decoder backend used,
- success/failure,
- pixel hash or tolerance-based comparison to a trusted decoder,
- visual smoke result.

## Implementation guardrails

- Keep decoder detection in a focused core module rather than scattering string checks for `pylibjpeg`.
- Do not make the GUI depend on import errors for normal control flow.
- Preserve a clear unsupported-transfer-syntax user message.
- Log decoder backend/version in debug diagnostics and future QA provenance where compressed input may affect numerical results.
- Keep commercial/default requirements separate from optional/GPL or full-research profiles if multiple profiles are adopted.

## Proposed next steps

1. Create a `no-pylibjpeg-libjpeg` spike branch.
2. Remove only `pylibjpeg-libjpeg`; keep other accepted decoders unchanged.
3. Run the compressed-DICOM corpus and app smoke tests.
4. Record failures by transfer syntax and modality.
5. Decide whether Pillow-only is good enough for the default/commercial profile.
6. If not, run the same corpus against GDCM.
7. Only start PyTurboJPEG custom-plugin work if both Pillow-only and GDCM are rejected.

## Decoder options landscape & licenses (2026-06-14 spike findings)

Full non-GPL decoder landscape for the **at-risk classic JPEG** syntaxes
(`.50` Baseline, `.51` Extended, `.57` Lossless P14, `.70` Lossless P14 SV1). Spike results
recorded in [`DECODER_REPLACEMENT_SPIKE_PLAN.md`](../plans/supporting/DECODER_REPLACEMENT_SPIKE_PLAN.md).

| Decoder | License | At-risk JPEG coverage | Drop-in with current **pydicom 2.4.5**? |
|---------|---------|-----------------------|------------------------------------------|
| **GDCM** (`python-gdcm`) | **LGPL** | **Full** (spike: 0 failures, lossless bit-exact, `.57` bit-exact) | ✅ Registered pydicom handler today — **recommended** |
| **imagecodecs** (cgohlke) | **BSD-3** (most permissive) | Full — incl. lossless JPEG (`jpegsof3`/`ljpeg`), 12-bit | ⚠️ **pydicom 3.x plugin only** — not a 2.4.5 handler |
| **Pillow** | MIT/HPND | Partial — drops lossless (`.57/.70`) + 12-bit extended (`.51`) | ✅ but incomplete (spike: 7 failures) |
| **PyTurboJPEG / libjpeg-turbo** | BSD/IJG | Lossy baseline/extended only; lossless weak | ✗ no pydicom integration; not full |
| **DCMTK** CLI (`dcmdjpeg`) | OFFIS (BSD-like) | Full | ✗ shell-out to bundled binaries; heavy to package |
| **nvImageCodec** (NVIDIA) | proprietary, **CUDA/GPU** | Full, GPU-accelerated | ✗ needs NVIDIA GPU — not viable on the dev Parallels/CPU setup |

**Conclusion:** with **pydicom 2.4.5**, **GDCM (LGPL) is effectively the only drop-in non-GPL
full-coverage decoder**. LGPL is commercially acceptable (same compliance path as PySide6/Qt).

**imagecodecs is the most license-clean (BSD) full-coverage engine**, but it is a **pydicom 3.x**
decoder plugin. **pydicom 3.x is currently blocked by `pylinac` → `pydicom<3,>=2.0`** — the
*same* ceiling that blocks `highdicom` (see [`HIGHDICOM_OVERVIEW.md`](HIGHDICOM_OVERVIEW.md) §4a).
**Checked 2026-06-14:** even the **latest pylinac (3.44.0 PyPI / 3.45.0 dev)** *still* caps
`pydicom<3` — pylinac is actively developed (frequent 3.4x minor releases) but has **not** dropped
the cap. So this path is **blocked upstream**: a pylinac bump alone won't help; it requires pylinac
to first support pydicom 3. When that lands, a coordinated pydicom 3 + pylinac bump (re-verify ACR
QA) would unblock imagecodecs **and** highdicom. Tracked as a TO_DO.

**What actually breaks pylinac under pydicom 3 (source inspection, pylinac 3.43.2):** the concrete
dependency is `pylinac/core/image.py` → `import pydicom.pixel_data_handlers as pixels` and its call
`pixels.apply_rescale(...)`. pydicom 3.0 **reorganized `pixel_data_handlers` into `pydicom.pixels`**
(rescale/VOI/windowing now in `pydicom.pixels.processing`). pylinac's `pydicom.uid` imports
(`ExplicitVRLittleEndian, RTImageStorage, SecondaryCaptureImageStorage, generate_uid, UID`) are all
**still present** in v3, and pylinac references **none** of the removed UID constants
(`JPEGBaseline`/`JPEGExtended`/`JPEGLSLossy`/`PersonNameUnicode`). So the breakage surface looks
**small** — the `<3` cap may be more conservative than strictly necessary. **A pydicom-3 spike venv
(force-install past the cap, then run an ACR CT/MRI demo) is worth doing** to see whether pylinac
actually works; if so, the imagecodecs/highdicom path opens up sooner than waiting on upstream.

**Spike done 2026-06-14 — pylinac 3.43.2 works under pydicom 3.0.2.** Force-installed
`pydicom==3.0.2` past the cap (`pip install --no-deps "pydicom>=3"`); `import pylinac` and
`from pylinac import ACRCT, ACRMRILarge` succeed. Offline analyses give **identical** results on
both pydicom 2.4.5 and 3.0.2: **CatPhan504** (CT) `measured_slice_thickness_mm=2.4866`,
`origin_slice=32.0`; **QuartDVT** (MRI) `phantom_model="Quart DVT"`, same modules. pydicom 3.0.2
still ships the `pixel_data_handlers` shim incl. `apply_rescale`, so pylinac's suspect call path
doesn't break. **Update — the app's real ACR modules also validated identical under pydicom 3**
(run via `qa.run_acr_ct_analysis` / `run_acr_mri_large_analysis` on local fixtures): **ACR CT**
`success=True`, 25 images; **ACR MRI Large** `success=True`, 11 images, `low_contrast_score=10`,
`origin_slice=0` — byte-for-byte identical metrics on pydicom 2.4.5 vs 3.0.2 (compared the full
`raw_pylinac` results: CT module ROIs, uniformity, low-contrast CNR, spatial-resolution MTF — all
identical except the analysis timestamp). (pylinac demo ACR zips don't exist; used local data.)
**Nuclear also validated identical** under pydicom 3 — **8/8** types succeed with byte-identical
results (planar uniformity, four-bar, quadrant, center-of-rotation, tomographic resolution,
max-count-rate, tomographic uniformity, tomographic contrast); SimpleSensitivity (multi-file)
not run. **Conclusion:** the `pydicom<3` cap is conservative; a future app bump
to pydicom 3 (overriding pylinac's metadata cap, which is safe for a controlled PyInstaller build)
looks viable pending a full DEPENDENCY_BUMP_VERIFICATION pass (real ACR CT/MRI data + pylinac suite).

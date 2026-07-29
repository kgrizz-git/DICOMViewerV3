# Synthetic DICOM decoder fixtures

## Role

These tiny, wholly synthetic Secondary Capture files exercise the decoder
replacement without using a public study or PACS export.

| Fixture | Transfer syntax / purpose | Pixel contract |
|---|---|---|
| `synthetic_rgb_no_color_markers_jpeg_baseline.dcm` | JPEG Baseline `.50`; no JFIF APP0 or Adobe APP14 marker, but DICOM metadata and component IDs declare RGB | Independently confirmed RGB output; color-block pattern |
| `synthetic_monochrome_jpeg_extended_12_bit.dcm` | JPEG Extended `.51`; valid 12-bit SOF1 codestream | Independently confirmed lossy-decoder output |
| `synthetic_monochrome_jpeg_lossless_p14.dcm` | JPEG Lossless Process 14 `.57` | Exact match to 12-bit source pattern |
| `synthetic_monochrome_jpeg_lossless_sv1.dcm` | JPEG Lossless first-order `.70` | Exact match to 12-bit source pattern |
| `synthetic_monochrome_jpegls_lossless.dcm` | JPEG-LS `.80` control | Exact match to 12-bit source pattern |
| `synthetic_monochrome_jpeg2000_lossless_16_bit.dcm` | JPEG 2000 lossless `.90` control | Exact match to 16-bit source pattern |
| `synthetic_monochrome_rle_lossless.dcm` | RLE `.5` control | Exact match to 12-bit source pattern |
| `synthetic_monochrome_uncompressed_12_bit.dcm` / `synthetic_monochrome_uncompressed_16_bit.dcm` | Explicit VR Little Endian controls and the known source patterns | Exact known source patterns |

The RGB image is a color-block pattern; monochrome images are deterministic
grayscale patterns. None contains rendered text.

This fixture is a decoder regression input only. It is not clinical data and must
not be used for diagnostic or quantitative validation.

## Provenance and regeneration

- **Source:** Generated in-repo by
  `tests/scripts/generate_decoder_color_fixture.py` and
  `tests/scripts/generate_decoder_transfer_syntax_fixtures.py`; no external
  DICOM file or PACS export is used.
- **Generator dependencies:** libjpeg-turbo `cjpeg -rgb` creates the embedded
  RGB JPEG stream; `cjpeg -precision 12` creates the valid `.51` JPEG Extended
  stream independently of GDCM; `python-gdcm` creates the other compressed
  matrix members from deterministic uncompressed patterns. These are local
  fixture-generation tools, not application dependencies.
- **Regenerate:** with the project venv active, libjpeg-turbo installed, and an
  isolated GDCM environment available, run the color generator followed by
  `python tests/scripts/generate_decoder_transfer_syntax_fixtures.py` from the
  repository root. The latter script prints a clear error when GDCM is absent.
- **Reference rule:** GDCM must not be treated as the decoder oracle merely
  because it encoded some fixtures. Lossless fixtures are compared to their
  known source patterns; the `.50` and `.51` expected outputs were checked with
  both DCMTK and dcm4che before becoming GDCM regression hashes.
- **After regeneration:** visually review every rendered pattern and update its
  SHA-256 entry in `security/approved-media-sha256.json` through the normal
  artifact-review process.

## De-identification and scope

- Patient Name and Patient ID are present only as empty Type 2 values.
- No accession, institution, station, device, date, time, or real UID values are
  included. Stable fixture UIDs are derived from fixed synthetic labels.
- The test suite verifies the lack of identifying values, transfer-syntax and
  pixel metadata, RGB component identifiers and absence of APP0/APP14 markers,
  lossless source hashes, and independently confirmed GDCM outputs when GDCM is
  installed.

## License

The generator and generated color pattern are project-created test material.
DICOM attribute names and transfer-syntax UIDs are standard identifiers published
by NEMA; no external DICOM binary is included.

# Synthetic DICOM decoder fixtures

## Role

`synthetic_rgb_no_color_markers_jpeg_baseline.dcm` is a tiny, wholly synthetic
Secondary Capture image used to test an RGB JPEG Baseline interoperability edge.
Its JPEG codestream deliberately contains neither a JFIF APP0 nor Adobe APP14
color marker, while its DICOM metadata and JPEG component IDs explicitly declare
RGB. The image is a color-block pattern with no rendered text.

This fixture is a decoder regression input only. It is not clinical data and must
not be used for diagnostic or quantitative validation.

## Provenance and regeneration

- **Source:** Generated in-repo by
  `tests/scripts/generate_decoder_color_fixture.py`; no external DICOM file or
  PACS export is used.
- **Generator dependency:** `cjpeg -rgb` from libjpeg-turbo creates the embedded
  RGB JPEG stream. It is a local fixture-generation tool, not an application
  dependency.
- **Regenerate:** with the project venv active and libjpeg-turbo installed, run
  `python tests/scripts/generate_decoder_color_fixture.py` from the repository
  root.
- **After regeneration:** perform a visual review of the color-block image and
  update its SHA-256 entry in `security/approved-media-sha256.json` through the
  normal artifact-review process.

## De-identification and scope

- Patient Name and Patient ID are present only as empty Type 2 values.
- No accession, institution, station, device, date, time, or real UID values are
  included. Stable fixture UIDs are derived from fixed synthetic labels.
- The test suite verifies the lack of identifying values, JPEG transfer syntax,
  RGB metadata, RGB component identifiers, and absence of APP0/APP14 markers.

## License

The generator and generated color pattern are project-created test material.
DICOM attribute names and transfer-syntax UIDs are standard identifiers published
by NEMA; no external DICOM binary is included.

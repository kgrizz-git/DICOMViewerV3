"""Public, privacy-safe contract for the reviewed synthetic decoder fixtures."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DecoderFixtureExpectation:
    """Expected decoded result for one committed wholly synthetic fixture."""

    filename: str
    transfer_syntax_uid: str
    pixel_sha256: str
    allowed_stderr: bytes = b""


GDCM_12_BIT_FALLBACK_DIAGNOSTIC = b"Unsupported JPEG data precision 12\n"

DECODER_FIXTURE_EXPECTATIONS = (
    DecoderFixtureExpectation(
        "synthetic_rgb_no_color_markers_jpeg_baseline.dcm",
        "1.2.840.10008.1.2.4.50",
        "9d2130c830f7b173b355f25270a9eacbac1f5045acebd757a7f9264a1ef03c28",
    ),
    DecoderFixtureExpectation(
        "synthetic_monochrome_uncompressed_12_bit.dcm",
        "1.2.840.10008.1.2.1",
        "05c899747e8b1cbb4eeef12f342374b56424ed3932572f79d928a89e2f25f68e",
    ),
    DecoderFixtureExpectation(
        "synthetic_monochrome_uncompressed_16_bit.dcm",
        "1.2.840.10008.1.2.1",
        "f5ca7eb45ebf49f510773f1fb5a4edb8978a7116a4116d0bebe0d4f5e79d0332",
    ),
    DecoderFixtureExpectation(
        "synthetic_monochrome_jpeg_extended_12_bit.dcm",
        "1.2.840.10008.1.2.4.51",
        "8cb01fc3dac525da7d1868dfb1b8aaf8524f75dbf226712c579eb0f226a1b6dc",
        GDCM_12_BIT_FALLBACK_DIAGNOSTIC,
    ),
    DecoderFixtureExpectation(
        "synthetic_monochrome_jpeg_lossless_p14.dcm",
        "1.2.840.10008.1.2.4.57",
        "05c899747e8b1cbb4eeef12f342374b56424ed3932572f79d928a89e2f25f68e",
    ),
    DecoderFixtureExpectation(
        "synthetic_monochrome_jpeg_lossless_sv1.dcm",
        "1.2.840.10008.1.2.4.70",
        "05c899747e8b1cbb4eeef12f342374b56424ed3932572f79d928a89e2f25f68e",
    ),
    DecoderFixtureExpectation(
        "synthetic_monochrome_jpegls_lossless.dcm",
        "1.2.840.10008.1.2.4.80",
        "05c899747e8b1cbb4eeef12f342374b56424ed3932572f79d928a89e2f25f68e",
    ),
    DecoderFixtureExpectation(
        "synthetic_monochrome_jpeg2000_lossless_16_bit.dcm",
        "1.2.840.10008.1.2.4.90",
        "f5ca7eb45ebf49f510773f1fb5a4edb8978a7116a4116d0bebe0d4f5e79d0332",
    ),
    DecoderFixtureExpectation(
        "synthetic_monochrome_rle_lossless.dcm",
        "1.2.840.10008.1.2.5",
        "05c899747e8b1cbb4eeef12f342374b56424ed3932572f79d928a89e2f25f68e",
    ),
)

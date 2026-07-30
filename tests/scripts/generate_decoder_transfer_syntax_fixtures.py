"""Generate wholly synthetic decoder fixtures for the production GDCM matrix.

The fixtures share one deterministic 12-bit MONOCHROME2 pixel pattern and cover
the classic JPEG transfer syntaxes being moved from ``pylibjpeg-libjpeg`` to
GDCM, together with JPEG-LS, JPEG 2000, RLE, and uncompressed controls.  The
lossless output is checked against the source pattern; JPEG Extended is kept as
a decode-and-independent-reference case because its compression is lossy.

``python-gdcm`` is required only to generate the compressed fixtures.  It is a
local validation tool, not an application dependency.  Run this script from the
repository root in an isolated GDCM environment, for example::

    /private/tmp/dicom-gdcm-pydicom2/bin/python \
        tests/scripts/generate_decoder_transfer_syntax_fixtures.py

After regeneration, run the fixture tests, visually review the rendered
patterns, and update ``security/approved-media-sha256.json`` through the normal
review process before committing any generated DICOM file.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.encaps import encapsulate
from pydicom.filewriter import dcmwrite
from pydicom.uid import (
    PYDICOM_IMPLEMENTATION_UID,
    ExplicitVRLittleEndian,
    SecondaryCaptureImageStorage,
)

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.generate_decoder_fixtures import SYNTAX_MAP, transcode

FIXTURE_DIR = Path("tests/fixtures/dicom_decoder")
ROWS = 48
COLUMNS = 64
_SOURCE_NAME = "synthetic_monochrome_uncompressed_12_bit.dcm"
_JPEG2000_SOURCE_NAME = "synthetic_monochrome_uncompressed_16_bit.dcm"
_JPEG2000_NAME = "synthetic_monochrome_jpeg2000_lossless_16_bit.dcm"
_COMPRESSED_FIXTURES: tuple[tuple[str, str], ...] = (
    ("synthetic_monochrome_jpeg_lossless_p14.dcm", "jpeg_lossless_p14"),
    ("synthetic_monochrome_jpeg_lossless_sv1.dcm", "jpeg_lossless_sv1"),
    ("synthetic_monochrome_jpegls_lossless.dcm", "jpegls_lossless"),
    ("synthetic_monochrome_rle_lossless.dcm", "rle"),
)


def source_pixels() -> bytes:
    """Return deterministic little-endian 12-bit samples stored in 16 bits."""
    values = bytearray()
    for row in range(ROWS):
        for column in range(COLUMNS):
            value = (row * 73 + column * 29 + (row * column) % 127) % 4096
            values.extend(value.to_bytes(2, byteorder="little"))
    return bytes(values)


def source_pixels_16_bit() -> bytes:
    """Return a second deterministic pattern spanning the full unsigned 16-bit range."""
    values = bytearray()
    for row in range(ROWS):
        for column in range(COLUMNS):
            value = (row * 1237 + column * 811 + row * column * 17) % 65536
            values.extend(value.to_bytes(2, byteorder="little"))
    return bytes(values)


def _synthetic_uid(label: str) -> str:
    """Return a stable UID derived solely from a fixed synthetic label."""
    fixture_uuid = uuid.uuid5(uuid.NAMESPACE_URL, f"dicom-viewer-v3/{label}")
    return f"2.25.{fixture_uuid.int}"


def build_source_fixture(
    label: str = "decoder-matrix-source",
    *,
    bits_stored: int = 12,
    pixels: bytes | None = None,
) -> FileDataset:
    """Build the minimal, wholly synthetic uncompressed Secondary Capture image."""
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
    file_meta.MediaStorageSOPInstanceUID = _synthetic_uid(f"{label}-sop-instance")
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.ImplementationClassUID = PYDICOM_IMPLEMENTATION_UID

    dataset = FileDataset(None, {}, file_meta=file_meta, preamble=b"\0" * 128)
    dataset.is_implicit_VR = False
    dataset.is_little_endian = True
    dataset.SpecificCharacterSet = "ISO_IR 100"
    dataset.SOPClassUID = SecondaryCaptureImageStorage
    dataset.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    dataset.PatientName = ""
    dataset.PatientID = ""
    dataset.StudyInstanceUID = _synthetic_uid(f"{label}-study-instance")
    dataset.SeriesInstanceUID = _synthetic_uid(f"{label}-series-instance")
    dataset.StudyDate = ""
    dataset.StudyTime = ""
    dataset.SeriesDate = ""
    dataset.SeriesTime = ""
    dataset.ContentDate = ""
    dataset.ContentTime = ""
    dataset.Modality = "OT"
    dataset.ConversionType = "WSD"
    dataset.ImageType = ["DERIVED", "SECONDARY"]
    dataset.SeriesDescription = "Synthetic grayscale decoder matrix fixture"
    dataset.SeriesNumber = 1
    dataset.InstanceNumber = 1
    dataset.Manufacturer = "DICOMViewerV3 synthetic fixture"
    dataset.BurnedInAnnotation = "NO"
    dataset.Rows = ROWS
    dataset.Columns = COLUMNS
    dataset.SamplesPerPixel = 1
    dataset.PhotometricInterpretation = "MONOCHROME2"
    dataset.BitsAllocated = 16
    dataset.BitsStored = bits_stored
    dataset.HighBit = bits_stored - 1
    dataset.PixelRepresentation = 0
    dataset.PixelData = pixels if pixels is not None else source_pixels()
    return dataset


def _pgm_12_bit_bytes() -> bytes:
    """Return the source pattern as a 12-bit PGM for libjpeg-turbo's encoder."""
    samples = source_pixels()
    big_endian_samples = bytearray()
    for offset in range(0, len(samples), 2):
        value = int.from_bytes(samples[offset : offset + 2], byteorder="little")
        big_endian_samples.extend(value.to_bytes(2, byteorder="big"))
    return f"P5\n{COLUMNS} {ROWS}\n4095\n".encode("ascii") + bytes(big_endian_samples)


def _jpeg_extended_precision(payload: bytes) -> tuple[int, int, int]:
    """Return the SOF marker, sample precision, and component count of a JPEG frame."""
    if payload[:2] != b"\xff\xd8":
        raise ValueError("Expected a JPEG Start Of Image marker")

    position = 2
    while position < len(payload):
        if payload[position] != 0xFF:
            raise ValueError("Expected a JPEG marker in the header")
        while position < len(payload) and payload[position] == 0xFF:
            position += 1
        if position >= len(payload):
            raise ValueError("Truncated JPEG marker")
        marker = payload[position]
        position += 1
        if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
            continue
        if position + 2 > len(payload):
            raise ValueError("Truncated JPEG segment length")
        segment_length = int.from_bytes(payload[position : position + 2], "big")
        segment_end = position + segment_length
        if segment_length < 2 or segment_end > len(payload):
            raise ValueError("Invalid JPEG segment length")
        if marker == 0xDA:
            break
        if marker in {0xC0, 0xC1, 0xC2, 0xC3}:
            return marker, payload[position + 2], payload[position + 7]
        position = segment_end
    raise ValueError("Expected a JPEG Start Of Frame marker")


def _write_jpeg_extended_fixture(destination: Path, cjpeg: str) -> None:
    """Create a valid 12-bit JPEG Extended fixture without using GDCM's encoder."""
    with tempfile.TemporaryDirectory(prefix="dicom-decoder-extended-") as temp_dir:
        source = Path(temp_dir) / "source.pgm"
        frame_path = Path(temp_dir) / "frame.jpg"
        source.write_bytes(_pgm_12_bit_bytes())
        subprocess.run(
            [
                cjpeg,
                "-precision",
                "12",
                "-quality",
                "100",
                "-outfile",
                str(frame_path),
                str(source),
            ],
            check=True,
            capture_output=True,
        )
        frame = frame_path.read_bytes()

    if _jpeg_extended_precision(frame) != (0xC1, 12, 1):
        raise RuntimeError("Expected a 12-bit, single-component JPEG Extended (SOF1) frame")

    dataset = build_source_fixture("decoder-matrix-jpeg-extended")
    dataset.file_meta.TransferSyntaxUID = "1.2.840.10008.1.2.4.51"
    dataset.PixelData = encapsulate([frame])
    dataset["PixelData"].is_undefined_length = True
    dataset.LossyImageCompression = "01"
    dataset.LossyImageCompressionMethod = "ISO_10918_1"
    dcmwrite(destination, dataset, write_like_original=False)


def _apply_synthetic_identity(path: Path, label: str) -> None:
    """Give each transcoded fixture distinct stable UIDs without changing pixels."""
    import pydicom

    dataset = pydicom.dcmread(path)
    dataset.SOPInstanceUID = _synthetic_uid(f"{label}-sop-instance")
    dataset.file_meta.MediaStorageSOPInstanceUID = dataset.SOPInstanceUID
    dataset.StudyInstanceUID = _synthetic_uid(f"{label}-study-instance")
    dataset.SeriesInstanceUID = _synthetic_uid(f"{label}-series-instance")
    dcmwrite(path, dataset, write_like_original=False)


def generate(out_dir: Path, cjpeg: str) -> tuple[Path, ...]:
    """Write the source and each compressed fixture, returning their paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="dicom-decoder-matrix-") as temp_dir:
        source_path = Path(temp_dir) / _SOURCE_NAME
        dcmwrite(source_path, build_source_fixture(), write_like_original=False)
        jpeg2000_source_path = Path(temp_dir) / _JPEG2000_SOURCE_NAME
        dcmwrite(
            jpeg2000_source_path,
            build_source_fixture(
                "decoder-matrix-jpeg2000-source",
                bits_stored=16,
                pixels=source_pixels_16_bit(),
            ),
            write_like_original=False,
        )

        destination_paths = [out_dir / _SOURCE_NAME]
        dcmwrite(destination_paths[0], build_source_fixture(), write_like_original=False)
        jpeg2000_source = out_dir / _JPEG2000_SOURCE_NAME
        dcmwrite(
            jpeg2000_source,
            build_source_fixture(
                "decoder-matrix-jpeg2000-source",
                bits_stored=16,
                pixels=source_pixels_16_bit(),
            ),
            write_like_original=False,
        )
        destination_paths.append(jpeg2000_source)
        jpeg_extended = out_dir / "synthetic_monochrome_jpeg_extended_12_bit.dcm"
        _write_jpeg_extended_fixture(jpeg_extended, cjpeg)
        destination_paths.append(jpeg_extended)
        for filename, syntax_key in _COMPRESSED_FIXTURES:
            destination = out_dir / filename
            actual_uid = transcode(str(source_path), str(destination), syntax_key)
            expected_uid = SYNTAX_MAP[syntax_key][1]
            if actual_uid != expected_uid:
                raise RuntimeError(
                    f"{filename} has transfer syntax {actual_uid}, expected {expected_uid}"
                )
            _apply_synthetic_identity(destination, f"decoder-matrix-{syntax_key}")
            destination_paths.append(destination)
        jpeg2000 = out_dir / _JPEG2000_NAME
        actual_uid = transcode(str(jpeg2000_source_path), str(jpeg2000), "jpeg2000_lossless")
        expected_uid = SYNTAX_MAP["jpeg2000_lossless"][1]
        if actual_uid != expected_uid:
            raise RuntimeError(
                f"{_JPEG2000_NAME} has transfer syntax {actual_uid}, expected {expected_uid}"
            )
        _apply_synthetic_identity(jpeg2000, "decoder-matrix-jpeg2000-lossless")
        destination_paths.append(jpeg2000)
    return tuple(destination_paths)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=FIXTURE_DIR,
        help="Output directory (default: tests/fixtures/dicom_decoder).",
    )
    parser.add_argument(
        "--cjpeg",
        default=shutil.which("cjpeg"),
        help="Path to libjpeg-turbo cjpeg (default: locate on PATH).",
    )
    args = parser.parse_args()
    if not args.cjpeg:
        raise SystemExit("cjpeg from libjpeg-turbo is required to generate JPEG Extended")

    for fixture in generate(args.out_dir, args.cjpeg):
        print(f"Generated synthetic decoder fixture: {fixture.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Generate the synthetic marker-less RGB JPEG Baseline DICOM decoder fixture.

The fixture intentionally covers an interoperability edge: a JPEG Baseline frame
whose codestream has neither JFIF APP0 nor Adobe APP14 color markers.  The DICOM
metadata declares ``PhotometricInterpretation = RGB`` and the JPEG frame uses RGB
components, so a decoder must honor the DICOM metadata rather than infer the
color model from a missing marker.

The generator creates only wholly synthetic color blocks.  It writes no patient,
institution, accession, or device identifiers.  ``cjpeg -rgb`` from libjpeg-turbo
is required to produce the RGB JPEG codestream; it is a fixture-generation tool,
not an application dependency.

Run from the repository root with the project venv active::

    python tests/scripts/generate_decoder_color_fixture.py

After regenerating, visually review the result and update
``security/approved-media-sha256.json`` through the normal artifact-review flow.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.encaps import encapsulate
from pydicom.filewriter import dcmwrite
from pydicom.uid import (
    PYDICOM_IMPLEMENTATION_UID,
    JPEGBaseline8Bit,
    SecondaryCaptureImageStorage,
)

FIXTURE_NAME = "synthetic_rgb_no_color_markers_jpeg_baseline.dcm"
FIXTURE_DIR = Path("tests/fixtures/dicom_decoder")
BLOCK_SIZE = 16
BLOCK_COLUMNS = 4
COLORS: tuple[tuple[int, int, int], ...] = (
    (255, 0, 0),
    (0, 255, 0),
    (0, 0, 255),
    (255, 255, 0),
    (0, 255, 255),
    (255, 0, 255),
    (32, 32, 32),
    (128, 128, 128),
    (224, 224, 224),
    (48, 128, 208),
    (208, 48, 128),
    (128, 208, 48),
)


def _synthetic_uid(label: str) -> str:
    """Return a stable UID derived solely from the fixture label."""
    fixture_uuid = uuid.uuid5(uuid.NAMESPACE_URL, f"dicom-viewer-v3/{label}")
    return f"2.25.{fixture_uuid.int}"


def _ppm_bytes() -> tuple[bytes, int, int]:
    """Return a small P6 RGB test pattern with no text or clinical content."""
    rows = (len(COLORS) + BLOCK_COLUMNS - 1) // BLOCK_COLUMNS
    width = BLOCK_COLUMNS * BLOCK_SIZE
    height = rows * BLOCK_SIZE
    pixels = bytearray()

    for y in range(height):
        color_row = y // BLOCK_SIZE
        for x in range(width):
            color_column = x // BLOCK_SIZE
            color_index = color_row * BLOCK_COLUMNS + color_column
            color = COLORS[color_index] if color_index < len(COLORS) else (0, 0, 0)
            pixels.extend(color)

    return f"P6\n{width} {height}\n255\n".encode("ascii") + bytes(pixels), width, height


def _jpeg_header_markers(payload: bytes) -> tuple[int, ...]:
    """Return marker codes in the JPEG header through SOS, validating its structure."""
    if payload[:2] != b"\xff\xd8":
        raise ValueError("Expected a JPEG Start Of Image marker")

    markers: list[int] = []
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
        markers.append(marker)
        if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
            continue
        if position + 2 > len(payload):
            raise ValueError("Truncated JPEG segment length")
        segment_length = int.from_bytes(payload[position : position + 2], "big")
        if segment_length < 2 or position + segment_length > len(payload):
            raise ValueError("Invalid JPEG segment length")
        if marker == 0xDA:  # Start Of Scan: entropy-coded bytes follow.
            break
        position += segment_length
    return tuple(markers)


def _rgb_component_ids(payload: bytes) -> tuple[int, int, int]:
    """Return the component IDs from the baseline JPEG Start Of Frame segment."""
    position = 2
    while position < len(payload):
        if payload[position] != 0xFF:
            raise ValueError("Expected a JPEG marker in the header")
        while position < len(payload) and payload[position] == 0xFF:
            position += 1
        marker = payload[position]
        position += 1
        if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
            continue
        segment_length = int.from_bytes(payload[position : position + 2], "big")
        segment_end = position + segment_length
        if marker == 0xC0:  # SOF0 (baseline DCT)
            component_count = payload[position + 7]
            if component_count != 3:
                raise ValueError("Expected three RGB JPEG components")
            component_start = position + 8
            return tuple(payload[component_start + index * 3] for index in range(3))  # type: ignore[return-value]
        if marker == 0xDA:
            break
        position = segment_end
    raise ValueError("Expected a baseline JPEG Start Of Frame marker")


def _strip_color_markers(payload: bytes) -> bytes:
    """Remove optional APP0/APP14 marker segments without touching JPEG image data."""
    if payload[:2] != b"\xff\xd8":
        raise ValueError("Expected a JPEG Start Of Image marker")

    result = bytearray(payload[:2])
    position = 2
    while position < len(payload):
        marker_start = position
        if payload[position] != 0xFF:
            raise ValueError("Expected a JPEG marker in the header")
        while position < len(payload) and payload[position] == 0xFF:
            position += 1
        if position >= len(payload):
            raise ValueError("Truncated JPEG marker")
        marker = payload[position]
        position += 1
        if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
            result.extend(payload[marker_start:position])
            continue
        if position + 2 > len(payload):
            raise ValueError("Truncated JPEG segment length")
        segment_length = int.from_bytes(payload[position : position + 2], "big")
        segment_end = position + segment_length
        if segment_length < 2 or segment_end > len(payload):
            raise ValueError("Invalid JPEG segment length")
        if marker == 0xDA:  # Preserve SOS and every entropy-coded byte after it.
            result.extend(payload[marker_start:])
            break
        if marker not in {0xE0, 0xEE}:
            result.extend(payload[marker_start:segment_end])
        position = segment_end
    return bytes(result)


def _create_rgb_jpeg(cjpeg: str) -> tuple[bytes, int, int]:
    """Create a no-APP-marker RGB JPEG frame using libjpeg-turbo's encoder."""
    ppm, width, height = _ppm_bytes()
    with tempfile.TemporaryDirectory(prefix="dicom-decoder-fixture-") as temp_dir:
        source = Path(temp_dir) / "source.ppm"
        destination = Path(temp_dir) / "frame.jpg"
        source.write_bytes(ppm)
        subprocess.run(
            [
                cjpeg,
                "-rgb",
                "-quality",
                "100",
                "-sample",
                "1x1,1x1,1x1",
                "-outfile",
                str(destination),
                str(source),
            ],
            check=True,
            capture_output=True,
        )
        payload = _strip_color_markers(destination.read_bytes())

    markers = _jpeg_header_markers(payload)
    if 0xE0 in markers or 0xEE in markers:
        raise RuntimeError("Fixture JPEG must omit both APP0 and APP14 color markers")
    if _rgb_component_ids(payload) != (ord("R"), ord("G"), ord("B")):
        raise RuntimeError("Fixture JPEG must contain explicit RGB component identifiers")
    return payload, width, height


def build_fixture(cjpeg: str) -> FileDataset:
    """Build the minimal Secondary Capture DICOM dataset for the color edge case."""
    jpeg, width, height = _create_rgb_jpeg(cjpeg)
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
    file_meta.MediaStorageSOPInstanceUID = _synthetic_uid("sop-instance")
    file_meta.TransferSyntaxUID = JPEGBaseline8Bit
    file_meta.ImplementationClassUID = PYDICOM_IMPLEMENTATION_UID

    dataset = FileDataset(None, {}, file_meta=file_meta, preamble=b"\0" * 128)
    dataset.is_implicit_VR = False
    dataset.is_little_endian = True
    dataset.SpecificCharacterSet = "ISO_IR 100"
    dataset.SOPClassUID = SecondaryCaptureImageStorage
    dataset.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    dataset.PatientName = ""
    dataset.PatientID = ""
    dataset.StudyInstanceUID = _synthetic_uid("study-instance")
    dataset.SeriesInstanceUID = _synthetic_uid("series-instance")
    dataset.StudyDate = ""
    dataset.StudyTime = ""
    dataset.SeriesDate = ""
    dataset.SeriesTime = ""
    dataset.ContentDate = ""
    dataset.ContentTime = ""
    dataset.Modality = "OT"
    dataset.ConversionType = "WSD"
    dataset.ImageType = ["DERIVED", "SECONDARY"]
    dataset.SeriesDescription = "Synthetic RGB JPEG decoder fixture"
    dataset.SeriesNumber = 1
    dataset.InstanceNumber = 1
    dataset.Manufacturer = "DICOMViewerV3 synthetic fixture"
    dataset.BurnedInAnnotation = "NO"
    dataset.Rows = height
    dataset.Columns = width
    dataset.SamplesPerPixel = 3
    dataset.PhotometricInterpretation = "RGB"
    dataset.PlanarConfiguration = 0
    dataset.BitsAllocated = 8
    dataset.BitsStored = 8
    dataset.HighBit = 7
    dataset.PixelRepresentation = 0
    dataset.LossyImageCompression = "01"
    dataset.LossyImageCompressionMethod = "ISO_10918_1"
    dataset.PixelData = encapsulate([jpeg])
    dataset["PixelData"].is_undefined_length = True
    return dataset


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=FIXTURE_DIR / FIXTURE_NAME,
        help="Output DICOM path (default: tests/fixtures/dicom_decoder fixture).",
    )
    parser.add_argument(
        "--cjpeg",
        default=shutil.which("cjpeg"),
        help="Path to libjpeg-turbo cjpeg (default: locate on PATH).",
    )
    args = parser.parse_args()
    if not args.cjpeg:
        raise SystemExit("cjpeg is required; install libjpeg-turbo to generate this fixture")

    dataset = build_fixture(args.cjpeg)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    dcmwrite(args.out, dataset, write_like_original=False)
    print(f"Generated synthetic decoder fixture: {args.out.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

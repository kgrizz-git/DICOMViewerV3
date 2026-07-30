"""Structural and decode checks for wholly synthetic decoder fixtures."""

from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path

import pydicom
import pytest
from pydicom.encaps import generate_pixel_data_frame
from pydicom.uid import JPEGBaseline8Bit

from core.decoder_fixture_contract import (
    DECODER_FIXTURE_EXPECTATIONS,
    GDCM_12_BIT_FALLBACK_DIAGNOSTIC,
)

_ROOT = Path(__file__).resolve().parent.parent
_FIXTURE_DIR = _ROOT / "tests" / "fixtures" / "dicom_decoder"
_FIXTURE = _FIXTURE_DIR / "synthetic_rgb_no_color_markers_jpeg_baseline.dcm"
_GENERATOR = _ROOT / "tests" / "scripts" / "generate_decoder_color_fixture.py"
_SPEC = importlib.util.spec_from_file_location("generate_decoder_color_fixture", _GENERATOR)
assert _SPEC and _SPEC.loader
_generator = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_generator)

_EXPECTED_BY_FILENAME = {item.filename: item for item in DECODER_FIXTURE_EXPECTATIONS}
_LOSSY_EXTENDED_FIXTURE = "synthetic_monochrome_jpeg_extended_12_bit.dcm"
_MONOCHROME_FIXTURES = {
    item.filename: item.transfer_syntax_uid
    for item in DECODER_FIXTURE_EXPECTATIONS
    if item.filename != _FIXTURE.name
}
_LOSSLESS_PIXEL_HASHES = {
    item.filename: item.pixel_sha256
    for item in DECODER_FIXTURE_EXPECTATIONS
    if item.filename not in {_FIXTURE.name, _LOSSY_EXTENDED_FIXTURE}
}


@pytest.mark.parametrize("filename", [_FIXTURE.name, *_MONOCHROME_FIXTURES])
def test_synthetic_decoder_fixtures_have_no_identifying_values(filename: str) -> None:
    dataset = pydicom.dcmread(_FIXTURE_DIR / filename, stop_before_pixels=True)

    assert str(dataset.PatientName) == ""
    assert dataset.PatientID == ""
    assert not getattr(dataset, "AccessionNumber", "")
    assert not getattr(dataset, "InstitutionName", "")
    assert not getattr(dataset, "StationName", "")


def test_synthetic_decoder_fixture_is_markerless_rgb_jpeg_baseline() -> None:
    dataset = pydicom.dcmread(_FIXTURE)
    frame = next(generate_pixel_data_frame(dataset.PixelData))
    markers = _generator._jpeg_header_markers(frame)

    assert dataset.file_meta.TransferSyntaxUID == JPEGBaseline8Bit
    assert dataset.PhotometricInterpretation == "RGB"
    assert dataset.SamplesPerPixel == 3
    assert dataset.PlanarConfiguration == 0
    assert dataset.BurnedInAnnotation == "NO"
    assert 0xE0 not in markers  # JFIF APP0
    assert 0xEE not in markers  # Adobe APP14
    assert _generator._rgb_component_ids(frame) == (ord("R"), ord("G"), ord("B"))


def test_synthetic_decoder_fixture_decodes_to_color_pixels() -> None:
    dataset = pydicom.dcmread(_FIXTURE)

    pixels = dataset.pixel_array

    assert pixels.shape == (48, 64, 3)
    assert pixels.dtype.name == "uint8"


@pytest.mark.parametrize("filename, transfer_syntax", _MONOCHROME_FIXTURES.items())
def test_synthetic_monochrome_decoder_matrix_has_expected_structure(
    filename: str, transfer_syntax: str
) -> None:
    dataset = pydicom.dcmread(_FIXTURE_DIR / filename, stop_before_pixels=True)

    assert str(dataset.file_meta.TransferSyntaxUID) == transfer_syntax
    assert dataset.PhotometricInterpretation == "MONOCHROME2"
    assert dataset.SamplesPerPixel == 1
    assert dataset.BitsAllocated == 16
    assert dataset.BitsStored in {12, 16}
    assert dataset.HighBit == dataset.BitsStored - 1
    assert dataset.BurnedInAnnotation == "NO"


@pytest.mark.parametrize("filename, expected_hash", _LOSSLESS_PIXEL_HASHES.items())
def test_synthetic_lossless_decoder_matrix_matches_known_source(
    filename: str, expected_hash: str
) -> None:
    pixels = pydicom.dcmread(_FIXTURE_DIR / filename).pixel_array

    assert pixels.shape == (48, 64)
    assert pixels.dtype.name == "uint16"
    assert hashlib.sha256(pixels.tobytes()).hexdigest() == expected_hash


def test_synthetic_jpeg_extended_fixture_decodes_as_12_bit_grayscale() -> None:
    dataset = pydicom.dcmread(_FIXTURE_DIR / "synthetic_monochrome_jpeg_extended_12_bit.dcm")
    pixels = dataset.pixel_array

    assert pixels.shape == (48, 64)
    assert pixels.dtype.name == "uint16"
    assert int(pixels.min()) >= 0
    assert int(pixels.max()) <= 4095


def test_gdcm_reference_pixels_when_gdcm_is_the_available_handler() -> None:
    """Pin independently confirmed GDCM output for the selected runtime dependency."""
    from pydicom.pixel_data_handlers import gdcm_handler

    assert gdcm_handler.is_available(), "python-gdcm is a required runtime dependency"

    for filename in (
        "synthetic_rgb_no_color_markers_jpeg_baseline.dcm",
        "synthetic_monochrome_jpeg_extended_12_bit.dcm",
    ):
        dataset = pydicom.dcmread(_FIXTURE_DIR / filename)
        assert gdcm_handler.supports_transfer_syntax(dataset.file_meta.TransferSyntaxUID)
        assert hashlib.sha256(dataset.pixel_array.tobytes()).hexdigest() == _EXPECTED_BY_FILENAME[
            filename
        ].pixel_sha256


def test_gdcm_12_bit_fallback_diagnostic_is_exactly_allowlisted() -> None:
    """Keep the one accepted native fallback message narrow and independently observable."""
    fixture = _FIXTURE_DIR / "synthetic_monochrome_jpeg_extended_12_bit.dcm"
    child = """
import hashlib
import sys

import pydicom
from pydicom.pixel_data_handlers import gdcm_handler

dataset = pydicom.dcmread(sys.argv[1])
assert gdcm_handler.is_available()
assert gdcm_handler.supports_transfer_syntax(dataset.file_meta.TransferSyntaxUID)
pixels = dataset.pixel_array
print(hashlib.sha256(pixels.tobytes()).hexdigest())
"""

    result = subprocess.run(
        [sys.executable, "-c", child, str(fixture)],
        cwd=_ROOT,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout == (
        _EXPECTED_BY_FILENAME[fixture.name].pixel_sha256.encode("ascii") + b"\n"
    )
    assert result.stderr == GDCM_12_BIT_FALLBACK_DIAGNOSTIC

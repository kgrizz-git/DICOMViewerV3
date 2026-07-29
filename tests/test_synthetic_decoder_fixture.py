"""Structural checks for the committed synthetic RGB JPEG decoder fixture."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pydicom
from pydicom.encaps import generate_pixel_data_frame
from pydicom.uid import JPEGBaseline8Bit

_ROOT = Path(__file__).resolve().parent.parent
_FIXTURE = _ROOT / "tests" / "fixtures" / "dicom_decoder" / "synthetic_rgb_no_color_markers_jpeg_baseline.dcm"
_GENERATOR = _ROOT / "tests" / "scripts" / "generate_decoder_color_fixture.py"
_SPEC = importlib.util.spec_from_file_location("generate_decoder_color_fixture", _GENERATOR)
assert _SPEC and _SPEC.loader
_generator = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_generator)


def test_synthetic_decoder_fixture_has_no_identifying_values() -> None:
    dataset = pydicom.dcmread(_FIXTURE, stop_before_pixels=True)

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

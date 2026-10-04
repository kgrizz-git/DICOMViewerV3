""""From DICOM": the Modality LUT and VOI LUT a file embeds replace rescale and W/L."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest
from pydicom.dataset import Dataset
from pydicom.sequence import Sequence

from core import dicom_lut_sequences as module
from core.dicom_lut_sequences import dicom_voi_to_uint8, has_modality_lut, has_voi_lut
from core.lut_catalog import inverse_lut
from core.lut_display import grayscale_export_kwargs
from core.lut_series_state import (
    focused_pane_voi_from_dicom,
    get_series_voi_from_dicom,
    set_series_voi_from_dicom,
    slice_lut_kwargs,
)


def _lut_item(entries: list[int], first: int, bits: int) -> Dataset:
    item = Dataset()
    item.LUTDescriptor = [len(entries), first, bits]
    item.LUTData = entries
    return item


def _dataset(*, voi: Dataset | None = None, modality: Dataset | None = None) -> Dataset:
    ds = Dataset()
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.SamplesPerPixel = 1
    ds.BitsStored = 12
    ds.PixelRepresentation = 0
    if voi is not None:
        ds.VOILUTSequence = Sequence([voi])
    if modality is not None:
        modality.ModalityLUTType = "US"
        ds.ModalityLUTSequence = Sequence([modality])
    return ds


def test_presence_checks() -> None:
    assert not has_voi_lut(None)
    assert not has_voi_lut(_dataset())
    assert has_voi_lut(_dataset(voi=_lut_item([0, 255], 0, 8)))
    assert has_modality_lut(_dataset(modality=_lut_item([0, 1], 0, 16)))


def test_an_8_bit_voi_lut_maps_stored_values_directly() -> None:
    # A descending VOI LUT: stored 0..3 -> 255, 170, 85, 0.
    ds = _dataset(voi=_lut_item([255, 170, 85, 0], 0, 8))
    pixels = np.array([[0, 1], [2, 3]], dtype=np.uint16)
    out = dicom_voi_to_uint8(pixels, ds)
    assert out is not None
    assert out.dtype == np.uint8
    assert out.tolist() == [[255, 170], [85, 0]]


def test_a_12_bit_voi_lut_is_scaled_to_8_bits_with_rounding() -> None:
    ds = _dataset(voi=_lut_item([0, 2048, 4095], 100, 12))
    pixels = np.array([[99, 100, 101, 102, 500]], dtype=np.uint16)
    out = dicom_voi_to_uint8(pixels, ds)
    assert out is not None
    # Below first_map holds the first entry; past the end holds the last.
    assert out.tolist() == [[0, 0, 128, 255, 255]]


def test_the_modality_lut_runs_before_the_voi_lut() -> None:
    # Modality maps stored 0..2 to 2, 1, 0; the VOI LUT then maps 0..2 to 0, 128, 255.
    ds = _dataset(
        voi=_lut_item([0, 128, 255], 0, 8),
        modality=_lut_item([2, 1, 0], 0, 16),
    )
    out = dicom_voi_to_uint8(np.array([[0, 1, 2]], dtype=np.uint16), ds)
    assert out is not None
    assert out.tolist() == [[255, 128, 0]]


def test_rescale_applies_when_there_is_no_modality_lut() -> None:
    ds = _dataset(voi=_lut_item([0, 64, 128, 255], 0, 8))
    ds.RescaleSlope = 1
    ds.RescaleIntercept = 1
    out = dicom_voi_to_uint8(np.array([[0, 1, 2]], dtype=np.uint16), ds)
    assert out is not None
    assert out.tolist() == [[64, 128, 255]]


def test_without_a_voi_lut_the_window_still_applies() -> None:
    ds = _dataset(modality=_lut_item([0, 1], 0, 16))
    assert dicom_voi_to_uint8(np.zeros((1, 1), dtype=np.uint16), ds) is None


def test_an_unsupported_descriptor_falls_back_with_a_warning(caplog) -> None:
    ds = _dataset(voi=_lut_item([0, 1], 0, 9))
    with caplog.at_level("WARNING", logger=module.__name__):
        assert dicom_voi_to_uint8(np.zeros((1, 2), dtype=np.uint16), ds) is None
    assert "using window/level" in caplog.text


def _render(ds: Dataset, pixels: np.ndarray, monkeypatch, **kwargs):
    from core import dicom_pixel_array
    from core.dicom_processor import DICOMProcessor

    monkeypatch.setattr(dicom_pixel_array, "get_pixel_array", lambda _ds: pixels)
    return np.asarray(
        DICOMProcessor.dataset_to_image(ds, window_center=1.5, window_width=4.0, **kwargs)
    )


def test_dataset_to_image_uses_the_voi_lut_only_when_asked(monkeypatch) -> None:
    ds = _dataset(voi=_lut_item([255, 170, 85, 0], 0, 8))
    pixels = np.array([[0, 1, 2, 3]], dtype=np.uint16)
    windowed = _render(ds, pixels, monkeypatch)
    from_dicom = _render(ds, pixels, monkeypatch, voi_from_dicom=True)
    assert from_dicom.tolist() == [[255, 170, 85, 0]]
    assert windowed.tolist() != from_dicom.tolist()


def test_polarity_invert_and_display_lut_still_follow_the_voi_lut(monkeypatch) -> None:
    ds = _dataset(voi=_lut_item([255, 170, 85, 0], 0, 8))
    pixels = np.array([[0, 1, 2, 3]], dtype=np.uint16)
    inverted = _render(ds, pixels, monkeypatch, voi_from_dicom=True, image_inverted=True)
    assert inverted.tolist() == [[0, 85, 170, 255]]
    ds.PhotometricInterpretation = "MONOCHROME1"
    mono1 = _render(ds, pixels, monkeypatch, voi_from_dicom=True)
    assert mono1.tolist() == [[0, 85, 170, 255]]
    ds.PhotometricInterpretation = "MONOCHROME2"
    both = _render(ds, pixels, monkeypatch, voi_from_dicom=True, lut=inverse_lut())
    assert both.tolist() == [[0, 85, 170, 255]]


def test_the_choice_is_stored_per_series_and_reaches_the_slice_render() -> None:
    view_state = SimpleNamespace(series_defaults={}, current_series_identifier="s1", image_viewer=None)
    assert not get_series_voi_from_dicom(view_state, "s1")
    set_series_voi_from_dicom(view_state, True, "s1")
    set_series_voi_from_dicom(view_state, True, None)
    assert get_series_voi_from_dicom(view_state, "s1")
    assert not get_series_voi_from_dicom(view_state, "s2")
    assert focused_pane_voi_from_dicom(view_state)
    assert not focused_pane_voi_from_dicom(None)
    assert slice_lut_kwargs(view_state, "s1", True, "MONOCHROME2")["voi_from_dicom"] is True


@pytest.mark.parametrize(("photometric", "kept"), [("MONOCHROME2", True), ("RGB", False)])
def test_export_carries_the_choice_for_grayscale_only(photometric, kept) -> None:
    ds = Dataset()
    ds.PhotometricInterpretation = photometric
    ds.SamplesPerPixel = 1 if photometric.startswith("MONO") else 3
    kwargs = grayscale_export_kwargs(ds, False, None, True)
    assert kwargs.get("voi_from_dicom", False) is kept


def test_supported_means_a_descriptor_this_build_can_apply() -> None:
    from core.dicom_lut_sequences import voi_lut_supported

    assert not voi_lut_supported(_dataset())
    assert voi_lut_supported(_dataset(voi=_lut_item([0, 255], 0, 8)))
    assert voi_lut_supported(_dataset(voi=_lut_item([0, 4095], 0, 12)))
    assert not voi_lut_supported(_dataset(voi=_lut_item([0, 1], 0, 9)))
    no_data = _lut_item([0, 255], 0, 8)
    del no_data.LUTData
    assert not voi_lut_supported(_dataset(voi=no_data))

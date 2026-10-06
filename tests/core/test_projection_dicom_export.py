"""Tests for core.projection_dicom_export using synthetic in-test datasets."""

from __future__ import annotations

import warnings

import numpy as np
import pydicom
import pytest
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import (
    CTImageStorage,
    ExplicitVRLittleEndian,
    ImplicitVRLittleEndian,
    generate_uid,
)

from core import projection_dicom_export as pde

STUDY = "1.2.3"
SERIES = "1.2.3.4"


def _slice(values: list[list[int]], *, signed: bool = False, number: int = 1) -> Dataset:
    ds = Dataset()
    ds.file_meta = FileMetaDataset()
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.file_meta.MediaStorageSOPClassUID = CTImageStorage
    ds.file_meta.MediaStorageSOPInstanceUID = generate_uid()
    ds.is_implicit_VR = False
    ds.is_little_endian = True
    ds.SOPClassUID = CTImageStorage
    ds.SOPInstanceUID = ds.file_meta.MediaStorageSOPInstanceUID
    ds.StudyInstanceUID = STUDY
    ds.SeriesInstanceUID = SERIES
    ds.SeriesNumber = 5
    ds.InstanceNumber = number
    ds.Modality = "CT"
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.SamplesPerPixel = 1
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 1 if signed else 0
    arr = np.array(values, dtype=np.int16 if signed else np.uint16)
    ds.Rows, ds.Columns = arr.shape
    ds.PixelData = arr.tobytes()
    return ds


def _studies(*slices: Dataset) -> dict[str, dict[str, list[Dataset]]]:
    return {STUDY: {SERIES: list(slices)}}


def _build(slices: list[Dataset], index: int, ptype: str = "mip", count: int = 2, **kw):
    return pde.create_projection_dataset(
        slices[index], _studies(*slices), STUDY, SERIES, index, ptype, count, False, **kw
    )


def _pixels(ds: Dataset) -> np.ndarray:
    dtype = np.int16 if ds.PixelRepresentation else np.uint16
    return np.frombuffer(ds.PixelData, dtype=dtype).reshape(ds.Rows, ds.Columns)


def test_stack_export_shares_new_series_uid_and_numbers_instances() -> None:
    slices = [_slice([[1, 2], [3, 4]], number=n) for n in (1, 2, 3)]
    series_uid = generate_uid()
    out = [
        _build(slices, i, count=2, new_series_uid=series_uid, instance_number=i + 1)
        for i in range(2)
    ]
    assert all(ds is not None for ds in out)
    assert {ds.SeriesInstanceUID for ds in out} == {series_uid}
    assert series_uid != SERIES
    assert [ds.InstanceNumber for ds in out] == [1, 2]
    assert out[0].SOPInstanceUID != out[1].SOPInstanceUID


def test_series_uid_generated_when_not_supplied() -> None:
    slices = [_slice([[1]]), _slice([[2]])]
    ds = _build(slices, 0)
    assert ds is not None and ds.SeriesInstanceUID != SERIES


@pytest.mark.parametrize(
    ("source", "expected"), [(5, 605), ("7", 607), (None, 601), ("", 601)]
)
def test_series_number_offset(source, expected) -> None:
    slices = [_slice([[1]]), _slice([[2]])]
    for s in slices:
        if source is None:
            del s.SeriesNumber
        else:
            s.SeriesNumber = source
    ds = _build(slices, 0)
    assert ds is not None and ds.SeriesNumber == expected


def test_series_number_helper_handles_unparseable() -> None:
    assert pde.projection_series_number("abc") == 601


def test_replaced_pixels_get_fresh_explicit_vr_file_meta() -> None:
    slices = [_slice([[1, 9], [3, 4]]), _slice([[5, 2], [3, 8]])]
    slices[0].file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
    ds = _build(slices, 0)
    assert ds is not None
    assert ds.file_meta.MediaStorageSOPInstanceUID == ds.SOPInstanceUID
    assert ds.file_meta.MediaStorageSOPInstanceUID != slices[0].SOPInstanceUID
    assert ds.file_meta.TransferSyntaxUID == ExplicitVRLittleEndian
    assert ds.is_implicit_VR is False and ds.is_little_endian is True
    assert ds[0x7FE00010].VR == "OW"
    assert np.array_equal(_pixels(ds), [[5, 9], [3, 8]])


def test_saved_file_round_trips(tmp_path) -> None:
    slices = [_slice([[1, 9], [3, 4]]), _slice([[5, 2], [3, 8]])]
    ds = _build(slices, 0)
    path = str(tmp_path / "out.dcm")
    pde.save_projection_dataset(ds, path)
    back = pydicom.dcmread(path)
    assert back.file_meta.MediaStorageSOPInstanceUID == back.SOPInstanceUID
    assert np.array_equal(back.pixel_array, [[5, 9], [3, 8]])


def test_rle_compressed_source_writes_readable_file(tmp_path) -> None:
    slices = [_slice([[1, 9], [3, 4]]), _slice([[5, 2], [3, 8]])]
    try:
        slices[0].compress(pydicom.uid.RLELossless)
    except Exception as exc:  # encoder unavailable
        pytest.skip(f"RLE encoder unavailable: {type(exc).__name__}")
    assert slices[0].file_meta.TransferSyntaxUID == pydicom.uid.RLELossless
    ds = _build(slices, 0)
    assert ds is not None
    path = str(tmp_path / "rle.dcm")
    pde.save_projection_dataset(ds, path)
    back = pydicom.dcmread(path)
    assert back.file_meta.TransferSyntaxUID == ExplicitVRLittleEndian
    assert np.array_equal(back.pixel_array, [[5, 9], [3, 8]])


def test_single_slice_branch_keeps_source_transfer_syntax(tmp_path) -> None:
    src = _slice([[1, 2], [3, 4]])
    src.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
    src.is_implicit_VR = True
    ds = _build([src], 0, count=4)
    assert ds is not None
    assert ds.PixelData == src.PixelData
    assert ds.file_meta.TransferSyntaxUID == ImplicitVRLittleEndian
    assert ds.file_meta.MediaStorageSOPInstanceUID == ds.SOPInstanceUID
    path = str(tmp_path / "one.dcm")
    pde.save_projection_dataset(ds, path)
    back = pydicom.dcmread(path)
    assert back.file_meta.TransferSyntaxUID == ImplicitVRLittleEndian
    assert np.array_equal(back.pixel_array, [[1, 2], [3, 4]])


def test_aip_rounds_to_nearest_even_not_truncate() -> None:
    slices = [_slice([[2, 3], [0, 1]]), _slice([[3, 4], [1, 1]])]
    ds = _build(slices, 0, ptype="aip")
    assert ds is not None
    # means 2.5, 3.5, 0.5, 1.0 -> np.rint banker's rounding
    assert np.array_equal(_pixels(ds), np.rint([[2.5, 3.5], [0.5, 1.0]]).astype(np.uint16))
    assert np.array_equal(_pixels(ds), [[2, 4], [0, 1]])


def test_aip_rounds_negative_signed_values() -> None:
    slices = [_slice([[-3, -2]], signed=True), _slice([[-2, -3]], signed=True)]
    ds = _build(slices, 0, ptype="aip")
    assert ds is not None
    assert np.array_equal(_pixels(ds), np.rint([[-2.5, -2.5]]).astype(np.int16))
    assert np.array_equal(_pixels(ds), [[-2, -2]])


def test_metadata_and_no_dicom_cs_warnings() -> None:
    slices = [_slice([[1, 2]]), _slice([[3, 0]])]
    slices[0].SeriesDescription = "synthetic"
    slices[0].SpacingBetweenSlices = 2.0
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        ds = _build(slices, 0, ptype="minip")
    assert ds is not None
    assert not any("maximum length of 16" in str(w.message) for w in caught)
    assert ds.ImageType == ["DERIVED", "SECONDARY", "MINIP"]
    assert ds.SeriesDescription == "synthetic - MINIP"
    assert "Minimum Intensity Projection (MinIP) - 2 slices (instances 1 to 2)" in ds.ImageComments
    assert "SpacingBetweenSlices" not in ds


def test_missing_series_returns_none() -> None:
    src = _slice([[1]])
    assert pde.create_projection_dataset(src, {}, STUDY, SERIES, 0, "aip", 2, False) is None


def _with_rescale(ds: Dataset, slope: float, intercept: float) -> Dataset:
    ds.RescaleSlope = slope
    ds.RescaleIntercept = intercept
    return ds


def test_mixed_rescale_slab_projects_in_rescaled_space(tmp_path) -> None:
    slices = [
        _with_rescale(_slice([[10, 20], [30, 40]], signed=True), 1.0, -1000.0),
        _with_rescale(_slice([[5, 25], [10, 60]], signed=True), 2.0, -1000.0),
    ]
    ds = _build(slices, 0, ptype="mip")
    assert ds is not None
    assert ds.BitsAllocated == 16 and ds.PixelRepresentation == 1
    path = str(tmp_path / "mixed.dcm")
    pde.save_projection_dataset(ds, path)
    back = pydicom.dcmread(path)
    physical = back.pixel_array * float(back.RescaleSlope) + float(back.RescaleIntercept)
    expected = np.array([[-990.0, -950.0], [-970.0, -880.0]])
    tol = float(back.RescaleSlope)
    assert np.allclose(physical, expected, atol=tol)


def test_uniform_rescale_slab_keeps_stored_values() -> None:
    slices = [
        _with_rescale(_slice([[1, 9], [3, 4]]), 1.0, -1024.0),
        _with_rescale(_slice([[5, 2], [3, 8]]), 1.0, -1024.0),
    ]
    ds = _build(slices, 0)
    assert ds is not None
    assert np.array_equal(_pixels(ds), [[5, 9], [3, 8]])
    assert float(ds.RescaleSlope) == 1.0 and float(ds.RescaleIntercept) == -1024.0


def test_derivation_metadata_present() -> None:
    slices = [_slice([[1]], number=n) for n in (1, 2, 3)]
    ds = _build(slices, 1, ptype="mip", count=2)
    assert ds is not None
    assert ds.DerivationDescription == "Maximum Intensity Projection of 2 slices, instances 2-3"
    refs = [i.ReferencedSOPInstanceUID for i in ds.SourceImageSequence]
    assert refs == [slices[1].SOPInstanceUID, slices[2].SOPInstanceUID]
    assert ds.SourceImageSequence[0].ReferencedSOPClassUID == CTImageStorage
    assert ds.ReferencedSeriesSequence[0].SeriesInstanceUID == SERIES
    assert ds.SeriesInstanceUID != SERIES


def _walk(ds: Dataset):
    for elem in ds:
        yield elem
        if elem.VR == "SQ":
            for item in elem.value:
                yield from _walk(item)


def test_deep_anonymized_projection_export_has_no_source_identifiers(tmp_path) -> None:
    from gui.export_manager import ExportManager

    slices = [_slice([[1, 9], [3, 4]], number=n) for n in (1, 2, 3)]
    for s in slices:
        s.PatientName = "Doe^Jane"
        s.PatientID = "SRC-PID-77"
    items = {(STUDY, SERIES): list(enumerate(slices))}
    out = ExportManager.build_anonymized_projections(
        items, _studies(*slices), "mip", 2, False
    )
    assert len(out) == 3
    source_uids = {STUDY, SERIES} | {s.SOPInstanceUID for s in slices}
    for i, ds in enumerate(v for _, v in sorted(out.items())):
        path = str(tmp_path / f"a{i}.dcm")
        pde.save_projection_dataset(ds, path)
        back = pydicom.dcmread(path)
        values: list[str] = []
        for elem in _walk(back):
            values.extend(str(v) for v in (elem.value if elem.VM > 1 else [elem.value]))
        for elem in _walk(back.file_meta):
            values.append(str(elem.value))
        text = "\n".join(values)
        assert "Doe" not in text and "SRC-PID-77" not in text
        assert not any(uid in text for uid in source_uids)
    # One shared (remapped) series UID across the run; instances numbered 1..N.
    assert len({ds.SeriesInstanceUID for ds in out.values()}) == 1
    assert sorted(ds.InstanceNumber for ds in out.values()) == [1, 2, 3]

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
FOR_UID = "1.2.3.99"
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
    assert ds is not None
    assert ds.SeriesInstanceUID != SERIES


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
    assert ds is not None
    assert ds.SeriesNumber == expected


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
    assert ds.is_implicit_VR is False
    assert ds.is_little_endian is True
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
    assert ds.BitsAllocated == 16
    assert ds.PixelRepresentation == 1
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
    assert float(ds.RescaleSlope) == 1.0
    assert float(ds.RescaleIntercept) == -1024.0


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
        assert "Doe" not in text
        assert "SRC-PID-77" not in text
        assert not any(uid in text for uid in source_uids)
    # One shared (remapped) series UID across the run; instances numbered 1..N.
    assert len({ds.SeriesInstanceUID for ds in out.values()}) == 1
    assert sorted(ds.InstanceNumber for ds in out.values()) == [1, 2, 3]


def _positioned(ds: Dataset, z: float, thickness: float = 2.0) -> Dataset:
    ds.ImagePositionPatient = [10.0, 20.0, z]
    ds.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
    ds.SliceThickness = thickness
    ds.SliceLocation = z
    return ds


def test_slab_geometry_center_extent_and_slice_location_dropped() -> None:
    slices = [_positioned(_slice([[1, 2]]), z, 2.0) for z in (0.0, 3.0, 6.0, 9.0)]
    ds = _build(slices, 0, count=4)
    assert ds is not None
    assert [float(v) for v in ds.ImagePositionPatient] == [10.0, 20.0, 4.5]
    assert float(ds.SliceThickness) == 11.0  # 9 mm between centers + 2 mm
    assert "SliceLocation" not in ds
    assert "slab center at (10.00, 20.00, 4.50) mm" in ds.DerivationDescription


def test_slab_geometry_uses_normal_for_oblique_stacks() -> None:
    slices = [_positioned(_slice([[1]]), z) for z in (0.0, 4.0)]
    for s, y in zip(slices, (0.0, 3.0), strict=True):
        s.ImagePositionPatient = [10.0, 20.0 + y, s.ImagePositionPatient[2]]
    ds = _build(slices, 0)
    assert ds is not None
    # in-plane shift of 3 mm is ignored; normal distance 4 + thickness 2
    assert float(ds.SliceThickness) == 6.0


def test_missing_positions_fall_back_to_summed_thickness() -> None:
    slices = [_slice([[1]]), _slice([[2]])]
    for s in slices:
        s.SliceThickness = 2.5
        s.SliceLocation = 1.0
    ds = _build(slices, 0)
    assert ds is not None
    assert float(ds.SliceThickness) == 5.0
    assert "ImagePositionPatient" not in ds
    assert "SliceLocation" not in ds
    assert "slab center" not in ds.DerivationDescription


def _enhanced_multiframe(n_frames: int = 3) -> Dataset:
    ds = _slice([[0, 0], [0, 0]])
    ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2.1"
    ds.file_meta.MediaStorageSOPClassUID = ds.SOPClassUID
    ds.NumberOfFrames = n_frames
    ds.FrameOfReferenceUID = FOR_UID
    ds.DimensionIndexSequence = pydicom.Sequence([Dataset()])
    ds.ConcatenationUID = generate_uid()
    ds.FrameIncrementPointer = 0x00181063
    frames = np.stack(
        [np.array([[f, f + 1], [f + 2, f + 3]], dtype=np.uint16) for f in range(n_frames)]
    )
    ds.PixelData = frames.tobytes()
    per_frame = []
    for f in range(n_frames):
        item = Dataset()
        plane = Dataset()
        plane.ImagePositionPatient = [0.0, 0.0, 3.0 * f]
        item.PlanePositionSequence = pydicom.Sequence([plane])
        per_frame.append(item)
    ds.PerFrameFunctionalGroupsSequence = pydicom.Sequence(per_frame)
    shared = Dataset()
    orient = Dataset()
    orient.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
    shared.PlaneOrientationSequence = pydicom.Sequence([orient])
    measures = Dataset()
    measures.SliceThickness = 2.0
    measures.PixelSpacing = [1.0, 1.0]
    shared.PixelMeasuresSequence = pydicom.Sequence([measures])
    ds.SharedFunctionalGroupsSequence = pydicom.Sequence([shared])
    return ds


def _frame_series(n_frames: int = 3):
    from core.multiframe_handler import create_frame_dataset

    mf = _enhanced_multiframe(n_frames)
    return mf, [create_frame_dataset(mf, i) for i in range(n_frames)]


def test_multiframe_source_builds_plain_single_frame_secondary_capture_dataset(tmp_path) -> None:
    mf, frames = _frame_series()
    ds = pde.create_projection_dataset(
        frames[0], _studies(*frames), STUDY, SERIES, 0, "mip", 2, False
    )
    assert ds is not None
    assert type(ds) is Dataset
    for kw in ("NumberOfFrames", "PerFrameFunctionalGroupsSequence", "SharedFunctionalGroupsSequence"):
        assert kw not in ds
    assert ds.SOPClassUID == pydicom.uid.SecondaryCaptureImageStorage
    assert ds.file_meta.MediaStorageSOPClassUID == pydicom.uid.SecondaryCaptureImageStorage
    assert ds.Modality == "CT"
    for kw in ("DimensionIndexSequence", "ConcatenationUID", "FrameIncrementPointer"):
        assert kw not in ds
    assert ds.FrameOfReferenceUID == FOR_UID
    assert [float(v) for v in ds.ImagePositionPatient] == [0.0, 0.0, 1.5]
    assert float(ds.SliceThickness) == 5.0
    assert [r.ReferencedFrameNumber for r in ds.SourceImageSequence] == [1, 2]
    path = str(tmp_path / "mf.dcm")
    pde.save_projection_dataset(ds, path)
    back = pydicom.dcmread(path)
    assert np.array_equal(back.pixel_array, [[1, 2], [3, 4]])


def test_multiframe_single_slab_slice_gets_its_frame_pixels() -> None:
    mf, frames = _frame_series()
    ds = pde.create_projection_dataset(
        frames[2], _studies(*frames), STUDY, SERIES, 2, "mip", 4, False
    )
    assert ds is not None
    assert "NumberOfFrames" not in ds
    assert np.array_equal(_pixels(ds), [[2, 3], [4, 5]])


def test_unsplit_multiframe_instance_returns_none() -> None:
    mf = _enhanced_multiframe()
    assert pde.create_projection_dataset(
        mf, _studies(mf, mf), STUDY, SERIES, 0, "mip", 2, False
    ) is None


def test_negative_slope_uniform_slab_uses_rescaled_path(tmp_path) -> None:
    slices = [
        _with_rescale(_slice([[10, 20]], signed=True), -1.0, 100.0),
        _with_rescale(_slice([[30, 5]], signed=True), -1.0, 100.0),
    ]
    ds = _build(slices, 0, ptype="mip")
    assert ds is not None
    path = str(tmp_path / "neg.dcm")
    pde.save_projection_dataset(ds, path)
    back = pydicom.dcmread(path)
    physical = back.pixel_array * float(back.RescaleSlope) + float(back.RescaleIntercept)
    # physical values: [90, 80] and [70, 95]; MIP -> [90, 95]
    assert np.allclose(physical, [[90.0, 95.0]], atol=float(back.RescaleSlope))


def test_32_bit_values_above_float32_precision_survive() -> None:
    big = 2**30 + 1
    slices = []
    for v in (big, big - 1):
        s = _slice([[0]])
        s.BitsAllocated = 32
        s.BitsStored = 32
        s.HighBit = 31
        s.PixelRepresentation = 0
        s.PixelData = np.array([[v]], dtype=np.uint32).tobytes()
        slices.append(s)
    ds = _build(slices, 0, ptype="mip")
    assert ds is not None
    assert int(np.frombuffer(ds.PixelData, dtype=np.uint32)[0]) == big
    assert ds.BitsAllocated == 32


def test_stale_pixel_description_tags_removed_and_vr_ob_for_8_bit() -> None:
    slices = []
    for v in (1, 2):
        s = _slice([[0, 0]])
        s.BitsAllocated = 8
        s.BitsStored = 8
        s.HighBit = 7
        s.PixelData = np.array([[v, 0]], dtype=np.uint8).tobytes()
        s.PixelPaddingValue = 0
        s.SmallestImagePixelValue = 0
        s.LargestImagePixelValue = 255
        s.LossyImageCompression = "01"
        s.VOILUTSequence = pydicom.Sequence([Dataset()])
        slices.append(s)
    ds = _build(slices, 0, ptype="mip")
    assert ds is not None
    assert ds[0x7FE00010].VR == "OB"
    for kw in (
        "PixelPaddingValue", "SmallestImagePixelValue", "LargestImagePixelValue",
        "LossyImageCompression", "VOILUTSequence",
    ):
        assert kw not in ds


def test_16_bit_pixel_data_vr_is_ow() -> None:
    ds = _build([_slice([[1]]), _slice([[2]])], 0)
    assert ds is not None
    assert ds[0x7FE00010].VR == "OW"


def test_series_description_suffix_not_duplicated_and_truncated() -> None:
    slices = [_slice([[1]]), _slice([[2]])]
    slices[0].SeriesDescription = "base - MIP"
    ds = _build(slices, 0, ptype="mip")
    assert ds is not None
    assert ds.SeriesDescription == "base - MIP"
    slices[0].SeriesDescription = "x" * 64
    ds = _build(slices, 0, ptype="mip")
    assert ds is not None
    assert len(ds.SeriesDescription) == 64


def test_single_slice_has_no_projection_type_or_suffix_but_new_series() -> None:
    src = _slice([[1, 2]])
    src.SeriesDescription = "base"
    series_uid = generate_uid()
    ds = _build([src], 0, ptype="mip", count=4, new_series_uid=series_uid)
    assert ds is not None
    assert ds.ImageType == ["DERIVED", "SECONDARY"]
    assert ds.SeriesDescription == "base"
    assert ds.SeriesInstanceUID == series_uid
    assert ds.DerivationDescription == "Derived from instance 1"


def test_single_slice_rle_source_round_trips(tmp_path) -> None:
    src = _slice([[1, 9], [3, 4]])
    try:
        src.compress(pydicom.uid.RLELossless)
    except Exception as exc:  # encoder unavailable
        pytest.skip(f"RLE encoder unavailable: {type(exc).__name__}")
    ds = _build([src], 0, count=3)
    assert ds is not None
    path = str(tmp_path / "rle1.dcm")
    pde.save_projection_dataset(ds, path)
    back = pydicom.dcmread(path)
    assert back.file_meta.TransferSyntaxUID == pydicom.uid.RLELossless
    assert np.array_equal(back.pixel_array, [[1, 9], [3, 4]])


def test_save_handles_missing_file_meta(tmp_path) -> None:
    ds = _slice([[1, 2]])
    del ds.file_meta
    path = str(tmp_path / "nometa.dcm")
    pde.save_projection_dataset(ds, path)
    assert pydicom.dcmread(path, force=True).SOPInstanceUID == ds.SOPInstanceUID


def test_unbuildable_frame_wrapper_returns_none_without_raw_fallback() -> None:
    mf, frames = _frame_series()
    frames[0].BitsAllocated = 8  # frames stay valid, but a failing pixel read yields None
    frames[0]._frame_index = 99  # out-of-range frame: pixel read fails
    assert pde.create_projection_dataset(
        frames[0], _studies(*frames), STUDY, SERIES, 0, "mip", 1, False
    ) is None

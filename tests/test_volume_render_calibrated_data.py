"""Tests for 3D-only calibrated volume data preparation."""

from __future__ import annotations

import os
import sys

import numpy as np
import SimpleITK as sitk
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import core.volume_data_preparation as volume_data_preparation
from core.mpr_builder import MprBuilder
from core.mpr_volume import MprVolume
from core.volume_renderer import VolumeRenderer


def _make_ct_dataset(
    array: np.ndarray,
    *,
    z: float,
    slope: float | None = 1.0,
    intercept: float | None = -1024.0,
    instance_number: int = 1,
    study_uid: str,
    series_uid: str,
) -> Dataset:
    """Create a minimal CT slice with optional rescale metadata."""
    arr = np.asarray(array, dtype=np.uint16)
    ds = Dataset()
    ds.file_meta = FileMetaDataset()
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.SOPClassUID = generate_uid()
    ds.SOPInstanceUID = generate_uid()
    ds.StudyInstanceUID = study_uid
    ds.SeriesInstanceUID = series_uid
    ds.Modality = "CT"
    ds.Rows = int(arr.shape[0])
    ds.Columns = int(arr.shape[1])
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.PixelRepresentation = 0
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.ImagePositionPatient = [0.0, 0.0, z]
    ds.ImageOrientationPatient = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
    ds.PixelSpacing = [1.0, 1.0]
    ds.SliceThickness = 1.0
    ds.InstanceNumber = instance_number
    if slope is not None:
        ds.RescaleSlope = slope
    if intercept is not None:
        ds.RescaleIntercept = intercept
    ds.RescaleType = "HU"
    ds.PixelData = arr.tobytes()
    return ds


def _make_ct_series(
    *,
    slope: float | None = 1.0,
    intercept: float | None = -1024.0,
) -> list[Dataset]:
    study_uid = generate_uid()
    series_uid = generate_uid()
    return [
        _make_ct_dataset(
            np.full((2, 2), 1024 + i * 100, dtype=np.uint16),
            z=float(i),
            slope=slope,
            intercept=intercept,
            instance_number=i + 1,
            study_uid=study_uid,
            series_uid=series_uid,
        )
        for i in range(3)
    ]


def test_prepare_volume_data_can_calibrate_ct_without_mutating_mpr_volume() -> None:
    datasets = _make_ct_series(slope=1.0, intercept=-1024.0)
    volume = MprVolume.from_datasets(datasets)

    raw = sitk.GetArrayFromImage(volume.sitk_image)
    assert raw[0, 0, 0] == 1024.0

    volume_data = VolumeRenderer.prepare_volume_data(
        volume.sitk_image,
        source_datasets=volume.source_datasets,
        apply_rescale=True,
    )

    np.testing.assert_allclose(volume_data.array[:, 0, 0], [0.0, 100.0, 200.0])
    assert volume_data.rescale_applied is True
    assert volume_data.scalar_units == "HU"


def test_prepare_volume_data_falls_back_to_raw_when_rescale_metadata_incomplete() -> None:
    datasets = _make_ct_series(slope=1.0, intercept=None)
    volume = MprVolume.from_datasets(datasets)

    volume_data = VolumeRenderer.prepare_volume_data(
        volume.sitk_image,
        source_datasets=volume.source_datasets,
        apply_rescale=True,
    )

    np.testing.assert_allclose(volume_data.array[:, 0, 0], [1024.0, 1124.0, 1224.0])
    assert volume_data.rescale_applied is False
    assert volume_data.scalar_units is None


def test_varying_slope_intercept_per_slice() -> None:
    """Per-slice calibration must apply each slice's own slope/intercept."""
    study_uid = generate_uid()
    series_uid = generate_uid()
    datasets = [
        _make_ct_dataset(
            np.full((2, 2), 1000, dtype=np.uint16),
            z=0.0, slope=1.0, intercept=-1024.0,
            instance_number=1, study_uid=study_uid, series_uid=series_uid,
        ),
        _make_ct_dataset(
            np.full((2, 2), 1000, dtype=np.uint16),
            z=1.0, slope=1.0, intercept=-1000.0,
            instance_number=2, study_uid=study_uid, series_uid=series_uid,
        ),
        _make_ct_dataset(
            np.full((2, 2), 1000, dtype=np.uint16),
            z=2.0, slope=2.0, intercept=-500.0,
            instance_number=3, study_uid=study_uid, series_uid=series_uid,
        ),
    ]
    volume = MprVolume.from_datasets(datasets)
    vd = VolumeRenderer.prepare_volume_data(
        volume.sitk_image,
        source_datasets=volume.source_datasets,
        apply_rescale=True,
    )
    assert vd.rescale_applied is True
    # slice 0: 1000 * 1.0 + (-1024) = -24
    # slice 1: 1000 * 1.0 + (-1000) = 0
    # slice 2: 1000 * 2.0 + (-500)  = 1500
    np.testing.assert_allclose(vd.array[:, 0, 0], [-24.0, 0.0, 1500.0])


def test_mixed_rescale_units_falls_back_to_raw() -> None:
    """If slices report different rescale-unit strings, fall back to raw."""
    study_uid = generate_uid()
    series_uid = generate_uid()
    ds1 = _make_ct_dataset(
        np.full((2, 2), 100, dtype=np.uint16),
        z=0.0, slope=1.0, intercept=0.0,
        instance_number=1, study_uid=study_uid, series_uid=series_uid,
    )
    ds1.RescaleType = "HU"
    ds2 = _make_ct_dataset(
        np.full((2, 2), 100, dtype=np.uint16),
        z=1.0, slope=1.0, intercept=0.0,
        instance_number=2, study_uid=study_uid, series_uid=series_uid,
    )
    ds2.RescaleType = "OD"  # optical density — genuinely different from HU
    ds3 = _make_ct_dataset(
        np.full((2, 2), 100, dtype=np.uint16),
        z=2.0, slope=1.0, intercept=0.0,
        instance_number=3, study_uid=study_uid, series_uid=series_uid,
    )
    ds3.RescaleType = "HU"
    volume = MprVolume.from_datasets([ds1, ds2, ds3])
    vd = VolumeRenderer.prepare_volume_data(
        volume.sitk_image,
        source_datasets=volume.source_datasets,
        apply_rescale=True,
    )
    assert vd.rescale_applied is False
    assert vd.scalar_units is None


def test_nan_in_calibrated_output_falls_back_to_raw() -> None:
    """If calibration produces NaN/Inf, fall back to raw."""
    study_uid = generate_uid()
    series_uid = generate_uid()
    # slope=1e38 * large pixel value can overflow float32 to inf
    datasets = [
        _make_ct_dataset(
            np.full((2, 2), 65535, dtype=np.uint16),
            z=float(i), slope=1e35, intercept=0.0,
            instance_number=i + 1, study_uid=study_uid, series_uid=series_uid,
        )
        for i in range(3)
    ]
    volume = MprVolume.from_datasets(datasets)
    vd = VolumeRenderer.prepare_volume_data(
        volume.sitk_image,
        source_datasets=volume.source_datasets,
        apply_rescale=True,
    )
    assert vd.rescale_applied is False
    assert vd.scalar_units is None


def test_mpr_volume_remains_raw_and_mpr_rescale_still_applies_once() -> None:
    datasets = _make_ct_series(slope=1.0, intercept=-1024.0)
    volume = MprVolume.from_datasets(datasets)

    raw = sitk.GetArrayFromImage(volume.sitk_image)
    assert raw[0, 0, 0] == 1024.0

    worker = MprBuilder.create_worker(
        source_volume=volume,
        output_plane=MprBuilder.standard_planes()["axial"],
        output_spacing_mm=1.0,
        output_thickness_mm=1.0,
        interpolation="nearest",
    )
    result = worker._build()

    np.testing.assert_allclose(result.apply_rescale(np.array([[1024.0]], dtype=np.float32)), [[0.0]])


def test_prepare_volume_data_downsamples_view_before_float32_allocation(monkeypatch) -> None:
    """The memory guard must stride the SimpleITK view before its owned copy.

    In particular, calling ``GetArrayFromImage`` first would allocate a full
    renderer-sized array before the guard had any effect.  This test makes that
    old path raise and verifies both the retained voxels and physical geometry.
    """
    source = np.arange(3 * 4 * 6, dtype=np.int16).reshape(3, 4, 6)
    calls: list[str] = []

    class _Image:
        def GetSize(self):
            calls.append("size")
            return (6, 4, 3)  # SimpleITK x, y, z order

        def GetSpacing(self):
            return (0.5, 1.5, 3.0)

        def GetOrigin(self):
            return (10.0, 20.0, 30.0)

        def GetDirection(self):
            return (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)

    class _Sitk:
        @staticmethod
        def GetArrayViewFromImage(_image):
            assert calls == ["size"]
            calls.append("view")
            return source

        @staticmethod
        def GetArrayFromImage(_image):
            raise AssertionError("memory guard must not copy the full source array")

    monkeypatch.setattr(volume_data_preparation, "sitk", _Sitk)
    monkeypatch.setattr(
        volume_data_preparation,
        "compute_auto_downsample_factor",
        lambda *_args, **_kwargs: 2,
    )
    monkeypatch.setattr(
        volume_data_preparation,
        "_available_system_memory_bytes",
        lambda: 8,
    )

    prepared = VolumeRenderer.prepare_volume_data(_Image())

    np.testing.assert_array_equal(prepared.array, source[::2, ::2, ::2])
    assert prepared.array.flags.owndata
    assert prepared.array.flags.c_contiguous
    assert prepared.source_dimensions == (6, 4, 3)
    assert prepared.downsample_factor == 2
    assert prepared.spacing == (1.0, 3.0, 6.0)
    assert prepared.origin == (10.0, 20.0, 30.0)
    assert prepared.direction == (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
    assert prepared.estimated_peak_bytes is not None
    assert calls == ["size", "view"]


# ---------------------------------------------------------------------------
# Task B Step 1 — in-place calibration ownership contract and fallback safety
# ---------------------------------------------------------------------------

def test_calibrate_volume_array_ownership_contract_asserts_owndata() -> None:
    """_calibrate_volume_array must reject non-owned (view) arrays.

    The early-return on ``not source_datasets`` fires before the asserts, so
    we pass a matching-length dummy dataset list to reach the ownership check.
    """
    import pytest

    arr = np.ones((2, 3, 3), dtype=np.float32)
    view = arr[0:2]  # a view — owndata is False
    assert not view.flags.owndata

    from core.volume_renderer import _calibrate_volume_array

    # Dummy datasets matching the slice count so we reach the asserts.
    dummy_ds = [object() for _ in range(view.shape[0])]

    with pytest.raises(AssertionError):
        _calibrate_volume_array(view, source_datasets=dummy_ds)


def test_calibrate_volume_array_ownership_contract_asserts_float32() -> None:
    """_calibrate_volume_array must reject non-float32 arrays."""
    import pytest

    arr = np.ones((2, 3, 3), dtype=np.float64)  # owned but wrong dtype
    assert arr.flags.owndata

    from core.volume_renderer import _calibrate_volume_array

    dummy_ds = [object() for _ in range(arr.shape[0])]

    with pytest.raises(AssertionError):
        _calibrate_volume_array(arr, source_datasets=dummy_ds)


def test_calibrate_volume_array_mutates_in_place_no_extra_copy() -> None:
    """In-place calibration must not allocate a second full-size float32 buffer."""
    study_uid = generate_uid()
    series_uid = generate_uid()
    datasets = [
        _make_ct_dataset(
            np.full((4, 4), 1000, dtype=np.uint16),
            z=float(i), slope=1.0, intercept=-1024.0,
            instance_number=i + 1, study_uid=study_uid, series_uid=series_uid,
        )
        for i in range(3)
    ]
    volume = MprVolume.from_datasets(datasets)
    vd = VolumeRenderer.prepare_volume_data(
        volume.sitk_image,
        source_datasets=volume.source_datasets,
        apply_rescale=True,
    )
    # The returned array must be owned and contiguous — no lingering copy.
    assert vd.array.flags.owndata
    assert vd.array.flags.c_contiguous
    assert vd.array.dtype == np.float32
    assert vd.rescale_applied is True
    np.testing.assert_allclose(vd.array[:, 0, 0], [-24.0, -24.0, -24.0])


def test_calibrate_in_place_fallback_does_not_return_partial_mutation() -> None:
    """When calibration would overflow float32, fallback returns raw unmutated.

    The preflight overflow guard must catch the case *before* any slice is
    mutated, so the returned array equals the original raw values exactly —
    no partial mutation, no leftover inf.
    """
    study_uid = generate_uid()
    series_uid = generate_uid()
    # slope=1e38 * 65535 overflows float32 to inf.  The preflight bound
    # (max(|lo|,|hi|) * |slope| + |intercept| >= f32_max) must catch this.
    datasets = [
        _make_ct_dataset(
            np.full((2, 2), 65535, dtype=np.uint16),
            z=float(i), slope=1e38, intercept=0.0,
            instance_number=i + 1, study_uid=study_uid, series_uid=series_uid,
        )
        for i in range(3)
    ]
    volume = MprVolume.from_datasets(datasets)
    raw_values = sitk.GetArrayFromImage(volume.sitk_image).copy()

    vd = VolumeRenderer.prepare_volume_data(
        volume.sitk_image,
        source_datasets=volume.source_datasets,
        apply_rescale=True,
    )
    assert vd.rescale_applied is False
    assert vd.scalar_units is None
    # The returned array must equal the original raw values — no partial
    # mutation, no leftover inf.
    np.testing.assert_allclose(vd.array, raw_values)
    assert np.all(np.isfinite(vd.array))


def test_calibrate_overflow_with_finite_raw_and_extreme_slope() -> None:
    """Regression: finite raw values + extreme-but-finite slope → raw fallback.

    Uses the largest finite float32 slope that still overflows when multiplied
    by a realistic pixel value.  Guards against a regression where the overflow
    guard is removed and the inverse-transform fallback silently returns inf.
    """
    study_uid = generate_uid()
    series_uid = generate_uid()
    # np.finfo(np.float32).max ≈ 3.4e38; slope just below that, times a
    # realistic pixel value (4095), overflows to inf.
    slope = np.finfo(np.float32).max / 2.0  # ~1.7e38, finite
    datasets = [
        _make_ct_dataset(
            np.full((2, 2), 4095, dtype=np.uint16),
            z=float(i), slope=float(slope), intercept=0.0,
            instance_number=i + 1, study_uid=study_uid, series_uid=series_uid,
        )
        for i in range(3)
    ]
    volume = MprVolume.from_datasets(datasets)
    raw_values = sitk.GetArrayFromImage(volume.sitk_image).copy()

    vd = VolumeRenderer.prepare_volume_data(
        volume.sitk_image,
        source_datasets=volume.source_datasets,
        apply_rescale=True,
    )
    assert vd.rescale_applied is False
    assert vd.scalar_units is None
    np.testing.assert_allclose(vd.array, raw_values)
    assert np.all(np.isfinite(vd.array))


def test_calibrate_preflight_catches_bad_slice_before_any_mutation() -> None:
    """A bad slice must cause fallback before any slice is mutated.

    The preflight pass validates every slice's metadata before mutation, so a
    single bad slice (here: zero slope on slice 1) means *no* slice is touched.
    """
    study_uid = generate_uid()
    series_uid = generate_uid()
    datasets = [
        _make_ct_dataset(
            np.full((2, 2), 500, dtype=np.uint16),
            z=0.0, slope=1.0, intercept=-1024.0,
            instance_number=1, study_uid=study_uid, series_uid=series_uid,
        ),
        _make_ct_dataset(
            np.full((2, 2), 500, dtype=np.uint16),
            z=1.0, slope=0.0, intercept=0.0,  # zero slope → invalid
            instance_number=2, study_uid=study_uid, series_uid=series_uid,
        ),
        _make_ct_dataset(
            np.full((2, 2), 500, dtype=np.uint16),
            z=2.0, slope=1.0, intercept=-1024.0,
            instance_number=3, study_uid=study_uid, series_uid=series_uid,
        ),
    ]
    volume = MprVolume.from_datasets(datasets)
    raw_values = sitk.GetArrayFromImage(volume.sitk_image).copy()

    vd = VolumeRenderer.prepare_volume_data(
        volume.sitk_image,
        source_datasets=volume.source_datasets,
        apply_rescale=True,
    )
    assert vd.rescale_applied is False
    # No slice should have been mutated — the returned array equals raw.
    np.testing.assert_allclose(vd.array, raw_values)


def test_calibrate_applies_tiny_nonzero_rescale_slope() -> None:
    """Exact-zero policy: a tiny-but-nonzero RescaleSlope still calibrates.

    Pins that only exact ``0.0`` is rejected — prevents silent epsilon creep
    in ``is_usable_rescale_slope``.
    """
    study_uid = generate_uid()
    series_uid = generate_uid()
    tiny_slope = 1e-12
    datasets = [
        _make_ct_dataset(
            np.full((2, 2), 500, dtype=np.uint16),
            z=float(i),
            slope=tiny_slope,
            intercept=0.0,
            instance_number=i + 1,
            study_uid=study_uid,
            series_uid=series_uid,
        )
        for i in range(3)
    ]
    volume = MprVolume.from_datasets(datasets)
    raw_values = sitk.GetArrayFromImage(volume.sitk_image).astype(np.float32)

    vd = VolumeRenderer.prepare_volume_data(
        volume.sitk_image,
        source_datasets=volume.source_datasets,
        apply_rescale=True,
    )
    assert vd.rescale_applied is True
    np.testing.assert_allclose(vd.array, raw_values * np.float32(tiny_slope))


def test_calibrate_values_bit_identical_to_legacy_copy_path() -> None:
    """In-place calibration must produce bit-identical values to the old copy path.

    This guards against regressions: the mathematical result must be identical
    whether we mutate in place or copy-then-mutate.
    """
    study_uid = generate_uid()
    series_uid = generate_uid()
    datasets = [
        _make_ct_dataset(
            np.full((3, 3), 1024 + i * 50, dtype=np.uint16),
            z=float(i), slope=1.5, intercept=-200.0,
            instance_number=i + 1, study_uid=study_uid, series_uid=series_uid,
        )
        for i in range(4)
    ]
    volume = MprVolume.from_datasets(datasets)
    raw = sitk.GetArrayFromImage(volume.sitk_image)

    vd = VolumeRenderer.prepare_volume_data(
        volume.sitk_image,
        source_datasets=volume.source_datasets,
        apply_rescale=True,
    )
    assert vd.rescale_applied is True
    # Match the previous copy-then-mutate path operation for operation.
    expected = np.ascontiguousarray(raw, dtype=np.float32).copy()
    for z_index in range(expected.shape[0]):
        expected[z_index] = expected[z_index] * 1.5 + (-200.0)
    np.testing.assert_array_equal(vd.array, expected)

"""
Unit tests for core.image_resampler.ImageResampler (SimpleITK-based 3D volume
resampling for image fusion).

Real pydicom datasets with actual PixelData plus spatial tags (ImagePosition/
OrientationPatient, PixelSpacing, SliceThickness) are used so SimpleITK's real
conversion/resampling machinery runs end-to-end rather than being mocked out.
"""

from __future__ import annotations

import numpy as np
import pytest
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

from core.image_resampler import ImageResampler


def _make_ct_dataset(
    z,
    pixel_value=100,
    rows=4,
    cols=4,
    iop=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0),
    pixel_spacing=(1.0, 1.0),
    slice_thickness=1.0,
    sop_uid=None,
    rescale_slope=None,
    rescale_intercept=None,
):
    arr = np.full((rows, cols), pixel_value, dtype=np.uint16)
    ds = Dataset()
    ds.file_meta = FileMetaDataset()
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.SOPClassUID = generate_uid()
    ds.SOPInstanceUID = sop_uid or generate_uid()
    ds.Modality = "CT"
    ds.Rows = rows
    ds.Columns = cols
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.PixelRepresentation = 0
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelData = arr.tobytes()
    ds.ImagePositionPatient = [0.0, 0.0, float(z)]
    ds.ImageOrientationPatient = list(iop)
    ds.PixelSpacing = list(pixel_spacing)
    ds.SliceThickness = slice_thickness
    if rescale_slope is not None:
        ds.RescaleSlope = rescale_slope
    if rescale_intercept is not None:
        ds.RescaleIntercept = rescale_intercept
    return ds


def _make_series(values, **kwargs):
    return [_make_ct_dataset(z=i, pixel_value=v, **kwargs) for i, v in enumerate(values)]


@pytest.fixture
def resampler():
    return ImageResampler()


class TestGetLocation:
    def test_uses_slice_location_when_present(self, resampler):
        ds = _make_ct_dataset(z=5.0)
        ds.SliceLocation = 42.0
        assert resampler._get_location(ds) == 42.0

    def test_falls_back_to_image_position_patient_z(self, resampler):
        ds = _make_ct_dataset(z=7.5)
        assert resampler._get_location(ds) == 7.5

    def test_returns_none_when_neither_available(self, resampler):
        ds = Dataset()
        assert resampler._get_location(ds) is None

    def test_invalid_slice_location_falls_back_to_ipp(self, resampler):
        # SimpleNamespace stand-in: pydicom's DS VR would reject a non-numeric
        # string outright, but _get_location only does getattr + float().
        from types import SimpleNamespace
        ds = SimpleNamespace(SliceLocation="not-a-number", ImagePositionPatient=[0.0, 0.0, 3.0])
        assert resampler._get_location(ds) == 3.0


class TestSortDatasetsByLocation:
    def test_sorts_ascending_by_z(self, resampler):
        datasets = _make_series([10, 20, 30])
        shuffled = [datasets[2], datasets[0], datasets[1]]
        sorted_ds = resampler._sort_datasets_by_location(shuffled)
        assert [d.ImagePositionPatient[2] for d in sorted_ds] == [0.0, 1.0, 2.0]

    def test_filters_out_datasets_without_location(self, resampler):
        ds_valid = _make_ct_dataset(z=0.0)
        ds_invalid = Dataset()
        result = resampler._sort_datasets_by_location([ds_valid, ds_invalid])
        assert result == [ds_valid]

    def test_empty_input_returns_empty(self, resampler):
        assert resampler._sort_datasets_by_location([]) == []

    def test_slice_at_z_zero_sorts_to_correct_position_not_end(self, resampler):
        # Regression test: a location of exactly 0.0 must not be treated as
        # "missing" (falsy-zero bug) and sorted to the end.
        datasets = _make_series([10, 20, 30])  # z = 0, 1, 2
        shuffled = [datasets[2], datasets[0], datasets[1]]
        sorted_ds = resampler._sort_datasets_by_location(shuffled)
        assert [d.ImagePositionPatient[2] for d in sorted_ds] == [0.0, 1.0, 2.0]


class TestFilterDuplicateLocations:
    def test_keeps_first_occurrence_of_duplicate_locations(self, resampler):
        ds1 = _make_ct_dataset(z=0.0, pixel_value=1)
        ds2 = _make_ct_dataset(z=0.0, pixel_value=2)
        ds3 = _make_ct_dataset(z=1.0, pixel_value=3)
        result = resampler._filter_duplicate_locations([ds1, ds2, ds3])
        assert result == [ds1, ds3]

    def test_treats_near_duplicates_within_tolerance_as_same(self, resampler):
        ds1 = _make_ct_dataset(z=0.0)
        ds2 = _make_ct_dataset(z=0.005)
        result = resampler._filter_duplicate_locations([ds1, ds2])
        assert result == [ds1]

    def test_skips_datasets_without_valid_location(self, resampler):
        ds_valid = _make_ct_dataset(z=0.0)
        ds_invalid = Dataset()
        result = resampler._filter_duplicate_locations([ds_valid, ds_invalid])
        assert result == [ds_valid]

    def test_empty_input_returns_empty(self, resampler):
        assert resampler._filter_duplicate_locations([]) == []


class TestDicomSeriesToSitk:
    def test_returns_none_for_empty_datasets(self, resampler):
        assert resampler.dicom_series_to_sitk([]) is None

    def test_converts_series_with_correct_shape_and_values(self, resampler):
        datasets = _make_series([10, 20, 30])
        sitk_image = resampler.dicom_series_to_sitk(datasets)
        assert sitk_image is not None
        arr = resampler.sitk_to_numpy(sitk_image)
        assert arr.shape == (3, 4, 4)
        assert list(arr[:, 0, 0]) == [10.0, 20.0, 30.0]

    def test_sets_origin_from_first_slice_position(self, resampler):
        datasets = _make_series([10, 20])
        sitk_image = resampler.dicom_series_to_sitk(datasets)
        assert sitk_image.GetOrigin() == (0.0, 0.0, 0.0)

    def test_sets_spacing_from_pixel_spacing_and_slice_gap(self, resampler):
        datasets = _make_series([10, 20], pixel_spacing=(2.0, 3.0))
        sitk_image = resampler.dicom_series_to_sitk(datasets)
        # SimpleITK spacing is (x, y, z) = (col_spacing, row_spacing, slice_spacing)
        sx, sy, sz = sitk_image.GetSpacing()
        assert sx == pytest.approx(3.0)
        assert sy == pytest.approx(2.0)
        assert sz == pytest.approx(1.0)

    def test_applies_rescale_slope_and_intercept_per_slice(self, resampler):
        datasets = _make_series([10, 20], rescale_slope=2.0, rescale_intercept=-100.0)
        sitk_image = resampler.dicom_series_to_sitk(datasets)
        arr = resampler.sitk_to_numpy(sitk_image)
        assert list(arr[:, 0, 0]) == [-80.0, -60.0]

    def test_single_slice_uses_slice_thickness_for_spacing(self, resampler):
        datasets = _make_series([10], slice_thickness=2.5)
        sitk_image = resampler.dicom_series_to_sitk(datasets)
        _, _, sz = sitk_image.GetSpacing()
        assert sz == pytest.approx(2.5)

    def test_returns_none_when_no_valid_locations(self, resampler):
        ds = Dataset()
        ds.file_meta = FileMetaDataset()
        assert resampler.dicom_series_to_sitk([ds]) is None

    def test_returns_none_on_pixel_array_extraction_failure(self, resampler, monkeypatch):
        datasets = _make_series([10, 20])

        def bad_pixel_array(self):
            raise ValueError("corrupt pixel data")

        monkeypatch.setattr(Dataset, "pixel_array", property(bad_pixel_array))
        assert resampler.dicom_series_to_sitk(datasets) is None


class TestSitkToNumpy:
    def test_returns_none_for_none_image(self, resampler):
        assert resampler.sitk_to_numpy(None) is None

    def test_round_trips_pixel_values(self, resampler):
        datasets = _make_series([5, 15])
        sitk_image = resampler.dicom_series_to_sitk(datasets)
        arr = resampler.sitk_to_numpy(sitk_image)
        assert arr is not None
        assert arr.shape == (2, 4, 4)


class TestResampleToReference:
    def test_returns_none_when_moving_is_none(self, resampler):
        assert resampler.resample_to_reference(None, object()) is None

    def test_returns_none_when_reference_is_none(self, resampler):
        assert resampler.resample_to_reference(object(), None) is None

    def test_resamples_identical_grid_to_same_values(self, resampler):
        overlay = resampler.dicom_series_to_sitk(_make_series([10, 20, 30]))
        reference = resampler.dicom_series_to_sitk(_make_series([1, 2, 3]))
        resampled = resampler.resample_to_reference(overlay, reference)
        assert resampled is not None
        arr = resampler.sitk_to_numpy(resampled)
        np.testing.assert_allclose(arr[:, 0, 0], [10.0, 20.0, 30.0], atol=1e-4)

    def test_unknown_interpolator_falls_back_to_linear(self, resampler):
        overlay = resampler.dicom_series_to_sitk(_make_series([10, 20]))
        reference = resampler.dicom_series_to_sitk(_make_series([1, 2]))
        resampled = resampler.resample_to_reference(overlay, reference, interpolator="bogus")
        assert resampled is not None


class TestGetResampledSlice:
    def test_returns_none_for_negative_slice_index(self, resampler):
        reference = _make_series([1, 2])
        overlay = _make_series([10, 20])
        assert resampler.get_resampled_slice(overlay, reference, -1) is None

    def test_returns_none_when_slice_index_out_of_range(self, resampler):
        reference = _make_series([1, 2])
        overlay = _make_series([10, 20])
        assert resampler.get_resampled_slice(overlay, reference, 5) is None

    def test_returns_none_for_empty_reference_datasets(self, resampler):
        overlay = _make_series([10, 20])
        assert resampler.get_resampled_slice(overlay, [], 0) is None

    def test_returns_resampled_slice_matching_overlay_values(self, resampler):
        reference = _make_series([1, 2, 3])
        overlay = _make_series([10, 20, 30])
        result = resampler.get_resampled_slice(overlay, reference, 1)
        assert result is not None
        assert result.dtype == np.float32
        np.testing.assert_allclose(result, np.full((4, 4), 20.0), atol=1e-4)

    def test_caches_resampled_volume_across_calls(self, resampler, monkeypatch):
        reference = _make_series([1, 2, 3])
        overlay = _make_series([10, 20, 30])
        call_count = {"n": 0}
        original = resampler.dicom_series_to_sitk

        def counting_wrapper(datasets, series_uid=None):
            call_count["n"] += 1
            return original(datasets, series_uid)

        monkeypatch.setattr(resampler, "dicom_series_to_sitk", counting_wrapper)

        resampler.get_resampled_slice(
            overlay, reference, 0, overlay_series_uid="ov", reference_series_uid="ref"
        )
        first_call_count = call_count["n"]
        resampler.get_resampled_slice(
            overlay, reference, 1, overlay_series_uid="ov", reference_series_uid="ref"
        )
        assert call_count["n"] == first_call_count  # no new sitk conversion on cache hit

    def test_use_cache_false_bypasses_cache(self, resampler):
        reference = _make_series([1, 2, 3])
        overlay = _make_series([10, 20, 30])
        result1 = resampler.get_resampled_slice(
            overlay, reference, 0, use_cache=False,
            overlay_series_uid="ov", reference_series_uid="ref",
        )
        result2 = resampler.get_resampled_slice(
            overlay, reference, 0, use_cache=False,
            overlay_series_uid="ov", reference_series_uid="ref",
        )
        assert result1 is not None
        np.testing.assert_allclose(result1, result2, atol=1e-4)

    def test_returns_none_when_overlay_conversion_fails(self, resampler):
        reference = _make_series([1, 2])
        overlay = [Dataset()]  # no spatial metadata -> conversion fails
        assert resampler.get_resampled_slice(overlay, reference, 0) is None

    def test_handles_duplicate_reference_location_via_tolerance_search(self, resampler):
        # Reference has a duplicate location that gets filtered out during
        # sort+dedup; requested slice_idx targets the duplicate and must be
        # located by nearest-location search instead of direct list lookup.
        ds_a = _make_ct_dataset(z=0.0, pixel_value=1)
        ds_b = _make_ct_dataset(z=0.0, pixel_value=1)  # duplicate location
        ds_c = _make_ct_dataset(z=1.0, pixel_value=2)
        reference = [ds_a, ds_b, ds_c]
        overlay = _make_series([10, 20])
        result = resampler.get_resampled_slice(overlay, reference, 1)  # ds_b, duplicate of ds_a
        assert result is not None


class TestCalculateSliceSpacing:
    def test_returns_none_for_fewer_than_two_datasets(self, resampler):
        assert resampler._calculate_slice_spacing(_make_series([1])) is None

    def test_computes_median_spacing_along_slice_normal(self, resampler):
        datasets = _make_series([1, 2, 3])
        spacing = resampler._calculate_slice_spacing(datasets)
        assert spacing == pytest.approx(1.0)

    def test_falls_back_to_euclidean_distance_without_orientation(self, resampler):
        datasets = _make_series([1, 2])
        for ds in datasets:
            del ds.ImageOrientationPatient
        spacing = resampler._calculate_slice_spacing(datasets)
        assert spacing == pytest.approx(1.0)

    def test_returns_none_when_no_valid_spacings(self, resampler):
        ds1 = Dataset()
        ds1.SliceLocation = 0.0
        ds2 = Dataset()
        ds2.SliceLocation = 1.0
        assert resampler._calculate_slice_spacing([ds1, ds2]) is None


class TestNeedsResampling:
    def test_true_when_datasets_missing(self, resampler):
        needs, reason = resampler.needs_resampling([], _make_series([1]))
        assert needs is True
        assert "Missing datasets" in reason

    def test_true_when_orientation_missing(self, resampler):
        ds = Dataset()
        ds.file_meta = FileMetaDataset()
        needs, reason = resampler.needs_resampling([ds], _make_series([1]))
        assert needs is True
        assert "orientation" in reason.lower()

    def test_true_for_different_orientation(self, resampler):
        overlay = _make_series([1], iop=(0.0, 1.0, 0.0, 0.0, 0.0, -1.0))  # sagittal
        reference = _make_series([1], iop=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0))  # axial
        needs, reason = resampler.needs_resampling(overlay, reference)
        assert needs is True
        assert "orientation" in reason.lower()

    def test_true_for_large_thickness_ratio(self, resampler):
        overlay = _make_series([1], slice_thickness=1.0)
        reference = _make_series([1], slice_thickness=3.0)
        needs, reason = resampler.needs_resampling(overlay, reference)
        assert needs is True
        assert "thickness" in reason.lower()

    def test_true_for_large_spacing_ratio(self, resampler):
        overlay = _make_series([1, 2, 3])  # spacing 1mm
        reference = [
            _make_ct_dataset(z=0.0),
            _make_ct_dataset(z=3.0),
            _make_ct_dataset(z=6.0),
        ]  # spacing 3mm
        needs, reason = resampler.needs_resampling(overlay, reference)
        assert needs is True
        assert "spacing" in reason.lower()

    def test_false_when_compatible(self, resampler):
        overlay = _make_series([1, 2, 3])
        reference = _make_series([4, 5, 6])
        needs, reason = resampler.needs_resampling(overlay, reference)
        assert needs is False
        assert "Compatible" in reason


class TestClearCache:
    def test_clears_entire_cache_when_no_series_uid(self, resampler):
        reference = _make_series([1, 2])
        overlay = _make_series([10, 20])
        resampler.get_resampled_slice(
            overlay, reference, 0, overlay_series_uid="ov", reference_series_uid="ref"
        )
        assert len(resampler._cache) == 1
        resampler.clear_cache()
        assert len(resampler._cache) == 0
        assert len(resampler._numpy_cache) == 0
        assert len(resampler._sorted_ref_cache) == 0

    def test_clears_only_entries_matching_series_uid(self, resampler):
        reference = _make_series([1, 2])
        overlay = _make_series([10, 20])
        resampler.get_resampled_slice(
            overlay, reference, 0, overlay_series_uid="ov", reference_series_uid="ref"
        )
        resampler.clear_cache("other_series")
        assert len(resampler._cache) == 1
        resampler.clear_cache("ov")
        assert len(resampler._cache) == 0

    def test_clear_cache_noop_on_empty_cache(self, resampler):
        resampler.clear_cache()  # should not raise
        resampler.clear_cache("nonexistent")  # should not raise


class TestCacheEviction:
    def test_lru_eviction_when_over_capacity(self, resampler):
        reference = _make_series([1, 2])
        for i in range(resampler._MAX_CACHE_ENTRIES + 2):
            overlay = _make_series([i, i + 1])
            resampler.get_resampled_slice(
                overlay, reference, 0,
                overlay_series_uid=f"ov{i}", reference_series_uid="ref",
            )
        assert len(resampler._cache) == resampler._MAX_CACHE_ENTRIES

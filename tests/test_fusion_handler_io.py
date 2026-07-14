"""Unit tests for pure helpers in core.fusion_handler_io."""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace

from pydicom.dataset import Dataset

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.fusion_handler_io import (
    check_frame_of_reference_match,
    read_image_position_patient,
    read_pixel_spacing,
    read_pixel_spacing_with_source,
    read_slice_location,
    series_spatial_info_dict,
    sorted_slice_index_locations,
    translation_offset_pixels_from_ipps,
)


def test_read_slice_location_uses_direct_value_first() -> None:
    ds = Dataset()
    ds.SliceLocation = "12.5"
    ds.ImagePositionPatient = [1.0, 2.0, 99.0]
    assert read_slice_location(ds) == 12.5


def test_read_slice_location_falls_back_to_image_position_patient_z() -> None:
    ds = SimpleNamespace(SliceLocation="not-a-float", ImagePositionPatient=[1.0, 2.0, 33.5])
    assert read_slice_location(ds) == 33.5


def test_read_slice_location_returns_none_for_missing_or_invalid_geometry() -> None:
    ds = SimpleNamespace(ImagePositionPatient=["bad"])
    assert read_slice_location(ds) is None


def test_read_pixel_spacing_parses_two_values() -> None:
    ds = Dataset()
    ds.PixelSpacing = [0.8, 1.2]
    assert read_pixel_spacing(ds) == (0.8, 1.2)


def test_read_pixel_spacing_returns_none_for_invalid_values() -> None:
    ds = SimpleNamespace(PixelSpacing=["bad", 1.2])
    assert read_pixel_spacing(ds) is None


def test_read_pixel_spacing_with_source_prefers_pixel_spacing() -> None:
    ds = Dataset()
    ds.PixelSpacing = [0.7, 0.9]
    ds.ImagerPixelSpacing = [1.5, 1.6]
    assert read_pixel_spacing_with_source(ds) == ((0.7, 0.9), "pixel_spacing")


def test_read_pixel_spacing_with_source_falls_back_to_imager_spacing() -> None:
    ds = Dataset()
    ds.ImagerPixelSpacing = [1.5, 1.6]
    assert read_pixel_spacing_with_source(ds) == ((1.5, 1.6), "pixel_spacing")


def test_read_pixel_spacing_with_source_uses_reconstruction_diameter_heuristic() -> None:
    ds = Dataset()
    ds.ReconstructionDiameter = 400.0
    ds.Rows = 100
    ds.Columns = 200
    assert read_pixel_spacing_with_source(ds) == ((4.0, 2.0), "reconDiameter_cols")


def test_read_image_position_patient_parses_xyz() -> None:
    ds = Dataset()
    ds.ImagePositionPatient = [1.0, 2.0, 3.0]
    assert read_image_position_patient(ds) == (1.0, 2.0, 3.0)


def test_check_frame_of_reference_match_requires_same_uid() -> None:
    ds1 = Dataset()
    ds1.FrameOfReferenceUID = "1.2.3"
    ds2 = Dataset()
    ds2.FrameOfReferenceUID = "1.2.3"
    ds3 = Dataset()
    ds3.FrameOfReferenceUID = "9.9.9"
    assert check_frame_of_reference_match([ds1], [ds2]) is True
    assert check_frame_of_reference_match([ds1], [ds3]) is False


def test_sorted_slice_index_locations_omits_slices_without_locations() -> None:
    ds0 = Dataset()
    ds0.SliceLocation = 10.0
    ds1 = Dataset()
    ds1.ImagePositionPatient = [0.0, 0.0, 5.0]
    ds2 = Dataset()
    result = sorted_slice_index_locations([ds0, ds1, ds2])
    assert result == [(1, 5.0), (0, 10.0)]


def test_translation_offset_pixels_from_ipps_without_iop_uses_xy_components() -> None:
    offset = translation_offset_pixels_from_ipps(
        base_ipp=(10.0, 20.0, 30.0),
        overlay_ipp=(18.0, 26.0, 999.0),
        base_pixel_spacing=(2.0, 4.0),
    )
    assert offset == (2.0, 3.0)


def test_translation_offset_pixels_from_ipps_projects_oblique_offset_with_iop() -> None:
    offset = translation_offset_pixels_from_ipps(
        base_ipp=(0.0, 0.0, 0.0),
        overlay_ipp=(8.0, 0.0, 6.0),
        base_pixel_spacing=(2.0, 4.0),
        iop=(1.0, 0.0, 0.0, 0.0, 0.0, 1.0),
    )
    assert offset == (2.0, 3.0)


def test_series_spatial_info_dict_empty_input_returns_empty_dict() -> None:
    assert series_spatial_info_dict([]) == {}


def test_series_spatial_info_dict_includes_fov_and_matrix_size() -> None:
    ds = Dataset()
    ds.PixelSpacing = [2.0, 3.0]
    ds.ImagePositionPatient = [10.0, 20.0, 30.0]
    ds.Rows = 4
    ds.Columns = 5
    info = series_spatial_info_dict([ds])
    assert info["pixel_spacing"] == (2.0, 3.0)
    assert info["image_position"] == (10.0, 20.0, 30.0)
    assert info["matrix_size"] == (4, 5)
    assert info["field_of_view"] == (15.0, 8.0)

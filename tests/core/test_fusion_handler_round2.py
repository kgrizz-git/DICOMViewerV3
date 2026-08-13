"""Round-two unit coverage for deterministic FusionHandler state and geometry."""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian

from core.fusion_handler import FusionHandler, OverlayMatchResult


def _dataset(
    *,
    z: float | None = None,
    slice_location: float | None = None,
    for_uid: str | None = "1.2.3",
    spacing: tuple[float, float] | None = (1.0, 2.0),
    ipp: tuple[float, float, float] | None = None,
    pixels: np.ndarray | None = None,
) -> Dataset:
    """Build a small synthetic image dataset without clinical metadata."""
    ds = Dataset()
    if z is not None:
        ds.ImagePositionPatient = [0.0, 0.0, z]
    if slice_location is not None:
        ds.SliceLocation = slice_location
    if for_uid is not None:
        ds.FrameOfReferenceUID = for_uid
    if spacing is not None:
        ds.PixelSpacing = list(spacing)
    if ipp is not None:
        ds.ImagePositionPatient = list(ipp)
    if pixels is not None:
        values = np.asarray(pixels, dtype=np.uint16)
        ds.file_meta = FileMetaDataset()
        ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
        ds.Rows, ds.Columns = values.shape
        ds.SamplesPerPixel = 1
        ds.PhotometricInterpretation = "MONOCHROME2"
        ds.PixelRepresentation = 0
        ds.BitsAllocated = 16
        ds.BitsStored = 16
        ds.HighBit = 15
        ds.PixelData = values.tobytes()
    return ds


def test_setters_and_resampling_mode_reset_pair_state() -> None:
    handler = FusionHandler()
    handler.set_base_series("base-old")
    handler.set_overlay_series("overlay-old")
    handler.set_alignment("base-old", "overlay-old", (1.1, 0.9), (2.0, -1.0))
    handler._slice_location_cache["overlay-old"] = [(0, 1.0)]
    handler._actual_resampling_mode_used = True
    handler._resampling_failure_reason = "synthetic failure"

    handler.set_base_series("base-new")
    assert handler.get_alignment("base-old", "overlay-old") is None
    assert handler.get_actual_resampling_mode_used() is None
    assert handler.get_resampling_failure_reason() is None

    handler.set_overlay_series("overlay-new")
    handler.set_resampling_mode("fast")
    assert handler.resampling_mode == "fast"
    assert handler._slice_location_cache == {}
    assert handler._resampling_decision_cache is None
    assert handler._resampling_decision_cache_key is None


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    [
        ([_dataset(for_uid="1.2.3.1")], [_dataset(for_uid="1.2.3.1")], True),
        ([_dataset(for_uid="1.2.3.2")], [_dataset(for_uid="1.2.3.3")], False),
        ([], [_dataset()], False),
        ([_dataset(for_uid=None)], [_dataset()], False),
    ],
)
def test_frame_of_reference_checks_missing_and_mismatched_values(
    first: list[Dataset], second: list[Dataset], expected: bool
) -> None:
    assert FusionHandler().check_frame_of_reference_match(first, second) is expected


def test_slice_location_fallback_and_sorted_location_cache() -> None:
    handler = FusionHandler()
    fallback = _dataset(z=4.5)
    tagged = _dataset(z=9.0, slice_location=2.5)
    missing = _dataset()
    assert handler.get_slice_location(fallback) == 4.5
    assert handler.get_slice_location(tagged) == 2.5
    assert handler.get_slice_location(missing) is None

    datasets = [fallback, missing, tagged]
    locations = handler._get_sorted_slice_locations(datasets, "series")
    assert locations == [(2, 2.5), (0, 4.5)]
    assert handler._get_sorted_slice_locations([], "series") is locations


@pytest.mark.parametrize(
    ("base_z", "overlay_z", "expected"),
    [
        (5.0, [0.0, 10.0], (OverlayMatchResult.inside, 0, 1)),
        (-1.0, [0.0, 10.0], (OverlayMatchResult.below_stack, None, None)),
        (11.0, [0.0, 10.0], (OverlayMatchResult.above_stack, None, None)),
    ],
)
def test_matching_classifies_brackets_and_stack_boundaries(
    base_z: float, overlay_z: list[float], expected: tuple[OverlayMatchResult, int | None, int | None]
) -> None:
    handler = FusionHandler()
    handler.set_overlay_series("overlay")
    base = [_dataset(z=base_z)]
    overlay = [_dataset(z=value) for value in overlay_z]
    assert handler.find_matching_slice_with_classification(0, base, overlay) == expected


def test_matching_classifies_invalid_index_and_missing_geometry() -> None:
    handler = FusionHandler()
    assert handler.find_matching_slice_with_classification(1, [_dataset(z=0.0)], []) == (
        OverlayMatchResult.no_geometry,
        None,
        None,
    )
    assert handler.find_matching_slice_with_classification(0, [_dataset()], [_dataset(z=0.0)]) == (
        OverlayMatchResult.no_geometry,
        None,
        None,
    )
    assert handler.find_matching_slice(0, [_dataset(z=0.0)], []) == (None, None)


def test_spacing_ipp_and_series_spatial_info_use_dicom_and_heuristic_sources() -> None:
    handler = FusionHandler()
    ds = _dataset(ipp=(1.0, 2.0, 3.0), spacing=(0.5, 0.75))
    ds.Rows, ds.Columns = 4, 8
    assert handler.get_pixel_spacing(ds) == (0.5, 0.75)
    assert handler.get_pixel_spacing_with_source(ds) == ((0.5, 0.75), "pixel_spacing")
    assert handler.get_image_position_patient(ds) == (1.0, 2.0, 3.0)
    assert handler.get_series_spatial_info([ds]) == {
        "pixel_spacing": (0.5, 0.75),
        "image_position": (1.0, 2.0, 3.0),
        "matrix_size": (4, 8),
        "field_of_view": (6.0, 2.0),
    }

    heuristic = _dataset(spacing=None)
    heuristic.ReconstructionDiameter = 240.0
    heuristic.Rows, heuristic.Columns = 4, 8
    assert handler.get_pixel_spacing_with_source(heuristic) == (
        (60.0, 30.0),
        "reconDiameter_cols",
    )
    assert handler.get_pixel_spacing(_dataset(spacing=None)) is None
    assert handler.get_series_spatial_info([]) == {}


def test_translation_offset_handles_missing_ipp_and_oblique_orientation() -> None:
    handler = FusionHandler()
    assert handler.calculate_translation_offset(
        _dataset(), _dataset(ipp=(1.0, 1.0, 1.0)), (1.0, 1.0), (1.0, 1.0)
    ) is None
    base = _dataset(ipp=(0.0, 0.0, 0.0))
    base.ImageOrientationPatient = [0.0, 1.0, 0.0, -1.0, 0.0, 0.0]
    overlay = _dataset(ipp=(2.0, 3.0, 4.0))
    assert handler.calculate_translation_offset(base, overlay, (1.0, 2.0), (9.0, 9.0)) == (
        1.5,
        -2.0,
    )


def test_alignment_cache_supports_selective_and_global_clear() -> None:
    handler = FusionHandler()
    handler.set_alignment("base", "overlay", (1.0, 1.0), (2.0, 3.0))
    handler.set_alignment("other", "overlay", None, None)
    handler.set_alignment("base", "third", (2.0, 2.0), None)
    handler.set_alignment(None, "ignored", None, None)
    handler.clear_alignment_cache("overlay")
    assert handler.get_alignment("base", "overlay") is None
    assert handler.get_alignment("base", "third") is not None
    handler.clear_alignment_cache()
    assert handler.get_alignment("base", "third") is None


def test_available_series_and_resampling_status_cover_display_fallbacks() -> None:
    handler = FusionHandler()
    unnamed = _dataset()
    numbered = _dataset()
    numbered.Modality = "MR"
    studies = {"study": {"unnamed-series": [unnamed], "numbered-series": [numbered]}}
    assert handler.get_available_series_for_fusion(studies, "study") == [
        ("unnamed-series", "unnamed-series"),
        ("numbered-series", "MR"),
    ]

    handler.image_resampler = MagicMock()
    handler.image_resampler.needs_resampling.return_value = (False, "same geometry")
    base = [_dataset(z=0.0)]
    overlay = [_dataset(z=0.0)]
    handler.set_resampling_mode("fast")
    assert handler.get_resampling_status(base, overlay) == (
        "Fast Mode (2D)",
        "User selected Fast Mode (2D)",
    )
    handler.set_resampling_mode("unknown")
    assert handler.get_resampling_status(base, overlay) == (
        "High Accuracy (3D)",
        "Defaulting to High Accuracy Mode (3D)",
    )

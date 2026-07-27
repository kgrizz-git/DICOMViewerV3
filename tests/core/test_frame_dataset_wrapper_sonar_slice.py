"""
Characterization tests for FrameDatasetWrapper init helpers (Sonar S3776 slice).

Covers nested functional-group attribute extraction used by
``FrameDatasetWrapper.__init__`` without changing geometry/rescale/VOI behavior.
"""

from __future__ import annotations

from pydicom.dataset import Dataset
from pydicom.sequence import Sequence

from core.multiframe_handler import (
    _PIXEL_MEASURE_ATTRS,
    _RESCALE_ATTRS,
    _VOI_LUT_ATTRS,
    FrameDatasetWrapper,
    _apply_attrs_from_functional_groups,
    _apply_per_frame_plane_geometry,
    _apply_shared_plane_geometry_if_unset,
    _nested_sequence_attr,
    _set_local_attr_if_unset,
)


def _plane_pos(z: float) -> Dataset:
    item = Dataset()
    item.ImagePositionPatient = [0.0, 0.0, z]
    fg = Dataset()
    fg.PlanePositionSequence = Sequence([item])
    return fg


def _plane_orient() -> Dataset:
    item = Dataset()
    item.ImageOrientationPatient = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
    fg = Dataset()
    fg.PlaneOrientationSequence = Sequence([item])
    return fg


def test_nested_sequence_attr_missing_and_present() -> None:
    empty = Dataset()
    assert _nested_sequence_attr(empty, "PlanePositionSequence", "ImagePositionPatient") is None

    fg = _plane_pos(3.5)
    assert list(_nested_sequence_attr(fg, "PlanePositionSequence", "ImagePositionPatient")) == [
        0.0,
        0.0,
        3.5,
    ]


def test_set_local_attr_if_unset_skips_existing() -> None:
    wrapper = FrameDatasetWrapper(Dataset(), 0)
    wrapper._set_local_value("SliceThickness", 2.0)
    _set_local_attr_if_unset(wrapper, "SliceThickness", 9.0)
    assert float(wrapper.SliceThickness) == 2.0
    _set_local_attr_if_unset(wrapper, "SpacingBetweenSlices", 4.0)
    assert float(wrapper.SpacingBetweenSlices) == 4.0
    _set_local_attr_if_unset(wrapper, "PixelSpacing", None)
    assert wrapper.get("PixelSpacing") is None


def test_apply_per_frame_and_shared_plane_geometry() -> None:
    wrapper = FrameDatasetWrapper(Dataset(), 0)
    _apply_per_frame_plane_geometry(wrapper, _plane_pos(7.5))
    assert float(wrapper.ImagePositionPatient[2]) == 7.5

    shared = _plane_orient()
    shared_ipp = Dataset()
    shared_ipp.ImagePositionPatient = [1.0, 2.0, 3.0]
    shared.PlanePositionSequence = Sequence([shared_ipp])
    # IPP already set from per-frame — shared must not replace it; IOP fills gap.
    _apply_shared_plane_geometry_if_unset(wrapper, shared)
    assert float(wrapper.ImagePositionPatient[2]) == 7.5
    assert list(wrapper.ImageOrientationPatient) == [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]


def test_shared_measures_win_over_per_frame_when_both_present() -> None:
    """Preserves prior walk order: shared first, only fill unset attrs."""
    shared_fg = Dataset()
    shared_pm = Dataset()
    shared_pm.PixelSpacing = [0.5, 0.5]
    shared_pm.SliceThickness = 1.0
    shared_fg.PixelMeasuresSequence = Sequence([shared_pm])
    shared_seq = Sequence([shared_fg])

    per_frame_fg = Dataset()
    per_pm = Dataset()
    per_pm.PixelSpacing = [0.9, 0.9]
    per_pm.SliceThickness = 5.0
    per_pm.SpacingBetweenSlices = 5.0
    per_frame_fg.PixelMeasuresSequence = Sequence([per_pm])
    per_frame_seq = Sequence([per_frame_fg])

    wrapper = FrameDatasetWrapper(Dataset(), 0)
    _apply_attrs_from_functional_groups(
        wrapper,
        shared_seq,
        per_frame_seq,
        0,
        "PixelMeasuresSequence",
        _PIXEL_MEASURE_ATTRS,
    )
    assert list(wrapper.PixelSpacing) == [0.5, 0.5]
    assert float(wrapper.SliceThickness) == 1.0
    # Only present on per-frame — still filled as a gap.
    assert float(wrapper.SpacingBetweenSlices) == 5.0


def test_frame_wrapper_init_copies_rescale_and_voi_from_shared() -> None:
    ds = Dataset()
    ds.NumberOfFrames = 2
    ds.PerFrameFunctionalGroupsSequence = Sequence([Dataset(), Dataset()])
    shared = Dataset()
    transform = Dataset()
    transform.RescaleSlope = 2
    transform.RescaleIntercept = -1024
    transform.RescaleType = "HU"
    shared.PixelValueTransformationSequence = Sequence([transform])
    voi = Dataset()
    voi.WindowCenter = 40
    voi.WindowWidth = 400
    voi.WindowCenterWidthExplanation = "SOFT_TISSUE"
    shared.FrameVOILUTSequence = Sequence([voi])
    ds.SharedFunctionalGroupsSequence = Sequence([shared])

    wrapper = FrameDatasetWrapper(ds, 1)
    assert wrapper.NumberOfFrames == 1
    assert float(wrapper.RescaleSlope) == 2.0
    assert float(wrapper.RescaleIntercept) == -1024.0
    assert wrapper.RescaleType == "HU"
    assert float(wrapper.WindowCenter) == 40.0
    assert float(wrapper.WindowWidth) == 400.0
    assert wrapper.WindowCenterWidthExplanation == "SOFT_TISSUE"
    assert _RESCALE_ATTRS[0] == "RescaleSlope"
    assert _VOI_LUT_ATTRS[0] == "WindowCenter"

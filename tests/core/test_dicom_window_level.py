"""
Tests for DICOM window/level extraction helpers.
"""

from __future__ import annotations

from pydicom.dataset import Dataset
from pydicom.sequence import Sequence

from core.dicom_window_level import get_window_level_presets_from_dataset
from core.multiframe_handler import create_frame_dataset


def test_get_window_level_presets_uses_explanations() -> None:
    ds = Dataset()
    ds.WindowCenter = [10, 20, 30]
    ds.WindowWidth = [100, 200, 300]
    ds.WindowCenterWidthExplanation = ["NORMAL", "HARDER", "SOFTER"]

    presets = get_window_level_presets_from_dataset(ds)

    assert [preset[3] for preset in presets] == ["NORMAL", "HARDER", "SOFTER"]


def test_get_window_level_presets_uses_numeric_fallbacks_without_explanations() -> None:
    ds = Dataset()
    ds.WindowCenter = [10, 20, 30]
    ds.WindowWidth = [100, 200, 300]

    presets = get_window_level_presets_from_dataset(ds)

    assert [preset[3] for preset in presets] == ["1", "2", "3"]


def test_get_window_level_presets_fills_missing_explanations_by_index() -> None:
    ds = Dataset()
    ds.WindowCenter = [10, 20, 30]
    ds.WindowWidth = [100, 200, 300]
    ds.WindowCenterWidthExplanation = ["NORMAL", "", "SOFTER"]

    presets = get_window_level_presets_from_dataset(ds)

    assert [preset[3] for preset in presets] == ["NORMAL", "2", "SOFTER"]


def test_get_window_level_presets_uses_single_explanation_name() -> None:
    ds = Dataset()
    ds.WindowCenter = 42
    ds.WindowWidth = 80
    ds.WindowCenterWidthExplanation = "Brain"

    presets = get_window_level_presets_from_dataset(ds)

    assert [preset[3] for preset in presets] == ["Brain"]


def test_get_window_level_presets_reads_functional_group_explanations() -> None:
    voi = Dataset()
    voi.WindowCenter = [10, 20]
    voi.WindowWidth = [100, 200]
    voi.WindowCenterWidthExplanation = ["NORMAL", "SOFTER"]

    shared = Dataset()
    shared.FrameVOILUTSequence = Sequence([voi])

    ds = Dataset()
    ds.SharedFunctionalGroupsSequence = Sequence([shared])

    presets = get_window_level_presets_from_dataset(ds)

    assert [preset[3] for preset in presets] == ["NORMAL", "SOFTER"]


def test_multiframe_wrapper_uses_frame_voi_explanations() -> None:
    voi0 = Dataset()
    voi0.WindowCenter = [10, 20, 30]
    voi0.WindowWidth = [100, 200, 300]
    voi0.WindowCenterWidthExplanation = ["NORMAL", "HARDER", "SOFTER"]

    fg0 = Dataset()
    fg0.FrameVOILUTSequence = Sequence([voi0])

    ds = Dataset()
    ds.PerFrameFunctionalGroupsSequence = Sequence([fg0])
    ds.NumberOfFrames = 1

    frame = create_frame_dataset(ds, 0)
    assert frame is not None

    presets = get_window_level_presets_from_dataset(frame)

    assert [preset[3] for preset in presets] == ["NORMAL", "HARDER", "SOFTER"]

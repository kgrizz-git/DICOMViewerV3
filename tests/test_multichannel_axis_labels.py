"""
Unit tests for ``core.dicom_color.multichannel_axis_labels``.

Covers RGB vs YBR vs generic labels for three-channel data, and Ch0… naming
for other channel counts regardless of PhotometricInterpretation.
"""

from __future__ import annotations

from pydicom.dataset import Dataset

from core.dicom_color import multichannel_axis_labels


def test_rgb_three_channel() -> None:
    ds = Dataset()
    ds.PhotometricInterpretation = "RGB"
    assert multichannel_axis_labels(ds, 3) == ("R", "G", "B")


def test_ybr_full_422() -> None:
    ds = Dataset()
    ds.PhotometricInterpretation = "YBR_FULL_422"
    assert multichannel_axis_labels(ds, 3) == ("Y", "Cb", "Cr")


def test_missing_pi_three_channel() -> None:
    ds = Dataset()
    assert multichannel_axis_labels(ds, 3) == ("Ch0", "Ch1", "Ch2")


def test_none_dataset_three_channel() -> None:
    assert multichannel_axis_labels(None, 3) == ("Ch0", "Ch1", "Ch2")


def test_two_and_four_channels_ignore_rgb_pi() -> None:
    ds = Dataset()
    ds.PhotometricInterpretation = "RGB"
    assert multichannel_axis_labels(ds, 2) == ("Ch0", "Ch1")
    assert multichannel_axis_labels(ds, 4) == ("Ch0", "Ch1", "Ch2", "Ch3")


def test_palette_three_channel() -> None:
    ds = Dataset()
    ds.PhotometricInterpretation = "PALETTE COLOR"
    assert multichannel_axis_labels(ds, 3) == ("Ch0", "Ch1", "Ch2")


def test_zero_channel() -> None:
    assert multichannel_axis_labels(None, 0) == ()

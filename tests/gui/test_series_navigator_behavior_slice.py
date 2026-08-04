"""Focused SeriesNavigator behavior slice without MainWindow."""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest
from pydicom.dataset import Dataset
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent

from core.dicom_processor import DICOMProcessor
from gui.series_navigator import SeriesNavigator


def _ds(**kwargs) -> Dataset:
    ds = Dataset()
    for k, v in kwargs.items():
        setattr(ds, k, v)
    return ds


@pytest.mark.qt
def test_privacy_and_instance_flags(qapp) -> None:
    nav = SeriesNavigator(DICOMProcessor())
    assert nav.get_show_instances_separately() is False
    nav.set_show_instances_separately(True)
    assert nav.get_show_instances_separately() is True
    nav.set_privacy_mode(True)
    assert nav._privacy_mode_enabled is True
    nav.set_show_slice_frame_count_badge(False)
    assert nav._show_slice_frame_count_badge is False
    nav.clear()
    assert nav.thumbnails == {}
    assert nav.thumbnail_cache == {}


@pytest.mark.qt
def test_build_instance_entries_and_can_expand(qapp) -> None:
    from core.dicom_organizer import MultiFrameSeriesInfo

    nav = SeriesNavigator(DICOMProcessor())
    datasets = [
        _ds(SOPInstanceUID="1.2.3.1", InstanceNumber=1),
        _ds(SOPInstanceUID="1.2.3.2", InstanceNumber=2),
    ]
    entries = nav.build_instance_entries(datasets)
    assert len(entries) == 2
    assert all(isinstance(e[0], int) for e in entries)

    assert nav.can_expand_series("st", "se") is False
    nav.set_multiframe_info_map(
        {
            ("st", "se"): MultiFrameSeriesInfo(
                instance_count=3, max_frame_count=4
            )
        }
    )
    assert nav.can_expand_series("st", "se") is True


@pytest.mark.qt
def test_update_series_list_builds_thumbnails(qapp) -> None:
    nav = SeriesNavigator(DICOMProcessor())
    # Avoid real pixel work during list update.
    nav._generate_thumbnail = MagicMock(return_value=None)  # type: ignore[method-assign]
    ds = _ds(
        SeriesDescription="Axial SYNTH",
        Modality="CT",
        SeriesNumber=1,
        SOPInstanceUID="1.2.840.10008.10.20.0.1",
    )
    studies = {"1.2.840.10008.10.20.0.10": {"1.2.840.10008.10.20.0.20": [ds]}}
    nav.update_series_list(studies, "1.2.840.10008.10.20.0.10", "1.2.840.10008.10.20.0.20")
    assert nav._last_studies == studies
    assert len(nav.thumbnails) == 1
    nav.set_current_series("1.2.840.10008.10.20.0.20", "1.2.840.10008.10.20.0.10")
    assert nav.current_series_uid == "1.2.840.10008.10.20.0.20"
    nav.clear()
    assert nav.thumbnails == {}


@pytest.mark.qt
def test_mpr_thumbnail_set_and_clear(qapp) -> None:
    nav = SeriesNavigator(DICOMProcessor())
    nav._generate_thumbnail = MagicMock(return_value=None)  # type: ignore[method-assign]
    ds = _ds(SeriesDescription="Src", Modality="CT", SeriesNumber=1)
    studies = {"st": {"se": [ds]}}
    nav.update_series_list(studies, "st", "se")
    pixels = np.zeros((8, 8), dtype=np.float32)
    nav.set_mpr_thumbnail(0, pixels, "st", "se", window_center=40.0, window_width=400.0, n_slices=3)
    assert 0 in nav._mpr_thumbnail_specs
    assert nav._mpr_thumbnail_specs[0]["n_slices"] == 3
    nav.clear_mpr_thumbnail(0)
    assert 0 not in nav._mpr_thumbnail_specs


@pytest.mark.qt
def test_arrow_key_emits_navigation(qapp) -> None:
    nav = SeriesNavigator(DICOMProcessor())
    deltas: list[int] = []
    nav.series_navigation_requested.connect(deltas.append)
    left = QKeyEvent(
        QKeyEvent.Type.KeyPress, Qt.Key.Key_Left, Qt.KeyboardModifier.NoModifier
    )
    right = QKeyEvent(
        QKeyEvent.Type.KeyPress, Qt.Key.Key_Right, Qt.KeyboardModifier.NoModifier
    )
    nav.keyPressEvent(left)
    nav.keyPressEvent(right)
    assert deltas == [-1, 1]

"""Additional synthetic coverage for SeriesNavigator behavior and guards."""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest
from PIL import Image
from pydicom.dataset import Dataset
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent

from core.dicom_organizer import MultiFrameSeriesInfo
from gui.series_navigator import SeriesNavigator


def _dataset(**values: object) -> Dataset:
    dataset = Dataset()
    for key, value in values.items():
        setattr(dataset, key, value)
    return dataset


def _navigator(qapp) -> SeriesNavigator:
    navigator = SeriesNavigator(MagicMock())
    navigator._generate_thumbnail = MagicMock(return_value=Image.new("L", (8, 6)))  # type: ignore[method-assign]
    return navigator


@pytest.mark.qt
def test_empty_and_multi_study_updates_keep_only_nonempty_sections(qapp) -> None:
    navigator = _navigator(qapp)
    navigator.update_series_list({}, "", "")
    assert navigator.study_labels == []

    first = _dataset(SeriesDescription="First", SeriesNumber=1)
    second = _dataset(SeriesDescription="Second", SeriesNumber=2)
    navigator.update_series_list(
        {"study-1": {"series-1": [first]}, "study-empty": {}, "study-2": {"series-2": [second]}},
        "study-2",
        "series-2",
    )
    assert len(navigator.study_labels) == 2
    assert len(navigator.study_dividers) == 1
    assert set(navigator.thumbnails) == {"study-1:series-1", "study-2:series-2"}


@pytest.mark.qt
def test_deferred_series_and_instance_jobs_fill_caches_and_widgets(qapp) -> None:
    navigator = _navigator(qapp)
    navigator.set_multiframe_info_map(
        {("study", "series"): MultiFrameSeriesInfo(instance_count=2, max_frame_count=3)}
    )
    navigator.set_show_instances_separately(True)
    datasets = [
        _dataset(SOPInstanceUID="1", InstanceNumber=1),
        _dataset(SOPInstanceUID="2", InstanceNumber=2),
    ]
    navigator.update_series_list({"study": {"series": datasets}}, "study", "series")

    while navigator._pending_thumbnail_jobs or navigator._pending_instance_thumbnail_jobs:
        navigator._process_next_thumbnail()
        navigator._process_next_instance_thumbnail()

    assert ("study", "series") in navigator.thumbnail_cache
    assert set(navigator.instance_thumbnail_cache) == {
        ("study", "series", 0),
        ("study", "series", 1),
    }


@pytest.mark.qt
def test_assignments_map_series_and_instance_dots_and_current_position(qapp) -> None:
    navigator = _navigator(qapp)
    info = MultiFrameSeriesInfo(instance_count=2, max_frame_count=2)
    navigator.set_multiframe_info_map({("study", "series"): info})
    navigator.set_show_instances_separately(True)
    datasets = [_dataset(SOPInstanceUID="1"), _dataset(SOPInstanceUID="2")]
    navigator.update_series_list({"study": {"series": datasets}}, "study", "series")

    navigator.set_subwindow_assignments(
        {0: ("study", "series", 0), 1: ("study", "series", 1), 2: (), 3: ("other", "none")}
    )
    assert navigator.thumbnails["study:series"]._dot_slots == [0, 1]
    assert navigator.instance_thumbnails["study:series:0"]._dot_slots == [0]
    assert navigator.instance_thumbnails["study:series:1"]._dot_slots == [1]
    assert navigator._get_instance_thumbnail_key("study", "series", 99) == "study:series:1"
    assert navigator._get_instance_thumbnail_key("missing", "series", 0) is None

    navigator.set_current_position("series", "study", -4)
    assert navigator.current_slice_index == 0
    assert navigator.thumbnails["study:series"].is_current is True


@pytest.mark.qt
def test_thumbnail_window_level_uses_presets_tag_series_and_pixel_fallbacks(qapp, monkeypatch) -> None:
    processor = MagicMock()
    navigator = SeriesNavigator(processor)
    dataset = _dataset()
    processor.get_rescale_parameters.return_value = (2.0, 10.0, None)
    processor.get_series_pixel_value_range.return_value = (0.0, 100.0)
    processor.get_window_level_presets_from_dataset.return_value = [(20.0, 40.0, False, "preset")]
    monkeypatch.setattr(
        "gui.series_navigator.apply_window_level_rescale_conversion",
        lambda wc, ww, **kwargs: (wc + 1, ww + 1),
    )
    assert navigator._resolve_thumbnail_window_level(dataset, [dataset]) == (21.0, 41.0, True)

    processor.get_window_level_presets_from_dataset.return_value = []
    processor.get_window_level_from_dataset.return_value = (30.0, 50.0, False)
    assert navigator._resolve_thumbnail_window_level(dataset, [dataset]) == (31.0, 51.0, True)

    processor.get_window_level_from_dataset.return_value = (None, None, False)
    processor.get_series_pixel_median.return_value = None
    processor.get_series_pixel_value_range.return_value = (4.0, 4.0)
    assert navigator._resolve_thumbnail_window_level(dataset, [dataset]) == (4.0, 1.0, True)

    processor.get_series_pixel_value_range.side_effect = RuntimeError("range unavailable")
    processor.get_pixel_value_range.return_value = (0.0, 4.0)
    processor.get_pixel_array.return_value = np.array([[0, 2], [0, 4]])
    assert navigator._resolve_thumbnail_window_level(dataset, None) == (12.0, 4.0, True)


@pytest.mark.qt
def test_thumbnail_generation_and_regeneration_cover_success_and_errors(qapp, monkeypatch) -> None:
    processor = MagicMock()
    navigator = SeriesNavigator(processor)
    dataset = _dataset()
    processor.get_rescale_parameters.return_value = (None, None, None)
    processor.get_window_level_presets_from_dataset.return_value = []
    processor.get_window_level_from_dataset.return_value = (None, None, False)
    processor.get_pixel_value_range.return_value = (0.0, 8.0)
    processor.get_pixel_array.return_value = np.ones((8, 8))
    processor.dataset_to_image.return_value = Image.new("RGB", (80, 40))

    image = navigator._generate_thumbnail(dataset)
    assert image is not None and image.size == (57, 29)

    processor.dataset_to_image.return_value = None
    assert navigator._generate_thumbnail(dataset) is None
    processor.dataset_to_image.side_effect = RuntimeError("render failed")
    assert navigator._generate_thumbnail(dataset) is None

    monkeypatch.setattr("gui.series_navigator.is_compressed_transfer_syntax", lambda _: True)
    monkeypatch.setattr("gui.series_navigator.transfer_syntax_uid", lambda _: "compressed")

    class _CompressedDataset:
        @property
        def pixel_array(self):
            raise RuntimeError("decode")

    compression_image = navigator._generate_thumbnail(_CompressedDataset())  # type: ignore[arg-type]
    assert compression_image is not None and compression_image.size == (57, 57)

    navigator.thumbnail_cache[("study", "series")] = Image.new("L", (2, 2))
    navigator.regenerate_series_thumbnail("study", "series", dataset, 10, 20, False)
    assert ("study", "series") not in navigator.thumbnail_cache


@pytest.mark.qt
def test_regenerate_updates_existing_widget_and_clear_preserves_mpr(qapp) -> None:
    processor = MagicMock()
    processor.dataset_to_image.return_value = Image.new("L", (80, 40))
    navigator = SeriesNavigator(processor)
    dataset = _dataset()
    navigator.thumbnails["study:series"] = MagicMock()
    navigator.thumbnail_cache[("study", "series")] = Image.new("L", (2, 2))
    navigator.regenerate_series_thumbnail("study", "series", dataset, 1, 2, True)
    assert navigator.thumbnail_cache[("study", "series")].size == (57, 29)
    navigator.clear()
    assert navigator.thumbnails == {}
    assert navigator.thumbnail_cache == {}


@pytest.mark.qt
def test_key_press_ignores_auto_repeat_and_passes_unknown_keys_to_base(qapp) -> None:
    navigator = SeriesNavigator(MagicMock())
    event = QKeyEvent(
        QKeyEvent.Type.KeyPress,
        Qt.Key.Key_Left,
        Qt.KeyboardModifier.NoModifier,
        "",
        True,
        1,
    )
    navigator.keyPressEvent(event)
    assert event.isAccepted()

    unknown = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_A, Qt.KeyboardModifier.NoModifier)
    navigator.keyPressEvent(unknown)
    assert not unknown.isAccepted()

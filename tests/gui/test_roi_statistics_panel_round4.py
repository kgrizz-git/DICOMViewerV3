"""Focused tests for gui.roi_statistics_panel.ROIStatisticsPanel.

Covers: construction, update_statistics (basic, rescale, area branches,
multichannel), clear_statistics, _copy_stats_to_clipboard (empty / no-selection /
selected-rows), _show_context_menu, keyPressEvent.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent

from gui.roi_statistics_panel import (
    _STAT_AREA,
    _STAT_MAX,
    _STAT_MEAN,
    _STAT_MIN,
    _STAT_PIXELS,
    _STAT_STD_DEV,
    _TITLE_ROI_STATISTICS,
    ROIStatisticsPanel,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_stats(**overrides) -> dict:
    base = {
        "mean": 100.0,
        "std": 10.0,
        "min": 50.0,
        "max": 200.0,
        "count": 1000,
    }
    base.update(overrides)
    return base


def _cell_text(table, row, col):
    item = table.item(row, col)
    return item.text() if item else ""


# ---------------------------------------------------------------------------
# Construction / initial state
# ---------------------------------------------------------------------------

@pytest.mark.qt
def test_initial_state(qapp) -> None:
    panel = ROIStatisticsPanel()
    assert panel.title_label.text() == _TITLE_ROI_STATISTICS
    assert panel.current_statistics is None
    table = panel.stats_table
    assert table.columnCount() == 3
    assert table.rowCount() == 6
    labels = [_cell_text(table, i, 0) for i in range(6)]
    assert labels == [_STAT_MEAN, _STAT_STD_DEV, _STAT_MIN, _STAT_MAX, _STAT_PIXELS, _STAT_AREA]
    for i in range(6):
        assert _cell_text(table, i, 1) == ""
        assert _cell_text(table, i, 2) == ""


@pytest.mark.qt
def test_table_is_read_only(qapp) -> None:
    from PySide6.QtWidgets import QTableWidget
    panel = ROIStatisticsPanel()
    assert panel.stats_table.editTriggers() == QTableWidget.EditTrigger.NoEditTriggers


@pytest.mark.qt
def test_selection_mode_extended_rows(qapp) -> None:
    from PySide6.QtWidgets import QAbstractItemView
    panel = ROIStatisticsPanel()
    assert panel.stats_table.selectionBehavior() == QAbstractItemView.SelectionBehavior.SelectRows
    assert panel.stats_table.selectionMode() == QAbstractItemView.SelectionMode.ExtendedSelection


# ---------------------------------------------------------------------------
# update_statistics – basic
# ---------------------------------------------------------------------------

@pytest.mark.qt
def test_update_statistics_basic(qapp) -> None:
    panel = ROIStatisticsPanel()
    stats = _make_stats()
    panel.update_statistics(stats)
    assert panel.current_statistics is stats
    assert panel.title_label.text() == _TITLE_ROI_STATISTICS
    table = panel.stats_table
    assert table.rowCount() == 6
    assert _cell_text(table, 0, 1) == "100.00"
    assert _cell_text(table, 0, 2) == ""
    assert _cell_text(table, 1, 1) == "10.00"
    assert _cell_text(table, 2, 1) == "50.00"
    assert _cell_text(table, 3, 1) == "200.00"
    assert _cell_text(table, 4, 1) == "1000"


@pytest.mark.qt
def test_update_statistics_with_roi_identifier(qapp) -> None:
    panel = ROIStatisticsPanel()
    panel.update_statistics(_make_stats(), roi_identifier="ROI 1 (ellipse)")
    assert panel.title_label.text() == f"{_TITLE_ROI_STATISTICS} - ROI 1 (ellipse)"


@pytest.mark.qt
def test_update_statistics_without_roi_identifier_resets_title(qapp) -> None:
    panel = ROIStatisticsPanel()
    panel.update_statistics(_make_stats(), roi_identifier="ROI 1")
    assert "ROI 1" in panel.title_label.text()
    panel.update_statistics(_make_stats())
    assert panel.title_label.text() == _TITLE_ROI_STATISTICS


# ---------------------------------------------------------------------------
# update_statistics – rescale_type
# ---------------------------------------------------------------------------

@pytest.mark.qt
def test_update_statistics_rescale_type(qapp) -> None:
    panel = ROIStatisticsPanel()
    panel.update_statistics(_make_stats(), rescale_type="HU")
    table = panel.stats_table
    assert _cell_text(table, 0, 2) == "HU"
    assert _cell_text(table, 1, 2) == "HU"
    assert _cell_text(table, 2, 2) == "HU"
    assert _cell_text(table, 3, 2) == "HU"
    assert _cell_text(table, 4, 2) == ""


@pytest.mark.qt
def test_update_statistics_no_rescale_type_empty_unit(qapp) -> None:
    panel = ROIStatisticsPanel()
    panel.update_statistics(_make_stats())
    for i in range(4):
        assert _cell_text(panel.stats_table, i, 2) == ""


@pytest.mark.qt
def test_update_statistics_preserves_column_order_and_units(qapp) -> None:
    panel = ROIStatisticsPanel()
    panel.update_statistics(_make_stats(), rescale_type="HU")
    table = panel.stats_table
    for row in range(table.rowCount()):
        label = _cell_text(table, row, 0)
        value = _cell_text(table, row, 1)
        unit = _cell_text(table, row, 2)
        assert label and value
        if label in (_STAT_MEAN, _STAT_STD_DEV, _STAT_MIN, _STAT_MAX):
            assert unit == "HU"
        elif label == _STAT_PIXELS:
            assert unit == ""


# ---------------------------------------------------------------------------
# update_statistics – area branches
# ---------------------------------------------------------------------------

@pytest.mark.qt
def test_area_mm2_small_shows_mm2(qapp) -> None:
    panel = ROIStatisticsPanel()
    panel.update_statistics(_make_stats(area_mm2=50.0))
    row = panel.stats_table.rowCount() - 1
    assert _cell_text(panel.stats_table, row, 0) == _STAT_AREA
    assert _cell_text(panel.stats_table, row, 1) == "50.00"
    assert _cell_text(panel.stats_table, row, 2) == "mm²"


@pytest.mark.qt
def test_area_mm2_large_shows_cm2(qapp) -> None:
    panel = ROIStatisticsPanel()
    panel.update_statistics(_make_stats(area_mm2=250.0))
    row = panel.stats_table.rowCount() - 1
    assert _cell_text(panel.stats_table, row, 0) == _STAT_AREA
    assert _cell_text(panel.stats_table, row, 1) == "2.50"
    assert _cell_text(panel.stats_table, row, 2) == "cm²"


@pytest.mark.qt
def test_area_mm2_boundary_exactly_100_shows_cm2(qapp) -> None:
    panel = ROIStatisticsPanel()
    panel.update_statistics(_make_stats(area_mm2=100.0))
    row = panel.stats_table.rowCount() - 1
    assert _cell_text(panel.stats_table, row, 1) == "1.00"
    assert _cell_text(panel.stats_table, row, 2) == "cm²"


@pytest.mark.qt
def test_area_mm2_boundary_99_shows_mm2(qapp) -> None:
    panel = ROIStatisticsPanel()
    panel.update_statistics(_make_stats(area_mm2=99.9))
    row = panel.stats_table.rowCount() - 1
    assert _cell_text(panel.stats_table, row, 1) == "99.90"
    assert _cell_text(panel.stats_table, row, 2) == "mm²"


@pytest.mark.qt
def test_area_fallback_to_pixels_when_no_area_mm2(qapp) -> None:
    panel = ROIStatisticsPanel()
    panel.update_statistics(_make_stats(area_pixels=350.5))
    row = panel.stats_table.rowCount() - 1
    assert _cell_text(panel.stats_table, row, 0) == _STAT_AREA
    assert _cell_text(panel.stats_table, row, 1) == "350.5"
    assert _cell_text(panel.stats_table, row, 2) == "pixels"


@pytest.mark.qt
def test_area_zero_area_pixels(qapp) -> None:
    panel = ROIStatisticsPanel()
    panel.update_statistics(_make_stats(area_pixels=0.0))
    row = panel.stats_table.rowCount() - 1
    assert _cell_text(panel.stats_table, row, 1) == "0.0"
    assert _cell_text(panel.stats_table, row, 2) == "pixels"


@pytest.mark.qt
def test_area_mm2_zero_shows_mm2(qapp) -> None:
    """0.0 < 100.0 so it should show mm²."""
    panel = ROIStatisticsPanel()
    panel.update_statistics(_make_stats(area_mm2=0.0))
    row = panel.stats_table.rowCount() - 1
    assert _cell_text(panel.stats_table, row, 1) == "0.00"
    assert _cell_text(panel.stats_table, row, 2) == "mm²"


# ---------------------------------------------------------------------------
# update_statistics – multichannel
# ---------------------------------------------------------------------------

@pytest.mark.qt
def test_multichannel_with_labels(qapp) -> None:
    stats = _make_stats(
        multichannel_count=2,
        channel_labels=["Red", "Green"],
        mean_ch0=110.0,
        std_ch0=5.0,
        min_ch0=80.0,
        max_ch0=140.0,
        mean_ch1=120.0,
        std_ch1=6.0,
        min_ch1=90.0,
        max_ch1=150.0,
    )
    panel = ROIStatisticsPanel()
    panel.update_statistics(stats)
    table = panel.stats_table
    assert table.rowCount() == 14
    assert _cell_text(table, 6, 0) == "Mean (Red)"
    assert _cell_text(table, 6, 1) == "110.00"
    assert _cell_text(table, 7, 0) == "Std (Red)"
    assert _cell_text(table, 8, 0) == "Min (Red)"
    assert _cell_text(table, 9, 0) == "Max (Red)"
    assert _cell_text(table, 10, 0) == "Mean (Green)"
    assert _cell_text(table, 11, 0) == "Std (Green)"
    assert _cell_text(table, 12, 0) == "Min (Green)"
    assert _cell_text(table, 13, 0) == "Max (Green)"


@pytest.mark.qt
def test_multichannel_without_labels_fallback(qapp) -> None:
    stats = _make_stats(
        multichannel_count=3,
        mean_ch0=10.0,
        mean_ch1=20.0,
        mean_ch2=30.0,
    )
    panel = ROIStatisticsPanel()
    panel.update_statistics(stats)
    table = panel.stats_table
    assert table.rowCount() == 18
    assert _cell_text(table, 6, 0) == "Mean (Ch0)"
    assert _cell_text(table, 10, 0) == "Mean (Ch1)"
    assert _cell_text(table, 14, 0) == "Mean (Ch2)"


@pytest.mark.qt
def test_multichannel_with_wrong_length_labels_fallback(qapp) -> None:
    stats = _make_stats(
        multichannel_count=2,
        channel_labels=["OnlyOne"],
        mean_ch0=10.0,
        mean_ch1=20.0,
    )
    panel = ROIStatisticsPanel()
    panel.update_statistics(stats)
    assert _cell_text(panel.stats_table, 6, 0) == "Mean (Ch0)"
    assert _cell_text(panel.stats_table, 10, 0) == "Mean (Ch1)"


@pytest.mark.qt
def test_multichannel_with_tuple_labels(qapp) -> None:
    stats = _make_stats(
        multichannel_count=2,
        channel_labels=("A", "B"),
        mean_ch0=1.0,
        mean_ch1=2.0,
    )
    panel = ROIStatisticsPanel()
    panel.update_statistics(stats)
    assert _cell_text(panel.stats_table, 6, 0) == "Mean (A)"
    assert _cell_text(panel.stats_table, 10, 0) == "Mean (B)"


@pytest.mark.qt
def test_multichannel_partial_keys(qapp) -> None:
    """Channel exists but some per-channel keys are missing – defaults to 0."""
    stats = _make_stats(
        multichannel_count=2,
        channel_labels=["X", "Y"],
        mean_ch0=10.0,
        mean_ch1=20.0,
    )
    panel = ROIStatisticsPanel()
    panel.update_statistics(stats)
    table = panel.stats_table
    assert table.rowCount() == 14
    assert _cell_text(table, 7, 1) == "0.00"
    assert _cell_text(table, 11, 1) == "0.00"


@pytest.mark.qt
def test_no_multichannel_when_count_is_one(qapp) -> None:
    stats = _make_stats(multichannel_count=1, mean_ch0=10.0)
    panel = ROIStatisticsPanel()
    panel.update_statistics(stats)
    assert panel.stats_table.rowCount() == 6


@pytest.mark.qt
def test_no_multichannel_when_count_is_zero(qapp) -> None:
    stats = _make_stats(multichannel_count=0)
    panel = ROIStatisticsPanel()
    panel.update_statistics(stats)
    assert panel.stats_table.rowCount() == 6


@pytest.mark.qt
def test_no_multichannel_when_count_missing(qapp) -> None:
    stats = _make_stats()
    panel = ROIStatisticsPanel()
    panel.update_statistics(stats)
    assert panel.stats_table.rowCount() == 6


# ---------------------------------------------------------------------------
# clear_statistics
# ---------------------------------------------------------------------------

@pytest.mark.qt
def test_clear_statistics_resets_to_defaults(qapp) -> None:
    panel = ROIStatisticsPanel()
    panel.update_statistics(
        _make_stats(area_mm2=150.0),
        roi_identifier="ROI 1",
        rescale_type="HU",
    )
    assert panel.stats_table.rowCount() != 6 or panel.title_label.text() != _TITLE_ROI_STATISTICS
    panel.clear_statistics()
    assert panel.current_statistics is None
    assert panel.title_label.text() == _TITLE_ROI_STATISTICS
    table = panel.stats_table
    assert table.rowCount() == 6
    labels = [_cell_text(table, i, 0) for i in range(6)]
    assert labels == [_STAT_MEAN, _STAT_STD_DEV, _STAT_MIN, _STAT_MAX, _STAT_PIXELS, _STAT_AREA]
    for i in range(6):
        assert _cell_text(table, i, 1) == ""
        assert _cell_text(table, i, 2) == ""


@pytest.mark.qt
def test_clear_statistics_after_multichannel(qapp) -> None:
    panel = ROIStatisticsPanel()
    panel.update_statistics(
        _make_stats(
            multichannel_count=2,
            channel_labels=["A", "B"],
            mean_ch0=1.0,
            mean_ch1=2.0,
        )
    )
    assert panel.stats_table.rowCount() == 14
    panel.clear_statistics()
    assert panel.stats_table.rowCount() == 6
    assert panel.current_statistics is None


# ---------------------------------------------------------------------------
# _copy_stats_to_clipboard
# ---------------------------------------------------------------------------

@pytest.mark.qt
def test_copy_empty_panel_noop(qapp) -> None:
    panel = ROIStatisticsPanel()
    mock_clip = MagicMock()
    with patch("gui.roi_statistics_panel.QApplication") as mock_qa:
        mock_qa.clipboard.return_value = mock_clip
        panel._copy_stats_to_clipboard()
        mock_clip.setText.assert_not_called()


@pytest.mark.qt
def test_copy_no_selection_copies_all_with_title(qapp) -> None:
    panel = ROIStatisticsPanel()
    panel.update_statistics(_make_stats(), roi_identifier="ROI 7")
    mock_clip = MagicMock()
    with patch("gui.roi_statistics_panel.QApplication") as mock_qa:
        mock_qa.clipboard.return_value = mock_clip
        panel._copy_stats_to_clipboard()
        written = mock_clip.setText.call_args[0][0]
        lines = written.split("\n")
        assert lines[0] == f"{_TITLE_ROI_STATISTICS} - ROI 7"
        assert len(lines) == 7
        assert lines[1].startswith(_STAT_MEAN)
        assert "\t" in lines[1]


@pytest.mark.qt
def test_copy_with_selection_copies_only_selected_rows(qapp) -> None:
    panel = ROIStatisticsPanel()
    panel.update_statistics(_make_stats())
    table = panel.stats_table
    from PySide6.QtCore import QItemSelectionModel
    sel = table.selectionModel()
    sel.select(
        table.model().index(0, 0),
        QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows,
    )
    sel.select(
        table.model().index(2, 0),
        QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows,
    )
    mock_clip = MagicMock()
    with patch("gui.roi_statistics_panel.QApplication") as mock_qa:
        mock_qa.clipboard.return_value = mock_clip
        panel._copy_stats_to_clipboard()
        written = mock_clip.setText.call_args[0][0]
        lines = written.split("\n")
        assert len(lines) == 2
        assert lines[0].startswith(_STAT_MEAN)
        assert lines[1].startswith(_STAT_MIN)


@pytest.mark.qt
def test_copy_no_selection_empty_values_still_copies(qapp) -> None:
    """current_statistics is set but value cells are empty – copy still works."""
    panel = ROIStatisticsPanel()
    panel.current_statistics = {"dummy": 1}
    mock_clip = MagicMock()
    with patch("gui.roi_statistics_panel.QApplication") as mock_qa:
        mock_qa.clipboard.return_value = mock_clip
        panel._copy_stats_to_clipboard()
        written = mock_clip.setText.call_args[0][0]
        lines = written.split("\n")
        assert lines[0] == _TITLE_ROI_STATISTICS
        assert len(lines) == 7


# ---------------------------------------------------------------------------
# _show_context_menu
# ---------------------------------------------------------------------------

@pytest.mark.qt
def test_show_context_menu_copy_disabled_when_no_stats(qapp) -> None:
    panel = ROIStatisticsPanel()
    with patch("gui.roi_statistics_panel.QMenu") as MockMenu:
        mock_menu = MagicMock()
        MockMenu.return_value = mock_menu
        mock_action = MagicMock()
        mock_menu.addAction.return_value = mock_action
        pos = panel.stats_table.viewport().mapToGlobal(panel.stats_table.rect().center())
        panel._show_context_menu(pos)
        mock_action.setEnabled.assert_called_with(False)


@pytest.mark.qt
def test_show_context_menu_copy_enabled_when_stats_loaded(qapp) -> None:
    panel = ROIStatisticsPanel()
    panel.update_statistics(_make_stats())
    with patch("gui.roi_statistics_panel.QMenu") as MockMenu:
        mock_menu = MagicMock()
        MockMenu.return_value = mock_menu
        mock_action = MagicMock()
        mock_menu.addAction.return_value = mock_action
        pos = panel.stats_table.viewport().mapToGlobal(panel.stats_table.rect().center())
        panel._show_context_menu(pos)
        mock_action.setEnabled.assert_called_with(True)


@pytest.mark.qt
def test_show_context_menu_connects_copy_action(qapp) -> None:
    panel = ROIStatisticsPanel()
    panel.update_statistics(_make_stats())
    with patch("gui.roi_statistics_panel.QMenu") as MockMenu:
        mock_menu = MagicMock()
        MockMenu.return_value = mock_menu
        mock_action = MagicMock()
        mock_menu.addAction.return_value = mock_action
        pos = panel.stats_table.viewport().mapToGlobal(panel.stats_table.rect().center())
        panel._show_context_menu(pos)
        mock_action.triggered.connect.assert_called_once()
        mock_menu.exec.assert_called_once()


# ---------------------------------------------------------------------------
# keyPressEvent
# ---------------------------------------------------------------------------

@pytest.mark.qt
def test_keyPressEvent_ctrl_c_triggers_copy(qapp) -> None:
    panel = ROIStatisticsPanel()
    panel.update_statistics(_make_stats())
    with patch.object(panel, "_copy_stats_to_clipboard") as mock_copy:
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
        panel.keyPressEvent(event)
        mock_copy.assert_called_once()
        assert event.isAccepted()


@pytest.mark.qt
def test_keyPressEvent_cmd_c_does_not_trigger_copy_on_offscreen(qapp) -> None:
    """On macOS offscreen QPA, StandardKey.Copy resolves to Ctrl+C, not Meta+C."""
    panel = ROIStatisticsPanel()
    panel.update_statistics(_make_stats())
    with patch.object(panel, "_copy_stats_to_clipboard") as mock_copy:
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_C, Qt.KeyboardModifier.MetaModifier)
        panel.keyPressEvent(event)
        mock_copy.assert_not_called()


@pytest.mark.qt
def test_keyPressEvent_other_key_does_not_copy(qapp) -> None:
    panel = ROIStatisticsPanel()
    with patch.object(panel, "_copy_stats_to_clipboard") as mock_copy:
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_A, Qt.KeyboardModifier.NoModifier)
        panel.keyPressEvent(event)
        mock_copy.assert_not_called()
        assert not event.isAccepted()


@pytest.mark.qt
def test_keyPressEvent_ctrl_v_does_not_copy(qapp) -> None:
    panel = ROIStatisticsPanel()
    with patch.object(panel, "_copy_stats_to_clipboard") as mock_copy:
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
        panel.keyPressEvent(event)
        mock_copy.assert_not_called()


# ---------------------------------------------------------------------------
# update_statistics – defaults for missing keys
# ---------------------------------------------------------------------------

@pytest.mark.qt
def test_update_statistics_empty_dict_uses_defaults(qapp) -> None:
    panel = ROIStatisticsPanel()
    panel.update_statistics({})
    table = panel.stats_table
    assert _cell_text(table, 0, 1) == "0.00"
    assert _cell_text(table, 1, 1) == "0.00"
    assert _cell_text(table, 2, 1) == "0.00"
    assert _cell_text(table, 3, 1) == "0.00"
    assert _cell_text(table, 4, 1) == "0"

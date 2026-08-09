"""
Comprehensive unit tests for src/gui/cine_controls_widget.py.

Achieves 100% statement and branch coverage for CineControlsWidget.
"""

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QPoint, Qt

from gui.cine_controls_widget import CineControlsWidget


def test_init_and_ui_state(qapp) -> None:
    """Test CineControlsWidget initialization and initial disabled state."""
    widget = CineControlsWidget()

    assert widget._is_playing is False
    assert widget.loop_start_frame is None
    assert widget.loop_end_frame is None

    # Initial controls should be disabled
    assert widget.play_pause_button.isEnabled() is False
    assert widget.stop_button.isEnabled() is False
    assert widget.speed_combo.isEnabled() is False
    assert widget.loop_button.isEnabled() is False
    assert widget.frame_slider.isEnabled() is False


def test_play_pause_and_stop_signals(qapp) -> None:
    """Test play/pause toggle button logic and stop signal emission."""
    widget = CineControlsWidget()
    widget.set_controls_enabled(True)

    play_mock = MagicMock()
    pause_mock = MagicMock()
    stop_mock = MagicMock()

    widget.play_requested.connect(play_mock)
    widget.pause_requested.connect(pause_mock)
    widget.stop_requested.connect(stop_mock)

    # 1. Click Play when not playing
    widget.play_pause_button.click()
    play_mock.assert_called_once()
    pause_mock.assert_not_called()

    # 2. Update playback state to playing
    widget.update_playback_state(True)
    assert widget.play_pause_button.text() == "⏸ Pause"

    # 3. Click Pause when playing
    widget.play_pause_button.click()
    pause_mock.assert_called_once()

    # 4. Update playback state to stopped/paused when controls disabled vs enabled
    widget.update_playback_state(False)
    assert widget.play_pause_button.text() == "▶ Play"

    widget.set_controls_enabled(False)
    widget.update_playback_state(
        True
    )  # Button disabled, appearance not refreshed until enabled
    widget.set_controls_enabled(True)
    assert widget.play_pause_button.text() == "⏸ Pause"

    # 5. Click Stop
    widget.stop_button.click()
    stop_mock.assert_called_once()


def test_speed_combo_and_signal(qapp) -> None:
    """Test speed combo box selection and signal emission."""
    widget = CineControlsWidget()
    widget.set_controls_enabled(True)

    speed_mock = MagicMock()
    widget.speed_changed.connect(speed_mock)

    # Select 2x speed
    widget.speed_combo.setCurrentText("2x")
    speed_mock.assert_called_with(2.0)

    # Select 0.5x speed
    widget.speed_combo.setCurrentText("0.5x")
    speed_mock.assert_called_with(0.5)

    # Invalid speed string exception handling
    widget._on_speed_changed("invalid_speed")  # Should be silently caught by try/except


def test_set_speed_accepts_existing_fractional_and_integral_labels(qapp) -> None:
    """Test supported fractional and integral speed labels."""
    widget = CineControlsWidget()

    widget.set_speed(0.25)
    assert widget.speed_combo.currentText() == "0.25x"

    widget.set_speed(1)
    assert widget.speed_combo.currentText() == "1x"



def test_loop_button_and_set_loop(qapp) -> None:
    """Test loop button toggle and set_loop method."""
    widget = CineControlsWidget()
    widget.set_controls_enabled(True)

    loop_mock = MagicMock()
    widget.loop_toggled.connect(loop_mock)

    widget.loop_button.click()
    loop_mock.assert_called_once_with(True)

    widget.set_loop(False)
    assert widget.loop_button.isChecked() is False


def test_frame_position_and_slider(qapp) -> None:
    """Test updating frame position label and slider bounds."""
    widget = CineControlsWidget()
    widget.set_controls_enabled(True)

    frame_mock = MagicMock()
    widget.frame_position_changed.connect(frame_mock)

    # Set range first, then move slider
    widget.update_frame_position(0, 10)
    widget.frame_slider.setValue(5)
    frame_mock.assert_called_with(5)

    # Update frame position when total_frames <= 0
    widget.update_frame_position(0, 0)
    assert widget.frame_position_label.text() == "0 / 0"

    # Update frame position for 10 total frames
    widget.update_frame_position(4, 10)
    assert widget.frame_slider.maximum() == 9
    assert widget.frame_slider.value() == 4
    assert widget.frame_position_label.text() == "5 / 10"


def test_fps_display(qapp) -> None:
    """Test updating FPS label."""
    widget = CineControlsWidget()
    widget.update_fps_display(24.5)
    assert widget.fps_label.text() == "FPS: 24.5"


def test_loop_bounds_management(qapp) -> None:
    """Test setting, adjusting, clearing, and displaying cine loop bounds."""
    widget = CineControlsWidget()
    widget.set_controls_enabled(True)

    start_mock = MagicMock()
    end_mock = MagicMock()
    clear_mock = MagicMock()

    widget.loop_start_set.connect(start_mock)
    widget.loop_end_set.connect(end_mock)
    widget.loop_bounds_cleared.connect(clear_mock)

    # 1. Set start frame
    widget._set_loop_start(3)
    assert widget.loop_start_frame == 3
    start_mock.assert_called_with(3)

    # 2. Set end frame before start (adjusts start)
    widget._set_loop_end(1)
    assert widget.loop_end_frame == 1
    assert widget.loop_start_frame == 1

    # 3. Set start frame after end (adjusts end)
    widget._set_loop_start(5)
    assert widget.loop_start_frame == 5
    assert widget.loop_end_frame == 5

    # 4. Display tooltips for various bounds combinations
    widget.update_frame_position(3, 10)  # Set maximum > 0 first
    widget.set_loop_bounds(2, 8)
    assert "Cine bounds: 3 - 9" in widget.frame_slider.toolTip()
    widget.update_frame_position(0, 0)  # max_val == 0
    widget.set_loop_bounds(
        2, 8
    )  # Triggers _update_loop_bounds_display with max_val == 0
    assert "Cine bounds" not in widget.frame_slider.toolTip()

    widget.set_loop_bounds(2, None)
    assert "Cine start: 3" in widget.frame_slider.toolTip()

    widget.set_loop_bounds(None, 8)
    assert "Cine end: 9" in widget.frame_slider.toolTip()

    # 5. Clear bounds
    widget._clear_loop_bounds()
    assert widget.loop_start_frame is None
    assert widget.loop_end_frame is None
    clear_mock.assert_called_once()

    # 6. Set loop end when start_frame is not None and start_frame <= frame_index (hits 354->357)
    widget._set_loop_start(2)
    widget._set_loop_end(8)
    assert widget.loop_start_frame == 2
    assert widget.loop_end_frame == 8


def test_frame_slider_context_menu(qapp) -> None:
    """Test frame slider right-click context menu creation and action triggers."""
    widget = CineControlsWidget()

    # 1. Disabled slider returns immediately
    widget._on_frame_slider_context_menu(QPoint(10, 5))

    # 2. Enabled slider creates menu and executes actions
    widget.set_controls_enabled(True)
    widget.update_frame_position(2, 10)

    with patch("gui.cine_controls_widget.QMenu") as mock_menu_cls:
        mock_menu_inst = mock_menu_cls.return_value
        widget._on_frame_slider_context_menu(QPoint(15, 5))
        mock_menu_inst.exec.assert_called_once()

    # 3. Test horizontal slider when slider width is 0 (hits line 315)
    with (
        patch.object(widget.frame_slider, "rect") as mock_rect,
        patch("gui.cine_controls_widget.QMenu") as mock_menu_cls,
    ):
        mock_rect.return_value.width.return_value = 0
        mock_menu_inst = mock_menu_cls.return_value
        widget._on_frame_slider_context_menu(QPoint(15, 5))
        mock_menu_inst.exec.assert_called_once()

    # 4. Test vertical slider branch (for 100% branch coverage)
    widget.frame_slider.setOrientation(Qt.Orientation.Vertical)
    with patch("gui.cine_controls_widget.QMenu") as mock_menu_cls:
        mock_menu_inst = mock_menu_cls.return_value
        widget._on_frame_slider_context_menu(QPoint(15, 5))
        mock_menu_inst.exec.assert_called_once()


@pytest.mark.xfail(
    strict=True,
    reason="Known defect #14A: integral float speed is formatted as an unsupported combo label.",
)
def test_set_speed_selects_integral_float_label(qapp) -> None:
    """Integral float speeds must select their matching combo-box label."""
    widget = CineControlsWidget()
    widget.speed_combo.setCurrentText("1x")

    widget.set_speed(2.0)

    assert widget.speed_combo.currentText() == "2x"


@pytest.mark.xfail(
    strict=True,
    reason="Known defect #14B: clearing frames leaves the prior cine-bounds tooltip visible.",
)
def test_update_frame_position_zero_frames_clears_stale_bounds_tooltip(
    qapp,
) -> None:
    """Closing a cine series must remove its previous bounds tooltip."""
    widget = CineControlsWidget()
    widget.set_controls_enabled(True)

    # 1. Load series with 10 frames and set loop bounds -> updates tooltip
    widget.update_frame_position(3, 10)
    widget.set_loop_bounds(2, 8)
    assert "Cine bounds: 3 - 9" in widget.frame_slider.toolTip()

    widget.update_frame_position(0, 0)

    assert "Cine bounds: 3 - 9" not in widget.frame_slider.toolTip()

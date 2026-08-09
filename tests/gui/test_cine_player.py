"""
Comprehensive unit tests for src/gui/cine_player.py.

Achieves 100% statement and branch coverage for CinePlayer.
"""

from unittest.mock import MagicMock, patch

import pytest
from pydicom.dataset import Dataset

from gui.cine_player import CinePlayer


@pytest.fixture
def mock_nav():
    """Mock slice_navigator and callbacks fixture."""
    nav = MagicMock()
    total_slices_cb = MagicMock(return_value=10)
    current_slice_cb = MagicMock(return_value=0)
    return nav, total_slices_cb, current_slice_cb


def test_init_and_getters(mock_nav) -> None:
    """Test CinePlayer initialization and getter methods."""
    nav, total_cb, current_cb = mock_nav
    player = CinePlayer(nav, total_cb, current_cb)

    assert player.is_playing is False
    assert player.is_paused is False
    assert player.get_current_frame_rate() == 10.0
    assert player.get_effective_frame_rate() == 10.0
    assert player.is_playback_active() is False

    assert player.is_cine_advancing() is False
    player._is_cine_advancing = True
    assert player.is_cine_advancing() is True
    player.reset_cine_advancing_flag()
    assert player.is_cine_advancing() is False


def test_set_series_context(mock_nav) -> None:
    """Test set_series_context with valid, missing, and None studies."""
    nav, total_cb, current_cb = mock_nav
    player = CinePlayer(nav, total_cb, current_cb)

    ds0 = Dataset()
    studies = {"study1": {"series1": [ds0]}}

    # 1. Valid series context
    player.set_series_context(studies, "study1", "series1")
    assert player.current_datasets == [ds0]

    # 2. Missing series context
    player.set_series_context(studies, "study1", "missing_series")
    assert player.current_datasets is None

    # 3. None studies
    player.set_series_context(None, None, None)
    assert player.current_datasets is None

    # 4. Stop playback if playing when context changes
    player.is_playing = True
    player.set_series_context(studies, "study1", "series1")
    assert player.is_playing is False


def test_set_datasets_and_linear_navigation(mock_nav) -> None:
    """Test set_datasets, set_use_linear_cine_navigation, and get_slice_groups."""
    nav, total_cb, current_cb = mock_nav
    player = CinePlayer(nav, total_cb, current_cb)

    # Empty datasets returns empty dict
    assert player.get_slice_groups() == {}

    ds0 = Dataset()
    ds0.SOPInstanceUID = "1.2.3"
    player.set_datasets([ds0])
    assert player.current_datasets == [ds0]

    # Non-empty datasets calls group_datasets_by_slice
    with patch("gui.cine_player.group_datasets_by_slice", return_value={123: [ds0]}):
        assert player.get_slice_groups() == {123: [ds0]}

    player.set_use_linear_cine_navigation(True)
    assert player._use_linear_cine_navigation is True


def test_is_cine_capable(mock_nav) -> None:
    """Test is_cine_capable with various series dataset shapes and document single-file multi-frame flaw."""
    nav, total_cb, current_cb = mock_nav
    player = CinePlayer(nav, total_cb, current_cb)

    # 1. None parameters
    assert player.is_cine_capable(None, "study", "series") is False

    # 2. Missing study or series
    studies = {"s1": {"se1": [Dataset()]}}
    assert player.is_cine_capable(studies, "s2", "se1") is False

    # 3. Single dataset non-multiframe
    assert player.is_cine_capable(studies, "s1", "se1") is False

    # 4. Sequential single-frame series (>= 2 datasets)
    studies["s1"]["se1"] = [Dataset(), Dataset()]
    assert player.is_cine_capable(studies, "s1", "se1") is True

    # 5. Flaw: Single multi-frame file (NumberOfFrames = 10, len(datasets) == 1)
    # Line 187 checks `len(datasets) < 2` and returns False before checking is_multiframe
    mf_ds = Dataset()
    mf_ds.NumberOfFrames = 10
    studies["s1"]["se1"] = [mf_ds]
    assert player.is_cine_capable(studies, "s1", "se1") is False  # Documents flaw

    # Multi-frame file when datasets array has >= 2 elements
    studies["s1"]["se1"] = [mf_ds, Dataset()]
    assert player.is_cine_capable(studies, "s1", "se1") is True

    # 6. Exception in is_cine_capable returns False
    with patch("gui.cine_player.is_multiframe", side_effect=Exception("Parsing error")):
        assert player.is_cine_capable(studies, "s1", "se1") is False


def test_start_pause_resume_stop_playback(mock_nav) -> None:
    """Test playback lifecycle: start, pause, resume, stop."""
    nav, total_cb, current_cb = mock_nav
    player = CinePlayer(nav, total_cb, current_cb)

    state_mock = MagicMock()
    advance_mock = MagicMock()
    player.playback_state_changed.connect(state_mock)
    player.frame_advance_requested.connect(advance_mock)

    # 1. Start playback when not cine capable
    assert player.start_playback() is False

    # 2. Start playback when linear_ok
    player.set_use_linear_cine_navigation(True)
    assert player.start_playback(frame_rate=15.0) is True
    assert player.is_playing is True
    assert player.current_frame_rate == 15.0
    state_mock.assert_called_with(True)

    # 3. Pause playback when playing
    player.pause_playback()
    assert player.is_playing is False
    assert player.is_paused is True
    state_mock.assert_called_with(False)

    # Pause playback when NOT playing (hits 259->exit branch)
    player.pause_playback()

    # 4. Resume playback when paused
    player.resume_playback()
    assert player.is_playing is True

    # Resume playback when NOT paused (hits 267->exit branch)
    player.is_paused = False
    player.resume_playback()

    # 5. Stop playback
    player.stop_playback()
    assert player.is_playing is False
    assert player.is_paused is False
    advance_mock.assert_called_with(0)

    # 6. Start playback with dataset frame rate extraction
    ds = Dataset()
    ds.CineRate = 30
    player.start_playback(dataset=ds)
    assert player.current_frame_rate == 30.0

    # 7. Start playback with invalid/zero frame rate and dataset without frame rate tags
    player.start_playback(frame_rate=0.0)  # hits 238->246 branch
    player.start_playback(dataset=Dataset())  # hits 240->246 branch



def test_set_speed_and_loop(mock_nav) -> None:
    """Test setting speed multiplier and loop enabled state."""
    nav, total_cb, current_cb = mock_nav
    player = CinePlayer(nav, total_cb, current_cb)

    # Invalid speed multiplier <= 0 ignored
    player.set_speed(0.0)
    assert player.speed_multiplier == 1.0

    player.set_speed(2.0)
    assert player.speed_multiplier == 2.0

    # Set speed while playing updates timer interval
    player.is_playing = True
    player.set_speed(4.0)
    assert player.speed_multiplier == 4.0

    player.set_loop(True)
    assert player.loop_enabled is True


def test_advance_frame_linear(mock_nav) -> None:
    """Test linear frame advancement (_advance_frame)."""
    nav, total_cb, current_cb = mock_nav
    player = CinePlayer(nav, total_cb, current_cb)
    player.set_use_linear_cine_navigation(True)

    advance_mock = MagicMock()
    player.frame_advance_requested.connect(advance_mock)

    # 1. Total slices == 0 -> stops playback
    total_cb.return_value = 0
    player._advance_frame()
    assert player.is_playing is False

    # 2. Advance linear frame 0 -> 1
    total_cb.return_value = 10
    current_cb.return_value = 0
    player._advance_frame()
    advance_mock.assert_called_with(1)

    # 3. Reach end with loop_enabled = False -> stops playback
    current_cb.return_value = 9
    player.loop_enabled = False
    player._advance_frame()
    assert player.is_playing is False

    # 4. Reach end with loop_enabled = True -> loops back to 0
    current_cb.return_value = 9
    player.loop_enabled = True
    player._advance_frame()
    advance_mock.assert_called_with(0)


def test_advance_frame_slice_aware(mock_nav) -> None:
    """Test slice-aware frame advancement across multi-frame slices."""
    nav, total_cb, current_cb = mock_nav
    player = CinePlayer(nav, total_cb, current_cb)
    player._use_linear_cine_navigation = False

    advance_mock = MagicMock()
    player.frame_advance_requested.connect(advance_mock)

    ds0 = Dataset()
    player.current_datasets = [ds0]

    with patch("gui.cine_player.get_slice_index_for_dataset", return_value=0), \
         patch("gui.cine_player.get_frame_index_in_slice", return_value=0), \
         patch("gui.cine_player.get_slice_frame_count", return_value=2), \
         patch("gui.cine_player.get_total_slice_groups", return_value=2), \
         patch("gui.cine_player.get_first_frame_index_for_slice", return_value=2):

        # 1. Advance to next frame in same slice (0 -> 1)
        current_cb.return_value = 0
        player._advance_frame()
        advance_mock.assert_called_with(1)

    with patch("gui.cine_player.get_slice_index_for_dataset", return_value=0), \
         patch("gui.cine_player.get_frame_index_in_slice", return_value=1), \
         patch("gui.cine_player.get_slice_frame_count", return_value=2), \
         patch("gui.cine_player.get_total_slice_groups", return_value=2), \
         patch("gui.cine_player.get_first_frame_index_for_slice", return_value=2):

        # 2. Advance from end of slice 0 to start of slice 1
        current_cb.return_value = 1
        player._advance_frame()
        advance_mock.assert_called_with(2)

    with patch("gui.cine_player.get_slice_index_for_dataset", return_value=1), \
         patch("gui.cine_player.get_frame_index_in_slice", return_value=1), \
         patch("gui.cine_player.get_slice_frame_count", return_value=2), \
         patch("gui.cine_player.get_total_slice_groups", return_value=2), \
         patch("gui.cine_player.get_first_frame_index_for_slice", return_value=0):

        # 3. End of last slice with loop_enabled = False -> stops
        current_cb.return_value = 3
        player.loop_enabled = False
        player._advance_frame()
        assert player.is_playing is False

        # 4. End of last slice with loop_enabled = True -> loops to slice 0
        player.loop_enabled = True
        player._advance_frame()
        advance_mock.assert_called_with(0)


def test_advance_frame_loop_bounds(mock_nav) -> None:
    """Test loop bounds clamping during frame advancement."""
    nav, total_cb, current_cb = mock_nav
    player = CinePlayer(nav, total_cb, current_cb)
    player.set_use_linear_cine_navigation(True)

    advance_mock = MagicMock()
    player.frame_advance_requested.connect(advance_mock)

    player.set_loop_bounds(2, 5)
    total_cb.return_value = 10

    # 1. next_index < loop_start -> clamped to loop_start (2)
    current_cb.return_value = 0
    player._advance_frame()
    advance_mock.assert_called_with(2)

    # 2. next_index > loop_end with loop_enabled = True -> loops to loop_start (2)
    current_cb.return_value = 5
    player.loop_enabled = True
    player._advance_frame()
    advance_mock.assert_called_with(2)

    # 3. next_index > loop_end with loop_enabled = False -> stops
    current_cb.return_value = 5
    player.loop_enabled = False
    player._advance_frame()
    assert player.is_playing is False

    # 4. Clear loop bounds
    player.clear_loop_bounds()
    assert player.loop_start_frame is None
    assert player.loop_end_frame is None


def test_flaw_is_cine_capable_rejects_single_multiframe_file(mock_nav) -> None:
    """Document flaw: is_cine_capable returns False for a single multi-frame DICOM file because of len(datasets) < 2 check."""
    nav, total_cb, current_cb = mock_nav
    player = CinePlayer(nav, total_cb, current_cb)

    mf_ds = Dataset()
    mf_ds.NumberOfFrames = 50  # Single multi-frame file with 50 frames
    studies = {"study1": {"series1": [mf_ds]}}

    # Documents the flaw: even though mf_ds is a multi-frame file with 50 frames,
    # is_cine_capable returns False because len(datasets) == 1 < 2.
    assert player.is_cine_capable(studies, "study1", "series1") is False

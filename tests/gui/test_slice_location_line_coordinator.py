"""
Comprehensive unit tests for src/gui/slice_location_line_coordinator.py.

Achieves 100% statement and branch coverage for SliceLocationLineCoordinator.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QGraphicsScene

from gui.slice_location_line_coordinator import SliceLocationLineCoordinator
from gui.slice_location_line_manager import SliceLocationLineManager


@pytest.fixture
def scene(qapp) -> QGraphicsScene:
    """Fixture providing a PySide6 QGraphicsScene."""
    return QGraphicsScene()


@pytest.fixture
def mock_app() -> SimpleNamespace:
    """Fixture providing a mock DICOMViewerApp instance."""
    app = SimpleNamespace()
    app.config_manager = MagicMock()
    app.config_manager.get_slice_location_lines_visible.return_value = True
    app.config_manager.get_slice_location_lines_same_group_only.return_value = False
    app.config_manager.get_slice_location_lines_focused_only.return_value = False
    app.config_manager.get_slice_location_line_mode.return_value = "middle"
    app.config_manager.get_slice_location_line_width_px.return_value = 1
    app.multi_window_layout = MagicMock()
    app.focused_subwindow_index = -1
    return app


def test_init(mock_app: SimpleNamespace) -> None:
    """Test initialization of SliceLocationLineCoordinator."""
    coord = SliceLocationLineCoordinator(mock_app)
    assert coord.app is mock_app
    assert coord._managers == {}
    assert coord._refreshing is False
    assert coord._pending_refresh_all is False


def test_ensure_and_remove_manager(
    mock_app: SimpleNamespace, scene: QGraphicsScene
) -> None:
    """Test creating, attaching scene, and removing managers."""
    coord = SliceLocationLineCoordinator(mock_app)

    # 1. Create manager without scene
    mgr1 = coord.ensure_manager(0)
    assert isinstance(mgr1, SliceLocationLineManager)
    assert 0 in coord._managers

    # 2. Call ensure_manager on existing index with scene -> sets scene
    mgr1_again = coord.ensure_manager(0, scene)
    assert mgr1_again is mgr1
    assert mgr1.has_scene() is True

    # 3. Create manager with scene directly
    mgr2 = coord.ensure_manager(1, scene)
    assert mgr2.has_scene() is True

    # 4. Remove existing manager
    coord.remove_manager(0)
    assert 0 not in coord._managers

    # 5. Remove missing manager (no-op)
    coord.remove_manager(99)
    assert 99 not in coord._managers


def test_remove_manager_calls_clear(mock_app: SimpleNamespace) -> None:
    """Test that remove_manager calls clear() on the target manager."""
    coord = SliceLocationLineCoordinator(mock_app)
    mock_mgr = MagicMock()
    coord._managers[0] = mock_mgr

    coord.remove_manager(0)
    mock_mgr.clear.assert_called_once()
    assert 0 not in coord._managers


def test_config_helper_methods_fallback(qapp) -> None:
    """Test configuration helper methods when config_manager is None."""
    app_no_config = SimpleNamespace()
    app_no_config.config_manager = None
    coord = SliceLocationLineCoordinator(app_no_config)

    assert coord._is_visible() is False
    assert coord._get_same_group_only() is False
    assert coord._get_focused_only() is False
    assert coord._get_line_mode() == "middle"
    assert coord._get_line_width_px() == 1


def test_config_helper_methods_custom_values(mock_app: SimpleNamespace) -> None:
    """Test configuration helper methods with mock config_manager."""
    mock_app.config_manager.get_slice_location_lines_visible.return_value = True
    mock_app.config_manager.get_slice_location_lines_same_group_only.return_value = True
    mock_app.config_manager.get_slice_location_lines_focused_only.return_value = True
    mock_app.config_manager.get_slice_location_line_mode.return_value = "begin_end"
    mock_app.config_manager.get_slice_location_line_width_px.return_value = 3

    coord = SliceLocationLineCoordinator(mock_app)
    assert coord._is_visible() is True
    assert coord._get_same_group_only() is True
    assert coord._get_focused_only() is True
    assert coord._get_line_mode() == "begin_end"
    assert coord._get_line_width_px() == 3


def test_subwindow_container_helpers_no_layout(qapp) -> None:
    """Test container and subwindow list helpers when multi_window_layout is missing/None."""
    app_no_layout = SimpleNamespace()
    coord = SliceLocationLineCoordinator(app_no_layout)

    assert coord._get_subwindow_container(0) is None
    assert coord._get_all_subwindows() == []


def test_subwindow_container_helpers_with_layout(mock_app: SimpleNamespace) -> None:
    """Test container and subwindow list helpers with mock layout."""
    sub0 = SimpleNamespace(name="sub0")
    sub1 = SimpleNamespace(name="sub1")
    mock_app.multi_window_layout.get_all_subwindows.return_value = [sub0, sub1]

    coord = SliceLocationLineCoordinator(mock_app)
    assert coord._get_all_subwindows() == [sub0, sub1]
    assert coord._get_subwindow_container(0) is sub0
    assert coord._get_subwindow_container(1) is sub1
    # Out of bounds
    assert coord._get_subwindow_container(-1) is None
    assert coord._get_subwindow_container(2) is None


def test_clear_all_visible(mock_app: SimpleNamespace) -> None:
    """Test _clear_all_visible clears line items and hides managers."""
    coord = SliceLocationLineCoordinator(mock_app)
    mgr0 = MagicMock()
    mgr1 = MagicMock()
    coord._managers = {0: mgr0, 1: mgr1}

    coord._clear_all_visible()
    mgr0.update_lines.assert_called_once_with([])
    mgr0.set_visible.assert_called_once_with(False)
    mgr1.update_lines.assert_called_once_with([])
    mgr1.set_visible.assert_called_once_with(False)


def test_refresh_all_not_visible(mock_app: SimpleNamespace) -> None:
    """Test refresh_all when slice location lines are not visible."""
    mock_app.config_manager.get_slice_location_lines_visible.return_value = False
    coord = SliceLocationLineCoordinator(mock_app)
    with patch.object(coord, "_clear_all_visible") as mock_clear:
        coord.refresh_all()
        mock_clear.assert_called_once()


@patch("gui.slice_location_line_coordinator.get_slice_location_line_segments")
def test_refresh_all_visible_various_subwindows(
    mock_get_segments: MagicMock,
    mock_app: SimpleNamespace,
    scene: QGraphicsScene,
) -> None:
    """Test refresh_all iterating over subwindows with valid scenes, missing scenes, and None entries."""
    sub0 = SimpleNamespace(image_viewer=SimpleNamespace(scene=scene))
    sub1 = None  # None entry in subwindows list
    sub2 = SimpleNamespace(image_viewer=None)  # image_viewer is None
    sub3 = SimpleNamespace(
        image_viewer=SimpleNamespace()
    )  # image_viewer has no scene attr

    mock_app.multi_window_layout.get_all_subwindows.return_value = [
        sub0,
        sub1,
        sub2,
        sub3,
    ]
    mock_get_segments.return_value = [{"source_idx": 1, "points": []}]

    coord = SliceLocationLineCoordinator(mock_app)
    coord.refresh_all()

    # Managers should be created for non-None subwindows (0, 2, 3)
    assert 0 in coord._managers
    assert 1 not in coord._managers
    assert 2 in coord._managers
    assert 3 in coord._managers

    # sub0 has a scene, so get_slice_location_line_segments was called for subwindow 0
    mock_get_segments.assert_called_with(
        0, mock_app, only_same_group=False, mode="middle"
    )


def test_refresh_all_reentrant(mock_app: SimpleNamespace) -> None:
    """Test refresh_all coalesces reentrant refresh calls via _pending_refresh_all."""
    coord = SliceLocationLineCoordinator(mock_app)
    mock_app.config_manager.get_slice_location_lines_visible.return_value = True
    mock_app.multi_window_layout.get_all_subwindows.return_value = []

    first_pass = True

    def side_effect(*args, **kwargs):
        nonlocal first_pass
        if first_pass:
            first_pass = False
            # Trigger re-entrant refresh_all call while _refreshing is True
            coord.refresh_all()

    with patch.object(
        coord, "_get_same_group_only", side_effect=side_effect
    ) as mock_same_group:
        coord.refresh_all()
        # _get_same_group_only should be called twice (once for initial pass, once for pending pass)
        assert mock_same_group.call_count == 2


def test_refresh_all_exception_resets_refreshing_flag(
    mock_app: SimpleNamespace,
) -> None:
    """Test that an exception during refresh_all still resets _refreshing to False."""
    coord = SliceLocationLineCoordinator(mock_app)
    mock_app.config_manager.get_slice_location_lines_visible.return_value = True
    sub0 = SimpleNamespace(image_viewer=SimpleNamespace(scene=MagicMock()))
    mock_app.multi_window_layout.get_all_subwindows.return_value = [sub0]

    with patch(
        "gui.slice_location_line_coordinator.get_slice_location_line_segments",
        side_effect=RuntimeError("Parsing error"),
    ):
        with pytest.raises(RuntimeError, match="Parsing error"):
            coord.refresh_all()
        assert coord._refreshing is False


def test_refresh_for_subwindow_not_visible(mock_app: SimpleNamespace) -> None:
    """Test refresh_for_subwindow when lines are not visible."""
    mock_app.config_manager.get_slice_location_lines_visible.return_value = False
    coord = SliceLocationLineCoordinator(mock_app)

    with patch.object(coord, "_clear_all_visible") as mock_clear:
        coord.refresh_for_subwindow(0)
        mock_clear.assert_called_once()


def test_refresh_for_subwindow_initializes_missing_manager(mock_app: SimpleNamespace) -> None:
    """A public refresh must create the target manager when it is absent."""
    coord = SliceLocationLineCoordinator(mock_app)
    coord.refresh_for_subwindow(0)
    assert 0 in coord._managers


def test_refresh_for_subwindow_attaches_scene_from_container(
    mock_app: SimpleNamespace, scene: QGraphicsScene
) -> None:
    """Test _refresh_for_subwindow attaches scene from container if manager missing scene."""
    coord = SliceLocationLineCoordinator(mock_app)
    # Register manager without scene
    mgr = coord.ensure_manager(0)
    assert mgr.has_scene() is False

    sub0 = SimpleNamespace(image_viewer=SimpleNamespace(scene=scene))
    mock_app.multi_window_layout.get_all_subwindows.return_value = [sub0]

    with patch(
        "gui.slice_location_line_coordinator.get_slice_location_line_segments",
        return_value=[],
    ):
        coord._refresh_for_subwindow(0, False)
        assert mgr.has_scene() is True


def test_refresh_for_subwindow_no_scene_returns_early(
    mock_app: SimpleNamespace,
) -> None:
    """Test _refresh_for_subwindow returns early if manager still lacks a scene."""
    coord = SliceLocationLineCoordinator(mock_app)
    coord.ensure_manager(0)  # No scene

    sub0 = SimpleNamespace(image_viewer=None)
    mock_app.multi_window_layout.get_all_subwindows.return_value = [sub0]

    with patch(
        "gui.slice_location_line_coordinator.get_slice_location_line_segments"
    ) as mock_get_segments:
        coord._refresh_for_subwindow(0, False)
        mock_get_segments.assert_not_called()


@patch("gui.slice_location_line_coordinator.get_slice_location_line_segments")
def test_refresh_for_subwindow_focused_only_filter(
    mock_get_segments: MagicMock,
    mock_app: SimpleNamespace,
    scene: QGraphicsScene,
) -> None:
    """Test _refresh_for_subwindow with focused_only option enabled."""
    coord = SliceLocationLineCoordinator(mock_app)
    coord.ensure_manager(0, scene)

    mock_app.config_manager.get_slice_location_lines_focused_only.return_value = True

    segments_data = [
        {"source_idx": 0, "points": [1, 2]},
        {"source_idx": 1, "points": [3, 4]},
    ]
    mock_get_segments.return_value = segments_data

    # Case A: focused_subwindow_index >= 0 (e.g. 1) -> filters segments to source_idx == 1
    mock_app.focused_subwindow_index = 1
    with patch.object(coord._managers[0], "update_lines") as mock_update:
        coord._refresh_for_subwindow(0, False)
        mock_update.assert_called_once_with([{"source_idx": 1, "points": [3, 4]}], 1)

    # Case B: focused_subwindow_index < 0 (e.g. -1) -> segments set to empty list []
    mock_app.focused_subwindow_index = -1
    with patch.object(coord._managers[0], "update_lines") as mock_update:
        coord._refresh_for_subwindow(0, False)
        mock_update.assert_called_once_with([], 1)


def test_refresh_for_subwindow_drains_reentrant_pending_work(mock_app: SimpleNamespace) -> None:
    """A re-entrant public refresh must schedule the pending full refresh."""
    coord = SliceLocationLineCoordinator(mock_app)
    mock_app.config_manager.get_slice_location_lines_visible.return_value = True

    with (
        patch.object(coord, "_refresh_for_subwindow", side_effect=lambda *_: coord.refresh_for_subwindow(0)),
        patch.object(coord, "refresh_all") as refresh_all,
    ):
        coord.refresh_for_subwindow(0)

    refresh_all.assert_called_once()
    assert coord._pending_refresh_all is False


@patch(
    "gui.slice_location_line_coordinator.get_slice_location_line_segments",
    return_value=[],
)
def test_refresh_for_subwindow_visible(
    mock_get_segments: MagicMock,
    mock_app: SimpleNamespace,
    scene: QGraphicsScene,
) -> None:
    """Test public refresh_for_subwindow entry point when visible."""
    coord = SliceLocationLineCoordinator(mock_app)
    coord.ensure_manager(0, scene)
    mock_app.config_manager.get_slice_location_lines_visible.return_value = True

    coord.refresh_for_subwindow(0)
    mock_get_segments.assert_called_once_with(
        0, mock_app, only_same_group=False, mode="middle"
    )
    assert coord._refreshing is False

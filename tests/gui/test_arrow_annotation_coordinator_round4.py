"""Round-4 tests for ArrowAnnotationCoordinator: pure coordination / guard / error paths using fakes."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QGraphicsScene

from gui.arrow_annotation_coordinator import ArrowAnnotationCoordinator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeArrow:
    """Lightweight arrow stand-in that behaves like ArrowAnnotationItem for
    attribute presence checks but does NOT auto-create attributes."""

    def __init__(self, start=(0, 0), end=(100, 100), scene=None):
        self.start_point = QPointF(*start)
        self.end_point = QPointF(*end)
        self._scene = scene
        self._line_update_calls: list = []

    def scene(self):
        return self._scene

    def update_line_end_for_view_scale(self, viewer):
        self._line_update_calls.append(viewer)

    def isVisible(self):
        return True

    def show(self):
        pass


def _make_coord(
    *,
    scene=None,
    undo_redo_manager=None,
    update_undo_redo_callback=None,
    has_transform_signal=True,
    has_zoom_signal=True,
):
    """Build a coordinator wired to lightweight fakes."""
    tool = MagicMock()
    tool.arrows = {}
    viewer = MagicMock()
    viewer.scene = scene

    if not has_transform_signal:
        del viewer.transform_changed
    if not has_zoom_signal:
        del viewer.zoom_changed

    coord = ArrowAnnotationCoordinator(
        arrow_annotation_tool=tool,
        image_viewer=viewer,
        get_current_dataset=lambda: None,
        get_current_slice_index=lambda: 0,
        undo_redo_manager=undo_redo_manager,
        update_undo_redo_state_callback=update_undo_redo_callback,
    )
    return coord, tool, viewer


# -----------------------------------------------------------------------
# __init__ signal wiring
# -----------------------------------------------------------------------


@pytest.mark.qt
class TestInitSignalConnections:
    def test_connections_when_viewer_has_signals(self, qapp):
        coord, _, viewer = _make_coord()
        assert coord.image_viewer is viewer

    def test_no_connection_when_viewer_lacks_signals(self, qapp):
        tool = MagicMock()
        viewer = MagicMock(spec=[])  # no attributes
        coord = ArrowAnnotationCoordinator(
            arrow_annotation_tool=tool,
            image_viewer=viewer,
            get_current_dataset=lambda: None,
            get_current_slice_index=lambda: 0,
        )
        assert coord.image_viewer is viewer


# -----------------------------------------------------------------------
# _update_arrow_lines_for_view_scale
# -----------------------------------------------------------------------


@pytest.mark.qt
class TestUpdateArrowLinesForViewScale:
    def test_noop_when_scene_none(self, qapp):
        coord, tool, _ = _make_coord(scene=None)
        coord._update_arrow_lines_for_view_scale()
        # Early return — tool.arrows.values() never called

    def test_skips_arrow_on_different_scene(self, qapp):
        scene_a = QGraphicsScene()
        scene_b = QGraphicsScene()
        arrow = FakeArrow(scene=scene_b)
        coord, tool, _ = _make_coord(scene=scene_a)
        tool.arrows = {("s1", "s2", 0): [arrow]}
        coord._update_arrow_lines_for_view_scale()
        assert arrow._line_update_calls == []

    def test_updates_matching_arrow(self, qapp):
        scene = QGraphicsScene()
        arrow = FakeArrow(scene=scene)
        coord, tool, _ = _make_coord(scene=scene)
        tool.arrows = {("s1", "s2", 0): [arrow]}
        coord._update_arrow_lines_for_view_scale()
        assert arrow._line_update_calls == [coord.image_viewer]


@pytest.mark.qt
class TestOnZoomChangedForArrows:
    def test_delegates_to_update(self, qapp):
        coord, _, _ = _make_coord(scene=None)
        with patch.object(coord, "_update_arrow_lines_for_view_scale") as patched:
            coord._on_zoom_changed_for_arrows(1.5)
            patched.assert_called_once()


# -----------------------------------------------------------------------
# handle_arrow_annotation_started
# -----------------------------------------------------------------------


@pytest.mark.qt
class TestHandleArrowAnnotationStarted:
    def test_no_dataset(self, qapp):
        coord, tool, _ = _make_coord()
        coord.handle_arrow_annotation_started(QPointF(10, 10))
        tool.set_current_slice.assert_not_called()
        tool.start_arrow.assert_called_once_with(QPointF(10, 10))

    def test_with_dataset(self, qapp):
        from pydicom.dataset import Dataset

        ds = Dataset()
        ds.StudyInstanceUID = "1.2.3"
        ds.SeriesInstanceUID = "4.5.6"
        coord, tool, _ = _make_coord()
        coord.get_current_dataset = lambda: ds
        coord.get_current_slice_index = lambda: 7

        coord.handle_arrow_annotation_started(QPointF(5, 5))

        tool.set_current_slice.assert_called_once_with("1.2.3", "4.5.6", 7)
        tool.start_arrow.assert_called_once_with(QPointF(5, 5))


# -----------------------------------------------------------------------
# handle_arrow_annotation_updated
# -----------------------------------------------------------------------


@pytest.mark.qt
class TestHandleArrowAnnotationUpdated:
    def test_noop_when_scene_none(self, qapp):
        coord, tool, _ = _make_coord(scene=None)
        coord.handle_arrow_annotation_updated(QPointF(1, 1))
        tool.update_arrow.assert_not_called()

    def test_delegates_to_tool(self, qapp):
        scene = QGraphicsScene()
        coord, tool, _ = _make_coord(scene=scene)
        coord.handle_arrow_annotation_updated(QPointF(2, 2))
        tool.update_arrow.assert_called_once_with(QPointF(2, 2), scene)


# -----------------------------------------------------------------------
# handle_arrow_annotation_finished
# -----------------------------------------------------------------------


@pytest.mark.qt
class TestHandleArrowAnnotationFinished:
    def test_noop_when_scene_none(self, qapp):
        coord, tool, _ = _make_coord(scene=None)
        coord.handle_arrow_annotation_finished()
        tool.finish_arrow.assert_not_called()

    def test_noop_when_finish_returns_none(self, qapp):
        scene = QGraphicsScene()
        coord, tool, _ = _make_coord(scene=scene)
        tool.finish_arrow.return_value = None
        coord.handle_arrow_annotation_finished()
        tool.finish_arrow.assert_called_once_with(scene)

    def test_without_undo_redo_manager(self, qapp):
        scene = QGraphicsScene()
        arrow = FakeArrow(scene=scene)
        coord, tool, _ = _make_coord(scene=scene, undo_redo_manager=None)
        tool.finish_arrow.return_value = arrow

        coord.handle_arrow_annotation_finished()

        # Callbacks are set on the arrow
        assert hasattr(arrow, "on_moved_callback")
        assert arrow.on_moved_callback == coord._on_arrow_moved
        assert arrow.on_mouse_release_callback == coord._finalize_arrow_move
        # Arrow is tracked
        assert arrow in coord._arrow_move_tracking
        assert len(arrow._line_update_calls) == 1

    def test_with_undo_redo_manager_no_dataset(self, qapp):
        scene = QGraphicsScene()
        arrow = FakeArrow(scene=scene)
        mgr = MagicMock()
        mgr.undo_stack = []
        coord, tool, _ = _make_coord(scene=scene, undo_redo_manager=mgr)
        tool.finish_arrow.return_value = arrow

        with patch("utils.undo_redo.ArrowAnnotationCommand") as MockCmd:
            coord.handle_arrow_annotation_finished()
            MockCmd.assert_called_once()
            mgr.execute_command.assert_called_once()

    def test_with_undo_redo_manager_and_dataset(self, qapp):
        from pydicom.dataset import Dataset

        ds = Dataset()
        ds.StudyInstanceUID = "1.2.3"
        ds.SeriesInstanceUID = "4.5.6"
        scene = QGraphicsScene()
        arrow = FakeArrow(scene=scene)
        mgr = MagicMock()
        mgr.undo_stack = []
        cb = MagicMock()
        coord, tool, _ = _make_coord(
            scene=scene, undo_redo_manager=mgr, update_undo_redo_callback=cb
        )
        coord.get_current_dataset = lambda: ds
        coord.get_current_slice_index = lambda: 3
        tool.finish_arrow.return_value = arrow

        with patch("utils.undo_redo.ArrowAnnotationCommand") as MockCmd:
            coord.handle_arrow_annotation_finished()
            cmd_instance = MockCmd.return_value
            mgr.execute_command.assert_called_once_with(cmd_instance)
            cb.assert_called_once()

    def test_stores_initial_position_only_once(self, qapp):
        scene = QGraphicsScene()
        arrow = FakeArrow(scene=scene)
        coord, tool, _ = _make_coord(scene=scene)
        tool.finish_arrow.return_value = arrow

        coord.handle_arrow_annotation_finished()
        first_tracking = coord._arrow_move_tracking[arrow]
        # Call again — should not overwrite
        coord.handle_arrow_annotation_finished()
        assert coord._arrow_move_tracking[arrow] is first_tracking


# -----------------------------------------------------------------------
# handle_arrow_annotation_delete_requested
# -----------------------------------------------------------------------


@pytest.mark.qt
class TestHandleArrowAnnotationDeleteRequested:
    def test_noop_when_scene_none(self, qapp):
        coord, tool, _ = _make_coord(scene=None)
        coord.handle_arrow_annotation_delete_requested(MagicMock())
        tool.delete_arrow.assert_not_called()

    def test_with_undo_redo_manager(self, qapp):
        from pydicom.dataset import Dataset

        ds = Dataset()
        ds.StudyInstanceUID = "1.2.840.10008.1"
        ds.SeriesInstanceUID = "1.2.840.10008.2"
        scene = QGraphicsScene()
        arrow_item = MagicMock()
        mgr = MagicMock()
        mgr.undo_stack = []
        cb = MagicMock()
        coord, tool, _ = _make_coord(
            scene=scene, undo_redo_manager=mgr, update_undo_redo_callback=cb
        )
        coord.get_current_dataset = lambda: ds
        coord.get_current_slice_index = lambda: 5

        with patch("utils.undo_redo.ArrowAnnotationCommand") as MockCmd:
            coord.handle_arrow_annotation_delete_requested(arrow_item)
            MockCmd.assert_called_once()
            mgr.execute_command.assert_called_once()
            cb.assert_called_once()
        tool.delete_arrow.assert_not_called()

    def test_fallback_direct_deletion(self, qapp):
        scene = QGraphicsScene()
        arrow_item = MagicMock()
        coord, tool, _ = _make_coord(scene=scene, undo_redo_manager=None)
        coord.handle_arrow_annotation_delete_requested(arrow_item)
        tool.delete_arrow.assert_called_once_with(arrow_item, scene)


# -----------------------------------------------------------------------
# display_arrows_for_slice (deeper paths)
# -----------------------------------------------------------------------


@pytest.mark.qt
class TestDisplayArrowsForSlice:
    def test_sets_callbacks_and_stores_initial_position(self, qapp):
        scene = QGraphicsScene()
        arrow = FakeArrow(scene=scene)
        coord, tool, _ = _make_coord(scene=scene)
        tool.arrows = {("s1", "s2", 0): [arrow]}

        coord.display_arrows_for_slice("s1", "s2", 0)

        assert arrow.on_moved_callback == coord._on_arrow_moved
        assert arrow.on_mouse_release_callback == coord._finalize_arrow_move
        assert arrow in coord._arrow_move_tracking
        t = coord._arrow_move_tracking[arrow]
        assert t["initialized"] is True
        assert isinstance(t["initial_start"], QPointF)

    def test_does_not_overwrite_existing_tracking(self, qapp):
        scene = QGraphicsScene()
        arrow = FakeArrow(start=(5, 5), end=(50, 50), scene=scene)
        coord, tool, _ = _make_coord(scene=scene)
        coord._arrow_move_tracking[arrow] = {"initialized": True, "sentinel": True}
        tool.arrows = {("s1", "s2", 0): [arrow]}

        coord.display_arrows_for_slice("s1", "s2", 0)

        assert coord._arrow_move_tracking[arrow].get("sentinel") is True

    def test_noop_when_scene_none(self, qapp):
        coord, tool, _ = _make_coord(scene=None)
        tool.arrows = {("s1", "s2", 0): [MagicMock()]}
        coord.display_arrows_for_slice("s1", "s2", 0)
        tool.display_arrows_for_slice.assert_not_called()


# -----------------------------------------------------------------------
# clear_arrows_from_other_slices
# -----------------------------------------------------------------------


@pytest.mark.qt
class TestClearArrowsFromOtherSlices:
    def test_delegates_to_tool(self, qapp):
        scene = QGraphicsScene()
        coord, tool, _ = _make_coord(scene=scene)
        coord.clear_arrows_from_other_slices("s1", "s2", 0)
        tool.clear_arrows_from_other_slices.assert_called_once_with(
            "s1", "s2", 0, scene
        )

    def test_noop_when_scene_none(self, qapp):
        coord, tool, _ = _make_coord(scene=None)
        coord.clear_arrows_from_other_slices("s1", "s2", 0)
        tool.clear_arrows_from_other_slices.assert_not_called()


# -----------------------------------------------------------------------
# _on_arrow_moved
# -----------------------------------------------------------------------


@pytest.mark.qt
class TestOnArrowMoved:
    def test_noop_for_none_arrow(self, qapp):
        coord, _, _ = _make_coord()
        coord._on_arrow_moved(None)
        assert coord._arrow_move_tracking == {}

    def test_noop_when_programmatic_update(self, qapp):
        arrow = FakeArrow()
        arrow._updating_position = True
        coord, _, _ = _make_coord()
        coord._on_arrow_moved(arrow)
        assert arrow not in coord._arrow_move_tracking

    def test_first_move_with_pre_drag_positions(self, qapp):
        arrow = FakeArrow(start=(0, 0), end=(10, 10))
        arrow._pre_drag_start_point = QPointF(0, 0)
        arrow._pre_drag_end_point = QPointF(10, 10)
        arrow.start_point = QPointF(20, 20)
        arrow.end_point = QPointF(30, 30)
        coord, _, _ = _make_coord()
        coord._on_arrow_moved(arrow)
        t = coord._arrow_move_tracking[arrow]
        assert t["initial_start"] == QPointF(0, 0)
        assert t["initial_end"] == QPointF(10, 10)
        assert t["current_start"] == QPointF(20, 20)

    def test_first_move_with_pre_move_positions(self, qapp):
        arrow = FakeArrow(start=(0, 0), end=(10, 10))
        arrow._pre_move_start_point = QPointF(0, 0)
        arrow._pre_move_end_point = QPointF(10, 10)
        arrow.start_point = QPointF(15, 15)
        arrow.end_point = QPointF(25, 25)
        coord, _, _ = _make_coord()
        coord._on_arrow_moved(arrow)
        t = coord._arrow_move_tracking[arrow]
        assert t["initial_start"] == QPointF(0, 0)

    def test_first_move_no_pre_drag_no_pre_move(self, qapp):
        arrow = FakeArrow(start=(7, 7), end=(14, 14))
        coord, _, _ = _make_coord()
        coord._on_arrow_moved(arrow)
        t = coord._arrow_move_tracking[arrow]
        assert t["initial_start"] == QPointF(7, 7)

    def test_subsequent_move_updates_current(self, qapp):
        arrow = FakeArrow(start=(0, 0), end=(10, 10))
        coord, _, _ = _make_coord()
        # First move — establishes tracking
        coord._on_arrow_moved(arrow)
        # Update positions and call again
        arrow.start_point = QPointF(50, 50)
        arrow.end_point = QPointF(60, 60)
        coord._on_arrow_moved(arrow)
        t = coord._arrow_move_tracking[arrow]
        # initial unchanged
        assert t["initial_start"] == QPointF(0, 0)
        assert t["current_start"] == QPointF(50, 50)

    def test_exception_does_not_propagate(self, qapp):
        """Exception inside the try block is swallowed."""
        class _ExplodingArrow(FakeArrow):
            def __getattr__(self, name):
                if name == '_pre_move_start_point':
                    raise RuntimeError("boom")
                raise AttributeError(name)

        arrow = _ExplodingArrow()
        coord, _, _ = _make_coord()
        # _pre_move_start_point access triggers RuntimeError inside try/except
        coord._on_arrow_moved(arrow)


# -----------------------------------------------------------------------
# _finalize_arrow_move
# -----------------------------------------------------------------------


@pytest.mark.qt
class TestFinalizeArrowMove:
    def test_noop_when_not_tracked(self, qapp):
        coord, _, _ = _make_coord()
        untracked = MagicMock()
        coord._finalize_arrow_move(untracked)

    def test_returns_early_for_invalid_arrow(self, qapp):
        """Arrow in tracking but invalid (no start_point) → removes from tracking."""
        scene = QGraphicsScene()
        arrow = FakeArrow(scene=scene)
        coord, tool, _ = _make_coord(scene=scene)
        coord._arrow_move_tracking[arrow] = {
            "initial_start": QPointF(0, 0),
            "initial_end": QPointF(0, 0),
            "current_start": QPointF(0, 0),
            "current_end": QPointF(0, 0),
            "initialized": True,
        }
        # Invalidate
        delattr(arrow, "start_point")
        coord._finalize_arrow_move(arrow)
        # Arrow removed from tracking
        assert arrow not in coord._arrow_move_tracking

    def test_no_command_when_position_unchanged(self, qapp):
        scene = QGraphicsScene()
        arrow = FakeArrow(start=(10, 10), end=(20, 20), scene=scene)
        mgr = MagicMock()
        coord, tool, _ = _make_coord(scene=scene, undo_redo_manager=mgr)
        coord._arrow_move_tracking[arrow] = {
            "initial_start": QPointF(10, 10),
            "initial_end": QPointF(20, 20),
            "current_start": QPointF(10, 10),
            "current_end": QPointF(20, 20),
            "initialized": True,
        }
        coord._finalize_arrow_move(arrow)
        mgr.execute_command.assert_not_called()
        assert arrow not in coord._arrow_move_tracking

    def test_no_command_when_no_manager(self, qapp):
        scene = QGraphicsScene()
        arrow = FakeArrow(start=(0, 0), end=(10, 10), scene=scene)
        coord, tool, _ = _make_coord(scene=scene, undo_redo_manager=None)
        coord._arrow_move_tracking[arrow] = {
            "initial_start": QPointF(0, 0),
            "initial_end": QPointF(0, 0),
            "current_start": QPointF(50, 50),
            "current_end": QPointF(60, 60),
            "initialized": True,
        }
        coord._finalize_arrow_move(arrow)
        assert arrow not in coord._arrow_move_tracking

    def test_no_command_when_scene_becomes_none(self, qapp):
        arrow = FakeArrow(start=(0, 0), end=(10, 10))
        mgr = MagicMock()
        coord, tool, _ = _make_coord(scene=None, undo_redo_manager=mgr)
        coord._arrow_move_tracking[arrow] = {
            "initial_start": QPointF(0, 0),
            "initial_end": QPointF(0, 0),
            "current_start": QPointF(50, 50),
            "current_end": QPointF(60, 60),
            "initialized": True,
        }
        coord._finalize_arrow_move(arrow)
        mgr.execute_command.assert_not_called()

    def test_creates_command_on_position_change(self, qapp):
        scene = QGraphicsScene()
        arrow = FakeArrow(start=(0, 0), end=(10, 10), scene=scene)
        mgr = MagicMock()
        mgr.undo_stack = []
        cb = MagicMock()
        coord, tool, _ = _make_coord(
            scene=scene, undo_redo_manager=mgr, update_undo_redo_callback=cb
        )
        coord._arrow_move_tracking[arrow] = {
            "initial_start": QPointF(0, 0),
            "initial_end": QPointF(0, 0),
            "current_start": QPointF(50, 50),
            "current_end": QPointF(60, 60),
            "initialized": True,
        }
        with patch("utils.undo_redo.ArrowAnnotationMoveCommand") as MockCmd:
            coord._finalize_arrow_move(arrow)
            MockCmd.assert_called_once()
            mgr.execute_command.assert_called_once()
            cb.assert_called_once()

    def test_cleans_up_pre_drag_attributes(self, qapp):
        scene = QGraphicsScene()
        arrow = FakeArrow(start=(0, 0), end=(0, 0), scene=scene)
        arrow._pre_drag_start_point = QPointF(5, 5)
        arrow._pre_drag_end_point = QPointF(6, 6)
        coord, tool, _ = _make_coord(scene=scene)
        coord._arrow_move_tracking[arrow] = {
            "initial_start": QPointF(0, 0),
            "initial_end": QPointF(0, 0),
            "current_start": QPointF(0, 0),
            "current_end": QPointF(0, 0),
            "initialized": True,
        }
        coord._finalize_arrow_move(arrow)
        assert not hasattr(arrow, "_pre_drag_start_point")
        assert not hasattr(arrow, "_pre_drag_end_point")

    def test_removes_from_tracking_after_finalize(self, qapp):
        scene = QGraphicsScene()
        arrow = FakeArrow(start=(0, 0), end=(0, 0), scene=scene)
        coord, tool, _ = _make_coord(scene=scene)
        coord._arrow_move_tracking[arrow] = {
            "initial_start": QPointF(0, 0),
            "initial_end": QPointF(0, 0),
            "current_start": QPointF(0, 0),
            "current_end": QPointF(0, 0),
            "initialized": True,
        }
        coord._finalize_arrow_move(arrow)
        assert arrow not in coord._arrow_move_tracking

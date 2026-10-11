"""Drag encode → drop decode → app dispatch → controller, by stable view ID.

Real tile widget payload, real ``SubWindowContainer`` drop, real controller.
A drag names a view, never a pane: after the source pane is cleared or
replaced the drop moves the original view (wherever it now is) or does
nothing; it can never move whatever view now occupies the old pane.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from main_mixin_delegation_support import _stub_for
from mpr_lifecycle_harness import (
    _light_display,
    _make_controller,
    _make_result,
    _seed_mpr_pane,
    _signals,
)
from PySide6.QtCore import QByteArray, QMimeData, QPoint

from core.mpr_view_drag import MPR_VIEW_MIME, encode_view_drag
from gui.image_viewer import ImageViewer
from gui.mpr_thumbnail_widget import MprThumbnailWidget
from gui.sub_window_container import SubWindowContainer


def _tile_drag_mime(
    ctrl, view_id: int, pane_index: int | None = None, origin: str | None = None
) -> QMimeData:
    """The MIME a real tile of *ctrl* produces (``origin`` overrides the controller's token)."""
    tile = MprThumbnailWidget(view_id, pane_index)
    tile.set_origin(ctrl.drag_origin if origin is None else origin)
    tile._drag_start_pos = QPoint(0, 0)
    captured: list[QMimeData] = []
    drag = MagicMock()
    drag.setMimeData.side_effect = captured.append
    with patch("gui.mpr_thumbnail_widget.QDrag", return_value=drag):
        tile._start_drag()
    return captured[0]


def _drop(container: SubWindowContainer, mime: QMimeData) -> MagicMock:
    event = MagicMock()
    event.mimeData.return_value = mime
    container.dropEvent(event)
    return event


def _container(qapp, stub, pane: int) -> SubWindowContainer:
    viewer = ImageViewer()
    viewer.subwindow_index = pane
    container = SubWindowContainer(viewer)
    container.mpr_view_drop_requested.connect(stub._on_mpr_view_drop_requested)
    return container


@pytest.mark.qt
class TestDropDispatch:
    def test_drag_of_a_detached_view_attaches_exactly_that_view(self, qapp) -> None:
        ctrl, app = _make_controller()
        _seed_mpr_pane(app, 0, _make_result())
        _seed_mpr_pane(app, 1, _make_result())
        first, second = ctrl.attached_view_id(0), ctrl.attached_view_id(1)
        ctrl.detach_mpr_from_subwindow(0)
        ctrl.detach_mpr_from_subwindow(1)
        stub = _stub_for("MPRNavigationMixin", _mpr_controller=ctrl)
        target = _container(qapp, stub, 1)

        with _light_display(ctrl):
            event = _drop(target, _tile_drag_mime(ctrl, second))

        event.acceptProposedAction.assert_called_once()
        assert ctrl.attached_view_id(1) == second  # the dragged view, not the other detached one
        assert ctrl.detached_view_ids() == [first]

    def test_drag_of_an_attached_view_relocates_it_and_preserves_the_displaced_one(self, qapp) -> None:
        ctrl, app = _make_controller()
        fired = _signals(ctrl)
        _seed_mpr_pane(app, 0, _make_result())
        _seed_mpr_pane(app, 1, _make_result())
        mover, resident = ctrl.attached_view_id(0), ctrl.attached_view_id(1)
        stub = _stub_for("MPRNavigationMixin", _mpr_controller=ctrl)

        with _light_display(ctrl):
            _drop(_container(qapp, stub, 1), _tile_drag_mime(ctrl, mover, 0))

        assert ctrl.attached_view_id(1) == mover and ctrl.attached_view_id(0) is None
        assert ctrl.detached_view_ids() == [resident]
        assert fired == {"activated": [1], "cleared": [0], "detached": [1]}

    def test_stale_attached_drag_after_clear_window_moves_the_original_not_the_replacement(
        self, qapp
    ) -> None:
        ctrl, app = _make_controller()
        _seed_mpr_pane(app, 0, _make_result())
        original = ctrl.attached_view_id(0)
        stale_drag = _tile_drag_mime(ctrl, original, 0)  # drag started while it was in pane 0
        # Meanwhile pane 0 is cleared (view detaches) and a different MPR takes it.
        ctrl.detach_mpr_from_subwindow(0)
        with _light_display(ctrl):
            ctrl._activate_mpr(0, _make_result(), "Coronal")
        replacement = ctrl.attached_view_id(0)
        assert replacement not in (None, original)
        stub = _stub_for("MPRNavigationMixin", _mpr_controller=ctrl)

        with _light_display(ctrl):
            _drop(_container(qapp, stub, 1), stale_drag)

        assert ctrl.attached_view_id(1) == original  # the original view moved
        assert ctrl.attached_view_id(0) == replacement  # the replacement never moved

    def test_stale_attached_drag_after_the_view_moved_follows_the_view(self, qapp) -> None:
        ctrl, app = _make_controller()
        _seed_mpr_pane(app, 0, _make_result())
        view = ctrl.attached_view_id(0)
        stale_drag = _tile_drag_mime(ctrl, view, 0)
        stub = _stub_for("MPRNavigationMixin", _mpr_controller=ctrl)
        with _light_display(ctrl):
            ctrl.relocate_mpr_subwindow(0, 1)  # the view left pane 0 already
            _seed_mpr_pane(app, 0, _make_result())  # something else now lives in pane 0
            bystander = ctrl.attached_view_id(0)
            _drop(_container(qapp, stub, 0), stale_drag)  # drop back on pane 0

        assert ctrl.attached_view_id(0) == view and ctrl.attached_view_id(1) is None
        assert ctrl._registry.get_view(bystander).pane_index is None  # displaced, preserved

    def test_stale_drag_of_a_cleared_view_is_a_no_op(self, qapp) -> None:
        ctrl, app = _make_controller()
        fired = _signals(ctrl)
        _seed_mpr_pane(app, 0, _make_result())
        gone = ctrl.attached_view_id(0)
        stale_drag = _tile_drag_mime(ctrl, gone, 0)
        ctrl.clear_mpr(0)  # Clear MPR discards the view
        with _light_display(ctrl):
            ctrl._activate_mpr(0, _make_result(), "Coronal")
        replacement = ctrl.attached_view_id(0)
        fired["activated"].clear()
        fired["cleared"].clear()
        stub = _stub_for("MPRNavigationMixin", _mpr_controller=ctrl)

        with _light_display(ctrl):
            _drop(_container(qapp, stub, 1), stale_drag)

        assert ctrl.attached_view_id(0) == replacement and ctrl.attached_view_id(1) is None
        assert fired == {"activated": [], "cleared": [], "detached": []}

    @pytest.mark.parametrize(
        "payload",
        [
            b"0", b"1", b"-1",
            b'{"v":1,"op":"move","view":99}',
            b'{"v":1,"op":"move","view":1,"pane":0}',
            b'{"v":1,"op":"move","view":1}',  # no origin
            b'{"v":1,"op":"move","view":1,"origin":"short"}',
        ],
    )
    def test_foreign_or_malformed_drags_never_touch_a_view(self, qapp, payload) -> None:
        ctrl, app = _make_controller()
        _seed_mpr_pane(app, 0, _make_result())
        detached = ctrl.attached_view_id(0)
        ctrl.detach_mpr_from_subwindow(0)
        stub = _stub_for("MPRNavigationMixin", _mpr_controller=ctrl)
        mime = QMimeData()
        mime.setData(MPR_VIEW_MIME, QByteArray(payload))

        with _light_display(ctrl):
            _drop(_container(qapp, stub, 1), mime)

        assert ctrl.detached_view_ids() == [detached] and ctrl.attached_view_id(1) is None

    def test_a_valid_payload_for_an_unknown_view_is_a_no_op(self, qapp) -> None:
        ctrl, _app = _make_controller()
        stub = _stub_for("MPRNavigationMixin", _mpr_controller=ctrl)
        mime = QMimeData()
        mime.setData(MPR_VIEW_MIME, QByteArray(encode_view_drag(12345, ctrl.drag_origin)))
        with _light_display(ctrl):
            _drop(_container(qapp, stub, 1), mime)
        assert ctrl._registry.view_count == 0


@pytest.mark.qt
class TestForeignOrigin:
    """View IDs are only unique per controller: both processes allocate view 1."""

    def _two_controllers(self):
        ctrl_a, app_a = _make_controller()
        ctrl_b, app_b = _make_controller()
        return (ctrl_a, app_a), (ctrl_b, app_b)

    def test_controllers_have_distinct_opaque_origin_tokens(self) -> None:
        (a, _), (b, _) = self._two_controllers()
        assert a.drag_origin != b.drag_origin
        assert 16 <= len(a.drag_origin) <= 32
        assert a.drag_origin.isascii()

    def test_a_foreign_drag_with_a_colliding_view_id_does_not_move_the_destination_view(
        self, qapp
    ) -> None:
        (ctrl_a, app_a), (ctrl_b, app_b) = self._two_controllers()
        _seed_mpr_pane(app_a, 0, _make_result())
        _seed_mpr_pane(app_b, 0, _make_result())
        view_a, view_b = ctrl_a.attached_view_id(0), ctrl_b.attached_view_id(0)
        assert view_a == view_b == 1  # the collision this guards against
        fired = _signals(ctrl_b)
        foreign_drag = _tile_drag_mime(ctrl_a, view_a, 0)  # produced by controller A's tile
        stub_b = _stub_for("MPRNavigationMixin", _mpr_controller=ctrl_b)

        with _light_display(ctrl_b):
            event = _drop(_container(qapp, stub_b, 1), foreign_drag)

        event.acceptProposedAction.assert_called_once()  # structurally valid, so accepted...
        assert ctrl_b.attached_view_id(0) == view_b  # ...but destination view 1 never moved
        assert ctrl_b.attached_view_id(1) is None
        assert fired == {"activated": [], "cleared": [], "detached": []}

    def test_the_same_drag_is_honoured_by_its_own_controller(self, qapp) -> None:
        (ctrl_a, app_a), _ = self._two_controllers()
        _seed_mpr_pane(app_a, 0, _make_result())
        view = ctrl_a.attached_view_id(0)
        stub_a = _stub_for("MPRNavigationMixin", _mpr_controller=ctrl_a)
        with _light_display(ctrl_a):
            _drop(_container(qapp, stub_a, 1), _tile_drag_mime(ctrl_a, view, 0))
        assert ctrl_a.attached_view_id(1) == view

    def test_foreign_detached_drag_does_not_attach_a_destination_detached_view(self, qapp) -> None:
        (ctrl_a, app_a), (ctrl_b, app_b) = self._two_controllers()
        _seed_mpr_pane(app_a, 0, _make_result())
        _seed_mpr_pane(app_b, 0, _make_result())
        ctrl_b.detach_mpr_from_subwindow(0)  # destination view 1 is detached
        stub_b = _stub_for("MPRNavigationMixin", _mpr_controller=ctrl_b)
        with _light_display(ctrl_b):
            _drop(_container(qapp, stub_b, 1), _tile_drag_mime(ctrl_a, 1, None))
        assert ctrl_b.detached_view_ids() == [1] and ctrl_b.attached_view_id(1) is None

    def test_the_token_survives_close_all_and_view_ids_are_not_reused(self) -> None:
        ctrl, app = _make_controller()
        _seed_mpr_pane(app, 0, _make_result())
        token, old_view = ctrl.drag_origin, ctrl.attached_view_id(0)
        ctrl.release_all_mpr()
        _seed_mpr_pane(app, 0, _make_result())
        assert ctrl.drag_origin == token  # never regenerated or reset
        assert ctrl.attached_view_id(0) != old_view  # IDs are monotonic: no reuse under one token
